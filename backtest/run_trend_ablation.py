"""
SPEC-020 trend ablation runner.
"""

from __future__ import annotations

from backtest.attribution import compute_strategy_attribution, print_strategy_attribution
from backtest.engine import run_backtest
from backtest.metrics_portfolio import compute_portfolio_metrics
from strategy.selector import StrategyParams


def run_trend_ablation(start_date: str = "2000-01-01", end_date: str = "2026-03-31") -> None:
    configs = {
        "EXP-baseline": StrategyParams(),
        "EXP-atr": StrategyParams(use_atr_trend=True),
        "EXP-persist": StrategyParams(bearish_persistence_days=3),
        "EXP-full": StrategyParams(use_atr_trend=True, bearish_persistence_days=3),
    }

    print("=== Trend Ablation ===")
    for name, params in configs.items():
        result = run_backtest(start_date=start_date, end_date=end_date, params=params, verbose=False)
        full_metrics = compute_portfolio_metrics(result.portfolio_rows)
        oos_rows = [row for row in result.portfolio_rows if row.date >= "2020-01-01"]
        oos_metrics = compute_portfolio_metrics(oos_rows)
        print(f"{name:<12} Full Sharpe {full_metrics.daily_sharpe:>6.2f}  OOS Sharpe {oos_metrics.daily_sharpe:>6.2f}  Full MaxDD {full_metrics.max_drawdown:>7.2%}")

    full_result = run_backtest(
        start_date=start_date,
        end_date=end_date,
        params=StrategyParams(use_atr_trend=True, bearish_persistence_days=3),
        verbose=False,
    )
    oos_trades = [trade for trade in full_result.trades if trade.exit_date >= "2020-01-01"]
    print("\n=== EXP-full OOS Strategy Attribution ===")
    print_strategy_attribution(compute_strategy_attribution(oos_trades))
