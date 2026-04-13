# MC_CLAUDE_INSTRUCTIONS.md — Minimal Revision Proposal

## Intent

Keep the current MC workflow unchanged:
- MC remains `Claude Quant + AMP Coder`
- OCR-friendly handoff format remains the primary transport
- No major role redesign is required

Only add a small compatibility layer so HC can update:
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`

---

## Recommended Revisions

### 1. Add one short paragraph near the top

Suggested text:

```markdown
补充说明：
本项目现采用“双层文档架构”。
MC handoff 仍以详细同步为主，但每次 handoff 还应提供可被 HC 侧整理进 `PROJECT_STATUS.md` 和 `RESEARCH_LOG.md` 的简短结构化摘要。
该摘要不替代详细内容，只用于低成本索引与状态维护。
```

### 2. Expand `【当前状态快照】` into a project-status-friendly block

Suggested replacement:

```markdown
【当前状态快照】
当前项目阶段 stable / research-driven / implementation-heavy
当前推荐生产配置 一句话描述
当前最高优先阻塞 xxx
当前正在推进的APPROVED SPEC SPEC-XXX, SPEC-YYY
当前MC端PARAM_MASTER版本号 vX
```

### 3. Expand `【研究发现】` so it can feed `RESEARCH_LOG.md`

Suggested replacement:

```markdown
【研究发现】
（无新发现时写：本期无新研究发现）

发现编号 F001
Topic 描述不超过40字
Findings 一到两句
Risks 一句话
Confidence low或medium或high
Recommendation enter Spec或hold或drop
相关SPEC SPEC-XXX
详见 doc/... 或实验名
```

This is the most important change.
It lets HC preserve a short index entry without rereading the entire packet.

### 4. Extend `【Master Doc影响清单】`

Suggested replacement:

```markdown
【Master Doc影响清单】
PARAM_MASTER需要更新 yes或no
open_questions需要更新 yes或no
strategy_status需要更新 yes或no
research_notes需要更新 yes或no
PROJECT_STATUS需要更新 yes或no
RESEARCH_LOG需要更新 yes或no
SPEC状态需要更新 yes或no
```

### 5. Optional: add one new small block for explicit index-layer hints

Only if you want cleaner downstream updates.
If added, keep it very short.

Suggested block:

```markdown
【索引层更新提示】
PROJECT_STATUS 若更新，更新哪一节 一句话
RESEARCH_LOG 若更新，新增哪条 Topic 一句话
```

This is optional, not required.

---

## What Should Not Change

- Do not remove the OCR-friendly constraints
- Do not replace the full handoff with summary-only content
- Do not force MC to maintain HC-side files directly
- Do not expand MC into a separate planning authority

---

## Net Effect

With these changes:
- MC keeps its current high-context workflow
- HC gains cleaner inputs for low-cost indexing
- Claude token usage on the HC side should drop
- No major retraining of the MC workflow is required
