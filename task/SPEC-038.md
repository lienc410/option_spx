# SPEC-038: Paper Trade Tag & Performance Filter

Status: DONE

## 目标

**What**：
1. 在真实交易录入链路中新增 `paper_trade` 标签
2. 让 trade log resolved 结果保留该标签
3. 让 live performance 页面可选择是否包含 `paper trade`

**Why**：
- 当前系统已经有真实交易录入、correction / void、live performance 页面
- 但还不能区分正式交易与模拟交易
- 如果 paper trades 与真实成交混在一起，会污染 realized PnL、win rate、expectancy 等绩效口径

---

## 核心口径

### Trade-level Flag

`paper_trade` 是 **trade_id 级别** 的标签，不是单条事件级别的独立统计对象。

也就是说：
- trade 的 `open` 事件决定该 trade 是否为 paper trade
- 同一 `trade_id` 下的 `roll / close / note / correction / void` 都继承这一属性

### Performance 默认口径

`/api/performance/live` 默认 **不包含** paper trades。

只有显式指定：

```http
GET /api/performance/live?include_paper=1
```

才把 paper trades 纳入 realized / by_strategy / monthly / recent_closed / open_positions。

### UI 默认行为

`/performance` 页面默认：
- `Exclude Paper Trades = ON`

用户可切换为包含 paper trades，但默认口径应保持“只看真实交易”。

---

## 功能定义

### F1 — Trade Log 新增 `paper_trade`

在 `SPEC-034` 的 open 录入中新增字段：

```json
{
  "paper_trade": true
}
```

适用范围：
- `POST /api/position/open`
- `GET /api/position/open-draft` 可返回默认值 `false`

说明：
- 若未传，默认 `false`
- 该字段写入：
  - `current_position.json`
  - `trade_log.jsonl` 的 `open` 事件

---

### F2 — State / Resolved Log 保留标签

`strategy/state.py` 和 `resolve_log()` 需要保留 `paper_trade`：

- 当前 open position API 应可返回：

```json
{
  "paper_trade": true
}
```

- `GET /api/trade-log` 的 resolved 结果中：

```json
{
  "id": "2026-04-05_bps_001",
  "paper_trade": true,
  "open": {...},
  "close": {...}
}
```

建议规则：
- resolved trade 的 `paper_trade` 取自 `open.paper_trade`，若缺失默认 `false`
- `resolve_log()` 在每条返回的 trade dict 顶层新增 `"paper_trade": bool` 字段（与 `voided` 同级），需修改 `logs/trade_log_io.py`

---

### F3 — Correction 支持修改 `paper_trade`

允许通过 correction 修正误录：

```json
{
  "trade_id": "2026-04-05_bps_001",
  "target_event": "open",
  "fields": {
    "paper_trade": true
  },
  "reason": "should have been logged as paper"
}
```

要求：
- `paper_trade` 加入 open 的可修正字段集合
- correction 后 resolved 视图与 performance 统计立即反映更新

---

### F4 — Live Performance API 过滤参数

扩展：

```http
GET /api/performance/live
GET /api/performance/live?include_paper=1
```

默认：
- `include_paper = false`

返回 payload 建议增加调试字段：

```json
{
  "include_paper": false,
  "paper_trade_count": 3
}
```

说明：
- `paper_trade_count` = resolved 中非 voided 的 paper trades 数量
- 便于前端显示当前过滤状态

---

### F5 — Performance 聚合口径

`compute_live_performance(...)` 新增参数：

```python
def compute_live_performance(
    resolved_trades: list[dict],
    schwab_snapshot: dict | None = None,
    include_paper: bool = False,
) -> dict:
    ...
```

过滤规则：
- `include_paper = False` 时：
  - `paper_trade = true` 的 trade 不进入：
    - summary
    - by_strategy
    - monthly
    - recent_closed
    - open_positions
- `include_paper = True` 时：
  - 正常纳入所有聚合
  - open_positions 每条 row 需包含 `"paper_trade": bool`，供前端显示 PAPER badge

