"""Q045 Phase 1 — Baseline ROE Decomposition Across Strategy Matrix.

Goal: ground the account-level ROE optimization discussion in concrete per-strategy
numbers. For each active strategy in the 3-year backtest:
  - N trades, win rate
  - Total PnL, AnnROE contribution
  - Avg BP%, avg hold days
  - $/BP-day (efficiency)
  - Peak concurrent BP, ceiling utilization
  - Worst trade, CVaR-equivalent

Cross-strategy:
  - Account-level total ROE
  - Concurrency matrix (which strategies coexist)
  - Peak combined BP across regimes
"""

from __future__ import annotations

import sys
from collections import defaultdict
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtest.engine import run_backtest, DEFAULT_PARAMS
from strategy.selector import StrategyName

WINDOW_START = "2023-01-01"
ACCOUNT_SIZE = 150_000.0


def _years(start_date: str) -> float:
    return (date.today() - pd.to_datetime(start_date).date()).days / 365.25


def _per_strategy_metrics(trades, account_size: float, years: float):
    """Compute per-strategy metrics from a list of trades."""
    by_strat = defaultdict(list)
    for t in trades:
        key = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
        by_strat[key].append(t)

    rows = []
    for strat, ts in sorted(by_strat.items()):
        n = len(ts)
        pnls = [t.exit_pnl for t in ts]
        total_pnl = sum(pnls)
        win_rt = sum(1 for p in pnls if p > 0) / n * 100 if n else 0

        bp_pcts = [t.bp_pct_account for t in ts if t.bp_pct_account]
        avg_bp_pct = np.mean(bp_pcts) if bp_pcts else 0.0

        holds = [t.hold_days for t in ts if t.hold_days]
        avg_hold = np.mean(holds) if holds else 0.0

        # $/BP-day = total_pnl / Σ(total_bp_$ × hold_days)
        bp_days_dollars = sum(t.total_bp * t.hold_days for t in ts
                              if t.hold_days and t.total_bp)
        per_bp_day = total_pnl / bp_days_dollars if bp_days_dollars > 0 else 0.0

        # AnnROE contribution = total_pnl / account / years
        ann_roe = total_pnl / account_size / years * 100 if years else 0.0

        worst = min(pnls) if pnls else 0.0
        worst_pct = worst / account_size * 100

        rows.append({
            "strategy": strat,
            "n": n,
            "win_rt": round(win_rt, 1),
            "total_pnl": round(total_pnl, 0),
            "ann_roe_pp": round(ann_roe, 3),
            "avg_bp_pct": round(avg_bp_pct, 1),
            "avg_hold": round(avg_hold, 1),
            "per_bp_day": round(per_bp_day, 5),
            "worst_$": round(worst, 0),
            "worst_pct": round(worst_pct, 2),
        })
    return rows


def _peak_concurrent_bp_per_strategy(trades):
    """For each strategy, peak concurrent BP% across the period."""
    by_strat = defaultdict(list)
    for t in trades:
        key = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
        by_strat[key].append(t)

    out = {}
    for strat, ts in by_strat.items():
        events = []
        for t in ts:
            if t.entry_date and t.exit_date:
                events.append((t.entry_date, +t.bp_pct_account))
                events.append((t.exit_date,  -t.bp_pct_account))
        events.sort(key=lambda x: x[0])
        cur, peak = 0.0, 0.0
        for _, d in events:
            cur += d
            peak = max(peak, cur)
        out[strat] = round(peak, 1)
    return out


def _peak_total_bp(trades):
    """Account-level peak concurrent BP% across all strategies."""
    events = []
    for t in trades:
        if t.entry_date and t.exit_date:
            events.append((t.entry_date, +t.bp_pct_account))
            events.append((t.exit_date,  -t.bp_pct_account))
    events.sort(key=lambda x: x[0])
    cur, peak = 0.0, 0.0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return round(peak, 1)


