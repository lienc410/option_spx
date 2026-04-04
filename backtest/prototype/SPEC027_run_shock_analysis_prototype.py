"""
Shock Engine Phase A — Shadow Mode Analysis (SPEC-027)

Runs a full-history backtest in shock_mode="shadow", then analyses the
ShockReport log to answer:
  - Hit rate by year and regime (would-be rejection rate if active)
  - Breach type distribution (core / incremental / bp_headroom)
  - Percentile distribution of shock values

Critical fix: compute hit_rates by comparing budget columns directly,
NOT by reading the `approved` field (which is always True in shadow mode).

Usage:
    python -m backtest.run_shock_analysis [--start 2000-01-01] [--end 2026-03-31]
"""

from __future__ import annotations

import argparse
import math
import statistics
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class ShockAnalysisResult:
    """Summary of shadow-mode shock analysis."""
    total_entry_checks:      int
    any_breach_count:        int
    any_breach_rate:         float   # would-be rejection rate
    core_breach_count:       int
    incremental_breach_count:int
    bp_headroom_breach_count:int

    # Annual hit rate: year (str) → fraction
    annual_hit_rate: dict[str, float] = field(default_factory=dict)

    # Regime hit rate: regime (str) → fraction
    regime_hit_rate: dict[str, float] = field(default_factory=dict)

    # Percentiles of abs(post_max_core_loss_pct)
    p50_core_shock: float = 0.0
    p95_core_shock: float = 0.0
    p99_core_shock: float = 0.0

    def print_summary(self) -> None:
        print(f"\n=== Shock Phase A: Shadow Analysis ===")
        print(f"Total entry checks:    {self.total_entry_checks}")
        print(f"Any breach (would-be): {self.any_breach_count} ({self.any_breach_rate*100:.1f}%)")
        print(f"  Core breach:         {self.core_breach_count}")
        print(f"  Incremental breach:  {self.incremental_breach_count}")
        print(f"  BP headroom breach:  {self.bp_headroom_breach_count}")
        print(f"\nCore shock percentiles:")
        print(f"  P50: {self.p50_core_shock*100:.3f}%  P95: {self.p95_core_shock*100:.3f}%  P99: {self.p99_core_shock*100:.3f}%")
        print(f"\nAnnual hit rates:")
        for year in sorted(self.annual_hit_rate):
            print(f"  {year}: {self.annual_hit_rate[year]*100:.1f}%")
        print(f"\nRegime hit rates:")
        for regime, rate in sorted(self.regime_hit_rate.items(), key=lambda x: -x[1]):
            print(f"  {regime:<15} {rate*100:.1f}%")


def compute_hit_rates(shock_records: list[dict]) -> ShockAnalysisResult:
    """
    Compute would-be rejection stats from a list of ShockReport dicts.

    CRITICAL: Do NOT use shock_record["approved"] — it is always True in shadow mode.
    Instead, compare budget columns directly (SPEC-027 bug fix).

    Expected keys per record:
      date, regime, post_max_core_loss_pct, incremental_shock_pct,
      bp_headroom_pct, budget_core, budget_incremental, bp_headroom_budget
    """
    if not shock_records:
        return ShockAnalysisResult(
            total_entry_checks=0, any_breach_count=0, any_breach_rate=0.0,
            core_breach_count=0, incremental_breach_count=0, bp_headroom_breach_count=0,
        )

    n = len(shock_records)
    core_breaches = []
    inc_breaches = []
    bp_breaches = []
    any_breaches = []
    core_shock_vals = []
    annual: dict[str, list[bool]] = {}
    regime: dict[str, list[bool]] = {}

    for rec in shock_records:
        # Direct budget comparison (not rec["approved"] — see SPEC-027 fix)
        core_b = abs(rec.get("post_max_core_loss_pct", 0.0)) > rec.get("budget_core", 0.0125)
        inc_b  = abs(rec.get("incremental_shock_pct", 0.0)) > rec.get("budget_incremental", 0.004)
        bp_b   = rec.get("bp_headroom_pct", 1.0) < rec.get("bp_headroom_budget", 0.15)
        any_b  = core_b or inc_b or bp_b

        core_breaches.append(core_b)
        inc_breaches.append(inc_b)
        bp_breaches.append(bp_b)
        any_breaches.append(any_b)

        core_shock_vals.append(abs(rec.get("post_max_core_loss_pct", 0.0)))

        year = rec.get("date", "0000")[:4]
        annual.setdefault(year, []).append(any_b)

        reg = rec.get("regime", "UNKNOWN")
        regime.setdefault(reg, []).append(any_b)

    # Percentiles of core shock
    sorted_shocks = sorted(core_shock_vals)
    p50 = _percentile(sorted_shocks, 0.50)
    p95 = _percentile(sorted_shocks, 0.95)
    p99 = _percentile(sorted_shocks, 0.99)

    return ShockAnalysisResult(
        total_entry_checks=n,
        any_breach_count=sum(any_breaches),
        any_breach_rate=sum(any_breaches) / n,
        core_breach_count=sum(core_breaches),
        incremental_breach_count=sum(inc_breaches),
        bp_headroom_breach_count=sum(bp_breaches),
        annual_hit_rate={y: sum(v) / len(v) for y, v in annual.items()},
        regime_hit_rate={r: sum(v) / len(v) for r, v in regime.items()},
        p50_core_shock=p50,
        p95_core_shock=p95,
        p99_core_shock=p99,
    )


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Return q-th percentile (0.0–1.0) of a sorted list."""
    if not sorted_vals:
        return 0.0
    idx = q * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def run_phase_a_analysis(
    start_date: str = "2000-01-01",
    end_date: str = "2026-03-31",
) -> ShockAnalysisResult:
    """
    Run full-history backtest in shadow mode and produce Phase A analysis.

    This function imports and runs the backtest engine with shock_mode="shadow"
    and collects ShockReport records for analysis.
    """
    from strategy.selector import StrategyParams
    from backtest.experiment import run_backtest

    params = StrategyParams()
    params.shock_mode = "shadow"
    params.overlay_mode = "disabled"

    print(f"Running Phase A shadow analysis: {start_date} → {end_date}")
    result = run_backtest(
        start_date=start_date,
        end_date=end_date,
        params=params,
        collect_shock_reports=True,
    )

    shock_records = getattr(result, "shock_reports", [])
    if not shock_records:
        print("Warning: no ShockReport records collected. Check engine collect_shock_reports support.")
        return ShockAnalysisResult(0, 0, 0.0, 0, 0, 0)

    analysis = compute_hit_rates(shock_records)
    analysis.print_summary()
    return analysis


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shock Phase A shadow analysis")
    parser.add_argument("--start", default="2000-01-01")
    parser.add_argument("--end",   default="2026-03-31")
    args = parser.parse_args()
    run_phase_a_analysis(args.start, args.end)
