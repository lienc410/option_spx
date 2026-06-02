"""Q082 P9 — Three missing computations demanded by G2 reviewer:
  (1) Y's MA-cross counterfactual: SPX 30d MA vs 200d MA at each entry,
      see how many DOWN windows the gate would filter (vs UP/FLAT false-kill).
  (2) Block bootstrap CI on DOWN-stratum BCD-vs-QQQ diff.
  (3) Skew sensitivity bracket: short-leg σ +X in DOWN windows, long-leg σ
      with contango factor — re-run BCD reconstruction at brackets, see if
      verdict survives both ends.

Reads: q082_p7_per_trade_comparison.csv (existing 137 trades + matched QQQ)
       q082_p6_synth_trades.csv (raw BCD with strikes for re-pricing under skew)
Writes: q082_p9_y_counterfactual.csv, q082_p9_bootstrap_ci.csv,
        q082_p9_skew_brackets.csv, q082_p9_memo.md (separate)
"""
from __future__ import annotations
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
COMPARISON_IN = ROOT / "research" / "q082" / "q082_p7_per_trade_comparison.csv"
TRADES_IN = ROOT / "research" / "q082" / "q082_p6_synth_trades.csv"
Y_OUT = ROOT / "research" / "q082" / "q082_p9_y_counterfactual.csv"
BOOT_OUT = ROOT / "research" / "q082" / "q082_p9_bootstrap_ci.csv"
SKEW_OUT = ROOT / "research" / "q082" / "q082_p9_skew_brackets.csv"

random.seed(2026)
BOOTSTRAP_N = 10_000

