"""Baseline snapshot runner — SPEC-077 default lift (profit_target=0.60).

Captures HC state after SPEC-077 raised `StrategyParams.profit_target` from
0.50 → 0.60 (strategy/selector.py:68). Compare against
`doc/baseline_2026-04-24/` (profit_target=0.50, MC-divergent baseline).

Outputs (under doc/baseline_2026-05-02/):
- trade_log.csv       Full trade history.
- metrics.json        Headline metrics dict.
- signals.csv         Daily signal_history rows.
- 2026-03-strikes.json IC_HV legs constructed on 2026-03-09 and 2026-03-10.
- selector_dump_2026-03-09.json / 2026-03-10.json  Per-day selector snapshot.

Usage:  arch -arm64 venv/bin/python doc/baseline_2026-05-02/run_baseline.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from dataclasses import asdict, is_dataclass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest import engine as eng
from strategy.selector import (
    StrategyName, select_strategy, DEFAULT_PARAMS,
)

OUT = Path(__file__).resolve().parent
TARGET_DATES = ("2026-03-09", "2026-03-10")

leg_records: list[dict] = []
_orig_build_legs = eng._build_legs


def _capture_build_legs(rec_or_strategy, spx, sigma, params=DEFAULT_PARAMS):
    legs, dte = _orig_build_legs(rec_or_strategy, spx, sigma, params)
    strategy = rec_or_strategy.strategy if hasattr(rec_or_strategy, "strategy") else rec_or_strategy
    leg_records.append({
        "strategy": strategy.value,
        "spx": round(float(spx), 4),
        "sigma": round(float(sigma), 6),
        "dte": dte,
        "legs": [
            {"action": int(a), "is_call": bool(c), "strike": float(k),
             "dte": int(d), "qty": int(q)}
            for (a, c, k, d, q) in legs
        ],
    })
    return legs, dte


def _to_serialisable(obj):
    if is_dataclass(obj):
        return {k: _to_serialisable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serialisable(v) for v in obj]
    if hasattr(obj, "value") and hasattr(obj, "name"):
        return obj.value
    return obj


def main() -> None:
    assert DEFAULT_PARAMS.profit_target == 0.60, (
        f"SPEC-077 baseline expects profit_target=0.60, got {DEFAULT_PARAMS.profit_target}"
    )
    eng._build_legs = _capture_build_legs
    print(f"Running SPEC-077 baseline (profit_target={DEFAULT_PARAMS.profit_target}, 2023-01-01 → today, EOD)...")
    result = eng.run_backtest(start_date="2023-01-01", verbose=False)
    eng._build_legs = _orig_build_legs

    trades, metrics, signals = result.trades, result.metrics, result.signals
    print(f"  Trades: {len(trades)}  |  Signals: {len(signals)}")

    if trades:
        keys = [f for f in trades[0].__dataclass_fields__]
        with (OUT / "trade_log.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(keys)
            for t in trades:
                w.writerow([getattr(t, k).value if hasattr(getattr(t, k), "value")
                            else getattr(t, k) for k in keys])

    (OUT / "metrics.json").write_text(json.dumps(_to_serialisable(metrics), indent=2))

    if signals:
        keys = sorted({k for row in signals for k in row.keys()})
        with (OUT / "signals.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(keys)
            for row in signals:
                w.writerow([row.get(k, "") for k in keys])

    by_date = {row["date"]: row for row in signals}
    for d in TARGET_DATES:
        snap = by_date.get(d)
        if snap is None:
            print(f"  ! No signal row for {d}")
            continue
        (OUT / f"selector_dump_{d}.json").write_text(
            json.dumps(_to_serialisable(snap), indent=2)
        )

    IC_VALUES = (StrategyName.IRON_CONDOR_HV.value, StrategyName.IRON_CONDOR.value)
    target_strikes = {}
    for d in TARGET_DATES:
        snap = by_date.get(d)
        if snap is None:
            continue
        if snap.get("strategy") not in IC_VALUES:
            target_strikes[d] = {
                "strategy_chosen": snap.get("strategy"),
                "note": "Not an IC_HV/IC entry on this date — recording selector decision only.",
                "vix": snap.get("vix"), "spx": snap.get("spx"),
                "ivr": snap.get("ivr"), "ivp": snap.get("ivp"),
                "trend": snap.get("trend"),
            }
            continue
        spx_target = float(snap["spx"])
        match = next(
            (rec for rec in leg_records
             if rec["strategy"] in IC_VALUES
             and abs(rec["spx"] - spx_target) < 0.5),
            None,
        )
        target_strikes[d] = {
            "strategy_chosen": snap["strategy"],
            "spx": spx_target, "vix": snap["vix"],
            "build_legs_call": match,
        }

    (OUT / "2026-03-strikes.json").write_text(
        json.dumps(target_strikes, indent=2)
    )

    print(f"  Wrote outputs to {OUT}")
    print("Done.")


if __name__ == "__main__":
    main()
