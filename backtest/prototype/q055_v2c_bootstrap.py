"""
V2c Bootstrap Validation
========================

Independent bootstrap significance test on V2c (true rolling weekly ladder,
entry=49 DTE, exit@21, STOP_MULT=8.0). Mirrors the V2 protocol from
q041_es_v2_validation.py so results are directly comparable.

V2 results (reference):
  - 75% seed significance at block=250
  - CI lo median +0.06% Ann ROE
  - B1 smooth transition starting at block=200

V2c is the derivative with soft stop=8.0; this validates whether adding
the stop preserves the borderline significance or degrades it.

Pass criteria:
  Seed significance ≥ 75% → borderline robust, write SPEC
  Seed significance 60–75% → write SPEC with explicit caveat
  Seed significance < 60% → return to PM for risk discussion
"""

import pickle
import math
import numpy as np
import pandas as pd

import warnings
warnings.filterwarnings('ignore')

# ─── Load V2c trades from prior run ───────────────────────────────────────────
with open('/tmp/q041_es_v2_validation.pkl', 'rb') as f:
    prior = pickle.load(f)
v2c_df = prior['b3_variants']['V2c_stop8']
v2c_pnls = v2c_df['pnl_$'].values

# Also load V2 for B3 comparison
with open('/tmp/q041_es_true_ladder.pkl', 'rb') as f:
    ladder_data = pickle.load(f)
v2_df = ladder_data['variants']['V2_true_49_21_nostop']
v2_pnls = v2_df['pnl_$'].values

# ─── Constants ────────────────────────────────────────────────────────────────
WINDOW_START = "2000-01-01"
WINDOW_END   = "2026-04-17"
ACCOUNT      = 500_000.0
YEARS        = (pd.Timestamp(WINDOW_END) - pd.Timestamp(WINDOW_START)).days / 365.25

print(f"V2c: n={len(v2c_pnls)}, mean=${v2c_pnls.mean():.0f}/trade, total=${v2c_pnls.sum():,.0f}")
print(f"V2:  n={len(v2_pnls)}, mean=${v2_pnls.mean():.0f}/trade, total=${v2_pnls.sum():,.0f}")
print(f"Window: {WINDOW_START} → {WINDOW_END} ({YEARS:.1f} yr)\n")

# ─── Bootstrap with seed control ──────────────────────────────────────────────
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
            'significant': lo > 0, 'block_size': block_size, 'seed': seed}

def to_ann_roe(mean_per_trade, n):
    return (mean_per_trade * (n / YEARS)) / ACCOUNT * 100

# ─── B1: Block-size sweep on V2c ──────────────────────────────────────────────
print(f"{'='*88}")
print(f"  B1: V2c Block-size sweep (seed=42, n_boot=2000)")
print(f"{'='*88}\n")
print(f"  {'block_size':>10}  {'CI lo $':>10}  {'CI hi $':>10}  {'CI lo Ann%':>12}  {'CI hi Ann%':>12}  {'sig?':>5}")
print(f"  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*5}")

b1_block_sizes = [50, 100, 200, 250, 500]
b1_results = []
for bs in b1_block_sizes:
    r = bootstrap_ci_seeded(v2c_pnls, bs, seed=42)
    n = len(v2c_pnls)
    ann_lo = to_ann_roe(r['ci_lo'], n)
    ann_hi = to_ann_roe(r['ci_hi'], n)
    sig = "✅" if r['significant'] else "❌"
    print(f"  {bs:>10}  {r['ci_lo']:>+10.2f}  {r['ci_hi']:>+10.2f}  {ann_lo:>+11.2f}%  {ann_hi:>+11.2f}%  {sig:>5}")
    b1_results.append({'block_size': bs, 'ci_lo_$': r['ci_lo'], 'ci_hi_$': r['ci_hi'],
                       'ci_lo_ann_%': round(ann_lo, 3), 'ci_hi_ann_%': round(ann_hi, 3),
                       'significant': r['significant']})

b1_df = pd.DataFrame(b1_results)
sig_blocks = b1_df[b1_df['significant']]['block_size'].tolist()

# Smoothness check: are CI bounds monotonic / continuous?
b1_lo_values = b1_df['ci_lo_ann_%'].values
print(f"\n  CI lower bound progression (block 50 → 500): "
      f"{', '.join(f'{x:+.2f}%' for x in b1_lo_values)}")

