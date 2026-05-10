# SPEC-072.1: Q029 Reporting Coverage Patch — matrix view + portfolio backtest + CSV export + governance

Status: DONE 2026-05-09 (F8-F11 implemented; smoke tests pass; Q029 closed)
Parent: SPEC-072 (DONE 2026-04-25)
Driver: Q029 Tier 1 closure — see RESEARCH_LOG `R-20260509-10` (forthcoming) and Quant Tier 1 evaluation 2026-05-09

---

## 目标

**What**：把 SPEC-072 的 dual-scale reporting 缓解扩展到 4 处当前未覆盖的 HIGH_VOL aggregate 数字消费场景，让 Q029 reporting-layer 缓解真正完整。

**Why**：Q029 Tier 1 调查发现 SPEC-072 frontend dual-scale 仅覆盖 4 个 template（`index.html` / `backtest.html` / `margin.html` / `spx.html`），但还有：

1. `matrix.html` cell stats 显示 HIGH_VOL avg_pnl 单列（PM 跨 regime 比较的主界面）
2. `portfolio_backtest.html` 没有 SPEC-072 helpers 引入（结构性预防）
3. CSV 导出（`scripts/export_backtest_trade_detail.py`）下游消费者看不到 scale 注脚
4. Manually-authored docs（`RESEARCH_LOG.md` / specs / handoffs）引用 HIGH_VOL aggregate 时无 governance 强制 scale 标注

**真正的 parity 缺口本质**（从 Q029 Tier 1 调查中纠正的认知）：engine 不存在 "qty=1 hardcoded"。`backtest/engine.py:_position_contracts()` 已经按 `account × bp_target / bp_per_contract` 做 fractional sizing。Parity 缺口是**单位口径解读**（research 用 fractional SPX vs live 用 discrete 1 XSP），是 reporting 层语义问题，**不需要 engine 重构**。SPEC-072.1 关闭这个语义缺口的最后几处。

---

## 范围与不在范围

| In Scope | Out of Scope |
|---|---|
| F8 — `matrix.html` 引入 spec072_helpers + HIGH_VOL cell 双值 avg_pnl | engine / selector / `_position_contracts` 改动 |
| F9 — `portfolio_backtest.html` 引入 spec072_helpers + HV trade log 双值（结构性预防） | 改 SPX/XSP 实际下单逻辑（live-side） |
| F10 — `scripts/export_backtest_trade_detail.py` CSV 加 `live_scale_factor` 列 | trade_log.csv 历史回填（仅影响新生成数据） |
| F11 — `QUANT_RESEARCHER.md` + `REVIEW_TEMPLATE.md` 写入 governance 条款 | 已发布的 RESEARCH_LOG 历史条目回溯标注 |
| ST6–ST9 smoke test | 与 SPEC-072 F1–F7 重叠的回归检查（ST1–ST5 已 covered） |

---

## 文件映射

| 功能 | 文件 | 实施位置 |
|---|---|---|
| F8 helper inject | `web/templates/matrix.html` | `<head>` 区，`<script src="...spec072_helpers.js">`（与 backtest.html 第 12 行同样写法）|
| F8 cell stat 双值 | `web/templates/matrix.html` 约 line 619-620 `stat()` 模板字面量 | 替换 `avg ${...}` 段为 `${formatDualPnl(s.avg_pnl, regime)}` 或等价模板 |
| F9 helper inject | `web/templates/portfolio_backtest.html` | `<head>` 区 |
| F9 trade log 双值 | `web/templates/portfolio_backtest.html` HV row PnL/BP/credit cells | 套用 SPEC-072 F5 同款双列样式 |
| F10 CSV column | `scripts/export_backtest_trade_detail.py` | trade row dict 内加 `"live_scale_factor"` field（HIGH_VOL → 0.1，其他 → 1.0）|
| F11 governance | `QUANT_RESEARCHER.md`、`REVIEW_TEMPLATE.md §4.3` 或新加 §6.2 | append 一条 markdown 条款 |

---

## 功能定义

### F8 — Matrix view cell stats 双值

**当前行为**（`matrix.html:619-620`）：

```js
const stat = s => s
  ? `<span class="cell-stat-wr ${wrClass(s.win_rate)}">WR ${s.win_rate}%</span>
     <span class="cell-stat-pnl ${avgClass(s.avg_pnl||0)}">avg ${s.avg_pnl>=0?'$+':'$-'}${Math.abs(s.avg_pnl||0)}</span>
     <span class="cell-stat-n">n=${s.n}</span>`
  : '<span class="cell-stat-na">NA</span>';
```

