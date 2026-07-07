"""Q090 — PM ratify 前逐条走查：每族胜者组合的最近触发实例。

每个触发日输出：日期、SPX 收盘、信号点位（簇位/趋势线值/量比）、
之后 1/5/10td 真实收益、按论文方向判定（S1r/S2/S4 看空 → fwd5<0 应验；
S1s 看多 → fwd5>0 应验）。取每族最近 10 例。
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "q085"))
import q085_battery_lib as B

df, C, H, L, V = B.df, B.C, B.H, B.L, B.V
n = len(df); K = 5; LOOK = 120
hi, lo, cl = H.to_numpy(), L.to_numpy(), C.to_numpy()
swing_hi = np.zeros(n, bool); swing_lo = np.zeros(n, bool)
for i in range(K, n - K):
    wh, wl = hi[i-K:i+K+1], lo[i-K:i+K+1]
    if hi[i] == wh.max() and (wh == hi[i]).sum() == 1: swing_hi[i] = True
    if lo[i] == wl.min() and (wl == lo[i]).sum() == 1: swing_lo[i] = True
hi_idx, lo_idx = np.where(swing_hi)[0], np.where(swing_lo)[0]

def fwd(t, h):
    return (cl[t+h]/cl[t]-1)*100 if t+h < n else np.nan

rows = []
def emit(fam, t, level, extra, bullish=False):
    f5 = fwd(t,5)
    rows.append({"family": fam, "date": df.index[t].date().isoformat(),
                 "close": round(cl[t],1), "level": level, "extra": extra,
                 "fwd1%": round(fwd(t,1),2), "fwd5%": round(f5,2), "fwd10%": round(fwd(t,10),2),
                 "verdict": ("✓应验" if (f5>0 if bullish else f5<0) else "✗未应验") if not np.isnan(f5) else "–"})

# S1r 胜者 b3_t3_p10（0.3% 带、≥3 触、1% 接近）
for t in range(2*K+LOOK, n):
    us = hi_idx[(hi_idx+K<=t)&(hi_idx>=t-LOOK)]
    if len(us) < 3: continue
    vals = hi[us]
    for v in vals:
        mem = vals[np.abs(vals/v-1)<=0.003]
        if len(mem)>=3:
            lvl = mem.mean()
            if lvl >= cl[t] >= lvl*0.99:
                emit("S1r压力簇", t, round(lvl,0), f"{len(mem)}触"); break

# S1s 胜者 b3_t2_p5
for t in range(2*K+LOOK, n):
    us = lo_idx[(lo_idx+K<=t)&(lo_idx>=t-LOOK)]
    if len(us) < 2: continue
    vals = lo[us]
    for v in vals:
        mem = vals[np.abs(vals/v-1)<=0.003]
        if len(mem)>=2:
            lvl = mem.mean()
            if lvl <= cl[t] <= lvl*1.005:
                emit("S1s支撑簇", t, round(lvl,0), f"{len(mem)}触", bullish=True); break

# S2 胜者 d2_v85（两连涨 × V/V20<0.85）
vr = (V/V.rolling(20).mean()).to_numpy()
up1 = (C>C.shift(1)).to_numpy()
for t in range(21, n):
    if up1[t] and up1[t-1] and vr[t] < 0.85:
        emit("S2缩量上涨", t, "-", f"V/20d={vr[t]:.2f}")

# S4 胜者 n3_p10（3 高递减、1% 接近）
for t in range(2*K+LOOK, n):
    us = hi_idx[(hi_idx+K<=t)&(hi_idx>=t-LOOK)]
    if len(us) < 3: continue
    v = hi[us[-3:]]
    if not (v[0]>v[1]>v[2]): continue
    i1,i2 = us[-2],us[-1]
    line = hi[i2] + (hi[i2]-hi[i1])/(i2-i1)*(t-i2)
    if line > cl[t] >= line*0.99:
        emit("S4递减线", t, round(line,0), f"高点{v[0]:.0f}→{v[1]:.0f}→{v[2]:.0f}")

out = pd.DataFrame(rows)
out.to_csv(ROOT / "research/q090/q090_walkthrough_recent.csv", index=False)
for fam in ("S1r压力簇","S1s支撑簇","S2缩量上涨","S4递减线"):
    w = out[out.family==fam]
    hitrate = (w.verdict=="✓应验").sum()
    print(f"\n== {fam} | 全样本触发 {len(w)} 次 | fwd5 应验率 {hitrate}/{len(w)} ({100*hitrate/max(len(w),1):.0f}%) | 最近 10 例 ==")
    print(w.tail(10).to_string(index=False))
