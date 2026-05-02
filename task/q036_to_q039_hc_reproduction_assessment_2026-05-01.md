# HC Reproduction Assessment — MC Handoff 2026-05-01

- Date: 2026-05-01
- Author: Quant Researcher
- Sources:
  - `sync/mc_to_hc/MC_Handoff_2026-05-01_v5.md` (审核通过)
  - `sync/HC_reproduction_queue_2026-05-01.md` (Planner routing)
  - `data/backtest_trades_3y_2026-04-29.csv` (HC 当前 3y backtest 输出, 57 trades)
  - HC canonical: `PROJECT_STATUS.md`, `RESEARCH_LOG.md`, `sync/open_questions.md`

## TL;DR

本轮 sync **不是** “七个 DONE spec 直接同步”。HC 侧应执行三层并行 workstream：(1) **`SPEC-074` tieout 收口** 是 reproduction sprint 的真正核心；(2) **`SPEC-075 / 076` 在 HC 侧只允许 shadow/disabled reproduction**，理由包括 MC 自己的 deploy 姿态以及 HC `Q036` canonical 与 MC 文本之间一处真实分歧；(3) **`Q037 / Q038 / Q039` 先进研究索引层**，不直接交 Developer。`Q020` 应在 `tieout #2` 跑完后再决定关闭，而不是基于 `SPEC-074 DONE` 立刻关。

最终 verdict 见 §6。

---

## 1. 本轮 sync 在 HC 侧应拆成的 workstreams

### Workstream W1 — Tieout-critical reproduction (`SPEC-074`)
- 唯一 tieout-真正-收口 的项
- 核心问题：`_backtest_select` simplification 是否是 HC vs MC `3y tieout` 的主因
- 必须先于 W3 (`SPEC-077`) 跑通，否则 `profit_target = 0.60` 的影响会与 selector 路径变化混淆
- 输出：`tieout #2` HC trade count / PnL / divergence list

### Workstream W2 — Capital-allocation overlay shadow reproduction (`SPEC-075 / 076`)
- 只允许 `shadow / disabled` reproduction
- 边界由 `Q036` HC canonical 划定（详见 §5.4）
- W2 结果不应进入 `tieout #2` 主对账（toggle disabled 状态下应对 trade structure 零影响；任何非零差异都是 reproduction bug）

### Workstream W3 — Rule-layer & filter reproduction (`SPEC-077 / 079 / 080`)
- 改变 entry / exit 行为，会进入 `tieout #2`
- `SPEC-079` 与 `SPEC-080` 是 PM `Path C`，**有依赖关系，不可独立裁剪**（MC handoff §`不要推断的项目` §4 已显式说明）
- HC 仍以 `disabled` 默认 toggle 入仓

### Workstream W4 — Reporting / dashboard (`SPEC-078`)
- 不影响 trade 本身，但影响 PM 看到的 ann ROE / Sharpe / MaxDD 数字
- 与 `tieout #2` 解读直接相关：若 dashboard 还在用旧的 `total_pnl / 100000 / years`，`SPEC-077` 的 `+0.91pp` 表述无法在 HC 端可视化复核

### Workstream W5 — Research / index sync (`Q037 / Q038 / Q039 / Q020`)
- 纯 Planner / Quant 索引层动作
- 不交 Developer

---

## 2. `SPEC-074..080` 分类

每条按 §5 prompt 要求三选一：`reproduce as-is` / `reproduce but keep shadow/disabled` / `needs PM clarification before HC adopts`。

