# SPX Strategy — Shared Agent Rules

## 项目阶段

本项目当前处于 **稳定阶段 / 研究驱动阶段**：

- 理论研究、策略判断、优先级选择的占比高于纯编码实现
- 并非所有研究结论都会立即进入 `APPROVED Spec -> 实施`
- 项目采用“研究 / 规划 / 实施”三层协作，而非仅“Spec -> 实施”

---

## Runtime Canonical Host

当前 live runtime 已迁移到 **old Air**（Early 2015 MacBook Air, 8GB RAM）。

这意味着：

- `Telegram bot` 的 canonical running instance 在 old Air
- `Flask web dashboard` 的 canonical running instance 在 old Air
- `Cloudflare Tunnel` 的 canonical running instance 在 old Air
- 主力机不再是 live runtime source of truth

协作规则：

- 需要查看 live recommendation、public web、bot health、runtime log 时，应优先读取 old Air
- 主力机主要用于开发、研究、规划、重回测，不应假定其本地缓存等于 live 状态
- 若 live 行为与主力机本地结果不一致，以 old Air 运行为准
- 无需默认启动独立的 server maintainer agent；涉及 old Air 的任务，可由当前角色直接 SSH 到 old Air 执行
- 所有涉及 old Air 的操作，都遵守 `SERVER_RUNTIME.md` 和 `doc/old_air_server_maintainer.md`

相关文档：

- `SERVER_RUNTIME.md`
- `doc/old_air_server_maintainer.md`

---

## 角色分工与模型分配

| 角色 | Agent 类型 | 默认模型 | 升级条件 |
|---|---|---|---|
| **PM（用户）** | 人类 | — | 唯一最终决策者 |
| **Planner** | OpenAI Codex | Codex-GPT-5.4 | 仅在策略路由有重大歧义时升级 |
| **Quant Researcher** | Anthropic ClaudeCode | claude-sonnet-4-6 | claude-opus-4-7（Tier 3 或 PM / Planner 明确批准） |
| **Developer** | OpenAI Codex | Codex-GPT-5.5 | 默认实施模型 |
| **2nd Reviewer / PM Audit** | OpenAI | GPT-5.5 Thinking | 按需，独立挑战与决策审计 |
| **Server Maintainer** | 由 Developer 兼任 | Codex-GPT-5.5 | 非独立 agent，不在 old Air 本地运行，通过 SSH 操作 |

**模型路由原则**：按错误成本、推理深度、可逆性、实施风险分配，不按角色声望分配。

**Server Maintainer 说明**：Server Maintainer **不是独立 agent**，由 Developer 兼任，通过 SSH 连接 old Air 执行运维操作（健康检查、日志排查、服务重启）。涉及代码修改时必须走 Developer 路径，不在 old Air 本地做策略逻辑或代码变更。

角色专属规则见：
- `DEVELOPER.md`（含 Server Maintainer via SSH 规则）
- `PLANNER.md`
- `QUANT_RESEARCHER.md`
- `doc/old_air_server_maintainer.md`

兼容说明：
- `CLAUDE.md` 是 `QUANT_RESEARCHER.md` 的兼容入口

---

## 三通道执行模型

- **路径 A（标准）**：Spec → Developer 实施 → Quant Researcher Review
- **路径 B（Fast Path）**：Quant Researcher 直接修改小范围低风险生产代码
- **路径 C（研究 / 规划）**：Quant Researcher 输出研究结论 → Planner / PM 整理优先级与项目状态 → PM 决定是否进入 Spec

说明：
- 路径 C 不直接触发生产代码修改
- 并非所有研究结论都需要立即形成 Spec
- 只有当 PM 将任务写入 `task/SPEC-{id}.md` 且设为 `Status: APPROVED` 后，Developer 才开始实施

Fast Path 适用于单文件、≤ 15 行、仅改 selector 路由分支或参数常量的低风险变更。此类变更默认不要求先经过 Developer。

**Fast Path 语义边界**：风险判定以**语义影响**为准，不以行数为准。以下变更即使 ≤ 15 行，也**禁止**走 Fast Path，必须走路径 A：

