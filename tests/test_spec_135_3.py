"""SPEC-135.3 — Trace 语义修复（advisory 档）+ 搬家首页（P0）.

AC coverage:
  advisory 节点语义（不拦文案 + 非红渲染类）        → AdvisoryTests
  7/7 固定用例全图恰一个红节点（G2）               → OneRedNodeTests
  cash 门 detail 补 override 说明                  → AdvisoryTests
  首页锚点与 /api/decision-trace 逐字一致（同源）   → SameSourceTests
  G2 文案不再裸长文本出现在 SPX 卡                  → UiAuditTests
  图例常显一行                                     → UiAuditTests
  边界：不动 selector/exposure 计算（135.1 合同沿用）→ AdvisoryTests / 既有套件

测试向量重生成注明：exposure degraded 分支 outcome 断言由 veto → advisory
（SPEC-135.3 词汇表补档；数值/文案向量不变）。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.bcd_governance as gov
import strategy.selector as sel
from tests.test_spec_135 import _carve_snapshots

ROOT = Path(__file__).resolve().parents[1]


def _funding_patches(degraded: bool = True):
    """健康现金 + degraded 敞口（7/7 生产态）——数据源钉死，计算层不动。"""
    return (
        patch("strategy.cash_budget_governance.get_current_liquid_cash",
              return_value={"total": 152_346.01, "source": "live",
                            "breakdown": {}, "error": None}),
        patch("strategy.cash_budget_governance.get_open_cash_collateral_total_usd",
              return_value={"total": 76_600.0}),
        patch("strategy.exposure.evaluate_exposure_degrade",
              return_value={"degraded": degraded, "pct_of_pool": 33.46,
                            "family_open_max_loss_usd": 76_600.0,
                            "strategy_pool_usd": 228_946.01,
                            "threshold_pct": 30.0, "note": None}),
        patch("strategy.capacity.used_defined_risk",
              return_value={"used_usd": 76_600.0, "capacity_usd": 238_000.0,
                            "buffer_usd": 100_000.0, "pct": 32.2,
                            "positions": []}),
    )


class AdvisoryTests(unittest.TestCase):
    def test_exposure_degraded_is_advisory_not_veto(self) -> None:
        """P0 缺陷修复：degraded 敞口 = 提示不拦 → advisory（曾误标 veto）。
        （向量重生成注明：本断言取代 135 时代的 veto 期望）"""
        from strategy.decision_trace import funding_trace
        p1, p2, p3, p4 = _funding_patches(degraded=True)
        with p1, p2, p3, p4:
            nodes = funding_trace("bull_call_diagonal")
        exp = next(n for n in nodes if n["check"] == "family_exposure_degrade")
        self.assertEqual(exp["outcome"], "advisory")
        # 不拦语义在文案里（label + detail 双处）
        self.assertIn("不拦操作", exp["label_human"])
        self.assertIn("不禁止任何操作", exp["detail"])
        # pass 分支不变
        q1, q2, q3, q4 = _funding_patches(degraded=False)
        with q1, q2, q3, q4:
            nodes2 = funding_trace("bull_call_diagonal")
        exp2 = next(n for n in nodes2 if n["check"] == "family_exposure_degrade")
        self.assertEqual(exp2["outcome"], "pass")

    def test_cash_gates_keep_veto_with_override_note(self) -> None:
        """cash_floor/cash_budget 是真拦截门（open API 有拦截路径）——veto
        保留，但 detail 补'手动单可 override'说明。"""
        from strategy.decision_trace import funding_trace
        p1, p2, p3, p4 = _funding_patches()
        with p1, p2, p3, p4:
            nodes = funding_trace("bull_call_diagonal")
        for check in ("cash_floor", "cash_budget"):
            n = next(x for x in nodes if x["check"] == check)
            self.assertIn("pm_override", n["detail"], check)
        # 破底线场景仍 veto（真拦截语义保留）
        with patch("strategy.cash_budget_governance.get_current_liquid_cash",
                   return_value={"total": 10_000.0, "source": "live",
                                 "breakdown": {}, "error": None}), \
             patch("strategy.exposure.evaluate_exposure_degrade",
                   return_value={"degraded": False, "pct_of_pool": 1.0,
                                 "family_open_max_loss_usd": 0.0,
                                 "threshold_pct": 30.0, "note": None}), \
             patch("strategy.capacity.used_defined_risk",
                   return_value={"used_usd": 0.0, "capacity_usd": 238_000.0,
                                 "buffer_usd": 100_000.0, "pct": 0.0,
                                 "positions": []}):
            nodes2 = funding_trace("bull_put_spread")
        floor = next(x for x in nodes2 if x["check"] == "cash_floor")
        self.assertEqual(floor["outcome"], "veto")

    def test_135_1_field_contract_unchanged(self) -> None:
        from strategy.decision_trace import funding_trace
        from tests.test_spec_135_1 import BASE_FIELDS
        p1, p2, p3, p4 = _funding_patches()
        with p1, p2, p3, p4:
            nodes = funding_trace("bull_call_diagonal")
        for n in nodes:
            self.assertEqual(set(n.keys()), BASE_FIELDS | {"kind", "stage"})


class OneRedNodeTests(unittest.TestCase):
    """AC: 7/7 固定用例（G2 halt + degraded 敞口 + 健康现金）全图恰一个红节点。"""

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

    def test_full_graph_exactly_one_red(self) -> None:
        from strategy.decision_trace import funding_trace
        vs, ivs, ts = _carve_snapshots()
        rec = sel.select_strategy(vs, ivs, ts)
        final = sel._apply_bcd_governance_live(rec, vs, ivs, ts)
        p1, p2, p3, p4 = _funding_patches(degraded=True)
        with p1, p2, p3, p4:
            lane_a = list(final.trace) + funding_trace("bull_call_diagonal")
        red = [n for n in lane_a if n["outcome"] in ("veto", "halt")]
        self.assertEqual(len(red), 1, [(n["check"], n["outcome"]) for n in red])
        self.assertEqual(red[0]["check"], "bcd_family_halt")     # 唯一的红 = G2
        # degraded 敞口在图里，且是琥珀提示档
        adv = [n for n in lane_a if n["outcome"] == "advisory"]
        self.assertEqual([n["check"] for n in adv], ["family_exposure_degrade"])


class SameSourceTests(unittest.TestCase):
    """AC: 首页锚点摘要与 /api/decision-trace 锚点逐字一致（同一 copy 源）。

    首页 SPX 卡从 /api/recommendation 的 rec.trace 取锚点；摘要卡从
    /api/decision-trace 取——两者都源自同一 rec.trace（decision-trace 的
    funding 追加层全为 evidence，不产锚点）。服务端断言两 API 锚点集逐字相等。"""

    def test_recommendation_and_decision_trace_anchors_verbatim(self) -> None:
        from web.server import app
        vs, ivs, ts = _carve_snapshots()
        rec = sel.select_strategy(vs, ivs, ts)
        p1, p2, p3, p4 = _funding_patches()
        with p1, p2, p3, p4, \
             patch("strategy.selector.get_recommendation", return_value=rec):
            c = app.test_client()
            rec_payload = c.get("/api/recommendation").get_json()
            trace_payload = c.get("/api/decision-trace").get_json()
        def anchors(nodes):
            return [(n["kind"], n["label_human"], n["detail"], n["code_ref"])
                    for n in nodes if n.get("kind") in ("verdict", "final")]
        a1 = anchors(rec_payload.get("trace") or [])
        a2 = anchors(trace_payload.get("lane_a") or [])
        self.assertTrue(a1)
        self.assertEqual(a1, a2)     # 逐字一致（label/detail/code_ref 全比）


class UiAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")
        cls.home = (ROOT / "web" / "templates" / "portfolio_home.html").read_text(encoding="utf-8")
        cls.tr = (ROOT / "web" / "static" / "trace_render.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "web" / "static" / "theme.css").read_text(encoding="utf-8")

    def test_shared_renderer_single_source(self) -> None:
        """渲染器单源：两页都引 trace_render.js；spx 本地渲染函数已删。"""
        for tpl in (self.spx, self.home):
            self.assertIn("trace_render.js", tpl)
        self.assertNotIn("const TRACE_ICONS", self.spx)
        self.assertNotIn("function traceNodeHtml", self.spx)

    def test_advisory_amber_red_reserved(self) -> None:
        """⚠ advisory 琥珀；红只留 veto/halt。"""
        self.assertIn("advisory: '⚠'", self.tr)
        self.assertIn("n.outcome === 'advisory' ? 'var(--orange)'", self.tr)
        self.assertIn(".trace-node.t-advisory { border-left-color: var(--orange-border); }", self.css)
        self.assertIn(".trace-anchor.a-advisory .a-icon { color: var(--orange); }", self.css)

    def test_legend_line_always_visible_both_pages(self) -> None:
        """图例常显一行（§3）：● 通过 · ⚠ 提示（不拦） · ⛔ 拦截 · ▶ 今日结论
        （0d5991f 整卡单源后图例活在共享 cardHtml 内，两页同一挂载）"""
        for token in ("通过", "提示（不拦）", "拦截", "今日结论"):
            self.assertIn(token, self.tr)
        self.assertIn("${traceLegendHtml()}", self.tr)          # 图例在整卡内
        self.assertIn("TraceRender.loadCard('decision-trace')", self.spx)
        self.assertIn("TraceRender.loadCard('decision-trace')", self.home)

    def test_homepage_anchor_home_and_expand(self) -> None:
        """SPEC-135.4 §1（0d5991f 再改版对齐）：首页决策链唯一渲染点 = 共享
        Decision Trace 整卡（PM 2026-07-08：与 /spx 完全一样）。独立摘要卡、
        锚点摘要块、展开入口全部退役——两处并存即信息漂移。"""
        self.assertNotIn('id="trace-summary"', self.home)
        self.assertNotIn("loadTraceSummary", self.home)
        self.assertNotIn("TraceRender.anchorSummaryHtml(", self.home)
        self.assertNotIn("expandFullTrace", self.home)
        self.assertEqual(self.home.count('id="decision-trace"'), 1)

    def test_spx_card_rationale_uses_trace_anchors_not_bare_text(self) -> None:
        """AC: G2 文案不再以裸长文本出现在 SPX 卡。0d5991f 后首页不再自渲染
        理由区——决策叙事（含 G2）只经共享整卡（trace 节点）呈现。"""
        self.assertNotIn('id="rationale-spx"', self.home)
        self.assertNotIn("rec.rationale", self.home)   # 裸长文本零渲染路径
        self.assertIn("TraceRender.loadCard('decision-trace')", self.home)

    def test_hover_carries_full_detail(self) -> None:
        # 锚点摘要 hover title = detail + 溯源（pm-clear 命令等完整文本由此
        # 承载；SPEC-135.4 起 code_ref 也只活在 tooltip/三件套）
        self.assertIn('title="${_esc(n.detail)}"', self.tr)      # evidence 同行段
        self.assertIn("' — 溯源: ' + (n.code_ref || '—')", self.tr)  # 锚点 tip


if __name__ == "__main__":
    unittest.main()
