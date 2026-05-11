# SPEC-099 — Telegram Bot SPX Profit-Target Alert Resilience

**Type**：engineering-driven
**Date**：2026-05-11
**Status**：DRAFT
**Owner**：Developer
**Source**：PM 报告 2026-05-11 live BPS 达到 profit target 0.60 但 bot 未推送 close 建议；Quant 诊断为 bot 依赖手动 `/opened` 注册，state.json 未记录真实仓位 → profit-target check silent return False

---

## 0. TL;DR

Bot 当前 SPX profit-target alert 完全依赖 `logs/current_position.json` 的 `status="open"` state，由 PM 手动通过 Telegram `/opened` 命令注册。当 PM 忘记跑 `/opened` 或 state file 留有 stale `status="closed"` 数据时，bot **silent miss**，无法推送 close 建议。本 spec 引入两层 resilience：

- **B**：broker-state reconciliation alert（Schwab 有 SPX option 仓位但 local state 无记录时推 warning）
- **C**：Schwab-direct profit-target check（state.json 缺失或 stale 时，fallback 直接用 Schwab `averagePrice` 计算 capture%）

## 1. Background

### 1.1 当前实现

[notify/telegram_bot.py:360-413](../notify/telegram_bot.py#L360-L413) `_check_spx_profit_target()`：

```python
state = read_state()   # 仅在 state.status == "open" 时返回 dict
if not state or state.get("underlying") != "SPX":
    return False, None  # ← silent miss path
```

`read_state()` 源自 [strategy/state.py:133-142](../strategy/state.py#L133-L142)，硬性 gate `data.get("status") == "open"`。

### 1.2 失败场景（2026-05-11 实例）

- `logs/current_position.json` 残留 2026-04-08 voided test trade（`status: closed`）
- PM 后续开真实 BPS，未跑 `/opened` 命令
- Bot 每小时 `intraday_monitor` 调用 `_check_spx_profit_target()` → `read_state()` 返回 None → silent return
- Live BPS 到达 60% 利润目标，**bot 不推送任何 close 提示**

### 1.3 已知 Schwab 数据可用性

[schwab/client.py:131-163](../schwab/client.py#L131-L163) `get_account_positions()` 已访问 Schwab API `averagePrice` 字段（line 157 用于 `unrealized_pnl` 计算），但未 expose 给上游消费者。

## 2. 实施目标

### 2.1 资源加固层 B — Broker-State Reconciliation Alert

**新增函数** [notify/telegram_bot.py](../notify/telegram_bot.py) `_check_broker_state_mismatch() -> Optional[str]`：

```python
def _check_broker_state_mismatch() -> Optional[str]:
    """
    Return a warning message if Schwab shows SPX option positions but local
    state.json has no matching open record. Returns None when consistent.
    """
    state = read_state()                       # None if no open SPX
    positions_payload = get_account_positions()
    if not positions_payload.get("configured") or not positions_payload.get("authenticated"):
        return None  # broker unavailable → can't reconcile, silent
    if positions_payload.get("stale"):
        return None
    
    spx_options = [
        p for p in positions_payload.get("positions", [])
        if p.get("asset_type") == "OPTION" and "SPX" in (p.get("symbol") or "")
    ]
    if state is None and spx_options:
        # Schwab shows positions, but local has nothing open
        return (
            "⚠️ <b>Broker-State Mismatch</b>\n"
            f"Schwab shows {len(spx_options)} open SPX option leg(s) but "
            f"local state has no open position recorded.\n"
            f"<i>Run /opened to register, or /sync to auto-import (after SPEC-099).</i>"
        )
    return None
```

在 [intraday_monitor()](../notify/telegram_bot.py#L580+) 中调用，与现有 profit-target check 并列。

**Dedup**：每个交易日只推一次（用 `_intraday_state` 加 `mismatch_alerted` flag，类似 `profit_alerted`）。

### 2.2 资源加固层 C — Schwab-Direct Profit-Target Check

**修订** [notify/telegram_bot.py](../notify/telegram_bot.py) `_check_spx_profit_target()`：保留现有路径（state.json 优先），新增 fallback：

```python
def _check_spx_profit_target() -> tuple[bool, float | None]:
    state = read_state()
    if state and state.get("underlying") == "SPX":
        entry_premium = _num(state.get("actual_premium")) or _num(state.get("model_premium"))
        opened_at = state.get("opened_at")
        if entry_premium and entry_premium > 0:
            # Existing path: use state.json data
            return _profit_check_from_state(state, entry_premium, opened_at)

    # FALLBACK: state.json missing or stale, try Schwab-direct
    return _profit_check_from_schwab()


def _profit_check_from_schwab() -> tuple[bool, float | None]:
    """
    Compute capture% directly from Schwab averagePrice + marketValue for an
    open SPX vertical credit spread (2-leg structure detection).
    """
    positions_payload = get_account_positions()
    if not positions_payload.get("configured") or not positions_payload.get("authenticated"):
        return False, None
    if positions_payload.get("stale"):
        return False, None
    
    legs = _identify_spx_spread_legs(positions_payload.get("positions", []))
    if legs is None:
        return False, None
    short_leg, long_leg = legs
    
    # Net entry credit per share = abs(short_avg_price) - abs(long_avg_price)
    # (Schwab returns averagePrice signed by buy/sell direction)
    entry_credit_ps = abs(short_leg["average_price"]) - abs(long_leg["average_price"])
    if entry_credit_ps <= 0:
        return False, None  # not a credit spread
    
    contracts = abs(short_leg["quantity"])
    # Net market_value: short + long combined (both signed appropriately)
    net_mv = (short_leg["market_value"] or 0) + (long_leg["market_value"] or 0)
    close_cost_ps = abs(net_mv) / contracts / 100
    captured_pct = (entry_credit_ps - close_cost_ps) / entry_credit_ps * 100
    
    PROFIT_TARGET_PCT = 60.0
    # Days held: derive from Schwab transaction history OR skip min_hold gate when state.json missing
    # Conservative: skip min_hold gate when fallback path (PM should /opened next time)
    reached = captured_pct >= PROFIT_TARGET_PCT
    return reached, round(captured_pct, 1)


def _identify_spx_spread_legs(positions: list[dict]) -> Optional[tuple[dict, dict]]:
    """Pair short and long SPX option legs into a vertical spread, or None."""
    spx_opts = [
        p for p in positions
        if p.get("asset_type") == "OPTION" and "SPX" in (p.get("symbol") or "")
    ]
    if len(spx_opts) != 2:
        return None  # not a single vertical spread
    short = next((p for p in spx_opts if (p.get("quantity") or 0) < 0), None)
    long_ = next((p for p in spx_opts if (p.get("quantity") or 0) > 0), None)
    if short is None or long_ is None:
        return None
    return short, long_
```

### 2.3 Schwab Client Expose averagePrice

**修订** [schwab/client.py:151-158](../schwab/client.py#L151) `parsed` dict：

```python
parsed = {
    "symbol": instr.get("symbol"),
    "description": instr.get("description"),
    "asset_type": instr.get("assetType"),
    "quantity": pos.get("longQuantity", 0) - pos.get("shortQuantity", 0),
    "market_value": pos.get("marketValue"),
    "average_price": pos.get("averagePrice"),  # NEW
    "unrealized_pnl": pos.get("marketValue", 0) - pos.get("averagePrice", 0) * abs(pos.get("longQuantity", 0) - pos.get("shortQuantity", 0)),
}
```

### 2.4 Fallback 路径的语义放宽

`_profit_check_from_schwab()` 在 fallback 模式下放宽两条规则：
- **min_hold_days gate 跳过**：因 fallback 模式下没有 `opened_at` ground truth（state.json 缺失），用 Schwab transaction history 计算 days_held 复杂度高；MVP 阶段直接跳过 10-day gate
- **Alert 前缀加标记**：fallback 路径触发的 profit target alert 前缀加 `⚠️ via Schwab fallback`，提醒 PM 数据源不是 local state.json

### 2.5 Alert 输出修订

`intraday_monitor()` 调度顺序：
1. 先 `_check_broker_state_mismatch()` → 若 mismatch 推 warning（dedup 内）
2. 再 `_check_spx_profit_target()` → 现有 alert flow，含 fallback 路径
3. fallback 路径的 alert message 加前缀 `⚠️ via Schwab fallback`

---

## 3. Acceptance Criteria

| AC# | 描述 | Verification |
|---|---|---|
| AC-099-1 | `schwab/client.py:get_account_positions` 返回 dict 含 `average_price` 字段 | curl `/api/positions` 检查 payload |
| AC-099-2 | `_check_broker_state_mismatch` 在 Schwab 有 SPX option 仓位 + state.json 无 open 记录时返回 warning 字符串 | unit test with mock Schwab + empty state |
| AC-099-3 | `_check_broker_state_mismatch` 在两边都没仓位时返回 None | unit test |
| AC-099-4 | `_check_broker_state_mismatch` 在两边都有仓位时返回 None（consistent） | unit test |
| AC-099-5 | `_identify_spx_spread_legs` 对 2 leg vertical spread 返回 (short, long) tuple | unit test |
| AC-099-6 | `_identify_spx_spread_legs` 对 0/1/3+ legs 或不含短腿/长腿 的 case 返回 None | unit test |
| AC-099-7 | `_profit_check_from_schwab` 计算 capture% 正确（manual test case：entry credit $5, close cost $2 → captured 60%） | unit test with mock payload |
| AC-099-8 | `_check_spx_profit_target` 在 state.json `status=open` 时走原 path（不变） | unit test |
| AC-099-9 | `_check_spx_profit_target` 在 state.json 无 open 但 Schwab 有 vertical spread 时走 fallback path，能正确返回 (reached, captured%) | unit test |
| AC-099-10 | 推 alert 时 fallback 路径加 `⚠️ via Schwab fallback` 前缀 | integration test with mock Schwab |
| AC-099-11 | `mismatch_alerted` dedup flag 每交易日只推一次 mismatch warning | integration test, 同日多次调用 |
| AC-099-12 | `profit_alerted` dedup flag 兼容 fallback path（不重复推） | integration test |

---

## 4. Out of Scope

- **Auto-write state.json from Schwab fills**：本 spec 仅 fallback 时 silent 用 Schwab 数据；不修改 state.json。PM 仍需 /opened 来切回 primary path
- **Multi-account aggregation**：本 spec 仅处理 Schwab 主账户；ETrade 端 fallback 留给未来 spec
- **`/sync` 命令实现**：mismatch alert 文案 mention 但本 spec 不交付 `/sync`，留给 SPEC-100
- **3+ leg spread support**：本 spec 仅处理 2-leg vertical spread（BPS / BCS），4-leg iron condor 留给未来 spec
- **`days_held` gate restore in fallback**：MVP 跳过 min_hold，未来通过 Schwab transaction history 恢复

---

## 5. Risk + Caveats

| Risk | Mitigation |
|---|---|
| Schwab averagePrice 符号约定不确定（buy 正 / sell 负 OR 都正） | Developer 实施时打 log，对 1 笔已知 spread 数据验证；必要时绝对值 + 短腿/长腿区分 |
| 2-leg detection 误识（PM 同时有 BPS + BCS） | `_identify_spx_spread_legs` 返回 None；fallback 不 fire；mismatch alert 仍会 fire 提示 PM 手动 /opened |
| Fallback path silent miss min_hold gate（容忍极早期 60% capture） | MVP 接受；现实中 60% capture 几乎不可能在 day 1-5 发生 |
| Schwab API stale data | 已 guard：`positions_payload.get("stale")` 直接 return False |
| Test coverage | 12 ACs 中 11 个有 unit/integration test，1 个（AC-099-1）curl 验证 |

---

## 6. RESEARCH_LOG 不写入

本 spec 为 engineering-driven，无 research finding。Spec 状态变更直接进 PROJECT_STATUS.md，不进 RESEARCH_LOG。

---

## 7. Deployment

- Local test PASS 后 commit + push
- Old Air pull + restart `com.spxstrat.telegram_bot` launchd 任务
- Smoke verify：手动触发 intraday_monitor，confirm mismatch alert fire（state.json 当前 status=closed + Schwab 有 PM 现有 SPX BPS 仓位 → 触发）

PM 后续可在 confirm fallback path 正常 fire 后，**安全清理 logs/current_position.json**（删除 stale voided record）。
