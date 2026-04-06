import unittest
import importlib.util
from pathlib import Path

import pandas as pd

from strategy.selector import StrategyName


MODULE_PATH = Path(__file__).resolve().parents[1] / "backtest" / "prototype" / "SPEC-030_intraday_stop.py"
SPEC = importlib.util.spec_from_file_location("spec_030_intraday_stop", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class DummyTrade:
    strategy = StrategyName.BULL_PUT_SPREAD
    entry_spx = 5000.0
    entry_vix = 20.0


class Spec030Tests(unittest.TestCase):
    def test_fetch_spx_ohlc_prefers_existing_cache_shape(self):
        self.assertTrue(module.SPX_CACHE.exists())
        ohlc = module.fetch_spx_ohlc()
        self.assertTrue({"open", "high", "low", "close"}.issubset(ohlc.columns))
        self.assertIsInstance(ohlc.index, pd.DatetimeIndex)

    def test_reconstruct_legs_builds_exact_engine_legs(self):
        legs = module._reconstruct_legs(DummyTrade(), params=type("Params", (), {
            "normal_dte": 30,
            "normal_delta": 0.30,
            "high_vol_dte": 35,
            "high_vol_delta": 0.20,
        })())
        self.assertEqual(len(legs), 2)
        self.assertEqual(legs[0][0], -1)
        self.assertFalse(legs[0][1])


if __name__ == "__main__":
    unittest.main()
