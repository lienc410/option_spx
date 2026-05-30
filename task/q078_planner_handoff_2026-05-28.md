# Q078 → SPEC-108 Planner Handoff

**From**: Quant Researcher
**To**: Planner
**Date**: 2026-05-28
**Purpose**: 索引层归档 Q078 研究闭合 + SPEC-108 APPROVED 状态

---

## 1. 单句摘要

Q078 BPS Ladder 研究 **CLOSED**；产物 **SPEC-108 APPROVED**（PM 2026-05-28 签字），等 Developer 实施 → Quant fidelity review → DONE。

---

## 2. 研究路径概览

```
Q078 framing → P0 anchored memo → P1a cadence attribution
  → G2 PASS
  → P1b-1 model corrections → P1b-2 sizing sweep
  → G2.5 PASS
  → P2 (eff_count fix) → P2 REVISED (daily MTM smoothing)
  → P3 (crisis + walk-forward + bias) → G4 REVISE
  → P4 portfolio integration
  → G4 PASS w/ 9 revisions R1-R9
  → SPEC-108 DRAFT
  → Comprehensive Audit
  → AUDIT PASS w/ 7 micro-revisions R1-R7
  → PM APPROVE 2026-05-28 ✅
```

11 phases / 2 days / 5 G-reviews / 16 task documents.

---

## 3. 核心研究结论（写进 RESEARCH_LOG 用）

**Topic**: 是否系统化 SPX 入仓节奏（"ladder"）能改善 portfolio 表现

**Findings**:
1. **V3 daily-cluster cadence + S3 sizing** （≤1 entry per 5-trading-day cluster, 3 contracts ≈ 7.5% BP）相对 SPEC-104 + SPEC-105 v2 baseline 产生：
   - Ann ROE: 8.21% → 10.02%（**+1.80pp mean**, CI [+1.61, +1.97]）
   - MaxDD: -8.71% → -7.40% (**+1.32pp IMPROVED**)
   - W20d: -7.04% → -5.88% (**+1.16pp IMPROVED**)
   - W63d: -8.66% → -5.06% (**+3.59pp IMPROVED**)
   - Sharpe: 2.02 → 3.21 (**+1.20**)
   - 5/5 crisis windows improved（含 COVID — combined REDUCES baseline COVID loss by +$15k）
2. **Bias-deflated 现实区间**: P4 mean +1.80pp 但残余 selection bias 未完全解决，realistic ΔROE ≈ **+0.8 到 +1.3pp**。这正是 Stage 1 shadow 强制存在的原因。
3. **Thesis 校正**: Q078 **不**解决 expiry concentration（PM 最初观察的"8 spreads at 6/18 expiry"症状未被治愈，eff_count Δ noise）。Q078 实际价值是 **ROE-cadence overlay** —— 系统化捕获 selector-PASS 机会。PM-facing 语言禁用"diversification"措辞。
4. **V1b weekly catch-up** 在 portfolio 层与 V3 差异 < 0.5pp（全部 noise threshold 之下）；PM 选 V3 因下游测试已基于 V3，V1b 仅保留为文档化备选（明令 Developer 禁止实施）。

**Risks / Counterarguments**:
- 残余 selection bias 未完全消除（用 Option B / Stage-1 shadow 路径管理，而非 engine-without-filters）
- Live shadow 数据可能与 P4 假设不符 → Stage 2 advancement gate 7 条款 + ≥10 shadow entries 兜底
- 操作负担 ~35 action days/yr + 每日 selector check，PM 接受

**Confidence**: G4 PASS + Audit PASS，两轮独立 reviewer 通过

**Next Tests**: 由 Stage 1 shadow live data 提供（per SPEC §5 monitoring obligations）

**Recommendation**: `enter Spec` — 已落地为 SPEC-108 APPROVED

---

## 4. SPEC-108 状态

