"""Q083 P5 — Robustness checks per G1 Q1/Q2/Q3 demands:

Q2 (cutpoint overfit, critical): split 26y in half — first define
  best-window from first half data, validate on second half independently.
  Also: IVP60/90/126/180/252 sensitivity grid — is the edge smooth across
  windows or cliffed at a single point?

Q1 (skew bracket, BPS-specific direction): BPS is net SHORT VEGA. Skew
  steepening in DOWN moves makes short put even richer (loss for BPS holder).
  So opposite direction from Q082 BCD CV1. Bracket-test: short put σ + Y vp
  in DOWN windows for IVP63 and IVP126 trades.

Q3 (narrow CI): block-bootstrap CI on aggregate Sortino and mean PnL for
  each design's trades.
"""
from __future__ import annotations
import csv
import math
import random
from pathlib import Path
from statistics import mean, stdev, median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q083_p1_counterfactual_bps import simulate_bps_trade, load_spx_history, load_vix_history, put_price

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
TRADES_IN = ROOT / "research" / "q083" / "q083_p4_d3_trades_compare.csv"
OUT_DIR = ROOT / "research" / "q083"

random.seed(2026)
BOOTSTRAP_N = 5000


def compute_ivp(vix_values, current_vix):
    if not vix_values:
        return 50.0
    return 100 * sum(1 for v in vix_values if v < current_vix) / len(vix_values)


def compute_ivr(vix_values, current_vix):
    if not vix_values:
        return 50.0
    lo, hi = min(vix_values), max(vix_values)
    return 100 * (current_vix - lo) / (hi - lo) if hi > lo else 50.0


def classify_iv_signal(ivr):
    if ivr > 50: return "HIGH"
    if ivr < 30: return "LOW"
    return "NEUTRAL"


def passes_gate(iv_signal, ivp):
    if iv_signal not in ("HIGH", "NEUTRAL"): return False
    if iv_signal == "NEUTRAL": return 43 <= ivp <= 55
    return 40 < ivp <= 70


def percentile(values, p):
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k); c = min(f+1, len(s)-1)
    if f == c: return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def sortino(values, threshold=0):
    if not values: return float("nan")
    mu = mean(values)
    dd = math.sqrt(sum(min(v-threshold, 0)**2 for v in values) / len(values))
    if dd == 0: return float("inf") if mu > threshold else 0
    return (mu - threshold) / dd


def block_bootstrap_metric(values, fn, block_size=4, n_boot=BOOTSTRAP_N):
    """Block bootstrap CI for arbitrary aggregate metric."""
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
        estimates.append(fn(sample))
    valid = [e for e in estimates if e is not None and not math.isnan(e) and not math.isinf(e)]
    if not valid:
        return None
    return {
        "point": fn(values),
        "ci_lo": percentile(valid, 2.5),
        "ci_hi": percentile(valid, 97.5),
        "median": percentile(valid, 50),
        "se": stdev(valid) if len(valid) > 1 else 0,
    }


