from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from research.strategies.ES_puts.backtest import BacktestResult, PutTrade, run_phase2_v2f
from web import server as server_mod
from web.server import app


class Spec095BacktestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_phase2_v2f(mode="baseline", start_date="2000-01-01", end_date="2026-04-17")

    def test_ac1_to_ac4_v2f_metrics(self) -> None:
        result = self.result
        self.assertEqual(result.phase, "phase2_v2f_m1")
        self.assertGreaterEqual(len(result.trades), 100)
        self.assertGreater(result.portfolio_metrics.get("ann_return", 0.0), 0.0)
        worst_trade_pct = min(t.pnl for t in result.trades) / 500_000.0
        self.assertGreaterEqual(worst_trade_pct, -0.15)
        self.assertGreaterEqual(result.bootstrap.get("sig_rate", 0.0), 0.80)
        self.assertIn("stress_cluster_pct", result.stress_metrics)


class Spec095RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.client = app.test_client()
        self.orig_disk_cache = server_mod._ES_DISK_CACHE_PATH
        server_mod._ES_DISK_CACHE_PATH = str(Path(self.tmpdir.name) / "es_backtest_cache.json")
        server_mod._ES_BT_CACHE.clear()

    def tearDown(self) -> None:
        server_mod._ES_DISK_CACHE_PATH = self.orig_disk_cache
        server_mod._ES_BT_CACHE.clear()

    def _fake_result(self) -> BacktestResult:
        result = BacktestResult(phase="phase2_v2f_m1", mode="baseline")
        result.trades = [
            PutTrade(
                slot=49,
                entry_date="2026-01-02",
                exit_date="2026-01-30",
                entry_spx=6000.0,
                exit_spx=5980.0,
                entry_vix=18.0,
                entry_premium=25.0,
                exit_premium=7.0,
                dte_at_entry=49,
                dte_at_exit=21,
                exit_reason="ladder_exit",
                contracts=1.0,
                pnl=1800.0,
            )
        ]
        result.portfolio_metrics = {"ann_return": 0.0267, "daily_sharpe": 0.20, "total_days": 252}
        result.bootstrap = {"sig_rate": 1.0, "ci_lo": 0.0016}
        result.stress_metrics = {"stress_worst_single_pct_nlv": -0.1513, "stress_cluster_pct": -0.4407}
        return result

    @patch("research.strategies.ES_puts.backtest.run_phase2_v2f")
    def test_ac5_api_shape(self, mock_run) -> None:
        mock_run.side_effect = [self._fake_result(), self._fake_result()]
        start = time.perf_counter()
        res = self.client.get("/api/es-backtest/v2f?start=2000-01-01")
        elapsed = time.perf_counter() - start

        self.assertEqual(res.status_code, 200)
        self.assertLess(elapsed, 60.0)
        payload = res.get_json()
        self.assertEqual(payload["phase"], "phase2_v2f_m1")
        self.assertEqual(payload["mode"], "baseline")
        self.assertEqual(payload["v2f_baseline"]["ann_roe_geometric"], 0.0267)
        self.assertEqual(payload["v2f_m1"]["bootstrap_sig_rate"], 1.0)
        self.assertIn("m1_delta", payload)
        self.assertIsInstance(payload["caveats"], list)

    @patch("research.strategies.ES_puts.backtest.run_phase2_v2f", side_effect=RuntimeError("boom"))
    def test_ac6_api_fail_soft(self, _mock_run) -> None:
        res = self.client.get("/api/es-backtest/v2f")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertEqual(payload["phase"], "phase2_v2f_m1")
        self.assertEqual(payload["v2f_m1"], None)
        self.assertIn("boom", payload["error"])

    def test_ac7_ac8_page_includes_v2f_surface(self) -> None:
        page = self.client.get("/es-backtest")
        self.assertEqual(page.status_code, 200)
        text = page.get_data(as_text=True)
        self.assertIn("data-es-tab-btn=\"v2f\"", text)
        self.assertIn("/api/es-backtest/v2f", text)
        self.assertIn("V0 vs V2f Summary", text)
        self.assertIn("Research Caveats", text)
        self.assertIn("M1 Cluster Throttle", text)

    @patch("research.strategies.ES_puts.backtest.run_phase1_hybrid")
    def test_ac11_existing_v0_route_shape_unchanged(self, mock_run) -> None:
        fake = BacktestResult(phase="phase1_hybrid", mode="filtered")
        fake.trades = []
        fake.daily_rows = []
        fake.portfolio_metrics = {
            "ann_return": 0.01,
            "daily_sharpe": 0.1,
            "max_drawdown": -0.02,
            "actual_market_entries": 1,
            "bs_fallback_entries": 0,
        }
        mock_run.return_value = fake
        res = self.client.get("/api/es/backtest?mode=filtered&start=2022-05-01&hybrid=1")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("filtered", payload)
        self.assertNotIn("v2f", payload)
        self.assertEqual(payload["filtered"]["phase"], "phase1_hybrid")


if __name__ == "__main__":
    unittest.main()
