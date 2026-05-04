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
        self.assertEqual(snapshot["pricing_source"], "spread_quote")
        self.assertEqual(snapshot["structure"], "2-leg spread")

    def test_live_position_snapshot_builds_condor_snapshot_from_chain_quotes(self) -> None:
        positions_payload = {
            "configured": True,
            "authenticated": True,
            "stale": False,
            "positions": [],
        }
        state = {
            "strategy_key": "iron_condor",
            "underlying": "SPX",
            "expiry": "2026-05-29",
            "short_put_strike": 7000,
            "long_put_strike": 6800,
            "short_call_strike": 7400,
            "long_call_strike": 7600,
            "contracts": 1,
            "actual_premium": 18.5,
        }
        put_rows = [
            {"strike": 7000.0, "bid": 52.0, "ask": 53.0, "mid": 52.5, "delta": -0.15, "gamma": 0.006, "theta": -0.03, "vega": 0.08},
            {"strike": 6800.0, "bid": 21.0, "ask": 22.0, "mid": 21.5, "delta": -0.07, "gamma": 0.003, "theta": -0.01, "vega": 0.04},
        ]
        call_rows = [
            {"strike": 7400.0, "bid": 39.0, "ask": 40.0, "mid": 39.5, "delta": 0.14, "gamma": 0.005, "theta": -0.025, "vega": 0.07},
            {"strike": 7600.0, "bid": 16.0, "ask": 17.0, "mid": 16.5, "delta": 0.06, "gamma": 0.002, "theta": -0.008, "vega": 0.03},
        ]
        def _fake_chain(_symbol, option_type, *_args, **_kwargs):
            return put_rows if option_type == "PUT" else call_rows

        with patch("schwab.client.get_account_positions", return_value=positions_payload), \
             patch("schwab.client._get_option_chain_exact_expiry", side_effect=_fake_chain):
            snapshot = live_position_snapshot(state)

        self.assertTrue(snapshot["visible"])
        self.assertEqual(snapshot["structure"], "4-leg condor")
        self.assertEqual(snapshot["pricing_source"], "spread_quote")
        self.assertEqual(snapshot["mark"], 54.0)
        self.assertEqual(snapshot["bid"], 52.0)
        self.assertEqual(snapshot["ask"], 56.0)
        self.assertAlmostEqual(snapshot["delta"], 0.0)
        self.assertAlmostEqual(snapshot["gamma"], -0.006)
        self.assertAlmostEqual(snapshot["theta"], 0.037)
        self.assertAlmostEqual(snapshot["vega"], -0.08)
        self.assertEqual(snapshot["trade_log_pnl"], -3550.0)

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
