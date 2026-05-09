import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backtest.pricer import find_strike_for_delta
import strategy.state as state_mod
from web.server import app


def _quote(last: float) -> dict:
    return {"last": last, "close": last, "quote_time": "2026-05-08T10:00:00-04:00", "realtime": True}


class Spec088Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.client = app.test_client()
        self.orig_state_file = state_mod.STATE_FILE
        self.state_file = Path(self.tmpdir.name) / "current_position.json"
        state_mod.STATE_FILE = str(self.state_file)

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self.orig_state_file

    def _write_es_state(self, *, strike: float | None = None, dte: int = 35) -> None:
        if strike is None:
            strike = find_strike_for_delta(5400.0, 45, 0.19, 0.20, is_call=False)
        state_mod.write_state(
            "/ES Short Put",
            "/ES",
            strategy_key="es_short_put",
            short_strike=strike,
            dte_at_entry=dte,
            contracts=1,
            actual_premium=21.0,
            entry_spx=5400.0,
            entry_vix=19.0,
        )

    @patch("schwab.client.get_spx_quote", return_value=_quote(5400.0))
    @patch("schwab.client.get_vix_quote", return_value=_quote(25.0))
    def test_ac1_returns_stressed_span_payload_for_live_es_position(self, _mock_vix, _mock_spx) -> None:
        self._write_es_state()

        res = self.client.get("/api/es/stressed-span")

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["has_es_live_position"])
        self.assertEqual(data["entry_static_span"], 20529.0)
        self.assertGreater(data["current_estimated_stressed_span"], 20529.0)
        self.assertGreater(data["stress_ratio"], 1.0)
        self.assertEqual(data["model"], "Q012 Phase A Model A2 existing-position SPAN estimate")

    @patch("schwab.client.get_spx_quote", return_value=_quote(5400.0))
    def test_ac2_vix_band_and_status_mapping(self, _mock_spx) -> None:
        self._write_es_state()
        cases = [
            (19.0, "normal", "ok"),
            (25.0, "stress", "elevated"),
            (45.0, "crisis", "high_stress"),
        ]
        for vix, band, status in cases:
            with self.subTest(vix=vix), patch("schwab.client.get_vix_quote", return_value=_quote(vix)):
                res = self.client.get("/api/es/stressed-span")
                data = res.get_json()
                self.assertEqual(data["stress_band"], band)
                self.assertEqual(data["status"], status)

    def test_ac3_no_es_position_fails_soft_unavailable(self) -> None:
        state_mod.write_state("Bull Put Spread", "SPX", strategy_key="bull_put_spread")

        res = self.client.get("/api/es/stressed-span")

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["has_es_live_position"])
        self.assertEqual(data["status"], "unavailable")
        self.assertEqual(data["stress_band"], "unavailable")

    @patch("schwab.client.get_vix_quote", side_effect=RuntimeError("schwab down"))
    def test_ac4_missing_market_input_fails_soft_insufficient_data(self, _mock_vix) -> None:
        self._write_es_state()

        res = self.client.get("/api/es/stressed-span")

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["has_es_live_position"])
        self.assertEqual(data["status"], "insufficient_data")
        self.assertIn("current_vix", data["missing_inputs"])

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_ac5_recommendation_shape_unchanged(self, mock_get_recommendation, _mock_hours) -> None:
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
        self.assertNotIn("es_stressed_span", json.dumps(data))
        self.assertNotIn("stress_ratio", data)

    def test_ac8_es_page_contains_read_only_disclaimer(self) -> None:
        res = self.client.get("/es")

        self.assertEqual(res.status_code, 200)
        text = res.get_data(as_text=True)
        self.assertIn("Stressed SPAN Visibility", text)
        self.assertIn("not a trade recommendation", text)

    @patch("schwab.client.get_spx_quote", return_value=_quote(5400.0))
    @patch("schwab.client.get_vix_quote", return_value=_quote(25.0))
    def test_zero_contracts_floors_to_one(self, _mock_vix, _mock_spx) -> None:
        """Defensive: contracts=0 in state should floor to 1, no divide-by-zero."""
        state_mod.write_state(
            "/ES Short Put", "/ES",
            strategy_key="es_short_put",
            short_strike=5300.0,
            dte_at_entry=35,
            contracts=0,
            actual_premium=21.0,
            entry_spx=5400.0,
            entry_vix=19.0,
        )
        res = self.client.get("/api/es/stressed-span")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(data["entry_static_span"], 20529.0)
        self.assertGreater(data["current_estimated_stressed_span"], 0)

    @patch("schwab.client.get_spx_quote", return_value=_quote(5400.0))
    @patch("schwab.client.get_vix_quote", return_value=_quote(25.0))
    def test_expired_expiry_does_not_crash(self, _mock_vix, _mock_spx) -> None:
        """Defensive: past expiry yields dte=0 floored to 1 in model; no crash."""
        state_mod.write_state(
            "/ES Short Put", "/ES",
            strategy_key="es_short_put",
            short_strike=5300.0,
            expiry="2020-01-01",
            contracts=1,
            actual_premium=21.0,
            entry_spx=5400.0,
            entry_vix=19.0,
        )
        res = self.client.get("/api/es/stressed-span")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertIn(data["status"], {"ok", "elevated", "high_stress", "insufficient_data"})


if __name__ == "__main__":
    unittest.main()
