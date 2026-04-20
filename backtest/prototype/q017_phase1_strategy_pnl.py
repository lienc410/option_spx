"""
Q017 Phase 1: Replace SPX forward-return proxy with actual strategy PnL,
and re-test after excluding the 2020-03 / 2025-04 / 2026-04 events.

Scope (Phase 1 only):
  T1.1 — lift each HIGH_VOL aftermath gate and measure new trades' PnL
  T1.2 — exclude 2020-03, 2025-04, 2026-04 and recompute

NO Tier 2 / Tier 3. No gate-change recommendations.

Method:
  - Variant A: sel.IVP63_BCS_BLOCK = 999  (lift ivp63>=70 gate)
  - Variant B: monkey-patch engine._vix_classify_trend to never return RISING
  - Variant C: both lifted simultaneously
  For each variant:
    - new_trades = {trades in variant} − {trades in baseline}
    - tag aftermath / non-aftermath using same definition as Q017 study
    - report PnL by (variant × aftermath × strategy)

Exclusion events (T1.2):
  2020-03-15 .. 2020-05-31   COVID
  2025-04-01 .. 2025-05-31   tariff
  2026-03-15 .. 2026-04-30   recent

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q017_phase1_strategy_pnl
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
import backtest.engine as engine_mod
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci
from signals.vix_regime import Trend

START = "2000-01-01"

PEAK_VIX_MIN = 28.0
PEAK_LOOKBACK = 10
OFF_PEAK_MIN_PCT = 0.05

EXCLUDE_EVENTS = [
    ("2020-03 COVID",  "2020-03-15", "2020-05-31"),
    ("2025-04 tariff", "2025-04-01", "2025-05-31"),
    ("2026-04 recent", "2026-03-15", "2026-04-30"),
]

HV_STRATS = {"Bull Put Spread (High Vol)", "Iron Condor (High Vol)", "Bear Call Spread (High Vol)"}
SHORT = {
    "Bull Put Spread (High Vol)": "BPS_HV",
    "Iron Condor (High Vol)":     "IC_HV",
    "Bear Call Spread (High Vol)":"BCS_HV",
}


def _aftermath_indices(signals: list[dict]) -> set[str]:
    """Return set of aftermath date strings (same definition as Q017)."""
    aftermath: set[str] = set()
    for i, s in enumerate(signals):
        lo = max(0, i - PEAK_LOOKBACK)
        window = signals[lo:i + 1]
        if not window:
            continue
        peak = max(x["vix"] for x in window)
        if peak < PEAK_VIX_MIN:
            continue
        if s["vix"] >= peak * (1 - OFF_PEAK_MIN_PCT):
            continue
        aftermath.add(s["date"])
    return aftermath


def _identity(t: Trade) -> tuple:
    return (t.entry_date, t.strategy.value, round(t.entry_spx, 2), round(t.entry_vix, 2))


def _closed(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.exit_reason != "end_of_backtest"]


def _stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "mean": 0, "total": 0, "win%": 0, "sharpe": 0.0, "ci": (None, None)}
    p = np.array([t.exit_pnl for t in trades])
    n = len(p)
    mu = float(p.mean())
    sd = float(p.std(ddof=1)) if n > 1 else 0.0
    ci = bootstrap_ci(p.tolist()) if n >= 5 else {"ci_lo": float("nan"), "ci_hi": float("nan")}
    return {
        "n": n,
        "mean": round(mu),
        "total": int(p.sum()),
        "win%": round((p > 0).mean() * 100, 1),
        "sharpe": round(mu / sd, 2) if sd > 0 else 0.0,
        "ci": (ci["ci_lo"], ci["ci_hi"]),
    }


def _in_excluded_event(date: str) -> bool:
    for _, lo, hi in EXCLUDE_EVENTS:
        if lo <= date <= hi:
            return True
    return False


def _run_variant(name: str, patch_fn) -> list[Trade]:
    print(f"  Running {name} ...")
    unpatch = patch_fn()
    try:
        bt = run_backtest(start_date=START, verbose=False)
    finally:
        unpatch()
    return _closed(bt.trades)


def _patch_none():
    return lambda: None


def _patch_ivp63_lifted():
    orig = sel.IVP63_BCS_BLOCK
    sel.IVP63_BCS_BLOCK = 999
    def undo():
        sel.IVP63_BCS_BLOCK = orig
    return undo


def _patch_vix_rising_off():
    orig = engine_mod._vix_classify_trend
    engine_mod._vix_classify_trend = lambda a, b: Trend.FLAT
    def undo():
        engine_mod._vix_classify_trend = orig
    return undo


def _patch_both():
    u1 = _patch_ivp63_lifted()
    u2 = _patch_vix_rising_off()
    def undo():
        u2()
        u1()
    return undo


def _fmt_stats(tag: str, st: dict) -> str:
    ci_lo, ci_hi = st["ci"]
    if ci_lo is None or (isinstance(ci_lo, float) and np.isnan(ci_lo)):
        ci_s = "—"
        sig = ""
    else:
        ci_s = f"[${round(ci_lo):,}, ${round(ci_hi):,}]"
        sig = "SIG+" if ci_lo > 0 else ("SIG-" if ci_hi < 0 else "n.s.")
    return (f"    {tag:<20} n={st['n']:>4}  total=${st['total']:>+9,}  "
            f"avg=${st['mean']:>+6,}  win={st['win%']:>5.1f}%  "
            f"sharpe={st['sharpe']:>+5.2f}  CI95 {ci_s} {sig}")


def run_study():
    # ── Baseline + aftermath date set ──────────────────────────────────
    print("  Loading baseline backtest + signals ...")
    bt_base = run_backtest(start_date=START, verbose=False)
    baseline_closed = _closed(bt_base.trades)
    baseline_ids = {_identity(t) for t in baseline_closed}
    aftermath_dates = _aftermath_indices(bt_base.signals)
    print(f"  baseline trades (closed): {len(baseline_closed)}")
    print(f"  aftermath dates: {len(aftermath_dates)}")

    # ── Variants ──────────────────────────────────────────────────────
    variants = [
        ("A: ivp63 gate lifted",        _patch_ivp63_lifted),
        ("B: VIX_RISING gate lifted",   _patch_vix_rising_off),
        ("C: both gates lifted",        _patch_both),
    ]

    results = {}
    for name, patch_fn in variants:
        trades = _run_variant(name, patch_fn)
        new_trades = [t for t in trades if _identity(t) not in baseline_ids]
        results[name] = new_trades

    # ── Report per variant ─────────────────────────────────────────────
    for name, new_trades in results.items():
        print(f"\n{'=' * 90}")
        print(f"  {name}")
        print(f"{'=' * 90}")
        print(f"  new trades (not in baseline): {len(new_trades)}")

        hv_trades = [t for t in new_trades if t.strategy.value in HV_STRATS]
        aftermath = [t for t in hv_trades if t.entry_date in aftermath_dates]
        non_aftermath = [t for t in hv_trades if t.entry_date not in aftermath_dates]

        print(f"  HV-strategy new trades: {len(hv_trades)}")
        print(f"    aftermath entries:     {len(aftermath)}")
        print(f"    non-aftermath entries: {len(non_aftermath)}")

        # T1.1 — aftermath vs non-aftermath (all HV new trades)
        print(f"\n  T1.1 — aftermath vs non-aftermath (HV new trades):")
        print(_fmt_stats("aftermath", _stats(aftermath)))
        print(_fmt_stats("non-aftermath", _stats(non_aftermath)))

        # Per-strategy breakdown (aftermath)
        print(f"\n  By strategy (aftermath entries):")
        for strat_name, short in SHORT.items():
            t_list = [t for t in aftermath if t.strategy.value == strat_name]
            if t_list:
                print(_fmt_stats(short, _stats(t_list)))

        # T1.2 — exclude 2020-03 / 2025-04 / 2026-04
        aftermath_t12 = [t for t in aftermath if not _in_excluded_event(t.entry_date)]
        non_aftermath_t12 = [t for t in non_aftermath if not _in_excluded_event(t.entry_date)]
        excluded_count = len(aftermath) - len(aftermath_t12)

        print(f"\n  T1.2 — exclude {len(EXCLUDE_EVENTS)} events "
              f"({excluded_count} aftermath trades removed):")
        print(_fmt_stats("aftermath (T1.2)", _stats(aftermath_t12)))
        print(_fmt_stats("non-aftermath (T1.2)", _stats(non_aftermath_t12)))

        # Per-strategy breakdown (aftermath post-exclusion)
        print(f"\n  By strategy (aftermath entries, T1.2):")
        for strat_name, short in SHORT.items():
            t_list = [t for t in aftermath_t12 if t.strategy.value == strat_name]
            if t_list:
                print(_fmt_stats(short, _stats(t_list)))

    # ── Variant C system-level check ─────────────────────────────────────
    print(f"\n{'=' * 90}")
    print(f"  VARIANT C SYSTEM-LEVEL (both gates lifted)")
    print(f"{'=' * 90}")
    name_c = "C: both gates lifted"
    # Re-run to capture full trades (we only kept new ones)
    u = _patch_both()
    try:
        bt_c = run_backtest(start_date=START, verbose=False)
    finally:
        u()
    sys_base = _stats(baseline_closed)
    sys_c = _stats(_closed(bt_c.trades))
    print(_fmt_stats("baseline", sys_base))
    print(_fmt_stats("variant C", sys_c))
    print(f"\n  Delta: n {sys_c['n'] - sys_base['n']:+d}, "
          f"total ${sys_c['total'] - sys_base['total']:+,}, "
          f"avg ${sys_c['mean'] - sys_base['mean']:+,}, "
          f"sharpe {sys_c['sharpe'] - sys_base['sharpe']:+.2f}")


if __name__ == "__main__":
    run_study()
