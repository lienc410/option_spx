# SPEC-087: Portfolio Command Center — Phase 1

Status: DONE

## Design Source

本 SPEC 是一个 **packaged implementation spec**，设计内容来源如下：

- **CEO Plan**: `ceo-plans/2026-05-07-portfolio-command-center-main-design.md` — 架构图、分阶段计划、Reviewer Concerns
- **Design System**: `DESIGN.md` — color tokens、typography、action state vocabulary、strategy card hierarchy
- **Quant Researcher**: action state 映射逻辑（SPX position_action 语义、/ES strategy_key 语义、Q041 candidate_status 语义）
- **Planner**: 将上述内容收口为可供 Developer 直接实现的窄范围 spec

本 SPEC 在 PM 审批前须完成 **Developer feasibility review**（见 F0 及 AC10）。

---

## 背景

当前 dashboard 是单策略展示（SPX 为中心），但项目已进入多策略并存的 portfolio 阶段（/ES short put 和 Q041 sleeves 均在运行）。每天使用时核心问题是"今天应该做什么"，当前布局没有明确答案。

SPEC-085 已建立 `/api/portfolio/summary` 和 `/api/sleeve-candidates` 两个只读 API。SPEC-086 定义了 /ES 告警阈值（EsStopLevel）。现有 `/api/recommendation` 和 `/api/es/recommendation` 均已在生产运行。

Phase 1 收口目标：在最小改动范围内，将现有 index.html 迁移到 `/spx`，并在 `/` 建立一个聚合只读的 Portfolio Command Center 首页。

---

## 目标

1. 将现有 SPX dashboard 路由迁移到 `/spx`；原 `/` 做 301 重定向，不破坏书签或 Telegram bot 链接
2. 在 `/` 建立新首页 Portfolio Command Center，聚合三个已存在 API 的只读展示
3. 统一 nav bar 为五页结构：Portfolio | SPX | /ES | Q041 | Backtest

---

## 核心原则

- **只读优先**：本 SPEC 不改动任何 API 的响应结构或写路径
- **fail-soft**：任何单个 API 失败不崩溃页面，降级显示 "unavailable"
- **设计 token 遵守**：所有颜色、字体、徽章使用 DESIGN.md 定义的 token，不自创新 token
- **Planner 不预先设计实现细节**：HTML/CSS 结构由 Developer 在 DESIGN.md 约束内自由实现
- **action state 由 API 透传**：Developer 不计算策略信号，只根据 API 返回字段做映射显示
- **Telegram bot 链接不能断**：`/api/*` 路由不变；`/` 做 301 而非删除

---

## In Scope

1. `web/server.py`: 新增 `/spx` 路由；原 `/` 改为 301 redirect
2. `web/templates/index.html` → 重命名为 `web/templates/spx.html`
3. `web/templates/portfolio_home.html`: 新建，作为 `/` 首页
4. 所有页面 nav bar 更新为 "Portfolio | SPX | /ES | Q041 | Backtest"
5. 首页 Today's Actions zone：聚合展示三个策略的 action state badge
6. 首页 Portfolio Snapshot zone：展示 `/api/portfolio/summary` 数据

---

## Out of Scope

- `/es` 策略详情页（Phase 2）
- `/q041` sleeve 观察页（Phase 3）
- `/portfolio-backtest` 回测页（Phase 4）
- `/api/es/position` 新 endpoint（Phase 2 前置）
- `/api/portfolio/summary` 扩展以包含 /ES bucket（Phase 2 前置，见 Known Gap）
- 任何 broker write
- 任何策略逻辑变更
- 任何 API 响应结构变更
- Unified portfolio routing engine（Q048 Stage 5，暂缓）

---

## 功能定义

### F0 — Developer Feasibility Review（Pre-condition，非实现任务）

在开始实现前，Developer 须确认：

1. Telegram bot 中是否存在指向 `/`（主页）的 web link button。若有，`/` 做 301 到 `/spx` 是否满足需求（bot 通常只链接到页面供用户浏览，301 对浏览器透明）
2. 是否有其他非 API 的 hardcoded `/` 引用（如 Telegram 消息模板、cron 健康检查）
3. 若存在需要直接打开 `/spx` 而非经过 redirect 的场景，在 SPEC 批注中记录

**Developer 以评论形式在本 SPEC 或 PR 中回复可行性确认，PM 审批后方可 merge。**

---

### F1 — 路由迁移：`/` → `/spx`（Sub-task 1a）

**server.py 变更：**

