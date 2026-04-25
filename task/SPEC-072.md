# SPEC-072: Frontend Dual-Scale Display + Broken-Wing Visual

Status: APPROVED
Blocker: (none — unblocked 2026-04-25 by `MC_Response_2026-04-25_v2.md` §2.1)

## 目标

**What**：在 HC 前端中并列显示研究口径与 live 估计口径，并对 aftermath broken-wing IC_HV 入场结构提供视觉强调：
- `research scale` — research 假设的 `1×SPX` 名义值
- `live estimated scale` — 按 live `SizeTier` × XSP 缩放后的估计值
- `Broken-wing IC` 紫色 badge + `BUY` 腿 delta 紫色加粗，仅在 aftermath broken-wing 入场时出现

**Why**：研究输出（HC 当前 IC_HV 全程 `qty=1` 编码 `1×SPX`）与 live 实际下单（aftermath HIGH_VOL 通常 `1×XSP` ≈ `0.1×SPX` 名义）在量级上有 ~10× gap。Q029 同时识别这一 parity issue 与 reporting-layer 缓解方案（`research_1spx + live_scaled_est`，由 SPEC-072 实现）。本 SPEC 仅做前端缩放显示，不动 backend / engine / selector。

---

## 核心原则

- **frontend-only**：不改 backend、engine、selector、artifact schema；所有缩放在 HTML / JS 层
- **live_scaled 是 estimate**：所有缩放数值都带 `(est)` 标记
- **scale factor 来自 SizeTier**：HIGH_VOL ≈ `0.1`（XSP），NORMAL = `1`（HALF tier），LOW_VOL = `2`（FULL tier）；strike 不缩放
- **broken-wing 视觉与 dual-scale 独立**：F2 / F5 / F6 是缩放，F3 / F4 是 broken-wing 强调
- **HC 文件映射 ≠ MC 单文件**：MC 在单文件 `web/html/spx_strat.html` 中实现；HC 当前 frontend 拆分为 `web/templates/{index,backtest,margin,matrix,performance}.html`，本 SPEC 按功能落到对应文件

---

## HC 文件映射

| MC 单文件功能段 | HC 实施目标文件 | 备注 |
|---|---|---|
| F1 JS helpers | 共用注入；首选 `web/templates/backtest.html` 内 `<script>` 段（其它页面通过 `include` 复用），若实现上更便利可放到独立 `static/js/spec072_helpers.js` | Developer 自决 |
| F2 Live Recommendation BP badge | `web/templates/index.html`（live recommendation 卡片） | |
| F3 Legs table broken-wing 强调 | `web/templates/index.html`（legs table） | |
| F4 Research view banner | `web/templates/backtest.html`（aftermath view 顶部） | |
| F5 Trade log table dual columns | `web/templates/backtest.html`（trade log section） | |
| F6 Current Position BP | `web/templates/margin.html`（BP capacity bar） | |
| F7 Backtest tab legend / info | `web/templates/backtest.html`（页脚 legend） | 包含 `SPEC-071 addendum` 链接 |

Developer 在实施时若发现某段内容已被其它 partial template 覆盖，可在文件映射上做局部调整，但需在 PR 描述中注明实际落点。

---

## 功能定义

### F1 — JS helpers

提供以下 helper 函数（位置由 Developer 决定，建议集中在一处 `<script>` 段或 `static/js/spec072_helpers.js`）：

- `liveScaleFactor(regime)` — 给定 regime 返回 scale factor：
  - `HIGH_VOL` → `0.1`
  - `NORMAL` → `1`
  - `LOW_VOL` → `2`
- `formatDualBp(bpResearch, regime)` — 返回 `"30.0% + 3.0% est"` 形式的 dual-scale 字符串；非 HIGH_VOL 退回单值
- `formatDualPnl(pnlResearch, regime)` — 同上，应用于 USD 数值
- `isBrokenWingIc(legs)` — 检测 BUY CALL 与 BUY PUT 的 delta 差异是否 > 0.02（即 broken-wing 阈值）

### F2 — Live Recommendation BP badge 双值

- 非 `HIGH_VOL` recommendation：BP badge 单值（现状）
- `HIGH_VOL aftermath` recommendation：BP badge 双值，例 `"30.0% + 3.0% est"`
- 数值来源：现有 BP 字段乘 `liveScaleFactor`

### F3 — Legs table broken-wing 强调

- 当 `isBrokenWingIc(rec.legs) === true`：
  - legs table 上方显示紫色 `Broken-wing IC` badge
  - `BUY` 腿（call long + put long）的 delta 数值用紫色 `font-weight:bold` 渲染
- 非 broken-wing 情况：保持现有 plain table

### F4 — Research view banner

- `web/templates/backtest.html` 中 `spec064_aftermath_ic_hv` 视图加载时：
  - banner 下方显示紫色 scale disclaimer：`"Research scale (1×SPX); live shown as scaled estimate"`
  - 仅在 aftermath view 显示，其他 view 不出现

### F5 — Trade log table 双列

- `web/templates/backtest.html` trade log 表中：
  - `HIGH_VOL` regime 行的 `entry_credit` / `total_bp` / `exit_pnl` 列改为双列显示（research + live est）
  - `LOW_VOL` 与 `NORMAL` 行保持单列
- 双列实现可以是单列单元格内 `<span>research</span> + <span class="est">live est</span>`，或额外列；Developer 选其一

### F6 — Current Position BP

