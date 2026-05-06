"""
Q041 Phase 2 — P1-1: IVR Entry Filter for Earnings Iron Condor
===============================================================
Question: Does filtering by implied-move rank (IMR) improve COST/JPM earnings IC?

Method:
- Load D4 results; isolate IC T-3 w=1.0x (production candidate combo)
- IMR = percentile rank of event's implied_move within same stock's event list
  (full-window rank — lookahead bias; disclosed as limitation, acceptable for
   directional research question: "does premium level predict outcomes?")
- Test IMR thresholds: 0% (no filter), 25%, 33%, 50%
- Primary: COST, JPM; secondary: full ex-META universe

Output: console table + /tmp/p11_ivr_filter_results.pkl
"""

import pandas as pd
import numpy as np
import pickle
from scipy.stats import ttest_1samp

# ─── Load D4 results ──────────────────────────────────────────────────────────
with open('/tmp/d4_earnings_results.pkl', 'rb') as f:
    df_all = pickle.load(f)

# ─── Isolate production candidate combo: IC T-3 w=1.0x ───────────────────────
df_ic = df_all[
    (df_all['spread_type'] == 'condor') &
    (df_all['entry_lag'] == 3) &
    (df_all['width_mult'] == 1.0)
].copy()

print(f"IC T-3 w=1.0x universe: {len(df_ic)} events across {df_ic['symbol'].nunique()} symbols")
print(f"Symbols: {sorted(df_ic['symbol'].unique())}")

# ─── Compute within-stock implied-move rank ───────────────────────────────────
# IMR = percentile of this event's implied_move among all events for same symbol
# Higher IMR = this earnings is priced at MORE premium than usual for this stock
df_ic['_rank'] = df_ic.groupby('symbol')['implied_move'].rank(method='average')
df_ic['_n']    = df_ic.groupby('symbol')['implied_move'].transform('count')
df_ic['imr']   = (df_ic['_rank'] - 1) / (df_ic['_n'] - 1).clip(lower=1)
df_ic = df_ic.drop(columns=['_rank', '_n'])

# ─── Filter thresholds ────────────────────────────────────────────────────────
THRESHOLDS = [0.0, 0.25, 0.33, 0.50]
SYMBOLS_FOCUS = ['COST', 'JPM']
META_EXCL = [s for s in df_ic['symbol'].unique() if s != 'META']

def metrics(df_sub, label):
    if len(df_sub) == 0:
        return {'label': label, 'N': 0}
    n = len(df_sub)
    pnl = df_sub['pnl']
    nc  = df_sub['net_credit']
    ml  = df_sub['max_loss']
    im  = df_sub['implied_move']

    roe_entry    = (nc / ml).mean() * 100          # max achievable ROE per event (%)
    roe_realized = (pnl / ml).mean() * 100         # actual realized ROE per event (%)
    wr           = (pnl > 0).mean() * 100
    sharpe       = pnl.mean() / pnl.std() if pnl.std() > 0 else np.nan
    worst        = pnl.min()
    cum_pnl      = pnl.sum()
    mean_im      = im.mean() * 100                 # implied move %
    mean_nc      = nc.mean()

    # t-test: mean pnl > 0?
    if n >= 4:
        t, p = ttest_1samp(pnl, 0)
    else:
        t, p = np.nan, np.nan

    return {
        'label'         : label,
        'N'             : n,
        'WR%'           : round(wr, 1),
        'mean_im%'      : round(mean_im, 2),
        'mean_nc$'      : round(mean_nc, 2),
        'roe_entry%'    : round(roe_entry, 1),
        'roe_realized%' : round(roe_realized, 1),
        'sharpe'        : round(sharpe, 2) if not np.isnan(sharpe) else 'N/A',
        'worst$'        : round(worst, 2),
        'cum_pnl$'      : round(cum_pnl, 2),
        't'             : round(t, 2) if not np.isnan(t) else 'N/A',
        'p'             : round(p, 3) if not np.isnan(p) else 'N/A',
    }

# ─── Run analysis ─────────────────────────────────────────────────────────────
results = []

for sym_set, set_name in [(SYMBOLS_FOCUS, 'COST+JPM'), (META_EXCL, 'ex-META')]:
    df_set = df_ic[df_ic['symbol'].isin(sym_set)]
    print(f"\n{'='*60}")
    print(f"  {set_name}  (IC T-3 w=1.0x, IMR filter sweep)")
    print(f"{'='*60}")

    rows = []
    for thr in THRESHOLDS:
        df_filt = df_set[df_set['imr'] >= thr]
        label = f"IMR≥{int(thr*100)}%"
        r = metrics(df_filt, label)
        r['sym_set'] = set_name
        r['imr_thr'] = thr
        rows.append(r)
        results.append(r)

    # Print table
    cols = ['label', 'N', 'WR%', 'mean_im%', 'mean_nc$',
            'roe_entry%', 'roe_realized%', 'sharpe', 'worst$', 'cum_pnl$', 't', 'p']
    print(pd.DataFrame(rows)[cols].to_string(index=False))

# ─── Per-symbol breakdown at IMR≥0% and IMR≥33% ──────────────────────────────
print(f"\n{'='*60}")
print("  Per-symbol: baseline vs IMR≥33%")
print(f"{'='*60}")

sym_rows = []
for sym in ['COST', 'JPM']:
    for thr, tag in [(0.0, 'baseline'), (0.33, 'IMR≥33%'), (0.50, 'IMR≥50%')]:
        df_filt = df_ic[(df_ic['symbol'] == sym) & (df_ic['imr'] >= thr)]
        r = metrics(df_filt, f"{sym} {tag}")
        sym_rows.append(r)

cols2 = ['label', 'N', 'WR%', 'mean_im%', 'mean_nc$',
         'roe_entry%', 'roe_realized%', 'worst$', 'cum_pnl$', 'p']
print(pd.DataFrame(sym_rows)[cols2].to_string(index=False))

# ─── Show which events COST/JPM would skip under IMR≥33% ─────────────────────
print(f"\n{'='*60}")
print("  Skipped events under IMR≥33% (COST + JPM)")
print(f"{'='*60}")
df_skip = df_ic[
    (df_ic['symbol'].isin(['COST', 'JPM'])) &
    (df_ic['imr'] < 0.33)
].sort_values(['symbol', 'earn_date'])
if len(df_skip) > 0:
    print(df_skip[['symbol', 'earn_date', 'imr', 'implied_move', 'realized_move',
                   'premium', 'pnl', 'net_credit', 'max_loss']].to_string(index=False))
else:
    print("  No events skipped.")

# ─── Save results ─────────────────────────────────────────────────────────────
with open('/tmp/p11_ivr_filter_results.pkl', 'wb') as f:
    pickle.dump({'df_ic_with_imr': df_ic, 'results': pd.DataFrame(results)}, f)
print("\nSaved → /tmp/p11_ivr_filter_results.pkl")
