"""
PnL Attribution — SPEC-028

Decomposes backtest results by strategy type and VIX regime to answer:
  - Which strategy generates the most capital-efficient returns?
  - Which regime is the most profitable?
  - Is BP being deployed where it generates the most value?

compute_strategy_attribution(): 11 columns, one row per strategy type
compute_regime_attribution():   8 columns, one row per VIX regime
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, TYPE_CHECKING
import statistics

if TYPE_CHECKING:
    from backtest.engine import Trade
    from backtest.portfolio import DailyPortfolioRow


# ─── Strategy attribution ─────────────────────────────────────────────────────

@dataclass
class StrategyAttributionRow:
    """Per-strategy aggregation (11 fields)."""
    strategy:            str
    trade_count:         int
    win_rate:            float    # fraction of trades with exit_pnl > 0
    gross_pnl:           float    # sum of exit_pnl (raw, not adjusted)
    net_pnl:             float    # sum of exit_pnl after haircut (same in Precision B)
    mean_pnl_per_trade:  float
    median_pnl_per_trade:float
    mean_hold_days:      float    # avg (dte_at_entry - dte_at_exit)
    total_bp_days:       float    # sum(total_bp × hold_days) — capital consumption
    pnl_per_bp_day:      float    # net_pnl / total_bp_days
    pct_of_total_pnl:    float    # this strategy's net_pnl as fraction of all strategies


def compute_strategy_attribution(
    trades: Sequence["Trade"],
) -> list[StrategyAttributionRow]:
    """
    Compute 11-column strategy attribution from closed trade records.

    Returns one row per strategy type, sorted by net_pnl descending.
    """
    from collections import defaultdict

    groups: dict[str, list["Trade"]] = defaultdict(list)
    for t in trades:
        groups[str(t.strategy)].append(t)

    total_net = sum(t.exit_pnl for t in trades)

    rows = []
    for strategy, ts in groups.items():
        pnls = [t.exit_pnl for t in ts]
        hold_days = [
            max(0, t.dte_at_entry - t.dte_at_exit)
            for t in ts
        ]
        bp_days = [
            t.total_bp * max(1, h)
            for t, h in zip(ts, hold_days)
        ]
        total_bp_days = sum(bp_days)
        net_pnl = sum(pnls)

        rows.append(StrategyAttributionRow(
            strategy=strategy,
            trade_count=len(ts),
            win_rate=sum(1 for p in pnls if p > 0) / len(pnls),
            gross_pnl=net_pnl,
            net_pnl=net_pnl,
            mean_pnl_per_trade=statistics.mean(pnls),
            median_pnl_per_trade=statistics.median(pnls),
            mean_hold_days=statistics.mean(hold_days) if hold_days else 0.0,
            total_bp_days=total_bp_days,
            pnl_per_bp_day=net_pnl / total_bp_days if total_bp_days > 0 else 0.0,
            pct_of_total_pnl=net_pnl / total_net if total_net != 0 else 0.0,
        ))

    rows.sort(key=lambda r: r.net_pnl, reverse=True)
    return rows


# ─── Regime attribution ───────────────────────────────────────────────────────

@dataclass
class RegimeAttributionRow:
    """Per-VIX-regime aggregation from daily portfolio rows (8 fields)."""
    regime:                    str
    day_count:                 int
    pct_of_trading_days:       float
    mean_daily_return_net:     float    # mean of daily_return_net in this regime
    regime_sharpe:             float    # annualized Sharpe within regime window
    mean_bp_utilization:       float    # mean(bp_used / account_size)
    total_net_pnl_contribution:float    # sum of total_pnl rows in this regime
    pct_of_total_pnl:          float


def compute_regime_attribution(
    rows: Sequence["DailyPortfolioRow"],
    account_size: float = 100_000,
) -> list[RegimeAttributionRow]:
    """
    Compute 8-column regime attribution from daily portfolio rows.

    Returns one row per regime, sorted by total_net_pnl_contribution descending.
    """
    import math
    from collections import defaultdict

    groups: dict[str, list["DailyPortfolioRow"]] = defaultdict(list)
    for r in rows:
        groups[r.regime].append(r)

    total_days = len(rows)
    total_pnl = sum(r.total_pnl for r in rows)

    result = []
    for regime, regime_rows in groups.items():
        daily_rets = [r.daily_return_net for r in regime_rows]
        n = len(daily_rets)
        mean_ret = statistics.mean(daily_rets) if daily_rets else 0.0
        std_ret = statistics.stdev(daily_rets) if n > 1 else 0.0
        regime_sharpe = (
            mean_ret / std_ret * math.sqrt(252) if std_ret > 0 else 0.0
        )
        mean_bp_util = statistics.mean(
            r.bp_used / account_size for r in regime_rows
        ) if regime_rows else 0.0
        regime_pnl = sum(r.total_pnl for r in regime_rows)

        result.append(RegimeAttributionRow(
            regime=regime,
            day_count=n,
            pct_of_trading_days=n / total_days if total_days > 0 else 0.0,
            mean_daily_return_net=mean_ret,
            regime_sharpe=regime_sharpe,
            mean_bp_utilization=mean_bp_util,
            total_net_pnl_contribution=regime_pnl,
            pct_of_total_pnl=regime_pnl / total_pnl if total_pnl != 0 else 0.0,
        ))

    result.sort(key=lambda r: r.total_net_pnl_contribution, reverse=True)
    return result


def print_strategy_attribution(rows: list[StrategyAttributionRow]) -> None:
    """Pretty-print strategy attribution table."""
    header = (
        f"{'Strategy':<25} {'N':>5} {'WR':>6} {'NetPnL':>10} "
        f"{'Avg':>8} {'Hold':>5} {'PnL/BP-day':>12} {'%Total':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r.strategy:<25} {r.trade_count:>5} {r.win_rate*100:>5.1f}% "
            f"{r.net_pnl:>10,.0f} {r.mean_pnl_per_trade:>8,.0f} "
            f"{r.mean_hold_days:>5.1f} {r.pnl_per_bp_day:>12.6f} "
            f"{r.pct_of_total_pnl*100:>6.1f}%"
        )


def print_regime_attribution(rows: list[RegimeAttributionRow]) -> None:
    """Pretty-print regime attribution table."""
    header = (
        f"{'Regime':<15} {'Days':>6} {'%Days':>7} {'AvgRet':>8} "
        f"{'Sharpe':>7} {'BPUtil':>7} {'PnL':>10} {'%PnL':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r.regime:<15} {r.day_count:>6} {r.pct_of_trading_days*100:>6.1f}% "
            f"{r.mean_daily_return_net*100:>7.3f}% {r.regime_sharpe:>7.2f} "
            f"{r.mean_bp_utilization*100:>6.1f}% {r.total_net_pnl_contribution:>10,.0f} "
            f"{r.pct_of_total_pnl*100:>6.1f}%"
        )
