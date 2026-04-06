# SPEC-019: Trend Signal × Strategy Family Effectiveness — Lag & Gate Analysis

## 目标

**What**：评估 50MA 趋势信号在各策略族中的实际预测价值，量化以下问题：
1. 趋势确认（lagging confirmation）对哪些策略族有帮助、对哪些策略族作用有限？
2. 50MA gap 量级（信号强度）是否与 PnL 单调正相关？
3. MA50 的滞后性代价是否显著（vs MA20）？
4. 趋势信号作为 ENTRY gate 和 EXIT trigger 哪个更有价值？

**Why**（Prototype 实证，`SPEC-019_trend_signal_effectiveness.py`，2026-03-30，26yr 386 笔）：

2nd Quant Review 指出"不要把系统重新框架为方向性趋势跟随引擎"——本 SPEC 量化趋势信号的实际贡献边界。

---

## 核心数据（Prototype 结果，2000–2026）

### 入场时趋势信号分布

| Signal | 笔数 | 占比 |
|--------|------|------|
| BULLISH | 213 | 55.2% |
| NEUTRAL | 87 | 22.5% |
| BEARISH | 86 | 22.3% |

**关键发现：所有 386 笔交易均为 100% aligned**。现有 selector 已将趋势信号作为硬性过滤器（hard gate），无任何反趋势入场。

### IC / IC_HV 按趋势信号分层

| 策略 | Entry Trend | n | WR | AvgPnL |
|------|------------|---|-----|--------|
| Iron Condor | NEUTRAL | 42 | 81% | $+390 |
| Iron Condor | BEARISH | 7 | **100%** | **$+1,099** |
| Iron Condor (High Vol) | NEUTRAL | 45 | 84% | $+543 |

### BPS 家族 MA Gap 量级 vs 性能

| MA50 Gap 区间 | n | WR | AvgPnL |
|--------------|---|-----|--------|
| 1–3% | 44 | 75% | $+440 |
| 3–6% | 39 | **87%** | $+402 |
| ≥6% (过度延伸) | 19 | **68%** | **$+158** |

### Bull Call Diagonal 损失解剖

| Entry Trend | n | WR | AvgPnL | 主要亏损原因 |
|------------|---|-----|--------|------------|
| BULLISH | 111 | 63% | $+816 | trend_flip ×32（78% of losses）, roll_21dte ×9 |

### MA20 vs MA50 滞后性

| 指标 | 值 |
|------|---|
| MA20 先于 MA50 看多的天数 | 6.3% 的交易日（1,545天/24,627天） |
| MA50 翻多时 MA20 已领先天数（均值） | 1.2 天 |
| MA50 翻多时 MA20 已领先天数（中位数） | 0 天 |
| P90 领先天数 | 5 天 |

---

## 关键发现

### 发现 1：趋势信号是当前系统的纯 Hard Gate，没有反趋势数据可对比

所有 386 笔交易的 alignment 均为 "aligned" 或 "neutral_strat"（IC类）。这证明 selector 已强制执行方向一致性。这**既是优点也是研究障碍**：由于没有反趋势基准数据，无法通过当前回测量化"如果去掉趋势过滤器，绩效会变化多少"。

### 发现 2：MA50 Gap 过度延伸（>6%）时，BPS 系列性能下降

BPS/BPS_HV 在 MA50 gap 1–3% 时 WR=75%，3–6% 时 WR=87%（最高），但在 ≥6% 时 WR 骤降至 68%，AvgPnL 也最低（$158）。

**解释**：当 SPX 已经远高于 50MA（>6%），市场处于过热状态：
- 短期均值回归压力增加，BPS 的 bull put 位置更易被回调击中
- 这类入场通常在强势上升趋势末段，而非初期

**建议**：在 MA gap > 5–6% 时对 BPS 系列降低置信度（但这需要 Prototype 2 验证，反事实数据不足）。

### 发现 3：IC 在 BEARISH 趋势下反而表现更好（n=7，WR=100%，$1,099）

传统直觉认为 IC 应该在 NEUTRAL 趋势时交易。但 7 笔 BEARISH 趋势下的 IC 入场（均为 NORMAL regime）全部盈利，均值是 NEUTRAL 趋势 IC 的 2.8 倍。

