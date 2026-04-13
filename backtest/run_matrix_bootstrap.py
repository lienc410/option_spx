"""
Matrix-level block bootstrap (SPEC-059 F2).

Reads matrix_audit.csv (or re-runs the audit), applies block bootstrap
to every cell with n >= MIN_N_BOOTSTRAP, and outputs an extended CSV.
"""
from __future__ import annotations

import os
from dataclasses import replace

import pandas as pd

from backtest.engine import DEFAULT_PARAMS, run_backtest
from backtest.run_bootstrap_ci import DEFAULT_N_BOOT, MIN_N_BOOTSTRAP, bootstrap_ci
from backtest.run_matrix_audit import STRATEGY_KEYS, run_matrix_audit
from strategy.catalog import strategy_key as catalog_key


def run_matrix_bootstrap(
    matrix_csv: str = "backtest/output/matrix_audit.csv",
    n_boot: int = DEFAULT_N_BOOT,
    min_n: int = MIN_N_BOOTSTRAP,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    save_csv: bool = True,
) -> pd.DataFrame:
    keys = STRATEGY_KEYS
    sig_lookup: dict[str, list[dict]] = {}

    for strategy_key in keys:
        forced_params = replace(DEFAULT_PARAMS, force_strategy=strategy_key)
        result = run_backtest(
            start_date=start_date,
            end_date=end_date,
            params=forced_params,
            verbose=False,
        )
        sig_by_date = {row["date"]: row for row in result.signals}

        trade_rows: list[dict] = []
        for trade in result.trades:
            if catalog_key(trade.strategy.value) != strategy_key:
                continue
            sig = sig_by_date.get(trade.entry_date, {})
            cell = f"{sig.get('regime', '?')}|{sig.get('iv_signal', '?')}|{sig.get('trend', '?')}"
            trade_rows.append({"cell": cell, "pnl": trade.exit_pnl})
        sig_lookup[strategy_key] = trade_rows

    audit_df = run_matrix_audit(
        strategy_keys=keys,
        start_date=start_date,
        end_date=end_date,
        save_csv=False,
    )

    ci_rows: list[dict] = []
    for _, row in audit_df.iterrows():
        strategy_key = row["strategy_key"]
        cell = row["cell"]
        n = int(row["n"])

        pnls = [item["pnl"] for item in sig_lookup.get(strategy_key, []) if item["cell"] == cell]
        if n < min_n or not pnls:
            ci = {
                "ci_lo": float("nan"),
                "ci_hi": float("nan"),
                "significant": False,
                "block_size": 0,
            }
        else:
            result_ci = bootstrap_ci(pnls, n_boot=n_boot)
            ci = {
                "ci_lo": result_ci["ci_lo"],
                "ci_hi": result_ci["ci_hi"],
                "significant": result_ci["significant"],
                "block_size": result_ci["block_size"],
            }
        ci_rows.append({**row.to_dict(), **ci})

    out_df = pd.DataFrame(ci_rows)
    if save_csv and not out_df.empty:
        os.makedirs("backtest/output", exist_ok=True)
        out_df.to_csv("backtest/output/matrix_audit_bootstrap.csv", index=False)
    return out_df


def print_bootstrap_matrix(df: pd.DataFrame) -> None:
    """
    Print pivot: rows = cell, columns = strategy.
    Format per cell: $mean [ci_lo, ci_hi] ✓/空
    Only shows n >= MIN_N_BOOTSTRAP rows.
    """
    if df.empty:
        print("No data.")
        return

    df_sig = df[df["n"] >= MIN_N_BOOTSTRAP].copy()
    rows: list[dict] = []
    for cell, grp in df_sig.groupby("cell"):
        row = {"cell": cell}
        for _, rec in grp.iterrows():
            if pd.isna(rec["ci_lo"]):
                tag = f"${rec['avg_pnl']:,.0f} (n={rec['n']})"
            else:
                marker = " ✓" if rec["significant"] else ""
                tag = f"${rec['avg_pnl']:,.0f} [${rec['ci_lo']:,.0f},${rec['ci_hi']:,.0f}]{marker}"
            row[rec["strategy_key"]] = tag
        rows.append(row)

    pivot = pd.DataFrame(rows).set_index("cell")
    ordered = [k for k in STRATEGY_KEYS if k in pivot.columns]
    print(pivot[ordered].to_string())


if __name__ == "__main__":
    print("Running matrix bootstrap (this may take 10–15 minutes)...\n")
    df = run_matrix_bootstrap()
    print_bootstrap_matrix(df)