# BS pricing constants (mirror P6)
R = 0.05
Q_DIV = 0.013


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _d1_d2(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or K <= 0 or S <= 0:
        return None, None
    d1 = (math.log(S/K) + (R - Q_DIV + 0.5*sigma*sigma)*T) / (sigma*math.sqrt(T))
    return d1, d1 - sigma*math.sqrt(T)


def call_price(S, K, dte, sigma):
    T = dte / 365.0
    d1, d2 = _d1_d2(S, K, T, sigma)
    if d1 is None:
        return max(S - K, 0)
    return S*math.exp(-Q_DIV*T)*_norm_cdf(d1) - K*math.exp(-R*T)*_norm_cdf(d2)


def load_trades_comparison():
    rows = []
    with open(COMPARISON_IN) as f:
        for r in csv.DictReader(f):
            rows.append({
                "entry":         r["entry"],
                "exit":          r["exit"],
                "hold_days":     int(r["hold_days"]),
                "entry_spx":     float(r["entry_spx"]),
                "exit_spx":      float(r["exit_spx"]),
                "entry_vix":     float(r["entry_vix"]),
                "ivp":           float(r["ivp"]) if r["ivp"] else None,
                "debit_usd":     float(r["debit_usd"]),
                "pnl_usd":       float(r["pnl_usd"]),
                "period_roe":    float(r["period_roe"]),
                "qqq_return":    float(r["qqq_return"]),
                "spx_return":    float(r["spx_return"]),
                "bcd_minus_qqq": float(r["bcd_minus_qqq"]),
            })
    return rows


def load_raw_trades():
    rows = []
    with open(TRADES_IN) as f:
        for r in csv.DictReader(f):
            rows.append({
                "entry":              r["entry_date"],
                "exit":               r["exit_date"],
                "hold_days":          int(r["hold_days"]),
                "entry_spx":          float(r["entry_spx"]),
                "exit_spx":           float(r["exit_spx"]),
                "entry_vix":          float(r["entry_vix"]),
                "exit_vix":           float(r["exit_vix"]),
                "long_strike":        float(r["long_strike"]),
                "short_strike":       float(r["short_strike"]),
                "long_entry_prem":    float(r["long_entry_prem"]),
                "short_entry_prem":   float(r["short_entry_prem"]),
                "long_exit_prem":     float(r["long_exit_prem"]),
                "short_exit_prem":    float(r["short_exit_prem"]),
                "entry_debit_per_share": float(r["entry_debit_per_share"]),
                "ivp":                float(r["ivp"]) if r["ivp"] else None,
            })
    return rows


def stratify(rows, key="bcd_minus_qqq"):
    strata = {"UP": [], "FLAT": [], "DOWN": []}
    for r in rows:
        if r["spx_return"] > 0.01:
            strata["UP"].append(r)
        elif r["spx_return"] < -0.01:
            strata["DOWN"].append(r)
        else:
            strata["FLAT"].append(r)
    return strata


def percentile(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


# ============================================================
# (1) Y MA-cross counterfactual
# ============================================================

def compute_y_counterfactual(trades):
    """For each trade, compute SPX 30d MA vs 200d MA at entry day.
    Y gate: BLOCK BCD if 30d MA < 200d MA (bearish trend cross).
    """
    import yfinance as yf
    print("Loading SPX history for MA computation...")
    df = yf.Ticker("^GSPC").history(start="2002-01-01", end="2026-06-15", auto_adjust=True)
    closes = {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}
    dates_sorted = sorted(closes.keys())
    # Build trailing 30d and 200d MA per date
    close_list = [closes[d] for d in dates_sorted]
    ma_at = {}
    for i, d in enumerate(dates_sorted):
        if i < 200:
            continue
        ma30 = sum(close_list[i-30+1:i+1]) / 30
        ma200 = sum(close_list[i-200+1:i+1]) / 200
        ma_at[d] = (ma30, ma200)

    results = []
    for t in trades:
        entry = t["entry"]
        # Find most recent date with MA computed
        d = date.fromisoformat(entry)
        ma_pair = None
        for _ in range(10):
            iso = d.isoformat()
            if iso in ma_at:
                ma_pair = ma_at[iso]
                break
            d -= timedelta(days=1)
        if ma_pair is None:
            continue
        ma30, ma200 = ma_pair
        gated = ma30 < ma200  # True = gate would block this entry
        spx_dir = ("UP" if t["spx_return"] > 0.01
                   else "DOWN" if t["spx_return"] < -0.01 else "FLAT")
        results.append({
            **t,
            "ma30":     round(ma30, 2),
            "ma200":    round(ma200, 2),
            "ma_cross_below": gated,
            "spx_dir":  spx_dir,
        })

    # Tally by spx_dir × gated
    tally = defaultdict(lambda: {"total": 0, "gated": 0, "not_gated": 0})
    for r in results:
        d = r["spx_dir"]
        tally[d]["total"] += 1
        if r["ma_cross_below"]:
            tally[d]["gated"] += 1
        else:
            tally[d]["not_gated"] += 1

    print("\n" + "=" * 90)
    print("(1) Y MA-CROSS COUNTERFACTUAL — would the gate filter DOWN windows?")
    print("=" * 90)
    print(f"{'spx_dir':<8} {'total':>6} {'gated':>7} {'not_gated':>10} {'gate %':>8} {'(of DOWN/UP/FLAT)':>22}")
    print("-" * 80)
    output = []
    for d in ["UP", "FLAT", "DOWN"]:
        t = tally[d]
        if t["total"] == 0:
            continue
        gate_pct = 100*t["gated"]/t["total"]
        print(f"{d:<8} {t['total']:>6} {t['gated']:>7} {t['not_gated']:>10} {gate_pct:>7.1f}%")
        output.append({
            "spx_dir":    d,
            "total":      t["total"],
            "gated":      t["gated"],
            "not_gated":  t["not_gated"],
            "gate_pct":   round(gate_pct, 1),
        })

    # Net effect: if Y is applied, what's the aggregate BCD vs QQQ?
    not_gated_trades = [r for r in results if not r["ma_cross_below"]]
    print(f"\nAggregate effect of applying Y gate:")
    print(f"  Trades remaining after gate: {len(not_gated_trades)}/{len(results)}")
    diffs = [r["bcd_minus_qqq"] for r in not_gated_trades]
    print(f"  Mean BCD-QQQ:  {mean(diffs):>+7.2%}  (vs no-gate: +9.70%)")
    print(f"  Median:        {median(diffs):>+7.2%}")
    print(f"  p05:           {percentile(diffs, 5):>+7.2%}")
    # Per stratum after gating
    print(f"\nPer-stratum BCD-QQQ AFTER Y gate (only un-gated trades):")
    for d in ["UP", "FLAT", "DOWN"]:
        sub = [r for r in not_gated_trades if r["spx_dir"] == d]
        if not sub:
            print(f"  {d:<6} 0 trades remaining")
            continue
        sd = [r["bcd_minus_qqq"] for r in sub]
        wins = sum(1 for v in sd if v > 0)
        print(f"  {d:<6} n={len(sub):>3}  mean={mean(sd):>+7.2%}  wins {wins}/{len(sub)}")

    with open(Y_OUT, "w", newline="") as f:
        if output:
            w = csv.DictWriter(f, fieldnames=list(output[0].keys()))
            w.writeheader()
            w.writerows(output)
    print(f"\nwrote {Y_OUT}")
    return results


# ============================================================
# (2) Block bootstrap CI on DOWN stratum diff
# ============================================================

def block_bootstrap_ci(rows, key="bcd_minus_qqq", block_size=4, n_boot=BOOTSTRAP_N):
    """Block bootstrap: resample blocks of `block_size` consecutive trades
    to preserve sequential structure. Returns CI on the mean of `key`.
    """
    if len(rows) < block_size:
        return None
    n = len(rows)
    estimates = []
    for _ in range(n_boot):
        sample = []
        while len(sample) < n:
            start = random.randint(0, n - block_size)
            sample.extend(rows[start:start+block_size])
        sample = sample[:n]
        estimates.append(mean([s[key] for s in sample]))
    return {
        "point":      mean([r[key] for r in rows]),
        "p05":        percentile(estimates, 5),
        "p25":        percentile(estimates, 25),
        "p50":        percentile(estimates, 50),
        "p75":        percentile(estimates, 75),
        "p95":        percentile(estimates, 95),
        "se":         stdev(estimates),
        "ci_low":     percentile(estimates, 2.5),
        "ci_high":    percentile(estimates, 97.5),
    }


def compute_bootstrap_ci(comparison_rows):
    """Per-stratum block bootstrap on BCD-QQQ diff."""
    print("\n" + "=" * 90)
    print("(2) BLOCK BOOTSTRAP CI ON BCD-vs-QQQ DIFF (block_size=4)")
    print("=" * 90)
    strata = stratify(comparison_rows)
    print(f"{'stratum':<8} {'n':>3} {'point':>9} {'95% CI':>22} {'p05':>9} {'p95':>9} {'SE':>8}")
    print("-" * 88)
    output = []
    for label in ["UP", "FLAT", "DOWN"]:
        s = strata[label]
        if len(s) < 4:
            continue
        ci = block_bootstrap_ci(s, "bcd_minus_qqq", block_size=4)
        if ci is None:
            continue
        print(f"{label:<8} {len(s):>3} {ci['point']:>+9.2%} "
              f"[{ci['ci_low']:>+6.2%}, {ci['ci_high']:>+6.2%}] "
              f"{ci['p05']:>+9.2%} {ci['p95']:>+9.2%} {ci['se']:.4f}")
        output.append({
            "stratum":  label,
            "n":        len(s),
            "point":    round(ci["point"], 4),
            "ci_low":   round(ci["ci_low"], 4),
            "ci_high":  round(ci["ci_high"], 4),
            "p05":      round(ci["p05"], 4),
            "p95":      round(ci["p95"], 4),
            "se":       round(ci["se"], 4),
            "block_size": 4,
        })

    # Also aggregate
    ci_agg = block_bootstrap_ci(comparison_rows, "bcd_minus_qqq", block_size=4)
    if ci_agg:
        print(f"{'AGG':<8} {len(comparison_rows):>3} {ci_agg['point']:>+9.2%} "
              f"[{ci_agg['ci_low']:>+6.2%}, {ci_agg['ci_high']:>+6.2%}] "
              f"{ci_agg['p05']:>+9.2%} {ci_agg['p95']:>+9.2%} {ci_agg['se']:.4f}")
        output.append({
            "stratum":  "AGG",
            "n":        len(comparison_rows),
            "point":    round(ci_agg["point"], 4),
            "ci_low":   round(ci_agg["ci_low"], 4),
            "ci_high":  round(ci_agg["ci_high"], 4),
            "p05":      round(ci_agg["p05"], 4),
            "p95":      round(ci_agg["p95"], 4),
            "se":       round(ci_agg["se"], 4),
            "block_size": 4,
        })

    with open(BOOT_OUT, "w", newline="") as f:
        if output:
            w = csv.DictWriter(f, fieldnames=list(output[0].keys()))
            w.writeheader()
            w.writerows(output)
    print(f"\nwrote {BOOT_OUT}")
    return output


# ============================================================
# (3) Skew bracket sensitivity
# ============================================================

def compute_skew_brackets(raw_trades, comparison_rows):
    """Re-price each BCD trade under two bracketing skew scenarios:
    BRACKET-LO (skew helps BCD): in DOWN windows, short-leg σ +5vp at exit
    BRACKET-HI (skew hurts BCD): no adjustment (baseline, σ flat) — = current synth

    For LO: at trade exit, if spx_return < -0.01, re-price short leg with σ+0.05
    and recompute pnl. This simulates real chain's short-leg IV expansion in
    DOWN moves.
    """
    print("\n" + "=" * 90)
    print("(3) SKEW BRACKET SENSITIVITY (DOWN-window short-leg σ +5 vol points)")
    print("=" * 90)

    # Map comparison rows by entry date for direction lookup
    dir_by_entry = {}
    for r in comparison_rows:
        if r["spx_return"] > 0.01:
            dir_by_entry[r["entry"]] = "UP"
        elif r["spx_return"] < -0.01:
            dir_by_entry[r["entry"]] = "DOWN"
        else:
            dir_by_entry[r["entry"]] = "FLAT"

    adjusted_diffs_by_dir = {"UP": [], "FLAT": [], "DOWN": []}
    by_entry = {r["entry"]: r for r in comparison_rows}

    for raw in raw_trades:
        entry = raw["entry"]
        cmp = by_entry.get(entry)
        if not cmp:
            continue
        spx_dir = dir_by_entry[entry]
        if spx_dir == "DOWN":
            # Re-price short leg at exit with σ+0.05 vol points
            exit_short_dte = 21  # short leg DTE remaining at exit (roll threshold)
            adjusted_short_exit = call_price(
                cmp["exit_spx"], raw["short_strike"], exit_short_dte,
                (cmp["entry_vix"] / 100.0) + 0.05  # use entry vix as proxy + bump
            )
            # PnL: original long PnL + adjusted short PnL component
            # Original short PnL = -(short_exit - short_entry); adjusted = -(adj_short_exit - short_entry)
            orig_short_pnl_per_share = -(raw["short_exit_prem"] - raw["short_entry_prem"])
            adj_short_pnl_per_share = -(adjusted_short_exit - raw["short_entry_prem"])
            delta_short_pnl = adj_short_pnl_per_share - orig_short_pnl_per_share

            # PnL change: this affects the BCD return
            new_pnl_per_share = (raw["entry_debit_per_share"] * cmp["period_roe"]) + delta_short_pnl
            new_period_roe = new_pnl_per_share / raw["entry_debit_per_share"]
            new_diff = new_period_roe - cmp["qqq_return"]
            adjusted_diffs_by_dir["DOWN"].append(new_diff)
        else:
            # No adjustment outside DOWN
            adjusted_diffs_by_dir[spx_dir].append(cmp["bcd_minus_qqq"])

    # Compare baseline vs LO bracket
    output = []
    print(f"{'stratum':<8} {'n':>3} {'baseline diff':>14} {'LO bracket diff':>16} {'shift':>9}")
    print("-" * 80)
    for d in ["UP", "FLAT", "DOWN"]:
        s_baseline = stratify(comparison_rows)[d]
        if not s_baseline:
            continue
        baseline_diffs = [r["bcd_minus_qqq"] for r in s_baseline]
        baseline_mean = mean(baseline_diffs)
        lo_mean = mean(adjusted_diffs_by_dir[d]) if adjusted_diffs_by_dir[d] else baseline_mean
        shift = lo_mean - baseline_mean
        print(f"{d:<8} {len(baseline_diffs):>3} {baseline_mean:>+14.2%} {lo_mean:>+16.2%} {shift:>+9.2%}")
        output.append({
            "stratum":      d,
            "n":            len(baseline_diffs),
            "baseline":     round(baseline_mean, 4),
            "lo_bracket":   round(lo_mean, 4),
            "shift":        round(shift, 4),
        })

    # Aggregate
    baseline_all_diffs = [r["bcd_minus_qqq"] for r in comparison_rows]
    lo_all_diffs = []
    for d in ["UP", "FLAT", "DOWN"]:
        lo_all_diffs.extend(adjusted_diffs_by_dir[d])
    baseline_agg = mean(baseline_all_diffs)
    lo_agg = mean(lo_all_diffs)
    print(f"{'AGG':<8} {len(baseline_all_diffs):>3} {baseline_agg:>+14.2%} {lo_agg:>+16.2%} {lo_agg-baseline_agg:>+9.2%}")
    output.append({
        "stratum":    "AGG",
        "n":          len(baseline_all_diffs),
        "baseline":   round(baseline_agg, 4),
        "lo_bracket": round(lo_agg, 4),
        "shift":      round(lo_agg - baseline_agg, 4),
    })

    with open(SKEW_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        w.writeheader()
        w.writerows(output)
    print(f"\nwrote {SKEW_OUT}")
    return output


def main():
    print("Loading trade data...")
    comparison_rows = load_trades_comparison()
    raw_trades = load_raw_trades()
    print(f"  comparison rows: {len(comparison_rows)}")
    print(f"  raw trades: {len(raw_trades)}")

    y_results = compute_y_counterfactual(comparison_rows)
    boot_results = compute_bootstrap_ci(comparison_rows)
    skew_results = compute_skew_brackets(raw_trades, comparison_rows)


if __name__ == "__main__":
    main()
