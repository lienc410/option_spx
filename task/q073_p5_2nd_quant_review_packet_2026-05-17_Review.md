# Q073 P5 — 2nd Quant Final Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-17
**Source**: `task/q073_p5_2nd_quant_review_packet_2026-05-17.md`
**Verdict**: **PASS — PROMOTE Arch-3**

---

## Final verdict

> Q073 passes final 2nd Quant review. Arch-3 is the preferred Round 2 ROE architecture. It achieves essentially the same net ROE as Arch-2 while materially improving MaxDD, worst-20d loss, worst-63d loss, Sharpe, and operational simplicity. The HV Ladder should be demoted to research-only / paper-only, not invalidated. Q042 Sleeve A target cap may be raised to 17.5%, preferably through staged implementation. A single integrated SPEC should implement SPX state-dependent caps, Q042 cap ramp, HV Ladder demotion, and monitoring obligations. Arch-2 remains fallback only if PM declines the Arch-3 implementation changes.

---

## 6 review questions — 2nd Quant answers

| Q | 2nd Quant answer |
|---|---|
| Q1 — Arch-3 vs Arch-2 framing? | **CORRECT** — Promote Arch-3; Arch-2 is fallback (not parallel promote) |
| Q2 — HV demotion language? | **ADEQUATE** — Use "research-only / paper-only"; avoid "failed" / "deleted" |
| Q3 — Q042 17.5% staged or direct? | **STAGED PREFERRED** — Target 17.5% validated, but production ramp staged |
| Q4 — SPEC-103 numeric tightening sub-SPEC? | **SINGLE INTEGRATED SPEC** with clear governance subsection |
| Q5 — Monitoring triggers? | **REASONABLE** — Add Q042 live concentration + normal→stress transition monitors |
| Q6 — Caveats / methodology? | **SUFFICIENT** — Add bootstrap CI wording caution (significance evidence, not forward forecast) |

---

## 6 Required Revisions Before SPEC Handoff

### Revision 1 — HV Ladder demotion language
Add explicit wording in final memo Caveat 2:

> **Demotion is a portfolio allocation decision, not a claim that the HV Ladder signal has no standalone alpha.**

> **HV Ladder is demoted, not invalidated. Its standalone Q071 evidence remains valid, but Q073 shows its marginal portfolio contribution is inferior to replacing it with additional Q042 Sleeve A allocation under the current sleeve stack.**

### Revision 2 — Q042 staged ramp
Replace "direct or staged" with **staged ramp recommended**:

```
Stage 1: 10% → 12.5%
Stage 2: 12.5% → 15%
Stage 3: 15% → 17.5%

Per-stage gate (not time-locked):
  - no execution issue
  - no unexpected slippage
  - no breach of rolling 20d risk monitor
  - PM confirms operational comfort
```

### Revision 3 — Governance philosophy unchanged
Final memo + SPEC must state:

> **The governance philosophy is unchanged; only numeric caps are updated based on Q073 evidence. Q073 does not overturn Q072 / SPEC-103 governance — it tightens numeric caps within the same framework.**

### Revision 4 — Add 2 monitors

- **Q042 live concentration monitor**: If top-3 live Q042 trades contribute >50% of cumulative Q042 PnL → review trigger
- **SPX normal→stress transition monitor**: Track losses during normal → stress transition windows. If realized loss before stress trigger exceeds expected historical transition loss → review trigger

### Revision 5 — Bootstrap CI wording caution
Final memo MUST NOT present "CI lo +18% ann" as forward ROE forecast. Correct wording:

> **Bootstrap confirms the PnL series is not noise. Expected production ROE remains around the simulated net ROE estimate (~8%), not the bootstrap CI statistic.**

### Revision 6 — Arch-2 fallback clarification
Final memo must clarify:

> **Arch-2 fallback is not risk-preferred; it is implementation-preferred.** It exists only if PM declines HV demotion or Q042 cap increase. Arch-3 is preferred on risk-adjusted basis.

---

## SPEC Structure (2nd Quant approved)

Single integrated SPEC titled: **`SPEC-XXX — Q073 Arch-3 Portfolio Architecture`**

| Section | Content |
|---|---|
| 8.1 SPX state-dependent caps | R1 70→80% / R5 60→50% / R6 50→40% (governance amendment subsection) |
| 8.2 Q042 Sleeve A cap | Target 17.5%, staged ramp (3 stages) |
| 8.3 HV Ladder demotion | Production alloc 0%, research-only / paper-only |
| 8.4 Monitoring | All triggers from final memo §7 + Q042 concentration + SPX transition |
| 8.5 Arch-2 fallback | Implementation-preferred fallback only |

---

## 2nd Quant Sign-off

- [x] PROMOTE Arch-3 verdict acceptable
- [x] Single integrated SPEC scope acceptable
- [x] 6 required revisions specified
- [x] No further methodology work required before SPEC

→ Quant applies 6 revisions to final memo, then hands off to PM for SPEC drafting.
