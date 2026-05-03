# SPEC-075: Overlay-F Core Logic Adoption (HC Local Materialization)

Status: DRAFT

> Note: current HC status is **ready for Developer planning**, but not yet approved for direct implementation. Quant clarification and Developer planning boundaries are now fixed; next step is controlled implementation planning / execution.

## 目标

**What**：将 MC 已确认的 `Overlay-F` core logic / sizing hook / recommendation wiring，整理并落地为 HC 本地可实施的 adoption spec。

**Why**：
- `Q036` 在 HC 侧已接受 MC 更接近 `escalate / productization stack` 的方向
- `sync/mc_to_hc/MC Response 2026-05-02_v2.md` 已提供 `SPEC-075/076` adoption 包
- 当前不再卡在上游定义缺失，而是需要把 MC adoption 包转成 HC 本地 implementation-ready 计划
- 这类改动会触及：
  - recommendation / live path
  - sizing
  - old Air runtime
  因此不应直接进入实现，必须先固定 scope / posture / regression envelope

---

## 核心原则

- **本 spec 当前只服务于 HC adoption planning**：不是已批准实施稿
- **与 SPEC-076 同批进入，但独立实施 / review**：`SPEC-075` 负责 core logic，`SPEC-076` 负责 telemetry / dashboard / review protocol
- **初始 posture 必须从 `disabled` 开始**：不允许直接 `shadow` 或 `active`
- **必须先过 disabled parity，再进入 shadow**
- **old Air 是 canonical live runtime**：任何 live-path 影响都必须按 `SERVER_RUNTIME.md` / `doc/old_air_server_maintainer.md` 组织

---

## 功能定义

### F1 — HC adoption source of truth 固定

MC adoption 输入来源固定为：

- `sync/mc_to_hc/MC Response 2026-05-02_v2.md`

重点章节：

- `§4.1 SPEC 全文`
- `§4.2 SPEC-075 file list`
- `§4.4 overlay_f_mode posture`
- `§4.5 old runtime 影响面`
- `§4.6 最小 regression / tieout 验证口径`
- `§4.7 staged rollout 建议`
- `§4.8 顺序建议`

### F2 — HC 本地最小文件面

本地 materialization 阶段至少应明确以下文件面：

#### new files

- `strategy/overlay.py`
- `tests/test_overlay_f_gate.py`
- `scripts/overlay_f_review_reports.py`

#### modified files

- `strategy/selector.py`
- `backtest/engine.py`
- `backtest/portfolio.py`
- `web/templates/index.html`

#### formal HC path mapping

- MC `web/html/spx_strat.html`
- HC `web/templates/index.html`

### F3 — Overlay-F rollout posture

HC canonical rollout posture：

- `disabled -> shadow -> active`

其中：

- `disabled`
  - 必须与 pre-SPEC-075 行为 byte-identical
- `shadow`
  - 允许记录 would-fire / would-size-up 事件
  - 不允许改变 trade list / PnL / recommendation outcome
- `active`
  - 才允许实际进入 overlay sizing 行为

### F3a — HC-specific guardrails to be fixed before implementation planning

HC 在交给 Developer planning 前，必须把以下 guardrails 写实：

- `short-gamma count` 使用 **position-count** productization 语义
- live `BP` / open positions / `VIX` / `SG count` 缺失或 stale 时，overlay **fail closed**
- disabled 模式下 recommendation payload 保持 inert
- MC → HC file mapping 写死
- backtest / live portfolio-state builder 一致性检查要求写入本地计划

### F4 — old Air 影响面预声明

实施完成后，预计会影响：

- `web`
- `bot`
- recommendation panel / API payload
- telemetry / runtime log

默认不影响：

- `cloudflared`

### F5 — 最小 regression / tieout 结构

#### Layer 1 — disabled parity

要求：

- full backtest
- trade list
- total PnL
- DD
- 关键 artifact 与 pre-SPEC-075 byte-identical

#### Layer 2 — shadow log-only parity

要求：

- `overlay_f_mode = shadow`
- trade list / PnL 与 disabled 相同
- 但应产生 telemetry artifacts

并且：

- shadow fires 数量与 active backtest fire count 同量级
- 每条 would-fire 需带完整 context：
  - `date / strategy / VIX / idle BP / SG count / mode / effective factor / rationale`
- 不允许 bot / dashboard 将 shadow 误解释为 actual size-up

#### Layer 3 — active reproduction envelope

要求：

- `overlay_f_mode = active`
- 对齐 MC 提供的 envelope：
  - `ann_roe`
  - `sharpe`
  - `fires`
  - `mdd`

---

## In Scope

| 项目 | 说明 |
|---|---|
| HC adoption source 固定 | 以 MC 已审核包为准 |
| core logic 本地文件面固定 | overlay / selector / engine / portfolio |
| rollout posture 固定 | disabled -> shadow -> active |
| regression / tieout 三层验证 | disabled / shadow / active |
| old Air 影响面预先声明 | web / bot / telemetry |

## Out of Scope

| 项目 | 理由 |
|---|---|
| 立即写生产实现 | 当前仍处于 adoption planning |
| dashboard / telemetry 细节 | 由 SPEC-076 主管 |
| Q036 方向争论 | 已收口 |
| 新 overlay variant 研究 | 不属于 Developer adoption 范围 |
| active rollout 批准 | 需 PM 单独决定 |

---

## 边界条件与风险

- 最大 implementation risk 不是算法本身，而是：
  - overlay hook 接入 `get_recommendation()` / `get_recommendation_live()`
  - 与 telemetry / runtime fields 的耦合
- HC 与 MC 的前端路径结构不同：
  - MC 可能写 `web/html/spx_strat.html`
  - HC 当前更可能映射到 `web/templates/index.html`
  - 这一点必须在实施前写死到 adoption note / file-map
- `disabled` 模式下不允许出现任何 recommendation / trade drift

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | HC 本地 `SPEC-075` 范围与 MC adoption 包章节对齐 | 文档审查 |
| AC2 | HC 本地文件面（new / modified）已明确 | 文档审查 |
| AC3 | rollout posture 明确为 `disabled -> shadow -> active` | 文档审查 |
| AC4 | disabled / shadow / active 三层验证包定义完备 | 文档审查 |
| AC5 | old Air 影响面已明确列出 | 文档审查 |
| AC6 | 与 SPEC-076 的分工明确 | 文档审查 |

---

## Pre-Implementation Checklist

- [ ] `task/SPEC-075.md` 已落地
- [ ] `task/SPEC-076.md` 已落地
- [ ] file-map / rollout / validation package 已统一冻结
- [ ] adoption note / file-map 已补齐
- [ ] `position-count` / fail-closed / shadow evidence guardrails 已写实
- [ ] MC file list → HC file path mapping 已写死
- [ ] disabled parity 验证口径已确认
- [ ] old Air 部署面已确认

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-03 | Planner 基于 `MC Response 2026-05-02_v2.md` §4 + Developer adoption-readiness reply 起草 HC 本地 skeleton | DRAFT |
| 2026-05-03 | Quant adoption-fit clarifier + Developer implementation-planning reply 吸收：formal HC file-map、expanded file surface、075->076 落地顺序、old Air 部署面与三层验证包已固定，状态推进到 ready for Developer planning | DRAFT |
