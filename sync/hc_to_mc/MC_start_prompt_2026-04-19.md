# MC Start Prompt — 2026-04-19

请作为 Claude Quant 工作。

先读取：
- `sync/hc_to_mc/MC_CLAUDE_INSTRUCTIONS.md`
- `sync/hc_to_mc/HC_return_2026-04-19.md`
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`

然后：
1. 用不超过 12 条总结当前项目状态
2. 明确当前哪些事项是：
   - 已经落地的生产事实
   - 仍在研究轨道
   - 当前最值得 PM 优先拍板的事项
3. 特别避免以下误判：
   - 不要把 `Q015` 当成仍待研究或待拍板问题
   - 不要把 `Q017` 当成仍待起 Spec 的问题
   - 不要把 `Q018` 误读成“应该直接开多槽位”
   - 不要把 `Q019` 误读成“现有 HIGH_VOL 研究都失效了”
   - 不要把 `/ES` 当前问题误判成 entry logic，而忽略 `Q013`
4. 最后输出你建议 MC 今天优先推进的 1 到 3 个方向，并说明每个方向属于：
   - research only
   - ready for DRAFT Spec
   - waiting on PM decision

如果你判断今天应该继续 `/ES`，再补充说明：
- `Q012`、`Q013` 的区别
- 为什么 `Q013` 仍然比 `Q018 / Q019` 更靠前

如果你判断今天应该继续 HIGH_VOL 研究，再补充说明：
- `Q018` 和 `Q019` 分别在回答什么问题
- 你建议先做哪一个，为什么
