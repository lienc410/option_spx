"""
Portfolio-level daily metrics.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from typing import Sequence

from backtest.portfolio import DailyPortfolioRow


TRADING_DAYS_PER_YEAR = 252


@dataclass
class PortfolioMetrics:
    ann_return: float
    daily_sharpe: float
    daily_sortino: float
    daily_calmar: float
    max_drawdown: float
    cvar_95: float
    worst_5d_drawdown: float
    positive_months_pct: float
    pnl_per_bp_day: float
    total_days: int
    experiment_id: str

    def to_dict(self) -> dict:
        return asdict(self)


def compute_portfolio_metrics(rows: Sequence[DailyPortfolioRow]) -> PortfolioMetrics:
    if not rows:
        raise ValueError("Cannot compute metrics from empty row list")

    daily_returns = [row.daily_return_net for row in rows]
    total_days = len(daily_returns)
    final_equity = rows[-1].cumulative_equity
    initial_equity = rows[0].start_equity
    years = total_days / TRADING_DAYS_PER_YEAR if total_days else 0.0
    ann_return = ((final_equity / initial_equity) ** (1.0 / years) - 1.0) if years and initial_equity > 0 else 0.0

    mean_ret = statistics.mean(daily_returns)
    std_ret = statistics.stdev(daily_returns) if total_days > 1 else 0.0
    downside = [ret for ret in daily_returns if ret < 0]
    downside_std = math.sqrt(sum(ret * ret for ret in downside) / len(downside)) if downside else 0.0

    daily_sharpe = (mean_ret / std_ret * math.sqrt(TRADING_DAYS_PER_YEAR)) if std_ret > 0 else 0.0
    daily_sortino = (mean_ret / downside_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if downside_std > 0 else 0.0
    max_drawdown = min((row.drawdown for row in rows), default=0.0)
    daily_calmar = ann_return / abs(max_drawdown) if max_drawdown < 0 else 0.0

    sorted_returns = sorted(daily_returns)
    cutoff = max(1, int(math.floor(total_days * 0.05)))
    cvar_95 = statistics.mean(sorted_returns[:cutoff]) if sorted_returns else 0.0

    worst_5d = 0.0
    for i in range(max(0, total_days - 4)):
        cumulative = 1.0
        for ret in daily_returns[i:i + 5]:
            cumulative *= (1.0 + ret)
        worst_5d = min(worst_5d, cumulative - 1.0)

    monthly: dict[str, float] = {}
    for row in rows:
        month_key = row.date[:7]
        monthly.setdefault(month_key, 1.0)
        monthly[month_key] *= (1.0 + row.daily_return_net)
    month_returns = [value - 1.0 for value in monthly.values()]
    positive_months_pct = (
        sum(1 for ret in month_returns if ret > 0) / len(month_returns)
        if month_returns else 0.0
    )

    total_bp_days = sum(row.bp_used for row in rows)
    total_net_pnl = final_equity - initial_equity
    pnl_per_bp_day = total_net_pnl / total_bp_days if total_bp_days > 0 else 0.0

    return PortfolioMetrics(
        ann_return=ann_return,
        daily_sharpe=daily_sharpe,
        daily_sortino=daily_sortino,
        daily_calmar=daily_calmar,
        max_drawdown=max_drawdown,
        cvar_95=cvar_95,
        worst_5d_drawdown=worst_5d,
        positive_months_pct=positive_months_pct,
        pnl_per_bp_day=pnl_per_bp_day,
        total_days=total_days,
        experiment_id=rows[0].experiment_id,
    )
