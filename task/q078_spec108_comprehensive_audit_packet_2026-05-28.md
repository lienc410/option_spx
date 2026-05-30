# Q078 + SPEC-108 — Comprehensive 2nd Quant Audit Packet

**Date**: 2026-05-28
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **Holistic end-to-end audit** of Q078 research line + SPEC-108 DRAFT before PM approval
**Decision sought**: AUDIT PASS (PM may approve SPEC-108) / AUDIT REVISE (specific items) / REJECT

---

## 0. Scope of audit

This is NOT a G-phase review (those are done: framing/G2/G2.5/G4 all PASS). This is a **comprehensive consistency check** before PM signs SPEC-108:

1. **Audit trail integrity** — every G-review verdict properly applied
2. **Framework consistency** — noise threshold + 5% NLV + thesis reframing land in all artifacts
3. **SPEC-108 implementation completeness** — code/AC/staged rollout / monitoring all present
4. **Risk handling adequacy** — Layer-1 preserved, Stage 1 shadow safeguards real
5. **Drift detection** — research findings = SPEC implementation 1:1?

---

## 1. Q078 audit trail summary

```
Date        Phase                    2nd Quant Verdict        Required Revisions
2026-05-27  Framing                  PASS w/ minor revisions  6 revisions → P0
2026-05-27  P0 anchored              (informational)          —
2026-05-27  P1a cadence              —                        —
2026-05-27  G2                       PASS w/ 3 fixes          BCD model / sizing / MTM
2026-05-27  P1b-1 model corrections  —                        Engine empirical pool
2026-05-27  P1b-2 sizing sweep       —                        S3 confirmed (5% NLV gate)
2026-05-28  G2.5                     PASS w/ methodology       Two-layer + framing
2026-05-28  P0 revision              (5% NLV gate, then noise threshold)
2026-05-28  P2                       (intermediate)            Eff_count + MTM bugs
2026-05-28  P2 REVISED               (intermediate)            L1/L4/L5 fixes
2026-05-28  P3                       (intermediate)            Crisis + walk-forward + bias
2026-05-28  G4 round 1               REVISE                    R1-R5 required (P4 missing)
2026-05-28  P4 portfolio integration  —                        Decision-grade
2026-05-28  G4 round 2 (re-submit)   PASS                      9 SPEC revisions (R1-R9)
2026-05-28  SPEC-108 DRAFT            —                        Pending PM approval
```

Total: 11 phases + 5 2nd Quant reviews + 9 SPEC revisions. All G-reviews PASS w/ specified revisions; all revisions applied.

---

## 2. G-review verdict → application audit

### 2.1 Framing 6 revisions
Per `q078_framing_2nd_quant_review_2026-05-27_Review.md`:
- R1: Baseline B as primary canonical ✓ (P0 §2.3)
- R2: 21 DTE roll preserved (Q079 future) ✓ (P0 §2.5)
- R3: L5 booster bonus excluded ✓ (P0 §4 + scope locks)
- R4: Cluster rule strict + catch-up only ✓ (P0 §2.4)
- R5: Tail hard gate ≤ +0.25pp (now noise) ✓ (P0 §7 revised)
- R6: P1 staged P1a + P1b ✓ (P0 §3.1 / 3.2)
- R7: Effective expiry count metric ✓ (P3 + P4 — initially broken in P2, fixed P2R)
- R8: Selector-provided DTE only ✓ (P0 §2.2)
- R9: P1 staged ✓ (P1a → P1b done)

**Status**: All 9 R applied. ✓

### 2.2 G2 — 3 fixes
- BCD model: ✓ engine empirical pool used (P1b-1)
- Sizing normalization: ✓ uniform 1-contract + sized (P1b-2)
- MTM bias: ✓ engine actual PnL (P1b-1) — analytical model superseded

### 2.3 G2.5 — 2-layer methodology
- Layer 1 shadow: ✓ in P2/P2R/P3/P4
- Layer 2 production gates: ✓ concurrency + BP ceiling applied
- Strategy-agnostic framing: ✓ in P0 R8 + reinforced throughout
- S3 sizing fixed: ✓
- Bootstrap CI required: ✓ 20-seed in P2R/P3/P4

