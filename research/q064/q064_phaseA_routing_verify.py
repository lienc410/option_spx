"""Q064 Phase A — Mechanical verification of Task 1 routing claim.

2nd Quant requested (Q1 verdict): "I would require a quick mechanical
confirmation in the script/log:
  For the 15 aftermath entry dates:
   - force is_aftermath = False
   - run selector normally
   - record routed strategy"

Method:
  1. Monkey-patch selector.is_aftermath to always return False
  2. Run full backtest (same span as P3)
  3. For each of the 15 aftermath entry dates (from P3), record what
     strategy/path the selector would have produced
  4. Cross-reference: do they route to BPS_HV (PM's assumption),
     IC_HV normal (Quant's Task 1 claim), or reduce_wait (guard fires)?
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest

REPO = Path(__file__).resolve().parents[2]
P3_CSV = REPO / "research" / "q064" / "q064_p3_results.csv"

START = "2009-01-01"
END = "2025-06-30"
ACCOUNT = 150_000.0


def main():
    print("=" * 90)
    print("Q064 Phase A — Mechanical routing verification: aftermath=False on 15 dates")
    print("=" * 90)

    # Load aftermath dates
    p3 = pd.read_csv(P3_CSV)
    aftermath_dates = set(p3["entry_date"].astype(str).tolist())
    print(f"Loaded {len(aftermath_dates)} aftermath entry dates from P3.")

    # Force is_aftermath = False
    orig_is_aftermath = sel.is_aftermath

    def patched_is_aftermath(vix):
        return False

    sel.is_aftermath = patched_is_aftermath
    # Engine imports is_aftermath via "from strategy.selector import ..." so we also
    # patch the engine binding (in case it ever imported the function directly).
    if hasattr(engine_mod, "is_aftermath"):
        engine_mod.is_aftermath = patched_is_aftermath

    try:
        print("\nRunning baseline backtest with is_aftermath=False ...")
        bt = run_backtest(start_date=START, end_date=END,
                          account_size=ACCOUNT, verbose=False)
    finally:
        sel.is_aftermath = orig_is_aftermath
        if hasattr(engine_mod, "is_aftermath"):
            engine_mod.is_aftermath = orig_is_aftermath

    # ── For each aftermath date, find: did selector emit a trade? what strategy?
    # We use signal_history (which records strategy recommended on each day)
    sig_df = pd.DataFrame(bt.signals)
    sig_df["date_str"] = sig_df["date"].astype(str)

    # Also use trades to see if a trade actually got opened on/near that date
    trades_by_entry = {t.entry_date: t for t in bt.trades}

    print("\n" + "=" * 90)
    print(f"{'aftermath_date':<14} {'selector_rec':<32} {'iv_signal':<8} {'trend':<10} "
          f"{'actual_trade?':<14} {'trade_strategy':<32}")
    print("-" * 130)
    routing_counter = Counter()
    for d in sorted(aftermath_dates):
        sig_row = sig_df[sig_df["date_str"] == d]
        if len(sig_row) == 0:
            print(f"{d:<14} (no signal — non-trading day or missing)")
            continue
        rec = sig_row.iloc[0]["strategy"]
        iv_s = sig_row.iloc[0].get("iv_signal", "?")
        trend = sig_row.iloc[0].get("trend", "?")
        # Check if a trade got opened on this date (or near it)
        trade_on = trades_by_entry.get(d, None)
        trade_label = ""
        if trade_on is not None:
            trade_label = trade_on.strategy.value
        else:
            # Maybe trade was opened next trading day
            for off_d in pd.bdate_range(d, periods=4)[1:]:
                t = trades_by_entry.get(off_d.strftime("%Y-%m-%d"))
                if t is not None:
                    trade_label = f"{t.strategy.value} (+{off_d.strftime('%Y-%m-%d')[8:10]})"
                    break
            if not trade_label:
                trade_label = "(no trade opened)"
        print(f"{d:<14} {rec:<32} {iv_s:<8} {trend:<10} "
              f"{'YES' if trade_on else 'next-day' if trade_label != '(no trade opened)' else 'NO':<14} "
              f"{trade_label:<32}")
        routing_counter[rec] += 1

    print("\n" + "=" * 90)
    print("Routing distribution summary (selector recommendation on aftermath dates with patched is_aftermath=False):")
    print("=" * 90)
    for strategy, count in routing_counter.most_common():
        pct = count / sum(routing_counter.values()) * 100
        print(f"  {strategy:<32}  n={count:>3}  ({pct:.1f}%)")

    print(f"\nTotal dates with signals: {sum(routing_counter.values())}")
    print(f"BPS_HV count (PM's assumption): {routing_counter.get('Bull Put Spread (High Vol)', 0)}")
    print(f"IC_HV count (Quant's Task 1 claim): {routing_counter.get('Iron Condor (High Vol)', 0)}")
    print(f"Reduce/Wait count: {routing_counter.get('Reduce / Wait', 0)}")


if __name__ == "__main__":
    main()
