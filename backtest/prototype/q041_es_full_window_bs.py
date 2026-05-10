"""
Q041 CSP DTE30 vs /ES P1 DTE45 — Full 26-Year BS-Flat Comparison
=================================================================

Premise: both backtests are synthetic when using BS-flat-vol with VIX as sigma
on SPX historical data. So extending Q041 to /ES's 26-year window is a fair
apples-to-apples comparison — same pricing methodology, same data, only the
strategy parameters (DTE, stop-loss design) differ.

Both:
  - SPX as underlying (^GSPC from yahoo)
  - VIX as flat sigma (^VIX from yahoo)
  - BS theoretical pricing
  - Δ0.20 short put
  - $500k account, 1 contract per slot
  - SLIP=3% on entry credit (Q041 convention; /ES has no slippage)

Strategy differences (the only things being tested):
  - Q041: DTE30, hold-to-expiry, monthly non-overlapping roll
  - /ES:  DTE45, STOP_MULT=3.0 mark stop, profit_target=10% mark, gamma_dte=5
"""

import pickle
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import calendar
from scipy.stats import norm

import warnings
warnings.filterwarnings('ignore')

_ROOT = Path(__file__).resolve().parents[2]
_ES_FILE = _ROOT / "research" / "strategies" / "ES_puts" / "backtest.py"
import importlib.util
spec = importlib.util.spec_from_file_location("es_backtest_mod", _ES_FILE)
es_backtest_mod = importlib.util.module_from_spec(spec)
sys.modules["es_backtest_mod"] = es_backtest_mod
spec.loader.exec_module(es_backtest_mod)
run_phase1 = es_backtest_mod.run_phase1

# ─── Configuration ────────────────────────────────────────────────────────────
WINDOW_START = "2000-01-01"
WINDOW_END   = "2026-04-17"
ACCOUNT      = 500_000.0
SPX_MULT     = 100
SLIP         = 0.03
R            = 0.045
TGT_DELTA    = 0.20
DTE_TGT      = 30
DTE_WIN      = 10

# ─── BS helpers ───────────────────────────────────────────────────────────────
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

def third_friday(year, month):
    cal = calendar.monthcalendar(year, month)
    fridays = [w[4] for w in cal if w[4] != 0]
    return pd.Timestamp(year, month, fridays[2])

# ─── Load SPX + VIX (same source as /ES backtest) ─────────────────────────────
print("Loading SPX + VIX history...")
gspc_path = _ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
with open(gspc_path, 'rb') as f:
    gspc = pickle.load(f)
gspc.index = pd.to_datetime(gspc.index).tz_localize(None)
spx_dict = gspc['Close'].to_dict()

vix_path = _ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
with open(vix_path, 'rb') as f:
    vix_df = pickle.load(f)
vix_df.index = pd.to_datetime(vix_df.index).tz_localize(None)
vix_dict = vix_df['Close'].to_dict()

# Window check
spx_dates = sorted(spx_dict.keys())
vix_dates = sorted(vix_dict.keys())
print(f"  SPX data range: {spx_dates[0].date()} → {spx_dates[-1].date()}")
print(f"  VIX data range: {vix_dates[0].date()} → {vix_dates[-1].date()}")

def get_val(d, dct, lookback=5):
    for i in range(lookback):
        t = d - pd.Timedelta(days=i)
        if t in dct:
            return dct[t]
    return None

# ─── Run Q041 CSP DTE30 BS-flat over 2000–2026 ────────────────────────────────
print(f"\nRunning Q041 CSP DTE30 BS-flat over {WINDOW_START} → {WINDOW_END}...")

START = pd.Timestamp(WINDOW_START)
END   = pd.Timestamp(WINDOW_END)

roll_dates_all = []
for yr in range(START.year, END.year + 1):
    for mo in range(1, 13):
        tf = third_friday(yr, mo)
        if START <= tf <= END:
            roll_dates_all.append(tf)

