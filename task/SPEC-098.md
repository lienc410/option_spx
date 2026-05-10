# SPEC-098: Q042 Drawdown Overlay — Independent Frontend Dashboard

Status: APPROVED

## Design Source

PM-driven。SPEC-094 F7 仅在 portfolio home 嵌入最小 UI block；PM 要求与 `/q041`、`/es-backtest` 平级的独立前端，支持完整策略监控和历史分析。

## 图表清单（PM 已批准，无需二次确认）

### Strategy Dashboard（`/q042`）

| ID | 图表 | 类型 | 用途 |
|---|---|---|---|
| C1 | Sleeve 状态卡片（A + B）| 状态卡 | 当前 state（armed / watching / active）+ ddATH% + 距触发阈值 |
| C2 | SPX Price + ATH + ddATH% 监控图 | 折线 + 双 Y 轴 | 实时位置感知：当前 SPX 相对 ATH 的距离 |
| C3 | 触发距离 gauge（Sleeve A / B）| 进度条 | ddATH 离 -4%（A）/ -15%（B）还有多远 |
| C4 | Sleeve B MA10 状态 | 状态 badge | close > MA10 当前状态 + MA10 具体数值 |
| C5 | 当前活跃仓位（如有）| 简表 | strikes / DTE / est. value |

### Backtest & History Page（`/q042/backtest`）

| ID | 图表 | 类型 | 用途 |
|---|---|---|---|
| C6 | SPX Price + ATH + 入场/出场 overlay | 折线 + marker | 19yr 历史触发时点全览 |
| C7 | 累计 P&L 曲线 | 折线 | 回测历史（实线）+ paper 实际（虚线，暂 fail-soft）|
| C8 | ddATH% at trigger 分布 | 直方图 | 每次入场时 ddATH 水位分布——判断"是否在合理深度入场" |
| C9 | Sleeve A vs B trade 对比表 | 表格 | 各自笔数 / WR / avg P&L / worst trade |
| C10 | P&L by year | 柱状图 | 按年份拆分盈亏，识别 strategy 友好 vs 不友好环境 |
| C11 | Combined BP timeline | 折线 | 历史 BP% 使用（来自 backtest account_pct 字段）|

## 导航规范

与 `/q041`、`/spx`、`/es` 平级，nav bar 新增 Q042 入口：
- `/q042` — Strategy Dashboard
- `/q042/backtest` — 回测 + 历史分析

## 功能要求

### F1 — 新增 API 端点（`server.py`）

**`GET /api/q042/state`**（已存在，确认 payload 是否足够）
- 确认返回：sleeve A/B state、ath_running_max、当前 ddATH%、combined_bp_pct
- 若缺少 ddATH%、MA10 值，补充计算逻辑（从 yfinance 取当日 SPX close 和 10日均线）

**`GET /api/q042/backtest`**（新增）
- 读取 `data/q042_backtest_trades.csv`
- 返回：trades list + 按 sleeve 聚合的 summary（n / wr / avg_pnl / worst_pnl）
- Fail-soft：文件不存在时返回 `{"trades": [], "summary": {}}`

**`GET /api/q042/paper`**（新增）
- 读取 `data/q042_paper_trades.jsonl`
- Fail-soft：文件不存在时返回 `[]`（当前无 paper trades）

**`GET /api/q042/spx-history`**（新增，C2/C6 用）
- 返回近 2yr SPX 日线数据 + rolling ATH（cummax from 2007-01-01）+ ddATH%
- 数据源：yfinance `^GSPC`（与现有 SPX recommendation chart 同源）

### F2 — `/q042` Dashboard 页面（新建 `web/templates/q042.html`）

- C1 Sleeve 状态卡片：
  - Sleeve A：state badge（🟢 Armed / 🟡 Watching / 🔴 Active）+ 当前 ddATH% + "距 dd4 还有 X.X%"
  - Sleeve B：同上 + "距 dd15 还有 X.X%" + MA10 状态（close > MA10 ✓ / ✗）
