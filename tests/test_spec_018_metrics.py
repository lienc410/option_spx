import unittest

from backtest.engine import Trade, compute_metrics
from notify.telegram_bot import _format_backtest_summary
from strategy.selector import StrategyName


def make_trade(pnl: float, strategy: StrategyName = StrategyName.BULL_PUT_SPREAD) -> Trade:
    return Trade(
        strategy=strategy,
        underlying="SPX",
        entry_date="2026-01-02",
        exit_date="2026-01-15",
        entry_spx=6000.0,
        exit_spx=6050.0,
        entry_vix=18.0,
        entry_credit=1000.0,
        exit_pnl=pnl,
        exit_reason="50pct_profit" if pnl > 0 else "stop_loss",
        dte_at_entry=30,
        dte_at_exit=17,
    )


class Spec018MetricsTests(unittest.TestCase):
    def test_compute_metrics_adds_extended_fields(self) -> None:
        metrics = compute_metrics([
            make_trade(500.0),
            make_trade(-1000.0),
            make_trade(250.0, StrategyName.IRON_CONDOR),
            make_trade(350.0, StrategyName.IRON_CONDOR),
        ])
        for key in ("calmar", "cvar5", "cvar10", "skew", "kurt"):
            self.assertIn(key, metrics)

    def test_compute_metrics_empty_is_safe(self) -> None:
        metrics = compute_metrics([])
        self.assertEqual(metrics["error"], "no trades")
        self.assertEqual(metrics["total_trades"], 0)
        for key in ("calmar", "cvar5", "cvar10", "skew", "kurt"):
            self.assertIn(key, metrics)

    def test_backtest_summary_mentions_spec_018_fields(self) -> None:
        metrics = compute_metrics([make_trade(500.0), make_trade(-250.0), make_trade(300.0)])
        msg = _format_backtest_summary([], metrics)
        self.assertIn("Calmar:", msg)
        self.assertIn("CVaR 5%:", msg)
        self.assertIn("Skew:", msg)


if __name__ == "__main__":
    unittest.main()
