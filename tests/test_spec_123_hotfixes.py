"""SPEC-123 addendum hotfixes (2026-07-06 watch-day findings).

H-1  stale-spot pollution of moff fields: chain-parity spot primary,
     yahoo fallback + divergence guard; per-leg (put vs call) real-chain
     assertions, AC-3 style.
H-2  settling heartbeat path registry fix.
H-3  close-event ledger integrity: debit-branch sign guard, open linkage +
     strikes on close events, discretionary close reason.
Plus: governance false-halt regression (the dirty −85,100×2 realized rows
     halted D1 on garbage — corrected data must fire zero gates).
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import notify.q085_s2bps_paper as q

BACKUP_CHAIN_DIR = Path.home() / "backups/oldair/data/q041_chains"


def _synth_chain(S: float, sigma: float = 0.14, dte: int = 30):
    """Synthetic put+call chain around spot S, BS-consistent mids."""
    import pandas as pd
    from pricing import core
    rows = []
    T = dte / 365.0
    for k_off in (-300, -220, -150, -80, -30, 0, 30, 80, 150, 200, 260, 330):
        K = round(S + k_off, 0)
        for typ in ("PUT", "CALL"):
            px = (core.put_price if typ == "PUT" else core.call_price)(
                S, K, T, sigma, q._MIV_R, q=0.0)
            delta = core.put_delta(S, K, T, sigma, q._MIV_R) if typ == "PUT" \
                else core.call_delta(S, K, T, sigma, q._MIV_R)
            rows.append({"option_type": typ, "dte": dte, "expiry": "2026-08-05",
                         "strike": K, "mid": round(px, 2), "bid": round(px - 0.5, 2),
                         "ask": round(px + 0.5, 2), "delta": round(delta, 4),
                         "iv": sigma * 100})
    df = pd.DataFrame(rows)
    return df[df.option_type == "PUT"], df[df.option_type == "CALL"]


class TestH1ParitySpot(unittest.TestCase):
    def test_parity_recovers_true_spot(self):
        puts, calls = _synth_chain(7540.0)
        s = q.parity_spot(puts, calls)
        self.assertAlmostEqual(s, 7540.0, delta=2.0)

    def test_resolver_prefers_parity_on_divergence(self):
        """Negative control = the 2026-07-06 failure mode: yahoo cache two
        sessions stale (7483.24) vs chain truth (~7539.77)."""
        puts, calls = _synth_chain(7539.77)
        spot, source = q.resolve_pricing_spot(puts, calls, 7483.24)
        self.assertEqual(source, "chain_parity")
        self.assertAlmostEqual(spot, 7539.77, delta=2.0)

    def test_resolver_falls_back_to_yahoo(self):
        spot, source = q.resolve_pricing_spot(None, None, 7483.24)
        self.assertEqual((spot, source), (7483.24, "yahoo_eod"))

    def test_skew_row_records_spot_source(self):
        puts, calls = _synth_chain(7540.0)
        orig = q.SKEW_OUT
        q.SKEW_OUT = Path(tempfile.mkdtemp()) / "skew.jsonl"
        try:
            row = q.measure_skew(puts, 15.57, "2026-07-06", calls=calls,
                                 spx=7539.77, spx_source="chain_parity")
        finally:
            q.SKEW_OUT = orig
        self.assertEqual(row["spx_source"], "chain_parity")
        self.assertEqual(row["spx"], 7539.77)

    def test_stale_spot_reproduces_pollution_synthetic(self):
        """Direction lock: solving the SAME chain with a stale-low spot pushes
        put miv DOWN and call miv UP — the observed 7/6 signature (with the
        real 56-pt gap some puts stop solving entirely; 20 pts keeps every
        leg solvable while locking the direction)."""
        puts, calls = _synth_chain(7540.0)
        orig = q.SKEW_OUT
        q.SKEW_OUT = Path(tempfile.mkdtemp()) / "skew.jsonl"
        try:
            good = q.measure_skew(puts, 15.57, "d1", calls=calls, spx=7540.0)
            bad = q.measure_skew(puts, 15.57, "d2", calls=calls, spx=7520.0)
        finally:
            q.SKEW_OUT = orig
        self.assertLess(bad["d30_moff"], good["d30_moff"] - 0.4)     # puts crushed
        self.assertGreater(bad["c30_moff"], good["c30_moff"] + 0.4)  # calls inflated


def _latest_backup_chain():
    if not BACKUP_CHAIN_DIR.exists():
        return None
    days = sorted(d for d in BACKUP_CHAIN_DIR.iterdir()
                  if (d / "SPX.parquet").exists())
    return days[-1] if days else None


class TestH1RealChainPerLeg(unittest.TestCase):
    """AC-3-style real-chain verification, put and call legs INDEPENDENTLY
    (the addendum's ask: leg-type attribution locked by test)."""

    @unittest.skipUnless(_latest_backup_chain(), "no backup chain on this machine")
    def test_put_and_call_legs_solve_against_their_own_side(self):
        import pandas as pd
        from pricing import core
        day = _latest_backup_chain()
        date_str = day.name
        df = pd.read_parquet(day / "SPX.parquet")
        puts = df[(df.option_type.str.upper() == "PUT") & df.iv.notna() & (df.iv > 1)]
        calls = df[(df.option_type.str.upper() == "CALL") & df.iv.notna() & (df.iv > 1)]
        spot = q.parity_spot(puts, calls)
        self.assertIsNotNone(spot)

        orig = q.SKEW_OUT
        q.SKEW_OUT = Path(tempfile.mkdtemp()) / "skew.jsonl"
        try:
            row = q.measure_skew(puts, 16.0, date_str, calls=calls, spx=spot,
                                 spx_source="chain_parity")
        finally:
            q.SKEW_OUT = orig

        # independent per-leg references: same selection, solved directly
        def ref_miv(chain, target, is_call):
            b = chain[(chain.dte >= 25) & (chain.dte <= 35)].assign(
                ad=lambda x: x.delta.abs())
            rows3 = b.iloc[(b.ad - target).abs().argsort()[:3]]
            vals = [core.implied_vol(float(r.mid), spot, float(r.strike),
                                     float(r.dte) / 365.0, q._MIV_R,
                                     is_call=is_call) * 100
                    for _, r in rows3.iterrows()]
            return sum(vals) / len(vals)

        self.assertAlmostEqual(row["d30_miv"], ref_miv(puts, 0.30, False), delta=0.05)
        self.assertAlmostEqual(row["c30_miv"], ref_miv(calls, 0.30, True), delta=0.05)
        # put leg must NOT equal a call-side solve (leg-crossing lock)
        self.assertGreater(abs(row["d30_miv"] - ref_miv(calls, 0.30, True)), 0.3)


class TestH2Registry(unittest.TestCase):
    def test_settling_path_points_at_logs(self):
        reg = json.loads((REPO / "ops" / "heartbeat_registry.json").read_text())
        entry = next(j for j in reg["jobs"]
                     if j["label"] == "com.spxstrat.signal_settling")
        self.assertEqual(entry["freshness"]["path"], "logs/q019_settling_state.json")


class TestH3CloseIntegrity(unittest.TestCase):
    def _close(self, positions, legs_payload):
        from web.server import app
        events = []
        state = {"trade_id": positions[0]["trade_id"],
                 "strategy_key": "bull_call_diagonal", "underlying": "SPX"}
        with patch("strategy.state.read_state", return_value=state), \
             patch("strategy.state.read_all_positions",
                   return_value={"positions": positions}), \
             patch("strategy.state.close_position"), \
             patch("logs.trade_log_io.append_event", side_effect=events.append):
            res = app.test_client().post("/api/position/close",
                                         json={"legs": legs_payload,
                                               "exit_reason": "discretionary"})
        return res.get_json(), events

    def test_debit_close_sign_guard(self):
        """The 7/6 incident: entry −411 debit, UI submitted +440 → recorded
        −85,100. Guarded flow must yield +2,900 and a signed exit_premium."""
        pos = [{"trade_id": "t1", "actual_premium": -411.0, "contracts": 1,
                "strategy_key": "bull_call_diagonal", "short_strike": 7700,
                "long_strike": 7200, "expiry": "2026-07-17",
                "long_expiry": "2026-08-31", "account": "schwab"}]
        data, events = self._close(pos, [{"trade_id": "t1", "exit_premium": 440.0}])
        self.assertEqual(data["actual_pnl"], 2900.0)
        close_ev = next(e for e in events if e["event"] == "close")
        self.assertEqual(close_ev["exit_premium"], -440.0)

    def test_credit_close_unaffected(self):
        pos = [{"trade_id": "t2", "actual_premium": 10.0, "contracts": 1,
                "strategy_key": "bull_put_spread", "short_strike": 7400,
                "long_strike": 7300, "expiry": "2026-08-21", "account": "schwab"}]
        data, _ = self._close(pos, [{"trade_id": "t2", "exit_premium": 3.0}])
        self.assertEqual(data["actual_pnl"], 700.0)

    def test_close_event_selfdescribing(self):
        """H-3 (b)+(c): open linkage + strikes/contracts on the close event —
        the 7/6 closes could only be attributed via broker reverse-lookup."""
        pos = [{"trade_id": "t3", "actual_premium": -411.0, "contracts": 2,
                "strategy_key": "bull_call_diagonal", "short_strike": 7700,
                "long_strike": 7200, "expiry": "2026-07-17",
                "long_expiry": "2026-08-31", "account": "schwab"}]
        _, events = self._close(pos, [{"trade_id": "t3", "exit_premium": 440.0}])
        ev = next(e for e in events if e["event"] == "close")
        for k, v in (("open_id", "t3"), ("short_strike", 7700),
                     ("long_strike", 7200), ("expiry", "2026-07-17"),
                     ("long_expiry", "2026-08-31"), ("contracts", 2),
                     ("strategy_key", "bull_call_diagonal"),
                     ("entry_premium", -411.0)):
            self.assertEqual(ev.get(k), v, k)

    def test_dropdown_has_discretionary(self):
        src = (REPO / "web" / "templates" / "spx.html").read_text(encoding="utf-8")
        self.assertIn('value="discretionary"', src)
        self.assertIn('value="manual"', src)


class TestH4PushDelivery(unittest.TestCase):
    def _mock_resp(self, code, text="ok"):
        m = MagicMock()
        m.status_code = code
        m.text = text
        return m

    def test_html_400_falls_back_to_plain_text(self):
        """The 7/6 incident: HTML parse 400 must trigger a plain-text resend,
        and the fallback must be counted."""
        import notify.event_push as ep
        stats = Path(tempfile.mkdtemp()) / "push_stats.json"
        calls = []

        def post(url, json=None, timeout=None):
            calls.append(json)
            return self._mock_resp(400 if "parse_mode" in json else 200,
                                   "can't parse entities")

        with patch.object(ep, "PUSH_STATS", stats), \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t",
                                       "TELEGRAM_CHAT_ID": "c"}), \
             patch.object(ep.requests, "post", side_effect=post):
            ok = ep._send("D1 门: 和 $-175,460 < 0")
        self.assertTrue(ok)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("parse_mode", calls[1])   # plain-text retry
        recorded = json.loads(stats.read_text())
        day = next(iter(recorded))
        self.assertEqual(recorded[day]["fallback"], 1)

    def test_double_failure_counts_failed(self):
        import notify.event_push as ep
        stats = Path(tempfile.mkdtemp()) / "push_stats.json"
        with patch.object(ep, "PUSH_STATS", stats), \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t",
                                       "TELEGRAM_CHAT_ID": "c"}), \
             patch.object(ep.requests, "post",
                          return_value=self._mock_resp(400, "nope")):
            ok = ep._send("x")
        self.assertFalse(ok)
        recorded = json.loads(stats.read_text())
        self.assertEqual(recorded[next(iter(recorded))]["failed"], 1)

    def test_halt_message_html_safe(self):
        """The exact 7/6 killer: gate details with raw '<' must arrive
        escaped in the push copy."""
        import strategy.bcd_governance as gov
        msg = gov._halt_message(
            [{"gate": "G4_family_cum", "full_halt": True,
              "detail": "家族累计（实现+标记）$-175,460 < $-15,000"}], "2026-07-06")
        self.assertIn("&lt;", msg)
        self.assertNotIn(" < ", msg)

    def test_heartbeat_surfaces_failed_pushes(self):
        import scripts.ops_heartbeat as hb
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime(2026, 7, 7, 17, 30, tzinfo=ZoneInfo("America/New_York"))
        tmp = Path(tempfile.mkdtemp())
        (tmp / "logs").mkdir()
        (tmp / "logs" / "push_stats.json").write_text(json.dumps(
            {"2026-07-07": {"sent": 3, "fallback": 1, "failed": 2}}))
        (tmp / "registry.json").write_text('{"jobs": []}')
        with patch.object(hb, "ROOT", tmp), \
             patch.object(hb, "REGISTRY", tmp / "registry.json"):
            violations = hb.run(now, dry_run=True)
        self.assertTrue(any("推送两次发送均失败" in v for v in violations),
                        violations)


