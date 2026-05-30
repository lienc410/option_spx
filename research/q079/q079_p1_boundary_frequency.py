"""Q079 P1 — VIX=15 boundary trigger frequency quantification.

Reads research/q078/_signal_history_cache.csv (26y daily signal history).

Edge cell definition (PM scope):
  VIX in [15, 16]  AND  IVP in [20, 40]  AND  trend in {BULLISH, NEUTRAL}
  AND  current routing = "Reduce / Wait"  (i.e. blocked by SPEC-058/060)

Computes:
  A. edge-cell trigger days (count + annual distribution)
  B. SPX forward returns 30d/60d/90d on edge-cell days (counterfactual proxy)
  C. VIX 14-16 chatter (boundary crossings per year)
  D. sensitivity: extend buffer to VIX in [14, 17]

Decision thresholds (PM):
  < 5 days/yr  → drop
  >= 10 days/yr → continue to Tier 2 full
  5-10         → PM-discretionary
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
OUT_CELLS = ROOT / "research" / "q079" / "q079_p1_cells.csv"
OUT_ANNUAL = ROOT / "research" / "q079" / "q079_p1_annual.csv"


def _edge_cell(df: pd.DataFrame, vix_lo: float, vix_hi: float,
               ivp_lo: float, ivp_hi: float) -> pd.Series:
    return (
        (df["vix"] >= vix_lo) & (df["vix"] < vix_hi)
        & (df["ivp"] >= ivp_lo) & (df["ivp"] < ivp_hi)
        & (df["trend"].isin(["BULLISH", "NEUTRAL"]))
        & (df["strategy"] == "Reduce / Wait")
    )


def main() -> int:
    df = pd.read_csv(SIGNAL, parse_dates=["date"])
    df["year"] = df["date"].dt.year
    print(f"[q079-p1] loaded {len(df):,} trading days, {df['date'].min().date()} → {df['date'].max().date()}")

    # ── A. Primary edge cell: VIX [15,16) + IVP [20,40) + BULLISH/NEUTRAL + R/W ──
    df["edge_primary"] = _edge_cell(df, 15.0, 16.0, 20.0, 40.0)

    # ── E. Sensitivity: extend buffer to VIX [14, 17) ──
    df["edge_extended"] = _edge_cell(df, 14.0, 17.0, 20.0, 40.0)

    # ── Why-blocked attribution: among edge cells, was it BULLISH/NEUTRAL/IVP?
    # selector logic: in NORMAL bucket, IV LOW (IVP<40) BULLISH → R/W (SPEC-060);
    #                 IV LOW NEUTRAL → R/W. So edge cell rejection IS because of
    #                 IVP-LOW + NORMAL-bucket combo.
    primary = df[df["edge_primary"]].copy()
    extended = df[df["edge_extended"]].copy()

    # Per-day cell tag (save for inspection)
    save_cols = ["date", "vix", "ivp", "ivp63", "ivp252", "trend", "iv_signal",
                 "regime", "strategy", "edge_primary", "edge_extended", "spx",
                 "year"]
    df[save_cols].to_csv(OUT_CELLS, index=False)
    print(f"[q079-p1] saved per-day cell tags → {OUT_CELLS.name}")

    # ── B. SPX forward proxy: 30d / 60d / 90d return after edge-cell day ──
    df = df.sort_values("date").reset_index(drop=True)
    for h in (30, 60, 90):
        df[f"spx_fwd_{h}d"] = df["spx"].shift(-h) / df["spx"] - 1.0

    primary = df[df["edge_primary"]].copy()
    extended = df[df["edge_extended"]].copy()

    # Annual aggregation
    span_years = (df["date"].max() - df["date"].min()).days / 365.25
    annual_primary = primary.groupby("year").size().rename("days_primary")
    annual_extended = extended.groupby("year").size().rename("days_extended")
    annual = pd.concat([annual_primary, annual_extended], axis=1).fillna(0).astype(int)
    # Fill years with 0 triggers explicitly
    all_years = pd.Index(range(int(df["year"].min()), int(df["year"].max()) + 1))
    annual = annual.reindex(all_years, fill_value=0)
    annual.index.name = "year"
    annual.to_csv(OUT_ANNUAL)

    n_primary = int(primary.shape[0])
    n_extended = int(extended.shape[0])

    print()
    print("=" * 78)
    print("A. Edge-cell trigger frequency")
    print("=" * 78)
    print(f"  PRIMARY  cell  VIX∈[15,16) + IVP∈[20,40) + BULL/NEUT + R/W:")
    print(f"    total days: {n_primary}")
    print(f"    span yrs:   {span_years:.1f}")
    print(f"    avg/yr:     {n_primary / span_years:.1f}")
    if n_primary:
        print(f"    annual min/median/max/p95: "
              f"{annual['days_primary'].min()}/{annual['days_primary'].median():.0f}/"
              f"{annual['days_primary'].max()}/{annual['days_primary'].quantile(0.95):.0f}")
    print()
    print(f"  EXTENDED cell  VIX∈[14,17) + IVP∈[20,40) + BULL/NEUT + R/W:")
    print(f"    total days: {n_extended}")
    print(f"    avg/yr:     {n_extended / span_years:.1f}")

    print()
    print("=" * 78)
    print("B. SPX forward return on edge-cell trigger days (counterfactual proxy)")
    print("=" * 78)
    if n_primary:
        print("  PRIMARY cell (n=%d):" % n_primary)
        for h in (30, 60, 90):
            col = primary[f"spx_fwd_{h}d"].dropna()
            if not col.empty:
                print(f"    SPX +{h}d:  mean {col.mean()*100:+.2f}%   "
                      f"median {col.median()*100:+.2f}%   "
                      f"std {col.std()*100:.2f}%   "
                      f"p05 {col.quantile(0.05)*100:+.2f}%   "
                      f"n={len(col)}")
    else:
        print("  PRIMARY cell empty — skip forward.")

    if n_extended:
        print(f"\n  EXTENDED cell (n={n_extended}):")
        for h in (30, 60, 90):
            col = extended[f"spx_fwd_{h}d"].dropna()
            if not col.empty:
                print(f"    SPX +{h}d:  mean {col.mean()*100:+.2f}%   "
                      f"median {col.median()*100:+.2f}%   "
                      f"std {col.std()*100:.2f}%   "
                      f"p05 {col.quantile(0.05)*100:+.2f}%   "
                      f"n={len(col)}")

    # ── C. VIX 14-16 chatter: crossings of VIX=15 line ──
    df["vix_band_14_16"] = (df["vix"] >= 14.0) & (df["vix"] < 16.0)
    df["vix_above_15"] = (df["vix"] >= 15.0).astype(int)
    df["vix_cross"] = df["vix_above_15"].diff().abs().fillna(0).astype(int)
    crossings_in_band = df.loc[df["vix_band_14_16"], "vix_cross"].sum()
    crossings_total = df["vix_cross"].sum()
    days_in_band = int(df["vix_band_14_16"].sum())
    print()
    print("=" * 78)
    print("C. VIX 14-16 chatter (boundary crossings)")
    print("=" * 78)
    print(f"  days with VIX ∈ [14, 16):                 {days_in_band}")
    print(f"  VIX=15 crossings within those days:        {int(crossings_in_band)}")
    print(f"  VIX=15 crossings total (any VIX level):    {int(crossings_total)}")
    if days_in_band:
        print(f"  crossings/day within band:                 {crossings_in_band/days_in_band:.3f}")
    print(f"  estimated annual crossings within band:    {crossings_in_band / span_years:.1f}")

    # ── D. Decision verdict ──
    avg_per_yr = n_primary / span_years
    print()
    print("=" * 78)
    print("D. Decision verdict (per PM threshold)")
    print("=" * 78)
    print(f"  primary cell avg trigger:   {avg_per_yr:.1f} days/yr")
    if avg_per_yr < 5:
        verdict = "DROP — < 5 days/yr threshold met"
    elif avg_per_yr >= 10:
        verdict = "CONTINUE TIER 2 — >= 10 days/yr threshold met"
    else:
        verdict = "PM-DISCRETIONARY — 5-10 days/yr borderline"
    print(f"  verdict: {verdict}")
    print()

    # save annual table also as pivoted summary
    print("Annual table:")
    print(annual.to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
