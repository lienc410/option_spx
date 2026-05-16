"""Q072 P2 — Entry Profile + HV Ladder Background Overlay.

Per `research/q072/q072_research_brief_2026-05-15.md` §P2, refined by PM gate
decision 2026-05-15 (see q072_p1_findings_2026-05-15.md §reclassification).

Structure (PM-revised):
    P2A — DD Overlay vs Aftermath entry feature comparison
          (Are they two expressions of the same stress signal?)
    P2B — HV Ladder background-state overlay
          (When stress sleeve fires, how much short-vol inventory is already on?)

Sample splits per PM:
    - full          2007-01 to 2026-05
    - post-2020     2020-01 onward (current architecture window)
    - recent        2024-01 onward (last 2y; most relevant for go-forward)

HV Ladder treated as STRUCTURAL SHORT-VOL ENGINE (active ~65% of days),
not as a stress-period sleeve.

Outputs:
    q072_p2_entries.csv             — every stress-sleeve entry with features
    q072_p2_entry_profile_stats.csv — distribution stats (KS / median / quartiles)
    q072_p2_hv_background.csv       — HV Ladder snapshot at each stress entry
    q072_p2_clustering.csv          — k-means cluster assignments
    q072_p2_findings_<date>.md      — narrative memo
"""

from __future__ import annotations

from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"
DD_OVERLAY = REPO / "data" / "q042_backtest_trades.csv"
HV_LADDER = OUT / "q072_hv_ladder_v2f_baseline_trades.csv"
IVP_DAILY = REPO / "research" / "q067" / "q067_daily_ivp_windows.csv"
VIX_FLAGS = REPO / "research" / "q064" / "q064_p1_daily_flags.csv"

SPLITS = {
    "full":      ("2007-01-01", "2026-05-13"),
    "post2020":  ("2020-01-01", "2026-05-13"),
    "recent2y":  ("2024-01-01", "2026-05-13"),
}

ES_MULTIPLIER = 50.0
ES_SPAN_FRAC = 0.05
ES_NLV = 100_000.0


def regime(vix: float) -> str:
    if vix < 14:
        return "LOW_VOL"
    elif vix < 22:
        return "NEUTRAL"
    elif vix < 40:
        return "HIGH_VOL"
    else:
        return "EXTREME_VIX"


def load_data() -> dict:
    print("Loading P1 daily flags + market context...")
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"])
    daily = daily.set_index("date")

    ivp = pd.read_csv(IVP_DAILY, parse_dates=["date"]).set_index("date")
    daily["ivp_252"] = ivp["ivp_252"].reindex(daily.index).ffill()

    # Build derived features on the daily frame
    daily["vix_10d_slope"] = daily["vix"].diff(10)
    daily["spx_20d_ret"] = daily["spx_close"].pct_change(20)
    daily["regime"] = daily["vix"].apply(regime)

    dd = pd.read_csv(DD_OVERLAY, parse_dates=["entry_date", "exit_date"])
    hv = pd.read_csv(HV_LADDER, parse_dates=["entry_date", "exit_date"])
    print(f"  daily rows: {len(daily)}  DD trades: {len(dd)}  HV trades: {len(hv)}")
    return {"daily": daily, "dd": dd, "hv": hv}


def aftermath_entry_dates(daily: pd.DataFrame) -> pd.DatetimeIndex:
    """An aftermath 'entry' is the first day of each contiguous is_aftermath run."""
    flag = daily["aftermath_active"].astype(bool).values
    entries = []
    prev = False
    for i, f in enumerate(flag):
        if f and not prev:
            entries.append(daily.index[i])
        prev = f
    return pd.DatetimeIndex(entries)


