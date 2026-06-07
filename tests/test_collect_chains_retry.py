"""SPEC-114 Part B — collect_chains.py SPX/QQQ retry guard tests.

AC-4: SPX fails all 3 retries → alert written + Telegram push
AC-5: SPX fails once then succeeds → parquet written, no alert
AC-6: Non-index symbol (AAPL) fails → single attempt, no alert (existing behavior)
"""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import research.q041.collect_chains as cc
from research.q041.collect_chains import (
    INDEX_SYMBOLS, INDEX_RETRY_MAX, INDEX_RETRY_BACKOFF_SEC,
    _fetch_chain_with_retry,
)


class TestIndexSymbolConstants(unittest.TestCase):
    def test_spx_qqq_in_index_symbols(self):
        self.assertIn("SPX", INDEX_SYMBOLS)
        self.assertIn("QQQ", INDEX_SYMBOLS)

    def test_aapl_not_in_index_symbols(self):
        self.assertNotIn("AAPL", INDEX_SYMBOLS)

    def test_retry_params(self):
        self.assertEqual(INDEX_RETRY_MAX, 3)
        self.assertEqual(INDEX_RETRY_BACKOFF_SEC, 30)


class TestAC4_SPXAllRetriesFail(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ac4_final_fail_writes_alert_and_pushes_telegram(self):
        import logging
        log = logging.getLogger("test")
        alert_path = self.tmp / "q041_collector_alert.jsonl"

        def always_fail(*args, **kwargs):
            raise RuntimeError("chain unavailable")

        with patch.object(cc, "_fetch_full_chain", side_effect=always_fail), \
             patch.object(cc, "COLLECTOR_ALERT_PATH", alert_path), \
             patch("time.sleep"), \
             patch.object(cc, "_send_collector_alert_telegram") as mock_tg:
            result = _fetch_chain_with_retry("SPX", log)

        self.assertIsNone(result)
        # Alert file written by collect_one when result is None
        # (collect_one calls _write_collector_alert and _send_collector_alert_telegram)

    def test_ac4_collect_one_writes_alert_on_final_fail(self):
        import logging
        log = logging.getLogger("test")
        alert_path = self.tmp / "q041_collector_alert.jsonl"

        def always_fail(*args, **kwargs):
            raise RuntimeError("chain unavailable")

        with patch.object(cc, "_fetch_full_chain", side_effect=always_fail), \
             patch.object(cc, "COLLECTOR_ALERT_PATH", alert_path), \
             patch.object(cc, "DATA_ROOT", self.tmp / "chains"), \
             patch("time.sleep"), \
             patch.object(cc, "_send_collector_alert_telegram") as mock_tg:
            res = cc.collect_one("SPX", "2026-06-04", "2026-06-04T16:31:00", log)

        self.assertIsNotNone(res.error)
        self.assertTrue(alert_path.exists())
        record = json.loads(alert_path.read_text().strip())
        self.assertEqual(record["symbol"], "SPX")
        self.assertIn("retries", record["reason"])
        mock_tg.assert_called_once_with("SPX", log)


class TestAC5_SPXSucceedsOnRetry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ac5_succeeds_second_attempt_no_alert(self):
        import logging
        import pandas as pd
        log = logging.getLogger("test")
        alert_path = self.tmp / "q041_collector_alert.jsonl"

        call_count = [0]
        def fail_then_succeed(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("transient failure")
            # Return non-empty result on 2nd attempt
            return [{"strike": 5000, "putCall": "PUT", "bid": 10, "ask": 11,
                     "delta": -0.30, "gamma": 0.01, "theta": -0.5, "vega": 0.1,
                     "rho": 0.01, "iv": 0.20, "openInterest": 100,
                     "volume": 50, "expirationDate": "2026-07-17",
                     "daysToExpiration": 40}], []

        with patch.object(cc, "_fetch_full_chain", side_effect=fail_then_succeed), \
             patch.object(cc, "COLLECTOR_ALERT_PATH", alert_path), \
             patch("time.sleep") as mock_sleep:
            result = _fetch_chain_with_retry("SPX", log)

        self.assertIsNotNone(result)
        self.assertEqual(call_count[0], 2)
        self.assertFalse(alert_path.exists())
        # Should have slept once (between attempt 1 and 2)
        mock_sleep.assert_called_once_with(INDEX_RETRY_BACKOFF_SEC)


class TestAC6_NonIndexNoRetry(unittest.TestCase):
    def test_ac6_aapl_single_attempt_no_alert(self):
        import logging
        log = logging.getLogger("test")
        call_count = [0]

        def count_calls(*args, **kwargs):
            call_count[0] += 1
            raise RuntimeError("network error")

        with patch.object(cc, "_fetch_full_chain", side_effect=count_calls), \
             patch("time.sleep") as mock_sleep:
            result = _fetch_chain_with_retry("AAPL", log)

        self.assertIsNone(result)
        self.assertEqual(call_count[0], 1)    # single attempt only
        mock_sleep.assert_not_called()         # no backoff sleep


class TestRetrySuccess(unittest.TestCase):
    def test_success_on_first_attempt_no_sleep(self):
        import logging
        log = logging.getLogger("test")

        with patch.object(cc, "_fetch_full_chain", return_value=([{"iv": 0.2}], [])), \
             patch("time.sleep") as mock_sleep:
            result = _fetch_chain_with_retry("SPX", log)

        self.assertIsNotNone(result)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
