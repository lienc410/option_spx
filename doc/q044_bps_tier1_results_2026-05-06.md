# Q044 Tier 1 Results — BPS Sizing and Account-Level ROE

Date: 2026-05-06
Role: Quant Researcher
Window: 2023-01-01 → 2026-05-06
Account: $150,000 (backtest baseline)
Script: backtest/prototype/q044_bps_sizing_tier1.py

---

## 一句话结论

**A1（bp_target 15%）是值得进入 Tier 2 的方向**：近线性扩展，marginal 衰减 -0.3%，BPS AnnROE 从 3.0% 升至 4.6%，无结构性破坏。A2（20%）触发 BP ceiling cliff，不可行。Axis B（加宽 spread）单调劣化，方向关闭。

---

## Axis A — bp_target 变体（保持 δ0.30/0.15 结构）

| 变体 | N | WR% | BPS PnL | AnnROE% | AvgBP% | AvgWidth | $/BP-day | Worst | CVaR5% |
|---|---|---|---|---|---|---|---|---|---|
| A0 baseline bp=10% | 15 | 73.3 | $15,252 | 3.042% | 10.0% | 182.7pt | 0.00782 | -$6,253 | -$4,076 |
| A1 medium bp=15% | 15 | 73.3 | $22,823 | 4.552% | 15.0% | 182.6pt | 0.00780 | -$9,380 | -$6,633 |
| A2 large bp=20% | 9 | 55.6 | -$2,470 | -0.493% | 20.0% | 183.4pt | -0.00102 | -$12,506 | -$10,671 |

**A1 — 近线性扩展（recommended）：**
- Marginal $/BP-day 衰减仅 -0.3%（从 0.00782 → 0.00780）
- BPS PnL：+$7,571（+50%），AnnROE +1.5pp
- 最差单笔亏损按比例放大（-$6,253 → -$9,380，同比例）
- CVaR5% 按比例放大（-$4,076 → -$6,633，同比例）
- 结论：扩展是干净的线性，无结构性劣化

**A2 — BP ceiling cliff（不可行）：**
- N 从 15 跌至 9：当 IC / Diagonal 等同时开仓时，20% BPS + 其余仓位超过 `bp_ceiling_normal = 35%`，6 笔 BPS 被封堵
- 被封堵的恰好是有利环境下的 6 笔；剩余 9 笔在不利条件下，总 PnL 转负
- 结论：20% 不是"同样结构更大"——它改变了哪些环境能进场，产生了选择偏误（adverse selection）

---

## Axis B — spread width 变体（保持 bp_target = 10%）

| 变体 | N | WR% | BPS PnL | AnnROE% | AvgWidth | $/BP-day | Worst |
|---|---|---|---|---|---|---|---|
| B0 baseline δ0.30/0.15 | 15 | 73.3 | $15,252 | 3.042% | 182.7pt | 0.00782 | -$6,253 |
| B1 moderate δ0.25/0.125 | 15 | 80.0 | $13,132 | 2.619% | 168.5pt | 0.00673 | -$5,837 |
| B2 wide δ0.20/0.10 | 15 | 80.0 | $9,526 | 1.900% | 154.6pt | 0.00492 | -$6,565 |

**Axis B 方向关闭：**
- 胜率从 73% 升至 80%（更 OTM 的 short put 更难被击穿）
- 但 $/BP-day 单调下降：-14%（B1）、-37%（B2）
- 机制：更宽的 spread = short put 更偏 OTM → 每 BP-dollar 收取的权利金更少
- 同一 bp_target 下合约数减少（因每合约 BP 更大），绝对 PnL 也减少
- 结论：加宽 spread 不是提升 BPS ROE 的路径。当前 δ0.30/0.15 结构是最优

---

## A2 Cliff 机制分析

当 bp_target = 20% 时，同时有 IC（10%）+ Diagonal（debit，不占 short-gamma ceiling）等持仓时：
- 已用 BP ~10%（IC）+ 20%（BPS）= 30%，仍在 bp_ceiling 35% 内
- 但若有 2 个 short-gamma 持仓（IC + BPS），加上 Diagonal，ceiling 可能被触达

更重要的 adverse selection 效应：
- 在 IC 已开的 HIGH_VOL 余震期，BPS 无法入场（regime 不对）
- 在 NORMAL 且 BULLISH 环境下，若同时有其他仓位导致 ceiling 达到，BPS 被跳过
- 被跳过的这 6 笔恰好是 NORMAL+BULLISH 最干净的环境，missing 掉了 profitable setups

---

## Tier 2 候选方向

**主线：A1（bp_target 15%）验证包：**
1. 逐年 attribution（确认非单年驱动，特别是 2024/2025）
2. A2 cliff 分析：哪些条件触发 ceiling 封堵？能否通过调整 bp_ceiling_normal（35%→40%）缓解？
3. Q036 Overlay-F active 共存分析：BPS 15% + IC_HV aftermath + Overlay-F 2x → 合计是否超 ceiling？
4. live PM 账户实际 Schwab BP consumed 核对（PM 账户下垂直价差的保证金 < max risk）

**关闭：**
- Axis B（所有 spread-width 变体）：结论已明确，单调劣化，不再研究
- A2（20%）：ceiling adverse selection 问题，除非同时研究 ceiling 调整，否则不进 Spec

---

## 对 Q036 依赖的修正结论

Tier 1 结果显示：
- **A1 与 Q036 的 BP 竞争是 regime-separated**：A1 大 BPS 在 NORMAL 环境；Q036 在 IC_HV aftermath。两者同时开仓时合计 BP 约 15%（BPS）+ 20%（IC_HV×2）= 35%，恰在 HIGH_VOL ceiling（50%）以内。
- **无需等 Q036 active 决策**即可进行 A1 Tier 2
- Q036 active 结果只影响 Tier 2 的 ceiling 分析数字，不影响 A1 的基本方向

---

## 数据说明

- 所有变体共用相同 market data（Yahoo Finance fetch_vix_history / fetch_spx_history）
- 策略 trigger 逻辑不变（NORMAL + BULLISH + IVP gate）
- N=15 是 3 年窗口内 NORMAL+BULLISH BPS 实际触发次数，符合低频策略特征
- CVaR5% 是**账户级全策略**最差 5% 平均，不仅限于 BPS
