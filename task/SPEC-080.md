# SPEC-080: BCD Debit Stop Tightening (`bcd_stop_tightening_mode`)

Status: DONE (2026-05-02; F1-F5 全部交付 + AC1-AC9 PASS)

## 目标

**What**：将 Bull Call Diagonal (BCD) 的 debit stop loss 从硬编码 `-0.50`（最大亏损 50%）收紧到 `-0.35`，并通过 `bcd_stop_tightening_mode` toggle 控制；同时修复 SPEC-077 中 documented 的 `backtest/engine.py` debit-side 硬编码（line ~917），使 BCD stop 可由 StrategyParams 驱动。

**Why**：
- Q038 Phase 2C：11-config stop sweep 显示 `-0.35` 是真正的 plateau 中心（ann ROE 13.59% vs -0.50 的 13.23%，Sharpe 1.407 vs 1.355）
- `-0.30` 是次优（V5 的配置）；ChatGPT 3rd Quant Review §4 明确要求 sweep 后采用 `-0.35`
- 当前 engine.py 对所有 debit 策略统一硬编 `-0.50`，无法区分 BCD 与其他 debit 策略
- MC `SPEC-080 DONE`（2026-04-29）；HC 需复现
- SPEC-077 변경 record 已显式标注"debit-side 硬编码 line 882 待 SPEC-080 处理"；本 spec 是该修复的正式落地
- 与 `SPEC-079` 共同构成 PM 选定的 **Path C**，toggle 独立可切

---

## 核心原则

- **toggle 默认 `disabled`**：与 SPEC-079 相同，PM 决定 shadow flip 时机
- **只改 BCD**：其他 debit 策略（未来可能有 BCS 等）继续沿用 `-0.50`，不受此 spec 影响
- **不改 credit-side stop**：credit 侧已正确使用 `params.stop_mult`（engine.py 已 wired，SPEC-077 锁定）；本 spec 只处理 debit 侧
- **stop 值 `-0.35` 来自 Q038 研究，不允许 post-hoc 调整**
- **shadow log**：engine 在 shadow 模式下应记录每次"如果 active 则会触发 stop"的事件

---

## 功能定义

### F1 — `StrategyParams` 增加 `bcd_stop_tightening_mode`

**[strategy/selector.py](strategy/selector.py)** StrategyParams dataclass：

```python
# BCD debit stop tightening (SPEC-080)
bcd_stop_tightening_mode: str = "disabled"   # "disabled" | "shadow" | "active"
```

### F2 — 新文件 `strategy/bcd_stop.py`

```python
"""BCD debit stop tightening (SPEC-080).

当 bcd_stop_tightening_mode == "active" 时，BCD debit stop loss 从 -0.50 收紧到 -0.35。
"""
from __future__ import annotations
import json
from pathlib import Path

BCD_STOP_DEFAULT  = -0.50   # legacy hardcoded value; non-BCD debit strategies
BCD_STOP_TIGHTER  = -0.35   # Q038 Phase 2C plateau; BCD when mode=active

_ENGINE_LOG = Path("data/bcd_stop_shadow_engine.jsonl")
_LIVE_LOG   = Path("data/bcd_stop_shadow_live.jsonl")


def bcd_debit_stop(mode: str) -> float:
    """Return the effective BCD debit stop ratio for the current mode."""
    if mode == "active":
        return BCD_STOP_TIGHTER
    return BCD_STOP_DEFAULT


def log_bcd_stop_event(
    date: str,
    pnl_ratio: float,
    mode: str,
    source: str = "engine",   # "engine" | "live"
) -> None:
    """Log a would-be BCD stop trigger event (shadow and active modes)."""
    path = _LIVE_LOG if source == "live" else _ENGINE_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "date": date, "pnl_ratio": round(pnl_ratio, 4),
            "mode": mode, "source": source,
            "stop_active": BCD_STOP_TIGHTER,
            "stop_legacy": BCD_STOP_DEFAULT,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass
```

### F3 — `backtest/engine.py` debit stop 修改

**当前（硬编码，line ~917）**：
```python
elif not is_credit and pnl_ratio <= -0.50:           # debit trade stop at 50% loss
    exit_reason = "stop_loss"
```

**修改后**：
```python
elif not is_credit:
    from strategy.selector import StrategyName
    from strategy.bcd_stop import bcd_debit_stop, log_bcd_stop_event, BCD_STOP_TIGHTER, BCD_STOP_DEFAULT
    is_bcd = (position.strategy == StrategyName.BULL_CALL_DIAGONAL)
    if is_bcd and params.bcd_stop_tightening_mode != "disabled":
        effective_stop = bcd_debit_stop(params.bcd_stop_tightening_mode)
        # shadow: log if -0.35 would trigger but -0.50 has not
        if params.bcd_stop_tightening_mode == "shadow":
            if BCD_STOP_TIGHTER >= pnl_ratio > BCD_STOP_DEFAULT:
                log_bcd_stop_event(position.entry_date, pnl_ratio, "shadow", "engine")
        if pnl_ratio <= effective_stop:
            exit_reason = "stop_loss"
    elif pnl_ratio <= -0.50:
        exit_reason = "stop_loss"
```

