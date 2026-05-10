"""
Q041 SPX CSP vs /ES — Methodology-Unified Comparison
=====================================================

Purpose: Determine whether the apparent ROE gap between Q041 SPX CSP T1
and /ES backtests is real strategy alpha or a denominator/period/pricing
artifact.

Three unifications applied:
  1. Same denominator: account-level Ann ROE on $500k
  2. Same window: 2022-05-20 → 2026-04-17 (Q041 data range)
  3. Pricing sensitivity: rerun Q041 cycles with BS-flat-vol (VIX as sigma)
     to isolate the effect of actual Massive prices vs theoretical BS pricing

Outputs side-by-side metrics for:
  - /ES Phase 1 baseline (DTE45, BS, no trend filter), windowed
  - /ES Phase 1 filtered  (DTE45, BS, trend filter on), windowed
  - Q041 CSP DTE30 actual (Massive prices, hold-to-expiry)
  - Q041 CSP DTE30 BS-flat (VIX as flat sigma, hold-to-expiry) — pricing sensitivity
"""

import pickle
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

import warnings
warnings.filterwarnings('ignore')

# /ES backtest is a research script (no package); load via importlib without
# polluting sys.path (otherwise its filename "backtest.py" would shadow the
# project's `backtest` package that the /ES file itself imports from).
_ROOT = Path(__file__).resolve().parents[2]
_ES_FILE = _ROOT / "research" / "strategies" / "ES_puts" / "backtest.py"
import importlib.util
spec = importlib.util.spec_from_file_location("es_backtest_mod", _ES_FILE)
es_backtest_mod = importlib.util.module_from_spec(spec)
sys.modules["es_backtest_mod"] = es_backtest_mod   # required for dataclasses
spec.loader.exec_module(es_backtest_mod)
run_phase1 = es_backtest_mod.run_phase1
P1_INITIAL_EQUITY = es_backtest_mod.P1_INITIAL_EQUITY
from signals.vix_regime import fetch_vix_history

# ─── Configuration ────────────────────────────────────────────────────────────
WINDOW_START = "2022-05-20"
WINDOW_END   = "2026-04-17"
ACCOUNT      = 500_000.0
SPX_MULT     = 100   # SPX option contract multiplier
SLIP         = 0.03
R            = 0.045

# ─── BS helpers (same as q041_p2_p21) ─────────────────────────────────────────
def bs_put_price(S, K, T, r, sigma):
    if T < 1e-6 or sigma < 1e-4:
        return max(0.0, K - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def bs_put_delta(S, K, T, r, sigma):
    if T < 1e-6 or sigma < 1e-4:
        return -1.0 if K > S else 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1) - 1.0

def find_strike_for_delta_bs(S, T, sigma, target_delta):
    lo, hi = S * 0.5, S * 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        d = abs(bs_put_delta(S, mid, T, R, sigma))
        if abs(d - target_delta) < 0.001:
            return round(mid)
        if d < target_delta:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2)

# ─── Metric framework ─────────────────────────────────────────────────────────
def account_metrics(label, dollar_pnls, dates_start, dates_end, n_trades, account=ACCOUNT):
    """Compute account-level metrics from a list of per-trade dollar PnLs."""
    arr = np.array(dollar_pnls, dtype=float)
    if len(arr) == 0:
        return None
    total = arr.sum()
    t0 = pd.Timestamp(dates_start)
    t1 = pd.Timestamp(dates_end)
    years = (t1 - t0).days / 365.25
    cum_ret = total / account
    ann_ret = (1.0 + cum_ret) ** (1.0 / years) - 1.0 if cum_ret > -1 else float('nan')
    wr = float((arr > 0).mean())
    worst = float(arr.min())
    best = float(arr.max())
    mean = float(arr.mean())
    std = float(arr.std()) if len(arr) > 1 else 0.0
    sharpe_per_trade = mean / std if std > 0 else 0.0
    freq = n_trades / years
    sharpe_ann = sharpe_per_trade * np.sqrt(freq)
    return {
        'label': label, 'n_trades': n_trades, 'years': round(years, 2),
        'total_pnl_$': round(total, 0),
        'cum_ret_%': round(cum_ret * 100, 2),
        'ann_ret_%': round(ann_ret * 100, 2),
        'wr_%': round(wr * 100, 1),
        'worst_$': round(worst, 0), 'best_$': round(best, 0),
        'mean_$': round(mean, 0), 'std_$': round(std, 0),
        'sharpe_ann': round(sharpe_ann, 2),
    }

