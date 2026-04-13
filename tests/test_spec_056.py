"""
Tests for SPEC-056: Data-driven strategy environment analysis tools
"""
from __future__ import annotations

import unittest
from unittest.mock import patch


def _fake_vix_snap(*, regime, trend):
    from strategy.selector import VixSnapshot

    return VixSnapshot(
        date="2024-01-01",
        vix=14.0 if regime.value == "LOW_VOL" else 28.0,
        regime=regime,
        trend=trend,
        vix_5d_avg=14.0,
        vix_5d_ago=14.0,
        transition_warning=False,
        vix3m=15.0,
        backwardation=False,
    )


def _fake_iv_snap(*, signal, ivp63, ivp252, iv_rank=25.0, iv_percentile=25.0, regime_decay=False, vix=14.0):
    from strategy.selector import IVSnapshot

    return IVSnapshot(
        date="2024-01-01",
        vix=vix,
        iv_rank=iv_rank,
        iv_percentile=iv_percentile,
        iv_signal=signal,
        iv_52w_high=35.0,
        iv_52w_low=10.0,
        ivp63=ivp63,
        ivp252=ivp252,
        regime_decay=regime_decay,
    )


def _fake_trend_snap(*, signal):
    from strategy.selector import TrendSnapshot

    return TrendSnapshot(
        date="2024-01-01",
        spx=4800.0,
        ma20=4750.0,
        ma50=4700.0,
        ma_gap_pct=0.02 if signal.value == "BULLISH" else -0.05 if signal.value == "BEARISH" else 0.0,
        signal=signal,
        above_200=True,
        atr14=None,
        gap_sigma=None,
    )


def _fake_backtest_result():
    from backtest.engine import BacktestResult, Trade
    from strategy.selector import StrategyName

    trades = [
        Trade(strategy=StrategyName.BULL_CALL_DIAGONAL, underlying="SPX", entry_date="2020-01-02", exit_date="2020-01-23", exit_pnl=100.0, exit_reason="50pct_profit"),
        Trade(strategy=StrategyName.BULL_CALL_DIAGONAL, underlying="SPX", entry_date="2020-02-03", exit_date="2020-02-24", exit_pnl=-50.0, exit_reason="stop_loss"),
        Trade(strategy=StrategyName.BULL_PUT_SPREAD, underlying="SPX", entry_date="2020-03-02", exit_date="2020-03-23", exit_pnl=80.0, exit_reason="50pct_profit"),
    ]
    signals = [
        {"date": "2020-01-02", "regime": "LOW_VOL", "trend": "BULLISH", "ivp": 25.0, "ivp252": 25.0, "ivp63": 60.0, "regime_decay": False, "local_spike": True},
        {"date": "2020-01-03", "regime": "LOW_VOL", "trend": "BULLISH", "ivp": 25.0, "ivp252": 25.0, "ivp63": 60.0, "regime_decay": False, "local_spike": True},
        {"date": "2020-01-06", "regime": "LOW_VOL", "trend": "BULLISH", "ivp": 25.0, "ivp252": 25.0, "ivp63": 60.0, "regime_decay": False, "local_spike": True},
        {"date": "2020-02-03", "regime": "NORMAL", "trend": "BULLISH", "ivp": 55.0, "ivp252": 55.0, "ivp63": 45.0, "regime_decay": True, "local_spike": False},
        {"date": "2020-02-04", "regime": "NORMAL", "trend": "BULLISH", "ivp": 55.0, "ivp252": 55.0, "ivp63": 45.0, "regime_decay": True, "local_spike": False},
        {"date": "2020-02-05", "regime": "NORMAL", "trend": "BULLISH", "ivp": 55.0, "ivp252": 55.0, "ivp63": 45.0, "regime_decay": True, "local_spike": False},
        {"date": "2020-03-02", "regime": "HIGH_VOL", "trend": "BEARISH", "ivp": 75.0, "ivp252": 75.0, "ivp63": 80.0, "regime_decay": False, "local_spike": False},
    ]
    return BacktestResult(trades=trades, metrics={}, signals=signals)


