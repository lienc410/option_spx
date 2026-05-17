"""Q072 P4 — Cap Recalibration with Production-View Baseline Maintenance.

PM observed (2026-05-16) that SPEC-103 governance panel uses ACCOUNT-LEVEL
maintenance margin (Schwab API / ETrade API integrated returns), but Q072
P1 backtest peak 67.9% was computed using SLEEVE-ONLY BP (spread max-loss +
DD Overlay account_pct). The two are not directly comparable.

This script reconstructs SPX PM pool peak under "production口径" by adding a
PARAMETERIZED non-sleeve baseline maintenance (= equity + other-options held
outside the sleeve research universe). Since true historical baseline is not
available (PM does not have 19y of Schwab/ETrade maintenance snapshots), we
run a sensitivity table across baseline assumptions.

Output:
    q072_p4_cap_recalibration.csv  — peak / P95 / cap-bind days across baselines
    Console table for PM decision

Anchor data (2026-05-16 live snapshot):
    Schwab baseline (equity maint / Schwab NLV) = 14.4%
    ETrade baseline (equity maint / ETrade NLV) = 24.4%
    Combined baseline ((Schwab equity + ETrade equity) / combined NLV) = 17.7%
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"

# Baseline scenarios (% of Schwab NLV that is non-sleeve equity/options maint)
BASELINE_SCENARIOS = [0.0, 5.0, 10.0, 14.4, 20.0, 25.0, 30.0, 35.0]

# Cap candidates to evaluate
CAP_CANDIDATES = [60.0, 65.0, 70.0, 75.0, 80.0]


def main():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    # Reconstruct sleeve-only SPX_PM pool BP (matches Q072 P1 §SPX_PM_pool)
    sleeve_only = daily["main_bp"] + daily["dd_overlay_bp"]

    print("=" * 80)
    print("Q072 P4 — Cap Recalibration (production-view baseline maintenance)")
    print("=" * 80)
    print(f"\nSleeve-only SPX_PM pool stats (matches Q072 P1):")
    print(f"  avg: {sleeve_only.mean():.1f}%  P95: {sleeve_only.quantile(0.95):.1f}%  "
          f"peak: {sleeve_only.max():.1f}%")
    print(f"  days >= 60%: {(sleeve_only >= 60).sum()}  >= 70%: {(sleeve_only >= 70).sum()}")
    print()
    print(f"Production口径 (Schwab API maintenance) anchor (2026-05-16 live):")
    print(f"  Schwab non-sleeve equity baseline = 14.4% of Schwab NLV")
    print(f"  ETrade non-sleeve equity baseline = 24.4% of ETrade NLV")
    print()

    rows = []
    for b in BASELINE_SCENARIOS:
        prod_view = sleeve_only + b
        row = {
            "baseline_pct": b,
            "avg": round(prod_view.mean(), 1),
            "P95": round(prod_view.quantile(0.95), 1),
            "peak": round(prod_view.max(), 1),
        }
        for cap in CAP_CANDIDATES:
            row[f"days_>={int(cap)}"] = int((prod_view >= cap).sum())
            row[f"%days_>={int(cap)}"] = round((prod_view >= cap).mean() * 100, 2)
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q072_p4_cap_recalibration.csv", index=False)

    print("Cap-bind sensitivity across baseline assumptions:\n")
    display_cols = ["baseline_pct", "avg", "P95", "peak"]
    for cap in CAP_CANDIDATES:
        display_cols.append(f"days_>={int(cap)}")
    print(df[display_cols].to_string(index=False))
    print()
    print("Days >= cap as % of 19y:")
    display_cols2 = ["baseline_pct", "avg", "P95", "peak"]
    for cap in CAP_CANDIDATES:
        display_cols2.append(f"%days_>={int(cap)}")
    print(df[display_cols2].to_string(index=False))

    # Decision table
    print("\n" + "=" * 80)
    print("Cap recommendation per baseline scenario:")
    print("=" * 80)
    print(f"{'Baseline':<10}{'Peak':<10}{'Suggested cap (peak + 5pp safety)':<40}")
    print("-" * 60)
    for b in BASELINE_SCENARIOS:
        prod_view = sleeve_only + b
        peak = prod_view.max()
        suggested = round(peak + 5, 0)  # peak + 5pp safety margin
        print(f"{b:<10.1f}{peak:<10.1f}{suggested:<10.0f}")

    print(f"\n→ At Schwab anchor baseline (14.4%): historical peak = "
          f"{(sleeve_only + 14.4).max():.1f}%, suggested cap "
          f"{round((sleeve_only + 14.4).max() + 5, 0):.0f}%")
    print(f"\nOutput: {OUT / 'q072_p4_cap_recalibration.csv'}")


if __name__ == "__main__":
    main()
