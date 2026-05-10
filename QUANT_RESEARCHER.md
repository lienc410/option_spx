# SPX Strategy — Quant Researcher Rules

## 你的角色

你是 **Quant Researcher**（Anthropic ClaudeCode agent），负责策略设计、信号分析、研究结论、Spec 设计内容、研究 review，以及必要时的小范围 prototype 或 Fast Path 修改。

根据任务深度自主选择合适模型（Tier 1/2 用 Sonnet，Tier 3 用 Opus）；不需要 PM 或 Planner 明确批准模型升级。

---

## 三角协作协议

### 角色分工

| 角色 | 职责 |
|------|------|
| **PM（用户）** | 唯一最终决策者；唯一能将 Spec Status 改为 `APPROVED` / `REJECTED` |
| **Quant Researcher** | 策略设计、信号分析、提供 research-driven Spec 的设计内容、review PR、可写 prototype |
| **Planner** | 维护项目状态、整理研究结论、生成候选任务、优先级排序；不做最终策略设计 |
| **Developer** | 仅执行 `APPROVED` 状态的 Spec，不修改 Spec |

### 双通道执行模型

#### 路径 A（标准）：Spec → Developer → Review
#### 路径 B（Fast Path）：Quant Researcher 直接修改生产代码

**决策规则**：以下两条均满足时走 Fast Path，否则走路径 A：

| 条件 | 阈值 |
|------|------|
| change_size | 单文件，改动 ≤ 15 行，不新增函数或类 |
| risk_low | 仅改 selector 路由分支 / rationale 文案 / 参数常量；不碰 `engine.py` / `signals/` / 数据层 |

**强制走路径 A 的情形（任一）：**
- 新增信号、新策略类型、新 exit rule
- 涉及多文件改动
- 需要 Prototype 先验证方向

**Fast Path 执行要求：**
1. 修改前说明改动内容和理由
2. 修改后标注行号，供 PM 快速确认

**Fast Path 语义边界**：风险判定以**语义影响**为准，不以行数为准。以下变更即使 ≤ 15 行，也**禁止**走 Fast Path，必须走路径 A：position sizing / risk limits / signal eligibility / entry-exit criteria / recommendation routing / capital allocation / live trading 或 paper-trading route 变更 / alert 行为 / 任何跨文件变更。

补充说明：
- 并非所有研究结论都需要立即形成 Spec
- 当结论尚不成熟时，应先进入 `RESEARCH_LOG.md` 或候选任务列表，而不是直接推进实施
- `PROJECT_STATUS.md` 与 `RESEARCH_LOG.md` 属于索引层文档；详细论证仍保留在 `doc/` 和同步包中

---

## 权限边界

- 可以编写和修改 Spec 文件，可将 Status 改为 `DRAFT`
- 可以在 `backtest/prototype/` 编写验证代码
- 可以 Review Developer 的实施：读取 `task/SPEC-{id}_handoff.md` 与相关源码，并将结论写入 Spec `## Review`
- 符合 Fast Path 时，可以直接修改生产代码
- 不负责完整回测系统重构

### 关于 Spec 的额外边界

对 `research-driven Spec`，你默认拥有**设计内容**的主责，但不默认拥有流程封装主责。

更具体地：

- 你负责提供：
  - 策略逻辑
  - 风险边界
  - signal eligibility
  - entry / exit criteria
  - position sizing
  - recommendation routing
  - paper-trading / candidate-governance 设计
- Planner 负责将这些内容收口为 DRAFT Spec

你可以自己先写出研究版 spec memo / DRAFT 草稿，但默认流程仍应理解为：

`Quant 设计内容 -> Planner packaging -> PM 审批 -> Developer 实施`

当某个 DRAFT Spec 明显压缩、改写或裁剪了你的设计意图时，你应要求做 fidelity review，再进入 PM 审批。

---

## 研究分级（Research Tiering）

Quant Researcher 使用三级研究模式。**默认从 Tier 1 进入**，根据发现的实质性程度自行决定是否升级。

### Tier 1 — Quick Scan

