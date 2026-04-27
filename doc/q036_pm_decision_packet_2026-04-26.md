# Q036 PM Decision Packet

- Date: 2026-04-26
- Owner: Planner / PM
- Topic: `Q036 — Idle BP Deployment / Capital Allocation`
- Packet status: PM reviewed — Option B selected
- Research verdict entering this packet: **PASS WITH CAVEAT**

---

## 1. Decision Request

This packet asks PM to make a governance decision on `Q036` after Quant completed:

- Phase 1 feasibility
- Phase 2 narrow overlay pilots
- Phase 3/4 guardrail refinement
- Phase 5 final confirmation on `Overlay-F_sglt2`
- external review reconciliation (`2nd Quant CHALLENGE`, `3rd Quant PASS`, final Quant verdict `PASS WITH CAVEAT`)

The core decision is **not** whether `SPEC-066` should change.

The core decision is:

> Should the project stop at research, or should it advance `Overlay-F_sglt2` into a more formal overlay discussion under the capital-allocation layer?

This packet is intended to answer:

- “Is there now a sufficiently credible overlay candidate to deserve PM governance judgment?”

This packet is **not** intended to answer:

- “Should we open implementation work now?”

## PM Decision

PM has now selected **Option B**:

> Advance `Overlay-F_sglt2` into a more formal overlay discussion under the capital-allocation layer, but do **not** open a DRAFT overlay spec yet.

Operational meaning:

- `Q036` moves beyond pure research and beyond packet-readiness
- the branch remains outside implementation
- the methodology caveat remains active
- any future productization path must still align the gate to position-count short-gamma semantics

---

## 2. Scope Boundary

This packet is strictly about:

- account-level idle BP deployment
- account-level ROE improvement under risk guardrails
- a capital-allocation overlay on top of the existing baseline

This packet is **not** about:

- replacing `V_A / SPEC-066` as the canonical rule
- reopening `Q021` semantic disputes
- changing current production behavior
- opening an implementation spec by default

Current framing remains:

- `Q021` = rule-layer evidence base
- `Q036` = capital-allocation research branch
- `Overlay-F_sglt2` = current lead candidate only

---

## 3. PM Objective

Top-level project objective:

> reasonably maximize account-level ROE

“Reasonably” currently means:

- avoid unacceptable drawdown
- avoid margin stress / forced-liquidation risk
- avoid hidden short-gamma concentration
- avoid deploying BP into overlays that crowd out better uses

Current opportunity-cost baseline:

- `A` = if no better use exists, idle BP may remain idle

This matters because `Q036` is judged against the **idle-capital baseline**, not against `V_A`’s rule-layer `PnL/BP-day`.

---

## 4. Candidate Under Review

### `Overlay-F_sglt2`

Definition:

- `2x` iff `idle BP >= 70%`
- `VIX < 30`
- `pre-existing short-gamma count < 2`

Layer:

- capital-allocation overlay

Not a claim:

- this is **not** a proposal to replace `SPEC-066`

Current interpretation:

- `Overlay-F` is the first candidate on the branch that appears economically positive, governance-aware, and not obviously dominated by a cleaner or stronger neighbor

---

## 5. Why Q036 Was Opened

Baseline observations that motivated the branch:

- account BP usage under baseline is structurally low
- idle BP is persistent and large
- rule-layer evidence from `Q021` showed that direct sizing-up did **not** justify replacing baseline rules
- therefore the remaining question shifted from rule design to capital deployment

One-line rationale:

> If large idle BP exists and the baseline rule is already fixed, the next legitimate question is whether a guarded overlay can improve account-level ROE without introducing unacceptable tail cost.

---

## 6. Research Path Completed

### Phase 1 — Feasibility

Question:

- Is idle BP persistent enough to justify overlay research?

Answer:

- Yes

Key evidence:

- average BP used: `8.68%`
- average idle BP: `91.32%`
- maximum BP used across full sample: `30%`
- aftermath days with `>= 70%` idle BP: `100%`
- disaster windows still retained large idle BP

Main risk discovered:

- capacity is not the bottleneck
- short-gamma stacking is

