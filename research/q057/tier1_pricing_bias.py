"""
Q057 Tier 1 — BS-Flat Pricing Bias Validation
==============================================

Question: For DTE≈49 SPX puts at Δ0.20, how much does BS-flat (VIX as sigma)
underestimate or overestimate the actual market premium?

Method:
  For each trading day in 2022-05 → 2026-05:
    1. Get SPX spot (S) and VIX (σ = VIX/100)
    2. Filter Massive SPX puts to DTE ∈ [42, 56]
    3. Pick best expiry (closest to DTE=49)
    4. Use BS-flat to find target K at |Δ|=0.20 (V2f convention)
    5. Find nearest actual market strike to target K
    6. Compare market close price vs BS-flat price at SAME strike
    7. bias = (actual - bs) / bs

This isolates pricing bias at the strike V2f would actually pick.

Decision threshold:
  ≤ 3%: V2f numbers robust, current caveat sufficient
  3-7%: V2f Ann ROE may be overstated by 0.1-0.2pp; SPEC review caveat
  > 7%: substantive caveat needed in SPEC-095 UI warning
"""

import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

import warnings
warnings.filterwarnings('ignore')

_ROOT = Path(__file__).resolve().parents[2]

# ─── Configuration ────────────────────────────────────────────────────────────
# Two DTE-window comparisons:
#   A: cal-DTE [42, 56] — user's spec; treats V2f "49 DTE" as calendar days
#   B: cal-DTE [64, 78] — V2f actual: 49 trading days = ~71 calendar days
# Both are valid questions; report both for transparency.
DTE_WINDOWS  = {
    'A_user_spec':   {'target': 49, 'range': (42, 56), 'desc': "[42, 56] cal-days (49 cal-day interpretation)"},
    'B_v2f_actual':  {'target': 71, 'range': (64, 78), 'desc': "[64, 78] cal-days (V2f's 49 trading-day actual)"},
}
TGT_DELTA    = 0.20
MIN_PRICE    = 0.10
RISK_FREE    = 0.045
TRADING_DAYS = 252
SPX_MULT     = 100

# ─── BS pricer using TRADING_DAYS convention (matches /ES backtest pricer.py) ─
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
    """V2f convention: BS-flat binary search."""
    lo, hi = S * 0.5, S * 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        d = abs(bs_put_delta(S, mid, dte_td, sigma))
        if abs(d - target_delta) < 0.001:
            return mid
        if d < target_delta:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

# ─── Load market data ─────────────────────────────────────────────────────────
print("Loading SPX option chain (Massive)...")
df = pd.read_parquet(_ROOT / "data" / "q041_historical" / "SPX.parquet")
df['date'] = pd.to_datetime(df['date'])
df['expiry'] = pd.to_datetime(df['expiry'])
df = df[(df['option_type'] == 'P') & (df['close'] > MIN_PRICE)].copy()
df['dte'] = (df['expiry'] - df['date']).dt.days
print(f"  Put rows: {len(df):,}")

