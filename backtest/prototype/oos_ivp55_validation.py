"""
OOS Validation: BPS IVP gate IVP<50 vs IVP<55

Research question (Q015 continuation):
  Dead Zone B found IVP<55 is the only Pareto improvement for BPS gate:
    - Full history Sharpe 0.40 → 0.41, PnL +$18,107
    - IVP [50,55) subset: n=8, avg +$1,494, Sharpe 0.66

  Is this robust across out-of-sample splits, or in-sample noise?

Method:
  Split: 2000-2018 (in-sample) / 2019-2026 (out-of-sample)
  For each split, compare BPS_NNB_IVP_UPPER=50 vs 55.
  Report system Sharpe, PnL, trade count, BPS-specific metrics.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.oos_ivp55_validation
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

ACCOUNT_SIZE = 150_000.0
BPS_NAME = "Bull Put Spread"

PERIODS = [
    ("Full (2000-2026)", "2000-01-01", None),
    ("In-sample (2000-2018)", "2000-01-01", "2018-12-31"),
    ("Out-of-sample (2019-2026)", "2019-01-01", None),
]

THRESHOLDS = [50, 55]


def _trade_stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "total_pnl": 0, "avg_pnl": 0, "win_rate": 0, "sharpe": 0.0}
    pnls = [t.exit_pnl for t in trades]
    arr = np.array(pnls)
    n = len(pnls)
    mu = arr.mean()
    sigma = arr.std(ddof=1) if n > 1 else 0
    return {
        "n": n,
        "total_pnl": round(sum(pnls)),
        "avg_pnl": round(mu),
        "win_rate": round(sum(1 for p in pnls if p > 0) / n * 100, 1),
        "sharpe": round(mu / sigma, 2) if sigma > 0 else 0.0,
    }


def _bootstrap_str(trades: list[Trade]) -> str:
    if len(trades) < 5:
        return f"n={len(trades)}, too few"
    pnls = [t.exit_pnl for t in trades]
    ci = bootstrap_ci(pnls)
    lo, hi = ci["ci_lo"], ci["ci_hi"]
    if np.isnan(lo) or np.isnan(hi):
        return "NaN"
    sig = "SIG+" if lo > 0 else ("SIG-" if hi < 0 else "n.s.")
    return f"[${round(lo):,}, ${round(hi):,}] {sig}"


def run_validation():
    orig_upper = sel.BPS_NNB_IVP_UPPER

    results = {}  # (period_name, threshold) -> (system_stats, bps_stats, bps_trades, all_trades)

    for period_name, start, end in PERIODS:
        for thresh in THRESHOLDS:
            sel.BPS_NNB_IVP_UPPER = thresh
            label = f"{period_name} / IVP<{thresh}"
            print(f"  Running: {label} ...")
            bt = run_backtest(
                start_date=start,
                end_date=end,
                account_size=ACCOUNT_SIZE,
            )
            closed = [t for t in bt.trades if t.exit_reason != "end_of_backtest"]
            bps = [t for t in closed if t.strategy == BPS_NAME]
            results[(period_name, thresh)] = (
                _trade_stats(closed),
                _trade_stats(bps),
                bps,
                closed,
            )

    sel.BPS_NNB_IVP_UPPER = orig_upper

    # ── Report ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print(f"  OOS VALIDATION: BPS IVP GATE  IVP<50 vs IVP<55")
    print(f"{'=' * 90}")

    for period_name, _, _ in PERIODS:
        s50 = results[(period_name, 50)]
        s55 = results[(period_name, 55)]
        sys50, bps50, bps_t50, all_t50 = s50
        sys55, bps55, bps_t55, all_t55 = s55

        print(f"\n  ┌─ {period_name} ─────────────────────────────────────")

        # System-level
        print(f"  │ SYSTEM LEVEL")
        print(f"  │   {'':20} {'IVP<50':>12} {'IVP<55':>12} {'Delta':>10}")
        print(f"  │   {'─' * 20} {'─' * 12} {'─' * 12} {'─' * 10}")
        for k in ["n", "total_pnl", "avg_pnl", "win_rate", "sharpe"]:
            v1, v2 = sys50[k], sys55[k]
            d = v2 - v1
            if k == "total_pnl":
                print(f"  │   {k:<20} ${v1:>11,} ${v2:>11,} ${d:>+9,}")
            elif k == "win_rate":
                print(f"  │   {k:<20} {v1:>11.1f}% {v2:>11.1f}% {d:>+9.1f}%")
            elif k == "sharpe":
                print(f"  │   {k:<20} {v1:>12.2f} {v2:>12.2f} {d:>+10.2f}")
            else:
                print(f"  │   {k:<20} {v1:>12} {v2:>12} {d:>+10}")

        # BPS-level
        print(f"  │")
        print(f"  │ BPS ONLY")
        print(f"  │   {'':20} {'IVP<50':>12} {'IVP<55':>12} {'Delta':>10}")
        print(f"  │   {'─' * 20} {'─' * 12} {'─' * 12} {'─' * 10}")
        for k in ["n", "total_pnl", "avg_pnl", "win_rate", "sharpe"]:
            v1, v2 = bps50[k], bps55[k]
            d = v2 - v1
            if k == "total_pnl":
                print(f"  │   {k:<20} ${v1:>11,} ${v2:>11,} ${d:>+9,}")
            elif k == "win_rate":
                print(f"  │   {k:<20} {v1:>11.1f}% {v2:>11.1f}% {d:>+9.1f}%")
            elif k == "sharpe":
                print(f"  │   {k:<20} {v1:>12.2f} {v2:>12.2f} {d:>+10.2f}")
            else:
                print(f"  │   {k:<20} {v1:>12} {v2:>12} {d:>+10}")

        # IVP [50,55) subset — the marginal trades
        prod_entries = {(t.entry_date, t.strategy) for t in all_t50}
        marginal = [t for t in all_t55
                    if (t.entry_date, t.strategy) not in prod_entries
                    and t.strategy == BPS_NAME
                    and t.exit_reason != "end_of_backtest"]

        ms = _trade_stats(marginal)
        print(f"  │")
        print(f"  │ MARGINAL BPS (IVP [50,55) — new trades only)")
        print(f"  │   n={ms['n']}  total=${ms['total_pnl']:,}  avg=${ms['avg_pnl']:,}  "
              f"win={ms['win_rate']}%  sharpe={ms['sharpe']}")
        if marginal:
            bs = _bootstrap_str(marginal)
            print(f"  │   Bootstrap 95% CI: {bs}")

            # List individual trades
            print(f"  │")
            print(f"  │   {'Entry':>12} {'Exit':>12} {'PnL':>10} {'Exit Reason':<18}")
            print(f"  │   {'─' * 12} {'─' * 12} {'─' * 10} {'─' * 18}")
            for t in sorted(marginal, key=lambda x: x.entry_date):
                print(f"  │   {t.entry_date:>12} {t.exit_date:>12} "
                      f"${t.exit_pnl:>+9,.0f} {t.exit_reason:<18}")

        print(f"  └{'─' * 60}")

    # ── Stability summary ─────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print(f"  STABILITY SUMMARY")
    print(f"{'=' * 90}")

    for period_name, _, _ in PERIODS:
        sys50 = results[(period_name, 50)][0]
        sys55 = results[(period_name, 55)][0]
        delta_sharpe = sys55["sharpe"] - sys50["sharpe"]
        delta_pnl = sys55["total_pnl"] - sys50["total_pnl"]
        status = "IMPROVED" if delta_sharpe >= 0 and delta_pnl >= 0 else (
            "DEGRADED" if delta_sharpe < 0 else "MIXED")
        print(f"  {period_name:40s} Sharpe {delta_sharpe:+.2f}  PnL ${delta_pnl:+,}  → {status}")

    # Overall verdict
    oos_sys50 = results[("Out-of-sample (2019-2026)", 50)][0]
    oos_sys55 = results[("Out-of-sample (2019-2026)", 55)][0]
    is_sys50 = results[("In-sample (2000-2018)", 50)][0]
    is_sys55 = results[("In-sample (2000-2018)", 55)][0]

    oos_ok = oos_sys55["sharpe"] >= oos_sys50["sharpe"]
    is_ok = is_sys55["sharpe"] >= is_sys50["sharpe"]

    print(f"\n  VERDICT: ", end="")
    if oos_ok and is_ok:
        print("ROBUST — Sharpe non-degrading in both IS and OOS")
    elif oos_ok:
        print("OOS ROBUST, IS WEAK — improvement concentrates in recent data")
    elif is_ok:
        print("IS ONLY — OOS degrades, likely in-sample artifact")
    else:
        print("FAIL — degrades in both sub-periods")

    print()


if __name__ == "__main__":
    run_validation()
