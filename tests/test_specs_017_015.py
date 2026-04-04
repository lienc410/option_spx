import unittest

import pandas as pd

from backtest.engine import (
    _block_hv_spell_entry,
    _block_short_gamma_limit,
    _block_synthetic_ic,
    _update_hv_spell_state,
)
from signals.vix_regime import Regime
from strategy.catalog import strategy_catalog_payload
from strategy.selector import StrategyParams


class Spec017And015Tests(unittest.TestCase):
    def test_strategy_catalog_payload_includes_greek_fields(self) -> None:
        payload = strategy_catalog_payload()
        diagonal = payload["strategies"]["bull_call_diagonal"]
        bull_put = payload["strategies"]["bull_put_spread"]
        for field in ("short_gamma", "short_vega", "delta_sign"):
            self.assertIn(field, diagonal)
            self.assertIn(field, bull_put)
        self.assertFalse(diagonal["short_gamma"])
        self.assertTrue(bull_put["short_gamma"])
        self.assertEqual(bull_put["delta_sign"], "bull")

    def test_synthetic_ic_pair_is_blocked(self) -> None:
        self.assertTrue(_block_synthetic_ic({"bull_put_spread_hv"}, "bear_call_spread_hv"))
        self.assertTrue(_block_synthetic_ic({"bear_call_spread_hv"}, "bull_put_spread_hv"))
        self.assertFalse(_block_synthetic_ic({"iron_condor_hv"}, "bull_put_spread_hv"))

    def test_short_gamma_limit_blocks_only_short_gamma_entries(self) -> None:
        existing = {"bull_put_spread", "iron_condor", "bear_call_spread_hv"}
        self.assertTrue(_block_short_gamma_limit(existing, "bull_put_spread_hv", 3))
        self.assertFalse(_block_short_gamma_limit(existing, "bull_call_diagonal", 3))

    def test_hv_spell_state_tracks_and_resets(self) -> None:
        day = pd.Timestamp("2022-04-01")
        start, count = _update_hv_spell_state(Regime.HIGH_VOL, 26.0, day, None, 0, 35.0)
        self.assertEqual(start, day)
        self.assertEqual(count, 0)

        start2, count2 = _update_hv_spell_state(Regime.NORMAL, 19.0, day + pd.Timedelta(days=1), start, 2, 35.0)
        self.assertIsNone(start2)
        self.assertEqual(count2, 0)

        start3, count3 = _update_hv_spell_state(Regime.HIGH_VOL, 36.0, day + pd.Timedelta(days=2), start, 2, 35.0)
        self.assertIsNone(start3)
        self.assertEqual(count3, 0)

    def test_hv_spell_entry_block_and_noop_config(self) -> None:
        params = StrategyParams()
        start = pd.Timestamp("2022-04-01")
        late_day = start + pd.Timedelta(days=31)
        self.assertTrue(
            _block_hv_spell_entry(Regime.HIGH_VOL, 27.0, "bull_put_spread_hv", start, 0, params, late_day)
        )
        self.assertTrue(
            _block_hv_spell_entry(Regime.HIGH_VOL, 27.0, "iron_condor_hv", start, 2, params, start + pd.Timedelta(days=5))
        )

        noop = StrategyParams(
            spell_age_cap=999,
            max_trades_per_spell=999,
            max_short_gamma_positions=999,
        )
        self.assertFalse(
            _block_hv_spell_entry(Regime.HIGH_VOL, 27.0, "bull_put_spread_hv", start, 2, noop, late_day)
        )
        self.assertFalse(_block_short_gamma_limit({"bull_put_spread", "iron_condor"}, "bear_call_spread_hv", noop.max_short_gamma_positions))


if __name__ == "__main__":
    unittest.main()
