# Q036 — Idle BP Deployment / Capital Allocation: Framing + Phase 1 Feasibility

- 日期：2026-04-26
- Author: Quant Researcher
- 上游：`task/IDLE_BP_OVERLAY_RESEARCH_NOTE.md`（2nd Quant 提出的 framing）、PM 顶层 objective reset 2026-04-26
- 上游研究：`doc/q021_phase4_sizing_curve_2026-04-26.md`（rule-layer evidence base）
- Prototype: `backtest/prototype/q036_phase1_idle_bp_baseline.py`
- 标准指标包永久规则: `~/.claude/projects/.../memory/feedback_strategy_metrics_pack.md`

---

## TL;DR

1. **Q036 是 capital-allocation layer 问题，不是 Q021 的延长**。Q021 已答 rule-layer：`V_A SPEC-066` 是 canonical rule，`V_D / V_E / V_J / V_G` 都不晋升为新 rule。Q036 问的是另一件事：在 baseline V_A 留下大量 idle BP 的前提下，是否应通过受控 overlay 部署一部分 idle BP 以提高账户级 ROE。两层 objective function 不同，**不能混**。

2. **Phase 1 直接测量结论：idle BP 极度持久，结构性平均 ~91% idle，max BP used 30%（26 年内未触顶）**。aftermath 窗口的 idle BP 与非 aftermath 几乎相等（90.7% vs 91.4%）。**deploy 容量在所有 aftermath 日 100% 满足 ≥70% 阈值**。

3. **新的关键约束发现**：47%（full）/ 54%（recent）的 aftermath 日，账户已经携带 ≥2 个 short-gamma 仓位。**overlay 在大多数 aftermath 日不会"分散"风险，而是"堆叠"** — 这是 Phase 2 必须严格用 no-overlap / disaster-cap 变体处理的核心 guardrail。

4. **Feasibility 决策**：**值得继续做 Phase 2 overlay study**（信号中等强度，BP 容量充足，但 short-gamma stacking 风险显性化）。**不开 SPEC**，**不改生产规则**。

5. **推荐 Phase 2 最小 pilot**：3 变体，全部以 idle-BP 阈值为前置门 — `Overlay-A 1.5× conditional`、`Overlay-B 2× conditional + disaster cap`、`Overlay-C 2× conditional + no overlap`。其中 **Overlay-C** 是直接回应 Phase 1 §8 short-gamma 发现的最重要变体。

---

## 1. Framing：为什么 Q036 不是 Q021 的延长

### 1.1 两层 objective function 不同

| 层级 | 问题 | 决策标准 | Q021 答案 |
|---|---|---|---|
| **Rule layer (Q021)** | 这是不是更好的 canonical rule？ | marginal $/BP-day **>** baseline ($4.85) | V_D/V_E/V_J/V_G 全部 < baseline → **不晋升** |
| **Capital allocation layer (Q036)** | baseline 之上闲置 BP 是否应受控部署？ | Δ account ROE > 0 AND tail cost 可接受 AND > 当前机会成本 | **待 feasibility** |

### 1.2 关键经济观察 — 这是 Q036 的核心命题

> 如果 baseline 的 BP 在大多数交易日确实是 idle 的（机会成本 = $0/BP-day），那么 overlay 的边际门槛就**不是 V_A 的 $4.85/BP-day**，而是 **$0/BP-day**。

在 Phase 4 数据中：

| Variant | Marginal $/BP-day | vs V_A baseline ($4.85) | vs idle baseline ($0) |
|---|---:|---|---|
| V_E | $2.70 | ✗ leverage drag | ✓ 显著为正 |
| V_J | $2.98 | ✗ leverage drag | ✓ 显著为正 |
| V_D | $3.37 | ✗ leverage drag | ✓ 显著为正 |
| V_G | $3.83 | ✗ leverage drag | ✓ 显著为正 |

Q021 Phase 4 的 "leverage drag" 结论在 rule-replacement 框架下**仍然成立**（不要尝试翻案）。在 overlay 框架下它的语义变成"边际资本效率低于 baseline 现行规则，但高于 idle"，**两件事不能混**：

- **Q021 close 不会被 Q036 翻案**
- **Q036 的判断不能直接套 Q021 的 marginal $/BP-day 门槛**
- **Q036 必须新建 account-level + tail-cost 评估包，而非借用 Q021 子策略级指标**

### 1.3 显式的非目标（PM 边界）

