# SPX Strategy — Prompt Index

目的：给 PM 一页可直接复制的常用 prompt，尽量减少翻文档和手动组织上下文的成本。

适用原则：
- 优先使用短 prompt
- 只有在需要更强约束时，再改用长 prompt
- 默认让各角色先读自己的角色文档，再读索引层或目标 Spec

---

## 1. Quant Researcher

### 研究判断（默认短版 / 最低 token）

```text
请作为 Quant Researcher 工作。

先读取：
QUANT_RESEARCHER.md

然后：
1. 如有必要，再自行补读 PROJECT_STATUS.md、RESEARCH_LOG.md、sync/open_questions.md 和相关专题文件
2. 用不超过10条总结当前项目状态与今天最值得推进的研究方向
3. 明确各事项属于 enter Spec / hold / drop
4. 不写生产代码，不替 PM 改 Spec 状态
```

### 研究判断（稳妥版 / 中等 token）

```text
请作为 Quant Researcher 工作。

先读取：
QUANT_RESEARCHER.md
PROJECT_STATUS.md
RESEARCH_LOG.md
sync/open_questions.md

如果今天有专题，再读取对应专题文件。

然后：
1. 用不超过10条总结当前项目状态与今天最值得推进的研究方向
2. 明确各事项属于 enter Spec / hold / drop
3. 不写生产代码，不替 PM 改 Spec 状态
```

### review SPEC（默认短版 / 最低 token）

```text
请作为 Quant Researcher，review SPEC-{id}。

先读取：
QUANT_RESEARCHER.md
task/SPEC-{id}.md

如有需要，再读取：
task/SPEC-{id}_handoff.md
相关源码文件

然后：
1. 核查接口定义、边界条件、验收标准
2. 将最终 review 结果直接写回 task/SPEC-{id}.md 的 `## Review`
3. 按结论更新 Status：PASS -> DONE；FAIL -> DRAFT
4. 不要把最终 review 只停留在聊天里
```

### review SPEC（稳妥版 / 中等 token）

```text
请作为 Quant Researcher，review SPEC-{id}。

先读取：
QUANT_RESEARCHER.md
task/SPEC-{id}.md
task/SPEC-{id}_handoff.md

再读取 handoff 中提到的关键源码文件。

然后：
1. 核查接口定义、边界条件、验收标准
2. 将最终 review 结果直接写回 task/SPEC-{id}.md 的 `## Review`
3. 按结论更新 Status：PASS -> DONE；FAIL -> DRAFT
4. 不要把最终 review 只停留在聊天里
```

### 更新 research_notes + strategy_status（默认短版 / 最低 token）

```text
请作为 Quant Researcher，基于本轮最新研究，更新：
- doc/research_notes.md
- 最新版 doc/strategy_status_YYYY-MM-DD.md

要求：
- research_notes 记录研究过程、证据、反例与 hold/drop 理由
- strategy_status 记录当前有效策略逻辑，并保留最小必要研究依据，供 MC / 新 agent 重建 HC 当前理解
- 不要把已失效的中间态和最终态混在一起
- 不改 Spec 状态

更新后请简要总结两份文档各改了什么。
```

### 更新 research_notes + strategy_status（稳妥版 / 中等 token）

```text
请作为 Quant Researcher 工作，更新详细层文档，不写生产代码。

先读取：
QUANT_RESEARCHER.md
PROJECT_STATUS.md
RESEARCH_LOG.md
sync/open_questions.md
doc/strategy_status_2026-04-10.md
doc/research_notes.md

如果这次研究涉及专题，再读取对应专题文档与相关 SPEC。

然后：
1. 判断本轮新结论哪些应写入 `doc/research_notes.md`
2. 判断哪些应写入最新版 `doc/strategy_status_YYYY-MM-DD.md`
3. 更新这两个文档：
   - `research_notes.md` 侧重研究问题、证据、反例、为何 hold/drop
   - `strategy_status_YYYY-MM-DD.md` 侧重当前有效策略逻辑，并保留最小必要研究依据，帮助 MC / 新 agent 重建 HC 当前理解
4. 不要把已失效的中间态和最终态混在一起
5. 不替 PM 改 Spec 状态
6. 最后简要说明：
   - 本次 research_notes 新增了什么
   - 本次 strategy_status 更新了什么
   - 哪些内容仍应只留在索引层或 open questions
