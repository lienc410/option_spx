# Q081 Framing — 2nd Quant Reviewer Input

**Date received**: 2026-05-29
**Forwarded by**: PM
**Author**: 2nd Quant Reviewer
**Trigger**: PM 询问"低 VIX 下 BCD vs BPS 资源效率"后，2nd quant 独立做了 framing 并把意见备忘转给 1st quant

> 注：这是 2nd quant 在我（1st quant）出 framing 前的 **pre-framing analysis**（不是 review of artifact），但具备 review 的功能——它形塑了 Q081 的 phase 结构。1st quant 的 Q081 framing memo (`research/q081/q081_framing_memo_2026-05-29.md`) 是对这份意见的结构化响应。

---

## 备忘内容（原文转载，含 2nd quant 自标 sourcing）

# 研究请求 / 意见备忘 — 低 VIX 下 BCD vs BPS 的资源效率，及策略矩阵潜在修改

**From**: PM（经第二方分析）
**To**: Quant Researcher
**主题**: 低 VIX regime 下 debit 策略（BCD）的现金机会成本未被现有治理层捕捉，请求量化验证 + 评估策略矩阵是否需改
**优先级**: 中（非紧急，但触及 SPEC-104 sleeve 治理的一个潜在结构缺口）

## 1. 核心命题（请先审框架对不对）

账户的**约束画像**是关键前提，请先用真实数据确认下面这条，整个分析的方向取决于它：

> **账户当前 cash-bound，不是 BP-bound**：现金紧、风险型 buying power 有余；闲置现金已在 QQQ/SGOV 做现金管理（即现金有正在发生的、非假设性的机会成本，hurdle ≈ SGOV 4.8% ~ QQQ 10–12%）。

如果数据证实这条，则核心命题是：

> 低 VIX / 低 IVP 时，selector 把路由推向 **BCD（debit，占用稀缺的现金、几乎不占富余的 BP）**，同时跳过 **BPS（credit，占用富余的 BP、几乎不占稀缺的现金）**。**从资源配置看这是反向的**——在消耗瓶颈资源、闲置富余资源。现有 SPEC-104 sleeve cap 按 *BP 占用* 设限，可能完全没有约束到 BCD 的真正瓶颈（现金），导致 debit 仓可以在 BP 充裕时堆积、吃光本应进 QQQ 的现金。

**请验证/反驳的第一件事**：账户是否真 cash-bound？取一段低 VIX 历史窗口，看 BCD 在场时的现金占用 vs 当时账户可用现金 vs 同期 BP 利用率。如果 BCD 在场期间现金利用率高而 BP 利用率低，命题成立。

## 2. 需要量化的对比（单位现金视角为主）

PM 明确要看 **ROE on cash**，不是 ROE on margin。在低 VIX（建议 VIX<15 或等价 IVP<40 子样本）下，对三个竞争同一块现金的去向做对比：

| 标的 | 占现金 | 占 BP | 待测指标 |
|---|---|---|---|
| **BCD** | 高（debit） | 低 | cash-ROE 的**均值、中位、p05、左尾（debit 归零频率）** |
| **BPS（低 IVP）** | ~0 | 高 | 确认 ROE-on-BP 在低 IVP 下确实差（基线，预期它差） |
| **现金 → QQQ/SGOV** | 全部 | 0 | 同期 QQQ/SGOV 实际回报，作为 BCD 的 **hurdle rate** |

**关键方法学要求（这条最重要）**：BCD vs QQQ 的比较**必须扣掉 BCD 的左尾后再比，不能只比均值**。低 VIX BCD 的卖点是"便宜的 long vol + 上行参与"，但 debit 可归零、路径依赖（SPX 上行但近月被击穿一样亏）。如果只比均值，几乎肯定显示 BCD 跑赢；扣掉左尾后是否还跑赢 QQQ，才是决策依据。

提醒：这正好命中我们那个 **0.5pp 噪声阈值框架的软肋**——这里比的不是两个 short-premium 变体之间的小差异，而是一个 debit 策略 vs 一个 beta 基准，方差结构完全不同，0.5pp 阈值在这里大概率不适用，请用左尾分位（p05/p01）而非均值差做门槛。

## 3. PM 的两个直觉，请分别裁决

