"""
Q060 Tier 1 — V2f+Dynamic Leverage SPEC Candidate Validation
=============================================================

Two gates required for SPEC entry:
  Task A: Bootstrap sig_rate ≥ 60% (block=250, 20 seeds) — same protocol as V2 / V2f
  Task B: Extreme-tail stress test worst trade ≥ -15% NLV (V1 veto holds under shock)

If both PASS → V2f_dynlev passes for SPEC consideration
If either FAILS → return to PM
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
WEEKLY_TD    = 5
YEARS = (pd.Timestamp(WINDOW_END) - pd.Timestamp(WINDOW_START)).days / 365.25

V2F_ENTRY_DTE  = 49
V2F_EXIT_DTE   = 21
V2F_MAX_SLOTS  = 5
V2F_STOP_MULT  = 15.0

P3_LEVERAGE_TABLE = [
    (40, 0.50), (30, 0.40), (20, 0.35), (15, 0.30), (0, 0.25),
]

def max_bp_ceiling(vix):
    for threshold, ceiling in P3_LEVERAGE_TABLE:
        if vix >= threshold:
            return ceiling
    return 0.25

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

def bp_per_contract(spx, strike, premium_pts):
    prem_usd = premium_pts * SPX_MULT
    method_a = 0.15 * spx * SPX_MULT - max(0, (spx - strike)) * SPX_MULT + prem_usd
    method_b = 0.10 * strike * SPX_MULT + prem_usd
    return max(method_a, method_b, 37.50)

# ─── Simulator (port from Tier 2-A; v2f core, alone-mode only) ───────────────
def run_v2f(sim_df, dynlev=False):
    positions = []
    short_trades = []
    daily_log = []
    equity = ACCOUNT
    eq_curve = []
    days_since_entry = WEEKLY_TD

    for i, (date, row) in enumerate(sim_df.iterrows()):
        spx = float(row["spx"]); vix = float(row["vix"])
        sigma = vix / 100.0
        dstr = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0

        # Manage existing positions
        still_open = []
        for pos in positions:
            pos['dte'] -= 1
            cur_val = bs_put_price(spx, pos['K'], max(pos['dte'], 0), sigma)
            pnl_delta = (pos['prev_val'] - cur_val) * pos['contracts'] * SPX_MULT
            daily_pnl += pnl_delta
            reason = None
            if pos['dte'] <= V2F_EXIT_DTE:
                reason = "ladder_exit"
            elif cur_val >= pos['stop_prem']:
                reason = "stop_loss"
            elif cur_val <= pos['profit_prem']:
                reason = "profit_target"
            elif pos['dte'] <= 0:
                reason = "expiry"

            if reason:
                trade_pnl = (pos['entry_prem'] - cur_val) * pos['contracts'] * SPX_MULT
                short_trades.append({
                    'entry_date': pos['entry_date'], 'exit_date': dstr,
                    'pnl_$': trade_pnl, 'exit_reason': reason,
                    'contracts': pos['contracts'], 'entry_vix': pos['entry_vix'],
                    'entry_spx': pos['entry_spx'], 'K': pos['K'],
                    'year': pd.Timestamp(pos['entry_date']).year,
                })
            else:
                pos['prev_val'] = cur_val
                still_open.append(pos)
        positions = still_open

        # Entry
        days_since_entry += 1
        if (days_since_entry >= WEEKLY_TD and i >= 64
            and len(positions) < V2F_MAX_SLOTS):
            K = find_strike_for_delta(spx, V2F_ENTRY_DTE, sigma, TARGET_DELTA)
            entry_prem = bs_put_price(spx, K, V2F_ENTRY_DTE, sigma)
            if entry_prem > 0.5:
                if dynlev:
                    bp_ceiling = max_bp_ceiling(vix)
                    per_slot_target = (bp_ceiling * equity) / V2F_MAX_SLOTS
                    bp_one = bp_per_contract(spx, K, entry_prem)
                    n_contracts = max(0.5, per_slot_target / bp_one)
                else:
                    n_contracts = 1.0
                positions.append({
                    'entry_date': dstr, 'dte': V2F_ENTRY_DTE, 'K': K,
                    'entry_prem': entry_prem,
                    'stop_prem': entry_prem * V2F_STOP_MULT,
                    'profit_prem': entry_prem * PROFIT_FRAC,
                    'prev_val': entry_prem,
                    'contracts': n_contracts,
                    'entry_vix': vix,
                    'entry_spx': spx,
                })
                days_since_entry = 0

        equity += daily_pnl
        daily_log.append({'date': date, 'spx': spx, 'vix': vix,
                          'daily_pnl': daily_pnl, 'equity': equity,
                          'n_positions': len(positions)})
        eq_curve.append(equity)

    # Force-close
    last_row = sim_df.iloc[-1]
    last_spx = float(last_row["spx"]); last_vix = float(last_row["vix"])
    last_sigma = last_vix / 100.0
    last_date = sim_df.index[-1].strftime("%Y-%m-%d")
    for pos in positions:
        cur_val = bs_put_price(last_spx, pos['K'], max(pos['dte'], 0), last_sigma)
        trade_pnl = (pos['entry_prem'] - cur_val) * pos['contracts'] * SPX_MULT
        short_trades.append({
            'entry_date': pos['entry_date'], 'exit_date': last_date,
            'pnl_$': trade_pnl, 'exit_reason': 'end_of_window',
            'contracts': pos['contracts'], 'entry_vix': pos['entry_vix'],
            'entry_spx': pos['entry_spx'], 'K': pos['K'],
            'year': pd.Timestamp(pos['entry_date']).year,
        })

    return {
        'short_trades': pd.DataFrame(short_trades),
        'daily_log': pd.DataFrame(daily_log),
        'final_equity': equity,
        'eq_curve': eq_curve,
    }

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

# ─── Load market data ────────────────────────────────────────────────────────
print("Loading market data...")
data, _ = es_mod._load_data()
sim_df = data[(data.index >= pd.Timestamp(WINDOW_START)) & (data.index <= pd.Timestamp(WINDOW_END))]
print(f"  Trading days: {len(sim_df)}")

# ─── Task A: Bootstrap on V2f_dynlev_alone ───────────────────────────────────
print(f"\n{'='*88}")
print(f"  Task A: Bootstrap on V2f_dynlev_alone (26-yr BS-flat baseline)")
print(f"{'='*88}\n")

print("  Running V2f_dynlev_alone (no shock)...")
r_dynlev = run_v2f(sim_df, dynlev=True)
trades = r_dynlev['short_trades']
pnls = trades['pnl_$'].values
print(f"  n_trades: {len(pnls)}")
print(f"  Total PnL: ${pnls.sum():,.0f}")
print(f"  Final equity: ${r_dynlev['final_equity']:,.0f}")
print(f"  Worst trade: ${pnls.min():,.0f} ({pnls.min()/ACCOUNT*100:+.2f}% NLV)")

# B1: Block-size sweep
print(f"\n  ── B1: Block-size sweep (seed=42) ──")
print(f"  {'block':>6}  {'CI lo Ann%':>11}  {'CI hi Ann%':>11}  {'sig?':>5}")
b1_results = []
for bs in [50, 100, 200, 250, 500]:
    r = bootstrap_ci_seeded(pnls, bs, seed=42)
    n = len(pnls)
    ann_lo = to_ann_roe(r['ci_lo'], n)
    ann_hi = to_ann_roe(r['ci_hi'], n)
    sig = "✅" if r['significant'] else "❌"
    print(f"  {bs:>6}  {ann_lo:>+10.2f}%  {ann_hi:>+10.2f}%  {sig:>5}")
    b1_results.append({'block_size': bs, 'ci_lo_ann': ann_lo, 'ci_hi_ann': ann_hi,
                       'significant': r['significant']})

# Smooth transition check
b1_df = pd.DataFrame(b1_results)
los = b1_df['ci_lo_ann'].values
diffs = np.diff(los)
max_reversal = max(0, -diffs.min()) if len(diffs) > 0 else 0
mean_step = np.abs(diffs).mean() if len(diffs) > 0 else 0
b1_smooth = max_reversal < mean_step * 2
print(f"\n  CI lo progression: {', '.join(f'{x:+.2f}%' for x in los)}")
print(f"  B1 transition: {'SMOOTH ✅' if b1_smooth else 'UNSTABLE ❌'}")

# B2: Seed stability at block=250
print(f"\n  ── B2: Seed stability (block=250, 20 seeds) ──")
b2_sig = 0
b2_lo_anns = []
for seed in range(1, 21):
    r = bootstrap_ci_seeded(pnls, 250, seed=seed)
    if r['significant']:
        b2_sig += 1
    b2_lo_anns.append(to_ann_roe(r['ci_lo'], len(pnls)))
b2_sig_rate = b2_sig / 20 * 100
b2_lo_median = float(np.median(b2_lo_anns))
print(f"  Significant seeds: {b2_sig} / 20 = {b2_sig_rate:.0f}%")
print(f"  CI lo Ann%: min={min(b2_lo_anns):+.3f}%, median={b2_lo_median:+.3f}%, max={max(b2_lo_anns):+.3f}%")

task_a_pass = b2_sig_rate >= 60
print(f"\n  Task A: {'✅ PASS (sig_rate ≥ 60%)' if task_a_pass else '❌ FAIL (sig_rate < 60%)'}")

# ─── Task B: Extreme tail stress simulation ──────────────────────────────────
print(f"\n{'='*88}")
print(f"  Task B: Extreme-Tail Stress Test")
print(f"  Synthetic shock: SPX -7%/day × 5 days = -30%, VIX 25 → 60+, then 10-day recovery")
print(f"{'='*88}\n")

# Pick anchor: VIX ≈ 25-26, sufficient prior data for ladder ramp-up
# Use 2022-11-09 (VIX was around 25); could pick others for sensitivity
anchor_target = pd.Timestamp("2022-11-09")
mask = sim_df.index >= anchor_target
anchor_idx = mask.argmax()
anchor_actual_date = sim_df.index[anchor_idx]
anchor_spx = sim_df.iloc[anchor_idx]['spx']
anchor_vix = sim_df.iloc[anchor_idx]['vix']
print(f"  Anchor date: {anchor_actual_date.date()}, SPX={anchor_spx:.0f}, VIX={anchor_vix:.1f}")

# Build shocked sim_df
sim_df_shocked = sim_df.copy()

# Shock window: T+1 to T+5
shock_indices = list(range(anchor_idx + 1, anchor_idx + 6))
spx_at_t5 = anchor_spx * (0.93 ** 5)
print(f"  Shock window: {sim_df.index[shock_indices[0]].date()} → {sim_df.index[shock_indices[-1]].date()}")
print(f"  SPX path: {anchor_spx:.0f} → ", end='')

vix_target_at_t5 = 60.0
for i, idx in enumerate(shock_indices, start=1):
    new_spx = anchor_spx * (0.93 ** i)
    new_vix = anchor_vix + (vix_target_at_t5 - anchor_vix) * (i / 5)
    d = sim_df.index[idx]
    sim_df_shocked.loc[d, 'spx'] = new_spx
    sim_df_shocked.loc[d, 'vix'] = new_vix
    print(f"{new_spx:.0f} ", end='')
print(f"(cumulative -30.4%)")

# Recovery window: T+6 to T+15, VIX returns from 60 to ~25
recovery_indices = list(range(anchor_idx + 6, anchor_idx + 16))
for j, idx in enumerate(recovery_indices, start=1):
    if idx >= len(sim_df):
        break
    new_vix = vix_target_at_t5 - (vix_target_at_t5 - anchor_vix) * (j / 10)
    d = sim_df.index[idx]
    sim_df_shocked.loc[d, 'vix'] = new_vix

# Post-shock SPX baseline shift: subsequent SPX uses shocked T+5 as base
shock_factor = spx_at_t5 / sim_df.iloc[anchor_idx + 5]['spx']
print(f"  SPX shock_factor: {shock_factor:.3f} (post-shock baseline lower)")
post_shock_dates = sim_df.index[anchor_idx + 6:]
for d in post_shock_dates:
    sim_df_shocked.loc[d, 'spx'] = sim_df.loc[d, 'spx'] * shock_factor

# Run both V2f_alone and V2f_dynlev_alone on shocked data
print("\n  Running V2f_alone (fixed 1 contract) on shocked data...")
r_alone_shock = run_v2f(sim_df_shocked, dynlev=False)
print(f"    n_trades: {len(r_alone_shock['short_trades'])}, "
      f"final equity: ${r_alone_shock['final_equity']:,.0f}")

print("  Running V2f_dynlev_alone on shocked data...")
r_dynlev_shock = run_v2f(sim_df_shocked, dynlev=True)
print(f"    n_trades: {len(r_dynlev_shock['short_trades'])}, "
      f"final equity: ${r_dynlev_shock['final_equity']:,.0f}")

# Find trades active during shock window
shock_start = anchor_actual_date
shock_end = sim_df.index[anchor_idx + 15]
print(f"\n  Shock window analysis: {shock_start.date()} → {shock_end.date()}\n")

def trades_during_shock(trades_df, start, end):
    t = trades_df.copy()
    t['entry_dt'] = pd.to_datetime(t['entry_date'])
    t['exit_dt']  = pd.to_datetime(t['exit_date'])
    # active during shock window if entry < end AND exit > start
    return t[(t['entry_dt'] <= end) & (t['exit_dt'] >= start)]

t_alone = trades_during_shock(r_alone_shock['short_trades'], shock_start, shock_end)
t_dynlev = trades_during_shock(r_dynlev_shock['short_trades'], shock_start, shock_end)

print(f"  V2f_alone trades active during shock: {len(t_alone)}")
if len(t_alone) > 0:
    print(t_alone[['entry_date', 'exit_date', 'entry_vix', 'contracts',
                   'pnl_$', 'exit_reason']].to_string(index=False))
    worst_alone = t_alone['pnl_$'].min()
    print(f"  Worst alone single trade in shock window: ${worst_alone:,.0f} ({worst_alone/ACCOUNT*100:+.2f}% NLV)")

print(f"\n  V2f_dynlev_alone trades active during shock: {len(t_dynlev)}")
if len(t_dynlev) > 0:
    print(t_dynlev[['entry_date', 'exit_date', 'entry_vix', 'contracts',
                    'pnl_$', 'exit_reason']].to_string(index=False))
    worst_dynlev = t_dynlev['pnl_$'].min()
    print(f"  Worst dynlev single trade in shock window: ${worst_dynlev:,.0f} ({worst_dynlev/ACCOUNT*100:+.2f}% NLV)")

# Account-level: 5-day cumulative loss during shock peak
def account_loss_in_window(daily_log, start, end):
    sub = daily_log[(daily_log['date'] >= start) & (daily_log['date'] <= end)]
    if len(sub) == 0:
        return 0, 0, 0
    cum_pnl = sub['daily_pnl'].cumsum()
    worst_cum = cum_pnl.min()
    final_pnl = cum_pnl.iloc[-1]
    eq_at_start = sub['equity'].iloc[0] - sub['daily_pnl'].iloc[0]
    return worst_cum, final_pnl, eq_at_start

print(f"\n  Account-level cumulative loss during shock window:")
for label, r in [("V2f_alone", r_alone_shock), ("V2f_dynlev_alone", r_dynlev_shock)]:
    worst_cum, final_pnl, eq_start = account_loss_in_window(r['daily_log'], shock_start, shock_end)
    print(f"    {label:<22}: worst cumulative loss ${worst_cum:,.0f} "
          f"({worst_cum/eq_start*100:+.2f}% of pre-shock equity)")

# ─── Task B verdict ───────────────────────────────────────────────────────────
worst_alone_pct = t_alone['pnl_$'].min() / ACCOUNT * 100 if len(t_alone) > 0 else 0
worst_dynlev_pct = t_dynlev['pnl_$'].min() / ACCOUNT * 100 if len(t_dynlev) > 0 else 0

print(f"\n  ── Task B Verdict ──")
print(f"    V2f_alone shock worst trade:        {worst_alone_pct:+.2f}% NLV")
print(f"    V2f_dynlev_alone shock worst trade: {worst_dynlev_pct:+.2f}% NLV")

if worst_dynlev_pct >= -15:
    task_b_verdict = "✅ PASS (worst ≥ -15% NLV)"
    task_b_pass = True
elif worst_dynlev_pct >= -20:
    task_b_verdict = "⚠ PM DECISION (-15% to -20%)"
    task_b_pass = "PM"
else:
    task_b_verdict = "❌ FAIL (worst < -20% NLV)"
    task_b_pass = False
print(f"    Task B: {task_b_verdict}")

# Sensitivity: what's the loss amplification ratio?
if abs(worst_alone_pct) > 0.01:
    amp = worst_dynlev_pct / worst_alone_pct
    print(f"    Loss amplification (dynlev / alone): {amp:.2f}×")

# ─── Combined verdict ────────────────────────────────────────────────────────
print(f"\n{'='*88}")
print(f"  COMBINED VERDICT")
print(f"{'='*88}\n")

print(f"  Task A (Bootstrap sig_rate): {b2_sig_rate:.0f}% → {'PASS' if task_a_pass else 'FAIL'}")
print(f"  Task B (Stress test worst): {worst_dynlev_pct:+.2f}% NLV → {task_b_verdict}")
print()
if task_a_pass and task_b_pass is True:
    overall = "✅ V2f_dynlev_alone CLEARED for SPEC consideration"
elif task_a_pass and task_b_pass == "PM":
    overall = (f"⚠ Task A PASS but Task B requires PM decision "
               f"(stress worst {worst_dynlev_pct:+.2f}% in -15% to -20% zone)")
elif task_a_pass:
    overall = f"❌ Task A PASS but Task B FAIL — do not write SPEC"
elif task_b_pass is True:
    overall = f"❌ Task B PASS but Task A FAIL — bootstrap insufficient"
else:
    overall = "❌ BOTH FAIL — V2f_dynlev_alone not ready for SPEC"
print(f"  RESULT: {overall}")

# ─── Save ─────────────────────────────────────────────────────────────────────
out_dir = _ROOT / "research" / "q060"
out_dir.mkdir(exist_ok=True)
out_pkl = out_dir / "q060_dynlev_validation.pkl"
with open(out_pkl, 'wb') as f:
    pickle.dump({
        'task_a': {
            'b1_results': b1_df,
            'b2_sig_rate': b2_sig_rate,
            'b2_lo_median': b2_lo_median,
            'b2_lo_anns': b2_lo_anns,
            'b1_smooth': b1_smooth,
            'pass': task_a_pass,
        },
        'task_b': {
            'anchor_date': str(anchor_actual_date.date()),
            'anchor_spx': anchor_spx,
            'anchor_vix': anchor_vix,
            'shock_factor': shock_factor,
            'worst_alone_pct_nlv': worst_alone_pct,
            'worst_dynlev_pct_nlv': worst_dynlev_pct,
            'shock_trades_alone': t_alone,
            'shock_trades_dynlev': t_dynlev,
            'pass': task_b_pass,
        },
        'overall': overall,
    }, f)
print(f"\n  Saved: {out_pkl}")
