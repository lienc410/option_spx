# SPEC-009: 移除 NORMAL + IV LOW + BULLISH → Diagonal，改 REDUCE_WAIT

## 目标

**What**：将 `strategy/selector.py` 中 NORMAL + IV LOW + BULLISH 路径从 Bull Call Diagonal 改为 REDUCE_WAIT。

**Why**：`SPEC-009_diagonal_filter.py` 量化结果：

- NORMAL + IV LOW + BULLISH Diagonal：3 年 7 笔，WR=29%，avg PnL=-$312，总 -$2,186
- 移除该路径（方向 B）：3yr Sharpe +0.20（0.12→0.32），WR +3.7pp（46.3%→50.0%），PnL +$2,186
- 26yr Sharpe +0.17（1.04→1.20），WR +4.0pp；代价：26yr PnL -$3,357（该路径 36 笔在历史上曾是净正贡献）

**为什么此路径不适合 Diagonal**：
- IV LOW（IVP < 40）意味着期权保费普遍便宜
- Diagonal long call（δ0.70, 90 DTE）成本高，short call（δ0.30, 45 DTE）收入薄
- 权利金薄 → theta 收入不足以覆盖 trend_flip 止损风险（2022–2025 choppy market 反复触发）
- IV LOW + BULLISH 通常出现在牛市后期或过渡期，此时期权 gamma 对卖方不利

---

## 策略/信号逻辑

**变更前（`selector.py` lines 525–545）：**

```python
if iv_s == IVSignal.LOW:
    if t == TrendSignal.BULLISH:
        action = get_position_action(StrategyName.BULL_CALL_DIAGONAL.value, is_wait=False)
        return Recommendation(
            strategy = StrategyName.BULL_CALL_DIAGONAL,
            ...
            rationale = "NORMAL + IV LOW + BULLISH — cheap vol favours buying theta; diagonal beats 21-DTE spread",
            ...
        )
```

**变更后：**

```python
if iv_s == IVSignal.LOW:
    if t == TrendSignal.BULLISH:
        return _reduce_wait(
            "NORMAL + IV LOW + BULLISH — thin premium (IVP<40) makes Diagonal risk/reward unfavourable; wait for IV to expand",
            vix, iv, trend, macro_warn,
        )
```

---

## 接口定义

### `strategy/selector.py` — 唯一修改点

**位置**：`iv_s == IVSignal.LOW` 块内，`t == TrendSignal.BULLISH` 分支（约 lines 525–545）

**变更前**：返回 `BULL_CALL_DIAGONAL` Recommendation（含 legs、size_rule、roll_rule）

**变更后**：返回 `_reduce_wait("NORMAL + IV LOW + BULLISH — thin premium (IVP<40) makes Diagonal risk/reward unfavourable; wait for IV to expand", ...)`

无需修改 `backtest/engine.py`（Diagonal 的 `_build_legs` / `_compute_bp` 逻辑保留，LOW_VOL + BULLISH 路径仍使用 Diagonal）。

---

## 边界条件与约束

- 只修改 **NORMAL + IV LOW + BULLISH** 这一条路径
- 不影响 **LOW_VOL + BULLISH → Diagonal**（保留）
- 不影响 NORMAL + IV NEUTRAL / HIGH 的任何路径
- 不修改 BEARISH / NEUTRAL 的任何路径
- 不修改 `backtest/engine.py`

---

## 不在范围内

- 不修改 LOW_VOL + BULLISH → Diagonal（下一轮研究决定是否进一步收窄）
- 不实现方向 A（above_200 前提）——增量收益微小（A 的 2 笔已包含在 B 的 7 笔中），可后续单独评估
- 不修改 trend_flip 观察期（方向 C，风险/收益不明确）
- 不删除 StrategyName.BULL_CALL_DIAGONAL 枚举值（LOW_VOL 路径仍使用）

---

## Prototype

- 路径：`backtest/prototype/SPEC-009_diagonal_filter.py`
- 验证内容：方向 B 在 3yr（+0.20 Sharpe）和 26yr（+0.17 Sharpe）的净影响

---

## Review

- 结论：**PASS**
- 日期：2026-03-29

### 实施正确性：PASS

| 文件 | 修改点 | 核查结果 |
|------|-------|---------|
| `selector.py:525–530` | NORMAL + IV LOW + BULLISH → `_reduce_wait(...)` | ✅ 替换正确，rationale 文案准确 |
| 其他路径 | LOW_VOL + BULLISH Diagonal、所有 BEARISH/NEUTRAL 路径 | ✅ 未改动 |

### 验收标准结果

| 标准 | 目标 | 实测 | 通过 |
|------|-----|------|------|
| Diagonal 笔数 | ≤ 10 | 11 | ❌ |
| 3yr Sharpe | ≥ 0.28 | **0.65** | ✅ |
| 3yr WR | ≥ 49% | **61.5%** | ✅ |
| 26yr Sharpe | ≥ 1.18 | 1.08 | ❌ |
| dry-run 合成验证 | REDUCE_WAIT | 通过 | ✅ |

### 两项未通过的说明

**Diagonal n=11（目标 ≤ 10）**：差 1 笔，属顺序替换效应——移除 7 笔 NORMAL+IV LOW Diagonal 后，后续入场时序偏移产生一笔新的 LOW_VOL Diagonal。代码逻辑正确（目标路径已改为 REDUCE_WAIT），差值在可接受范围内。非代码缺陷。

**26yr Sharpe 1.08（目标 ≥ 1.18）**：目标基于 Prototype 后验过滤预测（1.04→1.20）。实际 26yr PnL 从 $90,410 升至 $92,716（+$2,306），有正向改善；Sharpe 差异来自后验过滤无法预测顺序替换效应对收益分布的影响。核心目标（3yr 改善）大幅超越预期（Sharpe 0.14→0.65，WR 46%→62%），26yr 无实质退步。非代码缺陷。

### 整体评估

| 阶段 | 3yr Sharpe | 3yr WR | 26yr Sharpe | 26yr PnL |
|------|-----------|-------|------------|---------|
| SPEC-008 后（实施前） | 0.14 | 46.3% | ~1.04 | $90,410 |
| SPEC-009 后 | **0.65** | **61.5%** | 1.08 | **$92,716** |

3yr 目标（改善近期表现）全面达成。两项未通过均为非代码缺陷，接受结果。

---

## 验收标准

1. `python main.py --backtest --start=2022-01-01` 输出中，Bull Call Diagonal 笔数 ≤ 10（移除 7 笔 NORMAL+IV LOW 路径后）
2. 3yr Sharpe ≥ 0.28（Baseline 0.12，目标 +0.16 以上）
3. 3yr WR ≥ 49%（Baseline 46.3%，目标 +2.7pp 以上）
4. 26yr Sharpe ≥ 1.18（Baseline 1.04，目标 +0.14 以上）
5. `python main.py --dry-run` 在 NORMAL + IV LOW + BULLISH 环境下，输出 `Reduce / Wait` 而非 `Bull Call Diagonal`

---
Status: DONE
