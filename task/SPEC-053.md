# SPEC-053: Regime Decay Size-Up — DIAGONAL Only (Fix SPEC-048 Misapplication)

## 目标

**What**：修正 SPEC-048 的 `_compute_size_tier()` 实现，将 regime decay size-up 限定为仅在 `strategy == BULL_CALL_DIAGONAL` 时生效；BPS、BPS_HV、BCS_HV 不触发 regime decay size-up。

**Why**：
- F004 研究：regime decay size-up 对 DIAGONAL 有效（Sharpe +3.56）
- 对 BPS：Sharpe −0.87；BPS_HV：Sharpe −1.12；BCS_HV：Sharpe −2.84
- SPEC-048 将 size-up 应用于所有策略是错误的，需要修正

---

## 功能定义

### F1 — `_compute_size_tier` 增加 strategy 参数

```python
def _compute_size_tier(
    strategy_key: str,
    iv: IVSnapshot,
    vix: VixSnapshot,
) -> str:
    if iv.regime_decay and strategy_key == StrategyName.BULL_CALL_DIAGONAL.value:
        return "Full"   # regime decay size-up 仅 DIAGONAL 专属
    # 其他情况走原有逻辑
    ...
```

### F2 — 所有 _compute_size_tier 调用点需传入 strategy_key

- `select_strategy()` 内所有调用 `_compute_size_tier()` 的位置需传入当前 strategy 的 key
- 确认 BPS、BPS_HV、BCS_HV 调用点不再触发 regime decay size-up

---

## 常量（来自 SPEC-048，在此确认）

```python
REGIME_DECAY_IVP63_MAX  = 50   # ivp63 须 < 50
REGIME_DECAY_IVP252_MIN = 50   # ivp252 须 ≥ 50
```

---

## 验收标准

- AC1. DIAGONAL + regime_decay=True → Full size
- AC2. BPS + regime_decay=True → 不触发 Full（走正常 Half/Full 判断）
- AC3. BPS_HV + regime_decay=True → 不触发 Full
- AC4. BCS_HV + regime_decay=True → 不触发 Full
- AC5. `_compute_size_tier` 函数签名包含 `strategy_key: str` 参数

## Review
- 结论：PASS
- _compute_size_tier() 新增，含 strategy_key 参数
- regime_decay + DIAGONAL → "Full size — regime decay..."
- regime_decay + 其他策略（BPS 等）→ 走原 _size_rule() 逻辑，不触发 Full override
- DIAGONAL 调用点正确传入 StrategyName.BULL_CALL_DIAGONAL.value

---

Status: DONE
