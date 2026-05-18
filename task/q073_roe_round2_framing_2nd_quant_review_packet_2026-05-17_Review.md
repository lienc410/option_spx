# Q073 Round 2 ROE Optimization — 2nd Quant Framing Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-17
**Source packet**: `task/q073_roe_round2_framing_2nd_quant_review_packet_2026-05-17.md`
**Verdict**: **PASS WITH MAJOR REVISIONS**

> Q073 应该做，而且应该作为 Round 2 的顶层项目。但 framing 改成：**Risk-constrained portfolio ROE optimization under current multi-strategy, multi-account architecture.** 不是单纯找更高 ROE。**REVISE and proceed after P0 is anchored.**

---

## Required Revisions (Quant Researcher 必须落地)

1. **ROE 不能裸目标**: P0 改为 "ROE max subject to drawdown / CVaR / stress / governance vetoes"
2. **加 Lever F**: Strategy sizing / capital budget hierarchy
3. **加 Lever G**: Strategy retirement / simplification / role demotion
4. **拒绝立即加**: 新标的 (RUT/SPY) / butterflies / macro overlay / ML — 这些进 future research，不进 Q073 (避免 scope creep)
5. **重排 lever 优先级**: P1 → **C / D / F** → **B** → **A** (capital first, strategy matrix last)
6. **Friction = mandatory P1 adjustment**, 不是 late optional lever
7. **P2 改 hypothesis-driven**: 出 3-4 个 Arch candidate (Arch-0 baseline / Arch-1 conservative / Arch-2 moderate / Arch-3 radical)，**不做 brute-force grid**
8. **Strategy role classification** 必须在 P1 完成 (core income / opportunistic / hedge / permission module / idle filler / paper-only)
9. **Promotion level 4 档**: production-ready / paper-ready / shadow-only / research-only
10. **P0 必须 PM + Quant + 2nd Quant 三方锚定**, 不是 Quant 单独

---

## Blind Spots 2nd Quant 补充 (我自己没看到的)

### Blind Spot 1 — ROE denominator 定义
- combined NLV vs avg deployed BP vs risk capital vs SPAN
- P0 必须明确：Primary ROE = **annualized PnL / combined NLV**；Efficiency metric = **$/BP-day or return on avg BP**

### Blind Spot 2 — Cash yield / T-bill baseline (关键)
- Idle BP ≠ 0 收益。Schwab/E-Trade 现金 4-5% T-bill yield 是 baseline 比较点
- 如果 cash yield 已经 > strategy ROE → 该 strategy 不能作 ROE engine
- P0 必须把 cash yield 加进 baseline 公式

### Blind Spot 3 — Human attention / operational ROE
- 策略多 → PM 时间 / 执行错误 / 注意力 都是真实 cost
- P1 加 qualitative score: daily attention burden / execution complexity / automation readiness

### Blind Spot 4 — Correlated model error
- 所有策略基于同一 SPX/VIX historical + 同一 BS model → model error 是相关的
- P4 stress test 要假设: slippage / fills / margin estimate / VIX timing 在 stress 中**同时变差**

### Blind Spot 5 — Strategy role classification (关键)
- 不能按 ROE 单维排名
- 必须先分角色: core income / opportunistic / hedge / permission module / idle filler / paper-only
- 比如 Aftermath = permission module (Q064 结论)，不是 income engine
- HV Ladder = opportunistic sleeve, 不是 daily income
- P1 先做 role map，再做 ROE

---

## Methodology Pitfalls 2nd Quant 强调

### Pitfall 1 — Overfitting search space
- 5-7 lever × 3-5 variant = lucky architecture risk on 26y sample
- 解法: hypothesis-driven candidates, 最多 3-4 个 architecture, 每个 ≤ 5 个 lever 变动

### Pitfall 2 — Live/backtest gap
- 这是 Round 2 核心问题
- 许多策略 backtest ROE 低，live friction 折损后可能直接负
- P1 必须并列输出: backtest ROE + friction-adj ROE + live-observed (where available)

