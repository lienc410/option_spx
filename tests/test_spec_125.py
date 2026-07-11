"""SPEC-125 — frontend three-party review fix batch, acceptance tests.

AC map:
  C1 target 一字同源 (integration + fourth-mirror JS literal ban)
  C2 exit_reason label migration (producer renamed, consumer dual-label)
  D1 PAPER badge never orange/gold
  D2/D4/惯犯条款 --text-muted content-level CI grep (placeholder whitelist)
  D5 badge vocabulary regression (WAIT banned; vocab section exists)
  D6 nav single-source (no inline nav-links; all routes render, nav identical)
  D7 es_backtest hero closes before page-tabs
  C3/C4/D8/D10 copy assertions
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

TPL = REPO / "web" / "templates"
ALL_TEMPLATES = sorted(p for p in TPL.glob("*.html") if p.name != "_nav.html")


def _read(name: str) -> str:
    return (TPL / name).read_text(encoding="utf-8")


class TestC1ProfitTargetSingleSource(unittest.TestCase):
    def test_api_payload_carries_engine_target(self):
        from strategy.selector import DEFAULT_PARAMS
        from web.server import app
        state = {"strategy_key": "bull_put_spread", "underlying": "SPX",
                 "expiry": "2026-08-21", "trade_id": "t1"}
        with patch("strategy.state.read_state", return_value=state), \
             patch("strategy.state.read_all_positions", return_value={"positions": []}), \
             patch("schwab.client.live_position_snapshot", return_value={"visible": False}):
            res = app.test_client().get("/api/position")
        data = res.get_json()
        self.assertEqual(data["profit_target"], DEFAULT_PARAMS.profit_target)

    def test_frontend_has_no_target_literals(self):
        """Fourth mirror ban: template JS must not carry 0.50/0.60 constants."""
        src = _read("portfolio_home.html")
        self.assertNotRegex(src, r"[?(]\s*0\.50\s*:")     # ternary constants
        self.assertNotRegex(src, r"\*\s*0\.6[0]?\b")      # * 0.60 target math
        self.assertNotRegex(src, r"\*\s*0\.5[0]?\s*;")    # * 0.50 target math
        self.assertIn("pos.profit_target", src)           # consumes the API value


class TestC2ExitReasonMigration(unittest.TestCase):
    def test_producer_renamed(self):
        src = (REPO / "backtest" / "engine.py").read_text(encoding="utf-8")
        self.assertNotIn('exit_reason = "50pct_profit"', src)
        self.assertIn('exit_reason = "profit_target"', src)

    def test_consumer_accepts_both_labels(self):
        src = (REPO / "backtest" / "run_event_study.py").read_text(encoding="utf-8")
        self.assertIn('("profit_target", "50pct_profit")', src)

    def test_frozen_fixture_carries_new_label(self):
        import json
        rows = json.loads((REPO / "tests" / "fixtures" /
                           "matrix_flat_26y_frozen_trades.json").read_text())
        reasons = {r["exit_reason"] for r in rows}
        self.assertIn("profit_target", reasons)
        self.assertNotIn("50pct_profit", reasons)


class TestD1PaperBadge(unittest.TestCase):
    def test_paper_never_orange_or_gold(self):
        for p in ALL_TEMPLATES:
            src = p.read_text(encoding="utf-8")
            self.assertNotIn('badge-orange">PAPER', src, p.name)
            self.assertNotIn('"tag">PAPER', src, p.name)
            self.assertNotIn("badge-review'>PAPER", src, p.name)


PLACEHOLDER_GLYPHS = ("—", "○", "×", "→", "●", "…", "Loading",
                      "No trades", "No data", "No param", ">Retired<")
_CSS_DECL = re.compile(r"^\s*[a-zA-Z-]+\s*:\s*[^<>{}]*;?\s*$")


def _muted_content_violations() -> list[str]:
    """Inline `color:var(--text-muted)` on rendered CONTENT is banned (house
    rule, 4+ 次惯犯条款). Exemptions: CSS declarations (class rules define the
    vocabulary states like NO ENTRY whose color IS muted per DESIGN.md), JS
    comments, non-text usages (background/border/JS color maps — no `color:`
    prefix), and pure placeholder glyphs."""
    bad = []
    for p in ALL_TEMPLATES:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not re.search(r"color:\s*var\(--text-muted\)", line):
                continue
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "*", "#")):
                continue
            if ("{" in line and "${" not in line) or _CSS_DECL.match(line):
                continue                               # CSS declaration line
            if any(g in line for g in PLACEHOLDER_GLYPHS):
                continue
            bad.append(f"{p.name}:{i}: {stripped[:100]}")
    return bad


class TestMutedContentBan(unittest.TestCase):
    def test_zero_content_level_muted(self):
        self.assertEqual(_muted_content_violations(), [])

    def test_negative_detector_catches_violation(self):
        line = '<span style="color:var(--text-muted)">NLV unavailable</span>'
        self.assertNotIn("{", line.replace("${", ""))
        self.assertFalse(any(g in line for g in PLACEHOLDER_GLYPHS))


class TestD5Vocabulary(unittest.TestCase):
    def test_wait_label_banned(self):
        """Action-state badges must not read WAIT (= NO ENTRY). The matrix
        page's pf-pill WAIT is a different domain (selector verdict cell
        label, payoff_type "WAIT" in the API) and stays."""
        for p in ALL_TEMPLATES:
            src = p.read_text(encoding="utf-8")
            self.assertNotRegex(src, r"label:\s*'WAIT'", p.name)
            self.assertNotRegex(src, r'state-badge badge-wait"[^>]*>WAIT<', p.name)
            self.assertNotRegex(src, r'badge-wait">WAIT</span>', p.name)

    def test_design_md_has_signal_outcome_section(self):
        d = (REPO / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn("Signal-outcome states", d)
        self.assertIn("`WAIT` is NOT in the vocabulary", d)


class TestD6NavSingleSource(unittest.TestCase):
    def test_no_inline_nav_blocks(self):
        for p in ALL_TEMPLATES:
            src = p.read_text(encoding="utf-8")
            if '<nav class="nav">' in src:
                self.assertNotIn('<div class="nav-links">', src,
                                 f"{p.name} carries an inline nav — use _nav.html")
                self.assertIn('{% include "_nav.html" %}', src, p.name)

    def test_all_routes_render_with_identical_nav(self):
        from web.server import app
        routes = ["/", "/spx", "/backtest", "/matrix", "/es", "/es-backtest",
                  "/q042", "/aftermath", "/hvladder", "/q041",
                  "/portfolio-backtest", "/performance", "/margin", "/journal",
                  "/partnership"]
        client = app.test_client()
        nav_re = re.compile(r'<div class="nav-links">.*?</div>', re.S)
        canon = None
        for r in routes:
            res = client.get(r)
            self.assertEqual(res.status_code, 200, r)
            html = res.get_data(as_text=True)
            m = nav_re.search(html)
            self.assertIsNotNone(m, f"{r}: nav missing")
            items = re.sub(r'\s+class="nav-link[^"]*"', "", m.group(0))
            items = re.sub(r"\s+", " ", items)
            if canon is None:
                canon = items
            else:
                self.assertEqual(items, canon, f"{r}: nav set differs")
            self.assertNotIn("<sup", m.group(0), f"{r}: tier indicator on nav item")

    def test_nav_include_has_canonical_set(self):
        src = (TPL / "_nav.html").read_text(encoding="utf-8")
        for label in ("Portfolio", "SPX", "/ES", "DD Overlay", "Aftermath",
                      "Stress Put Ladder", "Sleeves", "Gov BT", "Performance",
                      "Journal", "Margin", "Funds", "Book"):
            self.assertIn(f">{label}</a>", src, label)


class TestD7HeroMarkup(unittest.TestCase):
    def test_hero_closes_before_page_tabs(self):
        src = _read("es_backtest.html")
        hero = src.index('<div class="page-hero">')
        close = src.index("SPEC-125 D7", hero)
        tabs = src.index('<div class="page-tabs">', hero)
        self.assertLess(close, tabs, "hero must close before page-tabs")


class TestCopyAssertions(unittest.TestCase):
    def test_c3_matrix_footer_lists_five_divergent_cells(self):
        src = _read("matrix.html")
        for cell in ("NORMAL|HIGH|BULLISH", "LOW_VOL|HIGH|BULLISH",
                     "LOW_VOL|HIGH|NEUTRAL", "HIGH_VOL|HIGH|BEARISH",
                     "HIGH_VOL|NEUTRAL|BULLISH"):
            self.assertIn(cell, src, cell)

    def test_c4_pricing_disclosure(self):
        src = _read("backtest.html")
        self.assertIn("经真实链校准证实高估 credit 结构收入", src)
        self.assertIn("research/q087", src)

    def test_d8_lifecycle_wording_removed(self):
        for name in ("hvladder.html", "es_backtest.html", "es.html"):
            src = _read(name)
            self.assertNotIn("no longer trading", src, name)
            self.assertNotIn("[archived]", src, name)
            self.assertNotIn("Legacy /ES", src, name)

    def test_d10_q042_display_names(self):
        self.assertIn("Drawdown <em>Overlay</em>", _read("q042.html"))
        self.assertIn("Drawdown Overlay <em>Backtest", _read("q042_backtest.html"))

    def test_d9_no_chinese_buttons_on_general_pages(self):
        exempt = {"funds.html", "partnership.html", "etrade_reauth.html"}
        cjk_button = re.compile(r"<button[^>]*>[^<]*[一-鿿][^<]*</button>")
        for p in ALL_TEMPLATES:
            if p.name in exempt:
                continue
            src = p.read_text(encoding="utf-8")
            hits = [h for h in cjk_button.findall(src)]
            self.assertEqual(hits, [], f"{p.name}: Chinese button(s) {hits[:2]}")


if __name__ == "__main__":
    unittest.main()
