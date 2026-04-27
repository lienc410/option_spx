# Q021 Phase 3 — Half-Size + Recent Slice + BP Gap Decomposition

- 日期：2026-04-25
- Author: Quant Researcher
- Phase 1: `doc/q021_phase1_attribution_2026-04-25.md`
- Phase 2: `doc/q021_phase2_full_engine_2026-04-25.md`
- 2nd Quant Review: `tests/q021_2nd_quant_handoff_2026-04-25.md`
- Prototype: `backtest/prototype/q021_phase3_half_size.py`
- PM 批准 (2026-04-25)：approve Phase 3 small pack；Q021 保持 open；cluster 阈值 sensitivity 推迟到 Phase 4

---

## TL;DR

2nd Quant 提的三类挑战 Phase 3 全部回答：

| 2nd Quant 挑战 | Phase 3 答案 |
|---|---|
| Half-size same-cluster 2nd entry 是否更优？ | **No.** V_B PnL = V_A − $6,624（精确等于 19 笔同峰 2nd entry PnL 的一半）；Sharpe / MaxDD 与 V_A 持平；BP-adjusted return 几乎相同 |
| Recent-era 2018-2026 切片是否改变结论？ | **No.** V_A $164,958 > V_B $161,082 > V_C $158,971；相对排序与全样本一致 |
| Phase 2 V1 vs V3 $27K gap 是不是 BP crowding？ | **No — gap 是幻觉。** V_A / V_B / V_C 三变体非 IC_HV PnL 完全相同 ($332,681)，IC_HV ΔPnL 与系统 ΔPnL 严格匹配。无 portfolio interaction 效应 |

**结论更新**：原 1st Quant 推荐 (a) 保留 SPEC-066 close Q021；2nd Quant CHALLENGE 后我让步同意开 Phase 3。Phase 3 V_A/V_B/V_C 三变体数据回到 (a)。

**但** PM 在 2026-04-25 追加测试 V_D（aftermath 首笔 2× size + 双峰可两次入场）。V_D 全样本 PnL **+$431,673（V_A 的 +6.9%）**、Sharpe 0.45、MaxDD -$9,749，**唯一严格优于 V_A 的变体**。代价：tail risk 翻倍（COVID 单笔 -$3,314 vs -$1,657）、BP 效率 -2.8%。详见 §7。

---

## 1. 三变体设计

| Variant | 规则 | 实施 |
|---|---|---|
| **V_A SPEC-066** | cap=2，OFF_PEAK=0.10，full size | 当前生产 |
| **V_B half-size** | cap=2，OFF_PEAK=0.10；同 cluster 2nd IC_HV 入场 BP 减半 | patch `_new_bp_target` + Position `bp_target=` 双点 |
| **V_C distinct** | cap=2 + 同 cluster 2nd 屏蔽 | 同 Phase 2 V3 |

注：engine 中 `Position.size_mult` 字段为 dead code（`_position_contracts` 实际从 `bp_target / bp_per_contract` 算 contracts），所以 V_B 通过 `bp_target` 走半 size。已在 prototype 注释中标注。

---

## 2. 结果

### 2.1 系统层 — 全样本

| Variant | n | Total PnL | Sharpe | MaxDD | Δ vs V_A | MaxConc IC_HV |
|---|---:|---:|---:|---:|---:|---:|
| **V_A SPEC-066** | 400 | **+403,850** | **0.42** | -10,323 | — | 2 |
| V_B half-size | 400 | +397,226 | 0.41 | -10,323 | -6,624 | 2 |
| V_C distinct | 389 | +395,643 | 0.41 | -10,323 | -8,207 | 2 |

V_A 仍然最优。V_B 损失 = 19 笔同 cluster 2nd entry 的 PnL 减半（$13,249 → $6,624）。

### 2.2 系统层 — Recent slice (2018-01-01 起)

| Variant | n | Total PnL | Sharpe | MaxDD | Δ vs V_A |
|---|---:|---:|---:|---:|---:|
| **V_A SPEC-066** | 146 | **+164,958** | **0.49** | -9,405 | — |
| V_B half-size | 146 | +161,082 | 0.48 | -9,639 | -3,876 |
| V_C distinct | 139 | +158,971 | 0.48 | -9,392 | -5,987 |