**谨慎解读**：n=7 样本量太小，不足以得出统计结论。但方向性提示：在 NORMAL regime 中，当 SPX 略低于 50MA（BEARISH）时，IC 可能是有利的——因为 IC 的 put side 可以开在更远 OTM 的位置（市场已经回调了一些）。不建议仅凭此数据修改 selector。

### 发现 4：趋势信号作为 EXIT trigger 价值远大于 ENTRY gate

Bull Call Diagonal 的 41 笔亏损中，**32 笔（78%）由 trend_flip EXIT 规则捕获**（BEARISH 翻转触发平仓），仅 9 笔是到期时 roll_21dte。这说明：

- 趋势信号在 Diagonal 中的核心价值是**持仓期间的保护机制**，而非入场过滤
- 如果没有 trend_flip EXIT 规则，Diagonal 的亏损将以"慢慢到期归零"的方式放大
- ENTRY gate（只在 BULLISH 入场）是必要前提，但 EXIT trigger 是主要的价值来源

这是对信号二元角色（入场 vs 出场）最重要的实证结论。

### 发现 5：MA50 vs MA20 的滞后性差异可忽略不计

MA50 翻多时 MA20 平均领先仅 1.2 天（中位数 0 天）。**MA50 在实践中并不比 MA20 显著滞后**。这意味着：
- 换用 MA20 作为趋势确认不会显著改善信号时效性
- 50MA 的"滞后"问题是理论上的，对于短周期信号迁移意义不大
- 当前 MA50 + 1% 阈值选择合理

---

## 策略含义

| 发现 | 现有设计 | 建议 |
|------|---------|------|
| Hard gate 已强制对齐 | ✓ 已实现 | 保持，不需变更 |
| ≥6% gap BPS 性能退化 | ❌ 无 cap | 可选：加 MA gap cap（>5.5% 时 BPS 降频）|
| IC 在 BEARISH 可入场 | ❌ 目前不允许（BEARISH→REDUCE_WAIT in NORMAL） | 样本太小，暂不修改 |
| Diagonal EXIT trigger 是主要价值 | ✓ trend_flip 规则已实现 | 保持，不要删除 |
| MA50 vs MA20 滞后相同 | ✓ MA50 足够 | 不需切换 |

---

## 建议的后续研究（不在本 SPEC 范围）

1. **MA gap cap 验证**：限制 MA gap > 5% 时不开新 BPS/BPS_HV，验证 Sharpe 变化
2. **IC 在 BEARISH NORMAL 的可行性**：扩大样本（模拟多起点，如 5yr、10yr、15yr 窗口）
3. **IC_HV 无 BULLISH 数据**：HIGH_VOL regime 中 BCS_HV 负责 BEARISH，但 HIGH_VOL + BULLISH 的 IC_HV 是否合理？（当前全部是 NEUTRAL 趋势入场）

---

## 不在范围内

- 添加新的趋势信号模型（RSI、ADX、Keltner channel）
- 修改现有 selector 矩阵（样本量不足以支持变更）
- 动态 MA 周期优化
- 反趋势 Diagonal 策略

---

## Prototype

路径：`backtest/prototype/SPEC-019_trend_signal_effectiveness.py`

关键数据摘要：
- 所有方向性策略 100% aligned（n=0 counter-trend 基准），无法做 A/B 对比
- IC BEARISH: n=7, WR=100%（样本太小）
- BPS ≥6% gap: WR=68%, AvgPnL=+$158（最弱分桶）
- Diagonal 亏损 78% 由 trend_flip EXIT 触发

---

## Review

- 结论：N/A（研究性 SPEC，无 Codex 实现）

---

## 验收标准

本 SPEC 为研究性结论文档：

1. 发现 1–5 已记录，PM 了解趋势信号在不同策略族的不同作用
2. PM 了解：MA gap >6% 是 BPS 系列的潜在风险区间（但样本不足以修改）
3. PM 了解：Diagonal 中 trend_flip EXIT 是趋势信号最重要的贡献（高于 ENTRY gate）
4. PM 了解：MA50 vs MA20 滞后性无实质差异（1.2 天均值领先）

---
Status: DONE
