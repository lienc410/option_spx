"""
Non-overlapping event study for strategy entry signals.
Evaluates whether the entry signal itself (independent of exit timing)
has statistical alpha.
"""
from __future__ import annotations

import os
import pandas as pd

from backtest.engine import run_backtest
from strategy.catalog import strategy_key as catalog_strategy_key


def run_event_study(
    strategy_key: str,
    fixed_hold_days: int = 21,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    save_csv: bool = True,
) -> pd.DataFrame:
    """
    For each entry signal trigger day, compute the fixed-hold P&L.
    Windows are non-overlapping: if a previous window is still active, skip.

    Returns DataFrame with columns:
        entry_date, exit_date, pnl, hit_target (bool), strategy_key
    """
    result = run_backtest(start_date=start_date, end_date=end_date, verbose=False)
    sig_by_date: dict[str, dict] = {row["date"]: row for row in result.signals}
    trades = result.trades

    filtered = [t for t in trades if catalog_strategy_key(t.strategy.value) == strategy_key]
    filtered.sort(key=lambda t: t.entry_date)

    rows = []
    last_exit = None
    for trade in filtered:
        entry = pd.Timestamp(trade.entry_date)
        if last_exit is not None and entry <= last_exit:
            continue
        exit_date = entry + pd.Timedelta(days=fixed_hold_days)
        last_exit = exit_date
        sig = sig_by_date.get(str(entry.date()), {})
        rows.append({
            "entry_date": entry,
            "exit_date": exit_date,
            "pnl": trade.exit_pnl,
            "hit_target": trade.exit_reason == "50pct_profit",
            "strategy_key": strategy_key,
            "regime": sig.get("regime", ""),
            "trend": sig.get("trend", ""),
            "ivp252": sig.get("ivp252", float("nan")),
            "ivp63": sig.get("ivp63", float("nan")),
            "regime_decay": sig.get("regime_decay", False),
            "local_spike": sig.get("local_spike", False),
        })

    df = pd.DataFrame(rows)
    if save_csv:
        os.makedirs("backtest/output", exist_ok=True)
        df.to_csv(f"backtest/output/event_study_{strategy_key}.csv", index=False)
    return df