def extract_entry_features(d: dict) -> pd.DataFrame:
    print("Extracting entry features for DD Overlay + Aftermath...")
    daily = d["daily"]
    rows = []

    for _, t in d["dd"].iterrows():
        if t["entry_date"] not in daily.index:
            continue
        snap = daily.loc[t["entry_date"]]
        rows.append({
            "sleeve": "DD_Overlay",
            "sub_sleeve": f"DD_{t['sleeve_id']}",  # A or B
            "entry_date": t["entry_date"],
            "vix": snap["vix"],
            "vix_10d_slope": snap["vix_10d_slope"],
            "ddath_max": snap["ddath_max"],
            "ivp_252": snap["ivp_252"],
            "spx_20d_ret": snap["spx_20d_ret"],
            "regime": snap["regime"],
        })

    aft_dates = aftermath_entry_dates(daily)
    print(f"  aftermath window starts: {len(aft_dates)}")
    for dt in aft_dates:
        snap = daily.loc[dt]
        rows.append({
            "sleeve": "Aftermath",
            "sub_sleeve": "Aftermath",
            "entry_date": dt,
            "vix": snap["vix"],
            "vix_10d_slope": snap["vix_10d_slope"],
            "ddath_max": snap["ddath_max"],
            "ivp_252": snap["ivp_252"],
            "spx_20d_ret": snap["spx_20d_ret"],
            "regime": snap["regime"],
        })

    df = pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)
    print(f"  total entries: {len(df)}  (DD={sum(df.sleeve=='DD_Overlay')}, "
          f"Aftermath={sum(df.sleeve=='Aftermath')})")
    return df


def hv_background_snapshot(d: dict, entries: pd.DataFrame) -> pd.DataFrame:
    """For each stress-sleeve entry, snapshot HV Ladder active state that day."""
    print("Snapshotting HV Ladder background state at stress entries...")
    hv = d["hv"]
    rows = []
    for _, e in entries.iterrows():
        dt = e["entry_date"]
        active = hv[(hv["entry_date"] <= dt) & (hv["exit_date"] >= dt)]
        if len(active) == 0:
            rows.append({**e.to_dict(),
                         "hv_active_slots": 0,
                         "hv_total_contracts": 0.0,
                         "hv_avg_age_days": None,
                         "hv_avg_entry_vix": None,
                         "hv_bp_dollar": 0.0,
                         "hv_bp_pct": 0.0,
                         })
            continue
        ages = (dt - active["entry_date"]).dt.days
        span = ES_SPAN_FRAC * active["entry_spx"] * ES_MULTIPLIER * active["contracts"]
        rows.append({**e.to_dict(),
                     "hv_active_slots": int(len(active)),
                     "hv_total_contracts": float(active["contracts"].sum()),
                     "hv_avg_age_days": float(ages.mean()),
                     "hv_avg_entry_vix": float(active["entry_vix"].mean()),
                     "hv_bp_dollar": float(span.sum()),
                     "hv_bp_pct": float(span.sum() / ES_NLV * 100),
                     })
    return pd.DataFrame(rows)


def distribution_stats(entries: pd.DataFrame, splits: dict) -> pd.DataFrame:
    """Compare DD Overlay vs Aftermath distributions across feature × split."""
    print("Computing distribution stats (KS + medians)...")
    features = ["vix", "vix_10d_slope", "ddath_max", "ivp_252", "spx_20d_ret"]
    rows = []
    for split_name, (s, e) in splits.items():
        sub = entries[(entries.entry_date >= s) & (entries.entry_date <= e)]
        dd = sub[sub.sleeve == "DD_Overlay"]
        af = sub[sub.sleeve == "Aftermath"]
        for f in features:
            dd_vals = dd[f].dropna()
            af_vals = af[f].dropna()
            if len(dd_vals) < 2 or len(af_vals) < 2:
                ks_stat, ks_p = None, None
            else:
                ks_stat, ks_p = stats.ks_2samp(dd_vals, af_vals)
            rows.append({
                "split": split_name,
                "feature": f,
                "dd_n": int(len(dd_vals)),
                "dd_median": round(float(dd_vals.median()), 4) if len(dd_vals) else None,
                "dd_p25": round(float(dd_vals.quantile(0.25)), 4) if len(dd_vals) else None,
                "dd_p75": round(float(dd_vals.quantile(0.75)), 4) if len(dd_vals) else None,
                "af_n": int(len(af_vals)),
                "af_median": round(float(af_vals.median()), 4) if len(af_vals) else None,
                "af_p25": round(float(af_vals.quantile(0.25)), 4) if len(af_vals) else None,
                "af_p75": round(float(af_vals.quantile(0.75)), 4) if len(af_vals) else None,
                "ks_stat": round(ks_stat, 4) if ks_stat is not None else None,
                "ks_p": round(ks_p, 5) if ks_p is not None else None,
                "distributions_differ_p005": (ks_p < 0.05) if ks_p is not None else None,
            })
    return pd.DataFrame(rows)


