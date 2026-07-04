"""Q085 P3 — S2-BPS robustness front-load (pre-G-review, per
feedback_post_withdrawal_proposals_front_load_robustness).

Upgrades over P2d (both arms identically):
  1. Engine-grade management: daily walk; stop when closing cost >= 3x credit;
     otherwise close at 21 DTE. (House BPS discipline; 60%-profit-after-10d
     never binds within the 9-day hold.)
  2. Pessimistic skew bracket: BS-flat is the BASE; PESS prices put skew
     against us — entry sigma: short leg VIX+1vp, long leg VIX+4vp (deeper
     OTM richer -> credit smaller); exit adds +2vp to both legs when VIX
     rose during hold (skew steepening stress). Strike selection stays
     flat-sigma (trader picks by delta; identical both arms).
  3. Cascade path: fraction of holds during which VIX crosses >=22 / >=35,
     and those trades' PnL (the "knife keeps falling" mechanism).
  4. BP/cash accounting: spread occupies BP (= width - credit), NOT cash;
     outside SPEC-111 cash caps on a PM account. Reported per arm.
Arms: INCUMBENT (allowed bull_put_spread days) vs CHALLENGER (blocked &
NORMAL & oversold & VIX<35), sequential non-overlapping, 2000-2026.
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
DTE, EXIT_DTE, STOP_X = 30, 21, 3.0
COST_RT = 130.0  # $/trade round trip: 2-leg SPX spread, ~$5 commissions + ~$0.30 half-spread x 2 legs x 2 sides

def _ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def put_price(S, K, dte, sig):
    T = max(dte, 0.01) / 365.0
    if sig <= 0:
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
    "INCUMBENT": (df["strategy_key"] == "bull_put_spread") & base_mask,
    "CHALLENGER": (~allowed) & (df["regime"] == "NORMAL") & comp & (df["vix"] < 35) & base_mask,
}
dates, close, vix = df.index, C.to_numpy(), df["vix"].to_numpy()

def leg_sigmas(v, scen, vix_up):
    if scen == "BASE":
        return v / 100, v / 100
    if scen == "CALIB":
        # measured from 23 days of real Schwab SPX chains (2026-05-29..07-03,
        # VIX 15-22 = exactly the challenger regime): d0.30 leg = VIX-2.0vp,
        # d0.15 leg = VIX+1.0vp, offsets stable across days incl. VIX 22
        return v / 100 - 0.020, v / 100 + 0.010
    add = 0.02 if vix_up else 0.0
    return v / 100 + 0.01 + add, v / 100 + 0.04 + add  # short, long PESS

def run(mask, scen):
    mv = mask.to_numpy()
    trades, i = [], 0
    while i < len(dates) - 15:
        if not mv[i]:
            i += 1
            continue
        S0, v0 = close[i], vix[i]
        flat = v0 / 100
        ks = strike_for_pdelta(S0, DTE, flat, 0.30)
        kl = strike_for_pdelta(S0, DTE, flat, 0.15)
        ss, sl = leg_sigmas(v0, scen, False)
        credit = put_price(S0, ks, DTE, ss) - put_price(S0, kl, DTE, sl)
        if credit <= 0 or ks <= kl:
            i += 1
            continue
        j, stopped, vmax = i, False, v0
        cost = credit
        while j < len(dates) - 1:
            j += 1
            vmax = max(vmax, vix[j])
            dte_rem = max(DTE - (dates[j] - dates[i]).days, 1)
            ss_x, sl_x = leg_sigmas(vix[j], scen, vix[j] > v0)
            cost = put_price(close[j], ks, dte_rem, ss_x) - put_price(close[j], kl, dte_rem, sl_x)
            if cost >= STOP_X * credit:
                stopped = True
                break
            if dte_rem <= EXIT_DTE:   # close AT 21 DTE (house rule)
                break
        trades.append(dict(entry=dates[i], spx=S0, credit=credit * 100,
                           width=(ks - kl) * 100, pnl=(credit - cost) * 100 - COST_RT,
                           stopped=stopped, breach=close[j] < ks,
                           casc22=vmax >= 22, casc35=vmax >= 35))
        i = j + 1
    return pd.DataFrame(trades)

spx_ref = close[-1]
yrs = 26.5
print(f"engine rules: stop {STOP_X}x credit daily-checked, close 21 DTE | SPX_ref {spx_ref:.0f}")
print(f"{'arm':<11} {'scen':<5} {'n':>4} {'win%':>5} {'meanPnL':>8} {'CVaR10':>8} {'worst':>8} "
      f"{'stop%':>6} {'brch%':>6} {'c22%':>5} {'net$/yr':>9} {'worst7y':>8}")
store = {}
for name, mask in ARMS.items():
    for scen in ("BASE", "CALIB", "PESS"):
        t = run(mask, scen)
        store[(name, scen)] = t
        scale = spx_ref / t.spx
        netyr = (t.pnl * scale).sum() / yrs
        k = max(1, int(0.10 * len(t)))
        cvar = t.pnl.nsmallest(k).mean()
        worst7, w7win = np.inf, ""
        for st in pd.date_range("2000-01-01", "2019-07-01", freq="6MS"):
            w = t[(t.entry >= st) & (t.entry < st + pd.DateOffset(years=7))]
            if len(w) >= 8 and w.pnl.mean() < worst7:
                worst7, w7win = w.pnl.mean(), f"{st.year}-{st.year+7}"
        print(f"{name:<11} {scen:<5} {len(t):>4} {100*(t.pnl>0).mean():>4.0f}% {t.pnl.mean():>8.0f} "
              f"{cvar:>8.0f} {t.pnl.min():>8.0f} {100*t.stopped.mean():>5.1f}% "
              f"{100*t.breach.mean():>5.1f}% {100*t.casc22.mean():>4.0f}% {netyr:>9,.0f} {worst7:>8.0f}")

# cascade detail + BP accounting for challenger PESS
t = store[("CHALLENGER", "PESS")]
casc = t[t.casc22]
print(f"\ncascade (challenger PESS): VIX>=22 during hold on {len(casc)}/{len(t)} trades "
      f"({100*len(casc)/len(t):.0f}%), their mean PnL ${casc.pnl.mean():,.0f}, worst ${casc.pnl.min():,.0f}")
print(f"VIX>=35 during hold: {int(t.casc35.sum())} trades")
print(f"BP accounting: avg width ${t.width.mean():,.0f}, avg credit ${t.credit.mean():,.0f} "
      f"-> BP occupied ~${(t.width-t.credit).mean():,.0f}/contract x ~9 days; cash consumed: $0 "
      f"(PM spread margin = max loss = BP; outside SPEC-111 cash caps)")
# IS/OOS
for name in ARMS:
    t = store[(name, "PESS")]
    h1 = t[t.entry < "2013-07-01"]; h2 = t[t.entry >= "2013-07-01"]
    print(f"IS/OOS ({name} PESS): first-half mean ${h1.pnl.mean():,.0f} (n={len(h1)}) | "
          f"second-half ${h2.pnl.mean():,.0f} (n={len(h2)})")
