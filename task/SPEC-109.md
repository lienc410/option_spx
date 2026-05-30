# SPEC-109 — Journal Greek Attribution Chart UX Enhancement (Tier A + B)

**Type**: UX enhancement (research-driven from Quant review of Greek attribution chart)
**Date**: 2026-05-28
**Status**: **DONE** — Implemented 2026-05-28 (commit db6c1af), deployed oldair, Quant fidelity PASS
**Owner**: Quant Researcher (draft) → PM approval → Developer implementation
**Source**: Quant review of `/journal` Greek attribution chart (2026-05-28); PM approved Tier A + B design
**Parent**: Existing Greek attribution stack — UNCHANGED algorithm (`scripts/compute_greek_attribution.py`, `/api/strategy/greek-attribution`, attribution section in `journal.html`)

---

## 0. TL;DR

`/journal` 页面 **Strategy PnL Attribution by Greek** 图当前只有 5 条独立线（Delta / Gamma / Theta / Vega / Residual），PM 不易一眼判断 "short-premium 生意是否健康"。

**Tier A**：图顶加 4 格 KPI strip（Premium captured / Vol risk paid / Direction / Net attribution + Closure %）、footer 加教学一句话。

**Tier B**：Theta 变绿色 area fill 向上、Gamma 变红色 area fill 向下；synthetic gap-day 加阴影 band 或 tooltip 标注。

**不动**：attribution 算法、`compute_greek_attribution.py`、jsonl schema、其它视图。

---

## 1. Background

### 1.1 现状

- 图位置：`/journal` 页面 `Strategy PnL Attribution by Greek · SPX Spread · BS reverse-solve` section
- 来源：`scripts/compute_greek_attribution.py`（Path A — BS reverse-solve）写 `data/strategy_pnl_attribution.jsonl`
- API: `/api/strategy/greek-attribution?strategy=spx_spread&window=cum|7d|30d`
- 前端：Chart.js line chart，5 条独立线，按 abs terminal magnitude 排序绘制
- 公式：`ΔPnL ≈ Δ·ΔS + ½Γ·ΔS² + Θ·Δt + V·ΔIV + Residual`
- 当前 cum residual ~5%（per commit 55e42bc）

### 1.2 Quant 评估发现的 PM 痛点

1. **Gamma 那条线一路向下** — PM 直觉读成"问题"，实际上是 short put credit spread 的**结构性事实**（net short gamma → gamma_attr 必然负）
2. **没有"健康判断"** — 5 条独立线缺少 `theta + vega vs gamma` 的相对关系视图
3. **Residual 5% 不显式** — PM 不知道 attribution 跟 broker actual 闭合率
4. **Synthetic gap-day 不可见** — q041 chain 数据缺漏的日子是 BS 插值（synth_state），但前端无标注，PM 容易把插值读成真实日间分布

### 1.3 决策路径（已 PM 确认）

| 选项 | 含 | 决策 |
|---|---|---|
| Tier A | KPI strip + footer 教学 + Closure % | ✅ 做 |
| Tier B | Theta/Gamma area fill + synthetic gap 标注 | ✅ 做 |
| Tier C | 双视图 toggle / Premium 生意视图 stacked | ❌ 不做（PM 暂不需要） |

---

## 2. Scope

### 2.1 文件改动

| 文件 | 动作 |
|---|---|
| `web/server.py` | EDIT — `/api/strategy/greek-attribution` 在 `series` 每行附加 `synthetic: bool`（any synthetic_t0/synthetic_t1 in source rows for that date） |
| `web/templates/journal.html` | EDIT — 实施 6 项 UX 改动（CSS + DOM + Chart.js dataset config + KPI compute JS） |

**不新增**：SPEC mirror 文档、pytest 模块（UX 改动无算法行为需 unit test）、新文件 / 新模块。

### 2.2 6 项 UX 改动

#### A1. KPI strip — 图上方 4 格

在 `<canvas id="attr-chart">` 上方插入 4 格 KPI：

