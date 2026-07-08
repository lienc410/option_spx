"""SPEC-116 — Q085 S2-BPS paper sleeve acceptance tests.

AC-1 signal consistency vs frozen vectors (cache-verified; see note below)
AC-2 chain extraction integration smoke (real SPX.parquet, non-mock)
AC-3 skew monitor strict-JSON schema
AC-4 non-signal-day Telegram silence
AC-5 paper lifecycle open→(stop|expiry) close, dual-basis PnL
AC-6 production zero-perturbation (selector/catalog/gates untouched vs HEAD)
AC-7 Layer-1: VIX>=35 never signals

Frozen-vector provenance (AC-1): the handoff's 12 positive dates were
independently re-verified against research/q078/_signal_history_cache.csv per
the handoff's own instruction. 7 of 12 did not reproduce (manual transcription
errors on the research side); the positives below are the cache-authoritative
replacements. All 12 negatives reproduced and are kept (two death-cause
annotations corrected to match cache).
"""
import glob
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from strategy.q085_s2bps_signal import (
    oversold_composite,
    signal_day,
    wilder_rsi,
)

REPO = Path(__file__).resolve().parents[1]
# SPEC-122 小修3 post-mortem: the q078 cache is a ROUTING SOURCE that gets
# regenerated with current selector code (external review condition) — its
# strategy_key column legitimately changes as routing evolves (e.g. SPEC-113
# re-routed 2025-12-16 to bull_call_diagonal, flipping that frozen vector's
# overlap gate). The frozen vectors therefore pin their own immutable fixture:
# the exact cache state they were ratified against (git f578933).
CACHE = REPO / "tests" / "fixtures" / "spec116_frozen_signal_cache.csv"

# Cache-verified positives (replaces handoff list; see module docstring)
POSITIVE_DATES = [
    "2024-04-04", "2024-04-15", "2024-07-19", "2024-07-24",
    "2024-09-05", "2024-10-23", "2024-11-15", "2025-02-26",
    "2025-05-21", "2025-06-20", "2025-08-01", "2025-12-16",
]
# Handoff negatives — all 12 reproduced against cache
NEGATIVE_DATES = [
    "2024-03-14",  # 未超卖 (LOW_VOL too)
    "2024-08-05",  # HIGH_VOL regime
    "2024-11-06",  # 未超卖 (annotation corrected; blocked=True in cache)
    "2025-04-07",  # VIX>35 Layer-1
    "2024-06-12",  # 未超卖
    "2024-10-15",  # 未超卖 (annotation corrected; blocked=True in cache)
    "2025-04-10",  # HIGH_VOL
    "2024-02-13",  # 未超卖 + 放行
    "2025-07-01",  # 未超卖
    "2024-09-06",  # 超卖但 HIGH_VOL
    "2025-05-14",  # 未超卖
    "2024-12-30",  # 超卖但放行日 (annotation corrected)
]


