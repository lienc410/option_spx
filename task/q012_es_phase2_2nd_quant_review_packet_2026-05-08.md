# Q012 — `/ES` Phase 2 DTE Ladder 2nd Quant Review Packet

- Date: 2026-05-08
- Prepared by: Quant Researcher
- Audience: 2nd Quant (independent review)
- Topic: `/ES` Short Put Phase 2 DTE Ladder — 诚实口径重跑结果与 thesis 存活性判断
- Current branch state: Phase 2 re-run complete under new production-aligned parameters；bootstrap 显著性消失；需要独立 review

---

## 1. Review Request

请就以下核心判断给出独立意见：

> 在当前诚实参数口径下（STOP_MULT=3.0，每槽 1 合约），Phase 2 DTE Ladder 的 bootstrap 显著性消失，但方向指标（WR、MaxDD、avg P&L）在 filtered vs baseline 的对比中仍然一致。这是否足以维持 `/ES` thesis？还是说这个结果在结构上已经足以否定？

我们 **不** 是在请求：

- 重开广泛的参数扫描或 delta/DTE 变体研究
- 重新定义 `/ES` 的 alpha 目标
- 评价 SPEC-061 / SPEC-086 / SPEC-088 等已实施内容

我们 **是** 在请求：

1. 独立评估 bootstrap 显著性消失的原因是否如 Quant 判断（STOP_MULT 过保守 + 1 合约规模限制），还是有其他解读
2. 独立判断 STOP_MULT=3.5 sensitivity study 的研究价值
3. 独立判断当前结果是否足以维持"Phase 4 BSH payoff 是 thesis 终局验证"的判断
4. 给出明确结论：`thesis alive`、`thesis alive with conditions`、还是 `thesis structurally denied`

---

## 2. 背景与项目定位

### 2.1 整体项目目标

PM 的账户级目标是：

> reasonably maximize account-level ROE（合理最大化账户层 ROE）

"合理"当前意味着：
- 保留回撤纪律
- 避免不可接受的尾部集中
- 优先统计可重复的 alpha，不推进信号丰富但脆弱的策略
- 当前 `/ES` 分配为 1 合约 / 单槽，总 BP 约 4% NLV（$500k 账户）

### 2.2 `/ES` 在组合中的定位

当前生产状态：
- `SPEC-061 DONE`：`/ES` short put 最小生产单元（1 合约，45 DTE，Δ0.20，trend filter）
- `SPEC-086 DONE`：`/ES` credit stop bot alerting（WARNING ≥2×，TRIGGER ≥3×）
- `SPEC-088 DONE`：stressed-SPAN visibility 监控面板（Q012 Phase A A2 模型）

研究判断（Q012 Phase C）：
- 在当前 1 合约规模下，任何治理架构对账户层 ROE 的边际影响约 ±0.01pp
- `/ES` 与 SPX Credit 的日收益 Pearson r = -0.028（接近零相关）
- `/ES` 当前规模太小，governance 复杂度不值得；visibility 层（SPEC-088）是正确的当前下一步

### 2.3 本次 Phase 2 研究的触发原因

前端 `/es-backtest` 页面显示当前 Phase 1 hybrid filtered 结果：
- Sharpe ≈ 0.00，ROE ≈ -0.11%

这触发了一个判断问题：**当前的差结果否定了什么？**

原始研究（RESEARCH_LOG.md / spec.md）中，Phase 2 DTE ladder（旧参数）曾显示 bootstrap [+30,+276]（显著）。因此本轮重跑 Phase 2 以验证在新诚实参数下是否保持显著。

---

## 3. 参数变化对比（关键）

本次重跑与原始研究的参数差异：

| 参数 | 原始研究 | 本次重跑 | 变化说明 |
|------|---------|---------|---------|
| `STOP_MULT` | 4.0 | **3.0** | 与 SPEC-086 bot trigger 对齐（mark=3× entry）|
| 每槽合约数 | `_contracts(equity, 5%, ...)` ≈ 0.4–4.0 浮动 | **固定 1 合约/槽** | 与 SPEC-061 production rule 对齐 |
| DTE slots | `[21,28,35,42,49]` | 同 | 不变 |
| `TARGET_DELTA` | 0.20 | 0.20 | 不变 |
| `PROFIT_TARGET` | 0.10（+90% profit） | 0.10 | 不变 |
| `GAMMA_DTE` | 5 | 5 | 不变 |
| 回测窗口 | 2000–present | 2000–present | 不变 |
| Pricing | BS mid-price | BS mid-price (Phase 2) | 不变 |

**STOP_MULT 的语义说明**（请 2nd Quant 特别注意）：

| STOP_MULT | 止损时 mark 水平 | 单笔损失 | 对应标签 |
|-----------|----------------|---------|---------|
| 3.0 | mark = 3× entry | 亏损 = 2× credit | "2× credit loss" |
| 4.0 | mark = 4× entry | 亏损 = 3× credit | "3× credit loss" |

