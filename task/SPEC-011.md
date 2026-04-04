# SPEC-011: 修复 Engine 短腿检测与 Diagonal DTE 不一致

## 目标

**What**：修复 `backtest/engine.py` 中两个相互关联的 bug：
1. **短腿误判**：engine 假设 `legs[0]` 为短腿，但 BULL_CALL_DIAGONAL 的 `legs[0]` 是多腿（long back-month call），导致 `dte_at_entry`、`dte_at_exit`、`roll_21dte` 均基于错误的腿计算。
2. **DTE 不一致**：`_build_legs` 中 BULL_CALL_DIAGONAL 的 `short_dte = 30`，但 `selector.py` 明确指定短腿为 45 DTE（`Leg("SELL", "CALL", 45, 0.30, ...)`）。

**Why**：以上两个 bug 导致：
- `roll_21dte` 在第 9 天触发（30-21=9 天持仓），而正确应在第 24 天触发（45-21=24 天持仓）
- `dte_at_entry` 记录为 30，实际应为 45
- P&L 模拟使用错误的 DTE 进行 BS 重定价，Diagonal 的历史回测结果全部基于错误参数

**背景**：此 bug 由 Codex 在实施 SPEC-010 期间发现并顺带修复（超出 SPEC-010 范围）。SPEC-011 为事后追溯记录，实施已完成。

---

## 策略/信号逻辑

无策略逻辑变更。纯 engine 实现修正，使回测行为与 selector 设计一致。

---

## 接口定义

### `backtest/engine.py` — 修改点

**新增辅助函数 `_short_leg(legs)`（约 line 125）：**
```python
def _short_leg(legs):
    """Return the first short leg tuple, or the first leg as fallback."""
    for leg in legs:
        if leg[0] < 0:
            return leg
    return legs[0] if legs else (0, False, 0.0, 0, 0)
```

**`_build_legs` 中 BULL_CALL_DIAGONAL（约 line 144）：**
- 变更前：`short_dte = 30`
- 变更后：`short_dte = 45`

**`run_backtest` 中短腿引用（3 处）：**
- 变更前：`legs[0]`（或隐含的 legs[0] 计算）
- 变更后：`_short_leg(position.legs)` / `_short_leg(legs)`

---

## 边界条件与约束

- 只修改 `backtest/engine.py`
- 不修改 `strategy/selector.py`、`signals/`、prototype 代码
- BEAR_CALL_DIAGONAL 同样受 `_short_leg` 修复保护（其 legs[0] 也是长腿）
- `_compute_bp` 中对 `legs[0]` 的引用属于 spread 宽度计算，逻辑正确，不需修改

---

## 不在范围内

- 不修改 selector 的 Diagonal 策略参数
- 不修改 SPEC-009 的验收结论（SPEC-009 的 3yr 改善仍然成立；engine 修复后的绝对数值另行核查）
- 不重新运行 SPEC-009 验收（属后续基线更新任务）

---

## Prototype
（无，bug 修复，不需要量化验证）

---

## Review
- 结论：PASS（确认型执行，代码已满足所有验收标准，无新增改动）

---

## 验收标准

1. `_short_leg()` 函数存在于 `engine.py`，对 BULL_CALL_DIAGONAL 返回 `legs[1]`（SELL CALL 45 DTE）
2. `_build_legs` 中 BULL_CALL_DIAGONAL 的 `short_dte == 45`
3. `run_backtest(start_date="2022-01-01")` 输出中，Diagonal `dte_at_entry` 为 45（而非 30）
4. 2023-12-08 的 BULL_CALL_DIAGONAL 交易：`dte_at_entry=45`，`exit_date=2024-01-16`，`dte_at_exit=21`，`exit_reason=roll_21dte`（Codex 已验证此用例）
5. 26yr 和 3yr 回测可正常完成，无异常报错

---
Status: DONE
