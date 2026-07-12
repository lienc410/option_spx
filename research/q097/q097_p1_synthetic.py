"""Q097 P1 — 合成基准:五个候选检测器在已知真值下的滞后/误翻/盲区。

生成器(charter §P1):双状态半马尔可夫日频对数价格
  趋势态: dlogP = +0.0007 + 0.01·ε        驻留 ~ N(60,20) TD, 下限 20
  区间态: OU 回归锚定转换时价位           驻留 ~ N(25,10) TD, 下限 15
        dlogP = -0.05·(logP - anchor) + 0.01·ε
真值转换点 = 构造已知。200 路径 × 2520 TD(10y)。

候选(charter §0.5 锁死):
  D1 fixed box   : 5%/15TD 因果贪婪箱体(现行)
  D2 ATR box     : 5×ATR14 带宽箱体, 其余同 D1(尺度自适应主候选)
  D3 ADX<20 ×5TD
  D4 ER20<0.30 ×5TD
  D5 slope |t|<1 ×5TD(20d 回归)
指标:趋势→区间检测滞后(中位/p75) · 纯趋势段误亮灯率(每百 TD) ·
     5TD 回翻率 · 15TD 内检出率。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "q097"
rng = np.random.default_rng(20260713)

N_PATHS, N_DAYS = 200, 2520
VOL, DRIFT, OU_K = 0.01, 0.0007, 0.05


def gen_path():
    state = 0  # 0 trend, 1 range
    dwell = max(20, int(rng.normal(60, 20)))
    logp, anchor = np.log(4000.0), None
    prices, states = [], []
    for t in range(N_DAYS):
        if dwell == 0:
            state = 1 - state
            dwell = (max(15, int(rng.normal(25, 10))) if state == 1
                     else max(20, int(rng.normal(60, 20))))
            anchor = logp if state == 1 else None
        if state == 0:
            logp += DRIFT + VOL * rng.standard_normal()
        else:
            logp += -OU_K * (logp - anchor) + VOL * rng.standard_normal()
        prices.append(np.exp(logp)); states.append(state)
        dwell -= 1
    return np.array(prices), np.array(states)


def atr14(close):
    """合成数据无 H/L,用 |ΔC| 的 Wilder 平滑作 ATR 代理(自洽即可)。"""
    tr = np.abs(np.diff(close, prepend=close[0]))
    a = np.empty_like(tr); a[0] = tr[:14].mean()
    for i in range(1, len(tr)):
        a[i] = a[i-1] + (tr[i] - a[i-1]) / 14
    return a


def box_detector(close, band_fn, min_len=15):
    """因果贪婪箱体:返回每日 bool(当日是否处于已确认 episode)。"""
    n = len(close); out = np.zeros(n, bool)
    s = 0
    while s < n - min_len:
        lo = hi = close[s]; e = s
        limit = band_fn(s)
        for j in range(s + 1, n):
            lo, hi = min(lo, close[j]), max(hi, close[j])
            if (hi - lo) / ((hi + lo) / 2) > limit:
                break
            e = j
        if e - s + 1 >= min_len:
            out[s + min_len - 1:e + 1] = True   # 因果:攒满 min_len 才亮
            s = e + 1
        else:
            s += 1
    return out


def streak(cond, k=5):
    """cond 连续 k 日为真后亮灯(因果)。"""
    c = np.asarray(cond, float)
    run = np.zeros_like(c)
    for i in range(len(c)):
        run[i] = (run[i-1] + 1) if (i and c[i]) else (1.0 if c[i] else 0.0)
    return run >= k


def detectors(close):
    px = pd.Series(close)
    a = atr14(close)
    d = {}
    d["D1_fixed5"] = box_detector(close, lambda s: 0.05)
    d["D2_atr5x"] = box_detector(close, lambda s: min(0.12, max(0.02, 5*a[s]/close[s])))
    # D3 ADX 代理(无 H/L):|20d 动量| 与行程比的 Wilder 版 → 用 ER 系; 改用文献等价:
    # ADX 近似 = 100·|EMA14(ΔC)| / EMA14(|ΔC|)(方向性指数简化,合成数据自洽)
    dc = px.diff()
    adx_proxy = 100 * dc.ewm(alpha=1/14, adjust=False).mean().abs() / \
        dc.abs().ewm(alpha=1/14, adjust=False).mean().replace(0, np.nan)
    d["D3_adx20"] = streak((adx_proxy < 20).fillna(False).values)
    er = (px - px.shift(20)).abs() / px.diff().abs().rolling(20).sum()
    d["D4_er030"] = streak((er < 0.30).fillna(False).values)
    x = np.arange(20)
    def slope_t(win):
        if win.isna().any(): return np.nan
        y = win.values
        b, a0 = np.polyfit(x, y, 1)
        resid = y - (b*x + a0)
        se = np.sqrt((resid**2).sum()/18 / ((x - x.mean())**2).sum())
        return abs(b/se) if se > 0 else np.nan
    tvals = px.rolling(20).apply(slope_t, raw=False)
    d["D5_slopet"] = streak((tvals < 1).fillna(False).values)
    return d


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    stats = {k: {"lags": [], "false_per100": [], "rev5": [], "hit15": []}
             for k in ("D1_fixed5", "D2_atr5x", "D3_adx20", "D4_er030", "D5_slopet")}
    for _ in range(N_PATHS):
        close, st = gen_path()
        dets = detectors(close)
        # 真值区间段
        segs, s = [], None
        for i, v in enumerate(st):
            if v and s is None: s = i
            elif not v and s is not None: segs.append((s, i-1)); s = None
        if s is not None: segs.append((s, len(st)-1))
        trend_days = (st == 0)
        for name, sig in dets.items():
            S = stats[name]
            for a0, b0 in segs:
                det = next((i - a0 for i in range(a0, b0+1) if sig[i]), None)
                if det is not None:
                    S["lags"].append(det)
                    S["hit15"].append(1 if det <= 15 else 0)
                else:
                    S["hit15"].append(0)
            # 误亮灯:纯趋势日中 sig 为真的比例(每百 TD)
            S["false_per100"].append(sig[trend_days].mean() * 100)
            # 5TD 回翻
            flips = np.flatnonzero(sig[1:] != sig[:-1]) + 1
            rev = sum(1 for i in flips if (sig[i+1:i+6] != sig[i]).any())
            S["rev5"].append(rev / max(len(flips), 1))
    rows = []
    for name, S in stats.items():
        lag = pd.Series(S["lags"])
        rows.append(dict(
            detector=name,
            lag_med=float(lag.median()), lag_p75=float(lag.quantile(.75)),
            hit15_pct=round(100*np.mean(S["hit15"]), 1),
            false_trend_pct=round(float(np.mean(S["false_per100"])), 2),
            rev5_pct=round(100*float(np.mean(S["rev5"])), 1),
        ))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q097_p1_synthetic.csv", index=False)
    print(df.to_string(index=False))
    print("\n杀标对照: K1 误翻/误亮 ≤ D1 · K2 lag_med ≤ D1+5 · (K3 在 P2 实证)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
