"""Q097 P3 — PM 边界追问双测(2026-07-12):确认期 K 扫描 + 斜通道冒烟。

Q-a: 15TD 确认是否延后太大,可否缩短?
  → K ∈ {8,10,12,15,20} 全量重放:推送量/确认后寿命/速死率/再锚定率/
    K3 崩盘真值(4 突发型硬标)/094.4 分型漂移(35 触发因果重分型)。
Q-b: "平移再锚定"是否水平箱体的问题,斜通道(平行斜线)能否避免?
  → ①历史再锚定规模与方向结构;②崩盘安全冒烟:4 个 K3 触发日前
    OLS 斜通道(残差带 ≤5%)是否成立——成立即通道检测器会把崩盘日
    分型为 episode(=BPS fallback 路由进崩盘);③近一年 7 次破箱的
    通道吸收测试(含 03-13 真裂口)。

程序定位:Q097 gauntlet 对两个新挑战者族的边界延伸(K 变体族/通道族),
非重开研究线;K3 4/4 为硬门槛(Q097 登记)。
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

SUDDEN = ["2018-02-05", "2020-02-24", "2020-09-04", "2025-02-27"]
BREAKS_1Y = ["2025-08-13", "2025-10-01", "2025-10-28", "2025-11-20",
             "2026-01-06", "2026-03-13", "2026-05-05"]


def load_close():
    df = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    return df["Close"].dropna().loc["1999-01-01":]


def find_eps(v, min_len, lim=0.05):
    n = len(v); out = []; s = 0
    while s < n - min_len:
        lo = hi = v[s]; e = s
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


def classify(close, t, min_len):
    c = close.loc[:pd.Timestamp(t)]
    for s, e in find_eps(c.values, min_len):
        if c.index[s] <= pd.Timestamp(t) <= c.index[e] + pd.Timedelta(days=7):
            return "episode"
    return "sudden"


def main() -> int:
    close = load_close()
    q = pd.read_csv(ROOT / "data" / "q042_backtest_trades.csv")
    q = q[q.sleeve_id == "A"]
    w0, w1 = pd.Timestamp("2025-07-13"), pd.Timestamp("2026-07-10")
    yrs = len(close) / 252

    rows = []
    for K in (8, 10, 12, 15, 20):
        eps = find_eps(close.values, K)
        L = np.array([e - s + 1 for s, e in eps]); life = L - K + 1
        reanchor = np.mean([eps[i + 1][0] - eps[i][1] <= 3
                            for i in range(len(eps) - 1)]) * 100
        cls = {t: classify(close, t, K) for t in q.signal_date}
        k3 = sum(1 for t in SUDDEN if cls.get(t) == "sudden")
        conf = [close.index[s + K - 1] for s, e in eps if s + K - 1 < len(close)]
        brk = [close.index[e + 1] for s, e in eps if e + 1 < len(close)]
        nyr = (sum(1 for d in conf if w0 <= d <= w1)
               + sum(1 for d in brk if w0 <= d <= w1))
        rows.append(dict(K=K, eps_per_yr=round(len(eps) / yrs, 1),
                         day_share_pct=round(L.sum() / len(close) * 100),
                         len_med=int(np.median(L)),
                         life_med_td=int(np.median(life)),
                         fastdeath_le5td_pct=round(np.mean(life <= 5) * 100),
                         reanchor_pct=round(reanchor),
                         k3_sudden_ok=k3,
                         ep_typed_n=sum(1 for v in cls.values() if v == "episode"),
                         pushes_lastyear=nyr))
    sweep = pd.DataFrame(rows)
    sweep.to_csv(OUT / "q097_p3_ksweep.csv", index=False)
    print(sweep.to_string(index=False))

    eps15 = find_eps(close.values, 15)
    re_dir = []
    for i in range(len(eps15) - 1):
        s0, e0 = eps15[i]; s1, e1 = eps15[i + 1]
        if s1 - e0 <= 3:
            m0 = (close.values[s0:e0 + 1].max() + close.values[s0:e0 + 1].min()) / 2
            m1 = (close.values[s1:e1 + 1].max() + close.values[s1:e1 + 1].min()) / 2
            re_dir.append(m1 > m0)
    print(f"\nK=15 历史再锚定 {len(re_dir)} 次: 上移 {np.mean(re_dir)*100:.0f}%")

    smoke = []
    for t in SUDDEN:
        t = pd.Timestamp(t); pre = close.loc[:t].iloc[:-1]
        for W in (15, 20, 30):
            v = pre.iloc[-W:].values; x = np.arange(W)
            co = np.polyfit(x, v, 1)
            r = v - np.polyval(co, x)
            smoke.append(dict(trigger=str(t.date()), window_td=W,
                              resid_band_pct=round((r.max() - r.min()) / v.mean() * 100, 1),
                              slope_pct_yr=round(co[0] * 252 / v.mean() * 100),
                              channel_holds=bool((r.max() - r.min()) / v.mean() <= 0.05)))
    for b in BREAKS_1Y:
        seg = close.loc[:pd.Timestamp(b)].iloc[-30:]
        v = seg.values; x = np.arange(len(v))
        r = v - np.polyval(np.polyfit(x, v, 1), x)
        smoke.append(dict(trigger=f"break_{b}", window_td=30,
                          resid_band_pct=round((r.max() - r.min()) / v.mean() * 100, 1),
                          slope_pct_yr=None,
                          channel_holds=bool((r.max() - r.min()) / v.mean() <= 0.05)))
    sm = pd.DataFrame(smoke)
    sm.to_csv(OUT / "q097_p3_channel_smoke.csv", index=False)
    print("\n" + sm.to_string(index=False))

    # ── P3b(PM 追问 2026-07-12): 破箱方向 × 前向风险 ────────────────────
    # 发现:四个 K3 崩盘触发全部发生在"弱上破"(顶上方 +0.18~0.81%)后
    # 5-10TD 内;但 P(崩盘|上破)=4/122=3.3%,且下破尾部更重——上破不可
    # 作为 veto gate(基率+n=4 切点+已死 point-in-time gate 家族三重反对)。
    v = close.values
    eps15 = find_eps(v, 15)
    dirs = []
    for s, e in eps15:
        if e + 1 >= len(v):
            continue
        lo, hi = v[s:e+1].min(), v[s:e+1].max()
        bc = v[e+1]
        fwd = v[e+1:min(e+22, len(v))]
        dirs.append(dict(brk=str(close.index[e+1].date()),
                         dir='up' if bc > hi else 'down',
                         poke_pct=round((bc/hi-1)*100 if bc > hi else (bc/lo-1)*100, 2),
                         dd20_pct=round((fwd.min()/bc-1)*100, 1),
                         ret20_pct=round((fwd[-1]/bc-1)*100, 1)))
    bd = pd.DataFrame(dirs)
    bd.to_csv(OUT / "q097_p3b_break_direction.csv", index=False)
    for d in ('up', 'down'):
        g = bd[bd.dir == d]
        print(f"[{d:>4}] n={len(g)} fwd20med {g.ret20_pct.median():+.1f}% "
              f"dd<=-7%: {(g.dd20_pct <= -7).mean()*100:.0f}%")

    # ── P3c(PM 追问 2026-07-12): 量能第二层能否区分 4 崩盘上破 vs 118 良性 ──
    # 预注册三个标准度量(无切点搜索): V1 破箱日量/前20TD中位;
    # V2 破箱前5日均量/前60TD中位; V3 破箱日量/箱内中位。
    # 裁定: 零分离——4例落在良性分布 43-79 分位(V1 居中 46-60),置换
    # p=0.79-0.96,全捕获阈值误伤 53-88%。崩盘前的弱上破在现货日线量能
    # 维度与普通再锚定不可区分(既非缩量假突破也非放量 blow-off)。
    vol = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    vi = pd.to_datetime(vol.index)
    if vi.tz is not None:
        vi = vi.tz_localize(None)
    vol.index = vi.normalize()
    vv = vol["Volume"].reindex(close.index).astype(float).values
    crash_brk = {"2018-01-22", "2020-02-12", "2020-08-28", "2025-02-18"}
    urows = []
    for s, e in eps15:
        b = e + 1
        if b >= len(v) or b < 60:
            continue
        hi = v[s:e+1].max()
        if v[b] <= hi:
            continue
        urows.append(dict(brk=str(close.index[b].date()),
                          crash=str(close.index[b].date()) in crash_brk,
                          V1=round(vv[b] / np.median(vv[b-20:b]), 3),
                          V2=round(np.mean(vv[b-4:b+1]) / np.median(vv[b-60:b]), 3),
                          V3=round(vv[b] / np.median(vv[s:e+1]), 3)))
    uv = pd.DataFrame(urows)
    uv.to_csv(OUT / "q097_p3c_upbreak_volume.csv", index=False)
    for m in ("V1", "V2", "V3"):
        x, y = uv[uv.crash][m], uv[~uv.crash][m]
        print(f"[{m}] 崩盘4例均值 {x.mean():.2f} vs 良性 {y.mean():.2f} | "
              f"分位 {[round((y < xi).mean()*100) for xi in x]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
