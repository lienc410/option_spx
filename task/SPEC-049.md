# SPEC-049: DIAGONAL Entry Gate — ivp252 Marginal Zone

## 目标

**What**：在 `selector.py` `LOW_VOL + BULLISH` 分支中新增第一道守护门：当 `ivp252 ∈ [30, 50]` 时返回 REDUCE_WAIT，否则继续后续逻辑。

**Why**：
- F006 研究发现 `ivp252 ≥ 50` 的 both-high 子条件对 DIAGONAL 有显著负 alpha
- 当 252 日 IVP 处于 30–50 的"过渡区间"时，长期 vol 环境方向不明，DIAGONAL 优势减弱
- 此门为 LOW_VOL + BULLISH 三道 gate 串联的第一道（串联顺序：SPEC-049 → SPEC-051 → SPEC-054）

---

## 功能定义

### F1 — LOW_VOL + BULLISH 分支新增 ivp252 过渡区间门

```python
# LOW_VOL + BULLISH 分支（在 SPEC-051/054 之前）
if 30 <= iv.ivp252 <= 50:
    return _reduce_wait(
        f"LOW_VOL + BULLISH but ivp252={iv.ivp252:.0f} in 30–50 marginal zone — "
        "long-term vol environment transitional; DIAGONAL edge reduced",
        ...
    )
```

### F2 — 常量

```python
DIAGONAL_IVP252_GATE_LO = 30
DIAGONAL_IVP252_GATE_HI = 50
```

---

## 边界条件

- `ivp252 < 30` → 通过此门（低长期 vol，DIAGONAL 有利）
- `ivp252 > 50` → 通过此门（进入 SPEC-054 both-high 检查）
- `ivp252 == 30` → 过渡区间边界，拦截（REDUCE_WAIT）
- `ivp252 == 50` → 过渡区间边界，拦截（REDUCE_WAIT）

---

## 不在范围内

- 不改动 NORMAL / HIGH_VOL 分支
- 不改动 SPEC-051 / SPEC-054 逻辑（串联顺序中的后续门）

---

## 验收标准

- AC1. ivp252=35 时 LOW_VOL+BULLISH 返回 REDUCE_WAIT
- AC2. ivp252=25 时此门通过，继续后续 SPEC-051 检查
- AC3. ivp252=55 时此门通过，继续后续 SPEC-054 检查
- AC4. SPEC-051 门在 SPEC-049 之后执行（串联顺序正确）

## Review
- 结论：PASS
- Gate 1 在 LOW_VOL + BULLISH 分支首位执行，顺序正确
- 拦截条件：30 <= ivp252 <= 50，边界值（30、50）均拦截，符合 SPEC
- 常量 DIAGONAL_IVP252_GATE_LO=30 / DIAGONAL_IVP252_GATE_HI=50 已定义

---

Status: DONE
