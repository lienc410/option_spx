# SPEC-058: NORMAL|HIGH IC 路由放宽 — 撤销 IVP ≥ 50 守护门

## 目标

**What**：在 `selector.py` NORMAL + IV_HIGH 分支中，撤销 BEARISH 和 NEUTRAL 两条路径上的 `IVP ≥ 50 → REDUCE_WAIT` 门，允许 IC 在 IVP ≥ 50 时入场。

**Why**：
- SPEC-057 全历史强制入场矩阵回测结论：
  - `NORMAL|HIGH|BEARISH`：IC avg $2,043，n=13，是全矩阵最强 cell 之一
  - `NORMAL|HIGH|NEUTRAL`：IC avg $1,017，n=9
- 原 IVP ≥ 50 门的经济逻辑是"stressed vol = IC put side at risk"，但矩阵数据显示 IC 在此环境下反而收益更高——富余 premium 补偿了尾部风险
- NORMAL regime（VIX 15–22）的 IVP ≥ 50 与 HIGH_VOL 的 vol spike 性质不同，不应同等对待

## 实施方式

Fast Path（单文件 `strategy/selector.py`，删除 2 处各 ~5 行，不新增函数）

---

## 变更 1：NORMAL + IV_HIGH + BEARISH（line 818）

**删除**：
```python
            if iv.iv_percentile >= 50:
                return _reduce_wait(
                    f"NORMAL + IV HIGH + BEARISH but IVP={iv.iv_percentile:.0f} ≥ 50 — stressed vol; IC put side at risk",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.IRON_CONDOR.value,
                    params=params,
                )
```

## 变更 2：NORMAL + IV_HIGH + NEUTRAL（line 860）

**删除**：
```python
        if iv.iv_percentile > 50:
            return _reduce_wait(
                f"NORMAL + IV HIGH + NEUTRAL but IVP={iv.iv_percentile:.0f} > 50 — tail risk too elevated for Iron Condor",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.IRON_CONDOR.value,
                params=params,
            )
```

VIX_RISING 门（两处）均保留不变。

---

## 不在范围内

- 不改动 NORMAL + IV_HIGH + BULLISH 路径（BPS，IVP ≥ 50 门保留——BPS 在 NORMAL|HIGH|BULLISH 表现为 −$299，门有保护价值）
- 不改动 HIGH_VOL 分支
- 不改动 LOW_VOL 分支

---

## 验收标准

- AC1. NORMAL + IV_HIGH + BEARISH + IVP=60 + VIX_FLAT → 返回 IRON_CONDOR（不再 REDUCE_WAIT）
- AC2. NORMAL + IV_HIGH + BEARISH + VIX_RISING → 仍返回 REDUCE_WAIT（VIX_RISING 门保留）
- AC3. NORMAL + IV_HIGH + NEUTRAL + IVP=60 + VIX_FLAT → 返回 IRON_CONDOR
- AC4. NORMAL + IV_HIGH + BULLISH + IVP=60 → 仍返回 REDUCE_WAIT（BPS 的 IVP ≥ 50 门保留）

## Review
- 结论：PASS
- 变更 1（BEARISH）：IVP ≥ 50 门已删除，替换为注释；AC1 ✓，AC2（VIX_RISING 保留）✓
- 变更 2（NEUTRAL）：IVP > 50 门已删除，替换为注释；AC3 ✓
- AC4：NORMAL+HIGH+BULLISH 的 BPS IVP ≥ 50 门未改动 ✓
- 114/114 通过，无回归

---

Status: DONE