- C2 SPX + ATH 监控图：Chart.js 折线，双数据集（SPX 主轴 / ddATH% 次轴），最近 252 交易日
- C3 触发距离 gauge：HTML progress bar，填满 = 已触发，当前值 = ddATH / 阈值
- C4 MA10 badge：绿色 = close > MA10（Sleeve B watch 条件满足），红色 = 否
- C5 活跃仓位：若 `active_position_id != null` 展示简表；否则显示 "No active position"

### F3 — `/q042/backtest` 分析页面（新建 `web/templates/q042_backtest.html`）

- C6 SPX + ATH + entry/exit overlay：历史 19yr SPX 价格 + ATH 线 + 每笔 trade 的 entry（▲）/ exit（▽）marker，按 sleeve 分色（A = 蓝，B = 橙）
- C7 累计 P&L：回测历史（实线）+ paper 实际（虚线）；paper 段 fail-soft（不存在时仅显示回测）
- C8 ddATH at trigger 直方图：x = ddATH%，bin width 1%，区分 Sleeve A / B
- C9 Sleeve 对比表：A vs B，列：笔数 / WR / avg P&L / worst P&L / avg DTE held
- C10 P&L by year：堆叠柱状图，A + B 各色，x = year
- C11 BP timeline：折线，x = signal_date，y = account_pct（来自 CSV 字段）

### F4 — nav bar 更新

在现有 nav（SPX / /ES / Q041 / Portfolio）中新增 Q042 入口，链接到 `/q042`。

### F5 — Sleeve State Caveat

在 `/q042` Dashboard 页顶部固定一行 caveat banner：  
`"Q042 is paper-trading only. Triggers generate Telegram alerts for manual execution. No automatic order placement."`

## 数据来源汇总

| 数据 | 来源 | 状态 |
|---|---|---|
| Sleeve state / ATH / ddATH | `/api/q042/state` + yfinance | 已有端点，需补充 ddATH% / MA10 |
| SPX 历史 + ATH | yfinance `^GSPC` | 复用现有 market cache 路径 |
| 回测历史 trades | `data/q042_backtest_trades.csv` | 已有（30 trades）|
| Paper trades | `data/q042_paper_trades.jsonl` | 空，fail-soft |
| MA10 | yfinance `^GSPC` 10日均线 | 新增计算 |

## 验收标准

- **AC1** — `/q042` 路由返回 200；nav bar 有 Q042 入口
- **AC2** — `/q042/backtest` 路由返回 200
- **AC3** — C1 Sleeve 状态卡片展示 A/B state + ddATH% + 距触发距离
- **AC4** — C2 SPX + ATH 监控图显示（最近 252 TD，ATH 折线可见）
- **AC5** — C3 触发距离 gauge 数值正确（ddATH / 阈值比例）
- **AC6** — C6 SPX overlay 含所有 30 笔回测 trade 的 entry/exit marker
- **AC7** — C7 累计 P&L 曲线显示回测历史；paper 段 fail-soft（无 paper trades 时不报错）
- **AC8** — C8 ddATH at trigger 直方图显示（区分 A / B）
- **AC9** — C9 Sleeve 对比表数据正确（WR / avg P&L 与 CSV 数据一致）
- **AC10** — F5 caveat banner 可见
- **AC11** — `/api/q042/backtest` 返回 30 trades + summary；fail-soft 验证
- **AC12** — 回归：SPX、/ES、/q041、portfolio home 不受影响

## 不在范围内

- 实时 Greeks / IV 展示
- 订单自动化（Telegram alert 模式不变）
- Q042 backtest 算法修改
- VIX regime 分布图（Q041 类似图；Q042 触发频率低，样本不足）

## 参考文件

```
web/templates/q041.html          ← Dashboard 参考（C1-C5 结构）
web/templates/q041_backtest.html ← Backtest 页参考（C6-C11 结构）
web/server.py                    ← /api/q042/state 已有；新端点挂载点
data/q042_backtest_trades.csv    ← C6/C7/C8/C9/C10/C11 数据源
data/q042_state.json             ← C1/C3/C4/C5 数据源
production/q042_executor.py      ← sleeve state 定义参考
task/SPEC-094.md                 ← Q042 策略规格参考
```

## Review

（待填写）