def main():
    print("Loading signal + price history...")
    sig_rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            try:
                sig_rows.append({"date": r["date"], "vix": float(r["vix"]),
                                  "regime": r["regime"], "trend": r["trend"]})
            except (ValueError, TypeError):
                continue
    sig_rows.sort(key=lambda r: r["date"])
    spx = load_spx_history()
    vix_hist = load_vix_history()
    vix_by_date = {r["date"]: r["vix"] for r in sig_rows}
    dates_sorted = sorted(vix_by_date)
    date_to_idx = {d: i for i, d in enumerate(dates_sorted)}

    # =============== Q2: cutpoint overfit checks ===============

    # Q2a — IVP window sensitivity grid
    print()
    print("=" * 80)
    print("Q2a — IVP window SENSITIVITY (smooth vs cliff?)")
    print("=" * 80)
    windows = [40, 60, 63, 90, 126, 180, 252]
    sensitivity_rows = []
    for w in windows:
        passes_dates = []
        for r in sig_rows:
            idx = date_to_idx[r["date"]]
            if idx < 252: continue
            if r["regime"] != "NORMAL" or r["trend"] != "BULLISH": continue
            window_vix = [vix_by_date[dates_sorted[j]] for j in range(idx-w, idx)]
            ivp = compute_ivp(window_vix, r["vix"])
            ivr = compute_ivr(window_vix, r["vix"])
            iv_sig = classify_iv_signal(ivr)
            if passes_gate(iv_sig, ivp):
                passes_dates.append(r["date"])
        # Simulate
        trades = []
        for d in passes_dates:
            t = simulate_bps_trade(d, spx, vix_hist)
            if t is not None:
                trades.append(t)
        if trades:
            pnls = [t["pnl_per_share"] for t in trades]
            sort = sortino(pnls)
            mean_pnl_dollar = mean(pnls) * 100
            worst = min(pnls) * 100
            sensitivity_rows.append({
                "window": w, "n_pass": len(passes_dates), "n_trades": len(trades),
                "mean_pnl_usd": round(mean_pnl_dollar, 0),
                "worst_pnl_usd": round(worst, 0),
                "sortino": round(sort, 3),
            })

    print(f"{'window':>7} {'n_pass':>7} {'n_trades':>9} {'mean$':>9} {'worst$':>9} {'Sortino':>8}")
    for r in sensitivity_rows:
        print(f"  {r['window']:>5} {r['n_pass']:>7} {r['n_trades']:>9} "
              f"{r['mean_pnl_usd']:>+9.0f} {r['worst_pnl_usd']:>+9.0f} {r['sortino']:>+7.3f}")
    print("→ Smooth = honest; cliff at single window = cutpoint risk")

    with open(OUT_DIR / "q083_p5_q2_window_sensitivity.csv", "w", newline="") as f:
        if sensitivity_rows:
            w = csv.DictWriter(f, fieldnames=list(sensitivity_rows[0].keys()))
            w.writeheader()
            w.writerows(sensitivity_rows)
    print(f"wrote q083_p5_q2_window_sensitivity.csv")

    # Q2b — Split 26y in half: train (first half) → which window? → validate on second half
    print()
    print("=" * 80)
    print("Q2b — TIME SPLIT (train first half, validate second half)")
    print("=" * 80)
    n_rows = len(sig_rows)
    mid_idx = n_rows // 2
    mid_date = sig_rows[mid_idx]["date"]
    print(f"  Split point: {mid_date} (first half {sig_rows[0]['date']} → {mid_date}, second half → {sig_rows[-1]['date']})")

    for label, lo_idx, hi_idx in [("first half (train)", 252, mid_idx), ("second half (validate)", mid_idx, n_rows)]:
        print(f"\n  {label}:")
        for w in [63, 126, 252]:
            passes_dates = []
            for j in range(lo_idx, hi_idx):
                r = sig_rows[j]
                if r["regime"] != "NORMAL" or r["trend"] != "BULLISH": continue
                if j < w: continue
                win = [vix_by_date[dates_sorted[k]] for k in range(j-w, j)]
                ivp = compute_ivp(win, r["vix"])
                ivr = compute_ivr(win, r["vix"])
                iv_sig = classify_iv_signal(ivr)
                if passes_gate(iv_sig, ivp):
                    passes_dates.append(r["date"])
            trades = []
            for d in passes_dates:
                t = simulate_bps_trade(d, spx, vix_hist)
                if t is not None: trades.append(t)
            if trades:
                pnls = [t["pnl_per_share"] for t in trades]
                print(f"    IVP{w:>3}: n_pass={len(passes_dates):>3}, n_trades={len(trades):>3}, "
                      f"mean=${mean(pnls)*100:>+5.0f}, sortino={sortino(pnls):>+6.3f}")
            else:
                print(f"    IVP{w:>3}: n_pass=0, n_trades=0")

    # =============== Q3: block bootstrap CI on each design ===============
    print()
    print("=" * 80)
    print("Q3 — BLOCK BOOTSTRAP CI (block_size=4, n_boot=5000)")
    print("=" * 80)

    # Reload from P4 trades file
    trades_by_design = {}
    with open(TRADES_IN) as f:
        for r in csv.DictReader(f):
            trades_by_design.setdefault(r["design"], []).append({
                "pnl_per_share": float(r["pnl_per_share"])
            })
    for design, trades in trades_by_design.items():
        pnls = [t["pnl_per_share"] for t in trades]
        if not pnls:
            continue
        n = len(pnls)
        # Block bootstrap mean and sortino
        bs_mean = block_bootstrap_metric(pnls, mean, block_size=min(4, n//2 if n>1 else 1))
        bs_sort = block_bootstrap_metric(pnls, sortino, block_size=min(4, n//2 if n>1 else 1))
        if bs_mean and bs_sort:
            print(f"\n  {design}: n={n}")
            print(f"    Mean PnL/share: point={bs_mean['point']:>+6.2f}, "
                  f"95% CI [{bs_mean['ci_lo']:>+6.2f}, {bs_mean['ci_hi']:>+6.2f}], "
                  f"SE={bs_mean['se']:.3f}")
            print(f"    Sortino:        point={bs_sort['point']:>+6.3f}, "
                  f"95% CI [{bs_sort['ci_lo']:>+6.3f}, {bs_sort['ci_hi']:>+6.3f}], "
                  f"SE={bs_sort['se']:.3f}")

    # =============== Q1: skew bracket for BPS (SHORT vega, opposite Q082 BCD) ===============
    print()
    print("=" * 80)
    print("Q1 — SKEW BRACKET (BPS net SHORT vega; opposite Q082 BCD direction)")
    print("=" * 80)
    print("BPS in DOWN move + skew steepening: real short-put IV expands faster than long-put IV.")
    print("Short-put vega gain (loss for SHORT position) > long-put vega gain (small)")
    print("→ Real BPS loses MORE in down moves than BS-flat synth shows")
    print("→ Skew bracket should make IVP63/126 wide-regime results WORSE, not better")
    print()
    print("Re-simulate IVP63 trades with short-leg σ +5vp in DOWN exit:")
    # Load IVP63 trades
    ivp63_trades = []
    with open(TRADES_IN) as f:
        for r in csv.DictReader(f):
            if r["design"] == "IVP63":
                ivp63_trades.append(r)
    # Need to know which exited in DOWN: spx_exit < spx_entry
    adjusted_pnls = []
    base_pnls = []
    n_down = 0
    for t in ivp63_trades:
        es = float(t["entry_spx"])
        xs = float(t["exit_spx"])
        ev = float(t["entry_vix"])
        sk = float(t["short_strike"])
        lk = float(t["long_strike"])
        s_entry = float(t["short_entry_prem"])
        l_entry = float(t["long_entry_prem"])
        s_exit_orig = float(t["short_exit_prem"])
        l_exit_orig = float(t["long_exit_prem"])
        is_down = (xs - es) / es < -0.005
        base_pnls.append(float(t["pnl_per_share"]))
        if is_down:
            n_down += 1
            # Re-price short leg with σ+5vp
            sigma_bracket = (ev / 100.0) + 0.05
            s_exit_adj = put_price(xs, sk, 21, sigma_bracket)
            # PnL: credit_received (s_entry - l_entry) - cost_to_close
            credit = s_entry - l_entry
            cost_to_close_adj = s_exit_adj - l_exit_orig  # short leg only adjusted
            adjusted_pnls.append(credit - cost_to_close_adj)
        else:
            adjusted_pnls.append(float(t["pnl_per_share"]))
    print(f"  IVP63 trades: {len(base_pnls)} total, {n_down} in DOWN windows")
    print(f"  Baseline (BS-flat): mean ${mean(base_pnls)*100:>+6.0f}, Sortino {sortino(base_pnls):>+6.3f}")
    print(f"  Skew bracket:       mean ${mean(adjusted_pnls)*100:>+6.0f}, Sortino {sortino(adjusted_pnls):>+6.3f}")
    print(f"  Shift: mean ${(mean(adjusted_pnls)-mean(base_pnls))*100:>+5.0f}, "
          f"Sortino {sortino(adjusted_pnls)-sortino(base_pnls):>+5.3f}")
    print(f"  → if skew bracket hurts BPS materially, real edge < synth edge")


if __name__ == "__main__":
    main()