原始研究标注"-300% credit stop"，实际使用 STOP_MULT=4.0（mark=4×）。  
SPEC-061 标注"-300% credit stop（3× 权利金）"，实际使用 mark=3×（对应 2× credit loss）。  
这是一个命名不一致问题，本次重跑采用 SPEC-061 的生产语义（mark=3×，STOP_MULT=3.0）。

---

## 4. Phase 2 重跑结果

### 4.1 核心数值对比

**新参数（STOP_MULT=3.0，1 合约/槽）：**

| 指标 | baseline | filtered | filtered-baseline Δ |
|------|---------|---------|---------------------|
| 交易数 | 2,209 | 1,383 | -826 |
| Win rate | 74.1% | **75.5%** | +1.4pp |
| Stop rate | 23.4% | **21.5%** | -1.9pp |
| Avg P&L / trade | $37 | **$110** | +$73 |
| Total P&L | $81,722 | **$151,933** | +$70,211 |
| Ann ROE | 0.66% | **1.08%** | +0.42pp |
| Max Drawdown | -59.8% | **-29.2%** | +30.6pp |
| Sharpe | 0.139 | **0.157** | +0.018 |
| Bootstrap mean | $37 | **$110** | — |
| Bootstrap CI | `[-128, +86]` | `[-113, +270]` | — |
| Bootstrap 显著 | **No** | **No** | — |

**原始研究结果（参考，旧参数）：**

| 指标 | baseline | filtered |
|------|---------|---------|
| Ann ROE | 1.3% | 1.2% |
| Max DD | -38.5% | -23.3% |
| Sharpe | 0.16 | 0.20 |
| Bootstrap CI | `[-33,+238]` | **`[+30,+276]`** ✅ |
| 显著 | No | **Yes** |
| PM 校正后 CI | — | **`[+47,+393]`** ✅ |

### 4.2 PnL 分布特征

- 最小单笔 PnL（1 合约）：-$18,226（约 -3.6% NLV）
- 最大单笔 PnL：+$6,907
- 分布明显左尾偏斜（裸 put 结构性特征）

### 4.3 Bootstrap 参数

- 方法：block bootstrap（避免时序自相关）
- Block size：filtered = 345 天（≈1.4 年），baseline = 552 天
- Bootstrap 次数：2000
- 显著性标准：CI 下界 > 0

---

## 5. Quant 初步判断（供 2nd Quant 挑战）

### 5.1 显著性消失的机制解释

**解释 A（Quant 倾向）：STOP_MULT 是主要 driver**

从 4.0 → 3.0，止损点提前了 25%。在 2008、2020 等极端窗口：
- put 迅速到达 3× mark
- 以 STOP_MULT=3.0 被止损
- 若持有到 4× 有些可能会反弹

结果：stop rate +5.5pp（16% → 21.5%），每个 stop 的损失较小但频率更高，拉低均值、放大方差，CI 下界从 +30 拉到 -113。

上界几乎不变（+276 → +270），说明好的 trade 没有被改变——只是坏的 trade 分布变了。

**解释 B（待 2nd Quant 评估）：1 合约规模是主要 driver**

旧研究在低 SPX 年代（2000–2010，SPX ≈ 1000–1500）每槽可做约 3–5 合约（BP 每合约约 $3–5k），产生足够多的 PnL 信号。1 合约固定后，低 SPX 年代的 per-trade PnL 从 $200–400 降到 $40–80，信噪比大幅下降。

**解释 C（待 2nd Quant 评估）：两者共同作用，无法分离**

STOP_MULT 变化影响坏 trade 的分布，1 合约变化影响所有 trade 的 PnL 规模。两者叠加，无法从现有结果单独归因。

### 5.2 "研究 stop 是否过于保守"的争议

**倾向于用 3.0 的理由**：
- 与生产 bot（SPEC-086）trigger 一致
- "诚实口径"的要求是参数与生产对齐

**倾向于用 3.5 或 4.0 的理由**：
- 生产 bot TRIGGER 只是发出 alert，不自动平仓
- PM 人工执行时，实际平仓点在 3.0–4.0× 之间
- 用 3.0 等于假设 PM 在 alert 瞬间完美执行，这是过于理想化的 best-case execution
- 更现实的研究 stop 应该是 3.5 左右（alert 后一天内人工平仓的典型 mark 水平）

Quant 判断：这不是研究应当人为拔高 STOP_MULT，而是研究的 stop 应该建模的是**实际成交行为**，而不是 alert 阈值本身。3.5 作为 sensitivity study 有研究合理性。

### 5.3 BSH 是否是 thesis 的必要条件

Phase 4 原始结果（旧参数，filtered）：

| 指标 | P3 cost-only | P4 BSH payoff |
|------|-------------|--------------|
| Ann ROE | 0.0% | 1.3% |
| Sortino | 0.05 | **0.98** |
| 最小净值/起始 | 57.3% | **64.0%** |
| 最终净值 | $501k | **$699k** |