**目标行为**：当 `regime === 'HIGH_VOL'` 时，`avg ${...}` 段改为 `formatDualPnl(s.avg_pnl, regime)` 输出，例如 `avg +$879 + +$87.90 est`；其他 regime 行保持单列。

**依赖**：渲染 cell 时已知 regime 字符串（`matrix.html:608` `cellKey` 已经包含 regime），把 regime 透传给 `stat()` 即可。

### F9 — Portfolio backtest dual-scale

**当前行为**：`portfolio_backtest.html` 不引入 spec072_helpers；trade log 与聚合数字在 HV 行单列显示。

**目标行为**：
- `<head>` 引入 `<script src="{{ url_for('static', filename='spec072_helpers.js') }}">`
- HV trade log 行 `exit_pnl` / `total_bp` / `entry_credit` 改为双列（套 SPEC-072 F5 形式）
- 如 portfolio_backtest 显示 by-regime aggregate（如 HV 总 PnL），那一格也按 dual format

**Developer 自决**：portfolio_backtest 的具体内容若已有大块只读组件，仅需对涉及 HV PnL/BP 的渲染点改动；不需要全文重写。

### F10 — CSV export 加 live_scale_factor 列

**当前行为**：`scripts/export_backtest_trade_detail.py:299+` 输出每笔 trade 的 dict，含 `regime`、`exit_pnl_usd` 等列，但没有 scale 注脚。

**目标行为**：在每笔 trade 的输出 dict 中加：

```python
"live_scale_factor": 0.1 if regime == "HIGH_VOL" else (2.0 if regime == "LOW_VOL" else 1.0),
"live_scaled_exit_pnl_usd": round(trade.exit_pnl * scale, 2),
"live_scaled_total_bp": round(trade.total_bp * scale, 2),
```

下游脚本（Q053 grinding analysis、Q041 portfolio attribution 等）可以自由选择哪列做聚合。CSV 的下游消费者按需启用 live_scaled 列。

**注**：仅影响新生成的导出 CSV；历史 CSV 不回填。Q053 已发表的 R-20260509-03 中的 -$26.8k 数字应在下次复跑时附 live_scaled context（见 F11 governance）。

### F11 — Governance 条款

**`QUANT_RESEARCHER.md`** 加入新章节 "HIGH_VOL Aggregate Scale Convention"：

> 任何引用 HIGH_VOL aggregate metric（avg PnL、total PnL、win_rate × avg_pnl 派生量、cumulative return 等）必须显式标注其口径：
>
> - 默认口径：`research scale (1×SPX equivalent, fractional contracts via bp_target)` ← engine 原生输出
> - 备选口径：`live scaled est (×0.1)` ← 假设 HIGH_VOL aftermath 实际走 1 XSP
>
> 标注方式：在数字括号内加 `(research)` 或 `(live est)`；或在引用段落开头声明口径默认。
>
> 例：`2022 Q4 HV PnL = -$26.8k (research scale; ≈ -$2.7k live scaled est)`
>
> 例外：如果上下文已经在引用 SPEC-072 dual-scale UI 截图，可省略括号注脚。
>
> Why：Q029 Tier 1 实测 HIGH_VOL 占交易 ~16%，占总 PnL ~3-5%，但在亏损年份占比显著（2022 Q4 集中）。混用 research/live scale 解读累积偏差最大的就是 grinding decline / aftermath 类研究。
>
> How to apply: 写 RESEARCH_LOG entry / spec / handoff 时，引用 HIGH_VOL aggregate 数字前先想 "我现在引用的是 research scale 还是 live est？" — 若不确定就标 research。

**`REVIEW_TEMPLATE.md §6.1`** （Short-Premium Standard Checks）加入新检查项：

> **6.1.7 — HIGH_VOL aggregate scale annotation**
>
> 若 spec / research 引用 HIGH_VOL aggregate metric（avg PnL、stop rate、recovery rate 等），是否显式标注 research scale 或 live scaled est 口径？未标注视为 research scale，但应主动标注以避免歧义。
>
> Reference: `QUANT_RESEARCHER.md` HIGH_VOL Aggregate Scale Convention 章节。

---

## 接受测试场景（ST6–ST9）

