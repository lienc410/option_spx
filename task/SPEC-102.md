# SPEC-102 — HV Ladder Dedicated Frontend (live + backtest page pair)

**Type**: research-driven (UI scope)
**Date**: 2026-05-15
**Status**: DONE
**Owner**: Quant Researcher → PM approval → Developer impl
**Source**: PM directive 2026-05-15 + Q071 promote (SPEC-101 paper deployment)

**PM 决策 (2026-05-15)**:
1. `/es-backtest` HV Ladder tab — **保留为 archive**（不删，demote 为 "Archive" tab label + thin redirect 卡）
2. Nav 集成 — **顶层主项**，与 aftermath/q041 平级
3. Telegram alert history section — **要**（从 JSONL 同源读取，无需新增持久化）
4. Crisis windows 表 — **进 `/hvladder_backtest`**

---

## 0. TL;DR

将 HV Ladder 从 `/es-backtest` 的一个 tab 升格为符合项目惯例的独立页对：

- **`/hvladder`** — live monitoring (VIX 临近度、gate checklist、paper-trade log、recent alerts)
- **`/hvladder_backtest`** — research view（搬运现有 tab 内容 + 扩展）

理由：HV Ladder 是 2nd Quant 明确定性的新策略（不是 V2f filter），UI 应反映这个心智模型；PM paper 阶段需要 signal-aware 实时面板，不仅是回测对比卡。

---

## 1. Background

### 1.1 现状
- HV Ladder 当前为 `/es-backtest` 的一个 tab（SPEC-101 部署，af2b2b1）
- Tab 内容：V2f Base vs HV Ladder 对比卡 + Monitoring Snapshot + caveat banner
- 已有 API: `/api/es-backtest/hvlad`

### 1.2 项目页对约定
| Strategy | Live page | Backtest page |
|---|---|---|
| Aftermath | /aftermath | /aftermath_backtest |
| Q041 | /q041 | /q041_backtest |
| Q042 | /q042 | /q042_backtest |
| Portfolio | /portfolio_home | /portfolio_backtest |
| ES (V2f) | /es | /es-backtest |
| **HV Ladder** | **(missing)** | (in /es-backtest tab) |

HV Ladder 不符合这个 pattern。SPEC-102 补齐。

### 1.3 PM paper-trade 观察需求
- PM 自主决定 paper→production 时机（feedback_spec_review_obligation）
- 需要 signal-aware 实时监控（VIX 距 22 还有多远、本周/本月是否触发过、累计 paper entries）
- 这些信息放 `/es-backtest` 一个 tab 内挤；放 `/hvladder` 主页自然

---

## 2. Scope

### 2.1 `/hvladder` (live monitoring) — 新建

| Section | 内容 |
|---|---|
| Header | 策略名 "ES High-Vol Sell Put Ladder" + caveat banner（paper/shadow mode only） |
| **VIX Live Card** | 当前 VIX、5TD 平均、最近收盘日期、距 gate threshold 的差值 (VIX − 22) |
| **Gate Status Checklist** | 五项实时状态: ☑/☐ warmed, trend_ok (BULLISH), cadence_ok, active_slots<5, vix_ok (≥22) |
| **Today's Signal** | 若所有 5 项都 ☑ → "HV Ladder signal LIVE"（绿色高亮）；否则显示哪一项阻挡 |
| **Recent Paper Entries** | 从 `data/q071_hv_paper_trades.jsonl` 读最近 20 条，按时间倒序：date, vix, strike, premium, status |
| **Telegram Alert History** | 同一 JSONL 数据另一视角：alert pushed at {timestamp}, gate ≥22 ✓, slots {n}/5；强调 "alert pushed" 框架，N=10 条 |
| **Mini Stats** | 累计 paper signal 次数、最远 VIX 触及高点、最近 30 天内 ≥22 的天数 |

### 2.2 `/hvladder_backtest` (research) — 从 `/es-backtest` 抽离

- 把现有 `/es-backtest` HV Ladder tab 的所有 widget 整体迁移到 `/hvladder_backtest`
- 增加：worst-year 列表、crisis windows (GFC/COVID/Bear22) 表格（已有 q071_p5_crisis.csv 数据但 UI 未展示）
- 保留 V2f Base vs HV Ladder 对比卡

