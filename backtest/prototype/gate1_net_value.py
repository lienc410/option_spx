"""
Gate 1 Net Value Analysis — Is the DIAGONAL ivp252 gate earning its keep?

Core question:
  Gate 1 blocks DIAGONAL entry when ivp252 ∈ [30, 50].
  The sensitivity study showed performance is flat across gate_hi = 40–65.
  This means the blocked trades are NOT bad. But are they GOOD?

Method:
  1. Run full-history backtest with Gate 1 DISABLED (gate_hi = 29 → range [30,29] = empty)
  2. Run full-history backtest with Gate 1 ENABLED (gate_hi = 50, production)
  3. Match trades by entry_date to identify which DIAGONAL trades were blocked
  4. Analyze the blocked set: avg PnL, win rate, worst trade, best trade
  5. Compute the gate's net P&L impact = (total PnL with gate) - (total PnL without gate)
     Negative = gate is costing money; Positive = gate is protecting money

  Also run Gate 2 (IV=HIGH) isolation to separate Gate 1 vs Gate 2 effects.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.gate1_net_value
"""

from __future__ import annotations

import numpy as np
import strategy.selector as selector_mod
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0
DIAGONAL_NAME = "Bull Call Diagonal"
ORIGINAL_GATE_HI = selector_mod.DIAGONAL_IVP252_GATE_HI  # 50


def _diag_trades(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.strategy == DIAGONAL_NAME]


def _print_trade_table(trades: list[Trade], label: str):
    print(f"\n  {label} ({len(trades)} trades)")
    print(f"  {'Entry':>12} {'Exit':>12} {'DTE':>5} {'PnL':>10} {'Exit Reason':<18}")
    print(f"  {'─'*12} {'─'*12} {'─'*5} {'─'*10} {'─'*18}")
    for t in sorted(trades, key=lambda x: x.entry_date):
        print(f"  {t.entry_date:>12} {t.exit_date:>12} {t.dte_at_entry:>5} ${t.exit_pnl:>+9,.0f} {t.exit_reason:<18}")


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


