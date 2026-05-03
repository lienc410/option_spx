import unittest
from dataclasses import replace

from strategy.overlay import (
    PortfolioState,
    build_portfolio_state,
    evaluate_overlay_f,
    short_gamma_count_from_positions,
)
from strategy.selector import DEFAULT_PARAMS, StrategyName
from backtest.engine import Position, _position_contracts


class _Pos:
    def __init__(self, strategy):
        self.strategy = strategy


class OverlayFGateTests(unittest.TestCase):
    def test_disabled_is_inert(self):
        d = evaluate_overlay_f(
            mode="disabled",
            strategy_key="iron_condor_hv",
            vix=24.0,
            portfolio_state=PortfolioState(idle_bp_pct=0.9, sg_count=0),
        )
        self.assertFalse(d.would_fire)
        self.assertEqual(d.effective_factor, 1.0)
        self.assertEqual(d.rationale, "")

    def test_active_fires_for_ic_hv_idle_bp_vix_and_sg_count(self):
        d = evaluate_overlay_f(
            mode="active",
            strategy_key="iron_condor_hv",
            vix=24.0,
            portfolio_state=PortfolioState(idle_bp_pct=0.75, sg_count=1),
        )
        self.assertTrue(d.would_fire)
        self.assertEqual(d.effective_factor, 2.0)

    def test_shadow_logs_intent_but_keeps_factor_one(self):
        d = evaluate_overlay_f(
            mode="shadow",
            strategy_key="iron_condor_hv",
            vix=24.0,
            portfolio_state=PortfolioState(idle_bp_pct=0.75, sg_count=1),
        )
        self.assertTrue(d.would_fire)
        self.assertEqual(d.effective_factor, 1.0)

    def test_sg_count_uses_position_count_not_family_dedup(self):
        count = short_gamma_count_from_positions([
            _Pos(StrategyName.IRON_CONDOR_HV),
            _Pos(StrategyName.IRON_CONDOR_HV),
        ])
        self.assertEqual(count, 2)

    def test_live_state_failure_fails_closed(self):
        d = evaluate_overlay_f(
            mode="active",
            strategy_key="iron_condor_hv",
            vix=24.0,
            portfolio_state=PortfolioState(idle_bp_pct=None, sg_count=None, valid=False, stale=True),
        )
        self.assertFalse(d.would_fire)
        self.assertTrue(d.fail_closed)
        self.assertEqual(d.effective_factor, 1.0)

    def test_params_default_shadow(self):
        self.assertEqual(DEFAULT_PARAMS.overlay_f_mode, "shadow")
        self.assertEqual(replace(DEFAULT_PARAMS, overlay_f_mode="shadow").overlay_f_mode, "shadow")

    def test_portfolio_state_uses_idle_bp_and_position_count(self):
        state = build_portfolio_state(
            positions=[_Pos(StrategyName.BULL_PUT_SPREAD), _Pos(StrategyName.IRON_CONDOR_HV)],
            used_bp_pct=0.25,
        )
        self.assertAlmostEqual(state.idle_bp_pct, 0.75)
        self.assertEqual(state.sg_count, 2)

    def test_overlay_factor_doubles_position_contracts(self):
        pos = Position(
            strategy=StrategyName.IRON_CONDOR_HV,
            underlying="SPX",
            entry_date="2026-05-03",
            entry_spx=5000.0,
            entry_vix=25.0,
            entry_sigma=0.25,
            bp_per_contract=1000.0,
            bp_target=0.07,
            overlay_factor=2.0,
        )
        self.assertAlmostEqual(_position_contracts(pos, 100000.0), 14.0)


if __name__ == "__main__":
    unittest.main()