- position sizing / risk limits
- signal eligibility / entry-exit criteria
- recommendation routing logic
- capital allocation 规则
- live trading 或 paper-trading route 变更
- alert 行为
- 任何跨文件变更

---

## L3-lite 协作原则

当前项目默认采用 **L3-lite** 协作方式：

- **Planner 是默认入口**
- Quant Researcher 和 Developer 不作为默认第一入口
- PM 仍保留最终拍板权
- Planner 负责路由、收缩范围、整理上下文和生成“下一棒可转发 prompt”
- Planner 不替 Quant 做研究判断，不替 PM 做最终结论，不替 Developer 定义超出 Spec 的实现

这意味着：

- 新问题、新方向、新 blocker，默认先给 Planner
- Planner 判断下一步属于：
  - `research only`
  - `ready for DRAFT Spec`
  - `ready for implementation`
  - `runtime maintenance`
- Planner 输出结构化结果，并尽量附上 PM 可直接转发给下一个角色的 prompt

### Quant 通道特殊规则

为避免研究偏航，Quant 通道采用 **保真优先** 原则：

- 不为了极简而删除 PM 的关键研究背景、例子、反例或边界
- 可压缩的是无关噪音、重复状态说明、与本次研究无关的 blocker
- 不可压缩的是 PM 的原始研究意图、异常样本、风险偏好和决策边界

目标不是“最短 prompt”，而是：

- 不显著增加 Quant token 消耗
- 不因过度压缩而让 Quant 走错研究方向

### Quant Prompt Compression Guardrail

当 Planner 为 Quant Researcher 整理 prompt 时，以下内容默认 **不可压缩、不可省略、不可改写语义**：

- PM 的原始研究问题
- PM 明确点名的异常样本、反例、特定日期或 case
- 当前决策边界
- 已知 blocker / dependency
- 明确的风险偏好或 downgrade / rollback 条件
- 本轮明确 **不在范围内** 的事项

允许压缩的只有：

- 重复状态说明
- 与本轮无关的历史背景
- 已在索引层稳定存在、且不影响本轮结论的上下文

---

## Spec 文件规范

- 位置：`task/SPEC-{三位数编号}.md`
- 每个任务一个文件，编号唯一
- 历史记录：`task/strategy_spec.md` 为旧格式存档（SPEC-001 ~ SPEC-003）
- 状态取值：`DRAFT` / `APPROVED` / `REJECTED` / `DONE`
- `Status: APPROVED` 是进入 Developer 实施的唯一入口

### Spec Draft Ownership

Planner 负责 **DRAFT Spec packaging**，但**不拥有独立的设计权**。

Spec 的设计内容必须来自合适的上游来源：

- **Quant Researcher**
  - 策略逻辑
  - 风险边界
  - signal eligibility
  - entry / exit criteria
  - position sizing
  - recommendation routing
  - paper-trading / candidate-governance 设计
- **Developer**
  - 实现设计
  - refactor 边界
  - test harness
  - logging / dashboard / data-pipeline 设计
  - runtime-safe engineering choices
- **PM**
  - 最终优先级
  - 批准 / 否决
  - 风险接受

Planner 可以：

- 识别任务类型
- 指出设计输入缺失
- 识别矛盾、scope creep 和 open questions
- 将设计内容收口为 `task/SPEC-{id}.md`
- 维护项目状态与索引层同步

Planner 不得独立发明：

- 策略逻辑
- 风险限额
- signal eligibility
- position sizing
- 生产 recommendation 行为

### Spec 类型

本项目默认区分两类 Spec：

- **research-driven Spec**
  - 新策略
  - 新 signal
  - risk logic
  - position sizing
  - recommendation routing
  - paper-trading route
  - overlap validation
  - 设计源头默认来自 Quant Researcher

- **engineering-driven Spec**
  - refactor
  - logging
  - test harness
  - dashboard improvement
  - config cleanup
  - runtime reliability
  - data pipeline improvement
  - 设计源头默认来自 Developer（必要时带 Server Maintainer 语境）

### DRAFT Review Rule

- 对 **research-driven Spec**：
  - 若 Planner 只是忠实收口既有 Quant 结论，默认不强制重复 review
  - 若 DRAFT 对设计意图做了实质性裁剪、风险较高、或 PM 明确要求，则应由 Quant Researcher 在 PM 审批前做 fidelity review

