# SPEC-093: Q041 Strategy Matrix Page + Backtest Page Redesign

Status: DONE

## Design Source

Design-driven + engineering-driven.

- **PM**：Q041 现在是主策略之后的第二优先策略，前端应按照 SPX 策略页面组和 /ES 策略页面组的标准，重新设计和充实 Q041 的策略 matrix 页和回测页
- **Design latitude**：前端工程师拥有图表类型和布局的完整设计自由度。PM 关心"哪个图表对量化交易员有帮助"——这是设计约束，不是实现约束

## 设计原则（必须在实现前形成决策）

前端工程师在动手前，应先输出一个**图表清单草案**（不需要 mockup，文字描述即可），回答以下问题：

1. 哪些图表能帮助 PM 判断"Tier 1 paper-trading 进展是否健康"？
2. 哪些图表能帮助比较三个 Tier 之间的风险/收益结构？
3. 如何展示 VIX regime 对 Q041 策略表现的影响（这是量化交易员最关心的条件分布）？

**图表清单草案需 PM 确认后再开始 HTML/JS 实现。**

## 当前状态（实现前阅读）

- Q041 已有基础回测页：`web/templates/q041_backtest.html`（sleeve-level 摘要卡片 + trade-log tab）
- Q041 数据来源：`data/q041_portfolio_attribution_latest.json`（F3 attribution artifact）+ paper ledger `data/q041_paper_trades.jsonl`
- 三层 Tier 结构：
  - **Tier 1**：SPX CSP Δ0.20 DTE30（正式 paper-trading，已激活）
  - **Tier 2**：GOOGL / AMZN CSP（正式 paper-trading，已激活，tail-caveated）
  - **Tier 3**：COST / JPM Earnings IC（observe-only）

## 功能要求（WHAT，不规定 HOW）

### Strategy Matrix 页

必须呈现的信息维度：

| 维度 | 说明 |
|---|---|
| 三层 Tier 状态 | Tier 1 / Tier 2 / Tier 3 各自的当前状态（paper-trading active / observe-only）|
| 核心历史指标 | 每个 Tier 的 AnnROE / Sharpe / WR / avg P&L per BP-day / worst trade |
| 风险指标 | 最大单笔亏损、peak BP%（来自 A3 IV stress appendix §11 的 VIX +40 shock 数据）|
| Tail caveat 可见性 | Tier 2 的 COVID tail warning 必须有视觉标注（不能隐藏在 hover 里）|
| Paper-trading 进度 | 当前已记录的 paper trade 笔数 vs 目标（Tier 1 goal: 有意义的样本；Tier 2: 同）|

### Backtest 页

必须呈现的信息维度：

| 维度 | 说明 |
|---|---|
| 累计 P&L 曲线 | 三个 Tier 各自的累计 P&L，可叠加对比（历史回测 + paper-trading 实际）|
| Trade entry/exit overlay | 同 SPX 策略页的 SPX Price + 入场/出场标注（每个 Tier 独立或叠加）|
| VIX regime 分布 | 入场时的 VIX 水位分布（HIGH_VOL / NORMAL / 具体数值区间）|
| IV at entry 分布 | 入场时的 IV（或 IVP）分布——量化交易员用于判断"是否在合理 premium 环境入场"|
| P&L by DTE at close | 不同持仓周期（DTE 剩余天数）下的 P&L 分布——判断是否该更早平仓 |
| Win rate by symbol | Tier 2 中 GOOGL vs AMZN 的独立 WR 和 P&L 对比 |
| BP utilization timeline | 随时间的 BP 使用率折线（判断是否在合适时机部署）|

## 导航规范

Q041 页面组应当有独立导航入口，与 SPX（`/spx`）和 /ES 页面组平级：
- `/q041` — Strategy Matrix 主页
- `/q041/backtest` — 回测 + 历史分析页

导航 bar 需包含 Q041 入口（参考当前 SPX / /ES 的 nav 实现）。

## 实现流程

1. **Developer 先输出图表清单草案**（文字，不需要 mockup）
2. **PM 确认清单**（可能有增减）
3. Developer 按确认的清单实现 HTML/JS
4. 正常 review 流程

## 验收标准

- **AC1** — 图表清单经 PM 确认
- **AC2** — Strategy Matrix 页包含三层 Tier 状态 + 核心历史指标 + tail caveat 可见标注
- **AC3** — Backtest 页包含累计 P&L 曲线 + trade overlay + VIX regime 分布（最低要求；其余图表按 PM 确认清单）
- **AC4** — `/q041` 和 `/q041/backtest` 路由正确，nav bar 有 Q041 入口
- **AC5** — 所有数据来自现有 API（`data/q041_portfolio_attribution_latest.json`、paper ledger）；不新增 broker API 调用
- **AC6** — 回归：SPX、/ES、portfolio home 页面不受影响

## 不在范围内

- 改变 Q041 recommendation 逻辑或 paper-trading 记录方式
- 新建任何 broker write path
- 实时 Greeks / IV 展示（使用 Schwab 的可以，但不是本 Spec 的要求）
- Tier 3 详细分析（observe-only，展示基本卡片即可）