**注意**：import 放在函数内部是为了避免循环引用风险；如果项目无此风险，可提升到文件顶部。

### F4 — 生产 config 确认默认 `disabled`

**[web/server.py](web/server.py)** — 确认任何 production_config 里 `bcd_stop_tightening_mode` 未被显式 override 为非 `"disabled"` 值。

### F5 — Unit test `tests/test_bcd_stop.py`

至少包含：
1. `test_disabled_returns_legacy_stop()` — mode="disabled" → stop=-0.50
2. `test_active_returns_tighter_stop()` — mode="active" → stop=-0.35
3. `test_shadow_returns_legacy_stop()` — mode="shadow" → stop=-0.50（不改行为）
4. `test_engine_bcd_stop_triggers_at_035_when_active()` — 构造 BCD position，pnl_ratio=-0.36，mode="active" → exit_reason="stop_loss"
5. `test_engine_bcd_stop_does_not_trigger_at_040_when_disabled()` — pnl_ratio=-0.40，mode="disabled" → no stop yet（-0.40 > -0.50）
6. `test_engine_non_bcd_debit_unaffected()` — 非 BCD debit position，mode="active" → still uses -0.50
7. `test_shadow_log_written_when_in_shadow_zone()` — pnl_ratio=-0.38（在 -0.35 ~ -0.50 之间），mode="shadow" → log entry written

---

## In Scope

| 项目 | 说明 |
|---|---|
| F1 StrategyParams | bcd_stop_tightening_mode 字段 |
| F2 bcd_stop.py | stop 计算 + shadow log |
| F3 engine.py 修改 | 替换 debit-side 硬编码 |
| F4 生产 config 确认 | 确保 disabled |
| F5 unit test | 7 cases |

## Out of Scope

| 项目 | 理由 |
|---|---|
| stop=-0.35 值调整 | Q038 locked |
| 非 BCD debit 策略的 stop 改动 | 本 spec 只改 BCD |
| credit-side stop | 已由 SPEC-077 wired，不动 |
| live 端 debit stop 修改 | log 基础设施落地，live wiring 由 follow-up spec 处理 |

---

## 边界条件

- `bcd_stop_tightening_mode = "shadow"` 时 engine 行为与 `"disabled"` 相同（不改 trade outcome）；仅在 pnl_ratio 落入 `[-0.50, -0.35)` 区间时写 shadow log
- log 写入失败应静默忽略，不影响 backtest 主路径
- 其他 debit 策略（非 BCD）不受影响，继续硬编 `-0.50`（直到有单独 spec 处理）

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `StrategyParams.bcd_stop_tightening_mode` 默认 `"disabled"` | grep |
| AC2 | `strategy/bcd_stop.py` 存在，`bcd_debit_stop` 可导入 | import |
| AC3 | mode="active" BCD pnl_ratio=-0.36 → stop_loss 触发 | test case 4 |
| AC4 | mode="disabled" BCD pnl_ratio=-0.40 → 不触发 | test case 5 |
| AC5 | mode="active" 非 BCD debit pnl_ratio=-0.36 → 不触发 | test case 6 |
| AC6 | engine.py debit-side 不再有裸露的 `<= -0.50` 硬编（BCD 分支已参数化） | grep |
| AC7 | `tests/test_bcd_stop.py` 所有 case PASS | pytest |
| AC8 | SPEC-077 `tests/test_engine_stop_wiring.py` 仍 PASS（无回归） | pytest |
| AC9 | 现有 test suite 无回归 | pytest tests/ |

---

## 与 SPEC-077 的关系

SPEC-077 변경 record（2026-05-02 entry）已记录：
> "debit 侧 line 882 硬编码 `-0.50` 替换 → SPEC-080 BCD 范围"

本 spec 是该项的正式落地。SPEC-077 的 AC3 全样本 magnitude gap（HC +0.086pp vs MC +0.91~1.03pp）中 "cause (b) debit-side stop hardcoding" 分项，将在本 spec 落地后通过 tieout #3 来重新评估。

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-02 | HC Quant 起草；基于 MC_Handoff_2026-05-01_v5.md + Q038 Phase 2C F-26-04-29-3 | DRAFT |
| 2026-05-02 | PM 审批 → APPROVED；进入实施 | APPROVED |
| 2026-05-02 | F1-F5 全部落地（Codex 实施）：`StrategyParams.bcd_stop_tightening_mode="disabled"` 加入 `selector.py:129`；`strategy/bcd_stop.py` 新建（`BCD_STOP_DEFAULT=-0.50` / `BCD_STOP_TIGHTER=-0.35`）；`engine.py:921-933` debit stop 参数化（BCD active → -0.35，BCD disabled/shadow + 非 BCD → -0.50）；shadow log 写 `data/bcd_stop_shadow_engine.jsonl`；`tests/test_bcd_stop.py` 7/7 PASS；`tests/test_engine_stop_wiring.py` PASS（无回归）。同样确认 3 条 pre-existing Gate 1 失败非本 spec 引入。SPEC-077 debit-side 硬编码 documented defect 正式闭合 | DONE |
