"""
Q058 Tier 2-A — Dynamic VIX Leverage + BSH in V2f Framework
=============================================================

Question: Does adding Phase 3-style dynamic VIX leverage to V2f change the
BSH economic verdict from Tier 1 (NET-NEGATIVE)?

Hypothesis (motivating Tier 2-A): Phase 3/4's BSH economic case may rely on
contract-sizing scaling with VIX. At high VIX, larger short put exposure →
larger downside vega → BSH payoff has more to insure proportionally. Tier 1
held V2f at fixed 1 contract per slot, which may have suppressed BSH's
relative value.

Method: Compare three new variants against Tier 1 baselines:
  V2f_dynlev_alone : V2f + Phase 3 leverage table, no BSH
  V2f_dynlev_cost  : V2f + Phase 3 leverage table + BSH cost only
  V2f_dynlev_full  : V2f + Phase 3 leverage table + BSH cost + payoff (Phase 4 model)

Compared to Tier 1:
  V2f_alone        : Fixed 1 contract per slot, no BSH
  V2f_bsh_full     : Fixed 1 contract per slot + BSH cost + payoff

Decision:
  If V2f_dynlev_full > V2f_dynlev_alone in Ann ROE → BSH economical with leverage
  If V2f_dynlev_full < V2f_dynlev_alone → BSH still NET-NEGATIVE; Tier 1 verdict stands
"""

import pickle
import sys
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

# ─── Constants ────────────────────────────────────────────────────────────────
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

BSH_WEEKLY_COST_PCT  = 0.0004
BSH_MONTHLY_COST_PCT = 0.0008
BSH_VIX_THRESHOLD    = 15.0

# Phase 3 leverage table (verbatim from backtest.py:84-90)
P3_LEVERAGE_TABLE = [
    (40, 0.50),
    (30, 0.40),
    (20, 0.35),
    (15, 0.30),
    ( 0, 0.25),
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

# Phase 3 BP-per-contract (verbatim semantics from backtest.py:160-167)
def bp_per_contract(spx, strike, premium_pts):
    prem_usd = premium_pts * SPX_MULT
    method_a = 0.15 * spx * SPX_MULT - max(0, (spx - strike)) * SPX_MULT + prem_usd
    method_b = 0.10 * strike * SPX_MULT + prem_usd
    return max(method_a, method_b, 37.50)

# ─── Unified simulator with dynamic-leverage option ──────────────────────────
def run_v2f_extended(sim_df, bsh_mode="alone", dynlev=False):
    """
    bsh_mode: 'alone' | 'cost' | 'full'
    dynlev:   True → Phase 3-style VIX leverage table for short put sizing
              False → fixed 1 contract per slot (Tier 1 baseline)
    """
    positions = []
    bsh_puts  = []
    short_trades = []
    bsh_total_cost = 0.0
    bsh_total_payoff_realized = 0.0
    daily_pnl_log = []
    equity = ACCOUNT
    eq_curve = []

    day_counter = 0
    days_since_entry = WEEKLY_TD

    for i, (date, row) in enumerate(sim_df.iterrows()):
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sigma = vix / 100.0
        spy   = spx / 10.0
        dstr  = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        day_counter += 1

        # ── BSH cost ────────────────────────────────────────────────────────
        if bsh_mode in ("cost", "full"):
            if day_counter % WEEKLY_TD == 0 and bsh_mode == "cost":
                cost = equity * BSH_WEEKLY_COST_PCT
                daily_pnl -= cost
                bsh_total_cost += cost
            if day_counter % 21 == 0 and vix < BSH_VIX_THRESHOLD:
                cost = equity * BSH_MONTHLY_COST_PCT
                daily_pnl -= cost
                bsh_total_cost += cost

        # ── BSH put purchase (full only) ────────────────────────────────────
        if bsh_mode == "full" and day_counter % WEEKLY_TD == 0:
            budget = equity * BSH_WEEKLY_COST_PCT
            bsh_dte    = 7  if vix > 20 else 30
            otm_frac   = 0.90 if vix > 20 else 0.80
            bsh_strike = spy * otm_frac
            cost_per   = bs_put_price(spy, bsh_strike, bsh_dte, sigma)
            cost_usd   = cost_per * 100
            if cost_usd > 0.01:
                n_contracts = budget / cost_usd
                bsh_puts.append({
                    'entry_date': dstr, 'strike': bsh_strike, 'dte': bsh_dte,
                    'contracts': n_contracts, 'prev_val': cost_per,
                })
                bsh_total_cost += budget

        # ── BSH puts daily MTM (full only) ──────────────────────────────────
        if bsh_mode == "full":
            to_expire = []
            for j, bp in enumerate(bsh_puts):
                bp['dte'] -= 1
                cur_val = bs_put_price(spy, bp['strike'], max(bp['dte'], 0), sigma)
                pnl_delta = (cur_val - bp['prev_val']) * bp['contracts'] * 100
                daily_pnl += pnl_delta
                bp['prev_val'] = cur_val
                if bp['dte'] <= 0:
                    bsh_total_payoff_realized += cur_val * bp['contracts'] * 100
                    to_expire.append(j)
            for j in reversed(to_expire):
                bsh_puts.pop(j)

        # ── V2f short put management ────────────────────────────────────────
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
                    'contracts': pos['contracts'],
                    'entry_vix': pos['entry_vix'],
                    'year': pd.Timestamp(pos['entry_date']).year,
                })
            else:
                pos['prev_val'] = cur_val
                still_open.append(pos)
        positions = still_open

        # ── V2f entry (with optional dynamic leverage sizing) ───────────────
        days_since_entry += 1
        if (days_since_entry >= WEEKLY_TD
            and i >= 64
            and len(positions) < V2F_MAX_SLOTS):
            K = find_strike_for_delta(spx, V2F_ENTRY_DTE, sigma, TARGET_DELTA)
            entry_prem = bs_put_price(spx, K, V2F_ENTRY_DTE, sigma)
            if entry_prem > 0.5:
                if dynlev:
                    # Phase 3-style: per-slot BP target = ceiling × NLV / max_slots
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
                })
                days_since_entry = 0

        equity += daily_pnl
        daily_pnl_log.append({'date': date, 'daily_pnl': daily_pnl, 'equity': equity, 'vix': vix})
        eq_curve.append(equity)

    # Force-close at end of window
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
            'contracts': pos['contracts'],
            'entry_vix': pos['entry_vix'],
            'year': pd.Timestamp(pos['entry_date']).year,
        })

    return {
        'short_trades': pd.DataFrame(short_trades),
        'daily_pnl_log': pd.DataFrame(daily_pnl_log),
        'final_equity': equity,
        'bsh_total_cost': bsh_total_cost,
        'bsh_total_payoff_realized': bsh_total_payoff_realized,
        'eq_curve': eq_curve,
    }

