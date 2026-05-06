"""
Q041 Phase 2 — P0-1: DTE45 Overlap-Corrected Rerun
===================================================
SPX Covered Call + Cash-Secured Put, DTE ≈ 45 days
Δ = 0.20 / 0.25 / 0.30 (6 combos × 2 versions = 12 rows)

Phase-1 version  : every monthly 3rd-Friday rolls regardless of whether the
                   previous DTE45 cycle has expired (→ ~15-day overlap)
Phase-2 corrected: new cycle only when previous cycle's expiry has passed

Period  : 2022-05-20 → 2026-04-17
Slippage: 3%  Risk-free: 4.5%  F1 filter: close > $0.10

Output : /tmp/p01_dte45_overlap_comparison.pkl   (DataFrame)
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
DATA_DIR  = '/Users/lienchen/Documents/workspace/SPX_strat/data/q041_historical'
GSPC_PATH = '/Users/lienchen/Documents/workspace/SPX_strat/data/market_cache/yahoo__GSPC__max__1d.pkl'
R         = 0.045
SLIP      = 0.03
F1        = 0.10        # close > $0.10
DTE_TGT   = 45
DTE_WIN   = 12          # ± days to find nearest expiry
START     = pd.Timestamp('2022-05-20')
END       = pd.Timestamp('2026-04-17')

# ─── Black-Scholes IV + Delta ─────────────────────────────────────────────────
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

def find_expiry(roll_date, df_date_slice):
    """Find expiry closest to DTE_TGT from options that actually have data on roll_date."""
    avail = df_date_slice['expiry'].unique()
    cands = [e for e in avail if e > roll_date]
    if not cands:
        return None
    return min(cands, key=lambda e: abs((e - roll_date).days - DTE_TGT))

# ─── Load Data ────────────────────────────────────────────────────────────────
print('Loading SPX option data...')
df = pd.read_parquet(f'{DATA_DIR}/SPX.parquet')
df['date']   = pd.to_datetime(df['date'])
df['expiry'] = pd.to_datetime(df['expiry'])

print('Loading SPX price (^GSPC)...')
with open(GSPC_PATH, 'rb') as f:
    gspc = pickle.load(f)
gspc.index = pd.to_datetime(gspc.index).tz_localize(None)
px_dict = gspc['Close'].to_dict()

all_expiries = sorted(df['expiry'].unique())

# ─── Roll dates ───────────────────────────────────────────────────────────────
roll_dates_all = []
for yr in range(2022, 2027):
    for mo in range(1, 13):
        tf = third_friday(yr, mo)
        if START <= tf <= END:
            roll_dates_all.append(tf)
print(f'Monthly roll dates in window: {len(roll_dates_all)}')

# ─── Pre-compute IV/delta for every needed (date, expiry, option_type) ────────
print('Pre-computing IV and delta for all roll-date/expiry pairs...')
# Pre-slice df by date for fast lookup
df_by_date = {d: df[df['date'] == d] for d in df['date'].unique()}

# Collect unique (roll_date, expiry) pairs first
pairs = {}
for rd in roll_dates_all:
    if rd not in df_by_date:
        # 2025-04-18 missing → use nearest prior trading day
        for i in range(1, 5):
            t = rd - pd.Timedelta(days=i)
            if t in df_by_date:
                rd_actual = t
                break
        else:
            continue
    else:
        rd_actual = rd
    exp = find_expiry(rd, df_by_date[rd_actual])
    if exp is not None:
        pairs[rd] = (rd_actual, exp)  # store (actual_date, expiry)

# Build option cache: (roll_date, expiry, ot) -> list of {K, price, iv, delta}
opt_cache = {}
for i, (rd, (rd_actual, exp)) in enumerate(pairs.items()):
    S = get_px(rd, px_dict)
    if S is None:
        continue
    T = (exp - rd).days / 365.0
    for ot in ('C', 'P'):
        sub = df_by_date[rd_actual][
            (df_by_date[rd_actual]['expiry']      == exp) &
            (df_by_date[rd_actual]['option_type'] == ot)  &
            (df_by_date[rd_actual]['close']       >  F1)
        ]
        records = []
        for _, row in sub.iterrows():
            iv = bs_iv(S, row['strike'], T, R, row['close'], ot)
            if np.isnan(iv):
                continue
            d = bs_delta(S, row['strike'], T, R, iv, ot)
            if np.isnan(d):
                continue
            records.append({'K': row['strike'], 'price': row['close'],
                             'iv': iv, 'delta': d})
        if records:
            opt_cache[(rd, exp, ot)] = records
    if (i + 1) % 10 == 0:
        print(f'  {i+1}/{len(pairs)} roll dates processed  '
              f'(rd={rd.date()}, exp={exp.date()}, DTE={( exp-rd).days})')

print(f'Option cache built: {len(opt_cache)} (date, expiry, type) entries')

# ─── Build Cycles ─────────────────────────────────────────────────────────────
def build_cycles(roll_dates, strategy, tgt_delta, overlapping):
    ot = 'C' if strategy == 'CC' else 'P'
    cycles = []
    prev_expiry = None

    for rd in roll_dates:
        # --- overlap filter ---
        if (not overlapping) and prev_expiry is not None and rd < prev_expiry:
            continue

        pair = pairs.get(rd)
        if pair is None:
            continue
        rd_actual, exp = pair

        key = (rd, exp, ot)
        if key not in opt_cache:
            continue

        S_entry = get_px(rd, px_dict)
        S_exit  = get_px(exp, px_dict)
        if S_entry is None or S_exit is None:
            continue

        # Find strike closest to target delta
        records  = opt_cache[key]
        best     = min(records, key=lambda r: abs(abs(r['delta']) - tgt_delta))
        K        = best['K']
        price    = best['price']
        net_prem = price * (1.0 - SLIP)
        act_dte  = (exp - rd).days

        if strategy == 'CC':
            settle    = max(0.0, S_exit - K)
            cycle_pnl = (S_exit - S_entry) + (net_prem - settle)
            bp        = S_entry
        else:   # CSP
            settle    = max(0.0, K - S_exit)
            cycle_pnl = net_prem - settle
            bp        = K

        cycles.append({
            'roll_date':    rd,
            'expiry':       exp,
            'act_dte':      act_dte,
            'S_entry':      S_entry,
            'S_exit':       S_exit,
            'K':            K,
            'price':        price,
            'delta_actual': best['delta'],
            'pnl':          cycle_pnl,
            'bp':           bp,
            'ret':          cycle_pnl / bp,
        })
        prev_expiry = exp

    return pd.DataFrame(cycles)

# ─── Metrics ─────────────────────────────────────────────────────────────────
def compute_metrics(cyc, label):
    if len(cyc) < 3:
        return {'label': label, 'n': len(cyc),
                'cum': np.nan, 'ann': np.nan, 'sharpe': np.nan,
                'mdd': np.nan, 'wr': np.nan, 'cvar': np.nan,
                'bpd': np.nan, 'worst': np.nan}

    rets  = cyc['ret'].values
    pnls  = cyc['pnl'].values
    t0    = cyc['roll_date'].min()
    t1    = cyc['expiry'].max()
    years = (t1 - t0).days / 365.25
    n     = len(rets)
    freq  = n / years   # actual cycles per year

    cum    = float(np.prod(1.0 + rets) - 1.0)
    ann    = float((1.0 + cum) ** (1.0 / years) - 1.0)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(freq)) if rets.std() > 0 else 0.0

    eq       = np.cumprod(1.0 + rets)
    roll_max = np.maximum.accumulate(eq)
    mdd      = float(((eq - roll_max) / roll_max).min())

    wr   = float((rets > 0).mean())
    cut  = max(1, int(np.floor(n * 0.05)))
    cvar = float(np.sort(rets)[:cut].mean())

    # $/100-BP/day (matches D3 bpd column)
    bpd_vals = pnls / (cyc['bp'].values * cyc['act_dte'].values) * 100.0
    bpd      = float(bpd_vals.mean())
    worst    = float(pnls.min())

    return dict(label=label, n=n, freq=round(freq, 1),
                cum=cum, ann=ann, sharpe=sharpe,
                mdd=mdd, wr=wr, cvar=cvar, bpd=bpd, worst=worst)

# ─── Run All Combos ───────────────────────────────────────────────────────────
COMBOS = [
    ('CC',  0.20), ('CC',  0.25), ('CC',  0.30),
    ('CSP', 0.20), ('CSP', 0.25), ('CSP', 0.30),
]

print('\nRunning backtests (Phase-1 overlap vs Phase-2 corrected)...')
all_results = []
cycle_store = {}

for strat, delta in COMBOS:
    cyc_ov = build_cycles(roll_dates_all, strat, delta, overlapping=True)
    cyc_nv = build_cycles(roll_dates_all, strat, delta, overlapping=False)

    lab_ov = f'{strat} Δ{delta:.2f} DTE45 [Phase1-overlap]'
    lab_nv = f'{strat} Δ{delta:.2f} DTE45 [Phase2-corrected]'

    all_results.append(compute_metrics(cyc_ov, lab_ov))
    all_results.append(compute_metrics(cyc_nv, lab_nv))

    cycle_store[lab_ov] = cyc_ov
    cycle_store[lab_nv] = cyc_nv

    print(f'  {strat} Δ{delta:.2f}:  overlap N={len(cyc_ov)}, corrected N={len(cyc_nv)}')

# ─── Display Results ──────────────────────────────────────────────────────────
res = pd.DataFrame(all_results)

print('\n' + '=' * 100)
print('RESULTS: Phase-1 (overlap) vs Phase-2 (corrected)')
print('=' * 100)
cols = ['label', 'n', 'freq', 'cum', 'ann', 'sharpe', 'mdd', 'wr', 'cvar', 'bpd', 'worst']

def fmt(r):
    return (f"{r['label']:<42}  N={r['n']:>2}  freq={r['freq']:>4.1f}  "
            f"cum={r['cum']:>+7.1%}  ann={r['ann']:>+6.1%}  "
            f"Sharpe={r['sharpe']:>5.2f}  MDD={r['mdd']:>+6.1%}  "
            f"WR={r['wr']:>4.1%}  CVaR={r['cvar']:>+6.1%}  "
            f"BPd={r['bpd']:>+6.4f}  Worst=${r['worst']:>+7.0f}")

print()
for i, row in res.iterrows():
    print(fmt(row))
    if i % 2 == 1:
        print()   # blank line between each combo pair

# ─── Save ─────────────────────────────────────────────────────────────────────
out = {'results': res, 'cycles': cycle_store}
with open('/tmp/p01_dte45_overlap_comparison.pkl', 'wb') as f:
    pickle.dump(out, f)
print('\nSaved → /tmp/p01_dte45_overlap_comparison.pkl')
