"""
Q012/Q051 — Leverage Table Recalibration
=========================================
原始 Phase 4 在 SPX≈1000 时代设计；当前 SPX 5400 下，原表会在 VIX>30 时
导致峰值 SPAN 占用 70%+ NLV，不可接受。

本研究目标：
设计一个对 SPX 水平鲁棒的 SPAN-budget cap，使峰值 SPAN 占用始终保持在
可接受范围内（≤ 30% NLV），同时保留 thesis 的核心机制（动态杠杆放大 theta）。

测试三个候选 leverage table 重设计：

V1 — 静态 SPAN cap：总 /ES SPAN ≤ 20% NLV，不分 VIX
V2 — VIX 分层 SPAN cap：低 VIX 严，高 VIX 略松（但仍 capped）
V3 — VIX 分层 + 绝对合约上限：保护极端情况下的 lot 集中

每个 V 在 STOP=3.5 + BSH 下重跑 Phase 4 完整体系，比较：
  Bootstrap 显著性
  AnnROE / Sortino
  峰值 SPAN 占比
  最差年份 / stress windows

如果 V1/V2/V3 中至少一个保持显著且峰值 SPAN 可控，则 thesis 可生产化。
"""
from __future__ import annotations

import math, sys
from pathlib import Path
from collections import defaultdict
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research.strategies.ES_puts.backtest import (
    _load_data, _trend, _make_row, _bp_per_contract,
    put_price, find_strike_for_delta,
    BacktestResult, PutTrade, PutPosition, BshPutPosition,
    TARGET_DELTA, PROFIT_TARGET, GAMMA_DTE, SPX_MULTIPLIER,
    WARMUP_DAYS, P3_DTE_SLOTS, P3_N_SLOTS,
    P3_INITIAL_EQUITY,
    BSH_WEEKLY_COST_PCT, BSH_MONTHLY_COST_PCT, BSH_VIX_THRESHOLD,
    TrendSignal,
)
from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.portfolio import DailyPortfolioRow
from backtest.run_bootstrap_ci import bootstrap_ci

START = "2000-01-01"

# Phase A SPAN model (inline)
ES_MULT       = 50.0
CALIB_VIX     = 19.0
CALIB_SPAN    = 20_529.0
CALIB_ES      = 5_400.0
SCAN_EXP      = 1.10
VOL_SHOCK     = 0.50

def _calibrate_base_scan() -> float:
    sigma0 = CALIB_VIX / 100.0
    k0     = find_strike_for_delta(CALIB_ES, 45, sigma0, 0.20, is_call=False)
    p0     = put_price(CALIB_ES, k0, 45, sigma0)
    target = CALIB_SPAN / ES_MULT
    lo, hi = 0.01, 0.35
    for _ in range(80):
        mid = (lo + hi) / 2.0
        ed  = CALIB_ES * (1 - mid)
        pdn = put_price(ed, k0, 45, sigma0 * 1.5)
        val = max(pdn - p0, 0.0) + p0
        if val < target: lo = mid
        else:            hi = mid
    return (lo + hi) / 2.0

_BASE_SCAN = _calibrate_base_scan()

def es_span_estimate(spx: float, vix: float, strike: float | None = None,
                     dte: int = 45, prem: float | None = None) -> float:
    """Per-contract /ES SPAN estimate via Phase A model.
    Uses SPX as /ES proxy; this is approximate but consistent with Phase A.
    """
    sigma = max(vix / 100.0, 0.01)
    if strike is None:
        strike = find_strike_for_delta(spx, dte, sigma, 0.20, is_call=False)
    if prem is None:
        prem = put_price(spx, strike, dte, sigma)
    scan_pct = _BASE_SCAN * (vix / CALIB_VIX) ** SCAN_EXP
    spx_dn = spx * (1 - scan_pct)
    prem_dn = put_price(spx_dn, strike, dte, sigma * (1 + VOL_SHOCK))
    return max(prem_dn - prem, 0.0) * ES_MULT + prem * ES_MULT


# ── Three leverage redesigns (SPAN-budget caps as fraction of NLV) ────────────

def v1_static_cap(vix: float) -> float:
    """V1: flat 20% NLV SPAN cap regardless of VIX."""
    return 0.20

