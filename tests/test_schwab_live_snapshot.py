import unittest
from unittest.mock import patch

from schwab.client import _find_matching_position, live_position_snapshot


class SchwabLiveSnapshotTests(unittest.TestCase):
    def test_find_matching_position_returns_none_when_state_present_but_no_leg_matches(self) -> None:
        positions = [
            {"symbol": "NVDA", "mark": 54150.70, "unrealized_pnl": -819.95},
            {"symbol": "SPXW  260529P06900000", "mark": 76.50},
        ]
        state = {"expiry": "2026-05-29", "short_strike": 7100}
        self.assertIsNone(_find_matching_position(positions, state))

    def test_live_position_snapshot_hides_panel_on_state_position_mismatch(self) -> None:
        positions_payload = {
            "configured": True,
            "authenticated": True,
            "stale": False,
            "positions": [
                {"symbol": "NVDA", "mark": 54150.70, "unrealized_pnl": -819.95},
                {"symbol": "SPXW  260529P06900000", "mark": 76.50, "unrealized_pnl": 1218.0},
            ],
        }
        state = {
            "expiry": "2026-05-29",
            "short_strike": 7100,
            "contracts": 2,
            "actual_premium": 31.9,
        }
        with patch("schwab.client.get_account_positions", return_value=positions_payload), \
             patch("schwab.client._get_option_chain_exact_expiry", return_value=[]):
            snapshot = live_position_snapshot(state)

        self.assertFalse(snapshot["visible"])
        self.assertTrue(snapshot["configured"])
        self.assertTrue(snapshot["authenticated"])
        self.assertIn("positions", snapshot)

    def test_live_position_snapshot_builds_spread_snapshot_from_chain_quotes(self) -> None:
        positions_payload = {
            "configured": True,
            "authenticated": True,
            "stale": False,
            "positions": [],
        }
        state = {
            "strategy_key": "bull_put_spread",
            "underlying": "SPX",
            "expiry": "2026-05-29",
            "short_strike": 7100,
            "long_strike": 6900,
            "contracts": 2,
            "actual_premium": 31.9,
        }
        chain_rows = [
            {
                "strike": 7100.0,
                "bid": 149.0,
                "ask": 151.0,
                "mid": 150.0,
                "delta": -0.31,
                "gamma": 0.012,
                "theta": -0.08,
                "vega": 0.21,
            },
            {
                "strike": 6900.0,
                "bid": 78.0,
                "ask": 80.0,
                "mid": 79.0,
                "delta": -0.16,
                "gamma": 0.007,
                "theta": -0.04,
                "vega": 0.11,
            },
        ]
        with patch("schwab.client.get_account_positions", return_value=positions_payload), \
             patch("schwab.client._get_option_chain_exact_expiry", return_value=chain_rows):
            snapshot = live_position_snapshot(state)

        self.assertTrue(snapshot["visible"])
        self.assertEqual(snapshot["mark"], 71.0)
        self.assertEqual(snapshot["bid"], 69.0)
        self.assertEqual(snapshot["ask"], 73.0)
        self.assertAlmostEqual(snapshot["delta"], 0.15)
        self.assertAlmostEqual(snapshot["gamma"], -0.005)
        self.assertAlmostEqual(snapshot["theta"], 0.04)
        self.assertAlmostEqual(snapshot["vega"], -0.1)
        self.assertEqual(snapshot["trade_log_pnl"], -7820.0)

    def test_live_position_snapshot_hides_panel_when_match_has_no_quote_fields(self) -> None:
        positions_payload = {
            "configured": True,
            "authenticated": True,
            "stale": False,
            "positions": [
                {
                    "symbol": "SPXW  260529P07100000",
                    "mark": -15340.0,
                    "bid": None,
                    "ask": None,
                    "delta": None,
                    "gamma": None,
                    "theta": None,
                    "vega": None,
                    "unrealized_pnl": -2528.0,
                },
            ],
        }
        state = {
            "expiry": "2026-05-29",
            "short_strike": 7100,
            "contracts": 2,
            "actual_premium": 31.9,
        }
        with patch("schwab.client.get_account_positions", return_value=positions_payload), \
             patch("schwab.client._get_option_chain_exact_expiry", return_value=[]):
            snapshot = live_position_snapshot(state)

        self.assertFalse(snapshot["visible"])

    def test_live_position_snapshot_still_returns_match_when_short_leg_exists(self) -> None:
        positions_payload = {
            "configured": True,
            "authenticated": True,
            "stale": False,
            "positions": [
                {
                    "symbol": "SPXW  260529P07100000",
                    "mark": 149.00,
                    "bid": 148.0,
                    "ask": 150.0,
                    "delta": -0.31,
                    "gamma": 0.01,
                    "theta": -0.05,
                    "vega": 0.12,
                    "unrealized_pnl": -2088.0,
                },
                {"symbol": "NVDA", "mark": 54150.70, "unrealized_pnl": -819.95},
            ],
        }
        state = {
            "expiry": "2026-05-29",
            "short_strike": 7100,
            "contracts": 2,
            "actual_premium": 31.9,
        }
        with patch("schwab.client.get_account_positions", return_value=positions_payload), \
             patch("schwab.client._get_option_chain_exact_expiry", return_value=[]):
            snapshot = live_position_snapshot(state)

        self.assertTrue(snapshot["visible"])
        self.assertEqual(snapshot["symbol"], "SPXW  260529P07100000")
        self.assertEqual(snapshot["mark"], 149.00)


if __name__ == "__main__":
    unittest.main()
