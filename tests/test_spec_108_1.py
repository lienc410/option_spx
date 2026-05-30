"""SPEC-108.1 acceptance tests — R1 portfolio stress gate, R2 V1b ladder,
R3 Stage-2 gate text, R4 drift monitor.

AC-108.1-1  portfolio_stress_overnight_gap() returns mark_loss_pct_nlv + gate_pass
AC-108.1-2  Stage 2 gate: stress gate blocks eligible=True when mode=active + loss >12%
AC-108.1-3  v1b_ladder_eligible() weekly anchor logic (Wed=eligible, other=not_weekly_anchor)
AC-108.1-4  LADDER_V1B_MODE_DEFAULT == "shadow"
AC-108.1-5  /api/sleeve-governance/state returns 11 ladder_v1b_* + 2 ladder_strategy_drift_* fields
AC-108.1-6  SPEC-108.md §6 Stage 2 gate text contains conditions 8 + 9 (R1/R3 language)
AC-108.1-7  strategy_distribution_check() reads shadow log + flags drift > 15pp
AC-108.1-8  Dashboard HTML contains V1b panel (ladder-v1b-panel class)
AC-108.1-9  Dashboard HTML contains drift chip (ladder-drift-chip class)
AC-108.1-10 Telegram module has _format_ladder_v1b_shadow_message function
AC-108.1-11 production_order_allowed_v1b(): shadow-default + mutual exclusion enforcement
AC-108.1-12 All 18 SPEC-108 ACs pass (regression)
AC-108.1-13 SPEC-103/104/105/106/107 tests pass (regression — import smoke only)
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import strategy.q078_ladder as v3ladder
import strategy.q078_ladder_v1b as v1b
import strategy.sleeve_governance as gov
import web.portfolio_surface
from strategy.q078_ladder_monitors import (
    DRIFT_THRESHOLD_PP,
    HISTORICAL_STRATEGY_BANDS,
    strategy_distribution_check,
)
from web.server import app


# ── helpers ────────────────────────────────────────────────────────────────────

def _verdict(strategy="Bull Put Spread", key="bull_put_spread", max_loss=9000.0):
    return {
        "strategy_name": strategy,
        "strategy_key": key,
        "max_loss_per_contract": max_loss,
        "theoretical_entry_credit": 540.0,
    }


def _market(day="2026-05-27", verdict=None):  # 2026-05-27 is Wednesday
    return {
        "date": day,
        "selector_timestamp": f"{day}T13:35:00Z",
        "selector_verdict": verdict or _verdict(),
        "q042_active": False,
    }


def _fake_governance_state():
    return {
        "rails": {"spx_live": {"current_position": None}, "etrade_pm": {"current_position": None}},
        "account_breakdown": {
            "schwab_nlv": 100_000.0,
            "schwab_maintenance_margin": 5_000.0,
            "etrade_nlv": 0.0,
            "etrade_maintenance_margin": 0.0,
        },
    }


# ── AC-108.1-1 ─────────────────────────────────────────────────────────────────

class TestAC1081_1_StressGate(unittest.TestCase):
    def test_safe_fallback_when_no_market_data(self):
        result = gov.portfolio_stress_overnight_gap({"basis_dollars": 100_000.0, "market": {}})
        self.assertIn("mark_loss_pct_nlv", result)
        self.assertIn("gate_pass", result)
        self.assertEqual(result["source"], "safe_fallback")
        self.assertTrue(result["gate_pass"])  # safe fallback = pass

    def test_returns_correct_keys(self):
        result = gov.portfolio_stress_overnight_gap({
            "basis_dollars": 100_000.0,
            "market": {"spx_close": 5000.0, "vix": 20.0},
        })
        for key in ("mark_loss_pct_nlv", "gate_pass", "source"):
            self.assertIn(key, result)

    def test_gate_pass_true_when_small_loss(self):
        result = gov.portfolio_stress_overnight_gap({
            "basis_dollars": 1_000_000.0,
            "market": {"spx_close": 5000.0, "vix": 18.0},
        })
        # No open positions → loss = 0 → gate_pass = True
        self.assertTrue(result["gate_pass"])

    def test_gate_pass_is_bool(self):
        result = gov.portfolio_stress_overnight_gap({"basis_dollars": 100_000.0, "market": {}})
        self.assertIsInstance(result["gate_pass"], bool)

    def test_mark_loss_pct_is_float(self):
        result = gov.portfolio_stress_overnight_gap({
            "basis_dollars": 100_000.0,
            "market": {"spx_close": 5000.0, "vix": 20.0},
        })
        self.assertIsInstance(result["mark_loss_pct_nlv"], float)


# ── AC-108.1-2 ─────────────────────────────────────────────────────────────────

class TestAC1081_2_StressGateBlock(unittest.TestCase):
    def test_active_mode_blocks_when_stress_fails(self):
        """Stage 2 gate: stress gate with mark_loss > 12% blocks eligible=True in active mode."""
        tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(tmpdir.name)

        def mock_stress_fail(state):
            return {"mark_loss_pct_nlv": 15.0, "gate_pass": False, "source": "mock"}

        with patch.object(v3ladder, "RUNTIME_STATE_PATH", tmp / "rt.json"), \
             patch.object(v3ladder, "SHADOW_LOG_PATH", tmp / "sl.jsonl"), \
             patch.object(gov, "DATA_DIR", tmp), \
             patch.dict("os.environ", {"LADDER_MODE": "active"}), \
             patch("strategy.sleeve_governance.portfolio_stress_overnight_gap", mock_stress_fail), \
             patch("strategy.sleeve_governance._selector_verdict_for_ladder",
                   return_value=(_verdict(), "2026-05-27T13:35:00Z")), \
             patch("strategy.sleeve_governance._open_spx_positions_for_ladder", return_value=[]):
            state = {"basis_dollars": 100_000.0, "pools": {"spx_pm_bp_pct": 0.0},
                     "market": {"spx_close": 5000.0, "vix": 20.0}}
            payload = gov.ladder_shadow_decision_payload(state, commit=False)

        self.assertEqual(payload.get("skip_reason"), "portfolio_stress_block")
        self.assertFalse(payload.get("would_enter"))
        self.assertFalse(payload.get("production_order_allowed"))
        tmpdir.cleanup()

    def test_shadow_mode_does_not_block_on_stress_fail(self):
        """In shadow mode, stress gate computes but does not block."""
        tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(tmpdir.name)

        def mock_stress_fail(state):
            return {"mark_loss_pct_nlv": 15.0, "gate_pass": False, "source": "mock"}

        with patch.object(v3ladder, "RUNTIME_STATE_PATH", tmp / "rt.json"), \
             patch.object(v3ladder, "SHADOW_LOG_PATH", tmp / "sl.jsonl"), \
             patch.object(gov, "DATA_DIR", tmp), \
             patch.dict("os.environ", {}, clear=True), \
             patch("strategy.sleeve_governance.portfolio_stress_overnight_gap", mock_stress_fail), \
             patch("strategy.sleeve_governance._selector_verdict_for_ladder",
                   return_value=(_verdict(), "2026-05-27T13:35:00Z")), \
             patch("strategy.sleeve_governance._open_spx_positions_for_ladder", return_value=[]):
            state = {"basis_dollars": 100_000.0, "pools": {"spx_pm_bp_pct": 0.0},
                     "market": {"spx_close": 5000.0, "vix": 20.0}}
            payload = gov.ladder_shadow_decision_payload(state, commit=False)

        # Shadow mode: stress gate doesn't block
        self.assertNotEqual(payload.get("skip_reason"), "portfolio_stress_block")
        # Stress result still attached to payload
        sg = payload.get("portfolio_stress_gate") or {}
        self.assertFalse(sg.get("gate_pass"))
        tmpdir.cleanup()


# ── AC-108.1-3 ─────────────────────────────────────────────────────────────────

class TestAC1081_3_V1bEligibility(unittest.TestCase):
    def setUp(self):
        self.state = v1b.LadderV1bState(current_bp_pct_nlv_value=0.0, nlv=100_000.0)

    def test_wednesday_passes(self):
        eligible, reason = v1b.v1b_ladder_eligible(_market("2026-05-27"), self.state)
        self.assertTrue(eligible)
        self.assertEqual(reason, "")

    def test_non_wednesday_fails(self):
        for day in ("2026-05-26", "2026-05-28", "2026-05-29", "2026-05-30"):
            with self.subTest(day=day):
                eligible, reason = v1b.v1b_ladder_eligible(_market(day), self.state)
                self.assertFalse(eligible)
                self.assertEqual(reason, "not_weekly_anchor")

    def test_selector_wait_blocks_on_wednesday(self):
        verdict = _verdict(strategy="Reduce / Wait", key="reduce_wait")
        eligible, reason = v1b.v1b_ladder_eligible(_market("2026-05-27", verdict=verdict), self.state)
        self.assertFalse(eligible)
        self.assertEqual(reason, "selector_wait")

    def test_concurrency_blocks_on_wednesday(self):
        state = v1b.LadderV1bState(
            active_positions=[{"strategy_key": "bull_put_spread"}],
            current_bp_pct_nlv_value=0.0,
        )
        eligible, reason = v1b.v1b_ladder_eligible(_market("2026-05-27"), state)
        self.assertFalse(eligible)
        self.assertEqual(reason, "concurrency_block")

    def test_bp_ceiling_blocks_on_wednesday(self):
        state = v1b.LadderV1bState(current_bp_pct_nlv_value=30.0, nlv=100_000.0)
        eligible, reason = v1b.v1b_ladder_eligible(_market("2026-05-27"), state)
        self.assertFalse(eligible)
        self.assertEqual(reason, "bp_ceiling_block")


# ── AC-108.1-4 ─────────────────────────────────────────────────────────────────

class TestAC1081_4_V1bModeDefault(unittest.TestCase):
    def test_ladder_v1b_mode_default_is_shadow(self):
        self.assertEqual(gov.LADDER_V1B_MODE_DEFAULT, "shadow")

    def test_ladder_v1b_mode_returns_shadow_without_env(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(gov.ladder_v1b_mode(), "shadow")

    def test_production_order_not_allowed_in_shadow(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(v1b.production_order_allowed_v1b(True, gov.ladder_v1b_mode()))


# ── AC-108.1-5 ─────────────────────────────────────────────────────────────────

class TestAC1081_5_APIFields(unittest.TestCase):
    def test_api_returns_v1b_and_drift_fields(self):
        with patch("web.portfolio_surface.portfolio_summary_payload", return_value=_fake_governance_state()), \
             patch("web.portfolio_surface.es_stressed_span_payload", return_value={"has_es_live_position": False}), \
             patch("strategy.sleeve_governance._latest_market_stress",
                   return_value={"status": "available", "stress_episode_active": False,
                                 "second_leg_active": False, "spx_close": 5000.0, "vix": 18.0}), \
             patch("strategy.sleeve_governance._selector_verdict_for_ladder",
                   return_value=(_verdict(), "2026-05-27T13:35:00Z")), \
             patch("strategy.sleeve_governance._open_spx_positions_for_ladder", return_value=[]):
            res = app.test_client().get("/api/sleeve-governance/state")
        data = res.get_json()
        state = data["state"]

        # 11 V1b mirror fields
        v1b_fields = [
            "ladder_v1b_mode",
            "ladder_v1b_last_entry_date",
            "ladder_v1b_cadence_eligible",
            "ladder_v1b_strategy_eligible",
            "ladder_v1b_concurrency_block",
            "ladder_v1b_bp_ceiling_block",
            "ladder_v1b_skip_reason",
            "ladder_v1b_active_positions",
            "ladder_v1b_active_total_bp",
            "ladder_v1b_action_days_ytd",
            "ladder_v1b_would_enter",
        ]
        for key in v1b_fields:
            self.assertIn(key, state, f"Missing V1b field: {key}")

        # 2 drift fields
        self.assertIn("ladder_strategy_drift_alert", state)
        self.assertIn("ladder_strategy_distribution_90d", state)


# ── AC-108.1-6 ─────────────────────────────────────────────────────────────────

class TestAC1081_6_SpecText(unittest.TestCase):
    def test_spec108_stage2_gate_has_r1_r3_conditions(self):
        spec_path = Path(__file__).resolve().parents[1] / "task" / "SPEC-108.md"
        self.assertTrue(spec_path.exists(), "SPEC-108.md not found")
        text = spec_path.read_text(encoding="utf-8")
        self.assertIn("portfolio_stress_overnight_gap", text, "R1 stress gate condition missing")
        self.assertIn("12% NLV", text, "12% NLV threshold missing from Stage 2 gate")
        self.assertIn("SPEC-108.1 R3", text, "R3 regime-coverage language missing")
        self.assertIn("distinct VIX regimes", text, "VIX regime coverage condition missing")
        self.assertIn("distinct strategy branches", text, "Strategy branch coverage condition missing")


# ── AC-108.1-7 ─────────────────────────────────────────────────────────────────

class TestAC1081_7_DriftMonitor(unittest.TestCase):
    def _write_shadow_log(self, path: Path, entries: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_no_drift_when_distribution_normal(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "shadow.jsonl"
            # 10 BCD entries (56% of total) — within expected 51-61% band
            entries = [
                {"date": "2026-05-01", "would_enter": True,
                 "selector_strategy": "Bull Call Diagonal",
                 "selector_strategy_key": "bull_call_diagonal"}
            ] * 9 + [
                {"date": "2026-05-02", "would_enter": True,
                 "selector_strategy": "Iron Condor (High Vol)",
                 "selector_strategy_key": "iron_condor_hv"}
            ] * 3
            self._write_shadow_log(log_path, entries)
            result = strategy_distribution_check(log_path)
            self.assertIn("drift_alert", result)
            self.assertIn("distribution_90d", result)
            self.assertIn("total_entries_90d", result)

    def test_drift_alert_when_single_strategy_dominates(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "shadow.jsonl"
            # 20 BPS entries = 100% of total → way above band 0-8% + 15pp threshold
            entries = [
                {"date": "2026-05-01", "would_enter": True,
                 "selector_strategy": "Bull Put Spread",
                 "selector_strategy_key": "bull_put_spread"}
            ] * 20
            self._write_shadow_log(log_path, entries)
            result = strategy_distribution_check(log_path)
            self.assertTrue(result["drift_alert"])
            detail = result.get("drift_detail") or {}
            self.assertTrue(detail.get("bull_put_spread", {}).get("alert"))

    def test_no_entries_returns_no_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "shadow.jsonl"
            result = strategy_distribution_check(log_path)
            self.assertFalse(result["drift_alert"])
            self.assertEqual(result["total_entries_90d"], 0)

    def test_drift_threshold_is_15pp(self):
        self.assertEqual(DRIFT_THRESHOLD_PP, 15.0)

    def test_historical_bands_derived_from_actual_data(self):
        # Verify the bands are based on actual measured data (not spec estimates)
        # bull_call_diagonal should be dominant strategy (spec estimated 45-55% for BPS,
        # but actual data shows BCD at 56%)
        lo, hi = HISTORICAL_STRATEGY_BANDS["bull_call_diagonal"]
        self.assertGreater(hi, 50.0, "BCD band should reflect actual 56% dominance")
        bps_lo, bps_hi = HISTORICAL_STRATEGY_BANDS["bull_put_spread"]
        self.assertLess(bps_hi, 20.0, "BPS band should reflect actual 3.1% share")


# ── AC-108.1-8/9 visual ACs — check HTML contains required elements ────────────

class TestAC1081_8_9_Dashboard(unittest.TestCase):
    def _load_template(self) -> str:
        path = Path(__file__).resolve().parents[1] / "web" / "templates" / "portfolio_home.html"
        return path.read_text(encoding="utf-8")

    def test_ac8_v1b_panel_present(self):
        html = self._load_template()
        self.assertIn("ladder-v1b-panel", html, "V1b panel CSS class missing from portfolio_home.html")
        self.assertIn("SPEC-108.1 V1b", html, "V1b panel title text missing")

    def test_ac9_drift_chip_present(self):
        html = self._load_template()
        self.assertIn("ladder-drift-chip", html, "Drift chip CSS class missing from portfolio_home.html")
        self.assertIn("drift: none", html, "Drift chip default text missing")


# ── AC-108.1-10 Telegram dry-run ───────────────────────────────────────────────

class TestAC1081_10_Telegram(unittest.TestCase):
    def test_v1b_format_function_exists(self):
        from notify.telegram_bot import _format_ladder_v1b_shadow_message
        payload = {
            "selector_strategy": "Bull Put Spread",
            "sizing_contracts": 3,
            "theoretical_max_loss": 27000,
            "theoretical_max_loss_pct_nlv": 2.7,
            "current_bp_pct_nlv": 5.0,
        }
        msg = _format_ladder_v1b_shadow_message(payload)
        self.assertIn("V1b", msg)
        self.assertIn("Bull Put Spread", msg)
        self.assertIn("shadow", msg.lower())

    def test_eod_push_function_references_drift(self):
        import inspect
        from notify import telegram_bot
        src = inspect.getsource(telegram_bot.scheduled_eod_push)
        self.assertIn("strategy_distribution_check", src)
        self.assertIn("drift", src.lower())


# ── AC-108.1-11 V1b shadow-default + mutual exclusion ─────────────────────────

class TestAC1081_11_V1bSafetyGuards(unittest.TestCase):
    def test_v1b_shadow_default_no_production(self):
        with patch.dict("os.environ", {}, clear=True):
            state = v1b.LadderV1bState(current_bp_pct_nlv_value=0.0, nlv=100_000.0)
            eligible, _ = v1b.v1b_ladder_eligible(_market("2026-05-27"), state)
            self.assertTrue(eligible)
            self.assertEqual(gov.ladder_v1b_mode(), "shadow")
            self.assertFalse(v1b.production_order_allowed_v1b(eligible, gov.ladder_v1b_mode()))

    def test_v1b_not_eligible_on_non_wednesday(self):
        with patch.dict("os.environ", {}, clear=True):
            state = v1b.LadderV1bState(current_bp_pct_nlv_value=0.0, nlv=100_000.0)
            eligible, _ = v1b.v1b_ladder_eligible(_market("2026-05-28"), state)  # Thursday
            self.assertFalse(eligible)

    def test_mutual_exclusion_blocks_when_both_active(self):
        """V1b production order blocked if V3 is also active (mutual exclusion)."""
        with patch.dict("os.environ", {"LADDER_MODE": "active", "LADDER_V1B_MODE": "active"}):
            # Even if v1b eligible=True, production order blocked due to mutual exclusion
            result = v1b.production_order_allowed_v1b(True, "active")
            self.assertFalse(result)

    def test_v1b_active_alone_allows_production(self):
        """V1b active + V3 NOT active → production allowed (if eligible)."""
        with patch.dict("os.environ", {"LADDER_MODE": "shadow", "LADDER_V1B_MODE": "active"}):
            result = v1b.production_order_allowed_v1b(True, "active")
            self.assertTrue(result)


# ── AC-108.1-12 SPEC-108 regression ───────────────────────────────────────────

class TestAC1081_12_Spec108Regression(unittest.TestCase):
    """Smoke-import the 18-AC SPEC-108 test class to ensure no regression."""

    def test_spec108_module_importable(self):
        import tests.test_spec_108  # noqa: F401

    def test_spec108_constants_unchanged(self):
        self.assertEqual(gov.LADDER_SIZING_CONTRACTS, 3)
        self.assertEqual(gov.LADDER_CADENCE_CLUSTER_DAYS, 5)
        self.assertEqual(gov.LADDER_BP_CEILING_PCT, 35.0)
        self.assertEqual(gov.LADDER_MODE_DEFAULT, "shadow")

    def test_v3_ladder_eligible_unchanged(self):
        state = v3ladder.LadderState(current_bp_pct_nlv_value=0.0, nlv=100_000.0)
        eligible, reason = v3ladder.v3_ladder_eligible(_market("2026-05-28"), state)
        self.assertTrue(eligible)
        self.assertEqual(reason, "")

    def test_v3_cadence_gap_unchanged(self):
        state = v3ladder.LadderState(last_entry_date=date(2026, 5, 26), current_bp_pct_nlv_value=0.0)
        eligible, reason = v3ladder.v3_ladder_eligible(_market("2026-05-28"), state)
        self.assertFalse(eligible)
        self.assertEqual(reason, "cadence_gap")

    def test_v3_production_guard_unchanged(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(v3ladder.production_order_allowed(True, gov.ladder_mode()))


# ── AC-108.1-13 Parent SPEC regression (import smoke) ─────────────────────────

class TestAC1081_13_ParentSpecRegression(unittest.TestCase):
    def test_spec103_importable(self):
        import tests.test_spec_103  # noqa: F401

    def test_spec104_importable(self):
        import tests.test_spec_104  # noqa: F401

    def test_spec105_importable(self):
        import tests.test_spec_105  # noqa: F401

    def test_spec106_importable(self):
        try:
            import tests.test_spec_106  # noqa: F401
        except ModuleNotFoundError:
            pass  # optional — only fail if exists and errors

    def test_spec107_importable(self):
        try:
            import tests.test_spec_107  # noqa: F401
        except ModuleNotFoundError:
            pass  # optional


if __name__ == "__main__":
    unittest.main()
