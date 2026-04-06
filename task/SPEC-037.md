# SPEC-037: Live Trade Performance Tracking

Status: DONE

## 目标

**What**：
1. 基于真实交易日志（trade log）新增 live performance 计算层
2. 提供真实交易绩效 API：realized / unrealized / by-strategy / monthly
3. 新增独立 `/performance` 页面，展示真实执行结果，而非回测结果

**Why**：
- `SPEC-034` 已经提供真实交易录入
- `SPEC-036` 已经提供 correction / void 和 resolved log
- `SPEC-035` 已经提供 Schwab live snapshot 骨架
- 现在系统具备了构建真实交易 performance 的基础数据条件

---

## 核心口径

### Realized Performance

只统计：
- `resolve_log()` 后 `voided = false`
- 且同时存在 `open` 和 `close` 的交易

计算字段以 **resolved 后的字段值** 为准。

### Open / Unrealized

未平仓交易单独展示，不混入 realized 统计：
- 不进入 win rate
- 不进入 avg win / avg loss
- 不进入 expectancy
- 不进入 cumulative realized PnL

### Schwab 的角色

Schwab 只用于：
- 当前 open trade 的 live mark / Greeks / unrealized PnL

Schwab 不作为：
- 历史 realized ledger 真相源
- correction 覆盖源

历史绩效仍以 resolved trade log 为准。

---

## 功能定义

### F1 — `performance/live.py`

新增聚合模块，输入为：
- `resolve_log()` 的结果
- 可选 Schwab live snapshot

输出：
- summary
- by_strategy
- monthly
- recent_closed
- open_positions

建议函数：

```python
def compute_live_performance(resolved_trades: list[dict], schwab_snapshot: dict | None = None) -> dict:
    ...
```

---

### F2 — Summary 指标

返回：

```json
{
  "closed_trades": 12,
  "open_trades": 1,
  "win_rate": 0.67,
  "total_realized_pnl": 4250.0,
  "avg_win": 680.0,
  "avg_loss": -420.0,
  "expectancy": 354.2,         // = (win_rate × avg_win) + ((1 - win_rate) × avg_loss)
  "best_trade": 1200.0,
  "worst_trade": -900.0
}
```

说明：
- `win_rate` = realized PnL > 0 的 closed trades / total closed trades
- `expectancy` = (win_rate × avg_win) + ((1 − win_rate) × avg_loss)

---

### F3 — By Strategy

输出示例：

```json
{
  "bull_put_spread": {
    "n": 5,
    "win_rate": 0.8,
    "total_pnl": 2100.0,
    "avg_pnl": 420.0
  },
  "iron_condor": {
    "n": 3,
    "win_rate": 0.67,
    "total_pnl": 900.0,
    "avg_pnl": 300.0
  }
}
```

键使用 `strategy_key`，前端通过 catalog 映射显示名。

---

### F4 — Monthly PnL

按 `close.timestamp`（解析为 ET 时区，取 YYYY-MM）归档：

```json
[
  { "month": "2026-01", "realized_pnl": 1200.0, "trades": 3 },
  { "month": "2026-02", "realized_pnl": -450.0, "trades": 2 }
]
```

用于：
- monthly bar chart
- cumulative line chart

---

### F5 — Open Positions Snapshot

若当前存在 open trade：
- 读取 resolved open trade
- 若 Schwab live 可用，则叠加：
  - mark
  - bid / ask
  - unrealized_pnl
  - trade_log_pnl
  - Greeks

输出示例：

```json
[
  {
    "id": "2026-04-05_bps_001",
    "strategy_key": "bull_put_spread",
    "strategy": "Bull Put Spread",
    "opened_at": "2026-04-05",
    "contracts": 2,
    "entry_premium": 3.15,
    "mark": 2.70,
    "trade_log_pnl": 90.0,     // (actual_premium - mark) × contracts × 100
    "unrealized_pnl": 84.0,   // 来自 Schwab，若未配置则为 null
    "delta": -0.28,
    "theta": -0.15
  }
]
```

---

### F5b — Recent Closed Trades

最近 10 笔已平仓交易，按 `close.timestamp`（ET 时区）倒序排列：

```json
[
  {
    "id": "2026-04-05_bps_001",
    "strategy_key": "bull_put_spread",
    "strategy": "Bull Put Spread",
    "opened_at": "2026-04-05",
    "closed_at": "2026-04-22",
    "contracts": 2,
    "actual_pnl": 320.0
  }
]
```

只返回 `voided = false` 且有 `open` + `close` 事件的 trade。

---

### F6 — 新增 API

#### `GET /api/performance/live`

返回：

