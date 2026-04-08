import unittest
from unittest.mock import Mock, patch

import schwab.client as client_mod
from schwab.scanner import _is_boundary_hit, _seek_target_delta_strike, build_strike_scan, scan_strikes


class SchwabScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        client_mod._CACHE.clear()

    def tearDown(self) -> None:
        client_mod._CACHE.clear()

    def test_scan_strikes_filters_and_marks_recommended(self) -> None:
        chain = [
            {"strike": 5490, "bid": 1.2, "ask": 1.35, "mid": 1.275, "spread_pct": 0.118, "delta": -0.21, "open_interest": 1240, "volume": 85, "expiry": "2026-05-12", "dte": 35},
            {"strike": 5480, "bid": 0.9, "ask": 1.4, "mid": 1.15, "spread_pct": 0.435, "delta": -0.19, "open_interest": 85, "volume": 10, "expiry": "2026-05-12", "dte": 35},
            {"strike": 5500, "bid": 1.55, "ask": 1.75, "mid": 1.65, "spread_pct": 0.125, "delta": -0.23, "open_interest": 980, "volume": 0, "expiry": "2026-05-12", "dte": 35},
        ]
        rows = scan_strikes(chain, target_delta=-0.20)
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["recommended"])
        self.assertFalse(rows[1]["recommended"])
        self.assertEqual(rows[0]["strike"], 5490)

    def test_scan_strikes_spx_keeps_zero_oi_rows(self) -> None:
        chain = [
            {"strike": 7310, "bid": 1.85, "ask": 3.2, "mid": 2.525, "spread_pct": 0.495, "delta": 0.021, "open_interest": 0, "volume": 0, "expiry": "2026-05-22", "dte": 45},
            {"strike": 7325, "bid": 1.6, "ask": 2.65, "mid": 2.125, "spread_pct": 0.494, "delta": 0.019, "open_interest": 0, "volume": 0, "expiry": "2026-05-22", "dte": 45},
        ]
        rows = scan_strikes(chain, target_delta=0.02, symbol="SPX")
        self.assertEqual(len(rows), 2)
        self.assertTrue(any(row["recommended"] for row in rows))

    def test_scan_strikes_non_index_still_filters_low_oi(self) -> None:
        chain = [
            {"strike": 210, "bid": 1.2, "ask": 1.3, "mid": 1.25, "spread_pct": 0.08, "delta": 0.2, "open_interest": 0, "volume": 10, "expiry": "2026-05-22", "dte": 45},
        ]
        rows = scan_strikes(chain, target_delta=0.2, symbol="SPY")
        self.assertEqual(rows, [])

    @patch("schwab.scanner.get_option_chain")
    def test_build_strike_scan_fallback_when_empty(self, mock_get_chain) -> None:
        mock_get_chain.return_value = [
            {"strike": 5490, "bid": 0.0, "ask": 1.35, "mid": 1.275, "spread_pct": 0.118, "delta": -0.21, "open_interest": 1240, "volume": 85, "expiry": "2026-05-12", "dte": 35},
            {"strike": 5500, "bid": 1.0, "ask": 2.2, "mid": 1.6, "spread_pct": 0.75, "delta": -0.20, "open_interest": 50, "volume": 10, "expiry": "2026-05-12", "dte": 35},
        ]
        scan = build_strike_scan("SPX", "PUT", -0.20, 35)
        self.assertEqual(scan["rows"], [])
        self.assertTrue(scan["scan_fallback"])

    @patch("schwab.scanner.get_option_chain")
    def test_build_strike_scan_passes_center_strike(self, mock_get_chain) -> None:
        mock_get_chain.return_value = []
        build_strike_scan("SPX", "PUT", -0.20, 35, center_strike=5500)
        self.assertEqual(mock_get_chain.call_args_list[0].kwargs["center_strike"], 5500)
        self.assertEqual(mock_get_chain.call_count, 1)
        self.assertEqual(mock_get_chain.call_args_list[0].kwargs["strike_window"], 80)

    @patch("schwab.scanner.get_option_chain")
    def test_build_strike_scan_interpolation_moves_closer_than_bs_center(self, mock_get_chain) -> None:
        mock_get_chain.side_effect = [
            [
                {"strike": 7300, "bid": 3.10, "ask": 3.30, "mid": 3.20, "spread_pct": 0.062, "delta": 0.24, "open_interest": 20, "volume": 5, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7310, "bid": 2.90, "ask": 3.10, "mid": 3.00, "spread_pct": 0.067, "delta": 0.22, "open_interest": 20, "volume": 5, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7320, "bid": 2.70, "ask": 2.90, "mid": 2.80, "spread_pct": 0.071, "delta": 0.19, "open_interest": 20, "volume": 5, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7330, "bid": 2.50, "ask": 2.70, "mid": 2.60, "spread_pct": 0.077, "delta": 0.17, "open_interest": 20, "volume": 5, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7340, "bid": 2.30, "ask": 2.50, "mid": 2.40, "spread_pct": 0.083, "delta": 0.15, "open_interest": 20, "volume": 5, "expiry": "2026-05-15", "dte": 38},
            ]
        ]
        scan = build_strike_scan("SPX", "CALL", 0.20, 45, center_strike=7355)
        self.assertEqual(mock_get_chain.call_count, 1)
        self.assertEqual(mock_get_chain.call_args_list[0].kwargs["strike_window"], 80)
        recommended = next(row for row in scan["rows"] if row["recommended"])
        self.assertEqual(recommended["strike"], 7320)
        self.assertLess(abs(recommended["delta"] - 0.20), abs(0.15 - 0.20))
        self.assertFalse(scan["scan_fallback"])

    @patch("schwab.scanner.get_option_chain")
    def test_build_strike_scan_center_none_matches_legacy_path(self, mock_get_chain) -> None:
        mock_get_chain.return_value = [
            {"strike": 5500, "bid": 1.8, "ask": 1.9, "mid": 1.85, "spread_pct": 0.054, "delta": -0.20, "open_interest": 500, "volume": 14, "expiry": "2026-05-12", "dte": 35},
        ]
        scan = build_strike_scan("SPY", "PUT", -0.20, 35)
        self.assertEqual(mock_get_chain.call_count, 1)
        self.assertNotIn("center_strike", mock_get_chain.call_args.kwargs)
        self.assertEqual(scan["rows"][0]["strike"], 5500)

    def test_seek_target_delta_strike_returns_boundary_when_target_outside_range(self) -> None:
        chain = [
            {"strike": 7200, "delta": 0.30},
            {"strike": 7210, "delta": 0.28},
            {"strike": 7220, "delta": 0.26},
        ]
        self.assertEqual(_seek_target_delta_strike(chain, 0.20), 7220.0)
        self.assertEqual(_seek_target_delta_strike(chain, 0.35), 7200.0)

    def test_seek_target_delta_strike_interpolates_crossing(self) -> None:
        chain = [
            {"strike": 7310, "delta": 0.22},
            {"strike": 7320, "delta": 0.19},
        ]
        sought = _seek_target_delta_strike(chain, 0.20)
        self.assertAlmostEqual(sought, 7316.6666667, places=4)

    def test_is_boundary_hit_detects_edges(self) -> None:
        chain = [
            {"strike": 7200, "delta": 0.30},
            {"strike": 7210, "delta": 0.28},
            {"strike": 7220, "delta": 0.26},
        ]
        self.assertTrue(_is_boundary_hit(chain, 7200.0))
        self.assertTrue(_is_boundary_hit(chain, 7220.0))
        self.assertFalse(_is_boundary_hit(chain, 7210.0))

    @patch("schwab.scanner.get_option_chain")
    def test_build_strike_scan_boundary_hit_on_pass1_triggers_second_request(self, mock_get_chain) -> None:
        mock_get_chain.side_effect = [
            [
                {"strike": 7200, "bid": 4.0, "ask": 4.2, "mid": 4.1, "spread_pct": 0.049, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7210, "bid": 3.8, "ask": 4.0, "mid": 3.9, "spread_pct": 0.051, "delta": 0.17, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
            [
                {"strike": 7180, "bid": 5.0, "ask": 5.2, "mid": 5.1, "spread_pct": 0.039, "delta": 0.21, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7190, "bid": 4.5, "ask": 4.7, "mid": 4.6, "spread_pct": 0.043, "delta": 0.20, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7200, "bid": 4.0, "ask": 4.2, "mid": 4.1, "spread_pct": 0.049, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
        ]
        scan = build_strike_scan("SPX", "CALL", 0.20, 45, center_strike=7355)
        self.assertEqual(mock_get_chain.call_count, 2)
        self.assertEqual(mock_get_chain.call_args_list[0].kwargs["strike_window"], 80)
        self.assertEqual(mock_get_chain.call_args_list[1].kwargs["strike_window"], 140)
        recommended = next(row for row in scan["rows"] if row["recommended"])
        self.assertEqual(recommended["strike"], 7190)

    @patch("schwab.scanner.get_option_chain")
    def test_build_strike_scan_boundary_hit_on_pass2_triggers_third_request(self, mock_get_chain) -> None:
        mock_get_chain.side_effect = [
            [
                {"strike": 7200, "bid": 4.0, "ask": 4.2, "mid": 4.1, "spread_pct": 0.049, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7210, "bid": 3.8, "ask": 4.0, "mid": 3.9, "spread_pct": 0.051, "delta": 0.17, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
            [
                {"strike": 7100, "bid": 10.0, "ask": 10.3, "mid": 10.15, "spread_pct": 0.03, "delta": 0.19, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7110, "bid": 9.4, "ask": 9.7, "mid": 9.55, "spread_pct": 0.031, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
            [
                {"strike": 7080, "bid": 11.2, "ask": 11.5, "mid": 11.35, "spread_pct": 0.026, "delta": 0.22, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7090, "bid": 10.6, "ask": 10.9, "mid": 10.75, "spread_pct": 0.028, "delta": 0.21, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7100, "bid": 10.0, "ask": 10.3, "mid": 10.15, "spread_pct": 0.03, "delta": 0.19, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
        ]
        scan = build_strike_scan("SPX", "CALL", 0.20, 45, center_strike=7355)
        self.assertEqual(mock_get_chain.call_count, 3)
        self.assertEqual(mock_get_chain.call_args_list[2].kwargs["strike_window"], 220)
        recommended = next(row for row in scan["rows"] if row["recommended"])
        self.assertEqual(recommended["strike"], 7090)

    @patch("schwab.scanner.get_option_chain")
    def test_build_strike_scan_stops_after_interior_crossing_on_second_pass(self, mock_get_chain) -> None:
        mock_get_chain.side_effect = [
            [
                {"strike": 7200, "bid": 4.0, "ask": 4.2, "mid": 4.1, "spread_pct": 0.049, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7210, "bid": 3.8, "ask": 4.0, "mid": 3.9, "spread_pct": 0.051, "delta": 0.17, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
            [
                {"strike": 7180, "bid": 5.0, "ask": 5.2, "mid": 5.1, "spread_pct": 0.039, "delta": 0.21, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7190, "bid": 4.5, "ask": 4.7, "mid": 4.6, "spread_pct": 0.043, "delta": 0.20, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7200, "bid": 4.0, "ask": 4.2, "mid": 4.1, "spread_pct": 0.049, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
        ]
        build_strike_scan("SPX", "CALL", 0.20, 45, center_strike=7355)
        self.assertEqual(mock_get_chain.call_count, 2)

    @patch("schwab.scanner.get_option_chain")
    def test_build_strike_scan_accepts_pass3_boundary_without_crashing(self, mock_get_chain) -> None:
        mock_get_chain.side_effect = [
            [
                {"strike": 7200, "bid": 4.0, "ask": 4.2, "mid": 4.1, "spread_pct": 0.049, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7210, "bid": 3.8, "ask": 4.0, "mid": 3.9, "spread_pct": 0.051, "delta": 0.17, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
            [
                {"strike": 7100, "bid": 10.0, "ask": 10.3, "mid": 10.15, "spread_pct": 0.03, "delta": 0.19, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7110, "bid": 9.4, "ask": 9.7, "mid": 9.55, "spread_pct": 0.031, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
            [
                {"strike": 7000, "bid": 20.0, "ask": 20.5, "mid": 20.25, "spread_pct": 0.025, "delta": 0.19, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
                {"strike": 7010, "bid": 19.2, "ask": 19.7, "mid": 19.45, "spread_pct": 0.026, "delta": 0.18, "open_interest": 10, "volume": 3, "expiry": "2026-05-15", "dte": 38},
            ],
        ]
        scan = build_strike_scan("SPX", "CALL", 0.20, 45, center_strike=7355)
        self.assertFalse(scan["scan_fallback"])
        self.assertEqual(mock_get_chain.call_count, 3)
        recommended = next(row for row in scan["rows"] if row["recommended"])
        self.assertEqual(recommended["strike"], 7000)

    @patch("schwab.client.ensure_access_token", return_value="token")
    @patch("schwab.client.is_configured", return_value=True)
    @patch("schwab.client.requests.get")
    def test_get_option_chain_parses_and_caches_best_expiry(self, mock_get, _mock_configured, _mock_token) -> None:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {
            "putExpDateMap": {
                "2026-05-12:35": {
                    "5490.0": [{
                        "bid": 1.2, "ask": 1.35, "delta": -0.21, "openInterest": 1240, "totalVolume": 85, "mark": 1.275,
                    }],
                    "5500.0": [{
                        "bid": 1.55, "ask": 1.75, "delta": -0.23, "openInterest": 980, "totalVolume": 0, "mark": 1.65,
                    }],
                },
                "2026-05-14:37": {
                    "5490.0": [{
                        "bid": 1.1, "ask": 1.4, "delta": -0.2, "openInterest": 120, "totalVolume": 20, "mark": 1.25,
                    }],
                },
            }
        }
        mock_get.return_value = response

        first = client_mod.get_option_chain("SPX", "PUT", 35)
        second = client_mod.get_option_chain("SPX", "PUT", 35)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0]["expiry"], "2026-05-12")
        self.assertEqual(first, second)
        self.assertEqual(mock_get.call_args.kwargs["params"]["symbol"], "$SPX")

    @patch("schwab.client.ensure_access_token", return_value="token")
    @patch("schwab.client.is_configured", return_value=True)
    @patch("schwab.client.requests.get")
    def test_get_option_chain_centers_window_and_cache_key(self, mock_get, _mock_configured, _mock_token) -> None:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {
            "putExpDateMap": {
                "2026-05-12:35": {
                    "5450.0": [{"bid": 1.2, "ask": 1.3, "delta": -0.15, "openInterest": 300, "totalVolume": 10, "mark": 1.25}],
                    "5480.0": [{"bid": 1.5, "ask": 1.6, "delta": -0.18, "openInterest": 400, "totalVolume": 12, "mark": 1.55}],
                    "5500.0": [{"bid": 1.8, "ask": 1.9, "delta": -0.20, "openInterest": 500, "totalVolume": 14, "mark": 1.85}],
                    "5520.0": [{"bid": 2.1, "ask": 2.2, "delta": -0.22, "openInterest": 450, "totalVolume": 16, "mark": 2.15}],
                    "5550.0": [{"bid": 2.4, "ask": 2.5, "delta": -0.25, "openInterest": 350, "totalVolume": 18, "mark": 2.45}],
                },
            }
        }
        mock_get.return_value = response

        centered = client_mod.get_option_chain("SPX", "PUT", 35, center_strike=5500, strike_window=3)
        shifted = client_mod.get_option_chain("SPX", "PUT", 35, center_strike=5450, strike_window=3)
        wider = client_mod.get_option_chain("SPX", "PUT", 35, center_strike=5500, strike_window=5)
        self.assertEqual([row["strike"] for row in centered], [5480.0, 5500.0, 5520.0])
        self.assertEqual([row["strike"] for row in shifted], [5450.0, 5480.0, 5500.0])
        self.assertEqual([row["strike"] for row in wider], [5450.0, 5480.0, 5500.0, 5520.0, 5550.0])
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["strikeCount"], 300)
        self.assertEqual(mock_get.call_args_list[2].kwargs["params"]["strikeCount"], 300)


if __name__ == "__main__":
    unittest.main()
