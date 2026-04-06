import unittest
from unittest.mock import patch

from performance.live import compute_live_performance
from web.server import app


class LivePerformanceTests(unittest.TestCase):
    def test_compute_live_performance_respects_voids_and_open_trades(self) -> None:
        resolved = [
            {
                "id": "t1",
                "voided": False,
                "open": {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "contracts": 2, "actual_premium": 3.0, "timestamp": "2026-04-01T09:31:00-04:00"},
                "close": {"exit_premium": 1.5, "timestamp": "2026-04-10T15:45:00-04:00"},
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
            {
                "id": "t2",
                "voided": False,
                "open": {"strategy_key": "iron_condor", "strategy": "Iron Condor", "contracts": 1, "actual_premium": 2.2, "timestamp": "2026-04-12T10:00:00-04:00"},
                "close": {"actual_pnl": -140.0, "timestamp": "2026-04-20T11:00:00-04:00"},
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
            {
                "id": "t3",
                "voided": False,
                "open": {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "contracts": 1, "actual_premium": 2.5, "timestamp": "2026-04-21T09:35:00-04:00"},
                "close": None,
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
            {
                "id": "t4",
                "voided": True,
                "open": {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "contracts": 1, "actual_premium": 2.5, "timestamp": "2026-04-02T09:35:00-04:00"},
                "close": {"actual_pnl": 500.0, "timestamp": "2026-04-06T15:30:00-04:00"},
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
        ]

        perf = compute_live_performance(resolved)
        self.assertEqual(perf["summary"]["closed_trades"], 2)
        self.assertEqual(perf["summary"]["open_trades"], 1)
        self.assertAlmostEqual(perf["summary"]["total_realized_pnl"], 160.0)
        self.assertAlmostEqual(perf["summary"]["win_rate"], 0.5)
        self.assertFalse(perf["include_paper"])
        self.assertEqual(perf["paper_trade_count"], 0)
        self.assertEqual(perf["trade_count_raw"], 4)
        self.assertEqual(perf["trade_count_effective"], 3)
        self.assertEqual(perf["by_strategy"]["bull_put_spread"]["n"], 1)
        self.assertEqual(perf["by_strategy"]["iron_condor"]["total_pnl"], -140.0)
        self.assertEqual(perf["monthly"][0]["month"], "2026-04")
        self.assertEqual(len(perf["recent_closed"]), 2)
        self.assertEqual(perf["recent_closed"][0]["id"], "t2")

    def test_compute_live_performance_enriches_open_position_with_schwab(self) -> None:
        resolved = [
            {
                "id": "t-open",
                "voided": False,
                "open": {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "contracts": 2, "actual_premium": 3.1, "timestamp": "2026-04-21T09:35:00-04:00"},
                "close": None,
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
        ]
        schwab_snapshot = {
            "visible": True,
            "mark": 2.7,
            "bid": 2.6,
            "ask": 2.8,
            "trade_log_pnl": 80.0,
            "unrealized_pnl": 74.0,
            "delta": -0.24,
            "theta": -0.11,
            "gamma": 0.02,
            "vega": 0.15,
        }

        perf = compute_live_performance(resolved, schwab_snapshot=schwab_snapshot)
        open_row = perf["open_positions"][0]
        self.assertEqual(open_row["mark"], 2.7)
        self.assertEqual(open_row["unrealized_pnl"], 74.0)
        self.assertEqual(open_row["delta"], -0.24)

    def test_compute_live_performance_can_include_paper(self) -> None:
        resolved = [
            {
                "id": "t-paper",
                "voided": False,
                "paper_trade": True,
                "open": {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "contracts": 1, "actual_premium": 2.0, "timestamp": "2026-04-01T09:31:00-04:00", "paper_trade": True},
                "close": {"actual_pnl": 120.0, "timestamp": "2026-04-10T15:45:00-04:00"},
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
        ]
        excluded = compute_live_performance(resolved)
        included = compute_live_performance(resolved, include_paper=True)
        self.assertEqual(excluded["summary"]["closed_trades"], 0)
        self.assertEqual(included["summary"]["closed_trades"], 1)
        self.assertTrue(included["include_paper"])
        self.assertEqual(included["paper_trade_count"], 1)

    @patch("schwab.client.live_position_snapshot")
    @patch("logs.trade_log_io.resolve_log")
    def test_api_performance_live_returns_payload(self, mock_resolve_log, mock_live_position_snapshot) -> None:
        mock_resolve_log.return_value = [
            {
                "id": "t1",
                "voided": False,
                "open": {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "contracts": 1, "actual_premium": 2.0, "timestamp": "2026-04-01T09:35:00-04:00"},
                "close": {"actual_pnl": 125.0, "timestamp": "2026-04-03T15:35:00-04:00"},
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
            {
                "id": "t2",
                "voided": False,
                "open": {"strategy_key": "iron_condor", "strategy": "Iron Condor", "contracts": 1, "actual_premium": 1.8, "timestamp": "2026-04-04T09:35:00-04:00"},
                "close": None,
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
        ]
        mock_live_position_snapshot.return_value = {
            "visible": True,
            "mark": 1.1,
            "trade_log_pnl": 70.0,
            "unrealized_pnl": 65.0,
            "delta": -0.12,
            "theta": -0.05,
            "gamma": 0.01,
            "vega": 0.09,
        }
        client = app.test_client()

        res = client.get("/api/performance/live")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("summary", data)
        self.assertIn("by_strategy", data)
        self.assertIn("monthly", data)
        self.assertIn("open_positions", data)
        self.assertEqual(data["summary"]["closed_trades"], 1)
        self.assertEqual(data["summary"]["open_trades"], 1)
        self.assertEqual(data["open_positions"][0]["mark"], 1.1)

    @patch("schwab.client.live_position_snapshot")
    @patch("logs.trade_log_io.resolve_log")
    def test_api_performance_live_can_include_paper(self, mock_resolve_log, mock_live_position_snapshot) -> None:
        mock_resolve_log.return_value = [
            {
                "id": "paper-1",
                "voided": False,
                "paper_trade": True,
                "open": {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "contracts": 1, "actual_premium": 2.0, "timestamp": "2026-04-01T09:35:00-04:00", "paper_trade": True},
                "close": {"actual_pnl": 125.0, "timestamp": "2026-04-03T15:35:00-04:00"},
                "rolls": [],
                "notes": [],
                "corrections": [],
            },
        ]
        mock_live_position_snapshot.return_value = {"visible": False}
        client = app.test_client()

        excluded = client.get("/api/performance/live").get_json()
        included = client.get("/api/performance/live?include_paper=1").get_json()
        self.assertEqual(excluded["summary"]["closed_trades"], 0)
        self.assertEqual(included["summary"]["closed_trades"], 1)
        self.assertTrue(included["include_paper"])


if __name__ == "__main__":
    unittest.main()
