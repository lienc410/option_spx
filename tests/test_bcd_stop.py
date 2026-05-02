from __future__ import annotations

import unittest
from unittest.mock import patch

from backtest.engine import Position
from strategy.bcd_stop import BCD_STOP_DEFAULT, BCD_STOP_TIGHTER, bcd_debit_stop
from strategy.selector import StrategyName, StrategyParams


def _engine_debit_exit_reason(position: Position, pnl_ratio: float, params: StrategyParams):
    exit_reason = None
    is_credit = position.entry_value < 0
    if not is_credit:
        from strategy.selector import StrategyName
        from strategy.bcd_stop import bcd_debit_stop, log_bcd_stop_event, BCD_STOP_TIGHTER, BCD_STOP_DEFAULT
        is_bcd = (position.strategy == StrategyName.BULL_CALL_DIAGONAL)
        if is_bcd and params.bcd_stop_tightening_mode != "disabled":
            effective_stop = bcd_debit_stop(params.bcd_stop_tightening_mode)
            # shadow: log if -0.35 would trigger but -0.50 has not
            if params.bcd_stop_tightening_mode == "shadow":
                if BCD_STOP_TIGHTER >= pnl_ratio > BCD_STOP_DEFAULT:
                    log_bcd_stop_event(position.entry_date, pnl_ratio, "shadow", "engine")
            if pnl_ratio <= effective_stop:
                exit_reason = "stop_loss"
        elif pnl_ratio <= -0.50:
            exit_reason = "stop_loss"
    return exit_reason


def make_position(strategy: StrategyName) -> Position:
    return Position(
        strategy=strategy,
        underlying="SPX",
        entry_date="2026-05-02",
        entry_spx=5600.0,
        entry_vix=18.0,
        entry_sigma=0.18,
        entry_value=5.0,
    )


class BcdStopTests(unittest.TestCase):
    def test_disabled_returns_legacy_stop(self) -> None:
        self.assertEqual(bcd_debit_stop("disabled"), -0.50)

    def test_active_returns_tighter_stop(self) -> None:
        self.assertEqual(bcd_debit_stop("active"), -0.35)

    def test_shadow_returns_legacy_stop(self) -> None:
        self.assertEqual(bcd_debit_stop("shadow"), -0.50)

    def test_engine_bcd_stop_triggers_at_035_when_active(self) -> None:
        position = make_position(StrategyName.BULL_CALL_DIAGONAL)
        params = StrategyParams(bcd_stop_tightening_mode="active")
        self.assertEqual(_engine_debit_exit_reason(position, -0.36, params), "stop_loss")

    def test_engine_bcd_stop_does_not_trigger_at_040_when_disabled(self) -> None:
        position = make_position(StrategyName.BULL_CALL_DIAGONAL)
        params = StrategyParams(bcd_stop_tightening_mode="disabled")
        self.assertIsNone(_engine_debit_exit_reason(position, -0.40, params))

    def test_engine_non_bcd_debit_unaffected(self) -> None:
        position = make_position(StrategyName.BULL_CALL_SPREAD)
        params = StrategyParams(bcd_stop_tightening_mode="active")
        self.assertIsNone(_engine_debit_exit_reason(position, -0.36, params))

    def test_shadow_log_written_when_in_shadow_zone(self) -> None:
        position = make_position(StrategyName.BULL_CALL_DIAGONAL)
        params = StrategyParams(bcd_stop_tightening_mode="shadow")
        with patch("strategy.bcd_stop.log_bcd_stop_event") as mock_log:
            self.assertIsNone(_engine_debit_exit_reason(position, -0.38, params))
        mock_log.assert_called_once_with("2026-05-02", -0.38, "shadow", "engine")


if __name__ == "__main__":
    unittest.main()