class TestGovernanceFalseHaltRegression(unittest.TestCase):
    def test_corrected_realized_fires_no_gates(self):
        """7/6 false halt: dirty realized −85,100×2 tripped G2+G4. With the
        corrected +2,900×2 and the real −5,260 marks, no gate may fire."""
        import strategy.bcd_governance as gov
        tmp = Path(tempfile.mkdtemp())
        orig = {n: getattr(gov, n) for n in
                ("STATE_PATH", "MARKS_PATH", "CLOSED_TRADES", "SHADOW_PATH")}
        gov.STATE_PATH = tmp / "s.json"
        gov.MARKS_PATH = tmp / "m.jsonl"
        gov.CLOSED_TRADES = tmp / "c.jsonl"
        gov.SHADOW_PATH = tmp / "sh.jsonl"
        try:
            with gov.CLOSED_TRADES.open("w") as f:
                for i in (1, 2):
                    f.write(json.dumps({
                        "trade_id": f"2026-06-05_bcd_{i:03d}",
                        "strategy_key": gov.BCD_KEY,
                        "closed_at": "2026-07-06", "realized_pnl": 2900.0}) + "\n")
            with patch.object(gov, "open_bcd_positions", return_value=[
                    {"id": "2026-06-03_bcd_001"}, {"id": "2026-06-03_bcd_002"}]):
                with gov.MARKS_PATH.open("w") as f:
                    for tid in ("2026-06-03_bcd_001", "2026-06-03_bcd_002"):
                        f.write(json.dumps({"date": "2026-07-06", "trade_id": tid,
                                            "pnl_mid": -2630.0}) + "\n")
                fired = gov.evaluate_gates("2026-07-06")
            self.assertEqual(fired, [])
        finally:
            for n, v in orig.items():
                setattr(gov, n, v)


if __name__ == "__main__":
    unittest.main()