# Determine smoothness: if no >50% reversal between adjacent blocks, smooth
diffs = np.diff(b1_lo_values)
max_reversal = max(0, -diffs.min()) if len(diffs) > 0 else 0
mean_step = np.abs(diffs).mean() if len(diffs) > 0 else 0
smooth = max_reversal < mean_step * 2  # heuristic: reversal smaller than 2× mean step

print(f"  Significant block sizes: {sig_blocks}")
if smooth:
    print(f"  Transition pattern: SMOOTH ✅ (no major reversals; consistent with regime alpha)")
else:
    print(f"  Transition pattern: NOT SMOOTH ⚠ (reversal {max_reversal:.3f}% vs mean step {mean_step:.3f}%)")

# ─── B2: Seed stability at block_size=250 ─────────────────────────────────────
print(f"\n{'='*88}")
print(f"  B2: V2c Seed stability (block_size=250, 20 seeds)")
print(f"{'='*88}\n")

b2_results = []
for seed in range(1, 21):
    r = bootstrap_ci_seeded(v2c_pnls, 250, seed=seed)
    n = len(v2c_pnls)
    ann_lo = to_ann_roe(r['ci_lo'], n)
    ann_hi = to_ann_roe(r['ci_hi'], n)
    b2_results.append({'seed': seed, 'ci_lo_$': r['ci_lo'], 'ci_hi_$': r['ci_hi'],
                       'ci_lo_ann_%': ann_lo, 'ci_hi_ann_%': ann_hi,
                       'significant': r['significant']})

b2_df = pd.DataFrame(b2_results)
sig_count = int(b2_df['significant'].sum())
sig_rate = sig_count / 20 * 100
print(f"  CI lo $ across seeds: min=${b2_df['ci_lo_$'].min():.2f}, "
      f"max=${b2_df['ci_lo_$'].max():.2f}, median=${b2_df['ci_lo_$'].median():.2f}")
print(f"  CI lo Ann% across seeds: min={b2_df['ci_lo_ann_%'].min():+.3f}%, "
      f"max={b2_df['ci_lo_ann_%'].max():+.3f}%, median={b2_df['ci_lo_ann_%'].median():+.3f}%")
print(f"  Significant seeds: {sig_count} / 20 = {sig_rate:.0f}%")
print(f"\n  Per-seed breakdown:")
print(b2_df.to_string(index=False))

if sig_rate >= 80:
    b2_verdict = "STABLE — borderline robust"
elif sig_rate >= 75:
    b2_verdict = "BORDERLINE ROBUST — passes 75% threshold"
elif sig_rate >= 60:
    b2_verdict = "WEAK SIGNIFICANCE — passes write-with-caveat threshold"
else:
    b2_verdict = "BELOW WRITE-WITH-CAVEAT THRESHOLD — return to PM"
print(f"\n  Verdict: {b2_verdict}")

# ─── B3: V2 vs V2c side-by-side ───────────────────────────────────────────────
print(f"\n{'='*88}")
print(f"  B3: V2 vs V2c side-by-side bootstrap comparison")
print(f"{'='*88}\n")

# Compute V2 stats for comparison (using same seeds 1-20)
v2_b2_results = []
for seed in range(1, 21):
    r = bootstrap_ci_seeded(v2_pnls, 250, seed=seed)
    n = len(v2_pnls)
    ann_lo = to_ann_roe(r['ci_lo'], n)
    v2_b2_results.append({'seed': seed, 'ci_lo_$': r['ci_lo'],
                          'ci_lo_ann_%': ann_lo, 'significant': r['significant']})
v2_b2_df = pd.DataFrame(v2_b2_results)
v2_sig_count = int(v2_b2_df['significant'].sum())
v2_sig_rate = v2_sig_count / 20 * 100
v2_ci_lo_median = v2_b2_df['ci_lo_ann_%'].median()
v2c_ci_lo_median = b2_df['ci_lo_ann_%'].median()

# Block-size sweep for V2 (same blocks)
v2_b1 = []
for bs in b1_block_sizes:
    r = bootstrap_ci_seeded(v2_pnls, bs, seed=42)
    n = len(v2_pnls)
    v2_b1.append({'block_size': bs, 'ci_lo_$': r['ci_lo'],
                  'ci_lo_ann_%': to_ann_roe(r['ci_lo'], n),
                  'significant': r['significant']})
