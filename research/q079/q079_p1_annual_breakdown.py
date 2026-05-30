"""Q079 P1 follow-up — annual breakdown of core stats + 2026 concentration check.

Reads per-day cell tags from q079_p1_cells.csv. Per year:
  - days_primary (VIX [15,16) edge)
  - days_extended (VIX [14,17) edge)
  - SPX forward +30d / +60d / +90d mean on primary edge days
  - VIX 14-16 chatter (boundary crossings within band per year)
  - first / last edge date (concentration span within year)
  - max consecutive primary streak (how clustered)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / "research" / "q079" / "q079_p1_cells.csv"
OUT_ANNUAL = ROOT / "research" / "q079" / "q079_p1_annual_full.csv"
OUT_2026 = ROOT / "research" / "q079" / "q079_p1_2026_dates.csv"


def _max_consec(flags: pd.Series) -> int:
    if flags.sum() == 0:
        return 0
    runs = (flags != flags.shift()).cumsum()
    return int(flags.groupby(runs).sum().max())


def main() -> int:
    df = pd.read_csv(CELLS, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Reattach SPX forward returns (cells.csv saved spx but not fwd cols)
    for h in (30, 60, 90):
        df[f"spx_fwd_{h}d"] = df["spx"].shift(-h) / df["spx"] - 1.0

    # VIX chatter: crossings of 15 line within 14-16 band
    df["vix_band_14_16"] = (df["vix"] >= 14.0) & (df["vix"] < 16.0)
    df["vix_above_15"] = (df["vix"] >= 15.0).astype(int)
    df["vix_cross"] = df["vix_above_15"].diff().abs().fillna(0).astype(int)

    rows = []
    years = sorted(df["year"].unique())
    for y in years:
        sub = df[df["year"] == y]
        prim = sub[sub["edge_primary"]]
        ext = sub[sub["edge_extended"]]
        chatter = int(sub.loc[sub["vix_band_14_16"], "vix_cross"].sum())
        days_band = int(sub["vix_band_14_16"].sum())
        max_streak = _max_consec(sub["edge_primary"])
        if len(prim):
            span_days = (prim["date"].max() - prim["date"].min()).days
            spx_30 = prim["spx_fwd_30d"].mean() * 100
            spx_60 = prim["spx_fwd_60d"].mean() * 100
            spx_90 = prim["spx_fwd_90d"].mean() * 100
        else:
            span_days = 0
            spx_30 = spx_60 = spx_90 = float("nan")
        rows.append({
            "year": int(y),
            "days_primary": int(len(prim)),
            "days_extended": int(len(ext)),
            "max_consec_streak": max_streak,
            "trigger_span_days": span_days,
            "spx_fwd_30d_mean_pct": round(spx_30, 2) if pd.notna(spx_30) else None,
            "spx_fwd_60d_mean_pct": round(spx_60, 2) if pd.notna(spx_60) else None,
            "spx_fwd_90d_mean_pct": round(spx_90, 2) if pd.notna(spx_90) else None,
            "days_vix_in_14_16": days_band,
            "vix_15_crossings_in_band": chatter,
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_ANNUAL, index=False)
    print("Annual breakdown saved →", OUT_ANNUAL.name)
    print()

    # Print non-zero years only (compact)
    nonzero = out[out["days_primary"] > 0].copy()
    print("=" * 100)
    print("Years with PRIMARY edge-cell triggers (sorted by year)")
    print("=" * 100)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    print(nonzero.to_string(index=False))

    # Concentration: among non-zero years, what fraction had streak >= 3?
    print()
    print(f"\nNon-zero years total: {len(nonzero)}")
    print(f"  with consecutive streak >= 2: {int((nonzero['max_consec_streak']>=2).sum())}")
    print(f"  with consecutive streak >= 3: {int((nonzero['max_consec_streak']>=3).sum())}")
    print(f"  with consecutive streak >= 5: {int((nonzero['max_consec_streak']>=5).sum())}")

    # 2026 dates
    p2026 = df[(df["year"] == 2026) & df["edge_primary"]][["date", "vix", "ivp", "trend", "spx"]].copy()
    p2026.to_csv(OUT_2026, index=False)
    print()
    print("=" * 100)
    print("2026 primary trigger detail (in-progress year)")
    print("=" * 100)
    if len(p2026):
        print(p2026.to_string(index=False))
        if len(p2026) >= 2:
            gaps = p2026["date"].diff().dt.days.dropna()
            print(f"\n  gaps between triggers (days): {list(gaps.astype(int))}")
            print(f"  span first→last: {(p2026['date'].max() - p2026['date'].min()).days} days")
    else:
        print("  no 2026 primary triggers.")

    # 2025 detail (full year recent)
    p2025 = df[(df["year"] == 2025) & df["edge_primary"]][["date", "vix", "ivp", "trend", "spx"]].copy()
    print()
    print("=" * 100)
    print("2025 primary trigger detail (full year, the historical max)")
    print("=" * 100)
    if len(p2025):
        print(p2025.to_string(index=False))
        if len(p2025) >= 2:
            gaps = p2025["date"].diff().dt.days.dropna()
            print(f"\n  gaps between triggers (days): {list(gaps.astype(int))}")
            print(f"  span first→last: {(p2025['date'].max() - p2025['date'].min()).days} days")

    return 0


if __name__ == "__main__":
    sys.exit(main())