# ─── Load data ───────────────────────────────────────────────────────────────
print("Loading market data...")
data, _ = es_mod._load_data()
sim_df = data[(data.index >= pd.Timestamp(WINDOW_START)) & (data.index <= pd.Timestamp(WINDOW_END))]
print(f"  Trading days: {len(sim_df)}")

# ─── Run six variants ────────────────────────────────────────────────────────
print("\nRunning variants (5 dynlev × 3 BSH modes + Tier 1 baselines)...\n")

variants = {}
for label, dynlev_flag, bsh_mode in [
    ("V2f_alone (Tier 1 ref)",        False, "alone"),
    ("V2f_bsh_full (Tier 1 ref)",     False, "full"),
    ("V2f_dynlev_alone",              True,  "alone"),
    ("V2f_dynlev_cost",               True,  "cost"),
    ("V2f_dynlev_full",               True,  "full"),
]:
    print(f"  {label}...", end='', flush=True)
    r = run_v2f_extended(sim_df, bsh_mode=bsh_mode, dynlev=dynlev_flag)
    variants[label] = r
    avg_contracts = r['short_trades']['contracts'].mean() if len(r['short_trades']) > 0 else 0
    print(f" trades={len(r['short_trades'])}, "
          f"final=${r['final_equity']:,.0f}, "
          f"avg_contracts={avg_contracts:.2f}")

