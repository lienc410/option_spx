"""
Q018 Phase 2-B — Combined Variant A + B: multi-slot + tightened OFF_PEAK.

Hypothesis:
  - Variant B (OFF_PEAK 0.05 → 0.10) filters out shallower aftermath
    triggers → removes some weak entries, especially early in disaster
    continuation where VIX has only modestly pulled back
  - Variant A (allow 2 concurrent IC_HV) captures the real double-spike
    alpha (2026-03 case, plus any similar patterns)
  - Combined: fewer BUT stronger signals, with 2-slot capacity for real
    double-dip cases → should reduce MaxDD damage from A while keeping
    most of the extra PnL

Four-way comparison:
  - baseline        (single slot, OFF_PEAK 0.05)
  - variant A       (multi slot,  OFF_PEAK 0.05)
  - variant B       (single slot, OFF_PEAK 0.10)
  - variant A+B     (multi slot,  OFF_PEAK 0.10)

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q018_phase2b_combo
"""

from __future__ import annotations

import numpy as np

import backtest.engine as engine_mod
import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from strategy.selector import StrategyName

from backtest.prototype.q018_phase2a_full_engine import _build_patched_run_backtest

START = "2000-01-01"


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _closed(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.exit_reason != "end_of_backtest"]


def _stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "mean": 0, "total": 0, "win%": 0.0, "sharpe": 0.0}
    p = np.array([t.exit_pnl for t in trades])
    n = len(p)
    mu = float(p.mean())
    sd = float(p.std(ddof=1)) if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mu),
        "total": int(p.sum()),
        "win%": round((p > 0).mean() * 100, 1),
        "sharpe": round(mu / sd, 2) if sd > 0 else 0.0,
    }


def _fmt(tag: str, s: dict) -> str:
    return (f"    {tag:<22} n={s['n']:>4}  total=${s['total']:>+10,}  "
            f"avg=${s['mean']:>+6,}  win={s['win%']:>5.1f}%  sharpe={s['sharpe']:>+5.2f}")


