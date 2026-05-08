# SPEC-086: /ES Short Put Credit Stop Monitor

Status: DONE

## 背景

`SPEC-061` 已实现 `/ES` short put 最小生产单元，并定义了 `-300%` credit stop 规则（即当空头期权 mark 涨至入场 premium 3 倍时，必须平仓止损）。当前系统只有人工盯盘，不满足 PM 的最低运营安全要求：**当 `/ES` short put 有开仓持仓时，必须存在系统告警，不能依赖人工监控 stop 条件**。

本 Spec 的唯一目标是在 Telegram bot 的现有 `intraday_monitor` 里追加 `/ES` credit stop 检查，使其与现有 VIX spike / SPX drop 告警共享同一套每 5 分钟轮询机制。

---

## 目标

当 `/ES` short put 有活跃持仓时：
- **WARNING**：当期权当前市价 ≥ 入场 premium × 2.0，发送警告（-200% credit level）
- **TRIGGER**：当期权当前市价 ≥ 入场 premium × 3.0，发送止损触发告警（-300% credit stop，即 SPEC-061 定义的止损线）

与现有 VIX/SPX 告警共享升级逻辑：同一周期内只在 level 上升时推送，避免重复发送。

---

## 核心原则

- **只读**：不做任何自动平仓 / broker write / 自动下单
- **fail-soft**：若 Schwab 数据不可用（stale / unauthenticated / positions fetch failure），静默跳过，不发送误报
- **最小改动**：仅扩展 `notify/telegram_bot.py`，不改动 `strategy/` 任何逻辑，不改 `SPEC-061` 任何 AC
- **复用已有模式**：`_intraday_state` 扩展 + escalation-only push，与 VIX/SPX 告警行为对称

---

## In Scope

1. 在 `_intraday_state` 中追加 `/ES` credit stop 级别追踪（`NONE / WARNING / TRIGGER`）
2. 在 `intraday_monitor` 中追加 `/ES` credit stop 检查逻辑
3. 新增 `_check_es_credit_stop()` 读取持仓 + 计算当前 mark 倍数
4. 新增 `_format_es_stop_alert()` 格式化 Telegram 推送消息
5. 新增测试覆盖（开仓 / 无仓 / Schwab 不可用三路径）

## Out of Scope

- 自动平仓 / broker write
- 修改 `strategy/selector.py`、`strategy/state.py`、`SPEC-061` 任何逻辑
- 重构现有 VIX/SPX 告警逻辑
- 新增独立监控进程 / 新增 launchd job
- 超过现有 Schwab API 的任何新集成
- 针对 `/ES` 的 MTM P&L 追踪或报告

---

## 功能定义

### 持仓判定

- 有活跃 `/ES` credit stop 需要监控的条件：
  - `current_position.json` 中 `strategy_key == "es_short_put"`（或等价判断）
  - 且 `actual_premium`（或 fallback: `model_premium`）> 0

若不满足，`_check_es_credit_stop()` 直接返回 `NONE`，不调用 Schwab API。

### 当前 mark 获取

- 调用已有 `get_account_positions()`
- 从持仓列表中用 `_is_es_option_position()` 找到 `/ES` PUT 持仓
- 取 `mark` 字段（per-share 期权市价），单位与 `actual_premium` 一致
  - 若 `mark` 字段缺失或 None，则 fail-soft（返回 `NONE`）
  - 若 positions stale / unauthenticated，fail-soft

### 级别判定

```
entry_prem = actual_premium (or model_premium fallback)
ratio      = current_mark / entry_prem

ratio < 2.0   → ES_STOP_NONE
2.0 ≤ ratio < 3.0 → ES_STOP_WARNING
ratio ≥ 3.0   → ES_STOP_TRIGGER
```

### 告警消息

**WARNING (ratio ≥ 2×)：**
```
⚠️ /ES Short Put — Stop Watch [–200%]
Entry premium: 10.50  →  Current mark: 21.20  (×2.02)
Credit stop is at ×3.0 (mark ≥ 31.50).
Monitor closely and prepare to close if mark continues rising.
```

**TRIGGER (ratio ≥ 3×)：**
```
🚨 /ES Short Put — Credit Stop TRIGGERED [–300%]
Entry premium: 10.50  →  Current mark: 32.80  (×3.12)
SPEC-061 credit stop line breached. Consider closing immediately.
/closed after exiting.
```

**Cleared（从 WARNING/TRIGGER 回落到 NONE）：**
```
✅ /ES Short Put — Stop watch cleared
Mark has fallen back below ×2.0 threshold. Current mark: {mark:.2f}
```

### 升级逻辑

- 与 VIX/SPX 一致：同一 session 内只在 level **上升**时推送
- 回落时推送 "cleared" 消息（与现有 VIX/SPX 已有的 cleared 逻辑对称）
- `_reset_intraday_state()` 同时清除 `es_stop_level`

---

## 边界条件

