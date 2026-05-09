"""
Q052 — H3: Delta/DTE Grid Search (deep OTM + longer DTE)
=========================================================
PM hypothesis: 当前 0.20 delta 风险敞口大，尝试更深 OTM strike + 更长 DTE
能否改变左尾分布。

Pre-scan finding: 在 SPX 5400 下，premium/SPAN 比率随 DTE 延长显著改善：
  0.20 delta @ 180-DTE  → 45.48% premium/SPAN  (vs 24.58% @ 45-DTE)
  0.10 delta @ 180-DTE  → 29.24%
  0.05 delta @ 180-DTE  → 18.91%

Grid: delta ∈ [0.20, 0.10, 0.05] × DTE ∈ [45, 90, 180]
Fixed: STOP=3.0 (production-aligned), 1 contract, hybrid no-BSH (Phase 1 style)

Hypothesis to test:
  H3a. Deep OTM (0.05 delta) reduces stop rate enough to improve
       risk-adjusted return.
  H3b. Long DTE (180 days) provides smoother theta + lower stop frequency.
  H3c. The optimal is in the (0.10 delta, 90+DTE) region rather than the
       extremes.
"""
from __future__ import annotations

import sys, math
from pathlib import Path
from collections import defaultdict
from typing import Literal

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research.strategies.ES_puts.backtest import (
    _load_data, _trend, _make_row, _bp_per_contract,
    put_price, find_strike_for_delta,
    BacktestResult, PutTrade, PutPosition,
    PROFIT_TARGET, GAMMA_DTE, SPX_MULTIPLIER,
    WARMUP_DAYS, P1_INITIAL_EQUITY, TrendSignal,
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


def run_phase1_variant(
    target_delta: float,
    entry_dte:    int,
    stop_mult:    float = 3.0,
    n_contracts:  int   = 1,
    mode:         Literal["baseline", "filtered"] = "filtered",
) -> BacktestResult:
    """Phase 1 single-slot with parametrised delta and DTE."""
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(START)]

    result    = BacktestResult(phase=f"h3_d{target_delta}_dte{entry_dte}", mode=mode)
    equity    = P1_INITIAL_EQUITY
    peak_eq   = P1_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions:  dict[int, PutPosition]  = {}

    # Adjust gamma DTE: longer entry DTE → larger gamma exit threshold
    gamma_dte = max(GAMMA_DTE, entry_dte // 9)  # 5 for 45-DTE, 10 for 90, 20 for 180

    for date, row in sim.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        sig = vix / 100.0
        dstr = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0

        window   = full_spx[full_spx.index <= date].iloc[-200:]
        warmed   = len(window) >= WARMUP_DAYS
        trend_ok = warmed and (_trend(window, spx) == TrendSignal.BULLISH if mode == "filtered" else True)

        # Manage open position
        pos = positions.get(entry_dte)
        if pos:
            pos.expiry_dte -= 1
            cur = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur) * pos.contracts * SPX_MULTIPLIER
            reason = None
            if   pos.expiry_dte <= gamma_dte:           reason = "gamma_risk"
            elif cur >= pos.stop_premium:                reason = "stop_loss"
            elif cur <= pos.profit_premium:              reason = "profit_target"
            elif pos.expiry_dte <= 0:                   reason = "expiry"
            if reason:
                pnl = (pos.entry_premium - cur) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=entry_dte, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx,
                    entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur,
                    dte_at_entry=entry_dte, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl,
                ))
                del positions[entry_dte]
            else:
                pos.prev_val = cur

        # Open new position
        if entry_dte not in positions and warmed and trend_ok:
            try:
                k = find_strike_for_delta(spx, entry_dte, sig, target_delta, False)
                prem = put_price(spx, k, entry_dte, sig)
            except Exception:
                k, prem = None, 0
            # Skip if premium too low to be meaningful (deep OTM at low VIX)
            if prem > 0.30:
                positions[entry_dte] = PutPosition(
                    slot=entry_dte, entry_date=dstr, expiry_dte=entry_dte,
                    strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                    contracts=float(n_contracts),
                    bp_used=n_contracts * _bp_per_contract(spx, k, prem),
                    stop_premium=prem * stop_mult,
                    profit_premium=prem * PROFIT_TARGET,
                    prev_val=prem,
                )

        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix,
                                         f"h3_d{target_delta}_dte{entry_dte}")
        daily_rows.append(dr)

    result.trades            = trades
    result.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    result.daily_rows        = daily_rows
    if len(trades) >= 10:
        result.bootstrap = bootstrap_ci([t.pnl for t in trades])
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def stress_pnl(trades):
    out = {}
    for label, start, end in STRESS_WINDOWS:
        ts, te = pd.Timestamp(start), pd.Timestamp(end)
        out[label] = round(sum(t.pnl for t in trades
                                if ts <= pd.Timestamp(t.entry_date) <= te), 0)
    return out