### Pitfall 3 — Idle BP fallback = tail leverage trap (关键)
- 看到 idle 62% 加 short-premium fallback → stress 前账户填满 → 真机会来无 BP / tail 叠加
- **Lever C 必须分两层**:
  - **C1**: low-risk idle cash yield / T-bill (low-risk ROE filler)
  - **C2**: option-premium idle deployment (real strategy risk)
- 不混在一起

### Pitfall 4 — 多账户不是简单合并 NLV
- Schwab + E-Trade margin / product / API / PM rules 可能不同
- D lever 必须先建: account-specific margin model + product eligibility + execution friction

### Pitfall 5 — Forward sample 几乎为 0
- Q042 / HV Ladder / R1-R6 都新东西
- 26y replay 有用，但 live evidence 几乎没有
- P5 结论必须分: production-ready / paper-ready / shadow-only / research-only

---

## Tear-down 边界 (2nd Quant 三层分类)

| 层 | 内容 | 可动度 |
|---|---|---|
| 不可动 | R1-R6 governance 框架的**理念** (risk vetoes / no naked tail / manual override SOP) | 仅 P0 明确批准 |
| 可调整 | strategy target sizing, capital budget, account split, idle BP usage, cap **数值**, active/paper/shadow 分类, HV Ladder deployment size | 默认 Q073 scope |
| 仅 Radical 可动 | strategy matrix axes, new primitives, new underlyings, macro overlays, ML/Bayesian | 仅 Arch-3 候选 |

R1-R6 **数值** 可以测，但 **理念**不可动。

---

## Revised P0-P5 (2nd Quant 版本)

### P0 — Define objective and constraints
- Primary ROE denominator (combined NLV)
- Risk veto (MaxDD ≤ 25-30%, rolling 20d/3m bounds, stress, bootstrap)
- Cash yield baseline (T-bill 4-5%)
- Allowed tear-down level (3 档)
- Promotion standard (4 档)
- Minimum evidence standard

### P1 — Current architecture truth table (扩展版)
- combined portfolio ROE (annual + rolling)
- friction-adjusted ROE
- cash-adjusted total account return
- BP utilization distribution + idle reason attribution
- **Strategy role map** (core/opportunistic/hedge/permission/filler/paper)
- strategy contribution + $/BP-day
- crisis windows (full architecture)
- account-level margin usage
- live readiness state + paper vs production distinction

### P2 — Capital architecture levers first (三步走)
P2A: **Capital utilization levers** — C (idle BP, 分 C1/C2) + D (account split) + F (sizing/budget)
P2B: **Risk governance levers** — B (cap **数值**, 不动理念)
P2C: **Strategy-set levers** — A (matrix) + G (retire/simplify)

先跑 P2A，再决定是否值得 P2B/P2C。

### P3 — Build 3 candidate architectures
- **Arch-0**: Current baseline
- **Arch-1 Conservative**: capital / account / sizing 改动 only, no new strategy
- **Arch-2 Moderate**: + idle BP fallback or strategy budget reallocation
- **Arch-3 Radical**: + strategy matrix redesign / retire / add primitives

### P4 — Full simulation / stress / walk-forward
- gross ROE
- friction-adjusted ROE
- stress-adjusted ROE
- walk-forward / split sample
- 2008 / 2020 / 2022 synthetic on current architecture
- account-specific margin
- correlated model error stress

### P5 — Decision (5 档输出)
implement now / paper trade / shadow monitor / defer / reject

---

## 优先级 (P0-P2 budget limited case)

如果只够跑 P0-P2，按这个顺序：

| Pri | Lever | 理由 |
|---|---|---|
| 1 | **P1 Current State** | 没有 baseline 不可能优化 |
| 2 | **C Idle BP** | 最大 ROE upside，但要先分 C1/C2 |
| 3 | **D Multi-account** | 低风险，BP 利用率提升 |
| 4 | **F Sizing / capital budget** | 比 cap 数值更重要 |
| 5 | **B Cap framework** | Q072 刚做过，重点 R1-R6 是否过紧/松 |
| 6 | **A Strategy matrix** | 最后做，先看 capital 是否能解决 ROE gap |
| 7 | **E Friction** | 不是独立 lever，是 P1 baseline adjustment |

注: **G (retire/simplify) 与 A 并列在 P2C**, 因为都涉及 strategy-set 改动。