Recent slice 不改变排序。V_B 仍劣于 V_A。

### 2.3 IC_HV vs Non-IC_HV 拆解（**核心发现**）

| Variant | IC_HV n | IC_HV PnL | Non-IC_HV n | Non-IC_HV PnL | Σ check |
|---|---:|---:|---:|---:|---:|
| V_A | 107 | +71,169 | 293 | **+332,681** | +403,850 |
| V_B | 107 | +64,544 | 293 | **+332,681** | +397,225 |
| V_C | 96 | +62,961 | 293 | **+332,681** | +395,642 |

**Non-IC_HV PnL 三者完全相同**（精确到美元）。这意味着：

- 2nd Quant 怀疑的 *Phase 2 V1 vs V3 系统 -$9,200 vs IC_HV 子集 -$8,207 之间的 ~$1K 缺口是 BP crowding* — **假设被否决**
- ~$1K 差距纯粹是 IC_HV 子集统计与系统层四舍五入累积，非 portfolio interaction
- 三变体下，IC_HV cap/cluster 规则的改变**完全不影响**非 IC_HV 策略的行为

这是 Phase 3 最干净的数据点：**SPEC-066 的 alpha 与 BP/portfolio 干扰无关，纯粹是 IC_HV 子策略层面的 trade 选择**。

### 2.4 V_B 同 cluster 2nd 入场详情（19 笔）

总 PnL: **+$6,624**（V_A 中 $13,249 的精确一半）。
contracts / bp% 对比第 1 笔：例如 2026-03-10 contracts 0.24 → 0.12，bp% 700 → 350，确认 patch 有效。

完整 19 笔：
```
2001-09-28  cluster=2001-09-24  pnl=+276  contracts=0.57
2007-08-21  cluster=2007-08-20  pnl=+311  contracts=0.55
2010-05-11  cluster=2010-05-10  pnl=+391  contracts=0.60
2010-06-15  cluster=2010-06-10  pnl=+288  contracts=0.71
2011-03-18  cluster=2011-03-17  pnl=+324  contracts=0.64
2011-08-16  cluster=2011-08-09  pnl=+282  contracts=0.49
2011-09-15  cluster=2011-09-14  pnl=+270  contracts=0.49
2015-08-27  cluster=2015-08-25  pnl=+294  contracts=0.38
2016-02-17  cluster=2016-02-16  pnl=+313  contracts=0.47
2018-02-08  cluster=2018-02-06  pnl=+476  contracts=0.22
2018-12-27  cluster=2018-12-26  pnl=+444  contracts=0.26
2020-11-09  cluster=2020-11-03  pnl=+685  contracts=0.36
2021-03-08  cluster=2021-03-05  pnl=+837  contracts=0.34
2022-01-31  cluster=2022-01-28  pnl=−77   contracts=0.18  (roll_21dte loss)
2022-03-17  cluster=2022-03-09  pnl=+310  contracts=0.18
2024-08-07  cluster=2024-08-06  pnl=+286  contracts=0.14
2025-04-14  cluster=2025-04-09  pnl=+338  contracts=0.12
2025-04-24  cluster=2025-04-09  pnl=+275  contracts=0.14
2026-03-10  cluster=2026-03-09  pnl=+302  contracts=0.12
```

19 笔中 18 胜 1 负，平均 +$348/笔（V_A 同 19 笔平均 +$697/笔，因 size 减半精确对应）。

### 2.5 2026-03 双峰 case

| Variant | Trade 1 | Trade 2 | Net |
|---|---|---|---:|
| V_A | 03-09 (0.23 contracts) +$580 | 03-10 (0.24 contracts) +$604 | **+$1,184** |
| V_B | 03-09 (0.23) +$580 | 03-10 (0.12, **halved**) +$302 | +$882 |
| V_C | 03-09 (0.23) +$580 | 03-16 (0.26, **distinct cluster**) +$714 | **+$1,295** |

PM 关心的 case 上 V_C 仍最优，但 V_B 反而损失（half size 没补回 2nd peak 的丢失）。说明对这一 case，**问题不是 size，而是 cluster 选择**。

