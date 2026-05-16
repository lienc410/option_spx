# Q072 Priority Scoring & Blocked-Entry Design — 2nd Quant Review

**Date**: 2026-05-15
**Reviewer**: 2nd Quant
**Original packet**: `task/q072_priority_scoring_2nd_quant_review_packet_2026-05-15.md`
**Verdict**: **REVISE, but not a blocker for P1 launch**

---

## Top-line verdict

P4C 的方向是对的：BP 不应默认 main-first，而应按 **signal quality × expected return × tail risk** 做机会排序。但当前 priority formula 太容易产生 **in-sample overfit、跨策略不可比、小样本桶不稳定、以及忽略 portfolio marginal risk** 的问题。

> **P1/P2 可以先启动；P4C 设计需要在 P3 之前修订。不要用当前 4 维 z-score formula 直接跑最终 P4C。**

---

## Q1 — Formula 合理性 — REVISE

不建议直接用 `0.4 / 0.4 / 0.2`。tail 权重偏低，且 signal_quality 与 expected_return_per_bp 可能高度相关（若都来自同一套历史分桶统计，重复计算同一信息）。

**建议改两层结构**：

```
base_score = rank(expected_return_per_bp)
risk_adjusted = base_score − λ × rank(tail_penalty)
```

`signal_quality` 作为 **eligibility / confidence adjustment**，而不是同等加权项。

**实用版本**：
```
priority = 0.6 × rank(expected_return_per_bp) − 0.4 × rank(tail_penalty)

confidence haircut:
    if bucket_n < 10: priority *= 0.5
    if bucket_n <  5: use parent bucket
```

不推荐 multiplicative `return / (1 + tail_penalty)`：当 expected return 为负或接近零时解释变差。

---

## Q2 — 分桶维度 — REVISE（4 维过细）

每个 sleeve 用它真正的 signal dimension，不要强行套统一 4 维桶：

| Strategy | 分桶 key |
|---|---|
| Main / BPS / IC | `regime × IVP bucket` |
| Drawdown Overlay | `ddATH bucket × VIX bucket` |
| Aftermath / BPS_HV permission | `VIX peak/off-peak state × current VIX bucket` |
| HV Ladder | `VIX bucket × trend_ok / VIX trend` |

VIX slope / VIX term 作为 later diagnostic，不进第一版 priority formula。

---

## Q3 — 小样本与过拟合 — 小样本更紧急

**必须立即修正**（shrinkage / parent bucket）：

```
if bucket_n >= 20:    use bucket statistic
elif 5 <= bucket_n < 20: 50% bucket + 50% parent strategy statistic
else:                 use parent strategy statistic
```

**Walk-forward**：作为 P4C robustness check，不阻塞 P1/P2。最低要求一个 split：
```
Train priority tables on 2007–2018
Test allocation on 2019–2026
```

---

## Q4 — Z-score 跨策略可比性 — REVISE

per-strategy z-score 后跨策略排序会让"弱策略内部 +1σ" 排在"强策略普通机会"前。

**改 global rank-percentile**：
1. 对所有 historical candidate trades 计算 realized `$/BP-day` 和 tail metric
2. 形成全局分布
3. 每个 candidate 的 expected return 与 tail penalty 都映射到全局 percentile
4. 再进行 priority 排序

per-strategy 信息保留作为 confidence / rarity adjustment，不作主 score。

---

## Q5 — Portfolio-level 约束 — 必须加，且作为 hard overlay

单 candidate priority 不够。否则可能出现：
> 每一笔单看都不错，但合在一起全是 short vol / short delta，组合尾部集中爆炸。

**两层约束**：

**1. Hard ceilings**
```
SPX PM pool BP <= X% NLV
/ES SPAN <= Y% NLV
combined stress loss <= Z% NLV
short-vega sleeve exposure <= cap
short-delta exposure <= cap
```

**2. Marginal risk check**
```
portfolio_CVaR_after − portfolio_CVaR_before
stress_loss_after − stress_loss_before
delta/vega/gamma concentration after
```

