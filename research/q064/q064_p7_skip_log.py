"""Q064 P7 — Skip log: exact select_strategy rationale for no-trade aftermath windows.

For each window in q064_p1_windows.csv that has no V3-A entry in q064_p6_results.csv,
captures rec.rationale returned by select_strategy() on the window start_date from
the actual backtest run.

Output: q064_p7_skip_log.csv
  window_start, vix, is_aftermath, regime, trend, iv_signal, strategy, rationale
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest
from signals.vix_regime import Regime

OUT = REPO / "research" / "q064" / "q064_p7_skip_log.csv"


def main() -> None:
    windows_path = REPO / "research" / "q064" / "q064_p1_windows.csv"
    trades_path  = REPO / "research" / "q064" / "q064_p6_results.csv"

    windows = pd.read_csv(windows_path, parse_dates=["start_date"])
    trades  = pd.read_csv(trades_path,  parse_dates=["entry_date"])

    # Windows whose start_date has no V3-A trade on or during the window
    trade_dates = set(trades["entry_date"].dt.normalize())

    def _has_trade(row) -> bool:
        start = row["start_date"]
        end   = pd.Timestamp(row["end_date"])
        return any(start <= d <= end for d in trade_dates)

    no_trade_starts = set(
        row["start_date"]
        for _, row in windows.iterrows()
        if not _has_trade(row)
    )

    print(f"Aftermath windows total:      {len(windows)}")
    print(f"Windows with V3-A trades:     {len(windows) - len(no_trade_starts)}")
    print(f"No-trade windows to capture:  {len(no_trade_starts)}")

    # Run engine with wrapper that intercepts select_strategy on target dates
    captured: dict[str, dict] = {}  # date_str → info

    orig = sel.select_strategy

    def wrapped(vix_snap, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = orig(vix_snap, iv, trend, params)
        date_key = str(vix_snap.date)[:10] if vix_snap.date else None
        if date_key and pd.Timestamp(date_key) in no_trade_starts:
            captured[date_key] = {
                "vix":          round(float(vix_snap.vix), 2),
                "is_aftermath": bool(sel.is_aftermath(vix_snap)),
                "regime":       vix_snap.regime.value if vix_snap.regime else "",
                "trend":        trend.signal.value    if trend  else "",
                "iv_signal":    iv.iv_signal.value    if iv     else "",
                "strategy":     rec.strategy.value,
                "rationale":    rec.rationale,
            }
        return rec

    sel.select_strategy    = wrapped
    engine_mod.select_strategy = wrapped
    try:
        print("\nRunning backtest 2009-01-01 → 2026-05-13 …")
        run_backtest(start_date="2009-01-01", end_date="2026-05-13",
                     account_size=150_000.0, verbose=False)
    finally:
        sel.select_strategy        = orig
        engine_mod.select_strategy = orig

    print(f"Captured rationales for {len(captured)} / {len(no_trade_starts)} target dates")

    rows = []
    for _, row in windows.iterrows():
        start = row["start_date"]
        start_str = start.strftime("%Y-%m-%d")
        if start not in no_trade_starts:
            continue
        info = captured.get(start_str, {})
        rows.append({
            "window_start": start_str,
            "vix":          info.get("vix",          ""),
            "is_aftermath": info.get("is_aftermath",  ""),
            "regime":       info.get("regime",        ""),
            "trend":        info.get("trend",         ""),
            "iv_signal":    info.get("iv_signal",     ""),
            "strategy":     info.get("strategy",      ""),
            "rationale":    info.get("rationale",     "(date not reached in backtest)"),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"\nWrote {OUT}  ({len(df)} rows)")

    print("\nRationale distribution:")
    print(df["rationale"].value_counts().to_string())


if __name__ == "__main__":
    main()
