from __future__ import annotations

import unittest

from backtest.engine import _build_legs
from strategy.selector import StrategyName


class Spec070Tests(unittest.TestCase):
    def test_ac1_ic_branch_uses_delta_based_long_legs(self) -> None:
        legs, dte = _build_legs(StrategyName.IRON_CONDOR_HV, 6795.99, 0.255)
        self.assertEqual(dte, 45)
        self.assertEqual(len(legs), 4)

        call_short = legs[0][2]
        call_long = legs[1][2]
        put_short = legs[2][2]
        put_long = legs[3][2]

        self.assertEqual(call_short, 7672.0)
        self.assertEqual(put_short, 6192.0)
        self.assertEqual(call_long, 8017.0)
        self.assertEqual(put_long, 5920.0)

    def test_ac2_2026_03_sample_strikes_shift_inside_old_wing_bounds(self) -> None:
        legs, _ = _build_legs(StrategyName.IRON_CONDOR_HV, 6795.99, 0.255)
        call_short = legs[0][2]
        call_long = legs[1][2]
        put_short = legs[2][2]
        put_long = legs[3][2]

        self.assertGreater(call_long, 7772.0)
        self.assertGreater(call_long, call_short)
        self.assertLess(put_long, 6092.0)
        self.assertLess(put_long, put_short)

    def test_ic_and_ic_hv_build_identically(self) -> None:
        ic_legs, ic_dte = _build_legs(StrategyName.IRON_CONDOR, 6795.99, 0.255)
        hv_legs, hv_dte = _build_legs(StrategyName.IRON_CONDOR_HV, 6795.99, 0.255)
        self.assertEqual(ic_dte, hv_dte)
        self.assertEqual(ic_legs, hv_legs)


if __name__ == "__main__":
    unittest.main()
