# Q078 P3 / G4 — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-28
**Source**: `task/q078_p3_g4_2nd_quant_review_packet_2026-05-28.md`
**Verdict**: **REVISE — V3 S3 is promising, but SPEC drafting is premature**

---

## Final verdict statement

> Q078 P3 supports V3 daily-cluster S3 as the leading candidate, but does not yet support SPEC drafting. The result is economically promising, with large ROE signal and acceptable preliminary crisis behavior, but the packet explicitly lacks full P4 portfolio integration and still relies on residual selection-bias estimates rather than a fully corrected selector-PASS shadow PnL framework. Additionally, the original expiry-diversification thesis has shifted to an ROE-cadence thesis, which requires PM sign-off. Proceed to P4 portfolio integration and corrected bias validation. If P4 passes, draft a new SPEC number for the selector-gated SPX execution ladder.

---

## Decision summary

| Item | Decision |
|---|---|
| V3 S3 as leading candidate | **YES** |
| Draft SPEC immediately | **NO** |
| Need P4 portfolio integration | **YES** (required pre-SPEC) |
| Need stronger bias correction | **YES** (shadow PnL for all selector-PASS entries OR proof equivalence) |
| Strategy-agnostic framing | **YES** (confirmed) |
| Eff_count / diversification thesis | **REFRAME** (no longer diversification, now ROE-cadence) |
| COVID crisis loss | **Acceptable IF P4 confirms tail** |
| SPEC number | **DO NOT reuse SPEC-107** (SPEC-107 = Intraday Recommendation Governance) |

---

## 6 questions — 2nd Quant answers

| Q | Answer |
|---|---|
| Q1 Noise threshold | **Partial accept** — interpretation aid, NOT gate override. Hard gates still need distribution-level validation. |
| Q2 Bias residual | **Not fully accepted** — year-bucket stratification incomplete; require full shadow PnL OR Stage-1-shadow-only SPEC. |
| Q3 COVID acceptance | **Conditionally acceptable** — require P4 replays of COVID 2020 + Vol 2018 + 2022 + 1 fast-shock synthetic. |
| Q4 Eff_count framing | **Accept reframing** — but PM must explicitly accept "Q078 is no longer expiry-diversification fix; it's ROE-cadence". |
| Q5 SPEC scope | **Mostly right but premature** — defer until P4 + bias correction done. Use new SPEC number. |
| Q6 Staged rollout | **Accept structure but strengthen Stage 1** — explicit shadow gates, not casual logging. |

---

## 5 required corrections before any SPEC drafting

### R1 — P4 portfolio integration (required)

Run combined simulation:
```
Baseline:  SPEC-104 Arch-3 + SPEC-105 v2 Gate F (current production)
Candidate: Baseline + V3 S3 ladder

Metrics required:
  Net ann ROE / ΔROE
  MaxDD / W20d / W63d / Sharpe
  Crisis windows (5 named + 1 fast-shock synthetic)
  Walk-forward H1 / H2
  Bootstrap distribution (not just mean)
  BP utilization combined timeline
  Capital competition with Q042
  Action days/year
  Per-strategy mix
  Per-expiry concentration combined
```

Per P0 §6 + Q078 framing principle: **portfolio-level validation required before SPEC**.

### R2 — Stronger bias correction (required)

Two options:
- **A: Full shadow PnL** — generate PnL for ALL selector-PASS candidate entries, separate production gates as filter layer
- **B: Stage-1-shadow-only SPEC** — defer production trading until live shadow data validates research estimates

For production promotion, prefer A. Year-bucket stratification (-0.86pp) is directionally reassuring but addresses time-period representativeness, not engine filter survivorship.

### R3 — Distribution-level gate validation (required)

Mean-pass not enough. P4 must report:
```
For each hard gate (V1/V2/V3, W20d/W63d, worst trade):
  Mean
  5th percentile
  95th percentile
  Worst seed
  Walk-forward H1/H2 separately
  Per-crisis-window separately
```

Material bootstrap-tail breach must be explained even if mean passes. Noise threshold (< 0.5pp) applies to point estimates, not to tail-distribution gating.

### R4 — PM sign-off on thesis reframing (required)

Original thesis: "ladder fixes expiry concentration (8-at-6/18 problem)".
Corrected thesis: "ladder captures more ROE from selector-PASS opportunities; does NOT materially improve expiry diversification (eff_count Δ 0.05 noise)".

PM must explicitly accept that **solving expiry concentration is no longer the primary success criterion**. Final memo language:
```
Expiry diversification benefit disappeared after corrected monthly bucketing.
Remaining value is ROE from capturing more selector-PASS opportunities at controlled sizing.
```

### R5 — Strengthen Stage 1 shadow gates (required for SPEC)

Stage 1 shadow MUST have explicit gates, not casual logging:

```
Stage 1 shadow log (per selector PASS day):
  - Would V3 enter? (yes/no per cadence)
  - Strategy type
  - Sizing
  - Skipped reason (if skip)
  - Theoretical PnL / MTM (computed for would-be trade)
  - BP utilization snapshot
  - Overlap with Q042 / existing SPX positions
  - Action burden tracking

Stage 2 advancement gate:
  - No hard gate breach in shadow
  - Live shadow trade quality resembles P4 expectations
  - PM confirms operational burden acceptable
  - Minimum [PM-discretionary] shadow period
```

---

## SPEC number conflict

**SPEC-107 already in use**:
- Title: Intraday Recommendation Governance
- Files: `task/SPEC-107.md`, `task/SPEC-107_handoff.md`, `task/SPEC-107_2nd_quant_review_packet_*.md`

**Use next available**: **SPEC-108** for Q078 (when ready).

---

## 2nd Quant Sign-off

- [x] PASS to P4 portfolio integration
- [x] V3 S3 confirmed as leading candidate (pending P4)
- [x] SPEC drafting BLOCKED until P4 + bias correction done
- [x] Distribution-level gate validation required (mean not enough)
- [x] Bias correction Option A preferred (full shadow PnL) OR Option B (Stage-1-shadow-only SPEC)
- [x] PM thesis reframing sign-off required
- [x] Stage 1 shadow gates strengthened
- [x] SPEC number conflict noted (use SPEC-108)
- [x] No additional research blockers beyond R1-R5

→ Quant proceeds to: (1) P4 portfolio integration on top of SPEC-104+105v2 baseline, (2) stronger bias correction (full shadow PnL preferred), (3) distribution-level hard gate validation, (4) PM thesis sign-off, (5) final memo with corrected language. SPEC-108 drafting deferred.
