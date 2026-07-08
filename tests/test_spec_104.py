import csv
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.sleeve_governance as gov
from notify.telegram_bot import _format_es_hv_paper_signal
from strategy.q042_config import (
    Q042_SLEEVE_A_PRODUCTION_CAP_PCT,
    Q042_SLEEVE_A_TARGET_CAP_PCT,
    Q042_SLEEVE_B_PAPER_SIZING_PCT,
    Q042_SLEEVE_B_PRODUCTION_CAP_PCT,
)
from strategy.q042_gate import compute_gate
from strategy.q042_sizing import q042_sleeve_cap_pct
from web.server import app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _state(*, second_leg=False, stress=False, spx=10.0, combined=15.0, short_vol=15.0):
    return {
        "timestamp": "2026-05-17T12:00:00-04:00",
        "status": "available",
        "basis_dollars": 200_000.0,
        "pools": {
            "spx_pm_bp_pct": spx,
            "es_span_bp_pct": 0.0,
            "combined_bp_pct": combined,
            "short_vol_bp_pct": short_vol,
        },
        "caps": gov.governance_caps(stress, second_leg),
        "stress_episode_active": stress,
        "second_leg_active": second_leg,
        "market": {"status": "available"},
        "active_overrides": [],
    }


class Spec104Tests(unittest.TestCase):
    def test_governance_caps_match_arch3_state_machine(self):
        self.assertEqual(gov.CAP_SPX_PM, 80.0)
        self.assertEqual(gov.CAP_STRESS_EPISODE, 50.0)
        self.assertEqual(gov.CAP_SECOND_LEG_EPISODE, 40.0)
        self.assertEqual(gov.governance_caps()["active_spx_pm_cap_pct"], 80.0)
        self.assertEqual(gov.governance_caps(True)["active_spx_pm_cap_pct"], 50.0)
        self.assertEqual(gov.governance_caps(True, True)["active_spx_pm_cap_pct"], 40.0)

    def test_second_leg_numeric_cap_blocks_new_spx_short_vol(self):
        decision = gov.evaluate_candidate(
            {"strategy_key": "bull_put_spread", "strategy": "Bull Put Spread", "requested_bp_dollars": 10_000},
            state=_state(second_leg=True, spx=38.0),
        )
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule, "R6")
        self.assertIn("40.0%", decision.reason)

    def test_q042_stage1_cap_and_gate(self):
        self.assertEqual(Q042_SLEEVE_A_PRODUCTION_CAP_PCT, 12.5)
        self.assertEqual(Q042_SLEEVE_A_TARGET_CAP_PCT, 17.5)
        self.assertEqual(Q042_SLEEVE_B_PRODUCTION_CAP_PCT, 0.0)
        self.assertEqual(Q042_SLEEVE_B_PAPER_SIZING_PCT, 10.0)
        self.assertEqual(q042_sleeve_cap_pct("A"), 12.5)
        self.assertEqual(q042_sleeve_cap_pct("B"), 10.0)

        gate = compute_gate(30.0, date="2026-05-17")
        self.assertEqual(gate.q042_combined_cap, 12.5)
        self.assertEqual(gate.sleeve_a_allowance, 12.5)
        self.assertEqual(gate.sleeve_b_allowance, 0.0)

    def test_hvladder_live_api_is_research_only(self):
        client = app.test_client()
        with patch("web.server._load_hvlad_paper_trades", return_value=[]), \
             patch("web.server._hvlad_vix_context", return_value={
                 "ok": True,
                 "vix_current": 25.0,
                 "vix_5td_avg": 24.0,
                 "latest_close_date": "2026-05-17",
                 "source": "unit",
                 "stale": False,
             }), \
             patch("web.server._hvlad_trend_status", return_value={"ok": True, "warmed": True, "trend_ok": True}):
            data = client.get("/api/hvladder/live").get_json()

        self.assertEqual(data["production_status"], "research_only")
        self.assertEqual(data["production_allocation_pct"], 0.0)
        self.assertFalse(data["execution_allowed"])

    def test_hvladder_rejects_production_open_records(self):
        client = app.test_client()
        with patch("web.server._hvlad_append") as append:
            res = client.post("/api/hvladder/position/open", json={
                "expiry": "2026-07-01",
                "short_strike": 6500,
                "contracts": 1,
                "entry_premium": 25.0,
                "paper_trade": False,
            })
        self.assertEqual(res.status_code, 403)
        append.assert_not_called()

    def test_hvladder_signal_wording_has_no_direct_entry_signal(self):
        text = _format_es_hv_paper_signal({
            "signal_date": "2026-05-17",
            "vix_at_signal": 25.0,
            "trend": "BULLISH",
            "active_slots": 1,
            "est_strike": 6500,
            "est_premium": 25.0,
        })
        self.assertNotIn("Entry Signal", text)
        # SPEC-136：同一约束（不下真实单）人话化为中文完整句
        self.assertIn("不会下任何真实单", text)

    def test_hvladder_page_banner_is_research_only(self):
        template = (REPO_ROOT / "web/templates/hvladder.html").read_text()
        self.assertIn("Research-only / Paper-only", template)
        self.assertIn("NO PRODUCTION EXECUTION", template)

    def test_q073_arch3_reference_numbers_available(self):
        path = REPO_ROOT / "research/q073/q073_p3_architecture_comparison.csv"
        with path.open() as f:
            rows = list(csv.DictReader(f))
        row = next(r for r in rows if r["architecture"] == "Arch-3 radical_no_HV")
        self.assertAlmostEqual(float(row["net_ann_roe_pct"]), 7.95, places=2)
        self.assertAlmostEqual(float(row["max_dd_pct"]), -8.71, places=2)
        self.assertAlmostEqual(float(row["worst_20d_pct"]), -7.04, places=2)


if __name__ == "__main__":
    unittest.main()
