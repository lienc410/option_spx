"""
Daily portfolio tracking for backtests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class DailyPortfolioRow:
    date: str
    start_equity: float
    end_equity: float
    daily_return_gross: float
    daily_return_net: float
    realized_pnl: float
    unrealized_pnl_delta: float
    total_pnl: float
    bp_used: float
    bp_headroom: float
    short_gamma_count: int
    open_positions: int
    regime: str
    vix: float
    cumulative_equity: float
    drawdown: float
    experiment_id: str

    def to_dict(self) -> dict:
        return asdict(self)


class PortfolioTracker:
    """Accumulate one daily portfolio row per backtest day."""

    def __init__(self, initial_equity: float, experiment_id: str, account_size: float | None = None) -> None:
        self.initial_equity = initial_equity
        self.experiment_id = experiment_id
        self.account_size = account_size or initial_equity
        self._rows: list[DailyPortfolioRow] = []
        self._peak_equity = initial_equity
        self._cumulative_equity = initial_equity
        self._prev_marks: dict[str, float] = {}

    def update_day(
        self,
        *,
        date: str,
        realized_pnl: float,
        open_position_marks: dict[str, float],
        bp_used: float,
        bp_headroom: float,
        short_gamma_count: int,
        open_positions: int,
        regime: str,
        vix: float,
    ) -> DailyPortfolioRow:
        curr_total_mark = sum(open_position_marks.values())
        prev_total_mark = sum(self._prev_marks.get(pid, 0.0) for pid in open_position_marks)
        unrealized_pnl_delta = curr_total_mark - prev_total_mark
        total_pnl = realized_pnl + unrealized_pnl_delta

        start_equity = self._cumulative_equity
        end_equity = start_equity + total_pnl
        self._cumulative_equity = end_equity
        daily_return = ((end_equity - start_equity) / start_equity) if start_equity else 0.0

        if end_equity > self._peak_equity:
            self._peak_equity = end_equity
        drawdown = ((end_equity - self._peak_equity) / self._peak_equity) if self._peak_equity else 0.0

        row = DailyPortfolioRow(
            date=date,
            start_equity=start_equity,
            end_equity=end_equity,
            daily_return_gross=daily_return,
            daily_return_net=daily_return,
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
        self._prev_marks = dict(open_position_marks)
        return row

    def get_rows(self) -> list[DailyPortfolioRow]:
        return list(self._rows)
