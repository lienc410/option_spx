from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import logs.recommendation_log_io as rec_log_mod
import notify.telegram_bot as bot_mod
import web.server as server_mod
from web.server import app

from strategy.selector import StrategyName
from tests.test_telegram_bot import make_recommendation


class RecommendationLogIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.orig_log_file = rec_log_mod.RECOMMENDATION_LOG_FILE
        rec_log_mod.RECOMMENDATION_LOG_FILE = Path(self.tmpdir.name) / "recommendation_log.jsonl"

    def tearDown(self) -> None:
        rec_log_mod.RECOMMENDATION_LOG_FILE = self.orig_log_file

    def test_ac4_ac6_ac7_reduce_wait_serializes_stable_schema(self) -> None:
        rec = make_recommendation(
            strategy=StrategyName.REDUCE_WAIT,
            strategy_key="reduce_wait",
            position_action="WAIT",
        )
        rec.underlying = "—"
        rec.legs = []
        rec.vix_snapshot.vix3m = None

        rec_log_mod.append_recommendation_event(
            rec=rec,
            source="telegram_today",
            mode="intraday",
            timestamp="2026-04-18T09:35:02-04:00",
            params_hash="479998b833",
        )

        raw = rec_log_mod.RECOMMENDATION_LOG_FILE.read_text(encoding="utf-8").strip()
        row = json.loads(raw)
        self.assertEqual(row["strategy_key"], "reduce_wait")
        self.assertEqual(row["source"], "telegram_today")
        self.assertEqual(row["mode"], "intraday")
        self.assertEqual(row["legs"], [])
        self.assertIsNone(row["vix3m"])
        expected_keys = {
            "timestamp", "source", "mode", "date", "underlying", "position_action",
            "strategy", "strategy_key", "rationale", "macro_warning", "backwardation",
            "vix", "regime", "vix3m", "iv_rank", "iv_percentile", "iv_signal",
            "spx", "trend_signal", "legs", "params_hash",
        }
        self.assertEqual(set(row.keys()), expected_keys)


class RecommendationLogBotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.orig_log_file = rec_log_mod.RECOMMENDATION_LOG_FILE
        self.orig_results_cache = server_mod._RESULTS_DISK_CACHE
        rec_log_mod.RECOMMENDATION_LOG_FILE = Path(self.tmpdir.name) / "recommendation_log.jsonl"
        server_mod._RESULTS_DISK_CACHE = Path(self.tmpdir.name) / "backtest_results_cache.json"
        self.client = app.test_client()

    def tearDown(self) -> None:
        rec_log_mod.RECOMMENDATION_LOG_FILE = self.orig_log_file
        server_mod._RESULTS_DISK_CACHE = self.orig_results_cache
        bot_mod._morning_snapshot = None

    def _read_rows(self) -> list[dict]:
        path = rec_log_mod.RECOMMENDATION_LOG_FILE
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @patch("notify.telegram_bot.is_trading_day", return_value=True)
    @patch("notify.telegram_bot.get_recommendation")
    def test_ac1_scheduled_push_appends_log(self, mock_get_recommendation, _mock_day) -> None:
        mock_get_recommendation.return_value = make_recommendation()
        bot = AsyncMock()

        import asyncio

        asyncio.run(bot_mod.scheduled_push(bot, "chat"))
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "scheduled_push")
        self.assertEqual(rows[0]["mode"], "intraday")

    @patch("notify.telegram_bot.is_trading_day", return_value=True)
    @patch("notify.telegram_bot.get_recommendation")
    def test_ac2_scheduled_eod_push_appends_eod_log(self, mock_get_recommendation, _mock_day) -> None:
        mock_get_recommendation.return_value = make_recommendation()
        bot = AsyncMock()

        import asyncio

        asyncio.run(bot_mod.scheduled_eod_push(bot, "chat"))
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "scheduled_eod_push")
        self.assertEqual(rows[0]["mode"], "eod")

    @patch("notify.telegram_bot.get_recommendation")
    def test_ac3_cmd_today_appends_log(self, mock_get_recommendation) -> None:
        mock_get_recommendation.return_value = make_recommendation()
        message = AsyncMock()
        update = type("Update", (), {"message": message})()
        ctx = type("Context", (), {"args": []})()

        import asyncio

        asyncio.run(bot_mod.cmd_today(update, ctx))
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "telegram_today")
        self.assertEqual(rows[0]["mode"], "intraday")

    @patch("notify.telegram_bot.log.exception")
    @patch("notify.telegram_bot.append_recommendation_event", side_effect=RuntimeError("boom"))
    @patch("notify.telegram_bot.get_recommendation")
    def test_ac5_append_failure_does_not_block_today(self, mock_get_recommendation, _mock_append, mock_log_exception) -> None:
        mock_get_recommendation.return_value = make_recommendation()
        message = AsyncMock()
        update = type("Update", (), {"message": message})()
        ctx = type("Context", (), {"args": []})()

        import asyncio

        asyncio.run(bot_mod.cmd_today(update, ctx))
        self.assertGreaterEqual(message.reply_text.await_count, 2)
        mock_log_exception.assert_called()

    @patch("web.server._is_market_hours", return_value=False)
    @patch("strategy.selector.get_recommendation")
    def test_ac8_api_recommendation_does_not_append_log(self, mock_get_recommendation, _mock_hours) -> None:
        mock_get_recommendation.return_value = make_recommendation()
        res = self.client.get("/api/recommendation")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(rec_log_mod.RECOMMENDATION_LOG_FILE.exists())


if __name__ == "__main__":
    unittest.main()