```
# 原 / 路由改为:
@app.route("/spx")
def spx_page():
    return render_template("spx.html")

# 新增 / 路由:
@app.route("/")
def index():
    from flask import redirect
    return redirect("/spx", code=301)
```

等到 F2（portfolio_home.html）完成后，`/` 路由改为：

```
@app.route("/")
def index():
    return render_template("portfolio_home.html")
```

即 F1 和 F2 应作为单次 PR 一起交付：`/` 最终指向 portfolio_home.html，不经过 301 中转。301 仅作为 F1 单独交付时的临时保护。**推荐以单 PR 同时完成 F1 + F2，此时 `/` 直接 render portfolio_home.html，不需要 301 临时状态。**

**模板变更：**

- `web/templates/index.html` → `web/templates/spx.html`（仅重命名，内容不变）
- `spx.html` 内部所有 `href="/"` → `href="/spx"`（nav 链接等）
- `spx.html` 中 SPX nav link 标记为 active；Portfolio nav link 指向 `href="/"`

**Nav bar 目标结构（所有页面统一）：**

```
Portfolio  |  SPX  |  /ES  |  Q041  |  Backtest
```

- Portfolio → `href="/"`, active on portfolio_home.html
- SPX → `href="/spx"`, active on spx.html
- /ES → `href="/es"`, placeholder（当前无页面，可 disabled 或 dim）
- Q041 → `href="/q041"`, placeholder
- Backtest → `href="/backtest"`, 指向现有 backtest.html（已存在）

---

### F2 — 新首页：Portfolio Command Center（Sub-task 1b）

新建 `web/templates/portfolio_home.html`，由 `web/server.py` 的 `/` route 渲染。

页面分为两个主要 zone，加 nav bar。

#### F2-A：Today's Actions Zone

从三个已存在 API 各发一次 fetch，独立 fail-soft：

| 策略行 | 数据来源 API |
|---|---|
| SPX | `GET /api/recommendation` |
| /ES | `GET /api/es/recommendation` |
| Q041 Sleeves | `GET /api/sleeve-candidates` |

每行展示：策略名称 + action state badge + 简短状态摘要（见下方 badge 映射）。

**Action State Badge 映射规则（display-only，Developer 不计算信号）：**

SPX（来自 `/api/recommendation` 响应字段 `position_action`）：

| `position_action` 值 | 显示 badge |
|---|---|
| `"OPEN"` 或 `"CLOSE_AND_OPEN"` | OPEN · `--green` |
| `"CLOSE"` | CLOSE · `--red` |
| `"WAIT"` 或 `"CLOSE_AND_WAIT"` | WAIT · `--text-muted` |
| 有开仓（`open == true`）且非以上 | HOLD · `--blue` |
| 其他 / 缺失 | WAIT · `--text-muted` |

/ES（来自 `/api/es/recommendation` 响应）：

| 条件 | 显示 badge |
|---|---|
| `strategy_key != "reduce_wait"` 且无 blocked 标志 | OPEN · `--green` |
| 响应含 `blocked: true` 或 `strategy_key == "reduce_wait"` | BLOCKED · `--text-muted`（reduced opacity） |
| API 调用失败 / error 字段存在 | —（unavailable 行，见 fail-soft） |

Q041 Sleeves（来自 `/api/sleeve-candidates` 响应，字段 `candidate_status`）：

| `candidate_status` 值 | 显示 badge |
|---|---|
| `"watching"` | REVIEW · `--gold-bg` + `--gold-border` |
| `"review_only"` | READ ONLY · `--gray-border` + `--text-muted` |
| 其他 / 无 candidates | WAIT · `--text-muted` |

注意：Q041 行可能聚合多个 sleeve，Developer 可选择显示优先级最高的 badge（REVIEW > READ ONLY > WAIT），或展示多行 sleeve。

**Badge 样式规范（来自 DESIGN.md）：**

- 字体：`--f-ui`，`0.60rem`，`font-weight: 500`，`text-transform: uppercase`，`letter-spacing: 0.10em`
- 颜色：见上方映射；背景用对应 `-bg` token，边框用对应 `-border` token
- Border radius: `5px`（pill 可用 `9999px`）

**Strategy name 样式：**

- SPX 行（Primary tier）：strategy name 用 `--f-display`
- /ES 行（Secondary tier）：name 用 `--f-ui`
- Q041 行（Sleeve/Observation tier）：name 用 `--f-ui` + `--text-2`

**Fail-soft 规则：**

若某 API fetch 失败（network error、HTTP 5xx、响应含 `error` 字段），对应行显示：

```
[策略名]    [API UNAVAILABLE] ← --text-muted, --f-ui
```

