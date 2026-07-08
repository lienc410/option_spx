"""SPEC-123 — BCD family governance + code fixes; Q088 A5 dev items.

AC map:
  D1 four gates unit + halt integration (synthetic scenario)  -> TestD1Gates
  selector downgrade while halted                             -> TestSelectorHalt
  D2 N/10 counting + unlock + first-5 advisory                -> TestD2QuoteGate
  ledger ID uniqueness regression (concurrent allocs)         -> TestLedgerIds
  _effective_iv_signal single source                          -> TestSingleSource
  heartbeat registry updated                                  -> TestRegistry
  A5: ES BP staleness surface                                 -> TestEsBpFreshness
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import strategy.bcd_governance as gov
import logs.trade_log_io as tlog


class GovBase(unittest.TestCase):
    """Redirect every governance data path into a temp dir."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig = {n: getattr(gov, n) for n in
                      ("STATE_PATH", "MARKS_PATH", "CLOSED_TRADES", "SHADOW_PATH", "ROOT")}
        gov.STATE_PATH = self.tmp / "state.json"
        gov.MARKS_PATH = self.tmp / "marks.jsonl"
        gov.CLOSED_TRADES = self.tmp / "closed.jsonl"
        gov.SHADOW_PATH = self.tmp / "shadow.jsonl"
        gov.ROOT = self.tmp
        self._orig_log = tlog.TRADE_LOG_FILE
        tlog.TRADE_LOG_FILE = self.tmp / "trade_log.jsonl"

    def tearDown(self):
        for n, v in self._orig.items():
            setattr(gov, n, v)
        tlog.TRADE_LOG_FILE = self._orig_log

    def _realized(self, pnls, start="2026-01-01"):
        with gov.CLOSED_TRADES.open("a") as f:
            for i, p in enumerate(pnls):
                f.write(json.dumps({
                    "trade_id": f"t{i:03d}", "strategy_key": gov.BCD_KEY,
                    "closed_at": f"2026-0{1 + i % 6}-1{i % 3}", "realized_pnl": p,
                }) + "\n")

    def _mark(self, trade_id, d, pnl):
        with gov.MARKS_PATH.open("a") as f:
            f.write(json.dumps({"date": d, "trade_id": trade_id, "pnl_mid": pnl}) + "\n")

    def _open_position(self, tid="2026-06-03_bcd_001", **kw):
        ev = {"id": tid, "event": "open", "timestamp": "2026-06-03T11:24:03-04:00",
              "strategy_key": gov.BCD_KEY, "contracts": 1, "actual_premium": -380.0,
              "short_strike": 7750.0, "long_strike": 7450.0,
              "expiry": "2026-07-17", "long_expiry": "2026-09-18"}
        ev.update(kw)
        tlog.append_event(ev)


class TestD1Gates(GovBase):
    def test_g1_last6_realized(self):
        self._realized([100, 200, -500, -300, 100, 100, -200])  # last6 sum = -700
        fired = gov.evaluate_gates("2026-07-05")
        self.assertIn("G1_last6_realized", [f["gate"] for f in fired])

    def test_g1_needs_full_window(self):
        self._realized([-500, -500])  # only 2 trades
        self.assertNotIn("G1_last6_realized",
                         [f["gate"] for f in gov.evaluate_gates("2026-07-05")])

    def test_g2_18m_combined_with_marks(self):
        self._realized([-900, -900])                    # 2 realized in-window
        self._open_position("2026-06-03_bcd_009")
        self._mark("2026-06-03_bcd_009", "2026-07-04", -500.0)   # 3rd unit, sum<0
        fired = [f["gate"] for f in gov.evaluate_gates("2026-07-05")]
        self.assertIn("G2_18m_combined", fired)

    def test_g3_month_mark_drawdown(self):
        self._open_position("2026-06-03_bcd_009")
        self._mark("2026-06-03_bcd_009", "2026-06-30", 2_000.0)
        self._mark("2026-06-03_bcd_009", "2026-07-03", -11_000.0)  # July dd = -13k
        fired = [f["gate"] for f in gov.evaluate_gates("2026-07-05")]
        self.assertIn("G3_month_mark_dd", fired)

    def test_g4_family_cum_full_halt(self):
        self._realized([-8_000, -4_000])
        self._open_position("2026-06-03_bcd_009")
        self._mark("2026-06-03_bcd_009", "2026-07-04", -3_500.0)  # cum -15.5k
        fired = gov.evaluate_gates("2026-07-05")
        g4 = next(f for f in fired if f["gate"] == "G4_family_cum")
        self.assertTrue(g4["full_halt"])

    def test_healthy_family_no_gates(self):
        self._realized([500, 800, -200, 900, 300, 400])
        self.assertEqual(gov.evaluate_gates("2026-07-05"), [])

    def test_halt_integration_and_routine_tone(self):
        """AC: constructed halt scenario end-to-end via daily_update."""
        self._realized([100, 100, -500, -300, -100, -100])   # G1 fires
        summary = gov.daily_update("2026-07-05", calls=None, dry_run=True)
        self.assertIn("G1_last6_realized", summary["gates_fired"])
        self.assertIsNotNone(gov.is_halted())
        push = "\n".join(summary.get("pushes", []))
        self.assertIn("例行复核", push)
        self.assertIn("39-48%", push)
        self.assertNotIn("🚨", push)
        # second day: already halted — no duplicate halt push
        s2 = gov.daily_update("2026-07-06", calls=None, dry_run=True)
        self.assertNotIn("例行复核", "\n".join(s2.get("pushes", [])))

    def test_pm_clear_recovers(self):
        self._realized([100, 100, -500, -300, -100, -100])
        gov.daily_update("2026-07-05", calls=None, dry_run=True)
        gov.pm_clear("复审通过：fresh 报价对照无异常")
        self.assertIsNone(gov.is_halted())
        self.assertEqual(len(gov.read_state()["pm_reviews"]), 1)

    def test_first_realized_close_triggers_preregistered_review(self):
        summary = gov.daily_update("2026-07-05", calls=None, dry_run=True)
        self.assertNotIn("预注册复审", "\n".join(summary.get("pushes", [])))
        self._realized([1_200])
        s2 = gov.daily_update("2026-07-06", calls=None, dry_run=True)
        self.assertIn("预注册复审触发", "\n".join(s2.get("pushes", [])))
        s3 = gov.daily_update("2026-07-07", calls=None, dry_run=True)   # once only
        self.assertNotIn("预注册复审触发", "\n".join(s3.get("pushes", [])))


