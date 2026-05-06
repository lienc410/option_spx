"""
Q041 Phase 2 — P2-2: IV Regime 年度效应分析
============================================
问题：D4 发现 2024 财报铁鹰溢价≈0；是否由 IV regime（VIX 水平）驱动？

分析步骤：
1. 加载 D4 IC T-3 w=1.0× ex-META 结果，附加入场日 VIX
2. 逐年：VIX 水平 vs 隐含移动溢价 vs IC PnL
3. VIX 分位数 → IC 结果的预测力
4. 逐标的年度效应（找哪个股票主导了年度不稳定）
5. 隐含移动溢价的年度统计显著性（t-test per year）
"""

import pandas as pd
import numpy as np
import pickle
from scipy.stats import ttest_1samp, pearsonr
import warnings
warnings.filterwarnings('ignore')

# ─── Load D4 results ──────────────────────────────────────────────────────────
with open('/tmp/d4_earnings_results.pkl', 'rb') as f:
    df_all = pickle.load(f)

df_ic = df_all[
    (df_all['spread_type'] == 'condor') &
    (df_all['entry_lag']   == 3) &
    (df_all['width_mult']  == 1.0) &
    (df_all['symbol']      != 'META')
].copy()

print(f"IC T-3 w=1.0x ex-META: {len(df_ic)} events, {df_ic['symbol'].nunique()} symbols")

# ─── Load VIX ─────────────────────────────────────────────────────────────────
with open('data/market_cache/yahoo__VIX__max__1d.pkl', 'rb') as f:
    vix_df = pickle.load(f)
vix_df.index = pd.to_datetime(vix_df.index).tz_localize(None)
vix_close = vix_df['Close']

def vix_on(d, lookback=5):
    for i in range(lookback):
        t = pd.Timestamp(d) - pd.Timedelta(days=i)
        if t in vix_close.index:
            return float(vix_close[t])
    return np.nan

# Attach VIX at entry
df_ic['entry_date'] = pd.to_datetime(df_ic['entry_date'])
df_ic['earn_date']  = pd.to_datetime(df_ic['earn_date'])
df_ic['vix_entry']  = df_ic['entry_date'].apply(vix_on)
df_ic['year']       = df_ic['earn_date'].dt.year

print(f"VIX attached. NaN count: {df_ic['vix_entry'].isna().sum()}\n")

# ─── 1. Annual VIX vs IC performance ─────────────────────────────────────────
print('='*65)
print('  A. ANNUAL BREAKDOWN: VIX level vs IC performance (ex-META)')
print('='*65)

annual_rows = []
for yr in sorted(df_ic['year'].unique()):
    sub = df_ic[df_ic['year'] == yr]
    n   = len(sub)
    if n == 0:
        continue
    vix_mean  = sub['vix_entry'].mean()
    vix_med   = sub['vix_entry'].median()
    im_mean   = sub['implied_move'].mean() * 100
    rm_mean   = sub['realized_move'].mean() * 100
    prem_mean = sub['premium'].mean() * 100
    wr        = (sub['pnl'] > 0).mean() * 100
    pnl_mean  = sub['pnl'].mean()
    cum_pnl   = sub['pnl'].sum()
    if n >= 3:
        t, p = ttest_1samp(sub['premium'], 0)
    else:
        t, p = np.nan, np.nan
    annual_rows.append({
        'year': yr, 'N': n,
        'VIX_mean': round(vix_mean, 1),
        'impl_move%': round(im_mean, 2),
        'real_move%': round(rm_mean, 2),
        'premium%': round(prem_mean, 2),
        'WR%': round(wr, 0),
        'mean_pnl$': round(pnl_mean, 2),
        'cum_pnl$': round(cum_pnl, 2),
        'prem_t': round(t, 2) if not np.isnan(t) else 'N/A',
        'prem_p': round(p, 3) if not np.isnan(p) else 'N/A',
    })

df_annual = pd.DataFrame(annual_rows)
print(df_annual.to_string(index=False))

# ─── 2. Per-stock annual PnL heatmap ─────────────────────────────────────────
print(f'\n{"="*65}')
print('  B. PER-STOCK ANNUAL PnL (mean $/event) — ex-META')
print(f'{"="*65}')

pivot = df_ic.pivot_table(
    index='symbol', columns='year', values='pnl', aggfunc='mean'
).round(1)
pivot['ALL'] = df_ic.groupby('symbol')['pnl'].mean().round(1)
print(pivot.to_string())

