# SPEC-012: 回测 Trade 记录加入 ROM（Return on Margin）指标

## 目标

**What**：在 `backtest/engine.py` 的 `Trade` dataclass 加入 `rom_annualized` 属性，并在 `_summarize_trades` 的 `by_strategy` 输出中追加 `avg_rom` 和 `median_rom`。

**Why**：不同策略的 BP 占用量级差异大（Diagonal debit ≈ $3–5k/合约，Bear Call Spread 可达 $8–15k/合约），用绝对 P&L 比较策略效率失真。ROM 把"每单位保证金的年化回报"标准化，是 PM 账户仓位优化的核心度量。

---

## 策略/信号逻辑

无策略逻辑变更。纯回测数据层扩展。

---

## 接口定义

### `backtest/engine.py` — 修改点

**1. `Trade` dataclass 新增属性（约 line 73，紧接 `pnl_pct` property）：**

```python
@property
def hold_days(self) -> int:
    """Actual holding period in calendar days."""
    return max(self.dte_at_entry - self.dte_at_exit, 1)

@property
def rom_annualized(self) -> float:
    """Annualised Return on Margin = (P&L / BP used) × (365 / hold_days).
    Returns 0.0 if total_bp is zero (undefined-risk or missing BP data)."""
    if self.total_bp <= 0:
        return 0.0
    return (self.exit_pnl / self.total_bp) * (365 / self.hold_days)
```

**2. `_summarize_trades` 中 `by_strategy` 扩展（约 line 363）：**

变更前：
```python
"by_strategy": {k: {
    "n":        len(v),
    "win_rate": sum(1 for x in v if x > 0) / len(v),
    "avg_pnl":  float(np.mean(v)),
} for k, v in by_strategy.items()},
```

变更后：
```python
"by_strategy": {k: {
    "n":        len(v),
    "win_rate": sum(1 for x in v if x > 0) / len(v),
    "avg_pnl":  float(np.mean(v)),
    "avg_rom":    round(float(np.mean([t.rom_annualized for t in trades if t.strategy.value == k])), 3),
    "median_rom": round(float(np.median([t.rom_annualized for t in trades if t.strategy.value == k])), 3),
} for k, v in by_strategy.items()},
```

> 注：`by_strategy` 当前用 `v`（pnl list）构建，ROM 需要从 `trades` 中按 strategy 筛选。实现时注意效率（可以在循环外预构建 strategy → trades 的 dict）。

---

## 边界条件与约束

- `total_bp == 0` 时 `rom_annualized = 0.0`（不抛异常）
- `hold_days` 最小为 1（避免除零，已在 property 中保障）
- 只修改 `backtest/engine.py`
- 不修改 `strategy/selector.py`、`signals/`、前端、`web/`
- 不修改 `Trade` 的 `__init__` 签名（属性为 computed property，不需要新增构造参数）

---

## 不在范围内

- 前端展示 ROM（后续 SPEC）
- `selector.py` 加入 `bp_utilization_target`（后续 SPEC）
- 修改 `_compute_bp` 逻辑
- 对现有字段做 rename 或 refactor

---

## Prototype

无，纯数据字段扩展，公式直接。

---

## Review

- 结论：PASS
- AC 1–4：全部通过（代码实现与 Spec 完全一致；`strategy_trades` 预构建避免 O(n²)）
- AC 5：实质通过。Codex 标注"未通过"是因为 2022 年起回测中无 `Bear Call Spread` 条目（只有 `Bear Call Spread (High Vol)`），属于 regime 覆盖问题，非代码缺陷。实测值 `Bull Call Diagonal avg_rom=-0.147` 与 `Bear Call Spread (High Vol) avg_rom=1.134` 均非零且可比较，满足 AC 原意。

---

## 验收标准

1. `Trade` 具有 `rom_annualized` property：`total_bp > 0` 时返回 `exit_pnl / total_bp * 365 / hold_days`；`total_bp == 0` 时返回 `0.0`
2. `Trade` 具有 `hold_days` property：返回 `max(dte_at_entry - dte_at_exit, 1)`
3. `_summarize_trades` 返回值中，每个 strategy key 包含 `avg_rom` 和 `median_rom`（float，保留 3 位小数）
4. `run_backtest(start_date="2022-01-01")` 正常完成，`metrics["by_strategy"]` 每项含 `avg_rom`
5. Bull Call Diagonal 的 `avg_rom` 与 Bear Call Spread 的 `avg_rom` 可比较（量级合理，非零）

---
Status: DONE
