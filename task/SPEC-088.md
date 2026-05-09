# SPEC-088: `/ES` Stressed-SPAN Visibility Surface

Status: DONE

## Design Source

This DRAFT is a **packaged spec**, not an independently invented design.

Design substance来源如下：

- **Quant Researcher**
  - `Q012 Phase A/B/C` 对 `/ES` shared-BP / SPAN 扩张问题的完整研究结论
  - 当前 live 尺度（`1` 合约）下，“完整治理框架是过度设计”的判断
  - 当前最合理的实现目标：**SPAN 后验可见性 / monitoring**
- **Planner**
  - 负责将上述研究结论收口成一个窄范围、可审批的 DRAFT

这是一个 **research-driven monitoring surface spec**。  
它不是 shared-BP governance engine spec，也不是 `/ES` allocator spec。

## 目标

在当前 `/ES` live 持仓规模下（`1` 合约，约 `~4%` NLV），为 PM 提供一个最小但真实有用的只读可见性层：

当 `/ES` 有活跃 live 仓位时，前端 / 只读 API 显示：

1. 入场时的静态 SPAN / BP 基线估算
2. 当前时点的估算 stressed SPAN
3. 二者比值
4. 当前 stress band / visibility status

本 Spec 的定位是：

- **monitoring-layer only**
- **read-only**
- **post-entry stress visibility**

本 Spec 不是：

- `/ES` shared-BP governance framework
- dynamic budget engine
- regime-priority entry gating spec
- broker action / auto-close spec

## 背景

`SPEC-061` 已实现 `/ES` 最小生产单元，`SPEC-086` 已补齐 `/ES` credit-stop bot alerting。

`Q012 Phase A/B/C` 给出了更完整的研究结论：

- Phase A：`/ES` SPAN 在高 VIX 下会显著扩张
- Phase B：`/ES` 与 SPX Credit 的 shared-BP collision 在抽象层面频繁出现
- Phase C：但在**当前 `1` 合约 live 规模**下，不同治理架构对账户层 ROE 的影响几乎为零（约 `±0.01pp`）

因此当前正确的实施目标不是“补一个完整 shared-BP 治理框架”，而是：

> **先把 post-entry SPAN expansion 看清楚。**

也就是：

- 不先改开仓逻辑
- 不先加 allocator
- 不先加 Rule A+ / Rule D 运行时强制约束
- 先让 PM 在 live `/ES` 存在时，能直接看到“现在这笔仓位的 stress 放大到什么程度”

## 核心原则

- **只读**
  - 不自动平仓
  - 不 broker write
  - 不修改 `/ES` 或 SPX 的开仓 / 持仓状态
- **post-entry only**
  - 本 Spec 只处理“已有 `/ES` live 仓位时”的 stressed-SPAN 可见性
  - 不处理新开仓 eligibility
- **fail-soft**
  - 若 `/ES` 仓位不存在、Schwab 数据不可用、估算输入缺失，应显示 `unavailable` / `insufficient_data`
  - 不得让 dashboard / API 500
- **不偷偷引入治理语义**
  - 不实现 shared-BP gating
  - 不实现 dynamic budget
  - 不实现 regime-priority block
- **不重构 state**
  - 不改 `strategy/state.py`
  - 不改主 `/api/recommendation` shape

## In Scope

1. `/ES` live 仓位存在时的只读 stressed-SPAN 估算
2. 一个只读 API / surface 返回：
   - `entry_static_span`
   - `current_estimated_stressed_span`
   - `stress_ratio`
   - `stress_band`
   - `status`
3. 一个独立 UI panel 或 portfolio surface 区块显示上述信息
4. 缺失数据时的 fail-soft 展示

## Out of Scope

- `/ES` 新开仓 gating
- shared-BP allocator
- SPX Credit priority rules
- Rule A+ / Rule D 的 runtime enforcement
- auto-alert beyond existing `SPEC-086`
- auto-close / broker write
- Layer 1 / Layer 3
- `/ES` alpha / entry redesign
- full SPAN engine
- broker-certified PM model

## 功能定义

### F1 — Read-Only Stressed-SPAN Payload

新增一个只读 payload（独立 endpoint 或现有 portfolio read surface 的独立 section），当 `/ES` live 仓位存在时返回：

- `has_es_live_position`
- `entry_static_span`
- `current_estimated_stressed_span`
- `stress_ratio`
- `stress_band`
- `status`
- `notes`

最小语义：

- `entry_static_span`
  - 使用静态基线常量 `_ES_BP_PER_CONTRACT = $20,529`（基于 VIX≈19、/ES≈5400 时的 Schwab 实测值）
  - 不尝试从入场时的 VIX / SPX 重建精确入场 SPAN；使用该常量作为 baseline
- `current_estimated_stressed_span`
  - 使用 **既有仓位 re-mark 模型（Q012 Phase A, Model A2）**：
    - 输入：当前 VIX、当前 /ES 价格、入场时的 strike（固定）、剩余 DTE
    - 不使用"新 20-delta 45-DTE 仓位"的 A1 估算，A1 会低估既有仓位的 stress（例如 VIX=30 时 A1≈1.65x，A2≈2.25x）
