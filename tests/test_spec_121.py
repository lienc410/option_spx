"""SPEC-121 — /ES HV Ladder canonical stop = 10x (Q087 A3, PM ratified 2026-07-05).

AC-1: monitor boundary — 9.9x mark is NOT a trigger, 10.0x IS; the 2x
      WARNING line is fixed and decoupled from stop_mult.
AC-5: SPX-side stops untouched (StrategyParams.stop_mult stays 2.0).
Plus: the single source of truth (EsShortPutParams) carries 10.0, and the
      HV Ladder backtest constant matches it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import notify.telegram_bot as bot_mod
from strategy.es_params import DEFAULT_ES_PARAMS


def _es_state(actual_premium: float) -> dict:
    return {"strategy_key": "es_short_put", "strategy": "/ES Short Put",
            "underlying": "/ES", "actual_premium": actual_premium}


def _positions_payload(mark: float) -> dict:
    return {"configured": True, "authenticated": True, "stale": False,
            "positions": [{"symbol": "/ESM26 PUT 6000",
                           "description": "/ES short put",
                           "quantity": -1, "mark": mark}]}


class Spec121StopBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        bot_mod._intraday_state["es_stop_level"] = bot_mod.EsStopLevel.NONE

    def _level_at(self, ratio: float):
        with patch("notify.telegram_bot.read_state", return_value=_es_state(10.0)), \
             patch("schwab.client.get_account_positions",
                   return_value=_positions_payload(10.0 * ratio)):
            return bot_mod._check_es_credit_stop().level

    def test_canonical_params(self):
        self.assertEqual(DEFAULT_ES_PARAMS.stop_mult, 10.0)
        self.assertEqual(bot_mod.ES_STOP_WARN_MULT, 2.0)

    def test_ac1_9x9_is_warning_not_trigger(self):
        self.assertEqual(self._level_at(9.9), bot_mod.EsStopLevel.WARNING)

    def test_ac1_10x0_triggers(self):
        self.assertEqual(self._level_at(10.0), bot_mod.EsStopLevel.TRIGGER)

    def test_ac1_warning_line_unchanged_at_2x(self):
        self.assertEqual(self._level_at(1.99), bot_mod.EsStopLevel.NONE)
        self.assertEqual(self._level_at(2.0), bot_mod.EsStopLevel.WARNING)

    def test_alert_texts_carry_new_thresholds(self):
        with patch("notify.telegram_bot.read_state", return_value=_es_state(10.0)), \
             patch("schwab.client.get_account_positions",
                   return_value=_positions_payload(100.0)):
            result = bot_mod._check_es_credit_stop()
        text = bot_mod._format_es_stop_alert(result)
        self.assertIn("×10 mark", text)

    def test_backtest_constant_matches_canonical(self):
        import research.strategies.ES_puts.backtest as ES
        self.assertEqual(ES.V2F_STOP_MULT, 10.0)

    def test_one_number_everywhere_no_stop_pins(self):
        """SPEC-121 final scope (PM 2026-07-05): canonical 10x everywhere,
        INCLUDING the ungated research baselines — PM knowingly accepted the
        baseline history rewrite (v2f baseline gains 29 stop exits and loses
        bootstrap significance; hvlad ungated comparison column gains 17 —
        see test_spec_095 for the retired pin). No code path may quietly
        re-introduce a per-mode stop override."""
        import inspect
        import research.strategies.ES_puts.backtest as ES
        for fn in (ES.run_phase2_v2f, ES.run_phase2_hvlad,
                   ES._run_phase2_v2f_on_frame):
            src = inspect.getsource(fn)
            self.assertNotIn("stop_mult=", src.replace("V2F_STOP_MULT", ""),
                             f"{fn.__name__} carries a stop override")
            self.assertNotIn("15.0", src, f"{fn.__name__} pins a legacy stop")

    def test_ac5_spx_stop_mult_untouched(self):
        from strategy.selector import DEFAULT_PARAMS
        self.assertEqual(DEFAULT_PARAMS.stop_mult, 2.0)


if __name__ == "__main__":
    unittest.main()
