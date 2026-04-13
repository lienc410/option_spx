import unittest

import pandas as pd

from signals.iv_rank import IVSignal, IVSnapshot, get_current_iv_snapshot
from signals.trend import TrendSignal
from signals.vix_regime import Regime, Trend
from strategy.selector import (
    StrategyName,
    _build_recommendation,
    _compute_size_tier,
    select_strategy,
)
from tests.test_strategy_unification import make_trend, make_vix


def make_iv_snapshot(
    *,
    signal: IVSignal = IVSignal.NEUTRAL,
    iv_rank: float = 45.0,
    iv_percentile: float = 45.0,
    vix: float = 18.0,
    ivp63: float = 45.0,
    ivp252: float = 45.0,
    regime_decay: bool | None = None,
) -> IVSnapshot:
    if regime_decay is None:
        regime_decay = (ivp252 >= 50.0) and (ivp63 < 50.0)
    return IVSnapshot(
        date="2026-04-10",
        vix=vix,
        iv_rank=iv_rank,
        iv_percentile=iv_percentile,
        iv_signal=signal,
        iv_52w_high=40.0,
        iv_52w_low=10.0,
        ivp63=ivp63,
        ivp252=ivp252,
        regime_decay=regime_decay,
    )


def make_iv_frame(*, lower_252: int, lower_63: int, current: float = 50.0) -> pd.DataFrame:
    older_len = 189
    recent_len = 62
    older_lower = max(0, min(older_len, lower_252 - lower_63))
    older_higher = older_len - older_lower
    recent_lower = max(0, min(recent_len, lower_63))
    recent_higher = recent_len - recent_lower
    values = ([40.0] * older_lower) + ([60.0] * older_higher) + ([40.0] * recent_lower) + ([60.0] * recent_higher) + [current]
    index = pd.bdate_range("2025-04-22", periods=len(values))
    return pd.DataFrame({"vix": values}, index=index)


