"""Q042 Tier 2 — P1 Trigger grid expansion.

Tier 1 found dd60≥10% has clear edge. Tier 2 P1 expands the trigger space:
  - Drawdown depth: 5%, 8%, 10%, 12%, 15%, 20%
  - Confirmation: none, MA50_reclaim, MA200_reclaim, VIX_decline, VIX_term_structure_normalize
  - Forward window: 3m / 6m / 12m

Compare each cell on:
  - n (sample size)
  - 12m positive rate
  - 12m median return
  - "wait cost": 12m return loss vs raw entry on dd10 trigger

OOS split: 2007-2018 vs 2019-2026.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
VIX3M_PKL = REPO / "data" / "market_cache" / "yahoo__VIX3M__max__1d.pkl"


def load() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    vix3m = pickle.loads(VIX3M_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    vix3m.index = pd.to_datetime(vix3m.index).tz_localize(None)
    return (
        spx.loc["2007-01-01":"2026-05-08"].copy(),
        vix.loc["2007-01-01":"2026-05-08"]["Close"].copy(),
        vix3m["Close"].copy(),  # VIX3M may have shorter history
    )


def first_triggers(condition: pd.Series) -> pd.DatetimeIndex:
    fired = condition & ~condition.shift(1).fillna(False)
    return condition.index[fired]


def build_features(spx: pd.DataFrame, vix: pd.Series, vix3m: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()
    df["vix"] = vix.reindex(df.index).ffill()
    df["vix_5d_avg"] = df["vix"].rolling(5).mean()
    df["vix_20d_max"] = df["vix"].rolling(20).max()
    df["vix3m"] = vix3m.reindex(df.index).ffill()
    df["term_struct"] = df["vix3m"] / df["vix"]  # >1 contango (normal), <1 backwardation
    for h, label in [(63, "fwd_3m"), (126, "fwd_6m"), (252, "fwd_12m")]:
        df[label] = df["close"].shift(-h) / df["close"] - 1
    return df


def find_entries(df: pd.DataFrame, dd_thr: float, confirmation: str) -> pd.DatetimeIndex:
    """For each first-trigger date of dd60 ≥ dd_thr, find first day within next 30
    trading days satisfying the confirmation rule. Return entry dates."""
    triggers = first_triggers(df["dd60"] <= -dd_thr)
    if confirmation == "none":
        return triggers

    entries = []
    for td in triggers:
        window = df.loc[td:].iloc[:30]
        if window.empty:
            continue
        if confirmation == "ma50_reclaim":
            ok = window[window["close"] > window["ma50"]]
        elif confirmation == "ma200_reclaim":
            ok = window[window["close"] > window["ma200"]]
        elif confirmation == "vix_decline":
            # VIX ≥ 5pt below its 20-day max (i.e. 5pt cooldown from peak)
            ok = window[window["vix"] <= (window["vix_20d_max"] - 5.0)]
        elif confirmation == "term_normalize":
            # Term structure flip back to contango (vix3m/vix > 1.05)
            ok = window[window["term_struct"] > 1.05]
        else:
            raise ValueError(confirmation)
        if not ok.empty:
            entries.append(ok.index[0])
    return pd.DatetimeIndex(entries).unique()


def evaluate(df: pd.DataFrame, dates: pd.DatetimeIndex) -> dict:
    sub = df.loc[dates]
    s3 = sub["fwd_3m"].dropna()
    s6 = sub["fwd_6m"].dropna()
    s12 = sub["fwd_12m"].dropna()
    return {
        "n": len(s12),
        "fwd_3m_med": s3.median() if len(s3) else np.nan,
        "fwd_3m_pos": (s3 > 0).mean() if len(s3) else np.nan,
        "fwd_6m_med": s6.median() if len(s6) else np.nan,
        "fwd_6m_pos": (s6 > 0).mean() if len(s6) else np.nan,
        "fwd_12m_med": s12.median() if len(s12) else np.nan,
        "fwd_12m_avg": s12.mean() if len(s12) else np.nan,
        "fwd_12m_pos": (s12 > 0).mean() if len(s12) else np.nan,
    }


def grid_scan(df: pd.DataFrame, label: str) -> pd.DataFrame:
    print(f"\n=== {label} ===")
    rows = []
    for dd_thr in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
        for conf in ["none", "ma50_reclaim", "ma200_reclaim", "vix_decline", "term_normalize"]:
            entries = find_entries(df, dd_thr, conf)
            if len(entries) < 3:
                continue
            res = evaluate(df, entries)
            rows.append({"dd_thr": dd_thr, "confirmation": conf, **res})
    grid = pd.DataFrame(rows)
    print(grid.to_string(index=False, float_format=lambda x: f"{x:.3f}" if abs(x) < 10 else f"{x:.1f}"))
    return grid


def main() -> None:
    spx, vix, vix3m = load()
    df = build_features(spx, vix, vix3m)
    print(f"data: {df.index.min().date()} → {df.index.max().date()} (n={len(df)})")
    print(f"vix3m coverage: {vix3m.index.min().date()} → {vix3m.index.max().date()} (n={len(vix3m.dropna())})")

    full_grid = grid_scan(df, "Full sample 2007-2026")
    df1 = df.loc["2007-01-01":"2018-12-31"]
    df2 = df.loc["2019-01-01":"2026-05-08"]
    is1 = grid_scan(df1, "OOS split 1: 2007-2018")
    oos1 = grid_scan(df2, "OOS split 2: 2019-2026")

    out_dir = Path(__file__).resolve().parent
    full_grid.to_csv(out_dir / "p1_grid_full.csv", index=False)
    is1.to_csv(out_dir / "p1_grid_2007_2018.csv", index=False)
    oos1.to_csv(out_dir / "p1_grid_2019_2026.csv", index=False)
    print("\nwrote p1_grid_*.csv")

    # Summary: top configs by 12m positive rate × n
    print("\n=== Top configs by 12m positive rate (full sample, n>=20) ===")
    full = full_grid[full_grid["n"] >= 20].copy()
    full["score"] = full["fwd_12m_pos"] * np.log(full["n"])  # rough utility
    print(full.sort_values("fwd_12m_pos", ascending=False).head(10).to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
