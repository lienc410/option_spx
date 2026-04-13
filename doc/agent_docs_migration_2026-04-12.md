# Agent Docs Migration — 2026-04-12

## 目的

本说明记录 2026-04-12 对项目角色文档结构的重组，避免后续在看到旧文件名或旧角色称呼时产生混淆。

---

## 本次调整

原先的角色说明存在两个问题：

- `AGENTS.md` 同时承载共享规则和 Developer 专属规则
- `CLAUDE.md` 实际描述的是 Claude 在本项目中承担的 Quant Researcher 角色，而不是通用的“Claude 模型说明”

因此本次调整改为：

- `AGENTS.md`
  - 只保留共享规则
  - 包括：项目阶段、角色分工、三通道执行模型、Spec 规范、双层文档架构、共享边界

- `DEVELOPER.md`
  - 只保留 Developer 专属规则
  - 包括：只处理 `APPROVED Spec`、权限边界、歧义上报、hook / handoff 要求

- `PLANNER.md`
  - 保留 Planner 专属规则
  - 并统一术语为 `Quant Researcher / Developer`

- `QUANT_RESEARCHER.md`
  - 承接原 `CLAUDE.md` 的研究角色规则
  - 用角色名而不是模型名表达职责

- `CLAUDE.md`
  - 保留为兼容入口
  - 仅提示：本项目中 Claude 对应 Quant Researcher，请改读 `QUANT_RESEARCHER.md`

---

## 新旧映射

| 旧入口 | 新入口 |
|------|------|
| `AGENTS.md`（共享 + Developer 混合） | `AGENTS.md` + `DEVELOPER.md` |
| `CLAUDE.md`（Claude 实际承担 Quant 角色） | `QUANT_RESEARCHER.md` |
| `Codex` | `Developer` |
| `Claude`（在当前正式协议语境中） | `Quant Researcher` |

说明：
- 在历史文档、旧 sync 包、旧研究记录中仍可能出现 `Claude` / `Codex`
- 这些表述多数保留为历史语境，不强行回改

---

## 当前正式入口

当前建议作为正式入口使用的文件：

- `AGENTS.md`
- `DEVELOPER.md`
- `PLANNER.md`
- `QUANT_RESEARCHER.md`

若只看工作流入口，则优先看：

- `DAILY_WORKFLOW.md`
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`

---

## 本次未改动的内容

为避免历史失真，本次**没有**系统性回改以下内容：

- `doc/markdown_agents_v1/`
- `doc/markdown_agents_v2/`
- 旧 sync handoff / return 包
- 历史研究记录、旧 system status / strategy status 文档

这些文件若出现旧角色名，应理解为：

- `Claude` ≈ `Quant Researcher`
- `Codex` ≈ `Developer`

---

## 使用建议

若后续新增角色说明文件，建议继续遵循以下原则：

- 共享规则放 `AGENTS.md`
- 角色专属规则放对应角色文档
- 文件名优先表达“角色”，而不是“模型名”

这样可以减少模型替换、角色扩展或多代理协作时的命名混乱。
