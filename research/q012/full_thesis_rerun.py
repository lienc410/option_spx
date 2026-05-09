"""
Q012 / Q051 — Full-Thesis Rerun: VIX Dynamic Leverage + BSH
=============================================================
Option B: PM-authorised full-system validation.

Configurations tested:
  A. Dynamic leverage + STOP=3.0 + no BSH  (Phase 3 cost-only)
  B. Dynamic leverage + STOP=3.0 + BSH     (Phase 4)
  C. Dynamic leverage + STOP=3.5 + BSH
  D. Dynamic leverage + STOP=4.0 + BSH

Required outputs (PM-standing metrics pack):
  Ann ROE, MaxDD, Sortino, Bootstrap CI
  worst-year breakdown, stress windows (2008/2020/2022)
  BSH annual cost vs theta income
  peak contract exposure, worst trade, worst cluster

This is the only path that can validate the full /ES three-layer thesis.
"""
from __future__ import annotations

import math, sys, calendar
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import research.strategies.ES_puts.backtest as bt_mod
from research.strategies.ES_puts.backtest import (
    _load_data, _trend, _make_row, _bp_per_contract,
    put_price, find_strike_for_delta,
    BacktestResult, PutTrade, PutPosition, BshPutPosition,
    TARGET_DELTA, PROFIT_TARGET, GAMMA_DTE, SPX_MULTIPLIER,
    WARMUP_DAYS, P3_DTE_SLOTS, P3_N_SLOTS,
    P3_INITIAL_EQUITY, P3_LEVERAGE_TABLE,
    BSH_WEEKLY_COST_PCT, BSH_MONTHLY_COST_PCT, BSH_VIX_THRESHOLD,
    _max_bp_ceiling, TrendSignal,
)
from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.portfolio import DailyPortfolioRow
from backtest.run_bootstrap_ci import bootstrap_ci

START = "2000-01-01"
STRESS_WINDOWS = [
    ("2008 GFC",   "2008-01-01", "2009-06-30"),
    ("2020 COVID", "2020-01-01", "2020-09-30"),
    ("2022 Bear",  "2022-01-01", "2022-12-31"),
]


# ── Parametrised Phase 3 (cost-only BSH drag) ────────────────────────────────

def run_p3_dynamic(stop_mult: float, mode: str = "filtered") -> dict:
    """Phase 3: VIX leverage table, cost-only BSH, variable STOP."""
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(START)]

    equity    = P3_INITIAL_EQUITY
    peak_eq   = P3_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions:  dict[int, PutPosition]  = {}
    day_counter = 0
    bsh_cost_total = 0.0
    theta_income_total = 0.0
    peak_contracts = 0

    for date, row in sim.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        sig = vix / 100.0
        dstr = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        day_counter += 1

        # BSH cost drag
        if day_counter % 5 == 0:
            cost = equity * BSH_WEEKLY_COST_PCT
            daily_pnl   -= cost
            bsh_cost_total += cost
        if day_counter % 21 == 0 and vix < BSH_VIX_THRESHOLD:
            cost = equity * BSH_MONTHLY_COST_PCT
            daily_pnl   -= cost
            bsh_cost_total += cost

        bp_ceiling  = _max_bp_ceiling(vix)
        bp_per_slot = bp_ceiling / P3_N_SLOTS

        window   = full_spx[full_spx.index <= date].iloc[-200:]
        warmed   = len(window) >= WARMUP_DAYS
        trend_ok = True
        if mode == "filtered" and warmed:
            trend_ok = (_trend(window, spx) == TrendSignal.BULLISH)

        total_bp = sum(p.bp_used for p in positions.values())
        bp_room  = equity * bp_ceiling - total_bp

        to_close = []
        for slot, pos in positions.items():
            pos.expiry_dte -= 1
            cur = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur) * pos.contracts * SPX_MULTIPLIER
            reason = None
            if   pos.expiry_dte <= GAMMA_DTE:     reason = "gamma_risk"
            elif cur >= pos.stop_premium:          reason = "stop_loss"
            elif cur <= pos.profit_premium:        reason = "profit_target"
            elif pos.expiry_dte <= 0:             reason = "expiry"
            if reason:
                pnl = (pos.entry_premium - cur) * pos.contracts * SPX_MULTIPLIER
                if reason == "profit_target":
                    theta_income_total += pnl
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

        if warmed and trend_ok:
            total_bp = sum(p.bp_used for p in positions.values())
            bp_room  = equity * bp_ceiling - total_bp
            for slot in P3_DTE_SLOTS:
                if slot in positions:
                    continue
                k    = find_strike_for_delta(spx, slot, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, slot, sig)
                if prem <= 0.5:
                    continue
                slot_bp  = _bp_per_contract(spx, k, prem)
                n        = (equity * bp_per_slot) / slot_bp if slot_bp > 0 else 0.0
                act_bp   = n * slot_bp
                if act_bp > bp_room + 1:
                    continue
                positions[slot] = PutPosition(
                    slot=slot, entry_date=dstr, expiry_dte=slot,
                    strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                    contracts=n, bp_used=act_bp,
                    stop_premium=prem * stop_mult,
                    profit_premium=prem * PROFIT_TARGET,
                    prev_val=prem,
                )
                bp_room -= act_bp

        peak_contracts = max(peak_contracts, sum(p.contracts for p in positions.values()))
        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix,
                                         f"p3_{mode}_stop{stop_mult}")
        daily_rows.append(dr)

    r = BacktestResult(phase=f"p3_{mode}_stop{stop_mult}", mode=mode)
    r.trades            = trades
    r.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    r.daily_rows        = daily_rows
    if len(trades) >= 10:
        r.bootstrap = bootstrap_ci([t.pnl for t in trades])

    return {"result": r, "bsh_cost": bsh_cost_total,
            "theta_income": theta_income_total, "peak_contracts": peak_contracts}


