"""Tests for SPEC-059: Block Bootstrap CI."""
from __future__ import annotations

import math
import os
import unittest
from unittest.mock import patch

from backtest.engine import BacktestResult, Trade
from strategy.selector import StrategyName


class Spec059Tests(unittest.TestCase):
    def test_ac1_all_positive_significant(self):
        from backtest.run_bootstrap_ci import bootstrap_ci

        result = bootstrap_ci([100.0] * 20)
        self.assertEqual(result["n"], 20)
        self.assertAlmostEqual(result["mean"], 100.0, places=1)
        self.assertTrue(result["significant"])
        self.assertGreater(result["ci_lo"], 0)

    def test_ac2_all_negative_not_significant(self):
        from backtest.run_bootstrap_ci import bootstrap_ci

        result = bootstrap_ci([-50.0] * 20)
        self.assertFalse(result["significant"])
        self.assertLess(result["ci_hi"], 0)

    def test_ac3_zero_mean_not_significant(self):
        from backtest.run_bootstrap_ci import bootstrap_ci

        result = bootstrap_ci([100.0, -100.0] * 10)
        self.assertFalse(result["significant"])
        self.assertLess(result["ci_lo"], 0)
        self.assertGreater(result["ci_hi"], 0)

    @patch("backtest.run_matrix_bootstrap.run_matrix_audit")
    @patch("backtest.run_matrix_bootstrap.run_backtest")
    def test_ac4_bootstrap_fills_ci_for_sufficient_n(self, mock_run_backtest, mock_run_matrix_audit):
        from backtest.run_bootstrap_ci import MIN_N_BOOTSTRAP
        from backtest.run_matrix_bootstrap import run_matrix_bootstrap

        mock_run_backtest.return_value = BacktestResult(
            trades=[Trade(strategy=StrategyName.BULL_PUT_SPREAD, underlying="SPX", entry_date=f"2020-01-{i:02d}", exit_date=f"2020-01-{i+1:02d}", exit_pnl=100.0 + i, exit_reason="50pct_profit") for i in range(2, 14)],
            metrics={},
            signals=[{"date": f"2020-01-{i:02d}", "regime": "NORMAL", "iv_signal": "HIGH", "trend": "BULLISH"} for i in range(2, 14)],
        )
        mock_run_matrix_audit.return_value = __import__("pandas").DataFrame([
            {"strategy_key": "bull_put_spread", "cell": "NORMAL|HIGH|BULLISH", "regime": "NORMAL", "iv_signal": "HIGH", "trend": "BULLISH", "n": MIN_N_BOOTSTRAP + 2, "avg_pnl": 106.0, "win_rate": 1.0, "sharpe": 1.0, "max_consec_loss": 0, "avg_hold_days": 1.0, "low_n_flag": False}
        ])
        df = run_matrix_bootstrap(n_boot=200, save_csv=False)
        sufficient = df[df["n"] >= MIN_N_BOOTSTRAP]
        self.assertFalse(sufficient.empty)
        for _, row in sufficient.iterrows():
            self.assertFalse(math.isnan(row["ci_lo"]))

    @patch("backtest.run_matrix_bootstrap.run_matrix_audit")
    @patch("backtest.run_matrix_bootstrap.run_backtest")
    def test_ac5_low_n_cells_have_nan_ci(self, mock_run_backtest, mock_run_matrix_audit):
        from backtest.run_bootstrap_ci import MIN_N_BOOTSTRAP
        from backtest.run_matrix_bootstrap import run_matrix_bootstrap

        mock_run_backtest.return_value = BacktestResult(
            trades=[Trade(strategy=StrategyName.BULL_PUT_SPREAD, underlying="SPX", entry_date="2020-01-02", exit_date="2020-01-03", exit_pnl=80.0, exit_reason="50pct_profit")],
            metrics={},
            signals=[{"date": "2020-01-02", "regime": "NORMAL", "iv_signal": "HIGH", "trend": "BULLISH"}],
        )
        mock_run_matrix_audit.return_value = __import__("pandas").DataFrame([
            {"strategy_key": "bull_put_spread", "cell": "NORMAL|HIGH|BULLISH", "regime": "NORMAL", "iv_signal": "HIGH", "trend": "BULLISH", "n": MIN_N_BOOTSTRAP - 1, "avg_pnl": 80.0, "win_rate": 1.0, "sharpe": 0.0, "max_consec_loss": 0, "avg_hold_days": 1.0, "low_n_flag": True}
        ])
        df = run_matrix_bootstrap(n_boot=200, save_csv=False)
        low_n = df[df["n"] < MIN_N_BOOTSTRAP]
        for _, row in low_n.iterrows():
            self.assertTrue(math.isnan(row["ci_lo"]))
            self.assertFalse(row["significant"])

    @patch("backtest.run_matrix_bootstrap.run_matrix_audit")
    @patch("backtest.run_matrix_bootstrap.run_backtest")
    def test_ac6_csv_saved(self, mock_run_backtest, mock_run_matrix_audit):
        from backtest.run_matrix_bootstrap import run_matrix_bootstrap

        path = "backtest/output/matrix_audit_bootstrap.csv"
        if os.path.exists(path):
            os.remove(path)

        mock_run_backtest.return_value = BacktestResult(
            trades=[Trade(strategy=StrategyName.BULL_PUT_SPREAD, underlying="SPX", entry_date=f"2020-01-{i:02d}", exit_date=f"2020-01-{i+1:02d}", exit_pnl=100.0 + i, exit_reason="50pct_profit") for i in range(2, 14)],
            metrics={},
            signals=[{"date": f"2020-01-{i:02d}", "regime": "NORMAL", "iv_signal": "HIGH", "trend": "BULLISH"} for i in range(2, 14)],
        )
        mock_run_matrix_audit.return_value = __import__("pandas").DataFrame([
            {"strategy_key": "bull_put_spread", "cell": "NORMAL|HIGH|BULLISH", "regime": "NORMAL", "iv_signal": "HIGH", "trend": "BULLISH", "n": 12, "avg_pnl": 106.0, "win_rate": 1.0, "sharpe": 1.0, "max_consec_loss": 0, "avg_hold_days": 1.0, "low_n_flag": False}
        ])
        df = run_matrix_bootstrap(n_boot=200, save_csv=True)
        if df.empty:
            self.skipTest("No rows to save")
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
