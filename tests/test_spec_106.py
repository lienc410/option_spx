"""Tests for SPEC-106 — Strategy Matrix Selector-Consistency & Payoff Semantics."""

import unittest

from strategy.selector import (
    DEFAULT_PARAMS,
    get_payoff_type,
    select_strategy,
)
from web.server import (
    _synth_iv_snapshot,
    _synth_trend_snapshot,
    _synth_vix_snapshot,
    app,
)


class GetPayoffTypeTests(unittest.TestCase):
    """SPEC-106 §3.2 — pure mapping table."""

    def test_credit_strategies(self):
        for name in (
            "Bull Put Spread",
            "Bull Put Spread (High Vol)",
            "Iron Condor",
            "Iron Condor (High Vol)",
            "Bear Call Spread (High Vol)",
            "ES Short Put",
        ):
            self.assertEqual(get_payoff_type(name), "CREDIT", msg=name)

    def test_debit_strategies(self):
        for name in ("Bull Call Diagonal", "Calendar", "Diagonal"):
            self.assertEqual(get_payoff_type(name), "DEBIT", msg=name)

    def test_wait(self):
        self.assertEqual(get_payoff_type("Reduce / Wait"), "WAIT")
        self.assertEqual(get_payoff_type("REDUCE_WAIT"), "WAIT")
        self.assertEqual(get_payoff_type(None), "WAIT")

    def test_research_only(self):
        self.assertEqual(get_payoff_type("Stress Put Ladder"), "RESEARCH_ONLY")
        self.assertEqual(get_payoff_type("HV Ladder"), "RESEARCH_ONLY")

    def test_unknown_strategy_falls_back_to_neutral(self):
        self.assertEqual(get_payoff_type("Some New Strategy 9000"), "NEUTRAL_PREMIUM")


class StrategyMatrixEndpointTests(unittest.TestCase):
    """SPEC-106 §3.1 — /api/strategy-matrix surface."""

    @classmethod
    def setUpClass(cls):
        # Bust the 5min cache so each test class run hits the live computation
        from web import server as srv
        srv._STRATEGY_MATRIX_CACHE.clear()
        cls.client = app.test_client()
        cls.data = cls.client.get("/api/strategy-matrix").get_json()

    def test_endpoint_returns_36_cells(self):
        """AC-106-2."""
        self.assertEqual(len(self.data["cells"]), 36)

    def test_every_cell_has_required_fields(self):
        """AC-106-3 — schema completeness."""
        required = {"cell_id", "vix_regime", "iv_bucket", "trend",
                    "selector_verdict", "payoff_type", "gated",
                    "is_current_active_cell", "reason"}
        for cell in self.data["cells"]:
            missing = required - set(cell.keys())
            self.assertFalse(missing, msg=f"{cell['cell_id']} missing: {missing}")

    def test_normal_high_bullish_is_gated_reduce_wait(self):
        """AC-106-1 — the original PM-flagged cell."""
        cell = next(c for c in self.data["cells"]
                    if c["cell_id"] == "NORMAL|HIGH|BULLISH")
        self.assertEqual(cell["selector_verdict"], "Reduce / Wait")
        self.assertEqual(cell["payoff_type"], "WAIT")
        self.assertTrue(cell["gated"])
        # SPEC-060 reason should mention "alpha"
        self.assertIn("alpha", cell["reason"].lower())
        # Historical reference must still surface so PM knows what would have traded
        self.assertEqual(cell["historical_reference_strategy"], "Bull Put Spread")
        # Gated cells must NOT carry historical stats (avoid contradiction)
        self.assertIsNone(cell["wr_3y"])
        self.assertIsNone(cell["avg_pnl_3y"])

    def test_low_vol_low_iv_bullish_is_bull_call_diagonal_debit(self):
        """AC-106-7 — debit/diagonal semantics in LOW_VOL regime."""
        cell = next(c for c in self.data["cells"]
                    if c["cell_id"] == "LOW_VOL|LOW|BULLISH")
        self.assertEqual(cell["selector_verdict"], "Bull Call Diagonal")
        self.assertEqual(cell["payoff_type"], "DEBIT")
        self.assertFalse(cell["gated"])

    def test_normal_low_bullish_routes_bcd_carve(self):
        """AC-106-8 originally pinned this cell to Reduce/Wait (thin premium).
        SPEC-113 (ratified) carves VIX<18 to Bull Call Diagonal — the matrix
        endpoint synthesizes this cell below 18, so the carve is the correct
        verdict now. (Stale pin fixed in the SPEC-123 batch.)"""
        cell = next(c for c in self.data["cells"]
                    if c["cell_id"] == "NORMAL|LOW|BULLISH")
        self.assertEqual(cell["selector_verdict"], "Bull Call Diagonal")
        self.assertEqual(cell["payoff_type"], "DEBIT")

    def test_extreme_vol_routes_to_reduce_wait(self):
        """All 9 EXTREME_VOL cells must gate (vix ≥ extreme_vix threshold)."""
        extreme = [c for c in self.data["cells"] if c["vix_regime"] == "EXTREME_VOL"]
        self.assertEqual(len(extreme), 9)
        for cell in extreme:
            self.assertTrue(cell["gated"], msg=cell["cell_id"])
            self.assertEqual(cell["payoff_type"], "WAIT")


