# SPEC-031: Frontend Improvements — Decision Clarity & Research Metrics

## 目标

**What**：基于三份前端 review（HC Claude、ChatGPT 2nd quant、Quant Trader 视角）的共识项，
对现有四页前端做针对性改进，提升日常交易操作效率和研究数据可读性。

**Why**：当前前端是合格的 strategy research dashboard，
但从量化交易员实操角度，缺少决策信心锚点（历史统计支撑）、
持仓风险状态、矩阵与实时信号的联动，以及回测的时间序列拆解。

---

## 接受 / 不接受的决策

### 接受（本 SPEC 实现）

三份 review 共识高、实现成本低的项目：

| 项目 | 来源 | 理由 |
|------|------|------|
| Rec 卡加历史 WR/n | HC + OAI | 数据已有（/api/backtest/stats），前端显示即可 |
| Matrix 格子加 Avg PnL | HC + OAI | 仅需 API 新增 avg_pnl 字段，前端展示 |
| Matrix 高亮当前信号格子 | HC + OAI | 前端纯逻辑，live signal 已在页面 |
| Position Panel 加 days_held + DTE 估算 | HC + OAI | 前端从 opened_at 计算，DTE 从 catalog 查表 |
| Backtest 加年度 PnL 柱状图 | HC | trades 数据已有，前端聚合 + Chart.js 渲染 |
| Grid Search 加 OOS 警告文字 | HC | 前端纯文案，一行改动 |

### 不接受（defer 到后续 SPEC）

| 项目 | 原因 |
|------|------|
| Portfolio Risk Bar（BP 利用率、shock state） | 需新 API + 多后端依赖 |
| Decision Strip 含 "re-enable when" 条件 | 需 strategy selector 暴露状态转换逻辑 |
| Margin 页 Live BP Calculator | 需新后端计算 endpoint |
| Position Panel 实时 unrealized PnL | 需 _current_value + 实时市场数据 fetch |
| Signal Strip sparkline（30日趋势线） | 需历史信号序列新 API |

---

## 功能定义

### F1 — Dashboard：Recommendation 卡加历史 WR/n

**位置**：rec-card 的 metrics 行下方，rationale 上方

**显示格式**：
```
HISTORICAL EDGE    All-time: WR 78% · n 102    3Y: WR 75% · n 24
```

**数据来源**：`/api/backtest/stats` 已有 `all` 和 `3y` 的 per-strategy `{n, win_rate}`。
前端根据 `d.strategy_key` 匹配后展示。

**边界**：
- 若 stats 尚未加载（异步），该行显示 `—`，不阻塞主卡渲染
- 若 n < 5，显示 `n too small`，不显示 WR

---

### F2 — Matrix：格子加 Avg PnL

**后端改动（server.py）**：
`/api/backtest/stats` 的 `by_strat` 和 `by_cell` 计算中，
额外累加 `total_pnl`，输出字段从 `{n, win_rate}` 扩展为 `{n, win_rate, avg_pnl}`。

```python
# 现有
rec["n"] += 1
if win: rec["wins"] += 1

# 新增
rec["total_pnl"] = rec.get("total_pnl", 0) + t.exit_pnl

# 序列化时
"avg_pnl": round(v["total_pnl"] / v["n"])
```

**前端显示**：
每个 matrix 格子从原来的：
```
BPS
WR 78%  n=102
```
改为：
```
BPS
WR 78%  avg $+373
n=102
```

avg_pnl 用颜色区分：正值绿色，负值红色。

---

### F3 — Matrix：高亮当前信号格子

**逻辑**：
`/api/recommendation` 返回的 `vix_snapshot.regime`、`iv_snapshot.iv_signal`、
`trend_snapshot.signal` 三者组合成 `REGIME|IV|TREND` key。
与 matrix 格子的 cell_key 比对，命中格子加 `current-cell` CSS class。

**视觉**：
- 命中格子加金色边框（`border: 2px solid var(--gold)`）
- 格子左上角加小标 "NOW" badge

**边界**：
- 若 live signal 加载失败，不高亮任何格子（静默降级）
- Matrix 页独立加载 `/api/recommendation`，不依赖 Dashboard

---

### F4 — Open Position Panel：加 days_held + DTE 估算