open_positions row 示例（include_paper=True 时）：
```json
{
  "id": "2026-04-05_bps_001",
  "strategy_key": "bull_put_spread",
  "paper_trade": true,
  "contracts": 2,
  "entry_premium": 3.15,
  "mark": null,
  "trade_log_pnl": null,
  "unrealized_pnl": null
}
```

Schwab 仍仅用于 enrich open positions，不改变 paper/real 分类。

---

### F6 — Dashboard Open Position 录入 UI

在 `Open Position` modal 中新增：

- `Paper Trade` checkbox

默认：
- 未勾选

提交后：
- `/api/position/open` 带上 `paper_trade`

当前 open position panel 建议也显示一个 badge：
- `PAPER`

避免用户忘记自己当前打开的是 paper trade。

---

### F7 — Performance 页面过滤开关

`/performance` 页面新增一个 toggle：

- `Exclude Paper Trades`

交互建议：
- 默认开启
- 开启时：请求 `/api/performance/live`
- 关闭时：请求 `/api/performance/live?include_paper=1`

页面顶部可显示一条小状态说明：

- `Showing live performance excluding paper trades`
- 或
- `Including paper trades in summary`

---

## 数据计算规则

### Realized Performance

在现有 `SPEC-037` 规则基础上额外增加：

1. 先排除 `voided = true`
2. 若 `include_paper = false`，再排除 `paper_trade = true`
3. 只统计同时存在 `open + close` 的 resolved trades

### Open / Unrealized

若 `include_paper = false`：
- paper open trades 不显示在 open positions 区

若 `include_paper = true`：
- paper open trades 可以显示
- 建议在前端卡片上带 `PAPER` badge

---

## 边界条件与约束

- `paper_trade` 只是一种分类标签，不改变 PnL 计算公式
- `paper_trade` 不影响 correction / void 的既有逻辑
- `paper_trade` 不改变 Schwab integration 行为
- 若当前 open position 是 paper trade，Schwab 可能没有对应 live position；页面应 graceful degrade
- 不支持一个 trade 中途从 real 变 paper 再分叉成两个 trade；若修正标签，则整个 trade 一并切换

---

## 不在范围内

- 单独的 paper account
- paper trade 与 broker reconciliation 自动对账
- 按 real vs paper 分开画两条长期 equity curve
- CSV 导出
- 多标签系统（如 journal / setup / confidence）

---

## 验收标准

1. **AC1**：`POST /api/position/open` 支持 `paper_trade`，并写入 state + trade log
2. **AC2**：`GET /api/trade-log` 的 resolved 结果带 `paper_trade`
3. **AC3**：`paper_trade` 可通过 correction 修改
4. **AC4**：`/api/performance/live` 默认排除 paper trades
5. **AC5**：`/api/performance/live?include_paper=1` 可包含 paper trades
6. **AC6**：`/performance` 页面提供过滤 toggle，且默认排除 paper trades
7. **AC7**：Dashboard 的 open position 录入支持勾选 `Paper Trade`
8. **AC8**：当前 open paper trade 在 UI 中有明显标识

---

## Review

- 结论：PASS
- AC1–AC8 全部通过代码核查与回归测试
- `resolve_log()`：顶层 `paper_trade = bool(open.get("paper_trade", False))` 正确处理缺失字段 ✓
- correction 流：`_CORRECTABLE_FIELDS["open"]` 已加入 `paper_trade`（server.py:449）；correction 后 state 同步更新，测试验证 True → False 切换 ✓
- `compute_live_performance()`：`include_paper=False` 时 paper trades 从 closed / open_only 两路均被排除；`paper_trade_count` 仅统计非 voided 的 paper trades ✓
- open_positions row 含 `paper_trade` 字段（via `update_open_position` + state 透传）✓
- `open-draft` 返回默认 `paper_trade: false` ✓
- Dashboard PAPER badge + Open Position modal checkbox 已实施 ✓

---

## 实施顺序建议

1. 先做后端字段贯通：open → state → resolved log
2. 再做 performance API 过滤
3. 最后做 Dashboard checkbox 与 `/performance` toggle

---

## 备注

依赖：
- `SPEC-034`
- `SPEC-036`
- `SPEC-037`

可选增强：
- 若未来新增 broker reconciliation，可把 `paper_trade` 作为排除对账的默认条件
