"""Q072 P4C.5 — Cap-Impact Ablation (simplified, allocator-agnostic).

Compares two cap configurations on 877 historical candidates:
    default: SPX 70 / ES 80 / combined 60 / short_vol 50 / stress 60 / R6 on
    B_tight: SPX 60 / ES 60 / combined 50 / short_vol 35 / stress 50 / R6 on

For each cap × split, computes:
    n_blocked / missed P&L (sum of exit_pnl of blocked trades) /
    avoided worst trade / net portfolio P&L impact

Splits include P4C.7 synthetic stress slices (2008 / 2022).

⚠ Simplified version: uses single-pass historical portfolio state (P4C.0 logic);
does NOT yet do full 5-allocator simulation (which requires lifecycle re-entry
after rejection). That step is deferred to next round.

Output:
    q072_p4c5_cap_impact_summary.csv
    q072_p4c5_blocked_trades.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

# Reuse P4C.0 logic
import sys
sys.path.insert(0, str(OUT))
from q072_p4c0_eligibility_filter import (
    build_portfolio_state, build_candidate_list, run_filter,
    SHORT_VOL_STRATS, FilterResult,
)
import q072_p4c0_eligibility_filter as p4c0

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"
BASELINE = REPO / "research" / "q042" / "baseline_19y_trades.csv"
DD_TRADES = REPO / "data" / "q042_backtest_trades.csv"
HV_TRADES = OUT / "q072_hv_ladder_v2f_baseline_trades.csv"
PRIORITY = OUT / "q072_p4c1_candidates_with_priority.csv"

CAPS = {
    "default": dict(SPX_PM=70.0, ES_SPAN=80.0, COMBINED=60.0,
                    SHORT_VOL=50.0, STRESS_EPISODE=60.0),
    "B_tight": dict(SPX_PM=60.0, ES_SPAN=60.0, COMBINED=50.0,
                    SHORT_VOL=35.0, STRESS_EPISODE=50.0),
}

SPLITS = {
    "full":         ("2007-01-01", "2026-05-13"),
    "post2020":     ("2020-01-01", "2026-05-13"),
    "recent2y":     ("2024-01-01", "2026-05-13"),
    "stress_2008":  ("2008-01-01", "2009-12-31"),
    "stress_2022":  ("2022-01-01", "2022-12-31"),
}


def apply_cap_config(cap_name: str):
    """Mutate P4C.0 module globals to apply cap config."""
    c = CAPS[cap_name]
    p4c0.CAP_SPX_PM = c["SPX_PM"]
    p4c0.CAP_ES_SPAN = c["ES_SPAN"]
    p4c0.CAP_COMBINED = c["COMBINED"]
    p4c0.CAP_SHORT_VOL = c["SHORT_VOL"]
    p4c0.CAP_STRESS_EPISODE = c["STRESS_EPISODE"]


def run_eligibility(daily, baseline, dd, hv, cap_name: str) -> pd.DataFrame:
    apply_cap_config(cap_name)
    state = build_portfolio_state(daily, baseline, dd, hv)
    state_lag1 = state.shift(1)
    candidates = build_candidate_list(baseline, dd, hv)
    rows = []
    for c in candidates:
        if c.entry_date not in state.index:
            continue
        idx = state.index.get_loc(c.entry_date)
        if idx == 0:
            continue
        sr = state_lag1.iloc[idx]
        r = run_filter(c, sr)
        rows.append({
            "sleeve": c.sleeve,
            "strategy": c.strategy,
            "entry_date": c.entry_date,
            "exit_date": c.exit_date,
            "bp_dollar": c.bp_dollar,
            "pool": c.pool,
            "is_short_vol": c.is_short_vol,
            "cap_config": cap_name,
            "passed": r.passed,
            "blocker": r.blocker,
        })
    return pd.DataFrame(rows)


def main():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    baseline = pd.read_csv(BASELINE, parse_dates=["entry_date", "exit_date"])
    dd = pd.read_csv(DD_TRADES, parse_dates=["entry_date", "exit_date"])
    hv = pd.read_csv(HV_TRADES, parse_dates=["entry_date", "exit_date"])

    # Load priority scores to enrich blocked-trade analysis
    priority_df = pd.read_csv(PRIORITY, parse_dates=["entry_date"])
    priority_lookup = priority_df.set_index(["sleeve", "entry_date"])["priority"]

    # Build candidate trade P&L lookup
    pnl_lookup = {}
    for _, t in baseline.iterrows():
        sleeve = t["strategy"].strip().replace(" ", "_").replace("(", "").replace(")", "")
        pnl_lookup[(sleeve, t["entry_date"])] = t["exit_pnl"]
    for _, t in dd.iterrows():
        pnl_lookup[(f"DD_Overlay_{t['sleeve_id']}", t["entry_date"])] = t["exit_pnl"]
    for _, t in hv.iterrows():
        pnl_lookup[("HV_Ladder", t["entry_date"])] = t["pnl"]

    results = []
    blocked_all = []
    for cap_name in CAPS:
        print(f"\n--- Running {cap_name} cap ---")
        log = run_eligibility(daily, baseline, dd, hv, cap_name)
        # Enrich with realized P&L
        log["realized_pnl"] = log.apply(
            lambda r: pnl_lookup.get((r["sleeve"], r["entry_date"]), 0), axis=1
        )
        log["priority_score"] = log.apply(
            lambda r: priority_lookup.get((r["sleeve"], r["entry_date"]), None), axis=1
        )
        log.to_csv(OUT / f"q072_p4c5_log_{cap_name}.csv", index=False)
        blocked = log[~log.passed].copy()
        blocked_all.append(blocked)

        print(f"  Total candidates: {len(log)}")
        print(f"  Passed: {log.passed.sum()} ({log.passed.mean()*100:.1f}%)")
        print(f"  Blocked: {len(blocked)}")
        print(f"  Blocker counts: {blocked.blocker.value_counts().to_dict()}")

        # Per split summary
        for split_name, (s, e) in SPLITS.items():
            sub = log[(log.entry_date >= s) & (log.entry_date <= e)]
            sub_blocked = blocked[(blocked.entry_date >= s) & (blocked.entry_date <= e)]
            missed_pnl = sub_blocked["realized_pnl"].sum()
            avoided_worst = sub_blocked["realized_pnl"].min() if len(sub_blocked) else 0
            results.append({
                "cap_config": cap_name,
                "split": split_name,
                "n_total": len(sub),
                "n_passed": sub.passed.sum(),
                "n_blocked": len(sub_blocked),
                "block_pct": round(len(sub_blocked) / len(sub) * 100, 1) if len(sub) else 0,
                "missed_pnl": round(missed_pnl, 0),
                "avoided_worst_trade": round(avoided_worst, 0),
                "blocker_breakdown": str(sub_blocked.blocker.value_counts().to_dict()),
            })

    summary = pd.DataFrame(results)
    summary.to_csv(OUT / "q072_p4c5_cap_impact_summary.csv", index=False)
    all_blocked_df = pd.concat(blocked_all, ignore_index=True)
    all_blocked_df.to_csv(OUT / "q072_p4c5_blocked_trades.csv", index=False)

    print("\n" + "=" * 80)
    print("Q072 P4C.5 — Cap Impact Summary (default vs B_tight)")
    print("=" * 80)

    for cap_name in CAPS:
        print(f"\n--- {cap_name} cap ---")
        sub = summary[summary.cap_config == cap_name]
        print(sub[["split", "n_total", "n_blocked", "block_pct",
                   "missed_pnl", "avoided_worst_trade"]].to_string(index=False))

    print(f"\n\nKey signal — how much MORE does B_tight block over default?")
    for split in SPLITS:
        d = summary[(summary.cap_config == "default") & (summary.split == split)]
        b = summary[(summary.cap_config == "B_tight") & (summary.split == split)]
        if len(d) == 0 or len(b) == 0:
            continue
        delta_blocked = b.iloc[0]["n_blocked"] - d.iloc[0]["n_blocked"]
        delta_missed = b.iloc[0]["missed_pnl"] - d.iloc[0]["missed_pnl"]
        delta_avoided = b.iloc[0]["avoided_worst_trade"] - d.iloc[0]["avoided_worst_trade"]
        print(f"  {split}: +{delta_blocked} blocked, "
              f"Δmissed_pnl ${delta_missed:+,.0f}, "
              f"Δworst_avoided ${delta_avoided:+,.0f}")

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
