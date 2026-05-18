# Q073 P0 — Anchored Objectives Memo

**Date**: 2026-05-17
**Status**: **SIGNED 2026-05-17** — three-party sign-off complete (PM + Quant + 2nd Quant CONDITIONAL PASS → 5 revisions applied → full PASS)
**Parent**: `task/q073_roe_round2_framing_2nd_quant_review_packet_2026-05-17.md` + Review (PASS WITH MAJOR REVISIONS)
**Project name**: Round 2 ROE Optimization — Risk-constrained portfolio ROE under current multi-strategy, multi-account architecture

---

## 0. Framing (2nd Quant final answer 锚定)

> **Risk-constrained portfolio ROE optimization under current multi-strategy, multi-account architecture.**
>
> 不是单纯找更高 ROE。ROE 是目标函数，drawdown / CVaR / stress / governance 是 hard veto，不是同等排名项。

**研究顺序铁律 (2nd Quant Final Answer)**:

```
P1 current architecture measurement
  ↓
P2A capital deployment levers (idle BP / 账户分工 / sizing)
  ↓
P2B cap framework numeric sensitivity
  ↓
P2C strategy-set 改动 (matrix redesign / retire) ← 最后做，且仅 Arch-3
```

**先跑 current architecture measurement 和 capital deployment levers，不要一开始就重构策略矩阵。**

## 0.1 三方锚定项

| 锚定项 | 决策 | 来源 |
|---|---|---|
| **Primary objective** | **Risk-constrained** combined account-level ann ROE max — ROE 是目标函数, V1-V7 vetoes 是 hard floor | PM 2026-05-17 + 2nd Quant Final |
| **Stretch goal** | **20% ann ROE** on combined NLV $894k — **aspirational, NOT a required feasibility threshold; not Q073 failure line** | PM 2026-05-17 + 2nd Quant P0 review |
| **Success floor** | **8% ann ROE** — Q073 minimum success floor under current strategy menu. P5 必须证明该 floor 可达且 V1-V5 全 pass | PM 2026-05-17 (选项 1) + 2nd Quant P0 review |
| **Cash yield baseline** | **~4.3%** (BOXX proxy, ~1-3M T-bill equivalent) | PM 2026-05-17 (PM verify trailing 12m) |
| **Tear-down level** | **激进** — Lever A/G 解锁, BUT 仅在 P2A 资本 lever 证明无法关 ROE gap 后才进入 P2C | PM 2026-05-17 + 2nd Quant 顺序约束 |
| **Promotion 4 档** | production-ready / paper-ready / shadow-only / research-only | 2nd Quant 框架 |
| **Methodology** | Hypothesis-driven (3-4 Arch candidates), NOT brute-force grid | 2nd Quant Pitfall 1 |
| **P2 顺序** | **P2A capital first → P2B cap → P2C strategy set last** (不可逆顺序) | 2nd Quant Final Answer |

---

## 1. ROE Definition (避免 numerator/denominator 歧义) — 修订 per 2nd Quant P0 review

```
Primary ROE         = annualized strategy PnL / combined NLV  ($894k baseline)
Cash baseline       = BOXX / 1-3M T-bill proxy, currently ~4.3%
Excess ROE over cash = Primary ROE − cash baseline   (used to judge income-engine viability)
Total Account Return = strategy PnL + cash yield on idle capital
                      (separately reported when idle cash actually earns interest)
Efficiency metric    = $/BP-day   (cross-strategy comparison, not top objective)
```

Stretch / Floor 都是 **Primary ROE** 维度。

**重要区分**:
- **Primary ROE** = 策略本身年化（不含闲置现金利息）
- **Excess ROE over cash** = Primary ROE − 4.3% baseline。任何策略 net-of-friction 低于 baseline 不能作为 income engine（per 2nd Quant Blind Spot 2）
- **Total Account Return** = Primary ROE + 闲置现金实际利息收益。**这才是 PM 看的"账户总年化"**

P1 deliverable 必须**分开报**这三个数字，避免 idle BP 讨论时混淆。

---

## 2. Risk Vetoes — 两层结构 (per 2nd Quant P0 review)

### 2.1 Hard Risk Vetoes (V1-V5) — 任何一条 fail 直接淘汰 architecture

