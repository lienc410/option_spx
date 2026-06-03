"""Q083 P4 — D3 head-to-head: IVP63 vs IVP126 vs IVP252 (current).

Per G1 §4.B: simulate three alternative gate designs over 26y. Each replaces
the existing IVP252-based gate with a different lookback window. Report:
  (a) normal VIX region pass rate (the original complaint)
  (b) spike recovery time (the lag complaint)
  (c) counterfactual BPS PnL on each design's allowed-open days
  (d) TAIL cost: worst trade, Sortino, % worst-trade-frequency in each design

Plus per memory feedback_status_quo_bias_in_verdicts: D3 may open more trades
but at worse times. The tail cost (d) must be honestly reported.
Per Q082 P10 lesson: BPS is net SHORT VEGA (opposite of BCD long vega),
so skew impact on BPS in down moves is unfavorable — report skew bracket
on D3's wider sample if any subset shows positive edge.
"""
from __future__ import annotations
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q083_p1_counterfactual_bps import (
    simulate_bps_trade,
    load_spx_history,
    load_vix_history,
)

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
PASS_OUT = ROOT / "research" / "q083" / "q083_p4_d3_pass_rate_compare.csv"
TRADES_OUT = ROOT / "research" / "q083" / "q083_p4_d3_trades_compare.csv"

random.seed(2026)
BOOTSTRAP_N = 5000


def compute_ivp(vix_values: list[float], current_vix: float) -> float:
    """IVP = % of past N values BELOW current."""
    if not vix_values:
        return 50.0
    below = sum(1 for v in vix_values if v < current_vix)
    return 100 * below / len(vix_values)


def compute_ivr(vix_values: list[float], current_vix: float) -> float:
    """IVR linear position in min-max range."""
    if not vix_values:
        return 50.0
    lo, hi = min(vix_values), max(vix_values)
    if hi == lo:
        return 50.0
    return 100 * (current_vix - lo) / (hi - lo)


def classify_iv_signal(ivr: float) -> str:
    if ivr > 50:
        return "HIGH"
    if ivr < 30:
        return "LOW"
    return "NEUTRAL"


def passes_gate(iv_signal: str, ivp: float) -> bool:
    if iv_signal not in ("HIGH", "NEUTRAL"):
        return False
    if iv_signal == "NEUTRAL":
        return 43 <= ivp <= 55
    return 40 < ivp <= 70


