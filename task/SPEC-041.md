# SPEC-041: EOD Signal Snapshot Push (4:03pm ET)

## 目标

**What**：在 Telegram bot 新增每交易日 **4:03pm ET** 的 EOD signal snapshot 推送，使用 4:00pm 收盘数据，捕捉日内信号变化（尤其是 VIX Trend 和 backwardation 状态切换）。

**Why**：
- 现有 9:35am 推送使用 5m intraday VIX override，与收盘 EOD 数据可能不一致
- HIGH_VOL 环境下 VIX Trend（RISING / FLAT / FALLING）日内可能切换，直接决定 `select_strategy()` 是否推荐入场（如 RISING → REDUCE_WAIT，FLAT → BPS_HV）
- SPX 期权收盘 4:15pm ET，4:03pm 推送后仍有 ~12 分钟可操作窗口
- 为明日 9:35am 推送提前校准预期

---

## 功能定义

### F1 — Morning Snapshot 缓存（`notify/telegram_bot.py`）

新增模块变量：

```python
_morning_snapshot: dict | None = None
# 格式: {"strategy_key": str, "position_action": str, "date": str}
```

- `scheduled_push()` 成功推送后，将 `rec.strategy_key / rec.position_action / rec.vix_snapshot.date` 写入 `_morning_snapshot`
- `_reset_intraday_state()` 每日 9:30 ET 同步清除 `_morning_snapshot = None`

---

### F2 — EOD 推送函数（`notify/telegram_bot.py`）

新增 `scheduled_eod_push(bot, chat_id)`：

1. `is_trading_day()` 检查，非交易日直接返回
2. 调用 `get_recommendation(use_intraday=False)` 拿 EOD 收盘信号
3. 读取 `_morning_snapshot` 做信号比对
4. 读取 `read_state()` 获取持仓信息（DTE / days held）
5. 调用 `_format_eod_snapshot()` 生成消息并发送

---

### F3 — EOD 消息格式

```
🌙 EOD Signal Snapshot — 2026-04-07
────────────────────────────────
VIX Close  24.83 [HIGH_VOL]  Trend: FLAT
IVR  62  IVP  58
SPX Trend  NEUTRAL  (+1.2% vs 50MA)
Term struct  contango  (VIX3M 26.40)

Recommendation:  Bull Put Spread (High Vol)
Action:  OPEN
```

**信号变化对比（有 morning snapshot 时）：**

若 strategy_key 或 position_action 不同：
```
⚠️ Signal changed from morning:
  Morning → REDUCE_WAIT  [VIX Trend RISING]
  EOD     → OPEN BPS_HV  [VIX Trend FLAT]
  Re-evaluate before tomorrow's open.
```

若相同：
```
✅ Signal confirmed — same as morning push.
```

若 bot 当天重启（无 morning snapshot）：
```
ℹ️ Morning snapshot unavailable (bot restarted today).
```

**持仓提示（有 open position 时）：**

若 state 有 `expiry` 字段：
```
📋 Open Position: Bull Put Spread (High Vol) | SPX | 21 DTE remaining
```

若无 `expiry`，回退到 days held：
```
📋 Open Position: Bull Put Spread (High Vol) | SPX | opened 5d ago
```

**底部固定行：**
```
────────────────────────────────
SPX options tradeable until 4:15pm ET
```

---

### F4 — Scheduler 注册（`notify/telegram_bot.py`）

在 `post_init()` 新增：

```python
scheduler.add_job(
    scheduled_eod_push,
    CronTrigger(day_of_week="mon-fri", hour=16, minute=3, timezone=ET),
    args=[application.bot, chat_id],
    id="eod_push",
    name="EOD signal snapshot push",
)
```

---

## 接口定义

### `notify/telegram_bot.py`

```python
_morning_snapshot: dict | None = None

async def scheduled_eod_push(bot: Bot, chat_id: str) -> None:
    """4:03pm ET EOD signal snapshot push. No-op on non-trading days."""

def _format_eod_snapshot(
    rec: Recommendation,
    morning: dict | None,
    state: dict | None,
) -> str:
    """Format EOD snapshot message with optional morning comparison and position line."""
```

---

## 边界条件与约束

- `use_intraday=False`：强制走 EOD 收盘数据，不受 5m intraday override 影响
- Morning snapshot 存 RAM，bot 重启会丢失；丢失时仅推 EOD，不报错
- 不新增任何持久化文件（不写 jsonl / state.json）
- 不新增 Telegram command（仅 scheduled push）
- 不修改 `_format_recommendation()`（9:35am 推送格式不变）
- 不修改 `scheduled_push()` 的现有逻辑，只在其成功分支追加写 `_morning_snapshot`

---

## 不在范围内

- 自动执行建议（仅推送，用户手动决策）
- EOD push 与 9:35am push 之间的多次日内 snapshot 记录
- Performance 汇总或 backtest 结果展示
- `/eod` command（按需触发）——留给后续

---

## 修改文件

| 文件 | 改动 |
|------|------|
| `notify/telegram_bot.py` | 新增 `_morning_snapshot` 变量；修改 `scheduled_push()` + `_reset_intraday_state()`；新增 `scheduled_eod_push()` + `_format_eod_snapshot()`；`post_init()` 注册 eod_push job |

---

## 验收标准

1. **AC1**：每个交易日 4:03pm ET 自动发送 EOD snapshot 消息
2. **AC2**：消息包含 VIX close 值、Regime、Trend、Backwardation 状态、最终 Recommendation 和 Action
3. **AC3**：当日有 morning snapshot 且 strategy_key 或 position_action 不同时，显示 `⚠️ Signal changed` 含两侧对比
4. **AC4**：当日有 morning snapshot 且信号相同时，显示 `✅ Signal confirmed`
5. **AC5**：Bot 当天重启导致无 morning snapshot 时，显示 `ℹ️ Morning snapshot unavailable`
6. **AC6**：有 open position 时，消息底部显示策略名 + DTE（优先）或 days held（fallback）
7. **AC7**：非交易日不发送（`is_trading_day()` 检查）
8. **AC8**：EOD push 失败不影响 bot 其他功能；异常仅写 log，不 crash

---

## 依赖

- SPEC-034（strategy state，持仓读取）

---

## Review
- 结论：PASS
- AC1-AC8 全部通过
- 加分：`_morning_snapshot` 额外存储 `vix_trend` 字段，对比消息可展示早晨 Trend 值，超出原 SPEC 要求

Status: DONE