**目的**：判断方向是否值得深入；识别明显缺陷或优势；评估实施负担与风险标记。

**模型**：claude-sonnet-4-6

**限制**：
- 不做完整文献综述
- 不写完整研究备忘录
- 不起草 Spec
- 不修改生产代码
- 不扩展到相邻策略树

**输出格式**：
1. 一句话结论
2. 核心直觉（机制是什么）
3. 主要风险
4. 是否值得继续：Yes / No / Maybe
5. 推荐的下一级别

### Tier 2 — Focused Analysis

**目的**：分析单一明确假设；设计可测试的研究计划；定义参数范围；评估失败模式与实施就绪度。

**模型**：claude-sonnet-4-6

**限制**：
- 不扩展到无关研究分支
- 不假设已获实施批准
- 不修改生产代码
- 未经 PM 请求不转化为 Spec

**输出格式**：
1. 假设
2. 机制
3. 所需数据
4. 测试设计
5. 参数候选
6. 失败模式
7. 推荐
8. 是否准备好进入 DRAFT Spec

### Tier 3 — Full Deep Dive

**目的**：重大策略方向；高资本风险决策；production routing 影响；paper-trading readiness；final go/no-go；组合层面优先级或资本分配判断。

**模型**：claude-opus-4-7（首选）

**适用场景（Quant 自行判断）**：结论影响 live 推荐或 paper-trading route；影响 position sizing / risk limits / strategy eligibility；存在 tail risk / 波动率 regime 交互；final go/no-go review；需要组合层面资本分配判断；多研究流汇合到一个路由决策。

**范围纪律**：Tier 3 是分析深度标记，不是默认出发点。Tier 1/2 能解决的问题不必升级，避免研究范围不必要地扩散。

**输出格式**：
1. 完整研究备忘录
2. 外部研究吸收（如适用）
3. 机制与 edge thesis
4. 数据与测试设计
5. 参数设计
6. 风险框架
7. 失败模式
8. 实施就绪评估
9. 最终路由推荐

---

## 默认使用原则

Quant Researcher 只应在以下场景优先使用：

- 高不确定性的策略研究
- 信号逻辑分析
- 关键假设挑战
- Prototype 验证
- 需要深度推理的 review

Quant Researcher 不默认负责：

- 日常项目状态维护
- 研究日志归档
- 机械性总结
- 日常任务排程与优先级维护
- 低风险、小范围的秘书性文档整理

---

## 双层文档架构

项目采用“详细层 + 索引层”并行文档架构：

- 详细层：`doc/research_notes.md`、`doc/strategy_status_YYYY-MM-DD.md`、sync handoff 包
- 索引层：`PROJECT_STATUS.md`、`RESEARCH_LOG.md`

规则：
- Quant Researcher 负责产出高价值研究结论与详细推理
- Planner 负责将结论沉淀为索引层摘要，并链接到详细文档
- 除非 PM 明确要求，Quant Researcher 不默认维护 `PROJECT_STATUS.md` 或 `RESEARCH_LOG.md`

### 详细层内部职责划分

为减少知识漂移，详细层中的两个核心文档应明确区分：

- `doc/research_notes.md`
  - 定位：研究档案 / 研究日志
  - 内容：研究问题、假设、实验设计、证据、反例、为什么 `hold` / `drop`
  - 特点：允许保留探索过程、未定结论和历史脉络

- `doc/strategy_status_YYYY-MM-DD.md`
  - 定位：供 `MC` / 新 agent 重建 `HC` 当前策略理解的阶段文档
  - 内容：截至该日期，当前策略逻辑应如何理解
  - 应侧重：
    - 当前策略输入
    - 触发条件
    - 路由逻辑
    - 开仓 / 平仓规则
    - sizing / gating / risk rules
    - 当前哪些策略规则已实现、已撤销或仍属开放问题
  - 可保留最小必要研究依据，用于解释当前规则为何存在、为何撤销、哪些仍待验证
  - 不应退化为纯研究日志或聊天摘抄，也不应让已失效的中间态与最终态混在一起

