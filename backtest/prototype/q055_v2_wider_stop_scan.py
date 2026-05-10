"""
V2 Wider Stop Sensitivity — Find Alpha-Preserving + Tail-Capping Sweet Spot
============================================================================

V2c (STOP=8) failed bootstrap (0/20 seeds significant) because the stop
removed 58% of V2's PnL. This script tests wider stops to find a setting
that preserves alpha while still capping COVID-style tails.

Variants (true rolling weekly ladder, entry=49 DTE, exit@21 DTE):
  V2c  : STOP_MULT=8.0  (already tested — fails bootstrap)
  V2d  : STOP_MULT=10.0
  V2e  : STOP_MULT=12.0
  V2f  : STOP_MULT=15.0
  V2   : no stop  (already tested — 75% seed sig, -15.5% NLV worst cycle)

Pass criteria (must pass BOTH):
  Alpha:  Bootstrap seed sig rate ≥ 60% (block=250)
  Tail:   Worst trade ≥ -15% NLV (V1 veto from Q055)

If found → recommend that variant for SPEC.
If not   → fall back to option 1 (V2 raw with explicit caveat).
"""

import pickle
import sys
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

import warnings
warnings.filterwarnings('ignore')

# ─── Setup ────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[2]
_ES_FILE = _ROOT / "research" / "strategies" / "ES_puts" / "backtest.py"
import importlib.util
spec_es = importlib.util.spec_from_file_location("es_backtest_mod", _ES_FILE)
es_mod = importlib.util.module_from_spec(spec_es)
sys.modules["es_backtest_mod"] = es_mod
spec_es.loader.exec_module(es_mod)

WINDOW_START = "2000-01-01"
WINDOW_END   = "2026-04-17"
ACCOUNT      = 500_000.0
SPX_MULT     = 100
TARGET_DELTA = 0.20
PROFIT_FRAC  = 0.10
TRADING_DAYS = 252
RISK_FREE    = 0.045
GAMMA_DTE    = 5
WEEKLY_TD    = 5
YEARS = (pd.Timestamp(WINDOW_END) - pd.Timestamp(WINDOW_START)).days / 365.25

