"""SPEC-136 — 全站人话化批 A（推送线）acceptance tests.

AC map:
  AC-1 静态扫描 — 改写表覆盖的 formatter 输出不含 SPEC-\\d / 裸 Q 号 /
       D1・D2・G4 类内部门代号
  AC-2 digest 人话 — 持仓行用 catalog 人话名（无裸 strategy_key）、DTE 带语义、
       quote-gate 行与 quote_gate_status().label_human 单源
  AC-3 词表 — EOD morning-label 对 reduce_wait 输出 NO ENTRY（非 REDUCE_WAIT）
  AC-4 晨报首行 — 与 trace final verdict label_human 逐字同源
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import notify.telegram_bot as bot
from notify.telegram_bot import EsStopLevel, EsStopResult

# 主文案禁用 token：SPEC 编号 / 研究 Q 号 / quote-gate 缩写。
# （日期型 trade_id 如 2026-06-03_bcd_001 是持仓标识，不在禁用之列。）
_FORBIDDEN = re.compile(r"SPEC-\d|Q0\d{2}(?![0-9])|quote-gate")


def _assert_human(tc: unittest.TestCase, text: str, where: str) -> None:
    m = _FORBIDDEN.search(text)
    tc.assertIsNone(m, f"{where}: 主文案含内部代号 {m.group(0) if m else ''!r}\n{text}")


class TestAC1StaticScan(unittest.TestCase):
    def test_ladder_shadow_messages(self):
        payload = {"selector_strategy": "Bull Put Spread", "sizing_contracts": 2,
                   "theoretical_max_loss": 4000, "theoretical_max_loss_pct_nlv": 1.2,
                   "current_bp_pct_nlv": 8.0}
        for fn in (bot._format_ladder_shadow_message,
                   bot._format_ladder_v1b_shadow_message):
            text = fn(payload)
            _assert_human(self, text, fn.__name__)
            self.assertIn("未下任何真实单", text)

    def test_es_stop_alert_all_levels(self):
        for level in (EsStopLevel.TRIGGER, EsStopLevel.WARNING, EsStopLevel.NONE):
            text = bot._format_es_stop_alert(EsStopResult(
                level=level, entry_premium=2.50, current_mark=7.50, ratio=3.0))
            _assert_human(self, text, f"es_stop_alert[{level}]")
        trig = bot._format_es_stop_alert(EsStopResult(
            level=EsStopLevel.TRIGGER, entry_premium=2.50, current_mark=7.50, ratio=3.0))
        # SPEC-136 #3 — 数字带语义：入场 → 现在几倍
        self.assertIn("入场价 3.0 倍", trig)
        self.assertIn("规则要求平仓", trig)
        self.assertIn("TRIGGERED", trig)  # _classify_intraday 路由 token 保留

    def test_es_hv_paper_signal(self):
        record = {"signal_date": "2026-07-08", "vix_at_signal": 21.3,
                  "active_slots": 2, "est_strike": 5600.0, "est_premium": 38.5}
        text = bot._format_es_hv_paper_signal(record)
        _assert_human(self, text, "es_hv_paper_signal")
        self.assertIn("纸面研究信号", text)

    def test_t3_earnings_formatters(self):
        import notify.q041_t3_earnings_check as chk
        cand = {"underlying": "COST", "earn_date": "2026-07-10", "spot": 972.4,
                "vix_entry": 16.4, "implied_move_usd": 41.08,
                "implied_move_pct": 0.0422, "spread_width_usd": 41.08,
                "K_short_put": 931, "K_long_put": 890, "K_short_call": 1013,
                "K_long_call": 1054, "net_credit_usd": 1420.0,
                "max_loss_usd": 2680.0, "cash_need_usd": 2680.0}
        msg = chk._format_t_minus_3(cand, {"accepted": True, "reason": "accepted"})
        _assert_human(self, msg, "_format_t_minus_3")
        self.assertIn("财报前 3 天", msg)
        close = {"s_exit": 1000.85, "breached": None, "strikes_held": True,
                 "paper_pnl_usd": 1420.0, "net_credit_usd": 1420.0,
                 "max_loss_usd": 2680.0}
        msg2 = chk._format_t_plus_1(cand, close)
        _assert_human(self, msg2, "_format_t_plus_1")

    def test_bcd_halt_message_gate_labels(self):
        from strategy.bcd_governance import _halt_message
        fired = [{"gate": "G1_last6_realized",
                  "label_human": "最近 6 笔合计门（安全刹车）",
                  "detail": "最近 6 笔实现和 $-1,234 < 0"}]
        text = _halt_message(fired, "2026-07-08")
        self.assertIn("安全刹车", text)
        self.assertNotIn("D1", text)
        self.assertNotIn("G1_last6_realized", text)  # gate id 降级为 label_human
        full = _halt_message([{"gate": "G4_family_cum", "full_halt": True,
                               "label_human": "家族累计全停门",
                               "detail": "家族累计（实现+标记）$-9,999 < $-8,000"}],
                             "2026-07-08")
        self.assertIn("全停线", full)
        self.assertNotIn("G4 家族累计门", full)

    def test_governance_decision_no_layer_prefix(self):
        rec = MagicMock(rationale="test rationale")
        decision = MagicMock(
            is_bypass_event=False, bypass_type=None, override_baseline=False,
            governed_position_action="HOLD", governed_strategy="Bull Put Spread",
            final_priority_layer=3, final_priority_name="Lifecycle Exit",
            vix=17.2, ivp252=44, regime="NORMAL",
            next_actionable_decision_at=None)
        text = bot._format_governance_decision(rec, decision)
        _assert_human(self, text, "_format_governance_decision")
        self.assertIn("Rule:", text)
        self.assertIn("第 3 优先层", text)


class TestAC2DigestHuman(unittest.TestCase):
    # SPEC-140 §2：digest 为四泳道镜像——Lane B/D 装配统一 patch 固定向量
    # （密闭：不读真 ledger、不 import web.server）。
    _LANE_D = {"semantics": "…", "engines": [], "summary_line": "压力机 CALM"}

    def test_digest_strategy_name_and_dte_semantics(self):
        rec = MagicMock()
        rec.strategy_key = "reduce_wait"
        rec.canonical_strategy = "Bull Put Spread"
        with patch.object(bot, "get_recommendation", return_value=rec), \
             patch("strategy.state.read_all_positions",
                   return_value={"positions": [
                       {"trade_id": "2026-06-03_bcd_001",
                        "strategy_key": "bull_call_diagonal",
                        "expiry": "2099-12-17"}]}), \
             patch("strategy.decision_trace.lane_b_positions",
                   return_value=[]), \
             patch("strategy.decision_trace.lane_d_sleeves",
                   return_value=dict(self._LANE_D)), \
             patch("strategy.bcd_governance.is_halted", return_value=None), \
             patch("strategy.bcd_governance.quote_gate_status",
                   return_value={"unlocked": False, "days": 3, "needed": 10,
                                 "label_human": "真实报价已积累 3/10 天"
                                                "（满 10 天才评估 BCD 重开）"}), \
             patch.object(bot, "read_state", return_value={}):
            _, _, body = bot.build_preclose_digest()
        self.assertIn("Bull Call Diagonal", body)          # catalog 人话名
        self.assertNotIn("bull_call_diagonal", body)       # 裸 key 不得出现
        self.assertIn("还剩", body)                         # DTE 带语义
        self.assertNotIn("quote-gate", body)

    def test_digest_quote_gate_single_source(self):
        """digest 治理位与 quote_gate_status().label_human 逐字同源。"""
        rec = MagicMock()
        rec.strategy_key = "reduce_wait"
        rec.canonical_strategy = "Bull Put Spread"
        sentinel = "SENTINEL·单源标签·136"
        with patch.object(bot, "get_recommendation", return_value=rec), \
             patch("strategy.state.read_all_positions",
                   return_value={"positions": []}), \
             patch("strategy.decision_trace.lane_b_positions",
                   return_value=[]), \
             patch("strategy.decision_trace.lane_d_sleeves",
                   return_value=dict(self._LANE_D)), \
             patch("strategy.bcd_governance.is_halted", return_value=None), \
             patch("strategy.bcd_governance.quote_gate_status",
                   return_value={"unlocked": False, "days": 3, "needed": 10,
                                 "label_human": sentinel}), \
             patch.object(bot, "read_state", return_value={}):
            _, _, body = bot.build_preclose_digest()
        self.assertIn(sentinel, body)

    def test_quote_gate_status_carries_label_human(self):
        """label_human 与门逻辑同居 bcd_governance（真值来源存在性）。"""
        import strategy.bcd_governance as gov
        with patch.object(gov, "read_state", return_value={}), \
             patch.object(gov, "_lowvol_quote_days", return_value=["a", "b"]):
            qg = gov.quote_gate_status()
        self.assertIn("真实报价已积累 2/", qg["label_human"])
        self.assertIn("BCD 重开", qg["label_human"])


class TestAC3Vocabulary(unittest.TestCase):
    def test_morning_label_no_entry(self):
        self.assertEqual(
            bot._morning_label({"position_action": "WAIT",
                                "strategy_key": "reduce_wait"}),
            "NO ENTRY")
        # 非 wait：动作 + catalog 人话名
        self.assertEqual(
            bot._morning_label({"position_action": "OPEN",
                                "strategy_key": "bull_put_spread"}),
            "OPEN Bull Put Spread")


class TestAC4MorningAnchor(unittest.TestCase):
    def test_recommendation_first_line_matches_trace_final(self):
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy
        from tests.test_strategy_unification import make_iv, make_trend, make_vix
        vix = make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT)
        iv = make_iv(signal=IVSignal.LOW, iv_rank=10.0, iv_percentile=12.0, vix=13.0)
        trend = make_trend(signal=TrendSignal.BULLISH)
        rec = select_strategy(vix, iv, trend)
        fv = next(n["label_human"] for n in rec.trace if n.get("kind") == "final")
        text = bot._format_recommendation(rec)
        first = text.splitlines()[0]
        self.assertIn(bot._h(fv), first)   # 逐字同源（HTML 转义后）
        self.assertTrue(fv.startswith("今日结论"))


if __name__ == "__main__":
    unittest.main()