| 字段 | 值 |
|---|---|
| SPEC ID | SPEC-108 |
| Title | Selector-Gated SPX Execution Ladder |
| Status | **APPROVED** (PM signed 2026-05-28) |
| Parent SPECs (UNCHANGED) | SPEC-104 Arch-3, SPEC-105 v2 Gate F, SPEC-077 exits, SPEC-103 vetoes |
| 实施工作量 | ~5h (CC+gstack workflow) / ~4 工作日 (人) |
| Stage 1 默认 | shadow-only, MANDATORY |
| Stage 2 advancement | PM signoff + ≥10 shadow entries + 7 advancement conditions |
| ACs | 18 (含 R3 audit 强制的 AC-108-17/18 CI tests) |
| Monitoring obligations | 8 (含 R1 audit 加的 ladder-only W20d/W63d incremental tail) |

---

## 5. 关键产物（文件路径）

### Research 详细层
```
research/q078/q078_framing_memo_2026-05-27.md
research/q078/q078_p0_anchored_memo_2026-05-27.md
research/q078/q078_p1a_memo.md
research/q078/q078_p1b_1_memo.md
research/q078/q078_p1b_2_memo.md
research/q078/q078_p2r_memo.md         ← REVISED 版（daily MTM smoothing fix）
research/q078/q078_p3_memo.md
research/q078/q078_p4_memo.md          ← decision-grade portfolio integration
research/q078/q078_p4_portfolio_integration.py  ← 主脚本（含 V1b vs V3 bonus）
```

### G-review 文件（task/）
```
task/q078_framing_2nd_quant_review_2026-05-27_Review.md          ← framing PASS
task/q078_p1a_g2_2nd_quant_review_2026-05-27_Review.md           ← G2 PASS
task/q078_p1b_g2_5_2nd_quant_review_2026-05-28_Review.md         ← G2.5 PASS
task/q078_p3_g4_2nd_quant_review_2026-05-28_Review.md            ← G4 REVISE
task/q078_p4_g4_resubmit_2026-05-28.md                           ← P4 resubmit packet
task/q078_p4_g4_resubmit_2026-05-28_Review.md                    ← G4 PASS w/ 9 revisions
task/q078_spec108_comprehensive_audit_packet_2026-05-28.md       ← audit packet
task/q078_spec108_comprehensive_audit_2026-05-28_Review.md       ← AUDIT PASS w/ R1-R7
```

### SPEC + Handoff
```
task/SPEC-108.md                       ← APPROVED, 单一 source of truth
task/q078_planner_handoff_2026-05-28.md  ← 本文档
```

### 新 Feedback memory
```
~/.claude/.../memory/feedback_noise_threshold.md  ← 新建：< 0.5pp = noise framework
```

---

## 6. PROJECT_STATUS.md 索引项（建议条目）

```markdown
- `SPEC-108` — Q078 Selector-Gated SPX Execution Ladder. **APPROVED 2026-05-28.**
  Q078 全 P0-P4 + 5 轮 G-review + 综合 audit (R1-R9 + R1-R7 全部应用)。
  ROE-cadence overlay on SPEC-104+105v2 baseline: V3 daily-cluster (≤1 entry per
  5-trading-day cluster, ~35 action days/year) + S3 sizing (3 contracts ≈ 7.5%
  BP). Strategy-agnostic (selector-provided per VIX regime). Expected impact:
  ROE +1.80pp mean (bias-deflated realistic +0.8 to +1.3pp), MaxDD +1.32pp,
  W20d +1.16pp, W63d +3.59pp, Sharpe +1.20. 5/5 crisis windows improved (incl
  COVID). Stage 1 shadow-only MANDATORY; Stage 2 PM-signoff + ≥10 shadow
  entries. NOT a diversification fix (eff_count Δ noise). 18 ACs incl
  AC-108-17/18 CI tests for shadow-default safety. Pending Developer
  implementation (CC+gstack ~5h). — See: task/SPEC-108.md,
  research/q078/q078_p4_memo.md
```

---

