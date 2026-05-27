import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import strategy.intraday_governance as gov
from signals.vix_regime import Regime


ET = ZoneInfo("America/New_York")


def _rec(
    *,
    strategy_key="bull_put_spread",
    strategy="Bull Put Spread",
    action="OPEN",
    ivp=48.0,
    vix=18.0,
    regime=Regime.NORMAL,
    rationale="test",
):
    return SimpleNamespace(
        strategy_key=strategy_key,
        strategy=SimpleNamespace(value=strategy),
        position_action=action,
        underlying="SPX",
        rationale=rationale,
        iv_snapshot=SimpleNamespace(iv_percentile=ivp),
        vix_snapshot=SimpleNamespace(vix=vix, regime=regime),
    )


class Spec107IntradayGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.state_path = self.data_dir / "state.json"
        self.log_path = self.data_dir / "log.jsonl"
        self.patches = [
            patch.object(gov, "DATA_DIR", self.data_dir),
            patch.object(gov, "STATE_PATH", self.state_path),
            patch.object(gov, "DECISION_LOG_PATH", self.log_path),
            patch.object(gov, "_telegram_alert", return_value=True),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _position(self):
        return {
            "status": "open",
            "account": "spx",
            "underlying": "SPX",
            "strategy_key": "bull_put_spread",
            "trade_id": "T1",
        }

    def test_entry_band_allows_bps_only_when_baseline_bps(self):
        dec = gov.evaluate_recommendation(
            _rec(ivp=48),
            now=datetime(2026, 5, 26, 10, 30, tzinfo=ET),
            position=None,
        )
        self.assertEqual(dec.hysteresis_state_new, "Bull Put Spread")
        self.assertEqual(dec.governed_strategy, "Bull Put Spread")
        self.assertTrue(dec.actionable)
        # SPEC-107 §A: hysteresis state is per-strategy (account|underlying|strategy),
        # not per-position. It must persist when new=BPS regardless of whether the
        # broker position is open yet — the broker opens downstream after the
        # actionable signal. Verifies AC7 12mo replay envelope match.
        persisted = json.loads(self.state_path.read_text())
        self.assertEqual(
            persisted["positions"],
            {"spx|SPX|bull_put_spread": {
                "state": "Bull Put Spread",
                **{k: v for k, v in persisted["positions"]["spx|SPX|bull_put_spread"].items() if k != "state"},
            }},
        )

    def test_hold_band_preserves_active_bps_state(self):
        key = "spx|SPX|bull_put_spread"
        self.state_path.write_text(json.dumps({"schema": 1, "positions": {key: {"state": "Bull Put Spread"}}}))
        rec = _rec(strategy_key="reduce_wait", strategy="Reduce / Wait", action="WAIT", ivp=36)
        dec = gov.evaluate_recommendation(
            rec,
            now=datetime(2026, 5, 26, 11, 0, tzinfo=ET),
            position=self._position(),
        )
        self.assertEqual(dec.hysteresis_state_prev, "Bull Put Spread")
        self.assertEqual(dec.hysteresis_state_new, "Bull Put Spread")
        self.assertEqual(dec.governed_strategy, "Bull Put Spread")
        self.assertFalse(dec.actionable)

    def test_upper_band_always_closes_to_wait(self):
        key = "spx|SPX|bull_put_spread"
        self.state_path.write_text(json.dumps({"schema": 1, "positions": {key: {"state": "Bull Put Spread"}}}))
        dec = gov.evaluate_recommendation(
            _rec(ivp=58),
            now=datetime(2026, 5, 26, 15, 30, tzinfo=ET),
            position=self._position(),
        )
        self.assertEqual(dec.hysteresis_state_new, "WAIT")
        self.assertEqual(dec.governed_position_action, "WAIT")
        self.assertTrue(dec.actionable)

    def test_lower_force_close_default_true(self):
        key = "spx|SPX|bull_put_spread"
        self.state_path.write_text(json.dumps({"schema": 1, "positions": {key: {"state": "Bull Put Spread"}}}))
        dec = gov.evaluate_recommendation(
            _rec(ivp=34),
            now=datetime(2026, 5, 26, 15, 30, tzinfo=ET),
            position=self._position(),
        )
        self.assertEqual(dec.hysteresis_state_new, "WAIT")
        self.assertTrue(dec.actionable)

    def test_lower_force_close_override_logs_alert_event(self):
        with patch.object(gov, "INTRADAY_HYS_LOWER_FORCE_CLOSE", False):
            gov.evaluate_recommendation(
                _rec(ivp=34),
                now=datetime(2026, 5, 26, 10, 30, tzinfo=ET),
                position=self._position(),
            )
        lines = [json.loads(line) for line in self.log_path.read_text().splitlines()]
        self.assertTrue(any(line.get("event") == "flag_override_detected" for line in lines))

    def test_corrupt_state_fails_safe_without_hysteresis(self):
        self.state_path.write_text("{not-json")
        dec = gov.evaluate_recommendation(
            _rec(ivp=48),
            now=datetime(2026, 5, 26, 10, 30, tzinfo=ET),
            position=self._position(),
        )
        self.assertTrue(dec.state_corrupt)
        self.assertEqual(dec.hysteresis_state_prev, "WAIT")
        self.assertEqual(dec.hysteresis_state_new, "WAIT")
        persisted = json.loads(self.state_path.read_text())
        self.assertEqual(persisted["positions"], {})

    def test_high_vol_regression_does_not_convert_to_bps(self):
        key = "spx|SPX|bull_put_spread"
        self.state_path.write_text(json.dumps({"schema": 1, "positions": {key: {"state": "Bull Put Spread"}}}))
        dec = gov.evaluate_recommendation(
            _rec(strategy_key="reduce_wait", strategy="Reduce / Wait", action="WAIT", ivp=45, regime=Regime.HIGH_VOL),
            now=datetime(2026, 5, 26, 15, 30, tzinfo=ET),
            position=self._position(),
        )
        self.assertNotEqual(dec.governed_strategy, "Bull Put Spread")

    def test_high_vol_synthetic_invariant_across_ivp_boundaries(self):
        key = "spx|SPX|bull_put_spread"
        for regime in (Regime.HIGH_VOL, "STRESS"):
            for ivp in (33, 35, 37, 42, 45, 50, 53, 57, 60):
                with self.subTest(regime=regime, ivp=ivp):
                    self.state_path.write_text(json.dumps({"schema": 1, "positions": {key: {"state": "Bull Put Spread"}}}))
                    dec = gov.evaluate_recommendation(
                        _rec(
                            strategy_key="iron_condor",
                            strategy="Iron Condor",
                            action="OPEN",
                            ivp=ivp,
                            regime=regime,
                        ),
                        now=datetime(2026, 5, 26, 15, 30, tzinfo=ET),
                        position=self._position(),
                    )
                    self.assertNotEqual(dec.governed_strategy, "Bull Put Spread")

    def test_bypass_classes_are_immediate_and_priority_wins(self):
        cases = [
            ("manual_override", {"manual_override": True}, 1, "manual_override"),
            ("broker_stop_loss", {"broker_stop_loss": True}, 2, "broker_stop_loss_or_lifecycle"),
            ("lifecycle_exit", {"lifecycle_exit": True}, 2, "broker_stop_loss_or_lifecycle"),
            ("spec_103_r5", {"spec_103_r5": True}, 3, "spec_103_hard_risk_daemon"),
            ("spec_103_r6", {"spec_103_r6": True}, 3, "spec_103_hard_risk_daemon"),
            ("selector_hard_exit", {"selector_hard_exit": True}, 4, "extreme_vol"),
            ("stale_data_failsafe", {"stale_data_failsafe": True}, 1, "manual_override"),
        ]
        for bypass_type, context, layer, name in cases:
            with self.subTest(bypass_type=bypass_type):
                dec = gov.evaluate_recommendation(
                    _rec(ivp=48),
                    now=datetime(2026, 5, 26, 11, 15, tzinfo=ET),
                    position=self._position(),
                    context=context,
                )
                self.assertTrue(dec.actionable)
                self.assertEqual(dec.bypass_type, bypass_type)
                self.assertEqual(dec.final_priority_layer, layer)
                self.assertEqual(dec.final_priority_name, name)

    def test_extreme_vol_bypass_is_immediate(self):
        dec = gov.evaluate_recommendation(
            _rec(ivp=48, vix=40.0, regime=Regime.HIGH_VOL),
            now=datetime(2026, 5, 26, 11, 15, tzinfo=ET),
            position=self._position(),
        )
        self.assertTrue(dec.actionable)
        self.assertEqual(dec.bypass_type, "extreme_vol")

    def test_scheduled_bars_regular_holiday_early_close_and_dst(self):
        regular = [b.strftime("%H:%M") for b in gov.scheduled_bars_for_day(date(2026, 5, 26))]
        self.assertEqual(regular, ["10:30", "15:30"])
        self.assertEqual(gov.scheduled_bars_for_day(date(2026, 12, 25)), [])
        early = [b.strftime("%H:%M") for b in gov.scheduled_bars_for_day(date(2026, 11, 27))]
        self.assertIn("10:30", early)
        self.assertIn("12:30", early)
        dst = gov.scheduled_bars_for_day(date(2026, 3, 9))
        self.assertTrue(dst)
        self.assertEqual(dst[0].tzinfo, ET)


if __name__ == "__main__":
    unittest.main()