# ── Parametrised Phase 4 (full BSH payoff) ───────────────────────────────────

def run_p4_dynamic(stop_mult: float, mode: str = "filtered") -> dict:
    """Phase 4: VIX leverage table + full BSH payoff + variable STOP."""
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
    peak_contracts = 0.0

    for date, row in sim.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        sig = vix / 100.0
        spy = spx / 10.0
        dstr = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        day_counter += 1

        if day_counter % 21 == 0 and vix < BSH_VIX_THRESHOLD:
            cost = equity * BSH_MONTHLY_COST_PCT
            daily_pnl      -= cost
            bsh_cost_total += cost

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

        bp_ceiling  = _max_bp_ceiling(vix)
        bp_per_slot = bp_ceiling / P3_N_SLOTS
        window      = full_spx[full_spx.index <= date].iloc[-200:]
        warmed      = len(window) >= WARMUP_DAYS
        trend_ok    = True
        if mode == "filtered" and warmed:
            trend_ok = (_trend(window, spx) == TrendSignal.BULLISH)

        to_close = []
        for slot, pos in positions.items():
            pos.expiry_dte -= 1
            cur = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur) * pos.contracts * SPX_MULTIPLIER
            reason = None
            if   pos.expiry_dte <= GAMMA_DTE:     reason = "gamma_risk"
            elif cur >= pos.stop_premium:          reason = "stop_loss"
            elif cur <= pos.profit_premium:        reason = "profit_target"
            elif pos.expiry_dte <= 0:             reason = "expiry"
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

        if warmed and trend_ok:
            total_bp = sum(p.bp_used for p in positions.values())
            bp_room  = equity * bp_ceiling - total_bp
            for slot in P3_DTE_SLOTS:
                if slot in positions:
                    continue
                k    = find_strike_for_delta(spx, slot, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, slot, sig)
                if prem <= 0.5:
                    continue
                slot_bp = _bp_per_contract(spx, k, prem)
                n       = (equity * bp_per_slot) / slot_bp if slot_bp > 0 else 0.0
                act_bp  = n * slot_bp
                if act_bp > bp_room + 1:
                    continue
                positions[slot] = PutPosition(
                    slot=slot, entry_date=dstr, expiry_dte=slot,
                    strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                    contracts=n, bp_used=act_bp,
                    stop_premium=prem * stop_mult,
                    profit_premium=prem * PROFIT_TARGET,
                    prev_val=prem,
                )
                bp_room -= act_bp

        peak_contracts = max(peak_contracts,
                             sum(p.contracts for p in positions.values()))
        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix,
                                         f"p4_{mode}_stop{stop_mult}")
        daily_rows.append(dr)

    r = BacktestResult(phase=f"p4_{mode}_stop{stop_mult}", mode=mode)
    r.trades            = trades
    r.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    r.daily_rows        = daily_rows
    if len(trades) >= 10:
        r.bootstrap = bootstrap_ci([t.pnl for t in trades])

    return {"result": r, "bsh_cost": bsh_cost_total,
            "peak_contracts": peak_contracts}


# ── Metrics helpers ───────────────────────────────────────────────────────────