- ❌ 不重新测试 V_D 是否替代 V_A
- ❌ 不把 overlay 写成 SPEC-066 修订
- ❌ 不假设 Phase 4 的 marginal $/BP-day < baseline 等于 overlay 不可行
- ❌ 不重启 Q021 semantic dispute（distinct-peak 语义在 Q021 已答）
- ❌ 不与 `/ES` 或其他未来 sleeve 比较机会成本（PM 当前 baseline = `A` idle）

---

## 2. Phase 1 Prototype Results — Idle BP Baseline (V_A SPEC-066, no overlay)

Prototype: [backtest/prototype/q036_phase1_idle_bp_baseline.py](../backtest/prototype/q036_phase1_idle_bp_baseline.py)

测量条件：V_A SPEC-066 production rule、`account_size = $150,000`（engine 默认）、`AFTERMATH_OFF_PEAK_PCT = 0.10`、2000-01-01 至今、6,617 交易日。

### 2.1 §1 全样本日级 idle BP

| 指标 | 数值 |
|---|---:|
| 总交易日 | 6,617 |
| 平均日 BP 使用 | **8.68%** |
| 平均日 BP idle | **91.32%** |
| 中位数 BP idle | 90% |
| 最大 BP 使用（26 年内峰值）| **30%** |

**直接结论**：account 在 baseline V_A 下 26 年从未超过 30% BP 占用。**idle BP 是结构性持久现象，不是偶发**。

### 2.2 §2 Idle BP 分布

| 切片 | mean | std | p5 | p25 | p50 | p75 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 全样本 | 91.3% | 6.8% | 79.0 | 90.0 | 90.0 | 100.0 | 100.0 |
| Recent (2018+) | 90.8% | 6.7% | 79.0 | 90.0 | 90.0 | 93.0 | 100.0 |

**recent slice p75 从 100% 下降到 93%** — 现代 regime 的 BP 占用比 2000-2017 紧一些，但 idle 仍然 ≥ 79% 在 95% 的天数里。

### 2.3 §3 Idle BP by Regime

| Regime | n | mean idle | p5 | p25 | p50 |
|---|---:|---:|---:|---:|---:|
| HIGH_VOL | 1,960 | 91.6% | 79.0 | 86.0 | 93.0 |
| NORMAL | 2,564 | 93.2% | 80.0 | 90.0 | 90.0 |
| LOW_VOL | 2,093 | 88.7% | 80.0 | 90.0 | 90.0 |

**反直觉发现**：HIGH_VOL idle (91.6%) 略高于 LOW_VOL (88.7%)。原因：HIGH_VOL 有 EXTREME_VOL 硬门槛（VIX ≥ 35 → REDUCE_WAIT）+ vol-spell throttle，反而限制了高波 regime 的 entry，使 BP 在该 regime 下更倾向闲置。**对 overlay 决策意味着**：HIGH_VOL aftermath 窗口里 idle BP 充足，不会被 baseline crowding。

### 2.4 §4 Idle BP by Aftermath State（关键决策切片）

| 切片 | n | mean idle | p5 | p25 | p50 |
|---|---:|---:|---:|---:|---:|
| Aftermath day (in cluster) — full | 805 | **90.7%** | 76.0 | 86.0 | 93.0 |
| Non-aftermath — full | 5,812 | 91.4% | 80.0 | 90.0 | 90.0 |
| Aftermath, 2018+ | 281 | **88.4%** | 76.0 | 83.0 | 86.0 |
| Non-aftermath, 2018+ | 1,808 | 91.2% | 80.0 | 90.0 | 90.0 |

**结论**：aftermath 窗口的 idle BP 比非 aftermath 略低（约 -0.7pp 全样本，-2.8pp recent slice），但仍维持 ≥ 88% — overlay deploy 时 **idle BP 充足不会成为约束**。

### 2.5 §5 Idle BP by VIX Bucket

| VIX bucket | n | mean idle | p5 |
|---|---:|---:|---:|
| VIX < 15 | 2,093 | 88.7% | 80.0 |
| 15 ≤ VIX < 20 | 1,972 | 93.7% | 80.0 |
| 20 ≤ VIX < 25 | 1,280 | 91.2% | 76.0 |
| 25 ≤ VIX < 30 | 649 | 91.9% | 79.0 |
| 30 ≤ VIX < 40 | 430 | 90.2% | 79.0 |
| **VIX ≥ 40** | **193** | **96.7%** | **86.0** |

