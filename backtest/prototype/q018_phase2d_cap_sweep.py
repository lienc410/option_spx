"""
Q018 Phase 2-D — Cap sweep for IC_HV concurrent positions + B filter.

Sweep concurrent IC_HV cap ∈ {1 (baseline), 2, 3, 4, 5, 7 (BP-max)} with
B filter (OFF_PEAK_PCT = 0.10) held constant.

Goal: find risk-adjusted optimum between cap=2 and cap=unlimited.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q018_phase2d_cap_sweep
"""

from __future__ import annotations

import inspect

import numpy as np

import backtest.engine as engine_mod
import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from strategy.selector import StrategyName

START = "2000-01-01"
OFF_PEAK_B = 0.10  # B filter

_ORIG_LINE = "_already_open = any(p.strategy == rec.strategy for p in positions)"


def _build_patched(cap: int):
    """Cap IC_HV concurrent at `cap`. cap=1 → baseline behavior for IC_HV."""
    if cap == 1:
        return run_backtest  # baseline (unmodified)
    replacement = (
        f"_already_open = ("
        f"(sum(1 for p in positions if p.strategy == rec.strategy) >= {cap}) "
        f"if rec.strategy == StrategyName.IRON_CONDOR_HV "
        f"else any(p.strategy == rec.strategy for p in positions)"
        f")"
    )
    src = inspect.getsource(engine_mod.run_backtest)
    assert _ORIG_LINE in src
    patched = src.replace(_ORIG_LINE, replacement)
    ns = dict(engine_mod.__dict__)
    exec(patched, ns)
    return ns["run_backtest"]


def _closed(trades):
    return [t for t in trades if t.exit_reason != "end_of_backtest"]


def _stats(trades):
    if not trades:
        return {"n": 0, "mean": 0, "total": 0, "win%": 0.0, "sharpe": 0.0}
    p = np.array([t.exit_pnl for t in trades])
    n = len(p)
    mu = float(p.mean())
    sd = float(p.std(ddof=1)) if n > 1 else 0.0
    return {"n": n, "mean": round(mu), "total": int(p.sum()),
            "win%": round((p > 0).mean() * 100, 1),
            "sharpe": round(mu / sd, 2) if sd > 0 else 0.0}


def _max_dd(trades):
    if not trades:
        return 0.0
    ts = sorted(trades, key=lambda t: t.exit_date)
    cum = np.cumsum([t.exit_pnl for t in ts])
    peak = np.maximum.accumulate(cum)
    return float((cum - peak).min())


def _ic_hv(trades):
    return [t for t in trades if t.strategy.value == StrategyName.IRON_CONDOR_HV.value]


def _max_concurrent_ic_hv(trades):
    events = []
    for t in _ic_hv(trades):
        events.append((t.entry_date, +1))
        events.append((t.exit_date, -1))
    events.sort()
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return peak


def _run(run_fn, off_peak):
    orig = sel.AFTERMATH_OFF_PEAK_PCT
    sel.AFTERMATH_OFF_PEAK_PCT = off_peak
    try:
        return _closed(run_fn(start_date=START, verbose=False).trades)
    finally:
        sel.AFTERMATH_OFF_PEAK_PCT = orig


