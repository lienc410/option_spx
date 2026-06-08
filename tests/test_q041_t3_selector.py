"""SPEC-115 Phase B — AC-4: T3 IC candidate construction."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import strategy.q041_t3_selector as sel
from strategy.q041_t3_selector import select_t3_earnings_ic


def _build_chain(sym: str, spot: float, expiry: str, dte: int) -> pd.DataFrame:
    """Symmetric synthetic chain around spot with $5 strikes ±$80."""
    rows = []
    strikes = [spot + i * 5 for i in range(-16, 17)]
    for k in strikes:
        dist = abs(k - spot)
        # crude price: ATM ~ $20/leg, decaying with distance
        call_px = max(0.5, 20 - dist * 0.20)
        put_px = max(0.5, 20 - dist * 0.20)
        rows.append({"option_type": "CALL", "strike": k, "dte": dte, "expiry": expiry,
                     "mid": round(call_px, 2), "delta": 0.5})
        rows.append({"option_type": "PUT", "strike": k, "dte": dte, "expiry": expiry,
                     "mid": round(put_px, 2), "delta": -0.5})
    return pd.DataFrame(rows)


class TestAC4_ICConstruction(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write(self, sym, date_str, spot, expiry, dte):
        day_dir = self.tmp / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        _build_chain(sym, spot, expiry, dte).to_parquet(day_dir / f"{sym}.parquet", index=False)
        pd.DataFrame([{"symbol": sym, "close": spot}]).to_parquet(
            day_dir / "_underlying.parquet", index=False)

    def test_ac4_cost_ic_four_legs(self):
        # COST spot 1000, expiry covers earn_date, DTE 7
        self._write("COST", "2026-06-05", spot=1000.0, expiry="2026-06-12", dte=7)
        with patch.object(sel, "CHAINS_ROOT", self.tmp):
            cand = select_t3_earnings_ic(
                "q041_t3_cost_earnings_ic", "2026-06-05", date(2026, 6, 8), vix_now=16.4)
        self.assertIsNotNone(cand)
        self.assertEqual(cand["underlying"], "COST")
        # 4 strikes present
        for k in ("K_short_put", "K_long_put", "K_short_call", "K_long_call"):
            self.assertIn(k, cand)
        self.assertEqual(cand["K_short_put"], cand["atm_strike"])
        self.assertEqual(cand["K_short_call"], cand["atm_strike"])
        self.assertLess(cand["K_long_put"], cand["atm_strike"])
        self.assertGreater(cand["K_long_call"], cand["atm_strike"])
        # net credit > 0, max loss > 0, cash_need == max_loss
        self.assertGreater(cand["net_credit_usd"], 0)
        self.assertGreater(cand["max_loss_usd"], 0)
        self.assertEqual(cand["cash_need_usd"], cand["max_loss_usd"])
        self.assertTrue(cand["paper_trade"])
        self.assertEqual(cand["imr_check"], "skipped")

    def test_vix_below_gate_returns_none(self):
        self._write("COST", "2026-06-05", spot=1000.0, expiry="2026-06-12", dte=7)
        with patch.object(sel, "CHAINS_ROOT", self.tmp):
            cand = select_t3_earnings_ic(
                "q041_t3_cost_earnings_ic", "2026-06-05", date(2026, 6, 8), vix_now=14.0)
        self.assertIsNone(cand)

    def test_missing_chain_returns_none(self):
        with patch.object(sel, "CHAINS_ROOT", self.tmp):
            cand = select_t3_earnings_ic(
                "q041_t3_jpm_earnings_ic", "2099-01-01", date(2099, 1, 5), vix_now=18.0)
        self.assertIsNone(cand)

    def test_expiry_before_earnings_excluded(self):
        # expiry 2026-06-06 is BEFORE earn_date 2026-06-08 → no qualifying expiry
        self._write("COST", "2026-06-05", spot=1000.0, expiry="2026-06-06", dte=1)
        with patch.object(sel, "CHAINS_ROOT", self.tmp):
            cand = select_t3_earnings_ic(
                "q041_t3_cost_earnings_ic", "2026-06-05", date(2026, 6, 8), vix_now=16.0)
        self.assertIsNone(cand)


if __name__ == "__main__":
    unittest.main()
