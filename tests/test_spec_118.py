"""SPEC-118 quick-win batch tests.

118.1 aftermath EXTREME boundary unified to StrategyParams.extreme_vix
118.2 NLV fallback: last-successful-basis + degraded alert + fail-closed
118.3 backtest cache keys embed the algo git hash
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import strategy.sleeve_governance as gov
from signals.vix_regime import Regime, Trend, VixSnapshot
from strategy.selector import DEFAULT_PARAMS, StrategyParams, is_aftermath


def _vix_snap(vix: float, peak: float) -> VixSnapshot:
    return VixSnapshot(
        date="2026-07-05", vix=vix, regime=Regime.HIGH_VOL, trend=Trend.FLAT,
        vix_5d_avg=vix, vix_5d_ago=vix, transition_warning=False,
        vix3m=vix + 2.0, backwardation=False, vix_peak_10d=peak,
    )


class TestAC1181_AftermathBoundary(unittest.TestCase):
    def test_boundary_now_params_extreme_vix(self):
        # peak 40, 10% off-peak → aftermath structurally true; boundary decides
        self.assertEqual(DEFAULT_PARAMS.extreme_vix, 35.0)
        self.assertTrue(is_aftermath(_vix_snap(34.9, peak=40.0)))
        # SPEC-118.1 visible change window: VIX in [35, 40) is now inactive
        self.assertFalse(is_aftermath(_vix_snap(35.0, peak=45.0)))
        self.assertFalse(is_aftermath(_vix_snap(39.0, peak=45.0)))
        self.assertFalse(is_aftermath(_vix_snap(40.0, peak=50.0)))

    def test_boundary_follows_params_override(self):
        p = StrategyParams(extreme_vix=40.0)
        self.assertTrue(is_aftermath(_vix_snap(38.0, peak=45.0), params=p))
        self.assertFalse(is_aftermath(_vix_snap(38.0, peak=45.0)))  # default 35


class TestAC1182_BasisFallback(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.runtime = Path(self.tmpdir.name) / "sleeve_governance_runtime.json"
        gov._BASIS_DEGRADED_ALERTED.clear()

    def _state(self, basis=None):
        return {
            "basis_dollars": basis,
            "pools": {"spx_pm_bp_pct": 5.0, "combined_bp_pct": 5.0,
                      "es_span_bp_pct": 0.0, "short_vol_bp_pct": 0.0},
            "caps": {"active_spx_pm_cap_pct": 80.0},
            "stress_episode_active": False, "second_leg_active": False,
            "booster_active": False,
        }

    def test_live_basis_passthrough(self):
        basis, degraded = gov._resolve_basis(self._state(basis=1_240_000.0))
        self.assertEqual(basis, 1_240_000.0)
        self.assertFalse(degraded)

    def test_degraded_uses_last_known_and_alerts_once(self):
        self.runtime.write_text(json.dumps(
            {"basis_dollars": 1_200_000.0, "timestamp": "2026-07-04T17:00:00"}))
        with patch.object(gov, "RUNTIME_STATE_PATH", self.runtime), \
             patch.object(gov, "_send_alert") as alert:
            b1, d1 = gov._resolve_basis(self._state(basis=None))
            b2, d2 = gov._resolve_basis(self._state(basis=None))
        self.assertEqual(b1, 1_200_000.0)
        self.assertTrue(d1 and d2)
        alert.assert_called_once()          # dedup per day
        self.assertIn("degraded", alert.call_args[0][0].lower())

    def test_degraded_snapshot_does_not_self_poison(self):
        # runtime written while degraded must NOT serve as last-known
        self.runtime.write_text(json.dumps(
            {"basis_dollars": 1_200_000.0, "basis_degraded": True}))
        with patch.object(gov, "RUNTIME_STATE_PATH", self.runtime):
            b, _ = gov._resolve_basis(self._state(basis=None))
        self.assertIsNone(b)

    def test_evaluate_candidate_fails_closed_with_no_basis_anywhere(self):
        with patch.object(gov, "RUNTIME_STATE_PATH", self.runtime):  # missing file
            decision = gov.evaluate_candidate(
                {"strategy_key": "bull_put_spread", "requested_bp_dollars": 10_000.0},
                state=self._state(basis=None),
            )
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule, "R0")
        self.assertIn("basis_unavailable", decision.reason)

    def test_evaluate_candidate_works_on_last_known(self):
        self.runtime.write_text(json.dumps(
            {"basis_dollars": 1_240_000.0, "timestamp": "2026-07-04T17:00:00"}))
        with patch.object(gov, "RUNTIME_STATE_PATH", self.runtime), \
             patch.object(gov, "_send_alert"):
            decision = gov.evaluate_candidate(
                {"strategy_key": "bull_put_spread", "requested_bp_dollars": 10_000.0},
                state=self._state(basis=None),
            )
        # 10k / 1.24M is tiny → accepted on the stale-but-real denominator
        self.assertTrue(decision.accepted)

    def test_no_100k_constant_left(self):
        src = Path(gov.__file__).read_text()
        self.assertNotIn("COMBINED_NLV", src)


class TestAC1183_AlgoHashInCacheKey(unittest.TestCase):
    def test_algo_hash_shape(self):
        import web.server as srv
        srv._ALGO_HASH_CACHE = None
        h = srv._algo_hash()
        self.assertTrue(h == "nogit" or (4 <= len(h) <= 12))

    def test_params_hash_changes_with_algo_hash(self):
        import web.server as srv
        srv._ALGO_HASH_CACHE = "aaaa111"
        h1 = srv._params_hash()
        srv._ALGO_HASH_CACHE = "bbbb222"
        h2 = srv._params_hash()
        srv._ALGO_HASH_CACHE = None  # restore lazy
        self.assertNotEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
