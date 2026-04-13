# SPX Strategy — HC/MC Sync Checklist

目的：给 `Planner` 一份固定清单，确保 HC / MC 同步不是靠记忆完成。

适用角色：
- Planner 为默认执行者
- PM 为最终拍板者

---

## 0. 同步前先读

每次处理 HC / MC 同步前，先读取：
- [PLANNER.md](/Users/lienchen/Documents/workspace/SPX_strat/PLANNER.md:1)
- [PROJECT_STATUS.md](/Users/lienchen/Documents/workspace/SPX_strat/PROJECT_STATUS.md:1)
- [RESEARCH_LOG.md](/Users/lienchen/Documents/workspace/SPX_strat/RESEARCH_LOG.md:1)
- [sync/open_questions.md](/Users/lienchen/Documents/workspace/SPX_strat/sync/open_questions.md:1)
- 本次 handoff / return 包

### PM 可直接复用的低 token sync prompt

#### Spec review 后同步

```text
请作为 Planner，读取 task/SPEC-{id}.md 的最新 Review 与 Status，并同步索引层。
```

其余常用 sync prompt 统一见仓库根目录 `PROMPTS.md`。

---

## 1. 基本信息检查

- 确认同步包日期
- 确认来源是 HC 还是 MC
- 确认本次同步覆盖的工作周期
- 确认是否有 OCR 风险、字段缺失或格式损坏

如果字段缺失，先标注“待 PM / MC 确认”，不要自行补全。

---

## 2. Spec 状态检查

逐项检查同步包中的 Spec 相关信息：

- 是否出现新的 `APPROVED`
- 是否出现新的 `REJECTED`
- 是否出现新的 `DONE`
- 是否有状态与仓库当前文件不一致

若发现不一致：
- 标注冲突
- 不擅自改 canonical 状态
- 提交给 PM 拍板

---

## 3. 参数与规则变化检查

检查是否出现：
- 新参数值
- 旧参数值纠正
- 策略逻辑改变
- 规则阈值改变

若有：
- 先判断这是否只是研究结论，还是已经是 PM 决策
- 若只是研究，不要写成已生效事实
- 若已是 PM 决策，确认是否需要后续进入 Spec 或更新主文档

---

## 4. 研究结论检查

逐项识别同步包中的研究输出：

- 是否有新的 Topic
- 是否有新的 Findings
- 是否有新的 Risks / Counterarguments
- 是否有新的 Confidence
- 是否有新的 Next Tests
- 是否已有明确 Recommendation：`enter Spec / hold / drop`

然后决定：
- 是否新增 `RESEARCH_LOG.md` 条目
- 是否只更新既有条目
- 是否需要关联某个 `Qxxx`

---

## 5. Open Questions 检查

检查是否出现以下情况：

- 新 blocker
- 新外部依赖
- 新范围分歧
- 新样本追踪项
- 某个旧 `Qxxx` 状态发生变化

若有：
- 更新 [sync/open_questions.md](/Users/lienchen/Documents/workspace/SPX_strat/sync/open_questions.md:1)
- 状态使用：
  - `open`
  - `blocked`
  - `resolved`

不要把所有小想法都写成 `Qxxx`。

---

## 6. PROJECT_STATUS 检查

检查本次同步是否影响：

- `Current Phase`
- `Active APPROVED Specs`
- `Top Blockers`
- `Open Questions Summary`
- `Next Priorities`
- `Recent Meaningful Changes`

若只是局部研究细节变化，而不影响项目优先级，不必强行更新 `PROJECT_STATUS.md`。

---

## 7. Canonical 冲突检查

重点查三类冲突：

1. HC 与 MC 的 Spec 状态不一致
2. HC 与 MC 的参数或规则解释不一致
3. HC 与 MC 对某研究结论的 Recommendation 不一致

处理原则：
- Planner 负责标出冲突
- PM 负责最终拍板
- Quant Researcher 不默认承担秘书性冲突整理
- Developer 不参与未定事项

---

## 8. 同步后最小更新动作

一次完整同步结束后，Planner 至少确认：

- `RESEARCH_LOG.md` 是否需要更新
- `PROJECT_STATUS.md` 是否需要更新
- `sync/open_questions.md` 是否需要更新
- 是否存在需要 PM 决策的冲突项
- 是否出现可收缩成 `DRAFT Spec` 的候选方向

---

## 9. 不要做的事

- 不要替 PM 直接批准或否决 Spec
- 不要把研究结论自动写成已实现事实
- 不要因为 OCR 模糊就自行猜测关键参数
- 不要让重要同步信息只停留在聊天记录里
- 不要让 Quant Researcher 默认承担整个同步维护工作

---

## 10. 同步完成时应输出什么

Planner 完成一次同步后，最好能给 PM 一个短摘要：

1. 本次同步新增了什么
2. 哪些文件已更新
3. 哪些事项需要 PM 拍板
4. 哪些方向仍然是 `hold`
5. 是否有方向已接近 `DRAFT Spec`

目标：
- PM 不需要重读整包，也能快速决策
