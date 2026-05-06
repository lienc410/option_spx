"""
Q041 Phase 1 – D4 Module C: Earnings IV Crush Event Study
==========================================================
For each Tier-1 stock:
  1. Identify earnings dates (hardcoded calendar, 2022-05 → 2026-04)
  2. Phase A: implied-move vs realized-move premium analysis
  3. Phase B: put-spread credit backtest (entry T-1, exit T+1)
     - width = 0.5× and 1.0× implied move
     - T-3 entry variant
  4. Phase C: iron-condor variant (put spread + call spread)

Output: /tmp/d4_earnings_results.pkl  (dict with DataFrames)
"""

import pandas as pd
import numpy as np
import pickle
from datetime import date, timedelta
from scipy.optimize import brentq
from scipy.stats import ttest_1samp
import warnings
warnings.filterwarnings('ignore')

# ─── Constants ────────────────────────────────────────────────────────────────
DATA_DIR = '/Users/lienchen/Documents/workspace/SPX_strat/data/q041_historical'
TIER1_PX_PATH = '/tmp/tier1_px.pkl'
R = 0.045
SLIP = 0.03          # 3% slippage on premium
F1_FILTER = 0.10     # close > $0.10

# ─── Hardcoded earnings calendar ──────────────────────────────────────────────
EARNINGS_DATES = {
    'AAPL': [
        date(2022, 7, 28), date(2022, 10, 27),
        date(2023, 2, 2),  date(2023, 5, 4),   date(2023, 8, 3),  date(2023, 11, 2),
        date(2024, 2, 1),  date(2024, 5, 2),   date(2024, 8, 1),  date(2024, 10, 31),
        date(2025, 1, 30), date(2025, 5, 1),   date(2025, 7, 31), date(2025, 10, 30),
        date(2026, 1, 29),
    ],
    'MSFT': [
        date(2022, 7, 26), date(2022, 10, 25),
        date(2023, 1, 24), date(2023, 4, 25), date(2023, 7, 25), date(2023, 10, 24),
        date(2024, 1, 30), date(2024, 4, 25), date(2024, 7, 30), date(2024, 10, 30),
        date(2025, 1, 29), date(2025, 4, 30), date(2025, 7, 30), date(2025, 10, 29),
        date(2026, 1, 29),
    ],
    'AMZN': [
        date(2022, 7, 28), date(2022, 10, 27),
        date(2023, 2, 2),  date(2023, 4, 27), date(2023, 8, 3),  date(2023, 10, 26),
        date(2024, 2, 1),  date(2024, 5, 2),  date(2024, 8, 1),  date(2024, 10, 31),
        date(2025, 2, 6),  date(2025, 5, 1),  date(2025, 8, 1),  date(2025, 10, 30),
        date(2026, 2, 5),
    ],
    'GOOGL': [
        date(2022, 7, 26), date(2022, 10, 25),
        date(2023, 2, 2),  date(2023, 4, 25), date(2023, 7, 25), date(2023, 10, 24),
        date(2024, 1, 30), date(2024, 4, 25), date(2024, 7, 29), date(2024, 10, 29),
        date(2025, 2, 4),  date(2025, 4, 29), date(2025, 7, 29), date(2025, 10, 28),
        date(2026, 2, 4),
    ],
    'META': [
        date(2022, 7, 27), date(2022, 10, 26),
        date(2023, 2, 1),  date(2023, 4, 26), date(2023, 7, 26), date(2023, 10, 25),
        date(2024, 2, 1),  date(2024, 4, 24), date(2024, 7, 31), date(2024, 10, 30),
        date(2025, 1, 29), date(2025, 4, 30), date(2025, 7, 30), date(2025, 10, 29),
        date(2026, 1, 29),
    ],
    'JPM': [
        date(2022, 7, 14), date(2022, 10, 14),
        date(2023, 1, 13), date(2023, 4, 14), date(2023, 7, 14), date(2023, 10, 13),
        date(2024, 1, 12), date(2024, 4, 12), date(2024, 7, 12), date(2024, 10, 11),
        date(2025, 1, 15), date(2025, 4, 11), date(2025, 7, 15), date(2025, 10, 14),
        date(2026, 1, 14),
    ],
    'WMT': [
        date(2022, 8, 16), date(2022, 11, 15),
        date(2023, 2, 21), date(2023, 5, 18), date(2023, 8, 17), date(2023, 11, 16),
        date(2024, 2, 20), date(2024, 5, 16), date(2024, 8, 15), date(2024, 11, 19),
        date(2025, 2, 18), date(2025, 5, 15), date(2025, 8, 19), date(2025, 11, 18),
        date(2026, 2, 17),
    ],
    'COST': [
        date(2022, 9, 22), date(2022, 12, 8),
        date(2023, 3, 2),  date(2023, 6, 1),  date(2023, 9, 26), date(2023, 12, 14),
        date(2024, 3, 7),  date(2024, 6, 6),  date(2024, 9, 26), date(2024, 12, 12),
        date(2025, 3, 6),  date(2025, 6, 5),  date(2025, 9, 25), date(2025, 12, 11),
        date(2026, 3, 5),
    ],
}

