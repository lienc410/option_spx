"""SPEC-139 §3 — Lane B 历史回放落盘.

AC coverage:
  - append 带 lane_b 快照 → 字段落盘、回放渲染
  - 无字段旧行回放标注降级（不空白不伪造）
  - 字段纯附加（既有字段逐字节不变）
  - strict-JSON
  - Lane A 回放零回归（同 chosen 行取 Lane A + Lane B）
"""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import logs.recommendation_log_io as rlog
import strategy.selector as sel
from tests.test_spec_135 import _carve_snapshots


class LaneBHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._orig = rlog.RECOMMENDATION_LOG_FILE
        rlog.RECOMMENDATION_LOG_FILE = Path(self.tmp.name) / "rec.jsonl"
        self.addCleanup(lambda: setattr(rlog, "RECOMMENDATION_LOG_FILE", self._orig))

    def _hist_rec(self):
        vs, ivs, ts = _carve_snapshots()
        vs = replace(vs, date="2026-07-01")     # 强制历史日
        return sel.select_strategy(vs, ivs, ts)

    def test_lane_b_snapshot_persisted_and_replayed(self) -> None:
        from web.server import app
        rec = self._hist_rec()
        snapshot = [{"trade_id": "T1", "state": "hold",
                     "label_human": "短腿还有 30 天到期（>21 天），未触发任何管理规则 — 继续持有",
                     "code_ref": "SPEC-127 §4 (21-DTE/collapse)"}]
        rlog.append_recommendation_event(
            rec=rec, source="test", mode="eod",
            timestamp="2026-07-01T09:35:00-04:00", params_hash="x",
            lane_b=snapshot)
        # 落盘校验：strict-JSON 且 lane_b 字段存在
        raw = rlog.RECOMMENDATION_LOG_FILE.read_text()

        def _bad(s):
            raise AssertionError(f"non-finite literal: {s}")
        ev = json.loads(raw.splitlines()[0], parse_constant=_bad)
        self.assertEqual(ev["lane_b"], snapshot)
        # 回放校验：历史日 Lane B 由存档快照渲染，Lane A 同步无回归
        res = app.test_client().get("/api/decision-trace?date=2026-07-01")
        d = res.get_json()
        self.assertFalse(d["is_today"])
        self.assertEqual(d["lane_b"], snapshot)
        self.assertEqual([n["check"] for n in d["lane_a"]],
                         [n["check"] for n in rec.trace])   # Lane A 零回归

    def test_missing_field_degrades_not_blank(self) -> None:
        from web.server import app
        rec = self._hist_rec()
        # 不传 lane_b（模拟 SPEC-139 之前的旧行）
        rlog.append_recommendation_event(
            rec=rec, source="test", mode="eod",
            timestamp="2026-07-01T09:35:00-04:00", params_hash="x")
        ev = json.loads(rlog.RECOMMENDATION_LOG_FILE.read_text().splitlines()[0])
        self.assertNotIn("lane_b", ev)     # 纯附加：不传即无 key
        res = app.test_client().get("/api/decision-trace?date=2026-07-01")
        d = res.get_json()
        self.assertGreaterEqual(len(d["lane_b"]), 1)             # 不空白
        self.assertIn("未存档", d["lane_b"][0]["label_human"])   # 如实降级

    def test_lane_b_field_is_pure_addition(self) -> None:
        """既有字段逐字节不变：加 lane_b 前后，其余字段完全一致。"""
        rec = self._hist_rec()
        rlog.append_recommendation_event(
            rec=rec, source="test", mode="eod",
            timestamp="2026-07-01T09:35:00-04:00", params_hash="x")
        without = json.loads(rlog.RECOMMENDATION_LOG_FILE.read_text().splitlines()[0])
        rlog.RECOMMENDATION_LOG_FILE.unlink()
        rlog.append_recommendation_event(
            rec=rec, source="test", mode="eod",
            timestamp="2026-07-01T09:35:00-04:00", params_hash="x",
            lane_b=[{"trade_id": "T1", "state": "hold",
                     "label_human": "x", "code_ref": "y"}])
        with_lb = json.loads(rlog.RECOMMENDATION_LOG_FILE.read_text().splitlines()[0])
        self.assertEqual(set(with_lb) - set(without), {"lane_b"})
        for k in without:
            self.assertEqual(with_lb[k], without[k], f"字段 {k} 被 lane_b 附加改动")


if __name__ == "__main__":
    unittest.main()
