"""Q072 P4C.6 — Walk-Forward Validation of Priority Lookup.

Build priority bucket lookup on 2007-2018 training data only.
Apply to 2019-2026 test data.
Compare:
    in-sample priority scores (full 19y lookup)
    out-of-sample priority scores (train-only lookup applied to test candidates)

If OOS priority materially differs from IS, the priority formula is overfit to
historical realized P&L distribution.

Output:
    q072_p4c6_walkforward_compare.csv  — per-test-candidate IS vs OOS priority
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

import sys
sys.path.insert(0, str(OUT))
import q072_p4c1_priority_allocator as p4c1

TRAIN_END = "2018-12-31"
TEST_START = "2019-01-01"


def main():
    daily, baseline, dd, hv = p4c1.load_data()
    cands_full = p4c1.build_candidates_df(daily, baseline, dd, hv)
    print(f"Total candidates: {len(cands_full)}")

    # Train: candidates with entry_date <= TRAIN_END
    train = cands_full[cands_full.entry_date <= TRAIN_END]
    test = cands_full[cands_full.entry_date >= TEST_START]
    print(f"Train (2007-2018): {len(train)}  Test (2019-2026): {len(test)}")

    # In-sample: full lookup
    bucket_full = p4c1.build_bucket_lookup(cands_full)
    parent_full = p4c1.build_parent_lookup(cands_full)
    # OOS: train-only lookup
    bucket_train = p4c1.build_bucket_lookup(train)
    parent_train = p4c1.build_parent_lookup(train)

    print(f"\nBucket counts: full {len(bucket_full)}  train {len(bucket_train)}")

    # Apply both lookups to test candidates; compare priority
    rows = []
    # need return/tail percentile rankings from full distribution
    # IS: shrunk stats from full lookup
    # OOS: shrunk stats from train lookup, rank against train-only realized $/BP-day distribution

    # First, compute IS shrunk stats for test
    test = test.copy()
    test["shrunk_dpbp_is"] = 0.0
    test["shrunk_tail_is"] = 0.0
    test["shrunk_dpbp_oos"] = 0.0
    test["shrunk_tail_oos"] = 0.0

    for i, row in test.iterrows():
        sd_is, st_is = p4c1.shrunk_stats(row["sleeve"], row["bucket_key"],
                                         bucket_full, parent_full)
        sd_oos, st_oos = p4c1.shrunk_stats(row["sleeve"], row["bucket_key"],
                                           bucket_train, parent_train)
        test.at[i, "shrunk_dpbp_is"] = sd_is
        test.at[i, "shrunk_tail_is"] = st_is
        test.at[i, "shrunk_dpbp_oos"] = sd_oos
        test.at[i, "shrunk_tail_oos"] = st_oos

    # Build full-distribution percentile rankings
    # IS distribution: full cohort shrunk stats
    cands_full_shrunk = cands_full.copy()
    cands_full_shrunk["shrunk_dpbp"] = 0.0
    cands_full_shrunk["shrunk_tail"] = 0.0
    for i, row in cands_full_shrunk.iterrows():
        sd, st = p4c1.shrunk_stats(row["sleeve"], row["bucket_key"],
                                   bucket_full, parent_full)
        cands_full_shrunk.at[i, "shrunk_dpbp"] = sd
        cands_full_shrunk.at[i, "shrunk_tail"] = st

    train_shrunk = train.copy()
    train_shrunk["shrunk_dpbp"] = 0.0
    train_shrunk["shrunk_tail"] = 0.0
    for i, row in train_shrunk.iterrows():
        sd, st = p4c1.shrunk_stats(row["sleeve"], row["bucket_key"],
                                   bucket_train, parent_train)
        train_shrunk.at[i, "shrunk_dpbp"] = sd
        train_shrunk.at[i, "shrunk_tail"] = st

    # IS priority percentile (vs full cohort)
    def percentile_score(val, ref):
        return (ref < val).sum() / len(ref) * 100

    test["return_pct_is"] = test["shrunk_dpbp_is"].apply(
        lambda v: percentile_score(v, cands_full_shrunk["shrunk_dpbp"]))
    test["tail_pct_is"] = test["shrunk_tail_is"].apply(
        lambda v: percentile_score(v, cands_full_shrunk["shrunk_tail"]))
    test["priority_is"] = (p4c1.PRIORITY_RETURN_WEIGHT * test["return_pct_is"]
                           - p4c1.PRIORITY_TAIL_WEIGHT * test["tail_pct_is"])

    test["return_pct_oos"] = test["shrunk_dpbp_oos"].apply(
        lambda v: percentile_score(v, train_shrunk["shrunk_dpbp"]))
    test["tail_pct_oos"] = test["shrunk_tail_oos"].apply(
        lambda v: percentile_score(v, train_shrunk["shrunk_tail"]))
    test["priority_oos"] = (p4c1.PRIORITY_RETURN_WEIGHT * test["return_pct_oos"]
                            - p4c1.PRIORITY_TAIL_WEIGHT * test["tail_pct_oos"])

    test["priority_diff"] = test["priority_is"] - test["priority_oos"]
    test.to_csv(OUT / "q072_p4c6_walkforward_compare.csv", index=False)

    print("\n" + "=" * 70)
    print("Q072 P4C.6 — Walk-Forward: IS vs OOS Priority Comparison")
    print("=" * 70)

    print(f"\nTest sample: {len(test)} candidates (2019-2026)")
    print(f"\nPriority score IS vs OOS:")
    print(f"  IS  mean: {test.priority_is.mean():.1f}  std: {test.priority_is.std():.1f}")
    print(f"  OOS mean: {test.priority_oos.mean():.1f}  std: {test.priority_oos.std():.1f}")
    print(f"  Mean abs diff: {test.priority_diff.abs().mean():.1f}")
    print(f"  Correlation IS vs OOS: {test[['priority_is', 'priority_oos']].corr().iloc[0, 1]:.3f}")

    print(f"\nBy sleeve (median priority_is / priority_oos / diff):")
    by_sleeve = test.groupby("sleeve").agg({
        "priority_is": "median",
        "priority_oos": "median",
        "priority_diff": "median",
    }).round(1)
    by_sleeve["n_test"] = test.groupby("sleeve").size()
    print(by_sleeve.to_string())

    # Rank stability: would priority ranking change between IS and OOS?
    test_sorted_is = test.sort_values("priority_is", ascending=False).reset_index(drop=True)
    test_sorted_oos = test.sort_values("priority_oos", ascending=False).reset_index(drop=True)
    # Spearman correlation of ranks
    test["rank_is"] = test["priority_is"].rank()
    test["rank_oos"] = test["priority_oos"].rank()
    spearman = test[["rank_is", "rank_oos"]].corr().iloc[0, 1]
    print(f"\nSpearman rank correlation (IS vs OOS rankings): {spearman:.3f}")
    print("  (>0.9 = stable; 0.7-0.9 = moderate; <0.7 = overfit warning)")


if __name__ == "__main__":
    main()