| SPEC | 主题 | 分类 | 原因要点 |
|---|---|---|---|
| `SPEC-074` | `_backtest_select` delegate to live `select_strategy` (incl. VIX3M / IVP63 / divergence) | **`reproduce as-is`** | tieout 收口的唯一根因路径；MC 已经过 3 次 review attempt PASS；HC 没有合理替代实现；产生改变是预期且可量化的 |
| `SPEC-075` | `Overlay-F` capital-allocation overlay 核心逻辑 (`overlay_f_mode` toggle) | **`reproduce but keep shadow/disabled`** | MC handoff 默认就是 `disabled`；但更重要：HC 当前 `Q036` canonical 与 MC `resolved` 状态有真实分歧（详见 §5.4）。HC 在拿到 PM 显式 escalate 文件之前，不能把 SPEC-075 视作 `as-is` adopted |
| `SPEC-076` | `Overlay-F` 监控 / 复盘 / quarterly review protocol | **`reproduce but keep shadow/disabled`** | 与 `SPEC-075` 同 fate；监控基础设施可以预先就位，但 alert / dashboard badge 应在 HC 端只在 toggle 切到 shadow 后才激活，不能把 `recommendation card overlay 面板` 在 HC 默认开 |
| `SPEC-077` | `profit_target = 0.60` + `stop_mult` wiring | **`reproduce as-is`** | rule-layer 改动有 `Q037 Phase 2A` 实证（全样本 `+0.91~+1.03pp`），且 `stop_mult` wiring 是 governance fix（StrategyParams 字段已存在但 engine 未读）。HC 没有任何反对证据 |
| `SPEC-078` | dashboard metrics 唯一权威化（API 为 source of truth） | **`reproduce as-is`** | 纯 reporting-layer governance；与 HC `Q029` 的 `live_scaled_est` 双口径需求兼容；不修会让 W3 数字解读不一致 |
| `SPEC-079` | `BCD comfortable top` 入场过滤 (`bcd_comfort_filter_mode` toggle) | **`reproduce as-is`**（toggle 默认 `disabled`） | 经过 ChatGPT 2nd / 3rd Quant review，发现并修复了原始 `Phase 2C` 中 `stop = 0.30` 的次优配置；filter 默认禁用，落地不带来风险 |
| `SPEC-080` | `BCD debit stop = -0.35` (`bcd_stop_tightening_mode` toggle) | **`reproduce as-is`**（toggle 默认 `disabled`） | 与 `SPEC-079` 是 PM `Path C` 的依赖配对，不可单独 reproduce；`F-26-04-29-3` 表明 `0.35 plateau` 是 sensitivity sweep 中心 |

注释：

- `reproduce as-is` 不等于 `flip to active`。所有四个新 toggle (`overlay_f_mode / bcd_comfort_filter_mode / bcd_stop_tightening_mode / shock_mode`) 在 HC 侧默认值都是 `disabled` / `shadow`，PM 单独 flip。这一点 MC handoff §`指令 5` 已显式要求。
- W2 的 `shadow/disabled` 与 `as-is`(toggle disabled) 的区别在于 **是否允许未来 PM 在 HC 端 flip 到 active**：`SPEC-079 / 080` 在 HC 端 PM 可任意时机 shadow flip；`SPEC-075 / 076` 在 HC 端 **PM flip shadow 需要先关闭 §5.4 的 canonical 分歧**。

---

## 3. `3y tieout` 最可能的 2-3 个 divergence root causes

MC 自己的解释（`MC Handoff §3y backtest tieout 数据`）是核心入手点：当双方同日都入场时 `100%` 选择同一策略，分歧不在策略选择而在 “是否入场” 的 gate 行为。基于此，root cause 候选按可能性排序：

### Cause #1 — `_backtest_select` 简化路径（**最可能, ~70% 解释力**）
- HC 当前 `_backtest_select` 走简化 fallback 矩阵，**不读** `VIX3M term structure` / `IVP63` / IVR-IVP divergence
- MC delegate 到 live tree 后这些分支重新生效
- 直接对应：
  - HC 独有 entry `29` / MC 独有 entry `24` → 多数应该是 “simplification 让 HC 路径更宽松或更紧严” 的 net effect
  - `IC regular` 项 HC `13` 笔 (+$16,705) vs MC `6` 笔 (+$1,090)：最大单一拖累，符合 “HC fallback 直接返回 IC vs MC 通过 live tree 走分支” 的 fingerprint
- 验证手段：reproduce `SPEC-074` 后 IC regular 项应显著向 MC 收敛

