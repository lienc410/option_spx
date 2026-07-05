"""SPEC-120 — engine sigma modes + offsets merger.

AC-1 (26y FLAT bit-identical vs the SPEC-119 frozen snapshot) runs as a
standalone script — too slow here. This file pins:
  - FLAT default equals explicit FLAT and leaves the resolver off
  - CALIB/PESS refuse to run without offsets (loud, no silent FLAT)
  - resolver semantics: PESS short/long bracket signs, CALIB per-leg offsets
  - offsets merger: date-dedupe (production wins), fail-soft field counting
  - CALIB actually changes entry credits in the expected direction
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backtest.engine import _build_legs, _entry_value, _make_leg_sigma_fn, run_backtest
from backtest.engine import StrategyName
from pricing.calibration import (
    CONV_ACT365, CONV_TD252, InsufficientCalibration, OffsetCurves,
    load_offsets_merged, to_trading_day_convention,
)
from pricing.sigma import SigmaMode

OFFSETS = {
    ("PUT", "25-35"): [(0.15, 2.0), (0.30, -0.3), (0.50, -2.2)],
    ("PUT", "80-100"): [(0.30, 1.0), (0.50, -0.5)],
    ("CALL", "25-35"): [(0.08, -6.2), (0.30, -5.2), (0.70, -2.4)],
    ("CALL", "80-100"): [(0.30, -3.9), (0.70, -1.2)],
}
# engine-ready variant (T=dte/252 basis; here tagged directly for tests that
# exercise the engine boundary — production callers convert from ACT/365)
OFFSETS_TD = OffsetCurves(OFFSETS, CONV_TD252)


class TestSigmaModeValidation(unittest.TestCase):
    def test_calib_without_offsets_raises(self):
        for mode in ("CALIB", "PESS"):
            with self.assertRaises(ValueError):
                run_backtest(start_date="2025-01-01", sigma_mode=mode)

    def test_flat_returns_no_resolver(self):
        self.assertIsNone(_make_leg_sigma_fn(SigmaMode.FLAT, 20.0, OFFSETS, 1.0))

    def test_engine_asserts_offset_convention(self):
        """Q087 C4: 365-basis (or untagged) offsets on the 252-basis engine
        must raise — the documented trap is now impossible to hit silently."""
        for bad in (OFFSETS,                                   # untagged dict
                    OffsetCurves(OFFSETS, CONV_ACT365)):       # unconverted
            with self.assertRaises(ValueError) as ctx:
                run_backtest(start_date="2025-01-01", end_date="2025-03-01",
                             sigma_mode="CALIB", sigma_offsets=bad)
            self.assertIn("convention", str(ctx.exception))

    def test_convention_conversion_scale(self):
        act = OffsetCurves(OFFSETS, CONV_ACT365)
        td = to_trading_day_convention(act)
        self.assertEqual(td.convention, CONV_TD252)
        scale = (252 / 365) ** 0.5
        self.assertAlmostEqual(dict(td[("PUT", "25-35")])[0.30], -0.3 * scale)
        # idempotent on already-converted curves
        self.assertIs(to_trading_day_convention(td), td)


class TestResolver(unittest.TestCase):
    def test_pess_bracket_signs(self):
        fn = _make_leg_sigma_fn(SigmaMode.PESS, 20.0, OFFSETS, 1.0)
        short = fn.for_target(0.30, False, 30, -1)
        long_ = fn.for_target(0.30, False, 30, +1)
        base = 20.0 - 0.3
        self.assertAlmostEqual(short * 100, base - 1.0)
        self.assertAlmostEqual(long_ * 100, base + 1.0)

    def test_calib_leg_sigma_by_flat_delta(self):
        fn = _make_leg_sigma_fn(SigmaMode.CALIB, 20.0, OFFSETS, 1.0)
        # ATM put: |delta| ~0.5 under FLAT → offset near -2.2
        s = fn(5000.0, -1, False, 5000.0, 30)
        self.assertLess(s, 20.0 / 100.0)          # below VIX (negative offset)
        # far OTM put (|delta|→small) → clamps to +2.0 leg → above VIX
        s = fn(5000.0, -1, False, 3500.0, 30)
        self.assertGreater(s, 20.0 / 100.0)

    def test_calib_shrinks_bps_entry_credit(self):
        """d0.30/d0.15 put offsets (−0.3/+2.0) narrow the short-long IV gap →
        BPS net credit must come in SMALLER than FLAT (the Q085 direction)."""
        spx, vix, sigma = 5000.0, 20.0, 0.20
        legs_flat, _ = _build_legs(StrategyName.BULL_PUT_SPREAD, spx, sigma)
        ev_flat = _entry_value(legs_flat, spx, sigma)
        fn = _make_leg_sigma_fn(SigmaMode.CALIB, vix, OFFSETS, 1.0)
        legs_cal, _ = _build_legs(StrategyName.BULL_PUT_SPREAD, spx, sigma,
                                  sigma_fn=fn.for_target)
        ev_cal = _entry_value(legs_cal, spx, sigma, fn)
        self.assertLess(ev_flat, 0)               # credit (negative)
        self.assertLess(ev_cal, 0)
        self.assertLess(abs(ev_cal), abs(ev_flat))


class TestOffsetsMerger(unittest.TestCase):
    def _jsonl(self, rows) -> Path:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for r in rows:
            f.write(json.dumps(r) + "\n")
        f.close()
        return Path(f.name)

    def test_dedupe_first_source_wins_and_stats(self):
        prod = self._jsonl([{"date": f"2026-06-{i:02d}", "vix": 17.0,
                             "atm_moff": -2.0, "d30_moff": -0.5, "d15_moff": 1.5}
                            for i in range(1, 11)])
        backfill = self._jsonl(
            [{"date": "2026-06-05", "vix": 17.0, "atm_moff": -99.0,
              "d30_moff": -99.0, "d15_moff": -99.0},          # dupe — must lose
             {"date": "2026-05-30", "vix": 17.0, "atm_moff": -2.0,
              "d30_moff": -0.5, "d15_moff": 1.5},
             {"date": "2026-05-29", "vix": 17.0}])            # no moff fields
        off, stats = load_offsets_merged([prod, backfill])
        self.assertEqual(stats["dupes_dropped"], 1)
        self.assertEqual(stats["days_total"], 12)
        self.assertEqual(stats["days_no_moff"], 1)
        curve = dict(off[("PUT", "25-35")])
        self.assertAlmostEqual(curve[0.30], -0.5)   # -99 dupe did not poison
        prod.unlink(); backfill.unlink()

    def test_insufficient_after_merge_raises(self):
        p = self._jsonl([{"date": "2026-06-01", "vix": 17.0, "atm_moff": -2.0,
                          "d30_moff": -0.5, "d15_moff": 1.5}])
        with self.assertRaises(InsufficientCalibration):
            load_offsets_merged([p])
        p.unlink()


class TestEngineShortWindowParity(unittest.TestCase):
    def test_flat_default_equals_explicit_flat(self):
        a = run_backtest(start_date="2024-06-01", end_date="2025-06-01")
        b = run_backtest(start_date="2024-06-01", end_date="2025-06-01",
                         sigma_mode="FLAT")
        sa = [(t.entry_date, t.exit_date, t.exit_pnl, t.entry_credit) for t in a.trades]
        sb = [(t.entry_date, t.exit_date, t.exit_pnl, t.entry_credit) for t in b.trades]
        self.assertEqual(sa, sb)

    def test_calib_changes_pricing_not_structure(self):
        flat = run_backtest(start_date="2024-06-01", end_date="2025-06-01")
        cal = run_backtest(start_date="2024-06-01", end_date="2025-06-01",
                           sigma_mode="CALIB", sigma_offsets=OFFSETS_TD)
        self.assertGreater(len(cal.trades), 0)
        self.assertNotEqual(
            [round(t.entry_credit, 6) for t in flat.trades[:5]],
            [round(t.entry_credit, 6) for t in cal.trades[:5]])


if __name__ == "__main__":
    unittest.main()