# ─── Metrics computation ─────────────────────────────────────────────────────
def metrics(r, label):
    short = r['short_trades']
    final = r['final_equity']
    total_pnl = final - ACCOUNT
    cum_ret = total_pnl / ACCOUNT
    ann_geom = ((1 + cum_ret) ** (1/YEARS) - 1) * 100 if cum_ret > -1 else float('nan')

    short_pnls = short['pnl_$'].values if len(short) > 0 else np.array([])
    worst_short = short_pnls.min() if len(short_pnls) > 0 else 0
    worst_short_pct = worst_short / ACCOUNT * 100
    wr = (short_pnls > 0).mean() * 100 if len(short_pnls) > 0 else 0
    avg_contracts = short['contracts'].mean() if len(short) > 0 else 0

    daily = r['daily_pnl_log']['daily_pnl'].values
    daily_ret = daily / ACCOUNT
    sharpe_ann = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0

    eq = np.array(r['eq_curve'])
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    mdd_pct = dd.min() * 100

    return {
        'label': label,
        'short_n': len(short),
        'avg_contracts': round(avg_contracts, 2),
        'final_equity_$': round(final, 0),
        'total_pnl_$': round(total_pnl, 0),
        'ann_roe_geom_%': round(ann_geom, 2),
        'short_wr_%': round(wr, 1),
        'worst_$': round(worst_short, 0),
        'worst_pct_nlv': round(worst_short_pct, 2),
        'sharpe_ann': round(sharpe_ann, 2),
        'mdd_%': round(mdd_pct, 1),
        'bsh_cost_$': round(r['bsh_total_cost'], 0),
        'bsh_payoff_$': round(r['bsh_total_payoff_realized'], 0),
    }

m_list = [metrics(variants[lbl], lbl) for lbl in variants.keys()]

# ─── Print comparison table ───────────────────────────────────────────────────
print(f"\n{'='*108}")
print(f"  Q058 Tier 2-A — Dynamic VIX Leverage + BSH in V2f Framework")
print(f"  Window: {WINDOW_START} → {WINDOW_END} ({YEARS:.1f} yr) | $500k account")
print(f"{'='*108}\n")

cmp_df = pd.DataFrame(m_list)
cols = ['label', 'short_n', 'avg_contracts', 'ann_roe_geom_%', 'short_wr_%',
        'worst_$', 'worst_pct_nlv', 'sharpe_ann', 'mdd_%',
        'bsh_cost_$', 'bsh_payoff_$']
print(cmp_df[cols].to_string(index=False))

# ─── BSH net effect comparison ────────────────────────────────────────────────
print(f"\n{'='*108}")
print(f"  BSH NET EFFECT — Tier 1 (fixed contracts) vs Tier 2-A (dynamic leverage)")
print(f"{'='*108}\n")

m_t1_alone  = next(m for m in m_list if 'V2f_alone' in m['label'])
m_t1_full   = next(m for m in m_list if 'V2f_bsh_full' in m['label'])
m_t2_alone  = next(m for m in m_list if 'V2f_dynlev_alone' == m['label'])
m_t2_cost   = next(m for m in m_list if 'V2f_dynlev_cost' == m['label'])
m_t2_full   = next(m for m in m_list if 'V2f_dynlev_full' == m['label'])

t1_net = m_t1_full['ann_roe_geom_%'] - m_t1_alone['ann_roe_geom_%']
t1_sharpe_net = m_t1_full['sharpe_ann'] - m_t1_alone['sharpe_ann']
t2_cost_drag  = m_t2_alone['ann_roe_geom_%'] - m_t2_cost['ann_roe_geom_%']
t2_payoff_recovery = m_t2_full['ann_roe_geom_%'] - m_t2_cost['ann_roe_geom_%']
t2_net = m_t2_full['ann_roe_geom_%'] - m_t2_alone['ann_roe_geom_%']
t2_sharpe_net = m_t2_full['sharpe_ann'] - m_t2_alone['sharpe_ann']

print(f"  Tier 1 (fixed 1 contract):")
print(f"    BSH net effect:   {t1_net:+.2f}pp Ann ROE   (cost-only - alone n/a; full - alone)")
print(f"    BSH Sharpe net:   {t1_sharpe_net:+.2f}")
print(f"    Verdict: {'NET-NEGATIVE' if t1_net < 0 else 'NET-POSITIVE'}")
print()
print(f"  Tier 2-A (dynamic VIX leverage):")
print(f"    BSH cost drag:        {t2_cost_drag:+.2f}pp Ann ROE   (alone - cost)")
print(f"    BSH payoff recovery:  {t2_payoff_recovery:+.2f}pp Ann ROE  (full - cost)")
print(f"    BSH net effect:       {t2_net:+.2f}pp Ann ROE   (full - alone)")
print(f"    BSH Sharpe net:       {t2_sharpe_net:+.2f}")
print(f"    Verdict: {'NET-NEGATIVE' if t2_net < 0 else 'NET-POSITIVE'}")
print()
print(f"  Δ between tiers (does dynamic leverage rescue BSH?):")
print(f"    Net effect change:  {t2_net - t1_net:+.2f}pp")
print(f"    Sharpe change:      {t2_sharpe_net - t1_sharpe_net:+.2f}")