### Cause #2 — `Q015` IVP63 gate / fallback 路径（**次要, ~20% 解释力**）
- MC 报告 `ivp252 >= 55` 触发 `REDUCE_WAIT` 的 gate 在 fallback 路径上对 11 笔 HC IC entry 全部 reject，合计约 `+$13,952`
- 这与 `IC regular HC 13 vs MC 6` 的 `+$16K` gap **大致量级吻合**，所以 Cause #1 与 Cause #2 部分是**同一现象的两个表述**：
  - SPEC-074 把 fallback 简化路径替换成 live tree
  - live tree 内的 IVP63 gate 自然就在 backtest 中生效
  - HC 的 11 笔 IC reject = MC 在 live tree 下被 gate 挡掉的同批
- 这也是 `Q039` candidate research 的来源（IVP gate 是否过 restrictive）

### Cause #3 — `trend persistence` / `ATR persistence` 触发时机（**小量, ~10% 解释力**）
- MC `2024-12-13 BCD` 案例：HC 在 `2024-12-18` 退出 `+$662`，MC 在 `2025-01-14` 退出 `-$9,577`
- 解释：HC `单日 bearish 即翻` vs MC `等多日确认`，被归为 `SPEC-020` 设计 trade-off
- 影响 `same-entry different-exit` 那一类（不是 entry-day divergence 主因），但 PnL 量级可能很大（单笔 `~$10K` 量级）
- 不在 `SPEC-074` 范围内；HC 当前是否启用 `use_atr_trend = True` 需要在 W1 跑完后单独核对

### 影响排序

> **Cause #1 + #2 是同一根（`SPEC-074` 收口）**；Cause #3 是独立项，不应与 SPEC-074 混合。

Tieout #2 的 acceptance gate（MC 目标 `>=99% trade match`, PnL diff `<$1,000`）能否达到，主要取决于 SPEC-074 是否完整复现。如果 SPEC-074 后仍有 trade match `<95%`，那是 reproduction bug 而不是设计差异；如果在 `95-98%` 区间，那是 Cause #3 残余，可以走 `Q039 + ATR persistence sanity check` 单独消化。

### 3.5 HC 代码核查更正（2026-05-01 batch 1 起步前发现）

**重要事实更正**：上述 Cause #1 / #2 是基于 MC 文本叙述写的。在着手起草 HC `SPEC-074 / 077 / 078` 前，对 HC 代码做了直接核查，发现因果方向与 MC 叙述**反向**：

| 项 | MC 叙述（handoff §3y tieout） | HC 代码实测（2026-05-01）|
|---|---|---|
| `_backtest_select` 是否存在 | MC 自己 “之前用简化 fallback 矩阵, SPEC-074 删除并 delegate 到 live select_strategy” | **HC 不存在 `_backtest_select` 函数**；`backtest/engine.py:835` & `:1252` 直接调用 `select_strategy(vix_snap, iv_snap, trend_snap, params)` |
| backwardation / VIX3M 分支 | SPEC-074 让 backtest 重新看到这些分支 | HC live `select_strategy` 已含 9+ backwardation 分支（`strategy/selector.py:698 / 746 / 786 / 963 / 1084` 等），且 `signals/vix_regime.py:188-200` 抓 VIX3M |
| IVP63 gate (`>= 70`) | SPEC-074 让 backtest 重新走 `IVP63_BCS_BLOCK` | HC `strategy/selector.py:165` & `:623` 已有 `IVP63_BCS_BLOCK = 70` 且 `not params.disable_entry_gates` 路径已生效 |
| `params.stop_mult` wiring | MC SPEC-077 “engine 之前未读取 stop_mult, 现已 wire through” | HC `backtest/engine.py:880` **credit 侧已读** `params.stop_mult`；只有 debit 侧仍硬编 `-0.50`（line 882），且这恰好是 SPEC-080 的 BCD 范围 |

**含义**：
1. HC 没有 “simplification fallback” 这个东西要删 —— **MC 之前是 “HC + 简化 fallback”，SPEC-074 是 MC 自己回到 HC 等价路径**
2. §3 的 “70% Cause #1 + 20% Cause #2” 不适用于 HC：HC 这边的 IC regular 13 笔 / +$16K 不是 “HC fallback 比 MC live 更宽松” 的 fingerprint，而是 **HC live = MC SPEC-074 之后的 live**，差异在别处
3. 真正的 HC vs MC 3y 残余 trade 差异最可能来自：
   - (a) `profit_target` HC 默认 `0.50` vs MC production `0.60`（SPEC-077 应在 HC 调默认值即可缩小）
   - (b) `stop_mult` debit 侧 HC 硬编 `-0.50` vs MC `SPEC-080` 的 BCD `-0.35`
   - (c) `use_atr_trend` / `bearish_persistence_days` 默认值与 MC 不同（待 SPEC-074 草案中确认）
