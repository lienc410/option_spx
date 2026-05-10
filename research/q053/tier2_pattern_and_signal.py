"""
Q053 Tier 2 — Multi-window pattern test + candidate detection signal
=====================================================================
Source: R-20260509-03 (Tier 1 confirmed weakness in 2022; Tier 2 expansion
        justified per R-20260509-02 Action A2 plan).

Three parallel investigations:

  1. Multi-window consistency:
     Run main strategy across 5 stress windows (Tier 1 + 3 new):
       - 2011-Q3:    Eurozone crisis (Aug-Dec 2011)
       - 2015-2016:  China devaluation + oil crash (Aug 2015 - Feb 2016)
       - 2018-Q1:   Volmageddon (Jan-Apr 2018)
       - 2018-Q4:   selloff (Tier 1)
       - 2022:      grinding bear (Tier 1)
     Question: is the underperformance a systematic pattern or 2022-specific?

  2. Candidate detection signal design:
     Hypothesis: "grinding decline" = VIX persistently in 20-30 range without
     triggering EXTREME_VOL gate. Test simple candidate signals:
       - S1: VIX 30-day rolling mean ≥ 22
       - S2: VIX > 20 for ≥ 20 consecutive trading days
       - S3: SPX 50-day return ≤ -5% AND VIX < 35 (declining without spike)

  3. Signal validation:
     For each candidate signal, compute:
       - Coverage: % of stress-window days flagged
       - False positive rate: % of "Other" days flagged
       - PnL conditional on signal: avg trade PnL when signal active vs inactive

Output: clear judgment on whether (a) pattern is systematic, and
(b) any candidate signal is good enough for a follow-up SPEC.

Boundary:
  - Tier 2 still does NOT design implementation
  - If a signal looks promising, the next step is a candidate SPEC, not direct
    runtime change
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest.engine import run_backtest
from signals.trend import fetch_spx_history
from signals.vix_regime import fetch_vix_history


# ── Window definitions ────────────────────────────────────────────────────────

STRESS_WINDOWS = {
    "2011-Q3 Eurozone":      ("2011-08-01", "2011-12-31"),
    "2015-2016 China/oil":   ("2015-08-01", "2016-02-29"),
    "2018-Q1 Volmageddon":   ("2018-01-01", "2018-04-30"),
    "2018-Q4 selloff":       ("2018-10-01", "2018-12-31"),
    "2022 grinding bear":    ("2022-01-01", "2022-12-31"),
}

FULL_START = "2007-01-01"
ACCOUNT    = 500_000.0


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class WindowMetrics:
    label:       str
    n_trades:    int
    total_pnl:   float
    win_rate:    float
    stop_rate:   float
    avg_pnl:     float
    worst_pnl:   float
    pnl_per_day: float


# ── Pattern test (1) ──────────────────────────────────────────────────────────

def _trades_in_window(trades, start: str, end: str):
    ts, te = pd.Timestamp(start), pd.Timestamp(end)
    return [t for t in trades
             if t.entry_date and ts <= pd.Timestamp(t.entry_date) <= te]


def _metrics(label: str, trades, start: str, end: str) -> WindowMetrics:
    if not trades:
        return WindowMetrics(label, 0, 0, 0, 0, 0, 0, 0)
    pnls  = [t.exit_pnl for t in trades]
    wins  = [t for t in trades if t.exit_pnl > 0]
    stops = [t for t in trades if t.exit_reason == "stop_loss"]
    days  = max((pd.Timestamp(end) - pd.Timestamp(start)).days, 1)
    return WindowMetrics(
        label=label, n_trades=len(trades),
        total_pnl=sum(pnls),
        win_rate=len(wins)/len(trades)*100,
        stop_rate=len(stops)/len(trades)*100,
        avg_pnl=np.mean(pnls), worst_pnl=min(pnls),
        pnl_per_day=sum(pnls)/days,
    )


# ── Candidate signal evaluation (2 + 3) ───────────────────────────────────────

def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    out = df.copy()
    out.index = idx.normalize()
    return out


def _build_market_series() -> pd.DataFrame:
    """Build daily VIX + SPX series for signal computation."""
    vdf = _strip_tz(fetch_vix_history(period="max", interval="1d"))
    sdf = _strip_tz(fetch_spx_history(period="max", interval="1d"))
    df = pd.DataFrame({"vix": vdf["vix"], "spx": sdf["close"]}).dropna()
    df = df[df.index >= pd.Timestamp(FULL_START)]
    # Pre-compute signal inputs
    df["vix_ma_30"]    = df["vix"].rolling(30, min_periods=15).mean()
    df["vix_above_20"] = (df["vix"] > 20).astype(int)
    df["vix_streak_above_20"] = (df["vix_above_20"]
                                  .groupby((df["vix_above_20"] != df["vix_above_20"].shift()).cumsum())
                                  .cumsum())
    df["spx_50d_ret"] = df["spx"].pct_change(50)
    return df


def _signal_S1(df: pd.DataFrame) -> pd.Series:
    """VIX 30-day rolling mean ≥ 22."""
    return df["vix_ma_30"] >= 22


def _signal_S2(df: pd.DataFrame) -> pd.Series:
    """VIX > 20 for ≥ 20 consecutive trading days."""
    return df["vix_streak_above_20"] >= 20


def _signal_S3(df: pd.DataFrame) -> pd.Series:
    """SPX 50-day return ≤ -5% AND VIX < 35 (declining without spike)."""
    return (df["spx_50d_ret"] <= -0.05) & (df["vix"] < 35)


def _signal_S4(df: pd.DataFrame) -> pd.Series:
    """Combined: any of S1/S2/S3 (broadest grinding-decline detector)."""
    return _signal_S1(df) | _signal_S2(df) | _signal_S3(df)


SIGNALS = {
    "S1: VIX 30-day MA ≥ 22":             _signal_S1,
    "S2: VIX > 20 for ≥ 20 consec days":  _signal_S2,
    "S3: SPX -5% over 50d & VIX < 35":     _signal_S3,
    "S4: any of S1/S2/S3 (combined)":      _signal_S4,
}


def _evaluate_signal(df: pd.DataFrame, signal: pd.Series, trades) -> dict:
    """Compute coverage / false-positive / conditional PnL for a signal."""
    # Day-level coverage in stress windows
    stress_dates = set()
    for s, e in STRESS_WINDOWS.values():
        ts, te = pd.Timestamp(s), pd.Timestamp(e)
        stress_dates.update(d for d in df.index if ts <= d <= te)
    stress_idx = pd.Index(sorted(stress_dates))

    in_stress = df.index.isin(stress_idx)

    # Coverage: % of stress days flagged
    if in_stress.sum() > 0:
        coverage = signal[in_stress].sum() / in_stress.sum() * 100
    else:
        coverage = 0

    # False positive: % of non-stress days flagged
    not_stress = ~in_stress
    if not_stress.sum() > 0:
        fp_rate = signal[not_stress].sum() / not_stress.sum() * 100
    else:
        fp_rate = 0

    # Trade-level: classify each trade by signal status at entry
    flagged_trades = []
    unflagged_trades = []
    for t in trades:
        if not t.entry_date:
            continue
        try:
            ed = pd.Timestamp(t.entry_date)
        except Exception:
            continue
        if ed in df.index:
            if signal.loc[ed]:
                flagged_trades.append(t)
            else:
                unflagged_trades.append(t)

    def avg_pnl(tlist):
        return np.mean([t.exit_pnl for t in tlist]) if tlist else 0
    def wr(tlist):
        wins = [t for t in tlist if t.exit_pnl > 0]
        return len(wins)/len(tlist)*100 if tlist else 0

    return {
        "coverage_pct":    coverage,
        "fp_rate_pct":     fp_rate,
        "n_flagged":       len(flagged_trades),
        "n_unflagged":     len(unflagged_trades),
        "avg_pnl_flagged":   avg_pnl(flagged_trades),
        "avg_pnl_unflagged": avg_pnl(unflagged_trades),
        "wr_flagged":      wr(flagged_trades),
        "wr_unflagged":    wr(unflagged_trades),
        "total_pnl_flagged": sum(t.exit_pnl for t in flagged_trades),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 80)
    print("Q053 TIER 2 — Multi-window pattern + candidate detection signal")
    print(f"  Window: {FULL_START} → today;  account NLV ${ACCOUNT:,.0f}")
    print("=" * 80)

    print("\n  [1/3] Running full main-strategy backtest …", flush=True)
    r = run_backtest(start_date=FULL_START, account_size=ACCOUNT, verbose=False)
    trades = r.trades
    print(f"  Total trades: {len(trades)}")

    # ── Pattern test ─────────────────────────────────────────────────────────
    print("\n\n" + "═" * 80)
    print("  PART 1: Multi-window pattern consistency")
    print("═" * 80)

    win_metrics = {}
    in_any = set()
    for label, (s, e) in STRESS_WINDOWS.items():
        wt = _trades_in_window(trades, s, e)
        win_metrics[label] = _metrics(label, wt, s, e)
        for t in wt:
            in_any.add(id(t))
    other = [t for t in trades if id(t) not in in_any]
    full_start = trades[0].entry_date if trades else FULL_START
    full_end   = trades[-1].exit_date or trades[-1].entry_date if trades else FULL_START
    base_m     = _metrics("Other (baseline)", other, full_start, full_end)

    print(f"\n  {'Window':<25}  {'n':>3}  {'TotalPnL':>12}  {'WR%':>5}  "
          f"{'Stop%':>6}  {'AvgPnL':>8}  {'Worst':>10}  {'$/day':>7}")
    print(f"  {'─'*88}")
    print(f"  {base_m.label:<25}  {base_m.n_trades:>3}  ${base_m.total_pnl:>11,.0f}  "
          f"{base_m.win_rate:>5.1f}  {base_m.stop_rate:>6.1f}  "
          f"${base_m.avg_pnl:>+7,.0f}  ${base_m.worst_pnl:>+9,.0f}  ${base_m.pnl_per_day:>6.0f}")
    for label in STRESS_WINDOWS:
        m = win_metrics[label]
        print(f"  {m.label:<25}  {m.n_trades:>3}  ${m.total_pnl:>11,.0f}  "
              f"{m.win_rate:>5.1f}  {m.stop_rate:>6.1f}  "
              f"${m.avg_pnl:>+7,.0f}  ${m.worst_pnl:>+9,.0f}  ${m.pnl_per_day:>6.0f}")

    print(f"\n  Pattern flags (vs baseline):")
    consistent_count = 0
    for label in STRESS_WINDOWS:
        m = win_metrics[label]
        if m.n_trades == 0:
            print(f"    {label:<25}  no trades in window")
            continue
        flags = []
        avg_dev = (m.avg_pnl - base_m.avg_pnl) / abs(base_m.avg_pnl) * 100 if base_m.avg_pnl else 0
        if avg_dev < -30:
            flags.append(f"avg PnL {avg_dev:+.0f}%")
        if m.win_rate < base_m.win_rate - 5:
            flags.append(f"WR {m.win_rate - base_m.win_rate:+.1f}pp")
        if m.total_pnl < 0:
            flags.append("NEGATIVE total PnL")
        if flags:
            consistent_count += 1
            print(f"    {label:<25}  ⚠️  {', '.join(flags)}")
        else:
            print(f"    {label:<25}  ✓ no major deviation")

    pct_consistent = consistent_count / len(STRESS_WINDOWS) * 100
    print(f"\n  Pattern consistency: {consistent_count}/{len(STRESS_WINDOWS)} windows show weakness "
          f"({pct_consistent:.0f}%)")

    # ── Signal evaluation ────────────────────────────────────────────────────
    print("\n\n" + "═" * 80)
    print("  PART 2: Candidate detection signals")
    print("═" * 80)

    print("\n  [2/3] Building VIX/SPX market series for signal computation …", flush=True)
    df = _build_market_series()
    print(f"  Series: {len(df)} trading days from {df.index[0].date()} to {df.index[-1].date()}")

    print(f"\n  [3/3] Evaluating candidate signals …\n")
    print(f"  {'Signal':<40}  {'Cov%':>5}  {'FP%':>5}  "
          f"{'n_flag':>6}  {'PnL_flag':>10}  {'PnL_norm':>9}  {'Δavg':>9}")
    print(f"  {'─'*100}")
    signal_results = {}
    for name, fn in SIGNALS.items():
        sig = fn(df)
        ev = _evaluate_signal(df, sig, trades)
        signal_results[name] = ev
        delta_avg = ev["avg_pnl_flagged"] - ev["avg_pnl_unflagged"]
        print(f"  {name:<40}  {ev['coverage_pct']:>5.1f}  {ev['fp_rate_pct']:>5.1f}  "
              f"{ev['n_flagged']:>6}  ${ev['avg_pnl_flagged']:>+9,.0f}  "
              f"${ev['avg_pnl_unflagged']:>+8,.0f}  ${delta_avg:>+8,.0f}")

    print()
    print("  Legend: Cov%=stress days flagged | FP%=non-stress days flagged")
    print("          PnL_flag=avg PnL of trades flagged | PnL_norm=avg of unflagged")
    print("          Δavg=signal selectivity (more negative = better detector)")

    # ── Final verdict ─────────────────────────────────────────────────────────
    print("\n\n" + "═" * 80)
    print("  TIER 2 VERDICT")
    print("═" * 80)

    if pct_consistent >= 60:
        print(f"\n  ✓ Pattern is SYSTEMATIC: {consistent_count}/{len(STRESS_WINDOWS)} stress")
        print(f"    windows show main-strategy weakness. Q053 hypothesis confirmed.")
    elif pct_consistent >= 40:
        print(f"\n  ~ Pattern is PARTIAL: {consistent_count}/{len(STRESS_WINDOWS)} windows show")
        print(f"    weakness. Mix of confirmed (2022 robust) and ambiguous cases.")
    else:
        print(f"\n  ✗ Pattern is NOT systematic: only {consistent_count}/{len(STRESS_WINDOWS)} windows")
        print(f"    show clear weakness. 2022 may be idiosyncratic.")

    # Best signal evaluation
    best_signal = min(signal_results.items(),
                      key=lambda kv: kv[1]["avg_pnl_flagged"] - kv[1]["avg_pnl_unflagged"])
    name, ev = best_signal
    delta = ev["avg_pnl_flagged"] - ev["avg_pnl_unflagged"]
    print(f"\n  Best candidate signal: {name}")
    print(f"    Coverage: {ev['coverage_pct']:.1f}%   FP rate: {ev['fp_rate_pct']:.1f}%")
    print(f"    Trades when active: {ev['n_flagged']}, avg PnL ${ev['avg_pnl_flagged']:,.0f}")
    print(f"    Trades when inactive: {ev['n_unflagged']}, avg PnL ${ev['avg_pnl_unflagged']:,.0f}")
    print(f"    Selectivity (Δavg): ${delta:,.0f}/trade")

    print()
    if delta < -3000 and ev['fp_rate_pct'] < 30:
        print(f"  → Signal is good enough to justify a candidate SPEC for follow-up.")
        print(f"    Next step: design entry-gate or sizing-reduction rule using this signal.")
    elif delta < -1000:
        print(f"  → Signal shows directional value but FP rate or selectivity needs refinement")
        print(f"    before SPEC. Consider tighter parameters or signal combinations.")
    else:
        print(f"  → No candidate signal cleanly separates grinding-decline from baseline.")
        print(f"    The pattern may exist but require a more nuanced detector.")


if __name__ == "__main__":
    run()
