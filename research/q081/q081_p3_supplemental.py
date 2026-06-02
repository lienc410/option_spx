"""Q081 P3 supplemental — Window direction stratification + Sortino.

Triggered by G-review 2 Q1 CHALLENGE (2026-06-01): the aggregate
direction-bias check in P3 §C (mean QQQ window +0.32%) was insufficient.
Reviewer flagged that 21 trades come from LOW_VOL × BULLISH cell which
may systematically be up-biased windows; aggregate mean ≈ 0 doesn't
disprove that BCD's +8pp could be concentrated in up-windows (= leveraged
beta, not alpha).

This script answers:
  1. §F  — Stratify 21 windows by SPX same-window return into up/flat/down
           buckets. Compare BCD vs QQQ within each.
  2. §G  — Sortino ratio for BCD vs QQQ period returns (threshold = 0).
           Replaces the mean-vs-p05 point comparison in P3.

Reads: q081_p3_per_trade_comparison.csv
Writes: q081_p3_window_stratified.csv, q081_p3_sortino.csv
"""
from __future__ import annotations
import csv
import math
from pathlib import Path
from statistics import mean, median, stdev

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "research" / "q081" / "q081_p3_per_trade_comparison.csv"
STRAT_OUT = ROOT / "research" / "q081" / "q081_p3_window_stratified.csv"
SORT_OUT = ROOT / "research" / "q081" / "q081_p3_sortino.csv"


def load() -> list[dict]:
    rows = []
    with open(IN) as f:
        for r in csv.DictReader(f):
            rows.append({
                "entry":          r["entry"],
                "exit":           r["exit"],
                "hold_days":      int(r["hold_days"]),
                "bcd_period_roe": float(r["bcd_period_roe"]),
                "qqq_return":     float(r["qqq_return"]),
                "spx_return":     float(r["spx_return"]),
                "bcd_minus_qqq":  float(r["bcd_minus_qqq"]),
                "vix":            float(r["vix"]),
                "ivp":            float(r["ivp"]),
            })
    return rows


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


def stratify_by_spx_direction(rows: list[dict]) -> dict[str, list[dict]]:
    """Split into up / flat / down based on SPX same-window return.
    Thresholds: up > +1%, down < -1%, flat in between.
    """
    out = {"up": [], "flat": [], "down": []}
    for r in rows:
        if r["spx_return"] > 0.01:
            out["up"].append(r)
        elif r["spx_return"] < -0.01:
            out["down"].append(r)
        else:
            out["flat"].append(r)
    return out


def sortino(returns: list[float], threshold: float = 0.0) -> float:
    """Sortino ratio: (mean - threshold) / downside_deviation.

    downside_deviation = sqrt(E[min(r - threshold, 0)²])
    """
    if not returns:
        return float("nan")
    mu = mean(returns)
    downside_sq = [min(r - threshold, 0.0) ** 2 for r in returns]
    dd = math.sqrt(sum(downside_sq) / len(returns))
    if dd == 0:
        return float("inf") if mu > threshold else 0.0
    return (mu - threshold) / dd


