"""SPEC-139 §1 — Gateway send-ledger (DEFERRED #22).

AC coverage:
  - gateway.push 实发一条 → push_ledger.jsonl 有对应行、字段齐
  - 无 key 件也记（dedupe_key=null）
  - SPEC-130 guard 未过 → 零 ledger 行（禁发即禁记）
  - fallback（HTML 400 → plain-text 200）标 fallback=True
  - 只有真送达才记（failed 不写行）
  - 既有裸 _send(text) 向后兼容（meta 全 optional，字段 null）
  - 14 日 rotation（与 push_stats 同窗口）
  - strict-JSON

依赖 tests/conftest.py 密闭 fixture：ep.PUSH_LEDGER 重定向 tmp、delenv SPX_PUSH_ENABLE。
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

import notify.event_push as ep
import notify.gateway as gw

# 生产推送主机上下文（HTTP 层已 mock，SPEC-130 密闭不破）
_PROD_ENV = {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c",
             "SPX_PUSH_ENABLE": "1"}


def _mock_resp(status: int, text: str = "ok"):
    m = MagicMock()
    m.status_code = status
    m.text = text
    return m


def _ledger_rows() -> list[dict]:
    """读回被密闭 fixture 重定向到 tmp 的 push_ledger.jsonl（strict-JSON 校验）。"""
    if not ep.PUSH_LEDGER.exists():
        return []
    rows = []
    for line in ep.PUSH_LEDGER.read_text().splitlines():
        line = line.strip()
        if not line:
            continue

        def _bad(s):
            raise AssertionError(f"non-finite literal in ledger: {s}")
        rows.append(json.loads(line, parse_constant=_bad))
    return rows


class SendLedgerTests(unittest.TestCase):
    def test_push_records_ledger_row_all_fields(self) -> None:
        title = "Position closed (via web) 这是一个很长的标题需要被截断到四十字以内校验前缀"
        with patch.dict("os.environ", _PROD_ENV), \
             patch.object(ep.requests, "post", return_value=_mock_resp(200)):
            ok = gw.push("ACTION", "持仓 T1", title, "body 内容", dedupe_key="k1")
        self.assertTrue(ok)
        rows = _ledger_rows()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(set(r), {"ts", "category", "about", "title_head",
                                  "dedupe_key", "quiet", "fallback"})
        self.assertEqual(r["category"], "ACTION")
        self.assertEqual(r["about"], "持仓 T1")
        self.assertEqual(r["title_head"], title[:40])
        self.assertLessEqual(len(r["title_head"]), 40)
        self.assertEqual(r["dedupe_key"], "k1")
        self.assertFalse(r["quiet"])          # ACTION rings
        self.assertFalse(r["fallback"])
        self.assertRegex(r["ts"], r"^\d{4}-\d{2}-\d{2}T")

    def test_no_key_push_records_null_key_and_quiet(self) -> None:
        with patch.dict("os.environ", _PROD_ENV), \
             patch.object(ep.requests, "post", return_value=_mock_resp(200)):
            ok = gw.push("FYI", "系统状态", "routine digest", "b")
        self.assertTrue(ok)
        rows = _ledger_rows()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["dedupe_key"])      # 无 key 件 key=null
        self.assertTrue(rows[0]["quiet"])             # FYI 静默

    def test_guard_denied_writes_zero_ledger_rows(self) -> None:
        """SPEC-130 未过（fixture delenv SPX_PUSH_ENABLE）→ 禁发即禁记。"""
        with patch.object(ep.requests, "post", return_value=_mock_resp(200)):
            ok = gw.push("ALERT", "系统状态", "should not send", "b",
                         dedupe_key="k2")
        self.assertFalse(ok)
        self.assertEqual(_ledger_rows(), [])
        self.assertFalse(ep.PUSH_LEDGER.exists())

    def test_fallback_flagged(self) -> None:
        def post(url, json=None, timeout=None):
            # HTML 首发 400，plain-text 重发 200
            return _mock_resp(400 if "parse_mode" in json else 200, "bad entity")
        with patch.dict("os.environ", _PROD_ENV), \
             patch.object(ep.requests, "post", side_effect=post):
            ok = gw.push("ACTION", "系统状态", "t", "x < 0 未闭合")
        self.assertTrue(ok)
        rows = _ledger_rows()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["fallback"])

    def test_failed_send_writes_no_ledger_row(self) -> None:
        with patch.dict("os.environ", _PROD_ENV), \
             patch.object(ep.requests, "post", return_value=_mock_resp(400, "nope")):
            ok = gw.push("ACTION", "系统状态", "t", "b")
        self.assertFalse(ok)
        self.assertEqual(_ledger_rows(), [])   # 只有真送达才记

    def test_naked_send_backward_compatible(self) -> None:
        """既有 _send(text) 裸调用不传 meta：仍记一行，分类字段 null。"""
        with patch.dict("os.environ", _PROD_ENV), \
             patch.object(ep.requests, "post", return_value=_mock_resp(200)):
            ok = ep._send("naked legacy text")
        self.assertTrue(ok)
        rows = _ledger_rows()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertIsNone(r["category"])
        self.assertIsNone(r["about"])
        self.assertIsNone(r["title_head"])
        self.assertIsNone(r["dedupe_key"])

    def test_rotation_keeps_last_14_distinct_days(self) -> None:
        # 预写 16 个不同历史日 → +今天一行 → 17 distinct → 保留最近 14
        pre = []
        for i in range(1, 17):
            pre.append(json.dumps({"ts": f"2000-01-{i:02d}T10:00:00-05:00",
                                   "category": "FYI", "about": "系统状态",
                                   "title_head": None, "dedupe_key": None,
                                   "quiet": True, "fallback": False}))
        ep.PUSH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        ep.PUSH_LEDGER.write_text("\n".join(pre) + "\n")
        ep._record_ledger({"category": "ACTION", "about": "系统状态",
                           "title": "today", "dedupe_key": None},
                          quiet=False, fallback=False)
        rows = _ledger_rows()
        days = {r["ts"][:10] for r in rows}
        self.assertEqual(len(days), 14)
        for dropped in ("2000-01-01", "2000-01-02", "2000-01-03"):
            self.assertNotIn(dropped, days)
        self.assertIn("2000-01-16", days)   # 最近的历史日保留


if __name__ == "__main__":
    unittest.main()
