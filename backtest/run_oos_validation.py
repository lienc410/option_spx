"""
SPEC-029 out-of-sample validation.
"""

from __future__ import annotations

from backtest.attribution import (
    compute_regime_attribution,
    compute_strategy_attribution,
    print_regime_attribution,
    print_strategy_attribution,
)
from backtest.engine import BacktestResult, run_backtest
from backtest.metrics_portfolio import compute_portfolio_metrics
from strategy.selector import StrategyParams


def _split(result: BacktestResult, cutoff: str = "2020-01-01") -> tuple[list, list]:
    is_rows = [row for row in result.portfolio_rows if row.date < cutoff]
    oos_rows = [row for row in result.portfolio_rows if row.date >= cutoff]
    return is_rows, oos_rows


def _run_config(config_name: str, params: StrategyParams, start_date: str = "2000-01-01", end_date: str = "2026-03-31") -> BacktestResult:
    print(f"\n=== {config_name} ===")
    return run_backtest(start_date=start_date, end_date=end_date, params=params, verbose=False)


def _trade_split(result: BacktestResult, cutoff: str) -> tuple[list, list]:
    is_trades = [trade for trade in result.trades if trade.exit_date < cutoff]
    oos_trades = [trade for trade in result.trades if trade.exit_date >= cutoff]
    return is_trades, oos_trades


def run_oos_validation(start_date: str = "2000-01-01", end_date: str = "2026-03-31", cutoff: str = "2020-01-01") -> None:
    baseline = _run_config("EXP-baseline", StrategyParams(overlay_mode="disabled", shock_mode="shadow"), start_date, end_date)
    full = _run_config("EXP-full", StrategyParams(overlay_mode="active", shock_mode="shadow"), start_date, end_date)

    for label, result in (("EXP-baseline", baseline), ("EXP-full", full)):
        is_rows, oos_rows = _split(result, cutoff)
        full_metrics = compute_portfolio_metrics(result.portfolio_rows)
        is_metrics = compute_portfolio_metrics(is_rows)
        oos_metrics = compute_portfolio_metrics(oos_rows)
        print(f"\n{label}:")
        print(f"  Full ann/sharpe/calmar/maxdd: {full_metrics.ann_return:.2%} / {full_metrics.daily_sharpe:.2f} / {full_metrics.daily_calmar:.2f} / {full_metrics.max_drawdown:.2%}")
        print(f"  IS   ann/sharpe/calmar/maxdd: {is_metrics.ann_return:.2%} / {is_metrics.daily_sharpe:.2f} / {is_metrics.daily_calmar:.2f} / {is_metrics.max_drawdown:.2%}")
        print(f"  OOS  ann/sharpe/calmar/maxdd: {oos_metrics.ann_return:.2%} / {oos_metrics.daily_sharpe:.2f} / {oos_metrics.daily_calmar:.2f} / {oos_metrics.max_drawdown:.2%}")

    baseline_is_rows, baseline_oos_rows = _split(baseline, cutoff)
    full_is_rows, full_oos_rows = _split(full, cutoff)
    baseline_is_trades, baseline_oos_trades = _trade_split(baseline, cutoff)
    _, full_oos_trades = _trade_split(full, cutoff)

    base_oos = compute_portfolio_metrics(baseline_oos_rows)
    full_oos = compute_portfolio_metrics(full_oos_rows)
    maxdd_improvement = abs(base_oos.max_drawdown) - abs(full_oos.max_drawdown)
    is_daily_pnl = sum(row.total_pnl for row in baseline_is_rows) / max(len(baseline_is_rows), 1)
    oos_daily_pnl = sum(row.total_pnl for row in baseline_oos_rows) / max(len(baseline_oos_rows), 1)
    pnl_retention = (oos_daily_pnl / is_daily_pnl) if is_daily_pnl else 0.0
    is_trade_freq = len(baseline_is_trades) / max(len(baseline_is_rows), 1)
    oos_trade_freq = len(baseline_oos_trades) / max(len(baseline_oos_rows), 1)
    trade_retention = (oos_trade_freq / is_trade_freq) if is_trade_freq else 0.0

    print("\n=== OOS Acceptance Criteria ===")
    print(f"OOS-1 Sharpe > 0: {'PASS' if full_oos.daily_sharpe > 0 else 'FAIL'} ({full_oos.daily_sharpe:.2f})")
    print(f"OOS-2 MaxDD improvement >= 5%: {'PASS' if maxdd_improvement >= 0.05 else 'FAIL'} ({maxdd_improvement:.2%})")
    print(f"OOS-3 PnL retention >= 85%: {'PASS' if pnl_retention >= 0.85 else 'FAIL'} ({pnl_retention:.1%})")
    print(f"OOS-4 Trade drop <= 15%: {'PASS' if trade_retention >= 0.85 else 'FAIL'} ({trade_retention:.1%})")

    print("\n=== OOS Strategy Attribution ===")
    print_strategy_attribution(compute_strategy_attribution(full_oos_trades))
    print("\n=== OOS Regime Attribution ===")
    print_regime_attribution(compute_regime_attribution(full_oos_rows))
