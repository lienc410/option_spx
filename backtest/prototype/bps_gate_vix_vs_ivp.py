"""
BPS Gate — VIX absolute level vs IVP as entry filter

Core question (PM raised):
  The IVP≥50 gate blocks BPS when IVP is above median, but IVP≥50 often
  corresponds to VIX=15-18 — objectively low vol. The gate is effectively
  saying "only sell puts when premium is cheapest." Is IVP even the right
  variable for this gate, or should it be absolute VIX level?

Analysis:
  1. Take ALL gate-OFF BPS trades (62 trades)
  2. Split by absolute VIX level (not IVP) to see where quality degrades
  3. Split by IVP band to see if IVP predicts anything beyond noise
  4. Cross-tabulate VIX × IVP to find the actual risk pockets
  5. Compare: "IVP≥50 gate" vs hypothetical "VIX≥20 gate" vs "no gate"

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.bps_gate_vix_vs_ivp
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0
BPS_NAME = "Bull Put Spread"


def _stats(trades, label=""):
    if not trades:
        return {"n": 0, "total_pnl": 0, "avg_pnl": 0, "win_rate": 0, "sharpe": 0}
    pnls = [t.exit_pnl if hasattr(t, "exit_pnl") else t[0] for t in trades]
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
    }


def _trade_stats(trades):
    if not trades:
        return {"n": 0, "total_pnl": 0, "avg_pnl": 0, "win_rate": 0, "sharpe": 0}
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
    }


def run_analysis():
    orig = sel.BPS_NNB_IVP_UPPER

    # Gate OFF — all BPS trades
    print("  Running gate-OFF backtest...")
    sel.BPS_NNB_IVP_UPPER = 999
    bt_off = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    sel.BPS_NNB_IVP_UPPER = orig

    sig_map = {row["date"]: row for row in bt_off.signals}
    bps_all = [t for t in bt_off.trades if t.strategy == BPS_NAME]

    # Enrich each trade with entry-day signals
    enriched = []
    for t in bps_all:
        sig = sig_map.get(t.entry_date, {})
        enriched.append({
            "trade": t,
            "vix": sig.get("vix", 0),
            "ivp": sig.get("ivp", 0),
            "ivr": sig.get("ivr", 0),
        })

    # ── 1. Split by absolute VIX level ────────────────────────────────
    print(f"\n{'='*80}")
    print("  1. BPS PERFORMANCE BY ABSOLUTE VIX LEVEL (gate OFF)")
    print("     Is absolute VIX a better predictor than IVP?")
    print(f"{'='*80}")

    vix_bins = [(14, 16), (16, 18), (18, 20), (20, 22), (22, 25)]
    print(f"\n  {'VIX Band':>12} {'n':>4} {'Avg PnL':>9} {'WinRate':>8} "
          f"{'Sharpe':>7} {'Total PnL':>11}")
    print(f"  {'─'*12} {'─'*4} {'─'*9} {'─'*8} {'─'*7} {'─'*11}")
    for lo, hi in vix_bins:
        subset = [e["trade"] for e in enriched if lo <= e["vix"] < hi]
        s = _trade_stats(subset)
        bar = "█" * s["n"]
        print(f"  [{lo:>2}, {hi:>2}) {s['n']:>4} ${s['avg_pnl']:>+8,} "
              f"{s['win_rate']:>7.1f}% {s['sharpe']:>7.2f} ${s['total_pnl']:>+10,}  {bar}")

    # ── 2. Split by IVP band ─────────────────────────────────────────
    print(f"\n{'='*80}")
    print("  2. BPS PERFORMANCE BY IVP BAND (gate OFF)")
    print("     Does IVP predict trade quality?")
    print(f"{'='*80}")

    ivp_bins = [(43, 50), (50, 55), (55, 60), (60, 65), (65, 75)]
    print(f"\n  {'IVP Band':>12} {'n':>4} {'Avg PnL':>9} {'WinRate':>8} "
          f"{'Sharpe':>7} {'Total PnL':>11} {'Avg VIX':>8}")
    print(f"  {'─'*12} {'─'*4} {'─'*9} {'─'*8} {'─'*7} {'─'*11} {'─'*8}")
    for lo, hi in ivp_bins:
        items = [e for e in enriched if lo <= e["ivp"] < hi]
        subset = [e["trade"] for e in items]
        s = _trade_stats(subset)
        avg_vix = np.mean([e["vix"] for e in items]) if items else 0
        print(f"  [{lo:>2}, {hi:>2}) {s['n']:>4} ${s['avg_pnl']:>+8,} "
              f"{s['win_rate']:>7.1f}% {s['sharpe']:>7.2f} ${s['total_pnl']:>+10,} "
              f"{avg_vix:>7.1f}")

    # ── 3. Cross-tab: VIX level × IVP band ───────────────────────────
    print(f"\n{'='*80}")
    print("  3. CROSS-TABULATION: VIX × IVP (gate OFF)")
    print("     Where are the actual risk pockets?")
    print(f"{'='*80}")

    print(f"\n  {'':>12}", end="")
    for ilo, ihi in ivp_bins:
        print(f"  IVP[{ilo},{ihi})", end="")
    print()
    print(f"  {'':>12}", end="")
    for _ in ivp_bins:
        print(f"  {'─'*11}", end="")
    print()

    for vlo, vhi in vix_bins:
        print(f"  VIX[{vlo:>2},{vhi:>2})", end="")
        for ilo, ihi in ivp_bins:
            items = [e for e in enriched if vlo <= e["vix"] < vhi and ilo <= e["ivp"] < ihi]
            if not items:
                print(f"  {'—':>11}", end="")
            else:
                s = _trade_stats([e["trade"] for e in items])
                print(f"  {s['n']:>2}@${s['avg_pnl']:>+5,}", end="")
        print()

    # ── 4. The "dangerous" trades — where are the big losses? ────────
    print(f"\n{'='*80}")
    print("  4. BIG LOSSES (PnL < -$4,000) — What were their VIX and IVP?")
    print(f"{'='*80}")

    big_losses = sorted([e for e in enriched if e["trade"].exit_pnl < -4000],
                        key=lambda e: e["trade"].exit_pnl)
    print(f"\n  {'Entry':>12} {'VIX':>6} {'IVP':>5} {'IVR':>5} {'PnL':>10} {'Exit':>12} {'Reason':<15}")
    print(f"  {'─'*12} {'─'*6} {'─'*5} {'─'*5} {'─'*10} {'─'*12} {'─'*15}")
    for e in big_losses:
        t = e["trade"]
        print(f"  {t.entry_date:>12} {e['vix']:>6.1f} {e['ivp']:>5.0f} {e['ivr']:>5.0f} "
              f"${t.exit_pnl:>+9,.0f} {t.exit_date:>12} {t.exit_reason:<15}")

    # ── 5. Hypothetical gate comparison ──────────────────────────────
    print(f"\n{'='*80}")
    print("  5. GATE COMPARISON: Which filter best separates good from bad BPS?")
    print(f"{'='*80}")

    filters = {
        "No gate (all)":             lambda e: True,
        "IVP < 50 (production)":     lambda e: e["ivp"] < 50,
        "IVP < 55":                  lambda e: e["ivp"] < 55,
        "IVP < 60":                  lambda e: e["ivp"] < 60,
        "VIX < 18":                  lambda e: e["vix"] < 18,
        "VIX < 19":                  lambda e: e["vix"] < 19,
        "VIX < 20":                  lambda e: e["vix"] < 20,
        "VIX < 18 OR IVP < 50":     lambda e: e["vix"] < 18 or e["ivp"] < 50,
        "VIX < 20 AND IVP < 60":    lambda e: e["vix"] < 20 and e["ivp"] < 60,
    }

    print(f"\n  {'Filter':<30} {'n':>4} {'Avg PnL':>9} {'WinRate':>8} "
          f"{'Sharpe':>7} {'Total PnL':>11}")
    print(f"  {'─'*30} {'─'*4} {'─'*9} {'─'*8} {'─'*7} {'─'*11}")

    for label, fn in filters.items():
        subset = [e["trade"] for e in enriched if fn(e)]
        s = _trade_stats(subset)
        marker = " ◄" if label == "IVP < 50 (production)" else "  "
        print(f"{marker}{label:<28} {s['n']:>4} ${s['avg_pnl']:>+8,} "
              f"{s['win_rate']:>7.1f}% {s['sharpe']:>7.2f} ${s['total_pnl']:>+10,}")

    # ── 6. The core issue: IVP vs VIX correlation ─────────────────────
    print(f"\n{'='*80}")
    print("  6. IVP vs VIX CORRELATION in NORMAL+NEUTRAL+BULLISH regime")
    print(f"{'='*80}")

    nnb_days = [
        row for row in bt_off.signals
        if row["regime"] == "NORMAL" and row["iv_signal"] == "NEUTRAL"
        and row["trend"] == "BULLISH"
    ]
    vix_arr = np.array([r["vix"] for r in nnb_days])
    ivp_arr = np.array([r["ivp"] for r in nnb_days])
    corr = np.corrcoef(vix_arr, ivp_arr)[0, 1]
    print(f"\n  NNB days: {len(nnb_days)}")
    print(f"  VIX range: [{vix_arr.min():.1f}, {vix_arr.max():.1f}], mean {vix_arr.mean():.1f}")
    print(f"  IVP range: [{ivp_arr.min():.0f}, {ivp_arr.max():.0f}], mean {ivp_arr.mean():.0f}")
    print(f"  Pearson correlation (VIX, IVP): {corr:.3f}")
    print(f"  → {'WEAK' if abs(corr) < 0.3 else 'MODERATE' if abs(corr) < 0.6 else 'STRONG'} correlation")

    # How many high-IVP days have low absolute VIX?
    high_ivp_low_vix = sum(1 for v, i in zip(vix_arr, ivp_arr) if i >= 50 and v < 18)
    high_ivp_total = sum(1 for i in ivp_arr if i >= 50)
    if high_ivp_total:
        print(f"\n  High-IVP (≥50) days with VIX < 18: {high_ivp_low_vix}/{high_ivp_total} "
              f"({high_ivp_low_vix/high_ivp_total*100:.0f}%)")
        print(f"  → {high_ivp_low_vix/high_ivp_total*100:.0f}% of the time, the gate is blocking "
              f"entries in a VIX<18 environment")

    print()


if __name__ == "__main__":
    run_analysis()