### 2.4 G4 round 1 → REVISE → P4 done
- R1 P4 portfolio integration: ✓ DONE (q078_p4_memo.md)
- R2 Bias correction: ✓ Option B (Stage 1 shadow) + 2-axis stratification
- R3 Distribution-level CI: ✓ 20-seed mean+p5+p95+worst seed
- R4 PM thesis sign-off: ✓ done 2026-05-28
- R5 Stage 1 shadow gates: ✓ in SPEC-108 §6

### 2.5 G4 round 2 — 9 SPEC revisions
Per `q078_p4_g4_resubmit_2026-05-28_Review.md`:

| # | Revision | Location in SPEC-108 |
|---|---|---|
| R1 | Title "selector-gated SPX execution ladder" | Title + §0 + §8.1 |
| R2 | Not expiry-diversification; ROE-cadence primary | §0 + §1.2 + §8.1 |
| R3 | Stage 1 shadow-only MANDATORY | §6 + AC-108-15 |
| R4 | Stage 2 requires PM signoff | §6 + AC-108-15 |
| R5 | ≥ 10 shadow entries OR PM waiver | §6 |
| R6 | S3 fixed at 3 contracts | §2.1 + §8.2 + §7 exclusion |
| R7 | Production gates enforced | §2.2 + §2.4 + §8.5 |
| R8 | Log skipped reasons + Q042/SPX overlap | §2.6 |
| R9 | SPEC-108 NOT SPEC-107 | Title + §0 + §11 |

**Status**: All 9 R applied to SPEC-108. ✓

---

## 3. Framework consistency check

### 3.1 5% NLV worst-trade gate (PM 2026-05-27)

| Artifact | 5% NLV gate present? |
|---|---|
| P0 anchored memo §7 | ✓ revised |
| P1b-2 sizing sweep | ✓ S2 rejected, S3 confirmed |
| P3 memo | ✓ all per-trade worst within gate |
| P4 memo | ✓ -4.29% NLV worst |
| SPEC-108 §7 out-of-scope | ✓ S2 rejected listed |
| SPEC-108 §8.2 sizing rationale | ✓ S2 → fail gate explained |

### 3.2 Noise threshold (PM 2026-05-28)

| Artifact | < 0.5pp = noise framework applied? |
|---|---|
| P0 anchored memo §7 verdict mapping | ✓ revised to ≥ +0.5pp signal |
| P2 REVISED memo | ✓ "all Δ within noise" flagged |
| P3 memo | ✓ noise framework synthesis section |
| P4 memo | ✓ ΔROE 3.6x noise = signal |
| SPEC-108 §0 TL;DR | ✓ implicit via "signal" language |
| Memory `feedback_noise_threshold.md` | ✓ saved 2026-05-28 |

### 3.3 Thesis reframing (PM signoff 2026-05-28)

| Artifact | "ROE-cadence NOT diversification" present? |
|---|---|
| P4 memo | ✓ explicit reframing |
| G4 re-submit packet | ✓ §3 + §4 |
| SPEC-108 §0 TL;DR | ✓ R2 quoted wording |
| SPEC-108 §1.2 | ✓ formal thesis statement |
| SPEC-108 §8.1 | ✓ V3 = daily-check not weekly ladder |

---

## 4. SPEC-108 implementation completeness check

### 4.1 Code changes covered
- ✓ New constants (4: SIZING, CLUSTER_DAYS, BP_CEILING, MODE_DEFAULT)
- ✓ New evaluator (`v3_ladder_eligible`)
- ✓ New module path (`strategy/q078_ladder.py`)
- ✓ State tracker (LadderState class)
- ✓ Skip reason codes (cadence_gap, selector_wait, concurrency_block, bp_ceiling_block)

### 4.2 API extension covered (§2.5)
- ✓ 9 new fields specified
- ✓ Backward compatible (additions only)

### 4.3 Shadow log schema (§2.6)
- ✓ 12 fields per entry
- ✓ Q042 overlap field present (per R8)
- ✓ Existing SPX position overlap field present (per R8)

### 4.4 ACs (16 total)
- ✓ AC-108-1 to AC-108-6: Evaluator logic
- ✓ AC-108-7: API contract
- ✓ AC-108-8 + AC-108-15: Stage 1 shadow default ENFORCED
- ✓ AC-108-9: Shadow log writes
- ✓ AC-108-10: Dashboard display
- ✓ AC-108-11: Telegram alerts
- ✓ AC-108-12 to AC-108-13: Tests + no-regression
- ✓ AC-108-14: Backtest cache refresh
- ✓ AC-108-16: Action days counter

