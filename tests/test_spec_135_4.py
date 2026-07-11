# SPEC-135.4 — 首页决策叙事去重与精修（P0，PM 实看抓出；根因 = 135.3 spec
# 同页两处渲染点的设计错误）。
#
# AC 覆盖：
#   §1 首页唯一决策链渲染点（独立摘要卡删除）
#   §2 溯源标识主行零 token（静态扫描）/ final verdict 1.2rem Newsreader+色条 /
#      安全刹车主行一句话 / 图例 0.6rem 项间 8px 右上 / WAIT·观望 → NO ENTRY
#   §3 三泳道呈现（文案全部代码自吐同源）
#
# 2026-07-11 对齐（0d5991f，PM 2026-07-08 指令）：首页决策链 = 与 /spx 完全
# 一样的共享 Decision Trace 整卡（TraceRender.cardHtml/loadCard）。135.4 §1/§3
# 时代的首页专属锚点摘要 + Lane B/C 迷你行已退役（两处并存即信息漂移）——
# 本文件断言按 F1 铁律（改动有档→测试对齐）迁到单卡合同；生产先行提交
# 0d5991f 未带测试，此处清偿。
#
# 135.3 语义断言（advisory 非红、恰一红节点、同源逐字一致）由 test_spec_135_3
# 沿用回归，此处不重复。
from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.selector as sel
from tests.test_spec_129 import _nnb_snapshots

ROOT = Path(__file__).resolve().parents[1]


