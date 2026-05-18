# Q073 — Round 2 ROE Optimization (Framing Review Packet)

**Date**: 2026-05-17
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **Pre-research framing review** — we have NOT yet run any research; we want the framing audited BEFORE we commit compute to it.
**Decision sought**: PASS / REVISE / REJECT the framing + research plan.
**Status**: 2nd Quant Review COMPLETE 2026-05-17 → **PASS WITH MAJOR REVISIONS** (see `q073_roe_round2_framing_2nd_quant_review_packet_2026-05-17_Review.md`). Framing reframed to **"Risk-constrained portfolio ROE optimization"**. 10 required revisions + 5 blind spots + 5 pitfalls + revised P0-P5 落地。等待 PM + Quant + 2nd Quant 三方 P0 锚定后启动。

---

## 0. TL;DR

PM 要求第二轮顶层 ROE 优化。明示"不要找捷径，不要小修小补，不怕推倒重来"。

自上一轮 ROE 优化（单策略内部参数 tune，Q041 family 时代）以来，**架构已经实质性变了**：5-6 个并存策略 + 双账户 + R1-R6 governance 框架。组合层面的 ROE lever 空间从未被系统 analyzed。

我提议开 **Q073** 做这件事，框架类比 Q071 P0-P5。**在开跑前请 2nd Quant 审阅**：
1. 框架本身（"组合层面 ROE 优化"）是否是正确问题
2. Lever 分解（5 个：A 策略矩阵 / B Cap / C Idle BP / D 多账户 / E Friction）是否 exhaustive
3. P0-P5 方法论是否 fit-for-purpose（Q071/Q072 类比）
4. Risk gates / vetoes 是否合理
5. 是否有我没看到的盲点 / pitfalls

**不锚定就开跑会浪费 compute（Q071 烧了不少），并且可能跑出 PM/2nd Quant 不接受的方向。**

---

## 1. Round 1 → Round 2: 架构变了什么

### 1.1 Round 1 (历史) optimization lever

Round 1 时（约 Q041-Q060 时代），ROE 优化 ≈ 单策略内部参数：

- SPEC-077: profit_target 0.50 → 0.60
- SPEC-084: BP target 14-15% per regime (Q045 J3 joint optimum)
- SPEC-094.1: Q042 Sleeve A DTE 90→30, OTM 5%→2.5%
- SPEC-100: max_trades_per_spell 2→3
- 多个 Q063/Q067/Q068/Q069: IVP gate jitter / hysteresis / 替代框架全部 reject

**Common pattern**: 假设其他策略不变，对单策略参数做敏感度 + Pareto check。

### 1.2 自 Round 1 后新增的结构性维度

| 新增 | 何时 | 来源 |
|---|---|---|
| **V3-A Aftermath overlay** | 2026-04~05 | Q064 P5 closure |
| **HV Ladder (/ES)** | 2026-05-14 | SPEC-101 (Q071 promote) |
| **HV Ladder dedicated frontend** | 2026-05-15 | SPEC-102 |
| **Q042 Dual-Sleeve overlay** | 2026-05-10 | SPEC-094 + 094.1 |
| **R1-R6 Sleeve Governance** | 2026-05-15 | SPEC-103 (Q072 promote) |
| **Q019 Signal 2 sidecar** | 2026-05-09 | SPEC-091, 6mo A/B period |
| **E-Trade PM account** | 2026-04 | SPEC-089 |

**Combined effect**: 上一轮的 lever（单策略内部）已经被用过；这一轮的 lever 必须是 **组合层面**（策略 mix、capital 分配、cap 框架、idle handling、多账户协同）—— 这块从未被系统 study 过。

### 1.3 为什么这是 Round 2 而不是 Round 1.5

不是 patch — 是 axis 切换。Round 1 是 "*single strategy parameter*"；Round 2 是 "*portfolio architecture*"。同一套 P0-P5 方法学可以复用，但 lever 空间完全不同。

---

## 2. Current State (诚实，含 unknown)

### 2.1 我知道的（measured）

