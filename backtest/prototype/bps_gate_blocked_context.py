"""
BPS Gate P1 — Blocked Trade Context Analysis

Question: When the IVP≥50 gate blocks a BPS, what is the actual VIX level
and VIX trend? Is it blocking during genuinely stressed environments, or
during "slightly above recent median" conditions (e.g. VIX=18, IVP=52)?

Also: does VIX trend (RISING vs FALLING/FLAT) differentiate blocked trade
quality? IVP=55 + VIX FALLING (vol normalizing from spike) should be a
sweet spot for selling puts, not a danger zone.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.bps_gate_blocked_context
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0
BPS_NAME = "Bull Put Spread"


def _bps_trades(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.strategy == BPS_NAME]


def _stats(trades: list[Trade]) -> dict:
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

    # Gate OFF — get all BPS trades
    print("  Running gate-OFF backtest (BPS_NNB_IVP_UPPER = 999)...")
    sel.BPS_NNB_IVP_UPPER = 999
    bt_off = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    bps_off = _bps_trades(bt_off.trades)
    sig_map = {row["date"]: row for row in bt_off.signals}

    # Gate ON — get production BPS trades
    print("  Running gate-ON backtest (BPS_NNB_IVP_UPPER = 50)...")
    sel.BPS_NNB_IVP_UPPER = 50
    bt_on = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    bps_on = _bps_trades(bt_on.trades)

    sel.BPS_NNB_IVP_UPPER = orig

    dates_on = {t.entry_date for t in bps_on}
    blocked = [t for t in bps_off if t.entry_date not in dates_on]

    # ── Blocked trades with full context ──────────────────────────────
    print(f"\n{'='*100}")
    print("  BLOCKED TRADES — Full Entry-Day Context")
    print(f"{'='*100}")
    print(f"  {'Entry':>12} {'VIX':>6} {'IVP':>5} {'IVR':>5} {'Regime':>10} {'Trend':>10} "
          f"{'VIX 5d':>7} {'PnL':>10} {'Exit':>12} {'Reason':<15}")
    print(f"  {'─'*12} {'─'*6} {'─'*5} {'─'*5} {'─'*10} {'─'*10} "
          f"{'─'*7} {'─'*10} {'─'*12} {'─'*15}")

    blocked_data = []
    for t in sorted(blocked, key=lambda x: x.entry_date):
        sig = sig_map.get(t.entry_date, {})
        vix = sig.get("vix", 0)
        ivp = sig.get("ivp", 0)
        ivr = sig.get("ivr", 0)
        regime = sig.get("regime", "?")
        trend = sig.get("trend", "?")
        vix_5d = sig.get("vix_5d_avg", 0)
        blocked_data.append({
            "trade": t, "vix": vix, "ivp": ivp, "ivr": ivr,
            "regime": regime, "trend": trend, "vix_5d": vix_5d,
        })
        print(f"  {t.entry_date:>12} {vix:>6.1f} {ivp:>5.0f} {ivr:>5.0f} {regime:>10} {trend:>10} "
              f"{vix_5d:>7.1f} ${t.exit_pnl:>+9,.0f} {t.exit_date:>12} {t.exit_reason:<15}")

    # ── VIX level distribution of blocked trades ──────────────────────
    print(f"\n\n{'='*80}")
    print("  BLOCKED TRADE VIX LEVEL DISTRIBUTION")
    print(f"{'='*80}")
    vix_bins = [(10, 15), (15, 18), (18, 20), (20, 25), (25, 30)]
    for lo, hi in vix_bins:
        subset = [d for d in blocked_data if lo <= d["vix"] < hi]
        trades = [d["trade"] for d in subset]
        s = _stats(trades)
        bar = "█" * len(subset)
        print(f"  VIX [{lo:>2}, {hi:>2}): {len(subset):>3} trades  "
              f"avg ${s['avg_pnl']:>+6,}  win {s['win_rate']:>5.1f}%  "
              f"sharpe {s['sharpe']:>5.2f}  {bar}")

    # ── Split by VIX trend: RISING vs FALLING vs FLAT ─────────────────
    # We compute VIX trend from 5d avg change (same as vix_regime.py)
    TREND_BAND = 0.03

    def _vix_trend(sig):
        """Recompute VIX trend from signal history."""
        return sig.get("trend", "FLAT")  # This is the SPX price trend, not VIX trend!

    # Actually, the signal_history "trend" field is the SPX PRICE trend (BULLISH/BEARISH/FLAT),
    # not the VIX trend. We need to compute VIX trend separately.
    # Let's compute from the raw vix_5d_avg series.
    signals_ordered = sorted(bt_off.signals, key=lambda r: r["date"])
    vix_trend_map = {}
    for i, row in enumerate(signals_ordered):
        if i < 5:
            vix_trend_map[row["date"]] = "FLAT"
            continue
        cur = row["vix_5d_avg"]
        prior = signals_ordered[i - 5]["vix_5d_avg"]
        if prior == 0:
            vix_trend_map[row["date"]] = "FLAT"
            continue
        change = (cur - prior) / prior
        if change > TREND_BAND:
            vix_trend_map[row["date"]] = "RISING"
        elif change < -TREND_BAND:
            vix_trend_map[row["date"]] = "FALLING"
        else:
            vix_trend_map[row["date"]] = "FLAT"

    print(f"\n\n{'='*80}")
    print("  BLOCKED TRADES BY VIX TREND (not SPX trend)")
    print("  RISING = vol escalating | FALLING = vol normalizing | FLAT = stable")
    print(f"{'='*80}")

    for vt in ["RISING", "FLAT", "FALLING"]:
        subset = [d for d in blocked_data if vix_trend_map.get(d["trade"].entry_date) == vt]
        trades = [d["trade"] for d in subset]
        s = _stats(trades)
        if not trades:
            print(f"\n  VIX {vt}: 0 trades")
            continue
        vix_vals = [d["vix"] for d in subset]
        ivp_vals = [d["ivp"] for d in subset]
        print(f"\n  VIX {vt}: {s['n']} trades")
        print(f"    Avg PnL: ${s['avg_pnl']:+,}, Win Rate: {s['win_rate']}%, Sharpe: {s['sharpe']}")
        print(f"    VIX range: [{min(vix_vals):.1f}, {max(vix_vals):.1f}], avg {np.mean(vix_vals):.1f}")
        print(f"    IVP range: [{min(ivp_vals):.0f}, {max(ivp_vals):.0f}], avg {np.mean(ivp_vals):.0f}")
        if len(trades) >= 5:
            ci = bootstrap_ci([t.exit_pnl for t in trades])
            lo, hi = ci["ci_lo"], ci["ci_hi"]
            if not (np.isnan(lo) or np.isnan(hi)):
                sig_str = "YES" if lo > 0 else "NO"
                print(f"    Bootstrap CI: [${lo:+,.0f}, ${hi:+,.0f}] — Significant: {sig_str}")

    # ── Key question: VIX FALLING + IVP>=50 — is this a vol crush sweet spot?
    print(f"\n\n{'='*80}")
    print("  KEY HYPOTHESIS: VIX FALLING + IVP≥50 = vol-crush sweet spot for BPS?")
    print(f"{'='*80}")

    falling_blocked = [d for d in blocked_data if vix_trend_map.get(d["trade"].entry_date) == "FALLING"]
    if falling_blocked:
        falling_trades = [d["trade"] for d in falling_blocked]
        s = _stats(falling_trades)
        print(f"\n  VIX FALLING + IVP≥50 blocked trades: {s['n']}")
        print(f"  Avg PnL: ${s['avg_pnl']:+,}, Win Rate: {s['win_rate']}%, Sharpe: {s['sharpe']}")
        print(f"  Total PnL: ${s['total_pnl']:+,}")

        # Compare to production BPS (IVP<50)
        on_s = _stats(bps_on)
        print(f"\n  For comparison — production BPS (IVP<50):")
        print(f"  Avg PnL: ${on_s['avg_pnl']:+,}, Win Rate: {on_s['win_rate']}%, Sharpe: {on_s['sharpe']}")

        if s["n"] >= 5 and on_s["n"] >= 5:
            print(f"\n  These VIX-FALLING blocked trades {'OUTPERFORM' if s['avg_pnl'] > on_s['avg_pnl'] else 'UNDERPERFORM'} production BPS")

    # Non-falling blocked
    non_falling_blocked = [d for d in blocked_data if vix_trend_map.get(d["trade"].entry_date) != "FALLING"]
    if non_falling_blocked:
        nf_trades = [d["trade"] for d in non_falling_blocked]
        s = _stats(nf_trades)
        print(f"\n  VIX NOT-FALLING + IVP≥50 blocked trades: {s['n']}")
        print(f"  Avg PnL: ${s['avg_pnl']:+,}, Win Rate: {s['win_rate']}%, Sharpe: {s['sharpe']}")
        print(f"  Total PnL: ${s['total_pnl']:+,}")
        if len(nf_trades) >= 5:
            ci = bootstrap_ci([t.exit_pnl for t in nf_trades])
            lo, hi = ci["ci_lo"], ci["ci_hi"]
            if not (np.isnan(lo) or np.isnan(hi)):
                print(f"  Bootstrap CI: [${lo:+,.0f}, ${hi:+,.0f}]")

    # ── IVP context: what does IVP=50 actually mean in VIX terms? ─────
    print(f"\n\n{'='*80}")
    print("  CONTEXT: What VIX level corresponds to IVP≥50?")
    print(f"{'='*80}")
    # Look at ALL signal rows where regime=NORMAL, iv_signal=NEUTRAL, trend=BULLISH, IVP≥50
    high_ivp_days = [
        row for row in bt_off.signals
        if row["regime"] == "NORMAL" and row["iv_signal"] == "NEUTRAL"
        and row["trend"] == "BULLISH" and row["ivp"] >= 50
    ]
    if high_ivp_days:
        vix_vals = [r["vix"] for r in high_ivp_days]
        ivp_vals = [r["ivp"] for r in high_ivp_days]
        print(f"  Days matching NORMAL+NEUTRAL+BULLISH+IVP≥50: {len(high_ivp_days)}")
        print(f"  VIX range: [{min(vix_vals):.1f}, {max(vix_vals):.1f}]")
        print(f"  VIX mean:  {np.mean(vix_vals):.1f}")
        print(f"  VIX median: {np.median(vix_vals):.1f}")
        print(f"  VIX P25/P75: {np.percentile(vix_vals, 25):.1f} / {np.percentile(vix_vals, 75):.1f}")
        print(f"  IVP mean: {np.mean(ivp_vals):.0f}")
        # How many of these days have VIX < 20?
        low_vix = sum(1 for v in vix_vals if v < 20)
        print(f"  Days with VIX < 20: {low_vix} ({low_vix/len(vix_vals)*100:.0f}%)")
        low_vix_18 = sum(1 for v in vix_vals if v < 18)
        print(f"  Days with VIX < 18: {low_vix_18} ({low_vix_18/len(vix_vals)*100:.0f}%)")

    print()


if __name__ == "__main__":
    run_analysis()
