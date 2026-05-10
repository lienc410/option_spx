"""
True Ladder vs Fixed-Slot Ladder — /ES Backtest Reimplementation
==================================================================

Tests whether the current /ES P2 implementation matches the spec_initial.md
design intent, which calls for:
  - Weekly entry of a single 49-DTE short put
  - Each position aged through 49 → 21 DTE
  - Exit at 21 DTE (or earlier on stop/profit)

Current /ES P2 implementation (research/strategies/ES_puts/backtest.py:529-549)
opens FIVE independent fixed-DTE position streams, not a single weekly cadence.
This script reimplements the true ladder and compares against the existing
P2 baseline on the same 26-year BS-flat synthetic dataset.

Variants tested:
  V0: current P2 baseline (fixed slots) — re-run for reference
  V1: true ladder, entry=49, exit_at_dte=21, STOP=3.0     ← matches spec intent
  V2: true ladder, entry=49, exit_at_dte=21, no stop      ← hold to exit_dte
  V3: true ladder, entry=49, hold-to-expiry (exit_at=5), STOP=3.0
  V4: true ladder, entry=45, exit_at_dte=21, STOP=3.0     ← shorter entry DTE

All metrics on $500k account, Δ0.20, BS-flat (VIX as sigma), 2000-2026.
"""

import pickle
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

import warnings
warnings.filterwarnings('ignore')

_ROOT = Path(__file__).resolve().parents[2]
_ES_FILE = _ROOT / "research" / "strategies" / "ES_puts" / "backtest.py"
import importlib.util
spec = importlib.util.spec_from_file_location("es_backtest_mod", _ES_FILE)
es_mod = importlib.util.module_from_spec(spec)
sys.modules["es_backtest_mod"] = es_mod
spec.loader.exec_module(es_mod)

# ─── Configuration ────────────────────────────────────────────────────────────
WINDOW_START = "2000-01-01"
WINDOW_END   = "2026-04-17"
ACCOUNT      = 500_000.0
SPX_MULT     = 100
TARGET_DELTA = 0.20
PROFIT_FRAC  = 0.10           # close at <=10% of entry premium (= +90% captured)
TRADING_DAYS = 252
RISK_FREE    = 0.045
GAMMA_DTE    = 5              # absolute floor; never hold beyond this
WEEKLY_TD    = 5              # 5 trading days ≈ 1 week

