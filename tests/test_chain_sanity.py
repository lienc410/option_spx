"""SPEC-114 Part A — chain sanity unit tests.

AC-1: evaluate_day on known-good data → all OK, no alert
AC-2: evaluate_day with missing SPX/QQQ → S1 fail, alert fires
AC-3: evaluate_day on non-trading day → skipped, no alert
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd

import research.q041.daily_chain_sanity as sanity
from research.q041.daily_chain_sanity import (
    SanityRecord, evaluate_day, _is_trading_day,
    N_WHITELIST, S3_IV_MIN_PCT, S2_LOW_FACTOR, S2_HIGH_FACTOR,
)
from research.q041.whitelist import WHITELIST


def _make_chain_df(n_rows: int = 100, iv_null_frac: float = 0.0) -> pd.DataFrame:
    import numpy as np
    n = n_rows
    df = pd.DataFrame({
        "symbol": ["SPX"] * n,
        "option_type": ["put"] * n,
        "delta": [0.40] * n,   # all in 0.25–0.75 band
        "iv": [0.20] * int(n * (1 - iv_null_frac)) + [None] * int(n * iv_null_frac),
    })
    return df


class TestTradingDayHelper(unittest.TestCase):
    def test_weekend_not_trading(self):
        self.assertFalse(_is_trading_day(date(2026, 6, 7)))  # Sunday
        self.assertFalse(_is_trading_day(date(2026, 6, 6)))  # Saturday

    def test_weekday_trading(self):
        self.assertTrue(_is_trading_day(date(2026, 6, 4)))   # Thursday

    def test_holiday_not_trading(self):
        self.assertFalse(_is_trading_day(date(2026, 5, 25))) # Memorial Day


class TestAC3_NonTradingDay(unittest.TestCase):
    def test_non_trading_day_returns_skipped(self):
        import logging
        log = logging.getLogger("test")
        rec = evaluate_day(date(2026, 5, 25), force=False, log=log)
        self.assertIn("skipped:non_trading_day", rec.notes)
        self.assertFalse(rec.alert_fired)
        self.assertEqual(rec.s1_present, 0)


class TestAC1_AllOK(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_good_day(self, day: date) -> None:
        """Create parquet files for all 17 whitelist symbols with clean data."""
        day_dir = self.tmp / day.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)
        for sym in WHITELIST:
            fname = sym.lstrip("/").replace("/", "_") + ".parquet"
            df = pd.DataFrame({
                "symbol": [sym] * 100,
                "delta": [0.40] * 100,
                "iv": [0.20] * 100,
            })
            df.to_parquet(day_dir / fname, index=False)
        # _underlying.parquet with 17 symbols
        under = pd.DataFrame({"symbol": list(WHITELIST)})
        under.to_parquet(day_dir / "_underlying.parquet", index=False)

    def test_ac1_all_symbols_present_no_alert(self):
        import logging
        log = logging.getLogger("test")
        day = date(2026, 6, 4)
        self._make_good_day(day)
        # Patch prior-days to have same row count (for S2 median)
        for d_offset in range(1, 8):
            prior = date(2026, 6, 4 - d_offset) if d_offset < 4 else date(2026, 5, 28)
            self._make_good_day(prior)

        with patch.object(sanity, "SCHWAB_ROOT", self.tmp):
            rec = evaluate_day(day, force=False, log=log)

        self.assertEqual(rec.s1_present, N_WHITELIST)
        self.assertEqual(rec.s1_missing, [])
        self.assertEqual(rec.s2_anomaly_count, 0)
        self.assertIsNotNone(rec.s3_iv_completeness_pct)
        self.assertGreaterEqual(rec.s3_iv_completeness_pct, S3_IV_MIN_PCT)
        self.assertEqual(rec.s4_eod_present, N_WHITELIST)
        self.assertFalse(rec.alert_fired)


class TestAC2_MissingSymbols(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ac2_missing_spx_qqq_triggers_alert(self):
        import logging
        log = logging.getLogger("test")
        day = date(2026, 5, 12)
        day_dir = self.tmp / day.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)
        # Write all symbols EXCEPT SPX and QQQ
        for sym in WHITELIST:
            if sym in ("SPX", "QQQ"):
                continue
            fname = sym.lstrip("/").replace("/", "_") + ".parquet"
            df = pd.DataFrame({"symbol": [sym]*50, "delta": [0.40]*50, "iv": [0.20]*50})
            df.to_parquet(day_dir / fname, index=False)

        with patch.object(sanity, "SCHWAB_ROOT", self.tmp):
            rec = evaluate_day(day, force=True, log=log)  # force to allow May 12

        self.assertEqual(rec.s1_present, N_WHITELIST - 2)
        self.assertIn("SPX", rec.s1_missing)
        self.assertIn("QQQ", rec.s1_missing)
        self.assertTrue(rec.alert_fired)

    def test_ac2_alert_text_contains_missing_symbols(self):
        from research.q041.daily_chain_sanity import _build_alert
        rec = SanityRecord(
            date="2026-05-12",
            s1_present=15, s1_total=17, s1_missing=["QQQ", "SPX"],
            s2_anomaly_count=0, s2_anomalies=[],
            s3_iv_completeness_pct=100.0,
            s4_eod_present=17, s4_eod_total=17,
            alert_fired=True, notes="",
        )
        alert = _build_alert(rec)
        self.assertIn("SPX", alert)
        self.assertIn("QQQ", alert)
        self.assertIn("标的缺失", alert)  # SPEC-136：S1 代号移出主文案


class TestReportFormat(unittest.TestCase):
    def test_report_format_all_ok(self):
        from research.q041.daily_chain_sanity import _build_report
        rec = SanityRecord(
            date="2026-06-04",
            s1_present=17, s1_total=17, s1_missing=[],
            s2_anomaly_count=0, s2_anomalies=[],
            s3_iv_completeness_pct=100.0,
            s4_eod_present=17, s4_eod_total=17,
            alert_fired=False, notes="",
        )
        report = _build_report(rec)
        self.assertIn("📋 期权链数据体检", report)  # SPEC-136：主文案零内部代号
        self.assertIn("17/17", report)
        self.assertIn("✅", report)
        self.assertNotIn("❌", report)


if __name__ == "__main__":
    unittest.main()
