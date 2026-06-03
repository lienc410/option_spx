"""Q083 P1b — Counterfactual BPS on state (a) days (PM's actual pain).

P1 (state c) tested 'IVR allows but IVP blocks' = IVP too HIGH scenarios.
PM's current pain (IVR=15, IVP=26) is state (a): iv_signal LOW AND IVP < 40.
Both gates block by current design. This script runs the same BS-flat BPS
counterfactual on state (a) days.

If state (a) counterfactual PnL is materially positive → matrix cell-routing
(iv_signal LOW → reduce_wait) is over-restrictive AND IVP < 40 gate too.
If negative → both gates are doing their job; PM's pain is the correct design.
"""
from __future__ import annotations
import csv
import math
from pathlib import Path
from statistics import mean, median, stdev
from collections import defaultdict

# Import simulation logic from P1
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from q083_p1_counterfactual_bps import (
    simulate_bps_trade,
    load_spx_history,
    load_vix_history,
    _252d_range_at,
)

ROOT = Path(__file__).resolve().parents[2]
ASSIGN = ROOT / "research" / "q083" / "q083_p0_state_assignments.csv"
TRADES_OUT = ROOT / "research" / "q083" / "q083_p1b_state_a_trades.csv"
STRAT_OUT = ROOT / "research" / "q083" / "q083_p1b_state_a_stratified.csv"


