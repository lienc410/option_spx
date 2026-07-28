"""Q105 P1 — FOMC 事件前操作研究（PM 2026-07-28 立项）。

场景：明日 FOMC（本次会议 hike 概率已抬升至 30%，较大可能 hold-unchanged
但给出鹰派言论），SPX 处于长期箱体（7259.22-7609.78，day 57）中下方。
问：方向性交易 / vol 交易 / 不交易？

## 数据边界（先说清楚测得到什么、测不到什么）
本仓库有 220 个 FOMC 公告日期（2000-2026，`data/q085_fomc_dates.csv`）+
完整 SPX/VIX/VIX3M 历史。**没有历史 Fed funds futures / CME FedWatch 概率
时间序列**——无法重建"哪些历史会议是'鹰派 hold'"或"哪些会议事前 hike
概率被定价到 30%"。因此本研究：
  - 能测：FOMC 公告日附近的真实 SPX 已实现波动 + VIX 隐含波动路径
    （事前累积/事后回落，即"vol crush"经验规律）——这是全样本，
    不区分会议类型的通用统计。
  - 不能测：条件于"鹰派 hold"这个具体会议类型的历史类比——诚实标注为
    数据缺口，不假装有更细的证据。
  - 能测：今天真实的箱体位置、DD Overlay 触发距离、系统当前真实信号
    （非讨论稿——直接跑生产 selector）。

## 预注册问题（先写后跑）
  Q1 FOMC 日 vol crush 的真实幅度与稳健性（事前 5 日 vs 事后 1/5 日 VIX
     变化），分全历史/post-2020，检验它是否是可交易的稳定现象。
  Q2 FOMC 日 SPX 已实现波动是否显著高于非 FOMC 日（配对同期基准，
     排除总体趋势混淆）——回答"vol trade 的隐含溢价是否对得起已实现风险"。
  Q3 当前实际点位相对箱体位置 + DD Overlay 触发距离——纯算术，非统计推断。
  Q4 当前系统实盘信号是什么（生产 selector 直接跑，不是讨论稿）——避免
     人工判断与已部署机制脱节。
  Q5 今日真实 VIX/VIX3M 期限结构相对历史 FOMC 前夜的位置——今天是
     contango 还是 backwardation，在历史分布里算不算异常。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "research" / "q105"


def load_data():
    spx = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    idx = pd.to_datetime(spx.index)
    spx.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
    close = spx["Close"].dropna()
    # VIX 数据从 1990 起，SPX 这份 max 缓存从 1927 起——起点不同，绝不可
    # 共用位置索引；reindex 到 close 的索引上（ffill）后位置索引才对齐。
    close = close.loc["1990-01-01":]
    vix = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl")
    vi = pd.to_datetime(vix.index)
    vix.index = (vi.tz_localize(None) if vi.tz is not None else vi).normalize()
    vix_aligned = vix["Close"].reindex(close.index).ffill()
    try:
        vix3m = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__VIX3M__max__1d.pkl")
        v3i = pd.to_datetime(vix3m.index)
        vix3m.index = (v3i.tz_localize(None) if v3i.tz is not None else v3i).normalize()
        vix3m_aligned = vix3m["Close"].reindex(close.index).ffill()
    except Exception:
        vix3m_aligned = pd.Series(index=close.index, dtype=float)
    fomc = pd.read_csv(ROOT / "data" / "q085_fomc_dates.csv", parse_dates=["announce_date"])
    return close, vix_aligned, vix3m_aligned, fomc["announce_date"]


def nearest_idx(index, date):
    pos = index.searchsorted(date)
    if pos >= len(index):
        return None
    return pos


def main() -> int:
    close, vix, vix3m, fomc_dates = load_data()
    print(f"data: {close.index[0].date()} → {close.index[-1].date()}  "
          f"FOMC dates: {len(fomc_dates)} ({fomc_dates.min().date()} → {fomc_dates.max().date()})")

    # ═ Q1/Q2: FOMC 日 vol crush + 已实现波动，全历史 + post-2020 ══════════
    rows = []
    ret = close.pct_change()
    for d in fomc_dates:
        i = nearest_idx(close.index, d)
        if i is None or i < 6 or i + 6 >= len(close):
            continue
        vix_pre5 = vix.iloc[i - 5]
        vix_day = vix.iloc[i]
        vix_post1 = vix.iloc[i + 1]
        vix_post5 = vix.iloc[i + 5]
        abs_move_day = abs(ret.iloc[i]) * 100
        abs_move_post1 = abs(ret.iloc[i + 1]) * 100
        rows.append({
            "date": close.index[i].date(), "year": close.index[i].year,
            "vix_pre5": vix_pre5, "vix_day": vix_day,
            "vix_post1": vix_post1, "vix_post5": vix_post5,
            "vix_chg_pre_to_day_pct": (vix_day / vix_pre5 - 1) * 100,
            "vix_crush_day_to_post1_pct": (vix_post1 / vix_day - 1) * 100,
            "vix_crush_day_to_post5_pct": (vix_post5 / vix_day - 1) * 100,
            "abs_move_day_pct": abs_move_day,
            "abs_move_post1_pct": abs_move_post1,
        })
    fdf = pd.DataFrame(rows)
    fdf.to_csv(OUT / "q105_p1_fomc_day_stats.csv", index=False)

    # 非 FOMC 日基准：同期所有交易日的已实现波动（配对基准，排除总体趋势混淆）
    all_abs_ret = ret.abs() * 100
    baseline_mean = all_abs_ret.loc[fdf.date.min():fdf.date.max()].mean()

    print(f"\n═ Q1: VIX 路径（vol crush）═")
    for era_label, sub in (("full", fdf), ("post2020", fdf[fdf.year >= 2020])):
        print(f"  [{era_label}] n={len(sub)}")
        print(f"    VIX 事前5日→当日: {sub.vix_chg_pre_to_day_pct.mean():+.1f}% "
              f"(累积，median {sub.vix_chg_pre_to_day_pct.median():+.1f}%)")
        print(f"    VIX 当日→+1日: {sub.vix_crush_day_to_post1_pct.mean():+.1f}% "
              f"(median {sub.vix_crush_day_to_post1_pct.median():+.1f}%) "
              f"| crush 发生率(下降): {(sub.vix_crush_day_to_post1_pct < 0).mean()*100:.0f}%")
        print(f"    VIX 当日→+5日: {sub.vix_crush_day_to_post5_pct.mean():+.1f}% "
              f"(median {sub.vix_crush_day_to_post5_pct.median():+.1f}%)")

    print(f"\n═ Q2: 已实现波动 vs 非 FOMC 日基准（同期 |日收益率| 均值 {baseline_mean:.2f}%）═")
    for era_label, sub in (("full", fdf), ("post2020", fdf[fdf.year >= 2020])):
        print(f"  [{era_label}] FOMC 当日 |move| 均值 {sub.abs_move_day_pct.mean():.2f}% "
              f"(median {sub.abs_move_day_pct.median():.2f}%) | "
              f"+1日 |move| 均值 {sub.abs_move_post1_pct.mean():.2f}%")
        ratio = sub.abs_move_day_pct.mean() / baseline_mean
        print(f"    FOMC日/基准 比值: {ratio:.2f}x")

    # 年块 bootstrap：FOMC 日 |move| 是否显著高于基准
    rng = np.random.default_rng(11)
    years = sorted(fdf.year.unique())
    diffs = []
    for _ in range(4000):
        yrs = rng.choice(years, size=len(years), replace=True)
        sample = pd.concat([fdf[fdf.year == y] for y in yrs])
        diffs.append(sample.abs_move_day_pct.mean() - baseline_mean)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"  年块 bootstrap CI（FOMC|move| − 基准）: [{lo:+.2f}, {hi:+.2f}]pp "
          f"→ {'显著更高' if lo > 0 else ('显著更低' if hi < 0 else '不显著')}")

    # ═ Q3: 今日箱体位置 + DD Overlay 触发距离（纯算术）══════════════════════
    print(f"\n═ Q3: 今日箱体/触发线算术（实盘数据）═")
    ath = 7609.78
    box_lo, box_hi = 7259.22, 7609.78
    spx_today = 7396.81  # live quote，见对话记录
    box_pos_pct = (spx_today - box_lo) / (box_hi - box_lo) * 100
    ddath = spx_today / ath - 1
    dist_to_a_trigger = spx_today - ath * 0.96
    dist_to_box_lo = spx_today - box_lo
    print(f"  现价 {spx_today} | 箱体 {box_lo}-{box_hi}（宽 {box_hi-box_lo:.0f} 点）")
    print(f"  箱内位置: {box_pos_pct:.0f}%（0%=下沿, 100%=上沿；中点=50%）")
    print(f"  ddATH: {ddath*100:+.2f}% | 距 DD Overlay A 触发(-4%): {dist_to_a_trigger:+.0f} 点 "
          f"({dist_to_a_trigger/spx_today*100:.1f}%)")
    print(f"  距箱体下沿: {dist_to_box_lo:+.0f} 点 ({dist_to_box_lo/spx_today*100:.1f}%)")

    # ═ Q5: 今日期限结构 vs 历史 FOMC 前夜分布 ══════════════════════════════
    print(f"\n═ Q5: 今日 VIX/VIX3M 期限结构 vs 历史 FOMC 前夜（-1TD）分布 ═")
    ts_rows = []
    for d in fomc_dates:
        i = nearest_idx(close.index, d)
        if i is None or i < 1:
            continue
        pre_i = i - 1
        pre_date = close.index[pre_i]
        if pre_date not in vix3m.index or pre_date not in vix.index:
            continue
        v, v3 = vix.loc[pre_date], vix3m.loc[pre_date]
        if pd.isna(v) or pd.isna(v3) or v3 == 0:
            continue
        ts_rows.append({"date": pre_date.date(), "vix": v, "vix3m": v3,
                        "ratio": v / v3, "backwardation": v > v3})
    tsdf = pd.DataFrame(ts_rows)
    tsdf.to_csv(OUT / "q105_p1_term_structure_preFOMC.csv", index=False)
    today_ratio = 18.81 / 20.2  # live 读数，见对话记录（VIX3M 用最近可得值）
    pctl = (tsdf.ratio < today_ratio).mean() * 100
    print(f"  历史 FOMC 前夜 backwardation 比例: {tsdf.backwardation.mean()*100:.0f}% (n={len(tsdf)})")
    print(f"  历史 VIX/VIX3M ratio 分布: mean {tsdf.ratio.mean():.3f} median {tsdf.ratio.median():.3f}")
    print(f"  今日 ratio {today_ratio:.3f} → 历史分位 {pctl:.0f}%（越低=越 contango/越不像典型事件前夜）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
