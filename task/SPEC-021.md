# SPEC-021: Filter Complexity Penalty Protocol

## 目标

**What**：建立 filter 边际价值评估框架，防止系统因过度添加 filter 导致样本枯竭和过拟合，落实 Warning B："不要假设更多 filter 总能改善结果"。

**Why**（Prototype 实证，`SPEC-021_filter_complexity.py`，2026-03-30，26yr 386 笔）：

---

## 核心数据（Prototype 结果）

### 关键实证：Filter 叠加没有改善 BPS 性能

| 配置 | n | WR | AvgPnL |
|------|---|-----|--------|
| 全部 BPS 家族（无额外 filter） | 102 | **78%** | **$+373** |
| 理想组合（VIX 18–26 + MA gap 1–5%）| 46 | 76% | $+346 |

**叠加两个额外 filter 反而使 WR 略降（−2pp）且 AvgPnL 略降（−$27）**。这正是 Warning B 的直接实证：进一步收紧 entry 条件并未提升质量，只是减少了数量。

### 各 Filter 边际贡献历史（SPEC 研究归纳）

| Filter | 类型 | 结论 | 来源 |
|--------|------|------|------|
| EXTREME_VOL hard stop（VIX≥35） | 硬性边界 | ✅ 必须保留 | COVID 2020 极端亏损防护 |
| VIX backwardation（SPEC-010） | 入场过滤 | ✅ 正向保留 | backwardation 时 BPS 高亏损率 |
| trend_flip EXIT（Diagonal） | 出场触发 | ✅ 正向保留 | 32/41 Diagonal 亏损由此捕获 |
| IV_LOW 路径移除（SPEC-009） | 路径删除 | ✅ 移除后改善 | IV_LOW + BULLISH WR <50%，删除提升 Sharpe |
| BCS_HV 增加（SPEC-006） | 路径新增 | ✅ 新增改善 | HIGH_VOL BEARISH WR=80% |
| IC_HV 增加（SPEC-008） | 路径新增 | ✅ 新增改善 | HIGH_VOL NEUTRAL WR=84% |
| **理想条件组合（VIX+MA gap）** | **复合过滤** | **❌ 无改善** | **见上表** |

### BPS VIX 分层（entry VIX vs WR）

| VIX 区间 | n | WR | AvgPnL |
|---------|---|-----|--------|
| < 18 | 14 | 71% | $+554 |
| 18–22 | 9 | 78% | $+781 |
| 22–26 | 54 | 76% | $+246 |
| 26–30 | 16 | 81% | $+298 |
| > 30 | 9 | **100%** | $+579 |

注：VIX > 30 时 WR=100%（n=9，样本太小，不可靠），但方向不差。VIX 高时 premium 更厚，能吸收更多波动。

---

## 关键发现

### 发现 1：Filter 叠加的边际效果递减（甚至负值）

以 BPS 为例：当前 selector 已要求 trend=BULLISH + IV signal（排除 IV_LOW）。在这基础上再加 "VIX 18–26 + MA gap 1–5%"，表现并未改善（WR −2pp，AvgPnL −$27）。

**原因**：
1. **样本缩减效应**：从 102 笔缩至 46 笔，统计噪声增大
2. **优质机会被过滤**：VIX>26 时 WR 仍达 81–100%，但被"更优"filter 排除
3. **过拟合风险**：在同一份数据上寻找最优 filter 参数组合，必然导致 in-sample 优化

### 发现 2：当前 Active Filters 数量已达合理上限

盘点现有系统中的 active filter 层：
1. VIX regime 分类（4 层：LOW/NORMAL/HIGH/EXTREME）
2. IV signal（HIGH/NEUTRAL/LOW）
3. Trend signal（BULLISH/NEUTRAL/BEARISH）
4. VIX backwardation（spot VIX > VIX3M）
5. EXTREME_VOL hard stop（VIX ≥ 35）
6. trend_flip EXIT（Diagonal 专属）
7. Vol spell age throttle（SPEC-015，待实现）

共 7 层。对于年均 15 笔的交易频率，已有 filter 足以区分好坏机会。进一步细分会使每个 bucket 的样本量降至 < 10，不具统计意义。

### 发现 3：有理论机制的 filter 优于纯数据发现的 filter

历史上有效的 filter 都有清晰的经济机制：
- backwardation：市场恐慌下短期 vol 扭曲，short put 尤其危险
- EXTREME_VOL：期权定价失真，short premium 策略整体不适用
- trend_flip EXIT：Diagonal 的 bull premise 已破坏

没有清晰机制的 filter（如"VIX 恰好 18–26"）容易过拟合。

---

## Filter 复杂度管理协议（本 SPEC 的核心输出）

### Protocol 1 — 新 Filter 最低门槛

| 要求 | 标准 |
|------|------|
| 样本量 | 过滤后 n ≥ 50（至少 50 笔"被过滤掉"的交易用于对比） |
| 一致性 | 26yr 和 3yr 窗口方向一致 |
| 机制 | 有明确的期权/市场结构理论依据 |
| 频率影响 | 不减少年均交易频率 > 30% |

### Protocol 2 — 任何新 Filter 前必须完成 Ablation Study

在添加 filter F_new 之前，必须运行：
1. `Baseline`: 当前 engine，无 F_new
2. `With F_new`: 在 baseline 基础上加 F_new（不改变其他 filter）
3. 比较：Sharpe、WR、TotalPnL、MaxDD、年均交易笔数
4. 如果 F_new 提升小于 5% Sharpe 且年交易量减少 > 20%：拒绝

### Protocol 3 — Filter 清理标准

以下情况可以考虑移除某个 filter：
- 历史数据中"被过滤掉"的交易事后 WR > 70%（filter 过于保守）
- 该 filter 对总 PnL 贡献 < 2%（边际无效）
- 理论机制已被更新（e.g. market structure change）

### Protocol 4 — 禁止在同一数据上多次优化

若已经在 26yr 数据上优化了 filter F1，则 F2 的测试必须在独立的 out-of-sample 窗口上。建议：
- 用 2000–2020 数据做 filter 设计（in-sample）
- 用 2021–2026 数据验证（out-of-sample）

---

## 不在范围内

- 自动 filter 优化（grid search）
- 机器学习 entry 过滤
- 实时 filter 参数调整

---

## Prototype

路径：`backtest/prototype/SPEC-021_filter_complexity.py`

关键数字：
- BPS 理想 filter 叠加：WR 76% < 基准 78%（filter 叠加无帮助）
- VIX>30 的 BPS: WR=100%（但 n=9，不可靠）
- 当前 active filter 层：7 层

---

## Review

- 结论：N/A（研究+协议性 SPEC，无 Codex 实现）

---

## 验收标准

1. PM 了解：filter 叠加没有改善 BPS 性能（WR −2pp）
2. PM 了解：当前 7 层 filter 已达合理复杂度上限
3. PM 了解并同意 Protocol 1–4 作为未来 filter 评估标准
4. 新 filter 提案必须通过 Protocol 1 的 n≥50 门槛

---
Status: DRAFT
