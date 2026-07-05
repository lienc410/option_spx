"""SPEC-122 — BCD real-quote shadow recording acceptance tests.

AC-1 signal day == production selector output (rec.strategy_key, no bypass)
AC-2 real-chain integration smoke (non-mock, 2026-07-02 snapshot)
AC-3 model debits match the pricing library called with the same params
AC-4 non-signal day: zero shadow writes, zero pushes (module has no Telegram)
AC-5 heartbeat registry carries the new marker entry
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import notify.q087_bcd_quote_shadow as shadow

BACKUP_CHAIN = Path.home() / "backups/oldair/data/q041_chains/2026-07-02/SPX.parquet"

OFFSETS_STUB = None  # built lazily in setUpModule to avoid import cost


def _rec(strategy_key: str, regime: str = "LOW_VOL"):
    r = types.SimpleNamespace()
    r.strategy_key = strategy_key
    r.vix_snapshot = types.SimpleNamespace(regime=types.SimpleNamespace(value=regime))
    return r


def _synthetic_calls():
    import pandas as pd
    rows = []
    for dte, expiry in ((44, "2026-08-18"), (91, "2026-10-05")):
        for strike, delta, iv, mid in (
            (7100, 0.72, 14.0, 420.0), (7300, 0.55, 13.0, 280.0),
            (7500, 0.31, 12.3, 150.0), (7700, 0.15, 11.5, 60.0),
        ):
            rows.append({"dte": dte, "expiry": expiry, "strike": float(strike),
                         "delta": delta, "iv": iv, "mid": mid,
                         "bid": mid - 1.0, "ask": mid + 1.0})
    return pd.DataFrame(rows)


class ShadowBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig_out = shadow.SHADOW_OUT
        self._orig_marker = shadow.RUN_MARKER
        shadow.SHADOW_OUT = self.tmp / "shadow.jsonl"
        shadow.RUN_MARKER = self.tmp / ".ran"

    def tearDown(self):
        shadow.SHADOW_OUT = self._orig_out
        shadow.RUN_MARKER = self._orig_marker


class TestSignalDayGate(ShadowBase):
    def test_ac1_reuses_selector_output_no_bypass(self):
        src = (REPO / "notify" / "q087_bcd_quote_shadow.py").read_text()
        self.assertNotIn("get_recommendation", src)   # never recomputes
        self.assertNotIn("select_strategy", src)

    def test_ac4_non_signal_day_zero_writes(self):
        # SPEC-123 §2 extended the recorder: LOW_VOL days record the quote-gate
        # lane even without a signal, so AC-4's zero-write guarantee now applies
        # to non-signal days OUTSIDE LOW_VOL.
        out = shadow.run("2026-07-06", _rec("bull_put_spread", regime="NORMAL"),
                         _synthetic_calls(), 7480.0, 16.0)
        self.assertIsNone(out)
        self.assertFalse(shadow.SHADOW_OUT.exists())   # zero data writes
        self.assertTrue(shadow.RUN_MARKER.exists())    # heartbeat still alive

    def test_spec123_lowvol_quote_gate_lane_records(self):
        out = shadow.run("2026-07-06", _rec("bull_put_spread", regime="LOW_VOL"),
                         _synthetic_calls(), 7480.0, 16.0)
        self.assertEqual(out["lane"], "lowvol_quote_gate")
        self.assertTrue(shadow.SHADOW_OUT.exists())

    def test_ac4_module_is_telegram_silent(self):
        # no sending machinery anywhere in the module (docstring may SAY
        # "Telegram silent" — the code must have no send path)
        src = (REPO / "notify" / "q087_bcd_quote_shadow.py").read_text()
        self.assertNotIn("_telegram_send", src)
        self.assertNotIn("send_message", src)
        self.assertNotIn("import telegram", src)
        self.assertNotIn("event_push", src)

    def test_signal_day_writes_row_and_lane(self):
        row = shadow.run("2026-07-06", _rec("bull_call_diagonal", "LOW_VOL"),
                         _synthetic_calls(), 7480.0, 16.0)
        self.assertEqual(row["lane"], "LOW_VOL|BULLISH")
        self.assertTrue(shadow.SHADOW_OUT.exists())
        # strict-JSON round trip (browser semantics)
        json.loads(shadow.SHADOW_OUT.read_text().strip(),
                   parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
        row2 = shadow.run("2026-07-07", _rec("bull_call_diagonal", "NORMAL"),
                          _synthetic_calls(), 7480.0, 16.0)
        self.assertEqual(row2["lane"], "SPEC-113_carve")

    def test_missing_chain_records_lost_sample(self):
        row = shadow.run("2026-07-06", _rec("bull_call_diagonal"),
                         None, 7480.0, 16.0)
        self.assertEqual(row["error"], "missing_chain")
        self.assertTrue(shadow.SHADOW_OUT.exists())   # the >=8 gate ledger is complete


class TestLegSelectionAndModels(ShadowBase):
    def test_leg_targets(self):
        row = shadow.run("2026-07-06", _rec("bull_call_diagonal"),
                         _synthetic_calls(), 7480.0, 16.0)
        self.assertEqual(row["long_dte"], 91)          # nearest 90
        self.assertEqual(row["short_dte"], 44)         # nearest 45
        self.assertAlmostEqual(row["long_delta"], 0.72)   # nearest .70
        self.assertAlmostEqual(row["short_delta"], 0.31)  # nearest .30
        self.assertAlmostEqual(row["debit_mid"], 420.0 - 150.0)
        self.assertAlmostEqual(row["debit_natural"], 421.0 - 149.0)

    def test_ac3_model_debits_match_pricing_library(self):
        from pricing import core
        from pricing.calibration import CONV_ACT365, OffsetCurves
        from pricing.sigma import SigmaMode, sigma_for
        offs = OffsetCurves({("CALL", "25-35"): [(0.30, -5.0), (0.70, -2.0)],
                             ("CALL", "80-100"): [(0.30, -3.9), (0.70, -1.2)],
                             ("PUT", "25-35"): [(0.30, -0.5), (0.50, -2.0)]},
                            CONV_ACT365)
        with patch("pricing.calibration.load_offsets_merged",
                   return_value=(offs, {})):
            row = shadow.run("2026-07-06", _rec("bull_call_diagonal"),
                             _synthetic_calls(), 7480.0, 16.0)

        def px(strike, dte, sigma):
            return core.call_price(7480.0, strike, dte / 365.0, sigma,
                                   shadow.MIV_R, q=0.0)

        # FLAT: same sigma both legs
        exp_flat = px(7100, 91, 0.16) - px(7500, 44, 0.16)
        self.assertAlmostEqual(row["model_flat_debit"], exp_flat, places=4)
        # CALIB: per-leg sigma keyed by chain |delta| at ACT/365 (library native)
        sl = sigma_for(SigmaMode.CALIB, vix=16.0, option_type="CALL",
                       abs_delta=0.72, dte=91, offsets=offs)
        ss = sigma_for(SigmaMode.CALIB, vix=16.0, option_type="CALL",
                       abs_delta=0.31, dte=44, offsets=offs)
        self.assertAlmostEqual(row["model_calib_debit"],
                               px(7100, 91, sl) - px(7500, 44, ss), places=4)
        # PESS: long +1vp / short -1vp
        pl = sigma_for(SigmaMode.PESS, vix=16.0, option_type="CALL",
                       abs_delta=0.72, dte=91, offsets=offs,
                       adverse_sign=+1, bracket_vp=1.0)
        ps = sigma_for(SigmaMode.PESS, vix=16.0, option_type="CALL",
                       abs_delta=0.31, dte=44, offsets=offs,
                       adverse_sign=-1, bracket_vp=1.0)
        self.assertAlmostEqual(row["model_pess_debit"],
                               px(7100, 91, pl) - px(7500, 44, ps), places=4)
        self.assertGreater(row["model_pess_debit"], row["model_calib_debit"])


class TestRealChainSmoke(ShadowBase):
    @unittest.skipUnless(BACKUP_CHAIN.exists(), "backup chain not on this machine")
    def test_ac2_real_chain_integration(self):
        import notify.q085_s2bps_paper as q
        orig = q.CHAIN_DIR
        q.CHAIN_DIR = BACKUP_CHAIN.parents[1]
        try:
            calls = q.load_today_calls("2026-07-02")
        finally:
            q.CHAIN_DIR = orig
        self.assertIsNotNone(calls)
        row = shadow.run("2026-07-02", _rec("bull_call_diagonal"),
                         calls, 7483.24, 16.15)
        for k in ("long_expiry", "long_strike", "long_bid", "long_ask",
                  "long_mid", "long_vendor_iv", "long_miv",
                  "short_expiry", "short_strike", "short_mid", "short_miv",
                  "debit_mid", "debit_natural",
                  "model_flat_debit", "model_calib_debit", "model_pess_debit"):
            self.assertIn(k, row, k)
        self.assertLessEqual(abs(row["long_dte"] - 90), 15)
        self.assertLessEqual(abs(row["short_dte"] - 45), 15)
        self.assertLessEqual(abs(abs(row["long_delta"]) - 0.70), 0.10)
        self.assertLessEqual(abs(abs(row["short_delta"]) - 0.30), 0.10)
        self.assertGreater(row["debit_natural"], row["debit_mid"])
        json.loads(shadow.SHADOW_OUT.read_text().strip(),
                   parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))


class TestRegistry(unittest.TestCase):
    def test_ac5_heartbeat_entry(self):
        reg = json.loads((REPO / "ops" / "heartbeat_registry.json").read_text())
        entry = next(j for j in reg["jobs"]
                     if j["label"] == "com.spxstrat.q085_s2bps.bcd_shadow")
        self.assertEqual(entry["kind"], "marker")
        self.assertEqual(entry["freshness"]["rule"], "trading_day")
        self.assertEqual(entry["freshness"]["path"],
                         str(shadow.RUN_MARKER.relative_to(REPO)))


if __name__ == "__main__":
    unittest.main()
