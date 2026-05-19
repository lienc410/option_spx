# Q074 P5 / G4 — 2nd Quant Final Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-18
**Source**: `task/q074_p5_g4_2nd_quant_review_packet_2026-05-18.md`
**Verdict**: **PASS — PROMOTE B4 moderate 90% as staged Bull Regime Booster overlay**

---

## Final verdict statement

> Q074 passes G4 final 2nd Quant review. B4 is accepted as Strong-eligible / production-acceptable for staged deployment. It raises net ROE from 7.95% to 8.20%, preserves MaxDD / worst-20d / worst-63d, passes bootstrap and walk-forward validation, remains robust to friction and funding stress, and has explained transition behavior. Quant may proceed to draft SPEC-105. B3 should remain a documented fallback only, not an initial runtime production toggle.

---

## 6 G4 questions — 2nd Quant answers

| Q | Verdict |
|---|---|
| Q1 Strong-eligible wording | **Accept** — use "Strong-eligible / production-acceptable", NOT literal Strong Pass |
| Q2 Tail invariance | **Accept** — no extra synthetic shocks needed before SPEC |
| Q3 VIX 20-22 explanation | **Accept WITH monitoring** — joint-slice explanation sufficient; sample sparse → ongoing monitor required |
| Q4 H1/H2 walk-forward | **Accept** — H1 zero contribution is design-correct, not over-fit |
| Q5 B4 vs B3 | **Promote B4 only** — B3 documented fallback, NOT runtime toggle |
| Q6 SPEC scope | **Accept** — narrow SPEC-105 overlay; do not modify Layer-1 or SPEC-104 survival rules |

---

## Required SPEC-105 elements

### Scope (narrow per Q6)
```
Add B4 benign signal evaluator.
Add booster state: SPX normal cap = 90%.
Preserve Arch-3 state priority:
  second-leg 40% > stress 50% > booster 90% > normal 80%
DO NOT modify Q042 staged ramp.
DO NOT modify HV Ladder demotion.
DO NOT modify R5/R6 trigger definitions.
DO NOT modify V1-V7.
```

### Monitoring obligations (7 items)
1. Booster active days % (review if >60% normal days)
2. Booster transition incremental loss (review if any 10d episode > -1% NLV)
3. VIX 20-22 booster activations (track IVP, ddATH, VIX 5d, subsequent stress)
4. Negative-cash / funding cost (live vs P4 assumptions)
5. Normal→stress transition losses (booster prior 10d + incremental < -0.5% NLV → review)
6. Rolling 20d / 63d loss (Layer-1 protection)
7. B4 vs B3 shadow comparison (optional but useful — evidence trail for tighter fallback)

### Staged rollout (PM-discretionary, NO time lock per `feedback_spec_review_obligation`)
```
Stage 1: paper / shadow logging
  Evaluate B4 state, B4 vs B3, transitions, VIX 20-22 activations, funding cost
Stage 2: limited production activation
  Enable booster cap in production with full monitoring
Stage 3: full production
  PM discretion after live evidence confirms no deviation from P4
```

### Strong-eligible wording (Q1)
> **B4 is Strong-eligible and production-acceptable for staged deployment. It is not a literal Strong Pass, but the ROE shortfall versus the +0.30pp threshold is economically immaterial and within estimation noise.**

---

## 2nd Quant Sign-off

- [x] B4 PROMOTE recommendation accepted
- [x] Strong-eligible classification approved
- [x] SPEC-105 narrow scope approved
- [x] Staged rollout required (not one-shot)
- [x] 7 monitors required (in SPEC-105 AC or post-deploy)
- [x] B3 documented fallback only (NOT runtime production toggle)
- [x] No additional research blockers (synthetic stress / VIX joint slice sufficient as-is)

→ Quant proceeds to SPEC-105 drafting.
