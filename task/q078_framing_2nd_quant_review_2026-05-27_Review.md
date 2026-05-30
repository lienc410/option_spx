# Q078 Framing — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-27
**Source**: `task/q078_framing_2nd_quant_review_packet_2026-05-27.md`
**Verdict**: **PASS WITH REVISIONS** — proceed to P0 after applying 9 revisions

---

## Final verdict statement

> Q078 framing passes as execution-layer research, not strategy override. The research should test whether systematic selector-gated entry cadence improves expiry dispersion, BP utilization, and ROE versus clustered ad-hoc entry. However, scope must remain tight: retain SPEC-077 21 DTE, keep booster bonus entries out of core, use cluster baseline as primary comparator, test strict/catch-up but not rolling cadence, and treat tail degradation as a hard gate. Cash/ad-hoc remains a valid endpoint.

---

## 6 questions — 2nd Quant answers

| Q | Verdict |
|---|---|
| Q1 Ladder framing | **PASS** — Execution layer only; no selector override |
| Q2 Baseline | **All three, but Baseline B is primary canonical**; A/C as sensitivity |
| Q3 21 vs 15 DTE | **Keep 21 DTE; open Q079 for 15 DTE separately** |
| Q4 Booster L5 | **Exclude from core P2**; diagnostic appendix only if P1 shows missed Gate F value |
| Q5 Cluster rule | **Test strict + catch-up; exclude rolling from core** |
| Q6 Success criteria | **Tail is hard gate with ≤0.25pp tolerance**; no weighted override beyond that |

---

## 9 required revisions before P0

### R1 — Keep ladder strictly execution-layer
Constraint #1 in P0. No partial override of selector gates. Already in framing; **must be written into P0 TL;DR and §1 non-negotiable**.

### R2 — Baseline tier
```
Primary canonical:   Baseline B (cluster/ad-hoc) — closest to observed PM behavior
Sensitivity:         Baseline A (every 21d), Baseline C (zero)
```
Main comparison reports Ladder vs B; A/C for sensitivity discussion only.

### R3 — 21 DTE roll preserved; 15 DTE → Q079
Q078 keeps SPEC-077 21 DTE exit. PM's 15 DTE proposal becomes **Q079 — 15 vs 21 DTE Roll / Exit Horizon Study** (separate framing). Reason: 15 DTE exit changes gamma exposure / theta capture / holding distribution — strategy lifecycle research, not ladder execution.

### R4 — L5 removed from core P2
Booster off-ladder bonus entry (L5) is scope creep. Q074 / SPEC-105 v2 already owns booster. Q078 core P2 = L1-L4. L5 only as **diagnostic appendix** IF P1 shows weekly ladder systematically misses high-quality Gate F windows.

### R5 — Cluster rule scope
P1 tests **strict + catch-up only**. Rolling excluded from core (would blur ladder concept into daily-conditional system).

```
Variant C1 — Strict weekly:    Only Monday; if WAIT, skip week
Variant C2 — Catch-up weekly:  If Monday WAIT, allow first PASS on Tue/Wed (no Thu/Fri)
EXCLUDED — Rolling:            "next PASS after last entry + 5 trading days" (too close to daily conditional)
```

### R6 — Tail degradation = HARD gate
No weighted ROE-vs-Tail trade. Strict:
```
V1/V2/V3 pass mandatory
W20d degradation ≤ +0.25pp
W63d degradation ≤ +0.25pp
No new crisis-window failure
```
Within 0 to +0.25pp tail degradation: soft-pass candidate (requires P3 forensic). Beyond +0.25pp: reject regardless of ROE.

### R7 — Add effective expiry count metric

```
Max expiry concentration:  max(single_expiry_max_loss) / total_max_loss
Effective expiry count:    1 / Σ(expiry_weight²)        ← Herfindahl inverse (NEW)
```
Effective expiry count is more robust than single max. 8 trades on same expiry → eff_count = 1. 4 expiries equally → eff_count = 4.

### R8 — Ladder uses selector-provided DTE / params
**Do not hard-code 30/35/45 DTE inside ladder.** Ladder must consume `selector_recommendation.legs[*].dte` and `selector_recommendation.bp_target_for_regime()`. This means if selector returns BCD (debit) in LOW_VOL, ladder either follows selector (different strategy this week) or skips. Either decision must be a P0 design question (not implicit).

### R9 — P1 staged into P1a + P1b
Avoid 27-cell matrix explosion. Stage:
```
P1a (Cadence + cluster rule):
  Fixed S1 (10% sizing), Baseline B
  Test: weekly strict / weekly catch-up / bi-weekly strict / daily-conditional
  Output: entry timing + expiry dispersion comparison

P1b (Sizing) — conditional on P1a winner:
  Top 1-2 cadence variants only
  Test: 10% / 15% / dynamic
  Output: BP utilization vs tail trade-off
```

---

## Critical P0 additions (not in framing)

### P0 TL;DR must explicitly state:
> "Ladder may improve expiry dispersion without improving average BP utilization. BP utilization improvement is an empirical question, not an assumption."

PM's intuition is that ladder fills BP. Reality (per SPEC-106 audit, 50% gated) is much less. Q078 must NOT assume BP fills; must verify.

### Operational burden as gate
P4 outputs must include:
```
entries/year
weeks with action
max actions in one week
manual attention events/year
```

Soft operational thresholds:
```
Preferred:        ≤ 1 new SPX BPS entry/week
Flag:             > 2 action days/week average in active months
Reject/downgrade: requires daily manual monitoring
```

### S3 dynamic sizing caution
P1b can test S3 but P2 candidate default = exclude. If S3 just systematizes ad-hoc cluster mechanism → reject.

P1b S3-specific report:
```
S3 max single-day BP add
S3 expiry concentration
S3 worst 20d contribution
```

### Promotion rule (full form)
```
PROMOTE only if ALL:
  ΔROE ≥ +0.05pp (Soft threshold)
  AND expiry concentration improves materially (eff_count increases ≥ +1 or max_concentration drops ≥ -30pp)
  AND W20d degradation ≤ +0.25pp
  AND W63d degradation ≤ +0.25pp
  AND no named crisis failure
  AND operational burden within soft threshold

SOFT-PASS candidate (requires P3+P4 review): meets ROE/diversification + W20d/W63d within 0 to +0.25pp range
REJECT: any hard gate fail
DOCUMENT: ROE < +0.05pp but ladder improves expiry concentration and operational discipline materially
```

---

## 2nd Quant Sign-off

- [x] PASS WITH REVISIONS to P0
- [x] 9 revisions specified
- [x] Q079 scope identified (15 vs 21 DTE — separate)
- [x] L5 booster bonus excluded from core
- [x] Cluster rule narrowed (strict + catch-up only)
- [x] Tail = hard gate
- [x] Effective expiry count metric required
- [x] Ladder uses selector-provided DTE (no hard-code)
- [x] P1 staged (P1a cadence first, P1b sizing conditional)
- [x] No additional research blockers

→ Quant proceeds to draft Q078 P0 anchored memo with 9 revisions + critical additions applied.