cycles = []
prev_expiry = None
for rd in roll_dates_all:
    if prev_expiry is not None and rd < prev_expiry:
        continue
    # Find DTE30 expiry
    target_exp = rd + pd.Timedelta(days=DTE_TGT)
    # Use third-Friday-of-following-month as the expiry (closest to DTE30)
    exp = third_friday(target_exp.year, target_exp.month) if target_exp.month <= 12 else third_friday(target_exp.year + 1, 1)
    act_dte = (exp - rd).days
    if not (DTE_TGT - DTE_WIN <= act_dte <= DTE_TGT + DTE_WIN):
        continue

    S_entry = get_val(rd, spx_dict)
    S_exit  = get_val(exp, spx_dict)
    vix_e   = get_val(rd, vix_dict)
    if S_entry is None or S_exit is None or vix_e is None:
        continue

    sigma = float(vix_e) / 100.0
    T = act_dte / 365.0
    K = find_strike_for_delta_bs(S_entry, T, sigma, TGT_DELTA)
    bs_credit = bs_put_price(S_entry, K, T, R, sigma)   # in points
    if bs_credit < 0.10:   # min price filter, same as Q041 P2-1
        continue
    net_prem  = bs_credit * (1 - SLIP)
    settle    = max(0.0, K - S_exit)
    cycle_pnl_pts = net_prem - settle
    cycle_pnl_dollars = cycle_pnl_pts * SPX_MULT

    cycles.append({
        'roll_date': rd, 'expiry': exp, 'act_dte': act_dte,
        'S_entry': round(S_entry, 1), 'K': K,
        'pct_otm': round((S_entry - K) / S_entry * 100, 1),
        'vix_entry': round(vix_e, 1),
        'bs_credit_pts': round(bs_credit, 2),
        'net_prem_pts': round(net_prem, 2),
        'S_exit': round(S_exit, 1),
        'settle_pts': round(settle, 2),
        'pnl_pts': round(cycle_pnl_pts, 2),
        'pnl_$': round(cycle_pnl_dollars, 0),
        'hit': S_exit < K,
        'year': rd.year,
    })
    prev_expiry = exp

q041_df = pd.DataFrame(cycles)
print(f"  Total cycles: {len(q041_df)}")
print(f"  Total PnL: ${q041_df['pnl_$'].sum():,.0f}")

# ─── Run /ES P1 baseline + filtered over same 26-year window ──────────────────
print(f"\nRunning /ES P1 baseline + filtered over {WINDOW_START} → {WINDOW_END}...")
es_baseline = run_phase1(mode="baseline", start_date=WINDOW_START, end_date=WINDOW_END)
es_filtered = run_phase1(mode="filtered", start_date=WINDOW_START, end_date=WINDOW_END)

es_b_pnls = [t.pnl for t in es_baseline.trades]
es_f_pnls = [t.pnl for t in es_filtered.trades]
print(f"  /ES baseline trades: {len(es_b_pnls)}, total PnL: ${sum(es_b_pnls):,.0f}")
print(f"  /ES filtered trades: {len(es_f_pnls)}, total PnL: ${sum(es_f_pnls):,.0f}")

# ─── Account-level metrics framework ──────────────────────────────────────────
def account_metrics(label, dollar_pnls, t0, t1, account=ACCOUNT):
    arr = np.array(dollar_pnls, dtype=float)
    if len(arr) == 0:
        return None
    total = arr.sum()
    years = (pd.Timestamp(t1) - pd.Timestamp(t0)).days / 365.25
    cum_ret = total / account
    ann_ret = (1.0 + cum_ret) ** (1.0 / years) - 1.0 if cum_ret > -1 else float('nan')
    wr = float((arr > 0).mean())
    worst = float(arr.min())
    best = float(arr.max())
    mean = float(arr.mean())
    std = float(arr.std()) if len(arr) > 1 else 0.0
    sharpe_per_trade = mean / std if std > 0 else 0.0
    freq = len(arr) / years
    sharpe_ann = sharpe_per_trade * np.sqrt(freq)
    # Equity curve & MaxDD on $500k account
    eq = ACCOUNT + np.cumsum(arr)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    mdd = float(dd.min())
    return {
        'label': label, 'n': len(arr), 'years': round(years, 1),
        'total_pnl_$': round(total, 0),
        'ann_roe_%': round(ann_ret * 100, 2),
        'wr_%': round(wr * 100, 1),
        'worst_$': round(worst, 0),
        'mdd_%': round(mdd * 100, 1),
        'sharpe_ann': round(sharpe_ann, 2),
    }

