"""
Q041 Phase 2 — P2-1: SPX CSP DTE30 2022 熊市压测
=================================================
问题：D3 报告 SPX CSP Δ0.20 DTE30 全期 MaxDD = -4.6%，
      但 2022 SPX 下跌 -27%。是否有单个 cycle 被击穿？
      逐月验证 2022 年度表现。

方法：同 D3/P0-1 框架（非重叠月度 roll，BS delta 选 strike）
      DTE_TGT = 30（非 45）
      输出：全期 + 2022 专项 cycle 明细表
"""

import pandas as pd
import numpy as np
import pickle
import calendar
from scipy.optimize import brentq
from scipy.stats import norm
import warnings
warnings.filterwarnings('ignore')

# ─── Constants ────────────────────────────────────────────────────────────────
DATA_DIR  = 'data/q041_historical'
GSPC_PATH = 'data/market_cache/yahoo__GSPC__max__1d.pkl'
R         = 0.045
SLIP      = 0.03
F1        = 0.10
DTE_TGT   = 30
START     = pd.Timestamp('2022-05-20')
END       = pd.Timestamp('2026-04-17')
TGT_DELTA = 0.20

# ─── BS helpers (same as P0-1) ────────────────────────────────────────────────
def bs_price(S, K, T, r, σ, ot):
    if T < 1e-6 or σ < 1e-4:
        return max(0.0, (S - K) if ot == 'C' else (K - S))
    d1 = (np.log(S / K) + (r + 0.5 * σ**2) * T) / (σ * np.sqrt(T))
    d2 = d1 - σ * np.sqrt(T)
    if ot == 'C':
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def bs_iv(S, K, T, r, price, ot):
    if price < 1e-6 or T < 1e-6:
        return np.nan
    intrinsic = max(0.0, (S - K) if ot == 'C' else (K - S))
    if price <= intrinsic:
        return np.nan
    try:
        return brentq(lambda s: bs_price(S, K, T, r, s, ot) - price, 0.001, 5.0, maxiter=50)
    except Exception:
        return np.nan

def bs_delta(S, K, T, r, σ, ot):
    if T < 1e-6 or σ < 1e-4:
        return np.nan
    d1 = (np.log(S / K) + (r + 0.5 * σ**2) * T) / (σ * np.sqrt(T))
    return norm.cdf(d1) if ot == 'C' else (norm.cdf(d1) - 1.0)

# ─── Helpers ─────────────────────────────────────────────────────────────────
def third_friday(year, month):
    cal = calendar.monthcalendar(year, month)
    fridays = [w[4] for w in cal if w[4] != 0]
    return pd.Timestamp(year, month, fridays[2])

def get_px(d, px_dict, lookback=5):
    for i in range(lookback):
        t = d - pd.Timedelta(days=i)
        if t in px_dict:
            return px_dict[t]
    return None

# ─── Load data ────────────────────────────────────────────────────────────────
print('Loading SPX options...')
df = pd.read_parquet(f'{DATA_DIR}/SPX.parquet')
df['date']   = pd.to_datetime(df['date'])
df['expiry'] = pd.to_datetime(df['expiry'])

print('Loading SPX price (^GSPC)...')
with open(GSPC_PATH, 'rb') as f:
    gspc = pickle.load(f)
gspc.index = pd.to_datetime(gspc.index).tz_localize(None)
px_dict = gspc['Close'].to_dict()

df_by_date = {d: g for d, g in df.groupby('date')}

# ─── Build roll dates (third Friday, non-overlapping DTE30) ──────────────────
roll_dates_all = []
for yr in range(2022, 2027):
    for mo in range(1, 13):
        tf = third_friday(yr, mo)
        if START <= tf <= END:
            roll_dates_all.append(tf)

def find_expiry_dte(roll_date, df_slice, dte_tgt=30, win=10):
    avail = [e for e in df_slice['expiry'].unique() if e > roll_date]
    cands = [e for e in avail if abs((e - roll_date).days - dte_tgt) <= win]
    if not cands:
        cands = [e for e in avail if e > roll_date]
    if not cands:
        return None
    return min(cands, key=lambda e: abs((e - roll_date).days - dte_tgt))

