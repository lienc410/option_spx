from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import research.q041.daily_alignment_check as mod


def _schwab_rows() -> list[dict]:
    return [
        {
            "symbol": "AAPL",
            "option_type": "CALL",
            "expiry": "2026-05-04",
            "strike": 100.0,
            "volume": 10,
            "delta": 0.30,
            "iv": 25.0,
            "last": 2.01,
        },
        {
            "symbol": "AAPL",
            "option_type": "PUT",
            "expiry": "2026-05-04",
            "strike": 95.0,
            "volume": 5,
            "delta": -0.40,
            "iv": 30.0,
            "last": 1.50,
        },
        {
            "symbol": "AAPL",
            "option_type": "CALL",
            "expiry": "2026-05-11",
            "strike": 105.0,
            "volume": 1,
            "delta": 0.60,
            "iv": 20.0,
            "last": 3.00,
        },
        {
            "symbol": "AAPL",
            "option_type": "PUT",
            "expiry": "2026-05-11",
            "strike": 90.0,
            "volume": 0,
            "delta": -0.50,
            "iv": 18.0,
            "last": 0.75,
        },
    ]


def _massive_rows() -> list[dict]:
    return [
        {
            "symbol": "AAPL",
            "expiration_date": "2026-05-04",
            "contract_type": "call",
            "strike_price": 100.0,
            "day_close": 2.00,
        },
        {
            "symbol": "AAPL",
            "expiration_date": "2026-05-04",
            "contract_type": "put",
            "strike_price": 95.0,
            "day_close": 1.49,
        },
        {
            "symbol": "AAPL",
            "expiration_date": "2026-05-11",
            "contract_type": "call",
            "strike_price": 105.0,
            "day_close": 3.00,
        },
        {
            "symbol": "AAPL",
            "expiration_date": "2026-05-11",
            "contract_type": "put",
            "strike_price": 90.0,
            "day_close": 0.80,
        },
    ]


class Spec090Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.schwab_root = root / "q041_chains"
        self.massive_root = root / "q041_massive_snapshot"
        self.output_path = root / "q041_overlap_daily.jsonl"
        self.alert_state_path = root / "q041_overlap_alert_state.jsonl"

        self.orig_schwab_root = mod.SCHWAB_ROOT
        self.orig_massive_root = mod.MASSIVE_ROOT
        self.orig_output_path = mod.OUTPUT_PATH
        self.orig_alert_state_path = mod.ALERT_STATE_PATH

        mod.SCHWAB_ROOT = self.schwab_root
        mod.MASSIVE_ROOT = self.massive_root
        mod.OUTPUT_PATH = self.output_path
        mod.ALERT_STATE_PATH = self.alert_state_path

    def tearDown(self) -> None:
        mod.SCHWAB_ROOT = self.orig_schwab_root
        mod.MASSIVE_ROOT = self.orig_massive_root
        mod.OUTPUT_PATH = self.orig_output_path
        mod.ALERT_STATE_PATH = self.orig_alert_state_path

    def _write_day(self, day: str, *, schwab_rows: list[dict] | None, massive_rows: list[dict] | None) -> None:
        if schwab_rows is not None:
            day_dir = self.schwab_root / day
            day_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(schwab_rows).to_parquet(day_dir / "AAPL.parquet", index=False)
        if massive_rows is not None:
            day_dir = self.massive_root / day
            day_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(massive_rows).to_parquet(day_dir / "AAPL.parquet", index=False)

    def test_ac1_and_ac2_metrics_and_jsonl_append(self) -> None:
        self._write_day("2026-05-04", schwab_rows=_schwab_rows(), massive_rows=_massive_rows())

        rc = mod.run(day=date(2026, 5, 4), force=True, send_telegram=False, verbose=False)
        self.assertEqual(rc, 0)

        lines = self.output_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["date"], "2026-05-04")
        self.assertEqual(payload["m1_match_pct"], 100.0)
        self.assertEqual(payload["m4_deviation_pct"], 0.0)
        self.assertEqual(payload["m6_iv_completeness_pct"], 100.0)
        self.assertFalse(payload["alert_fired"])
        self.assertIn("m1=3/3", payload["notes"])

    def test_ac3_daily_report_format(self) -> None:
        self._write_day("2026-05-04", schwab_rows=_schwab_rows(), massive_rows=_massive_rows())

        sent: list[str] = []
        with patch.object(mod, "_send_telegram_message", side_effect=lambda text, _log: sent.append(text) or True):
            rc = mod.run(day=date(2026, 5, 4), force=True, send_telegram=True, verbose=False)

        self.assertEqual(rc, 0)
        self.assertEqual(len(sent), 1)
        self.assertIn("📊 Q041 数据对齐日报 2026-05-04", sent[0])
        self.assertIn("M1 key match:    100.0% ✅", sent[0])
        self.assertIn("M4 price dev:     0.0% ✅", sent[0])
        self.assertIn("M6 IV complete:  100.0% ✅", sent[0])

    def test_ac4_threshold_alert_and_same_day_dedupe(self) -> None:
        schwab_rows = _schwab_rows()
        schwab_rows[2]["iv"] = None
        schwab_rows[3]["iv"] = None
        massive_rows = _massive_rows()
        massive_rows.pop(2)
        self._write_day("2026-05-04", schwab_rows=schwab_rows, massive_rows=massive_rows)

        sent: list[str] = []
        with patch.object(mod, "_send_telegram_message", side_effect=lambda text, _log: sent.append(text) or True):
            rc1 = mod.run(day=date(2026, 5, 4), force=True, send_telegram=True, verbose=False)
            rc2 = mod.run(day=date(2026, 5, 4), force=True, send_telegram=True, verbose=False)

        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        self.assertEqual(len(sent), 3)
        self.assertIn("📊 Q041 数据对齐日报 2026-05-04", sent[0])
        self.assertIn("🚨 Q041 数据对齐告警 2026-05-04", sent[1])
        self.assertIn("M1 key match 66.7% < 95.0%", sent[1])
        self.assertIn("M6 IV complete 50.0% < 95.0%", sent[1])
        self.assertIn("📊 Q041 数据对齐日报 2026-05-04", sent[2])

    def test_ac5_missing_source_fail_soft_no_data_notice(self) -> None:
        self._write_day("2026-05-04", schwab_rows=_schwab_rows(), massive_rows=None)

        sent: list[str] = []
        with patch.object(mod, "_send_telegram_message", side_effect=lambda text, _log: sent.append(text) or True):
            rc = mod.run(day=date(2026, 5, 4), force=True, send_telegram=True, verbose=False)

        self.assertEqual(rc, 0)
        self.assertEqual(len(sent), 1)
        self.assertIn("Q041 数据对齐：今日无数据 2026-05-04", sent[0])
        payload = json.loads(self.output_path.read_text(encoding="utf-8").strip())
        self.assertIsNone(payload["m1_match_pct"])
        self.assertFalse(payload["alert_fired"])
        self.assertEqual(payload["notes"], "missing_data:massive")

    def test_ac6_weekend_guard_skips(self) -> None:
        rc = mod.run(day=date(2026, 5, 9), force=False, send_telegram=False, verbose=False)
        self.assertEqual(rc, 0)
        payload = json.loads(self.output_path.read_text(encoding="utf-8").strip())
        self.assertEqual(payload["notes"], "skipped:non_trading_day")


if __name__ == "__main__":
    unittest.main()
