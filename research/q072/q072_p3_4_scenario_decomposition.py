"""Q072 P3.4 — Four-Path Scenario Decomposition.

Per brief §P3.4: classify 71 tight stress episodes from P1 into 4 SPX/VIX
path types and report sleeve P&L per class.

Path types:
    fast_recovery: episode end SPX ≥ episode start * 0.99 AND VIX ≤ peak/2
    sideways_crush: SPX range within ±3% AND VIX monotonically declining
    second_leg_selloff: a new lower low appears > 14 days after episode start
    pure_vol_spike: VIX > 30 but SPX dd shallow (-3% to 0) and recovers fast

For each episode × class: peak combined BP, sleeve aggregate P&L (using P3.3
linear-distribution daily P&L series), max combined drawdown, time to recovery.

Outputs:
    q072_p3_4_scenarios.csv      — every tight episode with path class + sleeve metrics
    q072_p3_4_class_summary.csv  — aggregate per path class × sample split
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"
EPISODES = OUT / "q072_p1_episodes.csv"
DAILY_PNL = OUT / "q072_p3_3_daily_pnl.csv"

SPLITS = {
    "full":     ("2007-01-01", "2026-05-13"),
    "post2020": ("2020-01-01", "2026-05-13"),
    "recent2y": ("2024-01-01", "2026-05-13"),
}


def classify_episode(sub_daily: pd.DataFrame) -> str:
    """Classify a tight episode into one of 4 path classes."""
    spx0 = sub_daily["spx_close"].iloc[0]
    spxN = sub_daily["spx_close"].iloc[-1]
    spx_min = sub_daily["spx_close"].min()
    vix0 = sub_daily["vix"].iloc[0]
    vix_peak = sub_daily["vix"].max()
    dd_min = sub_daily["ddath_max"].min()

    spx_max = sub_daily["spx_close"].max()
    spx_range_pct = (spx_max - spx_min) / spx0

    # day index of SPX min
    min_idx = sub_daily["spx_close"].idxmin()
    days_from_start_to_min = (min_idx - sub_daily.index[0]).days

    # Second-leg: SPX min happens > 14 days after episode start AND a higher SPX
    # exists between start and min (indicating a bounce that then re-bottomed)
    if days_from_start_to_min > 14:
        pre_min = sub_daily.loc[sub_daily.index[0]:min_idx, "spx_close"]
        if len(pre_min) > 5 and pre_min.iloc[1:-1].max() > spx_min * 1.02:
            # there was a >2% bounce before re-bottoming
            return "second_leg_selloff"

    # Pure vol spike: VIX>30 but SPX dd shallow
    if vix_peak > 30 and dd_min > -0.05 and (spxN / spx0 - 1) > -0.02:
        return "pure_vol_spike"

    # Fast recovery: ended at or above start * 0.99 AND VIX ≤ peak/2
    if spxN >= spx0 * 0.99 and sub_daily["vix"].iloc[-1] <= vix_peak * 0.6:
        return "fast_recovery"

    # Sideways crush: SPX range < 3% AND VIX declining from peak
    if spx_range_pct < 0.06 and sub_daily["vix"].iloc[-1] < vix_peak * 0.7:
        return "sideways_crush"

    # Default: ongoing stress (no clear class)
    return "unclassified"


def main():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    eps = pd.read_csv(EPISODES, parse_dates=["start", "end"])
    eps_tight = eps[eps.definition == "tight"].copy()
    pnl = pd.read_csv(DAILY_PNL, parse_dates=["date"]).set_index("date")

    print(f"Classifying {len(eps_tight)} tight episodes...")
    rows = []
    for _, e in eps_tight.iterrows():
        sub_daily = daily.loc[e["start"]:e["end"]]
        sub_pnl = pnl.loc[e["start"]:e["end"]]
        if len(sub_daily) < 3:
            continue
        cls = classify_episode(sub_daily)

        # aggregate sleeve P&L over episode
        sleeve_pnl = sub_pnl[["main", "aftermath", "dd_overlay", "hv_ladder"]].sum()
        combined_pnl_series = sub_pnl["portfolio_total"]
        peak_dd_combined = (combined_pnl_series.cumsum().cummax()
                            - combined_pnl_series.cumsum()).max()
        # worst 5d / 10d / 20d rolling sum
        roll5 = combined_pnl_series.rolling(5).sum().min()
        roll10 = combined_pnl_series.rolling(10).sum().min()
        roll20 = combined_pnl_series.rolling(20).sum().min()

        rows.append({
            "episode_id": int(e["episode_id"]),
            "start": e["start"].date(),
            "end": e["end"].date(),
            "length_days": int(e["length_days"]),
            "path_class": cls,
            "peak_vix": float(e["peak_vix"]),
            "peak_drawdown_spx": float(e["peak_drawdown"]) if not pd.isna(e["peak_drawdown"]) else None,
            "peak_combined_bp": float(e["peak_combined_bp"]),
            "max_concurrent_sleeves": int(e["max_concurrent_sleeves"]),
            "main_pnl": round(float(sleeve_pnl["main"]), 0),
            "aftermath_pnl": round(float(sleeve_pnl["aftermath"]), 0),
            "dd_overlay_pnl": round(float(sleeve_pnl["dd_overlay"]), 0),
            "hv_ladder_pnl": round(float(sleeve_pnl["hv_ladder"]), 0),
            "combined_pnl": round(float(combined_pnl_series.sum()), 0),
            "combined_pnl_dd": round(float(peak_dd_combined), 0),
            "worst_5d": round(float(roll5), 0),
            "worst_10d": round(float(roll10), 0),
            "worst_20d": round(float(roll20), 0),
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q072_p3_4_scenarios.csv", index=False)

    # Class summary across splits
    summary_rows = []
    for split_name, (s, e) in SPLITS.items():
        sub = df[(pd.to_datetime(df["start"]) >= s) & (pd.to_datetime(df["start"]) <= e)]
        for cls in ["fast_recovery", "sideways_crush", "second_leg_selloff",
                    "pure_vol_spike", "unclassified"]:
            csub = sub[sub.path_class == cls]
            if len(csub) == 0:
                continue
            summary_rows.append({
                "split": split_name,
                "path_class": cls,
                "n_episodes": len(csub),
                "median_length": int(csub.length_days.median()),
                "median_peak_vix": round(float(csub.peak_vix.median()), 1),
                "median_peak_dd_spx": round(float(csub.peak_drawdown_spx.dropna().median()), 4)
                    if csub.peak_drawdown_spx.notna().any() else None,
                "median_peak_combined_bp": round(float(csub.peak_combined_bp.median()), 1),
                "median_combined_pnl": round(float(csub.combined_pnl.median()), 0),
                "worst_combined_pnl": round(float(csub.combined_pnl.min()), 0),
                "median_main_pnl": round(float(csub.main_pnl.median()), 0),
                "median_dd_pnl": round(float(csub.dd_overlay_pnl.median()), 0),
                "median_aftermath_pnl": round(float(csub.aftermath_pnl.median()), 0),
                "median_hv_pnl": round(float(csub.hv_ladder_pnl.median()), 0),
                "median_worst_20d": round(float(csub.worst_20d.median()), 0),
                "worst_20d_min": round(float(csub.worst_20d.min()), 0),
            })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUT / "q072_p3_4_class_summary.csv", index=False)

    print("\n" + "=" * 70)
    print("Q072 P3.4 — Summary")
    print("=" * 70)

    print(f"\nPath class distribution (all 71 tight episodes):")
    print(df.path_class.value_counts())

    print(f"\nClass summary across splits:")
    for split in ["full", "post2020", "recent2y"]:
        print(f"\n--- {split} ---")
        view = summary_df[summary_df.split == split][
            ["path_class", "n_episodes", "median_length", "median_peak_combined_bp",
             "median_main_pnl", "median_dd_pnl", "median_aftermath_pnl",
             "median_hv_pnl", "median_combined_pnl", "worst_combined_pnl",
             "median_worst_20d", "worst_20d_min"]
        ]
        print(view.to_string(index=False))

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
