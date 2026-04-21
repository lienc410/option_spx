"""
Q018 Phase 2-C — Unlimited IC_HV slots (only BP ceiling gates).

Goes one step beyond Phase 2-A/B: instead of capping IC_HV concurrent
positions at 2, remove the slot cap entirely for IC_HV. The only thing
stopping a 3rd/4th/Nth IC_HV is the existing BP ceiling (50% in HIGH_VOL).

With bp_target = 7% per HIGH_VOL position, and ceiling = 50%:
  theoretical max concurrent HIGH_VOL positions = 50% / 7% ≈ 7

Four-way comparison:
  - baseline           (single slot, OFF_PEAK 0.05)
  - A_unlimited        (IC_HV unlimited, OFF_PEAK 0.05)  — BP-only gated
  - A+B combo          (IC_HV ≤ 2, OFF_PEAK 0.10)       — from Phase 2-B
  - A_unlimited+B      (IC_HV unlimited, OFF_PEAK 0.10) — BP-only + tight

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q018_phase2c_unlimited
"""

from __future__ import annotations

import inspect

import numpy as np

import backtest.engine as engine_mod
import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from strategy.selector import StrategyName

START = "2000-01-01"


# ──────────────────────────────────────────────────────────────────
# Build patched run_backtest variants
# ──────────────────────────────────────────────────────────────────

_ORIG_LINE = "_already_open = any(p.strategy == rec.strategy for p in positions)"


def _build_patched(mode: str):
    """mode: 'cap2' = IC_HV ≤ 2, 'unlimited' = IC_HV no cap (BP gated only)."""
    if mode == "cap2":
        replacement = (
            "_already_open = ("
            "(sum(1 for p in positions if p.strategy == rec.strategy) >= 2) "
            "if rec.strategy == StrategyName.IRON_CONDOR_HV "
            "else any(p.strategy == rec.strategy for p in positions)"
            ")"
        )
    elif mode == "unlimited":
        replacement = (
            "_already_open = ("
            "False "  # IC_HV: never block by slot count
            "if rec.strategy == StrategyName.IRON_CONDOR_HV "
            "else any(p.strategy == rec.strategy for p in positions)"
            ")"
        )
    else:
        raise ValueError(mode)
    src = inspect.getsource(engine_mod.run_backtest)
    assert _ORIG_LINE in src
    patched = src.replace(_ORIG_LINE, replacement)
    ns = dict(engine_mod.__dict__)
    exec(patched, ns)
    return ns["run_backtest"]


# ──────────────────────────────────────────────────────────────────
# Stats helpers
# ──────────────────────────────────────────────────────────────────

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


def _fmt(tag, s):
    return (f"    {tag:<26} n={s['n']:>4}  total=${s['total']:>+10,}  "
            f"avg=${s['mean']:>+6,}  win={s['win%']:>5.1f}%  sharpe={s['sharpe']:>+5.2f}")


def _max_dd(trades):
    if not trades:
        return 0.0
    ts = sorted(trades, key=lambda t: t.exit_date)
    cum = np.cumsum([t.exit_pnl for t in ts])
    peak = np.maximum.accumulate(cum)
    return float((cum - peak).min())


def _ic_hv(trades):
    return [t for t in trades if t.strategy.value == StrategyName.IRON_CONDOR_HV.value]


def _run_variant(*, run_fn, off_peak):
    orig = sel.AFTERMATH_OFF_PEAK_PCT
    sel.AFTERMATH_OFF_PEAK_PCT = off_peak
    try:
        return _closed(run_fn(start_date=START, verbose=False).trades)
    finally:
        sel.AFTERMATH_OFF_PEAK_PCT = orig


def _max_concurrent_ic_hv(trades):
    """Compute max concurrent IC_HV positions via entry/exit sweep."""
    events = []
    for t in _ic_hv(trades):
        events.append((t.entry_date, +1))
        events.append((t.exit_date, -1))
    events.sort()
    cur = 0
    peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return peak


# ──────────────────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────────────────

