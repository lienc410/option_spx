"""Q083 P14 — Cash time-coverage + QQQ opportunity cost net settlement.

Per G-review §1: max concurrent=1 (no crowd-out) is the wrong answer to PM's
real cash-bound question. The right question: how much TIME is cash occupied
by BCD pre- vs post-SPEC-113, and does the extra BCD PnL exceed the QQQ
opportunity cost on that occupied cash?

Method:
1. Re-simulate combined universe (LOW_VOL × BULL + NORMAL × IV_LOW × BULL ×
   VIX<18 per carve-out) under sequential ladder.
2. For each calendar day in 26y, check if a BCD is open. Track cash occupied.
3. Compute opportunity cost = sum_over_days(debit × hurdle / 365)
4. Compare pre-SPEC (Q082 alone) vs post-SPEC (Q082 + carve-out new cell):
   - Total BCD PnL
   - Total cash-day occupancy
   - Total opportunity cost @ QQQ 10%/yr (and @ SGOV 5%/yr)
   - Net = PnL - opp cost
"""
from __future__ import annotations
import csv
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q082"))
from q082_p6_bcd_synth_reconstruction import (
    load_spx_history, load_vix_history, simulate_bcd_trade,
)

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"


def main():
    print("Loading data...")
    sig_rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            try:
                sig_rows.append({
                    "date":      r["date"],
                    "vix":       float(r["vix"]),
                    "regime":    r["regime"],
                    "trend":     r["trend"],
                    "iv_signal": r["iv_signal"],
                })
            except (ValueError, TypeError):
                continue
    sig_rows.sort(key=lambda r: r["date"])
    spx = load_spx_history()
    vix = load_vix_history()

    # Build trade universes
    # (1) Pre-SPEC-113: existing LOW_VOL × BULL × BCD only
    pre_eligible = [r["date"] for r in sig_rows
                     if r["regime"] == "LOW_VOL" and r["trend"] == "BULLISH"]
    # (2) Post-SPEC-113: above + NORMAL × IV_LOW × BULL × VIX<18 (carve-out)
    post_eligible = [r["date"] for r in sig_rows
                      if (r["regime"] == "LOW_VOL" and r["trend"] == "BULLISH")
                      or (r["regime"] == "NORMAL" and r["trend"] == "BULLISH"
                          and r["iv_signal"] == "LOW" and r["vix"] < 18)]
    pre_eligible.sort()
    post_eligible.sort()

    def simulate_sequential(eligible_dates):
        """Sequential ladder over given eligible dates."""
        trades = []
        last_exit = None
        for d in eligible_dates:
            if last_exit and d <= last_exit:
                continue
            t = simulate_bcd_trade(d, spx, vix)
            if t is None:
                continue
            trades.append(t)
            last_exit = t["exit_date"]
        return trades

    print("Simulating sequential ladder...")
    pre_trades = simulate_sequential(pre_eligible)
    post_trades = simulate_sequential(post_eligible)
    print(f"  pre-SPEC-113 (LOW_VOL × BULL only): {len(pre_trades)} trades")
    print(f"  post-SPEC-113 (+ NORMAL × IV_LOW × BULL × VIX<18): {len(post_trades)} trades")

    # ============================================================
    # Cash time-coverage analysis
    # ============================================================
    print("\n" + "=" * 78)
    print("CASH TIME-COVERAGE ANALYSIS")
    print("=" * 78)

    # For each calendar day in 26y, determine cash occupied
    if not sig_rows:
        return
    all_dates = set(r["date"] for r in sig_rows)
    sorted_dates = sorted(all_dates)
    start = date.fromisoformat(sorted_dates[0])
    end = date.fromisoformat(sorted_dates[-1])
    total_trading_days = len(sorted_dates)
    total_calendar_days = (end - start).days + 1
    n_years = total_calendar_days / 365.25
    print(f"  Window: {start.isoformat()} → {end.isoformat()} ({total_trading_days} trading days, {n_years:.1f} years)")

    def cash_coverage_stats(trades):
        """For each trade [entry, exit), accumulate cash-days × debit."""
        occupied_trading_days = set()
        cash_day_dollar = 0.0  # sum of debit_usd × calendar_days_open
        debits = []
        hold_calendar_days = []
        for t in trades:
            d_in = date.fromisoformat(t["entry_date"])
            d_out = date.fromisoformat(t["exit_date"])
            # All trading days [d_in, d_out)
            d = d_in
            while d < d_out:
                iso = d.isoformat()
                if iso in all_dates:
                    occupied_trading_days.add(iso)
                d += timedelta(days=1)
            hold_calendar = (d_out - d_in).days
            cash_day_dollar += t["entry_debit_usd"] * hold_calendar
            debits.append(t["entry_debit_usd"])
            hold_calendar_days.append(hold_calendar)
        return {
            "occupied_days": len(occupied_trading_days),
            "cash_day_dollar": cash_day_dollar,
            "median_debit": median(debits) if debits else 0,
            "total_hold_calendar_days": sum(hold_calendar_days),
            "n_trades": len(trades),
        }

    pre_stats = cash_coverage_stats(pre_trades)
    post_stats = cash_coverage_stats(post_trades)

    pre_coverage_pct = 100 * pre_stats["occupied_days"] / total_trading_days
    post_coverage_pct = 100 * post_stats["occupied_days"] / total_trading_days
    delta_coverage = post_coverage_pct - pre_coverage_pct

    print(f"\n{'Metric':<40} {'Pre-SPEC-113':>14} {'Post-SPEC-113':>14} {'Δ':>10}")
    print("-" * 82)
    print(f"{'Trades over 26y':<40} {pre_stats['n_trades']:>14d} {post_stats['n_trades']:>14d} "
          f"{post_stats['n_trades']-pre_stats['n_trades']:>+10d}")
    print(f"{'Trades / year':<40} {pre_stats['n_trades']/n_years:>14.1f} "
          f"{post_stats['n_trades']/n_years:>14.1f} "
          f"{(post_stats['n_trades']-pre_stats['n_trades'])/n_years:>+10.1f}")
    print(f"{'Median debit ($)':<40} {pre_stats['median_debit']:>14,.0f} "
          f"{post_stats['median_debit']:>14,.0f}")
    print(f"{'BCD-occupied trading days (n)':<40} {pre_stats['occupied_days']:>14d} "
          f"{post_stats['occupied_days']:>14d} "
          f"{post_stats['occupied_days']-pre_stats['occupied_days']:>+10d}")
    print(f"{'Cash time-coverage rate (%)':<40} {pre_coverage_pct:>14.1f} "
          f"{post_coverage_pct:>14.1f} {delta_coverage:>+10.1f}")
    print(f"{'Cash-day-dollars ($)':<40} {pre_stats['cash_day_dollar']:>14,.0f} "
          f"{post_stats['cash_day_dollar']:>14,.0f}")

    # ============================================================
    # Opportunity cost net settlement
    # ============================================================
    print("\n" + "=" * 78)
    print("OPPORTUNITY COST NET SETTLEMENT")
    print("=" * 78)

    def net_settlement(stats, trades, hurdle_pct_per_year):
        opp_cost = stats["cash_day_dollar"] * hurdle_pct_per_year / 100 / 365
        bcd_pnl = sum(t["pnl_usd"] for t in trades)
        net = bcd_pnl - opp_cost
        return {
            "bcd_pnl": bcd_pnl,
            "opp_cost": opp_cost,
            "net": net,
            "bcd_pnl_per_year": bcd_pnl / n_years,
            "opp_cost_per_year": opp_cost / n_years,
            "net_per_year": net / n_years,
        }

    for hurdle_pct, label in [(10, "QQQ 10%/yr"), (5, "SGOV 5%/yr")]:
        print(f"\n--- Hurdle: {label} ---")
        pre_net = net_settlement(pre_stats, pre_trades, hurdle_pct)
        post_net = net_settlement(post_stats, post_trades, hurdle_pct)
        delta_pnl = post_net["bcd_pnl"] - pre_net["bcd_pnl"]
        delta_opp = post_net["opp_cost"] - pre_net["opp_cost"]
        delta_net = post_net["net"] - pre_net["net"]
        print(f"  {'Metric':<35} {'Pre':>14} {'Post':>14} {'Δ':>14}")
        print(f"  {'Total BCD PnL ($)':<35} {pre_net['bcd_pnl']:>14,.0f} "
              f"{post_net['bcd_pnl']:>14,.0f} {delta_pnl:>+14,.0f}")
        print(f"  {'Total opp cost ($)':<35} {pre_net['opp_cost']:>14,.0f} "
              f"{post_net['opp_cost']:>14,.0f} {delta_opp:>+14,.0f}")
        print(f"  {'Net = PnL - opp cost ($)':<35} {pre_net['net']:>14,.0f} "
              f"{post_net['net']:>14,.0f} {delta_net:>+14,.0f}")
        print(f"  {'Annualized: BCD ($/yr)':<35} {pre_net['bcd_pnl_per_year']:>14,.0f} "
              f"{post_net['bcd_pnl_per_year']:>14,.0f} {delta_pnl/n_years:>+14,.0f}")
        print(f"  {'Annualized: opp cost ($/yr)':<35} {pre_net['opp_cost_per_year']:>14,.0f} "
              f"{post_net['opp_cost_per_year']:>14,.0f} {delta_opp/n_years:>+14,.0f}")
        print(f"  {'Annualized: net ($/yr)':<35} {pre_net['net_per_year']:>14,.0f} "
              f"{post_net['net_per_year']:>14,.0f} {delta_net/n_years:>+14,.0f}")

        # Decision-level summary
        print(f"\n  Verdict at {label}:")
        if delta_net > 0:
            print(f"    SPEC-113 NET POSITIVE: +${delta_net/n_years:,.0f}/yr after opp cost")
            print(f"    Carve-cell BCD adds ${delta_pnl/n_years:,.0f}/yr PnL,")
            print(f"      occupies ${delta_opp/n_years:,.0f}/yr in opp cost,")
            print(f"      net ${delta_net/n_years:,.0f}/yr improvement.")
        else:
            print(f"    SPEC-113 NET NEGATIVE: ${delta_net/n_years:,.0f}/yr loss after opp cost")
            print(f"    Extra BCD PnL ${delta_pnl/n_years:,.0f}/yr < opp cost ${delta_opp/n_years:,.0f}/yr")
            print(f"    Recommend: do NOT add this cell, or add time-coverage cap on top of SPEC-111")

    # ============================================================
    # Additional: per-trade contribution from new cell only
    # ============================================================
    print("\n" + "=" * 78)
    print("ISOLATED: contribution of new cell trades only (not in sequential w/ old)")
    print("=" * 78)
    # The increment from adding the cell = post_pnl - pre_pnl
    new_cell_trades = len(post_trades) - len(pre_trades)
    new_cell_pnl = sum(t["pnl_usd"] for t in post_trades) - sum(t["pnl_usd"] for t in pre_trades)
    new_cell_cash_days = post_stats["cash_day_dollar"] - pre_stats["cash_day_dollar"]
    print(f"  Net additional trades (post - pre): {new_cell_trades}")
    print(f"  Net additional PnL: ${new_cell_pnl:+,.0f}")
    print(f"  Net additional cash-day-dollars: ${new_cell_cash_days:+,.0f}")
    if new_cell_trades > 0:
        print(f"  Per-trade increment PnL: ${new_cell_pnl/new_cell_trades:+,.0f}")
    print()
    print(f"  Per-year increment over 26y: ${new_cell_pnl/n_years:+,.0f}/yr")
    for hurdle_pct, label in [(10, "QQQ"), (5, "SGOV")]:
        opp_increment = new_cell_cash_days * hurdle_pct / 100 / 365
        print(f"  vs opp cost @ {label} {hurdle_pct}%: ${opp_increment/n_years:,.0f}/yr  →  net: ${(new_cell_pnl - opp_increment)/n_years:+,.0f}/yr")


if __name__ == "__main__":
    main()
