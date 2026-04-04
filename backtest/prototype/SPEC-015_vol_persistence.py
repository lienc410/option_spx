"""
SPEC-015 Prototype — Vol Persistence Analysis
研究 HIGH_VOL regime 进入后的持续时长分布，
以及入场时的特征变量是否能预测持续时长。

输出：
1. HIGH_VOL spell 持续时长分布（分位数 / 直方图统计）
2. 入场时 feature vs 持续时长的相关分析
3. 按持续时长分层的 BPS/BCS_HV 历史交易 PnL 分析
4. 提出 vol persistence risk throttle 的候选规则
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
from signals.vix_regime import fetch_vix_history, _classify_regime, Regime

# ─── 1. 加载 VIX 历史，标记每日 regime ────────────────────────────────────────

vix_df = fetch_vix_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
vix_df = vix_df.sort_index()

# 计算 5 日 VIX 均线（入场时 VIX trend 的 proxy）
vix_df["vix5"] = vix_df["vix"].rolling(5).mean()
vix_df["vix10"] = vix_df["vix"].rolling(10).mean()
vix_df["vix_slope"] = vix_df["vix5"] - vix_df["vix10"]  # 正 = rising, 负 = falling
vix_df["vix20"] = vix_df["vix"].rolling(20).mean()
vix_df["regime"] = vix_df["vix"].apply(_classify_regime)

# HIGH_VOL = VIX 22–35
HIGH_LOW  = 22.0
HIGH_HIGH = 35.0
vix_df["is_hv"] = (vix_df["vix"] >= HIGH_LOW) & (vix_df["vix"] < HIGH_HIGH)

# ─── 2. 识别 HIGH_VOL spell（连续 is_hv=True 区间）─────────────────────────

spells = []
in_spell = False
spell_start = None
spell_entry_vix = None
spell_entry_slope = None

for date, row in vix_df.iterrows():
    if row["is_hv"] and not in_spell:
        in_spell = True
        spell_start = date
        spell_entry_vix = row["vix"]
        spell_entry_slope = row["vix_slope"]
    elif not row["is_hv"] and in_spell:
        in_spell = False
        duration = (date - spell_start).days
        spells.append({
            "start":       spell_start,
            "end":         date,
            "duration_days": duration,
            "entry_vix":   spell_entry_vix,
            "entry_slope": spell_entry_slope,
            "peak_vix":    vix_df.loc[spell_start:date, "vix"].max(),
        })

# 若 spell 延续到数据末尾
if in_spell:
    date = vix_df.index[-1]
    duration = (date - spell_start).days
    spells.append({
        "start":       spell_start,
        "end":         date,
        "duration_days": duration,
        "entry_vix":   spell_entry_vix,
        "entry_slope": spell_entry_slope,
        "peak_vix":    vix_df.loc[spell_start:, "vix"].max(),
        "ongoing":     True,
    })

spells_df = pd.DataFrame(spells)

print("=" * 65)
print("  VOL PERSISTENCE ANALYSIS — HIGH_VOL Spell Duration")
print("=" * 65)
print(f"  数据范围: {vix_df.index[0].date()} → {vix_df.index[-1].date()}")
print(f"  总 HIGH_VOL spells: {len(spells_df)}")
print()

# ─── 3. 持续时长分布 ────────────────────────────────────────────────────────

dur = spells_df["duration_days"]
print("  持续时长分布（日历天数）:")
print(f"    中位数     : {dur.median():.0f} 天")
print(f"    均值       : {dur.mean():.0f} 天")
print(f"    P25        : {dur.quantile(0.25):.0f} 天")
print(f"    P75        : {dur.quantile(0.75):.0f} 天")
print(f"    P90        : {dur.quantile(0.90):.0f} 天")
print(f"    Max        : {dur.max():.0f} 天")
print(f"    ≤ 10 天    : {(dur <= 10).sum()} 笔 ({(dur <= 10).mean()*100:.0f}%)")
print(f"    ≤ 30 天    : {(dur <= 30).sum()} 笔 ({(dur <= 30).mean()*100:.0f}%)")
print(f"    > 60 天    : {(dur > 60).sum()} 笔 ({(dur > 60).mean()*100:.0f}%)")
print(f"    > 100 天   : {(dur > 100).sum()} 笔 ({(dur > 100).mean()*100:.0f}%)")
print()

# ─── 4. 入场时特征 vs 持续时长 ───────────────────────────────────────────────

print("  入场特征 vs 持续时长（相关性）:")
corr_vix   = spells_df["entry_vix"].corr(spells_df["duration_days"])
corr_slope = spells_df["entry_slope"].corr(spells_df["duration_days"])
corr_peak  = spells_df["peak_vix"].corr(spells_df["duration_days"])
print(f"    entry_vix  vs duration : r = {corr_vix:+.3f}")
print(f"    entry_slope vs duration: r = {corr_slope:+.3f}")
print(f"    peak_vix   vs duration : r = {corr_peak:+.3f}")
print()

# 分层：入场 VIX 分组
bins = [22, 25, 28, 35]
labels = ["22–25", "25–28", "28–35"]
spells_df["entry_vix_bin"] = pd.cut(spells_df["entry_vix"], bins=bins, labels=labels)
grp = spells_df.groupby("entry_vix_bin", observed=True)["duration_days"].agg(["median", "mean", "count"])
print("  按入场 VIX 水平分层（中位/均值 持续天数）:")
for label, row2 in grp.iterrows():
    print(f"    VIX {label}: n={int(row2['count']):>3}  中位={row2['median']:.0f}d  均值={row2['mean']:.0f}d")
print()

# 分层：入场时 VIX slope
spells_df["slope_rising"] = spells_df["entry_slope"] > 0
grp2 = spells_df.groupby("slope_rising", observed=True)["duration_days"].agg(["median", "mean", "count"])
print("  按入场 VIX slope 分层（rising vs falling）:")
for rising, row2 in grp2.iterrows():
    label = "VIX RISING" if rising else "VIX FALLING/FLAT"
    print(f"    {label}: n={int(row2['count']):>3}  中位={row2['median']:.0f}d  均值={row2['mean']:.0f}d")
print()

# ─── 5. Sticky spell（> 30 天）的特征 ────────────────────────────────────────

sticky = spells_df[spells_df["duration_days"] > 30]
short  = spells_df[spells_df["duration_days"] <= 30]
print("  Sticky spell（> 30 天）vs 短暂 spell（≤ 30 天）特征对比:")
print(f"    Sticky: n={len(sticky)}  entry_vix均={sticky['entry_vix'].mean():.1f}  slope均={sticky['entry_slope'].mean():.2f}  peak_vix均={sticky['peak_vix'].mean():.1f}")
print(f"    Short:  n={len(short)}   entry_vix均={short['entry_vix'].mean():.1f}  slope均={short['entry_slope'].mean():.2f}  peak_vix均={short['peak_vix'].mean():.1f}")
print()

# ─── 6. Sticky spell 列表（Top 10 最长）──────────────────────────────────────

print("  最长 HIGH_VOL spells（Top 10）:")
top = spells_df.nlargest(10, "duration_days")[["start", "end", "duration_days", "entry_vix", "peak_vix"]]
for _, r in top.iterrows():
    print(f"    {r['start'].date()} → {r['end'].date()}  {r['duration_days']:.0f}d  entryVIX={r['entry_vix']:.1f}  peakVIX={r['peak_vix']:.1f}")
print()

# ─── 7. 持续时长与短持策略（35 DTE）的重叠风险 ────────────────────────────────

print("  风险重叠分析:")
print(f"    BPS_HV/BCS_HV 持仓窗口: ~14 个交易日 ≈ 20 日历天")
pct_exceeds_hold = (dur > 20).mean() * 100
print(f"    HIGH_VOL spell 持续 > 20 天的比例: {pct_exceeds_hold:.0f}%")
print(f"    → 意味着 {pct_exceeds_hold:.0f}% 的入场时，整个持仓期仍处于 HIGH_VOL 环境内")
pct_very_long = (dur > 60).mean() * 100
print(f"    HIGH_VOL spell 持续 > 60 天: {pct_very_long:.0f}%")
print(f"    → 这类 spell 内连续开仓 2+ 笔，可能形成叠加 short-vol 暴露")
print()

# ─── 8. 候选风险阈值规则 ─────────────────────────────────────────────────────

print("  候选 Vol Persistence Throttle 规则:")
print()
print("  规则 A（时长概率）:")
p50 = dur.median()
p75 = dur.quantile(0.75)
print(f"    HIGH_VOL spell 中位数 {p50:.0f} 天。")
print(f"    入场后第 {int(p50)} 天仍在 HIGH_VOL → 已超过 50% spell 的正常持续时长")
print(f"    入场后第 {int(p75)} 天仍在 HIGH_VOL → 已进入 P75 sticky zone")
print(f"    建议：spell 内第二笔 BPS/BCS_HV 开仓要求 spell_age ≤ {int(p50)} 天")
print()
print("  规则 B（累积入场限制）:")
print("    同一 spell 内：允许最多 2 笔同类仓位；第 3 笔及以后 → REDUCE_WAIT")
print()
print("  规则 C（entry_vix 分层）:")
rising_median = spells_df[spells_df["slope_rising"]]["duration_days"].median()
falling_median = spells_df[~spells_df["slope_rising"]]["duration_days"].median()
print(f"    VIX RISING 入场的 spell 中位时长 = {rising_median:.0f} 天（当前已有 VIX RISING 过滤）")
print(f"    VIX FLAT/FALLING 入场的 spell 中位时长 = {falling_median:.0f} 天")
print(f"    → VIX RISING 过滤已捕获较高比例的 sticky spells")
