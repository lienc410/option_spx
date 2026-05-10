from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from web import server as server_mod
from web.server import app


class Spec093Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.client = app.test_client()
        self.orig_ledger_env = os.environ.get("Q041_PAPER_LEDGER_FILE")
        os.environ["Q041_PAPER_LEDGER_FILE"] = str(Path(self.tmpdir.name) / "q041_paper_trades.jsonl")

    def tearDown(self) -> None:
        if self.orig_ledger_env is None:
            os.environ.pop("Q041_PAPER_LEDGER_FILE", None)
        else:
            os.environ["Q041_PAPER_LEDGER_FILE"] = self.orig_ledger_env

    def _stub_backtest_payload(self) -> dict:
        return {
            "status": "ok",
            "start_date": "2022-05-06",
            "sleeves": [
                {
                    "symbol": "SPX",
                    "label": "SPX Tier-1 CSP",
                    "n_trades": 25,
                    "win_rate_pct": 76.0,
                    "stop_rate_pct": 12.0,
                    "total_pnl": 4400.0,
                    "equity_curve": [{"date": "2022-05-06", "equity": 50000.0}, {"date": "2026-04-29", "equity": 54400.0}],
                    "trades": [{"entry_date": "2022-05-20", "exit_date": "2022-06-17", "pnl": -1200.0, "dte_at_entry": 30, "dte_at_exit": 3, "exit_reason": "stop_loss", "vix_at_entry": 24.0}],
                },
                {
                    "symbol": "GOOGL",
                    "label": "GOOGL Tier-2 CSP",
                    "n_trades": 40,
                    "win_rate_pct": 91.0,
                    "stop_rate_pct": 5.0,
                    "total_pnl": 12000.0,
                    "equity_curve": [{"date": "2022-05-06", "equity": 50000.0}, {"date": "2026-04-29", "equity": 62000.0}],
                    "trades": [{"entry_date": "2022-05-20", "exit_date": "2022-06-10", "pnl": 400.0, "dte_at_entry": 21, "dte_at_exit": 4, "exit_reason": "profit_target", "vix_at_entry": 18.0}],
                },
                {
                    "symbol": "AMZN",
                    "label": "AMZN Tier-2 CSP",
                    "n_trades": 38,
                    "win_rate_pct": 84.0,
                    "stop_rate_pct": 8.0,
                    "total_pnl": 9000.0,
                    "equity_curve": [{"date": "2022-05-06", "equity": 50000.0}, {"date": "2026-04-29", "equity": 59000.0}],
                    "trades": [{"entry_date": "2022-05-20", "exit_date": "2022-06-10", "pnl": -300.0, "dte_at_entry": 21, "dte_at_exit": 4, "exit_reason": "stop_loss", "vix_at_entry": 28.0}],
                },
            ],
        }

    def _stub_attr(self) -> dict:
        return {
            "status": "available",
            "account_size_usd": 500000,
            "sleeves_simulated": [
                {"symbol": "SPX", "bp_cap_pct": 20.0},
                {"symbol": "GOOGL", "bp_cap_pct": 7.5},
                {"symbol": "AMZN", "bp_cap_pct": 7.5},
            ],
            "joint_bp_diagnostics": {"mean_pct": 38.04, "max_pct": 92.0},
            "idle_day_capture": {"value": 132, "share_of_j3_idle_pct": 86.84},
            "bp_fill_contribution": {"value": 22.21, "unit": "pct_points"},
            "worst_day_overlap": {"value": 87.8, "q041_open_occupancy_pct": 83.29},
        }

    @patch("web.portfolio_surface.attribution_payload")
    @patch("web.server._get_q041_backtest_payload")
    def test_overview_aggregates_q041_state(self, mock_backtest, mock_attr) -> None:
        mock_backtest.return_value = self._stub_backtest_payload()
        mock_attr.return_value = self._stub_attr()
        res = self.client.get("/api/q041/overview")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["tier_status"]["tier1"]["state"], "eliminated")
        self.assertEqual(payload["backtest_summary"]["tier2_combined"]["n_trades"], 78)
        self.assertEqual(payload["paper_progress"]["status"], "unavailable")

    @patch("web.portfolio_surface.attribution_payload")
    @patch("web.server._get_q041_backtest_payload")
    def test_matrix_page_includes_eliminated_and_caveat_surface(self, mock_backtest, mock_attr) -> None:
        mock_backtest.return_value = self._stub_backtest_payload()
        mock_attr.return_value = self._stub_attr()
        page = self.client.get("/q041")
        text = page.get_data(as_text=True)
        self.assertIn("/api/q041/overview", text)
        self.assertIn("ELIMINATED", text)
        self.assertIn("Tail caveat", text)
        self.assertIn("Tier 2 paper progress", text)

    def test_backtest_page_has_new_chart_carriers(self) -> None:
        page = self.client.get("/q041/backtest")
        text = page.get_data(as_text=True)
        self.assertIn("VIX Regime at Entry", text)
        self.assertIn("IV at Entry", text)
        self.assertIn("BP Utilization Timeline", text)
        self.assertIn("Main strategy overlay", text)
        self.assertIn("(backtest data)", text)
        self.assertIn("/api/q041/overview", text)
        self.assertIn("Geometric from equity curve", text)
        self.assertNotIn("on $${initEq.toFixed(0)}k baseline", text)

    @patch("web.server._build_q041_overview_payload", side_effect=RuntimeError("boom"))
    def test_overview_route_fails_soft(self, _mock_overview) -> None:
        res = self.client.get("/api/q041/overview")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertEqual(payload["status"], "error")
        self.assertIn("boom", payload["error"])


if __name__ == "__main__":
    unittest.main()