**直觉 A（PM 认为对）**：BCD 占的现金本可放 QQQ，这是真机会成本。
→ 我的看法：在 cash-bound 前提下成立。请用数据确认前提，并量化 hurdle。

**直觉 B（PM 倾向，但我已劝阻，请独立复核）**：既然 BPS 不占现金、且 BP 有余，是否该"低 VIX 也开 BPS"？
→ 我的看法：**不应该**。selector 跳过低 IVP BPS 的原始理由（credit 薄、风报比差、ROE-on-BP 仅 ~6%/yr 量级）不变。富余的 BP 不是开烂仓的理由——为了"用掉 BP"而开 ROE 差的仓违背"不为卖而卖"。**请独立验证这条**：低 IVP 下 BPS 的 ROE-on-BP 是否真的差到不值得开，即使 BP 是免费的。如果数据显示某些低 IVP 子区间 BPS 其实还行，我这条劝阻就要收回。

## 4. 真正的结论候选（待数据裁决）

我推测数据会指向下面两条之一或都成立，请验证：

**结论候选 1 — 加 debit-策略现金预算 cap（最可能、低风险）**：
现有 SPEC-104 按 BP 设 sleeve cap，但 BCD 的真瓶颈是现金。建议在 sleeve 层之上给所有 debit 仓加一个独立的 `cash_budget_pct ≤ X% NLV` 上限，强制 debit 仓与 QQQ 现金管理显式竞争同一预算。请评估：(a) 这个 cap 是否填补了真实治理缺口（即历史上是否出现过 BCD 现金占用挤掉 QQQ 配置的情形）；(b) X 的合理量级。

**结论候选 2 — 给 BCD 加 cash-hurdle gate（中等改动）**：
低 VIX 路由到 BCD 前，要求建仓预期 cash-ROE（保守、扣左尾估计）> QQQ 滚动 hurdle，否则降级为"现金留 QQQ / 缩减开仓"。本质是把"什么都不做、现金留 QQQ"变成 selector 的**一等竞争选项**——目前 selector 可能没有显式建模这个 outside option。请评估这个 gate 是否会过度抑制 BCD（即历史上大部分低 VIX BCD 是否本就跑不赢 QQQ）。

**明确不建议**：把"低 VIX 也开 BPS"加进矩阵（见 §3 直觉 B）。

## 5. 决策门槛建议（供你设定，非强制）

- 若 BCD 扣左尾后的 cash-ROE **不显著高于** QQQ hurdle（用 p05 而非均值判）→ 倾向结论候选 2（gate），低 VIX 默认现金留 QQQ。
- 若 BCD 扣左尾后**显著跑赢** QQQ，但历史上出现过现金挤占 → 仅需结论候选 1（cap），不必加 gate。
- 若账户其实并非 cash-bound（§1 前提被推翻）→ **整个请求作废**，BCD 占现金不是真成本，维持现状。请把这个作为一个真实的可能 verdict，不要为了得出修改建议而强行成立前提。

## 6. 我没有的数据 / 你需要补的

- 账户历史现金利用率 vs BP 利用率时间序列（验证 §1 前提）
- 低 VIX 子样本下实际开过的 BCD 的真实 debit、持有路径、了结 PnL
- 同期 QQQ/SGOV 回报（hurdle）
- 低 IVP 下 BPS 的 ROE-on-BP 实测分布（验证 §3 直觉 B）

我这边所有数字（BCD cash-ROE 20–35%、BPS ROE-on-BP ~6%）都是**量级估计、无回测支撑**，仅用于框定问题，请一律用真实信号缓存替换，不要继承我的假设值。

---

## 1st quant 对此份意见的处置

1. 框架结构 fully accepted（见 `research/q081/q081_framing_memo_2026-05-29.md`）
2. 2nd quant 的 §1 cash-bound 前提**未经 PM 显式声明**，仅 reviewer conjecture；P0 必须用真实账户数据验证，可推翻
3. 2nd quant 的"PM 直觉 A/B"是 reviewer 转述，1st quant 不预先采信，P4 独立验证
4. 2nd quant 自报数字（BCD 20-35% / BPS 6%）按其要求**全部替换为实测**，不继承
5. G-review 1 + G-review 2 默认请这位 2nd quant 接（连续性 + 已 framing-in），待 PM 确认
