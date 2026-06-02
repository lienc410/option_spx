"""Q082 P7 — Synthetic 26y BCD vs QQQ matched-window comparison + stratification.

Per Q081 §F method, applied to the 137 synthetic BCD trades from P6:
  For each trade compute QQQ same-window close-to-close return.
  Stratify by SPX same-window direction (UP/FLAT/DOWN).
  Compute per-stratum BCD vs QQQ diff.
  Compute aggregate + within-stratum Sortino.
  Compare to Q081 3y findings.
"""
from __future__ import annotations
import csv
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
TRADES_IN = ROOT / "research" / "q082" / "q082_p6_synth_trades.csv"
PER_TRADE_OUT = ROOT / "research" / "q082" / "q082_p7_per_trade_comparison.csv"
STRATIFIED_OUT = ROOT / "research" / "q082" / "q082_p7_stratified.csv"
SORTINO_OUT = ROOT / "research" / "q082" / "q082_p7_sortino.csv"


def load_qqq() -> dict[str, float]:
    import yfinance as yf
    df = yf.Ticker("QQQ").history(start="2003-01-01", end="2026-06-15", auto_adjust=True)
    return {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}


def load_spx_from_qqq_or_yfinance() -> dict[str, float]:
    import yfinance as yf
    df = yf.Ticker("^GSPC").history(start="2003-01-01", end="2026-06-15", auto_adjust=True)
    return {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}


def find_close(hist: dict[str, float], iso: str, max_skip: int = 5) -> tuple[str, float] | None:
    d = date.fromisoformat(iso)
    for _ in range(max_skip):
        s = d.isoformat()
        if s in hist:
            return s, hist[s]
        d -= timedelta(days=1)
    return None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def sortino(values: list[float], threshold: float = 0.0) -> float:
    if not values:
        return float("nan")
    mu = mean(values)
    dd = math.sqrt(sum(min(v - threshold, 0) ** 2 for v in values) / len(values))
    if dd == 0:
        return float("inf") if mu > threshold else 0.0
    return (mu - threshold) / dd


