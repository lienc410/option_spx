# SPX Strategy — Daily Workflow

目的：把每天开工顺序固定下来，减少“今天先做什么、该叫谁做什么”的切换成本。

适用角色：
- PM
- Quant Researcher
- Planner
- Developer

---

## 一句话总则

- Quant Researcher：负责深研究、策略判断、Spec 草案、review
- Planner：负责状态整理、sync 维护、研究沉淀、优先级建议
- Developer：只执行 `Status: APPROVED` 的 Spec
- PM：唯一最终拍板者

---

## PM 可直接复用的低 token prompt

常用 prompt 已统一收录在仓库根目录 [PROMPTS.md](/Users/lienchen/Documents/workspace/SPX_strat/PROMPTS.md:1)。

这里仅保留两个最高频动作：

### review 后同步索引层

```text
请作为 Planner，读取 task/SPEC-{id}.md 的最新 Review 与 Status，并同步索引层。
```

### 实施任务检查

```text
请先读取：
DEVELOPER.md
PROJECT_STATUS.md

然后检查今天是否存在 `Status: APPROVED` 的 Spec。
```

---

## 每天开工顺序

### Step 1 — PM 先看索引层

先读取：
- [PROJECT_STATUS.md](/Users/lienchen/Documents/workspace/SPX_strat/PROJECT_STATUS.md:1)
- [RESEARCH_LOG.md](/Users/lienchen/Documents/workspace/SPX_strat/RESEARCH_LOG.md:1)
- [sync/open_questions.md](/Users/lienchen/Documents/workspace/SPX_strat/sync/open_questions.md:1)

目标：
- 快速知道现在项目在哪
- 确认 blocker
- 确认今天最值得推进的方向

---

### Step 2 — 让 Quant Researcher 读取角色协议和专题文档

Quant Researcher 默认启动读取：
- [QUANT_RESEARCHER.md](/Users/lienchen/Documents/workspace/SPX_strat/QUANT_RESEARCHER.md:1)
- [PROJECT_STATUS.md](/Users/lienchen/Documents/workspace/SPX_strat/PROJECT_STATUS.md:1)
- [RESEARCH_LOG.md](/Users/lienchen/Documents/workspace/SPX_strat/RESEARCH_LOG.md:1)
- [sync/open_questions.md](/Users/lienchen/Documents/workspace/SPX_strat/sync/open_questions.md:1)

若今天有专题，再追加专题文件。
例如 ES Put：
- [research/strategies/ES_puts/spec.md](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/spec.md:1)
- [research/strategies/ES_puts/research_notes.md](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/research_notes.md:1)

Quant Researcher 的默认任务：
- 判断研究方向
- 挑战关键假设
- 输出 `enter Spec / hold / drop`
- 不直接进入实现

推荐启动 prompt：

```text
请先重新读取以下文件作为今天工作的上下文：
QUANT_RESEARCHER.md
PROJECT_STATUS.md
RESEARCH_LOG.md
sync/open_questions.md

如果今天涉及某个专题，再读取对应专题文件。

然后：
1. 用不超过10条总结当前项目状态与今天最值得推进的研究方向
2. 明确各事项属于 enter Spec / hold / drop 哪一种
3. 如果我给你新的研究材料，请按 Topic / Findings / Risks / Confidence / Next Tests / Recommendation 输出
4. 不写生产代码，不替 PM 改 Spec 状态
```

---

### Step 3 — 让 Planner 整理状态与下一步

Planner 默认启动读取：
- [PLANNER.md](/Users/lienchen/Documents/workspace/SPX_strat/PLANNER.md:1)
- [PROJECT_STATUS.md](/Users/lienchen/Documents/workspace/SPX_strat/PROJECT_STATUS.md:1)
- [RESEARCH_LOG.md](/Users/lienchen/Documents/workspace/SPX_strat/RESEARCH_LOG.md:1)
- [sync/open_questions.md](/Users/lienchen/Documents/workspace/SPX_strat/sync/open_questions.md:1)

如有专题，再追加专题详细文档。

Planner 的默认任务：
- 整理当天最高优先级
- 判断哪些事项需要更新索引层
- 判断哪些方向仍是 research track
- 判断哪些可收缩成最小可验证单元

推荐启动 prompt：

```text
请作为 Planner 工作，不做最终策略判断，不写生产代码。

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

---

### Step 4 — PM 拍板

PM 在看完 Quant Researcher 和 Planner 的输出后，只做决策：

- 继续 research
- 新增或更新 open question
- 收缩为一个最小可验证单元
- 起一个 `DRAFT Spec`
- 保持 `hold`
- 或 `drop`

此时仍然 **不该直接叫 Developer**，除非已经进入明确实现阶段。

---

### Step 5 — 只有进入 Spec 后，才交给 Developer

Developer 默认启动读取：
- [DEVELOPER.md](/Users/lienchen/Documents/workspace/SPX_strat/DEVELOPER.md:1)
- [PROJECT_STATUS.md](/Users/lienchen/Documents/workspace/SPX_strat/PROJECT_STATUS.md:1)

若需要实现，再读取：
- `task/SPEC-xxx.md`

规则：
- 只有当 `Status: APPROVED` 时，Developer 才实施
- 若只有 `DRAFT`，Developer 不动

推荐启动 prompt：

```text
请先读取：
DEVELOPER.md
PROJECT_STATUS.md

然后检查今天是否存在 `Status: APPROVED` 的 Spec。

如果没有 APPROVED Spec，请明确说明今天没有需要实施的任务。
如果有 APPROVED Spec，再读取对应 `task/SPEC-xxx.md`，只按 Spec 实施，不做研究判断，不扩展设计。
```

---

## 今天是研究日时的默认流程

若今天主要是研究，而不是实现，默认顺序应是：

1. PM 看索引层
2. Quant Researcher 做研究判断
3. Planner 做状态整理和范围收缩
4. PM 拍板
5. 必要时更新索引层和 open questions
6. 不叫 Developer

---

## 今天是实现日时的默认流程

若今天已经有明确实现任务，默认顺序应是：

1. PM 确认已有 `APPROVED Spec`
2. Developer 实施
3. Developer 写 handoff
4. Quant Researcher 将 review 结果直接写回 `task/SPEC-{id}.md` 的 `## Review` 与 `Status`
5. Planner 读取该 Spec 的最新 `Review + Status`，再更新索引层与状态

推荐 review 后同步 prompt：

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

---

## Reddit / 外部材料研究时的默认分工

如果今天是 Reddit、论坛、博客、播客等外部材料分析：

- Quant Researcher：负责研究判断
- Planner：负责沉淀与优先级整理
- Developer：不参与

外部材料不应直接变成实现任务。
应先经过：
- 研究判断
- 索引层沉淀
- PM 拍板
- 必要时再进入 Spec

---

## 结束前的最小检查

每天收尾前，PM 至少确认：

- `PROJECT_STATUS.md` 是否需要更新
- `RESEARCH_LOG.md` 是否需要新增条目
- `sync/open_questions.md` 是否需要新增或更新 `Qxxx`
- 今天产出的研究结论是否属于：
  - `enter Spec`
  - `hold`
  - `drop`

如果今天没有新的正式结论，也可以不更新文件。
但不要让重要新研究只停留在聊天记录里。
