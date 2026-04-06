# SPEC-034: Trade Entry UI & Trade Log

## 目标

**What**：
1. 为 Dashboard 新增交易操作 UI（开仓 / 平仓 / Roll / 备注）
2. 新增 `logs/trade_log.jsonl` 永久 trade log，记录每笔真实交易的完整信息
3. 为 state.py 已有的 write_state / close_position / roll_position / add_note 函数
   新增对应的 HTTP endpoint，供前端调用

**Why**：开始真实交易的基础数据层。
- 现在 state.py 只记录"当前持仓"，平仓后数据丢失
- 没有真实成交价格，无法计算 live performance（SPEC-035 Schwab API 和未来 performance page 都依赖此数据）
- 目前唯一的操作入口是 Telegram Bot，不方便复盘

---

## Trade Log Schema

文件：`logs/trade_log.jsonl`（每行一个 JSON 对象，append-only）

### 开仓记录（event: "open"）

```json
{
  "id":              "2026-04-05_bps_001",
  "event":           "open",
  "timestamp":       "2026-04-05T10:32:00-04:00",
  "strategy_key":    "bull_put_spread",
  "strategy":        "Bull Put Spread",
  "underlying":      "SPX",

  "short_strike":    5400,
  "long_strike":     5350,
  "expiry":          "2026-05-05",
  "dte_at_entry":    30,
  "contracts":       2,

  "actual_premium":  3.15,
  "model_premium":   3.28,

  "entry_spx":       5482.5,
  "entry_vix":       19.2,

  "regime":          "NORMAL",
  "iv_signal":       "HIGH",
  "trend_signal":    "BULLISH",

  "note":            ""
}
```

### 平仓记录（event: "close"）

```json
{
  "id":              "2026-04-05_bps_001",
  "event":           "close",
  "timestamp":       "2026-04-22T14:15:00-04:00",
  "exit_premium":    1.55,
  "exit_spx":        5510.0,
  "exit_reason":     "50pct_profit",
  "actual_pnl":      320.0,
  "note":            "closed at target"
}
```

### Roll 记录（event: "roll"）

```json
{
  "id":              "2026-04-05_bps_001",
  "event":           "roll",
  "timestamp":       "2026-04-28T11:00:00-04:00",
  "new_expiry":      "2026-05-30",
  "new_short_strike": 5420,
  "new_long_strike":  5370,
  "roll_credit":     1.20,
  "note":            "rolled at 21 DTE"
}
```

### 备注记录（event: "note"）

```json
{
  "id":              "2026-04-05_bps_001",
  "event":           "note",
  "timestamp":       "2026-04-10T09:00:00-04:00",
  "note":            "VIX spiked intraday, held position"
}
```

**设计原则**：
- `id` 由开仓时生成，格式 `{date}_{strategy_key_short}_{seq}`，后续所有事件共享同一 id
- append-only：从不修改已写入行，平仓/roll/备注都是新增行
- `actual_pnl` 在平仓时由前端计算：`(entry_premium - exit_premium) × contracts × 100`

---

## 功能定义

### F1 — Dashboard 操作面板（Position Panel 下方）

**无持仓时**：显示 `[+ Open Position]` 按钮

**有持仓时**：显示操作行
```
[Close]  [Roll]  [Add Note]
```

所有操作通过 modal 完成，不跳转页面。

---

### F2 — Open Position Modal

**触发**：点击 `[+ Open Position]` 按钮

**字段**（分两区）：

**自动预填区**（从当前推荐读取，可修改）：
- 策略：下拉选择（枚举 STRATEGIES_BY_KEY，过滤掉 reduce_wait）
- Underlying：SPX（固定）
- Expiry：date picker，根据策略 dte_text 建议默认值

**手动填写区**（真实成交数据）：
- Short Strike（数字输入）
- Long Strike（数字输入）
- Contracts（整数，默认 1）
- Actual Premium（填写时自动计算 vs model_premium 的差值并显示）
- Entry note（可选文字）

**提交行为**：
1. POST `/api/position/open`
2. 写入 state.py（调用 write_state）
3. append 一行 `event: "open"` 到 trade_log.jsonl
4. 关闭 modal，刷新 Position Panel

---

### F3 — Close Position Modal

**触发**：点击 `[Close]` 按钮

**字段**：
- Exit Premium（数字，真实平仓价格）
- Exit Reason：下拉（50pct_profit / stop_loss / roll_21dte / manual / expired）
- Note（可选）

**自动计算并显示**（只读）：
- Actual PnL = `(entry_premium - exit_premium) × contracts × 100`
- vs Model PnL（从 state 读取 model_premium 做对比，若有的话）

**提交行为**：
1. POST `/api/position/close`
2. 更新 state.py（调用 close_position）
3. append 一行 `event: "close"` 到 trade_log.jsonl（含 actual_pnl）
4. 刷新 Position Panel

---

### F4 — Roll Modal

**触发**：点击 `[Roll]` 按钮

**字段**：
- New Expiry
- New Short Strike
- New Long Strike
- Roll Credit（净权利金收入，正值 = 收 credit）
- Note（可选）