| Strategy | Ann ROE (backtest) | MaxDD | Sharpe | Bootstrap sig | 备注 |
|---|---|---|---|---|---|
| **SPX BPS main (Q041)** | 不在 cache | — | — | — | 26y backtest 需重跑 |
| **V3-A Aftermath** | gate-bypass 性质 | — | — | — | Q064 结论：non-structural alpha |
| **HV Ladder /ES** | **1.14%** | **-9.68%** | **0.34** | **100%** | Q071 P5, 26y, 146 trades |
| **V2f baseline (no G6)** | 1.04% | -33.3% | 0.15 | 0% | Q071 P5 comparison |
| **Q042 Sleeve A (dd4)** | 9.94% (Sleeve only) | -19.0% | — | p=0.09 | SPEC-094.1 post-fix, 35 trades |
| **Q042 Sleeve B (dd15)** | low n (5 trades) | — | — | — | 100% WR but thin sample |
| **Q019 Signal 2** | sidecar | — | — | — | 6mo A/B period only |

### 2.2 我不知道的（critical gaps）

- **Combined 组合层面 ROE**: 各策略 PnL 时间序列重叠后，组合 ann ROE / Sharpe / MaxDD 是多少？没人算过。
- **Live ROE vs backtest 折损率**: 真实 fill / slippage / commission / margin financing 把 backtest 1.14% 打成多少？没数据。
- **Idle BP %**: rolling 30/90/365 天的 mean BP utilization 多少？现在 portfolio summary 显示 idle 62%，但这是 snapshot 不是历史 distribution。
- **Cross-strategy 相关性**: Q066 算过 V3-A vs Q042 的 day-overlap 0.9% — 但没算过 *PnL correlation*（只是入场 day 重叠）。组合 Sharpe 需要相关性矩阵。
- **Crisis-period combined PnL**: 2008/2020/2022 在 *current full architecture* 下整体表现如何？各策略 stress 数据是分散的，没汇总。
- **Per-strategy $/BP-day** (per feedback_strategy_metrics_pack 的 metrics pack 要求): 没有跨策略统一计算。

### 2.3 警告 — 上一轮 ROE 目标我也不记得了

PM 提到 "上一轮 ROE 目标"。我搜不到明确的 round-1 ROE 数字目标（无论是 SPEC 还是 RESEARCH_LOG）。**Q073 P0 第一步是 PM/Quant 共同 anchor 一个 round-2 目标数字** —— 不是"比 round 1 好"（因为 round 1 数字不明），而是 absolute 锚定（如 "12mo combined ann ROE ≥ X%"）。

---

## 3. Lever Space — 5 个候选维度（unweighted，请 2nd Quant 重排）

按 "推倒重来" 程度排序（不代表 ROE upside 排序）：

### Lever A — 策略矩阵本身

- **现状**: regime (3) × IV signal (3) × trend (3) → ~27 cells → 5 类策略 primitive
- **未挑战的假设**: Q041 时代决定的 axis 切法仍然是最优的
- **可质疑点**:
  - LOW_VOL regime 下没有 income 策略（idle by design） → ROE 漏点
  - HV Ladder 只是 HIGH_VOL 一个角落的策略；为何不是 NORMAL+IV LOW 的 default？
  - 5x3x3 matrix 是否过度切分 → 单 cell 样本稀薄
- **激进选项**: 推倒重新 axis (e.g., "regime + structural primitive"，去掉 IV signal axis)
- **保守选项**: 保留 matrix，补 LOW_VOL income 策略 (e.g., low-delta cash-secured put)

### Lever B — Cap 框架（SPEC-103 R1-R4）

- **现状**: R1=70% / R2=80% / R3=60% / R4=50%
- **未挑战的假设**: 默认 caps 是 Q072 P4 给的 risk-conservative 默认 (R1 from Schwab PM call 80%−10pp safety)
- **可质疑点**:
  - PROJECT_STATUS 说 19y 中 R1 cap 仅 bind 5 天 → 99.93% headroom 未使用 → ROE under-deployment
  - R3=60% combined: 阻挡同时 multi-strategy fire — 但实际历史 simultaneous fire 频次未知
  - R5 stress (70→60) 一次触发持 3 天 — 频次和 ROE 减损未量化
- **激进选项**: cap framework redesign (e.g., dynamic cap by recent realized vol)
- **保守选项**: live 1mo 后实证 bind 频次再调整

### Lever C — Idle BP fallback

- **现状**: 组合 idle ≈ 62% (recent snapshot, 不一定 representative)
- **HV Ladder 21% slot occupancy** → 79% 时间该策略 BP 完全 idle
- **SPX BPS** 在 IVP filter 关闭时 (IVP ≥ 55) 也 idle — 当前正在发生
- **未挑战的假设**: idle BP 没有 fallback 是 by-design 安全策略
- **可质疑点**: 组合 ROE = ∑ (策略 ROE × BP 部署率)。Idle 时间 ROE 贡献 = 0，但是是否能 fill 至少部分 idle？
- **激进选项**: 低 IV regime idle period 引入新 strategy primitive
- **保守选项**: idle 期不做事，接受 baseline yield 0

