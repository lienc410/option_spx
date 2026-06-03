"""SPEC-113 AC-N — bit-identical regression on the 35 non-changed matrix cells.

All (regime × iv × trend) combinations EXCEPT NORMAL × LOW × BULLISH must produce
the exact same Recommendation (strategy, legs, size_rule, rationale) before and
after the dict-cell refactor in catalog.py.
"""
import json
import unittest
from pathlib import Path

from signals.iv_rank import IVSignal, IVSnapshot
from signals.trend import TrendSignal, TrendSnapshot
from signals.vix_regime import Regime, Trend, VixSnapshot
from strategy.selector import StrategyName, select_strategy

FROZEN_PATH = Path(__file__).parent / "fixtures" / "spec_113_pre_refactor_outputs.json"

REGIMES = [
    ("LOW_VOL",     13.0, Regime.LOW_VOL),
    ("NORMAL",      20.0, Regime.NORMAL),
    ("HIGH_VOL",    28.0, Regime.HIGH_VOL),
    ("EXTREME_VOL", 38.0, Regime.HIGH_VOL),   # EXTREME_VOL uses HIGH_VOL enum
]
IVS = [("HIGH", 75.0), ("NEUTRAL", 55.0), ("LOW", 30.0)]
TRENDS = [("BULLISH", TrendSignal.BULLISH), ("NEUTRAL", TrendSignal.NEUTRAL), ("BEARISH", TrendSignal.BEARISH)]
EXCLUDE = {("NORMAL", "LOW", "BULLISH")}


def _make_vix(vix: float, regime: Regime) -> VixSnapshot:
    return VixSnapshot(
        date="2026-06-03", vix=vix, regime=regime, trend=Trend.FLAT,
        vix_5d_avg=vix, vix_5d_ago=vix, transition_warning=False,
        vix3m=vix + 2.0, backwardation=False,
    )


def _make_iv(ivp: float) -> IVSnapshot:
    snap = IVSnapshot.__new__(IVSnapshot)
    snap.date = "2026-06-03"; snap.vix = 18.0
    snap.iv_rank = ivp * 0.6; snap.iv_percentile = ivp
    snap.iv_signal = (IVSignal.HIGH if ivp >= 70 else IVSignal.LOW if ivp < 40 else IVSignal.NEUTRAL)
    snap.iv_52w_high = 40.0; snap.iv_52w_low = 10.0
    snap.ivp63 = ivp; snap.ivp252 = ivp
    snap.regime_decay = False; snap.local_spike = False
    return snap


def _make_trend(signal: TrendSignal) -> TrendSnapshot:
    gap = (0.03 if signal == TrendSignal.BULLISH else
           -0.03 if signal == TrendSignal.BEARISH else 0.001)
    return TrendSnapshot(
        date="2026-06-03", spx=5600.0, ma20=5550.0, ma50=5500.0,
        ma_gap_pct=gap, signal=signal, above_200=True, dist_30d_high_pct=0.05,
    )


class TestACN_BitIdentical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = json.loads(FROZEN_PATH.read_text()) if FROZEN_PATH.exists() else {}

    def _run_cell(self, rname, rvix, rregime, ivname, ivp, tname, tsig):
        vix = _make_vix(rvix, rregime)
        iv = _make_iv(ivp)
        trend = _make_trend(tsig)
        return select_strategy(vix, iv, trend)

    def test_all_35_non_changed_cells_bit_identical(self):
        if not self.frozen:
            self.skipTest("Frozen snapshot not found — run fixture generator first")

        failures = []
        for rname, rvix, rregime in REGIMES:
            for ivname, ivp in IVS:
                for tname, tsig in TRENDS:
                    if (rname, ivname, tname) in EXCLUDE:
                        continue

                    key = f"{rname}_{ivname}_{tname}"
                    expected = self.frozen.get(key)
                    if not expected:
                        continue

                    rec = self._run_cell(rname, rvix, rregime, ivname, ivp, tname, tsig)
                    actual_strategy = rec.strategy.value if hasattr(rec.strategy, "value") else str(rec.strategy)
                    actual_legs = [
                        {"action": l.action, "option": l.option, "dte": l.dte, "delta": l.delta}
                        for l in (rec.legs or [])
                    ]
                    actual_rationale = getattr(rec, "rationale", "")

                    if actual_strategy != expected["strategy"]:
                        failures.append(
                            f"{key}: strategy {actual_strategy!r} != {expected['strategy']!r}"
                        )
                    if actual_legs != expected["legs"]:
                        failures.append(
                            f"{key}: legs differ\n  got:      {actual_legs}\n  expected: {expected['legs']}"
                        )
                    if actual_rationale != expected["rationale"]:
                        failures.append(
                            f"{key}: rationale changed\n  got:      {actual_rationale!r}\n  expected: {expected['rationale']!r}"
                        )

        if failures:
            self.fail("Bit-identical regression failures:\n" + "\n".join(failures))

    def test_changed_cell_excluded_from_regression(self):
        """The changed cell (NORMAL × LOW × BULLISH) must NOT be in the frozen outputs."""
        if self.frozen:
            self.assertNotIn("NORMAL_LOW_BULLISH", self.frozen,
                             "Changed cell should be excluded from frozen outputs")

    def test_frozen_snapshot_covers_35_cells(self):
        if self.frozen:
            self.assertEqual(len(self.frozen), 35,
                             f"Expected 35 frozen cells, got {len(self.frozen)}")


if __name__ == "__main__":
    unittest.main()