```
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Premium captured │ Vol risk paid    │ Direction        │ Net attribution  │
│  +$22,400        │  −$15,100        │  +$1,200         │  +$8,500         │
│  Θ +$18.2k       │  Γ −$15.1k       │  Δ +$1.2k        │  Actual: +$8,950 │
│  V +$4.2k        │                  │                  │  Closure: 95%    │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

字段计算（前端 JS，从 `payload.totals` 或 `series` 最末行取值）：

```javascript
const t = payload.totals;
const premiumCaptured = t.theta_attr + Math.max(t.vega_attr, 0);
const volRiskPaid     = t.gamma_attr + Math.min(t.vega_attr, 0);
const direction       = t.delta_attr;
const netAttribution  = t.delta_attr + t.gamma_attr + t.theta_attr + t.vega_attr;
const actualPnL       = t.actual_pnl;
const closurePct      = Math.abs(actualPnL) > 1
                          ? Math.max(0, 100 * (1 - Math.abs(t.residual) / Math.abs(actualPnL)))
                          : null;
```

#### A2. Footer 改写

替换 `<span id="attr-note">` 默认文案，分两行：

```
Δ·ΔS + ½Γ·ΔS² + Θ·Δt + V·ΔIV + Residual   ·   BS reverse-solve (r=5%, q=1.3%)
Short put spread = net short gamma  ·  健康标准: |Θ+V| > |Γ|
```

Cum mode 下保留 cum total 文案作为第 3 行。

#### A3. Closure % 显式

放在 KPI 第 4 格（Net attribution）副行：
- 若 `|Actual - Net| < 1% × |Actual|` → 显示绿色 `Closure: XX%`
- 否则 → 橙色

不要在 footer 再开第二处显示。

#### B1. Theta / Gamma area fill

修改 `greekDefs`（journal.html:898-904）+ Chart.js dataset 配置：

| Greek | borderColor | backgroundColor (rgba 18%) | fill | borderWidth |
|---|---|---|---|---|
| **Theta** | `var(--green)` | green-bg 18% alpha | `'origin'` | 1.5 |
| **Gamma** | `var(--red)` | red-bg 18% alpha | `'origin'` | 1.5 |
| Delta | 当前 blue 保留 | 透明 | `false` | 2 |
| Vega | 当前 purple 保留 | 透明 | `false` | 2 |
| Residual | 当前 grey 保留 | 透明 | `false` | 1 (dashed [4,3]) |

`fill: 'origin'` → 基线=0；Theta 累积正 → 绿 area 向上；Gamma 累积负 → 红 area 向下。

绘制顺序仍按 abs terminal 排序，dominant 在上层。

#### B2. Synthetic gap-day 标注

**后端 (server.py)**：

```python
keys = ("actual_pnl", "delta_attr", "gamma_attr", "theta_attr", "vega_attr", "residual")
for r in rows:
    d = r["date"]
    bucket = by_date.setdefault(d, {k: 0.0 for k in keys})
    for k in keys:
        bucket[k] += float(r.get(k) or 0.0)
    bucket["synthetic"] = bucket.get("synthetic", False) or bool(r.get("synthetic_t0")) or bool(r.get("synthetic_t1"))

series = [{"date": d, "synthetic": by_date[d].get("synthetic", False), **agg[i]}
          for i, d in enumerate(dates)]