WINDOW_START = date(2022, 5, 20)
WINDOW_END   = date(2026, 4, 17)

# ─── BAW / BS helpers ─────────────────────────────────────────────────────────
def bs_price(S, K, T, r, sigma, flag):
    from scipy.stats import norm
    if T <= 0 or sigma <= 0: return 0.0
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if flag == 'C':
        return S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
    else:
        return K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)

def bs_iv(price, S, K, T, r, flag):
    if T <= 1e-6 or price <= 0: return np.nan
    intrinsic = max(S-K, 0) if flag == 'C' else max(K-S, 0)
    if price <= intrinsic * 0.999: return np.nan
    try:
        lo, hi = 0.01, 5.0
        if bs_price(S, K, T, r, lo, flag) > price: return np.nan
        if bs_price(S, K, T, r, hi, flag) < price: return np.nan
        return brentq(lambda s: bs_price(S, K, T, r, s, flag) - price,
                      lo, hi, xtol=1e-4, maxiter=50)
    except:
        return np.nan

def bs_delta(S, K, T, r, sigma, flag):
    from scipy.stats import norm
    if T <= 0 or sigma <= 0: return 0.0
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return norm.cdf(d1) if flag == 'C' else norm.cdf(d1) - 1

# ─── Trading day helpers ──────────────────────────────────────────────────────
def prev_trading_day(d, trading_set, n=1):
    """Return the n-th previous trading day before d."""
    current = d - timedelta(days=1)
    count = 0
    while count < n:
        while current not in trading_set:
            current -= timedelta(days=1)
        if count < n - 1:
            current -= timedelta(days=1)
        count += 1
    return current

def next_trading_day(d, trading_set, n=1):
    current = d + timedelta(days=1)
    count = 0
    while count < n:
        while current not in trading_set:
            current += timedelta(days=1)
        if count < n - 1:
            current += timedelta(days=1)
        count += 1
    return current

# ─── Find nearest post-earnings expiry ───────────────────────────────────────
def nearest_post_earnings_expiry(earnings_date, all_expiries):
    """
    Return the nearest expiry that is >= earnings_date AND <= earnings_date + 14 days.
    This captures weekly options that expire right after earnings (1-2 weeks).
    Falls back to the nearest expiry within 30 days if no weekly found.
    """
    candidates = sorted([e for e in all_expiries
                         if earnings_date <= e <= earnings_date + timedelta(days=30)])
    return candidates[0] if candidates else None

