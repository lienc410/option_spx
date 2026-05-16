"""Q072 P1 — Episode Detection + Capital Stack + Co-activation.

Per `research/q072/q072_research_brief_2026-05-15.md` §P1.

Outputs:
    q072_p1_daily_flags.csv         — 19y daily 4-state + episode_id + ddATH
    q072_p1_episodes.csv            — per-episode summary
    q072_p1_capital_stack.csv       — daily BP per pool
    q072_p1_coactivation_matrix.csv — sleeve-sleeve + main-sleeve matrices

NOTES on BP normalization:
    SPX PM pool uses $100k baseline NLV seed (matches q042 baseline_19y_trades
    convention; bp_pct_account / account_pct columns are already % of $100k).
    /ES pool allocation set to $50k placeholder (separate sub-portfolio); V2f
    SPAN per contract approximated as 0.05 × entry_spx × 50 ($ES multiplier).
    Combined economic NLV = $150k. These are placeholders for directional
    reading per brief; absolute %'s should not be over-interpreted at P1.

NOTES on HV Ladder placeholder:
    V2f filtered mode (current production-leaning code, no IVP gate). Will be
    re-run once Q071 final config locks (per brief Phase ordering).
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_FLAGS = REPO / "research" / "q064" / "q064_p1_daily_flags.csv"
BASELINE_TRADES = REPO / "research" / "q042" / "baseline_19y_trades.csv"
DD_OVERLAY_TRADES = REPO / "data" / "q042_backtest_trades.csv"
HV_LADDER_TRADES = OUT / "q072_hv_ladder_v2f_baseline_trades.csv"

# Normalization constants (placeholder per brief)
# SPX_NLV matches q042 baseline_19y_trades convention; ES_NLV matches V2f
# backtest's own NLV_SEED. Combined NLV = $200k assumes PM holds both books
# in independently capitalized broker accounts.
SPX_NLV = 100_000.0
ES_NLV = 100_000.0
COMBINED_NLV = SPX_NLV + ES_NLV
ES_MULTIPLIER = 50.0  # /ES point multiplier
ES_SPAN_FRAC = 0.05   # SPAN ≈ 5% of notional (rough heuristic)

# Stress episode parameters
STRESS_VIX = 22.0
STRESS_DDATH_PCT = 0.04  # 4% drawdown from 20d/60d high
EPISODE_GAP = 3           # ≥ 3 stress-False days closes episode

# BP threshold reporting
BP_THRESH = [0.30, 0.40, 0.50]


def load_data() -> dict:
    print("Loading data...")
    with open(SPX_PKL, "rb") as f:
        spx_raw = pickle.load(f)
    spx = spx_raw[["Close"]].copy() if "Close" in spx_raw.columns else spx_raw.copy()
    spx.columns = ["close"]
    spx.index = pd.to_datetime(spx.index).tz_localize(None).normalize()
    spx = spx[(spx.index >= "2007-01-01") & (spx.index <= "2026-05-10")]
    spx["ath_20d"] = spx["close"].rolling(20, min_periods=1).max()
    spx["ath_60d"] = spx["close"].rolling(60, min_periods=1).max()
    spx["dd_20d"] = spx["close"] / spx["ath_20d"] - 1.0
    spx["dd_60d"] = spx["close"] / spx["ath_60d"] - 1.0

    vix_flags = pd.read_csv(VIX_FLAGS, parse_dates=["date"])
    vix_flags = vix_flags.set_index("date")

    baseline = pd.read_csv(BASELINE_TRADES, parse_dates=["entry_date", "exit_date"])
    dd_overlay = pd.read_csv(DD_OVERLAY_TRADES, parse_dates=["entry_date", "exit_date"])
    hv_ladder = pd.read_csv(HV_LADDER_TRADES, parse_dates=["entry_date", "exit_date"])

    print(f"  SPX rows: {len(spx)}")
    print(f"  VIX/aftermath flags: {len(vix_flags)}")
    print(f"  baseline trades: {len(baseline)} (incl BPS_HV)")
    print(f"  DD Overlay trades: {len(dd_overlay)}")
    print(f"  HV Ladder (V2f filtered) trades: {len(hv_ladder)}")
    return {"spx": spx, "vix": vix_flags, "baseline": baseline,
            "dd": dd_overlay, "hv": hv_ladder}


def build_active_flags(d: dict) -> pd.DataFrame:
    print("Building daily 4-state flags + BP per pool...")
    idx = d["vix"].index  # use VIX flags as canonical trading-day index
    df = pd.DataFrame(index=idx)
    df["vix"] = d["vix"]["vix"]
    df["is_aftermath"] = d["vix"]["is_aftermath"].astype(bool)

    spx_aligned = d["spx"].reindex(idx).ffill()
    df["spx_close"] = spx_aligned["close"]
    df["dd_20d"] = spx_aligned["dd_20d"]
    df["dd_60d"] = spx_aligned["dd_60d"]
    df["ddath_max"] = df[["dd_20d", "dd_60d"]].min(axis=1)  # most negative

    df["main_active"] = False
    df["main_bp"] = 0.0          # % of SPX NLV (baseline incl BPS_HV)
    df["dd_overlay_active"] = False
    df["dd_overlay_bp"] = 0.0    # % of SPX NLV
    df["hv_ladder_active"] = False
    df["hv_ladder_bp"] = 0.0     # % of /ES NLV
    df["hv_ladder_contracts"] = 0.0

    # baseline trades (main + BPS_HV occupy same SPX PM pool)
    for _, row in d["baseline"].iterrows():
        m = (df.index >= row["entry_date"]) & (df.index <= row["exit_date"])
        df.loc[m, "main_active"] = True
        df.loc[m, "main_bp"] += row["bp_pct_account"]

    # DD Overlay trades
    for _, row in d["dd"].iterrows():
        m = (df.index >= row["entry_date"]) & (df.index <= row["exit_date"])
        df.loc[m, "dd_overlay_active"] = True
        df.loc[m, "dd_overlay_bp"] += row["account_pct"] * 100  # store as %

    # HV Ladder trades (sum SPAN per active contract)
    for _, row in d["hv"].iterrows():
        m = (df.index >= row["entry_date"]) & (df.index <= row["exit_date"])
        df.loc[m, "hv_ladder_active"] = True
        span_per_contract = ES_SPAN_FRAC * row["entry_spx"] * ES_MULTIPLIER
        df.loc[m, "hv_ladder_bp"] += span_per_contract * row["contracts"]
        df.loc[m, "hv_ladder_contracts"] += row["contracts"]
    df["hv_ladder_bp"] = df["hv_ladder_bp"] / ES_NLV * 100  # convert to %

    # aftermath_active = is_aftermath permission window (NOT BPS_HV trade)
    df["aftermath_active"] = df["is_aftermath"]

    # combined economic BP (SPX + /ES, normalized to combined NLV)
    df["combined_bp_dollar"] = (
        df["main_bp"] / 100 * SPX_NLV
        + df["dd_overlay_bp"] / 100 * SPX_NLV
        + df["hv_ladder_bp"] / 100 * ES_NLV
    )
    df["combined_bp_pct"] = df["combined_bp_dollar"] / COMBINED_NLV * 100

    return df


def _label_episodes(flag: pd.Series) -> np.ndarray:
    """Group consecutive True days into episodes; tolerate gaps < EPISODE_GAP."""
    eid = np.full(len(flag), -1, dtype=int)
    cur = -1
    gap = EPISODE_GAP
    for i, s in enumerate(flag.values):
        if s:
            if gap >= EPISODE_GAP:
                cur += 1
            eid[i] = cur
            gap = 0
        else:
            gap += 1
            if gap < EPISODE_GAP and cur >= 0:
                eid[i] = cur
    return eid


def detect_episodes(df: pd.DataFrame) -> pd.DataFrame:
    print("Detecting stress episodes (broad + tight definitions)...")
    df = df.copy()
    # Broad: brief original spec (any sleeve including HV Ladder counts as stress)
    df["stress_broad"] = (
        (df["vix"] >= STRESS_VIX)
        | (df["ddath_max"] <= -STRESS_DDATH_PCT)
        | df["dd_overlay_active"]
        | df["aftermath_active"]
        | df["hv_ladder_active"]
    )
    # Tight: refined to exclude HV Ladder structural always-on. HV Ladder is a
    # rolling ladder (active ~93% of days), so including it makes episodes merge
    # into mega-blocks that lose discriminating power. Tight definition isolates
    # true stress windows (VIX spike / dd / DD-overlay or Aftermath fires).
    df["stress_tight"] = (
        (df["vix"] >= STRESS_VIX)
        | (df["ddath_max"] <= -STRESS_DDATH_PCT)
        | df["dd_overlay_active"]
        | df["aftermath_active"]
    )
    df["episode_id_broad"] = _label_episodes(df["stress_broad"])
    df["episode_id_tight"] = _label_episodes(df["stress_tight"])
    df["episode_id"] = df["episode_id_tight"]  # default = tight for downstream
    return df


def summarize_episodes(df: pd.DataFrame, eid_col: str = "episode_id_tight") -> pd.DataFrame:
    print(f"Summarizing episodes ({eid_col})...")
    rows = []
    for eid, sub in df[df[eid_col] >= 0].groupby(eid_col):
        sleeve_cols = ["main_active", "dd_overlay_active", "aftermath_active", "hv_ladder_active"]
        sleeves_seen = [c.replace("_active", "") for c in sleeve_cols if sub[c].any()]
        # day with max ≥2 sleeves overlap
        sleeve_count = sub[sleeve_cols].sum(axis=1)
        rows.append({
            "episode_id": int(eid),
            "start": sub.index.min().date(),
            "end": sub.index.max().date(),
            "length_days": len(sub),
            "n_sleeves_total": len(sleeves_seen),
            "sleeves_seen": ",".join(sleeves_seen),
            "max_concurrent_sleeves": int(sleeve_count.max()),
            "days_2plus_sleeves": int((sleeve_count >= 2).sum()),
            "days_3plus_sleeves": int((sleeve_count >= 3).sum()),
            "peak_main_bp": round(sub["main_bp"].max(), 2),
            "peak_dd_bp": round(sub["dd_overlay_bp"].max(), 2),
            "peak_hv_bp": round(sub["hv_ladder_bp"].max(), 2),
            "peak_combined_bp": round(sub["combined_bp_pct"].max(), 2),
            "peak_drawdown": round(sub["ddath_max"].min(), 4),
            "peak_vix": round(sub["vix"].max(), 2),
        })
    return pd.DataFrame(rows)


def coactivation_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    print("Building co-activation matrices...")
    sleeves = ["main_active", "dd_overlay_active", "aftermath_active", "hv_ladder_active"]
    n = len(df)
    pair_rows = []
    for i, a in enumerate(sleeves):
        for j, b in enumerate(sleeves):
            if i > j:
                continue
            both = (df[a] & df[b]).sum()
            either = (df[a] | df[b]).sum()
            pair_rows.append({
                "sleeve_a": a.replace("_active", ""),
                "sleeve_b": b.replace("_active", ""),
                "both_days": int(both),
                "both_pct": round(both / n * 100, 2),
                "a_only_days": int((df[a] & ~df[b]).sum()),
                "b_only_days": int((df[b] & ~df[a]).sum()),
                "either_days": int(either),
                "P(a_and_b|a)": round(both / df[a].sum() * 100, 2) if df[a].sum() else None,
                "P(a_and_b|b)": round(both / df[b].sum() * 100, 2) if df[b].sum() else None,
            })
    pair_df = pd.DataFrame(pair_rows)

    # 4-way co-occurrence (16 states)
    state_rows = []
    for state in range(16):
        bits = [(state >> i) & 1 for i in range(4)]
        mask = np.ones(len(df), dtype=bool)
        for k, s in enumerate(sleeves):
            mask &= (df[s].values == bool(bits[k]))
        state_rows.append({
            "main": bits[0], "dd_overlay": bits[1],
            "aftermath": bits[2], "hv_ladder": bits[3],
            "days": int(mask.sum()),
            "pct": round(mask.sum() / n * 100, 2),
        })
    state_df = pd.DataFrame(state_rows).sort_values("days", ascending=False).reset_index(drop=True)

    # global aggregates
    any_sleeve = (df["dd_overlay_active"] | df["aftermath_active"] | df["hv_ladder_active"])
    n_active_sleeves = (df["dd_overlay_active"].astype(int)
                        + df["aftermath_active"].astype(int)
                        + df["hv_ladder_active"].astype(int))
    aggregates = {
        "total_days": n,
        "any_sleeve_active_days": int(any_sleeve.sum()),
        "any_sleeve_active_pct": round(any_sleeve.sum() / n * 100, 2),
        "P(≥2 sleeves | any sleeve)":
            round(((n_active_sleeves >= 2) & any_sleeve).sum() / any_sleeve.sum() * 100, 2),
        "P(3 sleeves | any sleeve)":
            round((n_active_sleeves >= 3).sum() / any_sleeve.sum() * 100, 2)
                if any_sleeve.sum() else None,
        "P(main | any sleeve)":
            round((df["main_active"] & any_sleeve).sum() / any_sleeve.sum() * 100, 2),
    }
    return pair_df, state_df, aggregates


def capital_stack_summary(df: pd.DataFrame) -> pd.DataFrame:
    print("Capital stack summary by pool...")
    pools = {
        "SPX_PM_pool": df["main_bp"] + df["dd_overlay_bp"],
        "ES_pool": df["hv_ladder_bp"],
        "combined_economic": df["combined_bp_pct"],
    }
    # filter to stress episodes for stress-window stats
    in_episode = df["episode_id"] >= 0
    rows = []
    for name, series in pools.items():
        rows.append({
            "pool": name,
            "avg_bp_pct": round(series.mean(), 2),
            "P90_bp_pct": round(np.percentile(series, 90), 2),
            "P95_bp_pct": round(np.percentile(series, 95), 2),
            "peak_bp_pct": round(series.max(), 2),
            "peak_during_stress": round(series[in_episode].max(), 2) if in_episode.any() else None,
            "days_gt_30pct": int((series > 30).sum()),
            "days_gt_40pct": int((series > 40).sum()),
            "days_gt_50pct": int((series > 50).sum()),
        })
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = load_data()
    df = build_active_flags(d)
    df = detect_episodes(df)
    ep_tight = summarize_episodes(df, "episode_id_tight")
    ep_broad = summarize_episodes(df, "episode_id_broad")
    pair_df, state_df, aggregates = coactivation_matrix(df)
    cap_df = capital_stack_summary(df)

    # save outputs
    daily_out = df.reset_index().rename(columns={"index": "date"})
    daily_out.to_csv(OUT / "q072_p1_daily_flags.csv", index=False, float_format="%.4f")
    ep_tight["definition"] = "tight"
    ep_broad["definition"] = "broad"
    ep_df = pd.concat([ep_tight, ep_broad], ignore_index=True)
    ep_df.to_csv(OUT / "q072_p1_episodes.csv", index=False)
    cap_df.to_csv(OUT / "q072_p1_capital_stack.csv", index=False)
    pair_df.to_csv(OUT / "q072_p1_coactivation_matrix.csv", index=False)
    state_df.to_csv(OUT / "q072_p1_coactivation_4way.csv", index=False)

    # console summary
    print("\n" + "=" * 60)
    print("Q072 P1 — Summary")
    print("=" * 60)
    print(f"\nDaily aggregates:")
    for k, v in aggregates.items():
        print(f"  {k}: {v}")

    for label, sub in [("TIGHT (no HV)", ep_tight), ("BROAD (incl HV)", ep_broad)]:
        print(f"\nEpisodes — {label}: n={len(sub)}")
        if len(sub):
            print(f"  median length: {sub.length_days.median():.0f} days  "
                  f"P95: {sub.length_days.quantile(0.95):.0f}  "
                  f"max: {sub.length_days.max()} days")
            print(f"  ≥2 sleeves overlap: "
                  f"{(sub['max_concurrent_sleeves'] >= 2).sum()}/{len(sub)} "
                  f"({(sub['max_concurrent_sleeves'] >= 2).mean() * 100:.1f}%)")
            print(f"  ≥3 sleeves overlap: "
                  f"{(sub['max_concurrent_sleeves'] >= 3).sum()}/{len(sub)}")
            print(f"  peak combined BP within episode (median / P95 / max): "
                  f"{sub['peak_combined_bp'].median():.1f}% / "
                  f"{sub['peak_combined_bp'].quantile(0.95):.1f}% / "
                  f"{sub['peak_combined_bp'].max():.1f}%")

    print(f"\nCapital stack by pool:")
    print(cap_df.to_string(index=False))

    print(f"\nPairwise overlap (sleeve-sleeve only, excluding main):")
    sleeve_pairs = pair_df[
        (~pair_df.sleeve_a.isin(["main"]) | ~pair_df.sleeve_b.isin(["main"]))
        & (pair_df.sleeve_a != pair_df.sleeve_b)
    ]
    sleeve_only = pair_df[
        (~pair_df.sleeve_a.eq("main")) & (~pair_df.sleeve_b.eq("main"))
        & (pair_df.sleeve_a != pair_df.sleeve_b)
    ]
    print(sleeve_only[["sleeve_a", "sleeve_b", "both_days", "both_pct",
                       "P(a_and_b|a)", "P(a_and_b|b)"]].to_string(index=False))

    print(f"\nTop 4-way co-occurrence states:")
    print(state_df.head(8).to_string(index=False))

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
