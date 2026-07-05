"""
Full-history force-entry matrix audit (SPEC-057 Path B).

For each strategy, forces entry on every qualifying day and runs the
complete backtest with real exit rules (50% profit target, stop loss,
21 DTE roll). Buckets results by (regime × IV_signal × trend) cell
to compare strategy performance across all signal environments.
"""
from __future__ import annotations

import math
import os
from dataclasses import replace

import pandas as pd

from backtest.engine import DEFAULT_PARAMS, run_backtest
from strategy.catalog import STRATEGIES_BY_KEY, strategy_key as catalog_key

# Matrix scope: SPX / ES strategies only. Single-name paper sleeves (SPEC-115
# q041_t2/t3, GOOGL/AMZN/COST/JPM) are chain-based and have no forced-entry
# legs in the selector — they are not matrix cells.
STRATEGY_KEYS = [
    k for k, d in STRATEGIES_BY_KEY.items()
    if k != "reduce_wait" and d.underlying in ("SPX", "/ES")
]
MIN_CELL_N = 5


def _cell_label(regime: str, iv_signal: str, trend: str) -> str:
    return f"{regime}|{iv_signal}|{trend}"


def _worst_7y_net(grp: pd.DataFrame) -> float:
    """Worst rolling 7-year net PnL by entry year (the disaster-window metric
    from the strategy-metrics pack). Windows [y, y+6] over the sample span."""
    yr = grp.groupby("entry_year")["pnl"].sum()
    if yr.empty:
        return 0.0
    y0, y1 = int(yr.index.min()), int(yr.index.max())
    worst = None
    for start in range(y0, max(y0, y1 - 6) + 1):
        net = float(yr[(yr.index >= start) & (yr.index <= start + 6)].sum())
        worst = net if worst is None else min(worst, net)
    return worst if worst is not None else 0.0


def run_matrix_audit(
    strategy_keys: list[str] | None = None,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    save_csv: bool = True,
    sigma_mode: str = "FLAT",              # SPEC-120: FLAT | CALIB | PESS
    sigma_offsets: dict | None = None,
    pess_bracket_vp: float = 1.0,
    collect_trade_rows: list | None = None,  # SPEC-120: append trade-level dicts
) -> pd.DataFrame:
    keys = strategy_keys or STRATEGY_KEYS
    all_rows: list[dict] = []

    for strategy_key in keys:
        forced_params = replace(DEFAULT_PARAMS, force_strategy=strategy_key)
        result = run_backtest(
            start_date=start_date,
            end_date=end_date,
            params=forced_params,
            verbose=False,
            sigma_mode=sigma_mode,
            sigma_offsets=sigma_offsets,
            pess_bracket_vp=pess_bracket_vp,
        )

        sig_by_date: dict[str, dict] = {row["date"]: row for row in result.signals}

        trade_rows: list[dict] = []
        for trade in result.trades:
            if catalog_key(trade.strategy.value) != strategy_key:
                continue
            sig = sig_by_date.get(trade.entry_date, {})
            entry = pd.Timestamp(trade.entry_date)
            exit_ = pd.Timestamp(trade.exit_date) if trade.exit_date else entry
            trade_rows.append({
                "strategy_key": strategy_key,
                "regime": sig.get("regime", "UNKNOWN"),
                "iv_signal": sig.get("iv_signal", "UNKNOWN"),
                "trend": sig.get("trend", "UNKNOWN"),
                "entry_date": trade.entry_date,
                "exit_date": trade.exit_date,
                "entry_year": entry.year,
                "entry_vix": trade.entry_vix,
                "exit_reason": trade.exit_reason,
                "entry_credit": trade.entry_credit,
                "contracts": trade.contracts,
                "pnl": trade.exit_pnl,
                "hold_days": max((exit_ - entry).days, 1),
            })

        if collect_trade_rows is not None:
            collect_trade_rows.extend(trade_rows)
        if not trade_rows:
            continue

        df = pd.DataFrame(trade_rows)
        for (regime, iv_sig, trend), grp in df.groupby(["regime", "iv_signal", "trend"]):
            n = len(grp)
            avg_pnl = grp["pnl"].mean()
            win_rate = float((grp["pnl"] > 0).mean())
            std = grp["pnl"].std()
            sharpe = round(avg_pnl / std * math.sqrt(252 / 21), 2) if std and std > 0 else 0.0

            consec = max_consec = 0
            for pnl in grp["pnl"]:
                if pnl <= 0:
                    consec += 1
                    max_consec = max(max_consec, consec)
                else:
                    consec = 0

            g2020 = grp[grp["entry_year"] >= 2020]
            g2024 = grp[grp["entry_year"] >= 2024]
            all_rows.append({
                "strategy_key": strategy_key,
                "cell": _cell_label(regime, iv_sig, trend),
                "regime": regime,
                "iv_signal": iv_sig,
                "trend": trend,
                "n": n,
                "avg_pnl": round(avg_pnl, 0),
                "win_rate": round(win_rate, 3),
                "sharpe": sharpe,
                "max_consec_loss": max_consec,
                "avg_hold_days": round(grp["hold_days"].mean(), 1),
                "low_n_flag": n < MIN_CELL_N,
                # SPEC-120 era columns
                "net_pnl": round(float(grp["pnl"].sum()), 0),
                "worst7y_net": round(_worst_7y_net(grp), 0),
                "n_2020p": len(g2020),
                "net_2020p": round(float(g2020["pnl"].sum()), 0),
                "n_2024p": len(g2024),
                "net_2024p": round(float(g2024["pnl"].sum()), 0),
            })

    result_df = pd.DataFrame(all_rows)
    if save_csv and not result_df.empty:
        os.makedirs("backtest/output", exist_ok=True)
        result_df.to_csv("backtest/output/matrix_audit.csv", index=False)
    return result_df


def print_matrix(df: pd.DataFrame) -> None:
    if df.empty:
        print("No data.")
        return

    rows: list[dict] = []
    for cell, grp in df.groupby("cell"):
        row = {"cell": cell}
        for _, rec in grp.iterrows():
            tag = f"${rec['avg_pnl']:,.0f} (n={rec['n']}{'*' if rec['low_n_flag'] else ''})"
            row[rec["strategy_key"]] = tag
        rows.append(row)

    pivot = pd.DataFrame(rows).set_index("cell")
    ordered_cols = [k for k in STRATEGY_KEYS if k in pivot.columns]
    print(pivot[ordered_cols].to_string())


if __name__ == "__main__":
    print("Running full-history force-entry matrix audit...")
    print("This may take several minutes.\n")
    df = run_matrix_audit()
    print_matrix(df)
