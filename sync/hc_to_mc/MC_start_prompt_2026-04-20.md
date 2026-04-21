# MC Start Prompt — 2026-04-20

请作为 Claude Quant 工作。

先读取：
- `sync/hc_to_mc/MC_CLAUDE_INSTRUCTIONS.md`
- `sync/hc_to_mc/HC_return_2026-04-20.md`
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`

如需补详细层，再读取：
- `doc/strategy_status_2026-04-20.md`
- `doc/system_status_2026-04-20.md`

然后输出：

1. 当前项目状态（不超过 10 条）
2. 当前最高优先级事项是什么
3. 哪些事项已经是生产事实，不应再误判为 open question
4. `Q020` 的真实问题是什么，它和 `Q018 / SPEC-066` 的关系是什么
5. `Q019` 当前为什么还只是 research only
6. 如果今天只推进一个方向，你建议优先：
   - `/ES` 的 `Q013`
   - `Q020`
   - `Q019`
   并说明理由

额外要求：
- 不要把 `Q018` 当成仍待拍板的问题
- 不要把 `Q020` 误写成 “SPEC-066 已被推翻”
- 不要把 `Q015 / Q017` 当成仍未落地的研究项
- 如果你认为某处存在 HC 文档漂移，请明确指出文件与冲突点
