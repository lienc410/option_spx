"""SPEC-115 Phase A — AC-1: q041_selector.select_t2_csp chain reading + filter."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import strategy.q041_selector as sel
from strategy.q041_selector import select_t2_csp


def _make_chain(symbol: str, rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestSelectT2CSP(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_chain(self, symbol: str, date_str: str, rows: list[dict]) -> None:
        day_dir = self.tmp / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        fname = symbol.replace("/", "_") + ".parquet"
        _make_chain(symbol, rows).to_parquet(day_dir / fname, index=False)

    def test_ac1_returns_best_fit_googl_candidate(self):
        # GOOGL: δ0.20 target, DTE 21 target
        rows = [
            {"option_type": "PUT", "delta": -0.20, "dte": 21, "strike": 366.0, "mid": 4.50},
            {"option_type": "PUT", "delta": -0.30, "dte": 21, "strike": 380.0, "mid": 7.00},  # delta off
            {"option_type": "PUT", "delta": -0.20, "dte": 40, "strike": 360.0, "mid": 6.00},  # dte off
            {"option_type": "CALL", "delta": 0.20, "dte": 21, "strike": 400.0, "mid": 5.00},  # call
        ]
        self._write_chain("GOOGL", "2026-06-05", rows)
        with patch.object(sel, "CHAIN_ROOT", self.tmp):
            cand = select_t2_csp("q041_t2_googl_csp", "2026-06-05")
        self.assertIsNotNone(cand)
        self.assertEqual(cand["strategy_key"], "q041_t2_googl_csp")
        self.assertEqual(cand["underlying"], "GOOGL")
        self.assertEqual(cand["short_strike"], 366.0)
        self.assertAlmostEqual(cand["delta"], 0.20, places=2)
        self.assertEqual(cand["dte"], 21)
        # cash_need = 366 * 100 * 1
        self.assertAlmostEqual(cand["cash_need_usd"], 36_600.0)
        self.assertTrue(cand["paper_trade"])

    def test_ac1_returns_amzn_at_delta_25(self):
        rows = [
            {"option_type": "PUT", "delta": -0.25, "dte": 21, "strike": 252.0, "mid": 5.00},
        ]
        self._write_chain("AMZN", "2026-06-05", rows)
        with patch.object(sel, "CHAIN_ROOT", self.tmp):
            cand = select_t2_csp("q041_t2_amzn_csp", "2026-06-05")
        self.assertIsNotNone(cand)
        self.assertEqual(cand["underlying"], "AMZN")
        self.assertAlmostEqual(cand["cash_need_usd"], 25_200.0)

    def test_missing_chain_returns_none(self):
        with patch.object(sel, "CHAIN_ROOT", self.tmp):
            cand = select_t2_csp("q041_t2_googl_csp", "2099-01-01")
        self.assertIsNone(cand)

    def test_no_candidate_in_band_returns_none(self):
        # All deltas far from 0.20 target
        rows = [
            {"option_type": "PUT", "delta": -0.50, "dte": 21, "strike": 400.0, "mid": 10.0},
        ]
        self._write_chain("GOOGL", "2026-06-05", rows)
        with patch.object(sel, "CHAIN_ROOT", self.tmp):
            cand = select_t2_csp("q041_t2_googl_csp", "2026-06-05")
        self.assertIsNone(cand)

    def test_close_below_min_filtered(self):
        rows = [
            {"option_type": "PUT", "delta": -0.20, "dte": 21, "strike": 366.0, "mid": 0.05},  # < 0.10
        ]
        self._write_chain("GOOGL", "2026-06-05", rows)
        with patch.object(sel, "CHAIN_ROOT", self.tmp):
            cand = select_t2_csp("q041_t2_googl_csp", "2026-06-05")
        self.assertIsNone(cand)

    def test_unknown_strategy_key_returns_none(self):
        with patch.object(sel, "CHAIN_ROOT", self.tmp):
            self.assertIsNone(select_t2_csp("not_a_strategy", "2026-06-05"))


if __name__ == "__main__":
    unittest.main()
