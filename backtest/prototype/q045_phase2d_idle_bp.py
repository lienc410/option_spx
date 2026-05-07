"""Q045 Phase 2D — Idle BP timeline & opportunity analysis.

Even at J3 (joint optimum: N=15%, H=14%), avg BP utilization is only 15.93%
out of 35% NORMAL ceiling (or 50% HIGH_VOL ceiling). The remaining ~19pp
of idle BP is the next research frontier.

This phase decomposes WHEN BP is idle:
  - Days with zero positions open (full account idle)
  - Days with one position open (one strategy active)
  - Days with two positions open (within ceiling)
  - Days near or at ceiling

This identifies whether the idle BP is:
  (a) "Unfillable" — strategies declined entry (entry conditions not met)
  (b) "Fillable" — diversification or new strategies could occupy it
  (c) "Concentrated" — already at peak, waiting for current positions to close
"""

from __future__ import annotations

import sys
from collections import Counter
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


def _bp_timeline(trades, start: str, end: date):
    """Daily timeline of (total_bp_pct, n_open_strategies)."""
    if not trades:
        return pd.DataFrame()
    days = pd.date_range(pd.to_datetime(start), end, freq="D")
    bp_pct = pd.Series(0.0, index=days)
    n_open = pd.Series(0, index=days)
    strats_open = pd.Series([set() for _ in range(len(days))], index=days)

    for t in trades:
        if not t.entry_date or not t.exit_date:
            continue
        e = pd.to_datetime(t.entry_date).date()
        x = pd.to_datetime(t.exit_date).date()
        mask = (bp_pct.index >= pd.Timestamp(e)) & (bp_pct.index <= pd.Timestamp(x))
        bp_pct.loc[mask] += t.bp_pct_account
        n_open.loc[mask] += 1
        strat_name = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
        for d in days[mask]:
            strats_open.loc[d].add(strat_name)

    df = pd.DataFrame({"bp_pct": bp_pct, "n_open": n_open, "strats": strats_open})
    df = df[df.index.weekday < 5]  # trading days only
    return df