# ─── BS pricer (using TRADING_DAYS convention to match /ES backtest) ──────────
def bs_put_price(S, K, dte_td, sigma):
    """Put price; dte_td is trading days, sigma is annualised vol."""
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
def run_true_ladder(
    sim_df: pd.DataFrame,
    entry_dte_td: int,
    exit_at_dte_td: int,
    stop_mult: float | None,
    entry_cadence_td: int = WEEKLY_TD,
    profit_frac: float = PROFIT_FRAC,
    label: str = "true_ladder",
) -> pd.DataFrame:
    """
    Simulate a true rolling ladder:
      - Every `entry_cadence_td` trading days, open a new position at `entry_dte_td`.
      - Each position aged daily; exits when:
          * DTE drops to `exit_at_dte_td` (parameter), OR
          * mark >= entry_premium * stop_mult (if stop_mult is not None), OR
          * mark <= entry_premium * profit_frac, OR
          * DTE <= GAMMA_DTE (absolute floor)

    Returns DataFrame of closed trades with PnL in dollars.
    """
    # Active positions: list of dicts
    positions = []
    trades = []
    days_since_entry = entry_cadence_td  # ensure entry on day 0

    for i, (date, row) in enumerate(sim_df.iterrows()):
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sigma = vix / 100.0
        dstr  = date.strftime("%Y-%m-%d")

        # Manage existing positions: decrement DTE, check exits
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
                pnl_pts = (pos['entry_prem'] - cur_val)
                trades.append({
                    'entry_date': pos['entry_date'],
                    'exit_date': dstr,
                    'entry_dte': pos['entry_dte'],
                    'exit_dte_remaining': pos['dte'],
                    'days_held': pos['entry_dte'] - pos['dte'],
                    'K': pos['K'],
                    'S_entry': pos['S_entry'],
                    'S_exit': spx,
                    'vix_entry': pos['vix_entry'],
                    'entry_prem': pos['entry_prem'],
                    'exit_val': cur_val,
                    'exit_reason': reason,
                    'pnl_pts': pnl_pts,
                    'pnl_$': pnl_pts * SPX_MULT,
                    'year': pd.Timestamp(pos['entry_date']).year,
                })
            else:
                still_open.append(pos)
        positions = still_open

        # Entry: every entry_cadence_td trading days
        days_since_entry += 1
        if days_since_entry >= entry_cadence_td:
            # Need warmup
            if i >= 64:   # WARMUP_DAYS from /ES backtest
                K = find_strike_for_delta(spx, entry_dte_td, sigma, TARGET_DELTA)
                entry_prem = bs_put_price(spx, K, entry_dte_td, sigma)
                if entry_prem > 0.5:
                    positions.append({
                        'entry_date': dstr,
                        'entry_dte': entry_dte_td,
                        'dte': entry_dte_td,
                        'K': K,
                        'S_entry': spx,
                        'vix_entry': vix,
                        'entry_prem': entry_prem,
                        'stop_prem': entry_prem * stop_mult if stop_mult else None,
                        'profit_prem': entry_prem * profit_frac,
                    })
                    days_since_entry = 0

    # Force-close any remaining positions at end of window for fair accounting
    if len(positions) > 0:
        last_row = sim_df.iloc[-1]
        last_spx = float(last_row["spx"])
        last_vix = float(last_row["vix"])
        last_sigma = last_vix / 100.0
        last_date = sim_df.index[-1].strftime("%Y-%m-%d")
        for pos in positions:
            cur_val = bs_put_price(last_spx, pos['K'], max(pos['dte'], 0), last_sigma)
            pnl_pts = (pos['entry_prem'] - cur_val)
            trades.append({
                'entry_date': pos['entry_date'],
                'exit_date': last_date,
                'entry_dte': pos['entry_dte'],
                'exit_dte_remaining': pos['dte'],
                'days_held': pos['entry_dte'] - pos['dte'],
                'K': pos['K'],
                'S_entry': pos['S_entry'],
                'S_exit': last_spx,
                'vix_entry': pos['vix_entry'],
                'entry_prem': pos['entry_prem'],
                'exit_val': cur_val,
                'exit_reason': 'end_of_window',
                'pnl_pts': pnl_pts,
                'pnl_$': pnl_pts * SPX_MULT,
                'year': pd.Timestamp(pos['entry_date']).year,
            })

    df = pd.DataFrame(trades)
    df.attrs['label'] = label
    return df

# ─── Load market data via /ES backtest's loader ───────────────────────────────
print("Loading SPX + VIX history (via /ES backtest loader)...")
data, full_spx = es_mod._load_data()
sim_df = data[(data.index >= pd.Timestamp(WINDOW_START)) & (data.index <= pd.Timestamp(WINDOW_END))]
print(f"  Trading days: {len(sim_df)}")
print(f"  Range: {sim_df.index[0].date()} → {sim_df.index[-1].date()}")

# ─── Run all variants ─────────────────────────────────────────────────────────
print("\nRunning variants...")

variants = []

print("  V1: true ladder, entry=49, exit_at_dte=21, STOP=3.0...")
df_v1 = run_true_ladder(sim_df, entry_dte_td=49, exit_at_dte_td=21,
                        stop_mult=3.0, label="V1_true_49_21_stop3")
variants.append(df_v1)

print("  V2: true ladder, entry=49, exit_at_dte=21, no stop...")
df_v2 = run_true_ladder(sim_df, entry_dte_td=49, exit_at_dte_td=21,
                        stop_mult=None, label="V2_true_49_21_nostop")
variants.append(df_v2)

print("  V3: true ladder, entry=49, hold-to-gamma_floor=5, STOP=3.0...")
df_v3 = run_true_ladder(sim_df, entry_dte_td=49, exit_at_dte_td=GAMMA_DTE,
                        stop_mult=3.0, label="V3_true_49_5_stop3")
variants.append(df_v3)

print("  V4: true ladder, entry=45, exit_at_dte=21, STOP=3.0...")
df_v4 = run_true_ladder(sim_df, entry_dte_td=45, exit_at_dte_td=21,
                        stop_mult=3.0, label="V4_true_45_21_stop3")
variants.append(df_v4)

print("  V0: current /ES P2 baseline (fixed slots) — for reference...")
v0_result = es_mod.run_phase2(mode="baseline", start_date=WINDOW_START, end_date=WINDOW_END)
v0_pnls = [t.pnl for t in v0_result.trades]
v0_dates = [t.entry_date for t in v0_result.trades]
df_v0 = pd.DataFrame({
    'entry_date': v0_dates,
    'pnl_$': v0_pnls,
    'year': [pd.Timestamp(d).year for d in v0_dates],
})
df_v0.attrs['label'] = "V0_current_P2_fixed_slots"
variants.insert(0, df_v0)