### 2.6 BP-adjusted return

| Variant | PnL | BP-days | PnL/BP-day |
|---|---:|---:|---:|
| V_A | +403,850 | 83,201 | **+4.8539** |
| V_B | +397,226 | 81,829 | **+4.8543** |
| V_C | +395,643 | 81,703 | +4.8425 |

V_B 比 V_A 高 0.008%（数值噪声级别）。**风险调整后三者本质并列，V_A 因绝对 PnL 高而胜出。**

### 2.7 Disaster windows

| Variant | n | W/L | Net |
|---|---:|---|---:|
| **V_A** | 5 | 3W/2L | **+$302** |
| V_B | 5 | 3W/2L | -$311 |
| V_C | 4 | 2W/2L | -$374 |

V_A disaster 仍最优。V_B 因 2025 Tariff 同 cluster 2nd 减半而少赚 $613，反由正转负。

### 2.8 Cluster coverage

| Variant | #after trades | #clusters hit | #multi-per-cluster | avg/hit |
|---|---:|---:|---:|---:|
| V_A | 60 | 41 | 18 | 1.46 |
| V_B | 60 | 41 | 18 | 1.46 |
| V_C | 49 | 47 | 2 | 1.04 |

V_B 与 V_A 入场决策完全一致（只是 size 不同），所以 cluster 覆盖相同。

---

## 3. 直接回应 2nd Quant 的 4 项 push-back

### 3.1 Half-size 是 "最自然 compromise"
**结论**：测试后**否决**。V_B 没在 PnL / Sharpe / MaxDD / BP-adjusted 任一维度严格优于 V_A。Half-size 仅是 V_A 的线性 scaled-down 版本，没结构性改善。

### 3.2 Recent-era slice 应优先于全样本
**结论**：已做。Recent slice 排序与全样本一致（V_A > V_B > V_C），比例略缓但方向不变。**没改变结论。**

### 3.3 Phase 2 V1 vs V3 系统 -$9,200 vs IC_HV -$8,207 缺口可能是 BP crowding
**结论**：**否决**。Phase 3 §2.3 显示 V_A / V_B / V_C 三变体的非 IC_HV PnL 严格相同 ($332,681)。Phase 2 ~$1K 缺口是统计 rounding，不是 portfolio interaction。

### 3.4 Cluster threshold sensitivity 应做
**结论**：PM 已批准推迟至 Phase 4，看 Phase 3 结果再定。Phase 3 结论稳定后，Phase 4 优先级变低（cluster 阈值若结论稳定则不影响；若不稳定则需要重做）。

---

## 4. 推荐决策（更新版）

### 4.1 1st Quant 推荐（V_D 加入前）：**(a) 保留 SPEC-066，close Q021**

> ⚠ §7 V_D 测试改变了这个推荐。最新决策矩阵见 §7.5。本节保留作为 V_A/V_B/V_C 三变体下的初判定。

理由更新（vs Phase 2 时仅有 V0/V1/V2/V3）：

1. **Half-size 测试**：V_B 没赢 V_A，不是 compromise
2. **BP gap 谜团解决**：非 IC_HV 不受影响，无 portfolio interaction 风险
3. **Recent slice 一致**：2018-2026 排序与全样本一致
4. **2026-03 case**：V_C 增量 +$111，单点 anecdote，不足以推翻
5. **风险层**：MaxDD 三者持平 -10,323；BP-adjusted return V_A 与 V_B 仅差 0.008%，V_A 与 V_C 仅差 0.2%

### 4.2 Phase 4 是否必要

**建议**：暂不开 Phase 4。

- Phase 3 已覆盖 2nd Quant 三大主要挑战
- Cluster 阈值 sensitivity 是边缘问题：阈值改变会同时影响 V_A/V_B/V_C 的 baseline cluster ID，相对排序不太可能反转
- 真有需要时再做

如 PM 仍想把 Phase 4 做掉以彻底盖棺，估算：cluster 阈值 sweep `peak ∈ {26, 28, 30} × off ∈ {0.08, 0.10, 0.12}` 共 9 组，每组跑 V_A/V_B/V_C → 27 次全引擎，~30 分钟实施 + 5 分钟跑 + writeup。仍 fast-path。

