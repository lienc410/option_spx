# SPEC-056c: 撤销 SPEC-054 both_high 门

## 目标

**What**：删除 `selector.py` LOW_VOL + BULLISH 分支中的 Gate 3（SPEC-054），即 `ivp63 ≥ 50 AND ivp252 ≥ 50 → REDUCE_WAIT` 这一道门。

**Why**：
- SPEC-054 的拦截依据来自 F006 研究（n=8，Sharpe −1.36）
- SPEC-056 全历史矩阵分析发现：F006 的 n=8 是「已被 Gate 1+2 过滤后的残余子集」，存在负向选择偏差
- 禁门全样本 event study（n=14）：both_high DIAGONAL avg +$1,579，WR 50%，Sharpe 1.56——与 double_low（Sharpe 1.26）相近，是中性偏正环境
- 撤销此门后，both_high 场景进入正常 DIAGONAL 入场（Full size，因 ivp252 ≥ 50 通常已绕过 Gate 1）

## 实施方式

Fast Path（单文件 `strategy/selector.py`，删除约 8 行，不新增函数）

---

## 功能定义

删除 Gate 3 代码块：

```python
# ── Gate 3 (SPEC-054): both-high ─────────────────────────────
if iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 >= REGIME_DECAY_IVP252_MIN:
    return _reduce_wait(
        f"LOW_VOL + BULLISH but ivp63={iv.ivp63:.0f} >= 50 AND ivp252={iv.ivp252:.0f} >= 50 "
        "(both-high) — near-term AND long-term vol stressed; DIAGONAL tail risk too high",
        vix, iv, trend, macro_warn,
        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
        params=params,
    )
```

常量 `LOCAL_SPIKE_IVP63_MIN` 和 `REGIME_DECAY_IVP252_MIN` 仍被其他逻辑使用，不删除。

---

## 不在范围内

- 不改动 Gate 1（SPEC-049）和 Gate 2（SPEC-051）
- 不删除 SPEC-054 相关常量
- 尾部风险已由 regime_decay size-up（SPEC-053）的反向逻辑覆盖：both_high 的 ivp63 ≥ 50 属于 local_spike 或正常 DIAGONAL，均有对应处理

---

## 验收标准

- AC1. ivp63=60, ivp252=60（both-high）时 LOW_VOL+BULLISH 返回 DIAGONAL（不再 REDUCE_WAIT）
- AC2. Gate 1（ivp252=40）和 Gate 2（IV=HIGH）仍正常触发 REDUCE_WAIT
- AC3. both_high 进入 DIAGONAL 时，size_rule 走正常 `_compute_size_tier()` 逻辑（不含 local_spike 覆盖，因 ivp252 ≥ 50 不满足 local_spike 条件）

## Review
- 结论：PASS
- Gate 3 代码块已删除，替换为注释说明撤销原因
- AC1: ivp63=60, ivp252=60 → BULL_CALL_DIAGONAL（不再 REDUCE_WAIT）✓
- AC2: Gate 1（ivp252=40）、Gate 2（IV=HIGH）仍正常触发 REDUCE_WAIT ✓
- AC3: both-high size_rule 走 `_size_rule()` 正常路径（无 local_spike / regime_decay 覆盖）✓
- 测试：T7/T18 更新以反映新行为，107/107 通过

---

Status: DONE