def sortino(daily_rows: list[DailyPortfolioRow]) -> float:
    equities = [dr.end_equity for dr in daily_rows]
    if len(equities) < 2:
        return 0.0
    rets = [(equities[i] - equities[i-1]) / equities[i-1]
            for i in range(1, len(equities))]
    neg = [r for r in rets if r < 0]
    if not neg:
        return float("inf")
    down_dev = (sum(r**2 for r in neg) / len(neg)) ** 0.5
    ann_ret  = (equities[-1] / equities[0]) ** (252 / len(rets)) - 1
    return ann_ret / (down_dev * math.sqrt(252)) if down_dev > 0 else 0.0


def worst_year(trades: list[PutTrade]) -> tuple[str, float]:
    by_year: dict[int, float] = defaultdict(float)
    for t in trades:
        y = int(t.exit_date[:4]) if t.exit_date else int(t.entry_date[:4])
        by_year[y] += t.pnl
    if not by_year:
        return "—", 0.0
    wy = min(by_year, key=by_year.get)
    return str(wy), by_year[wy]


def stress_pnl(trades: list[PutTrade]) -> dict[str, float]:
    result = {}
    for label, start, end in STRESS_WINDOWS:
        ts, te = pd.Timestamp(start), pd.Timestamp(end)
        pnl = sum(
            t.pnl for t in trades
            if ts <= pd.Timestamp(t.entry_date) <= te
        )
        result[label] = round(pnl, 0)
    return result


def worst_cluster(trades: list[PutTrade], window: int = 5) -> float:
    """Worst rolling-5-trade P&L sum."""
    pnls = [t.pnl for t in trades]
    if len(pnls) < window:
        return min(pnls) if pnls else 0.0
    return min(sum(pnls[i:i+window]) for i in range(len(pnls) - window + 1))


def genuine_maxdd(daily_rows: list[DailyPortfolioRow], initial: float) -> float:
    """Max drawdown from initial capital (avoids BSH-inflated peak artifact)."""
    peak = initial
    max_dd = 0.0
    for dr in daily_rows:
        eq = dr.end_equity
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


def bsh_vs_theta(bsh_cost: float, trades: list[PutTrade]) -> tuple[float, float]:
    """Annual BSH cost and annual theta income, both in dollars."""
    years = 26.0  # 2000–2026
    theta = sum(t.pnl for t in trades if t.exit_reason == "profit_target")
    return bsh_cost / years, theta / years