- 若 `current_position.json` 不是 `es_short_put`，本检查完全静默，不影响 SPX 主推荐 bot 行为
- 若 Schwab token 过期或 positions endpoint 失败，fail-soft，不触发告警，不让 `intraday_monitor` 崩溃
- 若 `/ES` PUT 持仓在 Schwab 账户中不可见（例如已平仓但 `current_position.json` 未更新），fail-soft
- `mark` 字段使用 per-share 计价（与 `actual_premium` 单位一致）；若开发者发现单位不一致，需在实现前回报，不得静默换算

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | 当 `/ES` short put 有开仓且 mark ≥ 3× entry premium，bot 发送 TRIGGER 告警 | unit test / mock |
| AC2 | 当 mark 在 2–3× 区间，bot 发送 WARNING；当 mark 继续升过 3×，再发一次 TRIGGER（升级触发）| unit test |
| AC3 | 当没有活跃 `/ES` short put（`strategy_key` 非 `es_short_put`），`_check_es_credit_stop()` 不调用 Schwab，返回 NONE | unit test |
| AC4 | 当 Schwab positions 不可用（stale / unauthenticated / fetch error），`_check_es_credit_stop()` 静默 fail-soft 返回 NONE，不推送任何告警 | unit test |
| AC5 | 当 mark 从 WARNING/TRIGGER 回落到 < 2× entry premium，bot 发送 "cleared" 消息 | unit test |
| AC6 | 现有 VIX/SPX `intraday_monitor` 行为不受影响（regression） | existing tests pass |
| AC7 | `_reset_intraday_state()` 同时清除 es_stop_level，下一个 session 重新检测 | unit test |
| AC8 | 不写入 broker；不修改 `current_position.json`；不调用 Schwab write endpoint | code review |

---

## 实现指导

**建议改动范围（仅 `notify/telegram_bot.py`）：**

1. `_intraday_state` dict 增加 `"es_stop_level": EsStopLevel.NONE`（新建 `EsStopLevel` enum: `NONE / WARNING / TRIGGER`）
2. 新增 `_ES_STOP_RANK = {EsStopLevel.NONE: 0, EsStopLevel.WARNING: 1, EsStopLevel.TRIGGER: 2}`
3. 新增 `_check_es_credit_stop() -> EsStopResult`（读 state + 调 schwab positions + 计算 ratio）
4. 新增 `_format_es_stop_alert(result: EsStopResult) -> str`
5. `intraday_monitor` 末尾追加 es_stop 升级检查（与 VIX/SPX 部分对称）
6. `_reset_intraday_state()` 追加清除 es_stop_level
7. 新增测试 `tests/test_spec_086.py`，mock `schwab.client.get_account_positions` 和 `strategy.state.read_state`

**复用已有模式：**
- `_is_es_option_position()` 直接从 `web.server` import 或等价重实现（避免引入 web 依赖）
- `get_account_positions()` 已有缓存，5 分钟轮询不会产生额外 Schwab API 压力

**注意：**
- `mark` 单位确认：`_extract_quote_greeks` 里 `mark` = `instrument.get("mark") or instrument.get("marketValue")`。`mark` 通常是 per-share；`marketValue` 是 total position value。开发者需在实现前确认 per-share 语义，如不一致，需在 handoff 中说明单位处理。
- 若发现 `_is_es_option_position` 需要从 `web.server` import 会引入不必要耦合，应在 `notify/telegram_bot.py` 内独立实现等价的文本匹配（2 行）。

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-07 | Quant Researcher 起草 SPEC-086：/ES short put credit stop monitor | DRAFT |
| 2026-05-07 | Developer 实施：Telegram intraday monitor 增加 `/ES` short put credit stop WARNING/TRIGGER/cleared 只读告警；新增 fail-soft 观测有效性保护与单元测试 | DONE |

---

## Review — Quant Researcher 2026-05-07

- 结论：PASS
- AC1–AC8 独立核对全部通过，15/15 tests PASS（含 AC6 VIX/SPX regression）
- 设计亮点：`observed` 字段的语义区分是此次实现最关键的设计决策。`observed=False` 对应"无法观测"（Schwab stale/unauthenticated/exception/position not found/mark=None），`observed=True` 只出现在两种情况：(a) 系统状态确认无 /ES 持仓 (b) 成功读取 mark 并计算出 ratio。这使 "cleared" 消息只能由正向确认触发，而不会因 Schwab 数据暂时不可用而误清告警状态。正确的安全监控设计。
- AC4 extra coverage：`test_ac4_unavailable_does_not_send_false_clear_or_reset_state` 显式验证了"Schwab stale + 上一轮已有 WARNING = 不发消息 + 状态保持 WARNING"，这是最重要的 safety invariant，覆盖完整。
- 已知 open item（非阻塞，已在 handoff 中记录）：Schwab `mark` 字段的 per-share 单位尚未通过真实 /ES 持仓验证。实现假设 `mark` 单位与 `actual_premium` 一致（均为 per-share 期权价格）。若单位不一致，ratio 计算会出错。应在首次真实 /ES 持仓期间验证 Schwab positions payload 的 `mark` 字段，并在 `SPEC-086_handoff.md` 补充确认。

## Implementation Review

Result: PASS

- AC1 PASS：`/ES` short put mark >= 3x entry premium 时返回 TRIGGER 并格式化 stop breach 告警。
- AC2 PASS：2x-3x 返回 WARNING，继续升至 3x 后只发送一次升级 TRIGGER。
- AC3 PASS：非 `/ES` short put 状态不调用 Schwab positions，返回 NONE。
- AC4 PASS：Schwab stale / unauthenticated / fetch error 均 fail-soft；若上一轮已有 WARNING/TRIGGER，不误发 cleared，也不清空上一轮状态。
- AC5 PASS：有效 mark 从 WARNING/TRIGGER 回落至 <2x 时发送 cleared。
- AC6 PASS：现有 VIX/SPX Telegram intraday monitor 回归通过。
- AC7 PASS：`_reset_intraday_state()` 同时清除 `es_stop_level`。
- AC8 PASS：实现只读；未写 broker，未修改 `current_position.json`，未调用 Schwab write endpoint。

Validation:

- `arch -arm64 venv/bin/python -m py_compile notify/telegram_bot.py tests/test_spec_086.py`
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_086 tests.test_telegram_bot -v`
