"""SPEC-115 Phase B — AC-11/12: T3 Telegram message format + silent non-trigger days."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import notify.q041_t3_earnings_check as chk
import strategy.cash_budget_governance as cbg


def _mock_cash(total, source="live"):
    return {"total": total, "source": source, "breakdown": {}, "error": None}


def _mock_open(total):
    return {"total": total, "positions": []}


def _cand():
    return {
        "underlying": "COST", "earn_date": "2026-06-08", "vix_entry": 16.4,
        "spot": 972.35, "atm_strike": 972,
        "implied_move_pct": 0.0422, "implied_move_usd": 41.08, "spread_width_usd": 41.0,
        "K_short_put": 972, "K_long_put": 931, "K_short_call": 972, "K_long_call": 1013,
        "net_credit_usd": 1420.0, "max_loss_usd": 2680.0, "cash_need_usd": 2680.0,
    }


class TestAC11_TMinus3Format(unittest.TestCase):
    def test_ac11_format_blocked(self):
        decision = {"accepted": False, "reason": "cash_floor: liquid $16,918 < $30,000 floor"}
        msg = chk._format_t_minus_3(_cand(), decision)
        self.assertIn("📅 Q041 T3 Paper Signal: COST T-3", msg)
        self.assertIn("VIX: 16.4 ✅", msg)
        self.assertIn("ATM straddle: $41.08", msg)
        self.assertIn("Net credit: $1420", msg)
        self.assertIn("Max loss: $2680", msg)
        self.assertIn("blocked", msg)

    def test_ac11_format_open(self):
        msg = chk._format_t_minus_3(_cand(), {"accepted": True, "reason": "accepted"})
        self.assertIn("✅ PAPER OPEN", msg)


class TestAC12_TPlus1Format(unittest.TestCase):
    def test_ac12_close_held(self):
        close = {"s_exit": 1000.85, "breached": None, "strikes_held": True,
                 "paper_pnl_usd": 1420.0, "net_credit_usd": 1420.0, "max_loss_usd": 2680.0}
        msg = chk._format_t_plus_1(_cand(), close)
        self.assertIn("📅 Q041 T3 Paper Close: COST T+1", msg)
        self.assertIn("both strikes held", msg)
        self.assertIn("+$1420", msg)

    def test_ac12_close_breached(self):
        close = {"s_exit": 920.0, "breached": "put", "strikes_held": False,
                 "paper_pnl_usd": 320.0, "net_credit_usd": 1420.0, "max_loss_usd": 2680.0}
        msg = chk._format_t_plus_1(_cand(), close)
        self.assertIn("put breached", msg)
        self.assertIn("+$320", msg)


class TestSilentDays(unittest.TestCase):
    def test_non_trigger_day_silent(self):
        # earn date far away → days_to != 3 and != -1 → no results
        with patch.object(chk, "load_cache",
                          return_value={"COST": "2026-12-15", "JPM": "2026-12-16"}):
            results = chk.run(date(2026, 6, 3), dry_run=True,
                              mock_earn={"COST": "2026-12-15", "JPM": "2026-12-16"},
                              vix_override=18.0)
        self.assertEqual(results, [])

    def test_t_minus_3_triggers(self):
        # mock earn so that COST is exactly T-3 from asof; no chain → no_candidate path
        # asof 2026-06-03 (Wed); T-3 means earn is 3 trading days ahead = 2026-06-08 (Mon)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(chk, "PAPER_LOG", Path(tmp) / "log.jsonl"), \
                 patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(40_000.0)), \
                 patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
                results = chk.run(
                    date(2026, 6, 3), dry_run=True,
                    mock_earn={"COST": "2026-06-08"}, vix_override=18.0)
        # COST is T-3 → handler runs; no chain in temp → no_candidate blocked
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["underlying"], "COST")


if __name__ == "__main__":
    unittest.main()