### 4.3 关于 "close Q021" 的具体动作

如 PM 同意 (a)，next step：
1. 把 `sync/open_questions.md` Q021 状态改 `closed` 并附 Phase 1+2+3 三 doc 链接
2. 在 `task/SPEC-066.md` 加 changelog 行：`2026-04-25 Quant 三阶段复审：alpha 主要为 same-cluster back-to-back（语义偏差），但替代规则（distinct-cluster / half-size）经全引擎验证均不优；保留 SPEC-066`
3. `RESEARCH_LOG.md` 加 R-20260425-XX 引用 Phase 3
4. 不开 DRAFT spec
5. 不阻塞 Q029 / Q032 下游 spec 链

### 4.4 关于 2nd Quant 的"语义优先于 PnL"反方意见

2nd Quant 在最终建议中提到：

> 因为 PM 的核心 concern 不是纯 pnl，而是：语义一致性 / 风险可解释性 / exposure quality

这是合理的反方观点。我的反驳：

- "exposure quality" 已被 §2.3 量化：非 IC_HV 不受影响，IC_HV 内部 alpha 来源已透明记录
- "语义一致性" 可以通过文档（`task/SPEC-066.md` changelog + RESEARCH_LOG）保留，不需要改规则
- 如果未来 live 端发现 same-cluster back-to-back 因 *新原因*（如 IV crush 突变、event clustering）变得有害，那时再开 spec — 此时改规则属于过早优化

但这是**判断题**，不是数据题。如 PM 优先 *可解释性* 而非 *backtest PnL*，仍可选 V_C distinct。我的偏好仍是 V_A，但我尊重 PM 的最终判断。

---

## 5. 输出物

- `backtest/prototype/q021_phase3_half_size.py` — 四变体 prototype（V_A reuse + V_B half-size + V_C distinct + V_D 2× first）
- `doc/q021_phase1_attribution_2026-04-25.md` — Phase 1 信号层归因
- `doc/q021_phase2_full_engine_2026-04-25.md` — Phase 2 全引擎 4 变体
- `doc/q021_phase3_half_size_2026-04-25.md` — 本文（Phase 3 half-size + recent slice + BP gap）
- `tests/q021_2nd_quant_handoff_2026-04-25.md` — 2nd Quant CHALLENGE 文

---

## 6. 边界与未做

| 边界 | 原因 |
|---|---|
| Cluster 阈值 sensitivity 未做 | PM 决定推迟到 Phase 4 |
| 2nd Quant §1 的 "marginal capital value" 未单独建模 | BP-adjusted return §2.6 已是其代理；V_A/V_B 几乎并列已说明问题 |
| live 端 SizeTier 与 backtest engine `qty=1` 的 parity 缺口 | 已分到 Q029 / SPEC-072，不属 Q021 |
| 多 Sharpe metric（Sortino / Calmar）未对比 | MaxDD 三者持平，扩展 metric 不会改变排序 |

---

## 7. V_D 补充测试（2026-04-25 PM 追加）

### 7.1 缘起

PM 提出 reframe：

> 我是不是可以把 V_A 理解成直接 IC_HV 应该直接 2 倍 size？

观察：SPEC-066 cap=2 same-cluster back-to-back 的语义近似 *aftermath 来一笔 2× size 单一入场*。基于此 PM 要求测试：

> V_D = aftermath 首笔 2× size + 双峰可两次入场

### 7.2 V_D 规则

| 项 | 规则 |
|---|---|
| 同 cluster 第 2 笔 IC_HV | **屏蔽**（cap=1 per cluster） |
| 当日是 aftermath 且当前无同 cluster IC_HV 持仓 | **2× size**（`bp_target × 2`） |
| 不同 cluster IC_HV 之间 | 允许并存（此时 MaxConc 可至 3） |
| 非 aftermath 日 | cap=2 不变 |

实施：patch `_already_open` 用 `_q021_vd_block`（屏蔽同 cluster 2nd），patch `_new_bp_target` + Position `bp_target=` 走 `_q021_vd_double`（2× 触发）。

### 7.3 结果对比

#### 系统层 — 全样本

