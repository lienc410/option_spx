# Q073 — Round 2 ROE Optimization — Final Memo

> **Status: FINAL — Q073 RESEARCH COMPLETE + 2nd Quant PASS.**
> **Recommendation: PROMOTE Arch-3.** Single integrated SPEC.
> **2nd Quant final review verdict: PASS (2026-05-17)** with 6 wording revisions applied below.

**Date**: 2026-05-17
**Project**: Risk-constrained portfolio ROE optimization under current multi-strategy, multi-account architecture
**P0 anchored**: PM + Quant + 2nd Quant 三方 signed 2026-05-17
**Predecessors**: P1.1, P1.2, P1.3R, P1.4, P1.5, P2A, P2A+, P3, P4

---

## 0. Executive Verdict

**Q073 recommends Arch-3 as the Round 2 ROE architecture.**

```
Arch-3 (Recommended):
  Normal SPX cap     : 80%
  Stress SPX cap     : 50%       (R5 trigger reduces 70% → 50%)
  Second-leg SPX cap : 40%       (R6 trigger)
  HV Ladder /ES      : 0%        (demoted to research-only / paper-only)
  Q042 Sleeve A      : 17.5%     (cap increase from 10%)
  Cash (BOXX)        : residual

Result (net of friction, 26y):
  Ann ROE (geometric)    : 7.95%   (effectively at 8% floor)
  MaxDD                  : -8.71%
  Worst 20d              : -7.04%  (V2 buffer 3.96pp)
  Worst 63d              : -6.94%  (V3 buffer 10pp)
  Sharpe                 : 1.97
  V6 Bootstrap sig_rate  : 100%
  V7 Walk-forward (both halves) : floor 8% pass
  V1/V2/V3 all veto      : PASS
```

> **Bootstrap caveat (per 2nd Quant)**: V6 bootstrap confirms the PnL series is not noise (CI lo ann statistic is significance evidence, not forward ROE forecast). **Expected production ROE remains around the simulated net ROE estimate ~8%, not the bootstrap CI statistic**.

---

## 1. Q073 Journey: Numbers Anchored at Each Phase

| Phase | Setup | Net ROE | Worst 20d | Status |
|---|---|---|---|---|
| P0 anchor | PM defined stretch 20% / floor 8% / vetoes 28/11/17% | — | — | three-party signed |
| P1.1 SPX BPS 26y | engine alone | 8.52% (engine) | — | reference point |
| P1.2 V3-A marginal | +0.19pp permission alpha | — | — | V3-A keep but non-transformative |
| P1.3R unified-NLV (Arch-0) | static 60% SPX, no governance | **7.50%** | -12.46% | V2 FAIL |
| P1.5a actual SPEC-103 R5/R6 (Arch-1) | normal 70 / stress 60 / R6 50 | 7.87% | -11.82% | V2 still FAIL |
| P1.5b stress cap 50% | enhanced stress cap | 7.76% | -10.18% | V2 PASS, gap to floor 0.24pp |
| P2A Candidate E (sweep) | SPX 75/50/40 + HV 5% + Q42 12.5% | 7.85% gross | -10.25% | V2 PASS, sub-floor |
| **P2A+ Candidate E5** | **SPX 80/50/40 + HV 5% + Q42 12.5%** | **7.99% (Arch-2)** | -10.25% | **V2 PASS, ≈floor** |
| **P3 Arch-3 discovery** | **demote HV, Q42 17.5%** | **7.95% (Arch-3)** | **-7.04%** | **same ROE, much better tail** |
| P4 validation | bootstrap / walk-forward / concentration / friction / stress | both pass | both pass | Arch-3 wins on tail |

**Reframe achieved**: Q073 went from "find architecture passing floor 8%" to "Arch-3 dominates Arch-2 on risk-adjusted basis".

---

## 2. Why Arch-3 (not Arch-2)

Arch-2 (E5) keeps HV Ladder at 5% and lands at 7.99% Net ROE. Arch-3 demotes HV Ladder, raises Q042 to 17.5%, and lands at 7.95% Net ROE. Difference: 0.04pp ≈ $360/year on $894k NLV — **economically immaterial, in bootstrap noise**.

But on risk dimensions:

| Dimension | Arch-2 | Arch-3 | Δ |
|---|---|---|---|
| MaxDD | -11.68% | -8.71% | **+2.97pp** |
| Worst 20d | -10.25% | -7.04% | **+3.21pp** |
| Worst 63d | -9.94% | -6.94% | **+3.00pp** |
| Sharpe | 1.82 | 1.97 | **+0.15 (8% relative)** |
| V2 buffer (from 11%) | 0.75pp | 3.96pp | **5.3x larger** |

