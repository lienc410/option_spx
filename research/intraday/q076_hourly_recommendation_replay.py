"""Q076 — Hourly recommendation replay.

Question (PM 2026-05-26): the live web/server.py /api/recommendation endpoint
is intraday-aware (uses 5m bar override). What if we **fully** executed the
selector recommendation every hour during the past month — closing and
reopening positions as the recommendation changes?

This script replays `strategy.selector.select_strategy` once per 1h bar across
the past 21 trading days, using the SAME inputs the live endpoint uses but
with the 1h bar's SPX/VIX as the intraday override and EOD history truncated
to (bar_date - 1).

Output:
  research/intraday/q076_hourly_recs.csv     — one row per 1h bar
  research/intraday/q076_churn_summary.csv   — per-day + global churn metrics
  research/intraday/q076_transition_matrix.csv — strategy→strategy flip counts
"""

from __future__ import annotations

import sys
import pickle
import pandas as pd
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from signals.vix_regime import get_current_snapshot
from signals.iv_rank import get_current_iv_snapshot
from signals.trend import get_current_trend
from strategy.selector import select_strategy

OUT = REPO / "research" / "intraday"
OUT.mkdir(parents=True, exist_ok=True)

DAILY_VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
DAILY_SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
ALIGNED_1H = REPO / "data" / "market_cache" / "spx_vix_1h_aligned_1mo.pkl"


def _load_daily(pkl_path: Path, col: str) -> pd.DataFrame:
    df = pickle.load(open(pkl_path, "rb"))
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[["Close"]].rename(columns={"Close": col})


def _build_baseline_history(daily_df: pd.DataFrame, cutoff_date) -> pd.DataFrame:
    """Truncate daily history to strictly before cutoff_date (live endpoint
    behaviour: today's intraday override sits on top of yesterday's EOD)."""
    cutoff = pd.Timestamp(cutoff_date).normalize()
    return daily_df.loc[daily_df.index < cutoff]


def run_replay():
    print("Loading data...")
    vix_daily = _load_daily(DAILY_VIX_PKL, "vix")
    spx_daily = _load_daily(DAILY_SPX_PKL, "close")
    aligned = pickle.load(open(ALIGNED_1H, "rb"))
    print(f"  daily VIX: {len(vix_daily)} rows ({vix_daily.index[0].date()} → {vix_daily.index[-1].date()})")
    print(f"  daily SPX: {len(spx_daily)} rows")
    print(f"  1h aligned: {len(aligned)} rows ({aligned.index[0]} → {aligned.index[-1]})")

    # Patch fetch_vix3m to return None (avoid stale cache pollution; backwardation=False).
    # This matches "VIX3M unavailable" path — neutral for selector.
    rows = []

    # Use the most recent 2y of daily history (matches get_recommendation default).
    vix_2y_full = vix_daily.tail(500)
    spx_2y_full = spx_daily.tail(500)

    with patch("signals.vix_regime.fetch_vix3m", return_value=None):
        for ts, bar in aligned.iterrows():
            bar_date = ts.date()
            vix_baseline = _build_baseline_history(vix_2y_full, bar_date)
            spx_baseline = _build_baseline_history(spx_2y_full, bar_date)
            if len(vix_baseline) < 10 or len(spx_baseline) < 220:
                continue

            try:
                vix_snap = get_current_snapshot(vix_baseline, current_vix=float(bar["vix_close"]))
                iv_snap = get_current_iv_snapshot(vix_baseline, current_vix=float(bar["vix_close"]))
                trend_snap = get_current_trend(spx_baseline, current_spx=float(bar["spx_close"]))
                rec = select_strategy(vix_snap, iv_snap, trend_snap)
            except Exception as exc:
                rows.append({
                    "timestamp": ts, "date": bar_date,
                    "vix": float(bar["vix_close"]), "spx": float(bar["spx_close"]),
                    "strategy": "ERROR", "is_wait": None,
                    "regime": None, "trend_signal": None, "iv_signal": None,
                    "error": str(exc),
                })
                continue

            strat_str = rec.strategy.value if hasattr(rec.strategy, "value") else str(rec.strategy)
            pos_action = getattr(rec, "position_action", "")
            is_wait = pos_action in ("WAIT", "CLOSE_AND_WAIT")
            rows.append({
                "timestamp": ts,
                "date": bar_date,
                "vix": float(bar["vix_close"]),
                "spx": float(bar["spx_close"]),
                "strategy": strat_str,
                "position_action": pos_action,
                "is_wait": is_wait,
                "regime": vix_snap.regime.value if hasattr(vix_snap.regime, "value") else str(vix_snap.regime),
                "trend_signal": trend_snap.signal.value if hasattr(trend_snap.signal, "value") else str(trend_snap.signal),
                "iv_signal": str(getattr(iv_snap, "iv_signal", "")),
                "rationale": getattr(rec, "rationale", "") or "",
                "error": "",
            })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q076_hourly_recs.csv", index=False)
    print(f"\nWrote {len(df)} hourly rows → {OUT/'q076_hourly_recs.csv'}")
    return df


