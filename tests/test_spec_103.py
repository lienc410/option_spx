import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.sleeve_governance as gov
from web.server import app


def _state(*, second_leg=False, stress=False, spx=10.0, es=5.0, combined=15.0, short_vol=15.0):
    return {
        "timestamp": "2026-05-15T12:00:00-04:00",
        "status": "available",
        "basis_dollars": 200_000.0,
        "pools": {
            "spx_pm_bp_pct": spx,
            "es_span_bp_pct": es,
            "combined_bp_pct": combined,
            "short_vol_bp_pct": short_vol,
        },
        "caps": gov.governance_caps(stress, second_leg),
        "stress_episode_active": stress,
        "second_leg_active": second_leg,
        "market": {"status": "available"},
        "active_overrides": [],
    }


class Spec103Tests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.orig = {
            "STATE_LOG_PATH": gov.STATE_LOG_PATH,
            "DECISION_LOG_PATH": gov.DECISION_LOG_PATH,
            "OVERRIDE_LOG_PATH": gov.OVERRIDE_LOG_PATH,
            "RUNTIME_STATE_PATH": gov.RUNTIME_STATE_PATH,
        }
        gov.STATE_LOG_PATH = self.tmp / "state.jsonl"
        gov.DECISION_LOG_PATH = self.tmp / "decisions.jsonl"
        gov.OVERRIDE_LOG_PATH = self.tmp / "overrides.jsonl"
        gov.RUNTIME_STATE_PATH = self.tmp / "runtime.json"

    def tearDown(self):
        for key, value in self.orig.items():
            setattr(gov, key, value)

    def test_ac2_ac3_q072_replay_flags_match_reference(self):
        result = gov.q072_replay_validation()

        self.assertTrue(result["stress_pass"])
        self.assertEqual(result["stress_mismatch_days"], 0)
        self.assertTrue(result["second_leg_pass"])
        self.assertLessEqual(result["second_leg_mismatch_days"], 2)

    def test_ac8_allocator_smoke_matches_q072_default_cap(self):
        smoke = gov.q072_replay_validation()["allocator_smoke"]

        self.assertTrue(smoke["pass"])
        self.assertEqual(smoke["n_entered"], 872)
        self.assertEqual(round(smoke["total_pnl"]), 742193)
        self.assertEqual(round(smoke["max_dd"]), -174959)

    def test_ac4_r6_blocks_new_short_vol_but_allows_rolls(self):
        blocked = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 10_000},
            state=_state(second_leg=True),
        )
        allowed_roll = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "action": "roll", "requested_bp_dollars": 10_000},
            state=_state(second_leg=True),
        )

        self.assertFalse(blocked.accepted)
        self.assertEqual(blocked.rule, "R6")
        self.assertTrue(allowed_roll.accepted)

    def test_ac4_r1_r5_caps_are_enforced(self):
        r1 = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 30_000},
            state=_state(spx=70.0, combined=20.0, short_vol=20.0),
        )
        r5 = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 15_000},
            state=_state(stress=True, spx=45.0, combined=20.0, short_vol=20.0),
        )

        self.assertFalse(r1.accepted)
        self.assertEqual(r1.rule, "R1")
        self.assertFalse(r5.accepted)
        self.assertEqual(r5.rule, "R5")

    def test_ac5_decision_log_has_counterfactual_placeholders(self):
        decision = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 10_000},
            state=_state(second_leg=True),
        )
        payload = gov.log_decision(decision)

        row = json.loads(gov.DECISION_LOG_PATH.read_text().splitlines()[0])
        self.assertEqual(row["rule"], "R6")
        self.assertEqual(payload["counterfactual"]["status"], "pending_future_observation")
        self.assertIn("estimated_bp_saved", row)

    def test_ac6_manual_override_pauses_r6(self):
        gov.pause_rule("R6", "1d", "unit test")
        decision = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 10_000},
            state=_state(second_leg=True),
        )

        self.assertTrue(decision.accepted)
        self.assertTrue(gov.is_rule_paused("R6"))

    def test_ac7_dashboard_api_fails_soft_and_reports_state(self):
        self.client = app.test_client()
        with patch("strategy.sleeve_governance.current_governance_state", return_value=_state(second_leg=True)):
            res = self.client.get("/api/sleeve-governance/state")

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["surface"], "sleeve_governance")
        self.assertTrue(data["state"]["second_leg_active"])
        self.assertIn("replay_validation", data)

    def test_ac4_open_endpoint_rejects_production_short_vol_when_r6_active(self):
        self.client = app.test_client()
        with patch("strategy.sleeve_governance.current_governance_state", return_value=_state(second_leg=True)), \
             patch("strategy.sleeve_governance.maybe_alert_decision", return_value=True):
            res = self.client.post("/api/position/open", json={
                "strategy_key": "bull_put_spread",
                "short_strike": 5000,
                "long_strike": 4950,
                "contracts": 1,
                "actual_premium": 5.0,
            })

        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data["governance"]["rule"], "R6")

    def test_pools_by_view_account_filter(self):
        """Verify R1/R3/R4 口径 refinement: per-account-view BP using maintenance."""
        fake_summary = {
            "bp_basis": 200_000.0,
            "rails": {
                "spx_live": {"current_position": {"strategy_key": "bull_put_spread"}},
                "etrade_pm": {"current_position": None},
            },
            "account_breakdown": {
                "schwab_nlv": 120_000.0,
                "schwab_maintenance_margin": 24_000.0,   # 20% of Schwab NLV
                "etrade_nlv": 80_000.0,
                "etrade_maintenance_margin": 8_000.0,    # 10% of ETrade NLV
            },
        }
        fake_es = {"has_es_live_position": False}

        with patch("web.portfolio_surface.portfolio_summary_payload", return_value=fake_summary), \
             patch("web.portfolio_surface.es_stressed_span_payload", return_value=fake_es), \
             patch("strategy.sleeve_governance._latest_market_stress",
                   return_value={"status": "available", "stress_episode_active": False,
                                 "second_leg_active": False}):
            state = gov.current_governance_state()

        pbv = state["pools_by_view"]
        self.assertIn("all", pbv)
        self.assertIn("schwab", pbv)
        self.assertIn("etrade", pbv)

        # all view: combined maint / combined NLV = 32k / 200k = 16%
        self.assertAlmostEqual(pbv["all"]["spx_pm_bp_pct"], 16.0, places=1)
        self.assertEqual(pbv["all"]["nlv_basis"], 200_000.0)
        # /ES has no live position, so es_span = 0 in 'all'
        self.assertEqual(pbv["all"]["es_span_bp_pct"], 0.0)

        # schwab view: 24k / 120k = 20%
        self.assertAlmostEqual(pbv["schwab"]["spx_pm_bp_pct"], 20.0, places=1)
        self.assertEqual(pbv["schwab"]["nlv_basis"], 120_000.0)
        # schwab view: /ES is independent broker pool — should be None
        self.assertIsNone(pbv["schwab"]["es_span_bp_pct"])

        # etrade view: 8k / 80k = 10%
        self.assertAlmostEqual(pbv["etrade"]["spx_pm_bp_pct"], 10.0, places=1)
        self.assertEqual(pbv["etrade"]["nlv_basis"], 80_000.0)
        self.assertIsNone(pbv["etrade"]["es_span_bp_pct"])

        # Back-compat: 'pools' field equals 'all' view
        self.assertEqual(state["pools"]["spx_pm_bp_pct"], pbv["all"]["spx_pm_bp_pct"])


if __name__ == "__main__":
    unittest.main()