def _avg_bp_utilization_timeline(trades, start: str, end_date: date):
    """
    Compute time-weighted average total BP% used.
    Generates a daily timeline of total BP% in use; returns mean and median.
    """
    if not trades:
        return 0.0, 0.0

    # Build daily BP% timeline
    start_dt = pd.to_datetime(start).date()
    days = pd.date_range(start_dt, end_date, freq="D")
    bp_series = pd.Series(0.0, index=days)

    for t in trades:
        if not t.entry_date or not t.exit_date:
            continue
        e = pd.to_datetime(t.entry_date).date()
        x = pd.to_datetime(t.exit_date).date()
        mask = (bp_series.index >= pd.Timestamp(e)) & (bp_series.index <= pd.Timestamp(x))
        bp_series.loc[mask] += t.bp_pct_account

    # Trading-day approximation: filter to weekdays
    trading = bp_series[bp_series.index.weekday < 5]
    return round(float(trading.mean()), 2), round(float(trading.median()), 2)


def _concurrency_matrix(trades):
    """
    For each pair of strategies, count days when both were concurrently open.
    """
    by_strat = defaultdict(list)
    for t in trades:
        key = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
        by_strat[key].append(t)
    strats = sorted(by_strat.keys())

    # Build per-strategy daily presence
    matrix = {}
    for s in strats:
        ts = by_strat[s]
        if not ts:
            continue
        e_min = min(pd.to_datetime(t.entry_date).date() for t in ts if t.entry_date)
        x_max = max(pd.to_datetime(t.exit_date).date() for t in ts if t.exit_date)
        days = pd.date_range(e_min, x_max, freq="D")
        present = pd.Series(False, index=days)
        for t in ts:
            if not t.entry_date or not t.exit_date:
                continue
            e = pd.to_datetime(t.entry_date).date()
            x = pd.to_datetime(t.exit_date).date()
            mask = (present.index >= pd.Timestamp(e)) & (present.index <= pd.Timestamp(x))
            present.loc[mask] = True
        matrix[s] = present

    # Pairwise concurrency
    return matrix, strats


