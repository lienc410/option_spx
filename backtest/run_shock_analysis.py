"""
SPEC-027 shadow-mode shock analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backtest.engine import run_backtest
from strategy.selector import StrategyParams


@dataclass
class ShockAnalysisResult:
    total_entry_checks: int
    any_breach_count: int
    any_breach_rate: float
    core_breach_count: int
    incremental_breach_count: int
    bp_headroom_breach_count: int
    annual_hit_rate: dict[str, float] = field(default_factory=dict)
    regime_hit_rate: dict[str, float] = field(default_factory=dict)
    p50_core_shock: float = 0.0
    p95_core_shock: float = 0.0
    p99_core_shock: float = 0.0


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = q * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def compute_hit_rates(shock_records: list[dict]) -> ShockAnalysisResult:
    if not shock_records:
        return ShockAnalysisResult(0, 0, 0.0, 0, 0, 0)

    any_hits: list[bool] = []
    core_hits: list[bool] = []
    inc_hits: list[bool] = []
    bp_hits: list[bool] = []
    annual: dict[str, list[bool]] = {}
    regime: dict[str, list[bool]] = {}
    core_losses: list[float] = []

    for record in shock_records:
        core = abs(record.get("post_max_core_loss_pct", 0.0)) > record.get("budget_core", 0.0)
        incremental = abs(record.get("incremental_shock_pct", 0.0)) > record.get("budget_incremental", 0.0)
        bp = record.get("bp_headroom_pct", 1.0) < record.get("bp_headroom_budget", 0.15)
        breach = core or incremental or bp

        core_hits.append(core)
        inc_hits.append(incremental)
        bp_hits.append(bp)
        any_hits.append(breach)
        core_losses.append(abs(record.get("post_max_core_loss_pct", 0.0)))

        annual.setdefault(record.get("date", "0000")[:4], []).append(breach)
        regime.setdefault(record.get("regime", "UNKNOWN"), []).append(breach)

    sorted_losses = sorted(core_losses)
    return ShockAnalysisResult(
        total_entry_checks=len(shock_records),
        any_breach_count=sum(any_hits),
        any_breach_rate=sum(any_hits) / len(any_hits),
        core_breach_count=sum(core_hits),
        incremental_breach_count=sum(inc_hits),
        bp_headroom_breach_count=sum(bp_hits),
        annual_hit_rate={key: sum(vals) / len(vals) for key, vals in annual.items()},
        regime_hit_rate={key: sum(vals) / len(vals) for key, vals in regime.items()},
        p50_core_shock=_percentile(sorted_losses, 0.50),
        p95_core_shock=_percentile(sorted_losses, 0.95),
        p99_core_shock=_percentile(sorted_losses, 0.99),
    )


def run_phase_a_analysis(start_date: str = "2000-01-01", end_date: str = "2026-03-31") -> ShockAnalysisResult:
    params = StrategyParams(shock_mode="shadow", overlay_mode="disabled")
    result = run_backtest(start_date=start_date, end_date=end_date, params=params, collect_shock_reports=True)
    return compute_hit_rates(result.shock_reports)
