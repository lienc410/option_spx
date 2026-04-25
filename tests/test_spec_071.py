from __future__ import annotations

import unittest

from backtest.engine import _build_legs
from signals.iv_rank import IVSignal, IVSnapshot
from signals.trend import TrendSignal, TrendSnapshot
from signals.vix_regime import Regime, Trend, VixSnapshot
from strategy.selector import StrategyName, select_strategy


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


class Spec071Tests(unittest.TestCase):
    def test_ac1_aftermath_selector_returns_broken_wing_leg_deltas(self) -> None:
        rec = select_strategy(
            make_vix(vix=27.0, regime=Regime.HIGH_VOL, trend=Trend.RISING, vix_peak_10d=30.0),
            make_iv(signal=IVSignal.HIGH, iv_rank=78.0, iv_percentile=82.0),
            make_trend(TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR_HV)
        self.assertEqual(
            [(leg.action, leg.option, leg.dte, leg.delta) for leg in rec.legs],
            [
                ("SELL", "CALL", 45, 0.12),
                ("BUY", "CALL", 45, 0.04),
                ("SELL", "PUT", 45, 0.12),
                ("BUY", "PUT", 45, 0.08),
            ],
        )

    def test_ac2_non_aftermath_selector_keeps_symmetric_deltas(self) -> None:
        rec = select_strategy(
            make_vix(vix=29.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT, vix_peak_10d=30.0),
            make_iv(signal=IVSignal.HIGH, iv_rank=78.0, iv_percentile=82.0),
            make_trend(TrendSignal.NEUTRAL),
        )
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR_HV)
        self.assertEqual(
            [(leg.action, leg.option, leg.dte, leg.delta) for leg in rec.legs],
            [
                ("SELL", "CALL", 45, 0.16),
                ("BUY", "CALL", 45, 0.08),
                ("SELL", "PUT", 45, 0.16),
                ("BUY", "PUT", 45, 0.08),
            ],
        )

    def test_ac3_engine_reads_selector_deltas_for_aftermath_broken_wing(self) -> None:
        rec = select_strategy(
            make_vix(vix=27.0, regime=Regime.HIGH_VOL, trend=Trend.RISING, vix_peak_10d=30.0),
            make_iv(signal=IVSignal.HIGH, iv_rank=78.0, iv_percentile=82.0),
            make_trend(TrendSignal.NEUTRAL),
        )
        legs, dte = _build_legs(rec, 5600.0, 0.27)

        self.assertEqual(dte, 45)
        self.assertEqual(len(legs), 4)
        call_width = legs[1][2] - legs[0][2]
        put_width = legs[2][2] - legs[3][2]
        self.assertGreater(legs[1][2], legs[0][2])
        self.assertLess(legs[3][2], legs[2][2])
        self.assertGreater(call_width, put_width)


if __name__ == "__main__":
    unittest.main()
