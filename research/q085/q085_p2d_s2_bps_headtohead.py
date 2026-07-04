"""Q085 P2d — the missing test (PM full-review challenge, 2026-07-04).

PM: "all signals failed vs your benchmarks, yet we PROVED the incumbent
anti-times entries — so test challengers against THE INCUMBENT, not the
average day."

Two arms, IDENTICAL BPS simulation (house params: 30 DTE, short put d0.30,
long put d0.15, exit at 21 DTE ~9cd hold; BS-flat sigma=VIX/100; model
errors apply equally to both arms so the COMPARISON is robust):

  INCUMBENT : actual allowed bull_put_spread days (production selector output)
  CHALLENGER: blocked & NORMAL & oversold (rsi2<10 | down3) days
              — the entries the IVP gate currently forbids

Both sequential non-overlapping. Metrics: per-trade PnL, win rate, credit
richness, breach rate, CVaR, worst-7y era (SAME bracket applied to BOTH —
exposing whether the incumbent passes the bar we held challengers to),
today-scale net $/yr.
"""
from __future__ import annotations
import sys
import math
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q085_battery_lib as B

R, Q = 0.05, 0.013
DTE, EXIT_DTE = 30, 21
SHORT_D, LONG_D = 0.30, 0.15

def _ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def put_price(S, K, dte, sig):
    T = dte / 365.0
    if T <= 0 or sig <= 0:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + (R - Q + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    return K * math.exp(-R * T) * _ncdf(-d2) - S * math.exp(-Q * T) * _ncdf(-d1)

def put_delta_abs(S, K, dte, sig):
    T = dte / 365.0
    d1 = (math.log(S / K) + (R - Q + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    return math.exp(-Q * T) * (1 - _ncdf(d1))

def strike_for_pdelta(S, dte, sig, target):
    lo, hi = S * 0.5, S * 1.2
    for _ in range(70):
        mid = 0.5 * (lo + hi)
        if put_delta_abs(S, mid, dte, sig) > target:
            hi = mid
        else:
            lo = mid
    return round(mid / 5) * 5

df, C = B.df, B.C
sig_hist = pd.read_csv(B.ROOT / "research/q078/_signal_history_cache.csv",
                       parse_dates=["date"]).set_index("date")
df["strategy_key"] = sig_hist["strategy_key"].reindex(df.index)
df["regime"] = sig_hist["regime"].reindex(df.index)
allowed = df["strategy_key"].fillna("") != ""
comp = (B.SIGNALS["F3_rsi2_os"] | B.SIGNALS["F3_down3"]).fillna(False)
base_mask = (df.index >= "2000-01-01") & B.default_valid & df["vix"].notna()

ARMS = {
    "INCUMBENT (allowed BPS days)": (df["strategy_key"] == "bull_put_spread") & base_mask,
    "CHALLENGER (blocked NORMAL oversold)": (~allowed) & (df["regime"] == "NORMAL") & comp
                                            & (df["vix"] < 35) & base_mask,
}
dates = df.index
close, vix = C.to_numpy(), df["vix"].to_numpy()
HOLD_CD = DTE - EXIT_DTE  # 9 calendar days

def next_idx(i, cd):
    tgt = dates[i] + pd.Timedelta(days=cd)
    j = dates.searchsorted(tgt)
    return min(j, len(dates) - 1)

def run(mask):
    mv = mask.to_numpy()
    trades, i = [], 0
    while i < len(dates) - 15:
        if not mv[i]:
            i += 1
            continue
        S0, s0 = close[i], vix[i] / 100
        ks = strike_for_pdelta(S0, DTE, s0, SHORT_D)
        kl = strike_for_pdelta(S0, DTE, s0, LONG_D)
        credit = put_price(S0, ks, DTE, s0) - put_price(S0, kl, DTE, s0)
        if credit <= 0 or ks <= kl:
            i += 1
            continue
        j = next_idx(i, HOLD_CD)
        dte_rem = DTE - (dates[j] - dates[i]).days
        S1, s1 = close[j], vix[j] / 100
        exit_cost = put_price(S1, ks, dte_rem, s1) - put_price(S1, kl, dte_rem, s1)
        pnl = (credit - exit_cost) * 100
        trades.append(dict(entry=dates[i], spx=S0, vix=vix[i], credit=credit * 100,
                           width=(ks - kl) * 100, pnl=pnl, breach=S1 < ks))
        i = j + 1
    return pd.DataFrame(trades)

spx_ref = close[-1]
print(f"house BPS 30DTE d.30/d.15, exit 21DTE | SPX_ref {spx_ref:.0f}")
print(f"{'arm':<38} {'n':>4} {'n/yr':>5} {'win%':>5} {'credit$':>8} {'meanPnL':>8} "
      f"{'CVaR10':>8} {'worst':>8} {'breach%':>7} {'net$/yr(today)':>14}")
results = {}
for name, mask in ARMS.items():
    t = run(mask)
    yrs = 26.5
    scale = spx_ref / t.spx
    net_yr = (t.pnl * scale).sum() / yrs
    k = max(1, int(0.10 * len(t)))
    cvar = t.pnl.nsmallest(k).mean()
    print(f"{name:<38} {len(t):>4} {len(t)/yrs:>5.1f} {100*(t.pnl>0).mean():>4.0f}% "
          f"{t.credit.mean():>8.0f} {t.pnl.mean():>8.0f} {cvar:>8.0f} {t.pnl.min():>8.0f} "
          f"{100*t.breach.mean():>6.1f}% {net_yr:>14,.0f}")
    results[name] = t

# same worst-7y-era bracket applied to BOTH arms
print("\nworst rolling-7y era, per-trade mean PnL (same bracket both arms):")
for name, t in results.items():
    worst, worst_win = np.inf, None
    for st in pd.date_range("2000-01-01", "2019-07-01", freq="6MS"):
        w = t[(t.entry >= st) & (t.entry < st + pd.DateOffset(years=7))]
        if len(w) >= 8 and w.pnl.mean() < worst:
            worst, worst_win = w.pnl.mean(), f"{st.year}-{st.year+7} (n={len(w)})"
    print(f"  {name:<38} worst 7y mean ${worst:,.0f}/trade  [{worst_win}]")

# head-to-head: challenger minus incumbent, studentized
a, b = results[list(ARMS)[0]], results[list(ARMS)[1]]
sa, sb = a.pnl * spx_ref / a.spx, b.pnl * spx_ref / b.spx
se = math.sqrt(sa.var(ddof=1)/len(sa) + sb.var(ddof=1)/len(sb))
t_stat = (sb.mean() - sa.mean()) / se
print(f"\nhead-to-head (today-scale per trade): challenger {sb.mean():,.0f} vs incumbent {sa.mean():,.0f}"
      f"  diff {sb.mean()-sa.mean():+,.0f}  Welch t={t_stat:+.2f}")