- `web/templates/margin.html` 的 BP capacity bar：
  - 当前持仓存在 `HIGH_VOL` regime 仓位时，bar 下方文字显示 `"BP used: X% + Y% est"`
  - 否则保持现状

### F7 — Backtest tab legend / info

- `web/templates/backtest.html` 页脚 legend 区块加一行：
  - `"Aftermath broken-wing IC follows SPEC-071 addendum (LC δ0.04 / LP δ0.08)"`，含锚点链接到 `task/SPEC-071.md`

---

## 接受测试场景（ST1–ST5）

按 MC §2.1.c 的 5 项 smoke test 复用：

### ST1 — Tab 切换无 regression
- 在 `web/templates/index.html` 启动 dev server，分别切换 Today / Backtest / Position（或 HC 等价 nav entries）
- 浏览器 console 不出现 JS 报错

### ST2 — Live Recommendation 卡片
- 选一个非 `HIGH_VOL` 推荐日期 → BP badge 单值，无紫色 badge
- 选一个 `HIGH_VOL aftermath` 推荐日期（例 2026-03-09）→
  - BP badge 双值，例 `30.0% + 3.0% est`
  - Legs table 上方紫色 `Broken-wing IC` badge
  - `BUY CALL` 与 `BUY PUT` delta 紫色加粗

### ST3 — Backtest tab 切换 view
- `production` view：trade log 单列显示
- `spec064_aftermath_ic_hv` view：
  - Banner 下方紫色 scale disclaimer 出现
  - Trade log `HIGH_VOL` 行 PnL / BP / credit 双列
  - `LOW_VOL` 行单列

### ST4 — Position tab 开仓状态
- 当前 live `HIGH_VOL` regime 持仓存在时（例 backtest 末日 mock）→ BP capacity bar 双值
- 非 HIGH_VOL → 单值

### ST5 — Modal 开关无异常
- 触发 `Open / Close / Correct / Void` 四个 modal
- 打开关闭无 console error

---

## In Scope / Out of Scope

| In Scope | Out of Scope |
|---|---|
| F1–F7 frontend 实施 | backend / engine / selector 改动 |
| ST1–ST5 smoke test 跑通 | live 端实际 XSP 下单（Q029 / Q033 主线） |
| HC 多文件映射决策记录 | 多 scale factor（如 ES）扩展 |
| `localStorage` 不强制（PM 接受 session-only） | 新 backend API |

---

## 数据契约

| 字段 | 来源 | 用途 |
|---|---|---|
| `Trade.entry_credit / total_bp / exit_pnl` | `trade_log.csv` 既有列 | F5 trade log 双列 |
| `Recommendation.legs[*].delta` | `data/research_views.json` | F3 broken-wing 检测 |
| `Recommendation.regime` 或等价 vol cell | `data/research_views.json` | F2 / F6 scale 选择 |

后端不新增字段。

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `liveScaleFactor / formatDualBp / formatDualPnl / isBrokenWingIc` 四个 helper 实现且可在 console 直接调用得正确返回值 | 浏览器 console |
| AC2 | F2 在 `HIGH_VOL aftermath` recommendation 上显示双值 BP badge | ST2 visual |
| AC3 | F3 broken-wing 紫色 badge + delta 加粗仅在 `isBrokenWingIc` 为 true 时出现 | ST2 visual |
| AC4 | F4 banner scale disclaimer 仅在 `spec064_aftermath_ic_hv` view 出现 | ST3 visual |
| AC5 | F5 trade log 在 `HIGH_VOL` 行显示双列；`LOW_VOL` 行单列 | ST3 visual + spot check 数值 |
| AC6 | F6 BP capacity bar 在持有 `HIGH_VOL` 仓位时显示双值 | ST4 visual |
| AC7 | F7 legend 出现 SPEC-071 addendum 描述及锚点链接 | view-source 检查 |
| AC8 | 切换三个主 tab 与四个 modal 无 JS console error | ST1 + ST5 |
| AC9 | backend 文件 MD5 不变；`data/research_views.json` `mtime` 不变 | shasum + stat |
| AC10 | PM live smoke test：在 HC live 环境下用 dual-scale 看 1 笔历史 aftermath 入场，数值与手动 0.1× 计算一致 | PM 操作 |

---

## 边界条件与约束

- **scale factor 由 regime 决定，不是 sizeTier**：本 SPEC 直接用 regime 字符串映射；如果未来 sizeTier 与 regime 解耦，再开 SPEC
- **broken-wing 阈值**：`abs(legs.BUY_CALL.delta - legs.BUY_PUT.delta) > 0.02`；纯对称为 0.00 差，不应触发紫色 badge
- **strike 不缩放**：因为 live 直接交易 XSP，XSP option chain 的 strike 已是 1:10 后的数值，不二次缩放
- **数值精度**：所有 dual-scale 数字保留两位小数；不格式化为千分位以避免与现有显式

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-24 | 初稿 — MC v3 handoff `MC-side DONE` 同步项；HC 待补 deploy handoff，标记 BLOCKED_BY_HANDOFF | DRAFT |
| 2026-04-24 | PM 批量预批；下次 sync Quant 提醒 PM 向 MC 索取 deploy handoff | APPROVED (BLOCKED) |
| 2026-04-25 | MC 在 `MC_Response_2026-04-25_v2.md` §2.1 提供完整 spec 内容（F1–F7、5 项 smoke、AC 与 live-scale 规则）；HC 解封并按 §2.1 重写 SPEC，落到多文件映射 | APPROVED — 交 Developer 实施 |