### 2.3 `/es-backtest` 改动 (PM 决策: 保留为 archive)

- HV Ladder tab 重命名为 **"Archive (HV Ladder)"** 或在 label 上加 `[archived]` 标记
- Tab 内容替换为 thin redirect 卡:
  > "HV Ladder 已迁移到独立页 → [/hvladder](live) / [/hvladder_backtest](research)"
- 保留路由可访问（向后兼容旧书签 / 旧分享链接）
- 不动 `/api/es-backtest/hvlad` endpoint（仍由独立 page 使用）

### 2.4 新增 API

| Endpoint | 用途 |
|---|---|
| `GET /api/hvladder/live` | 返回 VIX 当前值 + 5TD avg + 距 gate 差 + gate checklist (warmed/trend/cadence/slots/vix) + signal status |
| `GET /api/hvladder/paper_trades?limit=20` | 读 `data/q071_hv_paper_trades.jsonl`，返回最近 N 条 |
| `GET /api/hvladder/stats` | 累计 signal count、近 30/90/365 天 VIX≥22 天数等 |

回测 API 沿用现有 `/api/es-backtest/hvlad`。

---

## 3. File Changes

| File | Action |
|---|---|
| `web/templates/hvladder.html` | NEW — live monitoring page |
| `web/templates/hvladder_backtest.html` | NEW — research page (从 es_backtest.html 抽出 HV Ladder tab 内容) |
| `web/server.py` | NEW: `/hvladder`, `/hvladder_backtest` 路由 + `/api/hvladder/*` 三个 API |
| `web/templates/es_backtest.html` | EDIT — HV Ladder tab 改为 thin redirect 卡 |
| `web/templates/portfolio_home.html` 或 nav | EDIT — 顶部 nav 增加 "HV Ladder" 链接 |

无 backend / strategy 文件改动 —— SPEC-101 已经把 engine 部署好。

---

## 4. Acceptance Criteria

| AC# | 描述 | Verification |
|---|---|---|
| AC-102-1 | `/hvladder` 可访问，404→ 200 | oldair curl |
| AC-102-2 | VIX Live Card 显示当前 VIX、5TD avg、距 22 差值 | 视觉 + JSON 对比 yfinance latest |
| AC-102-3 | Gate Status Checklist 显示 5 项实时状态 | 当 VIX < 22 时 vix_ok ☐；mock VIX=24 时 vix_ok ☑ |
| AC-102-4 | Recent Paper Entries 读 JSONL；文件空时显示 "No paper entries yet" | 删除/清空 JSONL 后刷新验证 |
| AC-102-5 | `/hvladder_backtest` 显示完整对比卡 + Monitoring Snapshot + Crisis Windows 表 | 视觉 |
| AC-102-6 | `/api/hvladder/live` 返回结构正确 (vix_current, vix_5td_avg, gate_status{...}, signal_live) | curl test |
| AC-102-7 | `/api/hvladder/paper_trades` 返回数组，fail-soft (文件不存在返回空数组) | rm + curl test |
| AC-102-8 | `/es-backtest` HV Ladder tab 仍可访问，显示重定向卡 + 链接到 /hvladder_backtest | 视觉 |
| AC-102-9 | Caveat banner（paper/shadow mode only）显示在 `/hvladder` 顶部 | 视觉 |

---

## 5. Out of Scope

- 修改 `run_phase2_hvlad` 或 `V2F_VIX_MIN_ENTRY` (SPEC-101 已定)
- Telegram alert 推送逻辑变更（SPEC-101 已部署）
- 生产 bot（SPEC-061）改动
- Paper-trade JSONL 写入路径变更
- 数据库化 paper trades（保持 JSONL，简单足够）

---

## 6. Design Notes

### 6.1 VIX 实时数据来源
- 沿用 `signals/vix_regime.py` 的 `fetch_vix_history` 或 `get_current_vix_snapshot`
- 5TD avg = 最近 5 个交易日的 close 均值
- 注意 stale guard：如 latest VIX 数据 > 1 个交易日 → 显示 "VIX data stale" 警告（SPEC-101 已实现 stale guard 逻辑，前端调用即可）

