"""Q072 P4C.1-3 — Priority Scoring + Confidence Haircut + Tie-break.

Per brief §P4C.1-3 (revised per round-2 2nd Quant review):

    priority = 0.6 × rank(expected_$/BP-day) − 0.4 × rank(tail_penalty)

    Global rank-percentile across all historical candidates.
    Strategy-specific 2-D bucket key.
    Shrinkage toward parent: n<5 → parent only; 5≤n<20 → 50/50; n≥20 → bucket.
    Tier tie-break only when |Δpriority| < 5 percentile points.

Strategy-specific bucket key:
    main BPS NNB / IC:              regime × IVP bucket
    DD Overlay:                     ddATH bucket × VIX bucket
    BPS_HV (aftermath permission):  VIX peak/off-peak state × current VIX
    HV Ladder:                      VIX bucket × VIX trend (10d slope sign)

Output: priority score function applied to 877 historical candidates;
        bucket lookup table; per-trade priority score CSV.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"
BASELINE = REPO / "research" / "q042" / "baseline_19y_trades.csv"
DD_TRADES = REPO / "data" / "q042_backtest_trades.csv"
HV_TRADES = OUT / "q072_hv_ladder_v2f_baseline_trades.csv"
IVP_DAILY = REPO / "research" / "q067" / "q067_daily_ivp_windows.csv"

SPX_NLV = 100_000.0
ES_NLV = 100_000.0
ES_MULTIPLIER = 50.0
ES_SPAN_FRAC = 0.05

PRIORITY_RETURN_WEIGHT = 0.6
PRIORITY_TAIL_WEIGHT = 0.4
TIER_TIE_BREAK_THRESHOLD = 5.0  # percentile points

# Tier groups (revised per reviewer per Q6)
TIER_MAP = {
    "Bull_Put_Spread_High_Vol": 1,         # rare + historically positive
    "DD_Overlay_B": 1,                     # dd15 + MA10 reclaim, rare
    "Iron_Condor_High_Vol": 2,             # high-vol opportunity
    "Bear_Call_Spread_High_Vol": 2,
    "HV_Ladder": 2,
    "DD_Overlay_A": 3,                     # dd4, more frequent
    "Bull_Put_Spread": 3,
    "Iron_Condor": 3,
    "Bull_Call_Diagonal": 3,
}


# ─── bucket key constructors ─────────────────────────────────────────────────
def regime_bucket(vix: float) -> str:
    if vix < 14: return "LOW_VOL"
    if vix < 22: return "NEUTRAL"
    if vix < 40: return "HIGH_VOL"
    return "EXTREME_VIX"


def ivp_bucket(ivp: float) -> str:
    if ivp < 30: return "ivp_low"
    if ivp < 43: return "ivp_mid_low"
    if ivp < 55: return "ivp_sweet"
    if ivp < 70: return "ivp_high"
    return "ivp_extreme"


def ddath_bucket(dd: float) -> str:
    if dd > -0.02: return "dd_lt2"
    if dd > -0.05: return "dd_2to5"
    if dd > -0.10: return "dd_5to10"
    return "dd_gt10"


def vix_bucket(vix: float) -> str:
    if vix < 15: return "vix_lt15"
    if vix < 18: return "vix_15to18"
    if vix < 22: return "vix_18to22"
    if vix < 26: return "vix_22to26"
    if vix < 30: return "vix_26to30"
    if vix < 40: return "vix_30to40"
    return "vix_gte40"


def vix_trend_bucket(slope_10d: float) -> str:
    if slope_10d > 1.0: return "rising"
    if slope_10d < -1.0: return "falling"
    return "flat"


def aftermath_state_bucket(in_aftermath: bool) -> str:
    return "in_aftermath" if in_aftermath else "not_aftermath"


def bucket_key(sleeve: str, snap: pd.Series) -> tuple:
    """Strategy-specific 2-D bucket key from daily snapshot."""
    if sleeve in ("Bull_Put_Spread", "Iron_Condor", "Bull_Call_Diagonal"):
        return (regime_bucket(snap["vix"]), ivp_bucket(snap["ivp_252"]))
    if sleeve in ("DD_Overlay_A", "DD_Overlay_B"):
        return (ddath_bucket(snap["ddath_max"]), vix_bucket(snap["vix"]))
    if sleeve in ("Bull_Put_Spread_High_Vol", "Iron_Condor_High_Vol",
                  "Bear_Call_Spread_High_Vol"):
        return (aftermath_state_bucket(snap["is_aftermath"]), vix_bucket(snap["vix"]))
    if sleeve == "HV_Ladder":
        return (vix_bucket(snap["vix"]), vix_trend_bucket(snap.get("vix_10d_slope", 0)))
    return ("unknown", "unknown")


# ─── load + build candidate features ─────────────────────────────────────────
def load_data():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    ivp = pd.read_csv(IVP_DAILY, parse_dates=["date"]).set_index("date")
    daily["ivp_252"] = ivp["ivp_252"].reindex(daily.index).ffill()
    daily["vix_10d_slope"] = daily["vix"].diff(10)
    daily["is_aftermath"] = daily["aftermath_active"].astype(bool)

    baseline = pd.read_csv(BASELINE, parse_dates=["entry_date", "exit_date"])
    baseline["strategy"] = baseline["strategy"].str.strip()
    dd = pd.read_csv(DD_TRADES, parse_dates=["entry_date", "exit_date"])
    hv = pd.read_csv(HV_TRADES, parse_dates=["entry_date", "exit_date"])
    return daily, baseline, dd, hv


def build_candidates_df(daily, baseline, dd, hv):
    """Build trade-level records with sleeve label, bucket key, realized $/BP-day & worst."""
    rows = []
    for _, t in baseline.iterrows():
        if t["entry_date"] not in daily.index:
            continue
        snap = daily.loc[t["entry_date"]]
        sleeve = t["strategy"].replace(" ", "_").replace("(", "").replace(")", "")
        bkey = bucket_key(sleeve, snap)
        days_held = max((t["exit_date"] - t["entry_date"]).days, 1)
        bp_dollar = t["bp_pct_account"] / 100 * SPX_NLV
        bp_days = bp_dollar * days_held
        dollar_per_bp_day = t["exit_pnl"] / bp_days if bp_days > 0 else 0
        rows.append({
            "sleeve": sleeve,
            "entry_date": t["entry_date"],
            "exit_date": t["exit_date"],
            "bucket_key": bkey,
            "bp_dollar": bp_dollar,
            "days_held": days_held,
            "exit_pnl": t["exit_pnl"],
            "dollar_per_bp_day": dollar_per_bp_day,
            "pool": "SPX_PM",
        })
    for _, t in dd.iterrows():
        if t["entry_date"] not in daily.index:
            continue
        snap = daily.loc[t["entry_date"]]
        sleeve = f"DD_Overlay_{t['sleeve_id']}"
        bkey = bucket_key(sleeve, snap)
        days_held = max((t["exit_date"] - t["entry_date"]).days, 1)
        bp_dollar = t["account_pct"] * SPX_NLV
        bp_days = bp_dollar * days_held
        dpbp = t["exit_pnl"] / bp_days if bp_days > 0 else 0
        rows.append({
            "sleeve": sleeve,
            "entry_date": t["entry_date"],
            "exit_date": t["exit_date"],
            "bucket_key": bkey,
            "bp_dollar": bp_dollar,
            "days_held": days_held,
            "exit_pnl": t["exit_pnl"],
            "dollar_per_bp_day": dpbp,
            "pool": "SPX_PM",
        })
    for _, t in hv.iterrows():
        if t["entry_date"] not in daily.index:
            continue
        snap = daily.loc[t["entry_date"]]
        bkey = bucket_key("HV_Ladder", snap)
        days_held = max((t["exit_date"] - t["entry_date"]).days, 1)
        bp_dollar = ES_SPAN_FRAC * t["entry_spx"] * ES_MULTIPLIER * t["contracts"]
        bp_days = bp_dollar * days_held
        dpbp = t["pnl"] / bp_days if bp_days > 0 else 0
        rows.append({
            "sleeve": "HV_Ladder",
            "entry_date": t["entry_date"],
            "exit_date": t["exit_date"],
            "bucket_key": bkey,
            "bp_dollar": bp_dollar,
            "days_held": days_held,
            "exit_pnl": t["pnl"],
            "dollar_per_bp_day": dpbp,
            "pool": "ES_SPAN",
        })
    return pd.DataFrame(rows)


def build_bucket_lookup(candidates_df: pd.DataFrame) -> pd.DataFrame:
    """For each (sleeve, bucket_key), compute median $/BP-day and worst trade per BP."""
    candidates_df = candidates_df.copy()
    candidates_df["worst_per_bp"] = candidates_df.apply(
        lambda r: r["exit_pnl"] / r["bp_dollar"] if r["bp_dollar"] > 0 else 0, axis=1
    )
    groups = candidates_df.groupby(["sleeve", "bucket_key"])
    rows = []
    for (sleeve, bkey), g in groups:
        # tail penalty per BP: |min trade per BP| + |CVaR 5% per BP|
        worst = g["worst_per_bp"].min()
        cvar5 = g["worst_per_bp"].quantile(0.05) if len(g) >= 5 else worst
        tail = abs(worst) + abs(cvar5)
        rows.append({
            "sleeve": sleeve,
            "bucket_key": str(bkey),
            "n": len(g),
            "median_dpbp": g["dollar_per_bp_day"].median(),
            "tail_per_bp": tail,
        })
    return pd.DataFrame(rows)


def build_parent_lookup(candidates_df: pd.DataFrame) -> pd.DataFrame:
    """Per-sleeve parent stats for shrinkage fallback."""
    candidates_df = candidates_df.copy()
    candidates_df["worst_per_bp"] = candidates_df.apply(
        lambda r: r["exit_pnl"] / r["bp_dollar"] if r["bp_dollar"] > 0 else 0, axis=1
    )
    rows = []
    for sleeve, g in candidates_df.groupby("sleeve"):
        worst = g["worst_per_bp"].min()
        cvar5 = g["worst_per_bp"].quantile(0.05)
        rows.append({
            "sleeve": sleeve,
            "parent_median_dpbp": g["dollar_per_bp_day"].median(),
            "parent_tail_per_bp": abs(worst) + abs(cvar5),
            "parent_n": len(g),
        })
    return pd.DataFrame(rows)


def shrunk_stats(sleeve: str, bkey: tuple,
                 bucket_lookup: pd.DataFrame,
                 parent_lookup: pd.DataFrame) -> tuple[float, float]:
    parent = parent_lookup[parent_lookup.sleeve == sleeve].iloc[0]
    bk = bucket_lookup[(bucket_lookup.sleeve == sleeve)
                       & (bucket_lookup.bucket_key == str(bkey))]
    if len(bk) == 0 or bk.iloc[0]["n"] < 5:
        return float(parent.parent_median_dpbp), float(parent.parent_tail_per_bp)
    row = bk.iloc[0]
    if row["n"] < 20:
        return (0.5 * row["median_dpbp"] + 0.5 * parent.parent_median_dpbp,
                0.5 * row["tail_per_bp"] + 0.5 * parent.parent_tail_per_bp)
    return float(row["median_dpbp"]), float(row["tail_per_bp"])


def main():
    daily, baseline, dd, hv = load_data()
    cands = build_candidates_df(daily, baseline, dd, hv)
    print(f"Built {len(cands)} candidate records")

    bucket_lookup = build_bucket_lookup(cands)
    parent_lookup = build_parent_lookup(cands)

    print(f"\nBucket lookup ({len(bucket_lookup)} unique buckets):")
    print(bucket_lookup.sort_values("n", ascending=False).head(15).to_string(index=False))

    print(f"\nParent (per-sleeve) lookup:")
    print(parent_lookup.to_string(index=False))

    # Apply shrinkage to each candidate
    print("\nApplying shrinkage + computing global rank-percentile priority...")
    cands["shrunk_dpbp"] = 0.0
    cands["shrunk_tail"] = 0.0
    for i, row in cands.iterrows():
        sd, st = shrunk_stats(row["sleeve"], row["bucket_key"],
                              bucket_lookup, parent_lookup)
        cands.at[i, "shrunk_dpbp"] = sd
        cands.at[i, "shrunk_tail"] = st

    # Global rank-percentile across all candidates
    cands["return_pct"] = cands["shrunk_dpbp"].rank(pct=True) * 100
    cands["tail_pct"] = cands["shrunk_tail"].rank(pct=True) * 100
    cands["priority"] = (
        PRIORITY_RETURN_WEIGHT * cands["return_pct"]
        - PRIORITY_TAIL_WEIGHT * cands["tail_pct"]
    )
    cands["tier"] = cands["sleeve"].map(TIER_MAP).fillna(3).astype(int)

    cands.to_csv(OUT / "q072_p4c1_candidates_with_priority.csv", index=False)
    bucket_lookup.to_csv(OUT / "q072_p4c1_bucket_lookup.csv", index=False)
    parent_lookup.to_csv(OUT / "q072_p4c1_parent_lookup.csv", index=False)

    print("\n" + "=" * 70)
    print("Q072 P4C.1 — Priority Score Summary")
    print("=" * 70)
    print(f"\nPriority score distribution by sleeve (median / P25 / P75):")
    by_sleeve = cands.groupby("sleeve")["priority"].agg(
        ["count", "median", lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
    )
    by_sleeve.columns = ["n", "median", "P25", "P75"]
    print(by_sleeve.sort_values("median", ascending=False).to_string())

    print(f"\nPriority score quartile by sleeve+tier (Tier {','.join(str(t) for t in sorted(TIER_MAP.values()))}):")
    for tier in sorted(set(TIER_MAP.values())):
        tier_cands = cands[cands.tier == tier]
        print(f"  Tier {tier}: n={len(tier_cands)} median_priority={tier_cands.priority.median():.1f}")

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
