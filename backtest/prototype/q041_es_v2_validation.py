"""
V2 Validation: Block-size sweep + Seed stability + Soft-stop scan
==================================================================

B1: Block size sensitivity (transition smoothness)
B2: Random seed stability at block_size=250
B3: V2 + soft stop variants (STOP_MULT 5.0, 6.0, 8.0)

All on V2 = true ladder, entry=49 DTE (trading days), exit_at=21 DTE,
26-yr BS-flat (VIX as sigma), $500k account.
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

# ─── BS pricer ────────────────────────────────────────────────────────────────
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

# ─── True Ladder simulator ────────────────────────────────────────────────────
def run_true_ladder(sim_df, entry_dte_td, exit_at_dte_td, stop_mult,
                    entry_cadence_td=WEEKLY_TD, profit_frac=PROFIT_FRAC):
    positions = []
    trades = []
    days_since_entry = entry_cadence_td

    for i, (date, row) in enumerate(sim_df.iterrows()):
        spx = float(row["spx"])
        vix = float(row["vix"])
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
                trades.append({
                    'entry_date': pos['entry_date'], 'exit_date': dstr,
                    'pnl_$': pnl, 'exit_reason': reason,
                    'year': pd.Timestamp(pos['entry_date']).year,
                })
            else:
                still_open.append(pos)
        positions = still_open

        days_since_entry += 1
        if days_since_entry >= entry_cadence_td and i >= 64:
            K = find_strike_for_delta(spx, entry_dte_td, sigma, TARGET_DELTA)
            entry_prem = bs_put_price(spx, K, entry_dte_td, sigma)
            if entry_prem > 0.5:
                positions.append({
                    'entry_date': dstr, 'dte': entry_dte_td, 'K': K,
                    'entry_prem': entry_prem,
                    'stop_prem': entry_prem * stop_mult if stop_mult else None,
                    'profit_prem': entry_prem * profit_frac,
                })
                days_since_entry = 0

    if positions:
        last_row = sim_df.iloc[-1]
        last_spx = float(last_row["spx"]); last_vix = float(last_row["vix"])
        last_sigma = last_vix / 100.0
        last_date = sim_df.index[-1].strftime("%Y-%m-%d")
        for pos in positions:
            cur_val = bs_put_price(last_spx, pos['K'], max(pos['dte'], 0), last_sigma)
            pnl = (pos['entry_prem'] - cur_val) * SPX_MULT
            trades.append({
                'entry_date': pos['entry_date'], 'exit_date': last_date,
                'pnl_$': pnl, 'exit_reason': 'end_of_window',
                'year': pd.Timestamp(pos['entry_date']).year,
            })
    return pd.DataFrame(trades)

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

# ─── Load V2 trades from previous run ─────────────────────────────────────────
print("Loading V2 trades from prior run...")
with open('/tmp/q041_es_true_ladder.pkl', 'rb') as f:
    prior = pickle.load(f)
v2_df = prior['variants']['V2_true_49_21_nostop']
v2_pnls = v2_df['pnl_$'].values
print(f"  V2: n={len(v2_pnls)}, mean=${v2_pnls.mean():.0f}/trade, total=${v2_pnls.sum():,.0f}")

def to_ann_roe(mean_per_trade, n):
    return (mean_per_trade * (n / YEARS)) / ACCOUNT * 100

# ─── B1: Block-size sweep ─────────────────────────────────────────────────────
print(f"\n{'='*88}")
print(f"  B1: Block-size sweep on V2 (seed=42, n_boot=2000)")
print(f"{'='*88}\n")
print(f"  {'block_size':>10}  {'CI lo $':>10}  {'CI hi $':>10}  {'CI lo Ann%':>12}  {'CI hi Ann%':>12}  {'sig?':>5}")
print(f"  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*5}")

b1_results = []
for bs in [25, 50, 75, 100, 150, 200, 250, 300]:
    r = bootstrap_ci_seeded(v2_pnls, bs, seed=42)
    n = len(v2_pnls)
    ann_lo = to_ann_roe(r['ci_lo'], n)
    ann_hi = to_ann_roe(r['ci_hi'], n)
    sig = "✅" if r['significant'] else "❌"
    print(f"  {bs:>10}  {r['ci_lo']:>+10.0f}  {r['ci_hi']:>+10.0f}  {ann_lo:>+11.2f}%  {ann_hi:>+11.2f}%  {sig:>5}")
    b1_results.append({'block_size': bs, 'ci_lo_$': r['ci_lo'], 'ci_hi_$': r['ci_hi'],
                       'ci_lo_ann_%': round(ann_lo, 2), 'ci_hi_ann_%': round(ann_hi, 2),
                       'significant': r['significant']})

# Identify transition
b1_df = pd.DataFrame(b1_results)
sig_block_sizes = b1_df[b1_df['significant']]['block_size'].tolist()
print(f"\n  Significant block sizes: {sig_block_sizes}")
if len(sig_block_sizes) > 0:
    smallest_sig = min(sig_block_sizes)
    print(f"  Smallest block_size that gives significance: {smallest_sig}")
    if len(sig_block_sizes) == len([b for b in [25,50,75,100,150,200,250,300] if b >= smallest_sig]):
        print(f"  Transition pattern: SMOOTH — significance starts at block_size={smallest_sig} and persists")
    else:
        print(f"  Transition pattern: UNSTABLE — significance not monotonic")
else:
    print(f"  NO block size gives significance.")

# ─── B2: Seed stability at block_size=250 ─────────────────────────────────────
print(f"\n{'='*88}")
print(f"  B2: Seed stability on V2 (block_size=250, 20 seeds)")
print(f"{'='*88}\n")

b2_results = []
for seed in range(1, 21):
    r = bootstrap_ci_seeded(v2_pnls, 250, seed=seed)
    n = len(v2_pnls)
    ann_lo = to_ann_roe(r['ci_lo'], n)
    ann_hi = to_ann_roe(r['ci_hi'], n)
    b2_results.append({'seed': seed, 'ci_lo_$': r['ci_lo'], 'ci_hi_$': r['ci_hi'],
                       'ci_lo_ann_%': ann_lo, 'ci_hi_ann_%': ann_hi,
                       'significant': r['significant']})

b2_df = pd.DataFrame(b2_results)
sig_count = b2_df['significant'].sum()
print(f"  CI lo $ across seeds: min=${b2_df['ci_lo_$'].min():.0f}, max=${b2_df['ci_lo_$'].max():.0f}, "
      f"median=${b2_df['ci_lo_$'].median():.0f}")
print(f"  CI lo Ann% across seeds: min={b2_df['ci_lo_ann_%'].min():.2f}%, max={b2_df['ci_lo_ann_%'].max():.2f}%, "
      f"median={b2_df['ci_lo_ann_%'].median():.2f}%")
print(f"  Significant seeds: {sig_count} / 20")
print(f"\n  Per-seed results:")
print(b2_df.to_string(index=False))

if sig_count >= 18:
    b2_verdict = "STABLE — V2 significance robust to seed choice"
elif sig_count >= 12:
    b2_verdict = "MOSTLY STABLE — significance edge but mostly holds"
elif sig_count >= 8:
    b2_verdict = "BORDERLINE — significance is coin-flip on seed"
else:
    b2_verdict = "UNSTABLE — V2 'significance' at block=250 is mostly seed artifact"
print(f"\n  Verdict: {b2_verdict}")

# ─── B3: V2 + soft stop variants ──────────────────────────────────────────────
print(f"\n{'='*88}")
print(f"  B3: V2 + soft stop variants (STOP_MULT 5.0 / 6.0 / 8.0)")
print(f"{'='*88}\n")

print("Loading market data...")
data, _ = es_mod._load_data()
sim_df = data[(data.index >= pd.Timestamp(WINDOW_START)) & (data.index <= pd.Timestamp(WINDOW_END))]
print(f"  Trading days: {len(sim_df)}")

b3_variants = {}
for stop_mult, label in [(5.0, "V2a_stop5"), (6.0, "V2b_stop6"), (8.0, "V2c_stop8")]:
    print(f"\n  Running {label} (STOP_MULT={stop_mult})...")
    df = run_true_ladder(sim_df, entry_dte_td=49, exit_at_dte_td=21, stop_mult=stop_mult)
    b3_variants[label] = df
    print(f"    n={len(df)}, total=${df['pnl_$'].sum():,.0f}, "
          f"worst=${df['pnl_$'].min():,.0f}, "
          f"WR={(df['pnl_$']>0).mean()*100:.1f}%")

# Add V2 reference
b3_variants["V2_no_stop"] = v2_df

print(f"\n  Variant comparison:")
print(f"  {'Variant':<15}  {'n':>5}  {'total $':>12}  {'mean $':>10}  {'Ann ROE %':>10}  {'WR %':>6}  {'Worst $':>12}  {'CI lo bs250':>12}")
print(f"  {'-'*15}  {'-'*5}  {'-'*12}  {'-'*10}  {'-'*10}  {'-'*6}  {'-'*12}  {'-'*12}")

b3_summary = []
for label, df in b3_variants.items():
    pnls = df['pnl_$'].values
    n = len(pnls)
    total = pnls.sum()
    mean = pnls.mean()
    ann = to_ann_roe(mean, n)
    wr = (pnls > 0).mean() * 100
    worst = pnls.min()
    r = bootstrap_ci_seeded(pnls, 250, seed=42)
    ci_lo_ann = to_ann_roe(r['ci_lo'], n)
    sig_marker = " ✅" if r['significant'] else ""
    print(f"  {label:<15}  {n:>5}  {total:>+12,.0f}  {mean:>+10.0f}  {ann:>+9.2f}%  {wr:>5.1f}%  "
          f"{worst:>+12,.0f}  {ci_lo_ann:>+11.2f}%{sig_marker}")
    b3_summary.append({
        'variant': label, 'n': n, 'total_$': round(total, 0),
        'mean_$': round(mean, 0), 'ann_roe_%': round(ann, 2),
        'wr_%': round(wr, 1), 'worst_$': round(worst, 0),
        'ci_lo_ann_%_bs250': round(ci_lo_ann, 2),
        'significant_bs250': r['significant'],
    })

# ─── Stress year breakdown for B3 variants ────────────────────────────────────
print(f"\n  Stress-year worst-trade comparison (2008/2018/2020/2022):")
print(f"  {'Variant':<15}  {'2008 worst':>12}  {'2018 worst':>12}  {'2020 worst':>12}  {'2022 worst':>12}")
for label, df in b3_variants.items():
    yr_worst = {}
    for y in [2008, 2018, 2020, 2022]:
        sub = df[df['year'] == y]
        yr_worst[y] = sub['pnl_$'].min() if len(sub) > 0 else 0
    print(f"  {label:<15}  {yr_worst[2008]:>+12,.0f}  {yr_worst[2018]:>+12,.0f}  "
          f"{yr_worst[2020]:>+12,.0f}  {yr_worst[2022]:>+12,.0f}")

# ─── Save all ─────────────────────────────────────────────────────────────────
out_path = '/tmp/q041_es_v2_validation.pkl'
with open(out_path, 'wb') as f:
    pickle.dump({
        'b1_block_sweep': b1_df,
        'b2_seed_stability': b2_df,
        'b2_verdict': b2_verdict,
        'b3_variants': b3_variants,
        'b3_summary': pd.DataFrame(b3_summary),
    }, f)
print(f"\n  Saved: {out_path}")