### 6.2 Gate Status 实时计算
- 复用 `_run_phase2_v2f_on_frame` 中的判定逻辑
- 但只算"今日"一行，不跑完整回测
- 或：单独写一个轻量 `evaluate_hvladder_today()` 函数，返回 dict
  - 这个可放 `research/strategies/ES_puts/backtest.py` 或新建 `strategy/hvladder_live.py`

### 6.3 配色 / 设计语言
- 遵循 DESIGN.md 与现有 portfolio_home / aftermath 页一致
- HV Ladder 是 ES 系列衍生 → 沿用 ES 页深绿/金的色系；caveat banner 黄色
- VIX 临近度 (VIX − 22) 用颜色编码：< -5 灰（远）、-5 ~ 0 黄、≥ 0 绿

### 6.4 Nav 集成 (PM 决策: 顶层主项)
- HV Ladder 放顶 nav 主项，与 aftermath/q041 平级
- 显示 label: `HV Ladder` (不要写 "ES HV Ladder" — 顶 nav 简洁)
- 顺序建议: ... / es / **hvladder** / aftermath / ... （HV Ladder 紧接 ES 之后，因为 chassis 来自 V2f）
- 凸显新策略地位（呼应 naming hygiene memory）

---

## 7. Deploy

1. Developer 实施 → 本地 AC1-AC9 验证
2. Commit + push
3. Old Air `git pull` + restart web（per feedback_deploy_oldair）
4. Smoke verify: `curl https://oldair.spxstrat.app/hvladder` + `/api/hvladder/live`

---

## 8. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| 模板 + API 实现 | ~30 min | ~1 day |
| 视觉调整 / nav 集成 | ~15 min | ~0.5 day |
| AC 验证 + deploy | ~10 min | ~1h |
| **Total** | **~1h** | **~2 days** |

---

## 9. PM 决策 (2026-05-15, 已锁定)

1. `/es-backtest` HV Ladder tab → **保留为 archive**（label 加 `[archived]` + thin redirect 卡）
2. Nav 集成 → **顶层主项**（顺序: ES → HV Ladder → Aftermath → ...）
3. Telegram alert history section → **要**（与 paper entries 同源 JSONL，两个视角）
4. Crisis windows 表 → **进 `/hvladder_backtest`**（数据源 `research/q071/q071_p5_crisis.csv`）

---

## 10. 参考文件

- `research/q071/q071_memo_2026-05-14.md` — 策略 verdict + 数据来源
- `task/q071_2nd_quant_review_2026-05-14.md` — naming hygiene 要求
- `task/SPEC-101.md` — engine + paper-trade infrastructure
- `task/SPEC-101_handoff.md` — Developer 部署记录
- `web/templates/es_backtest.html` — 现有 HV Ladder tab（待迁移源）
- `data/q071_hv_paper_trades.jsonl` — paper trade 持久化来源
- `research/q071/q071_p5_crisis.csv` — crisis windows 数据

---

## 11. Implementation Review — 2026-05-15

**Result**: PASS / DONE

- AC-102-1 PASS: `/hvladder` route added and returns 200.
- AC-102-2 PASS: VIX live card consumes `/api/hvladder/live` with current VIX, 5TD average, close date, and gate distance.
- AC-102-3 PASS: Gate checklist returns and renders warmed / trend_ok / cadence_ok / slots_ok / vix_ok.
- AC-102-4 PASS: `/api/hvladder/paper_trades` reads `data/q071_hv_paper_trades.jsonl` and fail-softs to an empty array.
- AC-102-5 PASS: `/hvladder_backtest` displays HV Ladder backtest comparison and crisis windows from `research/q071/q071_p5_crisis.csv`.
- AC-102-6 PASS: `/api/hvladder/live` returns `vix_current`, `vix_5td_avg`, `gate_status`, and `signal_live`.
- AC-102-7 PASS: paper trades API handles missing/empty source without breaking.
- AC-102-8 PASS: `/es-backtest` retains an archived HV Ladder tab with redirect links to `/hvladder` and `/hvladder_backtest`.
- AC-102-9 PASS: `/hvladder` top banner states paper/shadow mode only.

No engine, strategy, production bot, Telegram alert, or paper-write behavior changed.
