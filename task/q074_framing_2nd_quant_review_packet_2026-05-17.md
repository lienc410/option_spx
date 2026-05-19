# Q074 — Bull Regime Booster Framing Review Packet

**Date**: 2026-05-17
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **Pre-research framing review** (per Q073 P0 / `feedback_survival_vs_income_layering` precedent)
**Decision sought**: PASS / REVISE / REJECT Q074 framing + research plan before P1 compute starts

---

## 0. TL;DR

Q074 = Layer-2 income optimization research. PM 2026-05-17 has pre-defined the full scope:

> **Q074 only researches: in confirmed benign regime, can SPX BPS normal cap be raised from 80% to 85% / 90%? Q073 Layer-1 survival constraints (V1-V7, stress 50%, second-leg 40%, HV demoted, Q042 staged 17.5%) MUST REMAIN UNCHANGED.**

Q074 must answer:
- Net ROE upside possible from booster?
- Transition risk (booster → stress) is the primary failure mode
- Layer-1 vetoes ALL preserved

**Decision before P1**: PM has already approved framing in the brief. Request 2nd Quant framing review for the same gate Q073 had (per `feedback_survival_vs_income_layering` saved memory: "future research must pass independent 2nd Quant framing review per Q073 P0/P3/P5 precedent").

P0 memo: `research/q074/q074_p0_anchored_memo_2026-05-17.md` (PM brief captured verbatim where possible).

---

## 1. Why pre-research framing review

Per `feedback_survival_vs_income_layering.md` (2026-05-17, saved after Q073 closure):

> Future research touching portfolio sizing / cap / capital deployment must:
> - keep Layer 1 floor (V1-V7 + crisis paths) intact
> - **pass independent 2nd Quant framing review per Q073 P0/P3/P5 precedent**

Q074 fits this exactly. Bull regime booster modifies SPX normal cap = capital deployment = governance-adjacent.

Q073 ran framing review BEFORE research started, saved a week of mis-directed work. Q074 should follow the same precedent.

---

## 2. Key Framing Locks (PM-anchored in P0)

### What Q074 CAN modify
- Normal SPX cap: 80% → conditionally 85% / 90% in confirmed benign
- Cash residual: auto-adjusts as result

### What Q074 CANNOT modify (per PM hard constraints)
| Out-of-scope | Why |
|---|---|
| V1-V7 vetoes | Layer-1 unchanged |
| Stress SPX cap (50%) | Survival floor |
| Second-leg SPX cap (40%) | Survival floor |
| 26y window evaluation (incl 2000-04) | "Carve out 2000-04" is wrong direction |
| HV Ladder re-promotion | Per SPEC-104, separate Q-research required |
| Q042 cap beyond 17.5% target | Per SPEC-104 staged ramp |
| Q042 Sleeve B activation | Research-only (Q073 Rule 4, n=5) |
| New strategy primitives | Layer-2 booster only |
| ML / black-box detector | Must be explainable state machine |

### Anti-pattern (saved in memory, explicit reminder for Q074)

> **WRONG**: relax Layer 1 to gain Layer 2 (e.g., "V2 → 12%, exclude 2000-04, raise stress cap to 55%")
>
> **CORRECT**: keep Layer 1 floor intact; selectively raise normal cap on multi-signal benign confirmation with hard snap-back

---

## 3. Hypothesis-Driven Booster Candidates (B0-B4)

NOT brute-force grid. PM pre-defined 4 candidates + control:

| Candidate | Benign signal stack | Booster cap |
|---|---|---|
| B0 control | none (Arch-3 baseline) | 80% |
| B1 strict | SPX>MA50 + MA50 slope>0 + ddATH>-3% + VIX<20 + VIX_5d_change ≤+1.0 + IVP<55 | 85% |
| B2 moderate | SPX>MA50 + ddATH>-4% + VIX<22 + VIX_5d_change ≤+1.5 + IVP<55 | 85% |
| B3 strict + stronger cap | same as B1 | 90% |
| B4 moderate + stronger cap | same as B2 | 90% |

**Snap-back rule (hard, no smoothing)**:
```
priority: second-leg(40%) > stress(50%) > booster(85/90) > normal_base(80%)
```

---

## 4. Phase Plan (per PM brief)

| Phase | Content |
|---|---|
| **P1** | Benign-regime attribution (no booster yet): per-bucket forward 20d/63d PnL distribution, + probability of stress trigger within next 10d/20d (critical predictor of transition risk) |
| **P2** | Booster candidate sweep (B1-B4): full 26y combined-NLV simulator with per-day SPX allocation policy |
| **P3** | **Transition-risk forensic** (CORE): false-benign count, per-transition PnL, top-10 booster losses, 2000-03 / 2007-07 / 2018-02 / 2020-02 / 2022-01 examination |
| **P4** | Validation: bootstrap, walk-forward, friction, crisis comparison vs Arch-3 |
| **P5** | Promote / paper / reject |

---

## 5. Success Criteria

| Tier | Criteria |
|---|---|
| **Strong pass** | ROE +0.30pp / V1-V3 all pass / Worst 20d ≥ -7.54% / transition < 2% NLV / walk-forward both halves pass / bootstrap 80%+ |
| **Soft pass** | ROE +0.10-0.30pp / V1-V3 pass / Worst 20d ~unchanged → paper/shadow only |
| **Fail** | V2 fail, OR worst 20d worsens >1pp, OR transition concentrated 1-2 episodes, OR ROE only in recent 2y, OR V1/V3 fail |

---

