# Q074 P5 — G4 Final 2nd Quant Review Packet

**Date**: 2026-05-18
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **G4 mandatory final review** (per P0 §9) — gate before SPEC-105 drafting
**Decision sought**: PASS / REVISE / REJECT Q074 P5 PROMOTE recommendation

---

## 0. TL;DR

Q074 P5 recommendation: **PROMOTE B4 moderate 90% as staged Bull Regime Booster overlay** (Layer-2 income optimization on top of Arch-3 / SPEC-104).

```
B4 booster active conditions (all required):
  NOT stress_active
  NOT second_leg_active
  SPX > MA50
  ddATH > -4%
  VIX < 22
  VIX 5d change ≤ +1.5
  IVP_252 < 55

When all true → Normal SPX cap 80% → 90%
When any false → fall back to Arch-3 state machine (80/50/40)
```

**Expected**: Net ROE 7.95% → 8.20% (+0.25pp), tail unchanged.

**Strong-eligible classification** (per G3 Q6 framework): point estimate +0.25pp vs +0.30pp Strong threshold, gap (0.048pp) is half of bootstrap noise σ (0.10pp) → economically equivalent to Strong, **acceptable for staged production**.

---

## 1. P4 Validation Pass Summary

| P4 test | B4 result | Verdict |
|---|---|---|
| V6 Bootstrap (block=250, 20 seeds) | sig 100%, noise σ ~0.10pp | PASS |
| V7 Walk-forward H1/H2 | H1 8.42% / H2 14.52%; both ≥ 8% floor | PASS |
| Friction sensitivity ±50% | ΔROE stable at +0.25pp | PASS |
| Episode-level transition (10d) | cum +$214k, worst -0.15% NLV | PASS |
| VIX 20-22 joint slice | All 20 days IVP<30 + shallow ddATH + falling VIX | EXPLAINED |
| Funding stress +600bp | ΔROE only -0.013pp degradation | PASS |
| B4 vs B3 active overlap | +183 B4-only days, +$52k incremental, all clean | PASS |
| Crisis windows (5 events) | All essentially unchanged | PASS |
| Synthetic crisis injection | Only -0.01pp impact | PASS |

**B4 elevated from Soft Pass (P2) to "Strong-eligible / production-acceptable" (P5)** based on this P4 evidence + bootstrap noise analysis.

---

## 2. Six Questions for G4 Final Review

### Q1 — Strong-eligible characterization

Is "Strong-eligible / production-acceptable" the correct verbal framing for B4 +0.25pp ΔROE vs +0.30pp threshold?

Quant proposal: yes — gap is half the bootstrap noise, economically equivalent. PM should treat as **staged production** (not full one-shot deployment).

**2nd Quant: confirm classification, or require alternative wording (e.g., "high-quality Soft Pass with paper-only deployment")?**

### Q2 — Tail invariance check

P4 shows MaxDD, Worst 20d, Worst 63d ALL unchanged (0.00pp Δ) between Arch-3 and B4. This is structurally driven by state machine priority (snap-back to 50%/40% during stress/2nd-leg).

**Concern**: Is "tail invariant by design" too clean? Should we verify with additional synthetic shocks (e.g., shock during 2018-Q1 calm period when B4 active, not just 2017)?

Quant prior: P4.9 synthetic shock confirmed robustness. Multiple synthetic shocks would add diminishing evidence.

### Q3 — VIX 20-22 explanation acceptable

P4.5 shows B4 booster-active at VIX 20-22 only on 20 days over 26y, ALL with IVP < 30 + ddATH > -3% + VIX_5d_change ≤ 0. This explains why "danger bucket" doesn't manifest as losses.

**Concern**: Sample is sparse (n=20). Live monitoring should track if this characteristic holds. Is the joint-slice analysis sufficient evidence for G4, or should we expand the slice (e.g., include VIX 18-20 days)?

### Q4 — H1 vs H2 walk-forward concern