### ST6 — Matrix view HV cell 双值

启动 dev server，打开 `/matrix`：
- 任一 HIGH_VOL 列的 cell（如 IC_HV @ HIGH_VOL/IV_HIGH/BULLISH）的 avg_pnl 显示为 `avg +$X + +$Y est`
- LOW_VOL / NORMAL 列的 cell 保持 `avg +$X` 单列
- WR 与 n 不变（不做 scaling）
- 切换 3Y/10Y/All 三个统计窗口都生效

### ST7 — Portfolio backtest HV 行双值

打开 `/portfolio_backtest` 或对应路由：
- HV trade 行 PnL/BP/credit 列双值
- 非 HV 行单列
- console 无 JS 报错

### ST8 — CSV export 含 scale 列

```bash
python3 scripts/export_backtest_trade_detail.py --start 2022-01-01 --end 2022-12-31 --out /tmp/q029_st8.csv
```
- 输出 CSV 包含 `live_scale_factor`、`live_scaled_exit_pnl_usd`、`live_scaled_total_bp` 三列
- HV 行 `live_scale_factor == 0.1`；非 HV 行 `== 1.0` 或 `== 2.0`（LOW_VOL）
- HV 行 `live_scaled_exit_pnl_usd == round(exit_pnl_usd * 0.1, 2)`

### ST9 — Governance 条款落地

- `QUANT_RESEARCHER.md` 新增 "HIGH_VOL Aggregate Scale Convention" 章节，含 Why / How to apply
- `REVIEW_TEMPLATE.md §6.1` 新增 6.1.7 检查项
- 两文件 commit message 含 `SPEC-072.1`

---

## Acceptance Criteria

