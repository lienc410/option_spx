"""
Q012 — Step 1: STOP_MULT Sensitivity  +  Step 2: Phase 4 BSH Rerun
====================================================================
2nd Quant 建议执行的两步验证：

Step 1 — Phase 2 filtered STOP sensitivity (3.0 / 3.5 / 4.0)
  回答：thesis 是否对 stop 执行假设过度敏感？

Step 2 — Phase 4 BSH payoff，1 合约/槽，STOP grid 同 Step 1
  回答：BSH 是否能让 thesis 不再依赖 STOP_MULT 的精确选择？

Step 3 — 2 合约 diagnostic（仅诊断，不作 production routing）
  回答：统计弱结果是否主要来自 1 合约的信噪比问题？
"""
from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

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
    WARMUP_DAYS, P2_DTE_SLOTS, P2_INITIAL_EQUITY,
    P3_DTE_SLOTS, P3_N_SLOTS, P3_INITIAL_EQUITY,
    BSH_WEEKLY_COST_PCT, BSH_MONTHLY_COST_PCT, BSH_VIX_THRESHOLD,
    _max_bp_ceiling, TrendSignal,
)
from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.portfolio import DailyPortfolioRow
from backtest.run_bootstrap_ci import bootstrap_ci

START = "2000-01-01"
STRESS_WINDOWS = [
    ("2008 GFC",    "2008-01-01", "2009-06-30"),
    ("2020 COVID",  "2020-01-01", "2020-09-30"),
    ("2022 Bear",   "2022-01-01", "2022-12-31"),
]


# ── Step 1: Phase 2 filtered with variable STOP_MULT ─────────────────────────

def run_p2_filtered_stop(stop_mult: float, n_contracts: int = 1) -> BacktestResult:
    """Phase 2 filtered with configurable STOP_MULT and per-slot contract count."""
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(START)]

    result    = BacktestResult(phase=f"p2_filtered_stop{stop_mult}", mode="filtered")
    equity    = P2_INITIAL_EQUITY
    peak_eq   = P2_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions:  dict[int, PutPosition]  = {}

    for date, row in sim.iterrows():
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sig   = vix / 100.0
        dstr  = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0

        window   = full_spx[full_spx.index <= date].iloc[-200:]
        warmed   = len(window) >= WARMUP_DAYS
        trend_ok = warmed and (_trend(window, spx) == TrendSignal.BULLISH)

        to_close = []
        for slot, pos in positions.items():
            pos.expiry_dte -= 1
            cur_val    = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur_val) * pos.contracts * SPX_MULTIPLIER
            reason = None
            if   pos.expiry_dte <= GAMMA_DTE:           reason = "gamma_risk"
            elif cur_val >= pos.stop_premium:            reason = "stop_loss"
            elif cur_val <= pos.profit_premium:          reason = "profit_target"
            elif pos.expiry_dte <= 0:                   reason = "expiry"
            if reason:
                pnl = (pos.entry_premium - cur_val) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=slot, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx,
                    entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur_val,
                    dte_at_entry=slot, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl,
                ))
                to_close.append(slot)
            else:
                pos.prev_val = cur_val
        for slot in to_close:
            del positions[slot]

        if warmed and trend_ok:
            for slot in P2_DTE_SLOTS:
                if slot in positions:
                    continue
                k    = find_strike_for_delta(spx, slot, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, slot, sig)
                if prem > 0.5:
                    n = float(n_contracts)
                    positions[slot] = PutPosition(
                        slot=slot, entry_date=dstr, expiry_dte=slot,
                        strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                        contracts=n, bp_used=n * _bp_per_contract(spx, k, prem),
                        stop_premium=prem * stop_mult,
                        profit_premium=prem * PROFIT_TARGET,
                        prev_val=prem,
                    )

        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix,
                                         f"p2_filt_stop{stop_mult}")
        daily_rows.append(dr)

    result.trades            = trades
    result.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    result.daily_rows        = daily_rows
    if len(trades) >= 10:
        result.bootstrap = bootstrap_ci([t.pnl for t in trades])
    return result


