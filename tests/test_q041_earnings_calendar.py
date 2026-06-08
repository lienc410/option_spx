"""SPEC-115 Phase B — AC-1/2/13: earnings calendar + trading-day arithmetic."""
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import strategy.q041_earnings_calendar as cal
from strategy.q041_earnings_calendar import get_next_earnings_date, _coerce_date
from notify.q041_t3_earnings_check import trading_days_until


class TestAC1_EarningsCalendar(unittest.TestCase):
    def _mock_ticker(self, earnings_value):
        m = MagicMock()
        m.calendar = {"Earnings Date": earnings_value}
        return m

    def test_ac1_future_date_returned(self):
        future = date.today() + timedelta(days=20)
        with patch("yfinance.Ticker", return_value=self._mock_ticker([future])):
            result = get_next_earnings_date("JPM")
        self.assertEqual(result, future)

    def test_ac1_stale_past_date_returns_none(self):
        past = date.today() - timedelta(days=10)
        with patch("yfinance.Ticker", return_value=self._mock_ticker([past])):
            result = get_next_earnings_date("COST")
        self.assertIsNone(result)

    def test_ac1_empty_calendar_returns_none(self):
        m = MagicMock(); m.calendar = {}
        with patch("yfinance.Ticker", return_value=m):
            self.assertIsNone(get_next_earnings_date("COST"))

    def test_ac1_yfinance_error_returns_none(self):
        with patch("yfinance.Ticker", side_effect=RuntimeError("network")), \
             patch.object(cal, "_emit_alert"):
            self.assertIsNone(get_next_earnings_date("JPM"))

    def test_coerce_date_variants(self):
        self.assertEqual(_coerce_date(date(2026, 7, 14)), date(2026, 7, 14))
        self.assertEqual(_coerce_date(datetime(2026, 7, 14, 9, 30)), date(2026, 7, 14))
        self.assertEqual(_coerce_date("2026-07-14"), date(2026, 7, 14))
        self.assertIsNone(_coerce_date(None))
        self.assertIsNone(_coerce_date("not-a-date"))


class TestAC2_TradingDaysUntil(unittest.TestCase):
    def test_ac2_t_minus_3_arithmetic(self):
        # asof Thu 2026-07-09 → earn Tue 2026-07-14: Fri=1, Mon=2, Tue=3
        self.assertEqual(trading_days_until(date(2026, 7, 14), date(2026, 7, 9)), 3)

    def test_same_day_zero(self):
        self.assertEqual(trading_days_until(date(2026, 7, 14), date(2026, 7, 14)), 0)

    def test_past_is_negative(self):
        # earn yesterday-trading-day → -1 (T+1 check)
        self.assertEqual(trading_days_until(date(2026, 7, 13), date(2026, 7, 14)), -1)

    def test_skips_holiday(self):
        # 2026-07-03 is observed July 4 holiday; from 2026-07-02 (Thu) to 2026-07-06 (Mon):
        # 7/3 holiday skip, 7/4-5 weekend, 7/6 Mon = 1 trading day
        self.assertEqual(trading_days_until(date(2026, 7, 6), date(2026, 7, 2)), 1)


class TestAC13_CacheRefresh(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.tmpdir.name) / "cal.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ac13_refresh_writes_cache(self):
        future = date.today() + timedelta(days=15)
        def fake_next(sym):
            return future if sym == "COST" else None
        with patch.object(cal, "CACHE_PATH", self.cache_path), \
             patch.object(cal, "get_next_earnings_date", side_effect=fake_next):
            result = cal.refresh_cache()
        self.assertTrue(self.cache_path.exists())
        self.assertEqual(result["COST"], future.isoformat())
        self.assertIsNone(result["JPM"])
        self.assertIn("refreshed_at", result)
        # round-trip via load_cache
        with patch.object(cal, "CACHE_PATH", self.cache_path):
            loaded = cal.load_cache()
        self.assertEqual(loaded["COST"], future.isoformat())


if __name__ == "__main__":
    unittest.main()
