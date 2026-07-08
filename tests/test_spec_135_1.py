"""SPEC-135.1 — Lane A 层级化渲染（kind/stage 纯附加字段）.

AC coverage:
  7/7 固定用例恰好 3 个 verdict/final 锚点（候选→刹停→观望）→ AnchorTests
  既有 trace 字段逐字节不变（kind/stage 纯附加）          → PureAdditionTests
  历史行无 kind 按 evidence 降级                          → UiAuditTests（降级路径）
  前端零硬编码 stage/gate 清单（层级由字段驱动）           → UiAuditTests
  strict-JSON（新字段随既有落盘断言自动覆盖）             → PureAdditionTests
  折叠交互 + 双主题                                       → UiAuditTests + browse 冒烟
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import strategy.bcd_governance as gov
import strategy.decision_trace as T
import strategy.selector as sel
from tests.test_spec_129 import _nnb_snapshots
from tests.test_spec_135 import _carve_snapshots

ROOT = Path(__file__).resolve().parents[1]

# SPEC-135 落地版节点字段集（135.1 前）——kind/stage 必须是纯附加
BASE_FIELDS = {"layer", "check", "label_human", "detail", "inputs",
               "outcome", "code_ref", "branch_taken"}


class PureAdditionTests(unittest.TestCase):
    def test_kind_stage_are_pure_additions(self) -> None:
        """每个节点 = 135 基础字段集 + {kind, stage}，不多不少；既有字段名
        逐字节不变。"""
        for snaps in (_nnb_snapshots(50.0), _nnb_snapshots(62.0), _carve_snapshots()):
            rec = sel.select_strategy(*snaps)
            for n in rec.trace:
                self.assertEqual(set(n.keys()), BASE_FIELDS | {"kind", "stage"},
                                 f"node {n['check']} 字段集漂移")
                self.assertIn(n["kind"], ("verdict", "evidence", "final"))
                self.assertIn(n["stage"], ("market_read", "routing", "gates",
                                           "capital", "governance", "final", ""))

    def test_gate_identity_contract_unchanged(self) -> None:
        T.reset()
        for v in (True, False):
            self.assertIs(T.gate(v, "x", "y"), v)

    def test_market_read_stage_on_data_nodes(self) -> None:
        rec = sel.select_strategy(*_nnb_snapshots(50.0))
        data_nodes = [n for n in rec.trace if n["layer"] == "data"]
        self.assertEqual(len(data_nodes), 4)
        for n in data_nodes:
            self.assertEqual(n["stage"], "market_read")
            self.assertEqual(n["kind"], "evidence")

    def test_funding_and_governance_nodes_annotated(self) -> None:
        from unittest.mock import patch
        from strategy.decision_trace import funding_trace
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   return_value={"total": 200_000.0, "source": "live",
                                 "breakdown": {}, "error": None}), \
             patch("strategy.cash_budget_governance.get_open_cash_collateral_total_usd",
                   return_value={"total": 0.0}), \
             patch("strategy.exposure.evaluate_exposure_degrade",
                   return_value={"degraded": False, "pct_of_pool": 10.0,
                                 "family_open_max_loss_usd": 0.0,
                                 "threshold_pct": 30.0, "note": None}):
            nodes = funding_trace("bull_put_spread")
        for n in nodes:
            self.assertEqual(n["stage"], "capital")
            self.assertEqual(n["kind"], "evidence")

    def test_strict_json_roundtrip_with_new_fields(self) -> None:
        import json
        import logs.recommendation_log_io as rlog
        rec = sel.select_strategy(*_nnb_snapshots(50.0))
        with tempfile.TemporaryDirectory() as tmp:
            orig = rlog.RECOMMENDATION_LOG_FILE
            rlog.RECOMMENDATION_LOG_FILE = Path(tmp) / "r.jsonl"
            try:
                rlog.append_recommendation_event(
                    rec=rec, source="t", mode="eod",
                    timestamp="2026-07-07T09:35:00-04:00", params_hash="x")
                raw = rlog.RECOMMENDATION_LOG_FILE.read_text()
                ev = json.loads(raw.splitlines()[0],
                                parse_constant=lambda s: (_ for _ in ()).throw(AssertionError(s)))
                self.assertEqual(ev["trace"][0]["kind"], "evidence")
            finally:
                rlog.RECOMMENDATION_LOG_FILE = orig


class AnchorTests(unittest.TestCase):
    """AC: 7/7 固定用例恰好 3 个锚点（候选 verdict → 刹停 verdict → 观望 final）。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._orig_state = gov.STATE_PATH
        gov.STATE_PATH = Path(self.tmp.name) / "gov_state.json"
        gov._write_state({"halt": {
            "at": "2026-07-07",
            "gates": [{"gate": "G2_18m_combined",
                       "detail": "18 个月实现+标记和 $-6,006 < 0（n=4）"}],
            "full_halt": False,
        }})

    def tearDown(self) -> None:
        gov.STATE_PATH = self._orig_state

    def test_77_exactly_three_anchors_in_order(self) -> None:
        vs, ivs, ts = _carve_snapshots()
        rec = sel.select_strategy(vs, ivs, ts)
        final = sel._apply_bcd_governance_live(rec, vs, ivs, ts)
        anchors = [n for n in final.trace if n["kind"] in ("verdict", "final")]
        self.assertEqual(len(anchors), 3, [a["check"] for a in anchors])
        # 候选（accept 降级 verdict）→ 刹停（halt verdict）→ 观望（final wait）
        self.assertEqual([a["kind"] for a in anchors], ["verdict", "verdict", "final"])
        self.assertEqual(anchors[0]["outcome"], "accept")
        self.assertIn("Bull Call Diagonal", anchors[0]["label_human"])
        self.assertEqual(anchors[0]["stage"], "routing")
        self.assertEqual(anchors[1]["outcome"], "halt")
        self.assertEqual(anchors[1]["stage"], "governance")
        self.assertEqual(anchors[2]["outcome"], "wait")
        self.assertEqual(anchors[2]["stage"], "final")
        # evidence 全部归组（无游离 verdict 外的 kind）
        for n in final.trace:
            if n not in anchors:
                self.assertEqual(n["kind"], "evidence", n["check"])

    def test_normal_day_single_final_anchor(self) -> None:
        gov._write_state({"halt": None})
        vs, ivs, ts = _carve_snapshots()
        rec = sel.select_strategy(vs, ivs, ts)
        final = sel._apply_bcd_governance_live(rec, vs, ivs, ts)
        anchors = [n for n in final.trace if n["kind"] in ("verdict", "final")]
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["kind"], "final")
        self.assertEqual(anchors[0]["outcome"], "accept")

    def test_veto_day_final_anchor_with_veto_evidence(self) -> None:
        rec = sel.select_strategy(*_nnb_snapshots(62.0))
        anchors = [n for n in rec.trace if n["kind"] in ("verdict", "final")]
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["outcome"], "wait")
        vetoes = [n for n in rec.trace if n["outcome"] == "veto"]
        self.assertTrue(all(n["kind"] == "evidence" for n in vetoes))


class UiAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")

    def test_hierarchy_wiring_present(self) -> None:
        for token in ("trace-anchor", "is-final", "trace-ev-group", "trace-market",
                      "traceKindOf", "trace-ev-inline", "trace-postnote", "附注"):
            self.assertIn(token, self.spx)

    def test_backward_compat_fallback(self) -> None:
        # 历史行无 kind → evidence 降级（kindOf 默认 + 全 evidence 平铺路径）
        self.assertIn("n.kind || 'evidence'", self.spx)
        self.assertIn("历史行降级", self.spx)

    def test_collapse_interaction_and_mobile_default(self) -> None:
        self.assertIn("style.display = g.style.display==='none'", self.spx)
        self.assertIn("window.innerWidth < 720", self.spx)

    def test_no_hardcoded_stage_or_gate_lists(self) -> None:
        """层级纯由 kind/stage 字段驱动：模板不得含 stage 清单数组或 gate 名。
        （market_read 是 spec 钦定的唯一渲染特例，允许出现）"""
        for gate_check in ("nnb_ivp_upper", "nlb_spec113_carve", "g2_18m",
                           "bcd_family_halt"):
            self.assertNotIn(gate_check, self.spx)
        for stage in ("'routing'", '"routing"', "'gates'", '"gates"',
                      "'capital'", '"capital"'):
            self.assertNotIn(f"[{stage}", self.spx)   # 无 stage 枚举数组

    def test_anchor_colors_via_theme_vars(self) -> None:
        # 双主题：锚点色全走 CSS vars（无裸 hex 于 135.1 新增块）
        i = self.spx.find(".trace-anchor")
        block = self.spx[i:i + 1400]
        self.assertIn("var(--green)", block)
        self.assertIn("var(--red)", block)
        self.assertIn("var(--blue", block)
        self.assertNotIn("--text-muted", block)


if __name__ == "__main__":
    unittest.main()
