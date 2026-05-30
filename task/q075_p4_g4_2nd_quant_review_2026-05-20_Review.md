# Q075 P4 / G4 — 2nd Quant Final Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-20
**Source**: `research/q075/q075_p4_memo.md`
**Verdict**: **PASS — accept DOCUMENT outcome. Close Q075 with no SPEC.**

---

## Final verdict statement

> Q075 passes final G4 review with DOCUMENT outcome. The IC overlay is structurally clean, tail-invariant, and mildly diversifying, but economically sub-threshold at current research sizing. IC w25 and w35 do not meet the Soft promotion threshold. BCS, C2, and IC w15 remain rejected. No SPEC should be drafted. The operational conclusion is that IVP-blocked Type C normal-state days are cash / BOXX days at the current $894k NLV scale and PM bandwidth. Future revisit requires a separate scaling/deployment study, not a continuation of Q075.

---

## 6 G4 questions — 2nd Quant answers

| Question | Answer |
|---|---|
| Does IC pass risk? | **Yes** — tail metrics unchanged, no capital conflict |
| Does IC pass economics? | **No** — +0.004pp / +0.007pp below Soft (+0.05pp) |
| Should IC be promoted? | **No** — DOCUMENT only |
| Should scaling override this? | **No** — scaling is separate deployment decision |
| Should Q075 draft a SPEC? | **No** |
| Should Q075 close? | **Yes** — close with DOCUMENT outcome |

---

## Reject list (final, do NOT reopen inside Q075)

- IC w15 (failed Mild downside shock — thin credit cushion)
- BCS (failed 4/4 melt-up analogs)
- C2 short-DTE BPS (turned negative under refactored mark model)
- Calendar / diagonal (never advanced past P1 seed)
- Multi-entry cluster (excluded by P0)

---

## Operational principle (preserved for project record)

> **IVP-blocked Type C normal-state days are cash / BOXX days at current $894k NLV scale. A small IC overlay is structurally clean (tail-invariant, negatively correlated, stress-adjacent robust, no capital conflict) but economically sub-threshold at 1× research sizing. Do not deploy a production replacement strategy. Revisit only if NLV scale, sizing appetite, and PM operational bandwidth materially change — and only as a separate sizing-specific research item, not a Q075 continuation.**

---

## Memory updates required

1. New feedback memory: `feedback_layer_n_replacement_outcome.md`:
   > If a Layer-3 replacement strategy is structurally clean but sub-threshold at research sizing, the correct outcome is DOCUMENT, not scaling the trade until it passes. Scaling is a separate deployment decision requiring explicit PM judgment about NLV, operational bandwidth, execution, and risk appetite.

2. Update MEMORY.md index with the new feedback entry.

---

## Q075 closure status

```
Phase  Status   Output
P0     CLOSED   q075_p0_anchored_memo_2026-05-19.md
P1     CLOSED   q075_p1_attribution_memo.md  (Type C 50% stress prob discovery)
P2     CLOSED   q075_p2_memo.md  (later corrected by P3 refactored mark)
P3     CLOSED   q075_p3_memo.md  (BCS dead, C2 dead, IC w25/w35 advanced)
P4     CLOSED   q075_p4_memo.md  (sub-threshold ROE → DOCUMENT)
G4     PASS     this file
```

```
Q075 CLOSED — DOCUMENT.
No SPEC.
Operational principle: IVP-blocked Type C days remain cash / BOXX at current scale.
```

---

## 2nd Quant Sign-off

- [x] G4 PASS — DOCUMENT outcome accepted
- [x] No SPEC drafted
- [x] Operational principle preserved
- [x] Memory + project status updates required
- [x] Reject list finalized (BCS, C2, IC w15, calendar, multi-entry)
- [x] Future revisit framework: only at NLV scale change + separate research, NOT Q075 continuation

→ **Q075 formally closed 2026-05-20.**