Quant 判断：**BSH payoff 从根本上改变了损失分布**——将裸 put 的高方差左尾（每次 stop = 大单笔损失）转变为"有 BSH 对冲的受控尾部"。这正是 Phase 2 统计不显著的对应解药：用 BSH 在尾部事件中产生大额正 PnL，对冲并压缩裸 put 的 stop 损失，使整体分布向正偏移动。

若该判断成立，那么 **Phase 2 统计不显著是结构性的，在没有 BSH 的情况下，单靠裸 put 的 theta 无法在 26 年的 bootstrap 中稳定产生显著 CI**。Thesis 的可验证形式是完整三层体系（Phase 4），不是单独的 Phase 2。

### 5.4 方向指标的一致性

尽管 bootstrap 不显著，以下方向一致，且具有研究意义：

- Trend filter 将 MaxDD 从 -59.8% → -29.2%（改善 30.6pp）
- Trend filter 将 stop rate 从 23.4% → 21.5%（-1.9pp）
- Trend filter 将 avg P&L 从 $37 → $110（+$73，+197%）
- Trend filter 将 Ann ROE 从 0.66% → 1.08%（+0.42pp）

这些改善在方向上与原始研究的 Phase 2 结论一致，支持"trend filter 作为 risk-control gate 有效"的判断。

---

## 6. 具体请 2nd Quant 回答的问题

**Q1（显著性）**：  
Phase 2 filtered bootstrap CI `[-113, +270]` 下界为负，均值 $110。你如何读这个结果？  
- 是"strategy lacks alpha at this scale"？  
- 是"sample noise dominates at 1-contract level"？  
- 还是"stop parameter creates structural statistical artifact"？

**Q2（STOP 参数）**：  
Quant 建议做 STOP_MULT 3.0 / 3.5 / 4.0 sensitivity study，理由是生产里 bot→人工执行会有 mark 漂移。  
你认为这个研究方向合理吗？还是认为应该 lock STOP=3.0 并接受结果？

**Q3（BSH 作为必要条件）**：  
Quant 判断：Phase 2 的统计弱结果在裸 put 结构下是"结构性"的，BSH payoff 才是让统计质量达到显著水平的关键。  
你是否同意？如果同意，应该直接推进 Phase 4 在新参数下的重跑吗？

**Q4（1 合约 sizing 限制）**：  
当前 1 合约 / 槽是 SPEC-061 的生产约束，不是研究假设。如果账户扩张或 PM 允许 2 合约/槽，是否值得评估放松这个约束对 bootstrap 的影响？还是认为研究应该严格对齐生产约束？

**Q5（最终 routing 判断）**：  
基于以上，你对 `/ES` thesis 的判断是：  
- (A) `thesis alive`：继续推进，按 Quant 建议做 sensitivity + Phase 4 重跑  
- (B) `thesis alive with conditions`：thesis 成立，但条件是完整三层体系（Phase 4 with BSH），当前单独 Phase 2 不是有效验证形式  
- (C) `thesis structurally denied`：当前证据足以否定，停止进一步研究

---

## 7. 源材料索引

| 文件 | 内容 |
|------|------|
| `research/strategies/ES_puts/spec.md` | 完整 `/ES` 研究结论，含 Phase 1–4 原始结果 |
| `research/strategies/ES_puts/research_notes.md` | 研究复现指南，参数语义，误读防范 |
| `research/strategies/ES_puts/backtest.py` | 唯一代码真源；Phase 2 n=2209/1383 trades |
| `strategy/es_params.py` | 生产参数单一来源（STOP_MULT=3.0，n_contracts=1）|
| `task/SPEC-061.md` | 最小生产 cell；BP 上限 20% NLV；单槽 1 合约 |
| `task/SPEC-086.md` | bot alerting；WARNING ≥2×，TRIGGER ≥3× |
| `research/q012/phase_c_joint_simulation.py` | Phase C 联合仿真；当前 1 合约 ROE 贡献 ≈ ±0.01pp |
| `RESEARCH_LOG.md` → R-20260508-01 等 | 项目最新索引 |

---

## 8. 明确不在范围内

本次 review 不需要评价：

- SPEC-061 / SPEC-086 / SPEC-088 的实施合理性（已 DONE）
- Q050 portfolio-level shared-BP governance 框架（独立研究道）
- `/ES` 与 Q041 的三方 BP 分配问题
- DTE ladder 以外的变体（如 0.15 delta、30 DTE 等）
- 生产路径的技术实现细节

---

## 9. 建议输出格式

请针对 Q1–Q5 逐项给出判断，最后给出 A/B/C 之一的 routing verdict，以及如果推进应该做的最小下一步。

如果你认为某个 Quant 判断存在方法论问题（如 bootstrap block size 选取、stop 参数选取逻辑），请明确指出。
