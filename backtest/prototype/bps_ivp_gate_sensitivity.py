"""
BPS IVP Gate Sensitivity & Net Value Analysis

Target gate: NORMAL + IV_NEUTRAL + BULLISH → iv.iv_percentile >= 50 → REDUCE_WAIT
  (strategy/selector.py — BPS_NNB_IVP_UPPER)
This gate restricts BPS entry to a narrow IVP window [43, 50).

Method: monkey-patch sel.BPS_NNB_IVP_UPPER and re-run the backtest.
  (disable_entry_gates does NOT bypass this check — only BCS ivp63 and the
   retired DIAGONAL Gate 1 were behind that flag.)

Phase 1 — Sensitivity: run full backtests for IVP upper ∈ {45, 50, 55, 60, 65, 70, 999}.
Phase 2 — Net Value: compare gate-on (50) vs gate-off (999); identify blocked trades,
                     bootstrap their PnL, measure displacement to other strategies.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.bps_ivp_gate_sensitivity
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0
BPS_NAME = "Bull Put Spread"

IVP_UPPER_CANDIDATES = [45, 50, 55, 60, 65, 70, 999]
CURRENT_VALUE = 50


def _bps_trades(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.strategy == BPS_NAME]


def _stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "total_pnl": 0, "avg_pnl": 0, "win_rate": 0,
                "sharpe": 0, "worst": 0, "best": 0}
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
        "sharpe": round(mu / sigma, 2) if sigma > 0 else 0,
        "worst": round(min(pnls)),
        "best": round(max(pnls)),
    }


def _trade_max_dd(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    equity = peak = 0.0
    worst = 0.0
    for t in sorted(trades, key=lambda x: x.exit_date):
        equity += t.exit_pnl
        if equity > peak:
            peak = equity
        dd = equity - peak
        if dd < worst:
            worst = dd
    return worst


def _print_trade_table(trades: list[Trade], label: str, max_rows: int = 40):
    print(f"\n  {label} ({len(trades)} trades)")
    print(f"  {'Entry':>12} {'Exit':>12} {'DTE':>5} {'PnL':>10} {'Exit Reason':<18}")
    print(f"  {'─'*12} {'─'*12} {'─'*5} {'─'*10} {'─'*18}")
    shown = sorted(trades, key=lambda x: x.entry_date)
    if len(shown) > max_rows:
        shown = shown[:max_rows]
        truncated = True
    else:
        truncated = False
    for t in shown:
        print(f"  {t.entry_date:>12} {t.exit_date:>12} {t.dte_at_entry:>5} ${t.exit_pnl:>+9,.0f} {t.exit_reason:<18}")
    if truncated:
        print(f"  ... ({len(trades) - max_rows} more rows omitted)")


def run_sensitivity():
    original_upper = sel.BPS_NNB_IVP_UPPER
    results = []
    cache: dict[int, object] = {}  # ivp_upper -> BacktestResult

    # ── Phase 1: Sensitivity runs ─────────────────────────────────────
    for ivp_upper in IVP_UPPER_CANDIDATES:
        sel.BPS_NNB_IVP_UPPER = ivp_upper
        marker = " ◄ CURRENT" if ivp_upper == CURRENT_VALUE else ""
        label = "DISABLED" if ivp_upper == 999 else str(ivp_upper)

        print(f"\n{'='*70}")
        print(f"  Running backtest with BPS_NNB_IVP_UPPER = {label}{marker}")
        print(f"  (BPS blocked when IVP >= {label}; floor still at {sel.BPS_NNB_IVP_LOWER})")
        print(f"{'='*70}")

        bt = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
        cache[ivp_upper] = bt

        bps = _bps_trades(bt.trades)
        s = _stats(bps)
        max_dd = _trade_max_dd(bps)

        ci_lo = ci_hi = None
        if len(bps) >= 5:
            ci = bootstrap_ci([t.exit_pnl for t in bps])
            lo, hi = ci["ci_lo"], ci["ci_hi"]
            if not (np.isnan(lo) or np.isnan(hi)):
                ci_lo = round(lo)
                ci_hi = round(hi)

        print(f"  BPS trades: {s['n']} | Avg ${s['avg_pnl']:+,} | "
              f"WinRate {s['win_rate']}% | Sharpe {s['sharpe']} | MaxDD ${round(max_dd):+,}")
        if ci_lo is not None:
            print(f"  Bootstrap CI: [${ci_lo:+,}, ${ci_hi:+,}]")

        results.append({
            "ivp_upper": ivp_upper,
            "label": label,
            **s,
            "max_dd": round(max_dd),
            "ci_lo": ci_lo,
            "ci_hi": ci_hi,
            "all_trades_pnl": round(sum(t.exit_pnl for t in bt.trades)),
            "all_trades_n": len(bt.trades),
        })

    # Restore
    sel.BPS_NNB_IVP_UPPER = original_upper

    # ── Summary table ─────────────────────────────────────────────────
    print(f"\n\n{'='*96}")
    print("  SENSITIVITY SUMMARY — BPS Gate P1 (NORMAL+NEUTRAL+BULLISH, IVP upper)")
    print(f"  IVP floor fixed at {sel.BPS_NNB_IVP_LOWER} | Other upstream gates unchanged")
    print(f"  BPS entry window: IVP ∈ [{sel.BPS_NNB_IVP_LOWER}, upper)")
    print(f"{'='*96}")
    print(f"  {'Threshold':>10} {'BPS n':>6} {'BPS Avg':>9} {'WinRate':>8} "
          f"{'Sharpe':>7} {'BPS MaxDD':>10} {'CI Lo':>9} {'CI Hi':>9} "
          f"{'Sys n':>6} {'Sys PnL':>11}")
    print(f"  {'─'*10} {'─'*6} {'─'*9} {'─'*8} {'─'*7} {'─'*10} "
          f"{'─'*9} {'─'*9} {'─'*6} {'─'*11}")
    for r in results:
        marker = " ◄" if r["ivp_upper"] == CURRENT_VALUE else "  "
        ci_lo_s = f"${r['ci_lo']:+,}" if r["ci_lo"] is not None else "—"
        ci_hi_s = f"${r['ci_hi']:+,}" if r["ci_hi"] is not None else "—"
        print(
            f"{marker}{r['label']:>8} {r['n']:>6} ${r['avg_pnl']:>+8,} "
            f"{r['win_rate']:>7.1f}% {r['sharpe']:>7.2f} ${r['max_dd']:>+9,} "
            f"{ci_lo_s:>9} {ci_hi_s:>9} "
            f"{r['all_trades_n']:>6} ${r['all_trades_pnl']:>+10,}"
        )
    print(f"\n  ◄ = current production value ({CURRENT_VALUE})")
    print(f"  Sys columns = total system PnL / trade count across ALL strategies")

    # ── Phase 2: Net value — gate-on (50) vs gate-off (999) ───────────
    print(f"\n\n{'='*70}")
    print("  PHASE 2 — Net Value Analysis: Gate P1 (IVP ≥ 50) on vs off")
    print(f"{'='*70}")

    bt_on = cache[CURRENT_VALUE]
    bt_off = cache[999]

    bps_on = _bps_trades(bt_on.trades)
    bps_off = _bps_trades(bt_off.trades)

    dates_on = {t.entry_date for t in bps_on}
    dates_off = {t.entry_date for t in bps_off}

    blocked_dates = dates_off - dates_on
    displaced_dates = dates_on - dates_off  # BPS only exists with gate on (capital shift)
    blocked = [t for t in bps_off if t.entry_date in blocked_dates]
    displaced = [t for t in bps_on if t.entry_date in displaced_dates]

    s_on = _stats(bps_on)
    s_off = _stats(bps_off)
    s_blocked = _stats(blocked)
    s_displaced = _stats(displaced)

    print(f"\n  ┌─ BPS trades WITHOUT gate (IVP floor 43, no upper)")
    print(f"  │  Trades: {s_off['n']}, Total PnL: ${s_off['total_pnl']:+,}, "
          f"Avg: ${s_off['avg_pnl']:+,}, Sharpe: {s_off['sharpe']}, "
          f"WinRate: {s_off['win_rate']}%")
    print(f"  │")
    print(f"  ├─ BPS trades WITH gate (production, IVP ∈ [43, 50))")
    print(f"  │  Trades: {s_on['n']}, Total PnL: ${s_on['total_pnl']:+,}, "
          f"Avg: ${s_on['avg_pnl']:+,}, Sharpe: {s_on['sharpe']}, "
          f"WinRate: {s_on['win_rate']}%")
    print(f"  │")
    print(f"  ├─ Blocked by gate (exist only in gate-OFF run)")
    print(f"  │  Trades: {s_blocked['n']}, Total PnL: ${s_blocked['total_pnl']:+,}, "
          f"Avg: ${s_blocked['avg_pnl']:+,}")
    print(f"  │  Win Rate: {s_blocked['win_rate']}%, "
          f"Worst: ${s_blocked['worst']:+,}, Best: ${s_blocked['best']:+,}")

    if displaced:
        print(f"  │")
        print(f"  ├─ Displacement (BPS trades only present WITH gate — capital shift)")
        print(f"  │  Trades: {s_displaced['n']}, Total PnL: ${s_displaced['total_pnl']:+,}, "
              f"Avg: ${s_displaced['avg_pnl']:+,}")

    net_bps_impact = s_on["total_pnl"] - s_off["total_pnl"]
    print(f"  │")
    print(f"  └─ NET BPS IMPACT (gate-on − gate-off): ${net_bps_impact:+,}")
    if net_bps_impact > 0:
        print(f"     → Gate is PROTECTING ${net_bps_impact:+,} in BPS PnL")
    elif net_bps_impact < 0:
        print(f"     → Gate is COSTING ${abs(net_bps_impact):,} in BPS PnL")
    else:
        print(f"     → Gate has ZERO direct BPS impact")

    # Bootstrap on blocked
    if len(blocked) >= 5:
        ci = bootstrap_ci([t.exit_pnl for t in blocked])
        print(f"\n  Bootstrap CI on blocked trades: "
              f"[${ci['ci_lo']:+,.0f}, ${ci['ci_hi']:+,.0f}]")
        if ci["ci_lo"] > 0:
            print(f"  → Blocked trades are SIGNIFICANTLY PROFITABLE — gate is blocking good trades")
        elif ci["ci_hi"] < 0:
            print(f"  → Blocked trades are SIGNIFICANTLY NEGATIVE — gate is doing its job")
        else:
            print(f"  → Blocked trades are NOT significantly different from zero")

    if blocked:
        _print_trade_table(blocked, "Blocked trades (detail)")

    # ── Full system impact ────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("  FULL SYSTEM IMPACT (all strategies, not just BPS)")
    print(f"{'='*70}")

    all_pnl_on = sum(t.exit_pnl for t in bt_on.trades)
    all_pnl_off = sum(t.exit_pnl for t in bt_off.trades)
    full_impact = all_pnl_on - all_pnl_off

    print(f"  System PnL with gate (production): ${all_pnl_on:+,.0f} "
          f"({len(bt_on.trades)} trades)")
    print(f"  System PnL without gate:           ${all_pnl_off:+,.0f} "
          f"({len(bt_off.trades)} trades)")
    print(f"  Net system impact: ${full_impact:+,.0f}")
    if full_impact > 0:
        print(f"  → Gate IMPROVES total system by ${full_impact:+,.0f}")
    elif full_impact < 0:
        print(f"  → Gate HURTS total system by ${abs(full_impact):,.0f}")
    else:
        print(f"  → Gate has ZERO system impact")

    # Displacement to non-BPS
    non_bps_on = [t for t in bt_on.trades if t.strategy != BPS_NAME]
    non_bps_off = [t for t in bt_off.trades if t.strategy != BPS_NAME]
    nd_pnl_on = sum(t.exit_pnl for t in non_bps_on)
    nd_pnl_off = sum(t.exit_pnl for t in non_bps_off)
    print(f"\n  Non-BPS trades with gate:    {len(non_bps_on)} trades, PnL ${nd_pnl_on:+,.0f}")
    print(f"  Non-BPS trades without gate: {len(non_bps_off)} trades, PnL ${nd_pnl_off:+,.0f}")
    print(f"  Non-BPS difference: ${nd_pnl_on - nd_pnl_off:+,.0f}")

    print()


if __name__ == "__main__":
    run_sensitivity()