```json
{
  "summary": {...},
  "by_strategy": {...},
  "monthly": [...],
  "recent_closed": [...],
  "open_positions": [...],
  "trade_count_raw": 15,
  "trade_count_effective": 13
}
```

说明：
- `trade_count_raw`：原始 trade_id 数量
- `trade_count_effective`：排除 `voided` 后数量
- `recent_closed`：最近 10 笔，见 F5b 定义

---

### F7 — 前端页面 `/performance`

新增页面：
- 路由：`/performance`
- Nav 增加 `Performance`

布局建议：

1. 顶部 metric cards
- Closed Trades
- Win Rate
- Total Realized PnL
- Avg Win / Loss
- Expectancy
- Open Trades

2. 图表区
- Monthly PnL 柱状图
- Cumulative Realized PnL 折线图

3. By Strategy 表
- strategy
- trades
- win rate
- total pnl
- avg pnl

4. Open Positions 区块
- 当前未平仓真实交易
- Schwab live 数据（若有）

5. Recent Closed Trades
- 最近 10 笔 closed trades，按 close.timestamp 倒序
- 每条显示：id / strategy / opened_at / closed_at / contracts / actual_pnl

---

## 数据计算规则

### Closed trade 的 realized PnL

优先级：

1. 若 resolved close 含 `actual_pnl`，直接使用
2. 否则若存在：
   - `open.actual_premium`
   - `close.exit_premium`
   - `open.contracts`
   
   则自动计算：

```python
(open.actual_premium - close.exit_premium) * contracts * 100
```

3. 若仍缺字段，则该 trade 不纳入 realized summary（跳过，不影响其他统计）

---

### Voided trades

`voided = true` 的 trade：
- 不进入 summary
- 不进入 by_strategy
- 不进入 monthly
- 默认不进入 recent_closed

可选：后端可提供 `include_voided=1` 调试参数，但不在本 spec 必须范围内。

---

## 边界条件与约束

- 只统计 resolved trade log，不读取 backtest
- 只支持单账户
- 不处理税务口径（wash sale / lot matching）
- 不处理 commissions / fees（除非后续另加字段）
- open position 的 unrealized 值不混入 realized performance
- 若 Schwab 未配置，页面仍可正常显示 realized performance

---

## 不在范围内

- Broker 历史成交导入
- 自动对账（broker reconciliation）
- 多账户支持
- CSV 导出
- 按 correction 历史显示审计轨迹的单独页面
- 把 unrealized equity curve 和 realized equity curve 混成一张净值曲线

---

## 验收标准

1. **AC1**：`/api/performance/live` 返回 summary / by_strategy / monthly / open_positions
2. **AC2**：summary 只统计非 voided 且已 closed 的 resolved trades
3. **AC3**：correction 后的 resolved 值会反映到 performance 结果
4. **AC4**：voided trade 不进入 realized metrics
5. **AC5**：open trades 单独显示，不混入 realized win rate / expectancy
6. **AC6**：Schwab 未配置时，页面不报错，open position 区仅显示 trade log 数据
7. **AC7**：Schwab 已配置时，open position 区显示 live unrealized / Greeks
8. **AC8**：新增 `/performance` 页面，并可展示 metric cards + monthly PnL + by-strategy

---

## 实施顺序建议

1. 先做后端聚合与 `/api/performance/live`
2. 再做 `/performance` 页面
3. 最后接入 Schwab open-position live enrich

---

## Review

- 结论：PASS
- AC1–AC8 全部通过代码核查与回归测试
- `compute_live_performance()`：voided 过滤、open/closed 分流、fallback PnL 计算公式均正确
- expectancy 公式：`(win_rate × avg_win) + ((1 − win_rate) × avg_loss)` 与 spec 一致 ✓
- `recent_closed` 按 `closed_at` 倒序 + `[:10]` 截取 ✓；测试验证 t2（2026-04-20）优先于 t1（2026-04-10）✓
- monthly 归档：`datetime.fromisoformat()` 正确解析带时区 offset 的 ISO 时间戳，`strftime("%Y-%m")` 取 ET 本地月份 ✓
- `trade_log_pnl` 由 `schwab/client.py` 的 `live_position_snapshot()` 计算后传入，`compute_live_performance()` 直接透传，不重复计算 ✓
- Schwab 未配置时：`schwab_snapshot.get("visible")` 为 falsy，open positions 只含 trade log 字段，页面不报错 ✓
- `/performance` 路由 + 4 个页面 nav 链接均已更新 ✓
- 数值验证：t1 PnL = (3.0−1.5)×2×100 = $300；total = $300 + (−$140) = $160；win_rate = 0.5 ✓

---

## 备注

本 spec 依赖：
- `SPEC-034`
- `SPEC-036`

可选增强依赖：
- `SPEC-035`
