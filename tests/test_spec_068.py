from __future__ import annotations

import unittest

import pandas as pd

from backtest.engine import _block_hv_spell_entry, _update_hv_spell_state
from signals.vix_regime import Regime
from strategy.selector import StrategyParams


class Spec068Tests(unittest.TestCase):
    def test_ac1_hv_spell_state_is_dict_and_resets_to_empty_dict(self) -> None:
        day = pd.Timestamp("2022-04-01")
        start, counts = _update_hv_spell_state(Regime.HIGH_VOL, 26.0, day, None, {}, 35.0)
        self.assertEqual(start, day)
        self.assertEqual(counts, {})

        start2, counts2 = _update_hv_spell_state(
            Regime.NORMAL,
            19.0,
            day + pd.Timedelta(days=1),
            start,
            {"iron_condor_hv": 2},
            35.0,
        )
        self.assertIsNone(start2)
        self.assertEqual(counts2, {})

    def test_ac7_ic_hv_at_cap_does_not_block_bps_hv(self) -> None:
        params = StrategyParams(max_trades_per_spell=2)
        start = pd.Timestamp("2022-04-01")
        counts = {"iron_condor_hv": 2}
        self.assertFalse(
            _block_hv_spell_entry(
                Regime.HIGH_VOL,
                27.0,
                "bull_put_spread_hv",
                start,
                counts,
                params,
                start + pd.Timedelta(days=5),
            )
        )
        self.assertTrue(
            _block_hv_spell_entry(
                Regime.HIGH_VOL,
                27.0,
                "iron_condor_hv",
                start,
                counts,
                params,
                start + pd.Timedelta(days=5),
            )
        )

    def test_spell_age_cap_still_blocks(self) -> None:
        params = StrategyParams()
        start = pd.Timestamp("2022-04-01")
        late_day = start + pd.Timedelta(days=31)
        self.assertTrue(
            _block_hv_spell_entry(
                Regime.HIGH_VOL,
                27.0,
                "bull_put_spread_hv",
                start,
                {},
                params,
                late_day,
            )
        )


if __name__ == "__main__":
    unittest.main()