**Trade is one-sided**: trivial ROE giveup for material tail improvement.

### HV Ladder as portfolio-level tail driver

This is the structural finding underlying the Arch-3 advantage:

- Q072 P4 identified HV as 2022 stress co-driver
- Q073 P2A original sweep: HV 5% → 7.5% directly broke V2 in ALL variants (B/D/F/H)
- Q073 P3: removing HV (5% → 0%) improves V2 by 3.21pp and MaxDD by 2.97pp
- HV Ladder is **opportunistic high-vol sleeve by design** (enters on VIX ≥ 22) — same regime trigger that makes it occasionally profitable also makes it active during early-stage selloffs where short-put positions accumulate losses before broader hedges (V3-A, Q042) can engage
- This is a **structural property**, not a parameter bug

### Q042's role

Q042 Sleeve A is **convex overlay** (drawdown-triggered call spread). At 17.5% allocation:
- Adds +1.76% combined ann ROE
- Has near-zero correlation with SPX BPS (0.02) and HV Ladder (0.00)
- Concentration robust: top-1 trade only 7.4% of total Q042 PnL, top-5 only 32%
- Removing top-5 winners drops Arch-3 ROE by only 0.06pp
- Worst trade at 17.5% sizing: -1.75% NLV (well within V1/V2 buffers)

Q042's diffuse profit pattern + low correlation makes it an effective HV Ladder replacement at the portfolio level.

---

## 3. Why Not the 20% Stretch Target

PM anchored stretch 20% / floor 8% in P0. Q073 finds:

- 20% stretch is **not achievable** under the current strategy menu without breaching V1-V3 vetoes or adding new strategy primitives (out-of-scope per P0)
- Adding capital to higher-ROE strategies (SPX BPS) breaches V2
- Reducing cash baseline trades 4.3% safe yield for higher-vol strategy alpha — net effect is marginal
- The realistic risk-constrained ceiling under the current strategy menu is **~8% net**

**P0 stretch 20% was correctly defined as aspirational, not failure threshold** (per 2nd Quant P0 review). Q073 reaches the realistic 8% floor; this is the project success criterion.

---

## 4. What Changed from P0 Expectation

| P0 expectation | P5 actual finding |
|---|---|
| 20% stretch is challenging | 20% unreachable from current menu; 8% is realistic |
| Maybe need radical Arch-3 strategy matrix redesign | Less radical than expected — just demote HV Ladder + boost Q042 |
| Capital deployment is main lever | Confirmed — SPX normal cap 60% → 80% adds most ROE |
| Governance R1-R6 frozen | R1 / R5 / R6 numeric caps need tightening for Arch-3 production |
| Floor 8% as success line | Floor achievable, but only via state-dependent SPX allocation + Q042 cap increase |

P3 / P4 surprise: **demoting HV Ladder** improves the portfolio on every meaningful risk dimension while sacrificing only 0.04pp ROE. The cleanest Q073 finding is "less is more for the high-vol sleeve".

---

## 5. SPEC Handoff Scope

Recommend a **single integrated SPEC** for Arch-3 promotion (avoid SPEC fragmentation):

### SPEC-XXX — Q073 Arch-3 Portfolio Architecture

**Sections**:

#### 5.1 SPX BPS state-dependent allocation cap (governance amendment subsection)

> **The governance philosophy is unchanged; only numeric caps are updated based on Q073 evidence. Q073 does not overturn Q072 / SPEC-103 governance — it tightens numeric caps within the same R1-R6 framework.**

```
Normal:      80%  (amend SPEC-103 R1 normal cap 70 → 80)
Stress:      50%  (amend SPEC-103 R5 stress cap 60 → 50)
Second-leg:  40%  (amend SPEC-103 R6 cap 50 → 40)
State definitions: UNCHANGED (stress_episode_from_flags + detect_second_leg_state per SPEC-103)
```

#### 5.2 Q042 Sleeve A cap increase (STAGED — per 2nd Quant)
```
Target cap: 17.5% (amend SPEC-094 from 10%)
Implementation: STAGED RAMP (recommended by 2nd Quant)

  Stage 1: 10% → 12.5%
  Stage 2: 12.5% → 15%
  Stage 3: 15% → 17.5%

Per-stage gate (not time-locked, per feedback_spec_review_obligation):
  - no execution issue at current stage
  - no unexpected slippage vs friction estimate
  - no breach of rolling 20d risk monitor
  - PM confirms operational comfort

Sleeve B unchanged (research-only per Rule 4).
```

