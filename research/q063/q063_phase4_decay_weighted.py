"""Q063 Phase 4 — Decay-Weighted + Recent-Window Review.

PM hypothesis revisit: full-sample analysis (Phase 3) rejected A, but PM's
intuition came from recent low-VIX regime (2023-2026). Phase 4 tests:

  1. Decay-weighted total P&L (half-life 3y / 5y / 10y, ref=2026-05-11)
     — does giving recent trades more weight change A vs baseline ranking?
  2. Recent-window cuts:
     - last 2y (2024-2026)
     - last 3y (2023-2026)
     - last 5y (2021-2026)
     — does A win when restricted to recent window?
  3. Per-year P&L attribution (BL vs A) — find which years drive the divergence
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest
from strategy.selector import IVSignal, Regime, StrategyName

START = "2007-01-01"
END = "2026-05-10"
ACCOUNT = 150_000.0
REF_DATE = pd.Timestamp("2026-05-11")


def _make_patcher(gate_fn, base_select):
    BPS = StrategyName.BULL_PUT_SPREAD
    def patched(vix, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = base_select(vix, iv, trend, params)
        if rec.strategy != BPS:
            return rec
        from strategy.selector import _effective_iv_signal, _reduce_wait
        if not (vix.regime == Regime.NORMAL
                and _effective_iv_signal(iv) == IVSignal.NEUTRAL
                and trend.signal.value == "BULLISH"):
            return rec
        if gate_fn(vix.vix, iv.iv_percentile):
            return _reduce_wait(
                f"gate blocks (VIX={vix.vix:.1f}, IVP={iv.iv_percentile:.0f})",
                vix, iv, trend, macro_warn=not trend.above_200,
                canonical_strategy=BPS.value, params=params,
            )
        return rec
    return patched


def _run_with_gate(gate_fn, base_select, orig_engine_select):
    sel.select_strategy = _make_patcher(gate_fn, base_select)
    engine_mod.select_strategy = sel.select_strategy
    try:
        return run_backtest(start_date=START, end_date=END,
                            account_size=ACCOUNT, verbose=False)
    finally:
        sel.select_strategy = base_select
        engine_mod.select_strategy = orig_engine_select


def _decay_weights(dates, half_life_y, ref_date=REF_DATE):
    if half_life_y == float('inf'):
        return np.ones(len(dates))
    lam = np.log(2) / half_life_y
    ys_ago = np.array([(ref_date - pd.Timestamp(d)).days / 365.25 for d in dates])
    return np.exp(-lam * ys_ago)


def _weighted_total_pnl(trades, half_life_y):
    if not trades:
        return 0.0, 0.0  # total, ESS
    dates = [t.entry_date for t in trades]
    pnls = np.array([t.exit_pnl for t in trades])
    w = _decay_weights(dates, half_life_y)
    w_norm = w / w.sum() * len(w)  # rescale so weighted sum has same scale as unweighted
    weighted_sum = float((w_norm * pnls).sum())
    ess = float(w.sum() ** 2 / (w ** 2).sum())
    return weighted_sum, ess


def _window_filter(trades, start, end):
    return [t for t in trades if start <= t.entry_date <= end]


def main():
    print("=" * 100)
    print("Q063 Phase 4 — Decay-Weighted + Recent-Window Review")
    print("=" * 100)

    orig_select = sel.select_strategy
    orig_engine_select = engine_mod.select_strategy
    orig_upper = sel.BPS_NNB_IVP_UPPER
    sel.BPS_NNB_IVP_UPPER = 999

    # Run baseline and A
    bt_bl = _run_with_gate(lambda v, ivp: ivp >= 55, orig_select, orig_engine_select)
    bt_a = _run_with_gate(lambda v, ivp: ivp >= (70 if v < 18 else 55),
                          orig_select, orig_engine_select)

    bps_bl = [t for t in bt_bl.trades if t.strategy.value == "Bull Put Spread"]
    bps_a = [t for t in bt_a.trades if t.strategy.value == "Bull Put Spread"]

    # ── Test 1: decay-weighted total P&L (BPS only) ──
    print(f"\n{'='*100}")
    print(f"Test 1 — Decay-weighted total BPS P&L (ref date: {REF_DATE.date()})")
    print(f"  Weighted-sum is rescaled to match unweighted scale (so values comparable)")
    print(f"{'='*100}")
    print(f"{'gate':<24} {'unweighted':>12} {'10y HL':>12} {'5y HL':>12} {'3y HL':>12} {'ESS@3y':>8}")
    print("-" * 100)
    for name, trades in [("baseline (IVP<55)", bps_bl), ("A (VIX<18 → IVP<70)", bps_a)]:
        cells = []
        ess3 = 0
        for hl in [float('inf'), 10.0, 5.0, 3.0]:
            total, ess = _weighted_total_pnl(trades, hl)
            cells.append(f"${total:>+10,.0f}")
            if hl == 3.0:
                ess3 = ess
        print(f"{name:<24} {cells[0]:>12} {cells[1]:>12} {cells[2]:>12} {cells[3]:>12} {ess3:>7.1f}")

    # Compute delta
    print(f"\nΔ (A - baseline) by decay half-life:")
    for hl_name, hl in [("unweighted", float('inf')), ("10y", 10.0), ("5y", 5.0), ("3y", 3.0)]:
        tot_a, _ = _weighted_total_pnl(bps_a, hl)
        tot_bl, _ = _weighted_total_pnl(bps_bl, hl)
        diff = tot_a - tot_bl
        verdict = "A wins" if diff > 0 else "BL wins"
        print(f"  {hl_name:<12}: ${diff:>+9,.0f}  ({verdict})")

    # ── Test 2: Recent-window cuts ──
    print(f"\n{'='*100}")
    print(f"Test 2 — Recent-window cuts (BPS only)")
    print(f"{'='*100}")
    windows = [
        ("last 5y (21-26)", "2021-01-01"),
        ("last 3y (23-26)", "2023-01-01"),
        ("last 2y (24-26)", "2024-01-01"),
        ("last 1y (25-26)", "2025-05-11"),
    ]
    print(f"{'window':<22} | {'BL n':>5} {'BL sum':>11} | {'A n':>5} {'A sum':>11} | Δsum")
    print("-" * 90)
    for wn, ws in windows:
        bl_w = _window_filter(bps_bl, ws, END)
        a_w = _window_filter(bps_a, ws, END)
        bl_pnl = sum(t.exit_pnl for t in bl_w)
        a_pnl = sum(t.exit_pnl for t in a_w)
        diff = a_pnl - bl_pnl
        verdict = " ✓ A" if diff > 0 else " ✗ A loses" if diff < 0 else " tied"
        print(f"{wn:<22} | {len(bl_w):>5d} ${bl_pnl:>+9,.0f} | "
              f"{len(a_w):>5d} ${a_pnl:>+9,.0f} | ${diff:>+8,.0f}{verdict}")

    # ── Test 3: Per-year P&L attribution ──
    print(f"\n{'='*100}")
    print(f"Test 3 — Per-year BPS P&L attribution")
    print(f"{'='*100}")
    by_year_bl = defaultdict(lambda: [0, 0.0])  # n, sum
    by_year_a = defaultdict(lambda: [0, 0.0])
    for t in bps_bl:
        y = t.entry_date[:4]
        by_year_bl[y][0] += 1
        by_year_bl[y][1] += t.exit_pnl
    for t in bps_a:
        y = t.entry_date[:4]
        by_year_a[y][0] += 1
        by_year_a[y][1] += t.exit_pnl

    years_sorted = sorted(set(list(by_year_bl.keys()) + list(by_year_a.keys())))
    print(f"{'year':<6} | {'BL n':>4} {'BL pnl':>10} | {'A n':>4} {'A pnl':>10} | Δn  Δpnl")
    print("-" * 75)
    for y in years_sorted:
        bn, bp = by_year_bl[y]
        an, ap = by_year_a[y]
        dn = an - bn
        dp = ap - bp
        marker = "  ✓" if dp > 0 else "  ✗" if dp < 0 else ""
        print(f"{y:<6} | {bn:>4d} ${bp:>+8,.0f} | {an:>4d} ${ap:>+8,.0f} | "
              f"{dn:>+3d} ${dp:>+8,.0f}{marker}")

    # Restore
    sel.select_strategy = orig_select
    engine_mod.select_strategy = orig_engine_select
    sel.BPS_NNB_IVP_UPPER = orig_upper


if __name__ == "__main__":
    main()
