from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from web import server as server_mod
from web.server import app


class Spec092Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.client = app.test_client()
        self.orig_log_file = server_mod._Q019_SETTLING_LOG_FILE
        server_mod._Q019_SETTLING_LOG_FILE = Path(self.tmpdir.name) / "q019_settling_log.jsonl"

    def tearDown(self) -> None:
        server_mod._Q019_SETTLING_LOG_FILE = self.orig_log_file

    def test_ac1_flip_days_endpoint_filters_changed_rows(self) -> None:
        rows = [
            {
                "date": "2026-05-12",
                "vix_signal1": 24.3,
                "rec_signal1": "bull_put_spread",
                "vix_signal2": 21.8,
                "rec_signal2": "iron_condor",
                "elapsed_min": 47,
                "changed": True,
            },
            {
                "date": "2026-05-13",
                "vix_signal1": 18.1,
                "rec_signal1": "bull_put_spread",
                "vix_signal2": 18.0,
                "rec_signal2": "bull_put_spread",
                "elapsed_min": 60,
                "changed": False,
            },
        ]
        server_mod._Q019_SETTLING_LOG_FILE.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        res = self.client.get("/api/q019/flip-days")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["date"], "2026-05-12")
        self.assertEqual(payload[0]["rec_signal1"], "BPS")
        self.assertEqual(payload[0]["rec_signal2"], "IC")
        self.assertEqual(payload[0]["elapsed_min"], 47)

    def test_ac1_endpoint_fails_soft_when_missing_or_empty(self) -> None:
        res_missing = self.client.get("/api/q019/flip-days")
        self.assertEqual(res_missing.status_code, 200)
        self.assertEqual(res_missing.get_json(), [])

        server_mod._Q019_SETTLING_LOG_FILE.write_text("", encoding="utf-8")
        res_empty = self.client.get("/api/q019/flip-days")
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(res_empty.get_json(), [])

    def test_ac2_to_ac5_backtest_page_includes_toggle_overlay_surface(self) -> None:
        page = self.client.get("/backtest")
        self.assertEqual(page.status_code, 200)
        text = page.get_data(as_text=True)
        self.assertIn("Show Q019 VIX Flip Days", text)
        self.assertIn("/api/q019/flip-days", text)
        self.assertIn("Q019 VIX Flip Day (Signal changed)", text)
        self.assertIn("Signal 1 (open): VIX", text)
        self.assertIn("Signal 2 (stable): VIX", text)
        self.assertIn("toggleQ019FlipDays", text)
        self.assertIn("setSpxOverlay('vix',  this)", text)


if __name__ == "__main__":
    unittest.main()