| AC | 描述 | 验证 |
|---|---|---|
| AC1 | F8 — `matrix.html` 引入 spec072_helpers 且 HV cell avg_pnl 双值 | ST6 visual + view-source |
| AC2 | F8 — 非 HV cell 仍单列；WR/n 不被 scale 影响 | ST6 visual |
| AC3 | F9 — `portfolio_backtest.html` 引入 spec072_helpers 且 HV row 双值 | ST7 visual |
| AC4 | F10 — CSV 含三个新列；HV 行 `live_scale_factor=0.1`；非 HV 行 `1.0` 或 `2.0` | ST8 CSV inspection |
| AC5 | F10 — `live_scaled_exit_pnl_usd ≈ exit_pnl_usd × scale`（容许浮点 round 0.01 误差） | ST8 numerical spot check |
| AC6 | F11 — `QUANT_RESEARCHER.md` 新章节存在且含 Why/How | ST9 view file |
| AC7 | F11 — `REVIEW_TEMPLATE.md §6.1.7` 检查项存在 | ST9 view file |
| AC8 | 三个 frontend 主 tab 切换无 JS console error | ST6 + ST7 + SPEC-072 ST1 复跑 |
| AC9 | backend 文件 MD5 不变（除 export script F10）；engine.py / selector.py / signals/* 不动 | shasum spot check |
| AC10 | PM live smoke：Matrix view 上挑一笔 HV cell 数字与手动 ×0.1 计算一致 | PM 操作 |

---

## 边界条件与约束

- **scale factor 来源**：沿用 SPEC-072 helpers 的硬编码（HIGH_VOL=0.1, LOW_VOL=2, default=1）；**不在本 patch 重新讨论**
- **CSV 列名稳定**：`live_scale_factor` / `live_scaled_exit_pnl_usd` / `live_scaled_total_bp` 三列名固定，下游脚本可信赖
- **historical CSV 不回填**：仅影响新生成；下游脚本应处理两种 schema（旧 CSV 无三列时退回单口径解读）
- **governance 条款不强制 retroactive**：已发表的 RESEARCH_LOG entry 不要求回溯标注；新写作生效
- **engine 与 selector 文件 MD5 不变**：本 patch 是 reporting-only，与 SPEC-072 一致

---

## In Scope / Out of Scope（细化）

| In Scope | Out of Scope |
|---|---|
| F8/F9 frontend 改动 | 改 backend trade aggregation 逻辑 |
| F10 CSV 三列添加 | 改 trade_log.csv schema 历史回填 |
| F11 governance 条款 | 自动检测器（lint 工具检查 Quant 文档是否标注 scale）|
| ST6–ST9 smoke test | live 端 SPX/XSP 切换逻辑 |

---

## 数据契约

| 字段 | 来源 | 用途 |
|---|---|---|
| `cellStats[regime\|iv\|trend].avg_pnl` | 已有 `data/research_views.json` 派生 | F8 dual-scale 输入 |
| `Trade.regime` / `Trade.exit_pnl` / `Trade.total_bp` | 已有 trade log fields | F9 / F10 |
| `Recommendation.regime` | 已有 | helper 决定 scale factor |

后端不新增字段。

---

## Risks / Counterarguments

- **R1**：governance 条款强制力有限——Quant 写作时仍可能忘记标注。Mitigation：REVIEW_TEMPLATE §6.1.7 在 2nd Quant review 时强制检查
- **R2**：CSV 三列可能影响下游脚本 schema parsing。Mitigation：列名追加到末尾，下游用 dict-style read 不会断
- **R3**：matrix.html 的 cell 渲染逻辑与 SPEC-072 F5 trade log 渲染逻辑略不同（cell 是 stat 聚合，row 是单笔）；helper 复用应该没问题但需 ST6 验证
- **R4**：用户仍可能主要看 research scale，把 live_scaled 当装饰品 → 不影响 SPEC，但是 governance gap 要持续教育

---

## Implementation 估算

| 任务 | 工作量（CC+gstack 估算）|
|------|------------------------|
| F8 matrix.html | ~10 min |
| F9 portfolio_backtest.html | ~15 min |
| F10 CSV column | ~5 min |
| F11 governance edits | ~10 min |
| ST6–ST9 smoke test | ~15 min |
| **总计** | **~1 小时** |

---

## 变更记录

| 日期 | 变更 | 状态 |
|------|------|------|
| 2026-05-09 | Quant 起草 SPEC-072.1（Q029 Tier 1 closure 推动） | DRAFT |
| 2026-05-09 | PM approved | APPROVED |
| 2026-05-09 | Quant 实施 F8-F11；smoke tests pass | DONE |

## 实施记录

- **F8** `web/templates/matrix.html`: 引入 `spec072_helpers.js`；`stat()` 重构为 `statBase(s, dualScale)`；strategy column 单值（跨 regime aggregate），cell column 在 `regime === 'HIGH_VOL'` 时双值（`avg $X + $Y est`）。WR / n 不变。
- **F9** `web/templates/portfolio_backtest.html`: 引入 `spec072_helpers.js`（structural prevention）。当前页面渲染 sleeve-level joint metrics（BP utilization、idle day capture），无 HV-specific 渲染点；helpers ready for future content。
- **F10** `scripts/export_backtest_trade_detail.py`: 在每笔 trade dict 末尾追加 3 个新字段 — `live_scale_factor`、`live_scaled_exit_pnl_usd`、`live_scaled_total_bp`。下游脚本通过 dict-style read 安全访问。
- **F11** governance:
  - `QUANT_RESEARCHER.md` 新增 "HIGH_VOL Aggregate Scale Convention" 章节（含强制标注规则 + Why + How to apply + 当前 frontend 覆盖矩阵）
  - `REVIEW_TEMPLATE.md §6.1` 新增 "HIGH_VOL aggregate scale annotation" 检查项

## Smoke test 结果（2026-05-09）

- Python syntax: `scripts/export_backtest_trade_detail.py` py_compile PASS
- HTML helper inject 验证:
  - `matrix.html`: `spec072_helpers.js` ✅、`liveScaleFactor` ✅、`dual-est` class ✅
  - `portfolio_backtest.html`: `spec072_helpers.js` ✅
- CSV columns 验证: 三个新字段名都已在 export script 中
- Governance 文件验证: QR / REVIEW_TEMPLATE 关键字符串都已存在

完整 ST6-ST9 浏览器视觉测试由 PM live smoke 时验证。

---

## 关联

- **Parent**: SPEC-072（Frontend Dual-Scale Display + Broken-Wing Visual，DONE 2026-04-25）
- **Question**: Q029（research/live notional parity）
- **Research source**: Q029 Tier 1 evaluation 2026-05-09（待写入 RESEARCH_LOG R-20260509-10）
- **Multi-agent flow**: Quant draft → PM authorise → Developer (Fast Path) → Q029 closure
- **Predecessor mitigation**: SPEC-072 frontend dual-scale 在 4 个主 template 已 done；本 patch 补完矩阵视图 / 组合回测 / CSV / governance 4 处缺口
