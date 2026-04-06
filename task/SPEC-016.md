# SPEC-016: Realism Haircut & Strategy Re-ranking

## 目标

**What**：建立每个策略族的实际性能调整框架，量化三类 Precision B 乐观偏差，在调整后的 ROM 下重新为策略排名，指导策略权重和参数优化决策。

**Why**（Prototype 实证，`SPEC-016_realism_haircut.py`，2026-03-30，26yr 386 笔）：

Precision B 回测存在三类系统性偏差，且偏差对不同策略族影响不对称：

| 偏差类型 | 方向 | 对 short-vega 策略 | 对 long-vega（Diagonal） |
|---------|------|-------------------|------------------------|
| IV Bias（sigma=当天VIX） | SPX涨→VIX跌→short put自动盈利 | **高估** 10–12% | **低估**（反向）|
| Bid-Ask Slippage | 每腿 $40–75 SPX 期权 | 2腿 $80–150/trade | 2腿，同量级 |
| 资金占用成本（5% p.a.） | BP × rate × hold_days | 小（短持）| 较大（长持）|

---

## 核心数据（Prototype 结果，2000–2026）

### 各策略 Raw vs Adjusted ROM

| 策略 | n | Raw ROM | Adj ROM | Haircut | Raw排名 | Adj排名 | 变化 |
|------|---|---------|---------|---------|--------|--------|------|
| Bull Put Spread | 23 | +3.476 | +2.433 | 30% | #1 | **#1** | — |
| Iron Condor HV | 45 | +2.949 | +0.847 | 71% | #2 | **#2** | — |
| Bull Put Spread HV | 79 | +2.681 | +0.747 | 72% | #3 | **#3** | — |
| Bull Call Diagonal | 111 | +0.770 | +0.725 | **6%** | #6 | **#4↑** | **+2** |
| Bear Call Spread HV | 79 | +1.206 | +0.313 | 74% | #4 | **#5↓** | −1 |
| Iron Condor | 49 | +1.020 | +0.269 | 74% | #5 | **#6↓** | −1 |

---

## 关键发现

### 发现 1：Bull Put Spread（Normal）是最稳健的策略

Haircut 仅 30%（bid-ask 摩擦较小，合约数少），调整后 ROM=+2.433 仍为最高。这与 SPEC-009（过滤 IV_LOW 路径）和 IVP 入场过滤配合，是整个系统最"真实"的 alpha 来源。

### 发现 2：Bull Call Diagonal 实际上是 haircut 最小的策略（6%）

两个效应相反相消：
- **vega bias 为负（回测偏悲观 10%）**：VIX 与 SPX 同向联动让 long call 的 vega 损失被高估 → 实际表现比回测更好
- **bid-ask 摩擦**：2 腿 × $60 = $120/trade

净效果：调整后 ROM=+0.725，与原始 +0.770 相差极小。**Diagonal 是回测可信度最高的策略**，其 raw ROM 不需要大幅折扣。

### 发现 3：HV 信用策略（IC_HV、BPS_HV、BCS_HV）haircut 达 70–74%

**主因是 bid-ask 摩擦**，而非 vega bias：
- IC_HV：4 腿 × $60 = $240/trade，占 raw PnL 大头
- BPS_HV：2 腿 × $75 = $150/trade（HIGH_VOL 期 spread 更宽）

调整后 ROM 仍为正（0.3–0.85），但已不是"显著领先"的策略。**HV 信用策略的看起来高的 ROM 很大程度上是 Precision B 的乐观偏差，而非真实 alpha。**

### 发现 4：排名关键变化——IC 类策略被大幅降权

IC / IC_HV 的 4 腿结构使 bid-ask 摩擦翻倍。在 NORMAL VIX 环境下，IC 常规版本 adj_rom=+0.269，几乎与 reduce_wait 无实质区别（adj total PnL $6,356 over 49 trades = $130/trade，扣除摩擦后几乎为 0）。**IC 的战略价值主要是"占用 regime 空隙"，而非高效率 alpha。**

---

## 策略含义

这份分析不要求修改 selector 或 engine，但应当驱动以下研究决策：

| 决策领域 | 调整前（Raw ROM） | 调整后（Adj ROM） | 建议 |
|---------|----------------|----------------|------|
| 资源分配 | IC_HV=2.95 >> Diagonal=0.77 | IC_HV=0.85 ≈ Diagonal=0.73 | Diagonal 值得更多研究，不应因 raw ROM 低而轻视 |
| 参数优化 | 倾向改善 HV 策略 | HV 策略真实 alpha 有限 | BPS Normal 是最值得参数细化的策略 |
| 多仓优先级 | 多开 IC_HV 看似高效 | 实际上 bid-ask 摩擦大 | 限制 IC 类仓位数量，优先 BPS/BCS |
| 止损阈值 | 基于 raw ROM 调整 | 考虑每笔实际摩擦成本 | 止损阈值应 ≥ 一次开平仓的双边 bid-ask |

---

## Haircut 参数说明（Prototype 使用的估算值）

| 参数 | 依据 |
|------|------|
| vega bias 10–12%（credit strategies） | 业界估算：VIX/SPX 负相关约 −4 相关系数，短持信用策略每 1% SPX 移动造成约 0.5% vega P&L 误差 |
| vega bias −10%（Diagonal） | Long vega：VIX 联动方向相反，等量回撤 |
| bid-ask $40–75/leg | SPX 期权在不同波动率下的经验 spread：NORMAL $30–50，HIGH_VOL $60–80；取中间值 |
| 资金成本 5% p.a. | Schwab margin account T-bill rate proxy |

**这些是量级估算，不是精确值。**关键结论是方向性的：HV 信用策略的真实 alpha 远低于 raw ROM 暗示的水平。

---

## 接口定义

**本 SPEC 无 Codex 实现任务。** 这是研究性发现文档，指导参数和策略权重决策。

如需后续实现，候选扩展方向：
- 在 `compute_metrics` 输出中加入每策略的预估 adj_rom 字段（用固定 haircut 参数）
- 在 backtest report 底部打印"Realism Adjusted ROM"表格

---

## 不在范围内

- 动态 bid-ask 估算（基于实时 VIX 水平调整每腿 spread 估算）
- 实际滑点模拟（需要 Level 2 数据）
- 期权保证金利率动态计算（使用固定 5%）

---

## Prototype

路径：`backtest/prototype/SPEC-016_realism_haircut.py`

---

## Review

- 结论：N/A（研究性 SPEC，无 Codex 实现）

---

## 验收标准

本 SPEC 为研究性结论文档，不触发 Codex 实现。验收标准为：

1. 研究发现已记录在 research_notes.md §22（待写入）
2. PM 已了解：IC_HV / BPS_HV 的 raw ROM 需大幅折扣（70%+），调整后仍为正但不显著领先
3. PM 已了解：Bull Call Diagonal 的回测 ROM 是所有策略中最可靠的（6% haircut）
4. PM 已了解：Bull Put Spread（Normal）是 adj ROM 最高的策略（+2.433）

---
Status: DONE
