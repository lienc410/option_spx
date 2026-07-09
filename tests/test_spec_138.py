"""SPEC-138 — 缺轨污染修复 + 门在降级分母开火.

F3 (headline)  : rail_aware_nlv_change — 缺轨 fixture 不出 >20% 假跌 + 口径标注；
                 全轨 fixture 与 legacy combined 数学 bit-identical。
F4 (governance): cash/exposure 门携 rail_complete；缺轨降 advisory，不出硬红门；
                 全轨 bit-identical。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from web.portfolio_surface import rail_aware_nlv_change


def _row(date_s: str, schwab: float, etrade: float) -> dict:
    """A FULL daily-snapshot row (both rails present)."""
    return {
        "date": date_s,
        "combined_nlv": round(schwab + etrade, 2),
        "partial_accounts": [],
        "accounts": {"schwab": {"nlv": schwab}, "etrade": {"nlv": etrade}},
    }


# 三个锚：YTD(1/02) · MTD(7/01) · prev(7/07)；今天 = 7/08
RECORDS = [
    _row("2026-01-02", 80_000.0, 40_000.0),   # combined 120k — YTD anchor
    _row("2026-07-01", 100_000.0, 50_000.0),  # combined 150k — MTD anchor
    _row("2026-07-07", 100_000.0, 50_000.0),  # combined 150k — prev day
]
TODAY = "2026-07-08"


class F3FullRailBitIdentical(unittest.TestCase):
    """全轨 fixture → 数值与 legacy combined 数学一致（零行为变更）。"""

    def test_full_rail_matches_legacy_combined_math(self) -> None:
        today = {"schwab": 101_000.0, "etrade": 51_000.0}
        combined = 152_000.0
        d = rail_aware_nlv_change(RECORDS, TODAY, today,
                                  today_combined=combined, flows=[])
        self.assertEqual(d["status"], "available")
        self.assertTrue(d["rail_complete"])
        self.assertIsNone(d["rail_caption"])
        # legacy: combined vs combined anchors
        self.assertEqual(d["today_nlv"], 152_000.0)
        self.assertEqual(d["prev_nlv"], 150_000.0)
        self.assertEqual(d["change_dollars"], 2_000.0)
        self.assertEqual(d["change_pct"], round(2_000 / 150_000 * 100, 3))   # 1.333
        self.assertEqual(d["mtd_pct"], round(2_000 / 150_000 * 100, 2))       # 1.33
        self.assertEqual(d["ytd_pct"], round(32_000 / 120_000 * 100, 2))      # 26.67
        self.assertEqual(d["source_label"], "Live · Schwab+ETrade")
        # no flows → adj == raw
        self.assertEqual(d["mtd_adj_pct"], d["mtd_pct"])
        self.assertEqual(d["ytd_adj_pct"], d["ytd_pct"])


class F3RailGapNoFakeDrop(unittest.TestCase):
    """缺轨 fixture（E-Trade 缺席）→ 头条不出 >20% 假跌 + 口径标注。"""

    def test_missing_etrade_uses_same_scope_no_fake_crash(self) -> None:
        today = {"schwab": 101_000.0, "etrade": 0.0}   # E-Trade token expired
        combined = 101_000.0                            # schwab-only live sum
        d = rail_aware_nlv_change(RECORDS, TODAY, today,
                                  today_combined=combined, flows=[])
        self.assertEqual(d["status"], "available")
        self.assertFalse(d["rail_complete"])
        self.assertIsNotNone(d["rail_caption"])
        self.assertIn("E-Trade", d["rail_caption"])
        self.assertIn("Schwab", d["rail_caption"])
        # 同口径：schwab 101k vs schwab 100k → +1.0%，绝非 cross-scope 的 -32.67%
        self.assertEqual(d["change_pct"], 1.0)
        self.assertLess(abs(d["change_pct"]), 20.0)          # 不出 >20% 假跌
        self.assertEqual(d["mtd_pct"], 1.0)                  # 101k vs 100k schwab
        self.assertEqual(d["ytd_pct"], round(21_000 / 80_000 * 100, 2))  # 26.25
        # cross-scope 的假跌值必须没出现
        cross = round((101_000 - 150_000) / 150_000 * 100, 3)   # -32.667
        self.assertNotEqual(d["change_pct"], cross)
        self.assertEqual(d["today_nlv"], 101_000.0)          # 只显示在轨的 schwab
        self.assertEqual(d["source_label"], "Live · Schwab")

    def test_no_history_and_first_day(self) -> None:
        self.assertEqual(rail_aware_nlv_change([], TODAY, {"schwab": 1},
                                               today_combined=1)["status"],
                         "no_history")
        only_today = rail_aware_nlv_change(
            [_row("2026-07-08", 1.0, 1.0)], TODAY, {"schwab": 1, "etrade": 1},
            today_combined=2.0)
        self.assertEqual(only_today["status"], "first_day")


if __name__ == "__main__":
    unittest.main()
