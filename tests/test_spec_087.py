"""
tests/test_spec_087.py — SPEC-087 Portfolio Command Center Phase 1

AC1: GET /spx returns 200
AC2: GET / returns 200 and renders portfolio_home.html (not a redirect)
AC3: portfolio_home.html response contains "Portfolio" nav link
AC4: /api/recommendation, /api/es/recommendation, /api/sleeve-candidates response shapes unchanged
AC6: When /api/es/recommendation is mocked to fail, /api/portfolio/summary still works
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.state as state_mod
from web.server import app


class Spec087RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.client = app.test_client()
        self.orig_state_file = state_mod.STATE_FILE
        state_mod.STATE_FILE = str(Path(self.tmpdir.name) / "current_position.json")
        # Isolate Q041 env vars
        self._orig_ledger = os.environ.get("Q041_PAPER_LEDGER_FILE")
        self._orig_config = os.environ.get("Q041_PAPER_CONFIG_FILE")
        self._orig_attr   = os.environ.get("Q041_PORTFOLIO_ATTRIBUTION_FILE")
        os.environ["Q041_PAPER_LEDGER_FILE"]          = str(Path(self.tmpdir.name) / "q041_ledger.jsonl")
        os.environ["Q041_PAPER_CONFIG_FILE"]           = str(Path(self.tmpdir.name) / "q041_config.json")
        os.environ["Q041_PORTFOLIO_ATTRIBUTION_FILE"]  = str(Path(self.tmpdir.name) / "q041_attr.json")

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self.orig_state_file
        self._restore("Q041_PAPER_LEDGER_FILE",         self._orig_ledger)
        self._restore("Q041_PAPER_CONFIG_FILE",          self._orig_config)
        self._restore("Q041_PORTFOLIO_ATTRIBUTION_FILE", self._orig_attr)

    def _restore(self, key: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    # ── AC1 ──────────────────────────────────────────────────────────────────
    def test_ac1_spx_route_returns_200(self) -> None:
        """GET /spx must return HTTP 200."""
        res = self.client.get("/spx")
        self.assertEqual(res.status_code, 200)

    # ── AC2 ──────────────────────────────────────────────────────────────────
    def test_ac2_root_returns_200_not_redirect(self) -> None:
        """GET / must return HTTP 200 (not 301/302) and render portfolio_home.html."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200,
            "/ must render portfolio_home.html directly — no redirect")

    # ── AC3 ──────────────────────────────────────────────────────────────────
    def test_ac3_portfolio_home_contains_portfolio_nav_link(self) -> None:
        """portfolio_home.html response must contain a 'Portfolio' nav link."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode()
        self.assertIn("Portfolio", html,
            "portfolio_home.html must include 'Portfolio' in the nav")
        # Must also contain the nav link pointing to /
        self.assertIn('href="/"', html)

    # ── AC4 — /api/recommendation shape unchanged ─────────────────────────────
    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_ac4_recommendation_shape_unchanged(self, mock_rec, _mock_hours) -> None:
        """GET /api/recommendation must still return the existing shape."""
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy
        from tests.test_strategy_unification import make_iv, make_trend, make_vix

        mock_rec.return_value = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        res = self.client.get("/api/recommendation")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        # Required top-level fields from existing spec
        for field in ("strategy", "strategy_key", "position_action", "underlying",
                      "vix_snapshot", "iv_snapshot", "trend_snapshot"):
            self.assertIn(field, data,
                f"/api/recommendation missing expected field: {field}")
        # Must NOT contain any new SPEC-087 portal fields
        self.assertNotIn("portfolio_command_center", data)

    # ── AC4 — /api/es/recommendation shape unchanged ─────────────────────────
    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_es_recommendation")
    def test_ac4_es_recommendation_shape_unchanged(self, mock_es_rec, _mock_hours) -> None:
        """GET /api/es/recommendation must return the existing shape."""
        from dataclasses import dataclass

        @dataclass
        class FakeEsRec:
            strategy: str = "/ES Short Put"
            strategy_key: str = "es_short_put"
            underlying: str = "/ES"
            position_action: str = "OPEN"
            rationale: str = "test rationale"
            vix_snapshot: dict = None
            legs: list = None
            max_risk: str = "—"
            target_return: str = "—"
            size_rule: str = "—"
            roll_rule: str = "—"
            guardrail_label: str = ""
            re_enable_hint: str = ""
            canonical_strategy: str = ""
            macro_warning: bool = False
            backwardation: bool = False
            shock_mode: str = "disabled"
            overlay_mode: str = "inactive"
            overlay_f_factor: float = 1.0
            overlay_f_rationale: str = ""
            overlay_f_would_fire: bool = False
            open: bool = False

            def __post_init__(self):
                if self.vix_snapshot is None:
                    self.vix_snapshot = {"vix": 20.0, "regime": "NORMAL", "date": "2026-05-07"}
                if self.legs is None:
                    self.legs = []

        mock_es_rec.return_value = FakeEsRec()
        res = self.client.get("/api/es/recommendation")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("strategy_key", data)
        self.assertIn("strategy", data)

    # ── AC4 — /api/sleeve-candidates shape unchanged ─────────────────────────
    def test_ac4_sleeve_candidates_shape_unchanged(self) -> None:
        """GET /api/sleeve-candidates must return sleeve_candidates + review_only arrays."""
        res = self.client.get("/api/sleeve-candidates")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("sleeve_candidates", data)
        self.assertIn("review_only", data)
        self.assertIsInstance(data["sleeve_candidates"], list)
        self.assertIsInstance(data["review_only"], list)

    # ── AC6 — ES failure does not crash /api/portfolio/summary ───────────────
    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_es_recommendation", side_effect=RuntimeError("ES API down"))
    def test_ac6_es_failure_does_not_affect_portfolio_summary(self, _mock_fail, _mock_hours) -> None:
        """When /api/es/recommendation errors, /api/portfolio/summary still returns 200."""
        # /es/recommendation should return 500
        res_es = self.client.get("/api/es/recommendation")
        self.assertEqual(res_es.status_code, 500)
        data_es = res_es.get_json()
        self.assertIn("error", data_es)

        # portfolio/summary is independent — must still return 200
        res_summary = self.client.get("/api/portfolio/summary")
        self.assertEqual(res_summary.status_code, 200)
        data_summary = res_summary.get_json()
        self.assertIn("total_used_bp_pct", data_summary)
        self.assertIn("idle_capacity_pct", data_summary)

    # ── Nav structure sanity check (all five links present) ──────────────────
    def test_spx_page_contains_five_nav_links(self) -> None:
        """spx.html must contain all five nav links."""
        res = self.client.get("/spx")
        html = res.data.decode()
        for label in ("Portfolio", "SPX", "/ES", "Q041", "Backtest"):
            self.assertIn(label, html,
                f"spx.html nav missing: {label}")

    def test_portfolio_home_contains_five_nav_links(self) -> None:
        """portfolio_home.html must contain all five nav links."""
        res = self.client.get("/")
        html = res.data.decode()
        for label in ("Portfolio", "SPX", "/ES", "Q041", "Backtest"):
            self.assertIn(label, html,
                f"portfolio_home.html nav missing: {label}")

    def test_spx_page_has_active_spx_link(self) -> None:
        """/spx nav must mark SPX as active."""
        res = self.client.get("/spx")
        html = res.data.decode()
        self.assertIn('href="/spx" class="nav-link active"', html)

    def test_portfolio_home_has_active_portfolio_link(self) -> None:
        """portfolio_home.html nav must mark Portfolio as active."""
        res = self.client.get("/")
        html = res.data.decode()
        self.assertIn('href="/" class="nav-link active"', html)

    def test_portfolio_home_contains_todays_actions_zone(self) -> None:
        """portfolio_home.html must include the Today's Actions section."""
        res = self.client.get("/")
        html = res.data.decode()
        self.assertIn("Today's Actions", html)

    def test_portfolio_home_contains_portfolio_snapshot_zone(self) -> None:
        """portfolio_home.html must include the Portfolio Snapshot section."""
        res = self.client.get("/")
        html = res.data.decode()
        self.assertIn("Portfolio Snapshot", html)


if __name__ == "__main__":
    unittest.main()
