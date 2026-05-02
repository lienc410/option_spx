"""SPEC-078 F4 — annualized_roe server SoT vs JS formula parity test.

The server's `compute_metrics` adds three SPEC-078 fields:
- `annualized_roe`        (float, %)
- `annualized_roe_basis`  ("final_equity_compound")
- `period_years`          (float, years)

These must be byte-identical (within 1e-6) to the JS reference at
web/templates/backtest.html:1965  `impliedAnnualizedRoe`.

Run:
    arch -arm64 venv/bin/python -m unittest tests.test_metrics_annualized_roe -v
"""
from __future__ import annotations

import math
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.engine import (
    Trade, compute_metrics, _annualized_roe_pct, _BACKTEST_BASELINE_EQUITY,
)
from strategy.selector import StrategyName


def _js_implied_roe(total_pnl: float, trades: list[Trade]) -> tuple[float, float]:
    """Reference implementation that mirrors backtest.html:1965 line-for-line."""
    if not trades:
        return 0.0, 0.0
    start = datetime.fromisoformat(str(trades[0].entry_date)[:10])
    end = datetime.fromisoformat(str(trades[-1].exit_date)[:10])
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    years = days / 365.25
    final_equity = _BACKTEST_BASELINE_EQUITY + float(total_pnl or 0.0)
    if years <= 0 or final_equity <= 0:
        return 0.0, years
    return (math.pow(final_equity / _BACKTEST_BASELINE_EQUITY, 1.0 / years) - 1.0) * 100.0, years


def _make_trade(entry: str, exit_: str, pnl: float) -> Trade:
    return Trade(
        strategy=StrategyName.IRON_CONDOR,
        underlying="SPX",
        entry_date=entry,
        exit_date=exit_,
        entry_credit=-1000.0,
        exit_pnl=pnl,
    )


class AnnualizedRoeServerSotTests(unittest.TestCase):
    """SPEC-078 F4 — server `annualized_roe` matches JS formula byte-identically."""

    def test_byte_identical_to_js_formula(self):
        trades = [
            _make_trade("2023-01-04", "2023-01-25", 1500.0),
            _make_trade("2023-02-01", "2023-02-25", -800.0),
            _make_trade("2024-06-10", "2024-07-05", 2200.0),
            _make_trade("2026-04-01", "2026-04-25", 1100.0),
        ]
        total_pnl = sum(t.exit_pnl for t in trades)

        srv_roe, srv_years = _annualized_roe_pct(total_pnl, trades)
        js_roe, js_years = _js_implied_roe(total_pnl, trades)

        self.assertAlmostEqual(srv_roe, js_roe, delta=1e-6)
        self.assertAlmostEqual(srv_years, js_years, delta=1e-6)

    def test_empty_trades_returns_zero(self):
        srv_roe, srv_years = _annualized_roe_pct(0.0, [])
        self.assertEqual(srv_roe, 0.0)
        self.assertEqual(srv_years, 0.0)

    def test_same_day_trade_does_not_divide_by_zero(self):
        trades = [_make_trade("2026-04-01", "2026-04-01", 250.0)]
        srv_roe, srv_years = _annualized_roe_pct(250.0, trades)
        js_roe, js_years = _js_implied_roe(250.0, trades)
        self.assertTrue(math.isfinite(srv_roe))
        self.assertTrue(math.isfinite(srv_years))
        self.assertAlmostEqual(srv_roe, js_roe, delta=1e-6)

    def test_compute_metrics_emits_spec078_fields(self):
        trades = [
            _make_trade("2023-01-04", "2023-01-25", 1500.0),
            _make_trade("2026-04-01", "2026-04-25", -300.0),
        ]
        # Set hold-day spread so sharpe path doesn't crash.
        for t in trades:
            t.dte_at_entry = 45
            t.dte_at_exit = 30
        m = compute_metrics(trades)
        self.assertIn("annualized_roe", m)
        self.assertIn("annualized_roe_basis", m)
        self.assertIn("period_years", m)
        self.assertEqual(m["annualized_roe_basis"], "final_equity_compound")
        self.assertGreater(m["period_years"], 3.0)
        self.assertLess(m["period_years"], 4.0)

    def test_compute_metrics_no_trades_branch_emits_spec078_fields(self):
        m = compute_metrics([])
        self.assertEqual(m["annualized_roe"], 0.0)
        self.assertEqual(m["period_years"], 0.0)
        self.assertEqual(m["annualized_roe_basis"], "final_equity_compound")


if __name__ == "__main__":
    unittest.main(verbosity=2)