```

---

## 2. Planner

### 日常状态整理（全量版 / 重建上下文）

```text
请作为 Planner 工作。

先读取：
PLANNER.md
PROJECT_STATUS.md
RESEARCH_LOG.md
sync/open_questions.md

如果今天有专题，再读取对应专题文件。

然后输出：
1. 当前最高优先级事项
2. 当前 blocker
3. 今天最值得推进的 1 到 3 个方向
4. 每个方向属于：
   - research only
   - ready for DRAFT Spec
   - waiting on dependency
5. 哪些文件需要更新：
   - PROJECT_STATUS.md
   - RESEARCH_LOG.md
   - sync/open_questions.md
```

### review 后同步索引层（短版 / 最低 token）

```text
请作为 Planner，读取 task/SPEC-{id}.md 的最新 Review 与 Status，并同步索引层。
```

### review 后同步索引层（稳妥版 / 中等 token）

```text
请作为 Planner 工作。

先读取：
PLANNER.md
task/SPEC-{id}.md

如有需要，再读取：
task/SPEC-{id}_handoff.md
PROJECT_STATUS.md
RESEARCH_LOG.md
sync/open_questions.md

然后：
1. 根据 SPEC-{id} 中最新的 Review 与 Status，判断哪些索引层文件需要更新
2. 直接更新需要更新的文件
3. 简要说明本次同步了什么，哪些没有同步
```

### HC / MC 同步整理（稳妥版 / 中等 token）

```text
请作为 Planner 工作。

先读取：
PLANNER.md
PROJECT_STATUS.md
RESEARCH_LOG.md
sync/open_questions.md

再读取本次 HC / MC sync 包。

然后：
1. 判断这次同步新增了什么
2. 判断哪些索引层文件需要更新
3. 直接更新需要更新的文件
4. 简要说明哪些事项仍需 PM 拍板
```

### HC / MC 冲突检查（短版 / 最低 token）

```text
请作为 Planner，读取本次 HC / MC sync 包，并只输出：
1. 哪些 canonical 冲突需要 PM 拍板
2. 哪些只是研究更新，不应写成已生效事实
3. 哪些事项需要更新 open question
```

---

## 3. Developer

### 实施任务检查（短版 / 最低 token）

```text
请先读取：
DEVELOPER.md
PROJECT_STATUS.md

然后检查今天是否存在 `Status: APPROVED` 的 Spec。

如果没有 APPROVED Spec，请明确说明今天没有需要实施的任务。
如果有 APPROVED Spec，再读取对应 `task/SPEC-xxx.md`，只按 Spec 实施，不做研究判断，不扩展设计。
```

### 开始按某个 SPEC 实施（稳妥版 / 中等 token）

```text
请作为 Developer 工作。

先读取：
DEVELOPER.md
task/SPEC-{id}.md

然后只按 Spec 实施，不做研究判断，不扩展设计。
实施完成后按规则写 handoff（若触发条件满足）。
```

---

## 4. PM 自查

### 今天先做什么（短版 / 最低 token）

```text
请作为 Planner 工作。

先读取：
PLANNER.md
PROJECT_STATUS.md
RESEARCH_LOG.md
sync/open_questions.md

然后只回答：
1. 当前最高优先级事项
2. 当前 blocker
3. 今天最值得推进的 1 到 3 个方向
```

### 某个方向能否进入 DRAFT Spec（稳妥版 / 中等 token）

```text
请作为 Planner 工作，不做最终策略判断。

先读取相关专题文件与索引层文档。

然后只回答：
1. 这个方向当前属于 research only / ready for DRAFT Spec / waiting on dependency 哪一种
2. 如果要进入 DRAFT，最小可验证单元应该是什么
3. 哪些内容必须明确后置，不应一起带入
```

---

## 5. 使用建议

- 研究判断后，如果决定推进实现，优先先形成 `DRAFT Spec`
- 实施完成后，不要手动转贴长 review；优先让 Quant Researcher 直接写回 Spec，再让 Planner 按 Spec 同步索引层
- 若只想快速触发某个固定动作，优先用一行版 prompt
