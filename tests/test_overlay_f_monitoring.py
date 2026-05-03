import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from strategy.overlay import OverlayDecision, append_overlay_f_log


class OverlayFMonitoringTests(unittest.TestCase):
    def test_shadow_log_schema_and_alert_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "overlay_f_shadow.jsonl"
            alert_path = Path(tmp) / "overlay_f_alert_latest.txt"
            decision = OverlayDecision(
                mode="shadow",
                would_fire=True,
                effective_factor=1.0,
                rationale="Overlay-F fires",
                idle_bp_pct=0.82,
                sg_count=1,
            )
            with patch("strategy.overlay._SHADOW_LOG", log_path), patch("strategy.overlay._ALERT_LATEST", alert_path):
                append_overlay_f_log(date="2026-05-03", strategy="iron_condor_hv", vix=24.5, decision=decision)

            row = json.loads(log_path.read_text().strip())
            for key in ("date", "strategy", "vix", "idle_bp_pct", "sg_count", "mode", "effective_factor", "rationale"):
                self.assertIn(key, row)
            self.assertEqual(row["mode"], "shadow")
            self.assertEqual(row["effective_factor"], 1.0)
            latest = json.loads(alert_path.read_text())
            self.assertEqual(latest["date"], "2026-05-03")

    def test_no_log_when_decision_does_not_fire(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "overlay_f_shadow.jsonl"
            alert_path = Path(tmp) / "overlay_f_alert_latest.txt"
            decision = OverlayDecision(
                mode="shadow",
                would_fire=False,
                effective_factor=1.0,
                rationale="Overlay-F blocked",
                idle_bp_pct=0.2,
                sg_count=3,
            )
            with patch("strategy.overlay._SHADOW_LOG", log_path), patch("strategy.overlay._ALERT_LATEST", alert_path):
                append_overlay_f_log(date="2026-05-03", strategy="iron_condor_hv", vix=24.5, decision=decision)

            self.assertFalse(log_path.exists())
            self.assertFalse(alert_path.exists())


if __name__ == "__main__":
    unittest.main()