# ─── Build option cache ───────────────────────────────────────────────────────
print('Building option cache...')
pairs = {}
for rd in roll_dates_all:
    rd_actual = rd
    if rd not in df_by_date:
        for i in range(1, 5):
            t = rd - pd.Timedelta(days=i)
            if t in df_by_date:
                rd_actual = t
                break
        else:
            continue
    exp = find_expiry_dte(rd, df_by_date[rd_actual])
    if exp is not None:
        pairs[rd] = (rd_actual, exp)

opt_cache = {}
for i, (rd, (rd_actual, exp)) in enumerate(pairs.items()):
    S = get_px(rd, px_dict)
    if S is None:
        continue
    T = (exp - rd).days / 365.0
    sub = df_by_date[rd_actual][
        (df_by_date[rd_actual]['expiry']      == exp) &
        (df_by_date[rd_actual]['option_type'] == 'P') &
        (df_by_date[rd_actual]['close']       >  F1)
    ]
    records = []
    for _, row in sub.iterrows():
        iv = bs_iv(S, row['strike'], T, R, row['close'], 'P')
        if np.isnan(iv):
            continue
        d = bs_delta(S, row['strike'], T, R, iv, 'P')
        if np.isnan(d):
            continue
        records.append({'K': row['strike'], 'price': row['close'], 'iv': iv, 'delta': d})
    if records:
        opt_cache[rd] = records

print(f'Cache built: {len(opt_cache)} roll dates with put data')

# ─── Run non-overlapping CSP DTE30 cycles ────────────────────────────────────
print('Running CSP DTE30 Δ0.20 non-overlapping cycles...')
cycles = []
prev_expiry = None

for rd in roll_dates_all:
    if prev_expiry is not None and rd < prev_expiry:
        continue   # skip overlapping
    if rd not in opt_cache:
        continue
    pair = pairs.get(rd)
    if pair is None:
        continue
    rd_actual, exp = pair

    S_entry = get_px(rd, px_dict)
    S_exit  = get_px(exp, px_dict)
    if S_entry is None or S_exit is None:
        continue

    records = opt_cache[rd]
    best = min(records, key=lambda r: abs(abs(r['delta']) - TGT_DELTA))
    K        = best['K']
    price    = best['price']
    delta    = best['delta']
    iv_entry = best['iv']

    net_prem  = price * (1.0 - SLIP)
    settle    = max(0.0, K - S_exit)
    cycle_pnl = net_prem - settle
    bp        = K
    ret       = cycle_pnl / bp
    pct_otm   = (S_entry - K) / S_entry   # how far OTM at entry
    hit       = S_exit < K                # was short strike breached?

    cycles.append({
        'roll_date' : rd,
        'expiry'    : exp,
        'act_dte'   : (exp - rd).days,
        'S_entry'   : round(S_entry, 1),
        'K'         : K,
        'pct_otm'   : round(pct_otm * 100, 1),   # % OTM
        'delta_act' : round(delta, 3),
        'iv_entry'  : round(iv_entry * 100, 1),   # IV %
        'price'     : round(price, 2),
        'net_prem'  : round(net_prem, 2),
        'S_exit'    : round(S_exit, 1),
        'spx_ret%'  : round((S_exit - S_entry) / S_entry * 100, 1),
        'hit'       : hit,
        'settle'    : round(settle, 2),
        'pnl'       : round(cycle_pnl, 2),
        'ret'       : ret,
        'bp'        : bp,
    })
    prev_expiry = exp

df_cyc = pd.DataFrame(cycles)
print(f'Total cycles: {len(df_cyc)}\n')