页面不崩溃，其余行正常显示。

#### F2-B：Portfolio Snapshot Zone

从 `/api/portfolio/summary` 获取数据（SPEC-085 F2，已存在）。

展示内容：

1. **BP by Bucket**：水平 bar 或数值列表，显示各 bucket 的 BP 占用
   - 当前 `/api/portfolio/summary` 包含 SPX live bucket 和 Q041 bucket
   - Known Gap（Phase 2 修复）：`/api/portfolio/summary` 当前不含 /ES bucket；Phase 1 仅展示现有字段，不强求 /ES 数据
2. **Open Position Count**：各策略当前开仓数（来自 summary）
3. **Idle Capacity**：空闲 BP 容量（来自 summary）

所有数值使用 `--f-mono`。所有标签使用 `--f-ui`。

**Fail-soft：** 若 `/api/portfolio/summary` 失败，Portfolio Snapshot 区域显示 "Portfolio data unavailable"，不影响 Today's Actions zone。

**Known Gap（在页面上以 muted 文字标注）：**

> /ES BP bucket not yet included — Phase 2

---

## 边界条件

| # | 场景 | 预期行为 |
|---|---|---|
| B1 | `/api/recommendation` 返回 HTTP 500 | SPX 行显示 "API UNAVAILABLE"，页面其余部分正常 |
| B2 | `/api/es/recommendation` 超时或网络失败 | /ES 行显示 "API UNAVAILABLE" |
| B3 | `/api/sleeve-candidates` 返回空 candidates 数组 | Q041 行显示 WAIT badge |
| B4 | `/api/portfolio/summary` 返回 HTTP 500 | Portfolio Snapshot 显示 "Portfolio data unavailable" |
| B5 | 用户访问旧书签 `http://localhost:5050/` | 在 F1+F2 合并交付后，`/` 直接渲染 portfolio_home.html（无重定向） |
| B6 | Telegram bot 存在指向 `/` 的 web 链接 | F0 feasibility review 需确认；若 bot 只做浏览器跳转，则无影响（bot API 路径均为 `/api/*`） |
| B7 | `/es` 或 `/q041` nav link 被点击（Phase 1 无页面） | placeholder 链接可渲染空页或 404；不阻塞 Phase 1 交付 |
| B8 | `position_action` 字段缺失或为未知值 | SPX badge 降级为 WAIT |
| B9 | `/api/es/recommendation` 返回不含 `strategy_key` 字段 | /ES badge 降级为 BLOCKED |

---

## Acceptance Criteria

| AC# | 描述 | 验证方式 |
|---|---|---|
| AC1 | `GET /spx` 返回 HTTP 200，渲染原 SPX dashboard 全部功能（推荐卡片、持仓、回测入口）无回归 | 手动访问 `/spx`，所有现有功能正常 |
| AC2 | `GET /` 在 F1+F2 合并交付后渲染 portfolio_home.html；不存在临时 301 状态 | 访问 `/`，页面标题或 h1 含 "Portfolio" 字样 |
| AC3 | 所有页面（`/`、`/spx`、`/backtest`）的 nav bar 显示 "Portfolio \| SPX \| /ES \| Q041 \| Backtest" 五个 link；当前页 link 显示 active 样式（`--gold` + `--gold-bg`） | 各页面逐一检查 nav |
| AC4 | 首页 Today's Actions zone 显示三行（SPX、/ES、Q041），每行含策略名称 + action state badge；badge 颜色与 DESIGN.md Action State Vocabulary 一致 | 访问 `/`，检查三行渲染；对比 DESIGN.md 颜色定义 |
| AC5 | 首页 Portfolio Snapshot 显示 BP by bucket（SPX live / Q041）+ open position count + idle capacity，数值来自 `/api/portfolio/summary` | 对比 `/api/portfolio/summary` JSON 原始响应与页面展示数值 |
| AC6 | 当 `/api/es/recommendation` 不可用时，/ES 行显示 "API UNAVAILABLE"（或等效降级文字），页面其他内容不受影响 | 临时屏蔽 `/api/es/recommendation` endpoint，刷新页面 |
| AC7 | 当 `/api/portfolio/summary` 不可用时，Portfolio Snapshot 区域降级显示，Today's Actions zone 不受影响 | 临时屏蔽 `/api/portfolio/summary` endpoint，刷新页面 |
| AC8 | `/api/recommendation`、`/api/es/recommendation`、`/api/sleeve-candidates`、`/api/portfolio/summary` 四个 API 的响应结构与 Phase 1 前完全一致（无新增字段、无删除字段、无类型变更） | `git diff` 确认 `web/portfolio_surface.py`、`strategy/selector.py` 无 API shape 相关变更 |
| AC9 | 所有 action badge 使用 DESIGN.md 定义的 CSS token：OPEN=`--green`、HOLD=`--blue`、CLOSE=`--red`、WAIT/BLOCKED=`--text-muted`/`--gray-*`、REVIEW=`--gold-bg`+`--gold-border`；badge 字体为 `--f-ui` 0.60rem 500 weight uppercase | 检查 portfolio_home.html CSS / inline style，对照 DESIGN.md Action State Vocabulary 表 |
| AC10 | Developer feasibility review 评论已在 PR 中提交，确认 Telegram bot web link 不因 `/` 行为变更而断链（或说明无 bot web link 引用 `/`） | PR review comments 中存在 Developer 的 feasibility 确认文字 |

