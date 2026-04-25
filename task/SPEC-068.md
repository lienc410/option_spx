# SPEC-068: HV Spell Throttle → Per-Strategy Dict

Status: APPROVED

## 目标

**What**：将 `hv_spell_trade_count` 从单一 scalar 改为 per-strategy dict，使每个 HV 策略（IC_HV / BPS_HV / BCS_HV）独立计数 spell budget。

**Why**：
- 当前 HC 实现：`hv_spell_trade_count: int = 0`（[backtest/engine.py:670](backtest/engine.py#L670)），所有 HV 策略共享一个 spell budget
- 当 SPEC-066 允许 IC_HV 在同一 spell 中开 2 笔（cap=2），第二笔会让 aggregate count 达到 `max_trades_per_spell` 上限，错误阻挡其他 HV 策略（BPS_HV / BCS_HV）入场
- MC 在 2026-03 双峰场景下复现到该 bug；HC 当前 trade set 中虽未 trigger（参见 `doc/hc_vs_mc_v3_semantic_audit.md` §2），但 D2 PM 决策为 (a) 防御性复现以避免未来 spell budget 溢出
- per-strategy 计数是直接对齐 SPEC-066 cap=2 多槽位逻辑的最小修补

---

## 核心原则

- **per-strategy 独立 budget**：IC_HV / BPS_HV / BCS_HV 各自有独立 `max_trades_per_spell` 配额
- **`max_trades_per_spell` 参数语义不变**：每策略上限保持原值；只是从 aggregate 改为 per-strategy
- **spell start / spell end 逻辑不变**：进入 HIGH_VOL 时启动 spell，退出 HIGH_VOL（或进入 EXTREME_VOL）时清零
- **接受非零回归（仅 cascade）**：spell budget 释放可能让一些 HV 策略入场日期前移；trade count 的总数与 entry_date 集合需说明差异
- **不破坏现有调用契约**：`_block_hv_spell_entry` / `_update_hv_spell_state` 函数签名变更需要在所有 callsite 同步更新

---

## 功能定义

### F1 — 状态字段类型变更

**[backtest/engine.py:670](backtest/engine.py#L670) 与 [backtest/engine.py:1100](backtest/engine.py#L1100)**：

当前：
```python
hv_spell_trade_count = 0
```

修改后：
```python
hv_spell_trade_count: dict[str, int] = {}
```

`key` 用 `catalog_key(rec.strategy.value)` 即 `"iron_condor_hv"` / `"bull_put_spread_hv"` / `"bear_call_spread_hv"`，与 `HIGH_VOL_STRATEGY_KEYS` 集合对齐。

### F2 — `_update_hv_spell_state` 签名 / 行为更新

**[backtest/engine.py:465-478](backtest/engine.py#L465-L478)**：

当前签名：
```python
def _update_hv_spell_state(
    regime, vix, date, hv_spell_start, hv_spell_trade_count: int, extreme_vix,
) -> tuple[Optional[pd.Timestamp], int]:
```

新签名：
```python
def _update_hv_spell_state(
    regime, vix, date, hv_spell_start, hv_spell_trade_count: dict[str, int], extreme_vix,
) -> tuple[Optional[pd.Timestamp], dict[str, int]]:
```

行为：
- 进入 HV spell（HIGH_VOL 且 vix < extreme_vix）：保留现有 dict，`hv_spell_start` 设为当日（如未设）
- 离开 HV spell：返回 `(None, {})`（清零所有 strategy 的 budget）

### F3 — `_block_hv_spell_entry` 检查 per-strategy

**[backtest/engine.py:481-499](backtest/engine.py#L481-L499)**：

当前 line 497：
```python
if hv_spell_trade_count >= params.max_trades_per_spell:
    return True
```

修改后：
```python
if hv_spell_trade_count.get(new_key, 0) >= params.max_trades_per_spell:
    return True
```

`new_key` 即 `catalog_key(rec.strategy.value)`，与 dict 的 key 一致。

### F4 — 入场后 increment

**[backtest/engine.py:998](backtest/engine.py#L998)**：

当前：
```python
if rec_key in HIGH_VOL_STRATEGY_KEYS:
    hv_spell_trade_count += 1
```

修改后：
```python
if rec_key in HIGH_VOL_STRATEGY_KEYS:
    hv_spell_trade_count[rec_key] = hv_spell_trade_count.get(rec_key, 0) + 1
```

### F5 — `signal_history` 输出（可选）

`signal_history` 中 `hv_spell_age` 字段保留；若需 per-strategy budget 可视化，可添加新字段 `hv_spell_budget_used`（key=strategy, value=count）。本 SPEC 不强制；若 SPEC-072 dual-scale display 需要再追加。

---

## In Scope

| 项目 | 说明 |
|---|---|
| `hv_spell_trade_count` 类型从 `int` → `dict[str, int]` | engine.py 全部 callsite 同步更新 |
| `_update_hv_spell_state` 签名 + 行为更新 | 退出 spell 返回空 dict |
| `_block_hv_spell_entry` per-strategy 检查 | 用 `new_key` 作为 dict 索引 |
| 入场 increment 改 dict | engine.py:998 |
| 第二份 `run_backtest` 入口（line ~1100）的初始化同步更新 | 同样初始化为 `{}` |

## Out of Scope

| 项目 | 理由 |
|---|---|
| 改变 `max_trades_per_spell` 数值 | 数值由 StrategyParams 决定；本 SPEC 不调参 |
| 新增 `hv_spell_budget_used` signal_history 字段 | 留待 SPEC-072 决定 |
| 改变 spell start / end 触发条件 | 未变；仅类型变更 |
| 引入 per-strategy `max_trades_per_spell` 上限差异化 | 未变；所有 HV 策略共用同一上限值 |
| EXTREME_VOL 进入逻辑变化 | 与本 SPEC 无关 |

---

## 边界条件与约束

- **spell 内多策略并发**：HC 当前 trade set 显示 spell 内通常只一种 HV 策略入场（per audit doc §2），因此 per-strategy 改造不会改变 HC 历史 trade set；但 SPEC-066 cap=2 + per-strategy throttle 联合上线后，理论上一个 spell 内可同时开 2 笔 IC_HV + 1 笔 BPS_HV + 1 笔 BCS_HV
- **退出 spell 清零语义**：退出 HV regime 即清零所有 strategy 的 budget；这与 scalar 实现一致
- **回归预期方向**：HC 历史回测中（2023-2026）若无 IC_HV cap=2 双槽位时 BPS_HV / BCS_HV 被错误阻挡的样本，本 SPEC 应产生 0 net trade count change
- **SPEC-066 已提交**，本 SPEC 是其防御性补足；二者无功能冲突

---

## 数据契约

| 字段 | 来源 | 说明 |
|---|---|---|
| `hv_spell_trade_count` | engine.py 局部状态 | 类型由 `int` 改为 `dict[str, int]` |
| `signal_history.hv_spell_age` | engine.py:807 | 保持原义 |
| `doc/baseline_post_spec068/` | F3 之后由 Quant 生成 | 与 `doc/baseline_post_spec070/` 比对 |

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `backtest/engine.py` 中 `hv_spell_trade_count` 所有出现点类型为 `dict[str, int]`（不是 int）| 代码审查 + grep |
| AC2 | `_update_hv_spell_state` 函数签名第 5 / 返回类型为 `dict[str, int]` | 代码审查 |
| AC3 | `_block_hv_spell_entry` 第 497 行使用 `hv_spell_trade_count.get(new_key, 0)` | 代码审查 |
| AC4 | 入场 increment 是 `hv_spell_trade_count[rec_key] = ... + 1` | 代码审查 |
| AC5 | `arch -arm64 venv/bin/python -m py_compile backtest/engine.py` 成功 | 一行命令 |
| AC6 | 全回测 trade count 与 SPEC-070 v2 后的 baseline 一致或仅 IC_HV / BPS_HV / BCS_HV 类发生 cascade（非 HV 策略不应受影响）| Quant 出 cascade 报告 |
| AC7 | 单元测试：构造一个 HV spell 内 IC_HV 已开 2 笔（达 cap=2）的场景，验证 BPS_HV 仍可入场（不再被错误阻挡）| Developer 写一个 minimal pytest |
| AC8 | 单元测试：HV spell 退出后，`hv_spell_trade_count` 重置为 `{}` | pytest |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-24 | 初稿 — MC v3 handoff 同步项；HC 防御性复现（per audit doc D2 PM 决策 (a)）| DRAFT |
| 2026-04-24 | PM 批量预批（070/068/069/071/072 一起），交 Developer 实施 | APPROVED |
