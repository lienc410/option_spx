"""Q063 Phase 3 — Robustness Check on Candidate A (IVP<70 if VIX<low else IVP<55).

Phase 2 finding: A & B are equivalent in 19y empirical sample, +0.26pp ann ROE
vs baseline, no DD penalty. n=38 vs n=53 — small but consistent edge.

Phase 3 tests:
  1. OOS split: train 2007-2017 / test 2018-2026 — A wins on BOTH halves?
  2. VIX threshold sensitivity: test threshold ∈ {16, 17, 18, 19, 20}
  3. Disaster window per-year: 2008/2009/2011/2015/2018-Q4/2020/2022
  4. Bootstrap CI on diff (A - baseline) → reject H0?

Output: console summary; verdict on whether to recommend SPEC change.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest
from strategy.selector import IVSignal, Regime, StrategyName

START = "2007-01-01"
END = "2026-05-10"
TRAIN_END = "2017-12-31"
TEST_START = "2018-01-01"
ACCOUNT = 150_000.0
N_BOOTSTRAP = 2000
RNG = np.random.default_rng(20260511)


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
                f"NORMAL + IV NEUTRAL + BULLISH but gate blocks "
                f"(VIX={vix.vix:.1f}, IVP={iv.iv_percentile:.0f})",
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


def _filter_window(trades, start_str, end_str):
    return [t for t in trades if start_str <= t.entry_date <= end_str]


def _ann_pnl(trades, years):
    if not trades or years <= 0:
        return 0.0
    return sum(t.exit_pnl for t in trades) / years


def _max_dd(trades):
    if not trades:
        return 0.0
    eq = [0.0]
    for t in sorted(trades, key=lambda x: x.exit_date):
        eq.append(eq[-1] + t.exit_pnl)
    eq = np.array(eq)
    peak = np.maximum.accumulate(eq)
    return float((eq - peak).min())


def _bootstrap_diff_pnls(pnls_a, pnls_b, n_iter=N_BOOTSTRAP):
    """Bootstrap CI of (mean_a - mean_b) per-trade pnl distribution.
    Note: doesn't account for different sample sizes — that's the point (compare strategies)."""
    diffs = []
    a, b = np.array(pnls_a), np.array(pnls_b)
    for _ in range(n_iter):
        sa = a[RNG.integers(0, len(a), len(a))].mean() if len(a) > 0 else 0
        sb = b[RNG.integers(0, len(b), len(b))].mean() if len(b) > 0 else 0
        diffs.append(sa - sb)
    diffs = np.array(diffs)
    return {
        "point": float(diffs.mean()),
        "ci_lo": float(np.percentile(diffs, 2.5)),
        "ci_hi": float(np.percentile(diffs, 97.5)),
        "p_a_gt_b": float((diffs > 0).mean()),
    }


def main():
    print("=" * 100)
    print("Q063 Phase 3 — Robustness Check on Candidate A (low-VIX IVP relaxation)")
    print("=" * 100)

    orig_select = sel.select_strategy
    orig_engine_select = engine_mod.select_strategy
    orig_upper = sel.BPS_NNB_IVP_UPPER
    sel.BPS_NNB_IVP_UPPER = 999

    full_years = (pd.Timestamp(END) - pd.Timestamp(START)).days / 365.25
    train_years = (pd.Timestamp(TRAIN_END) - pd.Timestamp(START)).days / 365.25
    test_years = (pd.Timestamp(END) - pd.Timestamp(TEST_START)).days / 365.25
    print(f"Full: {full_years:.1f}y | Train (07-17): {train_years:.1f}y | Test (18-26): {test_years:.1f}y")

    # ── Test 1: OOS split for baseline vs A ──
    print("\n" + "=" * 100)
    print("Test 1 — Out-of-Sample Split")
    print("=" * 100)
    candidates = {
        "baseline (IVP<55)": lambda v, ivp: ivp >= 55,
        "A (VIX<18 → IVP<70)": lambda v, ivp: ivp >= (70 if v < 18 else 55),
    }
    oos_results = {}
    for name, fn in candidates.items():
        bt = _run_with_gate(fn, orig_select, orig_engine_select)
        bps = [t for t in bt.trades if t.strategy.value == "Bull Put Spread"]
        bps_train = _filter_window(bps, "2007-01-01", TRAIN_END)
        bps_test = _filter_window(bps, TEST_START, END)
        all_train = _filter_window(bt.trades, "2007-01-01", TRAIN_END)
        all_test = _filter_window(bt.trades, TEST_START, END)
        oos_results[name] = {
            "bps_full_n": len(bps), "bps_train_n": len(bps_train), "bps_test_n": len(bps_test),
            "ann_train_all": _ann_pnl(all_train, train_years),
            "ann_test_all": _ann_pnl(all_test, test_years),
            "bps_ann_train": _ann_pnl(bps_train, train_years),
            "bps_ann_test": _ann_pnl(bps_test, test_years),
            "max_dd_full": _max_dd(bt.trades),
            "bps_train_pnls": [t.exit_pnl for t in bps_train],
            "bps_test_pnls": [t.exit_pnl for t in bps_test],
        }
    print(f"{'gate':<26} {'bps_n':>6} {'train_n':>7} {'train_ann':>11} {'test_n':>7} {'test_ann':>11}")
    print("-" * 90)
    for name, r in oos_results.items():
        print(f"{name:<26} {r['bps_full_n']:>6d} {r['bps_train_n']:>7d} "
              f"${r['bps_ann_train']:>+9.0f} {r['bps_test_n']:>7d} ${r['bps_ann_test']:>+9.0f}")
    bl = oos_results["baseline (IVP<55)"]
    a = oos_results["A (VIX<18 → IVP<70)"]
    print(f"\nΔ A vs baseline:")
    print(f"  train ann delta: ${a['bps_ann_train'] - bl['bps_ann_train']:+,.0f}/yr "
          f"({'PASS' if a['bps_ann_train'] > bl['bps_ann_train'] else 'FAIL'})")
    print(f"  test ann delta:  ${a['bps_ann_test'] - bl['bps_ann_test']:+,.0f}/yr "
          f"({'PASS' if a['bps_ann_test'] > bl['bps_ann_test'] else 'FAIL'})")
    oos_pass = (a['bps_ann_train'] > bl['bps_ann_train']) and (a['bps_ann_test'] > bl['bps_ann_test'])
    print(f"  Overall OOS: {'PASS (A beats baseline both periods)' if oos_pass else 'PARTIAL/FAIL'}")

    # ── Test 2: VIX threshold sensitivity ──
    print("\n" + "=" * 100)
    print("Test 2 — VIX Threshold Sensitivity (vary VIX-low threshold in A)")
    print("=" * 100)
    print(f"{'threshold':<10} {'bps_n':>6} {'WR%':>6} {'total':>11} {'avg':>9} {'ann_pnl':>11} {'max_dd':>10} {'worst':>11}")
    print("-" * 95)
    for vix_thr in [16, 17, 18, 19, 20, 21]:
        gate = lambda v, ivp, t=vix_thr: ivp >= (70 if v < t else 55)
        bt = _run_with_gate(gate, orig_select, orig_engine_select)
        bps = [t for t in bt.trades if t.strategy.value == "Bull Put Spread"]
        if not bps:
            continue
        pnls = [t.exit_pnl for t in bps]
        wr = sum(1 for p in pnls if p > 0) / len(pnls) * 100
        print(f"VIX<{vix_thr:<4}  {len(bps):>6d} {wr:>5.1f}% ${sum(pnls):>+9,.0f} "
              f"${np.mean(pnls):>+7,.0f} ${_ann_pnl(bps, full_years):>+9,.0f} "
              f"${_max_dd(bt.trades):>+8,.0f} ${min(pnls):>+9,.0f}")

    # ── Test 3: Disaster window per-year ──
    print("\n" + "=" * 100)
    print("Test 3 — Disaster Window per-year P&L (BPS only)")
    print("=" * 100)
    bt_bl = _run_with_gate(lambda v, ivp: ivp >= 55, orig_select, orig_engine_select)
    bt_a = _run_with_gate(lambda v, ivp: ivp >= (70 if v < 18 else 55), orig_select, orig_engine_select)
    bps_bl = [t for t in bt_bl.trades if t.strategy.value == "Bull Put Spread"]
    bps_a = [t for t in bt_a.trades if t.strategy.value == "Bull Put Spread"]
    windows = [
        ("2008-Q4 GFC",        "2008-09-01", "2009-03-31"),
        ("2011-Q3 EuroDebt",   "2011-07-01", "2011-12-31"),
        ("2015-Q3 China",      "2015-08-01", "2016-02-29"),
        ("2018-Q4 selloff",    "2018-10-01", "2018-12-31"),
        ("2020-Q1 COVID",      "2020-02-15", "2020-04-30"),
        ("2022 bear",          "2022-01-01", "2022-12-31"),
    ]
    print(f"{'window':<22} | {'BL_n':>4} {'BL_pnl':>9} | {'A_n':>4} {'A_pnl':>9} | Δ_pnl")
    print("-" * 80)
    for wn, ws, we in windows:
        bl_w = _filter_window(bps_bl, ws, we)
        a_w = _filter_window(bps_a, ws, we)
        bl_pnl = sum(t.exit_pnl for t in bl_w)
        a_pnl = sum(t.exit_pnl for t in a_w)
        print(f"{wn:<22} | {len(bl_w):>4d} ${bl_pnl:>+7,.0f} | "
              f"{len(a_w):>4d} ${a_pnl:>+7,.0f} | ${a_pnl - bl_pnl:>+7,.0f}")

    # ── Test 4: Bootstrap CI on per-trade pnl difference ──
    print("\n" + "=" * 100)
    print(f"Test 4 — Bootstrap CI on per-trade mean P&L difference ({N_BOOTSTRAP} resamples)")
    print("=" * 100)
    bl_pnls = [t.exit_pnl for t in bps_bl]
    a_pnls = [t.exit_pnl for t in bps_a]
    boot = _bootstrap_diff_pnls(a_pnls, bl_pnls)
    print(f"  baseline mean per-trade P&L: ${np.mean(bl_pnls):+,.0f}  (n={len(bl_pnls)})")
    print(f"  A mean per-trade P&L:        ${np.mean(a_pnls):+,.0f}  (n={len(a_pnls)})")
    print(f"  Bootstrap mean diff (A-BL):  ${boot['point']:+,.0f}")
    print(f"  95% CI of diff:              [${boot['ci_lo']:+,.0f}, ${boot['ci_hi']:+,.0f}]")
    print(f"  P(A > baseline per-trade):   {boot['p_a_gt_b']*100:.1f}%")
    print(f"  Statistically significant (CI > 0)?  "
          f"{'YES' if boot['ci_lo'] > 0 else 'NO (CI includes 0)'}")

    # ── Cleanup ──
    sel.select_strategy = orig_select
    engine_mod.select_strategy = orig_engine_select
    sel.BPS_NNB_IVP_UPPER = orig_upper

    # ── Verdict ──
    print("\n" + "=" * 100)
    print("Tier 3 Verdict Summary")
    print("=" * 100)
    print(f"OOS:           {'PASS' if oos_pass else 'PARTIAL/FAIL'}")
    print(f"Bootstrap CI:  {'CI > 0 (REJECT H0)' if boot['ci_lo'] > 0 else 'CI overlaps 0 (cannot reject)'}")
    print(f"P(A > BL):     {boot['p_a_gt_b']*100:.1f}%")


if __name__ == "__main__":
    main()
