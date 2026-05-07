"""Q045 Phase 2A — NORMAL regime bp_target sweep.

Engine reality: bp_target is regime-level, not strategy-level.
Changing bp_target_normal scales BPS, BCD, IC simultaneously when they
are in NORMAL regime. This phase tests the joint effect.

Variants:
  N0 (baseline): bp_target_normal = 0.10 (current)
  N1:            bp_target_normal = 0.15
  N2:            bp_target_normal = 0.20

Per variant:
  - Per-strategy: N, total PnL, AnnROE, $/BP-day
  - Account-level: total ROE, peak BP%, avg BP%, Sharpe
  - Strategy-by-strategy attribution
  - Cliff identification (which strategies blocked at N2)
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
        return 0.0, 0.0
    start = pd.to_datetime(WINDOW_START).date()
    end = date.today()
    days = pd.date_range(start, end, freq="D")
    bp_series = pd.Series(0.0, index=days)
    for t in trades:
        if not t.entry_date or not t.exit_date:
            continue
        e = pd.to_datetime(t.entry_date).date()
        x = pd.to_datetime(t.exit_date).date()
        mask = (bp_series.index >= pd.Timestamp(e)) & (bp_series.index <= pd.Timestamp(x))
        bp_series.loc[mask] += t.bp_pct_account
    trading = bp_series[bp_series.index.weekday < 5]
    return round(float(trading.mean()), 2), round(float(trading.median()), 2)


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


def run_variant(label: str, bp_normal: float):
    print(f"  Running {label}...", flush=True)
    p = deepcopy(DEFAULT_PARAMS)
    p.bp_target_normal = bp_normal
    p.bp_target_low_vol = bp_normal  # NORMAL+LOW_VOL share many strategies
    r = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p)
    return {
        "label": label,
        "bp_target": bp_normal,
        "trades": r.trades,
        "per_strat": _per_strat(r.trades),
        "peak_bp": _peak_bp(r.trades),
        "avg_bp": _avg_bp(r.trades),
        "account": _account_metrics(r.trades),
    }


def print_per_strat_table(results: list, target_strats: list[str]):
    print("\n── Per-Strategy Breakdown ──")
    hdr = f"{'Strategy':<32} {'Variant':<14} {'N':>4} {'WR%':>5} {'PnL':>10} {'AnnROE':>7} {'AvgBP%':>7} {'$/BPday':>9}"
    print(hdr)
    print("-" * len(hdr))
    for strat in target_strats:
        for r in results:
            data = r["per_strat"].get(strat, {})
            if not data:
                continue
            print(f"{strat[:32]:<32} {r['label']:<14} "
                  f"{data['n']:>4} {data['win_rt']:>5.1f} "
                  f"{data['pnl']:>10,.0f} {data['ann_roe']:>7.3f} "
                  f"{data['avg_bp']:>7.1f} {data['per_bp_day']:>9.5f}")
        print()


def main():
    print("Q045 Phase 2A — NORMAL regime bp_target sweep")
    print("=" * 90)
    print(f"Window: {WINDOW_START} → today  |  Account: ${ACCOUNT_SIZE:,.0f}  |  Years: {YEARS:.2f}")
    print(f"Mechanism: bp_target_normal applies to BPS / BCD / IC (NORMAL regime joint scaling)\n")

    print("Running variants...")
    results = [
        run_variant("N0 bp=10%", 0.10),
        run_variant("N1 bp=15%", 0.15),
        run_variant("N2 bp=20%", 0.20),
    ]

    # ── Account-level summary ─────────────────────────────────────────
    print("\n" + "═" * 90)
    print("ACCOUNT-LEVEL SUMMARY")
    print("═" * 90)
    hdr = f"{'Variant':<14} {'TotalPnL':>10} {'AnnROE%':>8} {'N':>5} {'Peak%':>6} {'AvgBP%':>7} {'CVaR5':>9} {'Worst':>9} {'Sharpe':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        a = r["account"]
        avg, _ = r["avg_bp"]
        print(f"{r['label']:<14} {a['total_pnl']:>10,.0f} {a['ann_roe']:>8.3f} "
              f"{a['n_trades']:>5} {r['peak_bp']:>6.1f} {avg:>7.2f} "
              f"{a['cvar5']:>9,.0f} {a['worst']:>9,.0f} {a['sharpe']:>7.2f}")

    # ── Per-strategy sweep ────────────────────────────────────────────
    primary = ["Bull Call Diagonal", "Bull Put Spread", "Iron Condor"]
    aux     = ["Iron Condor (High Vol)", "Bull Put Spread (High Vol)", "Bear Call Spread (High Vol)"]
    print_per_strat_table(results, primary)
    print("--- HIGH_VOL strategies (should be unchanged across variants) ---")
    print_per_strat_table(results, aux)

    # ── Marginal analysis ─────────────────────────────────────────────
    print("\n── Marginal $/BP-day Decay (per strategy) ──")
    print(f"{'Strategy':<32} {'N0':>10} {'N1':>10} {'N2':>10} {'N0→N1':>9} {'N0→N2':>9}")
    print("-" * 95)
    for strat in primary:
        d0 = results[0]["per_strat"].get(strat, {})
        d1 = results[1]["per_strat"].get(strat, {})
        d2 = results[2]["per_strat"].get(strat, {})
        if not (d0 and d1 and d2):
            continue
        v0 = d0["per_bp_day"]
        v1 = d1["per_bp_day"]
        v2 = d2["per_bp_day"]
        decay_1 = (v1 - v0) / v0 * 100 if v0 else 0
        decay_2 = (v2 - v0) / v0 * 100 if v0 else 0
        print(f"{strat:<32} {v0:>10.5f} {v1:>10.5f} {v2:>10.5f} "
              f"{decay_1:>+8.1f}% {decay_2:>+8.1f}%")

    # ── Trade count delta (cliff detection) ──────────────────────────
    print("\n── Trade Count vs Baseline (cliff detection) ──")
    base = results[0]["per_strat"]
    for r in results[1:]:
        print(f"\n  {r['label']}:")
        for strat in primary:
            n0 = base.get(strat, {}).get("n", 0)
            n1 = r["per_strat"].get(strat, {}).get("n", 0)
            delta = n1 - n0
            print(f"    {strat:<32} N={n1:>3} (vs N0={n0:>3}, Δ={delta:+d})")

    # ── PnL attribution per variant ──────────────────────────────────
    print("\n── ROE Attribution by Strategy (AnnROE pp) ──")
    print(f"{'Strategy':<32} {'N0':>9} {'N1':>9} {'N2':>9} {'ΔN1':>8} {'ΔN2':>8}")
    print("-" * 90)
    for strat in primary + aux:
        d0 = results[0]["per_strat"].get(strat, {})
        d1 = results[1]["per_strat"].get(strat, {})
        d2 = results[2]["per_strat"].get(strat, {})
        if not d0 and not d1 and not d2:
            continue
        a0 = d0.get("ann_roe", 0)
        a1 = d1.get("ann_roe", 0)
        a2 = d2.get("ann_roe", 0)
        print(f"{strat:<32} {a0:>9.3f} {a1:>9.3f} {a2:>9.3f} "
              f"{a1-a0:>+8.3f} {a2-a0:>+8.3f}")

    # Total
    print("-" * 90)
    t0 = results[0]["account"]["ann_roe"]
    t1 = results[1]["account"]["ann_roe"]
    t2 = results[2]["account"]["ann_roe"]
    print(f"{'TOTAL':<32} {t0:>9.3f} {t1:>9.3f} {t2:>9.3f} {t1-t0:>+8.3f} {t2-t0:>+8.3f}")


if __name__ == "__main__":
    main()
