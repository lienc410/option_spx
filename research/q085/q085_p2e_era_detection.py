"""Q085 P2e — era detection feasibility, EXECUTABLE form (review C6 fix).

Route A (predictive): impossible at n=1 dead era (unfalsifiable fitting).
Route B (reactive trailing stop, generic form): tested below on the S6-MES
event stream. Result: worst-7y mean barely moves (-$31 -> -$23/-$37),
full-sample net drops (whipsaw cost) — reactive stops cannot rescue
ZERO-MEAN CHOP failure modes. (Review note: they DO work on persistent-bleed
modes like BPS-CALIB's worst era at -$288/trade — this asymmetry is why the
degradation rule is retained in the adaptive adoption design.)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q085_battery_lib as B

df, C = B.df, B.C
ibs = ((C - B.L) / (B.H - B.L)).to_numpy()
comp = (B.SIGNALS["F3_rsi2_os"] | B.SIGNALS["F3_down3"]).fillna(False)
ok = (comp & (df["vix"] < 35) & (df.index >= "2000-01-01") & B.default_valid).to_numpy()
close, dates = C.to_numpy(), df.index
ev, i = [], 0
while i < len(dates) - 11:
    if not ok[i]:
        i += 1; continue
    j = i + 10
    for k in range(i + 1, i + 11):
        if ibs[k] > 0.8:
            j = k; break
    ev.append((dates[i], (close[j] - close[i]) * 5 - 3.6))
    i = j + 1
ev = pd.DataFrame(ev, columns=["date", "pnl"])
pnls = ev.pnl.to_numpy()

def apply_stop(p, K, rK):
    executed, halted = np.zeros(len(p), bool), False
    for t in range(len(p)):
        hist, rh = p[max(0, t - K):t], p[max(0, t - rK):t]
        if halted:
            if len(rh) >= rK and rh.sum() > 0:
                halted = False
        elif len(hist) >= K and hist.sum() < 0:
            halted = True
        executed[t] = not halted
    return executed

def worst7(mask):
    worst = np.inf
    for st in pd.date_range("2000-01-01", "2019-07-01", freq="6MS"):
        sel = (ev.date >= st) & (ev.date < st + pd.DateOffset(years=7)) & mask
        if sel.sum() >= 8:
            worst = min(worst, ev.pnl[sel].mean())
    return worst

print(f"baseline: worst7y ${worst7(np.ones(len(ev), bool)):,.0f}/ev, net/yr(1x) ${ev.pnl.sum()/26.5:,.0f}")
for K, rK in ((10, 5), (20, 10)):   # pre-registered grid
    m = apply_stop(pnls, K, rK)
    print(f"stop K={K}/re{rK}: exec {100*m.mean():.0f}%, worst7y ${worst7(m):,.0f}/ev, "
          f"net/yr(1x) ${ev.pnl[m].sum()/26.5:,.0f}")
