import unittest
from unittest.mock import Mock, patch

import schwab.client as client_mod
from signals.intraday import (
    SpikeLevel,
    StopLevel,
    get_spx_stop_from_quote,
    get_vix_spike_from_quote,
)


class SchwabQuoteTests(unittest.TestCase):
    def setUp(self) -> None:
        client_mod._CACHE.clear()

    def tearDown(self) -> None:
        client_mod._CACHE.clear()

    @patch("schwab.client.ensure_access_token", return_value="token")
    @patch("schwab.client.is_configured", return_value=True)
    @patch("schwab.client.requests.get")
    def test_get_vix_quote_normalizes_payload(self, mock_get, _mock_configured, _mock_token) -> None:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {
            "$VIX": {
                "symbol": "$VIX",
                "realtime": True,
                "quote": {
                    "lastPrice": 25.78,
                    "openPrice": 25.09,
                    "highPrice": 28.00,
                    "lowPrice": 24.34,
                    "closePrice": 24.17,
                    "securityStatus": "Closed",
                    "tradeTime": 1775592901211,
                },
            }
        }
        mock_get.return_value = response

        quote = client_mod.get_vix_quote()
        self.assertEqual(quote["symbol"], "$VIX")
        self.assertEqual(quote["last"], 25.78)
        self.assertEqual(quote["open"], 25.09)
        self.assertEqual(quote["security_status"], "Closed")
        self.assertTrue(quote["realtime"])
        self.assertIn("2026-04-07T16:15:01", quote["quote_time"])

    @patch("schwab.client.ensure_access_token", return_value="token")
    @patch("schwab.client.is_configured", return_value=True)
    @patch("schwab.client.requests.get")
    def test_get_spx_quote_normalizes_payload(self, mock_get, _mock_configured, _mock_token) -> None:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {
            "$SPX": {
                "symbol": "$SPX",
                "realtime": True,
                "quote": {
                    "lastPrice": 5205.25,
                    "openPrice": 5255.00,
                    "highPrice": 5260.00,
                    "lowPrice": 5198.50,
                    "closePrice": 5268.75,
                    "securityStatus": "Open",
                    "tradeTime": 1775575200000,
                },
            }
        }
        mock_get.return_value = response

        quote = client_mod.get_spx_quote()
        self.assertEqual(quote["symbol"], "$SPX")
        self.assertEqual(quote["last"], 5205.25)
        self.assertEqual(quote["open"], 5255.00)
        self.assertEqual(quote["security_status"], "Open")
        self.assertTrue(quote["realtime"])

    def test_get_vix_spike_from_quote_uses_open_and_last(self) -> None:
        spike = get_vix_spike_from_quote(
            {
                "symbol": "$VIX",
                "open": 25.00,
                "last": 27.50,
                "quote_time": "2026-04-07T13:55:00-04:00",
                "realtime": True,
            }
        )
        self.assertEqual(spike.timestamp, "2026-04-07 13:55")
        self.assertEqual(spike.vix_open, 25.00)
        self.assertEqual(spike.vix_current, 27.50)
        self.assertAlmostEqual(spike.spike_pct, 0.10)
        self.assertEqual(spike.level, SpikeLevel.WARNING)
        self.assertTrue(spike.realtime)

    def test_get_spx_stop_from_quote_uses_open_and_last(self) -> None:
        stop = get_spx_stop_from_quote(
            {
                "symbol": "$SPX",
                "open": 5300.0,
                "last": 5194.0,
                "quote_time": "2026-04-07T13:55:00-04:00",
                "realtime": True,
            }
        )
        self.assertEqual(stop.timestamp, "2026-04-07 13:55")
        self.assertEqual(stop.spx_open, 5300.0)
        self.assertEqual(stop.spx_current, 5194.0)
        self.assertAlmostEqual(stop.drop_pct, -0.02)
        self.assertEqual(stop.level, StopLevel.TRIGGER)
        self.assertTrue(stop.realtime)


if __name__ == "__main__":
    unittest.main()