**提交行为**：
1. POST `/api/position/roll`
2. 更新 state.py（调用 roll_position，更新 rolled_at）
3. append 一行 `event: "roll"` 到 trade_log.jsonl
4. 同时更新 state.py 中的 strike/expiry 字段（见下方 state schema 扩展）

---

### F5 — Add Note Modal

**触发**：点击 `[Add Note]` 按钮

**字段**：单行文本输入

**提交行为**：
1. POST `/api/position/note`
2. 调用 state.py add_note
3. append 一行 `event: "note"` 到 trade_log.jsonl

---

## 后端改动

### state.py — schema 扩展

`write_state()` 新增字段（开仓时写入）：

```python
{
  ...existing fields...,
  "trade_id":       "2026-04-05_bps_001",
  "short_strike":   5400,
  "long_strike":    5350,
  "expiry":         "2026-05-05",
  "dte_at_entry":   30,
  "contracts":      2,
  "actual_premium": 3.15,
  "model_premium":  3.28,
  "entry_spx":      5482.5,
  "entry_vix":      19.2,
  "regime":         "NORMAL",
  "iv_signal":      "HIGH",
  "trend_signal":   "BULLISH",
}
```

这些字段在 close / roll 时保留，供 PnL 计算使用。

### server.py — 新增 endpoints

```
POST /api/position/open
POST /api/position/close
POST /api/position/roll
POST /api/position/note
GET  /api/trade-log          ← 返回 trade_log.jsonl 内容（用于 performance page）
```

### 新增 logs/trade_log_io.py

封装 trade log 的 read / append 操作：
- `append_event(event: dict) -> None`
- `load_log() -> list[dict]`
- `load_log_by_id(trade_id: str) -> list[dict]`

---

## 接口定义

### POST /api/position/open

Request body:
```json
{
  "strategy_key": "bull_put_spread",
  "underlying": "SPX",
  "short_strike": 5400,
  "long_strike": 5350,
  "expiry": "2026-05-05",
  "dte_at_entry": 30,
  "contracts": 2,
  "actual_premium": 3.15,
  "model_premium": 3.28,
  "entry_spx": 5482.5,
  "entry_vix": 19.2,
  "regime": "NORMAL",
  "iv_signal": "HIGH",
  "trend_signal": "BULLISH",
  "note": ""
}
```

Response: `{ "ok": true, "trade_id": "2026-04-05_bps_001" }`

### POST /api/position/close

Request body:
```json
{
  "exit_premium": 1.55,
  "exit_spx": 5510.0,
  "exit_reason": "50pct_profit",
  "note": ""
}
```

Response: `{ "ok": true, "actual_pnl": 320.0 }`

### POST /api/position/roll

Request body:
```json
{
  "new_expiry": "2026-05-30",
  "new_short_strike": 5420,
  "new_long_strike": 5370,
  "roll_credit": 1.20,
  "note": ""
}
```

### POST /api/position/note

Request body: `{ "note": "VIX spiked, held" }`

### GET /api/trade-log

Response: `{ "trades": [ ...all jsonl records... ] }`

---

## 边界条件与约束

- 若 actual_premium 未填（用户跳过），model_premium 作为 fallback，但标注为 `"premium_source": "model"`
- trade_id 生成规则：`{YYYY-MM-DD}_{strategy_key_abbrev}_{当日序号}`，确保唯一性
- `/api/trade-log` 为只读，不提供删除/修改接口（append-only 原则）
- open position modal 中策略下拉过滤 `manual_entry_allowed=False` 的策略（即 reduce_wait 不显示）
- 平仓时如果 state.py 中没有 actual_premium（旧格式持仓），actual_pnl 字段为 null
- 不改动 engine.py、backtest 层、signals 层

---

## 不在范围内

- Performance Tracking 页面（依赖本 SPEC 的 trade log，单独 SPEC）
- Schwab API 实时价格对比（SPEC-035）
- Telegram Bot 与 trade log 的联动（后续）
- 多仓位并发管理（state.py 目前单仓，保持不变）

---

## Review

- 结论：PASS
- AC1–AC7 全部通过代码核查与回归测试
- 额外实现：`/api/position/open-draft` 自动从当前推荐预填 Open modal（含 BS 模型 strike + premium），超出 SPEC 范围但有价值
- actual_pnl 计算验证：(3.15 − 1.55) × 2 × 100 = $320，结果正确
- Roll 后 strike 字段更新确认：state["short_strike"] 从 5400 → 5420，符合预期

---

## 验收标准

1. **AC1**：Dashboard 无持仓时显示 `[+ Open Position]` 按钮
2. **AC2**：Open modal 提交后，state.py 有持仓记录，trade_log.jsonl 有 `event: "open"` 行
3. **AC3**：Close modal 提交后，state.py 状态变 closed，trade_log.jsonl 有 `event: "close"` 行，含 actual_pnl
4. **AC4**：Roll modal 提交后，state.py roll_count +1，trade_log.jsonl 有 `event: "roll"` 行
5. **AC5**：`/api/trade-log` GET 返回完整 jsonl 记录
6. **AC6**：actual_premium 与 model_premium 差值在 Open modal 中实时显示
7. **AC7**：策略下拉不显示 reduce_wait

---

Status: DONE
