import json
import os
import tempfile
import unittest
from unittest.mock import patch

import strategy.state as state_mod
from web.server import app


class StateAndApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.orig_state_file = state_mod.STATE_FILE
        state_mod.STATE_FILE = os.path.join(self.tmpdir.name, "current_position.json")
        self.client = app.test_client()

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self.orig_state_file

    def test_write_state_derives_strategy_key(self) -> None:
        state_mod.write_state("Bull Put Spread", "SPX")
        state = state_mod.read_state()
        self.assertIsNotNone(state)
        self.assertEqual(state["strategy_key"], "bull_put_spread")

    def test_read_state_backfills_legacy_record_without_strategy_key(self) -> None:
        with open(state_mod.STATE_FILE, "w") as fh:
            json.dump(
                {
                    "strategy": "Iron Condor",
                    "underlying": "SPX",
                    "opened_at": "2026-03-27",
                    "status": "open",
                    "roll_count": 0,
                    "rolled_at": None,
                    "notes": [],
                    "closed_at": None,
                    "close_note": None,
                },
                fh,
            )
        state = state_mod.read_state()
        self.assertIsNotNone(state)
        self.assertEqual(state["strategy_key"], "iron_condor")

    def test_api_position_returns_strategy_meta(self) -> None:
        state_mod.write_state("Bull Put Spread", "SPX")
        res = self.client.get("/api/position")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["open"])
        self.assertEqual(data["strategy_key"], "bull_put_spread")
        self.assertEqual(data["strategy_meta"]["name"], "Bull Put Spread")
        self.assertEqual(data["strategy_meta"]["emoji"], "💰")

    def test_api_strategy_catalog_contains_matrix_and_manual_options(self) -> None:
        res = self.client.get("/api/strategy-catalog")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("strategies", data)
        self.assertIn("matrix", data)
        self.assertEqual(data["matrix"]["NORMAL"]["HIGH"]["BULLISH"], "bull_put_spread")
        manual_keys = {item["key"] for item in data["manual_entry_options"]}
        self.assertNotIn("reduce_wait", manual_keys)

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_api_recommendation_preserves_strategy_key(self, mock_get_recommendation, _mock_hours) -> None:
        from tests.test_strategy_unification import make_iv, make_trend, make_vix
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy

        mock_get_recommendation.return_value = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        res = self.client.get("/api/recommendation")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["strategy_key"], "bull_put_spread")
        self.assertEqual(data["strategy"], "Bull Put Spread")


if __name__ == "__main__":
    unittest.main()
