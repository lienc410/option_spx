# Q072 Global Sleeve Evaluation Design — 2nd Quant Review

**Date**: 2026-05-15
**Reviewer**: 2nd Quant
**Original packet**: `task/q072_sleeve_global_eval_design_review_2026-05-15.md`
**Verdict**: **PASS WITH REVISIONS**

---

## Top-line verdict

**框架方向正确，但需要把"触发同步"升级为"同一 stress episode 下的资本/希腊值/路径风险叠加评估"。**

Drawdown Overlay、Aftermath、HV Ladder 三个 sleeve 都在 high vol 或市场承压时启动，单独看每个策略可能合理，但组合层面可能出现：

> **同一压力窗口里，多个 sleeve 同时占用 BP、同向承受回撤、并挤压主策略/其它机会。**

当前 Q072 的 P1–P4 框架基本覆盖了这个问题：co-activation、entry profile、co-loss、ablation 都是必要模块。主要修改建议：**P1 不要只看 day-level overlap，要做 episode-level overlap；P3 必须加入 portfolio Greek / margin stress path；P4 需要修正 Aftermath 的口径。**

---

# Q1 — 框架完整性

## Verdict: **PASS with additions**

P1–P4 大方向合理：

| Phase | 作用 |
| --- | --- |
| P1 Co-activation | 看三个 sleeve 是否同时在场 |
| P2 Entry profile | 看它们是否真是同一类 signal |
| P3 Co-loss / drawdown | 看同场时是否同亏 |
| P4 Ablation | 看组合 marginal value 是否值得 |

建议补充五个维度。

## 1. Episode-level overlap

Day-level overlap 会低估风险。三个 sleeve 可能不在同一天入场，但属于同一个 volatility / drawdown episode。

例如：
```
Day 0: VIX spike
Day 3: Aftermath fires
Day 5: Drawdown Overlay fires
Day 8: HV Ladder fires
```

day-level overlap 可能不高，但组合风险是在同一 episode 中累积的。

建议 P1 增加：
```
stress episode = continuous period where:
    VIX >= 22
    OR SPX drawdown from 20d/60d high >= 4%
    OR any sleeve active
```

输出：
```
P(≥2 sleeves active within same episode)
P(3 sleeves active within same episode)
median / max episode length
episode-level peak BP
episode-level peak drawdown
```

## 2. Peak capital stack, not just average BP

BP 竞争是 peak stack 问题，不是平均占用问题。

P1 应输出：
```
average BP / P90 BP / P95 BP / peak BP
peak BP during stress episodes
days with BP > 30%, 40%, 50% NLV
```

按 pool 分层：
```
SPX PM pool: main + Drawdown Overlay + Aftermath/BPS_HV
/ES futures pool: HV Ladder
Combined economic risk: SPX PM + /ES notional/stress margin proxy
```

## 3. Greek netting path

P3 不能只看 P&L correlation，需要看 entry 和 stress window 中的 Greek path：
```
portfolio delta / gamma / vega / theta
short-vol vs long-vol notional
```

建议 P3 加：
```
Greek before sleeve entry
Greek after sleeve entry
Greek at MAE date
Greek at worst 5% portfolio P&L dates
```

## 4. Path-dependent drawdown after entry

每个 sleeve 都要有 post-entry path profile：
```
1d / 3d / 5d / 10d / 20d PnL after entry
MAE before exit / MFE before exit
time to max pain / time to recovery
```

## 5. Opportunity-cost / blocked-entry analysis

P4 要量化：sleeve active 时是否阻止主策略或其它 sleeve 入场？
```
blocked trade count
blocked trade counterfactual PnL
blocked trade counterfactual drawdown
```

---

# Q2 — Greek 方向不同如何处理？

## Verdict: **必须单独建模，不应只靠 P4 ablation**

P3 把 sleeve 分成两类：

**A. Stress-reversal sleeve**: Drawdown Overlay（long delta / long gamma），payoff 依赖 SPX rebound after drawdown
**B. Stress-premium sleeve**: Aftermath / HV Ladder（short vol / short gamma / theta+），payoff 依赖 vol 稳定或 mean revert

P3 做 **two-path stress decomposition**：

