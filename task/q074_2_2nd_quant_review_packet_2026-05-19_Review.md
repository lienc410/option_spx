# Q074.2 — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-19
**Source**: `task/q074_2_2nd_quant_review_packet_2026-05-19.md`
**Verdict**: **PASS — PROMOTE Gate F to SPEC-105 v2**

---

## Final verdict statement

> Q074.2 passes 2nd Quant review. Gate F should replace the current IVP-only condition in SPEC-105 v2. The amendment is narrow, tail-neutral, bootstrap-positive, and improves cumulative expected PnL. The economic effect is small, but implementation cost is negligible and the current gate demonstrably false-blocks low absolute VIX days. Add a lightweight diagnostic monitor for Gate-F-only activations, then continue Stage 1 shadow under v2.

---

## 5 questions — 2nd Quant answers

| Q | Answer |
|---|---|
| Q1 materiality | **Accept**. Small, but positive and tail-neutral; worth a one-line amendment |
| Q2 F vs F2 | **Promote F**. F dominates cumulative cash and bootstrap lower bound |
| Q3 failed_benign +3 | **Not concerning**. Mild, no tail impact |
| Q4 SPEC scope | **Accept narrow SPEC-105 v2 amendment**. Add optional Gate-F-only diagnostic monitor |
| Q5 timing | **Amend now**. Stage 1 is too new to justify waiting |

---

## Required SPEC-105 v2 elements

### Scope (single-line condition change)
```diff
B4 benign booster conditions:
  not stress_active
  not second_leg_active
  SPX > MA50
  ddATH > -4%
  VIX < 22
  VIX 5d change <= +1.5
- IVP_252 < 55
+ IVP_252 < 55 OR VIX < 15
```

### Unchanged (do NOT modify in v2)
- 90% booster cap
- 80/50/40 state machine priority
- Q042 staged ramp
- HV Ladder demotion
- V1-V7 vetoes
- Existing 7 monitoring obligations
- Staged rollout (PM-discretionary, no time lock)

### New diagnostic monitor (1 item)
```
Gate-F-only activation tracking (shadow/diagnostic, NOT a stop rule):
  - days where IVP_252 >= 55 AND VIX < 15 (the F-added segment)
  - PnL on those days
  - stress trigger within 10d / 20d
  - failed_benign count
```

Purpose: verify live behavior matches backtest expectation for the F-added segment specifically. Diagnostic only; no production logic impact.

### Timing
- Amend SPEC-105 to v2 immediately
- Use Gate F for Stage 1 shadow going forward
- Current B4 as historical reference only
- No need to run v1 and v2 in parallel unless logging both is nearly free

---

## 2nd Quant Sign-off

- [x] Gate F PROMOTE approved
- [x] F over F2 confirmed
- [x] failed_benign +3 accepted as noise
- [x] SPEC-105 v2 narrow scope approved
- [x] Gate-F-only diagnostic monitor required
- [x] Immediate amendment approved (no time lock)
- [x] No additional research blockers

→ Quant proceeds to draft SPEC-105 v2.