# ─── Per-year breakdown (key for stress-period interpretation) ────────────────
def annual_breakdown(label, df_pnl_year):
    """df_pnl_year: DataFrame with columns 'pnl_$' and 'year'"""
    yr_grp = df_pnl_year.groupby('year').agg(
        n=('pnl_$', 'count'),
        total=('pnl_$', 'sum'),
        worst=('pnl_$', 'min'),
        wr=('pnl_$', lambda x: (x > 0).mean()),
    ).round(0)
    yr_grp['wr_%'] = (yr_grp['wr'] * 100).round(0).astype(int)
    yr_grp = yr_grp.drop(columns=['wr'])
    return yr_grp

# Build per-year DataFrames
q041_yearly = q041_df[['year', 'pnl_$']].copy()
es_b_yearly = pd.DataFrame([
    {'year': pd.Timestamp(t.exit_date).year, 'pnl_$': t.pnl} for t in es_baseline.trades
])
es_f_yearly = pd.DataFrame([
    {'year': pd.Timestamp(t.exit_date).year, 'pnl_$': t.pnl} for t in es_filtered.trades
])

# ─── Build comparison ─────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print(f"  Methodology-Symmetric Comparison: 26-Year BS-Flat Window")
print(f"  {WINDOW_START} → {WINDOW_END} | $500k account | Δ0.20 | BS-flat (VIX as sigma)")
print(f"{'='*80}\n")

results = [
    account_metrics("Q041 CSP DTE30 BS-flat (hold to expiry)",
                    q041_df['pnl_$'].tolist(), WINDOW_START, WINDOW_END),
    account_metrics("/ES P1 DTE45 BS-flat (baseline, no filter)",
                    es_b_pnls, WINDOW_START, WINDOW_END),
    account_metrics("/ES P1 DTE45 BS-flat (filtered, trend on)",
                    es_f_pnls, WINDOW_START, WINDOW_END),
]
cmp_df = pd.DataFrame([r for r in results if r is not None])
print(cmp_df.to_string(index=False))

# ─── Stress-period focus: 2008, 2020, 2022 ────────────────────────────────────
print(f"\n{'='*80}")
print(f"  Stress-Period Annual Breakdown (key tail events)")
print(f"{'='*80}\n")

stress_years = [2008, 2009, 2020, 2022]
print("\n  Q041 CSP DTE30 (hold-to-expiry):")
q041_yr = annual_breakdown("Q041", q041_yearly)
print(q041_yr[q041_yr.index.isin(stress_years)].to_string())
print(f"\n  Full annual breakdown (Q041):")
print(q041_yr.to_string())

print("\n  /ES P1 baseline (DTE45, stop-loss):")
es_b_yr = annual_breakdown("/ES baseline", es_b_yearly)
print(es_b_yr[es_b_yr.index.isin(stress_years)].to_string())

print("\n  /ES P1 filtered (DTE45, stop-loss + trend filter):")
es_f_yr = annual_breakdown("/ES filtered", es_f_yearly)
print(es_f_yr[es_f_yr.index.isin(stress_years)].to_string())

# ─── Save ─────────────────────────────────────────────────────────────────────
out_path = '/tmp/q041_es_full_window_bs.pkl'
with open(out_path, 'wb') as f:
    pickle.dump({
        'q041_cycles': q041_df,
        'es_b_pnls': es_b_pnls,
        'es_f_pnls': es_f_pnls,
        'comparison': cmp_df,
        'q041_annual': q041_yr,
        'es_b_annual': es_b_yr,
        'es_f_annual': es_f_yr,
    }, f)
print(f"\n  Saved: {out_path}")