# ─── /ES Phase 1 windowed runs ────────────────────────────────────────────────
print(f"{'='*72}")
print(f"  Running /ES Phase 1 windowed: {WINDOW_START} → {WINDOW_END}")
print(f"{'='*72}\n")

es_baseline = run_phase1(mode="baseline", start_date=WINDOW_START, end_date=WINDOW_END)
es_filtered = run_phase1(mode="filtered", start_date=WINDOW_START, end_date=WINDOW_END)

es_b_pnls = [t.pnl for t in es_baseline.trades]
es_f_pnls = [t.pnl for t in es_filtered.trades]

print(f"  /ES baseline trades: {len(es_b_pnls)}, total PnL: ${sum(es_b_pnls):,.0f}")
print(f"  /ES filtered trades: {len(es_f_pnls)}, total PnL: ${sum(es_f_pnls):,.0f}\n")

# ─── Q041 CSP actual (Massive) — load from pickle ─────────────────────────────
print(f"{'='*72}")
print(f"  Loading Q041 CSP DTE30 (Massive actual prices)")
print(f"{'='*72}\n")

with open('/tmp/p21_spx_csp_bearmarket.pkl', 'rb') as f:
    df_q041 = pickle.load(f)

# Q041 pnl is in per-unit space (no ×100). Convert to per-contract dollars.
q041_actual_pnls = (df_q041['pnl'].values * SPX_MULT).tolist()
q041_dates_start = df_q041['roll_date'].min()
q041_dates_end   = df_q041['expiry'].max()
print(f"  Q041 cycles: {len(q041_actual_pnls)}")
print(f"  Window: {q041_dates_start} → {q041_dates_end}")
print(f"  Per-unit total PnL (raw): ${df_q041['pnl'].sum():.2f}")
print(f"  Per-contract dollar PnL (×100): ${df_q041['pnl'].sum() * SPX_MULT:,.0f}\n")

# ─── Q041 CSP BS-sensitivity — same dates, BS pricing ─────────────────────────
print(f"{'='*72}")
print(f"  Running Q041 CSP DTE30 with BS flat-vol (VIX as sigma)")
print(f"{'='*72}\n")

vix_df = fetch_vix_history(period="5y")
vix_df.index = pd.to_datetime(vix_df.index).tz_localize(None)
vix_dict = vix_df['vix'].to_dict()

import pickle as _pkl
gspc_path = '/Users/lienchen/Documents/workspace/SPX_strat/data/market_cache/yahoo__GSPC__max__1d.pkl'
with open(gspc_path, 'rb') as f:
    gspc = _pkl.load(f)
gspc.index = pd.to_datetime(gspc.index).tz_localize(None)
spx_dict = gspc['Close'].to_dict()

def get_val(d, dct, lookback=5):
    for i in range(lookback):
        t = d - pd.Timedelta(days=i)
        if t in dct:
            return dct[t]
    return None

q041_bs_pnls = []
bs_detail = []
for _, row in df_q041.iterrows():
    rd  = row['roll_date']
    exp = row['expiry']
    S_entry = get_val(rd, spx_dict)
    S_exit  = get_val(exp, spx_dict)
    vix     = get_val(rd, vix_dict)
    if S_entry is None or S_exit is None or vix is None:
        continue
    sigma = float(vix) / 100.0
    T = (exp - rd).days / 365.0
    K = find_strike_for_delta_bs(S_entry, T, sigma, 0.20)
    bs_credit  = bs_put_price(S_entry, K, T, R, sigma)   # in points
    net_prem   = bs_credit * (1 - SLIP)
    settle     = max(0.0, K - S_exit)
    cycle_pnl_pts = net_prem - settle
    cycle_pnl_dollars = cycle_pnl_pts * SPX_MULT
    q041_bs_pnls.append(cycle_pnl_dollars)
    bs_detail.append({
        'roll_date': rd, 'expiry': exp, 'S_entry': round(S_entry, 1),
        'K_bs': K, 'vix': round(vix, 1), 'bs_credit': round(bs_credit, 2),
        'actual_credit': round(row['price'], 2),
        'net_prem': round(net_prem, 2), 'settle': round(settle, 2),
        'pnl_$': round(cycle_pnl_dollars, 0),
    })

