"""Q081 P1 — Historical BCD cash deployment timeline + crowd-out events.

Method:
1. Load 21 BCD trades from 3y backtest cache.
2. Build daily timeline 2023-06-02 → 2026-04-29: for each trading day, sum
   the entry debit ($USD) of all BCD positions held open on that day.
3. Compare daily aggregate BCD debit against the steady-state available
   cash baseline ($37,046 per P0).
4. Flag "crowd-out events": days where aggregate BCD debit would have
   exceeded $37k under PM's current steady-state, forcing QQQ/SPY sale.
5. Also report opportunity cost (debit × QQQ_hurdle × days / 365).

Output:
- q081_p1_bcd_cash_timeline.csv (one row per trading day with debit
  in-force, position count, crowd-out flag, opp cost incrementing)
- q081_p1_crowdout_events.csv (one row per crowd-out date)
"""
from __future__ import annotations
import csv
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRADES = ROOT / "data" / "backtest_trades_3y_2026-04-29.csv"
TIMELINE_OUT = ROOT / "research" / "q081" / "q081_p1_bcd_cash_timeline.csv"
CROWDOUT_OUT = ROOT / "research" / "q081" / "q081_p1_crowdout_events.csv"

STEADY_STATE_CASH = 37_046.00       # P0 baseline post-Schwab→QQQ
QQQ_HURDLE_ANNUAL = 0.10             # PM-ratified hurdle
DAYS_PER_YEAR = 365


def load_bcd_trades() -> list[dict]:
    out = []
    with open(TRADES) as f:
        for r in csv.DictReader(f):
            if r["strategy_key"] != "bull_call_diagonal":
                continue
            out.append({
                "entry":  date.fromisoformat(r["entry_date"]),
                "exit":   date.fromisoformat(r["exit_date"]),
                "debit":  float(r["option_premium_enter_usd"]),
                "pnl":    float(r["exit_pnl_usd"]),
                "vix":    float(r["entry_vix"]),
                "regime": r["regime"],
            })
    return sorted(out, key=lambda t: t["entry"])


def daterange(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri only (ignore holidays for simplicity;
                              # over 3y the few holidays won't change verdict)
            yield d
        d += timedelta(days=1)


def main() -> None:
    trades = load_bcd_trades()
    start = trades[0]["entry"]
    end = max(t["exit"] for t in trades)
    print(f"BCD trades: {len(trades)}  window: {start} → {end}")
    print(f"Steady-state cash baseline: ${STEADY_STATE_CASH:,.0f}")
    print(f"QQQ hurdle: {QQQ_HURDLE_ANNUAL*100:.1f}%/yr")

    timeline_rows = []
    crowdout_rows = []
    cum_opp_cost = 0.0

    for d in daterange(start, end):
        # In-force window: [entry, exit) — exclude exit day to avoid double-
        # counting same-day rolls (position closes AM, next opens PM = cash
        # impact is wash on that day, not 2×).
        open_trades = [t for t in trades if t["entry"] <= d < t["exit"]]
        if not open_trades:
            continue
        total_debit = sum(t["debit"] for t in open_trades)
        n_open = len(open_trades)
        max_vix = max(t["vix"] for t in open_trades)

        crowdout_pct = total_debit / STEADY_STATE_CASH
        crowdout_flag = total_debit > STEADY_STATE_CASH
        cash_remaining_or_overshoot = STEADY_STATE_CASH - total_debit

        # Daily opportunity cost: debit × hurdle / 365 (continuous accrual)
        opp_cost_today = total_debit * QQQ_HURDLE_ANNUAL / DAYS_PER_YEAR
        cum_opp_cost += opp_cost_today

        timeline_rows.append({
            "date":               d.isoformat(),
            "n_bcd_open":         n_open,
            "total_debit":        round(total_debit, 0),
            "cash_baseline":      STEADY_STATE_CASH,
            "consumed_pct":       round(100 * crowdout_pct, 1),
            "cash_remaining":     round(cash_remaining_or_overshoot, 0),
            "crowdout":           crowdout_flag,
            "max_entry_vix":      round(max_vix, 2),
            "opp_cost_today":     round(opp_cost_today, 2),
            "cum_opp_cost":       round(cum_opp_cost, 2),
        })

        if crowdout_flag:
            crowdout_rows.append({
                "date":           d.isoformat(),
                "n_bcd_open":     n_open,
                "total_debit":    round(total_debit, 0),
                "cash_baseline":  STEADY_STATE_CASH,
                "overshoot":      round(total_debit - STEADY_STATE_CASH, 0),
                "max_entry_vix":  round(max_vix, 2),
                "trade_ids":      "; ".join(f"{t['entry']}→{t['exit']}" for t in open_trades),
            })

    # Write
    if timeline_rows:
        with open(TIMELINE_OUT, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(timeline_rows[0].keys()))
            w.writeheader()
            w.writerows(timeline_rows)
        print(f"\nwrote {TIMELINE_OUT} ({len(timeline_rows)} rows)")

    if crowdout_rows:
        with open(CROWDOUT_OUT, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(crowdout_rows[0].keys()))
            w.writeheader()
            w.writerows(crowdout_rows)
        print(f"wrote {CROWDOUT_OUT} ({len(crowdout_rows)} crowd-out days)")
    else:
        CROWDOUT_OUT.write_text("date,n_bcd_open,total_debit,cash_baseline,overshoot,max_entry_vix,trade_ids\n")
        print("no crowd-out events at steady-state baseline")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY (under steady-state baseline)")
    print(f"{'=' * 60}")
    print(f"Trading days with BCD open: {len(timeline_rows)}")
    print(f"  ≥1 BCD open: {sum(1 for r in timeline_rows if r['n_bcd_open']>=1)}")
    print(f"  ≥2 BCDs open: {sum(1 for r in timeline_rows if r['n_bcd_open']>=2)}")
    print(f"Crowd-out days (debit > $37k): {len(crowdout_rows)}")
    if crowdout_rows:
        max_overshoot = max(r['overshoot'] for r in crowdout_rows)
        print(f"  Max overshoot: ${max_overshoot:,.0f}")
    avg_consumed = sum(r['consumed_pct'] for r in timeline_rows) / len(timeline_rows) if timeline_rows else 0
    print(f"Avg cash consumption (when BCD open): {avg_consumed:.1f}% of $37k")
    print(f"Cumulative opportunity cost: ${cum_opp_cost:,.0f}")
    bcd_total_pnl = sum(t["pnl"] for t in trades)
    print(f"BCD total PnL: ${bcd_total_pnl:,.0f}")
    print(f"Net of opp cost: ${bcd_total_pnl - cum_opp_cost:,.0f}")
    print(f"Opp cost as % of gross PnL: {cum_opp_cost/bcd_total_pnl*100:.1f}%")


if __name__ == "__main__":
    main()