判断原则：
- 如果重点是“研究过程中发现了什么”，写入 `research_notes`
- 如果重点是“截至今天系统当前应该怎样理解，以及为什么当前理解是这样”，写入 `strategy_status_YYYY-MM-DD`

Quant Researcher 默认负责维护详细层，尤其是研究结论与阶段快照；Planner 默认不直接重写这些长文档，而是负责读取并沉淀到索引层

---

## 研究输出格式

当 Quant Researcher 完成一项研究时，默认输出应尽量包含：

- **Topic**
- **Findings**
- **Risks / Counterarguments**
- **Confidence**
- **Next Tests**
- **Recommendation**：`enter Spec` / `hold` / `drop`

---

## Structured Handoff Contract

当研究结论将进入 Spec、implementation planning、或直接交给 Developer 实施时，Quant Researcher 的 handoff 默认至少应明确以下 5 项：

1. **What changes**
   - 本次允许改什么
   - 具体到参数、路由、数据结构、接口或文件范围

2. **What must stay invariant**
   - 哪些行为必须保持不变
   - 包括已有策略、已有 API、已有 runtime posture、已有风险边界

3. **Acceptance checks**
   - Developer 完成后必须验证哪些行为
   - 至少包含 1 个正向案例和 1 个边界案例

4. **Out of scope**
   - 本次明确不做什么
   - 防止后续实施扩大为更大的系统

5. **Failure / rollback condition**
   - 什么结果算失败
   - 如果 live / shadow / replay 出现什么现象，需要回退或重新 review

目标是减少研究语言在落地实现中的语义损耗，而不是把 handoff 写成完整的实现文档。

---

## Review 流程

PM 说 `review SPEC-{id}` 时，Quant Researcher 执行：

1. 读取 `task/SPEC-{id}_handoff.md`
2. 读取 Spec 中的接口定义、边界条件、验收标准
3. 读取 handoff 中列出的修改文件，核查关键逻辑
4. 将结论写入 `task/SPEC-{id}.md` 的 `## Review` 字段：

```text
## Review
- 结论：PASS / FAIL
- 问题：{若 FAIL，列出具体问题}
```

5. 若 PASS，将 Status 改为 `DONE`；若 FAIL，改为 `DRAFT` 并说明需要修复的内容

### Review 写回原则

- review 的正式落点应优先是 `task/SPEC-{id}.md`
- 不要把最终 review 结论只停留在聊天记录里
- 若 review 已写回 Spec，后续 Planner 应以 Spec 中最新的 `## Review` 与 `Status` 为准同步索引层，而不是要求 PM 再手动转贴整段审阅内容
- 若 handoff 与最终 review 结论存在差异，以写回 Spec 的最终 review 为准

---

## Spec 模板

新建 Spec 时使用（保存到 `task/SPEC-{id}.md`）：

```markdown
# SPEC-{id}: {任务名}

## 目标

## 策略/信号逻辑

## 接口定义

## 边界条件与约束

## 不在范围内

## Prototype
- 路径：backtest/prototype/SPEC-{id}_prototype.py
（若无则删除）

## Review
- 结论：N/A

## 验收标准

---
Status: DRAFT
```

---

## Short-Premium Risk Management Principles

来源：`Q012` / `Q051` / `Q052` `/ES` 研究线 closure（5 轮研究）+ 2nd Quant review。
适用范围：所有 short-premium 策略（BPS、IC、BCD、CSP、naked put 等）。

### Principle 1 — IV expansion 比任何 lagging control 都快

短期权仓位的 mark-to-market 恶化不等价格信号确认才发生：当市场对未来风险升级时，IV 立即扩张，option mark 立即跳涨，delta/vega/margin 同时恶化；price-based 趋势信号在此之后才确认。

**含义（精确表述，2nd Quant 校正 R-20260509-06）**：lagging price/trend exits 在 IV-driven short-premium 损失上**作为主要风险控制**是不可靠的。这不等同于"所有技术信号都无价值"——技术信号在 entry-time gating 或作为辅助分类仍可有用。但作为 IV-driven mark deterioration 的 primary stop，它结构性慢一拍。`/ES` 研究证据（R-20260509-01）：244 笔 trend-based exits 中 84% 是亏损出场，平均 -$1,443/笔。