# ── Step 2: Phase 4 BSH with 1 contract/slot + variable STOP_MULT ────────────

def run_p4_bsh_production(stop_mult: float, n_contracts: int = 1) -> BacktestResult:
    """
    Phase 4 BSH payoff, production-aligned sizing (fixed n_contracts/slot).
    Keeps BSH cost + payoff modeling from original Phase 4.
    Removes VIX leverage table; uses fixed slots like Phase 2.
    """
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(START)]

    result    = BacktestResult(phase=f"p4_bsh_stop{stop_mult}", mode="filtered")
    equity    = P3_INITIAL_EQUITY
    peak_eq   = P3_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions:  dict[int, PutPosition]  = {}
    bsh_puts:   list[BshPutPosition]    = []

    day_counter = 0

    for date, row in sim.iterrows():
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sig   = vix / 100.0
        spy   = spx / 10.0
        dstr  = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        day_counter += 1

        # Monthly VIX call cost (cost-only)
        if day_counter % 21 == 0 and vix < BSH_VIX_THRESHOLD:
            daily_pnl -= equity * BSH_MONTHLY_COST_PCT

        # Weekly BSH SPY put purchase
        if day_counter % 5 == 0:
            budget     = equity * BSH_WEEKLY_COST_PCT
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

        # BSH daily MTM + expiry
        to_expire = []
        for i, bp in enumerate(bsh_puts):
            bp.expiry_dte -= 1
            cur_val    = put_price(spy, bp.strike, max(bp.expiry_dte, 0), sig)
            daily_pnl += (cur_val - bp.prev_val) * bp.contracts * 100
            bp.prev_val = cur_val
            if bp.expiry_dte <= 0:
                to_expire.append(i)
        for i in reversed(to_expire):
            bsh_puts.pop(i)

        # Trend filter
        window   = full_spx[full_spx.index <= date].iloc[-200:]
        warmed   = len(window) >= WARMUP_DAYS
        trend_ok = warmed and (_trend(window, spx) == TrendSignal.BULLISH)

        # Manage short put positions
        to_close = []
        for slot, pos in positions.items():
            pos.expiry_dte -= 1
            cur_val    = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur_val) * pos.contracts * SPX_MULTIPLIER
            reason = None
            if   pos.expiry_dte <= GAMMA_DTE:          reason = "gamma_risk"
            elif cur_val >= pos.stop_premium:           reason = "stop_loss"
            elif cur_val <= pos.profit_premium:         reason = "profit_target"
            elif pos.expiry_dte <= 0:                  reason = "expiry"
            if reason:
                pnl = (pos.entry_premium - cur_val) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=slot, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx,
                    entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur_val,
                    dte_at_entry=slot, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl,
                ))
                to_close.append(slot)
            else:
                pos.prev_val = cur_val
        for slot in to_close:
            del positions[slot]

        # Open new short put positions (production-aligned: fixed contracts)
        if warmed and trend_ok:
            for slot in P3_DTE_SLOTS:
                if slot in positions:
                    continue
                k    = find_strike_for_delta(spx, slot, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, slot, sig)
                if prem > 0.5:
                    n = float(n_contracts)
                    positions[slot] = PutPosition(
                        slot=slot, entry_date=dstr, expiry_dte=slot,
                        strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                        contracts=n, bp_used=n * _bp_per_contract(spx, k, prem),
                        stop_premium=prem * stop_mult,
                        profit_premium=prem * PROFIT_TARGET,
                        prev_val=prem,
                    )

        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix,
                                         f"p4_bsh_stop{stop_mult}")
        daily_rows.append(dr)

    result.trades            = trades
    result.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    result.daily_rows        = daily_rows
    if len(trades) >= 10:
        result.bootstrap = bootstrap_ci([t.pnl for t in trades])
    return result


# ── Reporting ─────────────────────────────────────────────────────────────────

