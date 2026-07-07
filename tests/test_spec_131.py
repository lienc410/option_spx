"""SPEC-131 — 敞口感知推荐降级（PM ratify 2026-07-07，阈值 T=40%）.

AC coverage:
  阈值单测（±边界）                       → ThresholdTests
  分母不可用 fail-soft（照常推荐 + n/a）   → ThresholdTests
  推送走 gateway 且类别正确（ACTION→STATE）→ MorningPushTests
  晨报与推荐卡文案一致性（逐字同源）        → CopyConsistencyTests
  零信号逻辑变更（selector 输出 bit-identical）→ SelectorUntouchedTests

测试向量脚本生成；selector fixture 复用 test_spec_129 的 N×N×B 构造。
"""
from __future__ import annotations

import asyncio
import unittest
from dataclasses import asdict
from unittest.mock import AsyncMock, patch

import strategy.exposure as ex
from strategy.selector import select_strategy
from tests.test_spec_129 import _nnb_snapshots


def _patched_exposure(family_usd: float, cash: float | None, cash_source: str = "live"):
    """把 evaluate_exposure_degrade 的两个数据源钉到给定向量。"""
    fam = {"family": "bull_put_spread", "family_open_max_loss_usd": family_usd,
           "family_open_positions": [{"trade_id": "X", "max_loss_usd": family_usd}]}
    return (
        patch.object(ex, "family_open_exposure", return_value=fam),
        patch.object(ex, "liquid_cash", return_value=(cash, cash_source)),
    )


class ThresholdTests(unittest.TestCase):
    def test_at_and_above_threshold_degrades(self) -> None:
        cash = 500_000.0
        for frac in (0.40, 0.41, 0.5028):     # 含 7/7 实证比例
            fam = round(cash * frac, 2)
            p1, p2 = _patched_exposure(fam, cash)
            with p1, p2:
                out = ex.evaluate_exposure_degrade("bull_put_spread")
            self.assertTrue(out["degraded"], f"frac={frac}")
            self.assertAlmostEqual(out["pct_of_cash"], frac * 100, places=1)
            self.assertIn("条件满足，敞口已满", out["copy"])
            self.assertIn(f"${fam:,.0f}", out["copy"])           # 绝对值显式
            self.assertIn("≥ 40%", out["copy"])                   # 阈值显式
            self.assertIn("流动现金", out["copy"])                # 分母定义显式

    def test_below_threshold_not_degraded(self) -> None:
        cash = 500_000.0
        for frac in (0.399, 0.25, 0.0):
            p1, p2 = _patched_exposure(round(cash * frac, 2), cash)
            with p1, p2:
                out = ex.evaluate_exposure_degrade("bull_put_spread")
            self.assertFalse(out["degraded"], f"frac={frac}")
            self.assertIsNone(out["copy"])

    def test_denominator_unavailable_fails_soft(self) -> None:
        p1, p2 = _patched_exposure(200_000.0, None, "unavailable")
        with p1, p2:
            out = ex.evaluate_exposure_degrade("bull_put_spread")
        self.assertFalse(out["degraded"])
        self.assertIsNone(out["pct_of_cash"])
        self.assertIn("n/a", out["note"])         # 照常推荐 + 标注 n/a


