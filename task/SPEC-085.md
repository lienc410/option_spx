# SPEC-085: Multi-Sleeve Read-Only Recommendation & Visualization Surface

Status: DONE

## Design Source

This DRAFT is a **packaged spec**, not an independently invented design.

Design substance来源如下：

- **Quant Researcher**
  - `Q041` Tier semantics
  - `Q046` mechanism-C conclusion
  - `Q048` governance scope-down
  - “可视化回测 + live signal forward-tracking 替代长周期 paper-trading”的研究侧判断
- **Developer-side architecture review**
  - 当前系统仍是 single-recommendation / single-position / SPX-centric rail
  - 不应在本轮先动 live write-path merge、unified routing、或 state-machine rewrite
- **Planner**
  - 负责将上述内容收口为一个窄范围、可审批的 DRAFT

由于这是一个 **engineering-driven implementation surface with research-governance inputs**，本 DRAFT 在 PM 审批前应有 **Developer feasibility review**。

## 目标

为 `Q041` / `Q046` / `Q048` 当前阶段提供一个**窄范围、只读、研究支持优先**的组合层支持面，用于：

1. 让 `Q041` Tier 1 / Tier 2 候选在 live 数据上以 **read-only sleeve candidates** 形式前向展示
2. 让当前 SPX live rail 与 `Q041` paper rail 在同一 summary surface 上被并排观察
3. 让 post-`SPEC-084` 的账户级 deployment-efficiency 问题有一个最小 attribution / visualization 入口

本 Spec 的定位是：

- **read-only support surface**
- **portfolio research support**
- **forward-tracking / visualization**

本 Spec **不是**：

- unified portfolio routing Spec
- multi-book state-machine rewrite
- broker integration 扩展
- 自动下单 / 自动记账 Spec
- full multi-asset simulator Spec

---

## 背景

`Q045` 已通过 `SPEC-084` 将主 SPX 矩阵的 `bp_target` 抬升到联合最优 `J3`，但 `Q046` 已明确指出：

- post-`SPEC-084` 之后账户级平均 BP 使用率仍只有 `~15.93%`
- 更大 sizing / concurrency / ceiling 都不是当前最佳下一机制
- **broader strategy / underlying coverage (`Q041`)** 是 post-`Q045` 的 primary deployment-efficiency axis

与此同时，`Q048` 架构规划发现：

- 当前系统仍围绕一个主推荐、一个当前 live position、一个 SPX 主回测宇宙构建
- `Q041` 已经引入第二条 rail（paper ledger），但它仍是旁路，不在主 dashboard / recommendation 语义里

Quant 对 `Q048` 的进一步收口结论是：

- 当前不应先做“大一统 portfolio platform”
- 更合适的替代路径是：
  - **可视化回测 + live signal forward-tracking**
  - 取代原来笨重的长周期 paper-trading 依赖
- 但这一步必须保持只读，不改写当前 SPX live rail

因此本 Spec 收敛为一个最小 support surface：

- `sleeve_candidates[]`
- portfolio summary
- minimal attribution artifact

补充说明：

- 支撑 F3 attribution artifact 的 multi-sleeve joint backtest 与可视化回测，仍归属 **Quant prototype path**（例如 `backtest/prototype/` 或等价的 Quant-maintained output）
- 本 Spec **不包揽** multi-sleeve joint backtest 本身
- 本 Spec 只承诺提供平台侧最小 carrier，使 Quant 提供的 prototype / fixture / static artifact 可以被读取和显示

---

## 核心原则

- **只读优先**：不改动当前 SPX live 写路径
- **双 rail 并存**：SPX live rail 与 `Q041` paper rail 继续独立存在
- **候选展示，不做自动行动**：输出 candidates，不做自动开仓 / 自动 promotion
- **研究支持优先于产品完整性**：先满足 Q041/Q046 的观察与量化需要，不提前承诺 unified portfolio platform
- **最小实现面**：只做当前问题真正需要的 surface，不引入新的 runtime 自动化
- **Planner 不发明接口细节**：DRAFT 只冻结行为边界与最小验收目标，不预先替 Developer 设计过细 schema / endpoint contract
- **主推荐面不漂移**：主 `/api/recommendation` 与当前 recommendation card 语义必须保持不变；本 Spec 的新增内容应进入独立只读 surface
- **fail-soft**：若 `Q041` ledger / config / attribution 数据缺失，本 Spec 的新增 surface 应返回 `unavailable` / `insufficient_data`，而不是让 dashboard 或 API 500
- **research-content ownership**：本 Spec 中 `candidate_status` 判定逻辑、Tier candidate 清单、`rationale / caveat` 文本、以及 F3 attribution 数值，均属于 research-side 内容，来源应由 Quant Researcher 提供（`Q041` packet、`Q046` 结论、Quant prototype 输出等）。Developer 在本 Spec 内仅承担 carrier / 透传 / 展示职责，不自行生成新的策略候选、不自创 caveat 文案、不自创 BP-fill / idle-day-capture 数值
- **forward-tracking 不是 trade recommendation**：本 Spec 的新增 surface 必须在 UI / docs 语义上明确表示为 forward-tracking observation，不构成 actionable trade recommendation

