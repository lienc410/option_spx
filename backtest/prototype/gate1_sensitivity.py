"""
Gate 1 Sensitivity Analysis — DIAGONAL ivp252 upper bound

Research question (解读 B — sensitivity, NOT optimization):
  Is the current DIAGONAL_IVP252_GATE_HI = 50 threshold sitting on a
  performance cliff, or is DIAGONAL performance stable across nearby values?

Method:
  For each candidate upper bound (40, 45, 50, 55, 60, 65):
    1. Monkey-patch DIAGONAL_IVP252_GATE_HI in strategy.selector
    2. Run full-history backtest (2000–2026)
    3. Extract only BULL_CALL_DIAGONAL trades
    4. Compute Sharpe, MaxDD, avg PnL, trade count
    5. Run block bootstrap CI on avg PnL

  The GATE_LO (30) is held fixed — we only vary the upper boundary.

Interpretation:
  - If metrics are stable across ±10 of current value → threshold is robust
  - If there's a sharp cliff → boundary is fragile, needs attention
  - We do NOT pick the "best" value — that would be optimization / overfitting

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.gate1_sensitivity
"""

from __future__ import annotations

import strategy.selector as selector_mod
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

# ─── Config ──────────────────────────────────────────────────────────────────

GATE_HI_CANDIDATES = [40, 45, 50, 55, 60, 65]
CURRENT_VALUE = 50  # mark for display
START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0
DIAGONAL_NAME = "Bull Call Diagonal"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_diagonal_trades(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.strategy == DIAGONAL_NAME]


def _trade_sharpe(trades: list[Trade]) -> float:
    if len(trades) < 2:
        return 0.0
    pnls = [t.exit_pnl for t in trades]
    import numpy as np
    arr = np.array(pnls)
    mu, sigma = arr.mean(), arr.std(ddof=1)
    if sigma == 0:
        return 0.0
    return float(mu / sigma)


def _max_drawdown_from_trades(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    equity = 0.0
    peak = 0.0
    worst_dd = 0.0
    for t in sorted(trades, key=lambda x: x.exit_date):
        equity += t.exit_pnl
        if equity > peak:
            peak = equity
        dd = equity - peak
        if dd < worst_dd:
            worst_dd = dd
    return worst_dd


# ─── Main ────────────────────────────────────────────────────────────────────

def run_sensitivity():
    original_hi = selector_mod.DIAGONAL_IVP252_GATE_HI

    results = []

    for gate_hi in GATE_HI_CANDIDATES:
        # Monkey-patch the module-level constant
        selector_mod.DIAGONAL_IVP252_GATE_HI = gate_hi

        print(f"\n{'='*60}")
        marker = " ◄ CURRENT" if gate_hi == CURRENT_VALUE else ""
        print(f"  Gate 1 upper bound: ivp252 ≤ {gate_hi}{marker}")
        print(f"  (DIAGONAL blocked when ivp252 in [30, {gate_hi}])")
        print(f"{'='*60}")

        bt = run_backtest(
            start_date=START_DATE,
            account_size=ACCOUNT_SIZE,
        )

        diag_trades = _extract_diagonal_trades(bt.trades)
        n = len(diag_trades)

        if n == 0:
            print(f"  No DIAGONAL trades — gate blocks everything")
            results.append({
                "gate_hi": gate_hi,
                "n": 0,
                "avg_pnl": 0,
                "sharpe": 0,
                "max_dd": 0,
                "win_rate": 0,
                "ci_lo": None,
                "ci_hi": None,
            })
            continue

        avg_pnl = sum(t.exit_pnl for t in diag_trades) / n
        sharpe = _trade_sharpe(diag_trades)
        max_dd = _max_drawdown_from_trades(diag_trades)
        win_rate = sum(1 for t in diag_trades if t.exit_pnl > 0) / n * 100

        # Bootstrap CI on avg PnL
        pnls = [t.exit_pnl for t in diag_trades]
        ci = bootstrap_ci(pnls)

        print(f"  Trades:   {n}")
        print(f"  Avg PnL:  ${avg_pnl:+,.0f}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Sharpe:   {sharpe:.2f}")
        print(f"  Max DD:   ${max_dd:+,.0f}")
        print(f"  Bootstrap CI (95%): [${ci['ci_lo']:+,.0f}, ${ci['ci_hi']:+,.0f}]")
        print(f"  Significant: {'YES' if ci['ci_lo'] > 0 else 'NO'}")

        results.append({
            "gate_hi": gate_hi,
            "n": n,
            "avg_pnl": round(avg_pnl),
            "sharpe": round(sharpe, 2),
            "max_dd": round(max_dd),
            "win_rate": round(win_rate, 1),
            "ci_lo": round(ci["ci_lo"]),
            "ci_hi": round(ci["ci_hi"]),
        })

    # Restore original
    selector_mod.DIAGONAL_IVP252_GATE_HI = original_hi

    # ── Summary table ────────────────────────────────────────────────
    print(f"\n\n{'='*80}")
    print("  SENSITIVITY SUMMARY — DIAGONAL Gate 1 (ivp252 upper bound)")
    print(f"  Gate LO fixed at 30 | Blocking range: ivp252 ∈ [30, gate_hi]")
    print(f"{'='*80}")
    print(f"  {'Gate HI':>8} {'Trades':>7} {'Avg PnL':>9} {'WinRate':>8} {'Sharpe':>8} {'MaxDD':>9} {'CI Lo':>8} {'CI Hi':>8} {'Sig':>5}")
    print(f"  {'─'*8} {'─'*7} {'─'*9} {'─'*8} {'─'*8} {'─'*9} {'─'*8} {'─'*8} {'─'*5}")

    for r in results:
        marker = " ◄" if r["gate_hi"] == CURRENT_VALUE else "  "
        sig = "YES" if r["ci_lo"] is not None and r["ci_lo"] > 0 else "NO" if r["ci_lo"] is not None else "—"
        ci_lo_s = f"${r['ci_lo']:+,}" if r["ci_lo"] is not None else "—"
        ci_hi_s = f"${r['ci_hi']:+,}" if r["ci_hi"] is not None else "—"
        print(
            f"{marker}{r['gate_hi']:>6} {r['n']:>7} ${r['avg_pnl']:>+8,} "
            f"{r['win_rate']:>7.1f}% {r['sharpe']:>8.2f} ${r['max_dd']:>+8,} "
            f"{ci_lo_s:>8} {ci_hi_s:>8} {sig:>5}"
        )

    print(f"\n  ◄ = current production value ({CURRENT_VALUE})")
    print(f"  Interpretation: stable across ±10 → robust; cliff at boundary → fragile")
    print()


if __name__ == "__main__":
    run_sensitivity()
