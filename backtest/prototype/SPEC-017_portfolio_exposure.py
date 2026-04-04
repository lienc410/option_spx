"""
SPEC-017 Prototype — Portfolio Exposure Aggregation
对每个策略分类其主导 greek 暴露，分析多仓并行时的集中度风险。

暴露维度：
  short_gamma: 方向性移动损失（期权卖方在价格大幅移动时的凸性损失）
  short_vega:  波动率上升损失（short premium 在 IV 扩张时亏损）
  long_vega:   波动率上升获益（Diagonal long leg 获益）
  delta_bull:  净正 delta（方向性多头偏向）
  delta_bear:  净负 delta（方向性空头偏向）
  theta:       每日 theta 收入方向

分析目标：
1. 所有策略的 greek 签名分类
2. 当前 dedup 规则下，可能同时存在的仓位组合
3. 找出哪些组合实际上是"相同交易"
4. 提出 portfolio-level 暴露 ceiling 规则
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
from backtest.engine import run_backtest
from strategy.selector import StrategyName

# ─── 1. 策略 Greek 签名表 ─────────────────────────────────────────────────────

GREEK_SIGNATURES = {
    # (short_gamma, short_vega, delta_dir, theta_income, notes)
    "Bull Put Spread": {
        "short_gamma": True,    # short put 受价格大跌的非线性损失
        "short_vega":  True,    # IV 上升对 short put 不利
        "delta":       "bull",  # 净正 delta（隐式多头）
        "theta":       "income",# 每日 theta 收入
        "regime":      "NORMAL/HIGH_VOL BULLISH",
        "tail_risk":   "put side: SPX 急跌",
    },
    "Bull Put Spread (High Vol)": {
        "short_gamma": True,
        "short_vega":  True,
        "delta":       "bull",
        "theta":       "income",
        "regime":      "HIGH_VOL BULLISH",
        "tail_risk":   "put side: SPX 急跌，HV 环境尤为危险",
    },
    "Bear Call Spread (High Vol)": {
        "short_gamma": True,
        "short_vega":  True,
        "delta":       "bear",  # 净负 delta（隐式空头）
        "theta":       "income",
        "regime":      "HIGH_VOL BEARISH",
        "tail_risk":   "call side: SPX 急涨反弹",
    },
    "Iron Condor": {
        "short_gamma": True,    # 双边 gamma 暴露，任一方向大移动均损
        "short_vega":  True,
        "delta":       "neut",  # 初始 delta ≈ 0
        "theta":       "income",
        "regime":      "LOW_VOL/NORMAL NEUTRAL",
        "tail_risk":   "任一方向 2σ 以上移动",
    },
    "Iron Condor (High Vol)": {
        "short_gamma": True,
        "short_vega":  True,
        "delta":       "neut",
        "theta":       "income",
        "regime":      "HIGH_VOL NEUTRAL",
        "tail_risk":   "任一方向，HV 环境翼宽更大",
    },
    "Bull Call Diagonal": {
        "short_gamma": False,   # long back-month 抵消大部分 gamma 暴露
        "short_vega":  False,   # 净 LONG vega（long call 90d vega > short call 45d vega）
        "long_vega":   True,
        "delta":       "bull",
        "theta":       "split", # long leg theta 付出 > short leg theta 收入（净付出）
        "regime":      "LOW_VOL BULLISH",
        "tail_risk":   "BEARISH 趋势翻转（已有 trend_flip 规则）",
    },
    "Bear Call Diagonal": {
        "short_gamma": False,
        "short_vega":  False,
        "long_vega":   True,
        "delta":       "bear",
        "theta":       "split",
        "regime":      "LOW_VOL BEARISH（已从 active matrix 移除）",
        "tail_risk":   "BULLISH 翻转",
    },
}

print("=" * 70)
print("  PORTFOLIO EXPOSURE ANALYSIS — Greek Signature & Concentration Risk")
print("=" * 70)

print("\n  一、策略 Greek 签名表")
print(f"  {'策略':<32} {'ShortGamma':>10} {'ShortVega':>10} {'Delta':>8} {'Theta':>8} {'Regime'}")
print("  " + "-" * 90)
for strat, sig in GREEK_SIGNATURES.items():
    sg = "✓" if sig.get("short_gamma") else "—"
    sv = "✓" if sig.get("short_vega")  else "LONG"
    dl = sig.get("delta", "?")
    th = sig.get("theta", "?")
    rg = sig.get("regime", "")
    print(f"  {strat:<32} {sg:>10} {sv:>10} {dl:>8} {th:>8}  {rg}")

# ─── 2. 可能的并发仓位组合分析 ────────────────────────────────────────────────

print("\n\n  二、多仓并行潜在暴露集中度分析")
print()
print("  CASE A — NORMAL regime，多信号依次触发：")
case_a = ["Bull Put Spread", "Iron Condor"]
print("  仓位: " + " + ".join(case_a))
for s in case_a:
    sig = GREEK_SIGNATURES[s]
    print(f"    {s}: short_gamma={'YES' if sig.get('short_gamma') else 'no'}, "
          f"short_vega={'YES' if sig.get('short_vega') else 'no'}, delta={sig['delta']}")
print("  ▶ 合并暴露: DOUBLE short_gamma + DOUBLE short_vega + net delta≈BULL")
print("  ▶ 等效于: 宽度更大的 Iron Condor，但 put 侧偏斜（bull bias）")
print("  ▶ 单一 SPX 急跌 5% 可同时击穿两个仓位的 put 侧")

print()
print("  CASE B — HIGH_VOL regime，BPS_HV + BCS_HV 同时开仓（dedup 允许）：")
case_b = ["Bull Put Spread (High Vol)", "Bear Call Spread (High Vol)"]
print("  仓位: " + " + ".join(case_b))
for s in case_b:
    sig = GREEK_SIGNATURES[s]
    print(f"    {s}: short_gamma={'YES' if sig.get('short_gamma') else 'no'}, "
          f"delta={sig['delta']}")
print("  ▶ 合并暴露: BPS(bull-delta) + BCS(bear-delta) = delta≈0（合成 IC）")
print("  ▶ 但两者 short_gamma + short_vega 叠加，比单个 IC 风险高")
print("  ▶ 实际上这两个策略当前由 dedup 阻止（不同 StrategyName，但同 regime 决策）")
print("  ▶ 注意: SPEC-014 dedup 只阻止完全相同的 StrategyName，BPS_HV+BCS_HV 可能同时存在")

print()
print("  CASE C — LOW_VOL + NORMAL 跨 regime 仓位叠加：")
case_c = ["Bull Call Diagonal", "Bull Put Spread"]
print("  仓位: " + " + ".join(case_c))
print("  ▶ Diagonal: long_vega + bull delta")
print("  ▶ BPS: short_vega + bull delta")
print("  ▶ 合并: vega 部分对冲（long + short），delta 叠加（double bull）")
print("  ▶ 这是最安全的组合——vega 暴露部分对冲")
print("  ▶ 但 delta 集中度上升（double bull），SPX 急跌时双重受损")

# ─── 3. 聚合 short_gamma 天数分析 ─────────────────────────────────────────────

print("\n\n  三、历史多仓期间的并发 short_gamma 暴露")
print("  （利用 SPEC-014 多仓后 26yr 回测数据）")
print()
print("  加载 26yr 回测数据...")
trades, metrics, _ = run_backtest(start_date="2000-01-01", verbose=False)

# 模拟每日持仓状态
from datetime import datetime, timedelta
import pandas as pd

# 构建每日仓位列表
position_events = []
for t in trades:
    position_events.append({"date": t.entry_date, "action": "open",  "strat": t.strategy.value})
    position_events.append({"date": t.exit_date,  "action": "close", "strat": t.strategy.value})

# 检查哪些日期有多个 short_gamma 仓位并发
SHORT_GAMMA_STRATS = {s for s, sig in GREEK_SIGNATURES.items() if sig.get("short_gamma")}

# 分析同期开仓的情况
concurrent_pairs = []
for i, t1 in enumerate(trades):
    for t2 in trades[i+1:]:
        # 检查是否有重叠持仓期
        if t1.entry_date <= t2.exit_date and t2.entry_date <= t1.exit_date:
            both_sg = (t1.strategy.value in SHORT_GAMMA_STRATS and
                       t2.strategy.value in SHORT_GAMMA_STRATS)
            if both_sg and t1.strategy != t2.strategy:
                concurrent_pairs.append({
                    "strat1": t1.strategy.value,
                    "strat2": t2.strategy.value,
                    "pnl1":   t1.exit_pnl,
                    "pnl2":   t2.exit_pnl,
                    "combined_pnl": t1.exit_pnl + t2.exit_pnl,
                })

if concurrent_pairs:
    cp_df = pd.DataFrame(concurrent_pairs)
    print(f"  发现 {len(cp_df)} 对并发 short_gamma 仓位组合:")
    combo_stats = cp_df.groupby(["strat1", "strat2"]).agg(
        n=("combined_pnl", "count"),
        avg_combined_pnl=("combined_pnl", "mean"),
        both_loss_pct=("combined_pnl", lambda x: (x < 0).mean() * 100),
    ).reset_index()
    for _, row in combo_stats.iterrows():
        print(f"    {row['strat1'][:25]} + {row['strat2'][:25]}")
        print(f"      n={int(row['n'])}  avg_combined=${row['avg_combined_pnl']:+.0f}  "
              f"both_loss={row['both_loss_pct']:.0f}%")
else:
    print("  暂无并发 short_gamma 对（可能因为回测日期范围内未触发多仓）")

# ─── 4. 建议的 exposure ceiling ────────────────────────────────────────────────

print("\n\n  四、Portfolio Exposure Ceiling 建议规则")
print()
print("  规则 1 — Short Gamma Count Limit:")
print("    同时持有 short_gamma 仓位最多 2 个")
print("    → 超过 2 个时，第 3 个 short_gamma 策略推荐 → REDUCE_WAIT")
print()
print("  规则 2 — Delta 集中度限制:")
print("    同向 delta 仓位（bull+bull 或 bear+bear）最多 2 个")
print("    → 防止 double-bull 在 SPX 急跌时双重受损")
print()
print("  规则 3 — Vega 中性优先:")
print("    若当前 positions 中已有 short_vega × 2，")
print("    优先推荐 long_vega 策略（Diagonal）以降低净 vega 暴露")
print("    → 当前 selector 已自然实现部分（regime 不同时推荐不同策略）")
print()
print("  规则 4 — BPS_HV + BCS_HV 合并为 IC_HV（等效合并）:")
print("    若 BPS_HV 已在 positions 中，且新信号为 BCS_HV，")
print("    则视为合成 IC_HV，不允许重复开仓（类 dedup 规则扩展）")
print("    → 防止合成出比 IC_HV 更大的 short_gamma 暴露")
print()
print("  注意: 规则 1 已部分由 SPEC-014 的 dedup + bp_ceiling 覆盖")
print("  规则 4 是当前架构的盲区，需要 Greek-signature-aware dedup")