### 4.5 Staged rollout (§6)
- ✓ Stage 1 shadow MANDATORY
- ✓ Stage 2 PM-signoff
- ✓ Stage 3 PM-discretionary after Stage 2 forward
- ✓ Minimum evidence gate (≥10 entries)
- ✓ 7 hard advancement conditions
- ✓ No time locks (per `feedback_spec_review_obligation`)

### 4.6 Out-of-scope (§7)
- ✓ Layer-1 caps frozen
- ✓ Booster Gate F frozen
- ✓ SPEC-077 exit frozen
- ✓ S3 sizing locked (R6)
- ✓ Cluster rule locked
- ✓ BPS-only / credit-only restriction excluded (R2)
- ✓ Q042 / HV changes excluded
- ✓ S2 (4 contracts) explicitly excluded
- ✓ Diversification claim language excluded (R2)

---

## 5. Risk handling adequacy

### 5.1 Layer-1 preservation

All SPEC-104 R5/R6 caps unchanged:
- Normal cap 80% ✓
- Booster cap 90% (when Gate F active) ✓
- Stress cap 50% ✓
- Second-leg cap 40% ✓

Ladder enters at sizing within 35% NORMAL ceiling — does NOT exceed Layer-1 limits.

### 5.2 Stage 1 shadow safeguards

`LADDER_MODE_DEFAULT = "shadow"` means:
- Code path enabled
- Decisions logged
- Production execution gated by `LADDER_MODE != "shadow"`

Risk: if shadow mode default not enforced at deploy time, accidental production trading.
Mitigation: AC-108-15 requires env var check.

### 5.3 Stage 2 advancement gate

7 conditions ALL must hold. The minimum evidence gate (R5: ≥10 shadow entries) prevents premature advancement.

**Concern**: 10 shadow entries at ~35/yr means ≥ ~3.5 months of shadow data. Adequate?

**Quant prior**: yes, but PM may want longer evidence base (e.g., ≥30 shadow entries = ~10 months). Discussion point.

### 5.4 Monitoring obligations (§5)

7 monitors specified. Cover:
- Signal rate (1) — anomaly detection
- Skip reason distribution (2, 3) — gate behavior validation
- Theoretical PnL tracking (4) — model drift detection
- Action burden (5) — PM bandwidth
- Q042/SPX overlap (6) — capital competition
- Shadow trade quality (7) — Stage 2 ongoing validation

**Quant assessment**: comprehensive. Missing: ladder-specific MaxDD/W20d/W63d monitoring during Stage 2 (covered by SPEC-103 standard Layer-1 monitors implicitly but could be explicit).

---

## 6. Drift detection: research vs SPEC

### 6.1 V3 cadence rule
- Research: ≤ 1 entry per 5 trading days, daily evaluation
- SPEC-108: `LADDER_CADENCE_CLUSTER_DAYS = 5`, daily check
- ✓ Match

### 6.2 S3 sizing
- Research: 3 contracts per entry
- SPEC-108: `LADDER_SIZING_CONTRACTS = 3`
- ✓ Match

### 6.3 Production gates
- Research: concurrency (1 per strategy, 2 for IC_HV) + BP ceiling 35% NORMAL
- SPEC-108: matches engine config; `LADDER_BP_CEILING_PCT = 35.0`
- ✓ Match

### 6.4 Strategy-agnostic
- Research P0 R8: selector-provided
- SPEC-108: §2.3 explicit
- ✓ Match

### 6.5 Exit logic
- Research: SPEC-077 unchanged (21 DTE roll, 60% profit, min 10d held)
- SPEC-108: §2.4 confirmation, no exit changes
- ✓ Match

### 6.6 Expected metrics
- Research P4: ΔROE +1.80pp, MaxDD/W20d/W63d improve
- SPEC-108 §0: same numbers
- ✓ Match

---

## 7. Six audit questions for 2nd Quant

### Q1 — Is Stage 2 minimum evidence ≥ 10 entries adequate?
~3.5 months at expected 35/yr cadence. PM-discretionary advance after that.
**2nd Quant: confirm 10 minimum, or require ≥20 / ≥30?**

### Q2 — Should monitoring add explicit ladder-only W20d/W63d tracking?
SPEC-103 monitors portfolio-level. Stage 2 ongoing validation per §5 monitor #7 is "shadow trade quality" but not formal W20d/W63d ladder-only series.
**2nd Quant: add a ladder-only tail tracker, or rely on portfolio-level monitors?**