def main():
    print("Loading signal history + SPX/VIX...")
    sig_rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            try:
                vix = float(r["vix"])
                sig_rows.append({
                    "date":   r["date"],
                    "vix":    vix,
                    "regime": r["regime"],
                    "trend":  r["trend"],
                })
            except (ValueError, TypeError):
                continue
    sig_rows.sort(key=lambda r: r["date"])
    print(f"  signal rows: {len(sig_rows)}")

    spx = load_spx_history()
    vix_hist = load_vix_history()

    # Recompute alt IVP / IVR per row using lookback windows
    # Index VIX by date for fast lookup
    vix_by_date = {r["date"]: r["vix"] for r in sig_rows}
    dates_sorted = sorted(vix_by_date.keys())
    date_to_idx = {d: i for i, d in enumerate(dates_sorted)}

    designs = ("IVP63", "IVP126", "IVP252_current")
    win_map = {"IVP63": 63, "IVP126": 126, "IVP252_current": 252}

    # For each row, compute alt readings per design
    augmented = []
    for r in sig_rows:
        idx = date_to_idx[r["date"]]
        if idx < 252:
            continue
        if r["regime"] != "NORMAL" or r["trend"] != "BULLISH":
            continue
        d_aug = {"date": r["date"], "vix": r["vix"]}
        for design_name, win in win_map.items():
            window = [vix_by_date[dates_sorted[j]] for j in range(idx - win, idx)]
            cur = r["vix"]
            ivp_alt = compute_ivp(window, cur)
            ivr_alt = compute_ivr(window, cur)
            iv_sig_alt = classify_iv_signal(ivr_alt)
            d_aug[f"{design_name}_ivp"] = round(ivp_alt, 1)
            d_aug[f"{design_name}_ivr"] = round(ivr_alt, 1)
            d_aug[f"{design_name}_iv_signal"] = iv_sig_alt
            d_aug[f"{design_name}_pass"] = passes_gate(iv_sig_alt, ivp_alt)
        augmented.append(d_aug)

    print(f"  classified {len(augmented)} NORMAL × BULL days across 3 designs")

    # --- (a) Pass rate per design ---
    print()
    print("=" * 78)
    print("(a) PASS RATE — per design (NORMAL × BULL days, 26y)")
    print("=" * 78)
    pass_rows = []
    for design in designs:
        n_total = len(augmented)
        n_pass = sum(1 for r in augmented if r[f"{design}_pass"])
        # Pass by VIX bucket
        bucket_stats = []
        for lo, hi in [(13, 15), (15, 17), (17, 19), (19, 21), (21, 22)]:
            sub = [r for r in augmented if lo <= r["vix"] < hi]
            if not sub:
                continue
            sub_pass = sum(1 for r in sub if r[f"{design}_pass"])
            bucket_stats.append((f"[{lo},{hi})", len(sub), sub_pass, 100*sub_pass/len(sub)))
        print(f"\n{design}: total pass rate = {n_pass}/{n_total} = {100*n_pass/n_total:.1f}%")
        for bk, n, p, pct in bucket_stats:
            print(f"  VIX {bk:<8} n={n:>4} pass={p:>4} {pct:>5.1f}%")
        pass_rows.append({
            "design": design,
            "total_n": n_total,
            "total_pass": n_pass,
            "total_pct": round(100*n_pass/n_total, 1),
        })

    with open(PASS_OUT, "w", newline="") as f:
        if pass_rows:
            w = csv.DictWriter(f, fieldnames=list(pass_rows[0].keys()))
            w.writeheader()
            w.writerows(pass_rows)
    print(f"\nwrote {PASS_OUT}")

    # --- (b)+(c)+(d) Simulate BPS PnL on each design's allowed days ---
    print()
    print("=" * 78)
    print("(b/c/d) COUNTERFACTUAL BPS PnL — each design's allowed-open days")
    print("=" * 78)
    design_results = {}
    for design in designs:
        allowed = [r for r in augmented if r[f"{design}_pass"]]
        print(f"\n{design}: {len(allowed)} allowed-open days, simulating BPS...")
        trades = []
        for r in allowed:
            t = simulate_bps_trade(r["date"], spx, vix_hist)
            if t is not None:
                trades.append(t)
        design_results[design] = trades
        if not trades:
            print(f"  (no trades — empty)")
            continue
        pnls = [t["pnl_per_share"] for t in trades]
        rois = [t["roe_on_max_loss"] for t in trades]
        wins = sum(1 for t in trades if t["win"])
        worst = min(pnls)
        worst_5pct = sorted(pnls)[:max(1, len(pnls)//20)]
        avg_worst = mean(worst_5pct)
        sd = stdev(pnls) if len(pnls) > 1 else 0
        downside = math.sqrt(sum(min(p, 0)**2 for p in pnls) / len(pnls))
        sortino = mean(pnls) / downside if downside > 0 else float("inf")
        sharpe = mean(pnls) / sd if sd > 0 else float("inf")
        # Disaster threshold = worst trade ≤ -50% credit (proxy: pnl_per_share ≤ -25 = $-2500 per contract = roughly bad BPS)
        disaster = sum(1 for p in pnls if p <= -25)
        print(f"  n_trades:         {len(trades)}")
        print(f"  win_rate:         {100*wins/len(trades):>5.1f}%")
        print(f"  mean PnL/share:   {mean(pnls):>+7.2f}  (${mean(pnls)*100:>+6.0f}/contract)")
        print(f"  median:           {median(pnls):>+7.2f}")
        print(f"  std:              {sd:>7.2f}")
        print(f"  worst trade:      {worst:>+7.2f}  (${worst*100:>+6.0f})")
        print(f"  avg of worst 5%:  {avg_worst:>+7.2f}")
        print(f"  Sortino:          {sortino:>+6.3f}")
        print(f"  Sharpe:           {sharpe:>+6.3f}")
        print(f"  disaster (≤-25/share = ≤ -$2500/contract): {disaster}/{len(trades)} = {100*disaster/len(trades):.1f}%")

    # --- (d) Summary comparison table ---
    print()
    print("=" * 78)
    print("HEAD-TO-HEAD SUMMARY")
    print("=" * 78)
    print(f"{'metric':<30} {'IVP63':>15} {'IVP126':>15} {'IVP252 (curr)':>15}")
    print("-" * 80)
    summary_rows = []
    for metric, key, fmt in [
        ("# trades opened (26y)", "n", "d"),
        ("Pass rate (NORMAL × BULL)", "pass_rate", "%"),
        ("Win rate", "win_rate", "%"),
        ("Mean PnL/contract ($)", "mean_pnl", "money"),
        ("Median PnL/contract ($)", "median_pnl", "money"),
        ("Worst trade ($)", "worst", "money"),
        ("Disaster rate (≤-$2500)", "disaster_rate", "%"),
        ("Sortino", "sortino", "ratio"),
        ("Total cumulative PnL ($)", "cum_pnl", "money"),
    ]:
        line = f"{metric:<30}"
        for design in designs:
            trades = design_results[design]
            if not trades:
                line += " " * 16
                continue
            pnls = [t["pnl_per_share"] for t in trades]
            if key == "n":
                v = len(trades)
                s = f"{v:>15d}"
            elif key == "pass_rate":
                tot = next(p for p in pass_rows if p["design"] == design)
                s = f"{tot['total_pct']:>14.1f}%"
            elif key == "win_rate":
                v = sum(1 for t in trades if t["win"]) / len(trades) * 100
                s = f"{v:>14.1f}%"
            elif key == "mean_pnl":
                v = mean(pnls) * 100
                s = f"${v:>+12.0f}"
            elif key == "median_pnl":
                v = median(pnls) * 100
                s = f"${v:>+12.0f}"
            elif key == "worst":
                v = min(pnls) * 100
                s = f"${v:>+12.0f}"
            elif key == "disaster_rate":
                v = sum(1 for p in pnls if p <= -25) / len(pnls) * 100
                s = f"{v:>14.1f}%"
            elif key == "sortino":
                downside = math.sqrt(sum(min(p, 0)**2 for p in pnls) / len(pnls))
                v = mean(pnls) / downside if downside > 0 else 0
                s = f"{v:>+15.3f}"
            elif key == "cum_pnl":
                v = sum(pnls) * 100
                s = f"${v:>+12.0f}"
            line += s
        print(line)

    # Write per-design trade list
    with open(TRADES_OUT, "w", newline="") as f:
        rows = []
        for design in designs:
            for t in design_results[design]:
                rows.append({**t, "design": design})
        if rows:
            fieldnames = list(rows[0].keys())
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
    print(f"\nwrote {TRADES_OUT}")


if __name__ == "__main__":
    main()