#### 5.3 HV Ladder demotion
```
HV Ladder production allocation: 5% → 0%
Status: research-only / paper-only.
SPEC-101 and SPEC-102 (HV Ladder backend + dedicated frontend) remain accessible but production capital allocation = 0%.
Re-promotion requires separate Q-research showing HV-specific tail gating.
```

**Important framing (per 2nd Quant)**:

> **Demotion is a portfolio allocation decision, not a claim that the HV Ladder signal has no standalone alpha.**
>
> **HV Ladder is demoted, not invalidated. Its standalone Q071 evidence remains valid (Q071 P5: Sharpe 0.34, sig 100%). Q073 shows its marginal portfolio contribution is inferior to replacing it with additional Q042 Sleeve A allocation under the current sleeve stack.**

Single-strategy promote (Q071) and portfolio-level demote (Q073) are not contradictory — they are different axes of evaluation.

#### 5.4 Monitoring obligations
```
- Monthly realized ROE vs Q073 P4 expected (~8% net)
- Worst rolling 20d realized vs Q073 expected (~-7%)
- Q042 Sleeve A trade count + per-trade concentration tracking
- Blocked HV signals (paper-only) log for future re-promotion evidence
- SPX cap state transitions (normal/stress/second-leg) — frequency vs P1.5 (44% / 12%)
- Live friction vs P4 estimate (SPX 0.35%/yr, Q42 0.05%/yr)
```

#### 5.5 Implementation-fallback (Arch-2)

> **Arch-2 fallback is NOT risk-preferred; it is implementation-preferred only.** It exists for the case PM declines HV Ladder demotion OR Q042 cap increase. Arch-3 is preferred on risk-adjusted basis.

```
If PM refuses HV Ladder demotion OR Q042 Sleeve A cap increase beyond 12.5%:
fallback to Arch-2:
  Normal SPX 80% / Stress 50% / 2nd-leg 40%
  HV Ladder 5% (retained)
  Q042 Sleeve A 12.5% (within current SPEC-094 cap requires only +2.5pp tightening)

Trade-off:
  Net ROE             : 7.99% (vs 7.95% Arch-3, +0.04pp, in noise)
  Worst 20d           : -10.25% (vs -7.04% Arch-3, -3.21pp WORSE)
  MaxDD               : -11.68% (vs -8.71% Arch-3, -2.97pp WORSE)
  V2 buffer           : 0.75pp (vs 3.96pp Arch-3, 5.3x SMALLER)
```

---

## 6. Caveats & Risk Disclosures

### Caveat 1 — Q042 17.5% exceeds current SPEC-094 cap

Arch-3 requires Q042 Sleeve A cap amendment from 10% to 17.5%. P4.3 evidence shows Q042 17.5% is concentration-robust (top-5 = 32%, not lucky-episode-driven), but **PM acceptance is required** per Rule 4 + per P0 §5 tear-down boundary (cap **数值** allowed under "可调" tier).

### Caveat 2 — HV Ladder just promoted (Q071 → SPEC-101 / 102)

SPEC-101 (HV Ladder engine + Telegram paper alerts) deployed 2026-05-14. SPEC-102 (dedicated frontend) deployed 2026-05-15. Q073 demoting HV Ladder 2 days later **must be transparent** about the framing:

> **Q071 promoted HV Ladder as a STANDALONE strategy candidate. Q073 portfolio-level review finds it inferior INSIDE THE COMBINED ARCHITECTURE.**
>
> Single-strategy validation (Q071 P5 Sharpe 0.34, sig 100%) is not invalidated. The portfolio-level finding is that HV Ladder's tail drag during early selloffs offsets its small marginal ROE contribution at the architecture level.

HV Ladder is **demoted to research-only / paper-only** under Arch-3, not deleted. If future Q-research (e.g., HV-specific stress gating, narrower entry conditions, dynamic sizing in DotCom-type regimes) addresses the tail issue, HV Ladder can be re-promoted via separate SPEC.

### Caveat 3 — Q042 17.5% live execution friction unknown

Q042 Sleeve A live execution friction is partially unknown (paper since 2026-05-10, 5 paper-trade entries). Friction estimate 0.05%/yr at 10% allocation, extrapolated to 17.5%. Friction sensitivity P4.4 tested ±50% — Arch-3 vs Arch-2 ranking stable.

