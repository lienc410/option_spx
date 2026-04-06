import unittest

from signals.iv_rank import IVSignal, IVSnapshot
from signals.trend import TrendSignal, TrendSnapshot
from signals.vix_regime import Regime, Trend, VixSnapshot
from strategy.catalog import CANONICAL_MATRIX, STRATEGIES_BY_KEY, strategy_catalog_payload, strategy_descriptor
from strategy.selector import StrategyName, select_strategy


def make_vix(*, vix: float, regime: Regime, trend: Trend, backwardation: bool = False) -> VixSnapshot:
    return VixSnapshot(
        date="2026-03-27",
        vix=vix,
        regime=regime,
        trend=trend,
        vix_5d_avg=vix,
        vix_5d_ago=vix,
        transition_warning=False,
        vix3m=(vix - 2.0) if backwardation else (vix + 2.0),
        backwardation=backwardation,
    )


def make_iv(*, signal: IVSignal, iv_rank: float, iv_percentile: float, vix: float = 18.0) -> IVSnapshot:
    return IVSnapshot(
        date="2026-03-27",
        vix=vix,
        iv_rank=iv_rank,
        iv_percentile=iv_percentile,
        iv_signal=signal,
        iv_52w_high=40.0,
        iv_52w_low=10.0,
    )


def make_trend(*, signal: TrendSignal, above_200: bool = True) -> TrendSnapshot:
    return TrendSnapshot(
        date="2026-03-27",
        spx=5600.0,
        ma20=5550.0,
        ma50=5500.0,
        ma_gap_pct=0.02 if signal == TrendSignal.BULLISH else (-0.02 if signal == TrendSignal.BEARISH else 0.0),
        signal=signal,
        above_200=above_200,
    )


class SelectorCatalogConsistencyTests(unittest.TestCase):
    def assert_catalog_backed(self, rec) -> None:
        desc = strategy_descriptor(rec.strategy_key)
        self.assertEqual(rec.underlying, desc.underlying)
        self.assertEqual(rec.max_risk, desc.max_risk_text)
        self.assertEqual(rec.target_return, desc.target_return_text)
        self.assertEqual(rec.roll_rule, desc.roll_rule_text)

    def test_canonical_matrix_only_references_known_strategies(self) -> None:
        payload = strategy_catalog_payload()
        self.assertEqual(set(payload["strategies"]), set(STRATEGIES_BY_KEY))
        for iv_map in CANONICAL_MATRIX.values():
            for trend_map in iv_map.values():
                for key in trend_map.values():
                    self.assertIn(key, STRATEGIES_BY_KEY)

    def test_low_vol_bullish_still_selects_diagonal(self) -> None:
        rec = select_strategy(
            make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.LOW, iv_rank=20.0, iv_percentile=25.0, vix=13.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)
        self.assertEqual(rec.strategy_key, "bull_call_diagonal")
        self.assert_catalog_backed(rec)

    def test_normal_high_iv_bullish_keeps_bull_put_spread(self) -> None:
        rec = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BULL_PUT_SPREAD)
        self.assertEqual(rec.strategy_key, "bull_put_spread")
        self.assert_catalog_backed(rec)

    def test_normal_bullish_backwardation_still_waits(self) -> None:
        rec = select_strategy(
            make_vix(vix=20.0, regime=Regime.NORMAL, trend=Trend.FLAT, backwardation=True),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=45.0, iv_percentile=45.0, vix=20.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertEqual(rec.strategy_key, "reduce_wait")
        self.assertTrue(rec.backwardation)
        self.assertEqual(rec.canonical_strategy, "Bull Put Spread")
        self.assertIn("contango restored", rec.re_enable_hint)
        self.assert_catalog_backed(rec)

    def test_normal_neutral_bearish_still_uses_iron_condor(self) -> None:
        rec = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.NEUTRAL, iv_rank=42.0, iv_percentile=35.0, vix=19.0),
            make_trend(signal=TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR)
        self.assertEqual(rec.strategy_key, "iron_condor")
        self.assert_catalog_backed(rec)

    def test_high_vol_bearish_rising_still_waits(self) -> None:
        rec = select_strategy(
            make_vix(vix=28.0, regime=Regime.HIGH_VOL, trend=Trend.RISING),
            make_iv(signal=IVSignal.HIGH, iv_rank=70.0, iv_percentile=80.0, vix=28.0),
            make_trend(signal=TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.REDUCE_WAIT)
        self.assertEqual(rec.strategy_key, "reduce_wait")
        self.assertEqual(rec.canonical_strategy, "Bear Call Spread (High Vol)")
        self.assertEqual(rec.re_enable_hint, "VIX trend turns FLAT or FALLING")
        self.assertEqual(rec.overlay_mode, "disabled")
        self.assertEqual(rec.shock_mode, "shadow")
        self.assert_catalog_backed(rec)

    def test_high_vol_bearish_stable_still_uses_bear_call_spread_hv(self) -> None:
        rec = select_strategy(
            make_vix(vix=28.0, regime=Regime.HIGH_VOL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=70.0, iv_percentile=80.0, vix=28.0),
            make_trend(signal=TrendSignal.BEARISH),
        )
        self.assertEqual(rec.strategy, StrategyName.BEAR_CALL_SPREAD_HV)
        self.assertEqual(rec.strategy_key, "bear_call_spread_hv")
        self.assert_catalog_backed(rec)


if __name__ == "__main__":
    unittest.main()
