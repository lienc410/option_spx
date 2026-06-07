"""SPEC-115 Phase A — AC-2/3/4: cash collateral governance extension.

AC-2: evaluate_cash_collateral_budget blocks $36,600 GOOGL CSP (> $22.2k cap)
AC-3: paper_trade=True candidate now走 cash gate (sleeve_governance integration)
AC-4: BCD path unchanged (entry_debit_usd / debit_usd field still read)
"""
import unittest
from unittest.mock import patch

import strategy.cash_budget_governance as cbg
from strategy.cash_budget_governance import (
    CASH_OCCUPYING_STRATEGIES,
    DEBIT_STRATEGIES,
    evaluate_cash_collateral_budget,
    evaluate_debit_cash_budget,
)


def _mock_cash(total, source="live"):
    return {"total": total, "source": source, "breakdown": {}, "error": None}


def _mock_open(total):
    return {"total": total, "positions": []}


class TestSetMembership(unittest.TestCase):
    def test_csp_strategies_in_set(self):
        self.assertIn("q041_t2_googl_csp", CASH_OCCUPYING_STRATEGIES)
        self.assertIn("q041_t2_amzn_csp", CASH_OCCUPYING_STRATEGIES)
        self.assertIn("bull_call_diagonal", CASH_OCCUPYING_STRATEGIES)

    def test_backward_compat_alias(self):
        # DEBIT_STRATEGIES alias must still resolve to the same set
        self.assertEqual(DEBIT_STRATEGIES, CASH_OCCUPYING_STRATEGIES)


class TestAC2_BlocksGooglCSP(unittest.TestCase):
    def test_ac2_blocks_36600_googl_csp(self):
        candidate = {
            "strategy_key": "q041_t2_googl_csp",
            "underlying": "GOOGL",
            "short_strike": 366.0,
            "cash_need_usd": 36_600.0,
            "paper_trade": True,
        }
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            result = evaluate_cash_collateral_budget(candidate)
        # 36600 > 60% of 37000 (22200) → blocked
        self.assertFalse(result["accepted"])
        self.assertIn("cash_collateral", result["reason"])
        self.assertAlmostEqual(result["stats"]["candidate_cash"], 36_600.0)

    def test_ac2_amzn_25200_also_blocked(self):
        candidate = {
            "strategy_key": "q041_t2_amzn_csp",
            "cash_need_usd": 25_200.0,
            "paper_trade": True,
        }
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            result = evaluate_cash_collateral_budget(candidate)
        self.assertFalse(result["accepted"])

    def test_small_csp_accepted(self):
        # A hypothetical small CSP under cap → accepted
        candidate = {"strategy_key": "q041_t2_googl_csp", "cash_need_usd": 10_000.0}
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            result = evaluate_cash_collateral_budget(candidate)
        self.assertTrue(result["accepted"])

    def test_csp_blocked_below_cash_floor(self):
        candidate = {"strategy_key": "q041_t2_googl_csp", "cash_need_usd": 10_000.0}
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(25_000.0)):
            result = evaluate_cash_collateral_budget(candidate)
        self.assertFalse(result["accepted"])
        self.assertIn("cash_floor", result["reason"])

    def test_non_cash_occupying_passes(self):
        candidate = {"strategy_key": "bull_put_spread", "requested_bp_dollars": 5000.0}
        result = evaluate_cash_collateral_budget(candidate)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["reason"], "not_cash_occupying")


class TestAC3_PaperGoesThruGate(unittest.TestCase):
    def test_ac3_paper_csp_blocked_in_sleeve_governance(self):
        import strategy.sleeve_governance as gov
        candidate = {
            "strategy_key": "q041_t2_googl_csp",
            "underlying": "GOOGL",
            "short_strike": 366.0,
            "cash_need_usd": 36_600.0,
            "requested_bp_dollars": 36_600.0,
            "paper_trade": True,
            "sleeve": "q041_paper",
        }
        with patch.object(gov, "current_governance_state", return_value={
            "basis_dollars": 500_000.0,
            "pools": {"spx_pm_bp_pct": 5.0, "combined_bp_pct": 5.0,
                      "es_span_bp_pct": 0.0, "short_vol_bp_pct": 0.0},
            "caps": {"active_spx_pm_cap_pct": 80.0},
            "stress_episode_active": False, "second_leg_active": False, "booster_active": False,
        }), patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            decision = gov.evaluate_candidate(candidate)
        # Paper CSP now subject to cash gate (SPEC-115 removed bypass) → blocked R111
        self.assertEqual(decision.rule, "R111")
        self.assertFalse(decision.accepted)


class TestAC4_BCDPathUnchanged(unittest.TestCase):
    def test_ac4_bcd_reads_debit_usd(self):
        # BCD candidate with debit_usd (no cash_need_usd) still works
        candidate = {"strategy_key": "bull_call_diagonal", "debit_usd": 24_000.0}
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            result = evaluate_cash_collateral_budget(candidate)
        # 24000 > 22200 → blocked, reason uses debit prefix
        self.assertFalse(result["accepted"])
        self.assertIn("debit_cash_budget", result["reason"])

    def test_ac4_bcd_via_deprecated_alias(self):
        candidate = {"strategy_key": "bull_call_diagonal", "debit_usd": 20_000.0}
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            result = evaluate_debit_cash_budget(candidate)  # deprecated alias
        # 20000 < 22200 → accepted
        self.assertTrue(result["accepted"])

    def test_ac4_bcd_requested_bp_dollars_fallback(self):
        candidate = {"strategy_key": "bull_call_diagonal", "requested_bp_dollars": 21_000.0}
        with patch.object(cbg, "get_current_liquid_cash", return_value=_mock_cash(37_000.0)), \
             patch.object(cbg, "get_open_cash_collateral_total_usd", return_value=_mock_open(0.0)):
            result = evaluate_cash_collateral_budget(candidate)
        self.assertTrue(result["accepted"])


if __name__ == "__main__":
    unittest.main()
