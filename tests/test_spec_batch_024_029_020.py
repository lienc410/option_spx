import math
import unittest

import pandas as pd

from backtest.engine import BacktestResult
from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.portfolio import DailyPortfolioRow
from backtest.run_oos_validation import _split
from backtest.run_shock_analysis import compute_hit_rates
from backtest.shock_engine import LegSnapshot, PositionSnapshot, run_shock_check
from signals.overlay import OverlayLevel, compute_overlay_signals
from signals.trend import _classify_trend_atr, _compute_atr14_close
from strategy.selector import StrategyParams


class SpecBatchTests(unittest.TestCase):
    def test_backtest_result_tuple_compatibility(self):
        result = BacktestResult(trades=[1], metrics={"a": 1}, signals=[{"b": 2}])
        trades, metrics, signals = result
        self.assertEqual(trades, [1])
        self.assertEqual(metrics["a"], 1)
        self.assertEqual(signals[0]["b"], 2)

    def test_portfolio_metrics_include_pnl_per_bp_day(self):
        rows = [
            DailyPortfolioRow(
                date="2026-01-02",
                start_equity=100_000,
                end_equity=100_500,
                daily_return_gross=0.005,
                daily_return_net=0.005,
                realized_pnl=300,
                unrealized_pnl_delta=200,
                total_pnl=500,
                bp_used=5_000,
                bp_headroom=95_000,
                short_gamma_count=1,
                open_positions=1,
                regime="NORMAL",
                vix=20.0,
                cumulative_equity=100_500,
                drawdown=0.0,
                experiment_id="EXP-TEST",
            ),
            DailyPortfolioRow(
                date="2026-01-03",
                start_equity=100_500,
                end_equity=100_700,
                daily_return_gross=200 / 100_500,
                daily_return_net=200 / 100_500,
                realized_pnl=100,
                unrealized_pnl_delta=100,
                total_pnl=200,
                bp_used=4_000,
                bp_headroom=96_000,
                short_gamma_count=1,
                open_positions=1,
                regime="NORMAL",
                vix=21.0,
                cumulative_equity=100_700,
                drawdown=0.0,
                experiment_id="EXP-TEST",
            ),
        ]
        metrics = compute_portfolio_metrics(rows)
        self.assertGreater(metrics.pnl_per_bp_day, 0.0)
        self.assertEqual(metrics.experiment_id, "EXP-TEST")

    def test_shock_check_shadow_and_active(self):
        params = StrategyParams()
        leg = LegSnapshot(option_type="put", strike=5000.0, dte=30, contracts=-50.0, current_spx=5000.0)
        pos = PositionSnapshot(strategy_key="bull_put_spread", is_short_gamma=True, legs=[leg])

        shadow = run_shock_check(
            positions=[pos],
            current_spx=5000.0,
            current_vix=25.0,
            date="2026-01-01",
            params=params,
            account_size=100_000.0,
        )
        self.assertTrue(shadow.approved)

        active_params = StrategyParams(shock_mode="active", shock_budget_core_normal=0.00001, shock_budget_incremental=0.00001)
        active = run_shock_check(
            positions=[],
            current_spx=5000.0,
            current_vix=25.0,
            date="2026-01-01",
            params=active_params,
            candidate_position=pos,
            account_size=100_000.0,
        )
        self.assertFalse(active.approved)
        self.assertTrue(active.reject_reason)

    def test_overlay_disabled_and_trim(self):
        disabled = compute_overlay_signals(
            vix=22.0,
            vix_3d_ago=21.0,
            book_core_shock=-0.002,
            bp_headroom=0.8,
            params=StrategyParams(),
        )
        self.assertEqual(disabled.level, OverlayLevel.L0_NORMAL)

        active = compute_overlay_signals(
            vix=30.0,
            vix_3d_ago=20.0,
            book_core_shock=-0.012,
            bp_headroom=0.7,
            params=StrategyParams(overlay_mode="active"),
        )
        self.assertEqual(active.level, OverlayLevel.L2_TRIM)
        self.assertTrue(active.force_trim)

    def test_compute_hit_rates_uses_budgets_not_approved(self):
        analysis = compute_hit_rates(
            [
                {
                    "date": "2024-01-02",
                    "regime": "HIGH_VOL",
                    "approved": True,
                    "post_max_core_loss_pct": -0.02,
                    "incremental_shock_pct": -0.001,
                    "bp_headroom_pct": 0.20,
                    "budget_core": 0.01,
                    "budget_incremental": 0.01,
                    "bp_headroom_budget": 0.15,
                }
            ]
        )
        self.assertEqual(analysis.any_breach_count, 1)
        self.assertEqual(analysis.core_breach_count, 1)

    def test_oos_split_has_no_overlap(self):
        result = BacktestResult(
            trades=[],
            metrics={},
            signals=[],
            portfolio_rows=[
                DailyPortfolioRow("2019-12-31", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, "NORMAL", 20, 1, 0, "EXP"),
                DailyPortfolioRow("2020-01-01", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, "NORMAL", 20, 1, 0, "EXP"),
            ],
        )
        is_rows, oos_rows = _split(result, "2020-01-01")
        self.assertEqual(len(is_rows), 1)
        self.assertEqual(len(oos_rows), 1)
        self.assertLess(is_rows[0].date, oos_rows[0].date)

    def test_atr_helpers(self):
        series = pd.Series([100 + i for i in range(20)], dtype=float)
        atr = _compute_atr14_close(series)
        self.assertTrue(math.isnan(atr.iloc[13]))
        self.assertFalse(math.isnan(atr.iloc[14]))
        self.assertEqual(_classify_trend_atr(1.0).value, "BULLISH")
        self.assertEqual(_classify_trend_atr(0.99).value, "NEUTRAL")


if __name__ == "__main__":
    unittest.main()
