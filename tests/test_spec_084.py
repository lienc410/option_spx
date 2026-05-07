import unittest
from unittest.mock import patch

import web.server as server_mod
from backtest.engine import run_backtest
from signals.iv_rank import IVSignal
from signals.trend import TrendSignal
from signals.vix_regime import Regime, Trend
from strategy.selector import StrategyParams, _size_rule
from tests.test_strategy_unification import make_vix


class Spec084Tests(unittest.TestCase):
    def test_default_bp_targets_are_q045_j3_values(self) -> None:
        params = StrategyParams()

        self.assertEqual(params.bp_target_low_vol, 0.15)
        self.assertEqual(params.bp_target_normal, 0.15)
        self.assertEqual(params.bp_target_high_vol, 0.14)

    def test_size_rule_display_text_uses_updated_account_risk(self) -> None:
        full = _size_rule(
            make_vix(vix=18.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            IVSignal.HIGH,
            TrendSignal.BULLISH,
        )
        half = _size_rule(
            make_vix(vix=18.0, regime=Regime.NORMAL, trend=Trend.RISING),
            IVSignal.HIGH,
            TrendSignal.BULLISH,
        )

        self.assertIn("4.5%", full)
        self.assertIn("2.25%", half)
        self.assertNotIn("3% of account", full)
        self.assertNotIn("1.5% of account", half)

    def test_old_baseline_override_remains_runnable(self) -> None:
        old_params = StrategyParams(
            bp_target_low_vol=0.10,
            bp_target_normal=0.10,
            bp_target_high_vol=0.07,
        )

        self.assertEqual(old_params.bp_target_for_regime(Regime.NORMAL) * 100.0, 10.0)
        with patch("strategy.selector.DEFAULT_PARAMS", old_params):
            self.assertEqual(
                server_mod._bp_target_fraction_for_strategy("bull_put_spread", "NORMAL") * 100.0,
                10.0,
            )

        result = run_backtest(
            start_date="2024-01-01",
            end_date="2024-03-31",
            params=old_params,
            verbose=False,
        )
        self.assertIsNotNone(result.metrics)

    def test_bp_ceilings_are_unchanged(self) -> None:
        params = StrategyParams()

        self.assertEqual(params.bp_ceiling_normal, 0.35)
        self.assertEqual(params.bp_ceiling_high_vol, 0.50)


if __name__ == "__main__":
    unittest.main()