```

**前端 (journal.html)**：

Synthetic=true 的日期画一个垂直灰色 band（Chart.js plugin 或 background annotation）：
- 颜色 `var(--theme-lit-095)` 或类似低对比 grey
- alpha 12%
- Tooltip 增加一行：`⚠ Chain data gap · BS interpolated`

**降级方案**（如 plugin 改动过重）：在图下方加小字 `Gray bands indicate chain data gaps (BS interpolated)`，并在 tooltip 对每个 synthetic 数据点加标记。最低可接受方案 = tooltip 标记。

### 2.3 颜色与字体约定

- 主数字字号大、`var(--f-mono)`、`var(--text)`
- 副行（Θ +$18.2k 等）字号小、`var(--f-mono)`、`var(--text-2)`
- 正数前缀 `+`、负数前缀 `−`（U+2212，**不是** hyphen）
- 负数颜色 `var(--red)`，正数颜色 `var(--green)`
- KPI label / footer 文案全部 `var(--text-2)` — **严禁** `var(--text-muted)`（per `feedback_text_muted_banned`）

### 2.4 Theme convention

- 复用现有 CSS vars：`--green`, `--red`, `--text`, `--text-2`, `--f-mono`, `--f-ui`
- 如需 area fill 的 18% alpha 颜色：用 `rgba(...)` 内联或局部 class，**不要新建 `:root` token override**（per `feedback_theme_convention`）

### 2.5 NOT changed

- `scripts/compute_greek_attribution.py` — **frozen**（算法、BS reverse-solve、r=5%/q=1.3%/365 convention、edge handling 全部保持）
- `data/strategy_pnl_attribution.jsonl` schema — 不动
- `/api/strategy/greek-attribution` 现有字段 — 只允许**新增** `synthetic`
- `/api/strategy/cum-pnl` — 不动
- 其它视图 `spx.html` / `matrix.html` / `margin.html` / `portfolio_home.html` / `performance.html` / `backtest.html` / `hvladder.html` / `es*.html` / `q041*.html` — 全部不动
- `journal.html` 其它 sections（NLV chart, Cum P&L chart, Regime strip, Positions table, Day Records）— 不动
- Window toggle (cum / 7d / 30d) 现有逻辑 — 不动；KPI 跟随 window 重算即可
- `theme.css` / `web/static/` — 不动

---

## 3. File Changes

| 文件 | 动作 | 行数估计 |
|---|---|---|
| `web/server.py` | EDIT — `/api/strategy/greek-attribution` 加 `synthetic` 字段聚合 + series 透传 | ~5-8 行 |
| `web/templates/journal.html` | EDIT — 内嵌 CSS 加 `.attr-kpi-strip` 系列；DOM 加 4 格 KPI 容器；JS `_renderAttrChart()` 加 KPI 计算 + 注入；`greekDefs` 改 Theta/Gamma 的 borderColor / backgroundColor / fill / borderWidth；footer 文案改 2-3 行；synthetic gap 标注 | ~120-150 行 |

---

## 4. Acceptance Criteria

| AC# | 验证 | 验证方式 |
|---|---|---|
| AC-109-1 | `/api/strategy/greek-attribution?strategy=spx_spread&window=cum` 响应 `series[i]` 含 `synthetic: bool` | curl + jq |
| AC-109-2 | 同上 endpoint 现有字段未删除（actual_pnl / delta_attr / gamma_attr / theta_attr / vega_attr / residual / totals / row_count / earliest / latest） | curl + diff |
| AC-109-3 | `/journal` attribution section 在 chart 上方显示 4 格 KPI strip | 视觉 |
| AC-109-4 | KPI 数字与 `payload.totals` 一致；切换 window cum/7d/30d 时 KPI 同步更新 | 视觉 + spot check |
| AC-109-5 | Net attribution 格显示 Actual + Closure% — 当 `|Actual-Net| < 1%×|Actual|` 时 Closure 绿色，否则橙色 | 视觉 |
| AC-109-6 | Footer 显示两行（cum mode 三行）：公式 + `BS reverse-solve (r=5%, q=1.3%)`；健康标准短语 | 视觉 |
| AC-109-7 | Theta 在图上是**绿色 area fill 向上**；Gamma 是**红色 area fill 向下**；Delta/Vega/Residual 保持细线 | 视觉 |
| AC-109-8 | Synthetic day 在图上有视觉提示（band 或 tooltip 标记），鼠标悬停看到 `Chain data gap · BS interpolated` | 视觉 |
| AC-109-9 | 负数用 `−` (U+2212) 不是 hyphen；负数 `var(--red)`，正数 `var(--green)` | grep + 视觉 |
| AC-109-10 | KPI label / 副行 / footer 全部 `var(--text-2)`；**无任何 `--text-muted`** 出现在 PM 要读的内容上 | grep + 视觉 |
| AC-109-11 | 无新建 `:root` token override；CSS vars 全部复用现有 | grep `:root` `--` |
| AC-109-12 | `/portfolio_home`, `/spx`, `/matrix`, `/margin`, `/performance`, `/backtest`, `/hvladder`, `/q041`, `/es` 无视觉变化 | 抽查 |
| AC-109-13 | 当 `payload.series.length === 0` (no_data) — KPI strip 显示 `—`，不报 JS 错；图沿用现有 "No attribution rows yet" 文案 | DevTools console + 视觉 |
| AC-109-14 | Window toggle 切换时 chart + KPI 同步切；3 个 window 模式都正确 | 视觉 |
| AC-109-15 | mobile / 窄屏（< 768px）KPI grid 改为 2×2，文字不截断 | 浏览器 responsive |

**无需新建 pytest 模块**（UX 改动，无新算法行为）。AC-109-2 可 grep verify。

---

## 5. Monitoring Obligations

无 standing monitor（UX 改动，不引入新策略 / 风险 / 数据流）。

---

## 6. Staged Rollout

**单步部署**，不需要 shadow / staged。理由：
- 不改 attribution 算法（同一份 jsonl 数据）
- 不改 entry / exit / sizing / routing
- 不引入新决策
- 不动其它视图
- 失败模式仅限前端渲染异常 → rollback 简单（git revert）

部署完即生效。

---

## 7. Out of Scope

| 不做 | 原因 |
|---|---|
| **Tier C** 双视图 toggle / Premium 生意视图 stacked | PM 暂不需要 |
| 改 attribution 算法 / 公式 / r/q / Taylor 阶数 / Vanna / 二阶交叉项 | Path A 算法 frozen；二阶改进进 Path B（独立任务） |
| Path B（broker chain greeks 替代 BS reverse-solve） | 独立任务 |
| 改其它视图 | 范围外 |
| 改 `/api/strategy/cum-pnl` 或其它 endpoint | 范围外 |
| 改 backtest cache | 范围外 |
| 改 Telegram / 通知 | 范围外 |
| 改 `compute_greek_attribution.py` 任何行 | 算法层 frozen |
| 改 7d/30d rolling 为 trade-life rolling | Tier C 议题 |
| Q078/SPEC-108 ladder panel | 不相关 SPEC |

---

## 8. Design Notes

### 8.1 为什么不上 Tier C

PM 评估：Tier A+B 已经把"看一眼判断 short premium 健康度"这个核心痛点解决。Tier C（双视图 + stacked premium 生意视图）锦上添花但增加 4h 工程量 + 维护负担。PM 优先级 = 解决误读 gamma，不在视觉重构。Tier C 留作未来可选升级。

### 8.2 为什么改 area fill 而不是 stacked

Stacked area 在 signed greek 上有 area sign 歧义（greek 跨 0 时面积方向反转、视觉混乱）。area fill from origin（基线=0）对**单一符号 cumulative greek** 是干净的视觉化：
- Theta 累积始终正 → fill 永远向上 = "拿到的钱"
- Gamma 累积始终负（short put spread 结构性事实）→ fill 永远向下 = "付出的对价"

PM 视觉直接比较 area 大小判断净值方向。

### 8.3 为什么显式 Closure %

Greek attribution 本质是 **BS 一阶 Taylor**：忽略 Vanna / Volga / Charm / 二阶交叉项。Residual 5% 是这些缺项的"垃圾桶"。

不显示 Closure → PM 误以为 5 条线相加等于 actual_pnl，对 attribution 的精度估计偏乐观。显示 Closure → 校准 PM 对 attribution 的信任。

阈值 1% 选取理由：5% residual 是当前实测；小于 1% deviation 视为高度闭合，绿色；大于则橙色提醒。

### 8.4 为什么 rgba 内联而不是新 token

Area fill 的 alpha 颜色是**局部视觉变体**，不是新的语义颜色（已有 `var(--green)` / `var(--red)` 语义）。新建 `--green-bg-50` 等 token 会污染全局 theme 命名空间，且只有这一处使用。`feedback_theme_convention` 明令禁止重新内联 `:root` token；但**单点 rgba alpha** 不属于 token override，属于局部样式。

### 8.5 为什么 synthetic 后端聚合 day-level

源 jsonl 是 (date, trade_id) 双 key，多 trade 同日可能部分 synthetic 部分真实。Day-level 聚合规则：**任一行 synthetic → 当日 synthetic**（最保守，避免漏标）。

### 8.6 为什么 Tier A 也加教学语 "健康标准: |Θ+V| > |Γ|"

PM 在 review 中明确表达过对 gamma 那条线的误读（"亏损这么大"）。教学语直接在 footer 给判断标准，避免下次再误读。短语用中文确保 PM 不需要心智翻译。

---

## 9. Deploy

1. Developer 实施 §3 文件改动 → 本地 AC1-AC15 验证
2. 跑现有 pytest 套件（53/53 SPEC-103~107 + 12/12 SPEC-108 + 其它）确认无回归
3. Commit + push
4. Old Air `git pull` + 重启 web（per `feedback_deploy_oldair`）
5. Smoke test：
   - `curl https://oldair.spxstrat.app/api/strategy/greek-attribution?strategy=spx_spread&window=cum | jq '.series[0]'` 含 `synthetic`
   - 访问 `/journal` 视觉验证 4 格 KPI + 双 area + footer 两行 + synthetic 标注
   - 切 window cum / 7d / 30d 看 KPI 同步
   - 抽查 `/portfolio_home`、`/spx`、`/matrix` 无视觉变化