class HomeSingleAnchorContainerTests(unittest.TestCase):
    """§1 去重（0d5991f 对齐）：首页恰一个决策链渲染点 = 共享整卡容器。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.home = (ROOT / "web" / "templates" / "portfolio_home.html").read_text(encoding="utf-8")
        cls.tr = (ROOT / "web" / "static" / "trace_render.js").read_text(encoding="utf-8")

    def test_standalone_summary_card_deleted(self) -> None:
        self.assertNotIn('id="trace-summary"', self.home)
        self.assertNotIn("loadTraceSummary", self.home)
        # 0d5991f：首页专属锚点摘要也退役（整卡是唯一决策链渲染点）
        self.assertNotIn("TraceRender.anchorSummaryHtml(", self.home)

    def test_exactly_one_render_site(self) -> None:
        # DOM 断言的静态等价：共享整卡容器在首页恰出现一次（SPX 卡内）
        self.assertEqual(self.home.count('id="decision-trace"'), 1)
        i = self.home.find('id="decision-trace"')
        card_block = self.home[max(0, i - 1500):i]
        self.assertIn('id="card-spx"', card_block)   # 容器住在 SPX 主卡内

    def test_full_chain_lives_in_shared_card(self) -> None:
        # 完整决策链（含静默通过的门）由共享整卡承载——cardHtml 内含 Lane A
        # 全图渲染；首页不再有独立"展开完整决策链"懒加载路径
        self.assertNotIn("expandFullTrace", self.home)
        self.assertIn("${traceLaneAHtml(d, 'trace-ev')}", self.tr)
        self.assertIn("TraceRender.loadCard('decision-trace')", self.home)


class ProvenanceOutOfMainRowTests(unittest.TestCase):
    """§2 溯源降级：主行纯人话，selector./SPEC- token 只活在 tooltip 与三件套。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tr = (ROOT / "web" / "static" / "trace_render.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "web" / "static" / "theme.css").read_text(encoding="utf-8")

    def test_t_ref_main_row_suffix_removed(self) -> None:
        # 主行溯源后缀 span 全数移除（渲染器 + CSS 规则）
        self.assertNotIn('class="t-ref"', self.tr)
        self.assertNotIn(".trace-node .t-ref {", self.css)

    def test_code_ref_only_in_tooltip_or_triple(self) -> None:
        # 静态扫描：渲染器中每处 code_ref 使用都在 tooltip（title/tip）或
        # 展开三件套"代码溯源"行的语句内——不进主行可见文本
        stmts = re.split(r";\n", self.tr)
        for s in stmts:
            if "code_ref" not in s:
                continue
            self.assertTrue(
                "title" in s or "tip" in s or "代码溯源" in s or "溯源" in s,
                f"code_ref 出现在非 tooltip/三件套语句: {s[:120]}")

    def test_anchor_row_markup_is_pure_human(self) -> None:
        # 锚点行 markup：icon + label 后直接闭合，无溯源 span
        self.assertIn(
            '<span class="a-label">${n.label_human || n.check}</span>\n'
            '      </div>', self.tr)


class VisualHierarchyCssTests(unittest.TestCase):
    """§2 final verdict 视觉锚 + 图例收纳（CSS 断言）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.css = (ROOT / "web" / "static" / "theme.css").read_text(encoding="utf-8")

    def _block(self, selector: str) -> str:
        i = self.css.find(selector + " {")
        self.assertGreater(i, -1, selector)
        return self.css[i:self.css.find("}", i)]

    def test_final_verdict_headline_level(self) -> None:
        blk = self._block(".trace-anchor.is-final")
        self.assertIn("font-size: 1.2rem", blk)
        self.assertIn("font-family: var(--f-display)", blk)   # Newsreader
        self.assertIn("border-left: 3px solid var(--blue)", blk)  # 左侧色条

    def test_anchor_and_evidence_scale(self) -> None:
        self.assertIn("font-size: 1.0rem", self._block(".trace-anchor"))
        self.assertIn("font-size: 0.72rem", self._block(".trace-node > summary"))

    def test_legend_top_right_spacing_scale(self) -> None:
        blk = self._block(".trace-legend")
        self.assertIn("font-size: 0.6rem", blk)
        self.assertIn("gap: 8px", blk)                    # spacing scale
        self.assertIn("justify-content: flex-end", blk)   # 锚点区右上角


class VocabularyTests(unittest.TestCase):
    """§2 词表合规：WAIT/观望 → NO ENTRY；halt 主行一句话。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")
        cls.home = (ROOT / "web" / "templates" / "portfolio_home.html").read_text(encoding="utf-8")
        cls.tr = (ROOT / "web" / "static" / "trace_render.js").read_text(encoding="utf-8")

    def test_wait_final_label_no_entry_narrative(self) -> None:
        vs, ivs, ts = _nnb_snapshots(50.0)
        rec = sel._reduce_wait("测试观望理由", vs, ivs, ts, False)
        fin = rec.trace[-1]
        self.assertEqual(fin["label_human"], "今日结论：不开新仓")
        self.assertNotIn("观望", fin["label_human"])

    def test_templates_use_no_entry_not_wait(self) -> None:
        # 0d5991f：verdict 文案随整卡渲染器迁到共享 trace_render.js
        self.assertIn("NO ENTRY（不开新仓）", self.tr)
        for src in (self.spx, self.tr):
            self.assertNotIn("今日观望", src)
        for tpl in (self.spx, self.home, self.tr):
            self.assertNotIn("return 'WAIT'", tpl)

    def test_halt_label_single_sentence(self) -> None:
        # 主行一句话；长说明（预注册概率 + pm-clear）收进 detail——
        # 功能级断言在 test_spec_135 G2HaltFixtureTests，此处锁 label 长度纪律
        src = (ROOT / "strategy" / "selector.py").read_text(encoding="utf-8")
        self.assertIn("安全刹车：该策略家族近期合计收益转负 → 暂停开新仓，等待复核", src)
        i = src.find("预注册说明：策略良好时每周期也有约四成概率误踩此门")
        j = src.find('"安全刹车：该策略家族近期合计收益转负')
        self.assertGreater(i, j)   # 预注册说明在 detail 参数内（label 之后）


class LaneBCHomeTests(unittest.TestCase):
    """§3 三泳道呈现（0d5991f 对齐）：Lane B/C 唯一渲染 = 共享整卡；
    首页专属迷你行（laneb-spx/lanec-spx）已退役（双源即漂移）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.home = (ROOT / "web" / "templates" / "portfolio_home.html").read_text(encoding="utf-8")
        cls.tr = (ROOT / "web" / "static" / "trace_render.js").read_text(encoding="utf-8")

    def test_lane_b_single_sourced_in_shared_card(self) -> None:
        self.assertNotIn('id="laneb-spx"', self.home)     # 迷你行退役
        self.assertIn("${traceLaneBHtml(d.lane_b)}", self.tr)   # 整卡内渲染
        self.assertIn("${it.label_human}", self.tr)       # 文案 = API 自吐
        # 反漂移：前端零规则硬编码（21-DTE 阈值/触发语句都来自 lane_b payload）
        for src in (self.home, self.tr):
            self.assertNotIn("short_dte", src)
            self.assertNotIn("21-DTE", src)
            self.assertNotIn("规则要求今天平掉或滚动", src)

    def test_lane_c_single_sourced_in_shared_card(self) -> None:
        self.assertNotIn('id="lanec-spx"', self.home)     # 迷你行退役
        self.assertIn("${laneC.narrative || '—'}", self.tr)     # 整卡内渲染
        self.assertIn("${laneC.disclaimer || ''}", self.tr)

    def test_lane_c_summary_line_code_emitted(self) -> None:
        from strategy import decision_trace as dt
        row = {"date": "2026-07-07", "s3_flag": True,
               "walls": {"calls": [{"strike": 7550.0, "dist_pct": 0.6},
                                    {"strike": 7600.0, "dist_pct": 1.9}]},
               "vol_ratio": 0.9}
        with patch("strategy.structure_map.read_shadow", return_value=[row]), \
             patch("strategy.structure_map.progress",
                   return_value={"s3_n": 2, "s3_target": 30,
                                 "s4_n": 0, "s4_target": 30}):
            out = dt.lane_c_terrain("2026-07-07")
        self.assertEqual(out["summary_line"],
                         "贴 call 墙（<0.5%）已记 2 天——7550/+0.6% · 7600/+1.9%")
        # 无墙且未贴墙 → 不发 summary_line（首页行 fail-soft 隐藏）
        row2 = {"date": "2026-07-07", "s3_flag": False, "walls": {"calls": []}}
        with patch("strategy.structure_map.read_shadow", return_value=[row2]), \
             patch("strategy.structure_map.progress",
                   return_value={"s3_n": 0, "s3_target": 30,
                                 "s4_n": 0, "s4_target": 30}):
            out2 = dt.lane_c_terrain("2026-07-07")
        self.assertNotIn("summary_line", out2)

    def test_spx_full_lanes_untouched(self) -> None:
        # 0d5991f：完整泳道渲染迁到共享 cardHtml；/spx 挂载同一整卡
        for token in ("${traceLaneAHtml(d, 'trace-ev')}",
                      "${traceLaneBHtml(d.lane_b)}"):
            self.assertIn(token, self.tr)
        spx = (ROOT / "web" / "templates" / "spx.html").read_text(encoding="utf-8")
        self.assertIn("TraceRender.loadCard('decision-trace')", spx)


if __name__ == "__main__":
    unittest.main()
