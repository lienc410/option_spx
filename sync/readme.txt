Sync 导航

本目录用于 HC 和 MC 两套环境之间的同步。

当前采用的规则分两层：

1. 正式协作协议
- `AGENTS.md`
- `DEVELOPER.md`
- `PLANNER.md`
- `QUANT_RESEARCHER.md`
- `sync/hc_to_mc/MC_CLAUDE_INSTRUCTIONS.md`

2. 双层文档架构
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`
- 详细证据仍保留在 `doc/` 和各类 sync 包中

同步维护责任：

- `Planner` 负责 HC / MC 同步流程的日常维护
- `Quant Researcher` 负责提供研究内容与判断
- `PM` 负责最终拍板与 canonical 决策
- `Developer` 仅在同步结果形成 `APPROVED Spec` 后参与

使用方式：

- HC 工作期：
  使用正式协议文件处理研究、Spec、review 和 return 包
- MC 工作期：
  使用 `sync/hc_to_mc/MC_CLAUDE_INSTRUCTIONS.md` 产出 scan-friendly handoff
- 需要快速重建项目状态时：
  先看 `PROJECT_STATUS.md`
- 需要快速检索研究结论时：
  先看 `RESEARCH_LOG.md`
- 需要完整上下文、表格、案例和历史推导时：
  看 `doc/research_notes.md`、`doc/strategy_status_YYYY-MM-DD.md` 和具体 sync 包

说明：

- 本文件现在是导航页，不再维护旧版分工说明正文
- 若正式协议与旧 sync 习惯存在冲突，以正式协议文件为准
- 若需要可直接复制的常用 prompt，请统一查看仓库根目录 `PROMPTS.md`
