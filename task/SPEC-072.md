# SPEC-072: Frontend Dual-Scale Display + Broken-Wing Visual

Status: APPROVED
Blocker: BLOCKED_BY_HANDOFF

## 目标

**What**：在研究/可视化前端显示 IC_HV / aftermath 入场结构时，并列显示：
- `research_1spx` 口径（research 假设 1×SPX 名义）
- `live_scaled_est` 口径（按 live 实际 1×XSP ≈ 1/10 SPX 名义换算的估计值）

并对 broken-wing aftermath IC_HV 入场提供视觉高亮（call / put 长腿距离不对称的可视化）。

**Why**：
- 研究侧（`Q029`）发现：HC engine 硬编码 `qty=1`，但 live 中 HIGH_VOL 期间 ~36% 交易实际是 1×XSP，研究产出与 live 实际 PnL 在量级上有 ~10x 偏差
- frontend 双列显示让 PM / 研究者 / 操盘手能立即区分"研究语义"与"live 估计"
- broken-wing 视觉高亮配合 SPEC-071 落地，让 V3-A 结构在 UI 层显式可见，避免被误读为对称 IC

---

## 核心原则

- **frontend-only**：不动 backend / engine / selector；所有口径换算在前端 JavaScript 层
- **live-scaled 是 estimate**：明确标注为 `est`；不引入新的 backend 数据流
- **research view 仍可单列查看**：用户可在 dual / research-only / live-only 三种视图间切换
- **broken-wing 视觉高亮独立于 dual-scale**：两个能力可分别上线

---

## 当前 BLOCKER

MC v3 handoff 引用的 `task/SPEC-072_deploy_handoff.md` 在 HC repo 中**不存在**。该文件包含：
- 5 个 smoke test 场景定义
- 单文件 `web/html/spx_strat.html` 的具体 HTML / JS diff（HC 当前 web template 在 `web/templates/`，无 `spx_strat.html`，应该映射到 HC 的研究视图主入口，可能是 `web/templates/index.html` 或 `backtest.html`，由 Developer 实施时确认）

**MC 端还需要回传**：
1. SPEC-072 的实际代码 diff（或最终 HTML 文件）
2. 5 个 smoke test 场景的具体内容
3. live-scaled 换算因子（XSP = SPX / 10？是否还有其他 scaling？）

**在收到 MC 补全 handoff 之前，本 SPEC 处于 BLOCKED_BY_HANDOFF 状态**；Developer 不应在此基础上猜测 MC 实现细节。

下次 sync 时 Quant 会提醒 PM 向 MC 索取该 handoff 文件。

---

## 功能定义（intent，待 MC handoff 补全后细化）

### F1 — Dual-scale toggle

研究 / margin / backtest 视图顶部新增切换：
- `Research (1×SPX)` — 现有口径
- `Live est (1×XSP)` — 所有 PnL / BP / credit / debit 数值乘以 0.1（XSP scale factor）
- `Both` — 两列并排显示

### F2 — Broken-wing visual highlight

aftermath IC_HV 入场显示中，若 `LC delta != LP delta`（即 broken-wing），用：
- 不对称 wing 距离的 SVG / CSS 视觉化（call wing 较窄、put wing 较宽）
- 标签 `Broken-wing V3-A` badge

非 aftermath 对称 IC 不显示该高亮。

### F3 — Smoke test 场景

待 MC 补全 5 个 smoke test 定义；每个场景应至少覆盖：
- 1 个 aftermath broken-wing 入场
- 1 个非 aftermath 对称 IC 入场
- dual-scale toggle 行为
- 数值正确性（live_est = research × 0.1）
- broken-wing 高亮在符合条件时出现 / 在不符合时消失

---

## In Scope

| 项目 | 说明 |
|---|---|
| frontend dual-scale toggle | F1 |
| broken-wing visual highlight | F2 |
| 5 个 smoke test 场景执行 | F3，需 MC 补 handoff |
| HC 部署到 old Air 主机 | 通过 Server Maintainer 通道 |
| live smoke test 在部署后由 PM 验收 | AC10 |

## Out of Scope

| 项目 | 理由 |
|---|---|
| backend / engine 改动 | frontend-only |
| live execution side（XSP 实际下单逻辑）| 由 Q029 / Q033 主线处理 |
| 新增 backend API | 不需要；scaling 在前端 |
| 多 scale factor（如 1×ES）| 仅 XSP 1/10；其他 scale 后续 |

---

## 边界条件与约束

- **scaling factor 0.1 验证**：XSP 是 SPX 的 1/10 contract size，但 minimum tick / strike grid 不同；frontend 仅做 PnL / BP / credit 数值缩放；strike 数值不缩放
- **dual-scale 持久化**：用户切换偏好可写到 `localStorage`，不要求服务器侧保存
- **broken-wing 阈值**：`abs(LC.delta - LP.delta) > 0.02` 即判为 broken-wing；纯对称为 0.00 差

---

## 数据契约

| 字段 | 来源 | 说明 |
|---|---|---|
| `Trade.entry_credit` / `total_bp` / `exit_pnl` | trade_log.csv | frontend 乘以 0.1 即得 live_est |
| selector `Recommendation.legs[*].delta` | research view artifact | 用于 broken-wing 检测 |

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | research view 顶部出现三选一 toggle：Research / Live est / Both | 浏览器 visual |
| AC2 | toggle 到 Live est 时，所有 USD 数值显示为 research 值 × 0.1，且带 `(est)` 标记 | visual + spot check |
| AC3 | aftermath broken-wing IC_HV 入场显示 `Broken-wing V3-A` badge 与不对称 wing 视觉化 | visual |
| AC4 | 非 aftermath 对称 IC 入场无 broken-wing 高亮 | visual |
| AC5 | dual-scale 切换不重新请求服务器 | 浏览器 network tab |
| AC6 | 切换 toggle 后用户偏好保留至下次访问 | localStorage 验证 |
| AC7 | 5 个 smoke test 场景全部通过 | 待 MC 补全场景定义后逐项验证 |
| AC8 | 部署到 old Air 后页面可访问无报错 | curl + console |
| AC9 | 与 SPEC-073 后的 margin 页面 BCD 删除 / 卡片排版兼容（无空白槽位）| visual |
| AC10 | live smoke test：在 HC live 环境下用 dual-scale 看 1 笔历史 aftermath 入场，数值与手动 0.1× 计算一致 | PM 操作验证 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-24 | 初稿 — MC v3 handoff `MC-side DONE` 同步项；HC 待补 deploy handoff 与 smoke test 场景；BLOCKED_BY_HANDOFF | DRAFT |
| 2026-04-24 | PM 批量预批；标记 BLOCKED_BY_HANDOFF；下次 sync Quant 提醒 PM 向 MC 索取 `task/SPEC-072_deploy_handoff.md` | APPROVED |
