"""Q097 P2 — 实证核验:(a) 尺度不变性(D1 vs D2 跨波动时代) (b) 结果真值分型安全。

(a) 真实 SPX 2011-2019(低波时代) vs 2020-2026(高波时代):episode 日占比/
    条数/中位时长的时代稳定性。D1 固定 5% 预期暴露时代依赖;D2=5×ATR14
    自适应带宽预期更稳。不变性度量 = 两时代 episode 日占比之比(越近 1 越好)。
(b) 结果真值(非循环):35 个 dip 触发中 4 个已知崩盘延续型
    (2018-02-05/2020-02-24/2020-09-04/2025-02-27)在候选检测器的因果分型下
    必须全部 = sudden(K3 硬标);其余对照 P6 forward 实现结果呈现。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "q097"

SUDDEN_TRUTH = {"2018-02-05", "2020-02-24", "2020-09-04", "2025-02-27"}


def load():
    df = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df[["High", "Low", "Close"]].dropna()
    tr = pd.concat([df.High - df.Low, (df.High - df.Close.shift()).abs(),
                    (df.Low - df.Close.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()
    return df.loc["1999-01-01":]


def find_eps(close, band, min_len=15):
    """band: callable(start_idx)->比例带宽。返回 [(s,e)] 最大不重叠段。"""
    v = close.values; n = len(v); out = []; s = 0
    while s < n - min_len:
        lo = hi = v[s]; e = s; lim = band(s)
        for j in range(s + 1, n):
            lo, hi = min(lo, v[j]), max(hi, v[j])
            if (hi - lo) / ((hi + lo) / 2) > lim:
                break
            e = j
        if e - s + 1 >= min_len:
            out.append((s, e)); s = e + 1
        else:
            s += 1
    return out


def era_stats(df, band_name, band):
    rows = []
    for era, a, b in (("2011-2019", "2011-01-01", "2019-12-31"),
                      ("2020-2026", "2020-01-01", "2026-12-31")):
        c = df.loc[a:b, "Close"]
        eps = find_eps(c, band(df.loc[a:b]))
        days = sum(e - s + 1 for s, e in eps)
        L = pd.Series([e - s + 1 for s, e in eps])
        rows.append(dict(detector=band_name, era=era, n_eps=len(eps),
                         eps_per_yr=round(len(eps) / (len(c) / 252), 2),
                         day_share_pct=round(days / len(c) * 100, 1),
                         len_med=float(L.median()) if len(L) else None))
    inv = rows[0]["day_share_pct"] / rows[1]["day_share_pct"] if rows[1]["day_share_pct"] else float("nan")
    return rows, round(inv, 2)


def classify(df, sig_date, band):
    """因果分型(094.4 同法):截至信号日跑分段,信号落在段内或段末 ≤7 日历日 = episode。"""
    t = pd.Timestamp(sig_date)
    c = df.loc[:t, "Close"]
    eps = find_eps(c, band(df.loc[:t]))
    for s, e in eps:
        d0, d1 = c.index[s], c.index[e]
        if d0 <= t <= d1 + pd.Timedelta(days=7):
            return "episode"
    return "sudden"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load()

    def band_d1(sub):
        return lambda s: 0.05

    def band_d2(sub):
        a, c = sub["atr"].values, sub["Close"].values
        return lambda s: min(0.12, max(0.02, 5 * a[s] / c[s]))

    print("=== (a) 尺度不变性(时代稳定性)===")
    allrows = []
    for name, band in (("D1_fixed5", band_d1), ("D2_atr5x", band_d2)):
        rows, inv = era_stats(df, name, band)
        allrows += rows
        for r in rows:
            print(f"{name} [{r['era']}] eps/yr {r['eps_per_yr']:>5} | day-share {r['day_share_pct']:>5}% | len_med {r['len_med']}")
        print(f"  → 时代占比之比(≈1 最稳): {inv}")
    pd.DataFrame(allrows).to_csv(OUT / "q097_p2a_era_stats.csv", index=False)

    print("\n=== (b) 结果真值分型(K3: 4 突发型硬标)===")
    q = pd.read_csv(ROOT / "data" / "q042_backtest_trades.csv")
    q = q[q.sleeve_id == "A"]
    res = []
    for name, band in (("D1_fixed5", band_d1), ("D2_atr5x", band_d2)):
        cls = {s: classify(df, s, band) for s in q.signal_date}
        sudden_ok = sum(1 for s in SUDDEN_TRUTH if cls.get(s) == "sudden")
        n_ep = sum(1 for v in cls.values() if v == "episode")
        print(f"{name}: 突发型判对 {sudden_ok}/4 {'✓' if sudden_ok==4 else '✗ K3 DEAD'} | episode 型 {n_ep}/35")
        res.append(dict(detector=name, sudden_ok=sudden_ok, episode_n=n_ep))
    pd.DataFrame(res).to_csv(OUT / "q097_p2b_truth.csv", index=False)

    # 6 月案例检测日对比
    print("\n=== (c) 6 月案例:各检测器亮灯日 ===")
    for name, band in (("D1_fixed5", band_d1), ("D2_atr5x", band_d2)):
        for probe in pd.bdate_range("2026-05-15", "2026-06-15"):
            if probe not in df.index:
                continue
            if classify(df, probe, band) == "episode":
                print(f"{name}: 首个 episode 判定日 = {probe.date()}")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
