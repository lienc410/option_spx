"""
Q061 Tier 1 — M1 + M2 Alpha Impact on V2f
==========================================

Quantify how the two PM-authorized tail-control rules affect V2f baseline alpha:

  M1: Cluster-loss monitor — when n_active_positions >= 4, extend entry
      cadence from every 5 TD to every 10 TD.
  M2: VIX-jump entry pause — when VIX 5-day return > 50%, pause new entries
      (existing positions continue to be managed).

Four variants compared on full 26-yr BS-flat window:
  V0: V2f_alone (baseline)         — for sanity match against Q060 (+2.46% / 0.15)
  V1: V2f + M1
  V2: V2f + M2
  V3: V2f + M1 + M2

For each: Ann ROE (geometric), Sharpe (daily), 1987-magnitude stress worst single
trade and account-level cluster loss (anchor 2022-11-09, SPX -7%/d × 5, VIX 25→60).

Decision framework:
  • If a variant restores 1987 stress worst single trade < -15% NLV (V1 veto holds)
    AND Ann ROE loss < 0.5pp vs V2f_alone → recommend SPEC integration.
  • If alpha loss > 0.5pp → escalate to PM (insurance-cost trade-off).
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
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_ES_FILE = _ROOT / "research" / "strategies" / "ES_puts" / "backtest.py"
import importlib.util
spec_es = importlib.util.spec_from_file_location("es_backtest_mod", _ES_FILE)
es_mod = importlib.util.module_from_spec(spec_es)
sys.modules["es_backtest_mod"] = es_mod
spec_es.loader.exec_module(es_mod)

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

# ─── M1 / M2 parameters ───────────────────────────────────────────────────────
M1_THRESHOLD       = 4    # n_active_positions
M1_CLUSTER_FREQ_TD = 10   # extended cadence when triggered
M2_VIX_LOOKBACK_TD = 5
M2_VIX_JUMP        = 0.50 # +50% over 5 TD → pause

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

# ─── Simulator with M1 / M2 toggles (alone-mode, fixed 1 contract) ───────────
def run_v2f(sim_df, m1=False, m2=False):
    positions = []
    short_trades = []
    daily_log = []
    equity = ACCOUNT
    days_since_entry = WEEKLY_TD

    vix_arr = sim_df['vix'].values

    for i, (date, row) in enumerate(sim_df.iterrows()):
        spx = float(row["spx"]); vix = float(row["vix"])
        sigma = vix / 100.0
        dstr = date.strftime("%Y-%m-%d")
        eq_at_open = equity
        daily_pnl = 0.0

        # Manage existing positions
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
                    'contracts': pos['contracts'], 'entry_vix': pos['entry_vix'],
                    'entry_spx': pos['entry_spx'], 'K': pos['K'],
                    'year': pd.Timestamp(pos['entry_date']).year,
                })
            else:
                pos['prev_val'] = cur_val
                still_open.append(pos)
        positions = still_open

        # Entry decision
        days_since_entry += 1

        # M1: extended cadence if cluster threshold met
        required_freq = WEEKLY_TD
        if m1 and len(positions) >= M1_THRESHOLD:
            required_freq = M1_CLUSTER_FREQ_TD

        # M2: VIX 5-day jump pause
        vix_pause = False
        if m2 and i >= M2_VIX_LOOKBACK_TD:
            v_prev = vix_arr[i - M2_VIX_LOOKBACK_TD]
            if v_prev > 0:
                jump = (vix - v_prev) / v_prev
                vix_pause = jump > M2_VIX_JUMP

        warmed = i >= 64
        should_enter = (
            warmed
            and days_since_entry >= required_freq
            and not vix_pause
            and len(positions) < V2F_MAX_SLOTS
        )

        if should_enter:
            K = find_strike_for_delta(spx, V2F_ENTRY_DTE, sigma, TARGET_DELTA)
            entry_prem = bs_put_price(spx, K, V2F_ENTRY_DTE, sigma)
            if entry_prem > 0.5:
                positions.append({
                    'entry_date': dstr, 'dte': V2F_ENTRY_DTE, 'K': K,
                    'entry_prem': entry_prem,
                    'stop_prem': entry_prem * V2F_STOP_MULT,
                    'profit_prem': entry_prem * PROFIT_FRAC,
                    'prev_val': entry_prem,
                    'contracts': 1.0,
                    'entry_vix': vix,
                    'entry_spx': spx,
                })
                days_since_entry = 0

        equity += daily_pnl
        daily_ret = daily_pnl / eq_at_open if eq_at_open > 0 else 0.0
        daily_log.append({'date': date, 'spx': spx, 'vix': vix,
                          'daily_pnl': daily_pnl, 'equity': equity,
                          'daily_ret': daily_ret,
                          'n_positions': len(positions)})

    # Force-close remainder
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
            'contracts': pos['contracts'], 'entry_vix': pos['entry_vix'],
            'entry_spx': pos['entry_spx'], 'K': pos['K'],
            'year': pd.Timestamp(pos['entry_date']).year,
        })

    return {
        'short_trades': pd.DataFrame(short_trades),
        'daily_log': pd.DataFrame(daily_log),
        'final_equity': equity,
    }


def perf_metrics(result):
    """Geometric Ann ROE + daily-return Sharpe + worst trade."""
    trades = result['short_trades']
    log = result['daily_log']
    final_eq = result['final_equity']
    n_days = len(log)
    years_eff = n_days / TRADING_DAYS
    ann_roe_geo = ((final_eq / ACCOUNT) ** (1.0 / years_eff) - 1.0) * 100 if years_eff > 0 else 0.0
    rets = log['daily_ret'].values
    mu = float(np.mean(rets))
    sd = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0.0
    sharpe = (mu / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0
    worst_pnl = float(trades['pnl_$'].min()) if len(trades) > 0 else 0.0
    worst_pct = worst_pnl / ACCOUNT * 100
    n_trades = len(trades)
    return {
        'ann_roe': ann_roe_geo,
        'sharpe': sharpe,
        'worst_full_$': worst_pnl,
        'worst_full_pct': worst_pct,
        'n_trades': n_trades,
        'final_equity': final_eq,
    }


# ─── Build shocked sim_df (mirrors Q060 Task B exactly) ──────────────────────
def build_shocked(sim_df):
    anchor_target = pd.Timestamp("2022-11-09")
    mask = sim_df.index >= anchor_target
    anchor_idx = mask.argmax()
    anchor_actual_date = sim_df.index[anchor_idx]
    anchor_spx = sim_df.iloc[anchor_idx]['spx']
    anchor_vix = sim_df.iloc[anchor_idx]['vix']

    shocked = sim_df.copy()
    shock_indices = list(range(anchor_idx + 1, anchor_idx + 6))
    spx_at_t5 = anchor_spx * (0.93 ** 5)
    vix_target_at_t5 = 60.0
    for i_, idx in enumerate(shock_indices, start=1):
        new_spx = anchor_spx * (0.93 ** i_)
        new_vix = anchor_vix + (vix_target_at_t5 - anchor_vix) * (i_ / 5)
        d = sim_df.index[idx]
        shocked.loc[d, 'spx'] = new_spx
        shocked.loc[d, 'vix'] = new_vix

    recovery_indices = list(range(anchor_idx + 6, anchor_idx + 16))
    for j, idx in enumerate(recovery_indices, start=1):
        if idx >= len(sim_df):
            break
        new_vix = vix_target_at_t5 - (vix_target_at_t5 - anchor_vix) * (j / 10)
        d = sim_df.index[idx]
        shocked.loc[d, 'vix'] = new_vix

    shock_factor = spx_at_t5 / sim_df.iloc[anchor_idx + 5]['spx']
    post_shock_dates = sim_df.index[anchor_idx + 6:]
    for d in post_shock_dates:
        shocked.loc[d, 'spx'] = sim_df.loc[d, 'spx'] * shock_factor

    return {
        'shocked': shocked,
        'anchor_date': anchor_actual_date,
        'anchor_idx': anchor_idx,
        'anchor_spx': anchor_spx,
        'anchor_vix': anchor_vix,
        'shock_factor': shock_factor,
        'shock_end': sim_df.index[anchor_idx + 15],
    }


def shock_outcomes(result, shock_start, shock_end):
    """Extract worst single trade active in shock window + cluster cumulative loss."""
    trades = result['short_trades'].copy()
    log = result['daily_log'].copy()
    if len(trades) == 0:
        return {'worst_single_$': 0, 'worst_single_pct': 0,
                'cluster_$': 0, 'cluster_pct': 0, 'n_active': 0}
    trades['entry_dt'] = pd.to_datetime(trades['entry_date'])
    trades['exit_dt']  = pd.to_datetime(trades['exit_date'])
    active = trades[(trades['entry_dt'] <= shock_end) &
                    (trades['exit_dt'] >= shock_start)]
    if len(active) == 0:
        worst_single_pnl = 0.0
    else:
        worst_single_pnl = float(active['pnl_$'].min())

    sub = log[(log['date'] >= shock_start) & (log['date'] <= shock_end)]
    if len(sub) == 0:
        return {'worst_single_$': worst_single_pnl,
                'worst_single_pct': worst_single_pnl / ACCOUNT * 100,
                'cluster_$': 0, 'cluster_pct': 0,
                'n_active': len(active)}
    cum = sub['daily_pnl'].cumsum()
    worst_cum = float(cum.min())
    eq_pre = float(sub['equity'].iloc[0] - sub['daily_pnl'].iloc[0])
    return {
        'worst_single_$': worst_single_pnl,
        'worst_single_pct': worst_single_pnl / ACCOUNT * 100,
        'cluster_$': worst_cum,
        'cluster_pct': worst_cum / eq_pre * 100,
        'n_active': len(active),
    }


# ─── Run all variants ────────────────────────────────────────────────────────
print("Loading market data...")
data, _ = es_mod._load_data()
sim_df = data[(data.index >= pd.Timestamp(WINDOW_START)) &
              (data.index <= pd.Timestamp(WINDOW_END))]
print(f"  Trading days: {len(sim_df)}")

shock = build_shocked(sim_df)
print(f"  Stress anchor: {shock['anchor_date'].date()}, "
      f"SPX={shock['anchor_spx']:.0f}, VIX={shock['anchor_vix']:.1f}")
print(f"  Shock window end: {shock['shock_end'].date()}")
shocked_df = shock['shocked']
shock_start = shock['anchor_date']
shock_end = shock['shock_end']

variants = [
    ('V2f_alone',         False, False),
    ('V2f + M1',          True,  False),
    ('V2f + M2',          False, True),
    ('V2f + M1 + M2',     True,  True),
]

print(f"\n{'='*94}")
print("  Running 4 variants on baseline (no-shock) and stressed scenarios")
print(f"{'='*94}\n")

rows = []
detail = {}
for name, m1, m2 in variants:
    print(f"  ▸ {name}  (m1={m1}, m2={m2})")
    base = run_v2f(sim_df, m1=m1, m2=m2)
    perf = perf_metrics(base)
    print(f"      n_trades={perf['n_trades']}, "
          f"AnnROE={perf['ann_roe']:+.2f}%, Sharpe={perf['sharpe']:.2f}, "
          f"worst_full={perf['worst_full_pct']:+.2f}% NLV")

    stress = run_v2f(shocked_df, m1=m1, m2=m2)
    so = shock_outcomes(stress, shock_start, shock_end)
    print(f"      stress: worst_single={so['worst_single_pct']:+.2f}% NLV, "
          f"cluster={so['cluster_pct']:+.2f}%, n_active={so['n_active']}")

    rows.append({
        'variant': name,
        'ann_roe_%': round(perf['ann_roe'], 3),
        'sharpe': round(perf['sharpe'], 3),
        'worst_full_%NLV': round(perf['worst_full_pct'], 2),
        'n_trades': perf['n_trades'],
        'stress_worst_single_%NLV': round(so['worst_single_pct'], 2),
        'stress_cluster_%': round(so['cluster_pct'], 2),
        'stress_n_active': so['n_active'],
    })
    detail[name] = {
        'baseline_perf': perf,
        'stress_outcomes': so,
        'baseline_trades': base['short_trades'],
        'stress_trades': stress['short_trades'],
    }

df_out = pd.DataFrame(rows)

# ─── Comparison table ────────────────────────────────────────────────────────
print(f"\n{'='*94}")
print("  COMPARISON TABLE")
print(f"{'='*94}\n")
print(df_out.to_string(index=False))

# ─── Decision framework ──────────────────────────────────────────────────────
baseline = df_out.iloc[0]
print(f"\n{'='*94}")
print("  DECISION FRAMEWORK")
print(f"{'='*94}\n")
print(f"  Baseline V2f_alone: AnnROE={baseline['ann_roe_%']:+.2f}%, "
      f"stress_worst_single={baseline['stress_worst_single_%NLV']:+.2f}%, "
      f"stress_cluster={baseline['stress_cluster_%']:+.2f}%\n")

verdicts = []
for _, r in df_out.iloc[1:].iterrows():
    delta_alpha = r['ann_roe_%'] - baseline['ann_roe_%']
    veto_restored = r['stress_worst_single_%NLV'] > -15.0
    cluster_improved = r['stress_cluster_%'] > baseline['stress_cluster_%']

    if veto_restored and abs(delta_alpha) <= 0.5:
        verdict = "✅ RECOMMEND SPEC (V1 veto restored, alpha intact)"
    elif veto_restored and delta_alpha > -0.5:
        verdict = "✅ RECOMMEND SPEC (V1 veto restored, alpha gain)"
    elif veto_restored:
        verdict = f"⚠ PM DECISION (veto restored but Δalpha={delta_alpha:+.2f}pp)"
    elif cluster_improved and abs(delta_alpha) <= 0.5:
        verdict = (f"⚠ PARTIAL (cluster improves {r['stress_cluster_%'] - baseline['stress_cluster_%']:+.2f}pp, "
                   f"single still fails V1 veto)")
    else:
        verdict = "❌ INSUFFICIENT (no V1 veto, marginal/no cluster gain)"

    print(f"  {r['variant']:<18}: Δalpha={delta_alpha:+.2f}pp, "
          f"veto_restored={veto_restored}, "
          f"cluster_Δ={r['stress_cluster_%'] - baseline['stress_cluster_%']:+.2f}pp")
    print(f"    → {verdict}\n")
    verdicts.append({'variant': r['variant'], 'delta_alpha': delta_alpha,
                     'veto_restored': veto_restored, 'verdict': verdict})

# ─── Save ────────────────────────────────────────────────────────────────────
out_dir = _ROOT / "research" / "q061"
out_dir.mkdir(parents=True, exist_ok=True)
out_pkl = out_dir / "q061_m1_m2_alpha_impact.pkl"
df_out.to_csv(out_dir / "q061_comparison.csv", index=False)
with open(out_pkl, 'wb') as f:
    pickle.dump({
        'comparison': df_out,
        'verdicts': verdicts,
        'detail': detail,
        'shock_meta': {
            'anchor_date': str(shock['anchor_date'].date()),
            'anchor_spx': float(shock['anchor_spx']),
            'anchor_vix': float(shock['anchor_vix']),
            'shock_factor': float(shock['shock_factor']),
            'shock_end': str(shock['shock_end'].date()),
        },
        'rules': {
            'M1': {'threshold': M1_THRESHOLD, 'cluster_freq_td': M1_CLUSTER_FREQ_TD},
            'M2': {'lookback_td': M2_VIX_LOOKBACK_TD, 'jump_threshold': M2_VIX_JUMP},
        },
    }, f)
print(f"  Saved: {out_pkl}")
print(f"  Saved: {out_dir / 'q061_comparison.csv'}")
