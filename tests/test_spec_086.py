import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from signals.intraday import IntradayStopTrigger, SpikeLevel, StopLevel, VixSpikeAlert
import notify.telegram_bot as bot_mod


def _push_body(call) -> str:
    """gateway.apush(bot, chat_id, category, about, title, body, ...) — body is
    the 6th positional arg. SPEC-126 migration: intraday_monitor now composes
    through the gateway, not raw bot.send_message."""
    if len(call.args) > 5:
        return str(call.args[5])
    return str(call.kwargs.get("body", ""))


def _es_state(**overrides):
    state = {
        "strategy_key": "es_short_put",
        "strategy": "/ES Short Put",
        "underlying": "/ES",
        "actual_premium": 10.5,
    }
    state.update(overrides)
    return state


def _positions_payload(mark: float, *, stale: bool = False, authenticated: bool = True):
    return {
        "configured": True,
        "authenticated": authenticated,
        "stale": stale,
        "positions": [
            {
                "symbol": "/ESM26 PUT 6000",
                "description": "/ES short put",
                "quantity": -1,
                "mark": mark,
            }
        ],
    }


def _flat_spike():
    return VixSpikeAlert(
        timestamp="2026-05-07 10:00",
        vix_open=18.0,
        vix_current=18.1,
        spike_pct=0.005,
        level=SpikeLevel.NONE,
        realtime=True,
    )


def _flat_stop():
    return IntradayStopTrigger(
        timestamp="2026-05-07 10:00",
        spx_open=7200.0,
        spx_current=7201.0,
        drop_pct=0.0001,
        level=StopLevel.NONE,
        realtime=True,
    )