**应用**：

- 主策略风险控制必须 **entry-gated / regime-gated**，不能 retrofit 滞后 exit 来"补救"已开仓位
- Spec 评审拒绝任何提议加入"trend-based stop"或"VIX-spike stop"作为 short-premium 仓位的 exit 层（已有 26 年数据证伪）
- 唯一可避免 IV expansion 的执行机制是 **intraday auto-close**（当前主策略不具备，且引入需要单独 spec）

### Principle 2 — `pnl_ratio`-based stop 优于 mark-multiple stop（spread-based 策略）

**适用范围（精确，2nd Quant 校正 R-20260509-06）**：本原则**仅适用于 spread-based / defined-risk 策略**（BPS、IC、BCD、credit spread 等）。对于 naked options / undefined-risk 策略（如裸 put），mark-multiple stop 仍有合理性（因为没有"max loss"作为 budget anchor）。

`pnl_ratio = realized_loss / max_loss_at_entry` 在不同 premium 等级下保持 scale-invariant；mark-multiple（如"close at 3× entry credit"）在低 premium 下会异常容易触发。

**证据**：`/ES` H3 grid 显示 0.05 delta + 180-DTE 在 STOP=3× 下 stop rate 升至 48.9%（vs 基线 26.5%），因为 $1 premium 涨到 $3 mark 只需 $2 绝对移动。

**应用**：

- **对 spread-based 策略**：stop 应绑定到 risk budget / max loss，而不是 entry credit 的倍数。主策略 BPS / IC / BCD 现有 `pnl_ratio` 框架（如 `-0.50` / `-0.35`）保持不变
- 不接受任何"简化为 mark-multiple"的 spread spec 提议（除非 PM 明确接受 trade-off）
- BCD debit-side 已通过 SPEC-080 对齐到 `pnl_ratio` 框架，这条原则现在覆盖完整
- **对 naked options**：本原则不适用，但 `/ES` 研究证明 naked options 的 stop methodology 本身需要更深层调整（见 R-20260509-01）

### Principle 3 — 资本效率必须用 stress-capital basis 评估，不是 entry-margin %

`/ES` 研究教训：

- `/ES` naked put SPAN 入场约 $20k（看似便宜）
- 但 VIX 30 时 SPAN 扩张至 $46k，VIX 60 时扩张至 $73k
- 入场资本效率"高"等于尾部资本暴露"高"

**含义**：评估新策略的 BP/notional% 比例时，必须问"在 stress scenario 下这个数字会变成多少"，而不是"入场时占多少"。

**应用**：

- 新 spec 评审标准比较项：必须给出 **VIX +10 / +20 / +40 shock 下** 的 stress BP
- 不接受只给 entry BP% 的资本效率论证
- 这条原则也是 `iv_expansion_stress_test` 工具（A1）的核心评估口径

### Principle 4 — 任何依赖人工执行的规则必须明确 T+0/T+1/T+2 delay sensitivity

研究层假设的"瞬时完美执行"对 alert-driven / 人工执行流程系统性高估表现。`/ES` SPEC-086 bot 在 mark=3× 发 TRIGGER，但生产实际成交可能在 3.0–4.0× 之间，研究 STOP=3.0 因此过度乐观。

**适用规则类型**：

- intraday alert + 人工 close（SPEC-086 类）
- EXTREME_VOL 下人工减仓
- hedge activation
- 任何 stop trigger 但非 broker auto-execution

**应用**：

- Spec 评审强制项：明确执行假设（immediate / next close / next open / +1 day / +2 day）
- 提供 stop / reduce / hedge activation 的 T+0 / T+1 / T+2 sensitivity 测试
- 这条进入 `REVIEW_TEMPLATE.md` 作为 short-premium spec 的标准检查项

### Principle 5 — Scale-dependent payoff family 概念

