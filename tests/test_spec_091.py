from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import production.vix_settling as settling_mod
from web.server import app


def _dt(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=settling_mod.ET)


def _frame(day: date, vals: list[tuple[int, float]]) -> pd.DataFrame:
    idx = [datetime(day.year, day.month, day.day, hour, 30) for hour, _ in vals]
    df = pd.DataFrame({"vix": [v for _, v in vals]}, index=idx)
    df["date"] = pd.Timestamp(day)
    return df


class Spec091Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.client = app.test_client()

        self.orig_state_file = settling_mod.STATE_FILE
        self.orig_log_file = settling_mod.LOG_FILE
        settling_mod.STATE_FILE = Path(self.tmpdir.name) / "q019_settling_state.json"
        settling_mod.LOG_FILE = Path(self.tmpdir.name) / "q019_settling_log.jsonl"

    def tearDown(self) -> None:
        settling_mod.STATE_FILE = self.orig_state_file
        settling_mod.LOG_FILE = self.orig_log_file

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_ac1_signal1_route_shape_unchanged(self, mock_get_recommendation, _mock_hours) -> None:
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy
        from tests.test_strategy_unification import make_iv, make_trend, make_vix

        mock_get_recommendation.return_value = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )

        res = self.client.get("/api/recommendation")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertNotIn("signal2", json.dumps(data))
        self.assertNotIn("settling", json.dumps(data).lower())

    def test_ac2_stable_and_timeout_logic(self) -> None:
        day = date(2026, 5, 11)
        stable_frame = _frame(day, [(9, 24.3), (10, 24.0)])
        timeout_frame = _frame(day, [(9, 24.3), (10, 23.4), (11, 22.7), (12, 23.5)])

        status, cur, prev, delta, elapsed, note = settling_mod._evaluate_settling(_dt(2026, 5, 11, 10, 30), stable_frame)
        self.assertEqual(status, "stable")
        self.assertEqual(cur, 24.0)
        self.assertEqual(prev, 24.3)
        self.assertAlmostEqual(delta, 0.3)
        self.assertEqual(note, None)
        self.assertEqual(elapsed, 60)

        status, cur, prev, delta, elapsed, note = settling_mod._evaluate_settling(_dt(2026, 5, 11, 12, 30), timeout_frame)
        self.assertEqual(status, "timeout")
        self.assertEqual(cur, 23.5)
        self.assertEqual(prev, 22.7)
        self.assertAlmostEqual(delta, 0.8)
        self.assertEqual(elapsed, 180)
        self.assertEqual(note, None)

    def test_ac3_ac4_ac5_message_formats(self) -> None:
        sig1 = settling_mod.SignalSummary("bull_put_spread", "Bull Put Spread", "OPEN", 24.3)
        sig2_changed = settling_mod.SignalSummary("iron_condor", "Iron Condor", "OPEN", 21.8)
        sig2_same = settling_mod.SignalSummary("bull_put_spread", "Bull Put Spread", "OPEN", 22.1)

        diff_msg = settling_mod._diff_message(sig1, sig2_changed, "stable", 47)
        self.assertIn("VIX 稳定信号更新", diff_msg)
        self.assertIn("开盘时 VIX 24.3", diff_msg)
        self.assertIn("推荐: BPS", diff_msg)
        self.assertIn("推荐: IC", diff_msg)

        same_msg = settling_mod._same_message(sig1, sig2_same, "stable", 47)
        self.assertIn("VIX 稳定确认", same_msg)
        self.assertIn("维持不变", same_msg)

        timeout_msg = settling_mod._same_message(sig1, sig2_same, "timeout", 180)
        self.assertIn("timeout 12:30 ET", timeout_msg)
        self.assertIn("按 12:30 当前值", timeout_msg)

    def test_ac6_web_route_and_home_panel(self) -> None:
        payload = {
            "date": "2026-05-11",
            "status": "waiting",
            "threshold": 0.5,
            "elapsed_min": 30,
            "current_vix": 24.3,
            "prev_vix": 25.1,
            "delta_vix": 0.8,
            "signal1": None,
            "signal2": None,
            "changed": None,
            "note": "awaiting_first_stable_check",
        }
        settling_mod.STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")

        with patch.object(settling_mod, "_now_et", return_value=_dt(2026, 5, 11, 10, 0)):
            res = self.client.get("/api/recommendation/settling")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "waiting")

        page = self.client.get("/")
        text = page.get_data(as_text=True)
        self.assertIn("Signal 2 · Settled VIX", text)
        self.assertIn("Forward-tracking observation only", text)

    def test_ac7_log_written_and_state_finalized(self) -> None:
        day = date(2026, 5, 11)
        sig1 = settling_mod.SignalSummary("bull_put_spread", "Bull Put Spread", "OPEN", 24.3)
        sig2 = settling_mod.SignalSummary("iron_condor", "Iron Condor", "OPEN", 21.8)
        frame = _frame(day, [(9, 24.3), (10, 24.0)])

        with patch.object(settling_mod, "_fetch_hourly_vix_frame", return_value=frame), \
             patch.object(settling_mod, "_build_signal1", return_value=sig1), \
             patch.object(settling_mod, "_build_signal2", return_value=sig2), \
             patch.object(settling_mod, "_send_telegram_message", return_value=True):
            rc = settling_mod.run_settling_process(
                now_fn=lambda: _dt(2026, 5, 11, 10, 30),
                sleep_fn=lambda _s: None,
                send_telegram=False,
                verbose=False,
            )

        self.assertEqual(rc, 0)
        state = json.loads(settling_mod.STATE_FILE.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "stable")
        self.assertTrue(state["changed"])
        log_rows = settling_mod.LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(log_rows), 1)
        row = json.loads(log_rows[0])
        self.assertEqual(row["rec_signal1"], "bull_put_spread")
        self.assertEqual(row["rec_signal2"], "iron_condor")
        self.assertEqual(row["settling_status"], "stable")

    def test_ac8_non_trading_day_guard(self) -> None:
        rc = settling_mod.run_settling_process(
            now_fn=lambda: _dt(2026, 5, 9, 9, 30),
            sleep_fn=lambda _s: None,
            send_telegram=False,
            verbose=False,
        )
        self.assertEqual(rc, 0)
        state = json.loads(settling_mod.STATE_FILE.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "skipped")

    def test_read_settling_state_fails_soft_when_missing(self) -> None:
        with patch.object(settling_mod, "_now_et", return_value=_dt(2026, 5, 11, 10, 0)):
            payload = settling_mod.read_settling_state()
        self.assertEqual(payload["status"], "unavailable")

    def test_spec117_skipped_state_schema_complete(self) -> None:
        """SPEC-117.2 regression guard: the skipped-branch constructor must supply
        every SettlingState field (2026-07 outage: signal1_captured_at was added
        as a required field but the skipped branch wasn't updated → nightly
        TypeError). Assert the written state carries the full dataclass schema."""
        import dataclasses
        rc = settling_mod.run_settling_process(
            now_fn=lambda: _dt(2026, 5, 9, 9, 30),   # Saturday → skipped branch
            sleep_fn=lambda _s: None,
            send_telegram=False,
            verbose=False,
        )
        self.assertEqual(rc, 0)
        state = json.loads(settling_mod.STATE_FILE.read_text(encoding="utf-8"))
        for f in dataclasses.fields(settling_mod.SettlingState):
            self.assertIn(f.name, state, f"skipped-state missing field {f.name}")


if __name__ == "__main__":
    unittest.main()
