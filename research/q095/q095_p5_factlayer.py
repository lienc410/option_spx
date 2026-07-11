"""Q095 P5 — 流动性/供需信号家族 A 组:事实层(预注册执行)。

宇宙(2026-07-12 采集后锁死,6 形态,不再增删):
  期限结构族(VIX9D/VIX/VIX3M 日收盘,2011-01+):
    T1 曲率      c = ln(VIX9D/VIX) − ln(VIX/VIX3M)   先验:高→forward 更差
    T2 短端比    VIX9D/VIX                            先验:高→更差
    T3 长端比    VIX/VIX3M(系统已有 backwardation 布尔的连续版) 先验:高→更差
    T4 短端倒挂持续 streak(VIX9D>VIX 连续日数)         先验:长→更差
  PCR 族(CBOE total P/C,2006-11→2019-10,era 条件性预先声明——结论只覆盖该时代):
    P1 PCR 252d 分位                                  先验:高(恐慌)→反向更好
    P2 PCR 5d z-score                                 先验:同上

事实层问题(先于任何 PnL):信号对 forward 20TD SPX 收益分布(均值/左尾 p10)
有无信息量——挂载点为敞口决定层,故看的是"未来一个月市场分布",不是策略盈亏。

方法(Q090 选择效应全套 + 宪法):
  - 推断样本 = 非重叠 20TD forward 窗口(每 20TD 采样一次,消序列重叠膨胀)
  - 两个预注册视图/形态:V1 中位切分 → 均值差(Welch t);
    V2 顶/底五分位 → p10 差(bootstrap B=2000 百分位 CI)
  - 发现集 = 全样本 12 tests(6 形态 × 2 视图),BH-FDR q=0.10(双侧)
  - 时代分层 = 幸存者的稳健性呈现(非发现渠道):TS 族 2011-19/2020-26,
    PCR 族 2006-12/2013-19;幸存者不得为单时代伪影(方向不得显著反转)
  - 杀标 K1(framing 已 ratify):FDR 后零幸存 → A 组 CLOSED-NULL

Output: q095_p5_facts.csv + 摘要。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "q095"
FWD = 20
B = 2000
rng = np.random.default_rng(20260712)


def _px(pkl):
    df = pd.read_pickle(ROOT / "data" / "market_cache" / pkl)
    s = df["Close"] if "Close" in df else df["close"]
    idx = pd.to_datetime(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")].dropna()


def load_pcr() -> pd.Series:
    raw = pd.read_csv(OUT / "data_totalpc.csv", skiprows=2)
    raw["DATE"] = pd.to_datetime(raw["DATE"])
    return raw.set_index("DATE")["P/C Ratio"].astype(float)


def main() -> int:
    spx = _px("yahoo__GSPC__max__1d.pkl")
    vix = _px("yahoo__VIX__max__1d.pkl")
    v9 = _px("yahoo__VIX9D__max__1d.pkl")
    v3m = _px("yahoo__VIX3M__max__1d.pkl")
    pcr = load_pcr()

    f = pd.DataFrame({"spx": spx, "vix": vix, "v9": v9, "v3m": v3m}).dropna()
    f["T1"] = np.log(f.v9 / f.vix) - np.log(f.vix / f.v3m)
    f["T2"] = f.v9 / f.vix
    f["T3"] = f.vix / f.v3m
    inv = (f.v9 > f.vix).astype(int)
    f["T4"] = inv.groupby((inv != inv.shift()).cumsum()).cumsum() * inv

    g = pd.DataFrame({"spx": spx, "pcr": pcr}).dropna()
    g["P1"] = g.pcr.rolling(252).rank(pct=True) * 100
    g["P2"] = (g.pcr - g.pcr.rolling(5).mean().shift(1)) / g.pcr.rolling(60).std()

    def forward_windows(frame, col):
        d = frame.dropna(subset=[col]).copy()
        d["fwd"] = d.spx.shift(-FWD) / d.spx - 1.0
        d = d.dropna(subset=["fwd"])
        return d.iloc[::FWD]                     # 非重叠采样

    rows = []
    specs = [("T1", f), ("T2", f), ("T3", f), ("T4", f), ("P1", g), ("P2", g)]
    for name, frame in specs:
        w = forward_windows(frame, name)
        # V1 中位切分 → 均值差
        med = w[name].median()
        hi, lo = w[w[name] > med].fwd, w[w[name] <= med].fwd
        t, p1v = stats.ttest_ind(hi, lo, equal_var=False)
        rows.append(dict(form=name, view="V1_mean", n=len(w),
                         stat=round(float(hi.mean() - lo.mean()) * 100, 3),
                         unit="pp(hi-lo)", t=round(float(t), 2), p=float(p1v)))
        # V2 顶/底五分位 → p10 差(bootstrap)
        q80, q20 = w[name].quantile(0.8), w[name].quantile(0.2)
        top, bot = w[w[name] >= q80].fwd.values, w[w[name] <= q20].fwd.values
        if min(len(top), len(bot)) >= 15:
            obs = np.quantile(top, 0.1) - np.quantile(bot, 0.1)
            boots = [np.quantile(rng.choice(top, len(top)), 0.1)
                     - np.quantile(rng.choice(bot, len(bot)), 0.1) for _ in range(B)]
            lo_ci, hi_ci = np.quantile(boots, [0.05, 0.95])
            p2v = float(2 * min((np.array(boots) <= 0).mean(), (np.array(boots) >= 0).mean()))
            rows.append(dict(form=name, view="V2_p10tail", n=f"{len(top)}/{len(bot)}",
                             stat=round(obs * 100, 3), unit="pp p10(top-bot)",
                             t=None, p=max(p2v, 1 / B),
                             ci=f"[{lo_ci*100:.2f},{hi_ci*100:.2f}]"))
    res = pd.DataFrame(rows)

    # BH-FDR q=0.10 across the 12 discovery tests
    m = len(res)
    res = res.sort_values("p").reset_index(drop=True)
    res["bh_crit"] = [(i + 1) / m * 0.10 for i in range(m)]
    passed_idx = res.index[res.p <= res.bh_crit]
    cutoff = passed_idx.max() if len(passed_idx) else -1
    res["fdr_pass"] = res.index <= cutoff
    res.to_csv(OUT / "q095_p5_facts.csv", index=False)

    print(f"发现集 {m} tests,BH-FDR q=0.10:")
    for _, r in res.iterrows():
        mark = "★PASS" if r.fdr_pass else "     "
        print(f" {mark} {r['form']:>3s} {r['view']:<11s} n={r['n']:>7} stat={r['stat']:>7} {r['unit']:<15s} p={r['p']:.4f}")

    # 幸存者时代分层(稳健性呈现)
    surv = res[res.fdr_pass]
    if len(surv) == 0:
        print("\n→ K1 触发:FDR 后零幸存,A 组 CLOSED-NULL(预注册条款)")
        return 0
    print("\n=== 幸存者时代分层 ===")
    for _, r in surv.iterrows():
        name = r["form"]
        frame = f if name.startswith("T") else g
        eras = ([("2011-2019", "2011-01-01", "2019-12-31"), ("2020-2026", "2020-01-01", "2026-12-31")]
                if name.startswith("T") else
                [("2006-2012", "2006-01-01", "2012-12-31"), ("2013-2019", "2013-01-01", "2019-12-31")])
        for elabel, a, b in eras:
            w = forward_windows(frame.loc[a:b], name)
            if len(w) < 30:
                print(f"  {name} [{elabel}] n={len(w)} <30 只记不算"); continue
            med = w[name].median()
            hi, lo = w[w[name] > med].fwd, w[w[name] <= med].fwd
            t, p = stats.ttest_ind(hi, lo, equal_var=False)
            print(f"  {name} [{elabel}] n={len(w)} mean-diff {float(hi.mean()-lo.mean())*100:+.2f}pp t={float(t):+.2f} p={float(p):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
