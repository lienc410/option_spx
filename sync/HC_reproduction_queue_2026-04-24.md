# HC Reproduction Queue — 2026-04-24

> 目的：基于已通过 MC 审核的 `sync/mc_to_hc/MC_Handoff_2026-04-24_v3.md`，为 HC 环境给出最小、可执行、按依赖排序的复现队列。
> 口径：本文件只定义 **HC 下一步应复现什么**，不把 MC-side `DONE` 直接视为 HC 已完成。

## 1. 复现目标

HC 需要复现并确认以下 MC 成果：

1. `SPEC-068`
   - `hv_spell_trade_count` 从单一 scalar 改为 per-strategy dict
   - 目标：避免 HV spell aggregate 计数错误阻挡 aftermath `IC_HV` 第二笔

2. `SPEC-069`
   - artifact / UI 增加 `open_at_end`
   - 目标：未平仓持仓在回测 / 研究视图中可见

3. `SPEC-070 v2`
   - engine `_build_legs` 的 IC 长腿构造改为 delta-based
   - 目标：对齐 selector / engine 的长腿语义

4. `SPEC-071`
   - aftermath `IC_HV` 结构改为 broken-wing
   - 目标参数：
     - `LC delta = 0.04`
     - `LP delta = 0.08`
     - `short call / short put delta = 0.12`（保持）
     - `DTE = 45`（保持）

5. `SPEC-072`
   - frontend dual-scale display
   - 注意：MC 标记为 `MC-side DONE`，HC 仍需部署和 live smoke test

6. `SPEC-073`
   - `BEAR_CALL_DIAGONAL` dead-code cleanup

## 2. 推荐顺序

### 阶段 A：先复现策略语义

按这个顺序：

1. `SPEC-068`
2. `SPEC-070 v2`
3. `SPEC-071`

原因：
- 这三项直接影响 aftermath 行为、长腿构造或参数语义
- 应先保证 selector / engine / strategy output 对齐，再谈 artifact / frontend

### 阶段 B：再复现 artifact / UI

按这个顺序：

1. `SPEC-069`
2. `SPEC-072`

原因：
- `SPEC-069` 为 artifact / UI 提供 `open_at_end`
- `SPEC-072` 的 smoke test 依赖 HC 实际部署

### 阶段 C：最后做低风险收尾

1. `SPEC-073`

原因：
- 这是 dead-code cleanup，不应阻塞主线复现

## 3. 每项最小验收点

### `SPEC-068`

- `hv_spell_trade_count` 确认为 per-strategy
- `2026-03` double-spike 下，不再因 aggregate spell count 错误阻挡第二笔 aftermath `IC_HV`

### `SPEC-069`

- artifact 中存在 `open_at_end`
- UI 可区分正常平仓与回测末尾仍未平仓

### `SPEC-070 v2`

- selector 与 engine 在 aftermath `IC_HV` 长腿语义上一致
- 不再出现 “selector 是 delta-based，engine 是 wing-based” 的错配

### `SPEC-071`

- aftermath selector / backtest 输出符合：
  - `LC 0.04`
  - `LP 0.08`
  - `DTE 45`
- 不把 `V3-C (LC 0.03)` 提前当成当前生产形态

### `SPEC-072`

- HC 完成 old Air deploy
- 完成 live smoke test
- 结果单独回写

### `SPEC-073`

- `BEAR_CALL_DIAGONAL` 已从代码库清除
- 无 behavior change

## 4. 与研究问题的关系

以下问题应被视为“复现时顺手确认，但不是主线分叉”：

- `Q029`
  - 先接受 MC 当前中间结论：不要立刻重写 engine
  - HC 先复现 `research_1spx + live_scaled_est` 双列 reporting 口径

- `Q032`
  - 只作为 monitor
  - 先不要把 `V3-C` 升级为当前策略

- `Q034`
  - 低优先级，不应挡住主线

- `Q035`
  - 长期项，不进入当前实现队列

## 5. 当前不要做的事

1. 不要把 `MC-side DONE` 直接写成 `HC canonical DONE`
2. 不要在未复现 `SPEC-071` 前就更新 `PARAM_MASTER`
3. 不要在 `Q019` 未获 PM 拍板前，自行把 close-based 口径改成 open-based
4. 不要把 `Q035` 的 live-scale engine rewrite 偷渡成当前 sprint

## 6. 仍需 PM 拍板

1. `Q019`
   - 走 `A / B / C` 哪条后续路径

2. `SPEC-067` / `/ES runtime safeguards`
   - 是否正式进入 DRAFT / APPROVED 流程

3. `Q032`
   - 在积累 `5–10` 笔 live aftermath 后，是否重开 `V3-C`

4. `Q035`
   - 是否长期保持 defer，还是未来单独开 RDD / architecture branch

## 7. 可直接转发给下一棒的 prompt

### 给 Quant Researcher

请基于 `sync/mc_to_hc/MC_Handoff_2026-04-24_v3.md` 和 `sync/HC_reproduction_queue_2026-04-24.md`，先判断 HC 侧应如何最小成本复现 `SPEC-068 / 070 v2 / 071` 的策略语义，并指出：
- 哪些是必须先在 HC 重放验证的
- 哪些可以暂时只接受为 MC 结论
- `Q029 / Q032 / Q019` 在本轮复现中各自应保持什么边界

### 给 Developer

请先读取：
- `DEVELOPER.md`
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`
- `sync/mc_to_hc/MC_Handoff_2026-04-24_v3.md`
- `sync/HC_reproduction_queue_2026-04-24.md`

然后仅按已批准的 Spec 状态，评估 HC 当前距离复现以下项目还差什么：
- `SPEC-068`
- `SPEC-069`
- `SPEC-070 v2`
- `SPEC-071`
- `SPEC-072`
- `SPEC-073`

要求：
- 不把 MC-side DONE 直接当作 HC 已完成
- 明确哪些项会改策略语义，哪些只是 artifact / UI / cleanup
- 给出最小实施顺序和依赖关系