def v2_tiered_cap(vix: float) -> float:
    """V2: VIX-tiered SPAN cap (12% / 15% / 20% / 25% / 30%)."""
    if vix < 15:   return 0.12
    if vix < 20:   return 0.15
    if vix < 30:   return 0.20
    if vix < 40:   return 0.25
    return 0.30

def v3_tiered_with_hard_cap(vix: float, equity: float) -> float:
    """V3: V2 cap, but additionally cap absolute SPAN at $150k regardless of NLV."""
    pct = v2_tiered_cap(vix)
    return min(pct, 150_000 / equity if equity > 0 else pct)


# ── Conservative redesigns (round 2) ─────────────────────────────────────────

def v4_very_conservative(vix: float) -> float:
    """V4: Very conservative SPAN cap: 6/8/10/12/15%."""
    if vix < 15:   return 0.06
    if vix < 20:   return 0.08
    if vix < 30:   return 0.10
    if vix < 40:   return 0.12
    return 0.15

def v5_moderate(vix: float) -> float:
    """V5: Moderate SPAN cap: 8/10/14/18/22%."""
    if vix < 15:   return 0.08
    if vix < 20:   return 0.10
    if vix < 30:   return 0.14
    if vix < 40:   return 0.18
    return 0.22

def v6_moderate_hard_cap(vix: float, equity: float) -> float:
    """V6: V5 with absolute $100k cap (tighter than V3's $150k)."""
    pct = v5_moderate(vix)
    return min(pct, 100_000 / equity if equity > 0 else pct)


# ── Parametrised Phase 4 with new leverage table ─────────────────────────────