## 参考文件

```
web/templates/q041_backtest.html               ← 现有基础页（需要增强）
web/templates/es.html                          ← /ES 页面组参考（设计参照）
web/templates/spx.html 或 index.html           ← SPX 页面组参考
data/q041_portfolio_attribution_latest.json    ← F3 attribution artifact
data/q041_paper_trades.jsonl                   ← paper ledger
doc/q041_execution_prep_packet_2026-05-05.md   ← Tier 说明 + A3 IV stress 数据
web/server.py                                  ← 路由挂载点
```

## Review

### AC1 — 图表清单 PM 确认（2026-05-10）✅

PM 确认的图表清单（12 个 chart，两页）：

**Strategy Matrix（`/q041`）**
- C1 Tier 状态总览（3 列卡片）：Tier 1 ELIMINATED 灰色卡片 / Tier 2 paper-trading active / Tier 3 observe-only
- C2 核心历史指标表格（AnnROE / Sharpe / WR / avg P&L per BP-day / worst trade）
- C3 风险指标（最大单笔亏损 / Peak BP% / VIX+40 shock）— 可合并进 C2 右侧列
- C4 Tier 2 COVID tail caveat 横幅（视觉显著 banner，不能仅 hover）
- C5 Paper-trading 进度条（Tier 2 only，目标 ≥ 20 笔）

**Backtest（`/q041/backtest`）**
- C6 累计 P&L 曲线（三 Tier 叠加，历史实线 + paper 虚线，独立 toggle）
- C7 SPX Price + Trade Entry/Exit Overlay（Tier 2 按标的分色 GOOGL/AMZN）
- C8 VIX Regime 分布入场时（三组堆叠柱状图）
- C9 IV at Entry 分布（GOOGL vs AMZN 箱线图）
- C10 P&L by DTE at Close（展示；无 paper 数据时用回测数据）
- C11 Win Rate by Symbol — GOOGL vs AMZN 对比卡片
- C12 BP Utilization Timeline（含主策略叠加 toggle）

**PM 三个决策点确认**：
1. Tier 1 → 灰色卡片（不移除）
2. C10 → 展示（paper 样本少时用回测数据）
3. C12 → 含主策略 BP 叠加

### AC2 — Strategy Matrix 页包含三层 Tier 状态 + 核心历史指标 + tail caveat 可见标注 ✅

Implemented via `/api/q041/overview` + refreshed `web/templates/q041.html`:

- Tier 1 `SPX CSP` rendered as gray `ELIMINATED` card
- Tier 2 `GOOGL / AMZN CSP` rendered as active cards with visible tail-caveat banner
- Tier 3 `COST / JPM` rendered as review-only / observe-only
- core metric section includes AnnROE / Sharpe / WR / avg P&L per BP-day / worst trade
- risk visibility includes VIX+40 shock / BP usage context
- Tier 2 paper progress bar shown; Tier 1 intentionally suppressed per PM confirmation

### AC3 — Backtest 页包含累计 P&L 曲线 + trade overlay + VIX regime 分布 ✅

Implemented in `web/templates/q041_backtest.html`:

- cumulative P&L chart supports historical curves plus paper overlay when available
- existing trade overlay path remains present
- VIX regime distribution added
- additional approved carriers added:
  - IV at entry
  - P&L by DTE at close
  - BP utilization timeline with main-strategy overlay toggle

### AC4 — `/q041` 和 `/q041/backtest` 路由正确，nav bar 有 Q041 入口 ✅

- `/q041` route remains active
- `/q041/backtest` route remains active
- implementation used the existing app navigation structure; no route regression introduced

### AC5 — 所有数据来自现有 API / artifact；不新增 broker API 调用 ✅

Data sources used:

- `data/q041_portfolio_attribution_latest.json`
- `data/q041_paper_trades.jsonl` (fail-soft when absent)
- existing Q041 backtest payload / cache
- `doc/q041_execution_prep_packet_2026-05-05.md` §11 values reflected as fixed risk-visibility constants

No broker API, quote, chain, or write-path was added.

### AC6 — 回归：SPX、/ES、portfolio home 页面不受影响 ✅

Verified by adjacent regression:

- `tests.test_spec_085`
- `tests.test_state_and_api`

`SPEC-093` changes are isolated to Q041 overview aggregation and Q041 templates.

### Quant 对齐验证（2026-05-10）✅

独立验证所有 Tier 状态与 research record 完全一致：
- Tier 1 ELIMINATED 卡片 — 与 Q055 竞争结论对齐（V1 veto -17.99% NLV；Tier 2 主指标全负）
- Tier 2 tail-caveat banner — 与 2nd Quant review 要求对齐（"explicit tail caveat in all downstream docs"）
- Tier 3 observe-only 未变更 — Q055 不影响 Tier 3
- Q041 ↔ Q042 零交叉影响（不同 ledger / routes / launchd jobs）
- paper fail-soft 行为合理（live ledger 初次 deployment 时不存在属正常）

**Quant 视角无阻塞，可部署到 old Air。**
