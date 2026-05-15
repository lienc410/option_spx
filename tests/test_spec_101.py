import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from zoneinfo import ZoneInfo


class Spec101HvLadderTests(unittest.TestCase):
    def test_hvlad_reproduces_q071_metrics(self):
        from research.strategies.ES_puts.backtest import run_phase2_hvlad

        result = run_phase2_hvlad(start_date="2000-01-01", end_date="2026-04-17")
        portfolio = result.portfolio_metrics
        worst = min(tr.pnl for tr in result.trades) / 500_000.0

        self.assertEqual(result.phase, "es_hv_ladder")
        self.assertEqual(len(result.trades), 146)
        self.assertAlmostEqual(portfolio["ann_return"], 0.0114, delta=0.0010)
        self.assertAlmostEqual(portfolio["daily_sharpe"], 0.34, delta=0.05)
        self.assertAlmostEqual(portfolio["max_drawdown"], -0.097, delta=0.015)
        self.assertAlmostEqual(portfolio["active_days_pct"], 0.214, delta=0.03)
        self.assertAlmostEqual(worst, -0.048, delta=0.015)
        self.assertEqual(result.bootstrap["sig_rate"], 1.0)

    def test_hvlad_api_shape(self):
        from web.server import app

        with app.test_client() as client:
            response = client.get("/api/es-backtest/hvlad?start=2000-01-01&end=2026-04-17")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["phase"], "es_hv_ladder")
        self.assertTrue(payload["paper_mode"])
        self.assertEqual(payload["vix_min_entry"], 22.0)
        self.assertIn("hvlad_metrics", payload)
        self.assertIn("v2f_baseline", payload)
        self.assertIn("hv_delta", payload)
        self.assertIn("paper_state", payload)

    def test_es_backtest_template_exposes_hv_ladder_tab(self):
        template = Path("web/templates/es_backtest.html").read_text(encoding="utf-8")
        self.assertIn('data-es-tab-btn="hvlad"', template)
        self.assertIn("/api/es-backtest/hvlad", template)
        self.assertIn("ES High-Vol Sell Put Ladder", template)
        self.assertIn("paper/shadow mode only", template)

    def test_paper_signal_writes_jsonl(self):
        from signals.trend import TrendSignal
        import notify.telegram_bot as bot

        now = datetime(2026, 5, 14, 11, 0, tzinfo=ZoneInfo("America/New_York"))
        vix_quote = {"last": 24.3, "quote_time": now.isoformat(timespec="seconds")}
        spx_quote = {"last": 5200.0, "quote_time": now.isoformat(timespec="seconds")}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "q071_hv_paper_trades.jsonl"
            bot._intraday_state["es_hv_signal_alerted_date"] = None
            bot._intraday_state["es_hv_stale_alerted_date"] = None
            with (
                patch("signals.trend.fetch_spx_history", return_value=object()),
                patch("signals.trend.get_current_trend", return_value=SimpleNamespace(signal=TrendSignal.BULLISH)),
            ):
                msg = bot._check_es_hv_ladder_paper_signal(
                    now=now,
                    vix_quote=vix_quote,
                    spx_quote=spx_quote,
                    paper_log_path=path,
                )

            self.assertIsNotNone(msg)
            self.assertIn("Paper Trade Signal", msg)
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["signal_date"], "2026-05-14")
            self.assertEqual(rows[0]["status"], "paper")
            self.assertGreater(rows[0]["est_premium"], 0)

    def test_stale_vix_guard_suppresses_paper_record(self):
        import notify.telegram_bot as bot

        now = datetime(2026, 5, 14, 11, 0, tzinfo=ZoneInfo("America/New_York"))
        stale_time = (now - timedelta(days=3)).isoformat(timespec="seconds")
        vix_quote = {"last": 24.3, "quote_time": stale_time}
        spx_quote = {"last": 5200.0, "quote_time": now.isoformat(timespec="seconds")}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "q071_hv_paper_trades.jsonl"
            bot._intraday_state["es_hv_signal_alerted_date"] = None
            bot._intraday_state["es_hv_stale_alerted_date"] = None
            msg = bot._check_es_hv_ladder_paper_signal(
                now=now,
                vix_quote=vix_quote,
                spx_quote=spx_quote,
                paper_log_path=path,
            )

            self.assertIsNotNone(msg)
            self.assertIn("VIX data unavailable/stale", msg)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