# ─── BS pricer + simulator (same as q041_es_v2_validation.py) ─────────────────
def bs_put_price(S, K, dte_td, sigma):
    T = dte_td / TRADING_DAYS
    if T <= 0 or sigma <= 0:
        return max(0.0, K - S)
    d1 = (np.log(S / K) + (RISK_FREE + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return K * np.exp(-RISK_FREE * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def bs_put_delta(S, K, dte_td, sigma):
    T = dte_td / TRADING_DAYS
    if T <= 0 or sigma <= 0:
        return -1.0 if K > S else 0.0
    d1 = (np.log(S / K) + (RISK_FREE + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1) - 1.0

def find_strike_for_delta(S, dte_td, sigma, target_delta):
    lo, hi = S * 0.5, S * 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        d = abs(bs_put_delta(S, mid, dte_td, sigma))
        if abs(d - target_delta) < 0.001:
            return round(mid)
        if d < target_delta:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2)

def run_true_ladder(sim_df, entry_dte_td, exit_at_dte_td, stop_mult,
                    entry_cadence_td=WEEKLY_TD, profit_frac=PROFIT_FRAC):
    positions = []
    trades = []
    days_since_entry = entry_cadence_td

    for i, (date, row) in enumerate(sim_df.iterrows()):
        spx = float(row["spx"]); vix = float(row["vix"])
        sigma = vix / 100.0
        dstr = date.strftime("%Y-%m-%d")

        still_open = []
        for pos in positions:
            pos['dte'] -= 1
            cur_val = bs_put_price(spx, pos['K'], max(pos['dte'], 0), sigma)
            reason = None
            if pos['dte'] <= GAMMA_DTE and exit_at_dte_td <= GAMMA_DTE:
                reason = "gamma_floor"
            elif pos['dte'] <= exit_at_dte_td:
                reason = "exit_dte"
            elif stop_mult is not None and cur_val >= pos['stop_prem']:
                reason = "stop_loss"
            elif cur_val <= pos['profit_prem']:
                reason = "profit_target"
            elif pos['dte'] <= 0:
                reason = "expiry"

            if reason:
                pnl = (pos['entry_prem'] - cur_val) * SPX_MULT
                trades.append({'entry_date': pos['entry_date'], 'exit_date': dstr,
                               'pnl_$': pnl, 'exit_reason': reason,
                               'year': pd.Timestamp(pos['entry_date']).year})
            else:
                still_open.append(pos)
        positions = still_open

        days_since_entry += 1
        if days_since_entry >= entry_cadence_td and i >= 64:
            K = find_strike_for_delta(spx, entry_dte_td, sigma, TARGET_DELTA)
            entry_prem = bs_put_price(spx, K, entry_dte_td, sigma)
            if entry_prem > 0.5:
                positions.append({'entry_date': dstr, 'dte': entry_dte_td, 'K': K,
                                  'entry_prem': entry_prem,
                                  'stop_prem': entry_prem * stop_mult if stop_mult else None,
                                  'profit_prem': entry_prem * profit_frac})
                days_since_entry = 0

    if positions:
        last_row = sim_df.iloc[-1]
        last_spx = float(last_row["spx"]); last_vix = float(last_row["vix"])
        last_sigma = last_vix / 100.0
        last_date = sim_df.index[-1].strftime("%Y-%m-%d")
        for pos in positions:
            cur_val = bs_put_price(last_spx, pos['K'], max(pos['dte'], 0), last_sigma)
            pnl = (pos['entry_prem'] - cur_val) * SPX_MULT
            trades.append({'entry_date': pos['entry_date'], 'exit_date': last_date,
                           'pnl_$': pnl, 'exit_reason': 'end_of_window',
                           'year': pd.Timestamp(pos['entry_date']).year})
    return pd.DataFrame(trades)

# ─── Bootstrap ────────────────────────────────────────────────────────────────
def bootstrap_ci_seeded(arr, block_size, seed=42, n_boot=2000, ci=0.95):
    arr = np.asarray(arr, dtype=float)
    n = len(arr)
    rng = np.random.default_rng(seed=seed)
    boot_means = np.empty(n_boot)
    max_start = max(1, n - block_size + 1)
    for idx in range(n_boot):
        n_blocks = math.ceil(n / block_size)
        starts = rng.integers(0, max_start, size=n_blocks)
        sample = np.concatenate([arr[s:s+block_size] for s in starts])[:n]
        boot_means[idx] = sample.mean()
    alpha = 1.0 - ci
    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return {'mean': float(arr.mean()), 'ci_lo': lo, 'ci_hi': hi,
            'significant': lo > 0}

def to_ann_roe(mean_per_trade, n):
    return (mean_per_trade * (n / YEARS)) / ACCOUNT * 100

def geom_ann_roe(total, account=ACCOUNT, years=YEARS):
    cum = total / account
    if cum <= -1:
        return float('nan')
    return ((1 + cum) ** (1/years) - 1) * 100

# ─── Load market data ─────────────────────────────────────────────────────────
print("Loading market data...")
data, _ = es_mod._load_data()
sim_df = data[(data.index >= pd.Timestamp(WINDOW_START)) & (data.index <= pd.Timestamp(WINDOW_END))]

# ─── Run new wider-stop variants ──────────────────────────────────────────────
print("\nRunning wider-stop variants...")
new_variants = {}
for stop_mult, label in [(10.0, "V2d_stop10"), (12.0, "V2e_stop12"), (15.0, "V2f_stop15")]:
    print(f"  {label} (STOP={stop_mult})...", end='', flush=True)
    df = run_true_ladder(sim_df, entry_dte_td=49, exit_at_dte_td=21, stop_mult=stop_mult)
    new_variants[label] = df
    print(f" n={len(df)}, total=${df['pnl_$'].sum():,.0f}, "
          f"worst=${df['pnl_$'].min():,.0f}")

# Load V2c and V2 from prior runs
with open('/tmp/q041_es_v2_validation.pkl', 'rb') as f:
    prior = pickle.load(f)
v2c_df = prior['b3_variants']['V2c_stop8']
new_variants['V2c_stop8'] = v2c_df

with open('/tmp/q041_es_true_ladder.pkl', 'rb') as f:
    ladder = pickle.load(f)
v2_df = ladder['variants']['V2_true_49_21_nostop']
new_variants['V2_no_stop'] = v2_df

# ─── For each variant: compute basic metrics + bootstrap (B2 seed stability) ──
print(f"\n{'='*88}")
print(f"  Wider-Stop Sensitivity Scan — Decision Matrix")
print(f"  Window: {WINDOW_START} → {WINDOW_END} ({YEARS:.1f} yr) | $500k account")
print(f"{'='*88}\n")

scan_order = ['V2c_stop8', 'V2d_stop10', 'V2e_stop12', 'V2f_stop15', 'V2_no_stop']
results = []

print(f"  {'Variant':<14}  {'STOP':>5}  {'n':>5}  {'Total $':>10}  {'AnnROE %':>9}  "
      f"{'Worst $':>10}  {'Worst%NLV':>9}  {'Sig rate':>9}  {'CI lo med':>10}  {'V1 pass':>7}  {'B2 pass':>7}")
print(f"  {'-'*14}  {'-'*5}  {'-'*5}  {'-'*10}  {'-'*9}  {'-'*10}  {'-'*9}  {'-'*9}  {'-'*10}  {'-'*7}  {'-'*7}")

for label in scan_order:
    df = new_variants[label]
    pnls = df['pnl_$'].values
    n = len(pnls)
    total = pnls.sum()
    ann = geom_ann_roe(total)
    worst = pnls.min()
    worst_pct = worst / ACCOUNT * 100
    stop_mult = {'V2c_stop8': 8.0, 'V2d_stop10': 10.0, 'V2e_stop12': 12.0,
                 'V2f_stop15': 15.0, 'V2_no_stop': None}[label]

    # B2: seed stability at block=250
    sig_count = 0
    ci_los = []
    for seed in range(1, 21):
        r = bootstrap_ci_seeded(pnls, block_size=250, seed=seed)
        if r['significant']:
            sig_count += 1
        ci_los.append(to_ann_roe(r['ci_lo'], n))
    sig_rate = sig_count / 20 * 100
    ci_lo_median = float(np.median(ci_los))

    v1_pass = worst_pct >= -15
    b2_pass_60 = sig_rate >= 60
    stop_str = f"{stop_mult:.0f}" if stop_mult else "none"
    print(f"  {label:<14}  {stop_str:>5}  {n:>5}  {total:>+10,.0f}  {ann:>+8.2f}%  "
          f"{worst:>+10,.0f}  {worst_pct:>+8.2f}%  {sig_rate:>7.0f}% / 20  "
          f"{ci_lo_median:>+9.2f}%  "
          f"{'✅' if v1_pass else '❌':>7}  {'✅' if b2_pass_60 else '❌':>7}")

    results.append({
        'variant': label, 'stop_mult': stop_mult, 'n': n,
        'total_$': round(total, 0), 'ann_roe_geom_%': round(ann, 2),
        'worst_$': round(worst, 0), 'worst_pct_nlv': round(worst_pct, 2),
        'sig_rate_%': sig_rate, 'ci_lo_median_ann_%': round(ci_lo_median, 3),
        'V1_pass_15pct': v1_pass, 'B2_pass_60': b2_pass_60,
        'overall_pass': v1_pass and b2_pass_60,
    })

results_df = pd.DataFrame(results)

# ─── B1: Block-size sweep on the most promising variant ──────────────────────
# Identify "best" candidate: passes V1 AND has highest sig_rate
candidates = results_df[results_df['V1_pass_15pct']].copy()
candidates = candidates.sort_values('sig_rate_%', ascending=False)
print(f"\n{'='*88}")
print(f"  Candidates passing V1 veto (worst ≥ -15% NLV), ranked by sig rate:")
print(f"{'='*88}")
print(candidates[['variant', 'stop_mult', 'ann_roe_geom_%', 'worst_pct_nlv',
                  'sig_rate_%', 'overall_pass']].to_string(index=False))

# B1 on top candidate
if len(candidates) > 0:
    top = candidates.iloc[0]
    top_label = top['variant']
    top_pnls = new_variants[top_label]['pnl_$'].values
    print(f"\n  B1 block-sweep on top V1-passer: {top_label}")
    print(f"  {'block_size':>10}  {'CI lo Ann%':>12}  {'CI hi Ann%':>12}  {'sig?':>5}")
    print(f"  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*5}")
    for bs in [50, 100, 200, 250, 500]:
        r = bootstrap_ci_seeded(top_pnls, block_size=bs, seed=42)
        n = len(top_pnls)
        ann_lo = to_ann_roe(r['ci_lo'], n)
        ann_hi = to_ann_roe(r['ci_hi'], n)
        sig = "✅" if r['significant'] else "❌"
        print(f"  {bs:>10}  {ann_lo:>+11.2f}%  {ann_hi:>+11.2f}%  {sig:>5}")

# ─── Recommendation ──────────────────────────────────────────────────────────
print(f"\n{'='*88}")
print(f"  RECOMMENDATION")
print(f"{'='*88}\n")

# Look for any variant passing both V1 and B2 (≥60% sig)
both_pass = results_df[results_df['overall_pass']]
v1_only = results_df[results_df['V1_pass_15pct'] & ~results_df['B2_pass_60']]

if len(both_pass) > 0:
    # Sweet spot found
    best = both_pass.sort_values('sig_rate_%', ascending=False).iloc[0]
    print(f"  ✅ SWEET SPOT FOUND: {best['variant']} (STOP_MULT={best['stop_mult']})")
    print(f"     Ann ROE: {best['ann_roe_geom_%']:+.2f}%")
    print(f"     Worst trade % NLV: {best['worst_pct_nlv']:+.2f}% (passes V1)")
    print(f"     Bootstrap sig rate: {best['sig_rate_%']:.0f}% (passes ≥60% threshold)")
    print(f"     CI lo median Ann ROE: {best['ci_lo_median_ann_%']:+.3f}%")
    print()
    print(f"  → Recommend writing SPEC for {best['variant']} as /ES P2 upgrade")
    if best['sig_rate_%'] >= 75:
        print(f"  → Borderline robust — minimal caveat needed")
    else:
        print(f"  → 60-75% range — write SPEC with explicit borderline-significance caveat")
    final = "OPTION 2 SUCCEEDED"
else:
    # No sweet spot — fall back to option 1
    print(f"  ❌ NO SWEET SPOT: all stop variants fail at least one criterion.")
    print(f"     Variants passing V1 (worst ≥ -15% NLV): "
          f"{candidates['variant'].tolist() if len(candidates) > 0 else 'none'}")
    print(f"     Variants passing B2 (sig rate ≥ 60%): "
          f"{results_df[results_df['B2_pass_60']]['variant'].tolist()}")
    print(f"     Intersection: empty")
    print()
    print(f"  → FALLBACK TO OPTION 1: SPEC V2 (no stop) with explicit caveats:")
    v2_row = results_df[results_df['variant'] == 'V2_no_stop'].iloc[0]
    print(f"     V2 Ann ROE: {v2_row['ann_roe_geom_%']:+.2f}%")
    print(f"     V2 Worst trade % NLV: {v2_row['worst_pct_nlv']:+.2f}% (FAILS V1 -15% threshold)")
    print(f"     V2 Bootstrap sig rate: {v2_row['sig_rate_%']:.0f}% (passes ≥60%)")
    print()
    print(f"  → Required SPEC caveats if going with V2 raw:")
    print(f"     - 2020-style sudden gap-down can produce -15.5% NLV single-cycle loss")
    print(f"     - Must include operational kill-switch (e.g., suspend new entries when VIX > 35)")
    print(f"     - Borderline bootstrap significance (75% seeds) — paper trade with monitoring")
    final = "OPTION 2 FAILED — FALLING BACK TO OPTION 1"

print(f"\n  Path: {final}")

# ─── Save ─────────────────────────────────────────────────────────────────────
out_path = '/tmp/q055_v2_wider_stop_scan.pkl'
with open(out_path, 'wb') as f:
    pickle.dump({
        'results_df': results_df,
        'variants': new_variants,
        'final_path': final,
    }, f)
print(f"\n  Saved: {out_path}")
