"""Q064 P5 — VIX Re-cross Stop Test on 15 Aftermath BPS_HV Counterfactual Trades.

Tests 4 stop variants on the same 15 BPS_HV counterfactual trades from P3:
  A: No stop (P3 baseline, BPS_HV with original exit)
  B: VIX > 28 first daily close → exit next day @ BS mid
  C: VIX > 30 first daily close → exit next day @ BS mid
  D: VIX > entry_vix × 1.10 first daily close → exit next day @ BS mid

Exit P&L estimation when stop fires:
  exit_cost_ps = exit_value_bps(S_stop_next, vix_stop_next, entry_dict, remaining_dte)
  pnl_per_share = entry_credit_per_share - exit_cost_ps
  pnl_total     = pnl_per_share * 100 * contracts

(Uses P3's exact pricing helpers — BS + term_multiplier — for consistency.)

For each version, reports:
  n_stop_triggered, win_rate, avg_pnl, worst_trade, $/BP-day, total_pnl,
  premature_exit_of_winner_count

V3-A equal-BP P4 result is loaded as final reference column.

Outputs:
  research/q064/q064_p5_results.csv     (per-trade detail × 4 versions)
  research/q064/q064_p5_summary.csv     (aggregated metrics)
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Reuse P3 helpers
from research.q064.q064_p3_structure_counterfactual import (
    BPS_HV_SHORT_DELTA, BPS_HV_LONG_DELTA, BPS_HV_DTE,
    term_multiplier, bs_put, delta_to_strike_put,
    price_bps_hv_entry, exit_value_bps,
)

P3_CSV = REPO / "research" / "q064" / "q064_p3_results.csv"
P4_CSV = REPO / "research" / "q064" / "q064_p4_results.csv"
OUT_DETAIL = REPO / "research" / "q064" / "q064_p5_results.csv"
OUT_SUMMARY = REPO / "research" / "q064" / "q064_p5_summary.csv"

# Stop thresholds
STOP_VIX_B = 28.0
STOP_VIX_C = 30.0
STOP_PCT_D = 1.10  # entry_vix × 1.10


def load_market_series(start: str = "2009-01-01", end: str = "2025-06-30"):
    """Pull SPX + VIX daily closes."""
    spx_raw = yf.download("^GSPC", start=start, end=end, progress=False, auto_adjust=False)
    vix_raw = yf.download("^VIX", start=start, end=end, progress=False, auto_adjust=False)
    for df in (spx_raw, vix_raw):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    spx = spx_raw["Close"].squeeze()
    vix = vix_raw["Close"].squeeze()
    spx.index = pd.to_datetime(spx.index).normalize()
    vix.index = pd.to_datetime(vix.index).normalize()
    return spx, vix


def next_trading_day(idx: pd.DatetimeIndex, after: pd.Timestamp) -> pd.Timestamp | None:
    after = pd.Timestamp(after).normalize()
    future = idx[idx > after]
    return future[0] if len(future) > 0 else None


def check_stop(vix_series: pd.Series,
               entry_date: pd.Timestamp,
               exit_date: pd.Timestamp,
               threshold: float) -> pd.Timestamp | None:
    """
    Return first trading day where VIX_close > threshold,
    strictly AFTER entry_date and on/before exit_date.
    None if no trigger.
    """
    entry = pd.Timestamp(entry_date).normalize()
    exit_ = pd.Timestamp(exit_date).normalize()
    # window: (entry, exit_]
    window = vix_series[(vix_series.index > entry) & (vix_series.index <= exit_)]
    triggered = window[window > threshold]
    return triggered.index[0] if len(triggered) > 0 else None


def simulate_trade_with_stop(row, spx: pd.Series, vix: pd.Series,
                             stop_threshold_fn, label: str) -> dict:
    """
    Simulate one trade with a given stop rule.

    stop_threshold_fn(entry_vix: float) -> float | None
        Returns the threshold; None means "no stop" (version A).
    """
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date_orig = pd.Timestamp(row["exit_date"]).normalize()
    S_entry = float(row["S_entry"])
    vix_entry = float(row["vix_at_entry"])
    contracts = float(row["contracts"])
    K_short = float(row["bps_short_K"])
    K_long = float(row["bps_long_K"])
    entry_credit_ps = float(row["bps_entry_credit"]) / 100.0 / contracts  # to per-share
    bp = float(row["bps_bp"])

    threshold = stop_threshold_fn(vix_entry)

    stop_triggered_on = None
    if threshold is not None:
        stop_triggered_on = check_stop(vix, entry_date, exit_date_orig, threshold)

    if stop_triggered_on is None:
        # No stop: use original P3 exit
        actual_exit_date = exit_date_orig
        S_exit = float(row["S_exit"])
        vix_exit = float(row["vix_at_exit"])
        was_stopped = False
    else:
        # Stop triggered: exit next trading day
        nd = next_trading_day(vix.index, stop_triggered_on)
        if nd is None or nd > exit_date_orig:
            # No next day available within hold window → fallback to original exit
            actual_exit_date = exit_date_orig
            S_exit = float(row["S_exit"])
            vix_exit = float(row["vix_at_exit"])
            was_stopped = False
        else:
            actual_exit_date = nd
            S_exit = float(spx.loc[nd]) if nd in spx.index else float(row["S_exit"])
            vix_exit = float(vix.loc[nd]) if nd in vix.index else float(row["vix_at_exit"])
            was_stopped = True

    # Compute remaining DTE at exit
    dte_at_exit = BPS_HV_DTE - (actual_exit_date - entry_date).days
    dte_at_exit = max(dte_at_exit, 0)

    # Recompute P&L with BS mid at exit
    entry_dict = {
        "short_strike": K_short,
        "long_strike":  K_long,
        "spread_width": K_short - K_long,
        "entry_credit_per_share": entry_credit_ps,
    }
    exit_cost_ps = exit_value_bps(S_exit, vix_exit, entry_dict, dte_at_exit)
    pnl_ps = entry_credit_ps - exit_cost_ps
    pnl_total = pnl_ps * 100.0 * contracts

    hold_days = (actual_exit_date - entry_date).days
    bp_day = (pnl_total / bp) * (365.0 / max(hold_days, 1)) if bp > 0 else 0.0

    # Reference: original P3 BPS_HV P&L (no stop) for "premature winner" check
    p3_orig_pnl = float(row["bps_pnl"])

    return {
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "exit_date_orig": exit_date_orig.strftime("%Y-%m-%d"),
        "actual_exit_date": actual_exit_date.strftime("%Y-%m-%d"),
        "stop_triggered_on": stop_triggered_on.strftime("%Y-%m-%d") if stop_triggered_on else "",
        "was_stopped": was_stopped,
        "vix_at_entry": vix_entry,
        "vix_at_exit": vix_exit,
        "hold_days": hold_days,
        "S_entry": S_entry,
        "S_exit": S_exit,
        "K_short": K_short,
        "K_long": K_long,
        "contracts": contracts,
        "entry_credit_ps": round(entry_credit_ps, 4),
        "exit_cost_ps": round(exit_cost_ps, 4),
        "pnl": round(pnl_total, 2),
        "p3_orig_pnl": round(p3_orig_pnl, 2),
        "premature_winner": was_stopped and p3_orig_pnl > 0 and pnl_total < p3_orig_pnl,
        "bp": bp,
        "bp_day": round(bp_day, 4),
        "version": label,
    }


def aggregate(rows: list[dict], label: str, bp_total: float, hold_days_total: int) -> dict:
    pnls = np.array([r["pnl"] for r in rows])
    wins = pnls > 0
    total_pnl = float(pnls.sum())
    total_bp_days = float(sum(r["bp"] * r["hold_days"] for r in rows))
    return {
        "version": label,
        "n_trades": len(rows),
        "n_stop_triggered": sum(1 for r in rows if r["was_stopped"]),
        "win_rate_pct": round(float(wins.mean() * 100), 1),
        "avg_pnl": round(float(pnls.mean()), 2),
        "median_pnl": round(float(np.median(pnls)), 2),
        "worst_trade": round(float(pnls.min()), 2),
        "best_trade": round(float(pnls.max()), 2),
        "total_pnl": round(total_pnl, 2),
        "dollar_per_bp_day": round(total_pnl / total_bp_days * 1e6, 2) if total_bp_days > 0 else 0.0,
        "premature_winners": sum(1 for r in rows if r["premature_winner"]),
    }


def main():
    print("=" * 80)
    print("Q064 P5 — VIX Re-cross Stop Test on 15 Aftermath BPS_HV trades")
    print("=" * 80)
    p3 = pd.read_csv(P3_CSV)
    p4 = pd.read_csv(P4_CSV)
    print(f"P3 rows (BPS_HV counterfactual): {len(p3)}")
    print(f"P4 rows (V3-A equal-BP):         {len(p4)}")

    print("\nLoading SPX + VIX series via yfinance...")
    spx, vix_series = load_market_series()
    print(f"  SPX bars: {len(spx)}")
    print(f"  VIX bars: {len(vix_series)}")

    stop_specs = [
        ("A_no_stop",   lambda v: None),
        ("B_vix_28",    lambda v: STOP_VIX_B),
        ("C_vix_30",    lambda v: STOP_VIX_C),
        ("D_entry_x110",lambda v: v * STOP_PCT_D),
    ]

    all_rows = []
    summaries = []
    bp_total = float(p3["bps_bp"].sum())

    for label, fn in stop_specs:
        rows = [simulate_trade_with_stop(row, spx, vix_series, fn, label)
                for _, row in p3.iterrows()]
        all_rows.extend(rows)
        hold_total = sum(r["hold_days"] for r in rows)
        summaries.append(aggregate(rows, label, bp_total, hold_total))

    # Add P4 V3-A equal-BP reference
    v3a_pnls = p4["v3a_pnl_adj"].values
    v3a_total_bp_days = float((p4["equal_bp"] * p4["hold_days"]).sum())
    summaries.append({
        "version": "V3A_equal_BP (P4 ref)",
        "n_trades": len(p4),
        "n_stop_triggered": 0,
        "win_rate_pct": round(float((v3a_pnls > 0).mean() * 100), 1),
        "avg_pnl": round(float(v3a_pnls.mean()), 2),
        "median_pnl": round(float(np.median(v3a_pnls)), 2),
        "worst_trade": round(float(v3a_pnls.min()), 2),
        "best_trade": round(float(v3a_pnls.max()), 2),
        "total_pnl": round(float(v3a_pnls.sum()), 2),
        "dollar_per_bp_day": round(float(v3a_pnls.sum()) / v3a_total_bp_days * 1e6, 2) if v3a_total_bp_days > 0 else 0,
        "premature_winners": 0,
    })

    detail_df = pd.DataFrame(all_rows)
    summary_df = pd.DataFrame(summaries)

    detail_df.to_csv(OUT_DETAIL, index=False)
    summary_df.to_csv(OUT_SUMMARY, index=False)
    print(f"\nWrote {OUT_DETAIL}")
    print(f"Wrote {OUT_SUMMARY}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(summary_df.to_string(index=False))

    # Trades stopped per version
    print("\n" + "=" * 80)
    print("Per-trade stop status (rows where any version stops)")
    print("=" * 80)
    print(f"{'entry_date':<12} {'vix_in':>6} {'B@28':>6} {'C@30':>6} {'D x1.10':>9} {'p3_orig_pnl':>12}")
    for _, r in p3.iterrows():
        cells = []
        for label, fn in stop_specs[1:]:  # skip A
            thr = fn(r["vix_at_entry"])
            stop_on = check_stop(vix_series, pd.Timestamp(r["entry_date"]),
                                 pd.Timestamp(r["exit_date"]), thr)
            cells.append(stop_on.strftime("%m-%d") if stop_on else "—")
        print(f"{r['entry_date']:<12} {r['vix_at_entry']:>6.2f} "
              f"{cells[0]:>6} {cells[1]:>6} {cells[2]:>9} ${r['bps_pnl']:>+9,.0f}")


if __name__ == "__main__":
    main()
