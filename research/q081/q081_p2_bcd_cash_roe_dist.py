"""Q081 P2 — Per-trade BCD cash-ROE distribution with left-tail focus.

Per PM ratification: comparison of debit-strategy vs beta benchmark must
use left-tail percentiles (p05/p01), not mean differences, not the
0.5pp threshold used for cross-strategy ROE noise.

Method:
1. Per BCD trade: cash_roe = pnl / debit, annualized = cash_roe × 365 / hold_days
2. Report full distribution stats: mean, median, p25, **p05**, **p01**, min,
   max, std.
3. Bootstrap CI for p05 (n=21 → resample with replacement 10k times,
   compute p05 of each resample, return 5-95% CI of p05 estimates).
4. Sub-bucket by IVP tertile and VIX tertile to see regime sensitivity
   (sub-bucket n very small — report with explicit caveat for G-review).

Output:
- q081_p2_bcd_cash_roe.csv — per-trade ROE table
- q081_p2_bcd_roe_distribution.csv — distribution stats overall + by bucket
- q081_p2_memo.md (separate file)
"""
from __future__ import annotations
import csv
import random
from datetime import date
from pathlib import Path
from statistics import mean, median, stdev

ROOT = Path(__file__).resolve().parents[2]
TRADES = ROOT / "data" / "backtest_trades_3y_2026-04-29.csv"
ROE_OUT = ROOT / "research" / "q081" / "q081_p2_bcd_cash_roe.csv"
DIST_OUT = ROOT / "research" / "q081" / "q081_p2_bcd_roe_distribution.csv"

BOOTSTRAP_N = 10_000
random.seed(2026)


def percentile(values: list[float], p: float) -> float:
    """Linear interpolation percentile, p in [0, 100]."""
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def load_bcd_trades() -> list[dict]:
    out = []
    with open(TRADES) as f:
        for r in csv.DictReader(f):
            if r["strategy_key"] != "bull_call_diagonal":
                continue
            debit = float(r["option_premium_enter_usd"])
            pnl = float(r["exit_pnl_usd"])
            hold = float(r["hold_days_calendar"])
            if debit <= 0 or hold <= 0:
                continue
            cash_roe_period = pnl / debit
            cash_roe_annualized = cash_roe_period * 365 / hold
            out.append({
                "entry":               date.fromisoformat(r["entry_date"]),
                "exit":                date.fromisoformat(r["exit_date"]),
                "debit":               debit,
                "pnl":                 pnl,
                "hold_days":           hold,
                "vix":                 float(r["entry_vix"]),
                "ivp":                 float(r["ivp"]),
                "iv_signal":           r["iv_signal"],
                "regime":              r["regime"],
                "trend":               r["trend"],
                "cash_roe_period":     cash_roe_period,
                "cash_roe_annualized": cash_roe_annualized,
            })
    return sorted(out, key=lambda t: t["entry"])


def distribution_stats(values: list[float], label: str, n_bootstrap: int = BOOTSTRAP_N) -> dict:
    n = len(values)
    if n == 0:
        return {"label": label, "n": 0}
    row = {
        "label":  label,
        "n":      n,
        "mean":   round(mean(values), 4),
        "median": round(median(values), 4),
        "std":    round(stdev(values), 4) if n > 1 else None,
        "min":    round(min(values), 4),
        "max":    round(max(values), 4),
        "p01":    round(percentile(values, 1), 4),
        "p05":    round(percentile(values, 5), 4),
        "p25":    round(percentile(values, 25), 4),
        "p75":    round(percentile(values, 75), 4),
    }
    if n >= 5:
        # Bootstrap CI for p05
        p05_estimates = []
        for _ in range(n_bootstrap):
            sample = [random.choice(values) for _ in range(n)]
            p05_estimates.append(percentile(sample, 5))
        row["p05_boot_lo"] = round(percentile(p05_estimates, 5), 4)
        row["p05_boot_hi"] = round(percentile(p05_estimates, 95), 4)
        row["p05_boot_se"] = round(stdev(p05_estimates), 4)
    return row