---

## 10. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| `web/server.py` synthetic 字段 | ~10 min | ~30 min |
| `web/templates/journal.html` CSS + DOM + JS（KPI strip） | ~1.5h | ~3-4h |
| Chart.js dataset config + area fill + synthetic band | ~1h | ~2h |
| AC verification + responsive 检查 | ~30 min | ~1h |
| Deploy + smoke | ~30 min | ~1h |
| **Total** | **~3.5h** | **~半天-1 天** |

---

## 11. PM Approval Signature

**PM signed 2026-05-28** (single "APPROVED" affirms all 7 items below)

- [x] Approve 4 格 KPI strip 设计（Premium captured / Vol risk paid / Direction / Net attribution）
- [x] Approve footer 改 2 行（含 r=5%, q=1.3% 假设披露 + 健康标准教学语）
- [x] Approve Theta/Gamma area fill（绿向上 / 红向下）
- [x] Approve Closure% 阈值 1% 绿/橙判定
- [x] Approve synthetic gap-day 视觉标注（band 或 tooltip）
- [x] Approve Tier C 暂不做
- [x] 确认 `web/server.py` `/api/strategy/greek-attribution` 只新增 `synthetic` 字段，不删除/修改已有字段

---

## 12. Developer Handoff Notes

### Implementation checklist

