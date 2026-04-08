import unittest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from signals.iv_rank import IVSignal, IVSnapshot
from signals.trend import TrendSignal, TrendSnapshot
from signals.vix_regime import Regime, Trend, VixSnapshot
import notify.telegram_bot as bot_mod
from signals.intraday import IntradayStopTrigger, SpikeLevel, StopLevel, VixSpikeAlert
from strategy.selector import Leg, Recommendation, StrategyName


def make_recommendation(
    *,
    strategy: StrategyName = StrategyName.BULL_PUT_SPREAD_HV,
    strategy_key: str = "bull_put_spread_hv",
    position_action: str = "OPEN",
    vix_trend: Trend = Trend.FLAT,
    backwardation: bool = False,
) -> Recommendation:
    return Recommendation(
        strategy=strategy,
        strategy_key=strategy_key,
        underlying="SPX",
        legs=[
            Leg(action="SELL", option="PUT", dte=21, delta=-0.20, note="short put"),
            Leg(action="BUY", option="PUT", dte=21, delta=-0.10, note="long put"),
        ],
        max_risk="$500",
        target_return="50% of credit",
        size_rule="1-lot",
        roll_rule="21 DTE",
        rationale="Test rationale",
        position_action=position_action,
        vix_snapshot=VixSnapshot(
            date="2026-04-07",
            vix=24.83,
            regime=Regime.HIGH_VOL,
            trend=vix_trend,
            vix_5d_avg=23.1,
            vix_5d_ago=22.4,
            transition_warning=False,
            vix3m=26.40,
            backwardation=backwardation,
        ),
        iv_snapshot=IVSnapshot(
            date="2026-04-07",
            vix=24.83,
            iv_rank=62.0,
            iv_percentile=58.0,
            iv_signal=IVSignal.HIGH,
            iv_52w_high=40.0,
            iv_52w_low=12.0,
        ),
        trend_snapshot=TrendSnapshot(
            date="2026-04-07",
            spx=5200.0,
            ma20=5190.0,
            ma50=5138.0,
            ma_gap_pct=0.012,
            signal=TrendSignal.NEUTRAL,
            above_200=True,
        ),
        macro_warning=False,
        backwardation=backwardation,
        canonical_strategy="Bull Put Spread (High Vol)",
        re_enable_hint="Wait for VIX to stop rising",
    )


class TelegramBotSpec041Tests(unittest.TestCase):
    def tearDown(self) -> None:
        bot_mod._morning_snapshot = None

    def test_format_eod_snapshot_signal_changed_and_position_line(self) -> None:
        rec = make_recommendation(vix_trend=Trend.FLAT)
        morning = {
            "strategy_key": "reduce_wait",
            "position_action": "WAIT",
            "date": "2026-04-07",
            "vix_trend": "RISING",
        }
        state = {
            "strategy": "Bull Put Spread (High Vol)",
            "underlying": "SPX",
            "expiry": "2099-04-28",
        }
        text = bot_mod._format_eod_snapshot(rec, morning, state)
        self.assertIn("⚠️ Signal changed from morning:", text)
        self.assertIn("Morning → REDUCE_WAIT", text)
        self.assertIn("EOD     → OPEN BULL_PUT_SPREAD_HV", text)
        self.assertIn("📋 Open Position: Bull Put Spread (High Vol) | SPX |", text)
        self.assertIn("SPX options tradeable until 4:15pm ET", text)

    def test_format_eod_snapshot_same_signal_and_unavailable(self) -> None:
        rec = make_recommendation()
        same = {
            "strategy_key": rec.strategy_key,
            "position_action": rec.position_action,
            "date": rec.vix_snapshot.date,
            "vix_trend": rec.vix_snapshot.trend.value,
        }
        self.assertIn("✅ Signal confirmed", bot_mod._format_eod_snapshot(rec, same, None))
        self.assertIn("ℹ️ Morning snapshot unavailable", bot_mod._format_eod_snapshot(rec, None, None))

    @patch("notify.telegram_bot.is_trading_day", return_value=True)
    @patch("notify.telegram_bot.get_recommendation")
    def test_scheduled_push_and_eod_push_manage_morning_snapshot(self, mock_get_recommendation, _mock_trading_day) -> None:
        morning_rec = make_recommendation(vix_trend=Trend.RISING)
        eod_rec = make_recommendation(vix_trend=Trend.FLAT, backwardation=True)
        mock_get_recommendation.side_effect = [morning_rec, eod_rec]
        bot = AsyncMock()

        import asyncio

        asyncio.run(bot_mod.scheduled_push(bot, "chat"))
        self.assertEqual(bot_mod._morning_snapshot["strategy_key"], morning_rec.strategy_key)
        asyncio.run(bot_mod.scheduled_eod_push(bot, "chat"))
        self.assertEqual(bot.send_message.await_count, 2)
        sent_text = bot.send_message.await_args_list[-1].kwargs["text"]
        self.assertIn("🌙 <b>EOD Signal Snapshot", sent_text)
        self.assertIn("Term struct", sent_text)

    def test_reset_intraday_state_clears_morning_snapshot(self) -> None:
        bot_mod._morning_snapshot = {"strategy_key": "bull_put_spread_hv"}
        bot_mod._reset_intraday_state()
        self.assertIsNone(bot_mod._morning_snapshot)


