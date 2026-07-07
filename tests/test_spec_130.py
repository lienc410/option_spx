"""SPEC-130 — 推送通道测试密闭性（INCIDENT 2026-07-07）.

AC coverage:
  AC-1 主机 guard：无 SPX_PUSH_ENABLE → _send/_safe_send/遗留 sender 零外呼
       + False；=1 → 正常发送路径（mock 200）          → HostGuardTests
  AC-2 生产冒烟（真发一条 STATE）                       → LivePushProductionSmoke
       （@live_push，默认 skip；oldair 上 SPX_TEST_LIVE_PUSH=1 显式跑）
  AC-3 全量 pytest 零外呼 + push_stats 零增量           → conftest 密闭层 +
       session 元断言（本文件 HermeticLayerTests 验证机制本身）
  AC-4 防线独立于 .env 止血改名                          → HostGuardTests
       （测试显式 patch 真-token-在位场景，guard 仍拦；套件层面由恢复 key 后
        重跑全量验证）
"""
from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

import notify.event_push as ep
import notify.gateway as gw
from tests.conftest import _REAL_SEND, PUSH_ATTEMPTS


def _resp(status: int = 200, text: str = "ok") -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.text = text
    return m


# ── AC-1 / AC-4 — 主机 guard ─────────────────────────────────────────────────

class HostGuardTests(unittest.TestCase):
    """真凭证在位（模拟 AC-4 恢复态）+ guard 未设 → 零外呼。防线不依赖
    .env key 改名止血。"""

    _CREDS = {"TELEGRAM_BOT_TOKEN": "real-looking-token",
              "TELEGRAM_CHAT_ID": "123456"}

    def test_guard_off_send_is_inert_even_with_creds(self) -> None:
        """AC-1/AC-4: 无 SPX_PUSH_ENABLE → 零 HTTP + False + 零 stats 写入。"""
        self.assertNotIn(ep.PUSH_ENABLE_ENV, os.environ)  # conftest 已 delenv
        post = MagicMock()
        with patch.dict(os.environ, self._CREDS), \
             patch.object(ep.requests, "post", post):
            ok = _REAL_SEND("synthetic test push — must never reach PM")
        self.assertFalse(ok)
        post.assert_not_called()                      # 零外呼（socket 层不可达）
        self.assertFalse(ep.PUSH_STATS.exists())      # stats 在 guard 之后

    def test_guard_on_normal_send_path(self) -> None:
        """AC-1: =1 → 正常发送（mock 200），stats sent+1（生产行为零变化）。"""
        post = MagicMock(return_value=_resp(200))
        with patch.dict(os.environ, {**self._CREDS, ep.PUSH_ENABLE_ENV: "1"}), \
             patch.object(ep.requests, "post", post):
            ok = _REAL_SEND("guard-on path", disable_notification=True)
        self.assertTrue(ok)
        post.assert_called_once()
        self.assertIn("api.telegram.org", post.call_args.args[0])
        import json as _json
        stats = _json.loads(ep.PUSH_STATS.read_text())
        self.assertEqual(stats[next(iter(stats))]["sent"], 1)

    def test_guard_value_must_be_exactly_1(self) -> None:
        post = MagicMock()
        for bad in ("0", "true", "yes", ""):
            with patch.dict(os.environ, {**self._CREDS, ep.PUSH_ENABLE_ENV: bad}), \
                 patch.object(ep.requests, "post", post):
                self.assertFalse(_REAL_SEND("x"))
        post.assert_not_called()

    def test_safe_send_guarded(self) -> None:
        """bot 传输同款 guard：无 env → bot.send_message 零 await + False。"""
        from notify.telegram_bot import _safe_send
        bot = AsyncMock()
        with patch.dict(os.environ, self._CREDS):
            ok = asyncio.run(_safe_send(bot, "chat", "synthetic"))
        self.assertFalse(ok)
        bot.send_message.assert_not_awaited()
        # =1 → 正常路径
        with patch.dict(os.environ, {**self._CREDS, ep.PUSH_ENABLE_ENV: "1"}):
            ok = asyncio.run(_safe_send(bot, "chat", "synthetic"))
        self.assertTrue(ok)
        bot.send_message.assert_awaited_once()

    def test_legacy_direct_senders_guarded(self) -> None:
        """遗留直连 sender（SPEC-126 两传输之外的历史通道）同样 deny-by-default。"""
        post = MagicMock()
        with patch.dict(os.environ, self._CREDS), \
             patch.object(requests, "post", post):
            from scripts.etrade_status_notify import _send_telegram as etrade_send
            self.assertFalse(etrade_send("x"))
            import logging
            from research.q041.daily_chain_sanity import _send_telegram as sanity_send
            self.assertFalse(sanity_send("x", logging.getLogger("t")))
            from research.q041.collect_chains import _send_collector_alert_telegram
            _send_collector_alert_telegram("SPX", logging.getLogger("t"))  # 静默 return
        post.assert_not_called()

    def test_gateway_end_to_end_denied_on_dev_host(self) -> None:
        """gateway → 传输全链路：真凭证在位、guard 未设 → False + 尝试被记录。"""
        n0 = len(PUSH_ATTEMPTS)
        with patch.dict(os.environ, self._CREDS):
            ok = gw.push("FYI", "系统状态", "t", "synthetic gateway push")
        self.assertFalse(ok)
        self.assertEqual(len(PUSH_ATTEMPTS), n0 + 1)   # conftest recorder 记录了尝试


# ── AC-3 机制自证 — 密闭层本身 ───────────────────────────────────────────────

class HermeticLayerTests(unittest.TestCase):
    def test_tripwire_fails_on_real_telegram_http(self) -> None:
        """任何测试直接对 api.telegram.org 发 HTTP → 立即 fail。"""
        from _pytest.outcomes import Failed
        with pytest.raises(Failed):
            requests.post("https://api.telegram.org/botXXX/sendMessage",
                          json={"chat_id": "1", "text": "x"})

    def test_push_enable_env_absent_inside_tests(self) -> None:
        self.assertNotIn(ep.PUSH_ENABLE_ENV, os.environ)

    def test_stats_and_dedupe_redirected_to_tmp(self) -> None:
        repo_logs = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "..", "logs"))
        self.assertNotEqual(os.path.realpath(str(ep.PUSH_STATS.parent)), repo_logs)
        self.assertIn("pytest", str(gw.DEDUPE_PATH) + str(ep.PUSH_STATS))


# ── AC-2 — 生产活体冒烟（默认 skip，oldair 显式 opt-in 跑）───────────────────

@pytest.mark.live_push
def test_live_push_production_smoke():
    """AC-2: guard 部署后生产真发一条 STATE（quiet，无需 PM 操作）。

    运行方式（仅 oldair，且已提前告知 PM 会收到这一条）：
      SPX_TEST_LIVE_PUSH=1 SPX_PUSH_ENABLE=1 \
        ./venv/bin/python -m pytest tests/test_spec_130.py -m live_push -q
    证明 guard 未误伤生产发送路径。"""
    ok = gw.push(
        "STATE", "系统状态", "SPEC-130 生产冒烟",
        "推送主机 guard 部署后传输验证 — 单条 STATE 测试推送，无需操作。",
        disable_notification=True,
    )
    assert ok, "production live smoke failed — guard 误伤生产路径"


if __name__ == "__main__":
    unittest.main()