def main() -> None:
    yrs = _years(WINDOW_START)
    print("Q045 Phase 1 — Baseline ROE Decomposition")
    print("=" * 90)
    print(f"Window: {WINDOW_START} → today  |  Account: ${ACCOUNT_SIZE:,.0f}  |  Years: {yrs:.2f}\n")

    print("Running baseline backtest...", flush=True)
    r = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE,
                     params=DEFAULT_PARAMS)
    trades = r.trades

    # ── Per-strategy table ────────────────────────────────────────────
    print("\n── Per-Strategy Metrics (sorted by AnnROE contribution) ──")
    rows = _per_strategy_metrics(trades, ACCOUNT_SIZE, yrs)
    rows.sort(key=lambda r: -r["ann_roe_pp"])

    hdr = (f"{'Strategy':<32} {'N':>4} {'WR%':>5} {'TotPnL':>9} "
           f"{'AnnROE':>7} {'AvgBP%':>7} {'AvgHold':>7} {'$/BPday':>9} "
           f"{'Worst$':>9} {'Worst%':>7}")
    print(hdr)
    print("-" * len(hdr))

    total_pnl_acct = 0
    for row in rows:
        total_pnl_acct += row["total_pnl"]
        print(f"{row['strategy']:<32} "
              f"{row['n']:>4} "
              f"{row['win_rt']:>5.1f} "
              f"{row['total_pnl']:>9,.0f} "
              f"{row['ann_roe_pp']:>7.3f} "
              f"{row['avg_bp_pct']:>7.1f} "
              f"{row['avg_hold']:>7.1f} "
              f"{row['per_bp_day']:>9.5f} "
              f"{row['worst_$']:>9,.0f} "
              f"{row['worst_pct']:>7.2f}")
    print("-" * len(hdr))

    total_ann_roe = total_pnl_acct / ACCOUNT_SIZE / yrs * 100
    print(f"{'TOTAL':<32} {sum(r['n'] for r in rows):>4}      "
          f"{total_pnl_acct:>9,.0f} {total_ann_roe:>7.3f}")

    # ── Strategy efficiency ranking ───────────────────────────────────
    print("\n── Strategy Efficiency Ranking ($/BP-day, descending) ──")
    by_eff = sorted(rows, key=lambda r: -r["per_bp_day"])
    for i, row in enumerate(by_eff, 1):
        print(f"  {i}. {row['strategy']:<32} ${row['per_bp_day']:.5f}/BP-day  "
              f"(N={row['n']}, AnnROE={row['ann_roe_pp']:.2f}pp)")

    # ── BP utilization profile ────────────────────────────────────────
    print("\n── BP Utilization Profile ──")
    avg_bp, med_bp = _avg_bp_utilization_timeline(trades, WINDOW_START, date.today())
    peak_total = _peak_total_bp(trades)
    peak_per_strat = _peak_concurrent_bp_per_strategy(trades)

    print(f"  Time-weighted avg total BP%   : {avg_bp:.2f}%  (across all trading days in window)")
    print(f"  Time-weighted median total BP%: {med_bp:.2f}%")
    print(f"  Peak total BP%                : {peak_total:.1f}%")
    print(f"  bp_ceiling_normal             : 35.0%   (utilization vs ceiling: {peak_total/35*100:.1f}%)")
    print(f"  bp_ceiling_high_vol           : 50.0%   (utilization vs ceiling: {peak_total/50*100:.1f}%)")

    print("\n  Per-strategy peak concurrent BP%:")
    for strat, peak in sorted(peak_per_strat.items(), key=lambda x: -x[1]):
        print(f"    {strat:<32} {peak:>5.1f}%")

    # ── Idle BP estimate ──────────────────────────────────────────────
    idle_low  = 35.0 - avg_bp   # vs NORMAL ceiling
    idle_high = 50.0 - avg_bp   # vs HIGH_VOL ceiling
    idle_total= 100.0 - avg_bp  # vs total account
    print(f"\n  IDLE BP (avg utilization vs ceilings):")
    print(f"    vs NORMAL ceiling (35%) : {idle_low:>5.1f}pp idle")
    print(f"    vs HIGH_VOL ceiling (50%): {idle_high:>5.1f}pp idle")
    print(f"    vs full account (100%)   : {idle_total:>5.1f}pp idle")

    # ── Concurrency matrix ────────────────────────────────────────────
    print("\n── Strategy Concurrency Matrix (overlap days) ──")
    matrix, strats = _concurrency_matrix(trades)
    if matrix:
        # Limit to strategies with at least 1 trade
        active = [s for s in strats if s in matrix]
        # Pairwise
        col_w = max(len(s.split(" ")[0]) for s in active) + 2
        print(f"  {'':<{col_w}}", end="")
        for s in active:
            print(f"{s.split(' ')[0][:8]:>10}", end="")
        print()
        for s_row in active:
            print(f"  {s_row.split(' ')[0][:col_w]:<{col_w}}", end="")
            for s_col in active:
                if s_row == s_col:
                    print(f"{'—':>10}", end="")
                    continue
                # Align indices
                if matrix[s_row] is None or matrix[s_col] is None:
                    print(f"{'0':>10}", end="")
                    continue
                common_idx = matrix[s_row].index.intersection(matrix[s_col].index)
                overlap_days = (matrix[s_row].loc[common_idx] & matrix[s_col].loc[common_idx]).sum()
                print(f"{int(overlap_days):>10}", end="")
            print()

    # ── Identify candidates for bp_target lift ────────────────────────
    print("\n── Phase 2 Candidates (highest $/BP-day with low avg_bp_pct) ──")
    candidates = sorted(
        [r for r in rows if r["n"] >= 5],
        key=lambda r: -(r["per_bp_day"] * (35 - r["avg_bp_pct"]))  # efficiency × headroom
    )
    print("  Strategies most likely to benefit from bp_target lift:")
    for i, r in enumerate(candidates[:5], 1):
        headroom = 35 - r["avg_bp_pct"]
        print(f"  {i}. {r['strategy']:<32} "
              f"$/BPday={r['per_bp_day']:.5f}  AvgBP={r['avg_bp_pct']:.1f}%  "
              f"Headroom={headroom:.1f}pp  AnnROE={r['ann_roe_pp']:.2f}pp")


if __name__ == "__main__":
    main()