```
V1  Max drawdown                  ≤ 28%   combined NLV   ($894k → 最低 $644k)
V2  Worst rolling 20-day loss     ≤ 11%   combined NLV   (~$98k / month)
V3  Worst rolling 3-month loss    ≤ 17%   combined NLV   (~$152k / 3-month)
V4  Peak combined BP / stress BP  ≤ governance caps (R1-R6 SPEC-103)
V5  Synthetic 2008 / 2020 / 2022  no path breach
```

V1-V3: PM 已锁定 2026-05-17。

### 2.2 Promotion-Level Evidence Gates (V6-V7) — 控制 promotion 级别，不是普通淘汰

```
V6  Bootstrap sig_rate ≥ 80%   (block=250, 20 seeds, per Q071 method)
    → Required for production-ready promotion.
    → If <80%, architecture CAN still be paper-ready or shadow-only.
    → Not applicable to hedge / permission / idle-filler modules (no standalone significance).

V7  Walk-forward stability  ≥ 0.5 Spearman   (per Q072 P3 method)
    → Required for production-ready promotion WHEN architecture uses learned/optimized allocators.
    → If no learned allocator (e.g., fixed rule-based architecture), use split-sample robustness instead.
```

**重要**: V6/V7 不再是普通 hard veto。一个 architecture 风险显著降低但 bootstrap sig 不达 80%，**不应自动淘汰**，可降级为 paper / shadow。

**PM 风险定位**: 28% MaxDD = 2008 GFC 级 (-55%) 灾难下"略低于大盘" / 2020 COVID (-34%) "明显好于大盘" / 2022 (-25%) "略好于大盘"。Sharpe 必须显著高于 buy-hold。

---

## 3. 数学张力 (PM 已 acknowledged 选项 1)

Stretch goal **20% ann ROE** vs Risk veto **MaxDD ≤ 28%** in current strategy menu (最高单策略 Sharpe = 0.34 HV Ladder) 通常需要组合 Sharpe ≥ 1.0+ 才可达。

PM 选了选项 1：**接受 20% 是 stretch，actual 6-12% 也 OK，floor 8%**。Q073 任务：
- 找到能达到 Floor (≥ 8%) 同时 V1-V7 全 pass 的 architecture (necessary condition)
- 在所有 V1-V7 pass 的 architecture 中找 ROE 最大的 (stretch optimization)
- P5 narrative: "Stretch 20% / Floor 8% / Achieved X%"，X 由实证决定

---

## 4. Lever Space (2nd Quant 重排版)

| Lever | 内容 | Priority |
|---|---|---|
| **C1** | Idle BP fallback — low-risk (T-bill / BOXX / cash equivalent) | 1 |
| **C2** | Idle BP fallback — option-premium deployment | 2 |
| **D** | Multi-account allocation (Schwab + E-Trade) — 必须先建 **account-specific margin model + product eligibility + execution friction** (per 2nd Quant Pitfall 4) | 3 |
| **F** | Strategy sizing / capital budget hierarchy | 4 |
| **B** | Cap framework R1-R6 数值 (理念不动) | 5 |
| **A** | Strategy matrix redesign (radical only) | 6 |
| **G** | Strategy retire / simplify / role demotion | 7 |
| **E** | Friction / execution layer (mandatory P1 baseline adj, NOT 独立 lever) | P1 |

**P2A 先**: C1 + C2 + D + F (capital utilization, 低 risk 高 ROE upside)
**P2B 后**: B (cap 数值)
**P2C 最后**: A + G (strategy set 改动)

**Note (per 2nd Quant)**: G (retire candidates) **在 P1 role map 里就先 identify**，但 actioned 在 P2C。即 P1 可标 "demotion candidate" 但不动结构。

P1 baseline adjustment **must include** friction (where available data). 缺数据策略 (HV Ladder live=0, Q042 paper) 显式标 N/A, 不假设。

---

## 5. Tear-down Boundary (三层)

| 层 | 内容 | Q073 处理 |
|---|---|---|
| **不可动** | R1-R6 governance **理念** (risk vetoes / no naked tail / manual override SOP) | Hard constraint, not modeled |
| **可调** | strategy target sizing, capital budget, account split, idle BP usage, cap **数值**, active/paper/shadow 分类, HV Ladder deployment size | P2A + P2B scope |
| **激进解锁** | strategy matrix axes, new primitives, retire candidates, role re-classification | P2C scope (only for Arch-3) |