def main():
    print("Loading state (a) days...")
    state_a_days = []
    with open(ASSIGN) as f:
        for r in csv.DictReader(f):
            if r["state"] == "a_double_blocked":
                state_a_days.append(r)
    print(f"  state (a) days: {len(state_a_days)}")

    print("Loading SPX + VIX...")
    spx = load_spx_history()
    vix = load_vix_history()

    print("Simulating counterfactual BPS trades on state (a) days...")
    trades = []
    skipped = 0
    for r in state_a_days:
        t = simulate_bps_trade(r["date"], spx, vix)
        if t is None:
            skipped += 1
            continue
        try:
            ivp = float(r["ivp"])
            ivr = float(r["ivr"]) if r["ivr"] else None
        except (TypeError, ValueError):
            ivp, ivr = None, None
        range_252d = _252d_range_at(r["date"], vix)
        t["state_ivp"] = round(ivp, 1) if ivp is not None else None
        t["state_ivr"] = round(ivr, 1) if ivr is not None else None
        t["state_iv_signal"] = r["iv_signal"]
        t["range_252d"] = round(range_252d, 2) if range_252d else None
        t["year"] = r["year"]
        trades.append(t)
    print(f"  trades synthesized: {len(trades)} (skipped {skipped})")

    if trades:
        with open(TRADES_OUT, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
            w.writeheader()
            w.writerows(trades)
        print(f"wrote {TRADES_OUT}")

    pnls = [t["pnl_per_share"] for t in trades]
    wins = sum(1 for t in trades if t["win"])
    print()
    print("=" * 80)
    print(f"AGGREGATE COUNTERFACTUAL BPS PnL — state (a) days (n={len(trades)})")
    print("=" * 80)
    print(f"  Win rate:       {wins}/{len(trades)} = {100*wins/len(trades):.1f}%")
    print(f"  Mean PnL/share: {mean(pnls):>+8.2f}  (×100 = ${mean(pnls)*100:>+8.0f} per contract)")
    print(f"  Median:         {median(pnls):>+8.2f}")
    print(f"  Std:            {stdev(pnls):>8.2f}")
    print(f"  Worst:          {min(pnls):>+8.2f}  (${min(pnls)*100:>+8.0f})")
    print(f"  Best:           {max(pnls):>+8.2f}")
    mp = mean(pnls)
    downside = math.sqrt(sum(min(p, 0)**2 for p in pnls) / len(pnls))
    sortino = mp / downside if downside > 0 else float("inf")
    sharpe = mp / stdev(pnls) if stdev(pnls) > 0 else float("inf")
    print(f"  Sharpe: {sharpe:+.3f}")
    print(f"  Sortino: {sortino:+.3f}")

    # Compare to P1 (state c)
    print()
    print("=" * 80)
    print("COMPARISON: state (a) vs state (c) counterfactuals")
    print("=" * 80)
    print(f"{'metric':<25} {'state (a)':>15} {'state (c) P1':>15}")
    print("-" * 65)
    print(f"{'n':<25} {len(trades):>15} {357:>15}")
    print(f"{'win rate':<25} {100*wins/len(trades):>14.1f}% {65.3:>14.1f}%")
    print(f"{'mean PnL/contract':<25} {mp*100:>+15.0f} {427:>+15.0f}")
    print(f"{'median PnL/contract':<25} {median(pnls)*100:>+15.0f} {521:>+15.0f}")
    print(f"{'worst PnL/contract':<25} {min(pnls)*100:>+15.0f} {-5681:>+15.0f}")
    print(f"{'Sortino':<25} {sortino:>+15.3f} {0.437:>+15.3f}")

    # Stratify by year
    print()
    print("State (a) — by year (top 10):")
    by_year = defaultdict(list)
    for t in trades:
        by_year[t["year"]].append(t)
    strat_rows = []
    for yr in sorted(by_year, key=lambda y: -len(by_year[y]))[:10]:
        ts = by_year[yr]
        p = [t["pnl_per_share"] for t in ts]
        wr = sum(1 for t in ts if t["win"]) / len(ts)
        print(f"  year {yr}: n={len(ts):>3} mean=${mean(p)*100:>+6.0f} med=${median(p)*100:>+6.0f} "
              f"worst=${min(p)*100:>+6.0f} win_rate={wr:>5.1%}")
        strat_rows.append({
            "year": yr, "n": len(ts),
            "mean_pnl_per_contract": round(mean(p)*100, 0),
            "median_pnl_per_contract": round(median(p)*100, 0),
            "worst_pnl_per_contract": round(min(p)*100, 0),
            "win_rate": round(wr, 4),
        })

    # Stratify by 252d range width
    print()
    print("State (a) — by 252d VIX range width tertile:")
    valid = [t for t in trades if t["range_252d"] is not None]
    if valid:
        widths = sorted(t["range_252d"] for t in valid)
        q33 = widths[len(widths)//3]
        q67 = widths[2*len(widths)//3]
        for label, fn in [
            (f"narrow < {q33:.1f}", lambda t: t["range_252d"] < q33),
            (f"mid {q33:.1f}-{q67:.1f}", lambda t: q33 <= t["range_252d"] < q67),
            (f"wide ≥ {q67:.1f}", lambda t: t["range_252d"] >= q67),
        ]:
            ts = [t for t in valid if fn(t)]
            if not ts:
                continue
            p = [t["pnl_per_share"] for t in ts]
            wr = sum(1 for t in ts if t["win"]) / len(ts)
            dd = math.sqrt(sum(min(v, 0)**2 for v in p) / len(p))
            sort = mean(p) / dd if dd > 0 else 0
            print(f"  {label:<20} n={len(ts):>3} mean=${mean(p)*100:>+7.0f} worst=${min(p)*100:>+7.0f} "
                  f"win_rate={wr:>5.1%} Sortino={sort:>+5.3f}")
            strat_rows.append({
                "stratum": label,
                "n": len(ts),
                "mean_pnl_per_contract": round(mean(p)*100, 0),
                "worst_pnl_per_contract": round(min(p)*100, 0),
                "win_rate": round(wr, 4),
                "sortino": round(sort, 3),
            })

    if strat_rows:
        with open(STRAT_OUT, "w", newline="") as f:
            # Use union of keys to handle mixed schemas
            all_keys = set()
            for r in strat_rows:
                all_keys.update(r.keys())
            w = csv.DictWriter(f, fieldnames=sorted(all_keys))
            w.writeheader()
            w.writerows(strat_rows)
        print(f"\nwrote {STRAT_OUT}")


if __name__ == "__main__":
    main()
