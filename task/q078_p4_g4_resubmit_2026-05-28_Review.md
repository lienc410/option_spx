# Q078 P4 / G4 Re-Review — 2nd Quant Verdict (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-28
**Source**: `task/q078_p4_g4_resubmit_2026-05-28.md`
**Verdict**: **PASS — draft SPEC-108, but only for staged shadow-first deployment**

---

## Final verdict statement

> Q078 P4 resolves the prior G4 blockers. Portfolio integration shows V3 S3 improves combined ROE and tail metrics versus SPEC-104 + SPEC-105 v2 baseline, crisis windows improve including COVID, walk-forward is positive in both halves, and distribution-level hard gates pass. Residual selection-bias uncertainty remains, so the correct promotion is not immediate production but SPEC-108 Stage-1 shadow deployment. If shadow evidence confirms P4 behavior and PM accepts operational burden, limited production can be considered in Stage 2.

---

## 6 questions — 2nd Quant answers

| Q | Answer |
|---|---|
| Q1 Noise framework | **Accept as interpretation aid**; P4 also validates distribution |
| Q2 Bias residual | **Accept only because Stage 1 is shadow-only**; not enough for immediate production |
| Q3 COVID | **Accept** — P4 shows COVID combined loss improves vs baseline |
| Q4 Eff_count reframing | **Accept** — Q078 is ROE-cadence, not diversification |
| Q5 SPEC scope | **Accept with shadow-only Stage 1 requirement**; use SPEC-108 NOT SPEC-107 |
| Q6 Staged rollout | **Accept**, but strengthen Stage 2 gate with minimum evidence / PM sign-off |

---

## 9 required revisions for SPEC-108

| # | Requirement |
|---|---|
| **R1** | Title: **"selector-gated SPX execution ladder"** (not "BPS ladder") |
| **R2** | Explicitly state: **NOT expiry-diversification fix; primary thesis is ROE-cadence overlay** |
| **R3** | Stage 1 must be **shadow-only** (mandatory, not optional) |
| **R4** | Stage 2 requires **PM explicit sign-off** after shadow review |
| **R5** | Add **minimum evidence gate**: at least **10 shadow candidate entries** OR explicit PM waiver before Stage 2 advancement |
| **R6** | **S3 sizing fixed at 3 contracts** unless separate sizing SPEC approves change |
| **R7** | Enforce production gates: **concurrency, BP ceiling, SPEC-103/104/105, SPEC-077 exits** |
| **R8** | Log: skipped reasons + Q042 / existing SPX position capital overlap |
| **R9** | Use **SPEC-108** number (SPEC-107 = Intraday Recommendation Governance) |

---

## Stage 1 shadow logging requirements (per R8)

```
Per selector PASS day shadow log:
  - selector PASS date
  - strategy type
  - would-enter / skip decision
  - skip reason (if skipped: cadence gap, concurrency, BP ceiling)
  - S3 sizing (3 contracts)
  - BP utilization snapshot
  - Q042 overlap (active or not)
  - existing SPX position overlap (concurrent strategies)
  - theoretical entry / exit / MTM (computed)
  - action burden (action day counter)
```

## Stage 2 advancement gate (per R4 + R5)

```
ALL of the following must hold:
  1. No V1/V2/V3 hard-gate breach in shadow period
  2. No single shadow trade projected loss > 5% NLV
  3. No unexpected Q042 / SPX capital conflict
  4. Realized action burden acceptable to PM
  5. Shadow candidate quality not materially worse than P4 expectation
  6. PM explicitly signs off before production activation
  7. Minimum evidence: ≥ 10 shadow candidate entries OR explicit PM waiver
```

Stage 2 is NOT time-locked; PM-discretionary AFTER all above gates met.

---

## Stage rollout (mandatory structure)

```
Stage 1: Shadow-only deployment
  - V3 cadence evaluator runs in shadow mode
  - All trades logged, no production execution
  - PM observes for PM-discretionary period (with minimum evidence gate per R5)

Stage 2: Limited production activation
  - Requires explicit PM sign-off after Stage 1 review
  - Booster cap effective at 90% in production (if Gate F active)
  - Full monitoring

Stage 3: Full production
  - Requires PM observation of Stage 2 forward live evidence
  - Standard monitoring continues
```

---

## Naming clarification (per V1b vs V3 discussion)

> V3 is a daily-check system, not a weekly ladder.

PM-facing language must NOT call it "weekly ladder". Correct:
```
Daily selector evaluation
At most one entry per 5-trading-day cluster
Expected ~35 action days/year
```

---

## 2nd Quant Sign-off

- [x] G4 PASS for SPEC-108 Stage-1 shadow deployment
- [x] 9 revisions specified for SPEC drafting (R1-R9)
- [x] Stage 1 shadow MANDATORY (not optional)
- [x] Stage 2 advancement gate with minimum evidence + PM sign-off
- [x] PM-facing language: "selector-gated SPX execution ladder" (not weekly BPS ladder)
- [x] SPEC number = SPEC-108 (not SPEC-107)
- [x] No additional research blockers

→ Quant proceeds to draft SPEC-108 with 9 revisions applied. PM approval required before Developer handoff.