def run_p4_with_leverage(
    leverage_fn: Callable,
    stop_mult: float = 3.5,
    label: str = "v",
) -> dict:
    """
    Phase 4 (BSH payoff) with new SPAN-budget leverage table.

    leverage_fn(vix) → max /ES SPAN as fraction of NLV
    Each slot is sized so total /ES SPAN across all open positions
    ≤ leverage_fn(vix) × NLV.
    """
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(START)]

    equity    = P3_INITIAL_EQUITY
    peak_eq   = P3_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions:  dict[int, PutPosition]  = {}
    bsh_puts:   list[BshPutPosition]    = []
    day_counter = 0
    bsh_cost_total = 0.0

    peak_span_pct = 0.0       # peak /ES SPAN as % of NLV ever observed
    peak_contracts = 0.0
    peak_span_dollars = 0.0
    span_pct_series = []      # daily /ES SPAN % of NLV

    for date, row in sim.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        sig = vix / 100.0
        spy = spx / 10.0
        dstr = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        day_counter += 1

        # BSH cost
        if day_counter % 21 == 0 and vix < BSH_VIX_THRESHOLD:
            cost = equity * BSH_MONTHLY_COST_PCT
            daily_pnl      -= cost
            bsh_cost_total += cost

        # Weekly BSH purchase
        if day_counter % 5 == 0:
            budget     = equity * BSH_WEEKLY_COST_PCT
            bsh_cost_total += budget
            bsh_dte    = 7 if vix > 20 else 30
            bsh_strike = spy * (0.90 if vix > 20 else 0.80)
            cost_per   = put_price(spy, bsh_strike, bsh_dte, sig)
            cost_usd   = cost_per * 100
            if cost_usd > 0.01:
                n_bsh = budget / cost_usd
                bsh_puts.append(BshPutPosition(
                    entry_date=dstr, spy_at_entry=spy, strike=bsh_strike,
                    expiry_dte=bsh_dte, contracts=n_bsh, prev_val=cost_per,
                    dte_spec=bsh_dte,
                ))

        # BSH MTM
        to_exp = []
        for i, bp in enumerate(bsh_puts):
            bp.expiry_dte -= 1
            cur = put_price(spy, bp.strike, max(bp.expiry_dte, 0), sig)
            daily_pnl += (cur - bp.prev_val) * bp.contracts * 100
            bp.prev_val = cur
            if bp.expiry_dte <= 0:
                to_exp.append(i)
        for i in reversed(to_exp):
            bsh_puts.pop(i)

        # SPAN budget for today
        if leverage_fn in (v3_tiered_with_hard_cap, v6_moderate_hard_cap):
            span_cap_pct = leverage_fn(vix, equity)
        else:
            span_cap_pct = leverage_fn(vix)
        span_budget = equity * span_cap_pct

        window      = full_spx[full_spx.index <= date].iloc[-200:]
        warmed      = len(window) >= WARMUP_DAYS
        trend_ok    = warmed and (_trend(window, spx) == TrendSignal.BULLISH)

        # Manage existing positions
        to_close = []
        for slot, pos in positions.items():
            pos.expiry_dte -= 1
            cur = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur) * pos.contracts * SPX_MULTIPLIER
            reason = None
            if   pos.expiry_dte <= GAMMA_DTE:    reason = "gamma_risk"
            elif cur >= pos.stop_premium:         reason = "stop_loss"
            elif cur <= pos.profit_premium:       reason = "profit_target"
            elif pos.expiry_dte <= 0:            reason = "expiry"
            if reason:
                pnl = (pos.entry_premium - cur) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=slot, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx,
                    entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur,
                    dte_at_entry=slot, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl,
                ))
                to_close.append(slot)
            else:
                pos.prev_val = cur
        for slot in to_close:
            del positions[slot]

        # Track current /ES SPAN (using Phase A re-mark for existing positions)
        current_span = sum(
            es_span_estimate(spx, vix, strike=p.strike, dte=max(p.expiry_dte,1),
                             prem=put_price(spx, p.strike, max(p.expiry_dte,1), sig)) * p.contracts
            for p in positions.values()
        )
        span_pct_now = current_span / equity if equity > 0 else 0
        span_pct_series.append(span_pct_now)
        if span_pct_now > peak_span_pct:
            peak_span_pct = span_pct_now
            peak_span_dollars = current_span

        # Open new positions respecting SPAN budget
        if warmed and trend_ok:
            current_span = sum(
                es_span_estimate(spx, vix, strike=p.strike,
                                 dte=max(p.expiry_dte,1),
                                 prem=put_price(spx, p.strike, max(p.expiry_dte,1), sig)) * p.contracts
                for p in positions.values()
            )
            span_room = span_budget - current_span

            for slot in P3_DTE_SLOTS:
                if slot in positions:
                    continue
                k    = find_strike_for_delta(spx, slot, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, slot, sig)
                if prem <= 0.5:
                    continue
                # Estimate SPAN cost of one contract
                slot_span = es_span_estimate(spx, vix, strike=k, dte=slot, prem=prem)
                if slot_span <= 0:
                    continue
                # Compute max contracts respecting span_room AND per-slot cap
                # Per-slot cap = budget / N_SLOTS (smooth distribution)
                per_slot_budget = span_budget / P3_N_SLOTS
                n_by_slot   = per_slot_budget / slot_span
                n_by_total  = span_room / slot_span
                n           = min(n_by_slot, n_by_total)
                if n < 0.1:
                    continue
                act_span = n * slot_span
                positions[slot] = PutPosition(
                    slot=slot, entry_date=dstr, expiry_dte=slot,
                    strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                    contracts=n, bp_used=n * _bp_per_contract(spx, k, prem),
                    stop_premium=prem * stop_mult,
                    profit_premium=prem * PROFIT_TARGET,
                    prev_val=prem,
                )
                span_room -= act_span

        peak_contracts = max(peak_contracts,
                             sum(p.contracts for p in positions.values()))
        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix,
                                         f"p4_{label}_stop{stop_mult}")
        daily_rows.append(dr)

    r = BacktestResult(phase=f"p4_{label}_stop{stop_mult}", mode="filtered")
    r.trades            = trades
    r.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    r.daily_rows        = daily_rows
    if len(trades) >= 10:
        r.bootstrap = bootstrap_ci([t.pnl for t in trades])

    return {
        "result":            r,
        "bsh_cost":          bsh_cost_total,
        "peak_contracts":    peak_contracts,
        "peak_span_pct":     peak_span_pct,
        "peak_span_dollars": peak_span_dollars,
        "median_span_pct":   float(np.median(span_pct_series)) if span_pct_series else 0.0,
        "p95_span_pct":      float(np.percentile(span_pct_series, 95)) if span_pct_series else 0.0,
    }


