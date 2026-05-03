# SPEC-076: Overlay-F Telemetry / Dashboard / Review Protocol Adoption (HC Local Materialization)

Status: DRAFT

> Note: current HC status is **ready for Developer planning**, but not yet approved for direct implementation. Quant clarification and Developer planning boundaries are now fixed; next step is controlled implementation planning / execution.

## 目标

**What**：将 MC 已确认的 `Overlay-F` telemetry / dashboard / review protocol 相关内容，整理并落地为 HC 本地可实施的 adoption spec。

**Why**：
- `SPEC-075` 若只落 core logic、不同时固定 telemetry / review protocol，HC 会留下 observability 缺口
- MC adoption 包已明确：
  - `overlay_f_mode` posture
  - old runtime 影响面
  - telemetry artifacts
  - staged rollout 纪律
- 这部分必须和 `SPEC-075` 同批进入规划，但保持独立 implementation / review 单元，便于定位问题

---

## 核心原则

- **本 spec 当前用于 HC adoption planning，不是已批准实施稿**
- **与 SPEC-075 同批进入，但职能分离**：
  - `SPEC-075` = overlay logic / sizing hook
  - `SPEC-076` = telemetry / dashboard / review protocol
- **shadow 是本 spec 的核心工作姿态**
  - `disabled` 下可以不产生日志
  - `shadow` 下必须有可读、稳定、可审查的 runtime artifacts
- **不允许为了 telemetry 改变 disabled parity**

---

## 功能定义

### F1 — telemetry artifacts 定义固定

HC adoption 阶段必须至少预留并确认以下 artifacts：

- `data/overlay_f_shadow.jsonl`
- `data/overlay_f_alert_latest.txt`

它们的角色应区分为：

- `shadow.jsonl`
  - 逐次事件记录
- `alert_latest.txt`
  - 最近一次 / 当前值得查看的摘要

### F2 — dashboard / recommendation enriched fields

HC 前端 / recommendation 层如需呈现 overlay 信息，必须先固定：

- 哪些字段进入 recommendation payload
- 哪些字段只在 shadow / active 才出现
- disabled 下是否完全不显示，还是显示“overlay disabled”姿态

MC 文件路径如写为：

- `web/html/spx_strat.html`

HC 正式本地映射路径为：

- `web/templates/index.html`

### F3 — review protocol 本地化

HC 需要一份本地 review protocol 文档，例如：

- `doc/OVERLAY_F_REVIEW_PROTOCOL.md`

最少应包含：

- disabled 阶段看什么
- shadow 阶段看什么
- active 阶段看什么
- 何种情况应回退到 disabled
- old Air 上如何抽查 runtime surface

### F4 — old Air runtime impact 固定

本 spec 在实施后预计会影响：

- `web`
- `bot`
- dashboard rendering
- telemetry file path

因此部署上至少预期：

- 代码同步
- `web` 重启
- `bot` 重启

### F5 — shadow verification 纪律

在 HC 本地，这部分的最低 shadow 验证要求应为：

- `overlay_f_mode = shadow`
- trade list / PnL 与 disabled 相同
- 但 telemetry artifacts 必须出现
- shadow fires 数量应与 MC 给出的参考量级大致相近

并且最少必须看到：

- fire context 包含：
  - `date`
  - `strategy`
  - `VIX`
  - `idle BP`
  - `SG count`
  - `mode`
  - `effective factor`
  - `rationale`
- bot / dashboard 不得把 shadow 当 active
- stale / missing live state 不得产生 false positive would-fire

---

## In Scope

| 项目 | 说明 |
|---|---|
| telemetry artifacts 定义 | shadow jsonl / alert latest |
| dashboard / recommendation 呈现面 | enriched fields 与本地路径映射 |
| review protocol 本地化 | 形成可执行观察规则 |
| old Air runtime 影响面 | web / bot / telemetry |
| shadow verification discipline | log-only parity |

## Out of Scope

| 项目 | 理由 |
|---|---|
| overlay-F core sizing logic | 由 SPEC-075 主管 |
| 直接 active rollout | 需 PM 单独批准 |
| 新研究 / 新指标发明 | adoption planning 阶段不扩树 |
| Q036 再讨论 | 已收口 |

---

## 边界条件与风险

- 最大风险不是文件写入本身，而是：
  - telemetry 与 recommendation/live path 的耦合
  - dashboard 字段与 runtime payload 不同步
  - old Air 上 shadow 产生副作用，误改 disabled parity
- HC 与 MC 前端路径不同，这一映射若不先固定，实施时最容易出现机械照搬错误
- `SPEC-080` 类似经验说明：某些 shadow 可能在 live runtime 上当前只是“姿态对齐”，不一定立刻产出同等丰富的 live artifacts；这应在 protocol 中写清楚

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | telemetry artifacts 已明确 | 文档审查 |
| AC2 | dashboard / recommendation 映射路径已明确 | 文档审查 |
| AC3 | review protocol 本地文档目标已定义 | 文档审查 |
| AC4 | old Air 影响面已明确 | 文档审查 |
| AC5 | shadow verification 纪律已固定 | 文档审查 |
| AC6 | 与 SPEC-075 的分工清楚 | 文档审查 |

---

## Pre-Implementation Checklist

- [ ] `task/SPEC-076.md` 已落地
- [ ] file-map / rollout / validation package 已统一冻结
- [ ] telemetry file-map 已确认
- [ ] shadow evidence schema 已写实
- [ ] HC 前端路径映射已写死
- [ ] recommendation payload enrichment 范围已确认
- [ ] shadow verification 指标已确认
- [ ] old Air 观测面已确认

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-03 | Planner 基于 `MC Response 2026-05-02_v2.md` §4 + Developer adoption-readiness reply 起草 HC 本地 skeleton | DRAFT |
| 2026-05-03 | Quant adoption-fit clarifier + Developer implementation-planning reply 吸收：formal HC dashboard path、shadow evidence expectations、old Air deployment面与 075->076 顺序已固定，状态推进到 ready for Developer planning | DRAFT |