def analyze_churn(df: pd.DataFrame):
    print("\nAnalyzing churn...")
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["prev_strategy"] = df["strategy"].shift(1)
    df["flipped"] = (df["strategy"] != df["prev_strategy"]) & df["prev_strategy"].notna()

    # Per-day churn
    by_day = df.groupby("date").agg(
        n_bars=("strategy", "size"),
        n_unique_strategies=("strategy", "nunique"),
        n_flips=("flipped", "sum"),
        n_wait=("is_wait", "sum"),
        first_strategy=("strategy", "first"),
        last_strategy=("strategy", "last"),
        vix_open=("vix", "first"),
        vix_close=("vix", "last"),
        spx_open=("spx", "first"),
        spx_close=("spx", "last"),
    ).reset_index()
    by_day["intraday_change"] = by_day["first_strategy"] != by_day["last_strategy"]
    by_day.to_csv(OUT / "q076_churn_summary.csv", index=False)

    # Transition matrix
    flips = df[df["flipped"]]
    tm = pd.crosstab(flips["prev_strategy"], flips["strategy"]).reset_index()
    tm.to_csv(OUT / "q076_transition_matrix.csv", index=False)

    # Console summary
    n_bars = len(df)
    n_unique_strats = df["strategy"].nunique()
    n_flips_total = df["flipped"].sum()
    n_days = by_day.shape[0]
    days_with_intraday_change = by_day["intraday_change"].sum()
    days_multi_strat = (by_day["n_unique_strategies"] > 1).sum()
    max_strats_in_day = by_day["n_unique_strategies"].max()

    print(f"\n  Total bars:                   {n_bars}")
    print(f"  Unique strategies appeared:   {n_unique_strats}")
    print(f"  Total intraday flips:         {n_flips_total}")
    print(f"  Trading days:                 {n_days}")
    print(f"  Days w/ open!=close strategy: {days_with_intraday_change} ({days_with_intraday_change/n_days*100:.1f}%)")
    print(f"  Days w/ ≥2 strategies in day: {days_multi_strat} ({days_multi_strat/n_days*100:.1f}%)")
    print(f"  Max strategies in 1 day:      {max_strats_in_day}")

    print("\n  Strategy frequency (% of bars):")
    print((df["strategy"].value_counts(normalize=True) * 100).round(1).to_string())

    print("\n  Top 10 strategy transitions:")
    top_trans = (df[df["flipped"]]
                 .groupby(["prev_strategy", "strategy"]).size()
                 .reset_index(name="n").sort_values("n", ascending=False))
    print(top_trans.head(10).to_string(index=False))

    return by_day


if __name__ == "__main__":
    df = run_replay()
    if df.empty:
        print("No data.")
        sys.exit(1)
    by_day = analyze_churn(df)
    print(f"\nOutputs in {OUT}/")