def worst_year(trades):
    by_year = defaultdict(float)
    for t in trades:
        y = int(t.exit_date[:4]) if t.exit_date else int(t.entry_date[:4])
        by_year[y] += t.pnl
    if not by_year: return "—", 0
    wy = min(by_year, key=by_year.get)
    return str(wy), by_year[wy]


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 80)
    print("Q052 / H3 — /ES Delta × DTE Grid (deep OTM + long DTE)")
    print(f"  STOP=3.0, 1 contract, Phase-1 single-slot, filtered, 2000–today")
    print("=" * 80)

    grid = []
    for delta in [0.20, 0.10, 0.05]:
        for dte in [45, 90, 180]:
            grid.append((delta, dte))

    results = {}
    for delta, dte in grid:
        tag = f"d{delta:.2f}_dte{dte}"
        print(f"\n  Running Δ={delta:.2f} DTE={dte} …", flush=True)
        r = run_phase1_variant(target_delta=delta, entry_dte=dte, stop_mult=3.0)
        results[tag] = (delta, dte, r)
        bs = r.bootstrap or {}
        print(f"    → {len(r.trades)} trades  AnnROE {r.portfolio_metrics.get('ann_return',0)*100:+.2f}%  "
              f"CI [{bs.get('ci_lo',0):+.0f}, {bs.get('ci_hi',0):+.0f}]  "
              f"{'✅' if bs.get('significant') else '❌'}")

    # ── Detail report ─────────────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("DETAIL: per (delta, DTE) configuration")
    print("=" * 80)
    for tag, (delta, dte, r) in results.items():
        t  = r.trades
        if not t:
            print(f"\n  Δ={delta:.2f} DTE={dte}: no trades")
            continue
        ws = [x for x in t if x.pnl > 0]
        ss = [x for x in t if x.exit_reason == "stop_loss"]
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        wy, wp = worst_year(t)
        sp = stress_pnl(t)

        sig = bs.get("significant", False)
        marker = "✅ SIGNIFICANT" if sig else "❌"
        print(f"\n  Δ={delta:.2f}  DTE={dte}  {marker}")
        print(f"    Trades:  {len(t)}   WR: {len(ws)/len(t)*100:.1f}%   Stop: {len(ss)/len(t)*100:.1f}%")
        print(f"    Avg P&L: ${bs.get('mean',0):,.0f}/trade   Total: ${sum(x.pnl for x in t):,.0f}")
        print(f"    Ann ROE: {m.get('ann_return',0)*100:+.2f}%   "
              f"Sharpe: {m.get('daily_sharpe',0):.3f}")
        print(f"    Worst trade: ${min(x.pnl for x in t):,.0f}   "
              f"Worst year: {wy} ${wp:,.0f}")
        print(f"    Bootstrap CI: [{bs.get('ci_lo',0):+,.0f}, {bs.get('ci_hi',0):+,.0f}]")
        print(f"    Stress: 2008=${sp['2008 GFC']:+,.0f}  "
              f"2020=${sp['2020 COVID']:+,.0f}  2022=${sp['2022 Bear']:+,.0f}")

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("H3 GRID SUMMARY")
    print("=" * 80)
    print(f"  {'Δ':>5} {'DTE':>4}  {'n':>5}  {'WR%':>5}  {'Stop%':>6}  "
          f"{'AvgPnL':>8}  {'AnnROE%':>8}  {'CI_lo':>7}  {'CI_hi':>7}  Sig")
    for tag, (delta, dte, r) in results.items():
        t = r.trades
        if not t: continue
        ws = [x for x in t if x.pnl > 0]
        ss = [x for x in t if x.exit_reason == "stop_loss"]
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        sig = "✅" if bs.get("significant") else "❌"
        print(f"  {delta:>5.2f} {dte:>4}  {len(t):>5}  "
              f"{len(ws)/len(t)*100:>5.1f}  {len(ss)/len(t)*100:>6.1f}  "
              f"${bs.get('mean',0):>7,.0f}  {m.get('ann_return',0)*100:>+8.2f}  "
              f"{bs.get('ci_lo',0):>+7,.0f}  {bs.get('ci_hi',0):>+7,.0f}  {sig}")

    # ── Verdict ──────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("H3 VERDICT")
    print("=" * 80)
    sig_configs = [
        (delta, dte) for tag, (delta, dte, r) in results.items()
        if r.bootstrap and r.bootstrap.get("significant", False)
    ]
    if sig_configs:
        best = max(
            results.values(),
            key=lambda x: x[2].portfolio_metrics.get("ann_return", -1)
        )
        print(f"\n  ✅ {len(sig_configs)} configuration(s) achieved bootstrap significance:")
        for d, dte in sig_configs:
            r = results[f"d{d:.2f}_dte{dte}"][2]
            m = r.portfolio_metrics
            bs = r.bootstrap
            print(f"     Δ={d:.2f}  DTE={dte}  AnnROE={m.get('ann_return',0)*100:+.2f}%  CI=[{bs['ci_lo']:+.0f}, {bs['ci_hi']:+.0f}]")
        print(f"\n  Best AnnROE: Δ={best[0]:.2f} DTE={best[1]}, "
              f"AnnROE={best[2].portfolio_metrics.get('ann_return',0)*100:+.2f}%")
        print(f"\n  → H3 has at least one viable configuration at production scale.")
        print(f"  → Next: layer H1 (technical exit) on top of best H3 config.")
    else:
        # Find best AnnROE even if not significant
        best = max(
            results.values(),
            key=lambda x: x[2].portfolio_metrics.get("ann_return", -1)
        )
        print(f"\n  ❌ No configuration achieved bootstrap significance.")
        print(f"  Best AnnROE: Δ={best[0]:.2f} DTE={best[1]}, "
              f"AnnROE={best[2].portfolio_metrics.get('ann_return',0)*100:+.2f}%")
        print(f"  CI: [{best[2].bootstrap.get('ci_lo',0):+.0f}, {best[2].bootstrap.get('ci_hi',0):+.0f}]")
        print(f"\n  → H3 alone does not validate. Check if any direction worth pursuing with H1/H2 overlay.")


if __name__ == "__main__":
    run()
