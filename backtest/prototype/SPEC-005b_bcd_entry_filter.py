# PROTOTYPE — SPEC-005b
# 目标：分析 BCD 入场前连续 BULLISH 天数与胜负的关系
# 研究问题：
#   1. 当前 BCD 入场时，入场前连续 BULLISH 天数分布如何？
#   2. 连续 BULLISH 天数越多，WR 是否越高？
#   3. 最优过滤阈值 N 是多少？（WR vs 笔数 trade-off）

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from backtest.engine import run_backtest
from strategy.selector import StrategyName

print("运行全量回测 2000-01-01...")
trades, metrics, signals = run_backtest(start_date="2000-01-01", verbose=False)

# 构建 signal_history 的日期→trend 映射
sig_df = pd.DataFrame(signals)
sig_df["date"] = pd.to_datetime(sig_df["date"])
sig_df = sig_df.set_index("date").sort_index()

bcd = [t for t in trades if t.strategy == StrategyName.BULL_CALL_DIAGONAL]
print(f"BCD 总笔数：{len(bcd)}\n")

# ─── 计算每笔 BCD 入场前连续 BULLISH 天数 ──────────────────────────────────
def count_consecutive_bullish_before(entry_date_str: str, sig_df: pd.DataFrame) -> int:
    """
    统计入场日之前（不含入场日当天）连续 BULLISH 的交易日数。
    返回 0 表示入场前一天就不是 BULLISH。
    """
    entry = pd.to_datetime(entry_date_str)
    prior = sig_df[sig_df.index < entry]
    if prior.empty:
        return 0
    count = 0
    for _, row in prior.iloc[::-1].iterrows():  # 从最近往前
        if row["trend"] == "BULLISH":
            count += 1
        else:
            break
    return count

rows = []
for t in bcd:
    consec = count_consecutive_bullish_before(t.entry_date, sig_df)
    rows.append({
        "entry":         t.entry_date,
        "exit_reason":   t.exit_reason,
        "consec_bull":   consec,
        "pnl":           t.exit_pnl,
        "win":           t.exit_pnl > 0,
    })

df = pd.DataFrame(rows)

# ─── 1. 连续 BULLISH 天数分布 ──────────────────────────────────────────────
print("=" * 55)
print("入场前连续 BULLISH 天数分布")
print("-" * 55)
buckets = [0, 1, 2, 3, 4, 5, 7, 10, 999]
labels  = ["0d","1d","2d","3d","4d","5d","6-10d",">10d"]
for i, label in enumerate(labels):
    lo, hi = buckets[i], buckets[i+1]
    subset = df[(df["consec_bull"] >= lo) & (df["consec_bull"] < hi)]
    bar = "█" * len(subset)
    print(f"  {label:<6} {len(subset):>3} 笔  {bar}")

# ─── 2. 按 consec_bull 阈值分析 WR & PnL ──────────────────────────────────
print(f"\n{'=' * 65}")
print(f"{'过滤阈值':<12} {'剩余笔数':>8} {'占比':>6} {'WR':>7} {'总PnL':>10} {'均PnL':>9} {'Sharpe代理':>10}")
print("-" * 65)

for threshold in [0, 1, 2, 3, 5, 7, 10]:
    subset = df[df["consec_bull"] >= threshold]
    if len(subset) == 0:
        continue
    n   = len(subset)
    wr  = subset["win"].mean() * 100
    tot = subset["pnl"].sum()
    avg = subset["pnl"].mean()
    pct = n / len(df) * 100
    # Sharpe 代理：均值 / 标准差（越大越好，忽略无风险利率）
    std = subset["pnl"].std()
    sharpe_proxy = avg / std if std > 0 else 0
    label = f"≥{threshold}d"
    print(f"  {label:<10} {n:>8} {pct:>5.0f}% {wr:>6.0f}% {tot:>+10.0f} {avg:>+9.0f} {sharpe_proxy:>+10.3f}")

# ─── 3. 关键截面：≥3d vs 当前（≥1d）明细对比 ──────────────────────────────
print(f"\n{'=' * 55}")
print("关键对比：当前（≥1d BULLISH 即入场）vs 过滤后（≥3d）")
print("-" * 55)
for label, thresh in [("当前 ≥1d", 1), ("过滤 ≥3d", 3), ("过滤 ≥5d", 5)]:
    s = df[df["consec_bull"] >= thresh]
    wr = s["win"].mean() * 100 if len(s) else 0
    print(f"  {label}：{len(s)} 笔，WR {wr:.0f}%，总PnL ${s['pnl'].sum():+.0f}")

# ─── 4. 被过滤掉的笔数的胜率（看过滤的是好是坏）──────────────────────────
print(f"\n{'=' * 55}")
print("被各阈值过滤掉的交易（入场前 BULLISH 天数不足）")
print("-" * 55)
for threshold in [2, 3, 5]:
    filtered_out = df[df["consec_bull"] < threshold]
    if len(filtered_out) == 0:
        continue
    wr  = filtered_out["win"].mean() * 100
    avg = filtered_out["pnl"].mean()
    print(f"  <{threshold}d（被过滤）：{len(filtered_out)} 笔，WR {wr:.0f}%，均PnL ${avg:+.0f}")

# ─── 5. 连续 BULLISH 天数 vs 胜率散点（分箱）──────────────────────────────
print(f"\n{'=' * 55}")
print("连续 BULLISH 天数 → WR（分箱）")
print("-" * 55)
bins = [(0,1,"0d"),(1,2,"1d"),(2,3,"2d"),(3,5,"3-4d"),(5,8,"5-7d"),(8,999,"≥8d")]
for lo, hi, label in bins:
    s = df[(df["consec_bull"] >= lo) & (df["consec_bull"] < hi)]
    if len(s) == 0:
        continue
    wr  = s["win"].mean() * 100
    avg = s["pnl"].mean()
    bar = "█" * int(wr / 5)
    print(f"  {label:<6} n={len(s):>2}  WR {wr:>3.0f}%  {bar}  均PnL ${avg:+.0f}")

print("\n完成。")