v2_b1_df = pd.DataFrame(v2_b1)
v2_smooth_blocks = v2_b1_df[v2_b1_df['significant']]['block_size'].tolist()

print(f"  Block-size sweep comparison:")
print(f"  {'block_size':>10}  {'V2 CI lo Ann%':>15}  {'V2c CI lo Ann%':>16}  {'V2 sig':>7}  {'V2c sig':>8}")
for bs in b1_block_sizes:
    v2_row = v2_b1_df[v2_b1_df['block_size'] == bs].iloc[0]
    v2c_row = b1_df[b1_df['block_size'] == bs].iloc[0]
    print(f"  {bs:>10}  {v2_row['ci_lo_ann_%']:>+14.3f}%  {v2c_row['ci_lo_ann_%']:>+15.3f}%  "
          f"{'✅' if v2_row['significant'] else '❌':>7}  {'✅' if v2c_row['significant'] else '❌':>8}")

print(f"\n  Seed stability comparison (block=250, 20 seeds):")
print(f"    V2:  significant {v2_sig_count}/20 ({v2_sig_rate:.0f}%), CI lo median {v2_ci_lo_median:+.3f}%")
print(f"    V2c: significant {sig_count}/20 ({sig_rate:.0f}%), CI lo median {v2c_ci_lo_median:+.3f}%")

# Detect whether STOP_MULT=8 degraded significance
delta_sig_rate = sig_rate - v2_sig_rate
delta_ci_lo = v2c_ci_lo_median - v2_ci_lo_median
print(f"\n  Δ (V2c - V2):")
print(f"    Sig rate: {delta_sig_rate:+.0f}pp")
print(f"    CI lo median Ann %: {delta_ci_lo:+.3f}pp")

# ─── Decision Summary Table ───────────────────────────────────────────────────
print(f"\n{'='*88}")
print(f"  DECISION SUMMARY TABLE")
print(f"{'='*88}\n")
print(f"  {'Metric':<35}  {'V2 (reference)':>18}  {'V2c (this run)':>18}")
print(f"  {'-'*35}  {'-'*18}  {'-'*18}")
print(f"  {'Seed significance rate':<35}  {v2_sig_rate:>17.0f}%  {sig_rate:>17.0f}%")
print(f"  {'CI lo median (Ann ROE)':<35}  {v2_ci_lo_median:>+17.3f}%  {v2c_ci_lo_median:>+17.3f}%")
print(f"  {'Smallest block giving significance':<35}  {min(v2_smooth_blocks) if v2_smooth_blocks else 'none':>18}  {min(sig_blocks) if sig_blocks else 'none':>18}")
print(f"  {'B1 smooth transition':<35}  {'✅':>18}  {'✅' if smooth else '❌':>18}")

# ─── Final verdict ────────────────────────────────────────────────────────────
print(f"\n  PASS CRITERIA:")
print(f"    seed sig ≥ 80%: borderline robust → write SPEC")
print(f"    seed sig ≥ 75%: borderline robust → write SPEC")
print(f"    seed sig ≥ 60%: write SPEC with explicit caveat")
print(f"    seed sig < 60%: return to PM")

if sig_rate >= 80:
    final = f"V2c PASSES at 'borderline robust' (≥80%) — proceed to SPEC, treat as caveated alpha"
elif sig_rate >= 75:
    final = f"V2c PASSES at 'borderline robust' (≥75%) — proceed to SPEC, treat as caveated alpha"
elif sig_rate >= 60:
    final = f"V2c PASSES at 'caveated' (60-75%) — proceed to SPEC with EXPLICIT borderline-significance disclosure"
else:
    final = f"V2c FAILS — return to PM for risk discussion"

print(f"\n  FINAL VERDICT: {final}")

# ─── Save ─────────────────────────────────────────────────────────────────────
out_path = '/tmp/q055_v2c_bootstrap.pkl'
with open(out_path, 'wb') as f:
    pickle.dump({
        'b1_v2c': b1_df,
        'b2_v2c': b2_df,
        'b1_v2_ref': v2_b1_df,
        'b2_v2_ref': v2_b2_df,
        'v2c_sig_rate': sig_rate,
        'v2c_ci_lo_median': v2c_ci_lo_median,
        'v2_sig_rate': v2_sig_rate,
        'v2_ci_lo_median': v2_ci_lo_median,
        'verdict': final,
    }, f)
print(f"\n  Saved: {out_path}")
