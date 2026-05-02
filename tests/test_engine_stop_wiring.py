"""
SPEC-077 F2 — engine stop_mult wiring + profit_target default governance test.

Locks two governance invariants:

1. credit-side stop loss in `backtest.engine.run_backtest` reads
   `params.stop_mult` (not a hardcoded constant). This guards against
   future refactors silently dropping the wiring.

2. debit-side stop loss is currently hardcoded at `-0.50` (engine.py:882).
   SPEC-080 will replace this for BCD specifically. The test asserts the
   hardcoded value is still present so SPEC-080 has a deterministic target.

3. `StrategyParams.profit_target` default is `0.60` (SPEC-077 §F1).
"""

from __future__ import annotations

import inspect
import unittest

from backtest import engine
from strategy.selector import DEFAULT_PARAMS, StrategyParams


class EngineStopWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine_src = inspect.getsource(engine.run_backtest)

    def test_profit_target_default_is_060(self) -> None:
        """SPEC-077 F1: StrategyParams.profit_target default is 0.60."""
        self.assertEqual(
            StrategyParams().profit_target,
            0.60,
            "profit_target default must be 0.60 (SPEC-077)",
        )
        self.assertEqual(DEFAULT_PARAMS.profit_target, 0.60)

    def test_engine_credit_stop_reads_params_stop_mult(self) -> None:
        """Credit-side stop loss must reference params.stop_mult, not a constant."""
        self.assertIn(
            "params.stop_mult",
            self.engine_src,
            "engine.run_backtest must wire params.stop_mult into credit stop",
        )
        # The exact wiring expression at engine.py:880
        self.assertIn(
            "pnl_ratio <= -params.stop_mult",
            self.engine_src,
            "credit stop expression must be `pnl_ratio <= -params.stop_mult`",
        )

    def test_engine_debit_stop_still_hardcoded_for_spec080(self) -> None:
        """Debit-side stop loss stays hardcoded at -0.50 until SPEC-080 replaces it for BCD."""
        # Line 882: `elif not is_credit and pnl_ratio <= -0.50:`
        self.assertIn(
            "pnl_ratio <= -0.50",
            self.engine_src,
            "debit-side hardcoded -0.50 must remain for SPEC-080 to replace",
        )

    def test_credit_stop_logic_equivalence(self) -> None:
        """Mirror engine.py:880 logic to verify stop_mult math.

        Credit trade fires stop when pnl_ratio <= -stop_mult.
        """

        def credit_stop_fires(pnl_ratio: float, stop_mult: float) -> bool:
            return pnl_ratio <= -stop_mult

        # stop_mult=1.5: pnl_ratio=-1.6 fires; pnl_ratio=-1.4 does not
        self.assertTrue(credit_stop_fires(-1.6, 1.5))
        self.assertFalse(credit_stop_fires(-1.4, 1.5))
        # stop_mult=3.0: pnl_ratio=-1.6 does not fire (looser stop)
        self.assertFalse(credit_stop_fires(-1.6, 3.0))
        # stop_mult=2.0 (default): pnl_ratio=-2.1 fires
        self.assertTrue(credit_stop_fires(-2.1, 2.0))

    def test_debit_stop_logic_equivalence(self) -> None:
        """Mirror engine.py:882 logic. SPEC-080 will tighten this to -0.35 for BCD."""

        def debit_stop_fires(pnl_ratio: float) -> bool:
            return pnl_ratio <= -0.50

        self.assertTrue(debit_stop_fires(-0.51))
        self.assertFalse(debit_stop_fires(-0.49))


if __name__ == "__main__":
    unittest.main()