def _cache_signal_frame() -> pd.DataFrame:
    df = pd.read_csv(CACHE, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    return df


def _signal_via_module(df: pd.DataFrame, date_str: str) -> dict:
    """Run signal_day() with point-in-time closes up to date_str + cache regime/key."""
    i = df.index[df.date_str == date_str]
    assert len(i) == 1, f"{date_str} not in cache"
    i = int(i[0])
    closes = df["spx"].astype(float).iloc[: i + 1].tolist()
    row = df.iloc[i]
    sk = row["strategy_key"]
    sk = None if (pd.isna(sk) or str(sk).strip() == "") else str(sk)
    return signal_day(closes, float(row["vix"]), str(row["regime"]), sk)


class TestAC1_FrozenVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = _cache_signal_frame()

    def test_positives(self):
        for d in POSITIVE_DATES:
            with self.subTest(date=d):
                out = _signal_via_module(self.df, d)
                self.assertTrue(out["signal"], f"{d} expected signal=True, got {out}")

    def test_negatives(self):
        for d in NEGATIVE_DATES:
            with self.subTest(date=d):
                out = _signal_via_module(self.df, d)
                self.assertFalse(out["signal"], f"{d} expected signal=False, got {out}")


class TestSignalPrimitives(unittest.TestCase):
    def test_wilder_rsi_extremes(self):
        up = list(range(100, 400))          # monotonic up → RSI ~100
        self.assertGreater(wilder_rsi([float(x) for x in up], 2), 90)
        dn = list(range(400, 100, -1))      # monotonic down → RSI ~0
        self.assertLess(wilder_rsi([float(x) for x in dn], 2), 10)

    def test_down3_semantics(self):
        base = [100.0] * 300
        self.assertTrue(oversold_composite(base + [99, 98, 97])["down3"])
        # flat day breaks the streak
        self.assertFalse(oversold_composite(base + [99, 99, 98])["down3"])

    def test_blocked_accepts_both_conventions(self):
        closes = [100.0] * 300 + [99, 98, 97]  # oversold via down3
        for sk in (None, "", "reduce_wait"):
            self.assertTrue(signal_day(closes, 18.0, "NORMAL", sk)["signal"], sk)
        self.assertFalse(signal_day(closes, 18.0, "NORMAL", "bull_put_spread")["signal"])


class TestAC7_Layer1(unittest.TestCase):
    def test_vix_35_blocks_even_when_oversold_and_blocked(self):
        closes = [100.0] * 300 + [99, 98, 97]
        for vix in (35.0, 36.0, 46.98, 82.7):  # includes 2020-03-style prints
            out = signal_day(closes, vix, "NORMAL", None)
            self.assertTrue(out["oversold"] and out["blocked"])
            self.assertFalse(out["signal"], f"VIX {vix} must not signal")
        self.assertTrue(signal_day(closes, 34.99, "NORMAL", None)["signal"])

    def test_cache_2025_04_07_style(self):
        df = _cache_signal_frame()
        out = _signal_via_module(df, "2025-04-07")  # VIX 46.98, oversold, blocked
        self.assertTrue(out["oversold"])
        self.assertFalse(out["layer1_ok"])
        self.assertFalse(out["signal"])


class TestAC2_ChainIntegration(unittest.TestCase):
    """Non-mock smoke on a real SPX.parquet (per feedback_spec_integration_test)."""

    @classmethod
    def setUpClass(cls):
        snaps = sorted(glob.glob(str(REPO / "data" / "q041_chains" / "*" / "SPX.parquet")))
        if not snaps:
            raise unittest.SkipTest("no SPX chain snapshot available locally")
        cls.snap = Path(snaps[-1])
        cls.date_str = cls.snap.parent.name

    def test_skew_and_bps_on_real_chain(self):
        import notify.q085_s2bps_paper as job
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(job, "CHAIN_DIR", self.snap.parents[1]), \
                 patch.object(job, "SKEW_OUT", Path(tmp) / "skew.jsonl"), \
                 patch.object(job, "LEDGER", Path(tmp) / "ledger.jsonl"):
                puts = job.load_today_chain(self.date_str)
                self.assertIsNotNone(puts)
                for col in ("expiry", "dte", "strike", "bid", "ask", "mid", "delta", "iv", "close"):
                    self.assertIn(col, puts.columns)

                skew = job.measure_skew(puts, vix=20.0, date_str=self.date_str)
                for k in ("date", "vix", "atm_iv", "d30_iv", "d15_iv", "d30_off", "d15_off", "atm_off"):
                    self.assertIn(k, skew)
                # put skew: deeper OTM legs carry higher IV than ATM
                self.assertGreater(skew["d15_iv"], skew["atm_iv"])

                opened = job.build_paper_bps(
                    puts, self.date_str, vix=20.0,
                    sig={"rsi2": 5.0, "down3": True},
                )
                self.assertLess(opened["k_long"], opened["k_short"])
                self.assertGreater(opened["credit_mid"], 0)
                # natural (cross the spread) never beats mid
                self.assertLessEqual(opened["credit_natural"], opened["credit_mid"])
                self.assertTrue(15 <= opened["dte"] <= 45)


class TestAC3_SkewStrictJSON(unittest.TestCase):
    def test_nan_rejected(self):
        import notify.q085_s2bps_paper as job
        with self.assertRaises(ValueError):
            job._assert_finite({"date": "2026-07-04", "vix": float("nan")}, "test")
        with self.assertRaises(ValueError):
            job._assert_finite({"x": float("inf")}, "test")
        job._assert_finite({"date": "2026-07-04", "vix": 20.0}, "test")  # no raise

    def test_written_rows_parse_strict(self):
        import notify.q085_s2bps_paper as job
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "skew.jsonl"
            with patch.object(job, "SKEW_OUT", out):
                job._append_jsonl(out, {"date": "2026-07-04", "vix": 20.0}, "t")
            raw = out.read_text()
            json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


class TestAC5_Lifecycle(unittest.TestCase):
    def _mk_chain(self, dte: int, s_mid: float, l_mid: float, spx_close: float = 5000.0):
        rows = []
        for strike, mid, delta in ((4900.0, s_mid, -0.30), (4700.0, l_mid, -0.15)):
            rows.append({
                "option_type": "PUT", "expiry": "2026-08-07", "dte": dte,
                "strike": strike, "bid": mid - 0.5, "ask": mid + 0.5, "mid": mid,
                "delta": delta, "iv": 25.0, "close": spx_close,
            })
        return pd.DataFrame(rows)

    def _open_pos(self, job, tmp):
        chain = self._mk_chain(dte=30, s_mid=40.0, l_mid=15.0)
        return job.build_paper_bps(chain, "2026-07-04", vix=20.0,
                                   sig={"rsi2": 4.2, "down3": False})

    def test_stop_path(self):
        import notify.q085_s2bps_paper as job
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(job, "SKEW_OUT", Path(tmp) / "s.jsonl"), \
                 patch.object(job, "LEDGER", Path(tmp) / "l.jsonl"):
                opened = self._open_pos(job, tmp)         # credit_mid = 25.0
                # cost_mid = 80-3=77 >= 3*25 → stop
                chain2 = self._mk_chain(dte=25, s_mid=80.0, l_mid=3.0, spx_close=4600.0)
                closes = job.manage_open_positions(chain2, "2026-07-10")
                self.assertEqual(len(closes), 1)
                c = closes[0]
                self.assertEqual(c["reason"], "stop")
                self.assertTrue(c["breach"])              # 4600 < 4900
                self.assertAlmostEqual(c["pnl_mid"], (25.0 - 77.0) * 100, places=2)
                self.assertEqual(c["hold_days"], 6)
                # natural leg: cost_natural = ask_s - bid_l = 80.5 - 2.5 = 78
                self.assertAlmostEqual(c["cost_natural"], 78.0, places=2)

    def test_expiry_path_and_no_double_close(self):
        import notify.q085_s2bps_paper as job
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(job, "SKEW_OUT", Path(tmp) / "s.jsonl"), \
                 patch.object(job, "LEDGER", Path(tmp) / "l.jsonl"):
                self._open_pos(job, tmp)
                # healthy cost but DTE hits 21 → expiry_rule
                chain2 = self._mk_chain(dte=21, s_mid=20.0, l_mid=5.0)
                closes = job.manage_open_positions(chain2, "2026-07-13")
                self.assertEqual(closes[0]["reason"], "expiry_rule")
                self.assertGreater(closes[0]["pnl_mid"], 0)
                self.assertFalse(closes[0]["breach"])
                # already closed → second manage pass is a no-op
                again = job.manage_open_positions(chain2, "2026-07-14")
                self.assertEqual(again, [])

    def test_no_trigger_stays_open(self):
        import notify.q085_s2bps_paper as job
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(job, "SKEW_OUT", Path(tmp) / "s.jsonl"), \
                 patch.object(job, "LEDGER", Path(tmp) / "l.jsonl"):
                self._open_pos(job, tmp)
                chain2 = self._mk_chain(dte=28, s_mid=45.0, l_mid=16.0)
                self.assertEqual(job.manage_open_positions(chain2, "2026-07-07"), [])

    def test_degradation_note(self):
        import notify.q085_s2bps_paper as job
        with tempfile.TemporaryDirectory() as tmp:
            led = Path(tmp) / "l.jsonl"
            with patch.object(job, "LEDGER", led):
                self.assertIsNone(job.degradation_note())          # empty ledger
                for pnl in (-3000.0, -2500.0):
                    job._append_jsonl(led, {"event": "close", "pnl_mid": pnl}, "t")
                note = job.degradation_note()
                self.assertTrue(note["trip_trailing"])
                self.assertTrue(note["trip_cum"])                  # -5500 <= -5000


class TestAC4_Silence(unittest.TestCase):
    def test_non_signal_day_no_telegram(self):
        """Full run on a real snapshot with signal forced False → zero sends."""
        import notify.q085_s2bps_paper as job
        snaps = sorted(glob.glob(str(REPO / "data" / "q041_chains" / "*" / "SPX.parquet")))
        if not snaps:
            self.skipTest("no SPX chain snapshot available locally")
        snap = Path(snaps[-1]); date_str = snap.parent.name

        class _Rec:  # minimal recommendation stub
            class vix_snapshot:
                vix = 18.0
                regime = "NORMAL"
            strategy_key = "bull_put_spread"   # not blocked → no signal

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(job, "CHAIN_DIR", snap.parents[1]), \
                 patch.object(job, "SKEW_OUT", Path(tmp) / "s.jsonl"), \
                 patch.object(job, "LEDGER", Path(tmp) / "l.jsonl"), \
                 patch.object(job, "_telegram_send") as tg, \
                 patch("strategy.selector.get_recommendation", return_value=_Rec()), \
                 patch("signals.trend.fetch_spx_history",
                       return_value=pd.DataFrame({"close": [5000.0] * 300})):
                out = job.run(date_str, dry_run=False)
            tg.assert_not_called()
            self.assertIsNotNone(out["skew"])       # skew still written
            self.assertFalse(out["signal"]["signal"])

    def test_missing_chain_notifies(self):
        import notify.q085_s2bps_paper as job
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(job, "CHAIN_DIR", Path(tmp)), \
                 patch.object(job, "_telegram_send") as tg:
                out = job.run("2099-01-01", dry_run=False)
            self.assertTrue(out.get("missing_chain"))
            tg.assert_called_once()
            self.assertIn("期权链缺失", tg.call_args[0][0])  # SPEC-136 人话化


class TestAC6_ZeroPerturbation(unittest.TestCase):
    """SPEC-116 must not touch selector/catalog/gate files: working tree == HEAD."""

    FROZEN = [
        "strategy/selector.py",
        "strategy/catalog.py",
        "strategy/sleeve_governance.py",
        "strategy/cash_budget_governance.py",
        "strategy/bcd_filter.py",
        "strategy/bcd_stop.py",
    ]

    def test_frozen_files_unmodified(self):
        r = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--"] + self.FROZEN,
            capture_output=True, text=True, cwd=REPO,
        )
        dirty = [l for l in r.stdout.splitlines() if l.strip()]
        self.assertEqual(dirty, [], f"SPEC-116 must not modify: {dirty}")


if __name__ == "__main__":
    unittest.main()
