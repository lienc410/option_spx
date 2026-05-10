"""
Q053 — Main Strategy Performance in Grinding-Decline Regimes (Tier 1)
=====================================================================

Source: R-20260509-02 Action A2.

Question:
    Does the main strategy systematically mis-route or over-allocate short
    premium exposure in medium-VIX grinding-decline environments where
    EXTREME_VOL gates do not trigger?

Tier 1 scope (this script):
    - Pull full main strategy backtest 2007-2026
    - Slice trades into:
        - 2018-Q4 (2018-10-01 to 2018-12-31)  — Q4 2018 selloff
        - 2022 full year (2022-01-01 to 2022-12-31)  — grinding bear market
        - "Other" (rest of sample)              — full-sample baseline
    - Compute per-window metrics:
        - Total PnL, WR, stop rate, avg P&L per trade
        - Regime distribution at entry (LOW_VOL / NORMAL / HIGH_VOL / EXTREME_VOL)
        - Per-strategy breakdown (BPS / IC / BCD / IC_HV / etc.)
    - Compare to "Other" baseline → identify systematic deviations

Tier 2 (out of scope; only if Tier 1 shows weakness):
    - 2011-Q3 (Eurozone crisis), 2015-Q3-2016-Q1, 2018-Q1 mini-stress windows
    - Candidate detection signal design (e.g. VIX rolling mean > 22 for 30+ days)

Boundary (per R-20260509-02):
    - Not re-running full backtest variants
    - Not re-evaluating EXTREME_VOL thresholds
    - Not based on SPX proxy data (uses real main strategy backtest output)
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


# ── Window definitions ────────────────────────────────────────────────────────

WINDOWS = {
    "2018-Q4 selloff":      ("2018-10-01", "2018-12-31"),
    "2022 grinding bear":   ("2022-01-01", "2022-12-31"),
}

FULL_START = "2007-01-01"
ACCOUNT    = 500_000.0


# ── Metrics helpers ───────────────────────────────────────────────────────────

@dataclass
class WindowMetrics:
    label:         str
    n_trades:      int
    total_pnl:     float
    win_rate:      float
    stop_rate:     float
    avg_pnl:       float
    median_pnl:    float
    worst_pnl:     float
    best_pnl:      float
    by_strategy:   dict             # strategy → (n, total_pnl, wr, stop_rate)
    by_exit:       dict             # exit_reason → count
    pnl_per_day:   float            # total_pnl / window_days


def _trades_in_window(trades, start: str, end: str):
    ts, te = pd.Timestamp(start), pd.Timestamp(end)
    out = []
    for t in trades:
        if not t.entry_date:
            continue
        try:
            ed = pd.Timestamp(t.entry_date)
        except Exception:
            continue
        if ts <= ed <= te:
            out.append(t)
    return out


def _window_metrics(label: str, trades, start: str, end: str) -> WindowMetrics:
    if not trades:
        return WindowMetrics(label, 0, 0, 0, 0, 0, 0, 0, 0, {}, {}, 0)
    pnls    = [t.exit_pnl for t in trades]
    wins    = [t for t in trades if t.exit_pnl > 0]
    stops   = [t for t in trades if t.exit_reason == "stop_loss"]

    by_strat = defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0, "stops": 0})
    for t in trades:
        s = str(t.strategy).split(".")[-1] if hasattr(t.strategy, "name") else str(t.strategy)
        by_strat[s]["n"] += 1
        by_strat[s]["pnl"] += t.exit_pnl
        if t.exit_pnl > 0:
            by_strat[s]["wins"] += 1
        if t.exit_reason == "stop_loss":
            by_strat[s]["stops"] += 1

    by_exit = defaultdict(int)
    for t in trades:
        by_exit[t.exit_reason or "unknown"] += 1

    days = max((pd.Timestamp(end) - pd.Timestamp(start)).days, 1)

    return WindowMetrics(
        label=label,
        n_trades=len(trades),
        total_pnl=sum(pnls),
        win_rate=len(wins)/len(trades)*100,
        stop_rate=len(stops)/len(trades)*100,
        avg_pnl=np.mean(pnls),
        median_pnl=float(np.median(pnls)),
        worst_pnl=min(pnls),
        best_pnl=max(pnls),
        by_strategy=dict(by_strat),
        by_exit=dict(by_exit),
        pnl_per_day=sum(pnls)/days,
    )


def _print_metrics(m: WindowMetrics) -> None:
    print(f"\n{'━'*78}")
    print(f"  {m.label}  (n={m.n_trades})")
    print(f"{'━'*78}")
    if m.n_trades == 0:
        print("  No trades in window.")
        return
    print(f"  Total PnL: ${m.total_pnl:,.0f}   PnL/day: ${m.pnl_per_day:,.1f}")
    print(f"  WR: {m.win_rate:.1f}%   Stop rate: {m.stop_rate:.1f}%")
    print(f"  Avg PnL: ${m.avg_pnl:,.0f}   Median: ${m.median_pnl:,.0f}")
    print(f"  Worst: ${m.worst_pnl:,.0f}   Best: ${m.best_pnl:,.0f}")
    print(f"\n  By strategy:")
    for s, data in sorted(m.by_strategy.items()):
        n     = data["n"]
        pnl   = data["pnl"]
        wr    = data["wins"]/n*100 if n else 0
        stp   = data["stops"]/n*100 if n else 0
        print(f"    {s:<28s}  n={n:>3}  pnl=${pnl:>+9,.0f}  WR={wr:>5.1f}%  Stop={stp:>5.1f}%")
    print(f"\n  Exit reasons: {dict(m.by_exit)}")


# ── Comparison ────────────────────────────────────────────────────────────────

def _print_comparison(window_m: WindowMetrics, baseline_m: WindowMetrics) -> None:
    """Print window vs baseline comparison."""
    if window_m.n_trades == 0 or baseline_m.n_trades == 0:
        return
    print(f"\n  ── vs baseline ('Other') ──")
    delta = lambda w, b: ((w - b) / abs(b) * 100) if b != 0 else 0
    print(f"    PnL/trade:   ${window_m.avg_pnl:>+9,.0f}  vs  baseline ${baseline_m.avg_pnl:>+9,.0f}  "
          f"({delta(window_m.avg_pnl, baseline_m.avg_pnl):+.1f}%)")
    print(f"    WR:          {window_m.win_rate:>5.1f}%   vs  baseline {baseline_m.win_rate:>5.1f}%   "
          f"({window_m.win_rate - baseline_m.win_rate:+.1f}pp)")
    print(f"    Stop rate:   {window_m.stop_rate:>5.1f}%   vs  baseline {baseline_m.stop_rate:>5.1f}%   "
          f"({window_m.stop_rate - baseline_m.stop_rate:+.1f}pp)")
    print(f"    Worst PnL:   ${window_m.worst_pnl:>+9,.0f}  vs  baseline ${baseline_m.worst_pnl:>+9,.0f}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 78)
    print("Q053 — Main Strategy Performance in Grinding-Decline Regimes (Tier 1)")
    print(f"  Window: {FULL_START} → today;  account NLV ${ACCOUNT:,.0f}")
    print("=" * 78)

    print("\n  Running full main-strategy backtest …", flush=True)
    r = run_backtest(start_date=FULL_START, account_size=ACCOUNT, verbose=False)
    trades = r.trades
    print(f"  Total trades: {len(trades)}")

    # Slice into windows
    win_trades  = {label: _trades_in_window(trades, s, e)
                   for label, (s, e) in WINDOWS.items()}
    in_any_win  = set()
    for tlist in win_trades.values():
        for t in tlist:
            in_any_win.add(id(t))
    other_trades = [t for t in trades if id(t) not in in_any_win]

    # Compute metrics
    window_metrics = {label: _window_metrics(label, win_trades[label], *WINDOWS[label])
                       for label in WINDOWS}
    full_start = trades[0].entry_date if trades else FULL_START
    full_end   = trades[-1].exit_date or trades[-1].entry_date if trades else FULL_START
    other_m    = _window_metrics("Other (baseline, rest of sample)",
                                  other_trades, full_start, full_end)

    # Print
    _print_metrics(other_m)
    for label in WINDOWS:
        _print_metrics(window_metrics[label])
        _print_comparison(window_metrics[label], other_m)

    # Verdict
    print("\n\n" + "=" * 78)
    print("VERDICT — does main strategy systematically suffer in grinding decline?")
    print("=" * 78)

    base_avg   = other_m.avg_pnl
    base_wr    = other_m.win_rate
    base_stop  = other_m.stop_rate
    base_worst = other_m.worst_pnl

    findings = []
    for label, m in window_metrics.items():
        if m.n_trades == 0:
            continue
        avg_dev    = (m.avg_pnl - base_avg) / abs(base_avg) * 100 if base_avg else 0
        wr_dev_pp  = m.win_rate - base_wr
        stop_dev   = m.stop_rate - base_stop
        worst_x    = m.worst_pnl / base_worst if base_worst < 0 else 0

        flags = []
        if avg_dev < -30:        flags.append(f"avg PnL drops {avg_dev:.0f}%")
        if wr_dev_pp < -5:       flags.append(f"WR drops {wr_dev_pp:.1f}pp")
        if stop_dev > 5:         flags.append(f"stop rate +{stop_dev:.1f}pp")
        if worst_x > 1.5:        flags.append(f"worst trade {worst_x:.1f}× baseline")

        findings.append((label, m, flags))

    for label, m, flags in findings:
        print(f"\n  {label}:")
        if flags:
            for f in flags:
                print(f"    ⚠️  {f}")
        else:
            print(f"    ✓ No significant deviation from baseline")
        print(f"    PnL ${m.total_pnl:,.0f} over {m.n_trades} trades  "
              f"(${m.pnl_per_day:.0f}/day vs baseline ${other_m.pnl_per_day:.0f}/day)")

    # Summary judgment
    has_systematic_weakness = any(flags for _, _, flags in findings)
    print()
    if has_systematic_weakness:
        print("  → Tier 1 finding: main strategy DOES show systematic weakness in")
        print("    grinding-decline windows. Tier 2 expansion (2011/2015/2018-Q1)")
        print("    is justified to test if pattern is consistent.")
    else:
        print("  → Tier 1 finding: NO systematic weakness detected in 2018-Q4 / 2022.")
        print("    Main strategy's existing risk_score / regime gating appears to")
        print("    handle grinding decline adequately. Tier 2 expansion not justified.")


if __name__ == "__main__":
    run()