# ── Main ─────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 72)
    print("Q012/Q051 — Full-Thesis Rerun: Dynamic Leverage + BSH")
    print(f"  Window: {START}→today   Initial equity: ${P3_INITIAL_EQUITY:,.0f}")
    print("=" * 72)

    configs = [
        ("A", "P3 cost-only", "p3", 3.0),
        ("B", "P4 + BSH",     "p4", 3.0),
        ("C", "P4 + BSH",     "p4", 3.5),
        ("D", "P4 + BSH",     "p4", 4.0),
    ]

    results = {}
    for tag, label, phase, stop in configs:
        print(f"\n  Running Config {tag}: {label} STOP={stop}× …", flush=True)
        if phase == "p3":
            pack = run_p3_dynamic(stop)
        else:
            pack = run_p4_dynamic(stop)
        results[tag] = (label, stop, pack)
        r = pack["result"]
        t = r.trades
        print(f"    → {len(t)} trades  "
              f"bootstrap: {r.bootstrap.get('ci_lo',0):+,.0f} to "
              f"{r.bootstrap.get('ci_hi',0):+,.0f}  "
              f"{'✅ SIGNIFICANT' if r.bootstrap.get('significant') else '❌'}")

    # ── Full report ───────────────────────────────────────────────────────────
    print("\n\n" + "=" * 72)
    print("FULL METRICS PACK")
    print("=" * 72)

    for tag, (label, stop, pack) in results.items():
        r  = pack["result"]
        t  = r.trades
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        ws = [x for x in t if x.pnl > 0]
        ss = [x for x in t if x.exit_reason == "stop_loss"]
        wy_yr, wy_pnl = worst_year(t)
        sp = stress_pnl(t)
        wc = worst_cluster(t)
        gdd = genuine_maxdd(r.daily_rows, P3_INITIAL_EQUITY)
        bsh_ann, theta_ann = bsh_vs_theta(pack.get("bsh_cost", 0), t)
        srt = sortino(r.daily_rows)
        n_years = 26.0

        sig = bs.get("significant", False)
        print(f"\n{'━'*72}")
        print(f"  Config {tag} — {label}  STOP={stop}×")
        print(f"{'━'*72}")
        print(f"  Trades:         {len(t)}   WR: {len(ws)/len(t)*100:.1f}%   Stop: {len(ss)/len(t)*100:.1f}%")
        print(f"  Avg P&L/trade:  ${bs.get('mean', sum(x.pnl for x in t)/len(t) if t else 0):,.0f}")
        print(f"  Total P&L:      ${sum(x.pnl for x in t):,.0f}")
        print(f"  Ann ROE:        {m.get('ann_return',0)*100:.2f}%")
        print(f"  Sharpe (daily): {m.get('daily_sharpe',0):.3f}")
        print(f"  Sortino:        {srt:.3f}")
        print(f"  Max DD:         {gdd:.1f}%  (from initial capital)")
        print(f"  Worst trade:    ${min(x.pnl for x in t):,.0f}" if t else "")
        print(f"  Worst 5-cluster:${wc:,.0f}")
        print(f"  Worst year:     {wy_yr}  ${wy_pnl:,.0f}")
        print()
        print(f"  Bootstrap CI:   [{bs.get('ci_lo',0):+,.0f}, {bs.get('ci_hi',0):+,.0f}]"
              f"  {'✅ SIGNIFICANT' if sig else '❌ not significant'}")
        print()
        print(f"  Stress windows:")
        for w, pnl in sp.items():
            print(f"    {w:14s}  ${pnl:+,.0f}")
        print()
        if pack.get("bsh_cost", 0) > 0:
            print(f"  BSH annual cost:  ${bsh_ann:,.0f}/yr")
            print(f"  Theta income:     ${theta_ann:,.0f}/yr  "
                  f"(profit-target exits only)")
            ratio = bsh_ann / theta_ann if theta_ann > 0 else float("inf")
            print(f"  BSH/theta ratio:  {ratio:.2f}×  "
                  f"({'✅ BSH <50% of theta' if ratio < 0.5 else '⚠️ BSH >50% of theta' if ratio < 1.0 else '❌ BSH > theta'})")
        print(f"  Peak contracts:   {pack.get('peak_contracts',0):.1f}")

    # ── Summary comparison ────────────────────────────────────────────────────
    print("\n\n" + "=" * 72)
    print("SUMMARY TABLE")
    print("=" * 72)
    print(f"  {'Cfg':>4}  {'Label':>18}  {'STOP':>5}  {'n':>5}  {'AnnROE%':>8}  "
          f"{'Sharpe':>7}  {'Sortino':>8}  {'MaxDD%':>7}  {'CI_lo':>8}  {'CI_hi':>8}  Sig")
    for tag, (label, stop, pack) in results.items():
        r  = pack["result"]
        t  = r.trades
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        gdd = genuine_maxdd(r.daily_rows, P3_INITIAL_EQUITY)
        srt = sortino(r.daily_rows)
        sig = "✅" if bs.get("significant") else "❌"
        print(f"  {tag:>4}  {label:>18}  {stop:>5.1f}  {len(t):>5}  "
              f"{m.get('ann_return',0)*100:>8.2f}  "
              f"{m.get('daily_sharpe',0):>7.3f}  {srt:>8.3f}  {gdd:>7.1f}  "
              f"{bs.get('ci_lo',0):>+8,.0f}  {bs.get('ci_hi',0):>+8,.0f}  {sig}")

    # ── Final thesis verdict ──────────────────────────────────────────────────
    print("\n\n" + "=" * 72)
    print("FINAL THESIS VERDICT")
    print("=" * 72)
    any_sig = any(
        results[tag][2]["result"].bootstrap.get("significant", False)
        for tag in results
    )
    best_tag = max(
        results,
        key=lambda tag: results[tag][2]["result"].portfolio_metrics.get("ann_return", 0)
    )
    best_label, best_stop, best_pack = results[best_tag]
    best_r  = best_pack["result"]
    best_bs = best_r.bootstrap or {}

    if any_sig:
        sig_configs = [
            tag for tag in results
            if results[tag][2]["result"].bootstrap.get("significant", False)
        ]
        print(f"\n  ✅ Bootstrap significance achieved in: {', '.join('Config '+t for t in sig_configs)}")
        print(f"  → THESIS ALIVE under dynamic leverage + BSH")
        print(f"  → Full-system form is required; 1-contract cell is insufficient")
    else:
        best_lo = best_bs.get("ci_lo", -999)
        print(f"\n  ❌ No configuration achieved bootstrap significance.")
        print(f"  Best CI: Config {best_tag} ({best_label} STOP={best_stop}) "
              f"[{best_lo:+,.0f}, {best_bs.get('ci_hi',0):+,.0f}]")
        print(f"  → THESIS NOT VALIDATED under current production-aligned parameters")
        print(f"  → Recommend: reclassify /ES as low-priority observation cell")
        print(f"  → Q041 remains primary BP deployment efficiency axis")

    print()


if __name__ == "__main__":
    run()
