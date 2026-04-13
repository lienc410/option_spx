from __future__ import annotations

import unittest
from unittest.mock import patch

from signals.iv_rank import IVSignal
from signals.trend import TrendSignal
from signals.vix_regime import Regime, Trend
from strategy.selector import StrategyName, select_es_short_put
from tests.test_strategy_unification import make_iv, make_trend, make_vix
from web.server import app


class Spec061SelectorTests(unittest.TestCase):
    def test_ac1_bullish_trend_builds_es_short_put_candidate(self) -> None:
        rec = select_es_short_put(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=45.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.ES_SHORT_PUT)
        self.assertEqual(rec.strategy_key, "es_short_put")
        self.assertEqual(rec.underlying, "/ES")
        self.assertEqual(len(rec.legs), 1)
        self.assertEqual(rec.legs[0].option, "PUT")
        self.assertEqual(rec.legs[0].dte, 45)
        self.assertEqual(rec.legs[0].delta, 0.20)
        self.assertIn("3× credit", rec.roll_rule)

    def test_ac3_non_bullish_trend_rejects_new_es_short_put(self) -> None:
        rec = select_es_short_put(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=45.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.NEUTRAL),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertEqual(rec.strategy_key, "reduce_wait")
        self.assertEqual(rec.canonical_strategy, "ES Short Put")


class Spec061ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    @patch("web.server._is_market_hours", return_value=False)
    @patch("web.server._live_es_bp_check", return_value={
        "ok": True,
        "reason": None,
        "nlv": 500000.0,
        "current_bp": 60000.0,
        "projected_bp": 80529.0,
        "bp_limit": 100000.0,
        "bp_check_passed": True,
        "es_bp_per_contract": 20529.0,
    })
    @patch("schwab.scanner.build_strike_scan", return_value={
        "rows": [
            {
                "strike": 5200,
                "expiry": "2026-05-27",
                "bid": 24.0,
                "ask": 25.0,
                "mid": 24.5,
                "spread_pct": 0.041,
                "delta": -0.21,
                "open_interest": 420,
                "volume": 27,
                "recommended": True,
            }
        ],
        "scan_fallback": False,
    })
    @patch("strategy.selector.get_es_recommendation")
    def test_ac2_ac4_ac5_es_open_draft_returns_tradeable_candidate(
        self,
        mock_get_es_recommendation,
        _mock_scan,
        _mock_bp,
        _mock_hours,
    ) -> None:
        mock_get_es_recommendation.return_value = select_es_short_put(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=45.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )

        res = self.client.get("/api/es/position/open-draft")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["strategy_key"], "es_short_put")
        self.assertEqual(data["underlying"], "/ES")
        self.assertEqual(data["contracts"], 1)
        self.assertTrue(data["trend_filter_passed"])
        self.assertTrue(data["bp_check_passed"])
        self.assertEqual(data["bp_preview"]["bp_target_pct"], 20.0)
        self.assertEqual(data["bp_gate"]["projected_bp"], 80529.0)
        self.assertEqual(data["short_strike"], 5200)
        self.assertIn("3× credit", data["roll_rule"])

    @patch("web.server._is_market_hours", return_value=False)
    @patch("web.server._live_es_bp_check", return_value={
        "ok": False,
        "reason": "Projected /ES BP would exceed NLV 20% cap",
    })
    @patch("strategy.selector.get_es_recommendation")
    def test_ac4_bp_cap_breach_rejects_candidate(self, mock_get_es_recommendation, _mock_bp, _mock_hours) -> None:
        mock_get_es_recommendation.return_value = select_es_short_put(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=45.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        res = self.client.get("/api/es/position/open-draft")
        self.assertEqual(res.status_code, 400)
        self.assertIn("NLV 20% cap", res.get_json()["error"])

    @patch("web.server._is_market_hours", return_value=False)
    @patch("web.server._live_es_bp_check", return_value={
        "ok": False,
        "reason": "Live Schwab balances/positions unavailable",
    })
    @patch("strategy.selector.get_es_recommendation")
    def test_ac7_missing_live_bp_or_nlv_rejects_candidate(self, mock_get_es_recommendation, _mock_bp, _mock_hours) -> None:
        mock_get_es_recommendation.return_value = select_es_short_put(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=45.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        res = self.client.get("/api/es/position/open-draft")
        self.assertEqual(res.status_code, 400)
        self.assertIn("unavailable", res.get_json()["error"])

    @patch("web.server._is_market_hours", return_value=False)
    @patch("web.server._live_es_bp_check", return_value={
        "ok": False,
        "reason": "Existing /ES short-put slot detected",
    })
    @patch("strategy.selector.get_es_recommendation")
    def test_ac8_existing_es_slot_rejects_second_entry(self, mock_get_es_recommendation, _mock_bp, _mock_hours) -> None:
        mock_get_es_recommendation.return_value = select_es_short_put(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=45.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        res = self.client.get("/api/es/position/open-draft")
        self.assertEqual(res.status_code, 400)
        self.assertIn("slot", res.get_json()["error"])

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_es_recommendation")
    def test_ac7_trend_filter_failure_rejects_candidate(self, mock_get_es_recommendation, _mock_hours) -> None:
        mock_get_es_recommendation.return_value = select_es_short_put(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=45.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BEARISH),
        )
        res = self.client.get("/api/es/position/open-draft")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Trend filter blocked", res.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
