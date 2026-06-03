"""Q083 P11 — Test BCD in NORMAL × IV_LOW × BULLISH days.

Hypothesis: NORMAL × IV_LOW (VIX 15-22, IVR<30, after-spike-not-recovered)
has 29.6% vol-expansion frequency — IDEAL for BCD's +vega cushion.
This regime currently routes to reduce_wait. Maybe should route to BCD.

Test: synthesize BCD trades on these 1023 days using same params as Q082
(90 DTE δ0.70 / 45 DTE δ0.30). Compare PnL distribution to Q082's
LOW_VOL × BULL baseline (n=137 trades, +9.7pp vs QQQ, Sortino +0.9).

If NORMAL × IV_LOW BCD performs comparable or better → strong case for
matrix change: NORMAL × IV_LOW × BULL → BCD (instead of reduce_wait).
"""
from __future__ import annotations
import csv
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q082"))

# Import BCD simulation from Q082 P6
from q082_p6_bcd_synth_reconstruction import (
    simulate_bcd_trade, load_spx_history, load_vix_history,
)

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
TRADES_OUT = ROOT / "research" / "q083" / "q083_p11_bcd_normal_low_ivr_trades.csv"


def main():
    # Load cache, filter NORMAL × IV_LOW × BULLISH
    rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "date": r["date"],
                    "vix": float(r["vix"]),
                    "regime": r["regime"],
                    "trend": r["trend"],
                    "iv_signal": r["iv_signal"],
                    "ivr": float(r["ivr"]),
                    "ivp": float(r["ivp"]),
                })
            except (ValueError, TypeError):
                continue
    rows.sort(key=lambda r: r["date"])

    target_days = [r for r in rows if r["regime"] == "NORMAL"
                   and r["trend"] == "BULLISH"
                   and r["iv_signal"] == "LOW"]
    print(f"Target days (NORMAL × IV_LOW × BULL): {len(target_days)}")

    # Load price history
    spx = load_spx_history()
    vix = load_vix_history()
    print(f"Loaded SPX ({len(spx)}) + VIX ({len(vix)})")

    # Apply sequential ladder logic (same as Q082 P6)
    # Per cell-rotation: only open NEW BCD if previous exit_date < this entry_date
    trades = []
    last_exit_date = None
    for r in target_days:
        entry_iso = r["date"]
        if last_exit_date is not None and entry_iso <= last_exit_date:
            continue  # ladder overlap
        t = simulate_bcd_trade(entry_iso, spx, vix)
        if t is None:
            continue
        t["ivp_at_entry"] = r["ivp"]
        t["ivr_at_entry"] = r["ivr"]
        trades.append(t)
        last_exit_date = t["exit_date"]

    print(f"Sequential BCD trades synthesized: {len(trades)}")

    if not trades:
        print("ERROR: no trades")
        return

    # Stats
    pnls = [t["pnl_usd"] for t in trades]
    rois = [t["period_roe"] for t in trades]
    holds = [t["hold_days"] for t in trades]
    debits = [t["entry_debit_usd"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)

    print(f"\n{'=' * 80}")
    print(f"BCD in NORMAL × IV_LOW × BULL (n={len(trades)} sequential trades)")
    print(f"{'=' * 80}")
    print(f"  Date range: {trades[0]['entry_date']} → {trades[-1]['entry_date']}")
    print(f"  Win rate: {wins}/{len(trades)} = {100*wins/len(trades):.1f}%")
    print(f"  Median entry debit: ${median(debits):,.0f}")
    print(f"  Median hold days: {median(holds)}")
    print(f"  Mean PnL: ${mean(pnls):>+8,.0f}")
    print(f"  Median PnL: ${median(pnls):>+8,.0f}")
    print(f"  Worst trade: ${min(pnls):>+8,.0f}")
    print(f"  Best trade: ${max(pnls):>+8,.0f}")
    print(f"  Mean period ROE: {mean(rois):>+7.2%}")
    print(f"  Median ROE: {median(rois):>+7.2%}")
    print(f"  Worst ROE: {min(rois):>+7.2%}")

    # Sortino
    period_pnls = [t["pnl_per_share"] for t in trades]
    downside = math.sqrt(sum(min(p, 0)**2 for p in period_pnls) / len(period_pnls))
    sortino = mean(period_pnls) / downside if downside > 0 else float("inf")
    print(f"  Sortino (per-share): {sortino:+.3f}")

    # Compare to Q082 LOW_VOL × BULL baseline
    print(f"\n{'=' * 80}")
    print(f"COMPARISON: NORMAL × IV_LOW × BULL vs Q082 LOW_VOL × BULL baseline")
    print(f"{'=' * 80}")
    print(f"{'metric':<25} {'NORMAL × IV_LOW':>15} {'Q082 LOW_VOL':>15}")
    print(f"  {'n_trades':<23} {len(trades):>15} {'137':>15}")
    print(f"  {'win_rate':<23} {100*wins/len(trades):>14.1f}% {'66.4%':>15}")
    print(f"  {'mean_pnl':<23} ${mean(pnls):>+13,.0f} ${'1,016':>13}")
    print(f"  {'median_pnl':<23} ${median(pnls):>+13,.0f} ${'895':>13}")
    print(f"  {'worst_trade':<23} ${min(pnls):>+13,.0f} ${'-6,909':>13}")
    print(f"  {'mean_period_roe':<23} {mean(rois):>14.2%} {'+10.47%':>15}")

    # Write trades CSV
    with open(TRADES_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
        w.writeheader()
        w.writerows(trades)
    print(f"\nwrote {TRADES_OUT}")

    # Stratify by year + IVP bucket
    print(f"\n{'=' * 80}")
    print(f"By IVP bucket (within the iv_signal=LOW universe):")
    print(f"{'=' * 80}")
    for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 40)]:
        sub = [t for t in trades if lo <= t["ivp_at_entry"] < hi]
        if sub:
            p = [t["pnl_usd"] for t in sub]
            w = sum(1 for x in p if x > 0)
            print(f"  IVP [{lo:>2},{hi:>2}): n={len(sub):>3} mean=${mean(p):>+7,.0f} "
                  f"median=${median(p):>+7,.0f} worst=${min(p):>+7,.0f} win={100*w/len(sub):.1f}%")

    print(f"\n{'=' * 80}")
    print(f"By VIX bucket (absolute level):")
    print(f"{'=' * 80}")
    for lo, hi in [(15, 16), (16, 17), (17, 18), (18, 19), (19, 20), (20, 21), (21, 22)]:
        sub = [t for t in trades if lo <= t["entry_vix"] < hi]
        if sub:
            p = [t["pnl_usd"] for t in sub]
            w = sum(1 for x in p if x > 0)
            print(f"  VIX [{lo},{hi}): n={len(sub):>3} mean=${mean(p):>+7,.0f} "
                  f"median=${median(p):>+7,.0f} worst=${min(p):>+7,.0f} win={100*w/len(sub):.1f}%")


if __name__ == "__main__":
    main()