## 7. RESEARCH_LOG.md 条目（建议）

```markdown
## Q078 — BPS Ladder / SPX Execution Cadence (CLOSED 2026-05-28)

**Question**: 是否系统化 SPX 入仓节奏能改善 portfolio 表现？

**Outcome**: `enter Spec` → SPEC-108 APPROVED

**Key finding**: ROE-cadence overlay 价值确认（+0.8 到 +1.3pp deflated），但 **不解决**
原始 expiry concentration 症状。Thesis reframed: "ROE-cadence overlay, NOT
diversification fix."

**Lessons (memory-worthy)**:
1. **Noise threshold < 0.5pp** framework — 已新建 feedback memory，未来策略比较
   通用
2. **Eff_count 度量陷阱** — grouped by exit_date 把每个交易日当独立 expiry，过
   度估计 diversification benefit ~200-800x；正确做法 group by monthly expiry
   bucket
3. **Daily MTM aggregation** — single-day exit spike 会扭曲 W20d/W63d，必须 linear
   distribute across hold days
4. **Bias correction Option B path** — Stage-1 shadow 作为 bias resolution，比 engine-
   without-filters 更务实（PM-acceptable）
5. **2-axis stratified bootstrap** (strategy × year × VIX bucket) — 不是完美但务实
6. **V1b vs V3 portfolio-level 差异 < noise** — sub-noise 决策由操作负担/下游研
   究基准决定，不强求最优

**Detailed artifacts**: research/q078/q078_p4_memo.md（decision-grade）+
task/q078_p4_g4_resubmit_2026-05-28_Review.md（G4 PASS verdict）
```

---

## 8. 待办 / 当前状态

| 项 | 状态 |
|---|---|
| Q078 research line | ✅ CLOSED |
| SPEC-108 DRAFT | ✅ DONE |
| 2nd Quant comprehensive audit | ✅ PASS w/ R1-R7 applied |
| PM approval | ✅ 2026-05-28 |
| Developer prompt 准备 | ✅ 已生成（PM 持有，未存档为文件） |
| **Developer 实施** | ⏳ **PENDING** — PM 即将启动 |
| Quant fidelity review (post-PR) | ⏳ PENDING — Developer 完成后做 |
| SPEC-108 Status → DONE | ⏳ PENDING — Quant review PASS 后 |
| PROJECT_STATUS.md 索引更新 | ⏳ **本次 Planner 动作** |
| RESEARCH_LOG.md Q078 closure | ⏳ **本次 Planner 动作** |

---

## 9. Planner 建议动作

1. **更新 PROJECT_STATUS.md** — 加 SPEC-108 索引条（§6 模板）；如有 Q078 候选条则标 CLOSED
2. **更新 RESEARCH_LOG.md** — 加 Q078 closure 条（§7 模板）；含 6 条 memory-worthy lessons
3. **不要重写**详细层文档（research/q078/ 已完整；task/ G-review 已完整）；Planner 只做索引层
4. **追踪 standing obligations**（待 Developer 完成后才激活）：
   - Stage 1 shadow 数据收集启动（≥10 entries before Stage 2 gate）
   - §5 8 项 monitoring obligations 进入月度 review checklist
5. **暂不操作**：FE Batch 2/3 audit、Q042 ddATH watch、SPEC-105 v2 Stage 1 monitoring 这些 standing 项不归本次 handoff，但 Planner 应在本次更新中确认它们仍 active

---

## 10. 给 PM 的快速 status sentence

> Q078 研究链路 CLOSED，SPEC-108 APPROVED 2026-05-28，等 Developer 实施 V3 daily-cluster ladder + Stage 1 shadow 部署。

---

## Quant 签字

- [x] Q078 研究闭合无遗留 blocker
- [x] SPEC-108 APPROVED + handoff package 完备
- [x] Planner handoff 文档完整
- [x] 等 Developer 实施 + 后续 fidelity review

→ Planner 可立即归档；研究历史不再修改。
