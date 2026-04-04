"""
PnL attribution helpers.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

from backtest.portfolio import DailyPortfolioRow


@dataclass
class StrategyAttributionRow:
    strategy: str
    trade_count: int
    win_rate: float
    gross_pnl: float
    net_pnl: float
    mean_pnl_per_trade: float
    median_pnl_per_trade: float
    mean_hold_days: float
    total_bp_days: float
    pnl_per_bp_day: float
    pct_of_total_pnl: float


@dataclass
class RegimeAttributionRow:
    regime: str
    day_count: int
    pct_of_trading_days: float
    mean_daily_return_net: float
    regime_sharpe: float
    mean_bp_utilization: float
    total_net_pnl_contribution: float
    pct_of_total_pnl: float


def compute_strategy_attribution(trades: Sequence) -> list[StrategyAttributionRow]:
    groups: dict[str, list] = {}
    for trade in trades:
        key = trade.strategy.value if hasattr(trade.strategy, "value") else str(trade.strategy)
        groups.setdefault(key, []).append(trade)

    total_net_pnl = sum(trade.exit_pnl for trade in trades)
    rows: list[StrategyAttributionRow] = []
    for strategy, items in groups.items():
        pnls = [trade.exit_pnl for trade in items]
        hold_days = [max(trade.dte_at_entry - trade.dte_at_exit, 1) for trade in items]
        total_bp_days = sum(trade.total_bp * hold for trade, hold in zip(items, hold_days))
        net_pnl = sum(pnls)
        rows.append(
            StrategyAttributionRow(
                strategy=strategy,
                trade_count=len(items),
                win_rate=sum(1 for pnl in pnls if pnl > 0) / len(items),
                gross_pnl=net_pnl,
                net_pnl=net_pnl,
                mean_pnl_per_trade=statistics.mean(pnls),
                median_pnl_per_trade=statistics.median(pnls),
                mean_hold_days=statistics.mean(hold_days),
                total_bp_days=total_bp_days,
                pnl_per_bp_day=(net_pnl / total_bp_days) if total_bp_days > 0 else 0.0,
                pct_of_total_pnl=(net_pnl / total_net_pnl) if total_net_pnl else 0.0,
            )
        )
    rows.sort(key=lambda row: row.net_pnl, reverse=True)
    return rows


def compute_regime_attribution(rows: Sequence[DailyPortfolioRow], account_size: float = 100_000.0) -> list[RegimeAttributionRow]:
    groups: dict[str, list[DailyPortfolioRow]] = {}
    for row in rows:
        groups.setdefault(row.regime, []).append(row)

    total_days = len(rows)
    total_pnl = sum(row.total_pnl for row in rows)
    results: list[RegimeAttributionRow] = []
    for regime, items in groups.items():
        daily_returns = [row.daily_return_net for row in items]
        mean_ret = statistics.mean(daily_returns) if daily_returns else 0.0
        std_ret = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.0
        sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0
        mean_bp_util = statistics.mean((row.bp_used / account_size) for row in items) if items else 0.0
        regime_pnl = sum(row.total_pnl for row in items)
        results.append(
            RegimeAttributionRow(
                regime=regime,
                day_count=len(items),
                pct_of_trading_days=(len(items) / total_days) if total_days else 0.0,
                mean_daily_return_net=mean_ret,
                regime_sharpe=sharpe,
                mean_bp_utilization=mean_bp_util,
                total_net_pnl_contribution=regime_pnl,
                pct_of_total_pnl=(regime_pnl / total_pnl) if total_pnl else 0.0,
            )
        )
    results.sort(key=lambda row: row.total_net_pnl_contribution, reverse=True)
    return results


def print_strategy_attribution(rows: list[StrategyAttributionRow]) -> None:
    print(f"{'Strategy':<28} {'N':>4} {'WR':>6} {'NetPnL':>10} {'PnL/BP-day':>12}")
    print("-" * 68)
    for row in rows:
        print(f"{row.strategy:<28} {row.trade_count:>4} {row.win_rate*100:>5.1f}% {row.net_pnl:>10,.0f} {row.pnl_per_bp_day:>12.6f}")


def print_regime_attribution(rows: list[RegimeAttributionRow]) -> None:
    print(f"{'Regime':<14} {'Days':>6} {'Sharpe':>8} {'BPUtil':>8} {'PnL':>10}")
    print("-" * 56)
    for row in rows:
        print(f"{row.regime:<14} {row.day_count:>6} {row.regime_sharpe:>8.2f} {row.mean_bp_utilization*100:>7.1f}% {row.total_net_pnl_contribution:>10,.0f}")
