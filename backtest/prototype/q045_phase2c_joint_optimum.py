"""Q045 Phase 2C — Joint optimization: NORMAL × HIGH_VOL bp_target combinations.

From Phases 2A and 2B, we identified:
  - NORMAL N1 (15%) gives +4.15pp account-level AnnROE alone
  - HIGH_VOL H2 (14%) gives +1.97pp account-level AnnROE alone

Phase 2C tests joint variants:
  J0: N=10%, H=7%   (baseline; equivalent to Phase 1)
  J1: N=15%, H=7%   (= Phase 2A N1)
  J2: N=10%, H=14%  (= Phase 2B H2)
  J3: N=15%, H=14%  (joint optimum candidate)
  J4: N=15%, H=10%  (conservative HIGH_VOL)
  J5: N=12%, H=14%  (conservative NORMAL)

Reports include account-level AnnROE, peak BP%, ceiling utilization,
worst trade, Sharpe, and idle BP analysis.
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

WINDOW_START = "2023-01-01"
ACCOUNT_SIZE = 150_000.0
YEARS = (date.today() - pd.to_datetime(WINDOW_START).date()).days / 365.25


def _peak_bp(trades):
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


def _avg_bp(trades):
    if not trades:
        return 0.0
    start = pd.to_datetime(WINDOW_START).date()
    days = pd.date_range(start, date.today(), freq="D")
    bp_series = pd.Series(0.0, index=days)
    for t in trades:
        if not t.entry_date or not t.exit_date:
            continue
        e = pd.to_datetime(t.entry_date).date()
        x = pd.to_datetime(t.exit_date).date()
        mask = (bp_series.index >= pd.Timestamp(e)) & (bp_series.index <= pd.Timestamp(x))
        bp_series.loc[mask] += t.bp_pct_account
    trading = bp_series[bp_series.index.weekday < 5]
    return round(float(trading.mean()), 2)


def _account_metrics(trades):
    pnls = sorted(t.exit_pnl for t in trades)
    total = sum(pnls)
    n = len(pnls)
    cvar5 = float(np.mean(pnls[:max(1, int(n * 0.05))]))
    pnl_arr = np.array([t.exit_pnl for t in trades])
    sharpe = (pnl_arr.mean() / pnl_arr.std() * np.sqrt(n / YEARS)
              if pnl_arr.std() > 0 else float("nan"))
    return {
        "total_pnl": round(total, 0),
        "ann_roe": round(total / ACCOUNT_SIZE / YEARS * 100, 3),
        "n_trades": n,
        "cvar5": round(cvar5, 0),
        "sharpe": round(sharpe, 2),
        "worst": round(min(pnls), 0) if pnls else 0,
    }


def run_variant(label: str, bp_n: float, bp_h: float):
    print(f"  Running {label}...", flush=True)
    p = deepcopy(DEFAULT_PARAMS)
    p.bp_target_normal   = bp_n
    p.bp_target_low_vol  = bp_n
    p.bp_target_high_vol = bp_h
    r = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p)
    return {
        "label": label,
        "bp_n": bp_n,
        "bp_h": bp_h,
        "trades": r.trades,
        "peak_bp": _peak_bp(r.trades),
        "avg_bp": _avg_bp(r.trades),
        "account": _account_metrics(r.trades),
    }


def main():
    print("Q045 Phase 2C — Joint NORMAL × HIGH_VOL bp_target sweep")
    print("=" * 95)
    print(f"Window: {WINDOW_START} → today  |  Account: ${ACCOUNT_SIZE:,.0f}  |  Years: {YEARS:.2f}\n")

    print("Running variants...")
    results = [
        run_variant("J0 N=10% H=7%   (baseline)",        0.10, 0.07),
        run_variant("J1 N=15% H=7%   (Phase 2A N1)",     0.15, 0.07),
        run_variant("J2 N=10% H=14%  (Phase 2B H2)",     0.10, 0.14),
        run_variant("J3 N=15% H=14%  (joint best)",      0.15, 0.14),
        run_variant("J4 N=15% H=10%  (conservative HV)", 0.15, 0.10),
        run_variant("J5 N=12% H=14%  (conservative N)",  0.12, 0.14),
    ]

    # ── Account-level summary ─────────────────────────────────────────
    print("\n" + "═" * 100)
    print("ACCOUNT-LEVEL SUMMARY (sorted by AnnROE)")
    print("═" * 100)
    hdr = (f"{'Variant':<35} {'TotalPnL':>10} {'AnnROE%':>8} {'ΔROE':>7} "
           f"{'N':>4} {'Peak%':>6} {'AvgBP%':>7} {'CVaR5':>9} {'Worst':>9} {'Sharpe':>7}")
    print(hdr)
    print("-" * len(hdr))

    base_roe = results[0]["account"]["ann_roe"]
    sorted_results = sorted(results, key=lambda r: -r["account"]["ann_roe"])

    for r in sorted_results:
        a = r["account"]
        delta = a["ann_roe"] - base_roe
        print(f"{r['label']:<35} {a['total_pnl']:>10,.0f} {a['ann_roe']:>8.3f} "
              f"{delta:>+7.2f} {a['n_trades']:>4} {r['peak_bp']:>6.1f} "
              f"{r['avg_bp']:>7.2f} {a['cvar5']:>9,.0f} {a['worst']:>9,.0f} {a['sharpe']:>7.2f}")

    # ── Idle BP comparison ────────────────────────────────────────────
    print("\n── Idle BP Analysis (avg utilization across variants) ──")
    print(f"{'Variant':<35} {'AvgBP%':>7} {'PeakBP%':>8} {'IdleAvg vs 35%':>15} {'IdleAvg vs 50%':>15}")
    print("-" * 90)
    for r in results:
        idle_n = 35.0 - r["avg_bp"]
        idle_h = 50.0 - r["avg_bp"]
        print(f"{r['label']:<35} {r['avg_bp']:>7.2f} {r['peak_bp']:>8.1f} "
              f"{idle_n:>15.2f}pp {idle_h:>15.2f}pp")

    # ── Linearity check ───────────────────────────────────────────────
    print("\n── Linearity Check (is joint = sum of parts?) ──")
    j0 = results[0]["account"]["ann_roe"]
    j1 = results[1]["account"]["ann_roe"]
    j2 = results[2]["account"]["ann_roe"]
    j3 = results[3]["account"]["ann_roe"]

    delta_n = j1 - j0   # NORMAL alone
    delta_h = j2 - j0   # HIGH_VOL alone
    delta_joint = j3 - j0     # joint
    sum_alone = delta_n + delta_h
    interaction = delta_joint - sum_alone

    print(f"  Δ NORMAL alone   (J1 - J0): {delta_n:+.3f}pp")
    print(f"  Δ HIGH_VOL alone (J2 - J0): {delta_h:+.3f}pp")
    print(f"  Sum (if independent)      : {sum_alone:+.3f}pp")
    print(f"  Δ JOINT          (J3 - J0): {delta_joint:+.3f}pp")
    print(f"  Interaction effect        : {interaction:+.3f}pp")
    print(f"    {'(positive = synergy; negative = ceiling crowding)' if interaction != 0 else ''}")

    # ── Recommendation ────────────────────────────────────────────────
    best = sorted_results[0]
    base = results[0]
    print("\n── Phase 2C Provisional Verdict ──")
    print(f"  Best variant: {best['label']}")
    print(f"    AnnROE: {best['account']['ann_roe']:.3f}%  vs baseline {base['account']['ann_roe']:.3f}%  "
          f"= +{best['account']['ann_roe']-base['account']['ann_roe']:.2f}pp")
    print(f"    Sharpe: {best['account']['sharpe']:.2f}  vs baseline {base['account']['sharpe']:.2f}")
    print(f"    Peak BP: {best['peak_bp']:.1f}%  vs ceilings (NORMAL 35% / HIGH_VOL 50%)")
    print(f"    Avg BP : {best['avg_bp']:.2f}%  vs baseline {base['avg_bp']:.2f}%")


if __name__ == "__main__":
    main()
