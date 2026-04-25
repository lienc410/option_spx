from __future__ import annotations

import unittest

import pandas as pd

from backtest.engine import (
    Position,
    StrategyName,
    Trade,
    _virtual_open_at_end_trade,
    compute_metrics,
)


class Spec069Tests(unittest.TestCase):
    def test_compute_metrics_excludes_open_at_end_and_counts_them(self) -> None:
        closed = Trade(
            strategy=StrategyName.BULL_PUT_SPREAD,
            underlying="SPX",
            entry_date="2026-01-05",
            exit_date="2026-01-18",
            entry_spx=5000.0,
            exit_spx=5050.0,
            entry_vix=18.5,
            entry_credit=3.2,
            exit_pnl=450.0,
            exit_reason="roll_21dte",
            dte_at_entry=45,
            dte_at_exit=21,
        )
        open_at_end = Trade(
            strategy=StrategyName.IRON_CONDOR_HV,
            underlying="SPX",
            entry_date="2026-02-10",
            exit_date="2026-02-28",
            entry_spx=5100.0,
            exit_spx=5120.0,
            entry_vix=27.0,
            entry_credit=-8.5,
            exit_pnl=9999.0,
            exit_reason="open_at_end",
            dte_at_entry=45,
            dte_at_exit=33,
            open_at_end=True,
        )

        metrics = compute_metrics([closed, open_at_end])

        self.assertEqual(metrics["total_trades"], 1)
        self.assertEqual(metrics["n_open_at_end"], 1)
        self.assertEqual(metrics["total_pnl"], 450.0)

    def test_virtual_trade_marks_open_at_end_with_terminal_mark(self) -> None:
        position = Position(
            strategy=StrategyName.IRON_CONDOR_HV,
            underlying="SPX",
            entry_date="2026-03-01",
            entry_spx=5000.0,
            entry_vix=25.0,
            entry_sigma=0.25,
            legs=[
                (-1, True, 5600.0, 45, 1),
                (+1, True, 5800.0, 45, 1),
                (-1, False, 4500.0, 45, 1),
                (+1, False, 4300.0, 45, 1),
            ],
            entry_value=-6.5,
            days_held=5,
            spread_width=200.0,
            bp_per_contract=19_350.0,
            bp_target=0.07,
        )

        trade = _virtual_open_at_end_trade(
            position=position,
            date=pd.Timestamp("2026-03-31"),
            spx=5050.0,
            sigma=0.22,
            account_size=150_000.0,
        )

        self.assertTrue(trade.open_at_end)
        self.assertEqual(trade.exit_reason, "open_at_end")
        self.assertEqual(trade.exit_date, "2026-03-31")
        self.assertGreater(trade.contracts, 0.0)
        self.assertNotEqual(trade.exit_pnl, 0.0)


if __name__ == "__main__":
    unittest.main()