def _stress_pnl(trades: list, windows: list) -> dict:
    """Sum PnL for each stress window."""
    out = {}
    for label, start, end in windows:
        ts = pd.Timestamp(start)
        te = pd.Timestamp(end)
        pnl = sum(
            t.pnl for t in trades
            if ts <= pd.Timestamp(t.entry_date) <= te
        )
        out[label] = round(pnl, 0)
    return out


def report(label: str, r: BacktestResult) -> None:
    t  = r.trades
    if not t:
        print(f"  {label}: no trades")
        return
    ws = [x for x in t if x.pnl > 0]
    ss = [x for x in t if x.exit_reason == "stop_loss"]
    m  = r.portfolio_metrics
    bs = r.bootstrap or {}
    pnls = [x.pnl for x in t]

    sig   = bs.get("significant", False)
    ci_lo = bs.get("ci_lo", float("nan"))
    ci_hi = bs.get("ci_hi", float("nan"))
    sig_marker = "✅" if sig else "❌"

    print(f"\n  {'─'*60}")
    print(f"  {label}")
    print(f"  {'─'*60}")
    print(f"  Trades: {len(t)}   WR: {len(ws)/len(t)*100:.1f}%   Stop: {len(ss)/len(t)*100:.1f}%")
    print(f"  Avg P&L:  ${bs.get('mean', sum(pnls)/len(pnls)):,.0f}")
    print(f"  Ann ROE:  {m.get('ann_return',0)*100:.2f}%   Sharpe: {m.get('daily_sharpe',0):.3f}")
    print(f"  Max DD:   {m.get('max_drawdown',0)*100:.1f}%")
    print(f"  Worst:    ${min(pnls):,.0f}   Best: ${max(pnls):,.0f}")
    print(f"  Bootstrap CI: [{ci_lo:+,.0f}, {ci_hi:+,.0f}]  {sig_marker} "
          f"({'significant' if sig else 'not significant'})")
    stress = _stress_pnl(t, STRESS_WINDOWS)
    for w, pnl in stress.items():
        print(f"  {w}: ${pnl:+,.0f}")