class TestMarks(GovBase):
    def test_marks_from_chain(self):
        import pandas as pd
        self._open_position()
        calls = pd.DataFrame([
            {"expiry": "2026-09-18", "strike": 7450.0, "mid": 520.0, "bid": 515.0, "ask": 525.0},
            {"expiry": "2026-07-17", "strike": 7750.0, "mid": 95.0, "bid": 93.0, "ask": 97.0},
        ])
        rows = gov.record_daily_marks(calls, "2026-07-05")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertAlmostEqual(r["value_mid"], 520.0 - 95.0)
        self.assertAlmostEqual(r["pnl_mid"], (-380.0 + 425.0) * 100)   # +$4,500
        self.assertAlmostEqual(r["value_natural"], 515.0 - 97.0)
        # strict-JSON on disk
        json.loads(gov.MARKS_PATH.read_text().strip(),
                   parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))


class TestSelectorHalt(GovBase):
    def _bcd_rec(self):
        from strategy.selector import (
            StrategyName, get_current_iv_snapshot, get_current_snapshot,
            get_current_trend,
        )
        rec = types.SimpleNamespace()
        return rec

    def test_halted_bcd_downgrades_to_wait(self):
        from strategy.selector import (
            IVSignal, Regime, StrategyName, TrendSignal, _apply_bcd_governance_live,
            select_strategy,
        )
        from tests.test_strategy_unification import make_iv, make_trend, make_vix
        gov._write_state({"halt": {"at": "2026-07-05",
                                   "gates": [{"gate": "G1_last6_realized"}]}})
        vix = make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=None)
        iv = make_iv(signal=IVSignal.LOW, iv_rank=10.0, iv_percentile=12.0, vix=13.0)
        trend = make_trend(signal=TrendSignal.BULLISH)
        rec = select_strategy(vix, iv, trend)
        self.assertEqual(rec.strategy_key, "bull_call_diagonal")   # matrix routes BCD
        wrapped = _apply_bcd_governance_live(rec, vix, iv, trend)
        self.assertEqual(wrapped.strategy, StrategyName.REDUCE_WAIT)
        self.assertIn("G1_last6_realized", wrapped.rationale)
        self.assertIn("例行复核", wrapped.rationale)

    def test_not_halted_bcd_passes_with_quote_gate_advisory(self):
        from strategy.selector import (
            IVSignal, Regime, TrendSignal, _apply_bcd_governance_live, select_strategy,
        )
        from tests.test_strategy_unification import make_iv, make_trend, make_vix
        vix = make_vix(vix=13.0, regime=Regime.LOW_VOL, trend=None)
        iv = make_iv(signal=IVSignal.LOW, iv_rank=10.0, iv_percentile=12.0, vix=13.0)
        trend = make_trend(signal=TrendSignal.BULLISH)
        rec = select_strategy(vix, iv, trend)
        wrapped = _apply_bcd_governance_live(rec, vix, iv, trend)
        self.assertEqual(wrapped.strategy_key, "bull_call_diagonal")
        # SPEC-136：rationale 与 quote_gate_status().label_human 单源
        self.assertIn("真实报价已积累 0/10 天", wrapped.rationale)