bs_df = pd.DataFrame(bs_detail)
print(f"  Q041 BS-priced cycles: {len(q041_bs_pnls)}")
print(f"  Total PnL: ${sum(q041_bs_pnls):,.0f}\n")

# ─── Build comparison table ───────────────────────────────────────────────────
print(f"{'='*72}")
print(f"  Methodology-Unified Comparison Table")
print(f"  Account: ${ACCOUNT:,.0f} | Window: {WINDOW_START} → {WINDOW_END}")
print(f"{'='*72}\n")

results = []
results.append(account_metrics(
    "/ES P1 baseline (DTE45, BS, no filter)",
    es_b_pnls, WINDOW_START, WINDOW_END, len(es_b_pnls),
))
results.append(account_metrics(
    "/ES P1 filtered (DTE45, BS, trend filter)",
    es_f_pnls, WINDOW_START, WINDOW_END, len(es_f_pnls),
))
results.append(account_metrics(
    "Q041 CSP DTE30 ACTUAL (Massive)",
    q041_actual_pnls, q041_dates_start, q041_dates_end, len(q041_actual_pnls),
))
results.append(account_metrics(
    "Q041 CSP DTE30 BS-flat (VIX sigma)",
    q041_bs_pnls, q041_dates_start, q041_dates_end, len(q041_bs_pnls),
))

cmp_df = pd.DataFrame([r for r in results if r is not None])
print(cmp_df.to_string(index=False))
print()

# ─── BS vs actual pricing — per-cycle credit comparison ───────────────────────
print(f"{'='*72}")
print(f"  Pricing methodology effect: BS vs Massive actual (per cycle)")
print(f"{'='*72}\n")

if len(bs_df) > 0:
    merged = df_q041[['roll_date', 'price', 'pnl', 'iv_entry']].merge(
        bs_df[['roll_date', 'bs_credit', 'pnl_$']], on='roll_date', how='inner',
        suffixes=('_actual', '_bs')
    )
    merged['credit_diff_pts'] = merged['bs_credit'] - merged['price']
    merged['credit_diff_pct'] = ((merged['bs_credit'] - merged['price']) / merged['price'] * 100).round(1)
    merged['actual_pnl_$'] = (merged['pnl'] * SPX_MULT).round(0)
    print("  Per-cycle credit comparison (first 10):")
    print(merged[['roll_date', 'iv_entry', 'price', 'bs_credit',
                  'credit_diff_pts', 'credit_diff_pct',
                  'actual_pnl_$', 'pnl_$']].head(10).to_string(index=False))
    print()
    print(f"  Avg actual credit:   {merged['price'].mean():.2f} pts")
    print(f"  Avg BS-flat credit:  {merged['bs_credit'].mean():.2f} pts")
    print(f"  Avg credit diff:     {merged['credit_diff_pts'].mean():+.2f} pts ({merged['credit_diff_pct'].mean():+.1f}%)")
    print()

# ─── Save outputs ─────────────────────────────────────────────────────────────
out_path = '/tmp/q041_es_methodology_comparison.pkl'
with open(out_path, 'wb') as f:
    pickle.dump({
        'comparison': cmp_df,
        'es_baseline_pnls': es_b_pnls,
        'es_filtered_pnls': es_f_pnls,
        'q041_actual_pnls': q041_actual_pnls,
        'q041_bs_pnls': q041_bs_pnls,
        'bs_detail': bs_df,
    }, f)
print(f"  Saved: {out_path}")
