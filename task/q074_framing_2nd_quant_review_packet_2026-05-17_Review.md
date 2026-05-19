# Q074 Framing — 2nd Quant Pre-Research Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-18
**Source**: `task/q074_framing_2nd_quant_review_packet_2026-05-17.md`
**Verdict**: **PASS WITH MINOR REVISIONS — start P1 after applying small wording additions**

---

## Final verdict statement

> Q074 framing is acceptable. It correctly preserves Q073 / SPEC-104 Layer-1 survival constraints and limits the research to benign-regime SPX normal-cap boosting. The B1–B4 candidate set is sufficiently disciplined and should not be expanded to 95% / 100%, smoothing, macro features, or term-structure features. P3 transition-risk forensic is correctly defined as the core validation layer; add a 20d diagnostic window and transition severity split. After minor wording updates, Quant may start P1 attribution.

---

## 6 framing questions — 2nd Quant answers

| Q | 2nd Quant answer |
|---|---|
| Q1 Layer-1/Layer-2 framing | **PASS** + add explicit prohibition on modifying stress / second-leg trigger definitions/timing |
| Q2 Feature set complete | **PASS** — do NOT add VIX3M, realized vol, macro, calendar effects in Q074 |
| Q3 Transition-risk methodology | **PASS with one addition** — keep 10d primary, add 20d diagnostic + mild/acute transition split |
| Q4 Snap-back smoothing? | **NO smoothing. Hard snap-back is correct. Do not add B5** |
| Q5 Test 95% / 100%? | **NO. 90% is upper bound for Q074** |
| Q6 Success criteria | **ACCEPT** — Strong / Soft / Fail thresholds appropriate for Layer-2 marginal optimization |

---

## 5 Required Minor Revisions Before P1

### Revision 1 — Explicit trigger immutability
P0 must state:
> **Q074 may not modify `stress_active` or `second_leg_active` trigger definitions OR their timing. Any proposal to change those triggers must be moved to a separate governance research item, not included in Q074.**

Rationale: Slowing the stress trigger to make booster look better is structurally equivalent to relaxing Layer-1. Block this anti-pattern explicitly.

### Revision 2 — Add 20d transition diagnostic
P3 must compute BOTH:
- **Primary transition window**: booster active in previous 10 TD before stress trigger (existing)
- **Secondary diagnostic window**: booster active in previous 20 TD before stress trigger (NEW)

Rationale: 10d catches fast rollovers (2020-02 COVID); 20d catches slow rollovers (2000, 2007, 2022).

### Revision 3 — Mild vs acute transition severity split
P3 must classify each transition as:
- **mild transition**: stress triggers without second-leg within next 20d
- **acute transition**: stress triggers followed by second-leg within next 20d
- **failed benign**: booster active, stress triggers, incremental booster PnL < 0

### Revision 4 — Freeze B1-B4 before P1
P0 must state:
> **P1 attribution is diagnostic only. Candidate definitions B1-B4 are frozen before P1 results are observed. Any new candidate derived from forward-return buckets requires a separate P0 amendment and 2nd Quant review.**

Rationale: P1 forward-return buckets must not be used to mine new booster definitions (look-ahead overfit risk).

### Revision 5 — 90% upper bound locked
P0 must state:
> **Booster cap upper bound remains 90% for Q074. 95% and 100% are NOT tested.**

Rationale: 95%+ leaves near-zero cash buffer, induces unacceptable transition risk severity.

---

## 2nd Quant Sign-off Status (CONDITIONAL PASS)

- [x] Layer-1/Layer-2 framing acceptable
- [revise → applied] Add trigger immutability statement
- [x] Feature set (5/6 features) sufficient; no expansion
- [revise → applied] Add 20d diagnostic + mild/acute split
- [x] Hard snap-back retained (no smoothing)
- [x] 90% upper bound (no 95/100%)
- [revise → applied] B1-B4 frozen before P1
- [x] Success criteria (Strong + Soft + Fail) acceptable
- [x] Methodology (unified-NLV, constant friction, point-in-time) inherits Q073 lessons

→ Quant applies 5 revisions to P0 memo, then may start P1.