4. 新的可能性：MC 的 “100% 同日同策略选择” 命题 → HC live select_strategy 与 MC SPEC-074 之后的 select_strategy 在 backwardation / IVP63 / IVR-IVP divergence 这些分支**几乎等价**。差异主要是 exit-rule（profit_target / stop_mult）和 trend persistence

**重置后的 root cause 排序（HC 视角）**：
- Cause A（约 50%）：`profit_target` 默认 `0.50` vs `0.60`（SPEC-077 改一行 default 即可大部分收敛）
- Cause B（约 30%）：BCD debit stop `-0.50` vs `-0.35`（SPEC-080 范围）
- Cause C（约 20%）：trend / ATR persistence default 不一致；或 `select_strategy` 里 MC SPEC-074 之后引入的细节分支与 HC 不同（待逐行 diff）

> 这条更正不撤销 §6.3 的执行顺序，只是把 W1 的实际工作从 “删 fallback” 改成 “逐行 diff HC `select_strategy` vs MC 等价文件，确认是否有缺失分支”。如果确认无缺失，**SPEC-074 在 HC 是 no-op declaration**，可直接进入 W3 / W4。

---

## 4. `Q037 / Q038 / Q039` 在 HC 侧的索引层处置

### `Q037` — `profit_target` 优化研究弧
- MC 状态：`部分 resolved`（`Phase 2A → SPEC-077 DONE`；`Phase 2B NORMAL BPS audit` deferred；`0.65` 候选 deferred）
- HC 当前索引：**未列入** `sync/open_questions.md`
- **建议处置**：在 `tieout #2` 完成 + `SPEC-077` 在 HC 侧 PASS 之后，**新增** `Q037` 条目，状态写成 “部分 resolved (`SPEC-077` DONE)，phase 2B / 0.65 候选 deferred”，并记录这两个 deferred 的 re-trigger 条件（4-8 周 live `0.60` 观察期）
- **不建议**：先开 `Q037` 然后再走 spec；先跟 MC 时序保持

### `Q038` — `BCD comfortable top` + `BCD stop tightening` 研究弧 (Path C umbrella)
- MC 状态：`部分 resolved`（`SPEC-079 / 080` DONE，研究 umbrella 仍 open，未来候选包括 state-conditional stop / `score >= 2` 更激进 filter）
- HC 当前索引：**未列入**
- **建议处置**：在 `SPEC-079 / 080` 在 HC 侧 PASS 之后新增 `Q038` 条目，明确两点：
  1. PM 选的是 `Path C`，`SPEC-079` 与 `SPEC-080` 不是独立 spec（MC handoff §`不要推断` §4）
  2. umbrella 仍 open 的真正含义 = walk-forward 已经跨 `1999-2018 → 2024-2025` 验证过 `10/10`，但还没建立长期 OOS prior，所以 `state-conditional stop` 等扩展应在累积更多 live 周后再讨论
- 与 HC `Q036` 没有 governance 牵连

### `Q039` — `ivp252 >= 55` IVP gate sensitivity（candidate）
- MC 状态：candidate research，正式编号缺失，按上下文整理为 `Q039`
- HC 影响：直接挂在 §3 Cause #2，是 `tieout #2` 残余差异最可能的研究后续
- **建议处置**：
  - 在 `tieout #2` 跑完之前，**不要** 把 `Q039` 写成正式 open question；先按 candidate 在 `RESEARCH_LOG.md` 备注
  - 在 `tieout #2` 跑完之后，根据 Cause #2 的实测 `IC` 笔数差异决定：
    - 若 `tieout #2` 收敛到 `>= 99% match` → `Q039` 可作为低优先 research candidate，等 PM 拍板再做 `IVP gate sensitivity sweep`（threshold 60 / 65）
    - 若 `tieout #2` 收敛到 `95-98%` → `Q039` 应升级为正式 open question，理由是它已经直接影响 reproduction quality
