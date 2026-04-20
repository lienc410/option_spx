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

## 角色分工

- **PM（用户）**：唯一最终决策者；唯一能将 Spec Status 改为 `APPROVED` / `REJECTED`
- **Quant Researcher**：负责策略设计、信号分析、研究结论、Spec 草案、研究 review
- **Planner**：负责维护项目状态、整理研究结论、生成候选任务与优先级建议；不做最终策略设计
- **Developer**：负责将已批准的 Spec 转化为生产代码；只执行，不设计
- **Server Maintainer（Codex on old Air）**：负责 old Air runtime 的健康检查、日志排查、服务重启与低风险运维；不做 quant 研究、不做产品设计、不自行修改 secrets 或策略逻辑

角色专属规则见：
- `DEVELOPER.md`
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

---

## Spec 文件规范

- 位置：`task/SPEC-{三位数编号}.md`
- 每个任务一个文件，编号唯一
- 历史记录：`task/strategy_spec.md` 为旧格式存档（SPEC-001 ~ SPEC-003）
- 状态取值：`DRAFT` / `APPROVED` / `REJECTED` / `DONE`
- `Status: APPROVED` 是进入 Developer 实施的唯一入口

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

## 决策与边界

- PM 是唯一最终拍板者
- Planner 不替 PM 修改 Spec 状态
- Developer 不越过 `APPROVED Spec` 自行实现
- Quant Researcher 不把“研究有趣”直接等同于“应该进入实现”

---

## 项目状态与研究沉淀文件

- `PROJECT_STATUS.md`：当前项目阶段、模块状态、主要瓶颈、最高优先级事项
- `RESEARCH_LOG.md`：研究主题、核心结论、风险、置信度、下一步验证建议
- `sync/open_questions.md`：未解决问题、阻塞项、待验证假设
