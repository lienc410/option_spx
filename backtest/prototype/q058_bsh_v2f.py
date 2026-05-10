"""
Q058 Tier 1 — BSH Economics Under V2f Framework
================================================

Question: V2f reduced worst trade from -15.5% (V2 no-stop) to -10.96% NLV.
Does BSH still earn its cost drag, or has V2f's tail improvement made BSH
net-negative under this framework?

Method:
  Run three variants on SAME 2000-2026 BS-flat synthetic data, $500k account:

  V2f_alone         : Pure V2f (matches SPEC-095 baseline result)
  V2f_bsh_cost      : V2f + BSH weekly cost (0.04% NLV) + monthly VIX call cost (0.08% if VIX<15)
  V2f_bsh_full      : V2f + BSH cost + BSH SPY put payoff (full Phase 4 BSH MTM model)

Strict scope (Tier 1):
  - NO VIX dynamic leverage (Phase 3 feature; Tier 2 follow-up)
  - V2f parameters identical: entry=49 trading days, exit@21, STOP=15, MAX_SLOTS=5,
    weekly cadence, profit=10% mark
  - Trend filter: baseline mode (no filter) — matches SPEC-095 cited result

Decision framework:
  V2f+full ROE > V2f alone → BSH net-positive in V2f → keep BSH research alive
  V2f+full ROE < V2f alone (Sharpe also worse) → BSH net-negative → drop
  Tail improves but ROE down ≥1pp → PM tradeoff decision
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

# V2f params (matches SPEC-095)
V2F_ENTRY_DTE  = 49
V2F_EXIT_DTE   = 21
V2F_MAX_SLOTS  = 5
V2F_STOP_MULT  = 15.0

# BSH params (from backtest.py)
BSH_WEEKLY_COST_PCT  = 0.0004
BSH_MONTHLY_COST_PCT = 0.0008
BSH_VIX_THRESHOLD    = 15.0

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

# ─── Unified V2f simulator with BSH layering ──────────────────────────────────
def run_v2f_with_bsh(sim_df, bsh_mode="alone"):
    """
    bsh_mode:
      'alone'    — pure V2f, no BSH
      'cost'     — V2f + BSH cost drag only (no payoff)
      'full'     — V2f + BSH cost + Phase-4-style SPY put payoff
    """
    positions = []          # short SPX puts
    bsh_puts  = []          # long SPY BSH puts (only used in 'full' mode)
    short_trades  = []
    bsh_realized  = 0.0
    bsh_total_cost = 0.0
    bsh_total_payoff_realized = 0.0
    daily_pnl_log = []
    equity = ACCOUNT
    peak_eq = ACCOUNT
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

        # ── BSH cost drag (cost / full only) ────────────────────────────────
        if bsh_mode in ("cost", "full"):
            if day_counter % WEEKLY_TD == 0:
                cost = equity * BSH_WEEKLY_COST_PCT
                if bsh_mode == "cost":
                    daily_pnl -= cost
                    bsh_total_cost += cost
                # In 'full' mode, the cost is absorbed by the put purchase below
                # (cost = budget; payoff modeled via MTM on the put position)
            if day_counter % 21 == 0 and vix < BSH_VIX_THRESHOLD:
                cost = equity * BSH_MONTHLY_COST_PCT
                daily_pnl -= cost                # cost-only for VIX call (Phase 4 convention)
                bsh_total_cost += cost

        # ── BSH put purchase (full mode) ────────────────────────────────────
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
                # Day-0 net pnl from purchase: 0 (paid budget, holding put worth budget)

        # ── BSH puts daily MTM (full mode) ──────────────────────────────────
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
            pnl_delta = (pos['prev_val'] - cur_val) * SPX_MULT
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
                trade_pnl = (pos['entry_prem'] - cur_val) * SPX_MULT
                short_trades.append({
                    'entry_date': pos['entry_date'], 'exit_date': dstr,
                    'pnl_$': trade_pnl, 'exit_reason': reason,
                    'year': pd.Timestamp(pos['entry_date']).year,
                })
            else:
                pos['prev_val'] = cur_val
                still_open.append(pos)
        positions = still_open

        # ── V2f entry ───────────────────────────────────────────────────────
        days_since_entry += 1
        if (days_since_entry >= WEEKLY_TD
            and i >= 64
            and len(positions) < V2F_MAX_SLOTS):
            K = find_strike_for_delta(spx, V2F_ENTRY_DTE, sigma, TARGET_DELTA)
            entry_prem = bs_put_price(spx, K, V2F_ENTRY_DTE, sigma)
            if entry_prem > 0.5:
                positions.append({
                    'entry_date': dstr, 'dte': V2F_ENTRY_DTE, 'K': K,
                    'entry_prem': entry_prem,
                    'stop_prem': entry_prem * V2F_STOP_MULT,
                    'profit_prem': entry_prem * PROFIT_FRAC,
                    'prev_val': entry_prem,
                })
                days_since_entry = 0

        # ── End-of-day equity ────────────────────────────────────────────────
        equity += daily_pnl
        peak_eq = max(peak_eq, equity)
        daily_pnl_log.append({'date': date, 'daily_pnl': daily_pnl, 'equity': equity})
        eq_curve.append(equity)

    # Force-close at end of window
    last_row = sim_df.iloc[-1]
    last_spx = float(last_row["spx"])
    last_vix = float(last_row["vix"])
    last_sigma = last_vix / 100.0
    last_date = sim_df.index[-1].strftime("%Y-%m-%d")
    for pos in positions:
        cur_val = bs_put_price(last_spx, pos['K'], max(pos['dte'], 0), last_sigma)
        trade_pnl = (pos['entry_prem'] - cur_val) * SPX_MULT
        short_trades.append({
            'entry_date': pos['entry_date'], 'exit_date': last_date,
            'pnl_$': trade_pnl, 'exit_reason': 'end_of_window',
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

# ─── Run three variants ──────────────────────────────────────────────────────
print("\nRunning three variants...")
print("  V2f_alone (no BSH)...")
r_alone = run_v2f_with_bsh(sim_df, bsh_mode="alone")
print(f"    short trades: {len(r_alone['short_trades'])}, final equity: ${r_alone['final_equity']:,.0f}")

print("  V2f_bsh_cost (BSH cost drag only)...")
r_cost = run_v2f_with_bsh(sim_df, bsh_mode="cost")
print(f"    short trades: {len(r_cost['short_trades'])}, final equity: ${r_cost['final_equity']:,.0f}")
print(f"    BSH total cost: ${r_cost['bsh_total_cost']:,.0f} ({r_cost['bsh_total_cost']/ACCOUNT*100:.1f}% of initial)")

print("  V2f_bsh_full (BSH cost + payoff)...")
r_full = run_v2f_with_bsh(sim_df, bsh_mode="full")
print(f"    short trades: {len(r_full['short_trades'])}, final equity: ${r_full['final_equity']:,.0f}")
print(f"    BSH realized payoffs: ${r_full['bsh_total_payoff_realized']:,.0f}")

# ─── Compute metrics ─────────────────────────────────────────────────────────
def metrics(r, label):
    short = r['short_trades']
    final = r['final_equity']
    total_pnl = final - ACCOUNT
    cum_ret = total_pnl / ACCOUNT
    ann_geom = ((1 + cum_ret) ** (1/YEARS) - 1) * 100 if cum_ret > -1 else float('nan')

    # Short-trade metrics (V2f cycles)
    short_pnls = short['pnl_$'].values if len(short) > 0 else np.array([])
    worst_short = short_pnls.min() if len(short_pnls) > 0 else 0
    worst_short_pct = worst_short / ACCOUNT * 100
    wr = (short_pnls > 0).mean() * 100 if len(short_pnls) > 0 else 0

    # Account-level Sharpe via daily PnL
    daily = r['daily_pnl_log']['daily_pnl'].values
    daily_ret = daily / ACCOUNT
    sharpe_ann = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0

    # MDD on equity curve
    eq = np.array(r['eq_curve'])
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    mdd_pct = dd.min() * 100

    return {
        'label': label,
        'short_n': len(short),
        'final_equity_$': round(final, 0),
        'total_pnl_$': round(total_pnl, 0),
        'ann_roe_geom_%': round(ann_geom, 2),
        'short_wr_%': round(wr, 1),
        'worst_short_$': round(worst_short, 0),
        'worst_short_pct_nlv': round(worst_short_pct, 2),
        'sharpe_ann': round(sharpe_ann, 2),
        'mdd_%': round(mdd_pct, 1),
        'bsh_cost_$': round(r['bsh_total_cost'], 0),
        'bsh_payoff_realized_$': round(r['bsh_total_payoff_realized'], 0),
    }

m_alone = metrics(r_alone, "V2f_alone")
m_cost  = metrics(r_cost, "V2f_bsh_cost")
m_full  = metrics(r_full, "V2f_bsh_full")

# ─── Print comparison table ───────────────────────────────────────────────────
print(f"\n{'='*92}")
print(f"  Q058 Tier 1 — BSH Economics Under V2f Framework")
print(f"  Window: {WINDOW_START} → {WINDOW_END} ({YEARS:.1f} yr) | $500k account | NO dynamic leverage")
print(f"{'='*92}\n")

cols = ['short_n', 'total_pnl_$', 'ann_roe_geom_%', 'short_wr_%',
        'worst_short_$', 'worst_short_pct_nlv', 'sharpe_ann', 'mdd_%',
        'bsh_cost_$', 'bsh_payoff_realized_$']
df = pd.DataFrame([m_alone, m_cost, m_full])
print(df.to_string(index=False))

# ─── 2020 COVID cycle analysis ───────────────────────────────────────────────
print(f"\n  ── 2020 COVID Year Detail (BSH's stress-test moment) ──")
for r, label in [(r_alone, "V2f_alone"), (r_cost, "V2f_bsh_cost"), (r_full, "V2f_bsh_full")]:
    sub = r['short_trades']
    sub2020 = sub[sub['year'] == 2020] if 'year' in sub.columns else pd.DataFrame()
    if len(sub2020) > 0:
        worst = sub2020['pnl_$'].min()
        total = sub2020['pnl_$'].sum()
        # Daily PnL for 2020
        daily_2020 = r['daily_pnl_log'][
            (r['daily_pnl_log']['date'] >= '2020-01-01') &
            (r['daily_pnl_log']['date'] < '2021-01-01')
        ]
        if len(daily_2020) > 0:
            year_pnl_2020 = daily_2020['daily_pnl'].sum()
        else:
            year_pnl_2020 = 0
        print(f"    {label:<18}: short trades worst=${worst:,.0f}, "
              f"short-only total=${total:,.0f}, "
              f"all-in daily-pnl total (incl BSH)=${year_pnl_2020:,.0f}")

# ─── Decision verdict ────────────────────────────────────────────────────────
print(f"\n{'='*92}")
print(f"  DECISION FRAMEWORK")
print(f"{'='*92}\n")

print(f"  V2f alone:           Ann ROE {m_alone['ann_roe_geom_%']:+.2f}%, MDD {m_alone['mdd_%']:.1f}%, Sharpe {m_alone['sharpe_ann']:.2f}")
print(f"  V2f + BSH cost:      Ann ROE {m_cost['ann_roe_geom_%']:+.2f}%, MDD {m_cost['mdd_%']:.1f}%, Sharpe {m_cost['sharpe_ann']:.2f}")
print(f"  V2f + BSH full:      Ann ROE {m_full['ann_roe_geom_%']:+.2f}%, MDD {m_full['mdd_%']:.1f}%, Sharpe {m_full['sharpe_ann']:.2f}")

cost_drag = m_alone['ann_roe_geom_%'] - m_cost['ann_roe_geom_%']
net_effect = m_full['ann_roe_geom_%'] - m_alone['ann_roe_geom_%']
mdd_improvement = m_alone['mdd_%'] - m_full['mdd_%']

print(f"\n  Cost drag (alone - cost-only):     {cost_drag:+.2f}pp")
print(f"  Net effect (full - alone):         {net_effect:+.2f}pp")
print(f"  MDD improvement (full vs alone):   {mdd_improvement:+.1f}pp")
print(f"  Sharpe Δ (full vs alone):          {m_full['sharpe_ann'] - m_alone['sharpe_ann']:+.2f}")

if net_effect > 0:
    if m_full['sharpe_ann'] > m_alone['sharpe_ann']:
        verdict = "BSH NET-POSITIVE in V2f — ROE up + Sharpe up. Keep BSH research alive."
    else:
        verdict = "BSH ROE-positive but Sharpe-neutral — payoff structure helps absolute return only."
elif net_effect > -1.0:
    verdict = (f"BSH borderline: ROE drag {-net_effect:+.2f}pp < 1pp. "
               f"PM tradeoff: Sharpe Δ {m_full['sharpe_ann']-m_alone['sharpe_ann']:+.2f}, "
               f"MDD improvement {mdd_improvement:+.1f}pp.")
elif m_full['sharpe_ann'] > m_alone['sharpe_ann']:
    verdict = (f"BSH ROE-negative ({net_effect:+.2f}pp) but Sharpe-positive. "
               f"PM tradeoff: insurance premium for risk reduction.")
else:
    verdict = (f"BSH NET-NEGATIVE in V2f — ROE down {-net_effect:+.2f}pp, Sharpe also worse. "
               f"V2f's tail improvement makes BSH redundant. RECOMMEND DROP.")

print(f"\n  VERDICT: {verdict}")

# ─── Save ─────────────────────────────────────────────────────────────────────
out_dir = _ROOT / "research" / "q058"
out_dir.mkdir(exist_ok=True)
out_pkl = out_dir / "q058_bsh_v2f_results.pkl"
with open(out_pkl, 'wb') as f:
    pickle.dump({
        'metrics': df,
        'r_alone': r_alone,
        'r_cost': r_cost,
        'r_full': r_full,
        'verdict': verdict,
        'cost_drag_pp': cost_drag,
        'net_effect_pp': net_effect,
    }, f)
print(f"\n  Saved: {out_pkl}")
