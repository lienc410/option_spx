# SPEC-036: Trade Log Corrections & Void Workflow

## 目标

**What**：在 append-only trade log 基础上，新增两种事件类型：
- `correction`：修正已有记录的字段（premium、contracts、strike、expiry、reason、note 等）
- `void`：作废一笔误录交易（点错开仓、重复录入）

**Why**：
- 手动录入难免出错，需要可靠的纠错机制
- 直接编辑 / 删除 jsonl 行破坏审计链，且可能使 state.py 与 log 不一致
- Append-only 模式下的 correction / void 是标准做法，便于未来与 Schwab 对账（broker reconciliation）

**核心原则**：
- 从不修改或删除已写入的行
- correction / void 均为新增行，与原始记录共享同一 `id`
- 读取时通过 `resolve_log()` 函数将原始行 + correction 合并后返回

---

## 事件 Schema

### correction 事件

```json
{
  "id":         "2026-04-05_bps_001",
  "event":      "correction",
  "timestamp":  "2026-04-06T09:15:00-04:00",
  "target_event": "open",
  "fields": {
    "actual_premium": 3.10,
    "contracts": 3
  },
  "reason": "mistyped premium at entry"
}
```

**字段说明**：
- `target_event`：被修正的原始事件类型（"open" / "close" / "roll"）
- `fields`：只包含需要修正的字段（patch style，不需要填写全部字段）
- `reason`：必填，说明为什么修正

**可修正的字段范围**：

| target_event | 可修正字段 |
|-------------|----------|
| open | actual_premium, model_premium, contracts, short_strike, long_strike, expiry, dte_at_entry, entry_spx, entry_vix, note |
| close | exit_premium, exit_spx, exit_reason, actual_pnl, note |
| roll | new_expiry, new_short_strike, new_long_strike, roll_credit, note |

**不可修正的字段**：`id`, `event`, `timestamp`, `strategy_key`, `strategy`（这些是交易身份标识，不能改）

---

### void 事件

```json
{
  "id":         "2026-04-05_bps_002",
  "event":      "void",
  "timestamp":  "2026-04-05T10:45:00-04:00",
  "reason":     "duplicate entry, correct trade is 2026-04-05_bps_001"
}
```

**void 的语义**：
- 整笔交易（该 `id` 的所有事件）被标记为作废
- void 后该 trade_id 不再计入 performance 统计
- 若被 void 的交易当前为 open 状态，state.py 中的持仓同时被清除

---

## 功能定义

### F1 — `resolve_log()` 函数（trade_log_io.py）

新增函数，按以下逻辑处理原始 log：

```
1. 按 trade_id 分组所有事件
2. 对每个 trade_id：
   a. 若存在 void 事件 → 整组标记为 voided=True
   b. 对非 void 的交易，按 target_event 将 correction 的 fields
      合并（patch）到对应的原始事件上
3. 返回已解析的交易列表，每笔交易包含：
   - resolved_events: 合并后的各事件（open/close/roll 各取最新 patch）
   - voided: bool
   - corrections: correction 事件原始列表（供审计查看）
```

**同时保留** `load_log()` 返回原始未处理行（供调试和审计使用）。

**`/api/trade-log` 默认返回 `resolve_log()` 结果**（用于前端展示和 performance 计算），`/api/trade-log?raw=1` 返回原始行。

---

### F2 — 后端 endpoints

```
POST /api/position/correction
POST /api/position/void
```

**`POST /api/position/correction`**

Request body：
```json
{
  "trade_id":     "2026-04-05_bps_001",
  "target_event": "open",
  "fields": {
    "actual_premium": 3.10,
    "contracts": 3
  },
  "reason": "mistyped premium at entry"
}
```

处理逻辑：
1. 验证 `trade_id` 存在于 log 中
2. 验证 `target_event` 为 open / close / roll 之一
3. 验证 `fields` 中不包含禁止修正的字段
4. append correction 事件到 trade_log.jsonl
5. **若 target_event == "open" 且 trade_id 对应当前开仓**：
   同步更新 state.py 中对应字段（actual_premium / contracts / short_strike / long_strike / expiry）
6. **若 target_event == "close" 且修正了 exit_premium / contracts**：
   重新计算 actual_pnl 并更新 correction fields 中的 actual_pnl

Response：`{ "ok": true }`

---

**`POST /api/position/void`**

Request body：
```json
{
  "trade_id": "2026-04-05_bps_002",
  "reason":   "duplicate entry"
}
```

处理逻辑：
1. 验证 `trade_id` 存在
2. 确认 reason 非空（强制要求说明作废原因）
3. append void 事件到 trade_log.jsonl
4. **若该 trade_id 对应当前 state.py 的开仓**：
   调用 `close_position(note=f"voided: {reason}")`，清除持仓状态
5. 返回是否同时清除了 state

Response：`{ "ok": true, "state_cleared": true/false }`

---

### F3 — 前端 — Dashboard Position Panel

**当前开仓的 correction**（在 Position Panel 上操作）：

现有操作行 `[Close] [Roll] [Add Note]` 后新增：
```
[Close] [Roll] [Add Note] [Correct] [Void]
```

**Correct 按钮 → Correction Modal**：

