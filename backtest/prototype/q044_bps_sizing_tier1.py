"""Q044 Tier 1 Quick Scan — BPS spread sizing and account-level ROE.

Axis A: bp_target_normal variants — same delta structure (δ0.30/0.15), more contracts
  A0 (baseline): bp_target = 0.10  (current)
  A1:            bp_target = 0.15  (+50% size)
  A2:            bp_target = 0.20  (+100% size)

Axis B: normal_delta variants — wider spread structure, same bp_target = 0.10
  B0 (baseline): normal_delta = 0.30 → short δ0.30, long δ0.15 (~130-150pt spread)
  B1:            normal_delta = 0.25 → short δ0.25, long δ0.125 (wider, less premium)
  B2:            normal_delta = 0.20 → short δ0.20, long δ0.10 (widest, lowest premium)

Window: 2023-01-01 → today.  Account: $150,000.
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from backtest.engine import run_backtest, StrategyParams, DEFAULT_PARAMS
from strategy.selector import StrategyName

WINDOW_START  = "2023-01-01"
ACCOUNT_SIZE  = 150_000.0
BPS_KEY       = StrategyName.BULL_PUT_SPREAD


def _bps_only(trades):
    return [t for t in trades if t.strategy == BPS_KEY]


def _metrics(label: str, trades, all_trades) -> dict:
    bps = _bps_only(trades)
    n   = len(bps)
    if n == 0:
        return {"label": label, "n_bps": 0}

    pnls   = [t.exit_pnl for t in bps]
    widths = [t.spread_width for t in bps]
    win_rt = sum(1 for p in pnls if p > 0) / n * 100
    worst  = min(pnls)

    # Marginal $/BP-day = total_pnl / Σ(total_bp_$ × hold_days)
    bp_days = sum(t.total_bp * t.hold_days for t in bps if t.hold_days and t.total_bp)
    marg    = sum(pnls) / bp_days if bp_days > 0 else 0.0

    # Annualised BPS ROE contribution
    from datetime import date
    import pandas as pd
    yrs         = (date.today() - pd.to_datetime(WINDOW_START).date()).days / 365.25
    ann_roe     = (sum(pnls) / ACCOUNT_SIZE / yrs * 100) if yrs > 0 else 0.0

    # CVaR 5% (account-level, all strategies)
    all_pnl = sorted(t.exit_pnl for t in all_trades)
    cvar5   = float(np.mean(all_pnl[:max(1, int(len(all_pnl) * 0.05))]))

    return {
        "label":       label,
        "n_bps":       n,
        "win_rt":      round(win_rt, 1),
        "total_pnl":   round(sum(pnls), 0),
        "ann_roe_pp":  round(ann_roe, 3),
        "avg_bp_pct":  round(np.mean([t.bp_pct_account for t in bps if t.bp_pct_account]), 1),
        "avg_width":   round(float(np.mean(widths)), 1),
        "avg_hold":    round(float(np.mean([t.hold_days for t in bps if t.hold_days])), 1),
        "marg_bpday":  round(marg, 5),
        "worst":       round(worst, 0),
        "cvar5":       round(cvar5, 0),
    }


def run_variant(label: str, params: StrategyParams) -> dict:
    print(f"  Running {label}...", flush=True)
    r = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=params)
    return _metrics(label, r.trades, r.trades)


def print_table(rows: list[dict]) -> None:
    hdr = (f"{'Variant':<28} {'N':>4} {'WR%':>6} {'BPS PnL':>9} "
           f"{'AnnROE%':>8} {'AvgBP%':>7} {'AvgWid':>7} {'$/BPday':>9} "
           f"{'Worst':>9} {'CVaR5%':>9}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if r.get("n_bps", 0) == 0:
            print(f"{r['label']:<28}   — no BPS trades")
            continue
        print(
            f"{r['label']:<28} "
            f"{r['n_bps']:>4} "
            f"{r['win_rt']:>6.1f} "
            f"{r['total_pnl']:>9,.0f} "
            f"{r['ann_roe_pp']:>8.3f} "
            f"{r['avg_bp_pct']:>7.1f} "
            f"{r['avg_width']:>7.1f} "
            f"{r['marg_bpday']:>9.5f} "
            f"{r['worst']:>9,.0f} "
            f"{r['cvar5']:>9,.0f}"
        )


def main() -> None:
    print("Q044 Tier 1 Quick Scan — BPS Sizing Variants")
    print("=" * 70)
    print(f"Window: {WINDOW_START} → today  |  Account: ${ACCOUNT_SIZE:,.0f}\n")

    results_a, results_b = [], []

    # ── Axis A: bp_target variants ────────────────────────────────────
    print("Axis A: bp_target_normal variants (same δ0.30/0.15 structure)")
    for label, bp in [
        ("A0-baseline bp=10%", 0.10),
        ("A1-medium   bp=15%", 0.15),
        ("A2-large    bp=20%", 0.20),
    ]:
        p = deepcopy(DEFAULT_PARAMS)
        p.bp_target_normal  = bp
        p.bp_target_low_vol = bp
        results_a.append(run_variant(label, p))

    # ── Axis B: spread-width variants (different normal_delta) ────────
    print("\nAxis B: normal_delta variants (wider spread, bp_target = 10%)")
    for label, nd in [
        ("B0-baseline δ0.30/0.15", 0.30),
        ("B1-moderate δ0.25/0.125", 0.25),
        ("B2-wide     δ0.20/0.10",  0.20),
    ]:
        p = deepcopy(DEFAULT_PARAMS)
        p.normal_delta      = nd
        p.bp_target_normal  = 0.10
        p.bp_target_low_vol = 0.10
        results_b.append(run_variant(label, p))

    # ── Results ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("AXIS A — more size (same spread structure)")
    print_table(results_a)

    print()
    print("AXIS B — wider spread (same bp_target)")
    print_table(results_b)

    # ── Axis A marginal ───────────────────────────────────────────────
    valid_a = [r for r in results_a if r.get("n_bps", 0) > 0]
    if len(valid_a) >= 2:
        print("\nAxis A — Marginal $/BP-day vs baseline:")
        base = valid_a[0]
        for r in valid_a[1:]:
            d_pnl = r["total_pnl"] - base["total_pnl"]
            d_bp  = r["avg_bp_pct"] - base["avg_bp_pct"]
            decay = (r["marg_bpday"] - base["marg_bpday"]) / base["marg_bpday"] * 100 if base["marg_bpday"] else 0
            print(f"  {r['label']}: ΔPNL={d_pnl:+,.0f}  ΔBP%={d_bp:+.1f}pp  "
                  f"marginal_decay={decay:+.1f}%")

    # ── Verdict ───────────────────────────────────────────────────────
    print("\nNotes:")
    print("  $/BPday = BPS total PnL / Σ(total_bp_$ × hold_days)")
    print("  CVaR5%  = account-level mean worst-5% trades (all strategies)")
    print("  AnnROE% = BPS-only PnL / account / years  (not full portfolio)")
    print("  Axis B changes BOTH short and long delta (same 0.5 ratio)")
    print("  B2 has same δ as BPS_HV but in NORMAL-regime entry context")


if __name__ == "__main__":
    main()