def main():
    print("Q045 Phase 2D — Idle BP Timeline & Opportunity Analysis")
    print("=" * 95)

    # Run baseline (J0) and joint optimum (J3)
    print("\nRunning J0 (baseline) and J3 (joint optimum)...")
    p_j0 = deepcopy(DEFAULT_PARAMS)
    p_j3 = deepcopy(DEFAULT_PARAMS)
    p_j3.bp_target_normal   = 0.15
    p_j3.bp_target_low_vol  = 0.15
    p_j3.bp_target_high_vol = 0.14

    r_j0 = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p_j0)
    r_j3 = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p_j3)

    df_j0 = _bp_timeline(r_j0.trades, WINDOW_START, date.today())
    df_j3 = _bp_timeline(r_j3.trades, WINDOW_START, date.today())

    # ── Distribution of daily BP utilization ─────────────────────────
    print("\n── Distribution of Daily BP Utilization ──\n")
    bins = [(0, 0), (0, 5), (5, 15), (15, 25), (25, 35), (35, 45), (45, 100)]
    print(f"{'Bucket':<22} {'J0 Days':>9} {'J0 %':>7} {'J3 Days':>9} {'J3 %':>7}")
    print("-" * 60)
    for lo, hi in bins:
        if lo == hi:  # zero bucket
            j0_n = (df_j0["bp_pct"] == 0).sum()
            j3_n = (df_j3["bp_pct"] == 0).sum()
            label = "= 0 (fully idle)"
        else:
            j0_n = ((df_j0["bp_pct"] > lo) & (df_j0["bp_pct"] <= hi)).sum()
            j3_n = ((df_j3["bp_pct"] > lo) & (df_j3["bp_pct"] <= hi)).sum()
            label = f"({lo:>3},{hi:>3}]"
        j0_pct = j0_n / len(df_j0) * 100 if len(df_j0) else 0
        j3_pct = j3_n / len(df_j3) * 100 if len(df_j3) else 0
        print(f"{label:<22} {j0_n:>9} {j0_pct:>7.1f} {j3_n:>9} {j3_pct:>7.1f}")

    # ── n_open distribution ───────────────────────────────────────────
    print("\n── Strategies Open per Day (concurrency) ──\n")
    for n_label, df_v in [("J0 baseline", df_j0), ("J3 joint", df_j3)]:
        n_dist = df_v["n_open"].value_counts().sort_index()
        print(f"  {n_label}:")
        for n_open_count, days in n_dist.items():
            pct = days / len(df_v) * 100
            print(f"    {n_open_count} strategies open : {days:>4} days ({pct:>5.1f}%)")

    # ── Idle days (zero BP) breakdown ─────────────────────────────────
    j0_zero = df_j0[df_j0["bp_pct"] == 0]
    j3_zero = df_j3[df_j3["bp_pct"] == 0]

    print(f"\n── Fully Idle Days (zero BP) ──")
    print(f"  J0 baseline: {len(j0_zero)} days ({len(j0_zero)/len(df_j0)*100:.1f}%)")
    print(f"  J3 joint   : {len(j3_zero)} days ({len(j3_zero)/len(df_j3)*100:.1f}%)")
    print(f"  Δ          : {len(j3_zero)-len(j0_zero)} days  (J3 should not have MORE idle days)")

    if len(j0_zero) > 0:
        gaps = []
        prev = None
        run_start = None
        for d in sorted(j0_zero.index):
            if prev is None or (d - prev).days > 1:
                if run_start is not None:
                    gaps.append((run_start, prev))
                run_start = d
            prev = d
        if run_start is not None:
            gaps.append((run_start, prev))
        gap_lengths = [(g[1] - g[0]).days + 1 for g in gaps]
        print(f"\n  Gap statistics (J0 baseline):")
        print(f"    Number of idle gaps: {len(gaps)}")
        print(f"    Avg gap length     : {np.mean(gap_lengths):.1f} days")
        print(f"    Max gap length     : {max(gap_lengths)} days")
        print(f"    Total idle days    : {sum(gap_lengths)} days ({sum(gap_lengths)/len(df_j0)*100:.1f}%)")

    # ── Idle BP $ value estimation ────────────────────────────────────
    avg_bp_j0 = df_j0["bp_pct"].mean()
    avg_bp_j3 = df_j3["bp_pct"].mean()
    n_days = len(df_j3)

    # If we could deploy at avg $/BP-day rate (use J3's actual rate)
    j3_pnl = sum(t.exit_pnl for t in r_j3.trades)
    j3_bp_days = sum(t.total_bp * t.hold_days for t in r_j3.trades if t.hold_days and t.total_bp)
    avg_per_bp_day_j3 = j3_pnl / j3_bp_days if j3_bp_days > 0 else 0

    # Idle BP at J3 vs ceilings
    idle_vs_n = 35.0 - avg_bp_j3   # vs NORMAL ceiling
    idle_vs_h = 50.0 - avg_bp_j3   # vs HIGH_VOL ceiling

    # If we deployed half the idle BP at J3's $/BP-day rate
    idle_dollars_n = idle_vs_n / 100 * ACCOUNT_SIZE
    annual_potential_n = idle_dollars_n * 0.5 * avg_per_bp_day_j3 * 365  # 50% of idle, daily basis
    annual_pp_n = annual_potential_n / ACCOUNT_SIZE * 100

    print(f"\n── Idle BP Opportunity Estimation ──")
    print(f"  J3 avg BP utilization: {avg_bp_j3:.2f}%")
    print(f"  J3 $/BP-day rate     : ${avg_per_bp_day_j3:.5f}")
    print(f"  Idle vs NORMAL ceiling (35%): {idle_vs_n:.2f}pp = ${idle_dollars_n:,.0f}")
    print(f"  If 50% of idle BP could be deployed at J3's rate:")
    print(f"    Annual incremental potential: ~${annual_potential_n:,.0f} = {annual_pp_n:.2f}pp AnnROE")
    print(f"  This is what Q041 paper-trading + Q036 Overlay-F is meant to capture.")

    # ── Save daily series for plotting ────────────────────────────────
    out_path = Path("data/q045_phase2d_idle_bp_timeline.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame({
        "j0_bp_pct": df_j0["bp_pct"],
        "j0_n_open": df_j0["n_open"],
        "j3_bp_pct": df_j3["bp_pct"],
        "j3_n_open": df_j3["n_open"],
    })
    summary.to_csv(out_path)
    print(f"\nDaily timeline saved: {out_path}")


if __name__ == "__main__":
    main()