**Retire 候选** (实际可动) — 必须按 **role** 评价，不按 standalone alpha (per 2nd Quant P0 review):

- ✅ Q019 Signal 2 sidecar — 评价标准: 6mo A/B 实证价值是否值得继续占认知资源
- ✅ V3-A Aftermath — **修订**: Q064 结论是 V3-A 价值是 permission/bypass alpha 而非 structural alpha。**P1 评价必须基于 permission/bypass 角色 marginal contribution, 而非 standalone sleeve ROE**。不要错把"低 standalone PnL"当作 retire 依据
- ✅ LOW_VOL 默认 reduce_wait (replace by income strategy)
- ✅ IVP gate triggered reduce_wait period (replace by alternative)
- ❌ HV Ladder (刚 deploy, 不动)
- ❌ Q042 (paper 期未结, 不动)
- ❌ SPX BPS main (核心 income engine, 可调参数 not retire)

**Role-based 评价铁律** (适用所有 retire 候选): hedge / permission / idle-filler / opportunistic 类模块必须按对应 role 的边际贡献评价，不按 standalone PnL 排名。

---

## 6. Out of Scope (避免 scope creep, 2nd Quant 明确 reject)

- 新标的 (RUT / SPY / IWM / NDX) — 进 future Q074+
- 新 option 结构 (butterflies / calendars / diagonals / ratios)
- Macro overlay (Fed / jobs / VIX-futures term structure)
- ML / Bayesian tail model
- Tax-aware optimization
- Real-time intraday strategy (SPEC-030 已 reject)
- Q072 已 reject variants (priority allocator / static per-sleeve cap)

---

## 7. P1-P5 Plan (2nd Quant 修订版)

| Phase | 内容 | Output |
|---|---|---|
| **P0** | (本 memo) Three-party anchored objectives | sign-off |
| **P1** | Current architecture truth table + role map + friction adj + **idle BP decomposition by reason** + **operational ROE score** + **ROE bridge (cash baseline → each strategy contribution → friction → total account ROE)** (per 2nd Quant P0 review) | `q073_p1_baseline.csv` + `q073_p1_role_map.md` + `q073_p1_operational_score.md` + `q073_p1_roe_bridge.md` + `q073_p1_idle_attribution.md` |
| **P2A** | Capital utilization levers: C1 / C2 / D / F sensitivity | `q073_p2a_results.csv` |
| **P2B** | Cap framework B 数值 sensitivity (lightweight, Q072 已 cover 多数) | `q073_p2b_results.csv` |
| **P2C** | Strategy set A / G hypothesis-driven candidates | `q073_p2c_candidates.md` |
| **P3** | Build 3 Architectures: Arch-0 (baseline) / Arch-1 (conservative, capital only) / Arch-2 (moderate, + idle fallback) / Arch-3 (radical, + matrix) | `q073_p3_arch_specs.md` |
| **P4** | Full 26y simulation + friction-adj + stress + walk-forward + correlated model error | `q073_p4_results.csv` + crisis tables |
| **P5** | Promote / Paper / Shadow / Defer / Reject + SPEC drafts | `q073_final_memo.md` + 2nd Quant review |

---

## 8. Stopping Conditions (early exit gates)

| Phase | Stop if … |
|---|---|
| **P1** | Current architecture combined ROE 已 ≥ 8% floor AND V1-V7 全 pass → "current is fine, don't tear down" → close Q073 |
| **P2A** | **修订 per 2nd Quant**: 单独 lever Δ ROE < +0.5pp **AND** 低风险 lever 组合 (C1+D+F) 也无 ≥ +1.0pp ROE plausible 提升 → capital layer low-upside, 继续 P2B/C 评估其他路径 |
| **P2B** | Cap 数值 sensitivity 无 Δ ROE ≥ +0.3pp → confirm Q072 caps already optimal |
| **P2C** | No retire/replace candidate produces ROE ≥ Floor 8% AND V1-V7 pass → architecture redesign infeasible, conclude Arch-3 not viable |
| **P3** | No Arch passes Floor + all vetoes → Q073 ends with "ROE Floor 8% infeasible under current strategy menu; further upside requires new strategy primitives (out-of-scope)" |
| **P4** | Walk-forward Spearman < 0.5 → architecture overfit, retreat to Arch-0 |