1. **后端**：`web/server.py:2185-2263` `/api/strategy/greek-attribution`：
   - `by_date` 聚合时加 `synthetic` flag（per §2.2 B2）
   - `series` 输出每行透传 `synthetic`

2. **前端 CSS**（`journal.html` 内嵌 `<style>` 块）：
   - 加 `.attr-kpi-strip` grid 容器（4 列，响应式 < 768px 改 2×2）
   - 加 `.attr-kpi-cell` cell 样式（边框、圆角、padding）
   - 加 `.attr-kpi-label` / `.attr-kpi-value` / `.attr-kpi-sub` 字号字体颜色（per §2.3）
   - 加 `.attr-kpi-closure-ok` / `.attr-kpi-closure-warn` 配色
   - 加 synthetic band CSS（Chart.js plugin 用）或 tooltip 强调样式（降级方案）

3. **前端 DOM**（`journal.html` attribution section）：
   - 在 `<canvas id="attr-chart">` 上方插入 KPI strip 容器
   - 4 格 cell 模板，初始内容 `—`

4. **前端 JS**（`_renderAttrChart` 函数）：
   - 加 `_updateAttrKpi(payload)` 函数：从 `payload.totals` 算 5 个字段 + closure_pct，注入 DOM
   - `greekDefs` 改 Theta/Gamma 的 borderColor / backgroundColor / fill / borderWidth（per §2.2 B1）
   - 替换 footer 文案为 2-3 行（per §2.2 A2）
   - synthetic band：Chart.js 自定义 plugin 或 background annotation；降级方案 tooltip 加 `⚠` 标记

5. **No-regression check**：
   - `pytest tests/test_spec_103.py tests/test_spec_104.py tests/test_spec_105.py tests/test_spec_106.py tests/test_spec_107.py tests/test_spec_108.py` 全 PASS
   - 抽查其它视图无视觉异常

### Implementation discipline (per PM)

> 严格按 Tier A + B 6 项改动实施。**不要**改 attribution 算法。**不要**扩展到 Tier C。**不要**改其它视图。**不要**改 `compute_greek_attribution.py`。**不要**新增 `:root` token override；如需 alpha 颜色用 rgba 内联或局部 class。

### Reference docs Developer should read

1. `task/SPEC-109.md`（本文件）
2. `DESIGN.md` — 颜色 / 字体 / 间距规则
3. `CLAUDE.md` + `QUANT_RESEARCHER.md` — 角色协议
4. `web/templates/journal.html:211-224, 871-960` — 现有 attribution panel
5. `web/server.py:2185-2263` — 现有 endpoint
6. `scripts/compute_greek_attribution.py` — 数据来源（**只读，不改**）

---

## 13. PROJECT_STATUS.md 索引项 (Planner 自助)

