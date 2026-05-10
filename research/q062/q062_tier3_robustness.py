"""Q062 Tier 3 — Robustness Check on Sleeve A D30 Candidates.

Tier 2 surfaced a striking finding: D30 short-DTE cluster shows ann ROE
+9.94% vs baseline +5.02% (+4.92pp) on full sample. This script tests
whether the finding survives:

  1. Out-of-sample split (2007-2017 train / 2018-2026 test)
     — Pass: D30 ann beats baseline ann on BOTH periods
     — Fail: only on train (in-sample bias) or noise (test ann ≤ baseline test ann)

  2. Disaster window check (2008-Q4 / 2020-Q1 / 2022)
     — Pass: D30 doesn't underperform baseline catastrophically in stress
     — Fail: D30 worse than baseline in any window by ≥ 2× baseline window loss

  3. Improved metrics (replacing saturated worst-trade)
     — frequency_of_disasters: count(-10% trades) / n
     — CVaR_10%: tail mean of worst 10% trades
     — median_loss: median of LOSING trades (not floor)
     — max_consec_losses: longest run of losers

  4. Bootstrap CI (1000 resamples per variant)
     — Pass: D30 95% CI lower bound > baseline 95% CI upper bound
     — Fail: CIs overlap → cannot statistically distinguish

Variants tested (Sleeve A only — B maintained per Tier 2):
  - baseline 5%/90D (control)
  - S1_2.5%/30D (top by AnnROE)
  - S1_5.0%/30D (top by AnnROE, tied)
  - S1_2.5%/180D (top by Sharpe / low DD)

Output:
  Console: full table of all 4 robustness checks per variant
  task/q062_tier3_memo_2026-05-10.md (separate write)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.q062.q062_tier1_structure_scan import (
    Variant, _build_signals, _load_data, _run_variant, TradeRecord, SIZING_PCT,
)

VARIANTS = [
    Variant("baseline_5pct_90D", "vertical", 0.00, 0.05, 90),
    Variant("S1_2.5pct_30D",     "vertical", 0.00, 0.025, 30),
    Variant("S1_5.0pct_30D",     "vertical", 0.00, 0.05, 30),
    Variant("S1_2.5pct_180D",    "vertical", 0.00, 0.025, 180),
]

TRAIN_END = "2017-12-31"
TEST_START = "2018-01-01"
N_BOOTSTRAP = 1000
RNG = np.random.default_rng(20260510)


def _filter_trades_window(trades: list[TradeRecord], start: str, end: str) -> list[TradeRecord]:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    return [t for t in trades if s <= t.entry_date <= e]


def _ann_roe(trades: list[TradeRecord], years: float) -> float:
    if not trades or years <= 0:
        return 0.0
    total = sum(t.pnl_pct_debit * SIZING_PCT for t in trades) * 100
    return total / years


def _account_pcts(trades: list[TradeRecord]) -> np.ndarray:
    return np.array([t.pnl_pct_debit * SIZING_PCT for t in trades])


def _max_dd(account_pcts: np.ndarray) -> float:
    if len(account_pcts) == 0:
        return 0.0
    eq = np.cumprod(1 + account_pcts)
    eq = np.insert(eq, 0, 1.0)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    return float(dd.min() * 100)


def _improved_metrics(trades: list[TradeRecord]) -> dict:
    if not trades:
        return {"freq_disaster": 0.0, "cvar10": 0.0, "med_loss": 0.0, "max_consec_l": 0}
    pnl = np.array([t.pnl_pct_debit * SIZING_PCT * 100 for t in trades])  # account %
    losers = pnl[pnl < 0]
    sorted_pnl = np.sort(pnl)
    cvar_n = max(1, int(len(sorted_pnl) * 0.10))
    cvar10 = float(sorted_pnl[:cvar_n].mean())
    freq_disaster = float((pnl <= -10.0 + 1e-6).mean())  # -10% floor hits
    med_loss = float(np.median(losers)) if len(losers) > 0 else 0.0

    is_loss = (pnl < 0).astype(int)
    max_consec, cur = 0, 0
    for x in is_loss:
        if x:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0
    return {
        "freq_disaster": freq_disaster,
        "cvar10": cvar10,
        "med_loss": med_loss,
        "max_consec_l": max_consec,
    }


def _bootstrap_ci(trades: list[TradeRecord], years: float, n_iter: int = N_BOOTSTRAP) -> tuple[float, float]:
    if not trades or years <= 0:
        return 0.0, 0.0
    pcts = _account_pcts(trades)
    n = len(pcts)
    samples = []
    for _ in range(n_iter):
        idx = RNG.integers(0, n, size=n)
        boot_total = pcts[idx].sum() * 100
        samples.append(boot_total / years)
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def main():
    print("=" * 80)
    print("Q062 Tier 3 — Robustness Check on Sleeve A D30 Candidates")
    print("=" * 80)

    df = _load_data()
    full_years = (df.index.max() - df.index.min()).days / 365.25
    train_years = (pd.Timestamp(TRAIN_END) - df.index.min()).days / 365.25
    test_years = (df.index.max() - pd.Timestamp(TEST_START)).days / 365.25
    print(f"Full window: {df.index.min().date()} → {df.index.max().date()} ({full_years:.1f}y)")
    print(f"Train: {df.index.min().date()} → {TRAIN_END} ({train_years:.1f}y)")
    print(f"Test:  {TEST_START} → {df.index.max().date()} ({test_years:.1f}y)")

    # Run each variant on full history; we'll slice trades by entry_date for periods
    runs = {}
    for v in VARIANTS:
        sig_a, _ = _build_signals(df, v.dte)
        trades = _run_variant(df, sig_a, v)
        runs[v.name] = trades

    # ── 1. Out-of-sample split ──
    print("\n" + "=" * 80)
    print("1. Out-of-Sample Split (Train 2007-2017 / Test 2018-2026)")
    print("=" * 80)
    print(f"{'variant':<22} | {'full n':>6} | {'train n':>7} | {'train ann':>9} | "
          f"{'test n':>6} | {'test ann':>8} | {'verdict':<25}")
    print("-" * 110)
    bl_train = _ann_roe(_filter_trades_window(runs["baseline_5pct_90D"], "2007-01-01", TRAIN_END), train_years)
    bl_test = _ann_roe(_filter_trades_window(runs["baseline_5pct_90D"], TEST_START, "2026-05-10"), test_years)
    for v in VARIANTS:
        full_t = runs[v.name]
        tr_t = _filter_trades_window(full_t, "2007-01-01", TRAIN_END)
        te_t = _filter_trades_window(full_t, TEST_START, "2026-05-10")
        tr_ann = _ann_roe(tr_t, train_years)
        te_ann = _ann_roe(te_t, test_years)
        if v.name == "baseline_5pct_90D":
            verdict = "control"
        else:
            wins_train = tr_ann > bl_train
            wins_test = te_ann > bl_test
            if wins_train and wins_test:
                verdict = "PASS (both periods)"
            elif wins_train and not wins_test:
                verdict = "FAIL (in-sample bias)"
            elif not wins_train and wins_test:
                verdict = "PARTIAL (test only)"
            else:
                verdict = "FAIL (loses both)"
        print(f"{v.name:<22} | {len(full_t):>6} | {len(tr_t):>7} | {tr_ann:>+8.2f}% | "
              f"{len(te_t):>6} | {te_ann:>+7.2f}% | {verdict:<25}")

    # ── 2. Disaster windows ──
    print("\n" + "=" * 80)
    print("2. Disaster Window PnL (per-window total account %)")
    print("=" * 80)
    windows = [
        ("2008-Q4 GFC",   "2008-09-01", "2009-03-31"),
        ("2020-Q1 COVID", "2020-02-15", "2020-04-30"),
        ("2022 grind",    "2022-01-01", "2022-12-31"),
    ]
    print(f"{'variant':<22} | " + " | ".join(f"{wn:>14}" for wn, _, _ in windows) + " | total stress")
    print("-" * 110)
    for v in VARIANTS:
        cols = []
        total_stress = 0.0
        for wn, ws, we in windows:
            wt = _filter_trades_window(runs[v.name], ws, we)
            if wt:
                pnl = sum(t.pnl_pct_debit * SIZING_PCT for t in wt) * 100
                cols.append(f"{len(wt):>2d} {pnl:>+7.1f}%")
                total_stress += pnl
            else:
                cols.append(f"{'0  none':>14}")
        print(f"{v.name:<22} | " + " | ".join(cols) + f" | {total_stress:>+7.1f}%")

    # ── 3. Improved metrics ──
    print("\n" + "=" * 80)
    print("3. Improved Metrics (replacing saturated worst-trade)")
    print("=" * 80)
    print(f"{'variant':<22} | {'n':>3} | {'freq_-10%':>9} | {'CVaR10%':>8} | "
          f"{'med_loss%':>9} | {'maxConsecL':>10} | {'ann full %':>10} | {'MaxDD %':>8}")
    print("-" * 110)
    for v in VARIANTS:
        t = runs[v.name]
        im = _improved_metrics(t)
        ann = _ann_roe(t, full_years)
        dd = _max_dd(_account_pcts(t))
        print(f"{v.name:<22} | {len(t):>3d} | {im['freq_disaster']*100:>8.1f}% | "
              f"{im['cvar10']:>+7.1f}% | {im['med_loss']:>+8.2f}% | "
              f"{im['max_consec_l']:>10d} | {ann:>+9.2f}% | {dd:>+7.1f}%")

    # ── 4. Bootstrap CI ──
    print("\n" + "=" * 80)
    print(f"4. Bootstrap 95% CI of AnnROE ({N_BOOTSTRAP} resamples)")
    print("=" * 80)
    print(f"{'variant':<22} | {'point ann':>10} | {'95% CI':>22} | vs baseline CI")
    print("-" * 100)
    bl_pt = _ann_roe(runs["baseline_5pct_90D"], full_years)
    bl_lo, bl_hi = _bootstrap_ci(runs["baseline_5pct_90D"], full_years)
    for v in VARIANTS:
        t = runs[v.name]
        pt = _ann_roe(t, full_years)
        lo, hi = _bootstrap_ci(t, full_years)
        if v.name == "baseline_5pct_90D":
            verdict = "control"
        elif lo > bl_hi:
            verdict = "PASS (CI > baseline CI)"
        elif hi < bl_lo:
            verdict = "FAIL (CI < baseline)"
        else:
            verdict = f"INDISTINGUISHABLE (overlaps {bl_lo:+.2f}~{bl_hi:+.2f})"
        print(f"{v.name:<22} | {pt:>+9.2f}% | [{lo:>+6.2f}, {hi:>+6.2f}]% | {verdict}")

    # ── Summary ──
    print("\n" + "=" * 80)
    print("Tier 3 Summary")
    print("=" * 80)
    print("\nFor each candidate, did it PASS all 4 robustness checks?\n")
    print(f"{'variant':<22} | {'OOS':<22} | {'disaster ok':<12} | {'CI':<35}")
    for v in VARIANTS:
        if v.name == "baseline_5pct_90D":
            continue
        # Recompute key tests
        full_t = runs[v.name]
        tr_t = _filter_trades_window(full_t, "2007-01-01", TRAIN_END)
        te_t = _filter_trades_window(full_t, TEST_START, "2026-05-10")
        tr_ann = _ann_roe(tr_t, train_years)
        te_ann = _ann_roe(te_t, test_years)
        oos_pass = (tr_ann > bl_train) and (te_ann > bl_test)

        disaster_total = 0.0
        bl_disaster_total = 0.0
        for wn, ws, we in windows:
            wt = _filter_trades_window(runs[v.name], ws, we)
            blwt = _filter_trades_window(runs["baseline_5pct_90D"], ws, we)
            disaster_total += sum(t.pnl_pct_debit * SIZING_PCT for t in wt) * 100
            bl_disaster_total += sum(t.pnl_pct_debit * SIZING_PCT for t in blwt) * 100
        disaster_ok = disaster_total >= bl_disaster_total - 5  # allow 5pp tolerance

        lo, hi = _bootstrap_ci(full_t, full_years)
        ci_pass = lo > bl_hi
        ci_overlap = not (lo > bl_hi or hi < bl_lo)

        oos_label = "PASS" if oos_pass else "FAIL"
        if not oos_pass:
            if tr_ann > bl_train and te_ann <= bl_test:
                oos_label = "FAIL (train-only)"
            elif tr_ann <= bl_train and te_ann > bl_test:
                oos_label = "PARTIAL (test-only)"

        ci_label = "PASS (separated)" if ci_pass else ("OVERLAP (indistinguishable)" if ci_overlap else "FAIL")
        print(f"{v.name:<22} | {oos_label:<22} | {'PASS' if disaster_ok else 'FAIL':<12} | {ci_label:<35}")


if __name__ == "__main__":
    main()
