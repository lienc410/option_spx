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
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from web.portfolio_surface import rail_aware_nlv_change

import strategy.cash_budget_governance as cbg
import strategy.exposure as expo


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


def _cash(total, source, error=None):
    return {"total": total, "source": source, "error": error,
            "breakdown": {"schwab": {"raw_cash": total}}
            if source != "unavailable" else {}}


class F4CashBudgetGate(unittest.TestCase):
    """缺轨 fixture → cash 门降 advisory（不出红 verdict）+ staleness；
    全轨 fixture → 与现状裁决 bit-identical。"""

    def _eval(self, cash_data, open_cash):
        cand = {"strategy_key": "bull_call_diagonal", "debit_usd": 5_000.0}
        with patch.object(cbg, "get_current_liquid_cash", return_value=cash_data), \
             patch.object(cbg, "get_open_cash_collateral_total_usd",
                          return_value={"total": open_cash, "positions": []}):
            return cbg.evaluate_cash_collateral_budget(cand)

    def test_partial_rail_cap_breach_downgrades_to_advisory(self) -> None:
        # 缺轨：pool 105k → post 75k > 60%×105k=63k 本会硬 BLOCK
        r = self._eval(_cash(105_000.0, "partial", "etrade: token expired"), 70_000.0)
        self.assertTrue(r["accepted"])                 # 不 veto
        self.assertEqual(r["outcome"], "advisory")
        self.assertFalse(r["stats"]["rail_complete"])
        self.assertTrue(r["stats"]["degraded"])
        self.assertIn("数据降级", r["reason"])
        self.assertEqual(r["stats"]["cash_source"], "partial")

    def test_full_rail_same_numbers_still_pass_bit_identical(self) -> None:
        # 全轨：pool 152k → post 75k < 60%×152k=91.2k → accepted（现状行为）
        r = self._eval(_cash(152_000.0, "live"), 70_000.0)
        self.assertTrue(r["accepted"])
        self.assertNotIn("outcome", r)                 # 非 advisory 档
        self.assertEqual(r["reason"], "accepted")
        self.assertTrue(r["stats"]["rail_complete"])

    def test_full_rail_still_vetoes_real_breach(self) -> None:
        # 全轨真超限：post 100k > 91.2k → 仍硬 BLOCK（未被削弱）
        r = self._eval(_cash(152_000.0, "live"), 95_000.0)
        self.assertFalse(r["accepted"])                # rail-complete 仍 veto
        self.assertTrue(r["stats"]["rail_complete"])

    def test_f6_committed_cash_read_error_degrades_not_silent(self) -> None:
        """SPEC-138 F6：committed 现金读取失败（get_open_cash_collateral 返回
        error+total=0）不再被静默当 0 用（会 fail-OPEN 接受超预算单）——降 advisory。"""
        cand = {"strategy_key": "bull_call_diagonal", "debit_usd": 5_000.0}
        with patch.object(cbg, "get_current_liquid_cash",
                          return_value=_cash(152_000.0, "live")), \
             patch.object(cbg, "get_open_cash_collateral_total_usd",
                          return_value={"total": 0.0, "positions": [],
                                        "error": "positions read failed"}):
            r = cbg.evaluate_cash_collateral_budget(cand)
        self.assertTrue(r["accepted"])                 # 不 veto
        self.assertEqual(r["outcome"], "advisory")
        self.assertEqual(r["stats"]["open_cash_read_error"], "positions read failed")


class F4ExposureDegrade(unittest.TestCase):
    """缺轨 fixture → exposure 不因缩水分母翻'敞口已满'；全轨 bit-identical。"""

    def _eval(self, cash_tuple, fam_max_loss, debit):
        with patch.object(expo, "liquid_cash", return_value=cash_tuple), \
             patch.object(expo, "deployed_debit_capital", return_value=debit), \
             patch.object(expo, "family_open_exposure",
                          return_value={"family": "bcd",
                                        "family_open_max_loss_usd": fam_max_loss,
                                        "family_open_positions": []}):
            return expo.evaluate_exposure_degrade("bull_call_diagonal")

    def test_partial_rail_does_not_flip_to_degraded(self) -> None:
        # 全轨 25% (<30) 清白；缺轨压低分母 → 45.5% 本会误判 degraded
        r = self._eval((110_000.0, "partial"), 50_000.0, 0.0)
        self.assertFalse(r["degraded"])                # 不翻"敞口已满"
        self.assertFalse(r["rail_complete"])
        self.assertIsNone(r["copy"])                   # 无降级文案
        self.assertIn("现金轨不齐", r["note"])
        self.assertGreater(r["pct_of_pool"], 30.0)     # 同口径 pct 仍如实报（仅供参考）

    def test_full_rail_clean_pass_bit_identical(self) -> None:
        r = self._eval((200_000.0, "live"), 50_000.0, 0.0)
        self.assertFalse(r["degraded"])
        self.assertTrue(r["rail_complete"])
        self.assertEqual(r["pct_of_pool"], 25.0)

    def test_full_rail_real_degrade_still_fires(self) -> None:
        # 全轨真超阈：40% > 30 → 仍 degraded（未削弱）
        r = self._eval((125_000.0, "live"), 50_000.0, 0.0)
        self.assertTrue(r["degraded"])
        self.assertTrue(r["rail_complete"])
        self.assertIsNotNone(r["copy"])


class F4DecisionTraceFunding(unittest.TestCase):
    """trace 资金/敞口节点缺轨时 outcome ∈ {advisory, info}，绝不 veto。"""

    def test_partial_rail_funding_nodes_never_veto(self) -> None:
        from strategy import decision_trace as dt
        import strategy.capacity as cap
        cash = _cash(105_000.0, "partial", "etrade: token expired")
        with patch.object(cbg, "get_current_liquid_cash", return_value=cash), \
             patch.object(cbg, "get_open_cash_collateral_total_usd",
                          return_value={"total": 90_000.0, "positions": []}), \
             patch("strategy.state.read_all_positions", return_value={"positions": []}), \
             patch.object(cap, "used_defined_risk",
                          return_value={"used_usd": 0.0, "capacity_usd": 100_000.0,
                                        "pct": 0.0, "buffer_usd": 100_000.0,
                                        "positions": []}):
            nodes = dt.funding_trace("bull_call_diagonal")
        by_check = {n["check"]: n for n in nodes}
        # 缺轨时 cap 超限（90k > 60%×105k=63k）→ 本会 veto，现降 advisory
        self.assertEqual(by_check["cash_budget"]["outcome"], "advisory")
        self.assertEqual(by_check["family_exposure_degrade"]["outcome"], "advisory")
        # 全场资金/敞口节点：无一 veto
        self.assertTrue(all(n["outcome"] in {"advisory", "info", "pass"}
                            for n in nodes),
                        [(n["check"], n["outcome"]) for n in nodes])


if __name__ == "__main__":
    unittest.main()
