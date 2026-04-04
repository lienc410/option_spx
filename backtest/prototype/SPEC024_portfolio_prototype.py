"""
Portfolio Tracker — SPEC-024

Tracks daily net equity, unrealized P&L delta, and BP utilization
across all open positions. Produces DailyPortfolioRow records for
downstream metrics computation.

Design:
- PortfolioTracker is instantiated once per backtest run
- Call update_day() after each daily engine loop iteration
- get_rows() returns a list of DailyPortfolioRow for metrics computation

DailyPortfolioRow fields (17 total):
  date, start_equity, end_equity, daily_return_gross, daily_return_net,
  realized_pnl, unrealized_pnl_delta, total_pnl, bp_used, bp_headroom,
  short_gamma_count, open_positions, regime, vix, cumulative_equity,
  drawdown, experiment_id
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DailyPortfolioRow:
    """One row per trading day in the backtest."""
    date:                 str
    start_equity:         float    # equity at start of day (= prev day end_equity)
    end_equity:           float    # equity at end of day after realized + unrealized delta
    daily_return_gross:   float    # (end_equity - start_equity) / start_equity (no cost adj)
    daily_return_net:     float    # same as gross in Precision B (no commissions modeled)
    realized_pnl:         float    # P&L from trades closed today
    unrealized_pnl_delta: float    # change in mark-to-market value of open positions today
    total_pnl:            float    # realized_pnl + unrealized_pnl_delta
    bp_used:              float    # total BP consumed today (USD)
    bp_headroom:          float    # bp_ceiling * account_size - bp_used (USD)
    short_gamma_count:    int      # number of open short-gamma positions today
    open_positions:       int      # total open positions today
    regime:               str      # VIX regime label (LOW_VOL / NORMAL / HIGH_VOL / etc.)
    vix:                  float    # VIX close for the day
    cumulative_equity:    float    # running cumulative equity from initial_equity
    drawdown:             float    # (cumulative_equity - peak_equity) / peak_equity  ≤ 0
    experiment_id:        str      # links this row to the experiment registry


class PortfolioTracker:
    """
    Accumulates daily portfolio state for a backtest run.

    Usage:
        tracker = PortfolioTracker(initial_equity=100_000, experiment_id="EXP-...")
        for each day in engine loop:
            tracker.update_day(date, realized_pnl, open_positions, bp_used, ...)
        rows = tracker.get_rows()
    """

    def __init__(
        self,
        initial_equity: float,
        experiment_id: str,
        account_size: float | None = None,
    ) -> None:
        self.initial_equity = initial_equity
        self.experiment_id = experiment_id
        self.account_size = account_size or initial_equity

        self._rows: list[DailyPortfolioRow] = []
        self._peak_equity = initial_equity
        self._prev_marks: dict[str, float] = {}   # position_id → mark value yesterday
        self._cumulative_equity = initial_equity

    def update_day(
        self,
        *,
        date: str,
        realized_pnl: float,
        open_position_marks: dict[str, float],   # position_id → current mark value
        bp_used: float,
        bp_ceiling_usd: float,
        short_gamma_count: int,
        open_positions: int,
        regime: str,
        vix: float,
    ) -> DailyPortfolioRow:
        """
        Record one day of portfolio state. Call once per day after engine logic.

        Args:
            realized_pnl:         P&L from closed trades today.
            open_position_marks:  Current mark-to-market values of all still-open positions.
                                  Keys are unique position identifiers (e.g. entry_date + strategy).
            bp_used:              Total buying power consumed today.
            bp_ceiling_usd:       BP ceiling for today in USD (ceiling_pct × account_size).
            short_gamma_count:    Number of open short-gamma positions.
            open_positions:       Number of open positions.
            regime:               Current VIX regime string.
            vix:                  Today's VIX close.
        """
        # Compute unrealized P&L delta = change in total mark value from yesterday
        curr_total_mark = sum(open_position_marks.values())
        prev_total_mark = sum(self._prev_marks.get(pid, v) for pid, v in open_position_marks.items())
        # For newly opened positions, prev mark is 0 (they weren't in portfolio yesterday)
        new_positions = {
            pid: mark for pid, mark in open_position_marks.items()
            if pid not in self._prev_marks
        }
        prev_total_mark = (
            sum(self._prev_marks.get(pid, 0.0) for pid in open_position_marks)
        )
        unrealized_pnl_delta = curr_total_mark - prev_total_mark

        total_pnl = realized_pnl + unrealized_pnl_delta

        start_equity = self._cumulative_equity
        end_equity = start_equity + total_pnl
        self._cumulative_equity = end_equity

        daily_return = (end_equity - start_equity) / start_equity if start_equity != 0 else 0.0

        # Update peak for drawdown calculation
        if end_equity > self._peak_equity:
            self._peak_equity = end_equity

        drawdown = (
            (end_equity - self._peak_equity) / self._peak_equity
            if self._peak_equity != 0 else 0.0
        )

        bp_headroom = bp_ceiling_usd - bp_used

        row = DailyPortfolioRow(
            date=date,
            start_equity=start_equity,
            end_equity=end_equity,
            daily_return_gross=daily_return,
            daily_return_net=daily_return,        # Precision B: no commission adjustment
            realized_pnl=realized_pnl,
            unrealized_pnl_delta=unrealized_pnl_delta,
            total_pnl=total_pnl,
            bp_used=bp_used,
            bp_headroom=bp_headroom,
            short_gamma_count=short_gamma_count,
            open_positions=open_positions,
            regime=regime,
            vix=vix,
            cumulative_equity=end_equity,
            drawdown=drawdown,
            experiment_id=self.experiment_id,
        )
        self._rows.append(row)

        # Save today's marks for tomorrow's unrealized delta computation
        self._prev_marks = dict(open_position_marks)

        return row

    def get_rows(self) -> list[DailyPortfolioRow]:
        """Return all daily rows accumulated so far."""
        return list(self._rows)

    def reset(self) -> None:
        """Reset tracker state (for multi-run experiments)."""
        self._rows.clear()
        self._prev_marks.clear()
        self._cumulative_equity = self.initial_equity
        self._peak_equity = self.initial_equity