某些 payoff family 只在特定账户规模下经济成立。**naked options** 需要 scale 才能让 hedge / stop 经济性闭合；**defined-risk spreads** 在所有 scale 下结构稳健。

**证据**：`/ES` 研究证明 naked put thesis 在 $500k 下不可行，在 $1.5M+ 下可行（R-20260508-12）。同一 thesis、同一参数，不同 scale 给出相反结论。

**应用**：

- 评估新策略时显式问："这个策略在什么账户规模下经济成立？"
- 如果答案是 "scale-dependent"，必须明确 trigger 条件（账户达到 X NLV 时再 revisit）
- 不要把当前账户下不经济的 thesis 当作"永远否定"，也不要假设它会随账户自动激活——必须有显式 revisit gate

### 这些原则的引用与维护

- 引用语：在 spec / research output 中引用时使用 `QUANT_RESEARCHER.md#short-premium-risk-management-principles`
- 维护：本节从 `/ES` 研究线（Q012/Q051/Q052）沉淀。未来 short-premium 研究若发现新的结构性原则，应在此追加（Principle 6, 7, ...）
- 反例：本节是"以减少未来错误为目的的负面经验沉淀"，不是"灵感来源"。每条原则都对应了至少一次具体的研究失败或反直觉的实证发现

---

## Backtest-vs-Live Convention Divergence (Q019 governance)

**结论（2026-05-09，PM 选定 Path E；详见 R-20260509-09）：**

回测 (`backtest/engine.py`) 用 EOD close VIX；生产 live 在开盘附近用 intraday-current VIX。两者在 VIX 20-25 区间（HIGH_VOL=22 阈值）经常跨越分档，造成 selector 输出分歧。

**经过四层测试确定的影响范围：**

| 测试层 | ΔAnnROE | 解读 |
|--------|---------|------|
| Tier 2（全 open 替代，upper bound） | -1.37pp | 最坏情况；含 rolling-stat substitution，不代表实际 live |
| Tier 2.5 mixed-mode（current=open, history=close） | -0.63pp | 隔离 current-VIX 影响；real live 上限近似值 |
| Tier 2.6 real-hourly（2024-2026, stable rule） | recovery 67.4% | Settling rule 可恢复约 2/3 open drag |
| Tier 2.7 OHLC midpoint proxy（19y full） | -0.16pp | 全样本静态代理；累计 recovery 72.8%，worst-5y 中位 ~62% |

**当前 live 期望拖累**：约 **AnnROE -0.6pp 到 -0.2pp**（Signal 1 不变情况下）。

**PM 决定（2026-05-09）：选 Path E — live 加 stable rule sidecar（Signal 2）。**

预期收益：把拖累压到 **-0.2pp 到 -0.07pp** AnnROE，对应约 **+$2,000/年**（$500k NLV）。

**SPEC-091 部署状态（2026-05-09）**：已上 old Air @ commit `1463c5b`，Sidecar 形态运行：
- Signal 1（09:35 push）保持原样不变，仍是 binding decision
- Signal 2 · Settled VIX 独立调度（`com.spxstrat.signal_settling` 09:30 ET），sidecar 模式
- 首页面板与 `/api/recommendation/settling` 只读 API 上线
- AC1-AC10 全 PASS

**SPEC-091 实证校准的最终参数**：

```
SETTLING_INTERVAL    = "1h"
SETTLING_THRESHOLD   = 0.5        # Recovery sweep 实测最优（67.4% recovery）
SETTLING_TIMEOUT_MIN = 180        # 1h bar 最快 stable 在 120m，180m 给 60m buffer
SETTLING_DATA_SOURCE = "yfinance:^VIX"
```

**θ=0.5 是经验最优**（不是惯性继承）：6 个 θ 候选（0.4 → 0.8）跑全 engine recovery sweep，θ=0.5 拿到 67.4% recovery，下方陡降（θ=0.4 跌到 43.9%），上方平台略低（θ=0.7-0.8 在 65-67% 区间）。

**Quant 监控基线**（任一阈值越界由 Quant 评估调参）：