- 编号建议：保留 MC 的 `Q039`，避免与 HC 现有编号冲突（HC 当前最高编号为 `Q036`，跳过 `Q037 / Q038` 接 `Q039` 是为了与 MC 严格对齐）

---

## 5. 关键 canonical 边界

### 5.1 `Q020` 是否应在同步后直接关闭

**建议：不要直接关闭。等 `tieout #2` 完成后再关。**

理由：

1. HC 当前 `Q020` 索引语义是 “MC `backtest_select` 简化导致 `SPEC-064 AC10` artifact count 偏少”，属于 MC-side housekeeping
2. MC 的关闭依据是 “`SPEC-074 DONE` → `_backtest_select` 完全对齐 `live select_strategy`” —— **这是 MC-side 的事实**，HC 还没复现
3. 在 HC 端 `SPEC-074` 真的 PASS 之前关闭 `Q020`，等于把 “MC 已修” 与 “HC 已修” 混为一谈；这违反 `不要默认 MC-side DONE = HC-side DONE` 原则
4. 实操：在 `tieout #2` 完成且 trade match 收敛后，再把 `Q020` 状态改为 `resolved`，并明确写明 “HC 侧通过 `SPEC-074` 实现路径同步关闭”

### 5.2 `Q036` 与 `SPEC-075 / 076` 的 HC canonical 边界（**最关键**）

存在一处真实分歧。

| 维度 | MC 文本（2026-05-01） | HC canonical（2026-04-26 最新） |
|---|---|---|
| `Q036` 状态 | `resolved` | `open` (`PM decision pending / Quant recommends hold`) |
| PM 选项 | `Option 2 = ESCALATE` | `Option B = governance track`，**explicitly outside DRAFT-spec and implementation status** |
| productization 前提 1–5 | 全闭环 | 不适用（HC 路径上未承认 escalate） |
| Quant 最新 PM-facing recommendation | （未单独存档） | **`hold as research candidate, do not productize now`**（`task/q036_pm_decision_packet_2026-04-26.md`） |
| `SPEC-075 / 076` 状态 | DONE，`overlay_f_mode = disabled` 待 PM shadow flip | 无本地 spec、未 adopt |

需要明确：

- HC `Option B`（governance track）与 MC `Option 2 = ESCALATE` **在文本上不冲突**：governance track 是 MC ESCALATE 路径的早期阶段。但 MC 已经走到了 `SPEC-075 / 076 DONE` (即 implementation 阶段)，而 HC PM 在 `2026-04-26` Quant 交付的 productization decision packet 上**尚未做出 final promote-vs-hold 判断**，且 Quant 当前推荐是 `hold`
- 因此 HC 不能直接 mirror MC 的 “`Q036 = resolved` + productization 前提栈闭环”
- **HC reproduction 边界**：
  - `SPEC-075` (overlay 核心逻辑) → reproduce **with `overlay_f_mode = disabled`**，作为 capacity preservation；不在 HC `RESEARCH_LOG` / `PROJECT_STATUS` 把 `Q036` 改为 `resolved`
  - `SPEC-076` (监控) → 同 fate；监控基础设施落地，但 HC alert / dashboard 默认全部沉默
  - HC 要等的事件序列：**PM 在 HC 端对 `task/q036_pm_decision_packet_2026-04-26.md` 给出 escalate/hold/drop 明确选择**，然后再决定 `Q036` 是否在 HC 端走向 `resolved`
- 这条不能被本轮 sync 静默覆盖

### 5.3 PM 的角色一致性问题

PM 在 MC 与 HC 是同一人。MC 文本已记 PM 选 `Option 2 = ESCALATE`；HC 文本已记 PM 选 `Option B`（同时 Quant 后续推荐 `hold`，PM 未确认）。两条 timeline 的演进可能性：

1. PM 真的在 MC 侧选了 escalate，HC 侧只是没记
2. PM 在两边的措辞含义不同（`Option B` vs `Option 2`）
3. PM 已经 evolve 到 escalate，但还没在 HC 侧 confirm 接受 Quant 的 hold recommendation

