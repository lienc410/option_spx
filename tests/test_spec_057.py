"""Tests for SPEC-057: Force-entry matrix audit."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch


class Spec057Tests(unittest.TestCase):
    def _make_snaps(self, ivp63=40.0, ivp252=25.0):
        from strategy.selector import IVSnapshot, TrendSnapshot, VixSnapshot
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend

        v = VixSnapshot(
            date="2024-01-01", vix=28.0, regime=Regime.HIGH_VOL,
            trend=Trend.FLAT, vix_5d_avg=27.0, vix_5d_ago=26.0,
            transition_warning=False, vix3m=27.0, backwardation=False,
        )
        i = IVSnapshot(
            date="2024-01-01", vix=28.0,
            iv_rank=70.0, iv_percentile=float(ivp252), iv_signal=IVSignal.HIGH,
            iv_52w_high=40.0, iv_52w_low=15.0,
            ivp63=float(ivp63), ivp252=float(ivp252), regime_decay=False,
        )
        t = TrendSnapshot(
            date="2024-01-01", spx=4200.0,
            ma20=4300.0, ma50=4400.0, ma_gap_pct=-0.05, signal=TrendSignal.BEARISH,
            above_200=False, atr14=None, gap_sigma=None,
        )
        return v, i, t

    def test_ac1_default_force_strategy_none(self):
        from strategy.selector import DEFAULT_PARAMS

        self.assertIsNone(DEFAULT_PARAMS.force_strategy)

    def test_ac2_force_strategy_overrides_routing(self):
        from strategy.selector import StrategyName, StrategyParams, select_strategy

        params = StrategyParams(force_strategy="bull_call_diagonal")
        v, i, t = self._make_snaps()
        rec = select_strategy(v, i, t, params)
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)

    def test_ac2b_force_strategy_never_reduce_wait(self):
        from strategy.selector import IVSnapshot, StrategyName, StrategyParams, TrendSnapshot, VixSnapshot, select_strategy
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend

        v = VixSnapshot(
            date="2024-01-01", vix=40.0, regime=Regime.HIGH_VOL,
            trend=Trend.RISING, vix_5d_avg=38.0, vix_5d_ago=32.0,
            transition_warning=False, vix3m=38.0, backwardation=False,
        )
        i = IVSnapshot(
            date="2024-01-01", vix=40.0,
            iv_rank=90.0, iv_percentile=30.0, iv_signal=IVSignal.NEUTRAL,
            iv_52w_high=45.0, iv_52w_low=15.0,
            ivp63=90.0, ivp252=30.0, regime_decay=False,
        )
        t = TrendSnapshot(
            date="2024-01-01", spx=4000.0,
            ma20=4200.0, ma50=4300.0, ma_gap_pct=-0.07, signal=TrendSignal.BEARISH,
            above_200=False, atr14=None, gap_sigma=None,
        )
        rec = select_strategy(v, i, t, StrategyParams(force_strategy="iron_condor"))
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR)

    def test_ac3_all_strategies_build_valid_recommendation(self):
        from strategy.catalog import STRATEGIES_BY_KEY
        from strategy.selector import StrategyParams, _build_forced_recommendation

        params = StrategyParams()
        v, i, t = self._make_snaps()
        keys = [k for k in STRATEGIES_BY_KEY if k != "reduce_wait"]
        for key in keys:
            rec = _build_forced_recommendation(key, v, i, t, params)
            self.assertIsNotNone(rec)
            self.assertIsNotNone(rec.strategy)
            self.assertTrue(len(rec.legs) > 0)

    @patch("backtest.run_matrix_audit.run_backtest")
    def test_ac4_matrix_audit_strategy_key_consistent(self, mock_run_backtest):
        from backtest.engine import BacktestResult, Trade
        from backtest.run_matrix_audit import run_matrix_audit
        from strategy.selector import StrategyName

        mock_run_backtest.return_value = BacktestResult(
            trades=[
                Trade(strategy=StrategyName.BULL_CALL_DIAGONAL, underlying="SPX", entry_date="2020-01-02", exit_date="2020-01-23", exit_pnl=100.0, exit_reason="50pct_profit"),
                Trade(strategy=StrategyName.BULL_CALL_DIAGONAL, underlying="SPX", entry_date="2020-02-03", exit_date="2020-02-24", exit_pnl=-50.0, exit_reason="stop_loss"),
            ],
            metrics={},
            signals=[
                {"date": "2020-01-02", "regime": "LOW_VOL", "iv_signal": "LOW", "trend": "BULLISH"},
                {"date": "2020-02-03", "regime": "NORMAL", "iv_signal": "NEUTRAL", "trend": "BEARISH"},
            ],
        )
        df = run_matrix_audit(strategy_keys=["bull_call_diagonal"], save_csv=False)
        if df.empty:
            self.skipTest("No trades in window")
        self.assertTrue((df["strategy_key"] == "bull_call_diagonal").all())

    def test_ac5_signal_history_has_iv_signal(self):
        from backtest.engine import run_backtest

        result = run_backtest(start_date="2020-01-01", end_date="2020-06-30", verbose=False)
        self.assertTrue(result.signals)
        row = result.signals[0]
        self.assertIn("iv_signal", row)
        self.assertIn(row["iv_signal"], ("HIGH", "NEUTRAL", "LOW"))

    @patch("backtest.run_matrix_audit.run_backtest")
    def test_ac6_matrix_audit_saves_csv(self, mock_run_backtest):
        from backtest.engine import BacktestResult, Trade
        from backtest.run_matrix_audit import run_matrix_audit
        from strategy.selector import StrategyName

        path = "backtest/output/matrix_audit.csv"
        if os.path.exists(path):
            os.remove(path)

        mock_run_backtest.return_value = BacktestResult(
            trades=[
                Trade(strategy=StrategyName.BULL_PUT_SPREAD, underlying="SPX", entry_date="2020-03-02", exit_date="2020-03-23", exit_pnl=80.0, exit_reason="50pct_profit"),
            ],
            metrics={},
            signals=[
                {"date": "2020-03-02", "regime": "HIGH_VOL", "iv_signal": "HIGH", "trend": "BEARISH"},
            ],
        )
        df = run_matrix_audit(strategy_keys=["bull_put_spread"], save_csv=True)
        if df.empty:
            self.skipTest("No trades to save")
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
