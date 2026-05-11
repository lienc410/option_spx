"""Q063 Phase 2 — Candidate Gate Head-to-Head Backtest.

Phase 1 showed:
  - VIX < 18 + IVP ≥ 55: BLOCKED entries are PROFITABLE (+$389 avg, sum +$7,389)
  - VIX 18-22 + IVP ≥ 55: BLOCKED entries are LOSSY (-$488 avg, sum -$4,393)
  - Current gate (IVP < 55 全 case) over-restricts low-VIX entries

Phase 2 tests 5 candidate replacement gates + current baseline as control:

  baseline:    IVP < 55 (current SPEC)
  A:           IVP < 70 if VIX < 18 else IVP < 55       (PM hypothesis, conservative)
  B:           IVP < 55 OR VIX < 18                       (PM hypothesis, aggressive)
  C:           block iff VIX × IVP > 1000                 (continuous composite)
  D:           block if VIX ≥ 22                          (replace IVP with abs VIX)
  E:           block iff IVP ≥ 70                          (full relax to top quartile)

Method: monkey-patch select_strategy to apply candidate gate AFTER disabling
the built-in IVP_UPPER check (preserves lower-bound IVP<43 gate, VIX-rising
gate, and all other paths intact).

Output: full-strategy metrics per candidate + BPS-only stratification.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest
from strategy.selector import (
    IVSignal, Regime, StrategyName, Leg,
    _build_recommendation, _effective_iv_signal, _size_rule,
    catalog_strategy_key, get_position_action,
)

REPO = Path(__file__).resolve().parents[2]
OUT_CSV = REPO / "research" / "q063" / "q063_phase2_gate_comparison.csv"

START = "2007-01-01"
END = "2026-05-10"
ACCOUNT = 150_000.0


def _make_gate_patcher(candidate_name: str, gate_fn, base_select):
    """Return a patched select_strategy that re-applies candidate gate AFTER
    base_select returns BPS (with built-in upper gate disabled).

    gate_fn(vix_value: float, ivp: float) -> bool   # True = block
    base_select: original select_strategy function (captured ONCE before any patching).
    """
    BPS = StrategyName.BULL_PUT_SPREAD

    def patched(vix, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = base_select(vix, iv, trend, params)
        # Only intervene on BPS recommendations from NORMAL+NEUTRAL+BULLISH path
        if rec.strategy != BPS:
            return rec
        if not (vix.regime == Regime.NORMAL
                and _effective_iv_signal(iv) == IVSignal.NEUTRAL
                and trend.signal.value == "BULLISH"):
            return rec
        # Apply candidate gate
        if gate_fn(vix.vix, iv.iv_percentile):
            from strategy.selector import _reduce_wait
            return _reduce_wait(
                f"NORMAL + IV NEUTRAL + BULLISH but {candidate_name} gate blocks "
                f"(VIX={vix.vix:.1f}, IVP={iv.iv_percentile:.0f})",
                vix, iv, trend, macro_warn=not trend.above_200,
                canonical_strategy=BPS.value,
                params=params,
            )
        return rec
    return patched


GATE_SPECS = [
    # name, gate_fn (returns True if should block)
    ("baseline_IVP<55",     lambda v, ivp: ivp >= 55),                          # current SPEC equivalent
    ("A_IVP<70_lowVIX",     lambda v, ivp: ivp >= (70 if v < 18 else 55)),     # PM conservative
    ("B_IVP<55_or_VIX<18",  lambda v, ivp: ivp >= 55 and v >= 18),             # PM aggressive
    ("C_VIXxIVP>1000",      lambda v, ivp: v * ivp > 1000),                     # continuous composite
    ("D_VIX>=22",           lambda v, ivp: v >= 22),                            # pure VIX gate
    ("E_IVP>=70",           lambda v, ivp: ivp >= 70),                          # full relax
]


def _trade_max_dd(pnls: list[float]) -> float:
    if not pnls:
        return 0.0
    equity = peak = worst = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def _account_max_dd_pct(trades: list, account: float) -> float:
    if not trades:
        return 0.0
    eq = [0.0]
    for t in sorted(trades, key=lambda x: x.exit_date):
        eq.append(eq[-1] + t.exit_pnl)
    eq = np.array(eq)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak)
    return float(dd.min() / account * 100)  # as % of starting account


def _compute_metrics(trades: list, account: float, years: float) -> dict:
    bps = [t for t in trades if t.strategy.value == "Bull Put Spread"]
    bps_pnls = [t.exit_pnl for t in bps]
    all_pnls = [t.exit_pnl for t in trades]
    total_pnl = sum(all_pnls)
    bps_total = sum(bps_pnls)
    wins = sum(1 for p in bps_pnls if p > 0)
    return {
        "all_n":            len(trades),
        "bps_n":            len(bps),
        "bps_wr_pct":       round(wins / len(bps) * 100, 1) if bps else 0,
        "bps_total_pnl":    round(bps_total),
        "bps_avg":          round(bps_total / len(bps)) if bps else 0,
        "bps_worst":        round(min(bps_pnls)) if bps else 0,
        "bps_tail_count":   sum(1 for p in bps_pnls if p < -5000),
        "all_total_pnl":    round(total_pnl),
        "all_ann_pnl":      round(total_pnl / years),
        "all_ann_roe_pct":  round(total_pnl / account / years * 100, 2),
        "max_dd_pct":       round(_account_max_dd_pct(trades, account), 1),
    }


def main():
    print("=" * 100)
    print("Q063 Phase 2 — Candidate Gate Head-to-Head Backtest")
    print("=" * 100)
    print(f"Window: {START} → {END}  | Account: ${ACCOUNT:,.0f}")
    print()

    years = (pd.Timestamp(END) - pd.Timestamp(START)).days / 365.25

    # Capture ORIGINAL select_strategy ONCE before any patching
    orig_select = sel.select_strategy
    orig_engine_select = engine_mod.select_strategy
    # Disable built-in upper gate; we apply candidate gate via monkey-patch
    orig_upper = sel.BPS_NNB_IVP_UPPER
    sel.BPS_NNB_IVP_UPPER = 999

    results = []
    for name, gate_fn in GATE_SPECS:
        # Build patcher referencing original (not previous patch) to avoid stacking
        patched = _make_gate_patcher(name, gate_fn, base_select=orig_select)
        sel.select_strategy = patched
        engine_mod.select_strategy = patched
        print(f"\nRunning {name} ...")
        bt = run_backtest(start_date=START, end_date=END,
                         account_size=ACCOUNT, verbose=False)
        m = _compute_metrics(bt.trades, ACCOUNT, years)
        m["gate"] = name
        results.append(m)
        print(f"  all_n={m['all_n']} bps_n={m['bps_n']} bps_wr={m['bps_wr_pct']}% "
              f"bps_total=${m['bps_total_pnl']:+,} all_ann=${m['all_ann_pnl']:+,} "
              f"all_ann_ROE={m['all_ann_roe_pct']:+.2f}% DD={m['max_dd_pct']:+.1f}%")

    # Restore
    sel.select_strategy = orig_select
    engine_mod.select_strategy = orig_engine_select
    sel.BPS_NNB_IVP_UPPER = orig_upper

    # ── Compare ──
    df = pd.DataFrame(results)[
        ["gate", "all_n", "bps_n", "bps_wr_pct", "bps_total_pnl", "bps_avg", "bps_worst",
         "bps_tail_count", "all_total_pnl", "all_ann_pnl", "all_ann_roe_pct", "max_dd_pct"]
    ]
    print("\n" + "=" * 130)
    print("Head-to-head comparison (sorted by all_ann_roe_pct)")
    print("=" * 130)
    df_sorted = df.sort_values("all_ann_roe_pct", ascending=False)
    print(df_sorted.to_string(index=False))

    # ── Delta vs baseline ──
    baseline = df[df["gate"] == "baseline_IVP<55"].iloc[0]
    print("\n" + "=" * 130)
    print("Delta vs baseline")
    print("=" * 130)
    print(f"{'gate':<22} {'Δbps_n':>7} {'Δwr_pp':>7} {'Δbps_total':>11} "
          f"{'Δann_ROE_pp':>12} {'Δmax_DD_pp':>11} {'Δbps_worst':>11}")
    for _, r in df_sorted.iterrows():
        if r["gate"] == "baseline_IVP<55":
            print(f"{r['gate']:<22} {'(control)':>7}")
            continue
        print(
            f"{r['gate']:<22} "
            f"{int(r['bps_n']-baseline['bps_n']):>+7d} "
            f"{r['bps_wr_pct']-baseline['bps_wr_pct']:>+6.1f}pp "
            f"${int(r['bps_total_pnl']-baseline['bps_total_pnl']):>+10,d} "
            f"{r['all_ann_roe_pct']-baseline['all_ann_roe_pct']:>+10.2f}pp "
            f"{r['max_dd_pct']-baseline['max_dd_pct']:>+9.1f}pp "
            f"${int(r['bps_worst']-baseline['bps_worst']):>+10,d}"
        )

    # ── Save CSV ──
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_sorted.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {OUT_CSV}")


if __name__ == "__main__":
    main()
