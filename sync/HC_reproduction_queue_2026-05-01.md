# HC Reproduction Queue — 2026-05-01

**类型**：Planner routing note  
**来源**：`sync/mc_to_hc/MC_Handoff_2026-05-01_v5.md`（MC 已审核通过，可进入 sync-ready）  
**用途**：把 `2026-05-01` 这轮 `MC -> HC` handoff，拆成 HC 侧可执行的 `Quant` / `Developer` / tieout 顺序，避免把 “MC 已完成” 误读成 “HC 已同步完成”。

---

## 1. 本轮 sync 在 HC 侧的真正含义

这不是单一 Spec，也不是单一研究结论回填。

HC 侧需要重现的是一个 **stacked reproduction sprint**，包含三层内容：

1. **回测 / selector fidelity 收口**
   - `SPEC-074`
   - 这是本轮最关键的 reproduction item，因为 MC 已明确指出：
     - 当前 `3y tieout` 的主要差异，不在“同日选错策略”，而在“是否入场”的 gate 行为
     - MC 怀疑 `_backtest_select` 简化路径、trend persistence、以及 fallback / IVP gate 路径，是差异主因

2. **新策略 / 新治理逻辑的 HC 侧复现**
   - `SPEC-075`
   - `SPEC-076`
   - `SPEC-077`
   - `SPEC-078`
   - `SPEC-079`
   - `SPEC-080`

3. **研究 / 状态 / 索引层同步**
   - `Q020`
   - `Q036`
   - `Q037`
   - `Q038`
   - `Q039` candidate

关键点：
- MC 文本中 `SPEC-074..080 = DONE`，这是 **MC canonical state**
- HC 当前本地 **没有** `task/SPEC-074.md` 到 `task/SPEC-080.md`
- 因此 Developer **不能直接开工**；必须先有 HC 侧可执行的 spec / diff 入口

---

## 2. HC 当前与 MC 本轮 handoff 的主要差距

### 2.1 HC 当前本地缺失

HC 当前本地未见：
- `task/SPEC-074.md`
- `task/SPEC-075.md`
- `task/SPEC-076.md`
- `task/SPEC-077.md`
- `task/SPEC-078.md`
- `task/SPEC-079.md`
- `task/SPEC-080.md`

这意味着：
- 现在还没有 Developer 可以合法执行的 `APPROVED Spec` 入口
- 也没有足够的本地详细层，能让 Developer 在不冒风险的前提下直接照着 MC 摘要重构代码

### 2.2 HC 当前 canonical 状态与 MC handoff 的潜在漂移

最需要显式保留的 HC 边界：

1. `Q036`
- MC 文本口径更接近：overlay productization 前提栈已经向前推进
- HC 当前 canonical 仍是：
  - `PASS WITH CAVEAT`
  - PM 已在 governance 轨道上前进
  - 但 Quant 最新 PM-facing recommendation 仍是：
    - **hold as research candidate, do not productize now**
- 这条不能被本轮 sync 静默覆盖

2. `Q020`
- MC 认为 `SPEC-074` 可关闭 `Q020`
- HC 当前对 `Q020` 的索引语义是：
  - 主要追踪 MC 侧 `backtest_select` simplification 导致的 artifact / tieout 偏差
- HC 需要先完成 reproduction，再决定是否真的按 MC 口径关闭

3. `Q037 / Q038 / Q039`
- 这些是 MC 本轮新增的重要研究弧
- 但 HC 目前还没有做本地 reproduction / review / canonical indexing
- 所以要先走 Quant 通道，不应直接变成 Developer 实现判断

---

## 3. 推荐的 HC 执行顺序

### 阶段 A — Quant reproduction / review first

目标：
- 先把 MC handoff 里的研究、参数、状态、风险边界翻译成 HC 可接受的 canonical 判断
- 明确哪些内容只是“MC 局部已完成”，哪些值得 HC 真正同步
- 为 Developer 提供精确定义，而不是让 Developer 从手工摘要倒推策略语义

重点任务：

1. **复核 `SPEC-074` 的 tieout-critical 逻辑意义**
- 确认它在 HC 侧是否真的是：
  - `_backtest_select` delegate 到 `live select_strategy`
  - 并因此解决当前 3y tieout 的主要 divergence