Reference:

- `doc/q036_framing_and_feasibility_2026-04-26.md`

### Phase 2 — Narrow Pilot Set

Variants:

- `Overlay-A`
- `Overlay-B`
- `Overlay-C`

Conclusion:

- positive incremental return exists
- but raw pilots were not clean enough for spec escalation
- `Overlay-A` was effectively eliminated
- branch narrowed to `B` vs `C`

Reference:

- `backtest/prototype/q036_phase2_overlay_pilots.py`
- summary in `RESEARCH_LOG.md`

### Phase 3/4 — Guardrail Refinement

Goal:

- reduce stacking without fully killing uplift

Conclusion:

- `Overlay-F_sglt2` emerged as the first credible compromise candidate:
  - cleaner than `Overlay-B`
  - materially less over-constrained than `Overlay-D`

References:

- `doc/q036_phase3_guardrail_refinement_2026-04-26.md`
- `doc/q036_phase4_short_gamma_guard_2026-04-26.md`

### Phase 5 — Final Narrow Confirmation

Goal:

- confirm that `Overlay-F` is not a fragile artifact

Conclusion:

- uplift is sparse but distributed
- fire distribution matches design
- recent era remains positive, though thinner
- no evidence supports widening the research tree further

Reference:

- `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`

---

## 7. Top-Line Summary for PM

### Full Sample

| Metric | Baseline | Overlay-F | Delta |
|---|---:|---:|---:|
| Total PnL | `+$403,850` | `+$412,855` | `+$9,005` |
| Annualized ROE | `8.675%` | `8.748%` | `+0.074pp` |
| MaxDD | `-10,323` | `-9,749` | improved |
| CVaR 5% | `-4,309` | `-4,382` | worse by `74` |
| Peak BP% | `30%` | `34%` | worse by `4pp` |
| Disaster-window net | `+301` | `+301` | unchanged |

### Recent Era (`2018+`)

| Metric | Baseline | Overlay-F | Delta |
|---|---:|---:|---:|
| Total PnL | `+$164,958` | `+$169,353` | `+$4,395` |
| Annualized ROE | `5.544%` | `5.583%` | `+0.040pp` |
| MaxDD | `-9,405` | `-9,392` | flat / slightly better |
| CVaR 5% | `-3,798` | `-3,798` | flat |
| Peak BP% | `30%` | `34%` | worse by `4pp` |

### Fire Distribution

| Slice | Result |
|---|---|
| Total fires | `23` |
| Regime | all `HIGH_VOL` |
| VIX buckets | `20-25: 5`, `25-30: 18` |
| Pre-existing short-gamma count | `0: 9`, `1: 14`, `>=2: 0` |
| Mean idle BP at fire | `80.5%` |

---

## 8. What We Know with Confidence

1. Idle BP is real, persistent, and not a fake bottleneck.
2. `Overlay-F` improves account-level return relative to the idle-capital baseline.
3. `Overlay-F` does not rely on observed `SG >= 2` stacking in the reported cleanliness metric.
4. `Overlay-F` fires only in the intended high-volatility window.
5. The uplift is not explained by only one or two years.
6. Recent-era behavior remains positive, not broken.
7. No evidence suggests further broad variant expansion would materially improve decision quality.

---

## 9. What Is Still Not Proven

1. The uplift is not large.
2. Tail cost is not zero.
3. Recent-era uplift is thinner than full-sample uplift.
4. This is not yet strong enough to self-justify implementation complexity.
5. No evidence yet proves that a production overlay is clearly worth the governance burden.

---

## 10. Methodology Caveat

This packet proceeds under **PASS WITH CAVEAT**, not under a clean unconditional pass.

The caveat is:

- the `Overlay-F` gate currently uses **family-deduplicated** short-gamma counting
- the framing / cleanliness metric is reported in **position-count** terms

Why this is not treated as a packet blocker:

- the headline cleanliness claim (`SG>=2 = 0 / 23`) is already measured on the stricter position-count metric
- Quant has verified that, in this sample, the discrepancy is a **presentation / governance caveat**, not a numerical invalidation