**数据来源**：
- `days_held`：前端计算 `today - opened_at`（纯 JS，无需 API 改动）
- `entry_dte`：从 `STRATEGY_META[strategy_key]` 查 `dte`（catalog 已有）
- `est_dte_remaining`：`entry_dte - days_held`，若 ≤ 0 显示 `expired / roll?`

**显示格式**（追加在 pos-meta 行）：
```
Opened 2026-03-15  ·  Day 20  ·  ~10 DTE remaining
```

**边界**：
- est_dte_remaining 仅为估算（不含 roll 后的 DTE 重置），加 `~` 前缀
- 若 roll_count > 0，DTE 估算不可靠，改为显示 `DTE est. unavailable (rolled)`

---

### F5 — Backtest：年度 PnL 柱状图

**位置**：Equity Curve 下方，新增一个 section

**标题**：`Annual P&L — By Year`

**图表**：Chart.js Bar chart
- X 轴：年份（从 trades 的 exit_date 提取）
- Y 轴：当年所有 trades 的 exit_pnl 之和
- 颜色：正值 `var(--green)`，负值 `var(--red)`
- 在 stress years（2008/2011/2015/2020/2022）的 bar 顶部加小标注 `stress`

**数据**：从 `/api/backtest` 返回的 `trades` 数组聚合，前端计算，无需新 API。

**边界**：
- 仅在 backtest 数据加载完成后渲染
- start_date 早于 2003 时才显示（否则年份太少，图没意义）

---

### F6 — Backtest Grid Search：OOS 警告

**位置**：Grid Search 面板标题行旁边

**文案**：
```
⚠ If start_date spans full history, results are in-sample.
  For valid OOS test, use start_date ≥ 2021-01-01.
```

**实现**：纯 HTML/CSS，静态文字，无逻辑。

---

## 接口定义

### 后端改动（仅 server.py）

`/api/backtest/stats` 响应格式扩展：

```json
{
  "all": {
    "bull_put_spread": { "n": 102, "win_rate": 78, "avg_pnl": 373 }
  },
  "all_cell": {
    "NORMAL|HIGH|BULLISH": { "n": 46, "win_rate": 76, "avg_pnl": 346 }
  }
}
```

### 前端改动

| 文件 | 改动 |
|------|------|
| `web/templates/index.html` | F1：rec 卡加 WR/n 行；F4：pos-panel 加 days_held/DTE |
| `web/templates/matrix.html` | F2：格子加 avg_pnl；F3：current-cell 高亮 |
| `web/templates/backtest.html` | F5：年度柱状图；F6：OOS 警告文字 |
| `web/server.py` | F2：stats API 加 avg_pnl 字段 |

---

## 边界条件与约束

- 所有改动为增量，不破坏现有布局和 API 兼容性
- 不改动 `engine.py`、`signals/`、`strategy/selector.py`
- F1/F3 的 stats/recommendation 加载失败时，静默降级，不影响主功能
- avg_pnl 使用 `exit_pnl`（回测 PnL），不是 unrealized PnL
- F4 的 DTE 估算明确标注 `~`，不作为交易决策依据

---

## 不在范围内

- Portfolio Risk Bar（BP 利用率 live 计算）
- Decision Strip 含状态转换逻辑
- Position Panel 实时 unrealized PnL
- Margin 页 Live BP Calculator
- Signal Strip sparkline

---

## Review

- 结论：PASS
- AC1–AC7 全部通过代码核查
- AC5 年度柱状图：start_date ≥ 2003-01-01 时隐藏，需跑 26yr 回测才可见，行为符合 SPEC 设计
- 注意事项：stats API 新增 avg_pnl 字段，需重启 web 进程令旧内存缓存失效

---

## 验收标准

1. **AC1**：Dashboard rec 卡在 recommendation 下方显示 `All-time WR / n` 和 `3Y WR / n`
2. **AC2**：Matrix 每个格子显示 avg_pnl（含颜色区分正负）
3. **AC3**：Matrix 当前信号格子有金色边框 + "NOW" badge
4. **AC4**：Open Position Panel 显示 days_held 和 `~X DTE remaining`（已 roll 时显示不可用）
5. **AC5**：Backtest 页有年度 PnL 柱状图，stress years 有标注
6. **AC6**：Grid Search 面板有 OOS 警告文字
7. **AC7**：所有改动在现有 API 失败时静默降级，不产生 JS 错误

---

Status: DONE
