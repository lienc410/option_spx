"""SPEC-150 — Open Position 弹窗宽版布局 regression locks.

PM 2026-09-14：弹窗被 560px 宽度限制，10 列扫描表折行（行高 61px vs 单行
32px）。修复为两档宽度 + 单元格 nowrap。本文件锁住"不再折回去"的不变量。

AC map:
  AC-1 只有 open 弹窗走宽版（其余表单弹窗保持 560px）
  AC-2 扫描表单元格与表头 nowrap + 粘性表头
  AC-3 每条腿 = leg-block（行权价输入 + 自己的扫描表）
  AC-4 响应式三档（3 栏 / 2 栏 ≤1100px / 1 栏 ≤720px）
  AC-5 DESIGN.md 记录该宽度规则（视觉决策以 DESIGN.md 为真值源）
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


class SpxTemplateCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spx = (REPO / "web" / "templates" / "spx.html").read_text(encoding="utf-8")

    def _css_block(self, selector: str) -> str:
        """取某条 CSS 规则的声明块（用于断言属性真的写在该规则里）。"""
        i = self.spx.index(selector)
        return self.spx[i:self.spx.index("}", i)]


class TestAC1WideOnlyForOpen(SpxTemplateCase):
    def test_wide_class_defined_with_two_tier_widths(self):
        self.assertIn("width: min(560px, 100%)", self.spx)       # 表单对话框
        self.assertIn(".modal.modal-wide { width: min(1060px, 100%); }", self.spx)

    def test_wide_toggled_on_open_kind_only(self):
        """kind === 'open' 才加 modal-wide；close/roll/note 必须落回 560px。
        用 toggle(第二参数) 而不是 add——否则宽版会粘在后续弹窗上。"""
        self.assertIn(
            "classList.toggle('modal-wide', kind === 'open')", self.spx)
        self.assertNotIn("classList.add('modal-wide')", self.spx)


class TestAC2TableNoWrap(SpxTemplateCase):
    def test_cells_and_headers_nowrap(self):
        for sel in (".scan-table th {", ".scan-table td {"):
            self.assertIn("white-space: nowrap;", self._css_block(sel), sel)

    def test_header_is_sticky(self):
        th = self._css_block(".scan-table th {")
        self.assertIn("position: sticky;", th)
        self.assertIn("top: 0;", th)
        # 粘住的表头必须有不透明背景，否则数据会从底下透出来
        self.assertIn("background: var(--surface-hi);", th)

    def test_scroll_container_allows_horizontal_overflow(self):
        """窄视口的退路是横向滚动，不是回到折行。"""
        self.assertIn("overflow: auto;", self._css_block(".scan-table-wrap {"))


class TestAC3LegBlocks(SpxTemplateCase):
    def test_every_leg_is_input_plus_its_scan(self):
        self.assertEqual(self.spx.count('class="modal-field full leg-block'), 4)
        for scan_id in ("scan-short-wrap", "scan-long-wrap",
                        "scan-short-put-wrap", "scan-long-put-wrap"):
            self.assertIn(scan_id, self.spx)

    def test_ic_legs_still_toggleable(self):
        """SPEC-148 的显隐开关按 .ic-only 查询——合并成 leg-block 后仍需带该类。"""
        self.assertEqual(self.spx.count("leg-block ic-only"), 2)
        self.assertIn(".ic-only", self.spx)

    def test_leg_input_width_capped(self):
        """整行区块里的行权价输入不能被拉成 1000px。"""
        self.assertIn("max-width: 220px;", self._css_block(".leg-block .leg-input {"))


class TestAC4Responsive(SpxTemplateCase):
    def test_three_then_two_then_one_column(self):
        self.assertIn(".modal-wide .modal-grid { grid-template-columns: repeat(3, 1fr); }",
                      self.spx)
        mid = self.spx[self.spx.index("@media (max-width: 1100px)"):]
        self.assertIn("grid-template-columns: 1fr 1fr;",
                      mid[:mid.index("@media (max-width: 720px)")])
        small = self.spx[self.spx.index("@media (max-width: 720px)"):]
        self.assertIn(".modal-wide .modal-grid", small)
        self.assertIn("grid-template-columns: 1fr;", small)


class TestAC5DesignDoc(unittest.TestCase):
    def test_modal_width_rule_recorded_in_design_md(self):
        d = (REPO / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn("Modal widths (SPEC-150)", d)
        self.assertIn("modal-wide", d)
        self.assertIn("1060px", d)
        # 决策日志同步留痕
        self.assertTrue(re.search(r"^\| 2026-09-14 \|.*modal-wide", d, re.M),
                        "decisions log row missing")


if __name__ == "__main__":
    unittest.main()