**EXTREME_VOL 自动 gate idle BP 高位**：VIX ≥ 40 反而 idle 最高（96.7%），因为 baseline 自己 REDUCE_WAIT。这意味着 overlay 即便不写 disaster-cap，最危险的 vol 区间已被 baseline 自动 skip。但 **30 ≤ VIX < 40 区间** idle 仍 90.2%（mean）但 worst case 79% — 这是 overlay 的真实风险窗口（baseline 不 skip，overlay 可能放大）。

### 2.6 §6 Disaster Windows — Forced-Liquidation Proxy

| Window | n | mean idle | p5 | worst day |
|---|---:|---:|---:|---|
| 2008 GFC | 85 | 97.2% | 90.0 | 2008-09-02: bp_used=10%, vix=22, drawdown -1.2% |
| 2020 COVID | 50 | 92.3% | 86.0 | 2020-03-04: bp_used=14%, vix=32, drawdown -0.32% |
| 2025 Tariff | 42 | 86.5% | 76.0 | 2025-04-14: bp_used=24%, vix=30.9, drawdown -2.54% |

**关键发现**：
- 2008 GFC：account 在 GFC 中保持 97.2% idle — 系统主动收缩
- 2020 COVID：尽管市场极端，account idle ≥ 86%，没有 margin stress
- 2025 Tariff：worst-idle day 76%，drawdown 仅 -2.54% — 这是最有压力的窗口但仍远离 forced liquidation 边界

**Forced-liquidation proxy 信号弱**：26 年内最坏的 single-day idle 也有 76%（2025-04-14），离 0% 还有 76pp 余量。**baseline V_A 不存在 margin-stress 风险**。

### 2.7 §7 Aftermath-day Deploy Capacity

| Threshold | Full (n=805) | Recent 2018+ (n=281) |
|---|---:|---:|
| ≥ 10% idle | 100.0% | 100.0% |
| ≥ 30% idle | 100.0% | 100.0% |
| ≥ 50% idle | 100.0% | 100.0% |
| ≥ 70% idle | 100.0% | 100.0% |
| ≥ 80% idle | 84.3% | 77.2% |

**Overlay 触发可行性极高**：在所有 aftermath 日中，idle BP ≥ 70% 的覆盖率为 100%。即使 overlay 设计要求 ≥ 80% idle 才触发，也能在 ~80% 的 aftermath 日触发。**deploy 容量不是约束**。

### 2.8 §8 Short-Gamma 重叠（最关键的新发现）

| 切片 | n | mean short-gamma | #0 | #1 | #≥2 |
|---|---:|---:|---|---|---|
| Full sample aftermath | 805 | 1.27 | 284 (35%) | 141 (18%) | **380 (47%)** |
| Recent (2018+) aftermath | 281 | 1.56 | 56 (20%) | 74 (26%) | **151 (54%)** |

**这是 Phase 1 最重要的发现**：在 47%（full）/ 54%（recent）的 aftermath 日，账户**已经携带 ≥ 2 个 short-gamma 仓位**。这意味着 overlay 在大多数 aftermath 日**不是分散风险，而是堆叠** — 既有的 BPS、Iron Condor、其他 premium-selling 位置已经短 gamma。

直接含义：

- **`Overlay-C 2× no-overlap`** 不再是"次优规则"，而是**针对此结构性 stacking 的核心 guardrail**
- 简单的 `1.5×` 或 `2× full` overlay 在多数 aftermath 日都会形成 3+ short-gamma 仓位 + 加倍 IC_HV
- Phase 2 任何 unconditional sizing-up overlay 都必须先回答："overlay 触发那天账户已有多少 short-gamma？"

---

## 3. Phase 1 → Q036 的 5 个 PM 问题映射

| PM 问题 | Phase 1 答 | 还需 Phase 2 |
|---|---|---|
| **Q1 idle BP 持久且大？** | **是**：avg 91% idle、max 30%、aftermath idle ≈ 88-91% | (此问题已答) |
| **Q2 overlay 提升 ROE？** | 间接证据：Phase 4 V_E/V_J/V_G 都 marginal > 0；理论上 deploy 必为正 | 需 Phase 2 直接算 account ROE / annualized ROE / positive-year% |
| **Q3 incremental tail cost？** | baseline tail 极小（worst-idle 76% / drawdown -2.54%）→ overlay 是否破坏此特性？ | 需 Phase 2 测 overlay 触发时的实际 idle 压缩、disaster window net、CVaR |
| **Q4 overlay vs idle 基线？** | 因 idle baseline = $0/BP-day，且 deploy 容量 100% 充足 → 任何正贡献 overlay 在 raw return 上都赢 | 需 risk-adjusted 比较：incremental ROE / incremental MaxDD ratio |
| **Q5 minimum pilot** | 见下文 §4 | Phase 2 Prototype |

