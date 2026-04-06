import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import logs.trade_log_io as trade_log_mod
import strategy.state as state_mod
import web.server as server_mod
from web.server import app


class StateAndApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.orig_state_file = state_mod.STATE_FILE
        self.orig_results_cache = server_mod._RESULTS_DISK_CACHE
        self.orig_trade_log_file = trade_log_mod.TRADE_LOG_FILE
        state_mod.STATE_FILE = os.path.join(self.tmpdir.name, "current_position.json")
        server_mod._RESULTS_DISK_CACHE = Path(self.tmpdir.name) / "backtest_results_cache.json"
        trade_log_mod.TRADE_LOG_FILE = Path(self.tmpdir.name) / "trade_log.jsonl"
        server_mod._backtest_cache.clear()
        server_mod._signals_cache.clear()
        self.client = app.test_client()

    def tearDown(self) -> None:
        state_mod.STATE_FILE = self.orig_state_file
        server_mod._RESULTS_DISK_CACHE = self.orig_results_cache
        trade_log_mod.TRADE_LOG_FILE = self.orig_trade_log_file

    def test_write_state_derives_strategy_key(self) -> None:
        state_mod.write_state("Bull Put Spread", "SPX")
        state = state_mod.read_state()
        self.assertIsNotNone(state)
        self.assertEqual(state["strategy_key"], "bull_put_spread")

    def test_read_state_backfills_legacy_record_without_strategy_key(self) -> None:
        with open(state_mod.STATE_FILE, "w") as fh:
            json.dump(
                {
                    "strategy": "Iron Condor",
                    "underlying": "SPX",
                    "opened_at": "2026-03-27",
                    "status": "open",
                    "roll_count": 0,
                    "rolled_at": None,
                    "notes": [],
                    "closed_at": None,
                    "close_note": None,
                },
                fh,
            )
        state = state_mod.read_state()
        self.assertIsNotNone(state)
        self.assertEqual(state["strategy_key"], "iron_condor")

    def test_api_position_returns_strategy_meta(self) -> None:
        state_mod.write_state("Bull Put Spread", "SPX")
        res = self.client.get("/api/position")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["open"])
        self.assertEqual(data["strategy_key"], "bull_put_spread")
        self.assertEqual(data["strategy_meta"]["name"], "Bull Put Spread")
        self.assertEqual(data["strategy_meta"]["emoji"], "💰")
        self.assertIn("schwab_live", data)

    def test_api_strategy_catalog_contains_matrix_and_manual_options(self) -> None:
        res = self.client.get("/api/strategy-catalog")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("strategies", data)
        self.assertIn("matrix", data)
        self.assertEqual(data["matrix"]["NORMAL"]["HIGH"]["BULLISH"], "bull_put_spread")
        manual_keys = {item["key"] for item in data["manual_entry_options"]}
        self.assertNotIn("reduce_wait", manual_keys)

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_api_recommendation_preserves_strategy_key(self, mock_get_recommendation, _mock_hours) -> None:
        from tests.test_strategy_unification import make_iv, make_trend, make_vix
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy

        mock_get_recommendation.return_value = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        res = self.client.get("/api/recommendation")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["strategy_key"], "bull_put_spread")
        self.assertEqual(data["strategy"], "Bull Put Spread")
        self.assertIn("canonical_strategy", data)
        self.assertIn("re_enable_hint", data)
        self.assertIn("overlay_mode", data)
        self.assertIn("shock_mode", data)

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_api_position_open_draft_returns_prefill_fields(self, mock_get_recommendation, _mock_hours) -> None:
        from tests.test_strategy_unification import make_iv, make_trend, make_vix
        from signals.iv_rank import IVSignal
        from signals.trend import TrendSignal
        from signals.vix_regime import Regime, Trend
        from strategy.selector import select_strategy

        mock_get_recommendation.return_value = select_strategy(
            make_vix(vix=19.0, regime=Regime.NORMAL, trend=Trend.FLAT),
            make_iv(signal=IVSignal.HIGH, iv_rank=62.0, iv_percentile=45.0, vix=19.0),
            make_trend(signal=TrendSignal.BULLISH),
        )
        res = self.client.get("/api/position/open-draft")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["strategy_key"], "bull_put_spread")
        self.assertIn("short_strike", data)
        self.assertIn("long_strike", data)
        self.assertIn("model_premium", data)
        self.assertFalse(data["paper_trade"])
        self.assertTrue(data["legs"])

    @patch("web.server._save_stats_disk")
    @patch("web.server._load_stats_disk", return_value={})
    @patch("backtest.engine.run_backtest")
    def test_api_backtest_stats_returns_avg_pnl(self, mock_run_backtest, _mock_disk, _mock_save) -> None:
        from backtest.engine import Trade
        from strategy.selector import StrategyName

        server_mod._backtest_cache.clear()

        trades = [
            Trade(
                strategy=StrategyName.BULL_PUT_SPREAD,
                underlying="SPX",
                entry_date="2026-01-02",
                exit_date="2026-01-10",
                exit_pnl=500.0,
            ),
            Trade(
                strategy=StrategyName.BULL_PUT_SPREAD,
                underlying="SPX",
                entry_date="2026-02-02",
                exit_date="2026-02-10",
                exit_pnl=-100.0,
            ),
        ]
        signals = [
            {"date": "2026-01-02", "regime": "NORMAL", "ivp": 62.0, "trend": "BULLISH"},
            {"date": "2026-02-02", "regime": "NORMAL", "ivp": 58.0, "trend": "BULLISH"},
        ]
        mock_run_backtest.return_value = (trades, {}, signals)

        res = self.client.get("/api/backtest/stats")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["all"]["bull_put_spread"]["n"], 2)
        self.assertEqual(data["all"]["bull_put_spread"]["avg_pnl"], 200)
        self.assertEqual(data["all_cell"]["NORMAL|NEUTRAL|BULLISH"]["avg_pnl"], 200)

    @patch("backtest.engine.run_backtest")
    def test_api_backtest_omits_signals_and_returns_metadata(self, mock_run_backtest) -> None:
        from backtest.engine import Trade
        from strategy.selector import StrategyName

        mock_run_backtest.return_value = (
            [
                Trade(
                    strategy=StrategyName.BULL_PUT_SPREAD,
                    underlying="SPX",
                    entry_date="2026-01-02",
                    exit_date="2026-01-10",
                    exit_pnl=500.0,
                )
            ],
            {"win_rate": 0.75, "total_trades": 1},
            [{"date": "2026-01-02", "regime": "NORMAL"}],
        )

        res = self.client.get("/api/backtest?start=2026-01-01")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertNotIn("signals", data)
        self.assertEqual(data["start_date"], "2026-01-01")
        self.assertIn("computed_at", data)
        self.assertIn("params_hash", data)

    @patch("backtest.engine.run_signals_only")
    def test_api_signals_history_returns_signals(self, mock_run_signals_only) -> None:
        mock_run_signals_only.return_value = [{"date": "2026-01-02", "regime": "NORMAL"}]
        res = self.client.get("/api/signals/history?start=2026-01-01")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["signals"][0]["regime"], "NORMAL")

    def test_api_backtest_latest_cached_returns_latest_entry(self) -> None:
        payload = {
            "old": {
                "date": "2026-04-05",
                "start_date": "2025-01-01",
                "params_hash": "aaaa",
                "computed_at": "2026-04-05T08:00:00",
                "payload": {"metrics": {"win_rate": 0.5}, "trades": []},
            },
            "new": {
                "date": "2026-04-05",
                "start_date": "2024-01-01",
                "params_hash": "bbbb",
                "computed_at": "2026-04-05T09:00:00",
                "payload": {"metrics": {"win_rate": 0.7}, "trades": [{"strategy": "X"}]},
            },
        }
        with open(server_mod._RESULTS_DISK_CACHE, "w") as fh:
            json.dump(payload, fh)

        res = self.client.get("/api/backtest/latest-cached")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["start_date"], "2024-01-01")
        self.assertEqual(data["params_hash"], "bbbb")
        self.assertEqual(data["metrics"]["win_rate"], 0.7)

    def test_position_open_close_roll_and_trade_log(self) -> None:
        open_res = self.client.post("/api/position/open", json={
            "strategy_key": "bull_put_spread",
            "underlying": "SPX",
            "short_strike": 5400,
            "long_strike": 5350,
            "expiry": "2026-05-05",
            "dte_at_entry": 30,
            "contracts": 2,
            "actual_premium": 3.15,
            "model_premium": 3.28,
            "entry_spx": 5482.5,
            "entry_vix": 19.2,
            "regime": "NORMAL",
            "iv_signal": "HIGH",
            "trend_signal": "BULLISH",
            "paper_trade": True,
            "note": "",
        })
        self.assertEqual(open_res.status_code, 200)
        trade_id = open_res.get_json()["trade_id"]
        state = state_mod.read_state()
        self.assertEqual(state["trade_id"], trade_id)
        self.assertEqual(state["short_strike"], 5400)
        self.assertTrue(state["paper_trade"])

        roll_res = self.client.post("/api/position/roll", json={
            "new_expiry": "2026-05-30",
            "new_short_strike": 5420,
            "new_long_strike": 5370,
            "roll_credit": 1.20,
            "note": "rolled",
        })
        self.assertEqual(roll_res.status_code, 200)
        state = state_mod.read_state()
        self.assertEqual(state["roll_count"], 1)
        self.assertEqual(state["short_strike"], 5420)

        close_res = self.client.post("/api/position/close", json={
            "exit_premium": 1.55,
            "exit_spx": 5510.0,
            "exit_reason": "50pct_profit",
            "note": "closed at target",
        })
        self.assertEqual(close_res.status_code, 200)
        self.assertAlmostEqual(close_res.get_json()["actual_pnl"], 320.0)
        self.assertIsNone(state_mod.read_state())

        log_res = self.client.get("/api/trade-log")
        self.assertEqual(log_res.status_code, 200)
        trades = log_res.get_json()["trades"]
        self.assertEqual(trades[0]["id"], trade_id)
        self.assertTrue(trades[0]["paper_trade"])
        self.assertEqual(trades[0]["open"]["short_strike"], 5400)
        self.assertEqual(trades[0]["rolls"][0]["new_short_strike"], 5420)
        self.assertEqual(trades[0]["close"]["actual_pnl"], 320.0)

    def test_correction_updates_state_and_resolved_log(self) -> None:
        open_res = self.client.post("/api/position/open", json={
            "strategy_key": "bull_put_spread",
            "underlying": "SPX",
            "short_strike": 5400,
            "long_strike": 5350,
            "expiry": "2026-05-05",
            "dte_at_entry": 30,
            "contracts": 2,
            "actual_premium": 3.15,
            "model_premium": 3.28,
            "entry_spx": 5482.5,
            "entry_vix": 19.2,
            "regime": "NORMAL",
            "iv_signal": "HIGH",
            "trend_signal": "BULLISH",
            "note": "",
        })
        trade_id = open_res.get_json()["trade_id"]
        corr_res = self.client.post("/api/position/correction", json={
            "trade_id": trade_id,
            "target_event": "open",
            "fields": {"actual_premium": 3.10, "contracts": 3},
            "reason": "mistyped premium at entry",
        })
        self.assertEqual(corr_res.status_code, 200)
        state = state_mod.read_state()
        self.assertEqual(state["contracts"], 3)
        self.assertEqual(state["actual_premium"], 3.10)

        resolved = self.client.get("/api/trade-log").get_json()
        self.assertEqual(resolved["raw_count"], 2)
        self.assertEqual(resolved["trades"][0]["open"]["contracts"], 3)
        self.assertFalse(resolved["trades"][0]["paper_trade"])
        self.assertEqual(resolved["trades"][0]["corrections"][0]["target_event"], "open")

        raw = self.client.get("/api/trade-log?raw=1").get_json()
        self.assertEqual(len(raw["raw"]), 2)
        self.assertEqual(raw["raw"][-1]["event"], "correction")

    def test_paper_trade_open_and_correction_flow(self) -> None:
        open_res = self.client.post("/api/position/open", json={
            "strategy_key": "bull_put_spread",
            "underlying": "SPX",
            "short_strike": 5400,
            "long_strike": 5350,
            "expiry": "2026-05-05",
            "dte_at_entry": 30,
            "contracts": 1,
            "actual_premium": 3.15,
            "paper_trade": True,
        })
        trade_id = open_res.get_json()["trade_id"]
        state = state_mod.read_state()
        self.assertTrue(state["paper_trade"])

        trade = self.client.get("/api/trade-log").get_json()["trades"][0]
        self.assertTrue(trade["paper_trade"])

        corr_res = self.client.post("/api/position/correction", json={
            "trade_id": trade_id,
            "target_event": "open",
            "fields": {"paper_trade": False},
            "reason": "should count as live",
        })
        self.assertEqual(corr_res.status_code, 200)
        state = state_mod.read_state()
        self.assertFalse(state["paper_trade"])
        trade = self.client.get("/api/trade-log").get_json()["trades"][0]
        self.assertFalse(trade["paper_trade"])

    def test_void_marks_trade_and_clears_open_state(self) -> None:
        open_res = self.client.post("/api/position/open", json={
            "strategy_key": "bull_put_spread",
            "underlying": "SPX",
            "short_strike": 5400,
            "long_strike": 5350,
            "expiry": "2026-05-05",
            "dte_at_entry": 30,
            "contracts": 2,
            "actual_premium": 3.15,
        })
        trade_id = open_res.get_json()["trade_id"]
        void_res = self.client.post("/api/position/void", json={
            "trade_id": trade_id,
            "reason": "duplicate entry",
        })
        self.assertEqual(void_res.status_code, 200)
        self.assertTrue(void_res.get_json()["state_cleared"])
        self.assertIsNone(state_mod.read_state())

        resolved = self.client.get("/api/trade-log").get_json()["trades"][0]
        self.assertTrue(resolved["voided"])

        again = self.client.post("/api/position/void", json={
            "trade_id": trade_id,
            "reason": "duplicate entry",
        })
        self.assertEqual(again.status_code, 400)

    def test_open_correction_auto_recalculates_closed_trade_pnl(self) -> None:
        open_res = self.client.post("/api/position/open", json={
            "strategy_key": "bull_put_spread",
            "underlying": "SPX",
            "short_strike": 5400,
            "long_strike": 5350,
            "expiry": "2026-05-05",
            "dte_at_entry": 30,
            "contracts": 2,
            "actual_premium": 3.15,
        })
        trade_id = open_res.get_json()["trade_id"]
        self.client.post("/api/position/close", json={
            "exit_premium": 1.55,
            "exit_spx": 5510.0,
            "exit_reason": "50pct_profit",
            "note": "",
        })
        corr_res = self.client.post("/api/position/correction", json={
            "trade_id": trade_id,
            "target_event": "open",
            "fields": {"actual_premium": 3.05},
            "reason": "mistyped premium at entry",
        })
        self.assertEqual(corr_res.status_code, 200)
        self.assertTrue(corr_res.get_json()["auto_recalculated"])
        trade = self.client.get("/api/trade-log").get_json()["trades"][0]
        self.assertEqual(trade["close"]["actual_pnl"], 300.0)

    @patch("schwab.client.is_configured", return_value=False)
    @patch("schwab.auth.is_configured", return_value=False)
    def test_schwab_status_and_balances_gracefully_degrade_when_unconfigured(self, _mock_auth, _mock_client) -> None:
        status = self.client.get("/api/schwab/status")
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.get_json()["configured"])

        balances = self.client.get("/api/schwab/balances")
        self.assertEqual(balances.status_code, 200)
        self.assertFalse(balances.get_json()["configured"])


if __name__ == "__main__":
    unittest.main()