# ─── 3. VIX quartile vs IC outcome ───────────────────────────────────────────
print(f'\n{"="*65}')
print('  C. VIX QUARTILE AT ENTRY vs IC outcome (ex-META)')
print(f'{"="*65}')

df_ic['vix_q'] = pd.qcut(df_ic['vix_entry'], q=4,
                          labels=['Q1 low','Q2','Q3','Q4 high'])
vix_q_stats = df_ic.groupby('vix_q').agg(
    N        = ('pnl', 'count'),
    VIX_mean = ('vix_entry', 'mean'),
    impl_mv  = ('implied_move', 'mean'),
    real_mv  = ('realized_move', 'mean'),
    premium  = ('premium', 'mean'),
    WR       = ('pnl', lambda x: (x > 0).mean()),
    mean_pnl = ('pnl', 'mean'),
    cum_pnl  = ('pnl', 'sum'),
).round(3)
vix_q_stats['VIX_mean'] = vix_q_stats['VIX_mean'].round(1)
vix_q_stats['impl_mv']  = (vix_q_stats['impl_mv'] * 100).round(2)
vix_q_stats['real_mv']  = (vix_q_stats['real_mv'] * 100).round(2)
vix_q_stats['premium']  = (vix_q_stats['premium'] * 100).round(2)
vix_q_stats['WR']       = (vix_q_stats['WR'] * 100).round(0)
vix_q_stats['mean_pnl'] = vix_q_stats['mean_pnl'].round(2)
vix_q_stats['cum_pnl']  = vix_q_stats['cum_pnl'].round(2)
print(vix_q_stats.to_string())

# ─── 4. VIX threshold filter ─────────────────────────────────────────────────
print(f'\n{"="*65}')
print('  D. VIX THRESHOLD FILTER: only enter if VIX >= threshold')
print(f'{"="*65}')

filter_rows = []
for thr in [0, 15, 18, 20, 22, 25]:
    sub = df_ic[df_ic['vix_entry'] >= thr]
    n   = len(sub)
    if n == 0:
        continue
    wr       = (sub['pnl'] > 0).mean() * 100
    mean_pnl = sub['pnl'].mean()
    cum_pnl  = sub['pnl'].sum()
    prem     = sub['premium'].mean() * 100
    if n >= 4:
        t, p = ttest_1samp(sub['premium'], 0)
    else:
        t, p = np.nan, np.nan
    filter_rows.append({
        'VIX≥': thr, 'N': n,
        'WR%': round(wr, 0),
        'mean_pnl$': round(mean_pnl, 2),
        'cum_pnl$': round(cum_pnl, 2),
        'premium%': round(prem, 2),
        't': round(t, 2) if not np.isnan(t) else 'N/A',
        'p': round(p, 3) if not np.isnan(p) else 'N/A',
    })

print(pd.DataFrame(filter_rows).to_string(index=False))

# ─── 5. Implied move vs realized move ratio by VIX regime ─────────────────────
print(f'\n{"="*65}')
print('  E. IV CRUSH QUALITY: implied/realized ratio by year + VIX')
print(f'{"="*65}')

df_ic['crush_ratio'] = df_ic['implied_move'] / df_ic['realized_move'].clip(lower=0.001)
annual_crush = df_ic.groupby('year').agg(
    N=('crush_ratio','count'),
    VIX=('vix_entry','mean'),
    impl=('implied_move', lambda x: x.mean()*100),
    real=('realized_move', lambda x: x.mean()*100),
    crush=('crush_ratio','mean'),
    prem_pos_pct=('premium', lambda x: (x > 0).mean() * 100),
).round(2)
annual_crush['VIX'] = annual_crush['VIX'].round(1)
print(annual_crush.to_string())

# ─── 6. Pearson correlation: VIX → premium ────────────────────────────────────
r, p_r = pearsonr(df_ic['vix_entry'].dropna(),
                  df_ic.loc[df_ic['vix_entry'].notna(), 'premium'])
print(f'\nPearson corr (VIX_entry vs premium): r={r:.3f}, p={p_r:.3f}')

r2, p_r2 = pearsonr(df_ic['vix_entry'].dropna(),
                    df_ic.loc[df_ic['vix_entry'].notna(), 'pnl'])
print(f'Pearson corr (VIX_entry vs pnl):     r={r2:.3f}, p={p_r2:.3f}')

print('\nDone.')