# ─── Main per-stock analysis ──────────────────────────────────────────────────
def analyze_stock(sym, df_opt, px_dict, trading_days):
    """
    Run implied-move and spread backtest for one stock.
    Returns list of event dicts.
    """
    events = []

    e_dates = [d for d in EARNINGS_DATES.get(sym, [])
               if WINDOW_START <= d <= WINDOW_END]

    all_expiries_in_data = sorted(df_opt['expiry'].unique())

    for earn_date in e_dates:
        # Step 1: find entry date (T-1 and T-3)
        for entry_lag in [1, 3, 7]:
            entry_date = prev_trading_day(earn_date, trading_days, n=entry_lag)
            if entry_date < WINDOW_START:
                continue

            # Entry stock price
            S = px_dict.get(entry_date)
            if S is None or S <= 0:
                continue

            # Exit date (T+1)
            exit_date = next_trading_day(earn_date, trading_days, n=1)
            if exit_date > WINDOW_END:
                continue
            S_exit = px_dict.get(exit_date)
            if S_exit is None:
                continue

            # Earnings day stock price (for realized move)
            S_earn = px_dict.get(earn_date) or px_dict.get(
                next_trading_day(earn_date - timedelta(days=1), trading_days, n=1))

            # Find nearest post-earnings expiry
            expiry = nearest_post_earnings_expiry(earn_date, all_expiries_in_data)
            if expiry is None:
                continue

            T_years = max((expiry - entry_date).days / 365.0, 1/365)

            # Filter to entry date, chosen expiry
            day_calls = df_opt[
                (df_opt['date'] == entry_date) &
                (df_opt['expiry'] == expiry) &
                (df_opt['option_type'] == 'C') &
                (df_opt['close'] > F1_FILTER)
            ].copy()
            day_puts = df_opt[
                (df_opt['date'] == entry_date) &
                (df_opt['expiry'] == expiry) &
                (df_opt['option_type'] == 'P') &
                (df_opt['close'] > F1_FILTER)
            ].copy()

            if day_calls.empty or day_puts.empty:
                continue

            # Find ATM call: closest strike to S
            day_calls['dist'] = (day_calls['strike'] - S).abs()
            day_puts['dist']  = (day_puts['strike']  - S).abs()
            atm_call_row = day_calls.loc[day_calls['dist'].idxmin()]
            atm_put_row  = day_puts.loc[day_puts['dist'].idxmin()]

            K_atm = atm_call_row['strike']
            atm_call_px = float(atm_call_row['close'])
            atm_put_px  = float(atm_put_row['close'])

            # Implied move
            straddle_px   = atm_call_px + atm_put_px
            implied_move  = straddle_px / S        # as fraction

            # Realized move
            realized_move = abs(S_exit - S) / S    # from entry to T+1

            premium       = implied_move - realized_move

            # Implied move in dollar terms
            impl_move_dol = implied_move * S

            # ── Phase B: Put spread backtest ───────────────────────────────
            for width_mult in [0.5, 1.0]:
                spread_width = impl_move_dol * width_mult  # dollar width

                # Short put: ATM (K_atm)
                # Long put: K_atm - spread_width (OTM)
                K_long = K_atm - spread_width

                # Find closest available long put strike on entry date
                long_put_cands = day_puts[day_puts['strike'] <= K_atm].copy()
                if long_put_cands.empty:
                    continue
                long_put_cands['dist_k'] = (long_put_cands['strike'] - K_long).abs()
                long_put_row = long_put_cands.loc[long_put_cands['dist_k'].idxmin()]

                K_long_actual  = float(long_put_row['strike'])
                long_put_px    = float(long_put_row['close'])

                # Net credit at entry (after slippage)
                net_credit = (atm_put_px - long_put_px) * (1 - SLIP)
                if net_credit <= 0:
                    continue

                # Max loss = spread_width_actual - net_credit
                actual_spread_w = K_atm - K_long_actual
                max_loss = actual_spread_w - net_credit

                # Settlement at T+1
                short_settle = max(0.0, K_atm - S_exit)
                long_settle  = max(0.0, K_long_actual - S_exit)
                settle_cost  = short_settle - long_settle   # cost to close at expiry value

                pnl = net_credit - settle_cost

                events.append({
                    'symbol'        : sym,
                    'earn_date'     : earn_date,
                    'entry_date'    : entry_date,
                    'exit_date'     : exit_date,
                    'entry_lag'     : entry_lag,
                    'expiry'        : expiry,
                    'dte_entry'     : (expiry - entry_date).days,
                    'S_entry'       : S,
                    'S_exit'        : S_exit,
                    'K_atm'         : K_atm,
                    'K_long'        : K_long_actual,
                    'atm_put_px'    : atm_put_px,
                    'long_put_px'   : long_put_px,
                    'net_credit'    : net_credit,
                    'max_loss'      : max_loss,
                    'settle_cost'   : settle_cost,
                    'pnl'           : pnl,
                    'implied_move'  : implied_move,
                    'realized_move' : realized_move,
                    'premium'       : premium,
                    'straddle_px'   : straddle_px,
                    'width_mult'    : width_mult,
                    'spread_type'   : 'put',
                    'win'           : pnl > 0,
                })

            # ── Phase C: Iron Condor variant ───────────────────────────────
            for width_mult in [0.5, 1.0]:
                spread_width = impl_move_dol * width_mult

                # Put spread side
                K_long_put = K_atm - spread_width
                long_put_cands = day_puts[day_puts['strike'] <= K_atm].copy()
                if long_put_cands.empty:
                    continue
                long_put_cands['dk'] = (long_put_cands['strike'] - K_long_put).abs()
                lp_row = long_put_cands.loc[long_put_cands['dk'].idxmin()]
                K_lp = float(lp_row['strike'])
                lp_px = float(lp_row['close'])

                # Call spread side
                atm_call_cands = day_calls[day_calls['strike'] >= K_atm].copy()
                K_long_call = K_atm + spread_width
                long_call_cands = day_calls[day_calls['strike'] >= K_atm].copy()
                if long_call_cands.empty:
                    continue
                long_call_cands['dk'] = (long_call_cands['strike'] - K_long_call).abs()
                lc_row = long_call_cands.loc[long_call_cands['dk'].idxmin()]
                K_lc = float(lc_row['strike'])
                lc_px = float(lc_row['close'])

                # Net credit (both sides, after slip)
                put_credit  = (atm_put_px - lp_px) * (1 - SLIP)
                call_credit = (atm_call_px - lc_px) * (1 - SLIP)
                net_credit_ic = put_credit + call_credit
                if net_credit_ic <= 0:
                    continue

                # Settlement
                put_settle  = max(0, K_atm - S_exit) - max(0, K_lp - S_exit)
                call_settle = max(0, S_exit - K_atm) - max(0, S_exit - K_lc)
                ic_settle = put_settle + call_settle

                pnl_ic = net_credit_ic - ic_settle

                events.append({
                    'symbol'        : sym,
                    'earn_date'     : earn_date,
                    'entry_date'    : entry_date,
                    'exit_date'     : exit_date,
                    'entry_lag'     : entry_lag,
                    'expiry'        : expiry,
                    'dte_entry'     : (expiry - entry_date).days,
                    'S_entry'       : S,
                    'S_exit'        : S_exit,
                    'K_atm'         : K_atm,
                    'K_long'        : K_lp,       # put protection
                    'atm_put_px'    : atm_put_px,
                    'long_put_px'   : lp_px,
                    'net_credit'    : net_credit_ic,
                    'max_loss'      : K_atm - K_lp - net_credit_ic,
                    'settle_cost'   : ic_settle,
                    'pnl'           : pnl_ic,
                    'implied_move'  : implied_move,
                    'realized_move' : realized_move,
                    'premium'       : premium,
                    'straddle_px'   : straddle_px,
                    'width_mult'    : width_mult,
                    'spread_type'   : 'condor',
                    'win'           : pnl_ic > 0,
                })

    return events


