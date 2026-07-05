"""SPEC-124 — Q088 T1 制度化批.

§1 SPEC-079 retirement (default disabled, shadow log unpolluted)
§2 assertion batch, each with a negative case:
   - profit-target catalog↔selector↔bot consistency
   - sleeve_governance 100k fallback is shadow-display only
   - matrix display↔behavior consistency (SPEC-060 case generalized,
     HIGH_VOL two cells attributed to aftermath)
§4 DEFERRED.md monthly digest (first-Monday trigger, fake-overdue integration)
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ET = ZoneInfo("America/New_York")


class TestSpec079Retirement(unittest.TestCase):
    def test_default_mode_disabled(self):
        from strategy.selector import DEFAULT_PARAMS
        self.assertEqual(DEFAULT_PARAMS.bcd_comfort_filter_mode, "disabled")

    def test_disabled_mode_writes_nothing_and_never_blocks(self):
        import strategy.bcd_filter as bf
        orig = bf._SHADOW_LOG
        bf._SHADOW_LOG = Path(tempfile.mkdtemp()) / "shadow.jsonl"
        try:
            # risk_score == 3 inputs — would block in active mode
            blocked = bf.should_block_bcd("disabled", vix=12.0,
                                          dist_30d_high_pct=-0.02, ma_gap_pct=0.02)
            self.assertFalse(blocked)
            self.assertFalse(bf._SHADOW_LOG.exists())   # zero log writes
            # negative control: shadow mode DOES write (research opt-in intact)
            bf.should_block_bcd("shadow", vix=12.0,
                                dist_30d_high_pct=-0.02, ma_gap_pct=0.02)
            self.assertTrue(bf._SHADOW_LOG.exists())
        finally:
            bf._SHADOW_LOG = orig


_PROFIT_PATTERNS = (
    r"(?<![-–\d])(\d{2})%\s+profit",       # "60% profit", "take 60% profit"
    r"[Cc]lose at (\d{2})% of credit",     # "Close at 60% of credit (received)"
    r"[Tt]ake profit at \+(\d{2})%",       # "Take profit at +60% of debit"
)


def _profit_pcts_in(text: str) -> set[int]:
    """Profit-target percents only — stop/loss phrasings ("-50% of debit",
    "50% loss") and return-magnitude ranges ("15–20% of debit paid") are
    different rules and deliberately not matched."""
    out: set[int] = set()
    for pat in _PROFIT_PATTERNS:
        out.update(int(m) for m in re.findall(pat, text))
    return out


def _check_profit_target_consistency(descriptors: dict, profit_target: float) -> list[str]:
    """Return violations: engine-managed SPX strategies whose catalog profit
    texts state a percent != params.profit_target."""
    expected = int(round(profit_target * 100))
    engine_keys = {"bull_put_spread", "bull_put_spread_hv", "iron_condor",
                   "iron_condor_hv", "bear_call_spread_hv", "bull_call_diagonal"}
    bad = []
    for key in engine_keys:
        d = descriptors[key]
        for text in (d.detail_roll_text, d.target_return_text, d.roll_rule_text):
            for pct in _profit_pcts_in(text):
                # stop texts use loss/credit multiples ("50% loss", "-50% of
                # debit") — the regex above only captures profit phrasings
                if pct != expected:
                    bad.append(f"{key}: '{text}' says {pct}% (expected {expected}%)")
    return bad


class TestProfitTargetConsistency(unittest.TestCase):
    def test_catalog_matches_selector(self):
        from strategy.catalog import STRATEGIES_BY_KEY
        from strategy.selector import DEFAULT_PARAMS
        self.assertEqual(
            _check_profit_target_consistency(STRATEGIES_BY_KEY, DEFAULT_PARAMS.profit_target),
            [])

    def test_bot_push_text_matches_selector(self):
        from strategy.selector import DEFAULT_PARAMS
        src = (REPO / "notify" / "telegram_bot.py").read_text(encoding="utf-8")
        expected = int(round(DEFAULT_PARAMS.profit_target * 100))
        self.assertIn(f"target: {expected}%", src)

    def test_negative_stale_text_is_caught(self):
        import types
        from strategy.catalog import STRATEGIES_BY_KEY
        fake = dict(STRATEGIES_BY_KEY)
        d = fake["iron_condor"]
        fake["iron_condor"] = types.SimpleNamespace(
            detail_roll_text="Target 50% profit after 10 days",
            target_return_text=d.target_return_text,
            roll_rule_text=d.roll_rule_text)
        bad = _check_profit_target_consistency(fake, 0.60)
        self.assertEqual(len(bad), 1)
        self.assertIn("iron_condor", bad[0])


def _check_100k_fallback_lines(src: str) -> list[str]:
    """Every 100_000.0 fallback in sleeve_governance must be tagged as
    shadow-display-only on the same line; cap math must never see it."""
    bad = []
    for i, line in enumerate(src.splitlines(), 1):
        if "100_000.0" in line and "shadow-display" not in line:
            bad.append(f"line {i}: {line.strip()}")
    return bad


class Test100kFallbackShadowOnly(unittest.TestCase):
    def test_source_tags_every_fallback(self):
        src = (REPO / "strategy" / "sleeve_governance.py").read_text(encoding="utf-8")
        self.assertEqual(_check_100k_fallback_lines(src), [])

    def test_negative_untagged_fallback_is_caught(self):
        bad = _check_100k_fallback_lines("nlv = basis or 100_000.0  # cap math\n")
        self.assertEqual(len(bad), 1)

    def test_cap_math_fails_closed_without_basis(self):
        """Functional negative: no basis anywhere → evaluate_candidate must
        reject (R0), NOT price the cap off the 100k display fallback."""
        import strategy.sleeve_governance as gov
        from unittest.mock import patch
        with patch.object(gov, "_resolve_basis", return_value=(None, True)):
            decision = gov.evaluate_candidate({
                "strategy_key": "bull_put_spread", "strategy": "Bull Put Spread",
                "underlying": "SPX", "account": "schwab", "action": "open",
                "contracts": 1, "requested_bp_dollars": 2_000.0,
            })
        self.assertFalse(decision.accepted)
        self.assertIn("basis_unavailable", decision.reason)


# SPEC-124 §2: display↔behavior divergences that are DOCUMENTED AND ATTRIBUTED.
# Anything outside this table failing display==behavior is regression drift.
MATRIX_DIVERGENCE_ATTRIBUTION = {
    # SPEC-060 case generalized: IVP dual-gate parks these displayed cells on
    # wait at the synthesized in-cell point (SPEC-120 verdict: wait correct)
    ("LOW_VOL", "HIGH", "BULLISH"): "reduce_wait",
    ("LOW_VOL", "HIGH", "NEUTRAL"): "reduce_wait",
    ("NORMAL", "HIGH", "BULLISH"): "reduce_wait",
    # aftermath attribution (Q088 T1 / external review): canonical BCS_HV /
    # BPS_HV paths are fully consumed by aftermath/VIX-rising/ivp63 gates —
    # these cells behaviorally ride iron_condor_hv (263/263, 175/175 days)
    ("HIGH_VOL", "HIGH", "BEARISH"): "iron_condor_hv",
    ("HIGH_VOL", "NEUTRAL", "BULLISH"): "iron_condor_hv",
}


def _matrix_divergences() -> dict:
    from strategy.catalog import CANONICAL_MATRIX
    from strategy.selector import select_strategy
    from web.server import (_synth_iv_snapshot, _synth_trend_snapshot,
                            _synth_vix_snapshot)
    out = {}
    for rg, ivmap in CANONICAL_MATRIX.items():
        for iv, tmap in ivmap.items():
            for tr, disp in tmap.items():
                rec = select_strategy(_synth_vix_snapshot(rg),
                                      _synth_iv_snapshot(iv),
                                      _synth_trend_snapshot(tr))
                disp_set = set(disp.values()) if isinstance(disp, dict) else {disp}
                if rec.strategy_key not in disp_set:
                    out[(rg, iv, tr)] = rec.strategy_key
    return out


class TestMatrixDisplayBehaviorConsistency(unittest.TestCase):
    def test_divergences_exactly_match_attribution_table(self):
        self.assertEqual(_matrix_divergences(), MATRIX_DIVERGENCE_ATTRIBUTION)

    def test_negative_unattributed_divergence_fails(self):
        stale = dict(MATRIX_DIVERGENCE_ATTRIBUTION)
        stale.pop(("HIGH_VOL", "HIGH", "BEARISH"))
        self.assertNotEqual(_matrix_divergences(), stale)


class TestDeferredMonthlyDigest(unittest.TestCase):
    def _md(self, rows: str) -> Path:
        p = Path(tempfile.mkdtemp()) / "DEFERRED.md"
        p.write_text(
            "# DEFERRED.md\n\n"
            "| # | 项目 | 来源 | 停靠日 | 复核期限 | Owner | 状态 |\n"
            "|---|---|---|---|---|---|---|\n" + rows, encoding="utf-8")
        return p

    def test_fake_overdue_item_integration(self):
        from scripts.ops_heartbeat import _deferred_digest
        p = self._md(
            "| 1 | 假过期项 | test | 2026-01-01 | 2026-06-30 | Quant | 排队 |\n"
            "| 2 | 在期项 | test | 2026-07-01 | 2099-12-31 | Quant | 排队 |\n"
            "| 3 | 条件项 | test | 2026-07-01 | 条件触发（xx） | PM | 挂起 |\n")
        first_monday = datetime(2026, 8, 3, 17, 30, tzinfo=ET)
        digest = _deferred_digest(first_monday, path=p)
        self.assertIn("逾期未复核 1 项", digest)
        self.assertIn("假过期项", digest)
        self.assertIn("2026-06-30", digest)
        self.assertIn("在期 1 项", digest)
        self.assertIn("条件/事件挂起 1 项", digest)

    def test_only_first_monday_fires(self):
        from scripts.ops_heartbeat import _deferred_digest
        p = self._md("| 1 | 假过期项 | test | 2026-01-01 | 2026-06-30 | Quant | 排队 |\n")
        self.assertIsNone(_deferred_digest(datetime(2026, 8, 10, 17, 30, tzinfo=ET), path=p))
        self.assertIsNone(_deferred_digest(datetime(2026, 8, 4, 17, 30, tzinfo=ET), path=p))

    def test_escaped_pipe_in_item_name(self):
        from scripts.ops_heartbeat import _deferred_digest
        p = self._md(
            "| 11 | LOW_VOL\\|NEUTRAL 格改路由 | BCD packet D3 | 2026-07-05 | 2026-06-30 | Quant | 排队 |\n")
        digest = _deferred_digest(datetime(2026, 8, 3, 17, 30, tzinfo=ET), path=p)
        self.assertIn("LOW_VOL|NEUTRAL 格改路由", digest)
        self.assertIn("owner Quant", digest)   # columns not shifted by the \\|

    def test_real_ledger_parses(self):
        from scripts.ops_heartbeat import _deferred_digest
        digest = _deferred_digest(datetime(2026, 8, 3, 17, 30, tzinfo=ET))
        self.assertIsNotNone(digest)   # the live ledger has rows


if __name__ == "__main__":
    unittest.main()