# ── Helper metrics ────────────────────────────────────────────────────────────

def sortino(daily_rows: list[DailyPortfolioRow]) -> float:
    eqs = [dr.end_equity for dr in daily_rows]
    if len(eqs) < 2: return 0.0
    rets = [(eqs[i] - eqs[i-1]) / eqs[i-1] for i in range(1, len(eqs))]
    neg = [r for r in rets if r < 0]
    if not neg: return float("inf")
    dd = (sum(r**2 for r in neg) / len(neg)) ** 0.5
    annr = (eqs[-1] / eqs[0]) ** (252 / len(rets)) - 1
    return annr / (dd * math.sqrt(252)) if dd > 0 else 0.0


def worst_year(trades):
    by_year = defaultdict(float)
    for t in trades:
        y = int(t.exit_date[:4]) if t.exit_date else int(t.entry_date[:4])
        by_year[y] += t.pnl
    if not by_year: return "—", 0
    wy = min(by_year, key=by_year.get)
    return str(wy), by_year[wy]


def stress_pnl(trades):
    out = {}
    for label, start, end in [("2008 GFC","2008-01-01","2009-06-30"),
                                ("2020 COVID","2020-01-01","2020-09-30"),
                                ("2022 Bear","2022-01-01","2022-12-31")]:
        ts, te = pd.Timestamp(start), pd.Timestamp(end)
        out[label] = round(sum(t.pnl for t in trades
                                if ts <= pd.Timestamp(t.entry_date) <= te), 0)
    return out