def main():
    print("Loading trades from P6...")
    trades = []
    with open(TRADES_IN) as f:
        for r in csv.DictReader(f):
            trades.append({
                "entry":        r["entry_date"],
                "exit":         r["exit_date"],
                "hold_days":    int(r["hold_days"]),
                "entry_spx":    float(r["entry_spx"]),
                "exit_spx":     float(r["exit_spx"]),
                "entry_vix":    float(r["entry_vix"]),
                "ivp":          float(r["ivp"]) if r["ivp"] else None,
                "iv_signal":    r["iv_signal"],
                "regime":       r["regime"],
                "trend":        r["trend"],
                "debit_usd":    float(r["entry_debit_usd"]),
                "pnl_usd":      float(r["pnl_usd"]),
                "period_roe":   float(r["period_roe"]),
            })
    print(f"  {len(trades)} synthetic BCD trades loaded")

    print("Loading QQQ + SPX history...")
    qqq = load_qqq()
    spx = load_spx_from_qqq_or_yfinance()
    print(f"  QQQ: {len(qqq)} rows, SPX: {len(spx)} rows")

    # Per-trade comparison
    enriched = []
    for t in trades:
        qe = find_close(qqq, t["entry"])
        qx = find_close(qqq, t["exit"])
        se = find_close(spx, t["entry"])
        sx = find_close(spx, t["exit"])
        if not all([qe, qx, se, sx]):
            continue
        qqq_ret = (qx[1] - qe[1]) / qe[1]
        spx_ret = (sx[1] - se[1]) / se[1]
        diff = t["period_roe"] - qqq_ret
        enriched.append({
            **t,
            "qqq_in":         round(qe[1], 2),
            "qqq_out":        round(qx[1], 2),
            "qqq_return":     round(qqq_ret, 4),
            "spx_in":         round(se[1], 2),
            "spx_out":        round(sx[1], 2),
            "spx_return":     round(spx_ret, 4),
            "bcd_minus_qqq":  round(diff, 4),
        })

    with open(PER_TRADE_OUT, "w", newline="") as f:
        fieldnames = list(enriched[0].keys())
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(enriched)
    print(f"\nwrote {PER_TRADE_OUT}")

    # Stratify by SPX same-window direction
    strata = {"UP": [], "FLAT": [], "DOWN": []}
    for r in enriched:
        if r["spx_return"] > 0.01:
            strata["UP"].append(r)
        elif r["spx_return"] < -0.01:
            strata["DOWN"].append(r)
        else:
            strata["FLAT"].append(r)

    print(f"\n{'=' * 90}")
    print("§F-ANALOG — Window-Direction Stratification (n=137 synthetic)")
    print(f"{'=' * 90}")
    print(f"{'stratum':<8} {'n':>4} {'BCD mean':>10} {'QQQ mean':>10} {'Diff':>10} "
          f"{'BCD med':>10} {'BCD wins':>12}")
    print("-" * 90)
    strat_rows = []
    for label in ["UP", "FLAT", "DOWN"]:
        s = strata[label]
        n = len(s)
        if n == 0:
            print(f"{label:<8} 0  (empty)")
            strat_rows.append({"stratum": label, "n": 0})
            continue
        bcd_vals = [r["period_roe"] for r in s]
        qqq_vals = [r["qqq_return"] for r in s]
        diff_vals = [r["bcd_minus_qqq"] for r in s]
        wins = sum(1 for d in diff_vals if d > 0)
        strat_rows.append({
            "stratum":      label,
            "n":            n,
            "bcd_mean":     round(mean(bcd_vals), 4),
            "bcd_median":   round(median(bcd_vals), 4),
            "bcd_min":      round(min(bcd_vals), 4),
            "bcd_max":      round(max(bcd_vals), 4),
            "qqq_mean":     round(mean(qqq_vals), 4),
            "qqq_median":   round(median(qqq_vals), 4),
            "diff_mean":    round(mean(diff_vals), 4),
            "diff_median":  round(median(diff_vals), 4),
            "bcd_wins":     wins,
            "win_rate":     round(100 * wins / n, 1),
        })
        print(f"{label:<8} {n:>4} {mean(bcd_vals):>+10.2%} {mean(qqq_vals):>+10.2%} "
              f"{mean(diff_vals):>+10.2%} {median(bcd_vals):>+10.2%} "
              f"{wins:>3}/{n:<3} = {100*wins/n:>4.1f}%")

    with open(STRATIFIED_OUT, "w", newline="") as f:
        fieldnames = ["stratum", "n", "bcd_mean", "bcd_median", "bcd_min", "bcd_max",
                      "qqq_mean", "qqq_median", "diff_mean", "diff_median",
                      "bcd_wins", "win_rate"]
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(strat_rows)

    # Sortino (aggregate + per stratum)
    print(f"\n{'=' * 90}")
    print("§G-ANALOG — Sortino Ratio (threshold=0)")
    print(f"{'=' * 90}")
    sortino_rows = []
    bcd_all = [r["period_roe"] for r in enriched]
    qqq_all = [r["qqq_return"] for r in enriched]
    diff_all = [r["bcd_minus_qqq"] for r in enriched]
    for label, vals in [("BCD period-ROE", bcd_all), ("QQQ same-window", qqq_all),
                          ("BCD minus QQQ", diff_all)]:
        mu = mean(vals)
        sd = stdev(vals)
        s = sortino(vals)
        sortino_rows.append({
            "metric":  label,
            "n":       len(vals),
            "mean":    round(mu, 4),
            "std":     round(sd, 4),
            "sortino": round(s, 3),
            "p05":     round(percentile(vals, 5), 4),
        })
        print(f"{label:<22} n={len(vals):>3}  μ={mu:>+7.2%}  σ={sd:>6.2%}  "
              f"Sortino={s:>+6.3f}  p05={percentile(vals,5):>+7.2%}")

    print(f"\nWithin-stratum Sortino (BCD vs QQQ in DOWN):")
    for label in ["UP", "FLAT", "DOWN"]:
        s = strata[label]
        if len(s) < 2:
            continue
        bcd = [r["period_roe"] for r in s]
        qqq = [r["qqq_return"] for r in s]
        print(f"  {label:<6} n={len(s):>3}  BCD Sortino={sortino(bcd):>+7.3f}  "
              f"QQQ Sortino={sortino(qqq):>+7.3f}")

    with open(SORTINO_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sortino_rows[0].keys()))
        w.writeheader()
        w.writerows(sortino_rows)
    print(f"\nwrote {SORTINO_OUT}")

    # Compare to Q081 3y
    print(f"\n{'=' * 90}")
    print("COMPARISON: Q082 26y synthetic vs Q081 3y backtest")
    print(f"{'=' * 90}")
    print(f"{'stratum':<8} {'Q082 n':>8} {'Q082 diff':>11} {'Q081 n':>8} {'Q081 diff':>11}")
    print("-" * 70)
    q081_data = {"UP": (10, "+19.38%"), "FLAT": (2, "+2.43%"), "DOWN": (9, "-3.38%")}
    for label in ["UP", "FLAT", "DOWN"]:
        s = strata[label]
        if not s:
            continue
        diff_val = mean(r["bcd_minus_qqq"] for r in s)
        q_n, q_diff = q081_data.get(label, (None, None))
        print(f"{label:<8} {len(s):>8} {diff_val:>+11.2%} {q_n:>8} {q_diff:>11}")

    # Verdict
    print(f"\n{'=' * 90}")
    print("VERDICT")
    print(f"{'=' * 90}")
    agg_diff = mean(diff_all)
    diff_sortino = sortino(diff_all)
    print(f"Aggregate BCD − QQQ across 26y: mean = {agg_diff:+.2%}, Sortino = {diff_sortino:+.3f}")
    if diff_sortino > 0.5 and agg_diff > 0.02:
        print("→ BCD ratify: aggregate edge persists at large n, decent Sortino")
    elif agg_diff < 0:
        print("→ BCD refute: 26y aggregate has BCD underperforming QQQ")
    else:
        print("→ Marginal: BCD edge ambiguous at 26y, leans positive but Sortino unclear")


if __name__ == "__main__":
    main()