## 5.5 — PM Pre-Review Revisions (Applied 2026-05-17)

Before sending to 2nd Quant, PM applied 6 minor revisions to P0 memo:

| # | Revision | Where in P0 |
|---|---|---|
| 1 | Booster activation explicitly requires `not stress_active AND not second_leg_active` | §3 booster table + new gate clause |
| 2 | Success criteria split absolute + relative: Strong pass needs both V2 absolute pass AND worst 20d no worse than Arch-3 by >0.5pp | §6 Strong pass |
| 3 | Soft pass cannot amend SPEC-104 production caps; paper/shadow only | §5 P5 Decision table |
| 4 | P1 look-ahead warning: forward returns for attribution only, not signal construction | §5 P1 new caveat block |
| 5 | Booster breadth diagnostic: if booster active > 60% of normal days → too broad, review | §5 P2 new diagnostic |
| 6 | False-benign loss = incremental loss vs Arch-3 baseline (NOT total) | §5 P3 critical definition |

All 6 revisions applied to P0 memo before this packet was finalized. 2nd Quant sees the revised P0.

---

## 6. Six Questions for 2nd Quant

### Q1 — Framing correct?
PM has pre-defined Q074 as Layer-2 income optimization with Layer-1 frozen. Is this framing complete and unambiguous, or are there ways future research could accidentally weaken Layer 1 (e.g., by re-engineering R5/R6 trigger conditions to be slower → effectively raising stress cap window)?

### Q2 — Benign feature set complete?
PM proposed 5 features (SPX trend, MA50 slope, ddATH, VIX absolute, VIX trend, IVP). Are there other features that should be in benign confirmation? E.g.:
- VIX3M term structure (backwardation / contango)
- 30d realized vol
- Bond yield / equity divergence
- Macro sentiment (PMI, NFP releases)
- Day-of-week or month-of-month (calendar effects)

Quant prior: stick with PM-listed 5 to avoid scope creep; complex features should be Q075+.

### Q3 — Transition risk methodology
P3 transition-risk forensic is Q074's core. Is the definition "booster active in previous 10 trading days AND stress state triggers today" sufficient?

Possible alternatives:
- Longer lookback (20d)?
- Multiple transition severity tiers (mild / acute)?
- Conditional on R6 second-leg follow-on within next 20d?

### Q4 — Snap-back smoothing
PM brief explicitly says "no smoothing" — booster cap 90% can drop to 50% same day if stress triggers. Is hard snap-back the right design, or should we test a 3-day rolling snap-back as B5?

Quant prior: hard snap-back is correct (Q069 smoothing variants all failed in Q063-Q069). But verifying with 2nd Quant since governance-adjacent.

### Q5 — Booster cap upper bound
PM brief proposes 85% / 90% as candidates. Should we also test 95%? 100%?

Quant prior: 90% likely the practical upper bound. 95%+ leaves no cash buffer and would heighten transition risk severely. But should 95% be tested as a control to show upper-bound failure?

### Q6 — Success criteria threshold
PM brief proposes Strong +0.30pp / Soft +0.10-0.30pp. Are these thresholds well-calibrated for Layer-2 marginal optimization?

Quant prior: Q073 found ~7.95% Net ROE Arch-3. Strong +0.30pp would bring portfolio to ~8.25%. Soft +0.10pp ~ 8.05% — just past floor 8%. Calibration seems appropriate but defer to 2nd Quant.

---

## 7. Caveats Self-Disclosed

1. **Backtest sample limited for benign-regime confirmation features**: e.g., MA50 slope + VIX < 20 + IVP < 55 confirmed-benign days are a sub-sample of 26y. Walk-forward H1/H2 may have very different benign-day counts.

2. **Bull-regime booster could overfit recent decade**: 2010-2026 has had unusual low-vol bull stretches. P4 walk-forward MUST separate H1 (2000-2012) from H2 (2013-2026) and ensure booster signal works in BOTH.

3. **Transition risk is the primary failure mode**: P3 must be exhaustive. If 1-2 transitions (e.g., 2018-02 vol spike, 2020-02 COVID onset) concentrate the booster losses, booster is fragile.

4. **Q074 cannot fix HV Ladder issue from Q073**: even if benign booster works, HV Ladder remains demoted (out of Q074 scope per PM).

5. **Friction model assumes per-trade cost stable across allocations**: at 90% SPX cap (booster max), per-trade contract count increases — slippage may not scale linearly. P4 friction sensitivity must test this.

6. **No live data yet for SPEC-104 deployment**: Q074 backtest assumes Arch-3 from 2000-01-01, but Arch-3 only went live 2026-05-17. Forward sample for cap state machine = 0 days.

---

## 8. Decision Matrix

| Reviewer verdict | Action |
|---|---|
| **PASS** framing acceptable | Quant starts P1 attribution; G2 light review after |
| **REVISE** specific points | Quant updates P0 memo + re-submits |
| **REJECT** Q074 framing | Quant defers Q074; PM may revise scope or open Q075 with different approach |
| **REVISE** to add more features (Q2) | Quant expands benign feature set; longer P1 |
| **REVISE** to add B5 smoothing (Q4) | Quant adds B5 to candidate set; longer P2 |

---

## 9. Quant Researcher Sign-off

Quant submits Q074 framing to 2nd Quant for pre-research review 2026-05-17. Awaiting verdict before starting P1 compute.

> **Q074's purpose is to test whether Arch-3 leaves benign-regime ROE on the table, NOT to revisit Q073's survival-floor decisions. Transition risk is the primary failure mode; P3 forensic is the core validation.**