---

## In Scope

1. `Q041` Tier 1 / Tier 2 的 **read-only sleeve candidates** 输出
2. 一个最小 **portfolio summary surface**
3. 一个最小 **portfolio attribution / visualization artifact**
4. 对 Tier 路径的 UI / surface 语义支持：
   - Tier 1 = live signal forward-tracking
   - Tier 2 = live signal forward-tracking + later fill calibration
   - Tier 3 = review-only forward log

---

## Out of Scope

- unified portfolio routing
- 改写 `strategy/state.py` 的主 live position 写路径
- 将 `Q041` paper ledger 自动并入 current_position 语义
- 自动下单
- broker write integration
- 自动 promotion / demotion
- scanner / bot 扩展
- full multi-asset simulator
- live MTM / Greeks portfolio engine
- 把 Q041 直接晋升为 production trading sleeve
- 任何自动 governance 判断（promotion / demotion / admission）

---

## 功能定义

### F1 — Read-Only `sleeve_candidates[]` 输出

在当前 recommendation 流程之外，新增一个**只读**的 sleeve candidate 输出层，用于前向展示 `Q041` 候选信号。

要求：

- 不替换当前 `/api/recommendation`
- 不修改当前 `/api/recommendation` 的 response shape
- 候选输出应优先通过**独立只读 endpoint** 或等价独立只读 surface 暴露，而不是塞进现有主 recommendation payload
- 新输出至少覆盖：
  - Tier 1: `SPX CSP Δ0.20 DTE30`
  - Tier 2: `GOOGL CSP Δ0.20 DTE21`
  - Tier 2: `AMZN CSP Δ0.25 DTE21`
- Tier 3（`COST/JPM` earnings IC）不进入可执行 candidate surface，只允许 review-only event surface

上述 Tier 1 / Tier 2 候选清单来源于 `Q041` execution-prep packet，由 Quant 维护。第一版至少必须包含这三条；若后续 Quant 调整 candidate 清单，只要不改变本 Spec 的只读 / forward-tracking / non-actionable 边界，平台层不需要因此重开本 Spec。

最小行为要求：

- 至少能区分：
  - `sleeve_id`
  - `tier`
  - `underlying`
  - `candidate_status`
  - `bp_target_pct`（或可比较的 sizing reference）
  - `rationale / caveat` 的最小只读说明

`candidate_status` 必须是**非执行性** vocabulary。第一版至少应能表达：

- `watching`
- `due`
- `blocked_missing_data`
- `review_only`
- `unavailable`

这些状态值可以由 platform 层承载，但其**判定逻辑**不由 Developer 自创；若 Quant 未提供足够的状态映射输入，应 fail-soft 为 `unavailable` / `blocked_missing_data`，而不是由实现层推断新的策略语义。

约束：

- 该输出为 **read-only**
- 不自动写入：
  - `current_position.json`
  - `q041_paper_trades.jsonl`
- 不触发 broker action

### F2 — Minimal Portfolio Summary Surface

新增一个最小组合层 summary surface，用于同时观察：

- 当前 SPX live position（若有）
- 当前 `Q041` paper open records（若有）
- 按 rail / tier 的 BP usage
- 当前 idle capacity
- next review item

最低展示要求：

- `live positions`
- `paper positions`
- `bp usage by bucket`
  - `SPX live`
  - `Q041 Tier 1`
  - `Q041 Tier 2`
  - `Q041 Tier 3`
- `total used BP%`
- `idle capacity`
- `next review item`

说明：

- 这是 summary / report surface，不是 action surface
- 可采用只读页面、只读区块、或 report 页面形式
- 不要求在本 Spec 中重做首页整体 IA
- 该 surface 的语义必须明确为：
  - **SPX live rail + Q041 paper rail 的只读汇总视图**
  - **不是统一 portfolio state model**

缺失数据要求：

- 若 `Q041` ledger 或 `account_total_bp` config 不存在：
  - summary 仍可显示 SPX live rail
  - `Q041` 相关区块返回 `unavailable`
  - 主页面和主 API 不得因此报 500

### F3 — Minimal Attribution / Visualization Artifact

为 `Q041` 的 forward-tracking 与 `Q046` 的后续 BP-fill quantification 提供一个最小 attribution artifact。