class LiveActiveCellIVDivergenceTests(unittest.TestCase):
    """Code-review finding 2026-05-26: _live_active_cell() must use selector's
    _effective_iv_signal (IVP override fires when IVR/IVP diverge by >15pt),
    not raw iv_signal. Otherwise the NOW highlight points to the wrong cell."""

    def test_iv_divergence_promotes_ivp_high(self):
        from unittest.mock import patch
        from signals.iv_rank import IVSnapshot, IVSignal
        from signals.trend import TrendSignal, TrendSnapshot
        from signals.vix_regime import Regime, Trend, VixSnapshot
        from strategy.selector import Recommendation, StrategyName
        from web.server import _live_active_cell

        # Diverged inputs: IVR signal says NEUTRAL (40), IVP says HIGH (72) — override path
        iv = IVSnapshot(
            date="t", vix=17.0, iv_rank=40.0, iv_percentile=72.0,
            iv_signal=IVSignal.NEUTRAL, iv_52w_high=85.0, iv_52w_low=10.0,
            ivp63=60.0, ivp252=72.0, regime_decay=False,
        )
        vix = VixSnapshot(
            date="t", vix=17.0, regime=Regime.NORMAL, trend=Trend.FLAT,
            vix_5d_avg=17.0, vix_5d_ago=17.0, transition_warning=False,
            vix3m=None, backwardation=False, vix_peak_10d=17.0,
        )
        trend = TrendSnapshot(
            date="t", spx=5000.0, ma20=4850.0, ma50=4850.0,
            ma_gap_pct=0.031, signal=TrendSignal.BULLISH, above_200=True,
        )
        fake_rec = Recommendation(
            strategy_key="bull_put_spread",
            strategy=StrategyName.BULL_PUT_SPREAD,
            underlying="SPX", legs=[],
            max_risk="—", target_return="—",
            size_rule="—", roll_rule="—",
            rationale="test", position_action="OPEN",
            vix_snapshot=vix, iv_snapshot=iv, trend_snapshot=trend,
        )
        with patch("strategy.selector.get_recommendation", return_value=fake_rec):
            result = _live_active_cell()
        self.assertEqual(
            result, ("NORMAL", "HIGH", "BULLISH"),
            msg=f"_live_active_cell should apply IVP override; got {result}",
        )


class SelectorPayoffPopulationTests(unittest.TestCase):
    """SPEC-106 §10 — Recommendation dataclass carries payoff_type."""

    def test_select_strategy_populates_payoff_type_credit(self):
        rec = select_strategy(
            _synth_vix_snapshot("NORMAL"),
            _synth_iv_snapshot("NEUTRAL"),
            _synth_trend_snapshot("BULLISH"),
            DEFAULT_PARAMS,
        )
        # NORMAL + NEUTRAL IV + BULLISH → BPS (CREDIT)
        self.assertEqual(rec.payoff_type, "CREDIT")
        self.assertEqual(rec.strategy.value, "Bull Put Spread")

    def test_select_strategy_populates_payoff_type_wait(self):
        rec = select_strategy(
            _synth_vix_snapshot("EXTREME_VOL"),
            _synth_iv_snapshot("HIGH"),
            _synth_trend_snapshot("BULLISH"),
            DEFAULT_PARAMS,
        )
        self.assertEqual(rec.payoff_type, "WAIT")
        self.assertEqual(rec.strategy.value, "Reduce / Wait")

    def test_select_strategy_populates_payoff_type_debit(self):
        rec = select_strategy(
            _synth_vix_snapshot("LOW_VOL"),
            _synth_iv_snapshot("LOW"),
            _synth_trend_snapshot("BULLISH"),
            DEFAULT_PARAMS,
        )
        self.assertEqual(rec.payoff_type, "DEBIT")
        self.assertEqual(rec.strategy.value, "Bull Call Diagonal")


if __name__ == "__main__":
    unittest.main()
