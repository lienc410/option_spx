"""Q042 Tier 2 — 19y baseline backtest for BP-envelope extraction.

Runs main strategy from 2007-01-01 → 2026-05-08 to produce a daily BP-used
series. Output: research/q042/baseline_19y_bp_daily.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest import engine as eng


def main() -> None:
    print("running 19y baseline backtest 2007-01-01 → 2026-05-08 …")
    result = eng.run_backtest(
        start_date="2007-01-01",
        end_date="2026-05-08",
        verbose=False,
    )
    print(f"  trades: {len(result.trades)}")
    print(f"  signals: {len(result.signals)}")
    print(f"  portfolio rows: {len(result.portfolio_rows)}")

    out = Path(__file__).resolve().parent / "baseline_19y_bp_daily.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "bp_used_usd", "bp_pct_account",
                    "open_positions", "regime", "vix",
                    "cumulative_equity", "drawdown"])
        for row in result.portfolio_rows:
            equity = max(row.cumulative_equity, 1.0)
            w.writerow([
                row.date,
                round(row.bp_used, 2),
                round(row.bp_used / equity * 100, 2),
                row.open_positions,
                row.regime,
                round(row.vix, 2) if row.vix is not None else "",
                round(row.cumulative_equity, 2),
                round(row.drawdown, 4),
            ])
    print(f"  wrote {out}")

    trades_out = Path(__file__).resolve().parent / "baseline_19y_trades.csv"
    with trades_out.open("w", newline="") as f:
        w = csv.writer(f)
        if result.trades:
            t0 = result.trades[0]
            w.writerow(["entry_date", "exit_date", "strategy", "regime",
                        "exit_pnl", "total_bp", "bp_pct_account",
                        "contracts", "dte_at_entry", "dte_at_exit"])
            for t in result.trades:
                w.writerow([
                    str(t.entry_date), str(t.exit_date),
                    t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy),
                    getattr(t, "regime", ""),
                    round(t.exit_pnl, 2),
                    round(t.total_bp, 2),
                    round(t.bp_pct_account, 4),
                    round(getattr(t, "contracts", 1.0), 4),
                    getattr(t, "dte_at_entry", ""),
                    getattr(t, "dte_at_exit", ""),
                ])
        print(f"  wrote {trades_out}")


if __name__ == "__main__":
    main()