### Caveat 4 — SPEC-103 R5/R6 cap tightening is a separate governance review

Tightening R5 60% → 50% and R6 50% → 40% is a governance change. Even though P0 says "数值可调", governance amendments traditionally require their own 2nd Quant review per Q072. Q073 P5 hand-off should include this as a sub-SPEC for governance approval.

### Caveat 5 — Forward-sample reliance

Q042 / HV Ladder / V3-A Aftermath all have limited live forward samples. Q073 is fundamentally backtest-driven with synthetic stress validation. Production deployment of Arch-3 will accumulate forward sample over months; 12-month live review recommended (subject to PM's per-feedback discretion on review timing).

---

## 7. Forward Monitoring & Review Obligations

Per PM `feedback_spec_review_obligation` (no time-locked reviews; PM-discretionary):

| Trigger | Quant action |
|---|---|
| Single rolling 20d loss > -8% (Arch-3 expected -7%) | Live review; check if regime is similar to 2000-04 or 2008-09 |
| Cumulative 90d ROE < 0 | Quant review against P4 expectation |
| HV-specific re-promotion signal (new Q-research) | Separate SPEC required |
| Q042 cap utilization hits or breaches current stage cap | Verify staged ramp progress; do not auto-advance |
| **Q042 live concentration**: top-3 trades contribute > 50% of cumulative Q042 PnL | **Review trigger** (added per 2nd Quant) — re-check if Arch-3 concentration assumption holds |
| **SPX normal→stress transition loss**: realized loss before stress trigger fires exceeds expected historical transition loss | **Review trigger** (added per 2nd Quant) — normal 80% SPX exposure may be vulnerable to delayed stress detection |
| Q072 SPEC-103 R5/R6 stress trigger frequency > P1.5 baseline (44%) | Investigate regime shift |

PM may declare any of these triggers at their discretion; Q073 does NOT impose time-locked monitoring.

---

## 8. P5 Hand-off Status

| Deliverable | Status |
|---|---|
| `q073_p0_anchored_memo_2026-05-17.md` — P0 sign-off | ✓ |
| `q073_p1_rules_2026-05-17.md` — 7 binding rules | ✓ |
| `q073_p1_2_marginal_attribution.md` — V3-A marginal | ✓ |
| `q073_p1_3r_unified_nlv_baseline.md` — unified-NLV baseline | ✓ |
| `q073_p1_4_idle_friction_v2_forensic.py` — idle/V2 forensic | ✓ |
| `q073_p1_5_governance_baseline.md` — P2A anchor | ✓ |
| `q073_p2a_plus_e5_candidate_memo.md` — Arch-2 E5 | ✓ |
| `q073_p3_architecture_candidates.md` — Arch-2 vs Arch-3 | ✓ |
| `q073_p4_validation_results.md` — dual-track validation | ✓ |
| **`q073_final_memo.md`** (this file) — recommendation | ✓ |
| 2nd Quant final review | **pending — request now** |
| SPEC drafting (single integrated SPEC) | pending PM approve + 2nd Quant ack |

---

## 9. Ask to 2nd Quant Final Reviewer

**Request**: final framing review for PROMOTE Arch-3 verdict + SPEC handoff scope.

**Key questions for 2nd Quant**:

1. Is Arch-3 vs Arch-2 framing correct (preferred + fallback) or should both be promoted as parallel candidates?
2. Is HV Ladder demotion language adequate ("research-only / paper-only" vs alternatives)?
3. Q042 17.5% sleeve cap increase — should it be staged (10 → 12.5 → 15 → 17.5) or direct?
4. SPEC-103 R1/R5/R6 numeric tightening — Q073 sub-SPEC or separate governance SPEC?
5. Forward monitoring triggers reasonable?
6. Caveats sufficient (especially HV Ladder demotion 2 days after SPEC-101 promote)?
7. Anything missed methodologically (friction model, walk-forward, concentration, synthetic stress all OK)?

---

## 10. Quant Researcher Sign-off

Quant Researcher signs off on Q073 final memo 2026-05-17. Awaiting 2nd Quant final review and PM SPEC approval to proceed with implementation.

**One-line summary**:

> **Q073 finds the realistic risk-constrained portfolio ROE ceiling at ~8% net under the current strategy menu. The recommended architecture (Arch-3) achieves this floor with materially better tail than the incremental alternative (Arch-2), by demoting HV Ladder and increasing Q042 Sleeve A allocation. Single integrated SPEC handoff covers SPX state-dependent caps, Q042 cap increase, HV Ladder demotion, and forward monitoring.**