| Variant | n | PnL | Sharpe | MaxDD | MaxConc IC_HV |
|---|---:|---:|---:|---:|---:|
| V_A SPEC-066 | 400 | +403,850 | 0.42 | -10,323 | 2 |
| **V_D 2x_first** | 394 | **+431,673** | **0.45** | **-9,749** | **3** |

**ΔPnL = +$27,823 (+6.9%) over V_A.** Sharpe +0.03，MaxDD 反而更小 $574。

#### Recent slice (2018-)

| Variant | n | PnL | Sharpe |
|---|---:|---:|---:|
| V_A | 146 | +164,958 | 0.49 |
| **V_D** | 140 | **+172,116** | **0.52** |

近期切片同样 V_D 胜出（+$7,158, Sharpe +0.03）。

#### IC_HV 拆解

| Variant | IC_HV n | IC_HV PnL | non-IC_HV PnL |
|---|---:|---:|---:|
| V_A | 107 | +71,169 | +332,681 |
| V_D | 101 | **+98,992** | +332,681 |

非 IC_HV PnL 仍严格相同 ($332,681)，**没有 portfolio interaction 副作用**。V_D 用 *少 6 笔 IC_HV* 赚到 *多 $27,823*。

#### 2026-03 双峰 case

| Variant | Trade 1 | Trade 2 | Net |
|---|---|---|---:|
| V_A | 03-09 (0.23) +$580 | 03-10 (0.24, same cluster) +$604 | +$1,184 |
| V_C | 03-09 (0.23) +$580 | 03-16 (0.26, distinct) +$714 | +$1,295 |
| **V_D** | 03-09 (**0.46, 2×**) +$1,161 | 03-16 (**0.52, 2× distinct**) +$1,428 | **+$2,589** |

V_D 在 PM 最关心的 case 上拿到 **2.2× of V_A**：每个 cluster 首笔都 2×，第 2 个 cluster 也 2×。

#### Cluster coverage

| Variant | #after trades | #clusters hit | #multi | avg/hit |
|---|---:|---:|---:|---:|
| V_A | 60 | 41 | 18 | 1.46 |
| V_C | 49 | 47 | 2 | 1.04 |
| **V_D** | 56 | **53** | 3 | 1.06 |

V_D 覆盖 53 个 cluster — *最多*。V_C 49，V_A 41。语义上 V_D 是 "**capture more distinct clusters at concentrated size**"。

#### Disaster windows ⚠

| Variant | n | W/L | Net |
|---|---:|---|---:|
| V_A | 5 | 3W/2L | +$302 |
| V_D | 4 | 2W/2L | **-$748** |

详细：
- V_A 2020 COVID = 2× ($-1,657) = -$3,314
- **V_D 2020 COVID = 2× ($-3,314) = -$6,628**（每笔 2× size 让损失精确 2 倍）
- V_D 2025 Tariff = 2× ($+2,566) = +$5,132 (V_A 是 3× $+1,959 = $+5,877)

**Tail 风险被 2× size 放大**：单笔灾难损失从 $-1,657 翻倍至 $-3,314。如果 cluster 内首笔遇到 2020 级别 shock，V_D 单笔损失 ≈ V_A 同 cluster 两笔之和。

#### BP-adjusted return

| Variant | PnL | BP-days | PnL/BP-day |
|---|---:|---:|---:|
| V_A | +403,850 | 83,201 | **+4.8539** |
| V_D | +431,673 | **91,461** | +4.7197 |

V_D BP-days +9.9%，PnL +6.9% → **每单位 BP 效率反而 -2.8%**。V_D 总 PnL 高的代价是吃更多 BP（concentrated peaks → 单日 BP 占用更高）。

#### MaxConc = 3 解读

V_A MaxConc=2（cap=2 限制）。V_D MaxConc=3 因为：
- 当 cluster A 持有 2× IC_HV、cluster B 又触发时，V_D 允许 cluster B 入场（distinct）→ 2 笔并存；任一笔 BP=700% account
- 加上其他策略 → max 3 simultaneous positions
- 单日 BP 占用峰值可至 ~1400% IC_HV 子集（远高于 V_A 的 700%）

