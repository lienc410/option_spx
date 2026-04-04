"""
Portfolio-Level Metrics — SPEC-024 / SPEC-028

Computes daily-return-based risk metrics from a list of DailyPortfolioRow records.

Metrics:
  - ann_return:         Annualized net return (geometric)
  - daily_sharpe:       Annualized Sharpe ratio using daily returns (risk-free = 0)
  - daily_sortino:      Sortino ratio (downside deviation only)
  - daily_calmar:       Calmar ratio = ann_return / |max_drawdown|
  - max_drawdown:       Maximum peak-to-trough drawdown (fraction, ≤ 0)
  - cvar_95:            Conditional Value at Risk at 95% (expected loss in worst 5% days)
  - worst_5d_drawdown:  Worst rolling 5-day cumulative return
  - positive_months_pct: Fraction of calendar months with positive net return
  - pnl_per_bp_day:     Total net PnL / sum(daily_used_bp) — capital efficiency (SPEC-028)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence
import statistics

from backtest.portfolio import DailyPortfolioRow


TRADING_DAYS_PER_YEAR = 252


@dataclass
class PortfolioMetrics:
    ann_return:           float   # annualized geometric return (fraction)
    daily_sharpe:         float   # annualized Sharpe (daily returns, rf=0)
    daily_sortino:        float   # annualized Sortino ratio
    daily_calmar:         float   # Calmar ratio (ann_return / |max_drawdown|)
    max_drawdown:         float   # worst drawdown (fraction, ≤ 0)
    cvar_95:              float   # CVaR 95% — mean of worst 5% daily returns
    worst_5d_drawdown:    float   # worst rolling 5-day cumulative return
    positive_months_pct:  float   # fraction of months with positive net return
    pnl_per_bp_day:       float   # net PnL per $1 of BP held for 1 day (capital efficiency)
    total_days:           int     # number of trading days in sample
    experiment_id:        str     # from the rows

    def __str__(self) -> str:
        return (
            f"Ann.Ret={self.ann_return*100:.2f}%  "
            f"Sharpe={self.daily_sharpe:.2f}  "
            f"Calmar={self.daily_calmar:.2f}  "
            f"MaxDD={self.max_drawdown*100:.2f}%  "
            f"CVaR95={self.cvar_95*100:.3f}%  "
            f"PnL/BP-day={self.pnl_per_bp_day:.6f}"
        )


def compute_portfolio_metrics(rows: Sequence[DailyPortfolioRow]) -> PortfolioMetrics:
    """
    Compute portfolio-level metrics from a sequence of DailyPortfolioRow records.

    Args:
        rows: Ordered daily rows from PortfolioTracker.get_rows()

    Returns:
        PortfolioMetrics dataclass with all computed values.

    Notes:
        - Risk-free rate assumed 0 (relative performance focus)
        - Sharpe / Sortino annualized by √252
        - CVaR 95%: mean of the worst 5% daily net returns
        - worst_5d_drawdown: rolling window of 5 cumulative returns
        - pnl_per_bp_day: total_net_pnl / sum(bp_used) per day
          handles zero BP days gracefully (returns 0.0)
    """
    if not rows:
        raise ValueError("Cannot compute metrics from empty row list")

    daily_returns = [r.daily_return_net for r in rows]
    n = len(daily_returns)

    # ── Annualized return (geometric) ──────────────────────────────────────────
    final_equity = rows[-1].cumulative_equity
    initial_equity = rows[0].start_equity
    if initial_equity <= 0:
        raise ValueError(f"initial_equity must be > 0, got {initial_equity}")
    years = n / TRADING_DAYS_PER_YEAR
    ann_return = (final_equity / initial_equity) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    # ── Sharpe ────────────────────────────────────────────────────────────────
    mean_ret = statistics.mean(daily_returns)
    std_ret = statistics.stdev(daily_returns) if n > 1 else 0.0
    daily_sharpe = (mean_ret / std_ret * math.sqrt(TRADING_DAYS_PER_YEAR)) if std_ret > 0 else 0.0

    # ── Sortino ───────────────────────────────────────────────────────────────
    downside = [r for r in daily_returns if r < 0]
    downside_std = math.sqrt(sum(r**2 for r in downside) / max(len(downside), 1))
    daily_sortino = (
        mean_ret / downside_std * math.sqrt(TRADING_DAYS_PER_YEAR)
        if downside_std > 0 else 0.0
    )

    # ── Max drawdown ──────────────────────────────────────────────────────────
    max_drawdown = min((r.drawdown for r in rows), default=0.0)

    # ── Calmar ────────────────────────────────────────────────────────────────
    daily_calmar = ann_return / abs(max_drawdown) if max_drawdown < 0 else 0.0

    # ── CVaR 95% ──────────────────────────────────────────────────────────────
    sorted_returns = sorted(daily_returns)
    cutoff = max(1, int(math.floor(n * 0.05)))
    cvar_95 = statistics.mean(sorted_returns[:cutoff]) if cutoff > 0 else sorted_returns[0]

    # ── Worst 5-day rolling drawdown ──────────────────────────────────────────
    worst_5d = 0.0
    for i in range(n - 4):
        window = daily_returns[i : i + 5]
        cumulative = 1.0
        for r in window:
            cumulative *= (1.0 + r)
        rolling_ret = cumulative - 1.0
        worst_5d = min(worst_5d, rolling_ret)

    # ── Positive months % ─────────────────────────────────────────────────────
    monthly: dict[str, float] = {}
    for row in rows:
        month_key = row.date[:7]   # "YYYY-MM"
        monthly.setdefault(month_key, 1.0)
        monthly[month_key] *= (1.0 + row.daily_return_net)

    month_returns = [v - 1.0 for v in monthly.values()]
    positive_months_pct = (
        sum(1 for r in month_returns if r > 0) / len(month_returns)
        if month_returns else 0.0
    )

    # ── PnL per BP-day (capital efficiency, SPEC-028) ─────────────────────────
    total_bp_days = sum(r.bp_used for r in rows)
    total_net_pnl = final_equity - initial_equity
    pnl_per_bp_day = total_net_pnl / total_bp_days if total_bp_days > 0 else 0.0

    experiment_id = rows[0].experiment_id if rows else ""

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
        total_days=n,
        experiment_id=experiment_id,
    )


if __name__ == "__main__":
    # Minimal smoke test with synthetic flat equity curve
    from backtest.portfolio import DailyPortfolioRow
    rows = [
        DailyPortfolioRow(
            date=f"2026-01-{i+1:02d}",
            start_equity=100000 + i * 10,
            end_equity=100000 + (i + 1) * 10,
            daily_return_gross=10 / (100000 + i * 10),
            daily_return_net=10 / (100000 + i * 10),
            realized_pnl=10.0,
            unrealized_pnl_delta=0.0,
            total_pnl=10.0,
            bp_used=5000.0,
            bp_headroom=45000.0,
            short_gamma_count=1,
            open_positions=1,
            regime="NORMAL",
            vix=18.0,
            cumulative_equity=100000 + (i + 1) * 10,
            drawdown=0.0,
            experiment_id="EXP-TEST",
        )
        for i in range(252)
    ]
    m = compute_portfolio_metrics(rows)
    print(m)
    assert m.daily_sharpe > 0, "Sharpe should be positive for rising equity curve"
    print("metrics_portfolio.py OK")
