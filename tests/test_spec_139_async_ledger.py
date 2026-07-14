"""SPEC-139 #22 异步通道台账缺口修复（2026-07-13）.

缺口：gateway.apush → telegram_bot._safe_send 只记 push_stats、从不写
send-ledger——bot 进程全部排程推送（晨报/digest/E-Trade/ladder/盘中）在
logs/push_ledger.jsonl 隐身；只有同步 gateway.push（web/launchd 脚本）有记录。
发现路径：2026-07-13 周一核查——digest 15:55 bot 日志显示已发但台账无行。

修复合同（镜像 event_push._send）：
  1. 真实送达（sent 或 plain fallback）后写 _record_ledger
  2. 台账写入严格位于 SPEC-130 host guard 之后（禁发即禁记）
  3. meta 由 apush 组装（category/about/title/dedupe_key）；裸 _safe_send
     调用 meta=None 仍记 null 字段行（与同步侧同语义）
"""
from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import notify.event_push as _ep


def _ledger_rows() -> list[dict]:
    p = Path(_ep.PUSH_LEDGER)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


class AsyncLedgerTests(unittest.TestCase):
    """conftest 已把 _ep.PUSH_LEDGER 重定向 tmp 且 delenv SPX_PUSH_ENABLE；
    需要 guard=1 分支的测试自行 setenv（bot 全程 AsyncMock，零真实 HTTP）。"""

    def _apush(self, bot, **kw):
        from notify.gateway import apush
        return asyncio.run(apush(bot, "123", kw.pop("category", "FYI"),
                                 kw.pop("about", "系统状态"),
                                 kw.pop("title", "测试 digest"),
                                 kw.pop("body", "body"), **kw))

    def test_apush_writes_ledger_row_on_delivery(self) -> None:
        bot = AsyncMock()
        with patch.dict("os.environ", {_ep.PUSH_ENABLE_ENV: "1"}):
            ok = self._apush(bot)
        self.assertTrue(ok)
        bot.send_message.assert_awaited()
        rows = _ledger_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["category"], "FYI")
        self.assertEqual(row["about"], "系统状态")
        self.assertEqual(row["title_head"], "测试 digest")
        self.assertFalse(row["fallback"])
        for key in ("ts", "dedupe_key", "quiet"):
            self.assertIn(key, row)

    def test_host_guard_deny_writes_nothing(self) -> None:
        """禁发即禁记：guard deny → 不发送、不写台账（conftest 已 delenv）。"""
        bot = AsyncMock()
        ok = self._apush(bot)
        self.assertFalse(ok)
        bot.send_message.assert_not_awaited()
        self.assertEqual(_ledger_rows(), [])

    def test_plain_fallback_row_marked(self) -> None:
        from telegram.error import BadRequest
        bot = AsyncMock()
        bot.send_message.side_effect = [BadRequest("bad html"), None]
        with patch.dict("os.environ", {_ep.PUSH_ENABLE_ENV: "1"}):
            ok = self._apush(bot)
        self.assertTrue(ok)
        rows = _ledger_rows()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["fallback"])

    def test_naked_safe_send_records_null_fields(self) -> None:
        """裸 _safe_send(meta=None) 与同步侧同语义：仍记 null 字段行。"""
        from notify.telegram_bot import _safe_send
        bot = AsyncMock()
        with patch.dict("os.environ", {_ep.PUSH_ENABLE_ENV: "1"}):
            ok = asyncio.run(_safe_send(bot, "123", "naked text"))
        self.assertTrue(ok)
        rows = _ledger_rows()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["category"])
        self.assertIsNone(rows[0]["title_head"])

    def test_send_failure_writes_nothing(self) -> None:
        """双次失败（HTML+plain 都炸）→ 无台账行（只记真实送达）。"""
        bot = AsyncMock()
        bot.send_message.side_effect = RuntimeError("network down")
        with patch.dict("os.environ", {_ep.PUSH_ENABLE_ENV: "1"}):
            ok = self._apush(bot)
        self.assertFalse(ok)
        self.assertEqual(_ledger_rows(), [])


if __name__ == "__main__":
    unittest.main()