- `stress_ratio`
  - `current_estimated_stressed_span / entry_static_span`
- `stress_band`（**Quant 提供的映射，Developer 不得修改边界**）

  | VIX 区间 | `stress_band` | 估算倍数（A2 模型，持仓约 10 天）|
  |---------|--------------|-------------------------------|
  | < 22    | `normal`     | ~1.0x                         |
  | 22–30   | `stress`     | ~1.3x                         |
  | 30–40   | `extreme`    | ~1.6–2.3x                     |
  | > 40    | `crisis`     | ~2.3x+                        |
  | 数据缺失 | `unavailable`| —                             |

- `status`（依据 `stress_ratio` 映射）

  | `stress_ratio` | `status`      |
  |---------------|---------------|
  | < 1.3         | `ok`          |
  | 1.3–1.8       | `elevated`    |
  | > 1.8         | `high_stress` |
  | 数据缺失       | `unavailable` |

注意：

- **band / status 的边界值由 Quant（Q012 Phase A）提供，Developer 不得自行扩写或调整治理语义**
- VIX 数据源应与 `SPEC-086` bot alerting 使用的 VIX 来源一致（市场开放期间用 intraday，收盘后用 EOD）

### F2 — UI / Surface

新增一个独立的只读 UI 区块，用于显示 `/ES` stressed-SPAN 状态。

最小展示内容：

- `/ES` active / not active
- entry static span
- current estimated stressed span
- ratio
- band / status
- 简短说明：
  - 这是 stress visibility
  - 不是 trade instruction

约束：

- 不得塞进主 SPX recommendation card
- 不得使用 actionable wording
- 优先放在：
  - portfolio home
  - `/es` 页面
  - 或等价独立 read-only panel
- **UI 必须包含以下标准免责说明（或等价中文翻译），文案不得由 Developer 自行拟写**：

  > "This is a model-based stress estimate only. It is not a trade recommendation or a risk management directive."
  >
  > 中文参考版本：「以下数据为基于 Q012 模型的估算值，仅供参考。不构成任何交易建议或风险管理指令。」

### F3 — Fail-Soft Behavior

若满足以下任一情况：

- 无活跃 `/ES` live 仓位
- Schwab positions 不可用
- VIX / 输入数据缺失
- 无法形成有效的 static-span 或 stressed-span 估算

则：

- 返回 `unavailable` / `insufficient_data`
- UI 仅显示不可用说明
- 不报 500
- 不影响主 recommendation / portfolio surfaces

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `/ES` live 仓位存在时，可返回 `entry_static_span` / `current_estimated_stressed_span` / `stress_ratio` | unit test |
| AC2 | `stress_band` / `status` 按 F1 节 Quant 提供的映射表执行：VIX<22→`normal`/`ok`；VIX22–30→`stress`/`elevated`；VIX>40→`crisis`/`high_stress` | unit test |
| AC3 | 无 `/ES` live 仓位时，surface fail-soft 为 `unavailable`，不报错 | unit test |
| AC4 | Schwab / market 输入缺失时，surface fail-soft 为 `insufficient_data` | unit test |
| AC5 | 新 UI 为独立只读区块，不改变主 `/api/recommendation` shape 与主 recommendation card 语义 | regression test / code review |
| AC6 | 不修改 `strategy/state.py` 逻辑 | code review |
| AC7 | 不引入 shared-BP gating / allocator / broker write | code review |
| AC8 | 文案明确说明这是 monitoring / visibility，不是 trade recommendation | code review |

## 实现指导

建议最小改动范围：

- `web/portfolio_surface.py` 或等价只读 helper
- `web/server.py`
- `web/templates/portfolio_home.html` 和/或 `web/templates/es.html`
- 新增 `tests/test_spec_088.py`

优先实现方式：

1. 读当前 `/ES` live position state
2. 读取当前 VIX / 所需输入
3. 按 Quant 提供的简化 stress band 规则形成只读估算
4. 在独立 panel / endpoint 暴露

如果实现中发现必须先做以下任一项，必须停止并报告：

- 改写 `/ES` 开仓 eligibility
- 改写 shared-BP crowding logic
- 修改 `strategy/state.py`
- 引入 broker write
- 设计完整动态预算 engine

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-08 | Planner 根据 `Q012 Phase A/B/C` 起草：将 `/ES` 下一步从 shared-BP governance 缩为 stressed-SPAN visibility monitoring | DRAFT |
| 2026-05-08 | Quant Researcher fidelity review PASS with 3 boundary edits：(1) F1 补入 Phase A VIX→stress_band 映射表及 A2 模型规范；(2) F2 补入 Quant-provided UI 免责文案要求；(3) AC2 细化为可执行断言 | — |
| 2026-05-08 | PM APPROVED | APPROVED |
| 2026-05-08 | Developer 实施；Quant Researcher review PASS：AC1–AC8 全部通过，三项 boundary edit 均正确落地，A2 re-mark 模型与映射表一致，免责文案由常量携带不由 Developer 自拟。Pre-existing test debt (test_spec_087 nav label) 已标记，与本 Spec 无关 | DONE |
