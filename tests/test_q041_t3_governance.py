"""SPEC-115 Phase B — AC-3/5/6/10: T3 governance (VIX gate, cash floor/cap, IMR skip)."""
import unittest
from datetime import date
from unittest.mock import patch

import strategy.cash_budget_governance as cbg
from strategy.cash_budget_governance import (
    CASH_OCCUPYING_STRATEGIES,
    evaluate_cash_collateral_budget,
)
import notify.q041_t3_earnings_check as chk


def _mock_cash(total, source="live"):
    return {"total": total, "source": source, "breakdown": {}, "error": None}


def _mock_open(total):
    return {"total": total, "positions": []}


def _ic_candidate(cash_need=2680.0, sk="q041_t3_cost_earnings_ic"):
    return {
        "strategy_key": sk,
        "underlying": "COST",
        "cash_need_usd": cash_need,
        "max_loss_usd": cash_need,
        "K_short_put": 972, "K_long_put": 931,
        "K_short_call": 972, "K_long_call": 1013,
        "net_credit_usd": 1420.0,
        "imr_check": "skipped",
        "paper_trade": True,
        "requested_bp_dollars": cash_need,
    }


class TestSetMembership(unittest.TestCase):
    def test_t3_strategies_in_set(self):
        self.assertIn("q041_t3_cost_earnings_ic", CASH_OCCUPYING_STRATEGIES)
        self.assertIn("q041_t3_jpm_earnings_ic", CASH_OCCUPYING_STRATEGIES)


class TestAC3_VixGate(unittest.TestCase):
    def test_ac3_vix_below_15_blocked(self):
        # T-3 handler with VIX 14.5 → blocked, reason vix_gate
        r = chk._handle_t_minus_3("COST", date(2026, 6, 8), 14.5, date(2026, 6, 3), dry_run=True)
        self.assertIsNotNone(r)
        self.assertFalse(r["decision"]["accepted"])
        self.assertIn("vix_gate", r["decision"]["reason"])

    def test_ac3_vix_none_blocked(self):
        r = chk._handle_t_minus_3("JPM", date(2026, 6, 8), None, date(2026, 6, 3), dry_run=True)
        self.assertFalse(r["decision"]["accepted"])
        self.assertIn("vix_gate", r["decision"]["reason"])


class TestAC5_CashFloorBlock(unittest.TestCase):
    def test_ac5_ic_blocked_below_floor(self):
        # liquid $16,918 < $30k floor → blocked regardless of small cash_need
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(16_918.0)):
            result = evaluate_cash_collateral_budget(_ic_candidate(2680.0))
        self.assertFalse(result["accepted"])
        self.assertIn("cash_floor", result["reason"])


class TestAC6_FitWhenCashRestored(unittest.TestCase):
    def test_ac6_ic_accepted_when_liquid_40k(self):
        # liquid $40k, cash_need $2,680 → 2680/40000 = 6.7% < 60% cap → accepted
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(40_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            result = evaluate_cash_collateral_budget(_ic_candidate(2680.0))
        self.assertTrue(result["accepted"])


class TestAC10_IMRSkip(unittest.TestCase):
    def test_ac10_imr_check_skipped_in_candidate(self):
        # Selector output carries imr_check=skipped; candidate proceeds (no block from IMR)
        cand = _ic_candidate(2680.0, sk="q041_t3_jpm_earnings_ic")
        self.assertEqual(cand["imr_check"], "skipped")
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(40_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            result = evaluate_cash_collateral_budget(cand)
        # IMR skip does not block; cash gate decides (accepted at $40k liquid)
        self.assertTrue(result["accepted"])


if __name__ == "__main__":
    unittest.main()