H1 (2000-2012) booster contribution = 0. H2 (2013-2026) booster contribution = +0.69pp.

**The +0.25pp ΔROE is entirely H2-driven**. Is this acceptable as "design working correctly" (booster off in hostile regime, on in benign) or as a concern about regime over-fit?

Quant position: **Acceptable per design intent**. Layer-2 booster is supposed to capture benign-regime opportunity; H1 regime hostility correctly suppresses booster. Both halves still pass floor 8% individually.

### Q5 — B4 vs B3: should both promote, or B4 alone?

Q074 P5 recommends B4 promote; B3 as fallback option. B4-only days (183) add +$52k clean incremental.

**Concern**: Should SPEC-105 implement B4 only, or also provide B3 as runtime-selectable variant (in case PM wants to dial back booster aggressiveness)?

Quant proposal: **B4 only in production code**, B3 as documented fallback in SPEC-105 §rollback. Avoids state machine complexity.

### Q6 — SPEC handoff scope

Q074 P5 recommends SPEC-105 as amendment to SPEC-104 R1 normal cap (state machine extension).

**Is the scope right?**
- Add booster cap (90%) + benign signal definition
- DO NOT modify Q042 staged ramp, HV Ladder demotion, stress/2nd-leg caps
- DO NOT modify V1-V7 vetoes

Quant proposal: minimal SPEC scope to reduce implementation risk. Monitoring obligations included.

---

## 3. Caveats Self-Disclosed (carry from P4 memo)

1. ROE upside concentrated in H2 (post-2013 bull regime)
2. VIX 20-22 sample sparse (n=20 over 26y)
3. Funding cost assumed BOXX yield (+ stress); real margin cost depends on broker
4. Q42 simultaneously at 17.5% target → combined exposure 107.5% during booster days
5. B4 promotes to SPEC-105 with STAGED rollout (paper/shadow → production)
6. B1/B2 NOT promoted (ROE too small)

---

## 4. Decision Matrix

| Reviewer verdict | Action |
|---|---|
| **PASS G4** + Q1-Q6 satisfactorily answered | Quant proceeds to draft SPEC-105 |
| **REVISE** (specific wording / scope) | Quant updates P5 memo + re-submits |
| **REJECT** (B4 not acceptable for production) | Q074 closes; Arch-3 SPEC-104 stays as-is |
| **PROMOTE B3 instead** | Quant adjusts SPEC-105 to use B3 strict 90 |
| **REVISE to require additional pre-SPEC checks** (e.g., 3-month paper before SPEC) | Quant defers SPEC-105 drafting until paper period |

---

## 5. Quant Researcher Sign-off

Quant submits Q074 P5 for G4 final review 2026-05-18. Awaiting verdict.

> Q074 found a clean Layer-2 income booster: B4 raises SPX normal cap to 90% only on multi-signal benign confirmation, snaps back to 50%/40% on stress/second-leg. P4 validates all tail-protective claims (MaxDD/W20d/W63d unchanged), bootstrap robust, walk-forward both halves pass floor 8%, funding stress robust. Point estimate ROE +0.25pp is below the +0.30pp Strong threshold but within bootstrap noise → "Strong-eligible / production-acceptable" for staged deployment.

---

## 6. Supporting Files

- `research/q074/q074_final_memo.md` — P5 decision (full)
- `research/q074/q074_p4_validation_memo.md` — P4 evidence
- `research/q074/q074_p3_transition_forensic_memo.md` — P3
- `research/q074/q074_p2_booster_sweep_memo.md` — P2
- `research/q074/q074_p1_attribution_memo.md` — P1
- `research/q074/q074_p0_anchored_memo_2026-05-17.md` — P0
- `task/q074_framing_2nd_quant_review_packet_2026-05-17_Review.md` — pre-research PASS
- `task/q074_p3_g3_2nd_quant_review_packet_2026-05-18_Review.md` — G3 PASS w/ revisions
- All P*-script.py + *.csv outputs in `research/q074/`