class Spec048055Tests(unittest.TestCase):
    def test_t1_ivs_snapshot_ivp63_exists_and_is_float(self) -> None:
        snap = get_current_iv_snapshot(make_iv_frame(lower_252=151, lower_63=25))
        self.assertIsInstance(snap.ivp63, float)

    def test_t2_ivp252_equals_iv_percentile(self) -> None:
        snap = get_current_iv_snapshot(make_iv_frame(lower_252=151, lower_63=25))
        self.assertEqual(snap.ivp252, snap.iv_percentile)

    def test_t3_regime_decay_true_when_long_high_short_low(self) -> None:
        snap = get_current_iv_snapshot(make_iv_frame(lower_252=151, lower_63=25))
        self.assertTrue(snap.regime_decay)

    def test_t4_regime_decay_false_when_both_high(self) -> None:
        snap = get_current_iv_snapshot(make_iv_frame(lower_252=151, lower_63=38))
        self.assertFalse(snap.regime_decay)

    def test_t5_low_vol_bullish_ivp252_35_waits_gate1(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.NEUTRAL, iv_percentile=45.0, ivp63=45.0, ivp252=35.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertIn("ivp252=35", rec.rationale)
        self.assertIn("marginal zone", rec.rationale)

    def test_t6_low_vol_bullish_iv_high_waits_gate2(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.HIGH, iv_rank=60.0, iv_percentile=50.0, ivp63=45.0, ivp252=20.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertIn("IV=HIGH", rec.rationale)

    def test_t7_low_vol_bullish_both_high_allows_diagonal(self) -> None:
        # SPEC-056c: Gate 3 (both-high) removed — both-high now enters DIAGONAL normally.
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.NEUTRAL, iv_percentile=45.0, ivp63=60.0, ivp252=60.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)

    def test_t8_low_vol_bullish_local_spike_allows_diagonal(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.NEUTRAL, iv_percentile=25.0, ivp63=60.0, ivp252=25.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)
        self.assertTrue(rec.local_spike)

    def test_t9_high_vol_bearish_ivp63_75_waits(self) -> None:
        rec = select_strategy(
            make_vix(vix=28.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.HIGH, iv_rank=70.0, iv_percentile=80.0, ivp63=75.0, ivp252=80.0, vix=28.0),
            make_trend(signal=TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertIn("ivp63=75", rec.rationale)

    def test_t10_high_vol_bearish_iv_high_routes_ic_hv(self) -> None:
        # SPEC-060 Change 1: HIGH_VOL + BEARISH + IV=HIGH → IC_HV
        rec = select_strategy(
            make_vix(vix=28.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.HIGH, iv_rank=70.0, iv_percentile=80.0, ivp63=65.0, ivp252=80.0, vix=28.0),
            make_trend(signal=TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR_HV)

    def test_t11_compute_size_tier_diagonal_regime_decay_full(self) -> None:
        size = _compute_size_tier(
            StrategyName.BULL_CALL_DIAGONAL.value,
            make_iv_snapshot(signal=IVSignal.NEUTRAL, ivp63=40.0, ivp252=60.0, regime_decay=True),
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.RISING),
            IVSignal.NEUTRAL,
            TrendSignal.BULLISH,
        )
        self.assertIn("regime decay", size)

    def test_t12_compute_size_tier_bps_regime_decay_does_not_override(self) -> None:
        size = _compute_size_tier(
            StrategyName.BULL_PUT_SPREAD.value,
            make_iv_snapshot(signal=IVSignal.NEUTRAL, ivp63=40.0, ivp252=60.0, regime_decay=True),
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.RISING),
            IVSignal.NEUTRAL,
            TrendSignal.BULLISH,
        )
        self.assertNotIn("regime decay", size)
        self.assertIn("Half size", size)

    def test_t13_recommendation_local_spike_defaults_false(self) -> None:
        rec = _build_recommendation(
            StrategyName.BULL_PUT_SPREAD,
            vix=make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            iv=make_iv_snapshot(signal=IVSignal.NEUTRAL),
            trend=make_trend(signal=TrendSignal.BULLISH),
            rationale="test",
            position_action="OPEN",
        )
        self.assertFalse(rec.local_spike)

    def test_t14_low_vol_bullish_local_spike_sets_flag_true(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.NEUTRAL, iv_percentile=25.0, ivp63=60.0, ivp252=25.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertTrue(rec.local_spike)

    def test_t15_low_vol_bullish_non_local_spike_sets_flag_false(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.NEUTRAL, iv_percentile=25.0, ivp63=40.0, ivp252=25.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)
        self.assertFalse(rec.local_spike)

    def test_t16_gate_order_gate1_blocks_before_others(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.HIGH, iv_rank=60.0, iv_percentile=50.0, ivp63=60.0, ivp252=35.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertIn("marginal zone", rec.rationale)
        self.assertNotIn("IV=HIGH", rec.rationale)
        self.assertNotIn("both-high", rec.rationale)

    def test_t17_gate_order_gate2_blocks_after_gate1_pass(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.HIGH, iv_rank=60.0, iv_percentile=50.0, ivp63=40.0, ivp252=20.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertIn("IV=HIGH", rec.rationale)
        self.assertNotIn("both-high", rec.rationale)

    def test_t18_gate_order_both_high_reaches_diagonal(self) -> None:
        # SPEC-056c: Gate 3 removed. both-high passes Gate 1+2 and reaches DIAGONAL.
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.NEUTRAL, iv_percentile=45.0, ivp63=60.0, ivp252=60.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)
        self.assertNotIn("both-high", rec.rationale)

    def test_t19_gate_order_passes_all_to_diagonal(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv_snapshot(signal=IVSignal.NEUTRAL, iv_percentile=20.0, ivp63=40.0, ivp252=20.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)


if __name__ == "__main__":
    unittest.main()