Quant 不主动消歧。**唯一安全的 HC 姿态是：等 PM 在 HC 端对 Quant 2026-04-26 packet 给出书面回应**。

### 5.4 `SPEC-079 / 080` 的 Path C 依赖

PM 选的是 `Path C`：`SPEC-079` 先独立立项，`SPEC-080` 并行验证后再开。这意味着：
- HC 可以分开实现这两个 spec（toggle 独立）
- 但 **不能把它们当成两个无依赖、可裁剪的 SPEC**：`SPEC-079` 的 walk-forward 验证依赖 `SPEC-080` 的 stop tightening 一起跑出来的 plateau
- 在 HC 端，如果 `SPEC-079` 在 v2 之外的 attempt 1 状态被发现（MC handoff §`不要推断` §3），Developer 必须 stop 并明确说明，不能用旧版 attempt 1 凑数

---

## 6. 综合 verdict

### 6.1 本轮 sync 在 HC 侧的真正含义

> 这不是 `SPEC-074..080` 的逐项搬运。它是一次以 **`SPEC-074` tieout 收口** 为核心、以 **`SPEC-075 / 076` shadow 边界** 为护栏、以 **`Q037 / Q038 / Q039` 索引层补完** 为后置的 reproduction sprint。

### 6.2 必要且必须先做的

1. **PM 同步**：PM 需在 HC 端对 `task/q036_pm_decision_packet_2026-04-26.md` 给出 escalate / hold / drop 明确选择。这是 §5.2 分歧的唯一消解路径
2. **本地 spec / diff 入口**：HC 当前 `task/SPEC-074.md` 到 `task/SPEC-080.md` 全部缺失（HC 仅有 `SPEC-070 / 071 / 072 / 073`）。Developer 在 PM 单独传 spec/diff 之前**不能开工**

### 6.3 推荐执行顺序

| 阶段 | 动作 | 责任方 | 阻塞条件 |
|---|---|---|---|
| 1 | Quant assessment（本文件）→ Planner review | Quant + Planner | — |
| 2 | PM 在 HC 端对 `q036_pm_decision_packet_2026-04-26.md` 拍板 | PM | 阶段 1 完成 |
| 3 | PM 传输 `SPEC-074..080` 本地 spec/diff 到 HC | PM | 阶段 2 完成 |
| 4 | Developer 实施 W1 (`SPEC-074`) → W3 (`SPEC-077 / 079 / 080`) → W4 (`SPEC-078`) → W2 (`SPEC-075 / 076` shadow-disabled) | Developer | 阶段 3 完成；W2 还需 PM 在 HC 端确认 `Q036 escalate` 后才能 mirror MC 的 `disabled-pending-shadow` 姿态 |
| 5 | `tieout #2`（`2023-04-29 → 2026-04-29` 重跑） | Developer | 阶段 4 完成 |
| 6 | `Q020` 关闭（如 `tieout #2` 收敛）；`Q037 / Q038` 索引层补条目；`Q039` candidate / open 由 tieout #2 残余决定 | Quant + Planner | 阶段 5 完成 |
| 7 | HC return 包给 MC | Planner | 阶段 6 完成 |

### 6.4 HC 侧不可逾越的边界

- **不要默认 `MC-side DONE = HC-side DONE`**：W1 / W3 / W4 必须本地实施 + tieout 验证才算 HC PASS
- **不要把 `Q036` 在 HC 索引层改 `resolved`**：直到 §5.2 分歧消解
- **不要单独 ship `SPEC-079` 没有 `SPEC-080`，或反之**：`Path C` 依赖
- **不要在 HC 端 flip 任何 toggle 到 `active`**：MC 默认全部 `disabled / shadow`，PM 单独决定 flip 时机

---

## 7. 仍待 PM 输入的事项清单

1. PM 对 `task/q036_pm_decision_packet_2026-04-26.md` 的 final promote/hold/drop 选择
2. PM 是否同意把 `Q037 / Q038 / Q039` 引入 HC `sync/open_questions.md` 编号体系（建议：`Q037 / Q038` 跟 MC 编号、`Q039` 保留为 candidate 直到 tieout #2）
3. PM 是否授权 Developer 启动 W1 / W3 / W4（W2 需要单独授权）
4. PM 是否对 `SPEC-074..080` 在 HC 端 `APPROVED` 状态显式确认

