import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.state as state_mod
from web.server import app


class Spec085Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.client = app.test_client()
        self.orig_state_file = state_mod.STATE_FILE
        self.orig_ledger_env = os.environ.get("Q041_PAPER_LEDGER_FILE")
        self.orig_config_env = os.environ.get("Q041_PAPER_CONFIG_FILE")
        self.orig_attribution_env = os.environ.get("Q041_PORTFOLIO_ATTRIBUTION_FILE")
        self.state_file = Path(self.tmpdir.name) / "current_position.json"
        self.ledger_file = Path(self.tmpdir.name) / "q041_paper_trades.jsonl"
        self.config_file = Path(self.tmpdir.name) / "q041_paper_trade_config.json"
        self.attribution_file = Path(self.tmpdir.name) / "q041_portfolio_attribution_latest.json"
        state_mod.STATE_FILE = str(self.state_file)
        os.environ["Q041_PAPER_LEDGER_FILE"] = str(self.ledger_file)
        os.environ["Q041_PAPER_CONFIG_FILE"] = str(self.config_file)
        os.environ["Q041_PORTFOLIO_ATTRIBUTION_FILE"] = str(self.attribution_file)

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self.orig_state_file
        self._restore_env("Q041_PAPER_LEDGER_FILE", self.orig_ledger_env)
        self._restore_env("Q041_PAPER_CONFIG_FILE", self.orig_config_env)
        self._restore_env("Q041_PORTFOLIO_ATTRIBUTION_FILE", self.orig_attribution_env)

    def _restore_env(self, key: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def _write_q041_row(self, row: dict) -> None:
        self.ledger_file.write_text(json.dumps(row) + "\n")

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_ac1_recommendation_shape_does_not_include_spec085_surfaces(self, mock_get_recommendation, _mock_hours) -> None:
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy
        from tests.test_strategy_unification import make_iv, make_trend, make_vix

        mock_get_recommendation.return_value = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )

        res = self.client.get("/api/recommendation")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["strategy_key"], "bull_put_spread")
        self.assertNotIn("sleeve_candidates", data)
        self.assertNotIn("portfolio_summary", data)
        self.assertNotIn("portfolio_attribution", data)

    def test_ac2_and_ac3_sleeve_candidates_are_read_only_and_tier3_review_only(self) -> None:
        res = self.client.get("/api/sleeve-candidates")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        candidates = data["sleeve_candidates"]
        review_only = data["review_only"]
        self.assertEqual({c["underlying"] for c in candidates}, {"SPX", "GOOGL", "AMZN"})
        self.assertNotIn("COST", {c["underlying"] for c in candidates})
        self.assertNotIn("JPM", {c["underlying"] for c in candidates})
        self.assertEqual({c["candidate_status"] for c in candidates}, {"watching"})
        self.assertEqual({c["candidate_status"] for c in review_only}, {"review_only"})
        self.assertFalse(self.ledger_file.exists())

    def test_ac4_ac5_and_ac11_portfolio_summary_fail_soft_when_q041_missing(self) -> None:
        state_mod.write_state(
            "Bull Put Spread",
            "SPX",
            strategy_key="bull_put_spread",
            short_strike=6900,
            long_strike=6830,
            actual_premium=3.0,
            contracts=1,
        )
        res = self.client.get("/api/portfolio/summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["rails"]["spx_live"]["status"], "open")
        self.assertEqual(data["rails"]["q041_paper"]["status"], "unavailable")
        self.assertIn("SPX live rail + Q041 paper rail", data["semantics"])
        self.assertEqual(data["bp_usage_by_bucket"]["q041_total_bp_pct"], None)
        self.assertIsNotNone(data["bp_usage_by_bucket"]["spx_live_bp_pct"])

    def test_ac4_ac5_portfolio_summary_reads_q041_budget_when_available(self) -> None:
        self.config_file.write_text(json.dumps({"account_total_bp": 500000}))
        self._write_q041_row({
            "record_id": "20260516-SPX-01",
            "status": "open",
            "tier": "tier1",
            "strategy_type": "csp",
            "symbol": "SPX",
            "entry_date": "2026-05-16",
            "expiry": "2026-05-10",
            "bp_reserved": 95000,
        })
        res = self.client.get("/api/portfolio/summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["rails"]["q041_paper"]["status"], "available")
        self.assertEqual(data["bp_usage_by_bucket"]["q041_tier1_bp_pct"], 19.0)
        self.assertEqual(data["bp_usage_by_bucket"]["q041_total_bp_pct"], 19.0)
        self.assertEqual(data["next_review_item"]["type"], "csp")

    def test_ac6_attribution_missing_source_returns_pending_quant_input(self) -> None:
        res = self.client.get("/api/portfolio/attribution")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "pending_quant_input")
        self.assertEqual(data["idle_day_capture"]["status"], "pending_quant_input")
        self.assertEqual(data["delta_avg_bp"]["status"], "pending_quant_input")
        self.assertEqual(data["worst_day_overlap"]["status"], "pending_quant_input")
        self.assertFalse(self.attribution_file.exists())

    def test_ac6_attribution_uses_quant_provided_artifact_when_present(self) -> None:
        self.attribution_file.write_text(json.dumps({
            "idle_day_capture": {"value": 3, "unit": "days"},
            "delta_avg_bp": {"value": 1.2, "unit": "pct_points"},
            "bp_fill_contribution": {"value": 2.1, "unit": "pct_points"},
            "worst_day_overlap": {"value": 0.4, "unit": "pct_points"},
            "notes": "fixture",
        }))
        res = self.client.get("/api/portfolio/attribution")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "available")
        self.assertEqual(data["idle_day_capture"]["value"], 3)
        self.assertEqual(data["notes"], "fixture")


if __name__ == "__main__":
    unittest.main()