def run_study():
    print("Q018 Phase 2-D — Cap sweep {1, 2, 3, 4, 5, 7} with B filter (OFF_PEAK=0.10)")
    print("(plus an unfiltered baseline reference at top)")
    print()

    # Pure baseline (single slot, OFF_PEAK 0.05) for DD / Sharpe reference
    print("  Running baseline (cap=1, OFF_PEAK=0.05) ...")
    baseline_trades = _run(run_backtest, 0.05)

    caps = [1, 2, 3, 4, 5, 7]
    results = {}
    for cap in caps:
        print(f"  Running cap={cap} + B (OFF_PEAK={OFF_PEAK_B}) ...")
        results[cap] = _run(_build_patched(cap), OFF_PEAK_B)

    base = _stats(baseline_trades)
    base_dd = _max_dd(baseline_trades)

    # ── Summary table ───────────────────────────────────────────────
    print()
    print("=" * 110)
    print(f"  VERDICT TABLE  (all use B filter OFF_PEAK=0.10; baseline row = cap=1, OFF_PEAK=0.05)")
    print("=" * 110)
    print(f"  {'Variant':<14} {'n':>4} {'Total PnL':>13} {'Sharpe':>8} "
          f"{'MaxDD':>12} {'DD Δ%':>7} {'PnL Δ':>10} {'MaxConc':>8} {'PnL/$DD':>8}")

    # baseline
    base_pnl_per_dd = base['total'] / abs(base_dd) if base_dd else 0
    print(f"  {'baseline':<14} {base['n']:>4} {base['total']:>+13,} {base['sharpe']:>+8.2f} "
          f"{base_dd:>+12,.0f} {'—':>7} {'—':>10} {1:>8} {base_pnl_per_dd:>+8.2f}  ← base")

    for cap in caps:
        s = _stats(results[cap])
        dd = _max_dd(results[cap])
        dd_pct = ((dd - base_dd) / abs(base_dd)) * 100 if base_dd else 0.0
        pnl_delta = s['total'] - base['total']
        mx = _max_concurrent_ic_hv(results[cap])
        pnl_per_dd = s['total'] / abs(dd) if dd else 0
        label = f"cap={cap}+B"
        print(f"  {label:<14} {s['n']:>4} {s['total']:>+13,} {s['sharpe']:>+8.2f} "
              f"{dd:>+12,.0f} {dd_pct:>+6.0f}% {pnl_delta:>+10,} {mx:>8} {pnl_per_dd:>+8.2f}")

    # ── Marginal analysis: cap=N vs cap=N-1 ────────────────────────
    print()
    print("=" * 110)
    print("  MARGINAL: what does each +1 cap buy? (cap=N minus cap=N-1, both with B filter)")
    print("=" * 110)
    prev = None
    for cap in caps:
        s = _stats(results[cap])
        dd = _max_dd(results[cap])
        if prev is None:
            prev = (s, dd, cap)
            continue
        ps, pdd, pc = prev
        d_n = s['n'] - ps['n']
        d_total = s['total'] - ps['total']
        d_sharpe = s['sharpe'] - ps['sharpe']
        d_dd = dd - pdd
        # Marginal PnL/DD: $ earned per $ additional drawdown
        marginal = d_total / abs(d_dd) if d_dd < 0 else float('inf')
        marginal_str = f"{marginal:+.2f}" if marginal != float('inf') else "inf"
        print(f"  cap={pc}+B → cap={cap}+B: "
              f"n {d_n:+d}, PnL ${d_total:+,}, "
              f"Sharpe {d_sharpe:+.2f}, "
              f"MaxDD ${d_dd:+,.0f}, "
              f"$earned/$DD = {marginal_str}")
        prev = (s, dd, cap)

    # ── Disaster window summary per cap ─────────────────────────────
    print()
    print("=" * 110)
    print("  DISASTER WINDOWS (2008-09..12, 2020-02..04, 2025-04..05)")
    print("=" * 110)
    disaster_windows = [
        ("2008 GFC",    "2008-09-01", "2008-12-31"),
        ("2020 COVID",  "2020-02-20", "2020-04-30"),
        ("2025 Tariff", "2025-04-01", "2025-05-31"),
    ]
    def _in_disaster(date):
        for name, lo, hi in disaster_windows:
            if lo <= date <= hi:
                return name
        return None

    for cap in caps:
        ic = _ic_hv(results[cap])
        disaster = [t for t in ic if _in_disaster(t.entry_date)]
        if not disaster:
            continue
        net = sum(t.exit_pnl for t in disaster)
        wins = sum(1 for t in disaster if t.exit_pnl > 0)
        by_event: dict[str, list[float]] = {}
        for t in disaster:
            ev = _in_disaster(t.entry_date)
            by_event.setdefault(ev, []).append(t.exit_pnl)
        bd = ", ".join(f"{ev}={len(pls)}×(${sum(pls):+,.0f})" for ev, pls in by_event.items())
        print(f"  cap={cap}+B: n={len(disaster)}, {wins}W/{len(disaster)-wins}L, "
              f"net ${net:+,.0f}  [{bd}]")

    # ── 2026-03 trigger case ───────────────────────────────────────
    print()
    print("=" * 110)
    print("  2026-03 DOUBLE-SPIKE CAPTURE")
    print("=" * 110)
    for cap in caps:
        ic = _ic_hv(results[cap])
        q2 = [t for t in ic if "2026-03" <= t.entry_date <= "2026-04-15"]
        pnl_sum = sum(t.exit_pnl for t in q2)
        dates = ", ".join(f"{t.entry_date}(${t.exit_pnl:+,.0f})" for t in q2)
        print(f"  cap={cap}+B: {len(q2)} entries, net ${pnl_sum:+,.0f}  [{dates}]")

    # ── Optimum recommendation ─────────────────────────────────────
    print()
    print("=" * 110)
    print("  OPTIMUM BY METRIC")
    print("=" * 110)
    best_sharpe = max(caps, key=lambda c: _stats(results[c])['sharpe'])
    best_pnl = max(caps, key=lambda c: _stats(results[c])['total'])
    best_dd = max(caps, key=lambda c: _max_dd(results[c]))  # max = least negative
    best_pnl_per_dd = max(caps,
                          key=lambda c: _stats(results[c])['total'] / abs(_max_dd(results[c]))
                          if _max_dd(results[c]) else 0)
    print(f"  Best Sharpe:       cap={best_sharpe}+B  (Sharpe {_stats(results[best_sharpe])['sharpe']:+.2f})")
    print(f"  Best total PnL:    cap={best_pnl}+B  (${_stats(results[best_pnl])['total']:+,})")
    print(f"  Smallest MaxDD:    cap={best_dd}+B  (${_max_dd(results[best_dd]):+,.0f})")
    print(f"  Best PnL/$DD:      cap={best_pnl_per_dd}+B  "
          f"(${_stats(results[best_pnl_per_dd])['total'] / abs(_max_dd(results[best_pnl_per_dd])):+.2f})")


if __name__ == "__main__":
    run_study()
