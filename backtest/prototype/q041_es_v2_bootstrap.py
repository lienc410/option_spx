"""
Bootstrap CI on V2 (true ladder, NO STOP, exit@DTE21)
=====================================================

Validates whether the +2.58% Ann ROE on V2 is statistically robust or
sample-noise. Uses block bootstrap with multiple block sizes.

Comparison baseline: V0 (current /ES P2 fixed-slots) and V1 (true ladder + STOP=3.0)
to see the structural shift in mean & CI.
"""

import pickle
import numpy as np
import pandas as pd

from backtest.run_bootstrap_ci import bootstrap_ci

with open('/tmp/q041_es_true_ladder.pkl', 'rb') as f:
    data = pickle.load(f)

variants = data['variants']
WINDOW_START, WINDOW_END = data['window']
ACCOUNT = 500_000.0
years = (pd.Timestamp(WINDOW_END) - pd.Timestamp(WINDOW_START)).days / 365.25

print(f"{'='*88}")
print(f"  Block Bootstrap CI on True Ladder Variants")
print(f"  Window: {WINDOW_START} → {WINDOW_END} ({years:.1f} yr)")
print(f"  Account: ${ACCOUNT:,.0f}")
print(f"{'='*88}\n")

# Block sizes: 1 yr (≈50 trades), 2 yr (≈100), 5 yr (≈250)
BLOCK_SIZES = [50, 100, 250]

results = []
for label in ['V0_current_P2_fixed_slots', 'V1_true_49_21_stop3',
              'V2_true_49_21_nostop', 'V3_true_49_5_stop3', 'V4_true_45_21_stop3']:
    df = variants[label]
    pnls = df['pnl_$'].values
    n = len(pnls)
    total = pnls.sum()
    mean = pnls.mean()
    ann_roe = ((1 + total/ACCOUNT) ** (1/years) - 1) * 100
    ann_pnl_implied = mean * (n / years)

    print(f"\n  {label}:")
    print(f"    n={n}, total=${total:,.0f}, mean=${mean:.0f}/trade, Ann ROE={ann_roe:+.2f}%")

    for bs in BLOCK_SIZES:
        ci = bootstrap_ci(pnls.tolist(), n_boot=2000, block_size=bs)
        # Convert CI bounds (mean per trade) to annual ROE
        ann_lo = (ci['ci_lo'] * (n / years)) / ACCOUNT * 100
        ann_hi = (ci['ci_hi'] * (n / years)) / ACCOUNT * 100
        sig = "✅ SIGNIFICANT" if ci['significant'] else "❌ not significant"
        print(f"    block_size={bs:>3}: CI mean/trade [${ci['ci_lo']:>+8.0f}, ${ci['ci_hi']:>+8.0f}]  "
              f"≈ Ann ROE [{ann_lo:+.2f}%, {ann_hi:+.2f}%]  {sig}")
        results.append({
            'variant': label, 'block_size': bs, 'n': n,
            'mean_$': round(mean, 0), 'ann_roe_%': round(ann_roe, 2),
            'ci_lo_$': ci['ci_lo'], 'ci_hi_$': ci['ci_hi'],
            'ci_lo_ann_%': round(ann_lo, 2), 'ci_hi_ann_%': round(ann_hi, 2),
            'significant': ci['significant'],
        })

print(f"\n{'='*88}")
print(f"  Summary Table (CI converted to Ann ROE on $500k)")
print(f"{'='*88}")
sdf = pd.DataFrame(results)
# Compact display
display_cols = ['variant', 'block_size', 'n', 'ann_roe_%',
                'ci_lo_ann_%', 'ci_hi_ann_%', 'significant']
print(sdf[display_cols].to_string(index=False))

# ─── Decision summary ────────────────────────────────────────────────────────
print(f"\n{'='*88}")
print(f"  Decision Read-out")
print(f"{'='*88}\n")

v2 = sdf[sdf['variant'] == 'V2_true_49_21_nostop']
v0 = sdf[sdf['variant'] == 'V0_current_P2_fixed_slots']
v2_sig = v2['significant'].all()
v0_sig = v0['significant'].all()

print(f"  V2 (true ladder, no stop): significant across all block sizes = {v2_sig}")
print(f"  V0 (current P2 baseline):  significant across all block sizes = {v0_sig}")
print()
print(f"  V2 CI mean range: [${v2['ci_lo_$'].min():.0f}, ${v2['ci_hi_$'].max():.0f}] / trade")
print(f"  V0 CI mean range: [${v0['ci_lo_$'].min():.0f}, ${v0['ci_hi_$'].max():.0f}] / trade")
print()

if v2_sig and v2['ci_lo_$'].min() > v0['ci_hi_$'].max():
    verdict = "V2 strictly dominates V0 (CI lower bound of V2 > CI upper bound of V0)"
elif v2_sig:
    verdict = "V2 alpha is significant, but CI overlaps with V0 — relative ranking less certain"
else:
    verdict = "V2 alpha is NOT significant — apparent +2.58% Ann ROE may be sample noise"

print(f"  Verdict: {verdict}")

# Save
with open('/tmp/q041_es_v2_bootstrap.pkl', 'wb') as f:
    pickle.dump({'results': sdf, 'verdict': verdict}, f)
print(f"\n  Saved: /tmp/q041_es_v2_bootstrap.pkl")
