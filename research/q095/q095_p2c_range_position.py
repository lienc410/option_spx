"""Q095 P2c — 已确认震荡内的入场位置条件化:事实层。

PM 挑战(2026-07-13)成立:P2b 杀的是"停手 gate",检测器本身存活且已部署
(SPEC-094.4)。批 1(区间上沿 7576)vs 批 2(低 1.3%)的 $4,900/对 自然实验
指向新物体:**已确认震荡内,入场日在区间中的位置是否决定 BPS/BCD 成败?**

预注册(锁死):
  条件:entry 日落在 hindsight episode 日历内(185 段,事实层刻画用;
       若成立,规则翻译走 094.4 式因果重放 AC)
  位置度量(纯因果,规则可直译):pos_t = (close_t − min15) / (max15 − min15)
       (trailing 15TD 区间位置,0=下沿 1=上沿)
  分层:绝对切点 0.333 / 0.667(非样本分位,免切点拟合)
  **主检验(唯一)**:下 1/3 vs 上 1/3 的 exit_pnl 均值差(Welch t,双侧)
  成功门槛:p<0.05 且方向=下沿更好 且效应 ≥$1,000/笔(engine scale)
       → 进规则设计+因果翻译;否则 CLOSED
  呈现(非发现渠道):family 拆分 / era 拆分 / 中位数差
边界:与 Q085 P1a(无条件近支撑 strike 放置,已 kill)不同物体——
  本研究条件于已确认震荡、度量入场时机;engine trades 含 selector 全部
  gate 通过后的入场,分层内生于路由(披露,不矫正)。

Output: q095_p2c_facts.csv + 摘要。
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


def main() -> int:
    tr = pd.read_csv(OUT / "q095_p1_attribution.csv", parse_dates=["entry_date"])
    tr = tr[tr.family.isin(["BPS", "BCD"])].copy()
    eps = pd.read_csv(OUT / "q095_p2b_episodes.csv", parse_dates=["start", "end"])

    df = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    close = pd.Series(df["Close"].values, index=idx.normalize()).dropna()
    lo15 = close.rolling(15).min()
    hi15 = close.rolling(15).max()
    pos = ((close - lo15) / (hi15 - lo15)).rename("pos")

    def in_episode(d):
        return bool(((eps.start <= d) & (d <= eps.end)).any())

    tr["in_ep"] = tr.entry_date.map(in_episode)
    tr["pos"] = tr.entry_date.map(lambda d: float(pos.get(d, np.nan)))
    sample = tr[tr.in_ep & tr.pos.notna()].copy()
    sample["tercile"] = pd.cut(sample.pos, [-0.01, 0.333, 0.667, 1.01],
                               labels=["bottom", "mid", "top"])
    sample.to_csv(OUT / "q095_p2c_facts.csv", index=False)

    n_all = len(tr)
    print(f"BPS+BCD 全部 {n_all} 笔 | episode 内入场 {len(sample)} 笔 "
          f"({len(sample)/n_all*100:.0f}%) | 位置分布: "
          f"bottom {sum(sample.tercile=='bottom')} / mid {sum(sample.tercile=='mid')} / top {sum(sample.tercile=='top')}")

    bot = sample[sample.tercile == "bottom"].exit_pnl
    top = sample[sample.tercile == "top"].exit_pnl
    t, p = stats.ttest_ind(bot, top, equal_var=False)
    diff = float(bot.mean() - top.mean())
    print(f"\n=== 主检验(唯一): bottom vs top ===")
    print(f"bottom n={len(bot)} avg ${bot.mean():,.0f} med ${bot.median():,.0f} WR {(bot>0).mean()*100:.0f}%")
    print(f"top    n={len(top)} avg ${top.mean():,.0f} med ${top.median():,.0f} WR {(top>0).mean()*100:.0f}%")
    print(f"diff ${diff:,.0f}/笔 | t={float(t):+.2f} p={float(p):.4f}")
    ok = (p < 0.05) and (diff > 0) and (diff >= 1000)
    print(f"→ 门槛(p<0.05 & 下沿更好 & ≥$1k/笔): {'PASS — 进规则设计+因果翻译' if ok else 'FAIL — CLOSED'}")

    print(f"\n=== 呈现(非发现)===")
    for fam in ("BPS", "BCD"):
        s = sample[sample.family == fam]
        b, tp = s[s.tercile == "bottom"].exit_pnl, s[s.tercile == "top"].exit_pnl
        if min(len(b), len(tp)) >= 5:
            print(f"[{fam}] bottom n={len(b)} avg ${b.mean():,.0f} | top n={len(tp)} avg ${tp.mean():,.0f} | Δ ${b.mean()-tp.mean():,.0f}")
    for era in ("pre2020", "post2020"):
        s = sample[sample.era == era]
        b, tp = s[s.tercile == "bottom"].exit_pnl, s[s.tercile == "top"].exit_pnl
        if min(len(b), len(tp)) >= 5:
            print(f"[{era}] bottom n={len(b)} avg ${b.mean():,.0f} | top n={len(tp)} avg ${tp.mean():,.0f} | Δ ${b.mean()-tp.mean():,.0f}")
    mid = sample[sample.tercile == "mid"].exit_pnl
    print(f"[mid 对照] n={len(mid)} avg ${mid.mean():,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
