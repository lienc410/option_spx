"""Q045 Phase 2B — HIGH_VOL regime bp_target sweep.

Tests bp_target_high_vol variants (currently 7%):
  H0 (baseline): bp_target_high_vol = 0.07 (current)
  H1:            bp_target_high_vol = 0.10
  H2:            bp_target_high_vol = 0.14  # = Overlay-F 2x equivalent

Direct comparison to Q036 Overlay-F: lifting base bp_target to 14% is the
"simple" alternative to Overlay-F's gated 2x mechanism. If the simple lift
gives equivalent uplift without the Overlay-F machinery, the simpler path
may be preferred.

NORMAL regime kept at baseline 10% to isolate HIGH_VOL effect.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtest.engine import run_backtest, DEFAULT_PARAMS
from strategy.selector import StrategyName

WINDOW_START = "2023-01-01"
ACCOUNT_SIZE = 150_000.0
YEARS = (date.today() - pd.to_datetime(WINDOW_START).date()).days / 365.25


def _key(t):
    return t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)


def _per_strat(trades):
    by = defaultdict(list)
    for t in trades:
        by[_key(t)].append(t)
    out = {}
    for s, ts in by.items():
        pnls = [t.exit_pnl for t in ts]
        bp_d = sum(t.total_bp * t.hold_days for t in ts if t.hold_days and t.total_bp)
        out[s] = {
            "n": len(ts),
            "pnl": round(sum(pnls), 0),
            "win_rt": round(sum(1 for p in pnls if p > 0)/len(ts)*100, 1) if ts else 0,
            "ann_roe": round(sum(pnls) / ACCOUNT_SIZE / YEARS * 100, 3),
            "avg_bp": round(np.mean([t.bp_pct_account for t in ts if t.bp_pct_account]), 1) if ts else 0,
            "per_bp_day": round(sum(pnls)/bp_d, 5) if bp_d > 0 else 0,
            "worst": round(min(pnls), 0) if pnls else 0,
        }
    return out


def _peak_bp(trades):
    events = []
    for t in trades:
        if t.entry_date and t.exit_date:
            events.append((t.entry_date, +t.bp_pct_account))
            events.append((t.exit_date,  -t.bp_pct_account))
    events.sort(key=lambda x: x[0])
    cur, peak = 0.0, 0.0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return round(peak, 1)


def _avg_bp(trades):
    if not trades:
        return 0.0
    start = pd.to_datetime(WINDOW_START).date()
    days = pd.date_range(start, date.today(), freq="D")
    bp_series = pd.Series(0.0, index=days)
    for t in trades:
        if not t.entry_date or not t.exit_date:
            continue
        e = pd.to_datetime(t.entry_date).date()
        x = pd.to_datetime(t.exit_date).date()
        mask = (bp_series.index >= pd.Timestamp(e)) & (bp_series.index <= pd.Timestamp(x))
        bp_series.loc[mask] += t.bp_pct_account
    trading = bp_series[bp_series.index.weekday < 5]
    return round(float(trading.mean()), 2)


def _account_metrics(trades):
    pnls = sorted(t.exit_pnl for t in trades)
    total = sum(pnls)
    n = len(pnls)
    cvar5 = float(np.mean(pnls[:max(1, int(n * 0.05))]))
    pnl_arr = np.array([t.exit_pnl for t in trades])
    sharpe = (pnl_arr.mean() / pnl_arr.std() * np.sqrt(n / YEARS)
              if pnl_arr.std() > 0 else float("nan"))
    return {
        "total_pnl": round(total, 0),
        "ann_roe": round(total / ACCOUNT_SIZE / YEARS * 100, 3),
        "n_trades": n,
        "cvar5": round(cvar5, 0),
        "sharpe": round(sharpe, 2),
        "worst": round(min(pnls), 0) if pnls else 0,
    }


def run_variant(label: str, bp_high: float):
    print(f"  Running {label}...", flush=True)
    p = deepcopy(DEFAULT_PARAMS)
    p.bp_target_high_vol = bp_high
    r = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p)
    return {
        "label": label,
        "bp_target_high": bp_high,
        "trades": r.trades,
        "per_strat": _per_strat(r.trades),
        "peak_bp": _peak_bp(r.trades),
        "avg_bp": _avg_bp(r.trades),
        "account": _account_metrics(r.trades),
    }


def main():
    print("Q045 Phase 2B — HIGH_VOL regime bp_target sweep")
    print("=" * 90)
    print(f"Window: {WINDOW_START} → today  |  Account: ${ACCOUNT_SIZE:,.0f}  |  Years: {YEARS:.2f}")
    print(f"NORMAL bp_target kept at 10% baseline; only bp_target_high_vol varies\n")

    print("Running variants...")
    results = [
        run_variant("H0 bp=7%  (baseline)", 0.07),
        run_variant("H1 bp=10%", 0.10),
        run_variant("H2 bp=14% (=2x baseline ≈ Overlay-F)", 0.14),
    ]

    # ── Account-level summary ─────────────────────────────────────────
    print("\n" + "═" * 90)
    print("ACCOUNT-LEVEL SUMMARY")
    print("═" * 90)
    hdr = f"{'Variant':<35} {'TotalPnL':>10} {'AnnROE%':>8} {'N':>4} {'Peak%':>6} {'AvgBP%':>7} {'CVaR5':>9} {'Worst':>9} {'Sharpe':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        a = r["account"]
        print(f"{r['label']:<35} {a['total_pnl']:>10,.0f} {a['ann_roe']:>8.3f} "
              f"{a['n_trades']:>4} {r['peak_bp']:>6.1f} {r['avg_bp']:>7.2f} "
              f"{a['cvar5']:>9,.0f} {a['worst']:>9,.0f} {a['sharpe']:>7.2f}")

    # ── Per-strategy HIGH_VOL detail ──────────────────────────────────
    hv_strats = ["Iron Condor (High Vol)", "Bull Put Spread (High Vol)", "Bear Call Spread (High Vol)"]
    print("\n── HIGH_VOL Strategy Breakdown ──")
    hdr2 = f"{'Strategy':<32} {'Variant':<22} {'N':>4} {'WR%':>5} {'PnL':>9} {'AnnROE':>7} {'AvgBP%':>7} {'Worst':>9}"
    print(hdr2)
    print("-" * len(hdr2))
    for strat in hv_strats:
        for r in results:
            data = r["per_strat"].get(strat, {})
            if not data:
                continue
            print(f"{strat:<32} {r['label']:<22} "
                  f"{data['n']:>4} {data['win_rt']:>5.1f} "
                  f"{data['pnl']:>9,.0f} {data['ann_roe']:>7.3f} "
                  f"{data['avg_bp']:>7.1f} {data['worst']:>9,.0f}")
        print()

    # ── NORMAL strategies should be unchanged ─────────────────────────
    print("── NORMAL strategies (should be unchanged across H variants) ──")
    norm_strats = ["Bull Call Diagonal", "Bull Put Spread", "Iron Condor"]
    for strat in norm_strats:
        anns = [results[i]["per_strat"].get(strat, {}).get("ann_roe", 0) for i in range(3)]
        print(f"  {strat:<32} AnnROE: {anns[0]:.3f} / {anns[1]:.3f} / {anns[2]:.3f}")

    # ── ROE attribution delta ─────────────────────────────────────────
    print("\n── ROE Attribution by Strategy (AnnROE pp delta from H0) ──")
    print(f"{'Strategy':<32} {'H0':>9} {'H1':>9} {'H2':>9} {'ΔH1':>8} {'ΔH2':>8}")
    print("-" * 90)
    for strat in hv_strats:
        d = [results[i]["per_strat"].get(strat, {"ann_roe": 0}) for i in range(3)]
        a = [d[i]["ann_roe"] for i in range(3)]
        print(f"{strat:<32} {a[0]:>9.3f} {a[1]:>9.3f} {a[2]:>9.3f} "
              f"{a[1]-a[0]:>+8.3f} {a[2]-a[0]:>+8.3f}")
    print("-" * 90)
    t = [results[i]["account"]["ann_roe"] for i in range(3)]
    print(f"{'TOTAL':<32} {t[0]:>9.3f} {t[1]:>9.3f} {t[2]:>9.3f} "
          f"{t[1]-t[0]:>+8.3f} {t[2]-t[0]:>+8.3f}")

    # ── Comparison to Q036 Overlay-F finding ─────────────────────────
    print("\n── Q036 Overlay-F Comparison ──")
    print("  Q036 finding: Overlay-F 2x factor on IC_HV aftermath delivers +0.074pp AnnROE")
    print("  (full sample 2007-2026; tested via gated 2x factor with short-gamma guard)")
    print()
    h2_uplift = results[2]["account"]["ann_roe"] - results[0]["account"]["ann_roe"]
    print(f"  Q045 Phase 2B finding (3y window, 2023-now):")
    print(f"  Lifting bp_target_high_vol 7% → 14% (no gate, no overlay machinery): {h2_uplift:+.3f}pp AnnROE")
    print(f"  Trade-off: simpler implementation, but no short-gamma guard, no fail-closed")


if __name__ == "__main__":
    main()
