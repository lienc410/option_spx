"""SPEC-126 — unified notification gateway acceptance tests.

AC map:
  contract violations raise (missing category / about)
  digest integration (three sources merged; empty anomaly zone omitted)
  parse-fallback negative (bad HTML → plain-text delivered)  [transport]
  same-day dedupe idempotent + upgrade-only resend + clears-follows
  migration completeness (no direct sends outside gateway/transports)
  quiet policy (FYI/STATE silent; ALERT/ACTION ring)
  non-trading-day digest silence
  DESIGN.md push-vocabulary section + decisions log entry
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import notify.gateway as gw


class GatewayBase(unittest.TestCase):
    def setUp(self):
        self._orig = gw.DEDUPE_PATH
        gw.DEDUPE_PATH = Path(tempfile.mkdtemp()) / "dedupe.json"

    def tearDown(self):
        gw.DEDUPE_PATH = self._orig


class TestContract(GatewayBase):
    def test_unknown_category_raises(self):
        with self.assertRaises(ValueError):
            gw.prepare("URGENT", "系统状态", "t")

    def test_missing_about_raises(self):
        with self.assertRaises(ValueError):
            gw.prepare("ALERT", "", "t")
        with self.assertRaises(ValueError):
            gw.prepare("ALERT", "   ", "t")

    def test_first_line_self_identification(self):
        text, _ = gw.prepare("ALERT", "持仓 /ES Short Put", "Stop TRIGGERED")
        first = text.splitlines()[0]
        self.assertEqual(first, "🔴 [ALERT] 关于持仓 /ES Short Put")
        text, _ = gw.prepare("FYI", "系统状态", "x")
        self.assertEqual(text.splitlines()[0], "⚪ [FYI] 系统状态")
        text, _ = gw.prepare("ACTION", "新开仓", "x")
        self.assertEqual(text.splitlines()[0], "🟡 [ACTION] 关于新开仓")


class TestQuietPolicy(GatewayBase):
    def test_defaults(self):
        for cat, quiet in (("FYI", True), ("STATE", True),
                           ("ALERT", False), ("ACTION", False)):
            _, dn = gw.prepare(cat, "系统状态", "t")
            self.assertEqual(dn, quiet, cat)

    def test_explicit_override(self):
        _, dn = gw.prepare("FYI", "系统状态", "t", disable_notification=False)
        self.assertFalse(dn)


class TestDedupe(GatewayBase):
    def test_same_day_idempotent(self):
        self.assertIsNotNone(gw.prepare("ACTION", "系统状态", "a", dedupe_key="k1"))
        self.assertIsNone(gw.prepare("ACTION", "系统状态", "a", dedupe_key="k1"))

    def test_upgrade_resends_downgrade_drops(self):
        self.assertIsNotNone(gw.prepare("ACTION", "系统状态", "watch", dedupe_key="es"))
        self.assertIsNotNone(gw.prepare("ALERT", "系统状态", "trigger", dedupe_key="es"))
        self.assertIsNone(gw.prepare("STATE", "系统状态", "still", dedupe_key="es"))

    def test_clears_only_follows_todays_alert(self):
        # nothing fired → clear suppressed
        self.assertIsNone(gw.prepare("STATE", "系统状态", "cleared", clears="es"))
        gw.prepare("ALERT", "系统状态", "trigger", dedupe_key="es")
        out = gw.prepare("STATE", "系统状态", "cleared", clears="es")
        self.assertIsNotNone(out)
        _, quiet = out
        self.assertTrue(quiet)   # clearing messages are always quiet


class TestTransportWiring(GatewayBase):
    def test_push_passes_quiet_flag_to_transport(self):
        sent = {}

        def fake_send(text, *, disable_notification=False):
            sent["text"], sent["quiet"] = text, disable_notification
            return True

        with patch("notify.event_push._send", side_effect=fake_send):
            ok = gw.push("FYI", "系统状态", "t", "b")
        self.assertTrue(ok)
        self.assertTrue(sent["quiet"])
        self.assertIn("[FYI]", sent["text"])

    def test_parse_fallback_end_to_end(self):
        """AC negative test: bad HTML through the gateway still delivers
        (transport falls back to plain text)."""
        import notify.event_push as ep
        stats = Path(tempfile.mkdtemp()) / "stats.json"
        calls = []

        def post(url, json=None, timeout=None):
            calls.append(json)
            m = MagicMock()
            m.status_code = 400 if "parse_mode" in json else 200
            m.text = "can't parse entities"
            return m

        with patch.object(ep, "PUSH_STATS", stats), \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t",
                                       "TELEGRAM_CHAT_ID": "c",
                                       # SPEC-130: 传输测试显式声明生产推送
                                       # 主机上下文（HTTP 已 mock，密闭）
                                       "SPX_PUSH_ENABLE": "1"}), \
             patch.object(ep.requests, "post", side_effect=post):
            ok = gw.push("ACTION", "系统状态", "bad <tag", "x < 0 未闭合")
        self.assertTrue(ok)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("parse_mode", calls[1])


class TestDigest(unittest.TestCase):
    def test_three_sources_merged_and_anomaly_zone_omitted(self):
        import notify.telegram_bot as bot
        rec = MagicMock()
        rec.strategy_key = "reduce_wait"
        rec.canonical_strategy = "Bull Put Spread"
        with patch.object(bot, "get_recommendation", return_value=rec), \
             patch("strategy.state.read_all_positions",
                   return_value={"positions": [
                       {"trade_id": "2026-06-03_bcd_001",
                        "strategy_key": "bull_call_diagonal",
                        "expiry": "2099-12-17"}]}), \
             patch("strategy.bcd_governance.is_halted", return_value=None), \
             patch("strategy.bcd_governance.quote_gate_status",
                   return_value={"unlocked": False, "days": 3, "needed": 10}), \
             patch.object(bot, "read_state", return_value={}):
            category, title, body = bot.build_preclose_digest()
        self.assertIn("今日新仓裁决", body)
        self.assertIn("NO ENTRY", body)          # push vocabulary
        self.assertNotIn("WAIT", body.replace("NO ENTRY", ""))
        self.assertIn("持仓 2026-06-03_bcd_001", body)
        self.assertIn("治理", body)
        # SPEC-136：quote-gate 缩写 → 人话（分子分母语义完整）
        self.assertIn("真实报价已积累 3/10 天", body)
        self.assertNotIn("异常", body)           # clean day → zone omitted
        self.assertEqual(category, "FYI")        # nothing actionable

    def test_anomalies_and_actionable_flip_category(self):
        import notify.telegram_bot as bot
        rec = MagicMock()
        rec.strategy_key = "bull_put_spread"
        rec.strategy = "Bull Put Spread"
        with patch.object(bot, "get_recommendation", return_value=rec), \
             patch("strategy.state.read_all_positions",
                   return_value={"positions": []}), \
             patch("strategy.bcd_governance.is_halted",
                   return_value={"at": "2026-07-06"}), \
             patch("strategy.bcd_governance.quote_gate_status",
                   return_value={"unlocked": True, "days": 10, "needed": 10}), \
             patch.object(bot, "read_state",
                          return_value={"requires_reauth": True}):
            category, _, body = bot.build_preclose_digest()
        self.assertEqual(category, "ACTION")
        self.assertIn("异常", body)
        self.assertIn("Schwab 需要重新授权", body)
        self.assertIn("已暂停开新仓", body)  # SPEC-136：halted → 人话

    def test_non_trading_day_sends_nothing(self):
        import asyncio
        import notify.telegram_bot as bot
        with patch.object(bot, "is_trading_day", return_value=False), \
             patch("notify.gateway.apush") as mock_push:
            asyncio.run(bot.scheduled_preclose_digest(MagicMock(), "c"))
        mock_push.assert_not_called()


class TestMigrationCompleteness(unittest.TestCase):
    """CI assertion (SPEC-126 + SPEC-137 §1 全仓扫描): after the gateway
    migration, the ONLY direct Telegram transport call sites in the entire
    repository are the two transports (notify/event_push._send +
    notify/telegram_bot._safe_send). Every other push — including the former
    legacy direct senders in scripts/ and research/q041/ — goes through
    notify.gateway.push. Interactive bot replies (update.message.reply_*) are
    replies, not pushes, and stay.

    The scan walks the whole repo by design (not a fixed dir list) so a NEW
    direct sender added anywhere is caught, not just in the dirs the author
    happened to think of."""

    # 全仓扫描跳过：虚拟环境 / 依赖 / 测试自身 / git / 平行 worktree
    _SKIP_DIRS = {"venv", ".venv", "node_modules", "tests", ".git", ".claude"}

    def _repo_py_files(self):
        for p in REPO.rglob("*.py"):
            if any(part in self._SKIP_DIRS
                   for part in p.relative_to(REPO).parts):
                continue
            yield p

    def test_no_direct_requests_to_telegram_api(self):
        """全仓：api.telegram.org 只允许出现在 event_push 传输层。"""
        allowed = {"notify/event_push.py"}
        offenders = [
            str(p.relative_to(REPO))
            for p in self._repo_py_files()
            if str(p.relative_to(REPO)) not in allowed
            and "api.telegram.org" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            offenders, [],
            f"直连 api.telegram.org 未迁 gateway（SPEC-137 §1）：{offenders}")

    def test_no_bot_send_message_outside_safe_send(self):
        src = (REPO / "notify" / "telegram_bot.py").read_text(encoding="utf-8")
        # exactly the two calls inside _safe_send
        self.assertEqual(src.count("await bot.send_message"), 2)

    def test_no_raw_send_imports_outside_gateway(self):
        """全仓：event_push._send 传输入口只允许 gateway/event_push 调用。"""
        allowed = {"notify/gateway.py", "notify/event_push.py"}
        offenders = []
        for p in self._repo_py_files():
            rel = str(p.relative_to(REPO))
            if rel in allowed:
                continue
            src = p.read_text(encoding="utf-8")
            if "from notify.event_push import _send" in src or "event_push._send(" in src:
                offenders.append(rel)
        self.assertEqual(
            offenders, [],
            f"直连 event_push._send 未走 gateway（SPEC-137 §1）：{offenders}")


class TestDesignDoc(unittest.TestCase):
    def test_push_vocabulary_section(self):
        d = (REPO / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn("## Push Vocabulary (SPEC-126)", d)
        self.assertIn("关于新开仓", d)
        self.assertIn("Unified notification gateway (SPEC-126)", d)


if __name__ == "__main__":
    unittest.main()