```
- `SPEC-109` — Journal Greek Attribution Chart UX Enhancement (Tier A + B).
  **DRAFT 2026-05-28.** `/journal` Strategy PnL Attribution by Greek 图加 4 格
  KPI strip（Premium captured / Vol risk paid / Direction / Net attribution
  + Closure %）+ footer 教学语；Theta 绿色 area fill 向上、Gamma 红色 area
  fill 向下；synthetic gap-day 加标注。不改 attribution 算法 (Path A BS
  reverse-solve frozen)，不改其它视图。AC1-AC15。预估 CC+gstack ~3.5h。
  — See: task/SPEC-109.md
```

---

## Review

**Reviewer**: Quant Researcher
**Date**: 2026-05-28
**Verdict**: **PASS** — implementation matches SPEC-109 Tier A + B fidelity
**Implementation commit**: `db6c1af` (feat(journal): SPEC-109 KPI strip + area fill on Greek attribution chart)
**Developer note**: backend `synthetic` field was already present in baseline (web/server.py:2228-2258); no server.py diff needed → only `journal.html` changed

### Test evidence
- 现有 SPEC-103 ~ SPEC-108 regression: **65/65 PASS** (local re-run 2026-05-28)
- Developer 报告 oldair smoke: `/journal` 200, `/api/strategy/greek-attribution` 200, `series[0].synthetic` is bool, 其它视图（`/portfolio_home`, `/spx`, `/matrix`, `/performance`, `/backtest`, `/hvladder`, `/q041`, `/es`, `/margin`, `/portfolio-backtest`）均 200

### Fidelity audit — 15 AC × implementation cross-check

| AC# | SPEC ask | Implementation | PASS |
|---|---|---|---|
| 1 | `series[i].synthetic: bool` | `web/server.py:2228-2236, 2258` (baseline 已含；synth_by_date 聚合) | ✅ |
| 2 | 现有 endpoint 字段未删除 | 同 endpoint 仅新增 synthetic，actual_pnl/delta/gamma/theta/vega/residual/totals 全部保留 | ✅ |
| 3 | 4 格 KPI strip 在 chart 上方 | `journal.html` DOM lines 294-318：Premium captured / Vol risk paid / Direction / Net attribution 四格 | ✅ |
| 4 | KPI 数字 = `payload.totals`；window cum/7d/30d 同步 | `_updateAttrKpi(payload)` 在 `_renderAttrChart` 内调用；每次 window 切换重 fetch + 重渲染 | ✅ |
| 5 | Closure% 阈值 1% 绿/橙 | `journal.html:1011-1012` `closureOk = Math.abs(residual) < Math.abs(actualPnL) * 0.01`；`.attr-kpi-closure.ok` 绿色 css | ✅ |
| 6 | Footer 两行（cum mode 三行） | `_updateAttrNote(payload)` 注入 formula + teaching 两行；cum mode 加 cum-total 第三行 | ✅ |
| 7 | Theta 绿 area fill 向上 / Gamma 红 area fill 向下 | `greekDefs` lines 1056-1060：Theta `fill: 'origin'` + `rgba(66,204,124,0.18)`；Gamma `fill: 'origin'` + `rgba(224,72,98,0.18)`；Delta/Vega/Residual 保留细线 | ✅ |
| 8 | Synthetic 视觉提示 + tooltip | `syntheticBandPlugin` (lines 1086-1103) 画 12% alpha 灰 band；tooltip 加 `⚠ Chain data gap · BS interpolated` (lines 1121)；synthetic 段还加 `dashOnSynth` 让线虚线（超额满足 SPEC） | ✅✅ |
| 9 | 负数 U+2212 + 红/绿色 | `_signedMoney` lines 954/961 使用 `'−'` (U+2212)；`_signedCls` lines 963-965 返回 `pos`/`neg` class → `--green`/`--red` | ✅ |
| 10 | 无 `--text-muted` 在 PM 内容 | `git show db6c1af` grep `text-muted` 空结果 | ✅ |
| 11 | 无新 `:root` token override | `git show db6c1af` grep `:root` 空结果；area fill 用 `rgba()` 内联（符合 §8.4 设计原则） | ✅ |
| 12 | 其它视图无变化 | commit 只触 `web/templates/journal.html`；Developer 抽查 10 个视图 全 200 | ✅ |
| 13 | no_data 状态 KPI 全 `—`，不报 JS 错 | `_resetAttrKpis()` (lines 968-979) 处理；`_renderAttrChart` no_data 分支调用 | ✅ |
| 14 | Window toggle 同步 | window switch handler 重 fetch → `_renderAttrChart` → `_updateAttrKpi` + `_updateAttrNote` 都重算 | ✅ |
| 15 | mobile < 768px → 2×2 grid | CSS media query line 152-155：`grid-template-columns: repeat(2, ...)`；note 改 `width: 100%, text-align: left` | ✅ |