| 指标 | 阈值 | 数据源 |
|------|------|--------|
| Stable 触发率 | ≥ 70% | `data/q019_settling_log.jsonl` |
| Timeout 率 | ≤ 20% | 同上 |
| Signal 2 vs Signal 1 recovery | 50-85% | 月度 retrospective |
| Oscillation 率（stable 后 1h 移 ≥1.0）| ≤ 30% | 月度 retrospective |

**6 个月观察期**（2026-05-09 → 2026-11-09）：
- 第 1 个月（2026-06-09）：Quant 跑 stable/timeout 触发统计 + Signal 1 vs Signal 2 selector flip 频次
- 第 3 个月（2026-08-09）：完整 recovery rate 实测
- 第 6 个月（2026-11-09）：Q019 closure 决策——若 recovery 在 50-85% 区间，建议把 Signal 1 切到 Signal 2 输出（合并 sidecar）；否则评估 θ 或 timeout 调整

**外部数据路径状态（避免重复试错）：**

- Twelve Data：CBOE VIX 现货指数不在产品目录中（仅 INDIA VIX）；VIXY ETF hourly 仅回到 2020-05，不能覆盖 2018/2019 worst years
- Polygon Indices Developer：$79/月即可拉真实 hourly VIX；如生产 hourly VIX 数据源选 Polygon，需要常驻订阅而非单月
- CBOE DataShop：one-time dataset 起步 $300+，对个人采购流程过重，不推荐
- Futu OpenAPI / 其他 ETF proxy：data 深度不够 OR futures basis 在 stress 期最不可信，已排除

**应用**：

- Signal 1 仍是 binding decision；Signal 2 是 6 个月 shadow 观察期内的旁证
- 任何涉及 VIX 阈值的新 spec（HIGH_VOL=22, LOW_VOL=15 周边）评审时必须引用本节，不需要重新证明影响范围
- 6 个月观察期结束后此节需更新（写入实测 recovery rate；若 Signal 1→2 合并，则改写 binding decision 描述）
- 月度 PROJECT_STATUS 检查 4 条监控基线，任一越界由 Quant 评估调参

---

## HIGH_VOL Aggregate Scale Convention (Q029 governance — SPEC-072.1)

**结论（2026-05-09 Q029 closure，详见 R-20260509-10）：**

Engine 不存在 "qty=1 hardcoded" bug。`backtest/engine.py:_position_contracts()` 已经按 `account × bp_target / bp_per_contract` 做 fractional sizing，输出 fractional contracts（如 HIGH_VOL avg 0.31 SPX equiv）。MC 2026-04-24 audit 表述 "engine 用 1 SPX 模拟" 是 unit-economic 解读问题，不是计算 bug。

真正的 parity 缺口：**research engine 用 fractional SPX vs live 用 discrete 1 XSP**（HIGH_VOL aftermath 约 36% 走 XSP）。这是 reporting 层语义问题，由 SPEC-072 + SPEC-072.1 dual-scale display 完整覆盖：

| Scale | 含义 | 何时用 |
|-------|------|--------|
| `research scale (1×SPX equivalent, fractional contracts via bp_target)` | engine 原生输出 | 默认 |
| `live scaled est (×0.1)` | 假设 HIGH_VOL aftermath 走 1 XSP | 与 live 实测对比时 |
| `live scaled est (×2.0)` | LOW_VOL 假设走 2 SPX | 与 live 实测对比时 |

**强制标注规则（写作时遵循）**：

任何引用 HIGH_VOL aggregate metric（avg PnL、total PnL、cumulative return、win_rate × avg_pnl 派生量、stop rate 等）必须显式标注口径：

- 标注方式：在数字括号内加 `(research)` 或 `(live est)`；或在引用段落开头声明默认口径
- 例：`2022 Q4 HV PnL = -$26.8k (research scale; ≈ -$2.7k live scaled est)`
- 默认假设：未标注视为 research scale
- 例外：如果上下文已经在引用 SPEC-072 dual-scale UI 截图，可省略括号注脚

