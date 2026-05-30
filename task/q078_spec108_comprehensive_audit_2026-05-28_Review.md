# SPEC-108 Comprehensive Audit — 2nd Quant Review

**Reviewer**: 2nd Quant
**Date**: 2026-05-28
**Scope**: Q078 全研究链路 (P0-P4 + 5 G-reviews) + SPEC-108 DRAFT
**Source packet**: `task/q078_spec108_comprehensive_audit_packet_2026-05-28.md`

---

## Verdict

**AUDIT PASS WITH MICRO-REVISIONS.**

SPEC-108 is directionally ready for PM approval / Developer handoff. The audit trail is clean: Q078 went through framing, G2, G2.5, G4 revise, P4 integration, and G4 re-submit; the packet shows all required revisions were applied, including thesis reframing, Stage 1 shadow requirement, S3 sizing, production gates, and SPEC-108 numbering.

I would not reject or reopen research. The remaining edits are implementation-hardening items, not strategy changes.

---

## 1. Overall audit judgment — Pass

Research-to-SPEC mapping is consistent:

```text
Research result:                 SPEC implementation:
  V3 daily-cluster                 same cadence
  S3 = 3 contracts                 same sizing
  strategy-agnostic selector       same strategy-agnostic framing
  5 trading-day cluster            same gates
  production gates                 same Stage 1 shadow default
  Stage 1 shadow
```

No major drift detected. The audit packet explicitly traces V3 cadence, S3 sizing, production gates, strategy-agnostic behavior, SPEC-077 exit logic, and expected P4 metrics from research into SPEC-108.

---

## 2. Six audit answers

| # | Question | 2nd Quant answer |
|---|---|---|
| Q1 | Stage 2 minimum ≥10 entries | **Accept** — enough for limited Stage 2 (≈3-4 months shadow @ 35 days/yr cadence). NOT enough for Stage 3 full production; require additional forward evidence after Stage 2. Do NOT raise to 20/30 (would make Stage 1 too slow). |
| Q2 | Add ladder-only W20d/W63d monitoring | **Add explicitly** — portfolio V1/V2/V3 necessary but not sufficient. SPEC-108 is a new execution overlay; should have its own incremental tail monitor. Trigger: ladder-only W20d/W63d degradation > +0.5pp NLV equivalent. |
| Q3 | "No booster off-ladder bonus" out of scope | **Add explicitly** — do not rely on implication. SPEC-105 v2 Gate F is a separate layer; ladder must NOT create daily bonus entries just because Gate F is active. |
| Q4 | AC-108-15 CI test | **Yes — automated CI test required.** Most important implementation-safety edit. Accidental production activation is the biggest implementation risk. |
| Q5 | V1b documented alternative | **Keep but demote.** Useful governance memory. But MUST relabel as "Historical alternative only — not implementable under SPEC-108" and explicit Developer prohibition. Swap requires PM approval + SPEC amendment. |
| Q6 | Bias residual disclosure | **Add to §0.** P4 mean +1.80pp is valid, but disclose realistic deflated range +0.8 to +1.3pp near the headline. Preserves trust + aligns with G4 packet. |

---

## 3. Seven required micro-revisions (PM signature gate)

| # | Edit |
|---|---|
| **R1** | Add ladder-only W20d / W63d incremental tail monitor to §5 |
| **R2** | Add "no booster off-ladder bonus entries" explicitly to §7 out-of-scope |
| **R3** | Add automated CI test for `LADDER_MODE_DEFAULT="shadow"` and no production order path under shadow (new AC) |
| **R4** | Clarify V1b as historical alternative only; Developer must NOT implement V1b under SPEC-108 |
| **R5** | Add residual-bias disclosure to §0: P4 mean +1.80pp, realistic deflated +0.8 to +1.3pp |
| **R6** | Fix API field-count mismatch: list says 9, actual list is 11 |
| **R7** | Add `ladder_mode` and `selector_timestamp` to shadow log schema (optionally `theoretical_entry_price_or_credit`, `theoretical_exit_rule`) |

These are small edits. None change the core research conclusion.

---

## 4. Detailed R-edit specifications

### R1 — Ladder-only incremental tail monitor

```text
Ladder incremental tail monitor:
  rolling 20d ladder-only incremental PnL
  rolling 63d ladder-only incremental PnL
  compare against baseline / expected P4 range
  trigger PM review if ladder-only W20d or W63d degradation
    exceeds +0.5pp NLV equivalent
```

Does NOT replace portfolio-level V1/V2/V3. Explains whether ladder itself is causing deterioration.

### R2 — Out-of-scope addendum

```text
No booster off-ladder bonus entries.
SPEC-105 v2 Gate F remains unchanged.
Q078 ladder only consumes selector-approved opportunities under V3 cadence rule.
```

### R3 — CI test additions

```text
AC-108-17 (positive):
  In absence of explicit LADDER_MODE=active,
  ladder mode resolves to "shadow",
  production order path is disabled,
  shadow log still writes would-enter events.

AC-108-18 (negative):
  Given LADDER_MODE_DEFAULT="shadow",
  v3_ladder_eligible may return eligible=True,
  but production_order_allowed must be False.
```

Must be in pytest CI, not just visual/manual deploy check.

### R4 — V1b prohibition

Revise §8.7 header to:

```text
Historical alternative only — not implementable under SPEC-108
```

Add line:

```text
Developer must not implement V1b under SPEC-108.
Any swap from V3 to V1b requires separate PM approval and SPEC amendment.
```

### R5 — Bias disclosure in §0

```text
Bias caveat:
  P4 mean ΔROE is +1.80pp.
  After residual selection-bias deflation,
  realistic expected ΔROE is approximately +0.8pp to +1.3pp.
  Stage 1 shadow is mandatory to validate live trade quality
  before production activation.
```

### R6 — API field count

Change "9 new fields" to "11 new fields". Keep all 11 listed fields.

### R7 — Shadow log enrichment

Required:
```text
ladder_mode
selector_timestamp
```

Optional (recommended):
```text
theoretical_entry_price_or_credit
theoretical_exit_rule
```

---

## 5. Final verdict statement

> Q078 + SPEC-108 pass comprehensive audit. The audit trail is intact, the G-review revisions were applied, the 5% NLV gate / noise threshold / ROE-cadence thesis are consistently reflected, and SPEC-108 matches the research outcome: V3 daily-cluster, S3 sizing, strategy-agnostic selector output, unchanged SPEC-077 exits, production gates, and mandatory Stage 1 shadow. PM may approve after micro-revisions: add ladder-only W20d/W63d monitoring, explicitly exclude booster off-ladder bonus entries, automate the shadow-default safety test, clarify V1b as non-implementable without amendment, disclose residual-bias adjusted ROE, fix API field count, and enrich the shadow log schema.

---

## 6. 2nd Quant sign-off

- [x] AUDIT PASS — Q078 research line + SPEC-108 DRAFT
- [x] R1-R7 micro-revisions specified
- [x] No reopen of research
- [x] No reject
- [x] PM may approve §11 after Quant applies R1-R7

→ Quant applies R1-R7 inline to SPEC-108. PM signs §11 (now 10 checkboxes incl. audit acknowledgement).
