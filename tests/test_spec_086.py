import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from signals.intraday import IntradayStopTrigger, SpikeLevel, StopLevel, VixSpikeAlert
import notify.telegram_bot as bot_mod


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
        mock_read_state.return_value = _es_state(actual_premium=10.5)
        mock_positions.side_effect = [_positions_payload(21.2), _positions_payload(106.0)]
        bot = AsyncMock()

        asyncio.run(bot_mod.intraday_monitor(bot, "chat"))
        asyncio.run(bot_mod.intraday_monitor(bot, "chat"))

        self.assertEqual(bot.send_message.await_count, 2)
        first = bot.send_message.await_args_list[0].kwargs["text"]
        second = bot.send_message.await_args_list[1].kwargs["text"]
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
        mock_read_state.return_value = _es_state(actual_premium=10.0)
        mock_positions.side_effect = [_positions_payload(22.0), _positions_payload(18.0)]
        bot = AsyncMock()

        asyncio.run(bot_mod.intraday_monitor(bot, "chat"))
        asyncio.run(bot_mod.intraday_monitor(bot, "chat"))

        self.assertEqual(bot.send_message.await_count, 2)
        cleared = bot.send_message.await_args_list[1].kwargs["text"]
        self.assertIn("Stop watch cleared", cleared)
        self.assertIn("18.00", cleared)

    def test_ac7_reset_clears_es_stop_level(self) -> None:
        bot_mod._intraday_state["es_stop_level"] = bot_mod.EsStopLevel.TRIGGER
        bot_mod._reset_intraday_state()
        self.assertEqual(bot_mod._intraday_state["es_stop_level"], bot_mod.EsStopLevel.NONE)


if __name__ == "__main__":
    unittest.main()