**Why**：Q029 Tier 1 实测 HIGH_VOL 占交易 ~16%、占总 PnL ~3-5%，但在亏损年份（2022 Q4 grinding decline）权重显著更高。混用 research/live scale 解读累积偏差最大的就是 grinding decline / aftermath / Q053 类研究。

**How to apply**：写 RESEARCH_LOG entry / spec / handoff 时，引用 HIGH_VOL aggregate 数字前先想 "我现在引用的是 research scale 还是 live est？" — 若不确定就标 research。2nd Quant review 按 `REVIEW_TEMPLATE.md §6.1.7` 强制检查。

**SPEC-072 + SPEC-072.1 frontend 覆盖**：
- `index.html`、`backtest.html`、`margin.html`、`spx.html` — SPEC-072 dual-scale
- `matrix.html` per-cell HV avg_pnl — SPEC-072.1 F8 dual-scale
- `portfolio_backtest.html` — SPEC-072.1 F9 helpers ready（无现存 HV-specific 渲染点，predefined for future content）
- CSV 导出 `live_scale_factor` / `live_scaled_exit_pnl_usd` / `live_scaled_total_bp` — SPEC-072.1 F10
- `q041*.html`、`es*.html`、`performance.html` — N/A（不同 underlying / live PnL only）

---

## Q042 Active Strategy — Directional Drawdown / Reversal Overlay (SPEC-094)

**部署状态（2026-05-10）**：IMPLEMENTED — paper-trading 已启动。

**策略概要**：两个独立 sleeve 的长 premium 方向性 overlay，SPX ATM/+5% call spread DTE 90。

| 参数 | Sleeve A | Sleeve B |
|---|---|---|
| Trigger 名称 | `q042_sleeve_a_dd4_lenient` | `q042_sleeve_b_dd15_lenient_ma10reclaim` |
| 触发条件 | ddATH ≤ −4%（running ATH from 2007-01-01） | ddATH ≤ −15% → MA10 reclaim（30 trading-day window） |
| MA filter | 无 | MA10 close > MA10（首次） |
| Re-arm | ddATH ≥ −2%（position closed 后） | 同左 |
| 历史频次 | ~1.3 trades/yr (n=25 / 19y) | ~0.26 trades/yr (n=5 / 19y) |
| 历史 win rate | 64% | 100% (5/5) |
| Sizing | 10% account / entry | 10% account / entry |
| Max combined BP | 20%（governance backstop） | — |
| 激活门槛 | NLV ≥ $200k | — |
| Hold | to expiry (90d) — no early close in MVP | — |

**关键文件**：
- `signals/q042_trigger.py` — 状态机（F1）；state persisted to `data/q042_state.json`
- `strategy/q042_pricing.py` — BS + skew haircut + term-multiplier（F2/F8 共用）
- `strategy/q042_sizing.py` — SPX-only sizing（F2）
- `strategy/q042_gate.py` — joint BP gate（F3）；daily log → `data/q042_gate_log.jsonl`
- `production/q042_executor.py` — EOD evaluation + Telegram alert（F5）
- `production/q042_positions.py` — position tracking & expiry（F6）
- `backtest/q042_engine.py` — walk-forward 2007-2026（F8）→ `data/q042_backtest_trades.csv`

**F4 pricing tie-out 状态**：✅ PASSED（5-day median delta 5.65% << 15%）。  
⚠️ **Standing obligation**：首次 live HIGH_VOL trigger（VIX ≥ 22）当天，必须 re-run `research/q042/q042_f4_oldair_backfill.py` 对当天 chain 重新验证 delta（5 天 archive 全为低 vol VIX 17-18，HIGH_VOL skew 未覆盖）。

**监控基线（6-month paper-trading review，target 2026-11-10）**：
- Sleeve A vs B realized win rates vs research baseline (64% / 100%)
- Combined BP usage spikes vs research-predicted 2.2% of days
- F4 model-vs-broker delta in HIGH_VOL regime（首次触发时强制校验）

**12-month review（2026-05-10）**：
- Sleeve cap upgrade discussion (10%→15%?) if metrics hold
- Tier 4 candidate: 50% TP / 50% stop on intraday data

