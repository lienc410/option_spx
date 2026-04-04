"""
SPEC-019 Prototype — Trend Signal × Strategy Family Effectiveness
分析趋势信号（50MA gap）在不同策略族中的实际预测价值。

核心问题：
  "In which strategy families is lagging confirmation helpful,
   and in which is it harmful?"

方法：
1. 从 SPX 历史重建每笔交易 entry_date 的 trend signal（MA50 gap）
2. 按 (strategy, trend_signal) 分组统计 WR / Avg PnL / ROM
3. 计算 "aligned" vs "counter-trend" 交易的表现差异
4. 量化 MA 滞后带来的信号衰减

Aligned = 策略与当日趋势信号方向一致（e.g. BPS_HV in BULLISH）
Counter  = 策略与当日趋势信号方向相反（e.g. BCS_HV in BULLISH）
Neutral  = 策略为中性（IC, IC_HV）或趋势为 NEUTRAL
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
from backtest.engine import run_backtest
from signals.trend import fetch_spx_history, TREND_THRESHOLD

# ─── 1. 运行 26yr 回测 ─────────────────────────────────────────────────────────

print("加载 26yr 回测数据...")
trades, _, _ = run_backtest(start_date="2000-01-01", verbose=False)
print(f"完成: {len(trades)} 笔")

# ─── 2. 重建每笔交易 entry_date 的趋势信号 ─────────────────────────────────────

print("加载 SPX 历史 (max) 用于 MA50 重建...")
spx_df = fetch_spx_history(period="max")
spx_df = spx_df.sort_index()

# 计算 MA50 和 MA_gap
spx_df["ma50"]      = spx_df["close"].rolling(50).mean()
spx_df["ma_gap_pct"] = (spx_df["close"] - spx_df["ma50"]) / spx_df["ma50"]
spx_df["trend"] = spx_df["ma_gap_pct"].apply(
    lambda g: "BULLISH" if g > TREND_THRESHOLD else ("BEARISH" if g < -TREND_THRESHOLD else "NEUTRAL")
)

# 移除时区信息（backtest 日期是字符串 YYYY-MM-DD）
if spx_df.index.tz is not None:
    spx_df.index = spx_df.index.tz_localize(None)
spx_df.index = pd.to_datetime(spx_df.index).normalize()

def get_trend_at_date(date_str: str) -> str:
    """返回 entry_date 的 trend signal，找不到则向前查找最近交易日"""
    dt = pd.to_datetime(date_str)
    if dt in spx_df.index:
        return str(spx_df.loc[dt, "trend"])
    # 向前找最近交易日
    prev = spx_df.index[spx_df.index <= dt]
    if len(prev) > 0:
        return str(spx_df.loc[prev[-1], "trend"])
    return "NEUTRAL"

def get_ma_gap_at_date(date_str: str) -> float:
    dt = pd.to_datetime(date_str)
    if dt in spx_df.index:
        v = spx_df.loc[dt, "ma_gap_pct"]
        return 0.0 if pd.isna(v) else float(v)
    prev = spx_df.index[spx_df.index <= dt]
    if len(prev) > 0:
        v = spx_df.loc[prev[-1], "ma_gap_pct"]
        return 0.0 if pd.isna(v) else float(v)
    return 0.0

print("重建每笔交易的 entry trend...")
records = []
for t in trades:
    entry_trend = get_trend_at_date(t.entry_date)
    ma_gap      = get_ma_gap_at_date(t.entry_date)

    # 判断 aligned / counter / neutral
    strat = t.strategy.value
    if strat in ("Bull Put Spread", "Bull Put Spread (High Vol)", "Bull Call Diagonal"):
        bull_strat = True
        bear_strat = False
    elif strat in ("Bear Call Spread (High Vol)",):
        bull_strat = False
        bear_strat = True
    else:  # IC, IC_HV = neutral
        bull_strat = False
        bear_strat = False

    if bull_strat:
        alignment = "aligned" if entry_trend == "BULLISH" else (
                    "counter" if entry_trend == "BEARISH" else "neutral_trend")
    elif bear_strat:
        alignment = "aligned" if entry_trend == "BEARISH" else (
                    "counter" if entry_trend == "BULLISH" else "neutral_trend")
    else:
        alignment = "neutral_strat"

    records.append({
        "strategy":     strat,
        "entry_date":   t.entry_date,
        "entry_trend":  entry_trend,
        "ma_gap_pct":   ma_gap * 100,  # 转为 %
        "alignment":    alignment,
        "pnl":          t.exit_pnl,
        "win":          t.exit_pnl > 0,
        "rom":          t.rom_annualized if t.total_bp > 0 else None,
        "hold_days":    t.hold_days,
        "exit_reason":  t.exit_reason,
    })

df = pd.DataFrame(records)

# ─── 3. 总体 trend signal 分布 ─────────────────────────────────────────────────

print("\n" + "=" * 70)
print("  TREND SIGNAL × STRATEGY EFFECTIVENESS")
print("=" * 70)

print("\n  一、26yr 入场时趋势信号分布")
trend_counts = df["entry_trend"].value_counts()
for trend, n in trend_counts.items():
    print(f"    {trend:<10} {n:>4} 笔  ({n/len(df)*100:.1f}%)")

# ─── 4. 按 strategy + alignment 分层统计 ──────────────────────────────────────

print("\n  二、按策略族×alignment 分层（WR / AvgPnL / AvgROM）")
print(f"  {'策略':<32} {'Alignment':<16} {'n':>4} {'WR':>7} {'AvgPnL':>10} {'AvgROM':>8}")
print("  " + "-" * 80)

group = df.groupby(["strategy", "alignment"])
for (strat, align), g in group:
    wr     = g["win"].mean() * 100
    avg_pnl = g["pnl"].mean()
    roms   = g["rom"].dropna()
    avg_rom = roms.mean() if len(roms) else 0
    print(f"  {strat:<32} {align:<16} {len(g):>4} {wr:>6.0f}% {avg_pnl:>+10,.0f} {avg_rom:>+8.3f}")

# ─── 5. Directional 策略：Aligned vs Counter 差异 ─────────────────────────────

print("\n  三、方向性策略 aligned vs counter 差异")
print()
directional_strats = ["Bull Put Spread", "Bull Put Spread (High Vol)",
                      "Bear Call Spread (High Vol)", "Bull Call Diagonal"]

for strat in directional_strats:
    sub = df[df["strategy"] == strat]
    if sub.empty:
        continue
    aligned  = sub[sub["alignment"] == "aligned"]
    counter  = sub[sub["alignment"] == "counter"]
    neutral  = sub[sub["alignment"] == "neutral_trend"]

    print(f"  {strat}  (n={len(sub)})")
    for label, grp in [("aligned     ", aligned), ("counter     ", counter), ("neutral_tr  ", neutral)]:
        if grp.empty:
            print(f"    {label}  n=0")
            continue
        wr  = grp["win"].mean() * 100
        avg = grp["pnl"].mean()
        rom = grp["rom"].dropna().mean() if len(grp["rom"].dropna()) else 0
        print(f"    {label}  n={len(grp):>3}  WR={wr:.0f}%  AvgPnL={avg:+,.0f}  ROM={rom:+.3f}")
    print()

# ─── 6. IC / IC_HV：NEUTRAL trend vs BULLISH/BEARISH ──────────────────────────

print("  四、中性策略（IC / IC_HV）按趋势信号分层")
print()
for strat in ["Iron Condor", "Iron Condor (High Vol)"]:
    sub = df[df["strategy"] == strat]
    if sub.empty:
        continue
    print(f"  {strat}  (n={len(sub)})")
    for trend_val in ["BULLISH", "NEUTRAL", "BEARISH"]:
        grp = sub[sub["entry_trend"] == trend_val]
        if grp.empty:
            continue
        wr  = grp["win"].mean() * 100
        avg = grp["pnl"].mean()
        print(f"    trend={trend_val:<10}  n={len(grp):>3}  WR={wr:.0f}%  AvgPnL={avg:+,.0f}")
    print()

# ─── 7. MA Gap 量级分析：趋势信号强度与 PnL 相关性 ────────────────────────────

print("  五、MA Gap 量级 vs 性能（Bull Put Spread 家族）")
print()
bps_family = df[df["strategy"].isin(["Bull Put Spread", "Bull Put Spread (High Vol)"])].copy()
bps_family["gap_bucket"] = pd.cut(
    bps_family["ma_gap_pct"],
    bins=[-100, -3, -1, 0, 1, 3, 6, 100],
    labels=["≤-3%", "-3~-1%", "-1~0%", "0~1%", "1~3%", "3~6%", "≥6%"]
)
gap_stats = bps_family.groupby("gap_bucket", observed=True).agg(
    n=("pnl", "count"),
    wr=("win", lambda x: x.mean() * 100),
    avg_pnl=("pnl", "mean"),
).reset_index()
for _, row in gap_stats.iterrows():
    print(f"    MA gap={row['gap_bucket']:<8}  n={int(row['n']):>4}  WR={row['wr']:.0f}%  AvgPnL={row['avg_pnl']:+,.0f}")

# ─── 8. 趋势翻转（trend flip）对 Diagonal 损失的关系 ──────────────────────────

print("\n  六、Bull Call Diagonal：entry trend vs exit reason")
print()
diag = df[df["strategy"] == "Bull Call Diagonal"]
if not diag.empty:
    for trend_val in ["BULLISH", "NEUTRAL", "BEARISH"]:
        grp = diag[diag["entry_trend"] == trend_val]
        if grp.empty:
            continue
        losses = grp[~grp["win"]]
        print(f"  entry_trend={trend_val:<10}  n={len(grp):>3}  WR={grp['win'].mean()*100:.0f}%  "
              f"AvgPnL={grp['pnl'].mean():+,.0f}")
        if not losses.empty:
            reasons = losses["exit_reason"].value_counts()
            for reason, cnt in reasons.items():
                print(f"      亏损原因: {reason} ×{cnt}")
    print()

# ─── 9. 滞后性分析：MA50 vs MA20 的 lag 差异 ──────────────────────────────────

print("  七、MA50 滞后性估算")
print()
# 计算 MA20 信号
spx_df["ma20"]      = spx_df["close"].rolling(20).mean()
spx_df["ma20_gap"]  = (spx_df["close"] - spx_df["ma20"]) / spx_df["ma20"] * 100
spx_df["ma50_gap"]  = spx_df["ma_gap_pct"] * 100

# MA20 与 MA50 信号分歧天数（MA20 BULLISH but MA50 NEUTRAL/BEARISH）
spx_recent = spx_df.dropna(subset=["ma20", "ma50"])
ma20_bull = spx_recent["ma20_gap"] > 1.0
ma50_bull = spx_recent["ma50_gap"] > 1.0
ma20_bear = spx_recent["ma20_gap"] < -1.0
ma50_bear = spx_recent["ma50_gap"] < -1.0

diverge_bull = (ma20_bull & ~ma50_bull).sum()   # MA20 先看多，MA50 还没跟上
diverge_bear = (ma20_bear & ~ma50_bear).sum()   # MA20 先看空，MA50 还没跟上
total_days = len(spx_recent)

print(f"  总交易日数: {total_days}")
print(f"  MA20 先于 MA50 看多（MA20>1% 但 MA50≤1%）: {diverge_bull} 天 ({diverge_bull/total_days*100:.1f}%)")
print(f"  MA20 先于 MA50 看空（MA20<-1% 但 MA50≥-1%）: {diverge_bear} 天 ({diverge_bear/total_days*100:.1f}%)")
print()

# 计算 MA50 翻转前需要多少天的 MA20 连续信号
print("  MA20 领先 MA50 的平均天数（趋势翻转时）：")
ma50_signal = spx_recent["ma50_gap"].apply(lambda g: "BULLISH" if g > 1 else ("BEARISH" if g < -1 else "NEUTRAL"))
ma20_signal = spx_recent["ma20_gap"].apply(lambda g: "BULLISH" if g > 1 else ("BEARISH" if g < -1 else "NEUTRAL"))

# 找 MA50 从 NON-BULLISH 翻转为 BULLISH 的转变点
transitions = []
prev_ma50 = "NEUTRAL"
for i in range(len(spx_recent)):
    curr_ma50 = ma50_signal.iloc[i]
    curr_ma20 = ma20_signal.iloc[i]
    if curr_ma50 == "BULLISH" and prev_ma50 != "BULLISH":
        # MA50 刚翻多 — 往前找 MA20 是何时翻多的
        j = i - 1
        lead = 0
        while j >= 0 and ma20_signal.iloc[j] == "BULLISH":
            lead += 1
            j -= 1
        transitions.append(lead)
    prev_ma50 = curr_ma50

if transitions:
    print(f"    MA50 翻多时，MA20 已领先 {np.mean(transitions):.1f} 天（中位数 {np.median(transitions):.0f} 天）")
    print(f"    P90 领先天数: {np.percentile(transitions, 90):.0f} 天")

# ─── 10. 综合发现 ──────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("  发现汇总")
print("=" * 70)
print("""
  【关键发现预期】
  - BPS / BPS_HV（bull 策略）：aligned > neutral_trend >> counter（方向一致时更好）
  - BCS_HV（bear 策略）：   aligned > neutral_trend >> counter
  - IC / IC_HV（neutral）：   NEUTRAL trend 时 WR 最高；BULLISH/BEARISH 时 WR 下降
  - Diagonal：                 aligned 时胜率最高；BEARISH entry 是最大风险（与 trend_flip 规则吻合）

  【滞后性代价】
  - MA50 趋势信号是 20–25 天滞后的"确认"信号，而非"预测"信号
  - 对于 30–35 DTE 的短期仓位，入场时的 trend signal 可能已偏移 1–2 个持仓周期
  - MA20 可能提供更少滞后的替代确认

  【策略含义】
  - 如果 aligned 策略相比 neutral_trend 只有微小 WR 提升（< 5%），说明趋势信号主要起"过滤"作用而非"选择"作用
  - 如果 counter 策略 WR 仍然 > 70%（高于随机），说明趋势方向对 short-vol 策略影响有限
""")
