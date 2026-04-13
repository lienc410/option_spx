"""
Conditional Cumulative P&L — Risk Layer (SPEC-056 F4)

Splits the P&L time-series by a signal state and shows how cumulative P&L
evolves within each signal environment. No independence assumption required.
"""
from __future__ import annotations

import os

import pandas as pd

from backtest.engine import run_backtest
from strategy.catalog import strategy_key as catalog_key


def run_conditional_pnl(
    strategy_key: str,
    signal_col: str,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    save_csv: bool = True,
) -> pd.DataFrame:
    result = run_backtest(start_date=start_date, end_date=end_date, verbose=False)

    sig_df = pd.DataFrame(result.signals)
    sig_df["date"] = pd.to_datetime(sig_df["date"])
    sig_df = sig_df.set_index("date")

    pnl_by_date: dict[str, float] = {}
    in_pos_by_date: dict[str, bool] = {}
    for trade in result.trades:
        if catalog_key(trade.strategy.value) != strategy_key:
            continue
        entry = pd.Timestamp(trade.entry_date)
        exit_ = pd.Timestamp(trade.exit_date) if trade.exit_date else entry
        hold_days = max((exit_ - entry).days, 1)
        daily_pnl = trade.exit_pnl / hold_days
        for d in pd.date_range(entry, exit_, freq="B"):
            ds = str(d.date())
            pnl_by_date[ds] = pnl_by_date.get(ds, 0.0) + daily_pnl
            in_pos_by_date[ds] = True

    rows: list[dict] = []
    cum_global = 0.0
    cum_by_state: dict = {}

    for date, sig_row in sig_df.iterrows():
        if signal_col not in sig_row.index:
            raise ValueError(
                f"signal_col={signal_col!r} not found in signal_history. "
                f"Available: {list(sig_row.index)}"
            )
        state = sig_row[signal_col]
        ds = str(date.date())
        pnl = pnl_by_date.get(ds, 0.0)
        in_pos = in_pos_by_date.get(ds, False)

        cum_global += pnl
        cum_by_state[state] = cum_by_state.get(state, 0.0) + pnl

        rows.append({
            "date": date,
            "signal_state": state,
            "pnl": round(pnl, 2),
            "cum_pnl_by_state": round(cum_by_state[state], 2),
            "cum_pnl_global": round(cum_global, 2),
            "in_position": in_pos,
        })

    df = pd.DataFrame(rows)
    if save_csv:
        os.makedirs("backtest/output", exist_ok=True)
        df.to_csv(f"backtest/output/conditional_pnl_{strategy_key}_{signal_col}.csv", index=False)
    return df


if __name__ == "__main__":
    for col in ["regime_decay", "local_spike", "regime"]:
        df = run_conditional_pnl("bull_call_diagonal", col)
        print(f"\n=== bull_call_diagonal × {col} ===")
        for state in df["signal_state"].unique():
            sub = df[df["signal_state"] == state]
            final_cum = sub["cum_pnl_by_state"].iloc[-1]
            in_pos_days = sub["in_position"].sum()
            print(f"  state={state}: final_cum_pnl=${final_cum:,.0f}, in_position_days={in_pos_days}")