- 需要明确哪些差异来自：
  - selector path
  - trend persistence
  - `Q015` IVP gate / fallback path

2. **复核 `Q037` / `SPEC-077`**
- 重点不是先改代码
- 而是确认：
  - `profit_target 0.50 -> 0.60` 的证据在 HC 语义下是否成立
  - `stop_mult` wiring 是纯治理修正还是会改变 HC backtest 解释

3. **复核 `Q038` / `SPEC-079` / `SPEC-080`**
- 明确 `Path C` 在 HC 侧意味着什么
- 明确 `BCD comfortable top` filter 与 `BCD stop tightening` 的依赖关系
- 防止 HC 误把它们当成两个完全独立、可以任意裁剪的 spec

4. **复核 `SPEC-075` / `SPEC-076` 与 HC 当前 `Q036` canonical 的关系**
- 这里尤其重要：
  - MC 文本更偏 productization stack
  - HC 当前仍是 `hold as research candidate`
- Quant 需要先判断：
  - HC 应把这两项视为“可索引但不立即 adopt”
  - 还是“可做 shadow-only reproduction”

5. **确认 `Q039` 的定位**
- 先判断它只是 candidate research note
- 还是值得进入 HC open question queue

Quant 产出目标：
- 一份 `HC reproduction assessment`，把本轮内容分成：
  - `reproduce as-is`
  - `reproduce but keep shadow / disabled`
  - `index only, do not implement yet`
  - `needs PM clarification before HC adopts`

### 阶段 A 已完成 — Quant reproduction assessment 结论

Quant 已按本队列要求完成 assessment，当前 HC 侧可直接采用的规划结论如下：

#### A1. Workstream 拆分

Quant 将本轮 sync 拆成 5 条工作流：

- `W1` — `SPEC-074` tieout 核心
- `W2` — `SPEC-075 / SPEC-076` shadow-disabled reproduction
- `W3` — `SPEC-077 / SPEC-079 / SPEC-080`
- `W4` — `SPEC-078` reporting / dashboard source-of-truth
- `W5` — 研究索引层（`Q020 / Q036 / Q037 / Q038 / Q039`）

这与 Planner 初始拆分基本一致，并进一步确认：
- 真正的 reproduction 核心是 `W1`
- 真正的 HC canonical 边界护栏是 `W2`

#### A2. `SPEC-074..080` 三选一分类（Quant verdict）

**reproduce as-is**
- `SPEC-074`
- `SPEC-077`
- `SPEC-078`
- `SPEC-079`
- `SPEC-080`

**reproduce but keep shadow / disabled**
- `SPEC-075`
- `SPEC-076`

**needs PM clarification before HC adopts**
- 无单独划入此类的单个 spec
- 但 `W2` 整体仍受 HC 侧 `Q036` canonical 边界约束：是否在 HC 侧 adopt `SPEC-075/076`，需要 PM 先明确 HC 对 `Q036` 的态度

#### A3. `3y tieout` 最可能 root causes（Quant 概率排序）

按 Quant 当前判断：

1. **`_backtest_select` 简化路径**（约 70%）
   - 最可能解释 `IC regular 13 vs 6` 的大头差异
   - 对应 `SPEC-074` 的主要 reproduction 价值

2. **`Q015` IVP63 fallback 路径**（约 20%）
   - 与 “`11` 笔 HC `IC reject` / `+$13,952`” 的量级吻合
   - 本质上与 `SPEC-074` 同属 selector fidelity 问题，只是从 gate 侧描述

3. **trend / ATR persistence 触发时机**（约 10%）
   - 主要解释诸如 `2024-12-13 BCD +$662 vs -$9,577` 这类同日入场但退出完全不同的 case
   - 这条不在 `SPEC-074` 的直接修复范围内，应视为 `tieout #2` 之后若仍残留差异时的第二层解释

#### A4. `Q037 / Q038 / Q039` 的索引层处置

Quant 建议：

- `Q037`：不要现在就补 HC canonical 条目，等 `tieout #2` 完成后再决定如何写入
- `Q038`：同上，先等 `SPEC-079/080` reproduction 与 tieout 结果
- `Q039`：等 `tieout #2` 后再决定是
  - `candidate research note`
  - 还是进入 HC `open question`