| Path | 预期 |
| --- | --- |
| Fast recovery | DD Overlay wins, short-vol sleeves likely win |
| Sideways vol crush | Aftermath/HV win, DD may decay |
| Second-leg selloff | all can lose |
| Vol spike without price collapse | DD weak, short-vol sleeves hurt |

---

# Q3 — Aftermath 的口径是否有问题？

## Verdict: **Yes — P4 必须修正口径**

Aftermath 不是 standalone strategy，是 permission label，解锁 BPS HV 入场。

P4 拆成：

**P4A — SPX PM pool ablation**
```
A: Main only
B: Main + Drawdown Overlay
C: Main + BPS_HV with aftermath permission
D: Main + Drawdown Overlay + BPS_HV aftermath permission
```

**P4B — /ES pool ablation**
```
E: HV Ladder only
F: SPX pack + HV Ladder
```

---

# Q4 — HV Ladder 时机

## Verdict: **选 C：P1/P2 先做，P3/P4 等 Q071 final config lock 后做**

```
Q072 Phase 1–2 can start now.
Q072 Phase 3–4 should wait for Q071 final memo / SPEC candidate.
```

---

# Q5 — 判断阈值是否合理？

## Verdict: **当前阈值可作为 heuristics，但不能作为 hard decision**

**P1 共激活率三层**：
```
<10%: low direct overlap
10–30%: moderate overlap, run P3
>30%: meaningful overlap, P3/P4 mandatory
>50%: high redundancy / high conflict risk
```

**P3 daily P&L correlation**：
```
Full-sample corr > 0.3: watch
Worst-5%-day corr > 0.3: material
Co-loss rate > independent baseline × 1.5: material
```

**P4 normalized**：
```
marginal PnL per incremental BP-day
marginal CVaR per incremental BP-day
marginal drawdown per incremental BP
```

Promote condition：
```
marginal $/BP-day positive
and CVaR does not worsen beyond threshold
and worst 20d window not worse by >X%
```

---

# Q6 — 优先级与停研条件

## Verdict: **P1 → P2 → P3 → P4 合理，但需要 early stop rules**

**Phase 1 停止条件**：
```
pairwise active overlap <5%
episode overlap <10%
peak SPX PM BP stack never exceeds cap
→ stop full P3/P4, light monitoring only
```

**Phase 1 必须继续**：
```
episode overlap >10%
or any stress window has ≥2 sleeves active
or peak BP stack >30–40% NLV
```

**Phase 3 启动**：P1 显示 meaningful overlap，或 PM 要 portfolio-tail evidence，或 HV Ladder promoted。
**Phase 4 启动**：P1/P3 显示 meaningful overlap / capital competition，或 PM 要 sleeve cap rule，或 HV Ladder goes live/paper。

---

# 修订版 Q072 结构

**P1 — Co-activation + episode-level capital stack**
```
daily overlap / episode overlap
SPX PM BP stack / /ES SPAN stack / combined economic stress stack
peak / P95 / stress-window BP
```

**P2 — Entry profile + regime clustering**
```
entry distributions: VIX, VIX slope, ddATH, IVP, VIX term if available
distance between sleeve entries
```

**P3 — Path / Greek / co-loss analysis**
```
post-entry MAE/MFE path
daily PnL corr / worst 5% co-loss
Greek netting
second-leg selloff scenario
```

**P4 — Corrected ablation**

SPX pool:
```
Main / Main + Drawdown / Main + BPS_HV aftermath permission /
Main + Drawdown + BPS_HV aftermath permission
```

/ES pool:
```
HV Ladder / SPX pack + HV Ladder economic overlay
```

---

# Final verdict

**PASS WITH REVISIONS.**

> Q072 的研究方向正确，P1–P4 覆盖了 sleeve 全局评估的核心问题。但设计应升级为 episode-level stress analysis，而不是仅 day-level overlap；P3 必须显式建模 Greek / path / co-loss；P4 必须修正 Aftermath 口径，把它作为 BPS_HV permission module，而不是 standalone sleeve。HV Ladder 可以先进入 P1/P2 触发分析，但 P3/P4 应等 Q071 final config lock 后再做。总体建议：先启动 revised P1/P2，视 overlap 和 peak BP stack 决定是否进入 P3/P4。