---

## 9. Mid-Review Gates

| Gate | Trigger | Reviewer |
|---|---|---|
| **G1 P0 sign-off** | This memo signed | PM + Quant + 2nd Quant |
| **G2 P1 attribution review** | P1 outputs ready | PM (decision) + Quant + 2nd Quant (light review) |
| **G3 P3 architecture review** | 3 Arch candidates defined, before P4 full simulation | **2nd Quant mid-review** (mandatory, per Q071/Q072 precedent) |
| **G4 P5 final review** | Promote/Reject decision | **2nd Quant final review** (mandatory) |

G3 必要的原因: Arch-3 radical 候选可能涉及 retire 现有 strategy + add new matrix cell。这是不可逆的研究方向, 必须 2nd Quant audit 后才进 P4 full simulation (P4 是 compute heavy)。

---

## 10. Estimated Effort

| Phase | Quant time | 2nd Quant time | Wall clock |
|---|---|---|---|
| P0 sign-off | 完成 (此 memo) | 1 day | 1 day |
| P1 measurement | 2-3 days | 0.5 day (G2 light) | 3-4 days |
| P2A | 1-2 days | — | 1-2 days |
| P2B | 0.5 day | — | 0.5 day |
| P2C | 1-2 days | — | 1-2 days |
| P3 + G3 mid-review | 1 day + 1 day review | 1 day | 2 days |
| P4 full sim | 2-3 days | — | 2-3 days |
| P5 + G4 final | 1 day + 2 day review | 2 days | 3-4 days |
| **Total** | **~10-13 days Quant** | **~4 days 2nd Quant** | **~2-3 weeks wall** |

---

## 11. Three-Party Sign-Off

### PM Sign-off (锚定 ROE 目标 + cash baseline + tear-down level)
- [x] Primary stretch 20% / floor 8% confirmed (2026-05-17)
- [x] Cash baseline ~4.3% BOXX (PM may verify trailing 12m from broker; 1pp 内不重锚)
- [x] Tear-down 激进 confirmed (2026-05-17)
- [x] V1-V7 数字: V1=**28%** / V2=**11%** / V3=**17%** (2026-05-17, 采纳 Quant 推荐)

### Quant Researcher (我) Sign-off
- [x] Methodology 接受
- [x] Lever priority 接受
- [x] Tear-down boundary 接受
- [x] Stopping condition 接受
- [x] Mid-review gate 接受

### 2nd Quant Sign-off (P0 final review 2026-05-17) — CONDITIONAL PASS → after 5 revisions → PASS
- [x] P0 锚定项 acceptable
- [x] V1-V5 hard veto acceptable (V6/V7 转 promotion-level evidence gate, 已修订 §2.2)
- [x] P1-P5 plan acceptable (修订版)
- [x] Stopping condition acceptable (P2A wording 已修订 per 2nd Quant)
- [x] G3 / G4 mid+final review scope acceptable
- [x] ROE 术语已改 "Excess ROE over cash" + 分开报 Total Account Return
- [x] 20% stretch / 8% floor 含义已明示 (stretch 非 failure line / floor 是 success line)
- [x] Aftermath retire 措辞改为 "按 permission/bypass role 评价"
- [x] P1 加 ROE bridge + idle BP decomposition by reason

---

## 12. References

- `task/q073_roe_round2_framing_2nd_quant_review_packet_2026-05-17.md` (Quant 起的 framing packet)
- `task/q073_roe_round2_framing_2nd_quant_review_packet_2026-05-17_Review.md` (2nd Quant verdict + 修订)
- `research/q071/q071_memo_2026-05-14.md` (HV Ladder promote, Round 2 重要 input)
- `research/q072/q072_final_memo_2026-05-15.md` (Sleeve Governance, R1-R6 framework)
- `PROJECT_STATUS.md` (current architecture state)
- `MEMORY.md` (operational feedback, especially `feedback_no_param_mirror_docs.md`)
