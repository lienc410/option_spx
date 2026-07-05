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

    def test_ungated_baselines_pinned_to_frozen_15x(self):
        """SPEC-121 scope: canonical 10x applies to the promoted/gated paths
        (proven bit-identical). The UNGATED research baselines (v2f baseline
        mode, hvlad vix_min_entry=0 comparison column) are frozen attribution
        artifacts — under 10x they are NOT bit-identical (29 / 17 stop exits
        appear, SPEC-095's sig_rate>=0.80 acceptance collapses to 0), so the
        runners pin them to their original 15x. This test reads the pin from
        the source so a silent removal fails loudly."""
        import inspect
        import research.strategies.ES_puts.backtest as ES
        src_v2f = inspect.getsource(ES.run_phase2_v2f)
        self.assertIn('15.0 if mode == "baseline" else None', src_v2f)
        src_hvlad = inspect.getsource(ES.run_phase2_hvlad)
        self.assertIn("15.0 if (vix_min_entry or 0.0) <= 0.0 else None", src_hvlad)

    def test_ac5_spx_stop_mult_untouched(self):
        from strategy.selector import DEFAULT_PARAMS
        self.assertEqual(DEFAULT_PARAMS.stop_mult, 2.0)


if __name__ == "__main__":
    unittest.main()