### Lever D — 多账户协同（Schwab + E-Trade）

- **现状**: Schwab $601k + E-Trade $293k = $894k combined NLV，combined idle 62%
- **未挑战的假设**: 两账户 mirror or default 分工是最优
- **可质疑点**:
  - 同一策略两账户 mirror = 风险无 hedge，只放大
  - SPX-only Schwab vs /ES-only E-Trade 分工 (or 反过来) 可能优化 BP 利用
  - E-Trade PM margin 规则可能与 Schwab PM 不同 → 同一仓位 BP cost 不同
- **激进选项**: 重设 per-account strategy 分工
- **保守选项**: 当前 default

### Lever E — Friction / Execution Layer

- **现状**: backtest 用 mid-quote pricing
- **未挑战的假设**: live execution 折损可忽略
- **可质疑点**:
  - Slippage on 30-DTE BPS, 49-DTE /ES put, Q042 OTM call spread 都不同
  - Commissions: Schwab vs E-Trade 不同
  - Margin financing cost on long-DTE positions
- **激进选项**: 把 friction 显式加入 ROE 模型，重新算 expected live ROE
- **保守选项**: 假设 friction 是同向噪音，不影响相对优化

---

## 4. Proposed Research Framework (Q073 P0-P5)

类 Q071 phased + stopping conditions。

### P0 — 决策标准 (PM + 2nd Quant + Quant 三方锚定)

锚定三件事：
1. **ROE 目标数字**: "12mo combined ann ROE ≥ X%" (X = ?)
2. **Risk constraint 红线**: e.g., "MaxDD ≤ 30% AND worst single-day -1d ≥ -10% NLV AND bootstrap sig ≥ 80%"
3. **Tear-down 允许程度**: 保守 / 中等 / 激进 三档（见我之前给 PM 的回复）

### P1 — Current State Measurement (诚实 attribution)

对当前完整 architecture 跑 26y 回测：
- 每个策略的 ann ROE / Sharpe / MaxDD / $/BP-day / worst trade / disaster window
- Combined 组合层面 ROE 时间序列
- BP utilization rolling distribution (mean / median / 5%-tile / 95%-tile)
- Crisis windows: 2008 / 2011 / 2018 / 2020 / 2022 portfolio-level outcome
- Cross-strategy PnL correlation matrix
- Live vs backtest delta (where available)

**P1 stopping condition**: 如果 current state 已经满足 P0 目标 → 不用优化 → 关 Q073

### P2 — Lever Sensitivity (per lever 独立 sweep)

5 个 lever 每个跑 3-5 个 variant，单 lever sensitivity:
- **A**: 替换/增删 1 个策略 cell
- **B**: R3 60→40/50/70/80, R4 50→30/40/60/70
- **C**: idle-BP fallback (3 candidate strategies)
- **D**: 多账户 strategy 分工 (mirror / split / cross-allocate)
- **E**: friction model 重新估 ROE

报告 per-lever Δ ROE / Δ MaxDD / Δ Sharpe vs baseline。

**P2 stopping condition**: 任何 lever 无 ann_roe ≥ baseline + 0.3pp 且 V1 pass → drop 该 lever

### P3 — Pareto Frontier + Architecture Candidates

P2 中胜出的 lever 组合成 1-3 套 candidate architecture：
- **Arch-1 Conservative**: lever B/D 调整 only
- **Arch-2 Moderate**: + lever C idle fallback
- **Arch-3 Radical**: + lever A 策略矩阵 redesign

### P4 — Full architecture simulation

每套 architecture 26y + stress + bootstrap + crisis windows + friction-adjusted。Full metrics pack per `feedback_strategy_metrics_pack`.

### P5 — Promote / Reject + SPEC drafts

可能产生 SPEC-104 / SPEC-105 等。**强制 2nd Quant review** 在 P3 中段（架构候选定下来）+ P5 最终。

---

## 5. Open Questions for 2nd Quant

### Q5.1 — 框架本身

是否同意 "Round 2 = portfolio-level architecture" 这个 reframe？
还是应该保留 Round 1 风格 single-strategy parameter 微调？