---

## 8. 给 Planner 的下一棒动作建议

1. 把本 assessment 列为 PM 阅读包的一部分
2. 在 PM 拍板 §7.1 / §7.3 之前，**不要** 启动 Developer 阶段
3. `Q037 / Q038 / Q039` 的索引层补完动作排在 `tieout #2` 之后，而不是现在
4. 不需要现在更新 `sync/open_questions.md` 的 `Q036` 状态；等 PM §7.1 决定后再写

---

## 9. 2026-05-01 batch 1 起步附记

PM 已授权 batch 1（SPEC-077 / 074 / 078 主体）。Quant 在起草前对 HC 代码作了直接核查，发现 §3.5 列的事实差异。结论性影响：

- **SPEC-074 (HC)**：极可能是 no-op declaration；先做 “HC `select_strategy` 与 MC SPEC-074 文本逐行 diff”，确认无缺失分支后即可结案
- **SPEC-077 (HC)**：实际工作 = `strategy/selector.py:68` 默认值 `profit_target=0.50 → 0.60`；`stop_mult` 在 credit 侧已 wire 通，无需再改；governance 需补 unit test 防止再退化
- **SPEC-078 (HC)**：仍待对 dashboard 代码做核查（pending todo）；不与 §3.5 冲突
- **W1 tieout 收口的真实主导项变成 SPEC-077 + SPEC-080**，而不是 SPEC-074。因此 batch 2（SPEC-079/080 研究 + SPEC-075 prototype lift）的优先级在 HC 端可能更紧迫；建议 PM 在看到本 §9 后再确认 batch 顺序

**Quant 当前推进姿态**：继续按 PM 授权完成 batch 1 三个 spec 草稿（SPEC-074 写 no-op 形式，SPEC-077 写 default-config-change 形式，SPEC-078 待 dashboard 核查后写），并在每条 spec 内引用本 §3.5 / §9 作为依据。如 PM 看到本节后认为应改顺序（先 batch 2 研究、再回 batch 1），请直接通知。

---

## 10. 2026-05-01 SPEC-074 F2 比对结果（基于 MC_Spec-074_short_summary_v3.md）

PM 在 batch 1 起步后提供了 `sync/mc_to_hc/MC_Spec-074_short_summary_v3.md`。Quant 完成 F2 逐行对照：

| 维度 | 结论 |
|---|---|
| 7 项 MC 列出的 gate 缺失 | 6 项 HC 已有；第 6 项 (`SPEC-054 DIAGONAL both-high gate`) **HC 主动由 SPEC-056c 移除**，与 MC canonical 分歧 |
| 5 个 MC 列出的实施组件 | 4 个 HC 已有（VIX3M / IVP63 helper / snapshot / delegation）；只缺 `tests/test_backtest_select_parity.py` |
| BBG VIX3M fetch 依赖 | HC 不需要；HC engine 走 yfinance `fetch_vix3m_history(period="max")`，覆盖 inception 2003-12-04 → today |

**§3.5 部分修正**：原写"SPEC-074 在 HC 是 no-op declaration"——更准确的说法是 **"HC 已实质对齐 SPEC-074 的功能层；治理层缺一个正式 parity test，且有一处真实分歧 (SPEC-054 vs SPEC-056c) 需要 PM 裁定"**。SPEC-074 不再是纯 no-op，但工作量也仅限于 F4 (test) + F5 (escalation)，不需要改 production 代码。

**对 §3.5 root-cause 排序的影响**：
- Cause A (profit_target 0.50 vs 0.60) 仍占 ~50%
- Cause B (BCD debit stop -0.50 vs -0.35) 仍占 ~30%  
- Cause C 需细化：HC vs MC 在 LOW_VOL + IVP_HIGH 路径上由于 SPEC-056c 分歧会有结构性差异，这是 tieout #2 残余不 100% match 的合法 fingerprint，不应视作 reproduction bug