class Spec056Tests(unittest.TestCase):
    def test_t1_signal_history_has_ivp63_fields(self):
        from backtest.engine import run_backtest

        result = run_backtest(start_date="2020-01-01", end_date="2020-06-30", verbose=False)
        self.assertTrue(result.signals)
        row = result.signals[0]
        self.assertIn("ivp63", row)
        self.assertIn("ivp252", row)
        self.assertIn("regime_decay", row)
        self.assertIn("local_spike", row)
        self.assertIsInstance(row["ivp63"], float)
        self.assertIsInstance(row["regime_decay"], bool)

    def test_t2_regime_decay_local_spike_mutually_exclusive(self):
        from backtest.engine import run_backtest

        result = run_backtest(start_date="2010-01-01", end_date="2020-12-31", verbose=False)
        for row in result.signals:
            self.assertFalse(row["regime_decay"] and row["local_spike"])

    def test_t3_iv_snapshot_ivp63_field(self):
        from backtest.engine import run_backtest

        result = run_backtest(start_date="2020-01-01", end_date="2020-03-31", verbose=False)
        self.assertTrue(all(0 <= row["ivp63"] <= 100 for row in result.signals))

    def test_t4_default_disable_entry_gates_false(self):
        from strategy.selector import DEFAULT_PARAMS

        self.assertFalse(DEFAULT_PARAMS.disable_entry_gates)

    def test_t5_disable_gates_bypasses_diagonal_gate1(self):
        from strategy.selector import StrategyName, StrategyParams, select_strategy
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend

        params = StrategyParams(disable_entry_gates=True)
        rec = select_strategy(
            _fake_vix_snap(regime=Regime.LOW_VOL, trend=Trend.FLAT),
            _fake_iv_snap(signal=IVSignal.NEUTRAL, ivp63=45.0, ivp252=40.0, iv_percentile=40.0),
            _fake_trend_snap(signal=TrendSignal.BULLISH),
            params,
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)

    def test_t6_disable_gates_bypasses_diagonal_gate2(self):
        from strategy.selector import StrategyName, StrategyParams, select_strategy
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend

        params = StrategyParams(disable_entry_gates=True)
        rec = select_strategy(
            _fake_vix_snap(regime=Regime.LOW_VOL, trend=Trend.FLAT),
            _fake_iv_snap(signal=IVSignal.HIGH, ivp63=25.0, ivp252=25.0, iv_rank=70.0),
            _fake_trend_snap(signal=TrendSignal.BULLISH),
            params,
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)

    def test_t7_disable_gates_bypasses_diagonal_gate3(self):
        from strategy.selector import StrategyName, StrategyParams, select_strategy
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend

        params = StrategyParams(disable_entry_gates=True)
        rec = select_strategy(
            _fake_vix_snap(regime=Regime.LOW_VOL, trend=Trend.FLAT),
            _fake_iv_snap(signal=IVSignal.NEUTRAL, ivp63=60.0, ivp252=60.0, iv_rank=60.0, iv_percentile=60.0),
            _fake_trend_snap(signal=TrendSignal.BULLISH),
            params,
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)

    def test_t8_disable_gates_bypasses_bcs_hv_gate(self):
        from strategy.selector import StrategyName, StrategyParams, select_strategy
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend

        params = StrategyParams(disable_entry_gates=True)
        rec = select_strategy(
            _fake_vix_snap(regime=Regime.HIGH_VOL, trend=Trend.FLAT),
            _fake_iv_snap(signal=IVSignal.HIGH, ivp63=75.0, ivp252=25.0, iv_rank=80.0, iv_percentile=25.0, vix=28.0),
            _fake_trend_snap(signal=TrendSignal.BEARISH),
            params,
        )
        self.assertEqual(rec.strategy, StrategyName.BEAR_CALL_SPREAD_HV)

    def test_t9_gates_still_active_when_not_disabled(self):
        from strategy.selector import DEFAULT_PARAMS, StrategyName, select_strategy
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend

        rec = select_strategy(
            _fake_vix_snap(regime=Regime.LOW_VOL, trend=Trend.FLAT),
            _fake_iv_snap(signal=IVSignal.NEUTRAL, ivp63=45.0, ivp252=40.0, iv_percentile=40.0),
            _fake_trend_snap(signal=TrendSignal.BULLISH),
            DEFAULT_PARAMS,
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)

    @patch("backtest.run_event_study.run_backtest")
    def test_t10_event_study_has_signal_cols(self, mock_run_backtest):
        from backtest.run_event_study import run_event_study

        mock_run_backtest.return_value = _fake_backtest_result()
        df = run_event_study("bull_call_diagonal", fixed_hold_days=21, save_csv=False)
        self.assertFalse(df.empty)
        for col in ["regime", "trend", "ivp252", "ivp63", "regime_decay", "local_spike"]:
            self.assertIn(col, df.columns)

    @patch("backtest.run_conditional_pnl.run_backtest")
    def test_t11_conditional_pnl_structure(self, mock_run_backtest):
        from backtest.run_conditional_pnl import run_conditional_pnl

        mock_run_backtest.return_value = _fake_backtest_result()
        df = run_conditional_pnl("bull_call_diagonal", "regime_decay", save_csv=False)
        self.assertFalse(df.empty)
        for col in ["date", "signal_state", "pnl", "cum_pnl_by_state", "cum_pnl_global", "in_position"]:
            self.assertIn(col, df.columns)
        states = set(df["signal_state"].unique())
        self.assertTrue(True in states or False in states)

    @patch("backtest.run_strategy_audit.run_backtest")
    def test_t12_strategy_audit_bucket_count(self, mock_run_backtest):
        from backtest.run_strategy_audit import BUCKETS, run_strategy_audit

        mock_run_backtest.return_value = _fake_backtest_result()
        audit = run_strategy_audit(strategy_keys=["bull_call_diagonal"], save_csv=False)
        self.assertIn("bull_call_diagonal", audit)
        df = audit["bull_call_diagonal"]
        self.assertEqual(len(df), len(BUCKETS))

    @patch("backtest.run_strategy_audit.run_backtest")
    def test_t13_audit_gates_disabled_more_trades(self, mock_run_backtest):
        from backtest.run_strategy_audit import run_strategy_audit

        mock_run_backtest.return_value = _fake_backtest_result()
        audit = run_strategy_audit(strategy_keys=["bull_call_diagonal"], save_csv=False)
        ivp_rows = audit["bull_call_diagonal"][audit["bull_call_diagonal"]["bucket"].str.startswith("ivp_")]
        self.assertEqual(int(ivp_rows["n"].sum()), 2)

    def test_t14_ivp252_equals_ivp(self):
        from backtest.engine import run_backtest

        result = run_backtest(start_date="2020-01-01", end_date="2020-12-31", verbose=False)
        for row in result.signals:
            self.assertLess(abs(row["ivp252"] - row["ivp"]), 0.01)


if __name__ == "__main__":
    unittest.main()