def _kmeans(X: np.ndarray, k: int = 3, n_iter: int = 50, seed: int = 42) -> np.ndarray:
    """Minimal k-means (no sklearn dep). Returns cluster labels."""
    rng = np.random.default_rng(seed)
    n = len(X)
    centers = X[rng.choice(n, k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(n_iter):
        # assign
        d2 = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = d2.argmin(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        # update centers
        for c in range(k):
            mask = labels == c
            if mask.any():
                centers[c] = X[mask].mean(axis=0)
    return labels


def cluster_entries(entries: pd.DataFrame) -> pd.DataFrame:
    """K-means on standardized features; report cluster assignments."""
    print("Clustering stress entries (k=3, custom k-means)...")
    features = ["vix", "vix_10d_slope", "ddath_max", "ivp_252", "spx_20d_ret"]
    df = entries[features + ["sleeve", "entry_date"]].dropna().reset_index(drop=True)
    # standardize
    X = df[features].values.astype(float)
    X = (X - X.mean(axis=0)) / X.std(axis=0)
    df["cluster"] = _kmeans(X, k=3)
    purity = (df.groupby(["cluster", "sleeve"]).size().unstack(fill_value=0))
    purity["total"] = purity.sum(axis=1)
    print(f"  cluster composition:\n{purity}")
    return df


def hv_background_split_summary(hv_bg: pd.DataFrame, splits: dict) -> pd.DataFrame:
    print("Summarizing HV Ladder background across splits...")
    rows = []
    for split_name, (s, e) in splits.items():
        sub = hv_bg[(hv_bg.entry_date >= s) & (hv_bg.entry_date <= e)]
        for sleeve in ["DD_Overlay", "Aftermath"]:
            ssub = sub[sub.sleeve == sleeve]
            if len(ssub) == 0:
                continue
            rows.append({
                "split": split_name,
                "stress_sleeve": sleeve,
                "n_entries": len(ssub),
                "pct_with_hv_active": round((ssub["hv_active_slots"] > 0).mean() * 100, 1),
                "hv_slots_median": float(ssub["hv_active_slots"].median()),
                "hv_slots_p75": float(ssub["hv_active_slots"].quantile(0.75)),
                "hv_slots_max": int(ssub["hv_active_slots"].max()),
                "hv_contracts_median": round(float(ssub["hv_total_contracts"].median()), 2),
                "hv_avg_age_median_days": (
                    round(float(ssub["hv_avg_age_days"].median()), 1)
                    if ssub["hv_avg_age_days"].notna().any() else None
                ),
                "hv_bp_pct_median": round(float(ssub["hv_bp_pct"].median()), 2),
                "hv_bp_pct_p75": round(float(ssub["hv_bp_pct"].quantile(0.75)), 2),
                "hv_bp_pct_max": round(float(ssub["hv_bp_pct"].max()), 2),
            })
    return pd.DataFrame(rows)


def main():
    d = load_data()
    entries = extract_entry_features(d)
    hv_bg = hv_background_snapshot(d, entries)
    dist = distribution_stats(entries, SPLITS)
    clusters = cluster_entries(entries)
    hv_summary = hv_background_split_summary(hv_bg, SPLITS)

    entries.to_csv(OUT / "q072_p2_entries.csv", index=False)
    hv_bg.to_csv(OUT / "q072_p2_hv_background.csv", index=False)
    dist.to_csv(OUT / "q072_p2_entry_profile_stats.csv", index=False)
    clusters.to_csv(OUT / "q072_p2_clustering.csv", index=False)
    hv_summary.to_csv(OUT / "q072_p2_hv_background_summary.csv", index=False)

    print("\n" + "=" * 60)
    print("Q072 P2 — Summary")
    print("=" * 60)

    print("\nP2A — Entry feature distributions (DD Overlay vs Aftermath):")
    for split in ["full", "post2020", "recent2y"]:
        print(f"\n--- {split} ---")
        sub = dist[dist.split == split]
        print(sub[["feature", "dd_n", "dd_median", "af_n", "af_median",
                   "ks_p", "distributions_differ_p005"]].to_string(index=False))

    print(f"\nP2B — HV Ladder background at stress entries:")
    print(hv_summary.to_string(index=False))

    print(f"\nCluster composition (k=3, all-history):")
    purity = clusters.groupby(["cluster", "sleeve"]).size().unstack(fill_value=0)
    print(purity)

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
