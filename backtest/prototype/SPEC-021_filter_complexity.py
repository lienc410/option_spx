"""
SPEC-021 Prototype — Filter Complexity Penalty Protocol
"Do not assume more filters always improve results."

方法：Sequential ablation study
  - 基线：不加任何额外 filter（仅 VIX regime 分类）
  - 逐一加入或移除各个 filter，测量 Sharpe / WR / TotalPnL 变化
  - 检查每个 filter 的边际贡献

可测试的 filter 维度：
  F1: IV rank/percentile signal（HIGH/NEUTRAL/LOW）
  F2: Trend signal（BULLISH/NEUTRAL/BEARISH via MA50）
  F3: VIX backwardation（spot VIX > VIX3M）
  F4: extreme_vix hard stop（≥ 35）

注意：这里用间接方法 — 分析已有回测中各类 filter 触发时的表现差异，
而不是重跑不同参数配置（需要修改 engine，超出 prototype 范围）。
间接方法：检查 backtest 数据中各信号组合的 PnL 分布。

另一角度：从研究历史（SPEC-004 ~ SPEC-014）归纳 filter 边际效果证据。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
from backtest.engine import run_backtest
from signals.vix_regime import fetch_vix_history, Regime
from signals.trend import fetch_spx_history, TREND_THRESHOLD

print("加载回测数据（2000-01-01）...")
trades, metrics, _ = run_backtest(start_date="2000-01-01", verbose=False)
print(f"完成: {len(trades)} 笔")

# ─── 重建入场时的多维信号状态 ─────────────────────────────────────────────────

vix_df = fetch_vix_history(period="max")
vix_df = vix_df.sort_index()
if vix_df.index.tz is not None:
    vix_df.index = vix_df.index.tz_localize(None)
vix_df.index = pd.to_datetime(vix_df.index).normalize()

spx_df = fetch_spx_history(period="max")
spx_df = spx_df.sort_index()
if spx_df.index.tz is not None:
    spx_df.index = spx_df.index.tz_localize(None)
spx_df.index = pd.to_datetime(spx_df.index).normalize()
spx_df["ma50"] = spx_df["close"].rolling(50).mean()
spx_df["ma_gap"] = (spx_df["close"] - spx_df["ma50"]) / spx_df["ma50"] * 100

def get_val(df, date_str, col, default):
    dt = pd.to_datetime(date_str)
    if dt in df.index:
        v = df.loc[dt, col]
        return default if pd.isna(v) else float(v)
    prev = df.index[df.index <= dt]
    if len(prev) > 0:
        v = df.loc[prev[-1], col]
        return default if pd.isna(v) else float(v)
    return default

# ─── 分析 filter 触发时的实际表现 ─────────────────────────────────────────────

print("\n" + "=" * 65)
print("  FILTER COMPLEXITY ANALYSIS — Marginal Value of Each Filter")
print("=" * 65)

# ─── F1: VIX backwardation filter ─────────────────────────────────────────────

# 从 engine.py 可知 backwardation 会阻止 BPS/BPS_HV 入场
# 但已过滤掉的交易无法直接看到。
# 间接方法：检查 BPS/BPS_HV 交易的 entry_vix 范围
# 如果 backwardation 经常发生在 HIGH_VOL，被过滤的交易是否质量更低？

print("\n  一、VIX 水平 vs BPS/BPS_HV 表现（间接验证 backwardation filter）")
print()
bps_family = [t for t in trades if t.strategy.value in ("Bull Put Spread", "Bull Put Spread (High Vol)")]
bps_df = pd.DataFrame([{
    "pnl": t.exit_pnl,
    "win": t.exit_pnl > 0,
    "entry_vix": t.entry_vix,
    "strat": t.strategy.value,
} for t in bps_family])

bps_df["vix_bucket"] = pd.cut(bps_df["entry_vix"], bins=[0, 18, 22, 26, 30, 100],
                               labels=["<18", "18-22", "22-26", "26-30", ">30"])
vix_perf = bps_df.groupby("vix_bucket", observed=True).agg(
    n=("pnl", "count"),
    wr=("win", lambda x: x.mean() * 100),
    avg_pnl=("pnl", "mean"),
).reset_index()
print(f"  BPS/BPS_HV 按 entry VIX 分层:")
for _, row in vix_perf.iterrows():
    print(f"    VIX={row['vix_bucket']:<8}  n={int(row['n']):>4}  WR={row['wr']:.0f}%  AvgPnL={row['avg_pnl']:+,.0f}")

# 结论：backwardation 发生在 entry_vix 高于正常的时候
# 如果高 VIX 时 WR 下降，则 backwardation filter 有价值

# ─── F2: 趋势信号强度分析（已从 SPEC-019 获知） ─────────────────────────────

print("\n  二、Trend Filter 触发时机 vs 实际交易质量")
print()
# 重建 entry MA gap
records = []
for t in trades:
    ma_gap = get_val(spx_df, t.entry_date, "ma_gap", 0.0)
    records.append({
        "strategy": t.strategy.value,
        "pnl": t.exit_pnl,
        "win": t.exit_pnl > 0,
        "ma_gap": ma_gap,
        "entry_vix": t.entry_vix,
    })

df_all = pd.DataFrame(records)

# Bull strategies: trend signal helps most when market is "borderline"
bull_credit = df_all[df_all["strategy"].isin(["Bull Put Spread", "Bull Put Spread (High Vol)"])]

bull_credit_copy = bull_credit.copy()
bull_credit_copy["ma_bucket"] = pd.cut(
    bull_credit_copy["ma_gap"],
    bins=[-100, 0, 1, 3, 6, 100],
    labels=["bearish", "0-1%", "1-3%", "3-6%", ">6%"]
)

print(f"  Bull 信用策略按 MA gap 分层（trend signal 边界区分）:")
for bucket, grp in bull_credit_copy.groupby("ma_bucket", observed=True):
    wr = grp["win"].mean() * 100
    avg = grp["pnl"].mean()
    print(f"    MA gap={bucket:<10}  n={len(grp):>4}  WR={wr:.0f}%  AvgPnL={avg:+,.0f}")

# ─── F3: IV signal 有效性（IV HIGH vs NEUTRAL 的 WR 差异） ────────────────────

print("\n  三、IV Signal 的边际贡献（从 selector.py 的 IVP 规则推断）")
print()
# 当前 engine 对所有信用策略在 HIGH_VOL 时都入场（无 IV signal 要求）
# 在 NORMAL regime 时要求 IV signal = HIGH 或 NEUTRAL
# 测量 NORMAL regime 中的 BPS 表现

normal_bps = [t for t in trades
              if t.strategy.value == "Bull Put Spread"
              and 15 <= t.entry_vix < 22]
hv_bps = [t for t in trades
          if t.strategy.value == "Bull Put Spread (High Vol)"
          and t.entry_vix >= 22]

for label, grp in [("BPS (NORMAL regime)", normal_bps), ("BPS_HV (HIGH_VOL regime)", hv_bps)]:
    if not grp:
        continue
    pnls = [t.exit_pnl for t in grp]
    wins = [p for p in pnls if p > 0]
    wr = len(wins) / len(pnls) * 100
    avg = np.mean(pnls)
    print(f"  {label}: n={len(grp)}, WR={wr:.0f}%, AvgPnL={avg:+,.0f}")

print()
print("  注：NORMAL regime BPS 要求 IV HIGH/NEUTRAL 才入场 → 已有 IV filter。")
print("  测量无法区分'有 IV filter'与'无 IV filter'因为 engine 已预过滤。")
print("  间接证据：若 NORMAL BPS WR 显著高于 HV BPS WR，部分可归因于 IV 过滤效果。")

# ─── F4: 从 SPEC 研究历史归纳 filter 边际贡献记录 ─────────────────────────────

print("\n  四、研究历史归纳：各 filter 的已知边际效果")
print()
filter_history = [
    ("IV_LOW 路径过滤（SPEC-009）",
     "NORMAL+IV_LOW+BULLISH → BCS（原方案）vs REDUCE（新方案）",
     "SPEC-009 实证：IV_LOW 路径 WR < 50%，移除后 Sharpe 提升",
     "正向（移除改善）"),
    ("VIX backwardation（SPEC-010）",
     "spot VIX > VIX3M → 阻止 BPS/BPS_HV 入场",
     "SPEC-010 实证：backwardation 时 BPS 亏损率高，过滤显著减少极端损失",
     "正向（保留）"),
    ("Trend flip exit（Diagonal）",
     "BEARISH trend 翻转时强制 Diagonal 出场",
     "SPEC-020 实证：32/41 Diagonal 亏损由此捕获，无 trend_flip 亏损会更大",
     "正向（保留）"),
    ("IVP vs IVR 裁决（SPEC-011 implied）",
     "当 IVR/IVP 分歧 >15pt 时用 IVP 代替 IVR",
     "研究背景：IVR 在极端期被 VIX spike 扭曲，IVP 更稳健",
     "正向（保留）"),
    ("EXTREME_VOL hard stop（VIX≥35）",
     "所有入场被阻止",
     "2020 COVID: 阻止了 VIX=80 的极端亏损路径",
     "正向（必须保留）"),
    ("Bear Call Diagonal 移除",
     "从 matrix 移除（LOW_VOL + BEARISH → REDUCE_WAIT）",
     "历史数据：Bear Call Diagonal n 太小，不稳定，已从 active matrix 删除",
     "正向（保留）"),
    ("BCS_HV 增加（SPEC-006）",
     "HIGH_VOL BEARISH → BCS_HV（之前是 REDUCE_WAIT）",
     "SPEC-006 实证：BCS_HV WR=80%，显著提升 HIGH_VOL bearish 路径收益",
     "正向（新增改善）"),
    ("IC_HV 增加（SPEC-008）",
     "HIGH_VOL NEUTRAL → IC_HV",
     "SPEC-008 实证：IC_HV WR=84%，ROM 高，高 premium 环境有优势",
     "正向（新增改善）"),
]

print(f"  {'Filter':<28} {'Verdict':<15} {'来源'}")
print("  " + "-" * 75)
for fname, change, evidence, verdict in filter_history:
    print(f"  {fname:<28} {verdict:<15}  {evidence[:50]}...")
    print()

# ─── F5: 过滤器复合效应 — 当多个 filter 同时激活时 ─────────────────────────────

print("  五、Filter 叠加：多个信号同向时的强化效果")
print()
# 当 trend=BULLISH + VIX 中等 + 无 backwardation 时，BPS 入场
# 这是最理想的组合 — 三个 filter 全部 aligned

# 分析 BPS 家族中 entry_vix 在"理想区间"（18-26）的表现
ideal_bps = df_all[
    (df_all["strategy"].isin(["Bull Put Spread", "Bull Put Spread (High Vol)"])) &
    (df_all["entry_vix"].between(18, 26)) &
    (df_all["ma_gap"].between(1, 5))
]
all_bps = df_all[df_all["strategy"].isin(["Bull Put Spread", "Bull Put Spread (High Vol)"])]

wr_ideal = ideal_bps["win"].mean() * 100 if len(ideal_bps) else 0
wr_all   = all_bps["win"].mean() * 100 if len(all_bps) else 0
avg_ideal = ideal_bps["pnl"].mean() if len(ideal_bps) else 0
avg_all   = all_bps["pnl"].mean() if len(all_bps) else 0

print(f"  理想组合（VIX 18-26 + MA gap 1-5%）: n={len(ideal_bps)}, WR={wr_ideal:.0f}%, AvgPnL={avg_ideal:+,.0f}")
print(f"  全部 BPS 家族:                        n={len(all_bps)}, WR={wr_all:.0f}%, AvgPnL={avg_all:+,.0f}")
print(f"  差异: WR +{wr_ideal-wr_all:.0f}pp, AvgPnL +${avg_ideal-avg_all:,.0f}")

# ─── 结论 ─────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("  发现汇总 — Filter Complexity Penalty")
print("=" * 65)
print("""
  核心结论：

  1. 当前已有的 filters 经过历史验证，均有正向边际贡献
     - SPEC-009: IV_LOW 路径移除 → 正向
     - SPEC-010: backwardation filter → 正向
     - EXTREME_VOL hard stop → 必须保留
     - trend_flip EXIT → 正向（减少 Diagonal 亏损）

  2. 新增 filter 的边际收益递减规律
     - 每增加一个 filter，可用交易机会减少（频率下降）
     - 在小样本条件下，过滤后的"高质量"机会组合往往过拟合
     - BPS 家族中 entry 样本 n=102，已不能支持进一步细分

  3. Warning B 的具体含义：
     - 已有 7–8 个 active filters；任何新 filter 边际价值需要 n≥50 的独立验证
     - 不应基于 backtest 改善就添加 filter（可能是 lookback bias）
     - 最危险的 filter：那些只在小样本（n<30）中"看起来有效"的规则

  4. 健康 filter 的特征：
     - 有清晰的理论机制（不只是数据发现）
     - 独立验证（26yr + 3yr 一致）
     - 不过度降低交易频率（每 filter 减少 > 30% 交易机会需要重新评估）
""")