也就是说，这三条当前仍然属于：
- **review/index later**
- 不是 Developer 先实现、Planner 先定 canonical 的对象

#### A5. 当前最关键的 HC 边界（Quant 与 Planner 一致）

1. **`Q020` 不要立即关闭**
- 即便 MC 认为 `SPEC-074` 可以关闭 `Q020`
- HC 也应等 `tieout #2` 结果后再决定

2. **`Q036` 是本轮最关键护栏**
- MC 当前口径更接近：
  - PM `ESCALATE`
  - `SPEC-075/076 DONE`
- HC 当前 canonical 仍是：
  - PM 只到 `Option B`
  - Quant recommendation = **hold as research candidate**
  - PM 最终 promote / hold decision pending
- 因此：
  - `SPEC-075/076` 可以复现
  - 但不能被理解成 HC 已接受 productization

3. **`SPEC-079 / SPEC-080` 是 `Path C` 依赖项**
- 不应被 HC 理解成两个完全无依赖、可随意拆开的独立小 spec

#### A6. Quant 对 Developer 启动条件的最终判断

Developer 启动前仍有两个硬阻塞：

- **阶段 2**：PM 先在 HC 端明确 `Q036` 与 `SPEC-075/076` 的 adopt 边界
- **阶段 3**：PM / MC 传输本地 `SPEC-074..080` 的 spec / diff 入口，使其在 HC 侧成为合法可执行对象

在这两个条件达成前：
- Planner 不应把本轮 sync 路由成 Developer 实施
- Developer 也不应根据 MC handoff 摘要自行猜测实现

### 阶段 B — Developer implementation second

Developer 只在以下条件成立后再启动：

1. HC 已收到并确认 `SPEC-074..080` 的本地 spec / diff 入口
2. PM 已明确这些 spec 在 HC 侧也属于 `APPROVED`
3. Quant 已完成上面的 reproduction assessment

Developer 实施顺序建议：

#### B1. 先做 tieout-critical core
- `SPEC-074`
- `SPEC-077`
- `SPEC-079`
- `SPEC-080`

原因：
- 这些最可能改变 `3y tieout #2` 的 entry / exit 结构
- 也是 MC 明确要求特别核对的核心逻辑层

#### B2. 再做 governance / monitoring / dashboard
- `SPEC-075`
- `SPEC-076`
- `SPEC-078`

原因：
- `SPEC-075/076` 当前在 HC 侧仍受 `Q036 hold` 边界约束
- 最稳妥姿态应是：
  - 如需复现，也保持 `disabled` / `shadow`
- `SPEC-078` 虽重要，但它更多影响 dashboard source-of-truth，而不是 3y trade tieout 的根因

### 阶段 C — one-time tieout after code sync

在 HC 完成代码同步后，再做一次 **one-time tieout**：

1. 重跑 `2023-04-29 -> 2026-04-29` 的 `3y backtest`
2. 导出和当前一致字段的 CSV
   - 继续用：
     - `data/backtest_trades_3y_2026-04-29.csv`
   - 或按新时间戳再导一版
3. 至少比较：
   - trade count
   - total PnL
   - strategy mix
   - entry-date overlap
   - same-entry different-exit trades
4. 如果差异仍 > MC 目标：
   - trade match `< 99%`
   - 或 PnL diff `> $1,000`
   - 则输出 divergence list，不要直接宣称同步完成

### 阶段 D — Planner index update last

只有在 Quant / Developer / tieout 都跑完后，Planner 才做最后索引层动作：
- 更新 `PROJECT_STATUS.md`
- 更新 `RESEARCH_LOG.md`
- 更新 `sync/open_questions.md`
- 准备 `HC -> MC return` 包

---

## 4. HC 对本轮 sync 的推荐边界

### 4.1 可以直接作为 HC reproduction 目标的

- `SPEC-074` selector / backtest fidelity 收口
- `SPEC-077` `profit_target = 0.60` + `stop_mult` wiring
- `SPEC-079` `BCD comfortable top` filter
- `SPEC-080` `BCD debit stop = -0.35`
- `SPEC-078` dashboard metrics source-of-truth

### 4.2 应以 shadow / disabled 姿态同步的