# ─── Run all stocks ───────────────────────────────────────────────────────────
print("Loading price data...")
with open(TIER1_PX_PATH, 'rb') as f:
    tier1_px = pickle.load(f)

all_events = []
symbols = list(EARNINGS_DATES.keys())

for sym in symbols:
    print(f"  Processing {sym}...", end=' ', flush=True)
    try:
        df_opt = pd.read_parquet(f"{DATA_DIR}/{sym}.parquet")
        # Ensure date/expiry are Python date objects
        if df_opt['date'].dtype != object:
            df_opt['date'] = pd.to_datetime(df_opt['date']).dt.date
        else:
            df_opt['date'] = pd.to_datetime(df_opt['date']).dt.date

        df_opt['expiry'] = pd.to_datetime(df_opt['expiry']).dt.date
        df_opt['strike'] = df_opt['strike'].astype(float)
        df_opt['close']  = df_opt['close'].astype(float)

        px_dict = tier1_px[sym]    # date → price dict
        trading_days = set(px_dict.keys())

        events = analyze_stock(sym, df_opt, px_dict, trading_days)
        all_events.extend(events)
        print(f"{len(events)} records")
    except Exception as e:
        print(f"ERROR: {e}")

print(f"\nTotal records: {len(all_events)}")
df_all = pd.DataFrame(all_events)
print(df_all.shape)
print(df_all.head(3).to_string())

with open('/tmp/d4_earnings_results.pkl', 'wb') as f:
    pickle.dump(df_all, f)
print("\nSaved → /tmp/d4_earnings_results.pkl")
