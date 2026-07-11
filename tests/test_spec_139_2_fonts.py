"""SPEC-139 §2 — Google Fonts 自托管（零外域）.

AC coverage（扩展 SPEC-134 / 132.1 的 no-CDN 断言到字体）:
  - 全模板零 fonts.google/gstatic（静态扫描）
  - 三家 woff2 vendored + wOF2 magic（字节校验）
  - SIL OFL LICENSE 随附
  - theme.css @font-face（三家三字重 + font-display:swap + 本地 src）
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "web" / "templates"
FONTS = ROOT / "web" / "static" / "fonts"
THEME_CSS = ROOT / "web" / "static" / "theme.css"


class SelfHostedFontsTests(unittest.TestCase):
    _EXPECTED_WOFF2 = [
        "Newsreader.latin.woff2", "Newsreader.latinext.woff2",
        "Newsreader-italic.latin.woff2", "Newsreader-italic.latinext.woff2",
        "JetBrainsMono.latin.woff2", "JetBrainsMono.latinext.woff2",
        "DMSans.latin.woff2", "DMSans.latinext.woff2",
    ]

    def test_all_templates_zero_external_font_refs(self) -> None:
        templates = sorted(TEMPLATES.glob("*.html"))
        self.assertGreater(len(templates), 20)
        for tpl in templates:
            text = tpl.read_text(encoding="utf-8")
            for token in ("fonts.googleapis.com", "fonts.gstatic.com",
                          "fonts.google"):
                self.assertNotIn(token, text,
                                 f"{tpl.name}: 残留外域字体 token {token}")

    def test_woff2_vendored_with_magic(self) -> None:
        for fname in self._EXPECTED_WOFF2:
            p = FONTS / fname
            self.assertTrue(p.exists(), f"缺 vendored woff2: {fname}")
            self.assertEqual(p.read_bytes()[:4], b"wOF2",
                             f"{fname}: 非法 woff2 magic")

    def test_ofl_licenses_present(self) -> None:
        for lic in ("Newsreader.LICENSE", "JetBrainsMono.LICENSE",
                    "DMSans.LICENSE"):
            p = FONTS / lic
            self.assertTrue(p.exists(), f"缺 OFL license: {lic}")
            self.assertIn("SIL OPEN FONT LICENSE", p.read_text())

    def test_theme_css_fontface_selfhosted(self) -> None:
        css = THEME_CSS.read_text(encoding="utf-8")
        for fam in ("'Newsreader'", "'JetBrains Mono'", "'DM Sans'"):
            self.assertIn(f"font-family: {fam};", css)
        # DESIGN.md 精确字重（变量字体权重区间）
        self.assertIn("font-weight: 400 600;", css)    # Newsreader italic / JBMono
        self.assertIn("font-weight: 300 500;", css)    # DM Sans
        self.assertIn("font-style: italic;", css)      # Newsreader 斜体叙事
        # font-display:swap 保留（8 个 @font-face 块）
        self.assertEqual(css.count("font-display: swap;"), 8)
        # src 全部本地相对路径，无外域
        for m in re.findall(r"src:\s*url\(([^)]+)\)", css):
            url = m.strip("'\"")
            self.assertTrue(url.startswith("fonts/"),
                            f"@font-face src 非本地: {url}")
        self.assertNotIn("gstatic", css)
        self.assertNotIn("fonts.google", css)


if __name__ == "__main__":
    unittest.main()