---

## 实现指导

### 文件变更清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `web/server.py` | Edit | 新增 `/spx` 路由；`/` 路由改为渲染 portfolio_home.html |
| `web/templates/index.html` | Rename → `spx.html` | 仅重命名；内容变更限于 nav link href 更新 |
| `web/templates/spx.html` | Edit | 更新 nav：`href="/"` → `href="/spx"`（自引用）；Portfolio link → `href="/"`；添加 /ES、Q041 placeholder links；SPX link 标记 active |
| `web/templates/portfolio_home.html` | Create | 新建 Portfolio Command Center 首页 |
| `web/templates/backtest.html` | Edit（可选）| 更新 nav bar 为五页结构（若 backtest.html 有独立 nav） |

### portfolio_home.html 技术指导

- 页面 fetch 逻辑：三个 Today's Actions API 并发 fetch（`Promise.all` 或各自独立 fetch + catch），Portfolio Snapshot 独立 fetch
- 每个 fetch 包裹在 try/catch；失败时 render unavailable 状态，不 throw
- CSS 复用 `spx.html` 的 `:root` CSS variables 块（直接复制或提取为 shared partial）；**不引入新 token**
- Google Fonts `<link>` 复用与 spx.html 完全相同的链接（Newsreader + JetBrains Mono + DM Sans）
- 布局：880px max-width，24px side padding，与 spx.html 保持一致（`DESIGN.md § Layout`）
- Nav bar HTML 结构与 spx.html 保持一致，仅 active class 位置不同

### 不应变更的文件

- `web/portfolio_surface.py` — API 逻辑不变
- `strategy/selector.py` — 推荐逻辑不变
- `strategy/state.py` — 持仓状态不变
- 所有 `/api/*` 路由 handler — 响应 shape 不变

---

## Review — Quant Researcher 2026-05-07

- 结论：PASS
- F0 feasibility：`notify/telegram_bot.py` 无任何指向 `/` 的 web link，路由变更安全
- AC1–AC10 全部通过（44/44 tests，含 SPEC-085 / SPEC-086 regression）
- Badge CSS 完全遵守 DESIGN.md Action State Vocabulary：`--f-ui` 0.60rem 500 uppercase letter-spacing:0.10em；8 种状态（open/hold/close/wait/blocked/review/readonly/unavail）颜色 token 逐一核对正确
- Badge 映射逻辑：SPX `position_action` → OPEN/CLOSE/WAIT/HOLD；/ES `strategy_key == "reduce_wait"` → BLOCKED；Q041 `candidate_status` → REVIEW / READ ONLY；unknown fallback → WAIT —— 均符合 SPEC-087 F2 规定，未超出 display-only 职责
- 所有 API response shapes 未变更（portfolio_surface.py / selector.py / state.py 均未修改）
- Known Gap 已在页面上以 muted 文字标注（/ES BP bucket — Phase 2），符合 F2-B 要求

## 变更记录

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-05-07 | v0.1 DRAFT | 初稿，基于 CEO Plan 2026-05-07 和 DESIGN.md；待 Developer feasibility review |
| 2026-05-07 | v0.2 APPROVED | PM 审批通过；进入 Developer feasibility review → 实施路径 |
| 2026-05-07 | v0.3 DONE | Developer 实施完成，44/44 tests PASS；Quant Researcher review PASS |
| 2026-05-07 | v1.0 DONE | Developer 实施完成；F0 确认 Telegram bot 无 `/` web link；F1+F2 合并交付；server.py 新增 `/spx` 路由，`/` 直接渲染 portfolio_home.html；spx.html 从 index.html 复制并更新 nav；backtest.html nav 更新为五页结构；13 项新测试全部通过，37 tests OK。|