Modal 显示当前持仓的可修正字段，预填当前值，用户只改需要改的部分：
- Actual Premium（当前值预填）
- Contracts（当前值预填）
- Short Strike / Long Strike（当前值预填）
- Expiry（当前值预填）
- Reason（必填文本）

提交时调用 `POST /api/position/correction`（target_event = "open"）。

**Void 按钮 → Void Confirmation Modal**：

```
⚠ Void this position?
This will mark the entire trade as void and clear the open position.
This cannot be undone.

Reason: [__________] (required)

[Cancel]  [Void Trade]
```

提交时调用 `POST /api/position/void`。

---

### F4 — correction 对 actual_pnl 的自动重算

当 correction 修正了 open 事件的 `actual_premium` 或 `contracts`，
且同一 trade_id 已有 close 事件时：

`POST /api/position/correction` 自动追加一条 close 的 correction：
```json
{
  "id":           "2026-04-05_bps_001",
  "event":        "correction",
  "target_event": "close",
  "fields": { "actual_pnl": <重新计算值> },
  "reason":       "auto-recalculated from open correction"
}
```

这保证 resolve_log() 返回的 actual_pnl 始终与 actual_premium / exit_premium / contracts 一致。

---

## 接口定义

### trade_log_io.py 新增函数

```python
def resolve_log() -> list[dict]:
    """
    返回已解析的交易列表。每笔交易：
    {
      "id":        str,
      "voided":    bool,
      "open":      dict | None,   # 合并 correction 后的 open 事件
      "close":     dict | None,   # 合并 correction 后的 close 事件
      "rolls":     list[dict],    # 合并 correction 后的 roll 事件列表
      "notes":     list[dict],
      "corrections": list[dict],  # 原始 correction 行（审计用）
    }
    """
```

### /api/trade-log 响应变化

```json
{
  "trades": [ ...resolve_log() 结果... ],
  "raw_count": 12
}
```

加 `?raw=1` 返回原始行：
```json
{ "raw": [ ...load_log() 结果... ] }
```

---

## 边界条件与约束

- void 后的 trade_id 不可再作为新 correction 的目标（返回 400）
- correction 的 `fields` 不可为空 dict（返回 400）
- 同一 target_event 可以有多个 correction（多次修正），resolve 时按 timestamp 顺序依次 patch
- correction 不能修正 void 事件本身（void 是最终状态）
- `actual_pnl` 自动重算仅在 open correction 修正了 premium / contracts 时触发，
  若用户直接提交 close correction 修正 actual_pnl，以用户值为准（不自动覆盖）
- void 一笔已 closed 的历史交易：仅追加 void 事件，不改变 state.py（已无持仓）
- 不改动 engine.py、backtest 层、signals 层

---

## 不在范围内

- Bulk correction（批量修正多笔交易）
- correction 的 undo（撤销 correction）——需要时可以再 correction 回去
- 前端 trade log 历史列表（Performance Tracking 页面，留给未来 SPEC）
- Correction 对 roll 事件 strike/expiry 的自动 state 同步（roll 的 state 更新逻辑较复杂，暂不覆盖）

---

## Review

- 结论：PASS
- AC1–AC9 全部通过代码核查与回归测试
- `resolve_log()`：按 timestamp 排序后正确 patch open / close / roll；roll 默认 patch 最近一条，符合 PM 确认假设
- `update_open_position()`：仅更新字段值，不重置 `opened_at` / `status`，身份字段安全
- `/api/position/correction`：禁止字段过滤 (`_CORRECTABLE_FIELDS`)、voided trade 拦截、auto-recalc 逻辑正确；公式 `(actual_premium − exit_premium) × contracts × 100` 验证：(3.05−1.55)×2×100 = $300 ✓
- `/api/position/void`：void 后 state 清除（`close_position(note="voided:…")`），重复 void 返回 400 ✓
- `/api/trade-log`：`?raw=1` 返回原始行，默认返回 `{trades, raw_count}` resolved 结构 ✓
- 前端 Correction modal 预填当前值 + Void modal 含确认文案 + 强制 reason 输入 ✓

---

## 验收标准

1. **AC1**：`POST /api/position/correction` 成功后，trade_log 新增 correction 行，state.py 相应字段更新
2. **AC2**：`POST /api/position/void` 成功后，trade_log 新增 void 行；若为当前开仓则 state.py 被清除
3. **AC3**：`resolve_log()` 对 correction 正确 patch：修正后的字段值覆盖原始值，原始行不变
4. **AC4**：`resolve_log()` 对 void 正确标记：voided trade 的 `voided=True`
5. **AC5**：`/api/trade-log` 默认返回 resolved 结果；`?raw=1` 返回原始行
6. **AC6**：open correction 修正 actual_premium 且已有 close 事件时，自动追加 actual_pnl 重算
7. **AC7**：Dashboard Position Panel 新增 `[Correct]` 和 `[Void]` 按钮，各有对应 modal
8. **AC8**：Void modal 有确认文案 + 强制 reason 输入，防止误操作
9. **AC9**：void 已 void 的 trade_id 返回 400；correction 不可修正 id / event / strategy 字段

---

Status: DONE