- `SPEC-075` overlay core logic
- `SPEC-076` overlay monitoring / review protocol

原因：
- MC handoff 已明确：
  - `overlay_f_mode = disabled`
  - `shock_mode = shadow`
- 且 HC 当前 `Q036` canonical 仍然是：
  - `hold as research candidate, do not productize now`

### 4.3 暂时只做 index / review，不做实现判断的

- `Q037`
- `Q038`
- `Q039`
- `Q020` 的关闭与否

原因：
- 这些首先是研究与状态同步问题
- 不应先交给 Developer 猜测其 canonical 含义

---

## 5. PM 当前待输入清单

Quant assessment 完成后，HC 当前还缺的不是更多研究，而是 **PM 输入**：

1. **HC 是否接受 `W2` 的 adopt posture**
- 即：
  - `SPEC-075`
  - `SPEC-076`
- 在 HC 侧是否明确按：
  - `reproduce but keep shadow/disabled`
  前进

2. **HC 侧 `Q036` 边界是否继续保持现 canonical**
- 即：
  - `hold as research candidate`
  - 不把 MC 的 `ESCALATE` 直接搬成 HC 当前事实

3. **PM / MC 是否已传输 `SPEC-074..080` 的本地 spec / diff**
- 这是 Developer 合法启动的前置条件

4. **`Q020` 的关闭条件**
- 当前建议：等 `tieout #2`
- 若 PM 想更激进关闭，需要明确覆盖这一建议

---

## 6. 给 Developer 的下一棒 prompt（条件性）

> 仅在 HC 已收到 `task/SPEC-074.md` 到 `task/SPEC-080.md`，且 PM 明确这些在 HC 侧也属于 `APPROVED` 后使用。

```text
请作为 Developer 工作。

先读取：
- DEVELOPER.md
- PROJECT_STATUS.md
- sync/open_questions.md
- sync/mc_to_hc/MC_Handoff_2026-05-01_v5.md
- sync/HC_reproduction_queue_2026-05-01.md
- 本地已存在且 `Status: APPROVED` 的 `task/SPEC-074.md` 到 `task/SPEC-080.md`

任务目标：
在 HC 环境重现 `MC_Handoff_2026-05-01_v5.md` 中要求同步的代码改动，但严格遵守 HC 当前 canonical 边界：
- `overlay_f_mode` / `bcd_comfort_filter_mode` / `bcd_stop_tightening_mode` 默认保持 `disabled`
- `shock_mode` 保持 `shadow`
- 不擅自 flip active

实施顺序：
1. 先同步 tieout-critical core：
   - `SPEC-074`
   - `SPEC-077`
   - `SPEC-079`
   - `SPEC-080`
2. 再同步：
   - `SPEC-075`
   - `SPEC-076`
   - `SPEC-078`
3. 完成后重跑 `3y backtest tieout`
4. 导出和现有一致格式的 trade CSV
5. 写 handoff，逐项回报：
   - `SPEC-074..080` PASS / FAIL
   - 3y tieout #2 trade count / PnL / divergence list
   - 四个 toggle 状态确认

要求：
- 严格按 APPROVED Spec 实施
- 不自行改 threshold
- 不把 `SPEC-075/076` 推到 active
- 若 `SPEC-079` 只看到旧 attempt，而未拿到最新修复版，必须停下并在 handoff 里明确说明
```

---

## 7. Planner 当前建议

当前最稳的 HC 路线是：

1. **Quant assessment 已完成，不再重复做研究路由**  
2. **先等 PM 回答 §5 的输入问题**  
3. **再确认 HC 是否真的收到了 074–080 的 APPROVED spec/diff**  
4. 条件满足后，再交 Developer  
5. 最后做 `3y tieout #2` 和 `HC return`

一句话总结：

> 这轮 `2026-05-01` sync 在 HC 侧不是“直接同步七个 DONE spec”这么简单，而是一次 **以 `SPEC-074` tieout 收口为核心、以 `SPEC-075/076` shadow 边界为护栏、以 `Q037/Q038/Q039` 研究索引为补充** 的 reproduction sprint；而且在 Quant assessment 完成后，Developer 启动前只剩 **PM 边界确认 + spec/diff 传输** 两个硬前置。