def run_study():
    print("Q018 Phase 2-C — Unlimited IC_HV slots (BP-only gating)")
    print()

    run_cap2 = _build_patched("cap2")
    run_unlim = _build_patched("unlimited")

    variants = [
        ("baseline",              run_backtest, 0.05),
        ("A cap=2",               run_cap2,     0.05),
        ("A unlimited",           run_unlim,    0.05),
        ("A cap=2 + B",           run_cap2,     0.10),
        ("A unlimited + B",       run_unlim,    0.10),
    ]

    results = {}
    for name, fn, op in variants:
        print(f"  Running {name} (off_peak={op}) ...")
        results[name] = _run_variant(run_fn=fn, off_peak=op)

    print()
    print("=" * 105)
    print("  SYSTEM-LEVEL")
    print("=" * 105)
    base = _stats(results["baseline"])
    base_dd = _max_dd(results["baseline"])
    for name, _, _ in variants:
        s = _stats(results[name])
        dd = _max_dd(results[name])
        mx = _max_concurrent_ic_hv(results[name])
        print(_fmt(name, s) + f"  dd=${dd:+,.0f}  max_concurrent_IC_HV={mx}")

    print()
    print("  Deltas vs baseline:")
    for name, _, _ in variants:
        if name == "baseline":
            continue
        s = _stats(results[name])
        dd = _max_dd(results[name])
        dd_pct = ((dd - base_dd) / abs(base_dd)) * 100 if base_dd else 0.0
        print(f"    {name:<22}  n {s['n'] - base['n']:+4d}  "
              f"total ${s['total'] - base['total']:>+9,}  "
              f"sharpe {s['sharpe'] - base['sharpe']:+.2f}  "
              f"MaxDD ${dd - base_dd:+,.0f} ({dd_pct:+.0f}%)")

    # IC_HV subset
    print()
    print("=" * 105)
    print("  IC_HV SUBSET")
    print("=" * 105)
    for name, _, _ in variants:
        s = _stats(_ic_hv(results[name]))
        print(_fmt(name + " IC_HV", s))

    # Disaster IC_HV breakdown
    print()
    print("=" * 105)
    print("  DISASTER-WINDOW IC_HV TRADES (2008-09..12, 2020-02..04, 2025-04..05)")
    print("=" * 105)
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

    for name, _, _ in variants:
        ic = _ic_hv(results[name])
        disaster_trades = [t for t in ic if _in_disaster(t.entry_date)]
        if not disaster_trades:
            print(f"\n  {name}: no disaster-window IC_HV trades")
            continue
        net = sum(t.exit_pnl for t in disaster_trades)
        wins = sum(1 for t in disaster_trades if t.exit_pnl > 0)
        print(f"\n  {name}: {len(disaster_trades)} disaster IC_HV entries, "
              f"{wins}W/{len(disaster_trades)-wins}L, net ${net:+,.0f}")
        for t in sorted(disaster_trades, key=lambda x: x.entry_date):
            print(f"    {t.entry_date} → {t.exit_date}  "
                  f"VIX {t.entry_vix:>5.1f}  "
                  f"pnl=${t.exit_pnl:>+9,.0f}  ({t.exit_reason})")

    # Verdict
    print()
    print("=" * 105)
    print("  VERDICT TABLE")
    print("=" * 105)
    print(f"  {'Variant':<22} {'n':>4} {'Total PnL':>13} {'Sharpe':>8} "
          f"{'MaxDD':>12} {'DD Δ%':>8}  {'MaxConc':>8}")
    for name, _, _ in variants:
        s = _stats(results[name])
        dd = _max_dd(results[name])
        dd_pct = ((dd - base_dd) / abs(base_dd)) * 100 if base_dd else 0.0
        mx = _max_concurrent_ic_hv(results[name])
        marker = "  ← base" if name == "baseline" else ""
        print(f"  {name:<22} {s['n']:>4} {s['total']:>+13,} {s['sharpe']:>+8.2f} "
              f"{dd:>+12,.0f} {dd_pct:>+7.0f}% {mx:>8}{marker}")


if __name__ == "__main__":
    run_study()
