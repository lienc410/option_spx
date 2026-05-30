# Q078 P1a / G2 — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-27
**Source**: `task/q078_p1a_g2_2nd_quant_review_packet_2026-05-27.md`
**Verdict**: **PASS P1a + greenlight P1b** — but P1b must fix BCD + sizing + MTM before economic conclusion

---

## Final verdict statement

> Q078 P1a passes as an attribution stage. It confirms that laddering improves expiry diversification, but current PnL comparisons are not decision-grade due to BCD placeholder PnL, non-normalized sizing, and optimistic MTM decay. P1b should proceed on V1b weekly catch-up and V3 daily-cluster only, after adding a simple analytical BCD model, normalizing sizing in both uniform and BP-target views, and replacing or recalibrating the BPS MTM curve. Q078 should be framed as a selector-gated execution ladder, not a BPS-only ladder. Cash/ad-hoc remains a valid endpoint.

---

## 5 questions — 2nd Quant answers

| Q | Answer |
|---|---|
| Q1 BCD modeling | **Build analytical BCD model** (option a). Use cache only for calibration. Do NOT drop BCD. |
| Q2 Sizing normalization | **Run both views** (option c): Uniform 1-contract + BP-normalized realistic |
| Q3 BPS-only vs agnostic | **Strategy-agnostic ladder.** Q078 is selector-gated execution ladder, not BPS-only |
| Q4 MTM bias | **Fix before P1b decision.** Engine logs preferred → recalibrate theta curve → don't leave as-is |
| Q5 DTE scope | **Selector-provided DTE only.** No constant 30 DTE in Q078 |

---

## Required pre-P1b fixes (3)

### Fix 1 — Analytical BCD model
```
Long deep-ITM call: ~0.70 delta, 90 DTE
Short OTM call:     ~0.30 delta, 45 DTE
Exit: per selector/lifecycle rule
MTM: intrinsic + remaining extrinsic decay
```
Calibrate against backtest cache if exists; don't block P1b on perfect option-level model.

### Fix 2 — Sizing normalization (both views)
```
View 1 (cadence isolated): all variants at 1 contract uniform
View 2 (BP-realistic):     all variants normalized to same target BP-days
                            Baseline B at scaled sizing
                            Ladder at 10%/15%/dynamic
Report separately. Do not merge tables.
```

### Fix 3 — MTM theta curve
Priority order:
1. Use existing engine per-trade PnL logs if aligned with selector
2. Recalibrate theta exponent from empirical backtest
3. (Fallback) keep current MTM but mark P1b as **relative-only, not economics-grade**

---

## P1b structured 2-layer scope (2nd Quant prescribed)

### P1b-1 — Model corrections
- Fix BCD model
- Fix MTM curve
- Normalize Baseline B sizing
- Re-run V1b + V3 at 1-contract sizing for sanity check

### P1b-2 — Sizing sweep (conditional on P1b-1 sanity)
```
Cadence:  V1b weekly catch-up, V3 daily-cluster, Baseline B (control)
Sizing:   S1=1ct, S2=10% BP, S3=15% BP, S4=dynamic (CAUTION)
Views:    Uniform-size + BP-normalized
```

### Operational burden metric front-and-center
```
entries/year
action days/year
weeks with >1 action
max actions per month
manual attention burden
```

A variant requiring daily monitoring should NOT automatically beat weekly catch-up even with higher PnL.

### S4 dynamic sizing caution
S4 may recreate clustering problem Q078 is trying to solve. P1b must report for S4 specifically:
```
single-day BP add
max expiry concentration during peak
worst 20d contribution
active BP spikes
```

If S4 just systematizes clustering aggressively → REJECT even if cum PnL higher.

---

## P1b success criteria (before P2/P3)

```
1. Expiry concentration materially improves vs Baseline B (eff_count > 1.30)
2. No obvious PnL collapse after BCD/MTM fixes
3. Operational burden acceptable (≤30 action days/yr preferred)
4. No sizing-induced BP spikes (S4 specifically)
5. Candidate still passes preliminary W20d/W63d screen
```

### DOCUMENT outcome is acceptable

If ladder improves dispersion but ROE is below threshold after all P1b fixes:
```
DOCUMENT: ladder improves expiry diversification, but economics insufficient for SPEC.
PM may still adopt ladder as operational discipline without SPEC promotion.
```

This is a valid winning outcome per P0 §0 / `feedback_layer_n_replacement_outcome`.

---

## Strategic finding accepted (framing language update)

> "Q078 studies a **selector-gated execution ladder**. It may execute BPS, IC, BCD, or other selector-approved existing strategies. **It does not force BPS exposure**."

This language must appear in every future Q078 memo. PM should not expect weekly BPS-only entries.

---

## 2nd Quant Sign-off

- [x] P1a PASSES as attribution stage
- [x] P1b greenlit conditional on 3 fixes
- [x] Strategy-agnostic ladder framing locked
- [x] V1b + V3 only (V1a / V2 rejected)
- [x] 2-layer P1b structure (model fix → sizing sweep)
- [x] S4 dynamic sizing flagged with explicit reject criteria
- [x] Operational burden as soft promotion gate
- [x] DOCUMENT outcome explicitly acceptable

→ Quant proceeds to draft P1b-1 (model corrections) script, then P1b-2 sizing sweep.