class TestD2QuoteGate(GovBase):
    def _shadow_day(self, d, regime="LOW_VOL", ok=True):
        row = {"date": d, "regime": regime, "lane": "lowvol_quote_gate"}
        if ok:
            row.update({"long_mid": 500.0, "short_mid": 120.0})
        else:
            row["error"] = "missing_chain"
        with gov.SHADOW_PATH.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def test_counting_excludes_errors_and_other_regimes(self):
        self._shadow_day("2026-07-01")
        self._shadow_day("2026-07-02", ok=False)
        self._shadow_day("2026-07-03", regime="NORMAL")
        self.assertEqual(gov.quote_gate_status()["days"], 1)

    def test_unlock_requires_days_and_drift(self):
        for i in range(10):
            self._shadow_day(f"2026-08-{i+1:02d}")
        with patch.object(gov, "_calib_drift_ok", return_value=(False, "c30 drift")):
            self.assertIsNone(gov.check_quote_gate_unlock("2026-08-11"))
            self.assertFalse(gov.quote_gate_status()["unlocked"])
        with patch.object(gov, "_calib_drift_ok", return_value=(True, "ok")):
            msg = gov.check_quote_gate_unlock("2026-08-11")
        # SPEC-136：D2 代号移出主文案
        self.assertIn("前置条件已满足", msg)
        self.assertIn("前 5 笔每笔限 1 张", msg)
        self.assertTrue(gov.quote_gate_status()["unlocked"])
        # idempotent
        with patch.object(gov, "_calib_drift_ok", return_value=(True, "ok")):
            self.assertIsNone(gov.check_quote_gate_unlock("2026-08-12"))

    def test_first5_advisory_counts_post_unlock_opens(self):
        gov._write_state({"quote_gate_unlocked": True,
                          "quote_gate_unlocked_at": "2026-08-11"})
        self._open_position("2026-08-12_bcd_001",
                            timestamp="2026-08-12T10:00:00-04:00")
        adv = gov.first5_advisory()
        self.assertIn("1/5", adv)
        for i in range(2, 6):
            self._open_position(f"2026-08-12_bcd_{i:03d}",
                                timestamp="2026-08-12T10:00:00-04:00")
        self.assertIsNone(gov.first5_advisory())


class TestLedgerIds(GovBase):
    def test_concurrent_allocations_unique(self):
        """Regression for the 2026-06-03 collision: allocate+append under
        ID_ALLOC_LOCK from many threads must yield unique ids."""
        ids = []

        def worker():
            with tlog.ID_ALLOC_LOCK:
                tid = tlog.next_trade_id("bull_call_diagonal")
                tlog.append_event({"id": tid, "event": "open"})
            ids.append(tid)

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(ids), len(set(ids)))

    def test_resolve_log_flags_duplicate_open(self):
        self._open_position("2026-06-03_bcd_001")
        self._open_position("2026-06-03_bcd_001",
                            timestamp="2026-06-03T11:24:05-04:00")
        row = next(r for r in tlog.resolve_log() if r["id"] == "2026-06-03_bcd_001")
        self.assertEqual(row["duplicate_open_count"], 2)


class TestSingleSource(unittest.TestCase):
    def test_effective_iv_signal_defined_once(self):
        """Q087 C4/SPEC-123 §4b: one production implementation, no copies."""
        defs = []
        for p in REPO.rglob("*.py"):
            if "venv" in p.parts or ".git" in p.parts:
                continue
            try:
                if re.search(r"^\s*def _effective_iv_signal\b",
                             p.read_text(encoding="utf-8"), re.M):
                    defs.append(str(p.relative_to(REPO)))
            except (UnicodeDecodeError, OSError):
                continue
        self.assertEqual(defs, ["strategy/selector.py"])

    def test_consumers_import_the_production_function(self):
        for p in REPO.rglob("*.py"):
            if "venv" in p.parts or p.name == "selector.py" or "prototype" in p.parts:
                continue
            try:
                src = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            # only CALLS count (name immediately followed by "(") — docstring
            # mentions like "_effective_iv_signal (IVR/IVP ...)" are fine
            if re.search(r"_effective_iv_signal\(", src):
                self.assertTrue(
                    "from strategy.selector import" in src
                    or "selector._effective_iv_signal" in src
                    or "import strategy.selector" in src
                    or p.name == "test_spec_123.py",
                    f"{p} calls _effective_iv_signal without importing it")


class TestRegistry(unittest.TestCase):
    def test_governance_marker_registered(self):
        reg = json.loads((REPO / "ops" / "heartbeat_registry.json").read_text())
        entry = next(j for j in reg["jobs"]
                     if j["label"] == "com.spxstrat.q085_s2bps.bcd_governance")
        self.assertEqual(entry["freshness"]["rule"], "trading_day")
        self.assertEqual(entry["freshness"]["path"], "data/.q087_bcd_gov_ran")


class TestEsBpFreshness(unittest.TestCase):
    def test_staleness_warning_after_90_days(self):
        from web import server as srv
        with patch.object(srv, "_ES_BP_PER_CONTRACT_AS_OF", "2026-01-01"):
            warn = srv._es_bp_staleness_warning()
        self.assertIsNotNone(warn)
        self.assertIn("re-measure", warn)
        with patch.object(srv, "_ES_BP_PER_CONTRACT_AS_OF",
                          srv.datetime.now(srv._ET).date().isoformat()):
            self.assertIsNone(srv._es_bp_staleness_warning())


if __name__ == "__main__":
    unittest.main()