---

## 4. Phase 2 推荐 — 最小 pilot shortlist (3 变体)

**前提**：Phase 1 已确认 idle BP persistence + deploy capacity 充足，但同时发现 short-gamma stacking 风险。**所有 Phase 2 变体必须以 idle-BP 阈值为前置门**，与 5 候选清单中"only when idle-BP exceeds threshold"对应。

### 4.1 三个 pilot 变体

| Pilot | 规则 | 选择理由 |
|---|---|---|
| **Overlay-A: 1.5× conditional** | aftermath 首笔 size = 1.5×，**仅在 system idle BP ≥ 70% 时触发**；否则 1× | 最低 tail cost；Phase 4 V_E 的 conditional 化版本；测试"温和 overlay"的下界 |
| **Overlay-B: 2× conditional + disaster cap** | aftermath 首笔 size = 2×，**仅在 idle BP ≥ 70% 且 VIX < 30** 时触发；否则 1× | 综合 V_G + idle-BP gating 两个最强 guardrail；Phase 4 V_G 已证明 disaster cap 在 COVID 起作用 |
| **Overlay-C: 2× conditional + no overlap** | aftermath 首笔 size = 2×，**仅在 idle BP ≥ 70% 且无任何 IC_HV 持仓** 时触发；否则 1× | **直接回应 Phase 1 §8 short-gamma stacking 发现**；Phase 4 V_J 已证明可消除 distinct-cluster overlapping leverage |

### 4.2 不在 pilot 范围（与用户 5 候选清单的对应）

| 用户清单候选 | 处理 | 原因 |
|---|---|---|
| 1.5× first-entry overlay | ✅ Overlay-A | 包含（conditional 化） |
| 2.0× first-entry no overlap | ✅ Overlay-C | 包含（conditional 化） |
| 2.0× only above idle-BP threshold | ✅ A / B / C 都内含此 gate | 这是所有变体的前置门，不单独列 |
| 2.0× with disaster downgrade | ✅ Overlay-B | 包含（conditional 化 + disaster cap） |
| Split-entry overlay | ❌ 不测 | Phase 4 V_H 已证明 split-entry = V_A − 1 trade，无独立 alpha；overlay 化也不会突然产生新 edge |

### 4.3 Phase 2 必备指标包

每个 overlay 变体必须输出以下三层指标（**永久 standing rule + Q036 新增**）：

#### Account-level（Q036 新顶层）
- Total account PnL / annualized account ROE / positive-year proportion
- Account-level MaxDD（不是子策略级 — 必须看整个 portfolio path）
- Incremental ROE / incremental MaxDD ratio
- Incremental ROE / incremental CVaR ratio

#### Phase 4 永久 metrics pack
- PnL/BP-day（per variant）
- **Marginal $/BP-day 双 baseline**：`vs V_A ($4.85)` AND `vs idle baseline ($0)` — Q036 关心后者
- Worst trade
- Disaster window net
- Max system BP%（不只是 IC_HV BP%）
- Concurrent overlap days
- IC_HV CVaR 5%

#### Q036 capital-allocation 专属
- **Idle-BP utilization rate**：overlay 实际部署了多少% 可用 idle BP（理想情况：低 — 说明 overlay 节制）
- **Margin-stress proxy**：overlay 触发期间 system BP% 峰值在 VIX > 30 时是否破 50%
- **Forced-liquidation proxy**：同一 disaster 窗口最大 BP 占用 × 同时 mark-to-market loss 的乘积峰值
- **Crowd-out check**：overlay 是否曾因 BP 占用阻挡了 baseline aftermath 信号（应为 0 — 因为 idle BP 阈值 gate）
- **Short-gamma stacking actualized**：overlay 触发那天 account 已有 short-gamma count 的分布（直接对比 Phase 1 §8）

---

## 5. Phase 1 → Phase 2 决策路径

```
Phase 1 ✅ DONE
     ↓
  idle BP 持久 ✅
  aftermath deploy capacity ≥ 70% 时 100% ✅
  short-gamma stacking 风险显性化 ⚠️
     ↓
Phase 2 (推荐进行) — 3-variant overlay study
     ↓
  per-variant 输出 account-level ROE + tail cost + short-gamma stacking
     ↓
  PM 决策点：
    (i)  approve Overlay-X → 写 SPEC-067 DRAFT
    (ii) drop Q036 → idle 仍是首选
    (iii) request additional Phase 3 (e.g. multi-strategy overlay 不限 IC_HV)
```

