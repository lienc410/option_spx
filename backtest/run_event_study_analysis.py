"""
Analyze event study results.
"""
from __future__ import annotations

import math

import pandas as pd

from backtest.run_event_study import run_event_study
from strategy.catalog import STRATEGIES_BY_KEY


def analyze_event_study(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    n = len(df)
    avg_pnl = df["pnl"].mean()
    win_rate = (df["pnl"] > 0).mean()
    std = df["pnl"].std()
    sharpe = (avg_pnl / std * math.sqrt(252 / 21)) if std and std > 0 else 0.0
    no_target = df[~df["hit_target"]]
    avg_no_target = no_target["pnl"].mean() if not no_target.empty else float("nan")
    return {
        "n": n,
        "avg_pnl": round(avg_pnl, 0),
        "win_rate": round(win_rate, 3),
        "sharpe": round(sharpe, 2),
        "avg_pnl_no_target": round(avg_no_target, 0),
        "n_no_target": len(no_target),
    }


if __name__ == "__main__":
    for key in [
        "bull_call_diagonal",
        "iron_condor",
        "bull_put_spread",
    ]:
        df = run_event_study(key, fixed_hold_days=21)
        stats = analyze_event_study(df)
        name = STRATEGIES_BY_KEY.get(key).name if key in STRATEGIES_BY_KEY else key
        print(f"\n=== {name} ({key}) ===")
        for stat_key, value in stats.items():
            print(f"  {stat_key}: {value}")