### Invariant audit

- ✅ `scripts/compute_greek_attribution.py` — `git show db6c1af` 不触此文件
- ✅ `data/strategy_pnl_attribution.jsonl` schema — 不动
- ✅ `/api/strategy/greek-attribution` 现有字段 — 仅新增 synthetic
- ✅ 其它视图 — commit 仅触 `web/templates/journal.html`
- ✅ `journal.html` 其它 section（NLV chart / Cum P&L / Regime strip / Positions / Day Records）— diff 仅集中在 attribution panel 与公用 helpers，未触其它 section 渲染逻辑
- ✅ Window toggle 现有逻辑 — 保留
- ✅ `theme.css` / `web/static/` — 不动
- ✅ 无新 `:root` token — verified

### 加分项（Developer 超额满足）

1. **Synthetic 段不仅有 band，连接线也画虚线**：`segment: { borderDash: dashOnSynth }` (line 1083) 让跨 synthetic 的线段虚线显示。这比 SPEC §2.2 B2 要求的 band-only 多一层视觉提示，PM 即使没注意到灰 band 也能从虚线段意识到。
2. **`_resetAttrKpis()` 单独抽函数**：no_data + initial state 复用，避免 DOM 状态泄漏
3. **`_signedMoney` / `_kMoney` / `_signedCls` 三个 helper 解耦**：未来如果要新加 KPI 卡片可复用，工程整洁

### Notes for future（NON-blocking）

1. **`Math.abs(actualPnL) > 1` 阈值**：当 cumulative actual PnL 接近 0（开仓初期或 hedged 净 0）时，Closure% 显示 `—`。当前合理。但 PM 在交易少量天数时可能看到 `Closure —` 而困惑——若 future 想精化，可在 actualPnL < 1 时显示 `n/a (small base)`。
2. **`_kMoney` 副行精度 1 位**：`+$18.2k` 这种 → PM 一眼 OK，但当 cum 进入 6 位数时 `+$182.3k` 还是 1 位 fixed，未来可考虑 `> $100k` 自动切 0 位。
3. **`syntheticBandPlugin` 在 zoom 时**：Chart.js 不支持 zoom plugin 时 band 位置稳定；若未来加 zoom，band 需要响应 scales.x 重算。当前无 zoom，所以无问题。
4. **Theta/Gamma area fill 在两线同号时遮挡**：理论上 Theta 永远 ≥ 0、Gamma 永远 ≤ 0，所以两 area 不会同区。但如果 7d/30d rolling 在某个短窗内 Theta 因 large vega buyback 而短暂 < 0，绿 area 会向下盖到 Gamma 红 area 上。短期内不会发生（PM hold 14 days avg），future watch。

### Verdict statement

> SPEC-109 实施 fidelity PASS。15 个 AC 全部覆盖；65/65 regression 无回归；6 项 Tier A+B 改动全部体现且**超额**满足（synthetic 段连线虚线 + helper 解耦）。`compute_greek_attribution.py` 算法 frozen 未触。`--text-muted` ban 与 `:root` token convention 遵守。SPEC-109 Status `APPROVED` → **DONE**。

---

---

## 14. References

- `scripts/compute_greek_attribution.py` — Path A BS reverse-solve attribution computation (UNCHANGED)
- `scripts/_reconcile_greek_attribution.py` — original diagnostic prototype
- `web/server.py:2185-2263` — `/api/strategy/greek-attribution` endpoint
- `web/templates/journal.html:211-224, 871-960` — current chart panel + render JS
- `data/strategy_pnl_attribution.jsonl` — backing data
- `DESIGN.md` — visual design system
- `~/.claude/.../memory/feedback_text_muted_banned.md` — `--text-muted` ban
- `~/.claude/.../memory/feedback_theme_convention.md` — theme token reuse
- `~/.claude/.../memory/feedback_frontend_color_account.md` — frontend color semantics
- Quant review chain (2026-05-28 conversation):
  - Method audit on Path A BS reverse-solve
  - "Gamma 亏损这么大" misread diagnosis
  - Tier A / B / C decision path
  - Developer prompt v1 (superseded by this SPEC)

---

Status: DRAFT
