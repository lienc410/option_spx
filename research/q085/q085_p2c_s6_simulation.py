"""Q085 P2c — S6 short-hold tactical slot simulation (A-layer scope).

Pre-registered protocol (P2 plan v2):
  Entry : (RSI(2)<10 or down3) on any trading day, Layer-1 screen VIX<35,
          entry at signal-day close (executable per PM 3:50pm check).
  Exits : grid {fix2 = close t+2, fix5 = close t+5,
                mirror = first close with IBS>0.8 (P2b strongest survivor),
                capped at 10td}. Grid SELECTED on 2000-01..2013-06,
          CONFIRMED on 2013-07..2026-07 (chosen rule must have 2nd-half
          net > 0 and rank top-2). No other exits considered.
  Sizing: MES ($5/pt), costs $1.8/side/contract; contracts n s.t. event
          p5 loss <= $2,000 (pre-registered loss budget), min 1.
  K3    : >=$4,000/yr where per-event edge takes the WORST of
          (a) confirmation-half mean, (b) studentized 95% CI lower bound
          (full sample), (c) worst rolling-7y era mean.
  Events: sequential non-overlapping.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q085_battery_lib as B

df, C, H, L = B.df, B.C, B.H, B.L
ibs = (C - L) / (H - L)
entry_sig = (B.SIGNALS["F3_rsi2_os"] | B.SIGNALS["F3_down3"]).fillna(False)
layer1 = df["vix"] < 35
ok = entry_sig & layer1 & (df.index >= "2000-01-01") & B.default_valid

dates = df.index.to_list()
close = C.to_numpy()
ibs_a = ibs.to_numpy()
COST_RT = 2 * 1.8  # $ per contract round trip
MULT = 5.0         # MES $ per index point

def simulate(exit_rule):
    """Return event list: (entry_date, exit_lag, pnl_per_contract_$)."""
    events, i, N = [], 0, len(dates)
    okv = ok.to_numpy()
    while i < N - 11:
        if not okv[i]:
            i += 1
            continue
        if exit_rule == "fix2":
            j = i + 2
        elif exit_rule == "fix5":
            j = i + 5
        else:  # mirror: first IBS>0.8 close after entry, cap 10
            j = i + 10
            for k in range(i + 1, i + 11):
                if ibs_a[k] > 0.8:
                    j = k
                    break
        pnl = (close[j] - close[i]) * MULT - COST_RT
        events.append((dates[i], j - i, pnl))
        i = j + 1  # non-overlapping
    return events

SPLIT = pd.Timestamp("2013-07-01")
END = pd.Timestamp("2026-07-01")

def stats(events, lo=None, hi=None):
    ev = [e for e in events if (lo is None or e[0] >= lo) and (hi is None or e[0] < hi)]
    if not ev:
        return None
    pnl = np.array([e[2] for e in ev])
    yrs = ((hi or END) - (lo or pd.Timestamp("2000-01-01"))).days / 365.25
    p5 = np.percentile(pnl, 5)
    n_ctr = max(1, int(2000 // abs(min(p5, -1))))
    return dict(n=len(ev), per_yr=len(ev) / yrs, mean=pnl.mean(), sd=pnl.std(ddof=1),
                p5=p5, cvar10=pnl[pnl <= np.percentile(pnl, 10)].mean(),
                contracts=n_ctr, net_yr=len(ev) / yrs * pnl.mean() * n_ctr,
                hold=np.mean([e[1] for e in ev]))

print("=" * 100)
print("S6-A simulation — per 1 MES contract unless noted")
print(f"{'rule':<7} {'half':<8} {'n':>4} {'ev/yr':>6} {'mean$':>8} {'p5$':>8} {'CVaR10$':>8} {'hold':>5} {'n_ctr':>5} {'net$/yr':>9}")
all_events = {}
for rule in ("fix2", "fix5", "mirror"):
    ev = simulate(rule)
    all_events[rule] = ev
    for half, lo, hi in (("SELECT", None, SPLIT), ("CONFIRM", SPLIT, None)):
        s = stats(ev, lo, hi)
        print(f"{rule:<7} {half:<8} {s['n']:>4} {s['per_yr']:>6.1f} {s['mean']:>8.1f} {s['p5']:>8.0f} "
              f"{s['cvar10']:>8.0f} {s['hold']:>5.1f} {s['contracts']:>5} {s['net_yr']:>9.0f}")

# selection on first half by CVaR-sized net/yr
sel = {r: stats(all_events[r], None, SPLIT)["net_yr"] for r in all_events}
chosen = max(sel, key=sel.get)
conf = {r: stats(all_events[r], SPLIT, None)["net_yr"] for r in all_events}
rank2 = sorted(conf, key=conf.get, reverse=True)[:2]
confirmed = conf[chosen] > 0 and chosen in rank2
print(f"\nselection half picks: {chosen} (net/yr {sel[chosen]:,.0f}); "
      f"confirmation: net/yr {conf[chosen]:,.0f}, rank {'top-2 OK' if chosen in rank2 else 'FAIL'}"
      f" -> {'CONFIRMED' if confirmed else 'NOT CONFIRMED'}")

# K3 pessimistic bracket on chosen rule (full-sample sizing, per-event edge brackets)
ev_all = all_events[chosen]
pnl = np.array([e[2] for e in ev_all])
full = stats(ev_all)
n_ctr = full["contracts"]
per_yr_full = full["per_yr"]
# (a) confirmation-half mean
a_mean = stats(ev_all, SPLIT, None)["mean"]
# (b) studentized 95% CI lower bound (full sample)
b_mean = pnl.mean() - 1.96 * pnl.std(ddof=1) / np.sqrt(len(pnl))
# (c) worst rolling 7y era mean
worst = np.inf
yr_starts = pd.date_range("2000-01-01", "2019-07-01", freq="6MS")
for st in yr_starts:
    s7 = stats(ev_all, st, st + pd.DateOffset(years=7))
    if s7 and s7["n"] >= 10:
        worst = min(worst, s7["mean"])
c_mean = worst
pess = min(a_mean, b_mean, c_mean)
print(f"\nK3 pessimistic bracket on '{chosen}' (per contract per event):")
print(f"  (a) confirm-half mean ${a_mean:,.0f}  (b) 95%CI lower ${b_mean:,.0f}  (c) worst-7y era ${c_mean:,.0f}")
print(f"  pessimistic edge ${pess:,.0f} x {per_yr_full:.1f} ev/yr x {n_ctr} contracts "
      f"= ${pess*per_yr_full*n_ctr:,.0f}/yr  vs K3 $4,000 -> {'PASS' if pess*per_yr_full*n_ctr>=4000 else 'FAIL'}")

# era table
print("\nrolling 7y era net/yr (chosen rule, CVaR sizing):")
for st in pd.date_range("2000-01-01", "2019-01-01", freq="2YS"):
    s7 = stats(ev_all, st, st + pd.DateOffset(years=7))
    if s7:
        print(f"  {st.year}-{st.year+7}: net ${s7['net_yr']*0+s7['per_yr']*s7['mean']*n_ctr:,.0f}/yr (n={s7['n']}, mean ${s7['mean']:,.0f})")
