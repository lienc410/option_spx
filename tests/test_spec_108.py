import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import strategy.q078_ladder as ladder
import strategy.sleeve_governance as gov
import web.portfolio_surface
from web.server import app


def _verdict(strategy="Bull Put Spread", key="bull_put_spread", max_loss=9000.0):
    return {
        "strategy_name": strategy,
        "strategy_key": key,
        "max_loss_per_contract": max_loss,
        "theoretical_entry_credit": 540.0,
    }


def _market(day="2026-05-28", verdict=None):
    return {
        "date": day,
        "selector_timestamp": f"{day}T13:35:00Z",
        "selector_verdict": verdict or _verdict(),
        "q042_active": False,
    }


class Spec108LadderTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.patches = [
            patch.object(ladder, "RUNTIME_STATE_PATH", self.tmp / "q078_ladder_runtime.json"),
            patch.object(ladder, "SHADOW_LOG_PATH", self.tmp / "q078_ladder_shadow.jsonl"),
            patch.object(gov, "DATA_DIR", self.tmp),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def test_ac108_1_constants_defined(self):
        self.assertEqual(gov.LADDER_SIZING_CONTRACTS, 3)
        self.assertEqual(gov.LADDER_CADENCE_CLUSTER_DAYS, 5)
        self.assertEqual(gov.LADDER_BP_CEILING_PCT, 35.0)
        self.assertEqual(gov.LADDER_MODE_DEFAULT, "shadow")

    def test_ac108_2_cadence_gap_blocks_under_five_trading_days(self):
        state = ladder.LadderState(last_entry_date=date(2026, 5, 26), current_bp_pct_nlv_value=0.0)
        self.assertEqual(ladder.v3_ladder_eligible(_market("2026-05-28"), state), (False, "cadence_gap"))

    def test_ac108_3_selector_wait_blocks_reduce_wait_string(self):
        state = ladder.LadderState(last_entry_date=None, current_bp_pct_nlv_value=0.0)
        verdict = _verdict(strategy="Reduce / Wait", key="reduce_wait")
        self.assertEqual(ladder.v3_ladder_eligible(_market(verdict=verdict), state), (False, "selector_wait"))

    def test_ac108_4_concurrency_blocks_same_strategy(self):
        state = ladder.LadderState(
            active_positions=[{"strategy_key": "bull_put_spread"}],
            current_bp_pct_nlv_value=0.0,
        )
        self.assertEqual(ladder.v3_ladder_eligible(_market(), state), (False, "concurrency_block"))

        ic_state = ladder.LadderState(
            active_positions=[{"strategy": "Iron Condor (High Vol)"}, {"strategy": "Iron Condor (High Vol)"}],
            current_bp_pct_nlv_value=0.0,
        )
        verdict = _verdict(strategy="Iron Condor (High Vol)", key="iron_condor_hv")
        self.assertEqual(ladder.v3_ladder_eligible(_market(verdict=verdict), ic_state), (False, "concurrency_block"))

    def test_ac108_5_bp_ceiling_blocks_projected_over_35pct(self):
        state = ladder.LadderState(current_bp_pct_nlv_value=30.0, nlv=100_000.0)
        self.assertEqual(ladder.v3_ladder_eligible(_market(), state), (False, "bp_ceiling_block"))

    def test_ac108_6_valid_entry_day_passes(self):
        state = ladder.LadderState(current_bp_pct_nlv_value=0.0, nlv=100_000.0)
        self.assertEqual(ladder.v3_ladder_eligible(_market(), state), (True, ""))

    def test_ac108_7_api_exposes_ladder_fields(self):
        fake_summary = {
            "rails": {"spx_live": {"current_position": None}, "etrade_pm": {"current_position": None}},
            "account_breakdown": {
                "schwab_nlv": 100_000.0,
                "schwab_maintenance_margin": 5_000.0,
                "etrade_nlv": 0.0,
                "etrade_maintenance_margin": 0.0,
            },
        }
        with patch("web.portfolio_surface.portfolio_summary_payload", return_value=fake_summary), \
             patch("web.portfolio_surface.es_stressed_span_payload", return_value={"has_es_live_position": False}), \
             patch("strategy.sleeve_governance._latest_market_stress", return_value={"status": "available", "stress_episode_active": False, "second_leg_active": False}), \
             patch("strategy.sleeve_governance._selector_verdict_for_ladder", return_value=(_verdict(), "2026-05-28T13:35:00Z")), \
             patch("strategy.sleeve_governance._open_spx_positions_for_ladder", return_value=[]):
            res = app.test_client().get("/api/sleeve-governance/state")
        data = res.get_json()
        state = data["state"]
        for key in (
            "ladder_mode",
            "ladder_last_entry_date",
            "ladder_cadence_eligible",
            "ladder_strategy_eligible",
            "ladder_concurrency_block",
            "ladder_bp_ceiling_block",
            "ladder_skip_reason",
            "ladder_active_positions",
            "ladder_active_total_bp",
            "ladder_active_q042_overlap",
            "ladder_action_days_ytd",
        ):
            self.assertIn(key, state)

    def test_ac108_8_default_shadow_and_non_active_order_path(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(gov.ladder_mode(), "shadow")
            self.assertFalse(ladder.production_order_allowed(True, gov.ladder_mode()))

    def test_ac108_9_shadow_log_writes_selector_pass_day(self):
        state = ladder.LadderState(current_bp_pct_nlv_value=0.0, nlv=100_000.0)
        eligible, reason = ladder.v3_ladder_eligible(_market(), state)
        payload = ladder.shadow_payload(_market(), state, eligible=eligible, skip_reason=reason, mode="shadow")
        ladder.append_shadow_log(payload)
        row = json.loads(ladder.SHADOW_LOG_PATH.read_text().strip())
        self.assertEqual(row["ladder_mode"], "shadow")
        self.assertEqual(row["selector_strategy"], "Bull Put Spread")
        self.assertTrue(row["would_enter"])

    def test_ac108_16_action_days_counter_only_counts_eligible(self):
        state = ladder.LadderState(current_bp_pct_nlv_value=0.0, nlv=100_000.0, action_days_ytd=4)
        payload = ladder.shadow_payload(_market(), state, eligible=True, skip_reason="", mode="shadow")
        self.assertEqual(payload["ladder_action_days_ytd"], 5)
        skipped = ladder.shadow_payload(_market(), state, eligible=False, skip_reason="cadence_gap", mode="shadow")
        self.assertEqual(skipped["ladder_action_days_ytd"], 4)

    def test_ac108_17_shadow_default_writes_would_enter_but_disables_production(self):
        with patch.dict("os.environ", {}, clear=True):
            state = ladder.LadderState(current_bp_pct_nlv_value=0.0, nlv=100_000.0)
            eligible, reason = ladder.v3_ladder_eligible(_market(), state)
            payload = ladder.shadow_payload(_market(), state, eligible=eligible, skip_reason=reason, mode=gov.ladder_mode())
            ladder.append_shadow_log(payload)
            self.assertTrue(eligible)
            self.assertEqual(gov.ladder_mode(), "shadow")
            self.assertFalse(ladder.production_order_allowed(eligible, gov.ladder_mode()))
            self.assertTrue(ladder.SHADOW_LOG_PATH.exists())

    def test_ac108_18_eligible_true_does_not_allow_order_under_shadow_default(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(ladder.v3_ladder_eligible(_market(), ladder.LadderState())[0])
            self.assertFalse(ladder.production_order_allowed(True, gov.ladder_mode()))


if __name__ == "__main__":
    unittest.main()
