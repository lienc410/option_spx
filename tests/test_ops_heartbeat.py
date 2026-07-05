"""SPEC-117.6 / F-1 follow-up — ops heartbeat freshness rules.

The heartbeat's acceptance was integration-level (real Telegram alert on a
manufactured stale marker). These unit tests pin the _check_freshness rule
semantics so registry entries can rely on them: missing file is always a
violation; daily_26h / weekly_8d age cutoffs; trading_day skips non-trading
days entirely.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.ops_heartbeat import _check_freshness  # noqa: E402

ET = ZoneInfo("America/New_York")


class FreshnessRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.f = self.tmp / "marker"
        self.f.touch()
        # a Monday, so trading_day rules are active
        self.now = datetime(2026, 7, 6, 17, 30, tzinfo=ET)

    def _age(self, delta: timedelta):
        t = (self.now - delta).timestamp()
        os.utime(self.f, (t, t))

    def _spec(self, rule: str) -> dict:
        return {"path": str(self.f), "rule": rule}

    def test_missing_file_is_violation_for_every_rule(self):
        spec = {"path": str(self.tmp / "nope"), "rule": "daily_26h"}
        self.assertIn("missing output", _check_freshness(spec, self.now))
        spec["rule"] = "weekly_8d"
        self.assertIn("missing output", _check_freshness(spec, self.now))

    def test_daily_26h(self):
        self._age(timedelta(hours=25))
        self.assertIsNone(_check_freshness(self._spec("daily_26h"), self.now))
        self._age(timedelta(hours=27))
        self.assertIn(">26h old", _check_freshness(self._spec("daily_26h"), self.now))

    def test_weekly_8d(self):
        self._age(timedelta(days=7))
        self.assertIsNone(_check_freshness(self._spec("weekly_8d"), self.now))
        self._age(timedelta(days=9))
        self.assertIn(">8d old", _check_freshness(self._spec("weekly_8d"), self.now))

    def test_trading_day_skips_weekend(self):
        sunday = datetime(2026, 7, 5, 17, 30, tzinfo=ET)
        self._age(timedelta(days=3))
        self.assertIsNone(_check_freshness(self._spec("trading_day"), sunday))
        # but on a trading day, yesterday's mtime is a violation
        self.assertIn("stale output", _check_freshness(self._spec("trading_day"), self.now))


if __name__ == "__main__":
    unittest.main()