### Q5.2 — Top metric

ROE 作为 main objective 合适吗？还是应该用：
- Sharpe-anchored (Sharpe ≥ X 前提下 max ROE)?
- Drawdown-adjusted (Calmar / Ulcer)?
- Path-dependent (CVaR / worst rolling 3m)?

PM 明示 "ROE 是顶层"，但作为 Quant 我担心 ROE-only 鼓励 tail-leveraged 解（高均值 + 厚尾）。Quant 这边建议加 *secondary objective* 作 veto。

### Q5.3 — Lever exhaustiveness

5 个 lever 是否 exhaustive？我能想到的可能 miss 的：
- **F. 时间维度**: 持有期 / DTE 选择 (已被 SPEC-094.1 部分覆盖)
- **G. 标的多元化**: SPX / /ES / SPY / RUT / etc. — 现在只用 SPX + /ES
- **H. 期权结构创新**: butterflies / calendars / diagonals (现在没有 long-vega 策略)
- **I. PM-level macro overlay**: 大盘 macro signal (Fed, jobs) override regime

要不要加进 lever 集？

### Q5.4 — Tear-down 边界

"推倒重来" 给 2nd Quant 的 risk 是显著的（PM 主导决策但 Quant 担责数据）。是否设：
- **不可动**: SPEC-103 R1-R6 governance 框架（最近通过两轮 review）
- **可动**: 策略矩阵、cap 具体数值、idle fallback、账户分工
- 建议什么作为绝对 floor (e.g., "无论 architecture 怎么改，组合 MaxDD ≤ Q72 historical baseline")

### Q5.5 — Methodology pitfall

担心的几个：
1. **Overfitting**: 26y data + 5 lever × 3-5 variants = 大 search space → P3 候选 architecture 的 in-sample bias 怎么控?
2. **Live vs backtest gap**: backtest 优化的 architecture 在 live 还是不是 optimal? Walk-forward Q072 有先例（Spearman 0.7）但这是 cap layer，不是 strategy mix layer
3. **2nd-order effects**: 改一个 lever 会影响其他 lever 的最优值（e.g., 提 R3 cap 后 idle fallback 的最优策略可能变）— per-lever sweep 假设独立性
4. **Composability over time**: 一年内策略加上去的（HV Ladder 5/14, Q042 5/10）— 是否有足够 forward sample 来检验组合假设？或者全靠 26y historical?

### Q5.6 — 优先级

如果 budget 只够跑 P0-P2，应该先跑哪个 lever？

---

## 6. 明确不在 Q073 scope 中（避免 scope creep）

| 项 | 理由 |
|---|---|
| 新增 broker / 资金 | PM-side capital allocation 决策，不属 Quant |
| Tax-aware optimization | 个人税务复杂，缺数据 |
| Real-time intraday strategy | SPEC-030 已研究，提前率 0%（per memory）— 不重启 |
| Q072 already-rejected variants (priority allocator, static per-sleeve cap) | 已实证否决 |
| Telegram / UI 改动 | 独立 SPEC 处理 |
| Live data 累积期未到的策略 forward 重测 | 数据不足 |

---

## 7. 我的请求

请 2nd Quant 给出：

1. **PASS / REVISE / REJECT** Q073 framing & plan
2. 若 REVISE: 具体修订点（lever 增删 / methodology 改动 / metric 调整）
3. 对 Q5.1-Q5.6 open questions 的判断
4. 任何我没想到的 pitfall / blind spot
5. 是否同意 P0 三件锚定（ROE 数字 / risk constraint / tear-down 边界）需要 PM + 2nd Quant + Quant **三方** 锚定，而不是 Quant 单独

---

## 8. Why review NOW vs 跑完之后

Q071 review 是 *post-research*；2nd Quant 给出 framing 修订（rename / promote level / etc.）后 memo 已经成型，反修很麻烦。

Q073 拟做的是 *组合层面架构* — 框架错了，后续 100h 计算全废。**Q073 应该是 pre-research review 优先于 post-research review**。

如果 framing PASS / REVISE，再开始跑 P0-P5（预计 Quant ~1 周 + 2nd Quant 1 轮 mid-review at P3 + 1 轮 final at P5）。
如果 framing REJECT，不开 Q073，转向 2nd Quant 建议的替代框架。

---

**Quant Researcher 等待 2nd Quant 回复后再启动 P0。**