class TelegramBotSpec046Tests(unittest.TestCase):
    def setUp(self) -> None:
        bot_mod._intraday_state["spike_level"] = SpikeLevel.NONE
        bot_mod._intraday_state["stop_level"] = StopLevel.NONE

    @patch("notify.telegram_bot.is_market_open", return_value=True)
    @patch("notify.telegram_bot.get_spx_stop")
    @patch("notify.telegram_bot.get_vix_spike")
    @patch("notify.telegram_bot.get_spx_stop_from_quote")
    @patch("notify.telegram_bot.get_vix_spike_from_quote")
    @patch("notify.telegram_bot.get_spx_quote")
    @patch("notify.telegram_bot.get_vix_quote")
    def test_intraday_monitor_prefers_schwab_quotes(
        self,
        mock_get_vix_quote,
        mock_get_spx_quote,
        mock_vix_from_quote,
        mock_spx_from_quote,
        mock_get_vix_spike,
        mock_get_spx_stop,
        _mock_open,
    ) -> None:
        mock_get_vix_quote.return_value = {"symbol": "$VIX"}
        mock_get_spx_quote.return_value = {"symbol": "$SPX"}
        mock_vix_from_quote.return_value = VixSpikeAlert(
            timestamp="2026-04-07 13:55",
            vix_open=25.0,
            vix_current=27.5,
            spike_pct=0.10,
            level=SpikeLevel.WARNING,
            realtime=True,
        )
        mock_spx_from_quote.return_value = IntradayStopTrigger(
            timestamp="2026-04-07 13:55",
            spx_open=5300.0,
            spx_current=5290.0,
            drop_pct=-0.0019,
            level=StopLevel.NONE,
            realtime=True,
        )
        bot = AsyncMock()

        import asyncio

        asyncio.run(bot_mod.intraday_monitor(bot, "chat"))
        mock_get_vix_quote.assert_called_once()
        mock_get_spx_quote.assert_called_once()
        mock_vix_from_quote.assert_called_once()
        mock_spx_from_quote.assert_called_once()
        mock_get_vix_spike.assert_not_called()
        mock_get_spx_stop.assert_not_called()
        self.assertEqual(bot.send_message.await_count, 1)

    @patch("notify.telegram_bot.is_market_open", return_value=True)
    @patch("notify.telegram_bot.get_spx_stop")
    @patch("notify.telegram_bot.get_vix_spike")
    @patch("notify.telegram_bot.get_spx_quote", side_effect=RuntimeError("no quote"))
    @patch("notify.telegram_bot.get_vix_quote", side_effect=RuntimeError("no quote"))
    def test_intraday_monitor_falls_back_to_yahoo(
        self,
        _mock_get_vix_quote,
        _mock_get_spx_quote,
        mock_get_vix_spike,
        mock_get_spx_stop,
        _mock_open,
    ) -> None:
        mock_get_vix_spike.return_value = VixSpikeAlert(
            timestamp="2026-04-07 13:55",
            vix_open=25.0,
            vix_current=27.5,
            spike_pct=0.10,
            level=SpikeLevel.WARNING,
        )
        mock_get_spx_stop.return_value = IntradayStopTrigger(
            timestamp="2026-04-07 13:55",
            spx_open=5300.0,
            spx_current=5290.0,
            drop_pct=-0.0019,
            level=StopLevel.NONE,
        )
        bot = AsyncMock()

        import asyncio

        asyncio.run(bot_mod.intraday_monitor(bot, "chat"))
        mock_get_vix_spike.assert_called_once_with(interval="5m")
        mock_get_spx_stop.assert_called_once_with(interval="5m")
        self.assertEqual(bot.send_message.await_count, 1)

    @patch("notify.telegram_bot.datetime")
    def test_format_spike_alert_labels_stale_quotes(self, mock_datetime) -> None:
        mock_datetime.now.return_value = datetime(2026, 4, 7, 15, 12, tzinfo=bot_mod.ET)
        mock_datetime.strptime.side_effect = datetime.strptime
        spike = VixSpikeAlert(
            timestamp="2026-04-07 13:55",
            vix_open=25.0,
            vix_current=27.5,
            spike_pct=0.10,
            level=SpikeLevel.WARNING,
            realtime=True,
        )
        text = bot_mod._format_spike_alert(spike)
        self.assertIn("sent 2026-04-07 15:12", text)
        self.assertIn("delayed 77m", text)

    def test_format_spike_alert_labels_non_realtime_quotes(self) -> None:
        spike = VixSpikeAlert(
            timestamp="2026-04-07 13:55",
            vix_open=25.0,
            vix_current=27.5,
            spike_pct=0.10,
            level=SpikeLevel.WARNING,
            realtime=False,
        )
        text = bot_mod._format_spike_alert(spike)
        self.assertIn("delayed — non-realtime quote", text)


if __name__ == "__main__":
    unittest.main()
