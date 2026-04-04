"""
backtest/experiment.py — Experiment logging and comparison for the optimization loop.

Each run_experiment() call:
  1. Executes run_backtest() with the given StrategyParams
  2. Appends results to logs/experiments.jsonl (one JSON object per line)
  3. Returns the experiment dict for immediate use

Schema per experiment:
{
  "id":         1,
  "ts":         "2026-03-28T10:00:00Z",
  "note":       "baseline",
  "start_date": "2020-01-01",
  "params":     { ... StrategyParams fields ... },
  "metrics":    { ... from compute_metrics() ... },
  "is_auto":    false
}
"""

from __future__ import annotations

import json
import os
import dataclasses
from datetime import datetime, timezone
from typing import Optional

from strategy.selector import StrategyParams, DEFAULT_PARAMS
from backtest.engine import run_backtest

EXPERIMENTS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "logs", "experiments.jsonl"
)


def _exp_path() -> str:
    return os.path.normpath(EXPERIMENTS_FILE)


def load_experiments() -> list[dict]:
    """Load all experiments from JSONL log, sorted by id ascending."""
    path = _exp_path()
    if not os.path.exists(path):
        return []
    results = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return sorted(results, key=lambda x: x.get("id", 0))


def _next_id(experiments: list[dict]) -> int:
    if not experiments:
        return 1
    return max(e.get("id", 0) for e in experiments) + 1


def run_experiment(
    params:     StrategyParams = DEFAULT_PARAMS,
    note:       str = "",
    start_date: str = "2020-01-01",
    end_date:   Optional[str] = None,
    is_auto:    bool = False,
) -> dict:
    """
    Run a single backtest experiment and persist the result.

    Args:
        params:     Strategy parameters for this run.
        note:       Human-readable description of what changed.
        start_date: Backtest start date (ISO format).
        end_date:   Backtest end date (ISO format, defaults to today).
        is_auto:    True if triggered by automated grid search.

    Returns:
        The experiment dict (same as what's written to JSONL).
    """
    trades, metrics, signals = run_backtest(
        start_date=start_date,
        end_date=end_date,
        params=params,
        verbose=False,
    )

    existing = load_experiments()
    exp_id   = _next_id(existing)

    exp = {
        "id":         exp_id,
        "ts":         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note":       note or f"run #{exp_id}",
        "start_date": start_date,
        "end_date":   end_date or "",
        "params":     dataclasses.asdict(params),
        "metrics":    metrics,
        "trade_count": len(trades),
        "is_auto":    is_auto,
    }

    # Append atomically
    path = _exp_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(exp) + "\n")

    return exp


def diff_params(exp_a: dict, exp_b: dict) -> dict:
    """
    Return a dict of parameters that differ between two experiments.
    Format: { param_name: (value_in_a, value_in_b) }
    """
    pa = exp_a.get("params", {})
    pb = exp_b.get("params", {})
    all_keys = set(pa) | set(pb)
    return {
        k: (pa.get(k), pb.get(k))
        for k in sorted(all_keys)
        if pa.get(k) != pb.get(k)
    }


def diff_metrics(exp_a: dict, exp_b: dict) -> dict:
    """
    Return metric deltas between two experiments (b - a, with pct change).
    Format: { metric: { "a": v, "b": v, "delta": v, "pct": v } }
    Only includes top-level numeric metrics.
    """
    ma = exp_a.get("metrics", {})
    mb = exp_b.get("metrics", {})
    result = {}
    for k in ("sharpe", "win_rate", "expectancy", "total_pnl", "max_drawdown", "total_trades"):
        va = ma.get(k)
        vb = mb.get(k)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            delta = vb - va
            pct   = (delta / abs(va) * 100) if va != 0 else None
            result[k] = {"a": va, "b": vb, "delta": delta, "pct": pct}
    return result