超过 ceiling 即使 priority 高也不能入场。

> **Eligibility first, priority second.**

---

## Q6 — Tier 平手逻辑 — REVISE

Tier 只用于真实平手，不能隐性覆盖 score：

```
Tier tie-break only if abs(priority_i - priority_j) < 5 percentile points
```

Tier 顺序略调：
```
Tier 1: rare + historically positive + cannot be delayed
Tier 2: high-vol opportunity sleeves
Tier 3: repeatable / stable strategies
```

不要只按"稀缺"定义 Tier。稀缺但弱的信号不应优先。

---

## Q7 — 对照组充分性 — 加 static cap baseline

production 最可能不会直接采用复杂 priority formula，而是采用简单 cap + 手工/规则化优先级。**必须证明 priority-based 明显优于 static cap，否则复杂度不值得**。

P4C 对照应为：

| 组 | 规则 |
|---|---|
| A | main-first |
| B | sleeve-first |
| C | FCFS |
| **D** | **static sleeve caps**（Main 70% / DD 10–20% / Aftermath-BPS_HV 10–15% / HV Ladder 独立 /ES cap）|
| E | priority-based |

---

## Q8 — P1 前 blocker？ — No

P1/P2 是 co-activation / entry profile，不依赖最终 priority formula，可先开跑。

**P4C 之前必须修订**：
1. 取消 4 维统一分桶
2. 不使用 per-strategy z-score 直接跨策略比较
3. 增加 shrinkage / parent-bucket fallback
4. 增加 global rank-percentile scoring
5. 增加 portfolio hard ceilings
6. 增加 static cap baseline
7. 明确 P4C 是 research allocator，不等于 production implementation

---

## 修订版 P4C 流程

**Step 1 — Eligibility filter**
```
candidate passes its own strategy rules
AND account-level BP/SPAN cap not breached
AND portfolio stress CVaR cap not breached
AND no sleeve-specific cap breached
```
不通过则 blocked，不进入 priority ranking。

**Step 2 — Candidate score**（global percentile）
```
return_score = percentile(expected $/BP-day among all candidates)
tail_score   = percentile(tail risk among all candidates)
priority     = 0.6 * return_score − 0.4 * tail_score
```
Sensitivity：`0.5/0.5, 0.7/0.3, 0.4/0.6`

**Step 3 — Confidence haircut**
```
if bucket_n < 5:  use parent strategy distribution
elif bucket_n < 20: shrink toward parent distribution
```

**Step 4 — Tie-break**
```
if abs(priority_i - priority_j) < 5 percentile points: Tier
else: priority wins
```

**Step 5 — Controls**：main-first / sleeve-first / FCFS / static cap / priority

---

## 8 个风险点直接判断

| 风险 | 修订 | 意见 |
|---|---|---|
| 1. 过拟合 | 是 | 至少做 2007–2018 train / 2019–2026 test |
| 2. 小样本桶 | 是 | 必须 shrinkage / parent bucket |
| 3. z-score 跨策略 | 是 | 改 global rank-percentile |
| 4. tail penalty 单边 | 是 | tail metric conditional by strategy/regime，并 shrink |
| 5. w_t=0.2 偏低 | 是 | tail 权重提高，或 hard CVaR cap |
| 6. 无 portfolio constraint | 是 | 必须加 hard ceiling / marginal CVaR |
| 7. HV Ladder final config | 是 | Q071 lock 后重算 |
| 8. production 落地路径 | 是 | 明确需另开 SPEC，不在 Q072 自动实施 |

---

## Final verdict

**REVISE, BUT P1 CAN START.**

> P4C 的"按信号质量 × 回报 profile 分配 BP"方向正确，但当前 scoring 版本过于 in-sample、分桶过细、跨策略 z-score 不可比，且缺 portfolio-level risk constraint。P1/P2 可以先启动；P4C 在运行前应改为 eligibility-first + global rank-percentile scoring + shrinkage + portfolio CVaR/BP ceilings，并增加 static sleeve-cap 对照组。不要把当前 priority formula 当成最终 allocator。
