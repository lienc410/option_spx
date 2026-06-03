"""Q083 P13 — Four robustness gates per G-review demand:

Gate 1: skew bracket +3/+5/+8 vp short-leg σ in DOWN exits (per Q082 P7 method)
Gate 2: per-VIX-bucket sensitivity under each skew level (decide carve-out)
Gate 3: cash overlap at 10/year frequency (vs Q081's 6/year baseline)
Gate 4: block-bootstrap aggregate CI

Per memory feedback_post_withdrawal_proposals_front_load_robustness: these must
be done BEFORE ratify, not as commit-gate.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q082"))
from q082_p6_bcd_synth_reconstruction import (
    load_spx_history, load_vix_history,
    call_price, find_strike_for_delta,
    R, Q as Q_DIV, SHORT_DTE, LONG_DTE,
    SHORT_DELTA_TARGET, LONG_DELTA_TARGET, ROLL_AT_DTE
)
DAYS_PER_YEAR = 365

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
TRADES_IN = ROOT / "research" / "q083" / "q083_p11_bcd_normal_low_ivr_trades.csv"
OUT_DIR = ROOT / "research" / "q083"

random.seed(2026)
BOOTSTRAP_N = 5000


def simulate_bcd_with_skew(entry_iso, spx, vix, skew_short_bump=0.0):
    """Walk-forward BCD sim. skew_short_bump bumps short-leg σ at exit if
    cumulative SPX return < -1% (DOWN window)."""
    if entry_iso not in spx or entry_iso not in vix:
        return None
    S0 = spx[entry_iso]
    sigma0 = vix[entry_iso] / 100.0
    if sigma0 <= 0:
        return None

    long_K = find_strike_for_delta(S0, LONG_DTE, sigma0, LONG_DELTA_TARGET)
    short_K = find_strike_for_delta(S0, SHORT_DTE, sigma0, SHORT_DELTA_TARGET)
    long_K_r = round(long_K / 5) * 5
    short_K_r = round(short_K / 5) * 5

    long_entry = call_price(S0, long_K_r, LONG_DTE, sigma0)
    short_entry = call_price(S0, short_K_r, SHORT_DTE, sigma0)
    entry_debit = long_entry - short_entry
    if entry_debit <= 0:
        return None

    entry_dt = date.fromisoformat(entry_iso)
    cur_S = S0
    cur_sigma = sigma0
    short_dte = SHORT_DTE
    long_dte = LONG_DTE

    for delta_days in range(1, 50):
        cur_dt = entry_dt + timedelta(days=delta_days)
        cur_iso = cur_dt.isoformat()
        if cur_iso in spx:
            cur_S = spx[cur_iso]
        if cur_iso in vix:
            cur_sigma = vix[cur_iso] / 100.0
        short_dte = max(0, SHORT_DTE - delta_days)
        long_dte = max(0, LONG_DTE - delta_days)

        if short_dte <= ROLL_AT_DTE and cur_iso in spx:
            # Determine DOWN move for skew application
            spx_return = (cur_S - S0) / S0
            is_down = spx_return < -0.01
            short_sigma_eff = cur_sigma + (skew_short_bump if is_down else 0.0)

            exit_long = call_price(cur_S, long_K_r, long_dte, cur_sigma)
            exit_short = call_price(cur_S, short_K_r, short_dte, short_sigma_eff)
            pnl_per_share = (exit_long - long_entry) - (exit_short - short_entry)
            return {
                "entry": entry_iso, "exit": cur_dt.isoformat(),
                "hold_days": delta_days,
                "entry_spx": S0, "exit_spx": cur_S,
                "entry_vix": sigma0 * 100, "exit_vix": cur_sigma * 100,
                "is_down": is_down,
                "pnl_per_share": pnl_per_share,
                "pnl_usd": pnl_per_share * 100,
                "entry_debit_per_share": entry_debit,
                "period_roe": pnl_per_share / entry_debit,
            }
    return None


def percentile(values, p):
    if not values: return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k); c = min(f+1, len(s)-1)
    if f == c: return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def sortino(values, threshold=0):
    if not values: return float("nan")
    mu = mean(values)
    dd = math.sqrt(sum(min(v - threshold, 0)**2 for v in values) / len(values))
    if dd == 0: return float("inf") if mu > threshold else 0
    return (mu - threshold) / dd


def block_bootstrap(values, fn, block_size=4, n_boot=BOOTSTRAP_N):
    n = len(values)
    if n < block_size:
        return None
    estimates = []
    for _ in range(n_boot):
        sample = []
        while len(sample) < n:
            start = random.randint(0, n - block_size)
            sample.extend(values[start:start+block_size])
        sample = sample[:n]
        try:
            estimates.append(fn(sample))
        except Exception:
            pass
    valid = [e for e in estimates if e is not None and not math.isnan(e) and not math.isinf(e)]
    if not valid: return None
    return {
        "point": fn(values),
        "ci_lo": percentile(valid, 2.5),
        "ci_hi": percentile(valid, 97.5),
        "se": stdev(valid) if len(valid) > 1 else 0,
    }


def main():
    print("Loading data...")
    sig_rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            try:
                sig_rows.append({
                    "date": r["date"],
                    "vix": float(r["vix"]),
                    "regime": r["regime"],
                    "trend": r["trend"],
                    "iv_signal": r["iv_signal"],
                })
            except (ValueError, TypeError):
                continue
    sig_rows.sort(key=lambda r: r["date"])
    spx = load_spx_history()
    vix = load_vix_history()

    # =========================================================
    # GATE 1+2: Skew bracket on 82 NORMAL × IV_LOW BCD trades
    # =========================================================
    print("\n" + "=" * 78)
    print("GATE 1: SKEW BRACKET (+0/+3/+5/+8 vp short-leg σ in DOWN exits)")
    print("=" * 78)
    target_days = [r for r in sig_rows if r["regime"] == "NORMAL"
                   and r["trend"] == "BULLISH" and r["iv_signal"] == "LOW"]

    bracket_results = {}
    for bump in (0.0, 0.03, 0.05, 0.08):
        trades = []
        last_exit = None
        for r in target_days:
            entry = r["date"]
            if last_exit and entry <= last_exit:
                continue
            t = simulate_bcd_with_skew(entry, spx, vix, skew_short_bump=bump)
            if t is None: continue
            t["entry_vix_bucket"] = r["vix"]
            trades.append(t)
            last_exit = t["exit"]
        pnls = [t["pnl_per_share"] for t in trades]
        if not pnls: continue
        wins = sum(1 for p in pnls if p > 0)
        sort = sortino(pnls)
        bracket_results[bump] = {
            "trades": trades,
            "n": len(trades),
            "mean_usd": mean(pnls) * 100,
            "median_usd": median(pnls) * 100,
            "worst_usd": min(pnls) * 100,
            "win_rate": wins / len(trades),
            "sortino": sort,
        }
        bump_label = f"+{int(bump*100)}vp" if bump > 0 else "baseline"
        print(f"\n{bump_label:>10}: n={len(trades)} mean=${mean(pnls)*100:>+7,.0f} "
              f"median=${median(pnls)*100:>+7,.0f} worst=${min(pnls)*100:>+6,.0f} "
              f"win={100*wins/len(trades):.1f}% Sortino={sort:+.3f}")

    # Baseline comparison
    baseline_q082 = 1016  # Q082 LOW_VOL × BULL mean PnL
    print(f"\n  vs Q082 LOW_VOL × BULL baseline mean = ${baseline_q082}/contract")
    print(f"  Beat baseline? ", end="")
    for bump in (0.0, 0.03, 0.05, 0.08):
        if bump in bracket_results:
            wins = "✓" if bracket_results[bump]["mean_usd"] > baseline_q082 else "✗"
            print(f"{int(bump*100)}vp={wins}", end=" ")
    print()

    # =========================================================
    # GATE 2: per-VIX-bucket × skew level (carve-out decision)
    # =========================================================
    print("\n" + "=" * 78)
    print("GATE 2: VIX BUCKET × SKEW LEVEL (carve-out decision)")
    print("=" * 78)

    vix_buckets = [(15, 16), (16, 17), (17, 18), (18, 19), (19, 20), (20, 21), (21, 22)]
    print(f"{'VIX':>10} | {'baseline':>10} {'+3vp':>10} {'+5vp':>10} {'+8vp':>10} | {'n':>4}")
    print("-" * 80)
    bucket_results = {}
    for lo, hi in vix_buckets:
        row = {}
        n_bucket = None
        for bump in (0.0, 0.03, 0.05, 0.08):
            if bump not in bracket_results:
                continue
            sub = [t for t in bracket_results[bump]["trades"] if lo <= t["entry_vix_bucket"] < hi]
            if not sub:
                row[bump] = None
                continue
            n_bucket = len(sub)
            row[bump] = mean(t["pnl_per_share"] for t in sub) * 100
        if n_bucket is None: continue
        bucket_results[(lo, hi)] = row
        print(f"[{lo:>3},{hi:>3})  | "
              f"${row.get(0.0, 0):>+8.0f}   "
              f"${row.get(0.03, 0):>+8.0f}   "
              f"${row.get(0.05, 0):>+8.0f}   "
              f"${row.get(0.08, 0):>+8.0f}   | "
              f"{n_bucket:>4}")

    # Identify which buckets turn negative under +8vp
    print("\nUnder +8vp pessimistic skew:")
    for (lo, hi), row in bucket_results.items():
        v8 = row.get(0.08)
        if v8 is None: continue
        if v8 < 0:
            print(f"  VIX [{lo},{hi}): ${v8:>+6.0f} **NEGATIVE** → carve-out candidate")
        elif v8 < 500:
            print(f"  VIX [{lo},{hi}): ${v8:>+6.0f} weak (< $500)")
        else:
            print(f"  VIX [{lo},{hi}): ${v8:>+6.0f} OK")

    # Aggregate excluding weak buckets
    print("\n--- Carve-out scenarios ---")
    for carve_vix_max in (None, 18, 19, 20):
        for bump in (0.0, 0.08):
            sub = [t for t in bracket_results[bump]["trades"]
                   if carve_vix_max is None or t["entry_vix_bucket"] < carve_vix_max]
            if not sub: continue
            pnls = [t["pnl_per_share"] for t in sub]
            label = f"VIX 15-{carve_vix_max if carve_vix_max else 22}"
            bump_label = "BS-flat" if bump == 0 else f"+{int(bump*100)}vp"
            print(f"  {label:<10} {bump_label:>8}: n={len(sub)} "
                  f"mean=${mean(pnls)*100:>+5.0f} Sortino={sortino(pnls):+.3f}")

    # =========================================================
    # GATE 3: Cash overlap at expanded frequency (LOW_VOL + NORMAL × IV_LOW)
    # =========================================================
    print("\n" + "=" * 78)
    print("GATE 3: CASH OVERLAP (combined cell-eligible days, sequential ladder)")
    print("=" * 78)

    # Combined BCD-eligible: existing LOW_VOL × BULL × any IVR + new NORMAL × IV_LOW × BULL
    combined_eligible = [r["date"] for r in sig_rows
                         if (r["regime"] == "LOW_VOL" and r["trend"] == "BULLISH")
                         or (r["regime"] == "NORMAL" and r["trend"] == "BULLISH"
                             and r["iv_signal"] == "LOW")]
    combined_eligible.sort()
    print(f"Combined BCD-eligible days (LOW_VOL × BULL + NORMAL × IV_LOW × BULL): {len(combined_eligible)}")

    # Simulate sequential ladder over combined universe + count overlaps
    trades_combined = []
    last_exit = None
    overlap_events = 0
    pending_eligible_days = []  # signals that came in while previous trade was open
    for d in combined_eligible:
        if last_exit and d <= last_exit:
            overlap_events += 1
            pending_eligible_days.append((d, last_exit))
            continue
        t = simulate_bcd_with_skew(d, spx, vix, skew_short_bump=0.0)
        if t is None:
            continue
        trades_combined.append(t)
        last_exit = t["exit"]

    print(f"Sequential ladder trades: {len(trades_combined)}")
    n_years = (date.fromisoformat(combined_eligible[-1]) -
               date.fromisoformat(combined_eligible[0])).days / 365.25
    print(f"  Frequency: {len(trades_combined)/n_years:.1f}/year over {n_years:.1f} years")
    print(f"  Signal overlap events (signal fired while prior open): {overlap_events}")
    print(f"  Overlap rate: {100*overlap_events/len(combined_eligible):.1f}% of eligible days")

    print(f"\n  Q081 baseline (LOW_VOL only): ~6/year")
    print(f"  Combined frequency: ~{len(trades_combined)/n_years:.1f}/year")
    print(f"  Frequency increase: {100*(len(trades_combined)/n_years - 6)/6:.0f}%")

    # If overlap is non-trivial, show typical overlap duration
    if overlap_events > 0:
        durations_days = []
        for sig_date, prior_exit in pending_eligible_days[:20]:
            d1 = date.fromisoformat(sig_date)
            d2 = date.fromisoformat(prior_exit)
            durations_days.append((d2 - d1).days)
        if durations_days:
            print(f"\n  Sample 20 overlap durations (days prior trade still open after new signal):")
            print(f"    median: {median(durations_days)}, max: {max(durations_days)}")

    # =========================================================
    # GATE 4: Block-bootstrap CI on aggregate PnL + Sortino
    # =========================================================
    print("\n" + "=" * 78)
    print("GATE 4: BLOCK-BOOTSTRAP CI (block_size=4, n_boot=5000)")
    print("=" * 78)

    # Use the 82 baseline NORMAL × IV_LOW × BULL BCD trades
    trades_b = bracket_results[0.0]["trades"]
    pnls_b = [t["pnl_per_share"] for t in trades_b]
    pnls_usd = [p * 100 for p in pnls_b]

    print(f"\nNORMAL × IV_LOW × BULL (baseline, n={len(pnls_usd)}):")
    bs_mean = block_bootstrap(pnls_usd, mean, block_size=4)
    bs_sort = block_bootstrap(pnls_b, sortino, block_size=4)
    if bs_mean:
        print(f"  Mean PnL/contract: point=${bs_mean['point']:>+5,.0f}, "
              f"95% CI [${bs_mean['ci_lo']:>+5,.0f}, ${bs_mean['ci_hi']:>+5,.0f}], "
              f"SE=${bs_mean['se']:,.0f}")
    if bs_sort:
        print(f"  Sortino:           point={bs_sort['point']:+.3f}, "
              f"95% CI [{bs_sort['ci_lo']:+.3f}, {bs_sort['ci_hi']:+.3f}], "
              f"SE={bs_sort['se']:.3f}")

    # Also CI for +5vp scenario (middle pessimistic)
    if 0.05 in bracket_results:
        trades_5 = bracket_results[0.05]["trades"]
        pnls_5 = [t["pnl_per_share"] * 100 for t in trades_5]
        bs_mean_5 = block_bootstrap(pnls_5, mean, block_size=4)
        if bs_mean_5:
            print(f"\nUnder +5vp skew (mid-pessimistic):")
            print(f"  Mean PnL/contract: point=${bs_mean_5['point']:>+5,.0f}, "
                  f"95% CI [${bs_mean_5['ci_lo']:>+5,.0f}, ${bs_mean_5['ci_hi']:>+5,.0f}]")
            print(f"  vs Q082 baseline $1,016: CI {'INCLUDES' if bs_mean_5['ci_lo'] <= 1016 <= bs_mean_5['ci_hi'] else 'EXCLUDES'} baseline")


if __name__ == "__main__":
    main()