def main() -> None:
    rows = load()
    print(f"Loaded {len(rows)} trades")

    # §F — Stratify by SPX same-window direction
    strata = stratify_by_spx_direction(rows)
    print()
    print("§F — Window-Direction Stratification (SPX same-window)")
    print("=" * 88)
    print(f"{'bucket':<10} {'n':>3} {'BCD mean':>10} {'QQQ mean':>10} "
          f"{'diff':>10} {'BCD med':>10} {'QQQ med':>10}")
    print("-" * 88)
    strat_rows = []
    for label in ["up", "flat", "down"]:
        s = strata[label]
        n = len(s)
        if n == 0:
            strat_rows.append({"bucket": label, "n": 0})
            print(f"{label:<10} {n:>3}  (empty)")
            continue
        bcd_vals = [r["bcd_period_roe"] for r in s]
        qqq_vals = [r["qqq_return"] for r in s]
        diff_vals = [r["bcd_minus_qqq"] for r in s]
        strat_rows.append({
            "bucket":       label,
            "n":            n,
            "bcd_mean":     round(mean(bcd_vals), 4),
            "bcd_median":   round(median(bcd_vals), 4),
            "bcd_min":      round(min(bcd_vals), 4),
            "bcd_max":      round(max(bcd_vals), 4),
            "qqq_mean":     round(mean(qqq_vals), 4),
            "qqq_median":   round(median(qqq_vals), 4),
            "qqq_min":      round(min(qqq_vals), 4),
            "qqq_max":      round(max(qqq_vals), 4),
            "diff_mean":    round(mean(diff_vals), 4),
            "diff_median":  round(median(diff_vals), 4),
            "bcd_wins":     sum(1 for d in diff_vals if d > 0),
        })
        print(f"{label:<10} {n:>3} {mean(bcd_vals):>+10.2%} {mean(qqq_vals):>+10.2%} "
              f"{mean(diff_vals):>+10.2%} {median(bcd_vals):>+10.2%} {median(qqq_vals):>+10.2%}")
        bcd_wins = sum(1 for d in diff_vals if d > 0)
        print(f"           BCD beats QQQ in {bcd_wins}/{n} = {100*bcd_wins/n:.0f}% of these windows")
        print(f"           BCD range [{min(bcd_vals):+.2%}, {max(bcd_vals):+.2%}]  "
              f"QQQ range [{min(qqq_vals):+.2%}, {max(qqq_vals):+.2%}]")

    # write strat CSV
    with open(STRAT_OUT, "w", newline="") as f:
        fieldnames = ["bucket", "n", "bcd_mean", "bcd_median", "bcd_min", "bcd_max",
                      "qqq_mean", "qqq_median", "qqq_min", "qqq_max",
                      "diff_mean", "diff_median", "bcd_wins"]
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(strat_rows)
    print(f"\nwrote {STRAT_OUT}")

    # §G — Sortino ratios
    print()
    print("§G — Sortino Ratio (threshold = 0)")
    print("=" * 88)
    bcd_all = [r["bcd_period_roe"] for r in rows]
    qqq_all = [r["qqq_return"] for r in rows]
    spx_all = [r["spx_return"] for r in rows]
    diff_all = [r["bcd_minus_qqq"] for r in rows]

    s_rows = []
    for label, vals in [
        ("BCD period-ROE",      bcd_all),
        ("QQQ same-window",     qqq_all),
        ("SPX same-window",     spx_all),
        ("BCD minus QQQ",       diff_all),
    ]:
        mu = mean(vals)
        sd = stdev(vals) if len(vals) > 1 else 0
        sortino_r = sortino(vals, 0)
        sharpe_r = mu / sd if sd > 0 else float("nan")
        s_rows.append({
            "metric":           label,
            "n":                len(vals),
            "mean":             round(mu, 4),
            "std":              round(sd, 4),
            "downside_std":     round(math.sqrt(sum(min(r, 0)**2 for r in vals)/len(vals)), 4),
            "sortino":          round(sortino_r, 3) if not math.isinf(sortino_r) else "inf",
            "sharpe":           round(sharpe_r, 3) if not math.isnan(sharpe_r) else "—",
        })
        print(f"{label:<22} n={len(vals):>3}  μ={mu:>+7.2%}  σ={sd:>6.2%}  "
              f"σ↓={math.sqrt(sum(min(r,0)**2 for r in vals)/len(vals)):>6.2%}  "
              f"Sortino={sortino_r:>+6.3f}  Sharpe={sharpe_r if not math.isnan(sharpe_r) else 0:>+6.3f}")

    with open(SORT_OUT, "w", newline="") as f:
        fieldnames = ["metric", "n", "mean", "std", "downside_std", "sortino", "sharpe"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(s_rows)
    print(f"\nwrote {SORT_OUT}")

    # §G addendum — Sortino within each stratum
    print()
    print("§G addendum — Sortino within each direction stratum (BCD vs QQQ)")
    print("-" * 88)
    for label in ["up", "flat", "down"]:
        s = strata[label]
        if len(s) < 2:
            continue
        bcd = [r["bcd_period_roe"] for r in s]
        qqq = [r["qqq_return"] for r in s]
        print(f"{label:<6} (n={len(s):>2})  "
              f"BCD Sortino={sortino(bcd,0):>+6.3f}  "
              f"QQQ Sortino={sortino(qqq,0):>+6.3f}")


if __name__ == "__main__":
    main()