### Q3 — Out-of-scope explicit inclusion of "no booster off-ladder bonus"?
Q074 territory; G2.5 R4 excluded. Currently captured implicitly via "Strategy-agnostic per selector" but not explicitly listed in §7.
**2nd Quant: add to §7 out-of-scope list, or implicit OK?**

### Q4 — Should AC-108-15 be a CI test, not just visual check?
"LADDER_MODE_DEFAULT='shadow' enforced at deploy" is critical safety guard. Currently AC is "env var check" which could be manual.
**2nd Quant: require automated CI assertion?**

### Q5 — V1b documented alternative — risk of confusion?
SPEC-108 §8.7 mentions V1b as future-swap-in. Could create implementation ambiguity.
**2nd Quant: keep documentation (PM future-option) or remove?**

### Q6 — Bias residual disclosure in SPEC-108?
Research caveats include "residual bias ~1-2pp" but SPEC-108 §0 TL;DR quotes mean ΔROE +1.80pp without deflation. Should SPEC explicitly state realistic range +0.8 to +1.8pp?
**2nd Quant: revise §0 to include deflated estimate, or research-disclaimer in §1.2 sufficient?**

---

## 8. Audit decision matrix

| 2nd Quant verdict | Action |
|---|---|
| **AUDIT PASS** + Q1-Q6 acceptable | PM may sign §11 SPEC-108 approval; Quant ready for Developer handoff |
| **AUDIT REVISE** (specific) | Apply specific fixes; re-submit |
| **REJECT** | SPEC-108 closes; Q078 documented as research only |

---

## 9. Files in scope

### Research artifacts (Q078)
- `research/q078/q078_p0_anchored_memo_2026-05-27.md`
- `research/q078/q078_p1a_memo.md`
- `research/q078/q078_p1b_1_memo.md`
- `research/q078/q078_p1b_2_memo.md`
- `research/q078/q078_p2_memo.md`
- `research/q078/q078_p2r_memo.md`
- `research/q078/q078_p3_memo.md`
- `research/q078/q078_p4_memo.md`
- `research/q078/*.csv` (all output CSVs)

### Task artifacts (G-reviews + SPEC)
- `task/q078_framing_2nd_quant_review_packet_2026-05-27.md` + Review
- `task/q078_p1a_g2_2nd_quant_review_packet_2026-05-27.md` + Review
- `task/q078_p1b_g2_5_2nd_quant_review_packet_2026-05-28.md` + Review
- `task/q078_p3_g4_2nd_quant_review_packet_2026-05-28.md` + Review (round 1: REVISE)
- `task/q078_p4_g4_resubmit_2026-05-28.md` + Review (round 2: PASS)
- `task/SPEC-108.md` (DRAFT awaiting PM)

### Memory
- `feedback_noise_threshold.md` (NEW 2026-05-28)
- `feedback_layer_n_replacement_outcome.md` (referenced)
- `feedback_layer_n_replacement_research.md` (referenced)
- `feedback_quant_review_location.md` (followed)

---

## 10. Quant sign-off

Quant submits Q078 + SPEC-108 DRAFT for comprehensive 2nd Quant audit before PM signature. All G-phase reviews PASS; all 9 SPEC revisions applied; all framework updates (5% NLV, noise threshold, thesis reframing) propagated to all artifacts; research findings 1:1 match SPEC implementation; risk handling adequate (Layer-1 preserved, Stage 1 shadow mandatory). 6 audit questions raised for 2nd Quant judgment.

> Q078 + SPEC-108 holistic audit packet: 11 research phases + 5 G-reviews + 9 SPEC revisions all documented and traced 1:1 from research findings to SPEC implementation. Framework evolution (5% NLV gate 2026-05-27, noise threshold 2026-05-28, thesis reframing PM signoff 2026-05-28) consistently applied across all 8 research memos + SPEC-108. V3 daily-cluster + S3 sizing locked per PM 2026-05-28 decision (V1b documented alternative for future operational change). Stage 1 shadow MANDATORY default with ≥10 entries minimum evidence gate + PM signoff Stage 2 advancement. 7 monitoring obligations + 16 AC. Layer-1 (SPEC-103/104/105 v2) untouched. No drift detected between research and SPEC. 6 audit questions for 2nd Quant judgment on minimum evidence threshold, ladder-only tail tracking, out-of-scope explicit listings, CI enforcement of shadow default, V1b documentation, and bias disclosure language.