def run() -> None:
    print("=" * 64)
    print("Q012 — STOP Sensitivity + Phase 4 BSH Rerun")
    print("=" * 64)

    stop_grid = [3.0, 3.5, 4.0]

    # ── Step 1: Phase 2 filtered STOP sensitivity ─────────────────────────────
    print("\n\n══ STEP 1 — Phase 2 Filtered, STOP sensitivity (1 contract/slot) ══")
    p2_results = {}
    for s in stop_grid:
        print(f"  Running STOP={s} …", flush=True)
        p2_results[s] = run_p2_filtered_stop(s, n_contracts=1)

    for s, r in p2_results.items():
        report(f"Phase 2 filtered | STOP={s}×", r)

    # ── STOP sensitivity summary ──────────────────────────────────────────────
    print("\n\n── Step 1 Summary: CI sensitivity to STOP_MULT ──")
    print(f"  {'STOP':>6}  {'n':>5}  {'WR%':>6}  {'Stop%':>7}  {'AvgPnL':>8}  {'AnnROE%':>8}  {'MaxDD%':>8}  {'CI_lo':>8}  {'CI_hi':>8}  Sig")
    for s, r in p2_results.items():
        t  = r.trades
        ws = [x for x in t if x.pnl > 0]
        ss = [x for x in t if x.exit_reason == "stop_loss"]
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        print(f"  {s:>6.1f}  {len(t):>5}  "
              f"{len(ws)/len(t)*100:>6.1f}  {len(ss)/len(t)*100:>7.1f}  "
              f"${bs.get('mean',0):>7,.0f}  {m.get('ann_return',0)*100:>8.2f}  "
              f"{m.get('max_drawdown',0)*100:>8.1f}  "
              f"{bs.get('ci_lo',0):>+8,.0f}  {bs.get('ci_hi',0):>+8,.0f}  "
              f"{'✅' if bs.get('significant') else '❌'}")

    # ── Step 2: Phase 4 BSH STOP sensitivity ─────────────────────────────────
    print("\n\n══ STEP 2 — Phase 4 BSH Payoff, STOP sensitivity (1 contract/slot) ══")
    p4_results = {}
    for s in stop_grid:
        print(f"  Running Phase 4 BSH STOP={s} …", flush=True)
        p4_results[s] = run_p4_bsh_production(s, n_contracts=1)

    for s, r in p4_results.items():
        report(f"Phase 4 BSH | STOP={s}×", r)

    # ── BSH sensitivity summary ───────────────────────────────────────────────
    print("\n\n── Step 2 Summary: BSH Phase 4 CI sensitivity ──")
    print(f"  {'STOP':>6}  {'n':>5}  {'WR%':>6}  {'Stop%':>7}  {'AvgPnL':>8}  {'AnnROE%':>8}  {'MaxDD%':>8}  {'CI_lo':>8}  {'CI_hi':>8}  Sig")
    for s, r in p4_results.items():
        t  = r.trades
        ws = [x for x in t if x.pnl > 0]
        ss = [x for x in t if x.exit_reason == "stop_loss"]
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        print(f"  {s:>6.1f}  {len(t):>5}  "
              f"{len(ws)/len(t)*100:>6.1f}  {len(ss)/len(t)*100:>7.1f}  "
              f"${bs.get('mean',0):>7,.0f}  {m.get('ann_return',0)*100:>8.2f}  "
              f"{m.get('max_drawdown',0)*100:>8.1f}  "
              f"{bs.get('ci_lo',0):>+8,.0f}  {bs.get('ci_hi',0):>+8,.0f}  "
              f"{'✅' if bs.get('significant') else '❌'}")

    # ── Step 3: 2-contract diagnostic ─────────────────────────────────────────
    print("\n\n══ STEP 3 — 2-Contract Diagnostic (not production routing) ══")
    print("  Running Phase 2 filtered STOP=3.0, n=2 …", flush=True)
    r2c = run_p2_filtered_stop(3.0, n_contracts=2)
    report("Phase 2 filtered | STOP=3.0 | 2 contracts/slot (diagnostic)", r2c)
    bs2 = r2c.bootstrap or {}
    print(f"\n  1-contract CI (STOP=3.0): [{p2_results[3.0].bootstrap.get('ci_lo',0):+,.0f}, "
          f"{p2_results[3.0].bootstrap.get('ci_hi',0):+,.0f}]  "
          f"{'✅' if p2_results[3.0].bootstrap.get('significant') else '❌'}")
    print(f"  2-contract CI (STOP=3.0): [{bs2.get('ci_lo',0):+,.0f}, "
          f"{bs2.get('ci_hi',0):+,.0f}]  "
          f"{'✅' if bs2.get('significant') else '❌'}")

    # ── Final cross-check: BSH vs no-BSH at same STOP ─────────────────────────
    print("\n\n── Cross-check: Phase 2 vs Phase 4 BSH at each STOP ──")
    print(f"  {'STOP':>6}  {'Layer':>16}  {'AvgPnL':>8}  {'AnnROE%':>8}  {'MaxDD%':>8}  {'CI_lo':>8}  {'CI_hi':>8}  Sig")
    for s in stop_grid:
        for label, rr in [("naked put (P2)", p2_results[s]), ("+ BSH (P4)", p4_results[s])]:
            t  = rr.trades
            m  = rr.portfolio_metrics
            bs = rr.bootstrap or {}
            print(f"  {s:>6.1f}  {label:>16}  "
                  f"${bs.get('mean',0):>7,.0f}  {m.get('ann_return',0)*100:>8.2f}  "
                  f"{m.get('max_drawdown',0)*100:>8.1f}  "
                  f"{bs.get('ci_lo',0):>+8,.0f}  {bs.get('ci_hi',0):>+8,.0f}  "
                  f"{'✅' if bs.get('significant') else '❌'}")


if __name__ == "__main__":
    run()