# ─── Metrics ──────────────────────────────────────────────────────────────────
def metrics(df, label):
    arr = df['pnl_$'].values
    n = len(arr)
    if n == 0:
        return None
    total = arr.sum()
    years = (pd.Timestamp(WINDOW_END) - pd.Timestamp(WINDOW_START)).days / 365.25
    cum_ret = total / ACCOUNT
    ann_ret = (1.0 + cum_ret) ** (1.0 / years) - 1.0 if cum_ret > -1 else float('nan')
    wr = float((arr > 0).mean())
    worst = float(arr.min())
    best = float(arr.max())
    mean = float(arr.mean())
    std = float(arr.std()) if n > 1 else 0.0
    sharpe_per = mean / std if std > 0 else 0.0
    freq = n / years
    sharpe_ann = sharpe_per * np.sqrt(freq)
    eq = ACCOUNT + np.cumsum(arr)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    mdd = float(dd.min())
    return {
        'label': label, 'n': n,
        'total_$': round(total, 0),
        'ann_roe_%': round(ann_ret * 100, 2),
        'wr_%': round(wr * 100, 1),
        'worst_$': round(worst, 0),
        'best_$': round(best, 0),
        'mdd_%': round(mdd * 100, 1),
        'sharpe_ann': round(sharpe_ann, 2),
        'mean_$': round(mean, 0),
    }

print(f"\n{'='*88}")
print(f"  Comparison: True Ladder vs Fixed-Slot Ladder ({WINDOW_START} → {WINDOW_END})")
print(f"{'='*88}")
results = [metrics(df, df.attrs['label']) for df in variants]
cmp = pd.DataFrame([r for r in results if r is not None])
print(cmp.to_string(index=False))

# ─── Annual breakdown for the best variant + V0 ───────────────────────────────
def annual(df, label):
    g = df.groupby('year')
    out = pd.DataFrame({
        'n': g['pnl_$'].count(),
        'total_$': g['pnl_$'].sum().round(0),
        'worst_$': g['pnl_$'].min().round(0),
        'wins': g['pnl_$'].apply(lambda x: int((x > 0).sum())),
    })
    out['wr_%'] = (out['wins'] / out['n'] * 100).round(0).astype(int)
    out = out.drop(columns=['wins'])
    return out

# Identify best variant by Ann ROE
best_idx = cmp['ann_roe_%'].idxmax()
best_label = cmp.iloc[best_idx]['label']
print(f"\n  Best variant by Ann ROE: {best_label}")

# Compare best vs V0 in stress years
print(f"\n  Stress-year comparison (V0 baseline vs {best_label}):")
v0_yr = annual(variants[0], "V0")
best_df = next(d for d in variants if d.attrs['label'] == best_label)
best_yr = annual(best_df, best_label)
stress_yrs = [2008, 2018, 2020, 2022]
for yr in stress_yrs:
    v0_row = v0_yr.loc[yr] if yr in v0_yr.index else None
    bx_row = best_yr.loc[yr] if yr in best_yr.index else None
    print(f"\n  {yr}:")
    if v0_row is not None:
        print(f"    V0:    n={v0_row['n']:>3}  total=${v0_row['total_$']:>+10,.0f}  worst=${v0_row['worst_$']:>+10,.0f}  WR={v0_row['wr_%']:>2}%")
    if bx_row is not None:
        print(f"    {best_label}: n={bx_row['n']:>3}  total=${bx_row['total_$']:>+10,.0f}  worst=${bx_row['worst_$']:>+10,.0f}  WR={bx_row['wr_%']:>2}%")

# ─── Diagnostic: exit reason distribution for true-ladder variants ────────────
print(f"\n{'='*88}")
print(f"  Exit-Reason Distribution (true-ladder variants only)")
print(f"{'='*88}")
for df in variants[1:]:   # skip V0 (different format)
    if 'exit_reason' not in df.columns:
        continue
    label = df.attrs['label']
    rc = df['exit_reason'].value_counts()
    print(f"\n  {label}:")
    print(rc.to_string())

# ─── Save ─────────────────────────────────────────────────────────────────────
out_path = '/tmp/q041_es_true_ladder.pkl'
with open(out_path, 'wb') as f:
    pickle.dump({
        'comparison': cmp,
        'variants': {df.attrs['label']: df for df in variants},
        'window': (WINDOW_START, WINDOW_END),
    }, f)
print(f"\n  Saved: {out_path}")
