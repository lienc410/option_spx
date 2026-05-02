from __future__ import annotations

import unittest
from unittest.mock import patch

from signals.iv_rank import IVSignal, IVSnapshot
from signals.trend import TrendSignal, TrendSnapshot
from signals.vix_regime import Regime, Trend, VixSnapshot
from strategy.bcd_filter import bcd_risk_score, should_block_bcd
from strategy.selector import StrategyName, StrategyParams, select_strategy


def make_vix(*, vix: float = 14.0, regime: Regime = Regime.LOW_VOL, trend: Trend = Trend.FLAT) -> VixSnapshot:
    return VixSnapshot(
        date="2026-05-02",
        vix=vix,
        regime=regime,
        trend=trend,
        vix_5d_avg=vix,
        vix_5d_ago=vix,
        transition_warning=False,
        vix3m=vix + 2.0,
        backwardation=False,
    )


def make_iv(*, signal: IVSignal = IVSignal.LOW, iv_rank: float = 20.0, iv_percentile: float = 25.0) -> IVSnapshot:
    return IVSnapshot(
        date="2026-05-02",
        vix=14.0,
        iv_rank=iv_rank,
        iv_percentile=iv_percentile,
        iv_signal=signal,
        iv_52w_high=40.0,
        iv_52w_low=10.0,
        ivp63=25.0,
        ivp252=iv_percentile,
    )


def make_trend(
    *,
    signal: TrendSignal = TrendSignal.BULLISH,
    ma_gap_pct: float = 0.020,
    dist_30d_high_pct: float | None = -0.02,
) -> TrendSnapshot:
    return TrendSnapshot(
        date="2026-05-02",
        spx=5600.0,
        ma20=5580.0,
        ma50=5490.0,
        ma_gap_pct=ma_gap_pct,
        signal=signal,
        above_200=True,
        spx_30d_high=5714.2857 if dist_30d_high_pct is not None else None,
        dist_30d_high_pct=dist_30d_high_pct,
    )


class BcdFilterTests(unittest.TestCase):
    def test_risk_score_all_three(self) -> None:
        self.assertEqual(bcd_risk_score(14.0, -0.02, 0.020), 3)

    def test_risk_score_two_of_three(self) -> None:
        self.assertEqual(bcd_risk_score(14.0, None, 0.020), 2)

    def test_disabled_mode_never_blocks(self) -> None:
        self.assertFalse(should_block_bcd("disabled", 14.0, -0.02, 0.020, "2026-05-02"))

    def test_shadow_mode_logs_but_not_blocks(self) -> None:
        with patch("strategy.bcd_filter._log_shadow") as mock_log:
            self.assertFalse(should_block_bcd("shadow", 14.0, -0.02, 0.020, "2026-05-02"))
        mock_log.assert_called_once()

    def test_active_mode_blocks_on_score3(self) -> None:
        self.assertTrue(should_block_bcd("active", 14.0, -0.02, 0.020, "2026-05-02"))

    def test_selector_returns_reduce_wait_when_active(self) -> None:
        rec = select_strategy(
            make_vix(vix=14.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.LOW, iv_rank=20.0, iv_percentile=25.0),
            make_trend(signal=TrendSignal.BULLISH, ma_gap_pct=0.020, dist_30d_high_pct=-0.02),
            StrategyParams(bcd_comfort_filter_mode="active"),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertEqual(rec.canonical_strategy, StrategyName.BULL_CALL_DIAGONAL.value)
        self.assertIn("BCD comfortable-top filter (SPEC-079)", rec.rationale)


if __name__ == "__main__":
    unittest.main()