def main() -> None:
    trades = load_bcd_trades()
    print(f"BCD trades loaded: {len(trades)}")

    # Per-trade ROE table
    with open(ROE_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "entry", "exit", "hold_days", "vix", "ivp", "iv_signal",
            "regime", "trend", "debit", "pnl",
            "cash_roe_period", "cash_roe_annualized",
        ])
        w.writeheader()
        for t in trades:
            w.writerow({
                "entry":               t["entry"].isoformat(),
                "exit":                t["exit"].isoformat(),
                "hold_days":           int(t["hold_days"]),
                "vix":                 round(t["vix"], 2),
                "ivp":                 round(t["ivp"], 2),
                "iv_signal":           t["iv_signal"],
                "regime":              t["regime"],
                "trend":               t["trend"],
                "debit":               round(t["debit"], 2),
                "pnl":                 round(t["pnl"], 2),
                "cash_roe_period":     round(t["cash_roe_period"], 4),
                "cash_roe_annualized": round(t["cash_roe_annualized"], 4),
            })
    print(f"wrote {ROE_OUT}")

    annualized = [t["cash_roe_annualized"] for t in trades]
    period = [t["cash_roe_period"] for t in trades]

    rows: list[dict] = []
    rows.append(distribution_stats(annualized, "all (annualized)"))
    rows.append(distribution_stats(period, "all (period)"))

    # NOTE on annualization: short-hold losses (worst trade closed in 3 days)
    # annualize to ~-1600%, polluting mean and tail estimates. Use PERIOD
    # ROE for left-tail comparisons. Annualized is only meaningful when
    # paired with matched-period QQQ (done in P3).

    # IVP sub-buckets: LOW (<33), MID (33-67), HIGH (>67) — use PERIOD ROE
    for label, fn in [
        ("ivp_LOW (<33) period",   lambda t: t["ivp"] < 33),
        ("ivp_MID (33-67) period", lambda t: 33 <= t["ivp"] < 67),
        ("ivp_HIGH (>=67) period", lambda t: t["ivp"] >= 67),
    ]:
        sub = [t["cash_roe_period"] for t in trades if fn(t)]
        rows.append(distribution_stats(sub, label))

    # VIX sub-buckets: 12-13, 13-14, 14-15 — use PERIOD ROE
    for lo, hi in [(12, 13), (13, 14), (14, 15.5)]:
        label = f"vix_[{lo},{hi}) period"
        sub = [t["cash_roe_period"] for t in trades if lo <= t["vix"] < hi]
        rows.append(distribution_stats(sub, label))

    # Worst trade in absolute $: report (already in P1 memo as -$3,248)

    with open(DIST_OUT, "w", newline="") as f:
        fieldnames = ["label", "n", "mean", "median", "std", "min", "max",
                      "p01", "p05", "p25", "p75",
                      "p05_boot_lo", "p05_boot_hi", "p05_boot_se"]
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {DIST_OUT}")

    # Pretty print summary
    print(f"\n{'=' * 76}")
    print("BCD cash-ROE distribution (annualized = pnl/debit × 365/hold_days)")
    print(f"{'=' * 76}")
    print(f"{'bucket':<28} {'n':>3} {'mean':>9} {'med':>9} {'p05':>9} {'p01':>9} {'min':>9}")
    print("-" * 76)
    for r in rows:
        if r["n"] == 0:
            print(f"{r['label']:<28} {r['n']:>3} (empty)")
            continue
        p05 = r.get("p05", "—")
        p01 = r.get("p01", "—")
        boot_se = r.get("p05_boot_se", "—")
        print(f"{r['label']:<28} {r['n']:>3} {r['mean']:>+9.2%} {r['median']:>+9.2%} "
              f"{r['p05']:>+9.2%} {r['p01']:>+9.2%} {r['min']:>+9.2%}")
        if boot_se != "—" and boot_se is not None:
            print(f"  └ p05 95% CI: [{r['p05_boot_lo']:>+8.2%}, {r['p05_boot_hi']:>+8.2%}]  (boot SE {boot_se:.4f})")


if __name__ == "__main__":
    main()
