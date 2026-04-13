# SPEC-051: DIAGONAL Entry Gate — IV=HIGH Block

## 目标

**What**：在 `selector.py` `LOW_VOL + BULLISH` 分支中新增第二道守护门（在 SPEC-049 之后）：当有效 IV 信号为 HIGH（`iv_s == IVSignal.HIGH`）时返回 REDUCE_WAIT。

**Why**：
- LOW_VOL regime 下 IV=HIGH 意味着短期 VIX spike 与长期低波动基准产生背离（IVR/IVP 分歧 > 15pt 场景）
- 在此环境下 DIAGONAL 的短腿（short OTM call）面临 vol expansion 风险，保费收益无法补偿 gamma 敞口
- 串联顺序：SPEC-049（ivp252 过渡区间门）→ **SPEC-051（IV=HIGH 门）** → SPEC-054（both-high 门）

---

## 功能定义

### F1 — LOW_VOL + BULLISH 分支新增 IV=HIGH 门

```python
# 在 SPEC-049 通过之后，SPEC-054 之前
if iv_s == IVSignal.HIGH:
    return _reduce_wait(
        f"LOW_VOL + BULLISH but IV=HIGH (IVP={iv.iv_percentile:.0f}) — "
        "vol expansion signal in low-vol regime; DIAGONAL short leg exposed",
        ...
        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
    )
```

---

## 边界条件

- `iv_s == IVSignal.HIGH` → 拦截（REDUCE_WAIT）
- `iv_s == IVSignal.NEUTRAL` → 通过，继续 SPEC-054
- `iv_s == IVSignal.LOW` → 通过（LOW_VOL + LOW IV = 最适合 DIAGONAL 的环境）

---

## 不在范围内

- 不改动 NORMAL / HIGH_VOL 分支的 IV=HIGH 处理逻辑
- SPEC-049 门顺序在前，不颠倒

---

## 验收标准

- AC1. LOW_VOL + BULLISH + IV=HIGH 返回 REDUCE_WAIT
- AC2. LOW_VOL + BULLISH + IV=NEUTRAL 通过此门，继续 SPEC-054 检查
- AC3. LOW_VOL + BULLISH + IV=LOW 通过此门，继续 SPEC-054 检查
- AC4. SPEC-049 在 SPEC-051 之前执行（串联顺序）

## Review
- 结论：PASS
- Gate 2 在 Gate 1（SPEC-049）之后执行，顺序正确
- 拦截条件：iv_s == IVSignal.HIGH，符合 SPEC
- LOW_VOL + BULLISH + IV=HIGH → REDUCE_WAIT，canonical_strategy 正确设置

---

Status: DONE