# ─── Average contracts deployed analysis ──────────────────────────────────────
print(f"\n{'='*108}")
print(f"  Position Sizing Comparison (does dynamic leverage actually scale meaningfully?)")
print(f"{'='*108}\n")

# Check distribution of contracts in dynlev variants
sub_dynlev = variants['V2f_dynlev_alone']['short_trades']
print(f"  V2f_dynlev_alone contract distribution by VIX bucket:")
sub_dynlev = sub_dynlev.copy()
sub_dynlev['vix_bucket'] = pd.cut(sub_dynlev['entry_vix'],
    bins=[0, 15, 20, 30, 40, 100], labels=['<15', '15-20', '20-30', '30-40', '≥40'])
for bucket, g in sub_dynlev.groupby('vix_bucket', observed=True):
    print(f"    VIX {str(bucket):>6}: n={len(g):>4}  avg_contracts={g['contracts'].mean():.2f}  "
          f"avg_PnL=${g['pnl_$'].mean():>+8,.0f}  worst=${g['pnl_$'].min():>+9,.0f}")

# ─── 2020 COVID stress test ──────────────────────────────────────────────────
print(f"\n{'='*108}")
print(f"  2020 COVID Stress Test — Critical Year for BSH Economics")
print(f"{'='*108}\n")

print(f"  {'Variant':<35}  {'2020 short total':>16}  {'2020 worst short':>16}  {'2020 daily-pnl total':>22}")
for lbl in variants.keys():
    r = variants[lbl]
    sub = r['short_trades']
    sub2020 = sub[sub['year'] == 2020] if 'year' in sub.columns else pd.DataFrame()
    daily_2020 = r['daily_pnl_log'][
        (r['daily_pnl_log']['date'] >= '2020-01-01') &
        (r['daily_pnl_log']['date'] < '2021-01-01')
    ]
    short_total = sub2020['pnl_$'].sum() if len(sub2020) > 0 else 0
    worst_2020 = sub2020['pnl_$'].min() if len(sub2020) > 0 else 0
    daily_total = daily_2020['daily_pnl'].sum() if len(daily_2020) > 0 else 0
    print(f"  {lbl:<35}  ${short_total:>+15,.0f}  ${worst_2020:>+15,.0f}  ${daily_total:>+21,.0f}")

# ─── Verdict ─────────────────────────────────────────────────────────────────
print(f"\n{'='*108}")
print(f"  TIER 2-A VERDICT")
print(f"{'='*108}\n")

if t2_net > 0:
    if m_t2_full['sharpe_ann'] > m_t2_alone['sharpe_ann']:
        verdict = ("BSH ECONOMICS RESCUED by dynamic leverage. "
                   f"Net +{t2_net:.2f}pp Ann ROE + Sharpe up {t2_sharpe_net:+.2f}. "
                   f"Reconsider BSH inclusion in V2f if dynamic leverage adopted.")
    else:
        verdict = (f"BSH ROE-positive ({t2_net:+.2f}pp) under dynamic leverage but Sharpe still down. "
                   f"Mixed signal — alpha up but risk-adjusted unclear.")
elif abs(t2_net) < 0.3:
    verdict = (f"BSH ECONOMICS UNCHANGED under dynamic leverage. "
               f"Net {t2_net:+.2f}pp Ann ROE — still net-negative or break-even. "
               f"Tier 1 verdict (DROP BSH) still applies.")
else:
    verdict = (f"BSH ECONOMICS WORSE under dynamic leverage. "
               f"Net {t2_net:+.2f}pp Ann ROE (vs Tier 1 {t1_net:+.2f}pp). "
               f"Tier 1 verdict (DROP BSH) reinforced — adding leverage doesn't help.")

print(f"  {verdict}")

# ─── Save ─────────────────────────────────────────────────────────────────────
out_dir = _ROOT / "research" / "q058"
out_dir.mkdir(exist_ok=True)
out_pkl = out_dir / "q058_tier2a_dynlev_bsh.pkl"
with open(out_pkl, 'wb') as f:
    pickle.dump({
        'metrics': cmp_df,
        'variants': variants,
        'verdict': verdict,
        't1_net_effect_pp': t1_net,
        't2_net_effect_pp': t2_net,
    }, f)
print(f"\n  Saved: {out_pkl}")