class Spec086Tests(unittest.TestCase):
    def setUp(self) -> None:
        bot_mod._intraday_state["spike_level"] = SpikeLevel.NONE
        bot_mod._intraday_state["stop_level"] = StopLevel.NONE
        bot_mod._intraday_state["es_stop_level"] = bot_mod.EsStopLevel.NONE
        # SPEC-138 F1：隔离 ES-stop escalation 路径。mismatch/profit 一次性检查
        # 也会调 get_account_positions，会提前吃掉 side_effect 里的持仓 payload
        # （module-level state 跨测试残留，setUp 原本没重置这两个 flag）→ 第二
        # 次 intraday_monitor 拿不到持仓、escalation 断掉。置 True 跳过它们。
        bot_mod._intraday_state["mismatch_alerted"] = True
        bot_mod._intraday_state["profit_alerted"] = True

    @patch("schwab.client.get_account_positions")
    @patch("notify.telegram_bot.read_state")
    def test_ac1_trigger_when_mark_reaches_stop_mult(self, mock_read_state, mock_positions) -> None:
        # SPEC-121: canonical trigger moved 3x -> 10x (mark 106.0 / 10.5 = 10.1x)
        mock_read_state.return_value = _es_state(actual_premium=10.5)
        mock_positions.return_value = _positions_payload(106.0)

        result = bot_mod._check_es_credit_stop()

        self.assertEqual(result.level, bot_mod.EsStopLevel.TRIGGER)
        self.assertAlmostEqual(result.ratio, 106.0 / 10.5)
        self.assertIn("Credit Stop TRIGGERED", bot_mod._format_es_stop_alert(result))

    @patch("notify.telegram_bot.is_market_open", return_value=True)
    @patch("schwab.client.get_account_positions")
    @patch("notify.telegram_bot.read_state")
    @patch("notify.telegram_bot.get_spx_stop_from_quote", return_value=_flat_stop())
    @patch("notify.telegram_bot.get_vix_spike_from_quote", return_value=_flat_spike())
    @patch("notify.telegram_bot.get_spx_quote", return_value={"symbol": "$SPX"})
    @patch("notify.telegram_bot.get_vix_quote", return_value={"symbol": "$VIX"})
    def test_ac2_warning_then_trigger_escalates_once(
        self,
        _mock_vix_quote,
        _mock_spx_quote,
        _mock_vix_from_quote,
        _mock_spx_from_quote,
        mock_read_state,
        mock_positions,
        _mock_open,
    ) -> None:
        # SPEC-121: 21.2 = 2.02x (warning), 106.0 = 10.1x (trigger)
        # SPEC-138 F1 行为判定：生产已迁 gateway（SPEC-126）——intraday_monitor
        # 经 notify.gateway.apush 推送，不再直调 bot.send_message；SPEC-130 主机
        # guard 在传输层，测试态 delenv 后 raw send 零 await（正是 await_count=0
        # 的原因）。断言改测 gateway 契约（升级一次、文案正确），非削弱。
        mock_read_state.return_value = _es_state(actual_premium=10.5)
        mock_positions.side_effect = [_positions_payload(21.2), _positions_payload(106.0)]
        bot = AsyncMock()

        with patch("notify.gateway.apush", new_callable=AsyncMock) as mock_push:
            asyncio.run(bot_mod.intraday_monitor(bot, "chat"))
            asyncio.run(bot_mod.intraday_monitor(bot, "chat"))

        self.assertEqual(mock_push.await_count, 2)   # 升级一次：WARNING → TRIGGER
        first = _push_body(mock_push.await_args_list[0])
        second = _push_body(mock_push.await_args_list[1])
        self.assertIn("Stop Watch", first)
        self.assertIn("Credit Stop TRIGGERED", second)

    @patch("schwab.client.get_account_positions")
    @patch("notify.telegram_bot.read_state")
    def test_ac3_non_es_position_does_not_call_schwab(self, mock_read_state, mock_positions) -> None:
        mock_read_state.return_value = {"strategy_key": "bull_put_spread", "actual_premium": 10.5}

        result = bot_mod._check_es_credit_stop()

        self.assertEqual(result.level, bot_mod.EsStopLevel.NONE)
        mock_positions.assert_not_called()

    @patch("schwab.client.get_account_positions")
    @patch("notify.telegram_bot.read_state")
    def test_ac4_schwab_unavailable_fails_soft(self, mock_read_state, mock_positions) -> None:
        mock_read_state.return_value = _es_state()
        mock_positions.return_value = _positions_payload(32.0, stale=True)
        self.assertEqual(bot_mod._check_es_credit_stop().level, bot_mod.EsStopLevel.NONE)
        self.assertFalse(bot_mod._check_es_credit_stop().observed)

        mock_positions.return_value = _positions_payload(32.0, authenticated=False)
        self.assertEqual(bot_mod._check_es_credit_stop().level, bot_mod.EsStopLevel.NONE)

        mock_positions.side_effect = RuntimeError("schwab down")
        self.assertEqual(bot_mod._check_es_credit_stop().level, bot_mod.EsStopLevel.NONE)

    @patch("notify.telegram_bot.is_market_open", return_value=True)
    @patch("schwab.client.get_account_positions")
    @patch("notify.telegram_bot.read_state")
    @patch("notify.telegram_bot.get_spx_stop_from_quote", return_value=_flat_stop())
    @patch("notify.telegram_bot.get_vix_spike_from_quote", return_value=_flat_spike())
    @patch("notify.telegram_bot.get_spx_quote", return_value={"symbol": "$SPX"})
    @patch("notify.telegram_bot.get_vix_quote", return_value={"symbol": "$VIX"})
    def test_ac4_unavailable_does_not_send_false_clear_or_reset_state(
        self,
        _mock_vix_quote,
        _mock_spx_quote,
        _mock_vix_from_quote,
        _mock_spx_from_quote,
        mock_read_state,
        mock_positions,
        _mock_open,
    ) -> None:
        bot_mod._intraday_state["es_stop_level"] = bot_mod.EsStopLevel.WARNING
        mock_read_state.return_value = _es_state(actual_premium=10.0)
        mock_positions.return_value = _positions_payload(32.0, stale=True)
        bot = AsyncMock()

        asyncio.run(bot_mod.intraday_monitor(bot, "chat"))

        bot.send_message.assert_not_awaited()
        self.assertEqual(bot_mod._intraday_state["es_stop_level"], bot_mod.EsStopLevel.WARNING)

    @patch("notify.telegram_bot.is_market_open", return_value=True)
    @patch("schwab.client.get_account_positions")
    @patch("notify.telegram_bot.read_state")
    @patch("notify.telegram_bot.get_spx_stop_from_quote", return_value=_flat_stop())
    @patch("notify.telegram_bot.get_vix_spike_from_quote", return_value=_flat_spike())
    @patch("notify.telegram_bot.get_spx_quote", return_value={"symbol": "$SPX"})
    @patch("notify.telegram_bot.get_vix_quote", return_value={"symbol": "$VIX"})
    def test_ac5_clear_message_when_mark_falls_below_2x(
        self,
        _mock_vix_quote,
        _mock_spx_quote,
        _mock_vix_from_quote,
        _mock_spx_from_quote,
        mock_read_state,
        mock_positions,
        _mock_open,
    ) -> None:
        # SPEC-138 F1：同上——经 gateway.apush 断言（clear 消息 body 文案）。
        mock_read_state.return_value = _es_state(actual_premium=10.0)
        mock_positions.side_effect = [_positions_payload(22.0), _positions_payload(18.0)]
        bot = AsyncMock()

        with patch("notify.gateway.apush", new_callable=AsyncMock) as mock_push:
            asyncio.run(bot_mod.intraday_monitor(bot, "chat"))
            asyncio.run(bot_mod.intraday_monitor(bot, "chat"))

        self.assertEqual(mock_push.await_count, 2)
        cleared = _push_body(mock_push.await_args_list[1])
        self.assertIn("Stop watch cleared", cleared)
        self.assertIn("18.00", cleared)

    def test_ac7_reset_clears_es_stop_level(self) -> None:
        bot_mod._intraday_state["es_stop_level"] = bot_mod.EsStopLevel.TRIGGER
        bot_mod._reset_intraday_state()
        self.assertEqual(bot_mod._intraday_state["es_stop_level"], bot_mod.EsStopLevel.NONE)


if __name__ == "__main__":
    unittest.main()
