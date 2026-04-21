from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

import backtest.engine as engine_mod
from backtest.shock_engine import ShockReport
from strategy.selector import (
    AFTERMATH_OFF_PEAK_PCT,
    DEFAULT_PARAMS,
    IC_HV_MAX_CONCURRENT,
    Recommendation,
    StrategyName,
)
from tests.test_spec_064 import make_iv, make_trend, make_vix


def _history_df(
    dates: pd.DatetimeIndex,
    column: str,
    value: float,
) -> pd.DataFrame:
    return pd.DataFrame({column: [value] * len(dates)}, index=dates)


def _mock_recommendation(strategy: StrategyName, date: str) -> Recommendation:
    vix = make_vix(
        vix=27.0,
        regime=engine_mod.Regime.HIGH_VOL,
        trend=engine_mod.Trend.FLAT,
        vix_peak_10d=30.0,
    )
    vix.date = date
    return Recommendation(
        strategy_key=(
            "iron_condor_hv"
            if strategy == StrategyName.IRON_CONDOR_HV
            else "bull_put_spread_hv"
            if strategy == StrategyName.BULL_PUT_SPREAD_HV
            else "reduce_wait"
        ),
        strategy=strategy,
        underlying="SPX",
        legs=[],
        max_risk="defined",
        target_return="50%",
        size_rule="test",
        roll_rule="21 DTE",
        rationale="test",
        position_action="OPEN" if strategy != StrategyName.REDUCE_WAIT else "WAIT",
        vix_snapshot=vix,
        iv_snapshot=make_iv(signal=engine_mod.IVSig.HIGH),
        trend_snapshot=make_trend(engine_mod.TrendSignal.NEUTRAL),
    )


class Spec066Tests(unittest.TestCase):
    def test_ac1_ic_hv_max_concurrent_constant(self) -> None:
        self.assertEqual(IC_HV_MAX_CONCURRENT, 2)

    def test_ac2_aftermath_off_peak_pct_is_ten_percent(self) -> None:
        self.assertEqual(AFTERMATH_OFF_PEAK_PCT, 0.10)

    def test_ac3_ic_hv_allows_two_slots(self) -> None:
        trades = self._run_slot_test(StrategyName.IRON_CONDOR_HV)
        self.assertEqual(sum(1 for t in trades if t.strategy == StrategyName.IRON_CONDOR_HV), 2)

    def test_ac4_non_ic_hv_remains_single_slot(self) -> None:
        trades = self._run_slot_test(StrategyName.BULL_PUT_SPREAD_HV)
        self.assertEqual(sum(1 for t in trades if t.strategy == StrategyName.BULL_PUT_SPREAD_HV), 1)

    def _run_slot_test(self, strategy: StrategyName) -> list[engine_mod.Trade]:
        dates = pd.bdate_range("2026-01-02", periods=70)
        vix_df = _history_df(dates, "vix", 27.0)
        spx_df = _history_df(dates, "close", 5800.0)
        vix3m_df = _history_df(dates, "vix3m", 29.0)
        open_dates = {str(d.date()) for d in dates[59:62]}

        def fake_select(vix_snap, _iv_snap, _trend_snap, _params=DEFAULT_PARAMS):
            if vix_snap.date in open_dates:
                return _mock_recommendation(strategy, vix_snap.date)
            return _mock_recommendation(StrategyName.REDUCE_WAIT, vix_snap.date)

        with (
            patch.object(engine_mod, "fetch_vix_history", return_value=vix_df),
            patch.object(engine_mod, "fetch_spx_history", return_value=spx_df),
            patch.object(engine_mod, "fetch_vix3m_history", return_value=vix3m_df),
            patch.object(engine_mod, "compute_iv_rank", return_value=75.0),
            patch.object(engine_mod, "compute_iv_percentile", return_value=80.0),
            patch.object(engine_mod, "select_strategy", side_effect=fake_select),
            patch.object(
                engine_mod,
                "run_shock_check",
                return_value=ShockReport(
                    date="2026-01-02",
                    nav=150000.0,
                    mode="disabled",
                    pre_scenarios={},
                    pre_max_core_loss_pct=0.0,
                    post_scenarios={},
                    post_max_core_loss_pct=0.0,
                    incremental_shock_pct=0.0,
                    budget_core=0.0,
                    budget_incremental=0.0,
                    approved=True,
                    reject_reason=None,
                ),
            ),
        ):
            result = engine_mod.run_backtest(
                start_date=str(dates[0].date()),
                end_date=str(dates[-1].date()),
                verbose=False,
            )
        return result.trades


if __name__ == "__main__":
    unittest.main()