本 Spec 只要求最小集，不要求 full simulator。

至少要支持的观察维度：

1. `idle-day capture` 观察入口
2. `BP-fill contribution` 观察入口
3. `worst-day overlap` 观察入口

最低可接受形式：

- 只读 JSON artifact
- 或 report page / backtest-side panel
- 或单独 API + 前端轻量可视化

最低信息要求：

- `idle-day capture`
- `delta avg BP`
- `worst-day overlap`
- `notes / interpretation`

说明：

- 本 Spec 不要求直接完成 `Q041` 的最终 quantification 结论
- 只要求平台提供最小可观察接口
- 第一版只允许：
  - 观测
  - 占位
  - 轻量汇总
- 第一版**不允许**在本 Spec 内引入复杂 BP-fill engine、联合模拟 engine、或自动策略结论生成
- F3 第一版展示的数值，必须来自 Quant 提供的 source（prototype 输出 / 静态 JSON / Quant-maintained fixture 等），不得由 Developer 自行定义新的 attribution 方法或策略结论；若数值 source 尚未就绪，artifact 应 fail-soft 显示 `pending_quant_input`

### F4 — Tier 路径语义固化（surface-only）

本 Spec 必须在 surface / docs / output semantics 中明确：

- **Tier 1**
  - 可以进入 `live signal forward-tracking`
  - 但不自动升级为 live trading sleeve
- **Tier 2**
  - 可以进入 `live signal forward-tracking`
  - 后续仍保留 `1–2 cycle` fill calibration 空间
- **Tier 3**
  - 仅 `review_only`
  - 不进入可执行 candidate surface

该要求是治理语义展示，不是自动 workflow engine。UI / docs 上也必须明确：forward-tracking surface 是观察层，不与主 recommendation card 共享同一行动语义。

---

## 边界条件

- 如果实现过程中发现必须先重构 `strategy/state.py` 才能完成本 Spec，应停止并回报；这表示范围已经滑向 `Q048` 的更深层状态模型重构，不应在本 Spec 内隐式完成
- 如果实现过程中发现必须先重写主 `Recommendation` dataclass 或 selector 主流程，默认视为超范围
- 如果实现过程中发现必须引入自动 paper-ledger 写入，默认视为超范围
- 如果实现过程中发现必须先定义复杂的跨 rail 统一预算服务，默认视为超范围
- 如果实现过程中发现必须把新增内容塞进主 recommendation card 才能落地，默认视为超范围；应回退到独立 panel / 独立只读 surface

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | 当前 `/api/recommendation` 主返回路径保持兼容，现有 SPX 主推荐行为不被替换 | API regression / snapshot |
| AC2 | 系统能通过独立只读 surface 输出 Tier 1 / Tier 2 `sleeve_candidates[]`，并可区分 tier / sleeve / candidate_status / sizing reference / rationale/caveat 最小信息 | API test / fixture |
| AC3 | Tier 3 `COST/JPM` 不进入可执行 candidate surface，只以 `review_only` 语义出现 | API / UI assertion |
| AC4 | 存在一个只读 portfolio summary surface，可同时看到当前 SPX live rail 与 `Q041` paper rail 的最小汇总信息，且其语义明确不是 unified portfolio state | UI / response inspection |
| AC5 | summary surface 至少能展示 BP usage by bucket 与 idle capacity | UI / response inspection |
| AC6 | 存在最小 attribution artifact，至少暴露 idle-day capture / delta avg BP / worst-day overlap 的可观察入口 | artifact / API inspection |
| AC7 | 本 Spec 不写入 `current_position.json`，也不自动写入 `q041_paper_trades.jsonl` | code review / regression |
| AC8 | 本 Spec 不引入 broker write integration，不新增自动下单或自动记账 | code review |
| AC9 | Tier 语义在 surface 上清楚：Tier 1/2 = forward-tracking；Tier 3 = review-only；candidate status vocabulary 不表达自动开仓指令 | UI / response / docs review |
| AC10 | Developer feasibility review 明确确认：本 Spec 可在不重构 `strategy/state.py`、不统一 routing、且不改 live write-path 的前提下实施 | pre-approval review note |
| AC11 | 当 `Q041` ledger/config 或 attribution 数据缺失时，新 surface fail-soft 返回 `unavailable` / `insufficient_data`，主 dashboard 和主 API 不会因此报 500 | negative-path test |

---

## Implementation Guidance

建议优先级：

1. 先做 **只读 candidate output**
2. 再做 **portfolio summary**
3. 最后做 **attribution artifact**

建议尽量复用：

- `SPEC-083` 的 `q041_paper_trade_io.py`
- 当前 `web/server.py` 的 BP helper 逻辑
- 现有只读 API / dashboard 结构