class MorningPushTests(unittest.TestCase):
    """晨报：走 gateway apush；降级日 ACTION→STATE，文案置顶；未降级不变。"""

    def _run_scheduled_push(self, rec, deg_out):
        import notify.telegram_bot as bot_mod
        sent = {}

        async def _rec_apush(bot, chat_id, category, about, title, body, **kw):
            sent.update({"category": category, "about": about,
                         "title": title, "body": body})
            return True

        with patch.object(bot_mod, "is_trading_day", return_value=True), \
             patch.object(bot_mod, "get_recommendation", return_value=rec), \
             patch.object(bot_mod, "_safe_append_recommendation_event"), \
             patch("strategy.exposure.evaluate_exposure_degrade",
                   return_value=deg_out), \
             patch("notify.gateway.apush", side_effect=_rec_apush):
            asyncio.run(bot_mod.scheduled_push(AsyncMock(), "chat"))
        return sent

    def test_degraded_day_demotes_action_to_state(self) -> None:
        rec = select_strategy(*_nnb_snapshots(50.0))       # 正常路由 BPS
        self.assertEqual(rec.strategy_key, "bull_put_spread")
        copy = ex.degrade_copy("bull_put_spread", 210_000.0, 42.0)
        deg = {"degraded": True, "copy": copy, "note": None}
        sent = self._run_scheduled_push(rec, deg)
        self.assertEqual(sent["category"], "STATE")        # ACTION 降 STATE
        self.assertEqual(sent["about"], "新开仓")           # gateway 契约不变
        self.assertIn("条件满足，敞口已满", sent["title"])
        self.assertIn("非加仓号召", sent["body"])
        self.assertIn("$210,000", sent["body"])            # 绝对值进正文
        self.assertIn("≥ 40%", sent["body"])

    def test_normal_day_stays_action(self) -> None:
        rec = select_strategy(*_nnb_snapshots(50.0))
        deg = {"degraded": False, "copy": None, "note": None}
        sent = self._run_scheduled_push(rec, deg)
        self.assertEqual(sent["category"], "ACTION")
        self.assertIn("OPEN 候选", sent["title"])
        self.assertNotIn("敞口已满", sent["body"])

    def test_cash_na_day_appends_note_keeps_action(self) -> None:
        rec = select_strategy(*_nnb_snapshots(50.0))
        deg = {"degraded": False, "copy": None,
               "note": "敞口检查: 流动现金 n/a — 降级检查跳过（fail-soft，照常推荐）"}
        sent = self._run_scheduled_push(rec, deg)
        self.assertEqual(sent["category"], "ACTION")
        self.assertIn("n/a", sent["body"])


class CopyConsistencyTests(unittest.TestCase):
    def test_card_payload_and_push_share_one_copy_source(self) -> None:
        """推荐卡（/api/recommendation payload）与晨报正文的降级文案逐字一致
        （同源 exposure.degrade_copy）。"""
        rec = select_strategy(*_nnb_snapshots(50.0))
        cash, fam = 500_000.0, 210_000.0
        p1, p2 = _patched_exposure(fam, cash)

        # 卡片侧：真 evaluate（钉数据源），经 /api/recommendation 组装
        from web.server import app
        with p1, p2, patch("strategy.selector.get_recommendation", return_value=rec):
            payload = app.test_client().get("/api/recommendation").get_json()
        card = payload.get("exposure_degrade") or {}
        self.assertTrue(card.get("degraded"), payload.get("error"))
        expected = ex.degrade_copy("bull_put_spread", fam, fam / cash * 100)
        self.assertEqual(card["copy"], expected)

        # 晨报侧：同一 evaluate 输出进 body
        import notify.telegram_bot as bot_mod
        sent = {}

        async def _rec_apush(bot, chat_id, category, about, title, body, **kw):
            sent.update({"category": category, "body": body})
            return True

        p1b, p2b = _patched_exposure(fam, cash)
        with patch.object(bot_mod, "is_trading_day", return_value=True), \
             patch.object(bot_mod, "get_recommendation", return_value=rec), \
             patch.object(bot_mod, "_safe_append_recommendation_event"), \
             p1b, p2b, \
             patch("notify.gateway.apush", side_effect=_rec_apush):
            asyncio.run(bot_mod.scheduled_push(AsyncMock(), "chat"))
        self.assertEqual(sent["category"], "STATE")
        self.assertIn(expected, sent["body"])              # 逐字（HTML 转义前）


class SelectorUntouchedTests(unittest.TestCase):
    def test_selector_output_bit_identical_and_module_untouched(self) -> None:
        """零信号逻辑变更：降级评估前后 selector 输出完全一致；selector 源码
        零 exposure 耦合。"""
        snaps = _nnb_snapshots(50.0)
        rec_before = select_strategy(*snaps)
        before = asdict(rec_before)

        p1, p2 = _patched_exposure(300_000.0, 500_000.0)
        with p1, p2:
            ex.evaluate_exposure_degrade(rec_before.strategy_key)

        self.assertEqual(asdict(rec_before), before)       # 对象未被降级评估修改
        rec_after = select_strategy(*snaps)
        self.assertEqual(asdict(rec_after), before)        # 重算 bit-identical

        import inspect
        import strategy.selector as sel
        src = inspect.getsource(sel)
        for token in ("strategy.exposure", "evaluate_exposure_degrade", "degrade_copy"):
            self.assertNotIn(token, src,
                             "selector 不得 import/调用 exposure 降级（SPEC-131 是显示层）")


if __name__ == "__main__":
    unittest.main()
