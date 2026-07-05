"""SPEC-119 — unified pricing library (pricing/) acceptance tests.

AC-1 (bit-identical 26y matrix backtest vs frozen snapshot) is run as a
standalone script against /tmp/spec119_pre_migration_trades.json — too slow
for the unit suite. Everything else lives here:
  - core parity vs the historical inline formulas (incl. degenerate guards)
  - A&S fallback CDF accuracy
  - sigma modes: FLAT / CALIB interpolation / PESS explicit-bracket contract (AC-5)
  - calibration min-sample gate (InsufficientCalibration)
  - skew-monitor extension: backward compat + delta-tolerance guard
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pricing import core
from pricing.sigma import SigmaMode, sigma_for
from pricing.calibration import InsufficientCalibration, load_offsets


def _ref_call(S, K, T, sigma, r, q=0.0):
    """Reference BS call — independent inline copy (the pre-SPEC-119 formula)."""
    from scipy.stats import norm
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def _ref_put(S, K, T, sigma, r, q=0.0):
    from scipy.stats import norm
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


class TestCoreParity(unittest.TestCase):
    CASES = [
        # (S, K, T, sigma, r, q) spanning production conventions
        (5000.0, 4800.0, 30 / 252, 0.18, 0.045, 0.0),    # pricer.py convention
        (5000.0, 5250.0, 45 / 365, 0.15, 0.04, 0.0),     # q042 convention
        (6900.0, 6600.0, 28 / 365, 0.17, 0.05, 0.013),   # attribution convention (q!=0)
        (4200.0, 4200.0, 90 / 252, 0.35, 0.045, 0.0),    # ATM high vol
        (5000.0, 2500.0, 5 / 252, 0.12, 0.045, 0.0),     # deep ITM call
    ]

    def test_call_put_match_reference(self):
        for S, K, T, sigma, r, q in self.CASES:
            self.assertAlmostEqual(core.call_price(S, K, T, sigma, r, q=q),
                                   _ref_call(S, K, T, sigma, r, q), places=10)
            self.assertAlmostEqual(core.put_price(S, K, T, sigma, r, q=q),
                                   _ref_put(S, K, T, sigma, r, q), places=10)

    def test_put_call_parity(self):
        for S, K, T, sigma, r, q in self.CASES:
            c = core.call_price(S, K, T, sigma, r, q=q)
            p = core.put_price(S, K, T, sigma, r, q=q)
            parity = S * math.exp(-q * T) - K * math.exp(-r * T)
            self.assertAlmostEqual(c - p, parity, places=8)

    def test_degenerate_guards_match_old_inline_branches(self):
        # q042_engine._bs_call historical guards
        self.assertEqual(core.call_price(5000, 4800, 0.0, 0.2, 0.04), 200.0)
        self.assertEqual(core.call_price(4800, 5000, 0.0, 0.2, 0.04), 0.0)
        self.assertAlmostEqual(core.call_price(5000, 4800, 0.1, 0.0, 0.04),
                               max(0.0, 5000 - 4800 * math.exp(-0.04 * 0.1)), places=12)
        # sleeve_governance._bs_put historical guard (T<=0 or sigma<=0 → intrinsic)
        self.assertEqual(core.put_price(4800, 5000, 0.0, 0.2, 0.05), 200.0)

    def test_as_fallback_cdf_accuracy(self):
        from scipy.stats import norm
        for x in (-3.0, -1.5, -0.5, 0.0, 0.7, 2.2, 4.0):
            t = 1.0 / (1.0 + 0.2316419 * abs(x))
            p = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
                     + t * (-1.821255978 + t * 1.330274429))))
            pdf = math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
            approx = (1.0 - pdf * p) if x >= 0 else pdf * p
            self.assertAlmostEqual(approx, float(norm.cdf(x)), places=6)

    def test_adapter_pricer_unchanged_conventions(self):
        from backtest import pricer
        S, K, dte, sigma = 5000.0, 4750.0, 30, 0.20
        T = dte / 252
        self.assertAlmostEqual(pricer.put_price(S, K, dte, sigma),
                               _ref_put(S, K, T, sigma, 0.045), places=10)
        self.assertAlmostEqual(pricer.put_delta(S, K, dte, sigma),
                               pricer.call_delta(S, K, dte, sigma) - 1.0, places=12)
        k = pricer.find_strike_for_delta(S, dte, sigma, 0.30, is_call=False)
        self.assertEqual(k, round(k))
        self.assertAlmostEqual(abs(pricer.put_delta(S, k, dte, sigma)), 0.30, delta=0.02)


class TestSigmaModes(unittest.TestCase):
    OFFSETS = {
        ("PUT", "25-35"): [(0.15, 1.0), (0.30, -2.0), (0.50, -4.0)],
        ("CALL", "25-35"): [(0.08, -5.0), (0.30, -3.6), (0.70, -2.0)],
        ("PUT", "80-100"): [(0.30, -1.8), (0.50, -4.3)],
    }

    def test_flat(self):
        self.assertAlmostEqual(sigma_for(SigmaMode.FLAT, vix=18.0), 0.18)

    def test_no_default_mode(self):
        with self.assertRaises(ValueError):
            sigma_for("FLAT", vix=18.0)  # bare string is not an explicit mode

    def test_calib_exact_and_interpolated(self):
        s = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                      abs_delta=0.30, dte=30, offsets=self.OFFSETS)
        self.assertAlmostEqual(s, (20.0 - 2.0) / 100.0)
        # midpoint 0.225 between (0.15,+1.0) and (0.30,-2.0) → -0.5
        s = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                      abs_delta=0.225, dte=30, offsets=self.OFFSETS)
        self.assertAlmostEqual(s, (20.0 - 0.5) / 100.0)

    def test_calib_edge_clamp_and_bucket_routing(self):
        s = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                      abs_delta=0.05, dte=30, offsets=self.OFFSETS)
        self.assertAlmostEqual(s, (20.0 + 1.0) / 100.0)   # clamped to 0.15 leg
        s = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                      abs_delta=0.30, dte=90, offsets=self.OFFSETS)
        self.assertAlmostEqual(s, (20.0 - 1.8) / 100.0)   # 80-100 bucket
        # SPEC-120: missing far curve falls back to the near curve (no raise);
        # a type with NO curve at all still raises
        s = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="CALL",
                      abs_delta=0.30, dte=90, offsets=self.OFFSETS)
        self.assertAlmostEqual(s, (20.0 - 3.6) / 100.0)   # near-curve fallback
        with self.assertRaises(ValueError):
            sigma_for(SigmaMode.CALIB, vix=20.0, option_type="CALL",
                      abs_delta=0.30, dte=30,
                      offsets={("PUT", "25-35"): [(0.3, -1.0), (0.5, -2.0)]})

    def test_calib_dte_interpolation_between_buckets(self):
        # SPEC-120: dte 60 is halfway between centers 30 and 90
        s30 = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                        abs_delta=0.30, dte=30, offsets=self.OFFSETS)
        s90 = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                        abs_delta=0.30, dte=90, offsets=self.OFFSETS)
        s60 = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                        abs_delta=0.30, dte=60, offsets=self.OFFSETS)
        self.assertAlmostEqual(s60, (s30 + s90) / 2)
        # clamped outside the centers
        s120 = sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                         abs_delta=0.30, dte=120, offsets=self.OFFSETS)
        self.assertAlmostEqual(s120, s90)

    def test_calib_floor(self):
        s = sigma_for(SigmaMode.CALIB, vix=4.0, option_type="PUT",
                      abs_delta=0.50, dte=30, offsets=self.OFFSETS)
        self.assertAlmostEqual(s, 0.01)  # (4-4)=0 vp floored at 1 vp

    def test_pess_requires_bracket_ac5(self):
        kw = dict(vix=20.0, option_type="PUT", abs_delta=0.30, dte=30,
                  offsets=self.OFFSETS)
        with self.assertRaises(ValueError):
            sigma_for(SigmaMode.PESS, adverse_sign=-1, **kw)      # no bracket_vp
        with self.assertRaises(ValueError):
            sigma_for(SigmaMode.PESS, bracket_vp=2.0, **kw)       # no adverse_sign
        with self.assertRaises(ValueError):
            sigma_for(SigmaMode.PESS, bracket_vp=2.0, adverse_sign=0, **kw)
        s = sigma_for(SigmaMode.PESS, bracket_vp=2.0, adverse_sign=-1, **kw)
        self.assertAlmostEqual(s, (20.0 - 2.0 - 2.0) / 100.0)

    def test_calib_requires_offsets(self):
        with self.assertRaises(ValueError):
            sigma_for(SigmaMode.CALIB, vix=20.0, option_type="PUT",
                      abs_delta=0.30, dte=30)


class TestCalibration(unittest.TestCase):
    def _write_rows(self, n, **extra):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for i in range(n):
            row = {"date": f"2026-06-{i+1:02d}", "vix": 17.0,
                   "atm_moff": -2.0 - 0.1 * (i % 3), "d30_moff": -0.3, "d15_moff": 2.0}
            row.update(extra)
            f.write(json.dumps(row) + "\n")
        f.close()
        return Path(f.name)

    def test_min_sample_gate(self):
        p = self._write_rows(9)
        with self.assertRaises(InsufficientCalibration):
            load_offsets(p)
        p.unlink()

    def test_offsets_from_min_days(self):
        p = self._write_rows(10)
        off = load_offsets(p)
        curve = dict(off[("PUT", "25-35")])
        self.assertAlmostEqual(curve[0.30], -0.3)
        self.assertAlmostEqual(curve[0.15], 2.0)
        self.assertAlmostEqual(curve[0.50], -2.1)  # median of -2.0/-2.1/-2.2 cycle
        self.assertNotIn(("CALL", "25-35"), off)   # no call fields in these rows
        p.unlink()

    def test_extended_fields_build_call_and_far_curves(self):
        p = self._write_rows(12, c70_moff=-1.0, c30_moff=-2.6, atm_moff_far=-2.3,
                             d30_moff_far=-0.8)
        off = load_offsets(p)
        self.assertIn(("CALL", "25-35"), off)
        self.assertIn(("PUT", "80-100"), off)
        p.unlink()

    def test_vendor_iv_fields_not_consumed(self):
        # rows carrying ONLY legacy vendor *_off fields must NOT calibrate:
        # vendor iv is convention-inconsistent with pricing.core (AC-3 finding)
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for i in range(15):
            f.write(json.dumps({"date": f"2026-06-{i+1:02d}", "vix": 17.0,
                                "atm_off": -4.0, "d30_off": -2.0, "d15_off": 1.0}) + "\n")
        f.close()
        with self.assertRaises(InsufficientCalibration):
            load_offsets(Path(f.name))
        Path(f.name).unlink()


class TestImpliedVol(unittest.TestCase):
    def test_round_trip(self):
        S, K, T, r = 7480.0, 7320.0, 28 / 365, 0.045
        for sigma in (0.12, 0.16, 0.25):
            px = core.put_price(S, K, T, sigma, r)
            self.assertAlmostEqual(core.implied_vol(px, S, K, T, r, is_call=False),
                                   sigma, places=5)
            pc = core.call_price(S, K, T, sigma, r)
            self.assertAlmostEqual(core.implied_vol(pc, S, K, T, r, is_call=True),
                                   sigma, places=5)

    def test_unattainable_price_returns_none(self):
        self.assertIsNone(core.implied_vol(0.0, 7480, 7320, 28 / 365, 0.045, is_call=False))
        # ITM put below discounted intrinsic (K·e^-rT − S ≈ 93.8) has no BS vol
        self.assertIsNone(core.implied_vol(50.0, 7480, 7600, 28 / 365, 0.045, is_call=False))
        self.assertIsNone(core.implied_vol(50.0, 7480, 7320, 0.0, 0.045, is_call=False))


class TestSkewMonitorExtension(unittest.TestCase):
    def _chain(self, dtes, ads, ivs):
        import pandas as pd
        return pd.DataFrame({"dte": dtes, "delta": ads, "iv": ivs})

    def setUp(self):
        import notify.q085_s2bps_paper as q
        self.q = q
        self._orig_out = q.SKEW_OUT
        self._tmp = Path(tempfile.mkdtemp()) / "skew.jsonl"
        q.SKEW_OUT = self._tmp

    def tearDown(self):
        self.q.SKEW_OUT = self._orig_out

    def test_backward_compatible_without_calls(self):
        puts = self._chain([30] * 9, [-0.5, -0.45, -0.48, -0.3, -0.32, -0.28, -0.15, -0.16, -0.14],
                           [15.0, 14.8, 14.9, 13.5, 13.6, 13.4, 12.0, 12.1, 11.9])
        row = self.q.measure_skew(puts, vix=14.0, date_str="2026-07-03")
        for k in ("atm_iv", "d30_iv", "d15_iv", "atm_off", "d30_off", "d15_off"):
            self.assertIn(k, row)
        self.assertFalse(any(k.startswith("c") for k in row))
        self.assertFalse(any("_miv" in k or "_moff" in k for k in row))  # no spx given

    def test_call_legs_and_far_bucket(self):
        puts = self._chain(
            [30] * 9 + [90] * 6,
            [-0.5, -0.45, -0.48, -0.3, -0.32, -0.28, -0.15, -0.16, -0.14,
             -0.5, -0.48, -0.52, -0.3, -0.31, -0.29],
            [15.0, 14.8, 14.9, 13.5, 13.6, 13.4, 12.0, 12.1, 11.9,
             15.5, 15.4, 15.6, 14.0, 14.1, 13.9])
        calls = self._chain(
            [30] * 12,
            [0.7, 0.71, 0.69, 0.3, 0.31, 0.29, 0.16, 0.17, 0.15, 0.08, 0.09, 0.07],
            [13.0, 13.1, 12.9, 11.5, 11.6, 11.4, 11.0, 11.1, 10.9, 10.5, 10.6, 10.4])
        row = self.q.measure_skew(puts, vix=14.0, date_str="2026-07-03", calls=calls)
        for k in ("c70_iv", "c30_iv", "c16_iv", "c08_iv",
                  "c70_off", "c30_off", "c16_off", "c08_off",
                  "atm_iv_far", "d30_iv_far", "atm_off_far", "d30_off_far"):
            self.assertIn(k, row)
        self.assertNotIn("d15_iv_far", row)         # far bucket lacks |d|~0.15 rows
        self.assertAlmostEqual(row["c30_off"], 11.5 - 14.0, places=2)
        # strict-JSON round trip (browser semantics — no NaN/Inf)
        txt = self._tmp.read_text().strip()
        json.loads(txt, parse_constant=lambda c: (_ for _ in ()).throw(
            ValueError(f"non-finite {c}")))

    def test_mid_implied_fields_recover_known_sigma(self):
        import pandas as pd
        S, r, sigma = 7480.0, 0.045, 0.15
        T = 30 / 365
        strikes = [7480, 7460, 7470, 7250, 7240, 7260, 7050, 7040, 7060]
        ads = [-0.5, -0.49, -0.51, -0.3, -0.29, -0.31, -0.15, -0.14, -0.16]
        mids = [core.put_price(S, k, T, sigma, r) for k in strikes]
        puts = pd.DataFrame({"dte": [30] * 9, "delta": ads, "iv": [15.0] * 9,
                             "strike": strikes, "mid": mids})
        row = self.q.measure_skew(puts, vix=14.0, date_str="2026-07-03", spx=S)
        for name in ("atm", "d30", "d15"):
            self.assertAlmostEqual(row[f"{name}_miv"], 15.0, delta=0.02)
            self.assertAlmostEqual(row[f"{name}_moff"], 1.0, delta=0.02)
        self.assertEqual(row["miv_conv"], "r045_q0_act365")
        self.assertEqual(row["spx"], 7480.0)

    def test_delta_tolerance_guard_skips_unreachable_legs(self):
        puts = self._chain([30] * 9, [-0.5, -0.45, -0.48, -0.3, -0.32, -0.28, -0.15, -0.16, -0.14],
                           [15.0, 14.8, 14.9, 13.5, 13.6, 13.4, 12.0, 12.1, 11.9])
        # calls only cover |d| 0.33-0.67 (strike-limited chain)
        calls = self._chain([30] * 6, [0.33, 0.4, 0.5, 0.6, 0.65, 0.67],
                            [12.0, 12.5, 13.0, 13.5, 13.8, 14.0])
        row = self.q.measure_skew(puts, vix=14.0, date_str="2026-07-03", calls=calls)
        self.assertIn("c30_off", row)               # 0.33 within 0.05 of 0.30
        self.assertIn("c70_off", row)               # 0.67 within 0.05 of 0.70
        self.assertNotIn("c16_off", row)            # nearest 0.33 too far from 0.16
        self.assertNotIn("c08_off", row)


if __name__ == "__main__":
    unittest.main()