def _max_dd(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    ts = sorted(trades, key=lambda t: t.exit_date)
    cum = np.cumsum([t.exit_pnl for t in ts])
    peak = np.maximum.accumulate(cum)
    return float((cum - peak).min())


def _ic_hv(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.strategy.value == StrategyName.IRON_CONDOR_HV.value]


def _run_variant(
    *,
    multi_slot: bool,
    off_peak: float,
    patched_run_backtest,
) -> list[Trade]:
    orig_off_peak = sel.AFTERMATH_OFF_PEAK_PCT
    sel.AFTERMATH_OFF_PEAK_PCT = off_peak
    try:
        fn = patched_run_backtest if multi_slot else run_backtest
        bt = fn(start_date=START, verbose=False)
        return _closed(bt.trades)
    finally:
        sel.AFTERMATH_OFF_PEAK_PCT = orig_off_peak


def run_study() -> None:
    print("Q018 Phase 2-B — Combined Variant A + B")
    print()
    print("  Building patched run_backtest (IC_HV up to 2 concurrent) ...")
    patched_run_backtest = _build_patched_run_backtest()

    variants = [
        ("baseline",      False, 0.05),
        ("variant A",     True,  0.05),
        ("variant B",     False, 0.10),
        ("variant A+B",   True,  0.10),
    ]

    results: dict[str, list[Trade]] = {}
    for name, multi, off_peak in variants:
        print(f"  Running {name} (multi_slot={multi}, off_peak={off_peak}) ...")
        results[name] = _run_variant(
            multi_slot=multi,
            off_peak=off_peak,
            patched_run_backtest=patched_run_backtest,
        )

    # ── System-level table ─────────────────────────────────────────
    print()
    print("=" * 100)
    print("  SYSTEM-LEVEL  (all closed trades, not just IC_HV)")
    print("=" * 100)
    base_stats = _stats(results["baseline"])
    base_dd = _max_dd(results["baseline"])
    for name, _, _ in variants:
        s = _stats(results[name])
        dd = _max_dd(results[name])
        print(_fmt(name, s) + f"  dd=${dd:+,.0f}")

    # Deltas vs baseline
    print()
    print("  Deltas vs baseline:")
    for name, _, _ in variants:
        if name == "baseline":
            continue
        s = _stats(results[name])
        dd = _max_dd(results[name])
        dd_delta = dd - base_dd
        dd_pct = (dd_delta / abs(base_dd)) * 100 if base_dd else 0.0
        print(f"    {name:<18}  "
              f"n {s['n'] - base_stats['n']:+4d}  "
              f"total ${s['total'] - base_stats['total']:>+9,}  "
              f"sharpe {s['sharpe'] - base_stats['sharpe']:+.2f}  "
              f"MaxDD ${dd_delta:+,.0f} ({dd_pct:+.0f}%)")

    # ── IC_HV subset ───────────────────────────────────────────────
    print()
    print("=" * 100)
    print("  IC_HV SUBSET")
    print("=" * 100)
    base_ic = _stats(_ic_hv(results["baseline"]))
    for name, _, _ in variants:
        s = _stats(_ic_hv(results[name]))
        print(_fmt(name + " IC_HV", s))

    # ── Disaster trades breakdown ──────────────────────────────────
    print()
    print("=" * 100)
    print("  DISASTER-WINDOW IC_HV TRADES (entry in 2008-09..10, 2020-03..04, 2025-04..05)")
    print("=" * 100)
    disaster_windows = [
        ("2008 GFC",    "2008-09-01", "2008-12-31"),
        ("2020 COVID",  "2020-02-20", "2020-04-30"),
        ("2025 Tariff", "2025-04-01", "2025-05-31"),
    ]

    def _in_disaster(date: str) -> str | None:
        for name, lo, hi in disaster_windows:
            if lo <= date <= hi:
                return name
        return None

    for name, _, _ in variants:
        ic_trades = _ic_hv(results[name])
        disaster_trades = [(t, _in_disaster(t.entry_date)) for t in ic_trades
                           if _in_disaster(t.entry_date)]
        if not disaster_trades:
            print(f"\n  {name}: no disaster-window IC_HV trades")
            continue
        net = sum(t.exit_pnl for t, _ in disaster_trades)
        wins = sum(1 for t, _ in disaster_trades if t.exit_pnl > 0)
        print(f"\n  {name}: {len(disaster_trades)} disaster IC_HV entries, "
              f"{wins}W/{len(disaster_trades)-wins}L, net ${net:+,.0f}")
        for t, label in sorted(disaster_trades, key=lambda x: x[0].entry_date):
            print(f"    {t.entry_date} → {t.exit_date}  "
                  f"VIX {t.entry_vix:>5.1f}  "
                  f"pnl=${t.exit_pnl:>+9,.0f}  ({t.exit_reason})  [{label}]")

    # ── 2026-03 trigger case check ─────────────────────────────────
    print()
    print("=" * 100)
    print("  2026-03 TRIGGER CASE (PM's original question)")
    print("=" * 100)
    for name, _, _ in variants:
        ic = _ic_hv(results[name])
        q2_trades = [t for t in ic if "2026-03" <= t.entry_date <= "2026-04-15"]
        print(f"\n  {name}: {len(q2_trades)} IC_HV entries in 2026-03..04-15")
        for t in sorted(q2_trades, key=lambda x: x.entry_date):
            print(f"    {t.entry_date} → {t.exit_date}  "
                  f"VIX {t.entry_vix:>5.1f}  "
                  f"pnl=${t.exit_pnl:>+9,.0f}  ({t.exit_reason})")

    # ── Final verdict table ────────────────────────────────────────
    print()
    print("=" * 100)
    print("  VERDICT TABLE")
    print("=" * 100)
    print(f"  {'Variant':<14} {'n':>6} {'Total PnL':>14} {'Sharpe':>8} "
          f"{'MaxDD':>12} {'MaxDD Δ%':>10}")
    for name, _, _ in variants:
        s = _stats(results[name])
        dd = _max_dd(results[name])
        dd_pct = ((dd - base_dd) / abs(base_dd)) * 100 if base_dd else 0.0
        baseline_marker = "  ← base" if name == "baseline" else ""
        print(f"  {name:<14} {s['n']:>6} {s['total']:>+14,} {s['sharpe']:>+8.2f} "
              f"{dd:>+12,.0f} {dd_pct:>+9.0f}%{baseline_marker}")


if __name__ == "__main__":
    run_study()
