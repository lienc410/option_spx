# SPEC-052: BCS_HV Entry Gate — ivp63 High Stress Block

## 目标

**What**：在 `selector.py` `HIGH_VOL + BEARISH` 分支中，在现有 VIX_RISING 检查之后新增：当 `ivp63 ≥ 70` 时返回 REDUCE_WAIT，不进入 BCS_HV。

**Why**：
- F007 研究：BCS_HV 在 ivp63 ≥ 70 区间（n=14）均值 −$2,222，胜率仅 21%
- 经济逻辑：VIX 处于 63 天高位（ivp63 ≥ 70）时，均值回归风险最高——短期 call 的 delta 可能被持续上涨消耗，BCS_HV 的 short call 被击穿风险极高

---

## 功能定义

### F1 — HIGH_VOL + BEARISH 分支新增 ivp63 门

```python
# HIGH_VOL + BEARISH，现有 VIX_RISING 检查之后
if iv.ivp63 >= IVP63_BCS_BLOCK_THRESHOLD:
    return _reduce_wait(
        f"HIGH_VOL + BEARISH but ivp63={iv.ivp63:.0f} ≥ 70 — "
        "VIX at 63-day high; mean reversion risk too elevated for BCS_HV short call",
        ...
        canonical_strategy=StrategyName.BEAR_CALL_SPREAD_HV.value,
    )
```

### F2 — 常量

```python
IVP63_BCS_BLOCK_THRESHOLD = 70
```

---

## 边界条件

- `ivp63 ≥ 70` → REDUCE_WAIT
- `ivp63 < 70` → 通过，正常进入 BCS_HV

---

## 不在范围内

- 不改动 BPS_HV（HIGH_VOL + BULLISH）分支
- 不改动 IC_HV（HIGH_VOL + NEUTRAL）分支

---

## 验收标准

- AC1. HIGH_VOL + BEARISH + ivp63=75 返回 REDUCE_WAIT
- AC2. HIGH_VOL + BEARISH + ivp63=65 通过此门，返回 BCS_HV（backwardation 和 VIX_RISING 检查通过前提下）
- AC3. 常量 `IVP63_BCS_BLOCK_THRESHOLD = 70` 存在于 selector.py

## Review
- 结论：PASS
- Gate 在 HIGH_VOL + BEARISH 分支，VIX_RISING 检查之后插入，顺序正确
- 拦截条件：iv.ivp63 >= IVP63_BCS_BLOCK（70），符合 SPEC
- 常量 IVP63_BCS_BLOCK=70 已定义

---

Status: DONE