Why this still matters:

- if the branch ever advances toward productization, the gate must be aligned to position-count semantics
- that alignment is a future hygiene requirement, not a reason to reopen the research tree now

Current packet meaning:

- PM may review and decide on the branch now
- but this packet should **not** be read as “methodology fully finalized for implementation”

---

## 11. External Review Convergence

### 2nd Quant

Verdict:

- `CHALLENGE`

Main contribution:

- identified the short-gamma-count semantic split

Accepted:

- framing
- lead candidate selection
- yearly attribution
- disaster posture

### 3rd Quant

Verdict:

- `PASS — ready for PM decision packet`

Main contribution:

- confirmed the branch has crossed the threshold for PM governance review
- still did **not** support direct spec escalation

### Quant integrated ruling

Verdict:

- `PASS WITH CAVEAT`

Meaning:

- packet may proceed
- caveat must be disclosed
- no further research-tree widening is justified before PM review

---

## 12. Decision Framing

PM is not choosing between “works” and “does not work.”

PM is choosing between:

### Option A — Stop at research

Interpretation:

- `Overlay-F` is directionally valid
- but uplift is too small to justify further productization

Pros:

- no new runtime complexity
- no new operational monitoring burden
- no new portfolio-risk management layer

Cons:

- leaves a measured positive idle-capital opportunity unused

### Option B — Advance to a more formal overlay discussion

Interpretation:

- `Overlay-F` is economically and operationally credible enough to justify a formal next stage
- not implementation yet, but no longer just open-ended research

Pros:

- preserves a plausible path to higher account-level ROE
- moves from abstract research into structured governance work

Cons:

- invites a new monitoring / control layer
- still may end in “do not ship”
- future productization would need explicit gate-metric semantic unification

### Option C — Request one final narrow clarification

Interpretation:

- PM is close to deciding, but wants one additional targeted question answered

Constraint:

- it must be materially narrower than reopening overlay exploration

Examples:

- one operational-monitoring burden estimate
- one explicit productization checklist
- one governance-only risk memo

---

## 13. Planner Recommendation

Current planner recommendation:

> **Option B** — advance `Overlay-F_sglt2` into a more formal overlay discussion, but do not open a DRAFT overlay spec yet.

Reasoning:

- the branch has already done the work needed to answer “is there a credible narrow candidate?”
- the answer is yes
- the branch has **not** yet shown enough economic force to justify skipping straight to productization

In other words:

- too strong to stop as mere curiosity
- not strong enough to treat as implementation-ready

That makes a PM governance decision the correct next step.

---

## 14. Explicit PM Decision Block

Please choose one:

- `A` — stop at research; keep `Q036` as a completed research branch, no overlay follow-up
- `B` — advance `Overlay-F_sglt2` into a more formal overlay discussion / next-stage packet
- `C` — request one final narrow clarification before deciding

If `C`, specify the exact remaining question:

- `[fill]`

---

## 15. PM Chose B — Planner Next Step

Planner next steps:

- convert `Q036` from research-only into a more formal next-stage planning packet
- define exact governance / monitoring questions
- preserve the explicit methodology caveat
- keep `SPEC-066` and `Q021` untouched

Not automatic:

- no direct Developer implementation
- no automatic `DRAFT Spec`
- no live rollout

---

## 16. Source Pack

- `doc/q036_framing_and_feasibility_2026-04-26.md`
- `doc/q036_phase3_guardrail_refinement_2026-04-26.md`
- `doc/q036_phase4_short_gamma_guard_2026-04-26.md`
- `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
- `task/q036_quant_review_packet_2026-04-26.md`
- `backtest/prototype/q036_phase1_idle_bp_baseline.py`
- `backtest/prototype/q036_phase2_overlay_pilots.py`
- `backtest/prototype/q036_phase3_guardrail_refinement.py`
- `backtest/prototype/q036_phase4_short_gamma_guard.py`
- `backtest/prototype/q036_phase5_overlay_f_confirmation.py`
- `doc/q021_phase4_sizing_curve_2026-04-26.md`
- `doc/q021_variant_matrix_2026-04-26.md`