# ─── Full-period metrics ──────────────────────────────────────────────────────
def metrics(cyc, label):
    if len(cyc) < 3:
        return
    rets  = cyc['ret'].values
    n     = len(rets)
    t0    = cyc['roll_date'].min()
    t1    = cyc['expiry'].max()
    years = (t1 - t0).days / 365.25
    freq  = n / years

    cum    = float(np.prod(1.0 + rets) - 1.0)
    ann    = float((1.0 + cum) ** (1.0 / years) - 1.0)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(freq)) if rets.std() > 0 else 0.0
    eq       = np.cumprod(1.0 + rets)
    roll_max = np.maximum.accumulate(eq)
    mdd      = float(((eq - roll_max) / roll_max).min())
    wr       = float((rets > 0).mean())
    cut      = max(1, int(np.floor(n * 0.05)))
    cvar     = float(np.sort(rets)[:cut].mean())
    worst    = float(np.sort(rets)[0])

    print(f'\n── {label} (N={n}, {years:.1f}yr) ──')
    print(f'  CumRet: {cum*100:.1f}%  AnnRet: {ann*100:.1f}%  Sharpe: {sharpe:.2f}')
    print(f'  MaxDD:  {mdd*100:.2f}%  WR: {wr*100:.0f}%  CVaR5%: {cvar*100:.2f}%')
    print(f'  Worst cycle ret: {worst*100:.2f}%')
    return {'label': label, 'n': n, 'sharpe': sharpe, 'mdd': mdd,
            'wr': wr, 'cvar': cvar, 'worst': worst}

metrics(df_cyc, 'SPX CSP Δ0.20 DTE30 | Full Period 2022-05 → 2026-04')

# ─── 2022 cycle detail ────────────────────────────────────────────────────────
df_22 = df_cyc[df_cyc['roll_date'].dt.year == 2022].copy()
print(f'\n{"="*70}')
print(f'  2022 CYCLE-BY-CYCLE DETAIL (N={len(df_22)})')
print(f'{"="*70}')
cols = ['roll_date', 'expiry', 'S_entry', 'K', 'pct_otm', 'iv_entry',
        'S_exit', 'spx_ret%', 'hit', 'net_prem', 'settle', 'pnl']
print(df_22[cols].to_string(index=False))

metrics(df_22, 'SPX CSP Δ0.20 DTE30 | 2022 Only')

# ─── Monthly SPX returns for context ──────────────────────────────────────────
print(f'\n── 2022 SPX monthly returns (context) ──')
spx_monthly = gspc['Close'].resample('ME').last()
for m in pd.date_range('2022-05', '2022-12', freq='ME'):
    prev = spx_monthly.get(m - pd.offsets.MonthEnd(1))
    curr = spx_monthly.get(m)
    if prev is not None and curr is not None:
        print(f'  {m.strftime("%Y-%m")}: {(curr/prev - 1)*100:+.1f}%')

# ─── Near-miss analysis: cycles where K was within 3% of S_exit ───────────────
print(f'\n── Near-miss cycles (K within 3% above S_exit, full period) ──')
df_cyc['cushion%'] = ((df_cyc['S_exit'] - df_cyc['K']) / df_cyc['K'] * 100)
near = df_cyc[df_cyc['cushion%'] < 3].sort_values('cushion%')
if len(near) > 0:
    print(near[['roll_date', 'expiry', 'S_entry', 'K', 'S_exit',
                'cushion%', 'spx_ret%', 'hit', 'pnl']].to_string(index=False))
else:
    print('  None.')

# ─── Equity curve by year ──────────────────────────────────────────────────────
print(f'\n── Annual PnL summary ──')
df_cyc['year'] = df_cyc['roll_date'].dt.year
annual = df_cyc.groupby('year').agg(
    N=('pnl','count'),
    cum_pnl=('pnl','sum'),
    WR=('ret', lambda x: (x>0).mean()),
    worst=('pnl','min'),
    sharpe=('ret', lambda x: x.mean()/x.std() if x.std()>0 else np.nan)
).round(2)
annual['WR'] = (annual['WR']*100).round(0).astype(int)
print(annual.to_string())

# ─── Save ─────────────────────────────────────────────────────────────────────
with open('/tmp/p21_spx_csp_bearmarket.pkl', 'wb') as f:
    pickle.dump(df_cyc, f)
print('\nSaved → /tmp/p21_spx_csp_bearmarket.pkl')