不建议：

- 在本 Spec 中引入新的复杂 engine
- 在本 Spec 中开始 unified state machine
- 在本 Spec 中预先冻结复杂数据模型；若需要更深 schema 设计，应由 Developer 在 feasibility review 中提出
- 在本 Spec 中把新只读内容直接嵌入主 recommendation card 作为唯一入口

---

## Review — Quant Researcher 2026-05-07

- 结论：PASS
- AC 核对：AC1–AC11 全部通过（含 negative-path AC11 fail-soft 测试覆盖）
- Research-content ownership guardrail 落地核对：
  - F1 candidates / caveat / rationale / sizing_reference 文本均带 `source: doc/q041_execution_prep_packet_2026-05-05.md`，由 Quant 维护，Developer 未自创
  - `candidate_status` 当前只输出 `watching` / `review_only`；"watching → due" 判定逻辑未在本 Spec 内实现，正确克制（属后续研究侧 signal logic）
  - F3 attribution carrier 仅读 Quant-provided artifact，缺失时 `pending_quant_input`；Developer 未自计算 idle_day_capture / delta_avg_bp / worst_day_overlap
  - Forward-tracking ≠ actionable 语义在 payload `semantics` 字段与 UI panel 副标题 + READ ONLY badge 上均明示
  - Tier 3 物理分隔到独立 `review_only[]` array，未污染可执行 candidate surface
- 维护性观察（不阻塞 PASS）：候选列表当前硬编在 `web/portfolio_surface.py:31-94`，与 Q041 packet 是手工同步关系。后续若候选频繁变动，建议改为 JSON/YAML 配置；属研究维护性优化，不需 reopen 本 Spec
- Quant follow-up（已在 handoff 记录）：Quant 在 `backtest/prototype/` 完成 multi-sleeve joint backtest 后，提供 `data/q041_portfolio_attribution_latest.json`（含 idle_day_capture / delta_avg_bp / bp_fill_contribution / worst_day_overlap / notes）；属 Quant prototype path，不在 SPEC-085 范围内

## Implementation Review — 2026-05-07

Status: DONE

Implemented as a narrow read-only support surface:

- F1: independent `/api/sleeve-candidates` endpoint; Tier 1 / Tier 2 candidates are exposed as forward-tracking observations; Tier 3 appears only in `review_only`.
- F2: independent `/api/portfolio/summary` endpoint; summarizes SPX live rail via `strategy.state.read_state()` and Q041 paper rail via `logs.q041_paper_trade_io.status_snapshot()` with fail-soft handling.
- F3: independent `/api/portfolio/attribution` endpoint; reads only a Quant-provided static artifact if present, otherwise returns `pending_quant_input`.
- UI: added an independent dashboard panel labeled `Multi-Sleeve Observation`; it is explicitly read-only and not an actionable recommendation.

Validation:

- `arch -arm64 venv/bin/python -m unittest tests.test_spec_085 -v` -> PASS, 6/6
- `arch -arm64 venv/bin/python -m unittest tests.test_state_and_api tests.test_spec_083 -v` -> PASS, 25/25
- `arch -arm64 venv/bin/python -m py_compile web/portfolio_surface.py web/server.py` -> PASS
- `arch -arm64 venv/bin/python -m compileall web tests` -> PASS

AC status:

- AC1-AC11 PASS.
- No `strategy/state.py` logic changes.
- No `/api/recommendation` shape changes.
- No broker write, auto-ledger-write, scanner/bot expansion, or unified routing introduced.
- F3 currently returns `pending_quant_input` until Quant supplies `data/q041_portfolio_attribution_latest.json` or an equivalent artifact via `Q041_PORTFOLIO_ATTRIBUTION_FILE`.

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-07 | Planner 初版起草：将 `Q048` 收成 read-only `sleeve_candidates[]` + portfolio summary + attribution artifact 的窄 DRAFT | DRAFT |
| 2026-05-07 | 按新 Spec 职责重做：明确 Quant / Developer / Planner 的设计来源边界，删去过细的 Planner 自行设计细节，并加入 Developer feasibility review 作为 PM 审批前条件 | DRAFT |
| 2026-05-07 | Quant fidelity review: PASS with boundary edits. Added research-content ownership guardrails, clarified that multi-sleeve joint backtest remains on Quant prototype path, and tightened forward-tracking / attribution-source boundaries | DRAFT |
| 2026-05-07 | PM 审批通过；`SPEC-085` 进入标准 Developer 实施路径 | APPROVED |
| 2026-05-07 | Developer implemented read-only candidates / summary / attribution carrier and dashboard observation panel; AC1-AC11 PASS | DONE |