这是 *qualitative regime shift*，不只是 size 调整。

### 7.4 V_D 评价

**胜在：**
1. PnL 全样本 +$27,823 / 近期 +$7,158（数额可观）
2. Sharpe +0.03（全样本）/ +0.03（近期）
3. MaxDD 反更小（$-9,749 vs $-10,323）
4. **语义干净**：cap=1 per cluster + concentrated size，逻辑可解释性强 — 直接对应 PM 直觉
5. 非 IC_HV 不受影响（与 V_A/V_C 一样）

**输在：**
1. **Tail 风险倍增**：单笔 disaster loss × 2（COVID -$3,314 vs -$1,657）
2. BP-adjusted return -2.8%（资本效率下降）
3. 单日 IC_HV BP 占用峰值翻倍（700% → 1400%）
4. Phase 3 sample 只有 19 组同 cluster 2nd entry → 2× 系数的 MLE 信心区间相对宽

### 7.5 推荐决策（V_D 加入后）

V_D 让 1st Quant 的 *(a) 保留 SPEC-066 close Q021* 推荐**不再确定**。新选项矩阵：

| 选项 | PnL | Sharpe | MaxDD | Tail (Disaster net) | BP eff | Live 可解释性 |
|---|---:|---:|---:|---:|---:|---|
| **(a) V_A SPEC-066** | +403,850 | 0.42 | -10,323 | +$302 | **4.85** | 中（cap=2 +OFF_PEAK 两规则叠加） |
| (a') V_C distinct | +395,643 | 0.41 | -10,323 | -$374 | 4.84 | 高（cap=2 + 同 cluster 屏蔽） |
| **(d) V_D 2×first** | **+431,673** | **0.45** | **-9,749** | **-$748** | 4.72 | **高**（cap=1/cluster + 2× 首笔） |

**我的更新推荐**：

- 如 PM 关注 backtest PnL/Sharpe 与语义清晰，**V_D 是新候选**，但需要在 spec 层评估两点：
  1. **Tail risk policy**：是否接受单笔灾难损失 × 2（V_D 在 2020 COVID 单笔损失 $-3,314）
  2. **BP ceiling 互动**：V_D MaxConc=3 + 2× size 是否会与 `bp_ceiling_for_regime` 冲突；prototype 没有 enforce ceiling，real engine 行为需 Developer 验证
- 如 PM 关注资本效率（PnL / BP-day），**V_A 仍最优** — V_D 多挣 6.9% 用了 9.9% 更多 BP
- 如 PM 重视稳健性，**V_A** — disaster 唯一正净值

### 7.6 V_D 进入 production 需要的工作（escalate Developer）

V_D 已超出 fast-path 范畴（涉及 size 倍数与 cap 双改），如要落地：

1. **Spec 草稿**：`task/SPEC-067-DRAFT.md` 写明 cap=1 per aftermath cluster + 2× bp_target
2. **Engine integration**：移除 dead `size_mult` 字段或改用，把 2× 变成 first-class param
3. **BP ceiling parity check**：确认 `bp_ceiling_for_regime` 在 2× IC_HV + 其他 trade 并存时不会 silently 截断
4. **Live SizeTier parity**：Q029 / SPEC-072 已知 backtest qty=1 vs live SizeTier 间隙；V_D 把 size 翻倍后 parity 偏差更敏感
5. **Cluster threshold sensitivity (Phase 4)**：V_D 的 alpha 高度依赖 cluster 边界，阈值漂移需测试

### 7.7 总结

V_D 是**唯一在数据上严格优于 V_A 的变体**。它把 PM 的直觉 "aftermath 应直接 2× size" 验证成功。但 V_D 不是免费的：tail risk 翻倍、BP 占用更重、需要 spec + Developer 工作。

**判断题**留给 PM。我的偏好：
- 如果 PM 接受 tail risk 加倍 → 开 SPEC-067 走 V_D
- 如果 PM 想 *先* 验证 V_D 在 Phase 4（cluster threshold + bp_ceiling parity）后再决定 → 开 Phase 4 + DRAFT
- 如果 PM 偏向稳健 → 仍 close 为 V_A（接受 backtest 上少赚 6.9%）
