import unittest

from signals.iv_rank import IVSignal, IVSnapshot
from signals.trend import TrendSignal, TrendSnapshot
from signals.vix_regime import Regime, Trend, VixSnapshot
from strategy.selector import StrategyName, is_aftermath, select_strategy


def make_vix(
    *,
    vix: float,
    regime: Regime,
    trend: Trend,
    backwardation: bool = False,
    vix_peak_10d: float | None = None,
) -> VixSnapshot:
    return VixSnapshot(
        date="2026-04-19",
        vix=vix,
        regime=regime,
        trend=trend,
        vix_5d_avg=vix,
        vix_5d_ago=vix,
        transition_warning=False,
        vix3m=(vix - 2.0) if backwardation else (vix + 2.0),
        backwardation=backwardation,
        vix_peak_10d=vix_peak_10d,
    )


def make_iv(*, signal: IVSignal, iv_rank: float = 75.0, iv_percentile: float = 80.0) -> IVSnapshot:
    return IVSnapshot(
        date="2026-04-19",
        vix=28.0,
        iv_rank=iv_rank,
        iv_percentile=iv_percentile,
        iv_signal=signal,
        iv_52w_high=40.0,
        iv_52w_low=10.0,
        ivp63=80.0,
        ivp252=iv_percentile,
    )


def make_trend(signal: TrendSignal) -> TrendSnapshot:
    return TrendSnapshot(
        date="2026-04-19",
        spx=5600.0,
        ma20=5580.0,
        ma50=5600.0,
        ma_gap_pct=0.0,
        signal=signal,
        above_200=True,
    )


class Spec064AftermathTests(unittest.TestCase):
    def test_ac1_is_aftermath_true_when_peak_and_off_peak_thresholds_met(self) -> None:
        self.assertTrue(
            is_aftermath(
                make_vix(vix=28.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT, vix_peak_10d=30.0)
            )
        )

    def test_ac1_is_aftermath_false_when_peak_below_threshold(self) -> None:
        self.assertFalse(
            is_aftermath(
                make_vix(vix=26.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT, vix_peak_10d=27.9)
            )
        )

    def test_ac1_is_aftermath_false_when_not_five_percent_off_peak(self) -> None:
        self.assertFalse(
            is_aftermath(
                make_vix(vix=28.6, regime=Regime.HIGH_VOL, trend=Trend.FLAT, vix_peak_10d=30.0)
            )
        )

    def test_ac1_is_aftermath_false_when_vix_is_extreme_vol(self) -> None:
        self.assertFalse(
            is_aftermath(
                make_vix(vix=40.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT, vix_peak_10d=42.0)
            )
        )

    def test_ac2_bearish_high_iv_aftermath_bypasses_rising_and_ivp63_gates(self) -> None:
        rec = select_strategy(
            make_vix(vix=28.0, regime=Regime.HIGH_VOL, trend=Trend.RISING, vix_peak_10d=30.0),
            make_iv(signal=IVSignal.HIGH, iv_rank=78.0, iv_percentile=82.0),
            make_trend(TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR_HV)
        self.assertIn("aftermath", rec.rationale)

    def test_ac3_neutral_high_iv_aftermath_non_backwardation_bypasses_rising_gate(self) -> None:
        rec = select_strategy(
            make_vix(vix=28.0, regime=Regime.HIGH_VOL, trend=Trend.RISING, vix_peak_10d=30.0),
            make_iv(signal=IVSignal.HIGH, iv_rank=78.0, iv_percentile=82.0),
            make_trend(TrendSignal.NEUTRAL),
        )
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR_HV)
        self.assertIn("aftermath", rec.rationale)

    def test_ac4_neutral_high_iv_aftermath_backwardation_still_waits(self) -> None:
        rec = select_strategy(
            make_vix(
                vix=28.0,
                regime=Regime.HIGH_VOL,
                trend=Trend.RISING,
                backwardation=True,
                vix_peak_10d=30.0,
            ),
            make_iv(signal=IVSignal.HIGH, iv_rank=78.0, iv_percentile=82.0),
            make_trend(TrendSignal.NEUTRAL),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertTrue(rec.backwardation)

    def test_ac5_extreme_vol_still_waits_even_if_aftermath_like_peak_exists(self) -> None:
        rec = select_strategy(
            make_vix(vix=40.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT, vix_peak_10d=45.0),
            make_iv(signal=IVSignal.HIGH, iv_rank=85.0, iv_percentile=88.0),
            make_trend(TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertIn("EXTREME_VOL", rec.rationale)

    def test_ac6_non_aftermath_bearish_iv_neutral_keeps_existing_ivp63_gate_behavior(self) -> None:
        rec = select_strategy(
            make_vix(vix=29.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT, vix_peak_10d=30.0),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=60.0, iv_percentile=55.0),
            make_trend(TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertIn("ivp63=80", rec.rationale)

    def test_ac7_normal_regime_unchanged(self) -> None:
        rec = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT, vix_peak_10d=30.0),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0),
            make_trend(TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_PUT_SPREAD)

    def test_ac8_high_vol_bullish_unchanged(self) -> None:
        rec = select_strategy(
            make_vix(vix=28.0, regime=Regime.HIGH_VOL, trend=Trend.RISING, vix_peak_10d=30.0),
            make_iv(signal=IVSignal.HIGH, iv_rank=78.0, iv_percentile=82.0),
            make_trend(TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertNotIn("aftermath", rec.rationale)


if __name__ == "__main__":
    unittest.main()