---

## 6. Quant Researcher 标准格式总结

- **Topic**: Q036 — Idle BP Deployment / Capital Allocation feasibility
- **Findings**:
  - Q036 与 Q021 的 objective function 完全不同；overlay 的边际门槛是 idle baseline ($0/BP-day)，不是 V_A baseline ($4.85)
  - Phase 1 直接测量：account 平均 91% idle、max BP used 30%；idle BP 是结构性持久现象
  - aftermath 窗口 idle 略低（88-91%）但完全足够 overlay 部署；deploy capacity ≥ 70% 阈值时 100% 满足
  - Disaster 窗口 idle 反而高（GFC 97%、COVID 92%）— EXTREME_VOL gate 自动 protect
  - **新风险信号**：47-54% 的 aftermath 日 account 已有 ≥ 2 个 short-gamma；overlay = stacking
- **Risks / Counterarguments**:
  - Phase 1 没有直接测 overlay 触发时的 actual short-gamma count；§8 是 baseline 切片，overlay 触发后会更高
  - account_size = $150K 是 engine 默认；live ~$500K 时 BP% 数字会按比例变化（Phase 2 应用 live 账户大小或保持比例化）
  - "idle BP = $0/BP-day 机会成本" 假设当前 baseline `A`；若未来 `/ES` 或其他 sleeve 上线，机会成本会上升，结论可能反转
  - 26 年最坏 idle 76% / drawdown -2.54% 仍远离 forced-liquidation；但 Phase 2 overlay 触发后，single-day BP 占用可能从 30% 跳到 50%+，需重测 worst case
- **Confidence**: medium-high（framing 正确性 high；经济答案 medium pending Phase 2）
- **Next Tests**:
  - **Phase 2** (推荐): 3 个 conditional overlay 变体 + 完整 metrics pack + Q036 capital-allocation 专属指标
- **Recommendation**: **research — 进入 Q036 Phase 2 prototype；不开 SPEC，不改生产**

---

## 7. 边界与未做

| 边界 | 原因 |
|---|---|
| 没在 Phase 1 测试任何 overlay 变体 | Phase 1 设计上只测 baseline；先确认 idle BP 是否值得 overlay |
| 没用 live $500K 账户大小 | engine 默认 $150K，与 Q021 Phase 4 等价；Phase 2 可以选择性放大到 $500K |
| 没量化 forced-liquidation proxy 的非线性边界 | Phase 1 显示 baseline 离边界很远；Phase 2 要在 overlay 触发场景下重新评估 |
| 没把 `/ES` 或其他 sleeve 作为机会成本对比 | PM 当前 baseline `A` 明确为 idle；future cycle 可考虑 |
| 没做 cluster threshold sweep | 与 Q036 不直接相关；Phase 2 用 SPEC-066 production cluster |
| 没在 multi-strategy（BPS_HV / DIAGONAL）层面探 overlay | PM 明确 IC_HV aftermath 为 pilot；多策略 overlay 是 Phase 3+ 议题 |

---

## 8. 总结

Phase 1 的 **decisive 数据**告诉我们：

1. **Idle BP 不是"也许有时候少量空着"，而是"几乎所有时候大量空着"** — 91% 平均闲置，max 30% 使用率
2. **Overlay deploy 容量不是约束** — 100% 的 aftermath 日有 ≥ 70% idle BP 可部署
3. **Forced-liquidation 风险在 baseline 下不存在** — 最坏 single-day idle 仍 76%
4. **真正的 capital-allocation 风险来自 short-gamma stacking** — 不是 BP 不够，而是同方向风险已经堆积

这意味着 Q036 的 framing 在经济层面**站得住**，但实施风险**主要落在 stacking 而非 leverage**。Phase 2 必须把 short-gamma overlap 作为一等公民评估指标 —— 这正好对应 `Overlay-C 2× no-overlap` 的设计动机。

> **Phase 2 不是"是否做 overlay"的问题，而是"用哪种 stacking 控制方式做 overlay"的问题**。

如果 Phase 2 三变体中有 ≥ 1 个能同时通过：
- account-level ROE 显著为正
- account-level MaxDD 增量可接受
- short-gamma stacking 不超过 baseline +1 仓位
- disaster window net 不退化

→ 进入 SPEC-067 DRAFT 讨论。
否则 → drop Q036，保留 idle 为机会成本基线。
