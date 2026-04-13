# SPEC-054: DIAGONAL Entry Gate — Both-High IVP Block

## 目标

**What**：在 `selector.py` `LOW_VOL + BULLISH` 分支中新增第三道守护门（SPEC-049 → SPEC-051 → **SPEC-054**）：当 `ivp63 ≥ 50 AND ivp252 ≥ 50`（both-high 子条件）时返回 REDUCE_WAIT。

**Why**：
- F006 研究：both-high 子条件（n=8），平均 −$2,556，Sharpe −1.36
- SPEC-049（ivp252 30–50 过渡区间）和 SPEC-051（IV=HIGH）无法全部拦截：6 笔穿透均值 −$2,624，最差单笔 −$14,973（2020-02-06 COVID 前期）
- 在近期和长期 vol 均高位时，DIAGONAL 面临 vol spike 直接击穿 short call 的尾部风险

---

## 功能定义

### F1 — LOW_VOL + BULLISH 分支新增 both-high 门

```python
# 在 SPEC-049、SPEC-051 通过之后（最后一道门）
if iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 >= REGIME_DECAY_IVP252_MIN:
    return _reduce_wait(
        f"LOW_VOL + BULLISH but ivp63={iv.ivp63:.0f} ≥ 50 AND ivp252={iv.ivp252:.0f} ≥ 50 "
        "(both-high) — near-term AND long-term vol stressed; DIAGONAL tail risk too high",
        ...
        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
    )
```

### F2 — 常量（与 SPEC-055 共享）

```python
LOCAL_SPIKE_IVP63_MIN  = 50   # ivp63 阈值（both-high 和 local_spike 共用）
REGIME_DECAY_IVP252_MIN = 50  # ivp252 阈值（与 SPEC-048/053 共用）
```

---

## 边界条件

- `ivp63=55, ivp252=55` → REDUCE_WAIT（both-high）
- `ivp63=55, ivp252=45` → 通过（local_spike 场景，SPEC-055 tag，不拦截）
- `ivp63=45, ivp252=55` → 通过（regime decay 场景）
- `ivp63=45, ivp252=45` → 通过（正常 DIAGONAL 入场）

---

## 串联顺序确认

`LOW_VOL + BULLISH` 执行顺序：
1. SPEC-049：`ivp252 ∈ [30, 50]` → REDUCE_WAIT
2. SPEC-051：`iv_s == HIGH` → REDUCE_WAIT
3. SPEC-054：`ivp63 ≥ 50 AND ivp252 ≥ 50` → REDUCE_WAIT
4. 通过所有门 → DIAGONAL

---

## 验收标准

- AC1. ivp63=60, ivp252=60 时 LOW_VOL+BULLISH 返回 REDUCE_WAIT
- AC2. ivp63=60, ivp252=40 时通过此门（local_spike 不拦截）
- AC3. 串联顺序：SPEC-054 在 SPEC-051 之后执行
- AC4. 常量 `LOCAL_SPIKE_IVP63_MIN=50` 和 `REGIME_DECAY_IVP252_MIN=50` 存在

## Review
- 结论：PASS
- Gate 3 在 Gate 2（SPEC-051）之后、最终 DIAGONAL 入场之前执行，顺序正确
- 拦截条件：ivp63 >= 50 AND ivp252 >= 50（both-high），符合 SPEC
- 与 Gate 1 组合：ivp252 ∈ [30,50] 被 Gate 1 拦截，ivp252 > 50 进入 Gate 3

---

Status: DONE