def run_analysis():
    # ── Run 1: Gate 1 DISABLED ────────────────────────────────────────
    print("=" * 70)
    print("  Run 1: Gate 1 DISABLED (all DIAGONAL trades allowed)")
    print("=" * 70)
    selector_mod.DIAGONAL_IVP252_GATE_HI = 29  # [30, 29] = empty → never blocks
    bt_no_gate = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    diag_no_gate = _diag_trades(bt_no_gate.trades)

    # ── Run 2: Gate 1 ENABLED (production) ────────────────────────────
    print("\n" + "=" * 70)
    print("  Run 2: Gate 1 ENABLED (production, ivp252 ∈ [30, 50] blocked)")
    print("=" * 70)
    selector_mod.DIAGONAL_IVP252_GATE_HI = ORIGINAL_GATE_HI  # restore 50
    bt_with_gate = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    diag_with_gate = _diag_trades(bt_with_gate.trades)

    # Restore
    selector_mod.DIAGONAL_IVP252_GATE_HI = ORIGINAL_GATE_HI

    # ── Identify blocked trades ───────────────────────────────────────
    gated_dates = {t.entry_date for t in diag_with_gate}
    no_gate_dates = {t.entry_date for t in diag_no_gate}

    # Trades that exist without gate but NOT with gate = blocked by Gate 1
    blocked_dates = no_gate_dates - gated_dates
    blocked_trades = [t for t in diag_no_gate if t.entry_date in blocked_dates]

    # Trades that exist with gate but NOT without gate = created by displacement
    # (Gate 1 blocked entry on day X → capital available → entered on day Y instead)
    displaced_dates = gated_dates - no_gate_dates
    displaced_trades = [t for t in diag_with_gate if t.entry_date in displaced_dates]

    # Common trades (exist in both runs, same entry date)
    common_dates = gated_dates & no_gate_dates
    common_with = [t for t in diag_with_gate if t.entry_date in common_dates]
    common_without = [t for t in diag_no_gate if t.entry_date in common_dates]

    # ── Print results ─────────────────────────────────────────────────

    s_no_gate = _stats(diag_no_gate)
    s_with_gate = _stats(diag_with_gate)
    s_blocked = _stats(blocked_trades)
    s_displaced = _stats(displaced_trades)

    print(f"\n\n{'='*70}")
    print("  GATE 1 NET VALUE ANALYSIS")
    print(f"{'='*70}")

    print(f"\n  ┌─ Without Gate 1 (all DIAGONAL trades)")
    print(f"  │  Trades: {s_no_gate['n']}")
    print(f"  │  Total PnL: ${s_no_gate['total_pnl']:+,}")
    print(f"  │  Avg PnL: ${s_no_gate['avg_pnl']:+,}")
    print(f"  │  Win Rate: {s_no_gate['win_rate']}%")
    print(f"  │  Sharpe: {s_no_gate['sharpe']}")

    print(f"  │")
    print(f"  ├─ With Gate 1 (production)")
    print(f"  │  Trades: {s_with_gate['n']}")
    print(f"  │  Total PnL: ${s_with_gate['total_pnl']:+,}")
    print(f"  │  Avg PnL: ${s_with_gate['avg_pnl']:+,}")
    print(f"  │  Win Rate: {s_with_gate['win_rate']}%")
    print(f"  │  Sharpe: {s_with_gate['sharpe']}")

    print(f"  │")
    print(f"  ├─ Blocked by Gate 1 (would have traded, but gate said no)")
    print(f"  │  Trades: {s_blocked['n']}")
    print(f"  │  Total PnL: ${s_blocked['total_pnl']:+,}")
    print(f"  │  Avg PnL: ${s_blocked['avg_pnl']:+,}")
    print(f"  │  Win Rate: {s_blocked['win_rate']}%")
    print(f"  │  Worst: ${s_blocked['worst']:+,}")
    print(f"  │  Best: ${s_blocked['best']:+,}")

    if displaced_trades:
        print(f"  │")
        print(f"  ├─ Displacement trades (exist ONLY with gate — entered on different dates)")
        print(f"  │  Trades: {s_displaced['n']}")
        print(f"  │  Total PnL: ${s_displaced['total_pnl']:+,}")
        print(f"  │  Avg PnL: ${s_displaced['avg_pnl']:+,}")

    # ── Net impact ────────────────────────────────────────────────────
    net_pnl_impact = s_with_gate["total_pnl"] - s_no_gate["total_pnl"]
    print(f"  │")
    print(f"  └─ NET IMPACT of Gate 1")
    print(f"     PnL difference (with gate − without gate): ${net_pnl_impact:+,}")
    if net_pnl_impact > 0:
        print(f"     → Gate 1 is PROTECTING ${net_pnl_impact:+,} in total PnL")
    elif net_pnl_impact < 0:
        print(f"     → Gate 1 is COSTING ${abs(net_pnl_impact):,} in total PnL")
    else:
        print(f"     → Gate 1 has ZERO net impact")

    # ── Bootstrap on blocked trades ───────────────────────────────────
    if len(blocked_trades) >= 5:
        blocked_pnls = [t.exit_pnl for t in blocked_trades]
        ci = bootstrap_ci(blocked_pnls)
        print(f"\n  Bootstrap CI on blocked trades: [${ci['ci_lo']:+,.0f}, ${ci['ci_hi']:+,.0f}]")
        if ci["ci_lo"] > 0:
            print(f"  → Blocked trades are SIGNIFICANTLY PROFITABLE — gate is blocking good trades")
        elif ci["ci_hi"] < 0:
            print(f"  → Blocked trades are SIGNIFICANTLY NEGATIVE — gate is doing its job")
        else:
            print(f"  → Blocked trades are NOT significantly different from zero")

    # ── Print blocked trade details ───────────────────────────────────
    if blocked_trades:
        _print_trade_table(blocked_trades, "Blocked trades (detail)")

    if displaced_trades:
        _print_trade_table(displaced_trades, "Displacement trades (detail)")

    # ── Full system impact (not just DIAGONAL) ────────────────────────
    print(f"\n\n{'='*70}")
    print("  FULL SYSTEM IMPACT (all strategies, not just DIAGONAL)")
    print(f"{'='*70}")

    all_pnl_no_gate = sum(t.exit_pnl for t in bt_no_gate.trades)
    all_pnl_with_gate = sum(t.exit_pnl for t in bt_with_gate.trades)
    full_impact = all_pnl_with_gate - all_pnl_no_gate

    print(f"  Total system PnL without Gate 1: ${all_pnl_no_gate:+,.0f} ({len(bt_no_gate.trades)} trades)")
    print(f"  Total system PnL with Gate 1:    ${all_pnl_with_gate:+,.0f} ({len(bt_with_gate.trades)} trades)")
    print(f"  Net system impact: ${full_impact:+,.0f}")

    if full_impact > 0:
        print(f"  → Gate 1 IMPROVES total system by ${full_impact:+,.0f}")
    elif full_impact < 0:
        print(f"  → Gate 1 HURTS total system by ${abs(full_impact):,.0f}")
    else:
        print(f"  → Gate 1 has ZERO system impact")

    # ── Displacement analysis ─────────────────────────────────────────
    # When Gate 1 blocks a DIAGONAL entry, does the capital get deployed
    # to a different strategy instead? Check non-DIAGONAL trades.
    print(f"\n\n{'='*70}")
    print("  DISPLACEMENT EFFECT — What happens when Gate 1 blocks DIAGONAL?")
    print(f"{'='*70}")

    non_diag_no_gate = [t for t in bt_no_gate.trades if t.strategy != DIAGONAL_NAME]
    non_diag_with_gate = [t for t in bt_with_gate.trades if t.strategy != DIAGONAL_NAME]

    nd_pnl_no = sum(t.exit_pnl for t in non_diag_no_gate)
    nd_pnl_with = sum(t.exit_pnl for t in non_diag_with_gate)

    print(f"  Non-DIAGONAL trades without Gate 1: {len(non_diag_no_gate)} trades, PnL ${nd_pnl_no:+,.0f}")
    print(f"  Non-DIAGONAL trades with Gate 1:    {len(non_diag_with_gate)} trades, PnL ${nd_pnl_with:+,.0f}")
    print(f"  Difference: ${nd_pnl_with - nd_pnl_no:+,.0f}")

    if nd_pnl_with != nd_pnl_no:
        print(f"  → Gate 1 changes non-DIAGONAL deployment (capital displacement effect)")
    else:
        print(f"  → No displacement effect on other strategies")

    print()


if __name__ == "__main__":
    run_analysis()