def genuine_maxdd(daily_rows, initial):
    peak = initial
    md = 0.0
    for dr in daily_rows:
        if dr.end_equity > peak: peak = dr.end_equity
        d = (peak - dr.end_equity) / peak * 100
        if d > md: md = d
    return md


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 76)
    print("Q012/Q051 — Leverage Table Recalibration")
    print("  Find a SPAN-budget cap that preserves thesis significance")
    print("  while keeping peak SPAN ≤ ~30% NLV")
    print("=" * 76)

    candidates = [
        ("V4 v.conserv 6-15%",    v4_very_conservative,  "v4"),
        ("V5 moderate 8-22%",     v5_moderate,           "v5"),
        ("V6 V5 + $100k cap",     v6_moderate_hard_cap,  "v6"),
    ]

    results = {}
    for desc, fn, tag in candidates:
        print(f"\n  Running {desc} (STOP=3.5 + BSH) …", flush=True)
        pack = run_p4_with_leverage(fn, stop_mult=3.5, label=tag)
        results[tag] = (desc, pack)
        r = pack["result"]
        sig = r.bootstrap.get("significant", False) if r.bootstrap else False
        print(f"    → {len(r.trades)} trades  "
              f"AnnROE {r.portfolio_metrics.get('ann_return',0)*100:+.2f}%  "
              f"peak SPAN {pack['peak_span_pct']*100:.1f}%  "
              f"{'✅ SIGNIFICANT' if sig else '❌'}")

    # ── Detail per candidate ──────────────────────────────────────────────────
    for tag, (desc, pack) in results.items():
        r  = pack["result"]
        t  = r.trades
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        ws = [x for x in t if x.pnl > 0]
        ss = [x for x in t if x.exit_reason == "stop_loss"]
        wy, wp = worst_year(t)
        sp = stress_pnl(t)
        gdd = genuine_maxdd(r.daily_rows, P3_INITIAL_EQUITY)
        srt = sortino(r.daily_rows)
        sig = bs.get("significant", False)

        print(f"\n{'━'*76}")
        print(f"  {desc}  STOP=3.5×")
        print(f"{'━'*76}")
        print(f"  Trades: {len(t)}  WR: {len(ws)/len(t)*100:.1f}%  Stop: {len(ss)/len(t)*100:.1f}%")
        print(f"  Avg P&L:    ${bs.get('mean',0):,.0f}/trade")
        print(f"  Total P&L:  ${sum(x.pnl for x in t):,.0f}")
        print(f"  Ann ROE:    {m.get('ann_return',0)*100:+.2f}%")
        print(f"  Sortino:    {srt:.3f}   Sharpe: {m.get('daily_sharpe',0):.3f}")
        print(f"  Max DD:     {gdd:.1f}%")
        print(f"  Worst trade:${min(x.pnl for x in t):,.0f}   Worst year: {wy} ${wp:,.0f}")
        print()
        print(f"  Bootstrap:  [{bs.get('ci_lo',0):+,.0f}, {bs.get('ci_hi',0):+,.0f}]"
              f"  {'✅ SIGNIFICANT' if sig else '❌ not significant'}")
        print()
        print(f"  Peak /ES SPAN:    ${pack['peak_span_dollars']:,.0f}  "
              f"({pack['peak_span_pct']*100:.1f}% NLV)")
        print(f"  P95 /ES SPAN:     {pack['p95_span_pct']*100:.1f}% NLV")
        print(f"  Median /ES SPAN:  {pack['median_span_pct']*100:.1f}% NLV")
        print(f"  Peak contracts:   {pack['peak_contracts']:.1f}")
        print()
        print(f"  Stress windows:")
        for w, pnl in sp.items():
            print(f"    {w:14s}  ${pnl:+,.0f}")

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n\n" + "=" * 76)
    print("RECALIBRATION SUMMARY")
    print("=" * 76)
    print(f"  {'Cfg':>4}  {'Description':>26}  {'AnnROE%':>8}  {'Sortino':>7}  "
          f"{'PeakSPAN%':>9}  {'PeakCtr':>7}  {'CI_lo':>8}  {'CI_hi':>8}  Sig")
    for tag, (desc, pack) in results.items():
        r  = pack["result"]
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        srt = sortino(r.daily_rows)
        sig = "✅" if bs.get("significant") else "❌"
        print(f"  {tag:>4}  {desc:>26}  "
              f"{m.get('ann_return',0)*100:>+8.2f}  {srt:>7.3f}  "
              f"{pack['peak_span_pct']*100:>9.1f}  {pack['peak_contracts']:>7.1f}  "
              f"{bs.get('ci_lo',0):>+8,.0f}  {bs.get('ci_hi',0):>+8,.0f}  {sig}")

    # ── Final verdict ─────────────────────────────────────────────────────────
    print("\n\n" + "=" * 76)
    print("FINAL PRODUCTION-VIABILITY VERDICT")
    print("=" * 76)

    # A candidate is production-viable if:
    # 1. Bootstrap CI significant
    # 2. Peak SPAN ≤ 35% NLV (allow some buffer above target)
    # 3. AnnROE > 0.5% (meaningful contribution)
    viable = []
    for tag, (desc, pack) in results.items():
        r  = pack["result"]
        bs = r.bootstrap or {}
        m  = r.portfolio_metrics
        sig         = bs.get("significant", False)
        peak_ok     = pack["peak_span_pct"] <= 0.35
        roe_ok      = m.get("ann_return", 0) >= 0.005
        if sig and peak_ok and roe_ok:
            viable.append((tag, desc, pack))

    if viable:
        print(f"\n  ✅ {len(viable)} configuration(s) production-viable:")
        for tag, desc, pack in viable:
            r = pack["result"]
            m = r.portfolio_metrics
            print(f"     {tag} ({desc})")
            print(f"        AnnROE: {m.get('ann_return',0)*100:+.2f}%   "
                  f"Peak SPAN: {pack['peak_span_pct']*100:.1f}%   "
                  f"Peak contracts: {pack['peak_contracts']:.1f}")
        print(f"\n  → THESIS PRODUCTION-VIABLE under recalibrated leverage table")
        print(f"  → Recommend most conservative viable config for DRAFT Spec")
    else:
        print(f"\n  ❌ No configuration meets all three production criteria:")
        print(f"     (significant + peak SPAN ≤ 35% NLV + AnnROE ≥ 0.5%)")
        print(f"  → THESIS NOT PRODUCTION-VIABLE without further redesign")
        print(f"  → Recommend: maintain 1-contract observation cell")

    print()


if __name__ == "__main__":
    run()
