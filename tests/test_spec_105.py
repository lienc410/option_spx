import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.sleeve_governance as gov
from web.server import app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _benign_market(**overrides):
    market = {
        "status": "available",
        "spx_close": 6000.0,
        "ma50": 5900.0,
        "ddath": -0.01,
        "vix": 16.0,
        "vix_5d_change": 0.2,
        "ivp252": 35.0,
        "stress_episode_active": False,
        "second_leg_active": False,
    }
    market.update(overrides)
    return market


def _state(*, booster=True, mode="shadow", spx=75.0, combined=20.0, short_vol=20.0):
    market = _benign_market() if booster else _benign_market(vix=24.0)
    cap_pct, cap_regime = gov.active_spx_cap(market, mode=mode)
    booster_active = gov.b4_benign_active(market)
    return {
        "timestamp": "2026-05-18T12:00:00-04:00",
        "status": "available",
        "basis_dollars": 200_000.0,
        "pools": {
            "spx_pm_bp_pct": spx,
            "es_span_bp_pct": 0.0,
            "combined_bp_pct": combined,
            "short_vol_bp_pct": short_vol,
        },
        "caps": gov.governance_caps(False, False, booster_active, cap_pct, cap_regime),
        "stress_episode_active": False,
        "second_leg_active": False,
        "booster_active": booster_active,
        "booster_mode": mode,
        "booster_signal_conditions": gov.booster_signal_conditions(market),
        "active_spx_pm_cap_pct": cap_pct,
        "active_spx_pm_cap_regime": cap_regime,
        "market": market,
        "active_overrides": [],
    }


class Spec105Tests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.orig = {
            "STATE_LOG_PATH": gov.STATE_LOG_PATH,
            "DECISION_LOG_PATH": gov.DECISION_LOG_PATH,
            "OVERRIDE_LOG_PATH": gov.OVERRIDE_LOG_PATH,
            "RUNTIME_STATE_PATH": gov.RUNTIME_STATE_PATH,
            "BOOSTER_SHADOW_LOG_PATH": gov.BOOSTER_SHADOW_LOG_PATH,
        }
        gov.STATE_LOG_PATH = self.tmp / "state.jsonl"
        gov.DECISION_LOG_PATH = self.tmp / "decisions.jsonl"
        gov.OVERRIDE_LOG_PATH = self.tmp / "overrides.jsonl"
        gov.RUNTIME_STATE_PATH = self.tmp / "runtime.json"
        gov.BOOSTER_SHADOW_LOG_PATH = self.tmp / "q074_booster_shadow.jsonl"

    def tearDown(self):
        for key, value in self.orig.items():
            setattr(gov, key, value)

    def test_b4_gate_requires_all_conditions(self):
        self.assertTrue(gov.b4_benign_active(_benign_market()))
        self.assertFalse(gov.b4_benign_active(_benign_market(status="unavailable")))
        self.assertFalse(gov.b4_benign_active(_benign_market(spx_close=5800.0)))
        self.assertFalse(gov.b4_benign_active(_benign_market(ddath=-0.05)))
        self.assertFalse(gov.b4_benign_active(_benign_market(vix=22.0)))
        self.assertFalse(gov.b4_benign_active(_benign_market(vix_5d_change=1.6)))
        self.assertFalse(gov.b4_benign_active(_benign_market(ivp252=55.0)))
        self.assertFalse(gov.b4_benign_active(_benign_market(stress_episode_active=True)))
        self.assertFalse(gov.b4_benign_active(_benign_market(second_leg_active=True)))

    def test_active_spx_cap_priority_and_shadow_mode(self):
        self.assertEqual(gov.CAP_SPX_BENIGN_BOOSTER, 90.0)
        self.assertEqual(gov.active_spx_cap(_benign_market(second_leg_active=True), mode="active"), (40.0, "second_leg"))
        self.assertEqual(gov.active_spx_cap(_benign_market(stress_episode_active=True), mode="active"), (50.0, "stress"))
        self.assertEqual(gov.active_spx_cap(_benign_market(), mode="active"), (90.0, "booster"))
        self.assertEqual(gov.active_spx_cap(_benign_market(), mode="shadow"), (80.0, "booster_shadow"))
        self.assertEqual(gov.active_spx_cap(_benign_market(vix=24.0), mode="active"), (80.0, "normal"))

    def test_stage1_shadow_does_not_expand_production_cap(self):
        decision = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 10_000},
            state=_state(booster=True, mode="shadow", spx=78.0, combined=20.0, short_vol=20.0),
        )
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule, "R1")
        self.assertIn("80.0% active cap", decision.reason)
        self.assertEqual(decision.state["active_spx_pm_cap_regime"], "booster_shadow")

    def test_future_active_mode_allows_booster_cap_without_changing_base_caps(self):
        accepted = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 10_000},
            state=_state(booster=True, mode="active", spx=84.0, combined=20.0, short_vol=20.0),
        )
        blocked = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 10_000},
            state=_state(booster=True, mode="active", spx=86.0, combined=20.0, short_vol=20.0),
        )
        self.assertTrue(accepted.accepted)
        self.assertFalse(blocked.accepted)
        self.assertEqual(blocked.rule, "R1")
        self.assertEqual(gov.CAP_SPX_PM, 80.0)
        self.assertEqual(gov.CAP_STRESS_EPISODE, 50.0)
        self.assertEqual(gov.CAP_SECOND_LEG_EPISODE, 40.0)

    def test_api_exposes_booster_fields(self):
        fake_payload = {
            "surface": "sleeve_governance",
            "state": _state(booster=True, mode="shadow"),
            "recent_blocked_candidates": [],
            "recent_counts": {},
            "monitors": {},
            "replay_validation": {},
        }
        with patch("strategy.sleeve_governance.governance_dashboard_payload", return_value=fake_payload):
            data = app.test_client().get("/api/sleeve-governance/state").get_json()

        state = data["state"]
        self.assertTrue(state["booster_active"])
        self.assertEqual(state["active_spx_pm_cap_regime"], "booster_shadow")
        self.assertEqual(state["active_spx_pm_cap_pct"], 80.0)
        self.assertIn("trend_ok", state["booster_signal_conditions"])
        self.assertIn("booster_shadow_cap_pct", state["caps"])

    def test_shadow_snapshot_writes_booster_observation_log(self):
        with patch("strategy.sleeve_governance.current_governance_state", return_value=_state(booster=True, mode="shadow")):
            gov.record_state_snapshot(send_alerts=False)

        self.assertTrue(gov.BOOSTER_SHADOW_LOG_PATH.exists())
        row = gov.BOOSTER_SHADOW_LOG_PATH.read_text().strip()
        self.assertIn('"booster_active": true', row)
        self.assertIn('"booster_shadow_cap_pct": 90.0', row)

    def test_q074_b4_reference_numbers_reproduce(self):
        path = REPO_ROOT / "research/q074/q074_p2_candidate_results.csv"
        with path.open() as f:
            row = next(r for r in csv.DictReader(f) if r["candidate"] == "B4_moderate_90")

        self.assertAlmostEqual(float(row["net_ann_roe_pct"]), 8.20, delta=0.10)
        self.assertAlmostEqual(float(row["max_dd_pct"]), -8.71, delta=0.50)
        self.assertAlmostEqual(float(row["worst_20d_pct"]), -7.04, delta=0.30)


if __name__ == "__main__":
    unittest.main()