print("Loading SPX spot (^GSPC)...")
with open(_ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl", 'rb') as f:
    gspc = pickle.load(f)
gspc.index = pd.to_datetime(gspc.index).tz_localize(None)
spx_dict = gspc['Close'].to_dict()

print("Loading VIX...")
with open(_ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl", 'rb') as f:
    vix_df = pickle.load(f)
vix_df.index = pd.to_datetime(vix_df.index).tz_localize(None)
vix_dict = vix_df['Close'].to_dict()

# Trading days in put data
trading_days = sorted(df['date'].unique())
print(f"  Trading days with put data: {len(trading_days)}")
print(f"  Range: {trading_days[0].date()} → {trading_days[-1].date()}")

# Group puts by date for fast lookup
puts_by_date = {d: g for d, g in df.groupby('date')}

# Pricing context: needs to convert calendar DTE → trading-day DTE.
# Massive 'dte' field is calendar days. BS pricer uses trading days (T=dte/252).
# For consistent V2f-convention comparison, keep dte_td = calendar_dte × 252/365.
# Alternative: use calendar dte / 365. Both conventions valid; matters only for
# absolute price level, not for bias % which is what we measure.
# /ES backtest uses dte_in_loop_steps decremented per trading day, so its "dte"
# IS already trading-day-counted. We replicate that:
def calendar_to_trading_dte(cal_dte):
    return cal_dte * 252 / 365

# ─── Build per-day comparison for each DTE window ────────────────────────────
from scipy.optimize import brentq

def run_window(label, target_dte, dte_lo, dte_hi):
    print(f"\nComputing window {label} (target {target_dte}, range [{dte_lo}, {dte_hi}])...")
    records = []
    n_skip_no_expiry = 0
    for date in trading_days:
        spx = spx_dict.get(date)
        vix = vix_dict.get(date)
        if spx is None or vix is None:
            continue
        sigma = vix / 100.0
        chain = puts_by_date[date]
        valid = chain[(chain['dte'] >= dte_lo) & (chain['dte'] <= dte_hi)]
        if len(valid) == 0:
            n_skip_no_expiry += 1
            continue
        valid = valid.copy()
        valid['dte_distance'] = (valid['dte'] - target_dte).abs()
        best_dte = valid.loc[valid['dte_distance'].idxmin(), 'dte']
        sub = valid[valid['dte'] == best_dte]

        dte_td = calendar_to_trading_dte(best_dte)
        K_target = find_strike_for_delta(spx, dte_td, sigma, TGT_DELTA)
        strikes = sub['strike'].values
        K_market = strikes[np.argmin(np.abs(strikes - K_target))]
        market_row = sub[sub['strike'] == K_market].iloc[0]
        actual_price = market_row['close']
        bs_price = bs_put_price(spx, K_market, dte_td, sigma)
        if bs_price <= 0:
            continue
        bias_pct = (actual_price - bs_price) / bs_price * 100
        try:
            market_iv = brentq(lambda s: bs_put_price(spx, K_market, dte_td, s) - actual_price,
                               0.01, 5.0, maxiter=50)
        except Exception:
            market_iv = np.nan
        records.append({
            'date': date, 'year': date.year, 'spx': round(spx, 2), 'vix': round(vix, 2),
            'cal_dte': best_dte, 'K_target_bs': round(K_target, 1),
            'K_market': round(K_market, 1),
            'actual_price': round(actual_price, 2), 'bs_price': round(bs_price, 2),
            'bias_pct': round(bias_pct, 2),
            'market_iv': round(market_iv * 100, 2) if not np.isnan(market_iv) else np.nan,
            'iv_skew_pp': round((market_iv * 100 - vix), 2) if not np.isnan(market_iv) else np.nan,
        })
    print(f"  records: {len(records)}, skipped: {n_skip_no_expiry}")
    return pd.DataFrame(records)

window_results = {}
for label, cfg in DTE_WINDOWS.items():
    window_results[label] = run_window(label, cfg['target'], cfg['range'][0], cfg['range'][1])

# Use window A as primary for backwards-compat
result_df = window_results['A_user_spec']

# ─── Aggregate analysis: BOTH windows side by side ────────────────────────────
print(f"\n{'='*80}")
print(f"  Q057 Tier 1 — BS-Flat Pricing Bias Analysis")
print(f"  Δ=0.20 SPX puts, 2022-05 → 2026-05")
print(f"{'='*80}\n")

print(f"\n  ── WINDOW COMPARISON: cal-DTE [42,56] vs cal-DTE [64,78] ──\n")
print(f"  {'Metric':<25}  {'A: [42,56]':>14}  {'B: [64,78] V2f-actual':>22}")
print(f"  {'-'*25}  {'-'*14}  {'-'*22}")
for stat_label, fn in [
    ('n samples', lambda d: len(d)),
    ('mean bias %', lambda d: f"{d['bias_pct'].mean():+.2f}"),
    ('median bias %', lambda d: f"{d['bias_pct'].median():+.2f}"),
    ('p25 bias %', lambda d: f"{d['bias_pct'].quantile(0.25):+.2f}"),
    ('p75 bias %', lambda d: f"{d['bias_pct'].quantile(0.75):+.2f}"),
    ('p95 bias %', lambda d: f"{d['bias_pct'].quantile(0.95):+.2f}"),
    ('median market IV %', lambda d: f"{d['market_iv'].median():.2f}"),
    ('median IV skew pp', lambda d: f"{d['iv_skew_pp'].median():+.2f}"),
]:
    a_val = fn(window_results['A_user_spec'])
    b_val = fn(window_results['B_v2f_actual'])
    print(f"  {stat_label:<25}  {str(a_val):>14}  {str(b_val):>22}")

# Switch to Window A (user's spec) for full analysis below
print(f"\n  ── Window A: cal-DTE [42, 56] (user spec) — Full Analysis ──\n")

print(f"  Total daily comparisons: {len(result_df)}")
print()
print(f"  ── Full Sample (bias = (actual - bs) / bs × 100%) ──")
b = result_df['bias_pct']
print(f"    Mean:     {b.mean():+.2f}%")
print(f"    Median:   {b.median():+.2f}%")
print(f"    p25:      {b.quantile(0.25):+.2f}%")
print(f"    p75:      {b.quantile(0.75):+.2f}%")
print(f"    p5:       {b.quantile(0.05):+.2f}%")
print(f"    p95:      {b.quantile(0.95):+.2f}%")
print(f"    Min:      {b.min():+.2f}%")
print(f"    Max:      {b.max():+.2f}%")

# ─── Yearly breakdown ────────────────────────────────────────────────────────
print(f"\n  ── By Year ──")
print(f"  {'Year':>6}  {'n':>5}  {'mean %':>8}  {'median %':>10}  {'p25 %':>8}  {'p75 %':>8}  {'p95 %':>8}")
for yr, g in result_df.groupby('year'):
    print(f"  {yr:>6}  {len(g):>5}  {g['bias_pct'].mean():>+7.2f}%  "
          f"{g['bias_pct'].median():>+9.2f}%  {g['bias_pct'].quantile(0.25):>+7.2f}%  "
          f"{g['bias_pct'].quantile(0.75):>+7.2f}%  {g['bias_pct'].quantile(0.95):>+7.2f}%")

# ─── 2022 grinding window deeper analysis ────────────────────────────────────
g2022 = result_df[result_df['year'] == 2022]
print(f"\n  ── 2022 Grinding Sub-Window Detail ──")
if len(g2022) > 0:
    print(f"    n = {len(g2022)} days (covers {g2022['date'].min().date()} → {g2022['date'].max().date()})")
    print(f"    Median bias: {g2022['bias_pct'].median():+.2f}%")
    print(f"    Mean bias:   {g2022['bias_pct'].mean():+.2f}%")
    # Months breakdown
    g2022 = g2022.copy()
    g2022['month'] = g2022['date'].dt.month
    print(f"\n    By month:")
    print(f"    {'Mon':>3}  {'n':>3}  {'med bias':>10}  {'med VIX':>9}  {'med IV skew':>12}")
    for mo, gm in g2022.groupby('month'):
        skew = gm['iv_skew_pp'].median() if 'iv_skew_pp' in gm.columns else np.nan
        print(f"    {mo:>3}  {len(gm):>3}  {gm['bias_pct'].median():>+9.2f}%  "
              f"{gm['vix'].median():>9.1f}  {skew:>+11.2f}pp")

# ─── IV skew interpretation ──────────────────────────────────────────────────
print(f"\n  ── Implied Vol Skew (market IV at Δ=0.20 vs VIX flat) ──")
iv_skew = result_df['iv_skew_pp'].dropna()
print(f"    Mean skew:   {iv_skew.mean():+.2f}pp (market IV − VIX)")
print(f"    Median skew: {iv_skew.median():+.2f}pp")
print(f"    Note: positive skew = OTM puts price higher IV than VIX (typical SPX skew)")

# ─── Correlation with VIX ────────────────────────────────────────────────────
print(f"\n  ── Bias Conditioning on VIX Level ──")
result_df['vix_bucket'] = pd.cut(result_df['vix'],
    bins=[0, 15, 20, 25, 30, 100],
    labels=['<15', '15-20', '20-25', '25-30', '≥30'])
print(f"  {'VIX bucket':>12}  {'n':>5}  {'med bias':>10}  {'mean bias':>10}")
for bucket, g in result_df.groupby('vix_bucket', observed=True):
    print(f"  {str(bucket):>12}  {len(g):>5}  {g['bias_pct'].median():>+9.2f}%  "
          f"{g['bias_pct'].mean():>+9.2f}%")

# ─── Verdict by threshold ────────────────────────────────────────────────────
median_bias = result_df['bias_pct'].median()
median_2022 = g2022['bias_pct'].median() if len(g2022) > 0 else np.nan
abs_median = abs(median_bias)
abs_2022 = abs(median_2022) if not np.isnan(median_2022) else 0

print(f"\n{'='*80}")
print(f"  VERDICT")
print(f"{'='*80}\n")
print(f"  Full-sample median bias: {median_bias:+.2f}%")
print(f"  2022 sub-window median:  {median_2022:+.2f}%")
print()
worst = max(abs_median, abs_2022)
if worst <= 3:
    verdict = "≤ 3% — V2f numbers ROBUST, current caveat sufficient"
elif worst <= 7:
    verdict = f"3-7% — V2f Ann ROE may be biased by ~0.1-0.2pp; flag in SPEC review"
else:
    verdict = f"> 7% — SUBSTANTIVE caveat needed; upgrade SPEC-095 UI warning"
print(f"  Threshold check: {verdict}")

# Bias direction interpretation
if median_bias > 0:
    direction = "BS UNDERESTIMATES market premium (skew effect — actual credit higher)"
else:
    direction = "BS OVERESTIMATES market premium"
print(f"\n  Direction: {direction}")

# Quantitative impact estimate on V2f Ann ROE
print(f"\n  Quantitative impact estimate on V2f:")
print(f"    V2f reported Ann ROE (BS-flat): +2.67%")
if median_bias > 0:
    print(f"    Real-data adjusted (median bias {median_bias:+.2f}%): roughly")
    print(f"    +2.67% × (1 + {median_bias/100:.4f}) ≈ {2.67 * (1 + median_bias/100):+.2f}% (if all premium scales proportionally)")
    print(f"    BUT: stop-loss settlement also scales; net effect is approximately")
    print(f"    proportional to (credit - settlement). Real ROE direction same as bias direction.")
else:
    print(f"    Negative bias: BS overstates premium → V2f Ann ROE may be optimistic")
    print(f"    Real-adjusted estimate: ~{2.67 * (1 + median_bias/100):+.2f}%")

# ─── Save ────────────────────────────────────────────────────────────────────
out_dir = _ROOT / "research" / "q057"
out_dir.mkdir(exist_ok=True)
out_pkl = out_dir / "tier1_pricing_bias_results.pkl"
with open(out_pkl, 'wb') as f:
    pickle.dump({
        'window_A': window_results['A_user_spec'],
        'window_B': window_results['B_v2f_actual'],
        'verdict': verdict,
        'median_bias_A': median_bias,
        'median_bias_B': window_results['B_v2f_actual']['bias_pct'].median(),
        'median_bias_2022_A': median_2022,
    }, f)
print(f"\n  Saved: {out_pkl}")

out_csv_a = out_dir / "tier1_pricing_bias_window_A.csv"
window_results['A_user_spec'].to_csv(out_csv_a, index=False)
print(f"  Saved: {out_csv_a}")

out_csv_b = out_dir / "tier1_pricing_bias_window_B.csv"
window_results['B_v2f_actual'].to_csv(out_csv_b, index=False)
print(f"  Saved: {out_csv_b}")