- 对 **engineering-driven Spec**：
  - 若实现边界、runtime blast radius、或 feasibility 不明显，则应由 Developer 在 PM 审批前做 feasibility review

---

## 双层文档架构

项目采用“详细层 + 索引层”并行文档架构。

### 详细层

用途：
- 保留完整研究背景、实验设计、证据、表格和历史脉络

典型文件：
- `doc/research_notes.md`
- `doc/strategy_status_YYYY-MM-DD.md`
- `research/strategies/.../*.md`
- sync handoff / return 包

### 索引层

用途：
- 快速重建项目状态
- 快速检索研究结论
- 减少高成本模型和 PM 反复阅读长文档的成本

核心文件：
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`

规则：
- Quant Researcher 负责产出高价值研究结论与详细推理
- Planner 负责将结论沉淀为索引层摘要，并维护同步整理
- Developer 仅在相关要求已经写入 `APPROVED Spec` 时，按 Spec 接触或更新这些文件

---

## Quant 研究分级

Quant Researcher 使用三级研究模式。默认从 Tier 1 进入，Planner 或 PM 明确批准后才升级。

| 级别 | 目的 | 默认模型 | 典型输出 |
|---|---|---|---|
| **Tier 1 — Quick Scan** | 判断方向是否值得深入；识别明显缺陷或优势 | claude-sonnet-4-6 | 一句话结论 + 核心直觉 + 主要风险 + 是否继续 |
| **Tier 2 — Focused Analysis** | 分析单一假设；设计测试方案；定义参数范围与失败模式 | claude-sonnet-4-6 | 假设 + 机制 + 测试设计 + 失败模式 + 推荐 |
| **Tier 3 — Full Deep Dive** | 重大策略方向；高资本风险决策；production routing；paper-trading readiness；final go/no-go | claude-opus-4-7（首选） | 完整研究备忘录 + 风险框架 + 实施就绪评估 + 路由推荐 |

**Tier 3 触发规则**：PM 或 Planner 必须明确批准。Quant 可以建议升级，但不得自行升级至 Tier 3。

详细分级规则与 Opus 用量规则见 `QUANT_RESEARCHER.md`。

---

## Spec Entry Discipline

- `Status: DRAFT` **不是**实施许可
- 只有 PM 能将 Spec 状态改为 `APPROVED` 或 `REJECTED`
- Developer 只在 Spec 文件存在且 `Status: APPROVED` 时才开始实施
- Developer 若发现需求缺口，应停止并报告，不得自行扩展 Spec 范围

---

## Review Conflict Arbitration

当不同角色的 review 结论发生冲突时，按问题类型确定默认权重，最终由 PM 裁决：

- **策略逻辑 / 路由 / 风险边界 / candidate tiering**
  - Quant Researcher 权重更高
- **实现正确性 / 回归风险 / runtime 安全 / deploy blast radius**
  - Developer 权重更高
- **上下文是否充分 / 是否需要升级模型 / 下一棒路由**
  - Planner 权重更高
- **是否进入 Spec / 是否 APPROVED / 是否上线**
  - PM 为唯一最终裁决者

若出现冲突，输出应尽量显式写出：

- 争议点是什么
- 属于哪一类问题
- 默认仲裁权重归属谁
- 还缺什么证据
- 是否需要 PM 拍板

---

## 决策与边界

- PM 是唯一最终拍板者
- Planner 不替 PM 修改 Spec 状态
- Developer 不越过 `APPROVED Spec` 自行实现
- Quant Researcher 不把”研究有趣”直接等同于”应该进入实现”
- Quant Researcher 不自行升级至 Tier 3，不在未获 APPROVED Spec 的情况下修改生产代码（Fast Path 定义的例外除外）

---

## 项目状态与研究沉淀文件

- `PROJECT_STATUS.md`：当前项目阶段、模块状态、主要瓶颈、最高优先级事项
- `RESEARCH_LOG.md`：研究主题、核心结论、风险、置信度、下一步验证建议
- `sync/open_questions.md`：未解决问题、阻塞项、待验证假设
