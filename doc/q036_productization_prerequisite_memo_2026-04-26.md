# Q036 Productization Prerequisite Memo v1

- Date: 2026-04-26
- Owner: Planner / PM
- Topic: `Q036 — Idle BP Deployment / Capital Allocation`
- Candidate in scope: `Overlay-F_sglt2`
- Branch state: governance-approved for continued planning, but **not** DRAFT-spec ready

---

## 1. Purpose

This memo defines the minimum prerequisites that must be satisfied before `Q036` should be allowed to enter any **DRAFT overlay spec discussion**.

It does **not** reopen the research branch.

It does **not** argue that `Overlay-F_sglt2` is already ready for implementation.

Its purpose is narrower:

> Given PM’s choice to continue the branch, what exact semantic, governance, telemetry, and scoping conditions must be met before the project can responsibly discuss a productization path at all?

---

## 2. Candidate Under Consideration

### `Overlay-F_sglt2`

Current research definition:

- `2x` iff `idle BP >= 70%`
- `VIX < 30`
- `pre-existing short-gamma count < 2`

Current standing:

- lead candidate on `Q036`
- economically positive relative to idle-capital baseline
- cleaner than `Overlay-B`
- less over-constrained than `Overlay-D`
- still carries a disclosed methodology caveat

Current top-line evidence:

- full-sample annualized ROE uplift: `+0.074pp`
- recent-era (`2018+`) uplift: `+0.040pp`
- disaster-window net: `+301` (unchanged from baseline)
- peak BP%: `34%` vs baseline `30%`
- reported `SG>=2` fires: `0 / 23`

Interpretation:

- enough to justify continued governance work
- not enough to justify DRAFT-spec promotion by itself

---

## 3. What This Memo Is Not

This memo is **not**:

- a request to modify `SPEC-066`
- a rule-layer sizing rewrite
- an implementation plan
- a runtime rollout plan
- a new research tree for exploring additional overlay families

Current boundary remains:

- `Q021` = rule-layer evidence base
- `Q036` = capital-allocation overlay branch

---

## 4. Current Blocking Picture

`Overlay-F` is no longer blocked at the research level.

It **is** still blocked at the productization-readiness level.

The blockers are no longer “does it work?” blockers.
They are now:

1. **semantic blocker**
2. **risk-policy blocker**
3. **telemetry blocker**
4. **operational review blocker**
5. **first-scope definition blocker**

The rest of this memo spells these out.

---

## 5. Mandatory Pre-DRAFT Requirements

### 5.1 Semantic Alignment Requirement

Current state:

- `Overlay-F` gate uses `family-deduplicated short-gamma count`
- the reported cleanliness metric is in `position-count` terms

Research-stage disposition:

- disclosed
- accepted as a **PASS WITH CAVEAT**
- not a PM-packet blocker

Productization-stage requirement:

- this cannot remain split
- a single canonical short-gamma-count semantic must be chosen
- if the branch moves forward, the gate must align to `position-count`

Minimum done condition:

- one canonical semantic written down
- gate logic and reported cleanliness metric use the same semantic
- the branch description no longer depends on a disclosure footnote to stay coherent

Planner note:

- this is the most obvious “hard blocker before DRAFT”

---

### 5.2 Canonical Risk Policy Requirement

Before productization discussion, the project needs explicit policy definitions for:

- unacceptable short-gamma stacking
- unacceptable peak BP%
- unacceptable disaster-window degradation
- unacceptable margin-stress / forced-liquidation proximity
- acceptable overlay contribution to system drawdown

Minimum done condition:

- each policy dimension has a named threshold or explicit policy rule
- thresholds are separated into:
  - **hard blockers**
  - **monitoring thresholds**
  - **review-only indicators**

Without this, the project would be trying to spec an overlay without a governance contract.

---

### 5.3 Opportunity-Cost Policy Requirement

Current baseline is:

- if no better use exists, idle BP may remain idle

That is enough for research.
It is not enough for productization discussion.

Before DRAFT, the project should define at least a minimum policy for:

- when an overlay is allowed to consume idle BP
- whether baseline sleeves always outrank overlay deployment
- how future sleeves like `/ES` would compete with `Overlay-F`
- whether the overlay is a default idle-capital consumer or only a fallback

Minimum done condition:

- a simple written priority rule for capital use
- not a full portfolio optimizer
- just enough to prevent future ambiguity

---

### 5.4 Monitoring / Telemetry Requirement

If the branch ever becomes more than research, these observability requirements must exist first.

#### Entry-time logging

Need a durable record of:

- idle BP at fire
- VIX bucket
- pre-existing short-gamma count
- disaster-cap state
- overlay-fire timestamp / event context

#### Exposure monitoring

Need account-level observability for:

- total short-gamma count
- overlay-specific exposure share
- peak BP%
- overlay contribution to drawdown windows

#### Risk alerts

Need at minimum:

- overlay fired near concentration threshold
- overlay + baseline pushed BP above policy threshold
- repeated overlay clustering in a short window
- overlay fired in a near-disaster context

Minimum done condition:

- required fields listed
- monitoring owner identified
- alert conditions named, even if not yet implemented

---

### 5.5 Review Loop Requirement

An overlay cannot be productized responsibly without a review loop.

Before DRAFT, the project should define:

- review cadence
- who reviews
- what metrics are reviewed
- what triggers a pause / rollback / re-evaluation

At minimum, the review loop must include:

- realized uplift
- realized tail contribution
- realized stacking incidents
- disaster-window behavior

Minimum done condition:

- a named post-deployment review protocol draft exists

---

## 6. Minimum Safe First Scope

If the branch ever does reach a DRAFT-spec stage, the first scope should remain narrow.

Recommended first-scope constraints:

- `Overlay-F_sglt2` only
- no multi-candidate bakeoff inside the spec
- no rule-layer changes to `SPEC-066`
- no cross-sleeve optimizer
- no auto-expansion to `/ES` or other future sleeves
- keep it as a pure capital-allocation overlay layer

Reason:

- the current evidence supports only one lead candidate
- the current governance maturity is not strong enough for a broad architecture jump

---

## 7. What Should Count as Hard Blockers vs Soft Gaps

### Hard blockers before DRAFT

1. short-gamma semantic alignment not resolved
2. no explicit risk-policy thresholds
3. no minimum monitoring / telemetry design
4. no opportunity-cost policy

### Soft gaps that can remain after DRAFT opens

1. exact UI/UX for monitoring views
2. exact wording of review cadence documentation
3. future multi-sleeve extension planning
4. long-horizon portfolio optimization ideas beyond `Overlay-F`

This distinction is important: we should not hold DRAFT to “everything must already be built,” but we also should not let DRAFT open while core semantic and governance blockers remain undefined.

---

## 8. Recommended Immediate Next Work

Planner recommendation:

> The next work item should be a **Governance Clarification / Productization Prerequisite Note** that explicitly resolves Sections 5.1–5.5 at the policy level.

This should be narrower than a spec and more concrete than a research memo.

It should answer:

- what must be true before DRAFT is even allowed
- what remains productization-risk rather than research-risk
- what minimum safe scope would be if DRAFT is later authorized

It should **not**:

- reopen new variants
- add new backtests unless needed for one blocker
- imply implementation is already expected

---

## 9. Planner Recommendation

Current planner recommendation is:

> Keep `Q036` in the formal governance/planning lane, and do **not** authorize DRAFT overlay spec discussion until the prerequisite items in this memo are explicitly resolved.

That is the cleanest path because:

- the research branch has already narrowed enough
- the remaining unknowns are governance questions, not alpha-discovery questions
- the candidate is promising enough to keep moving, but not strong enough to skip straight to spec

---

## 10. Explicit PM Decision Block

Based on this memo, the next PM choice should be one of:

- `A` — stop here; keep `Overlay-F` as governance-reviewed research only
- `B` — authorize a narrower prerequisite-resolution note covering the blockers in Section 5
- `C` — override planner caution and allow a narrow DRAFT-readiness discussion now

Planner default:

- `B`

Because it preserves momentum while still respecting the branch’s current evidence level.

---

## 11. Source Pack

- `doc/q036_pm_decision_packet_2026-04-26.md`
- `doc/q036_overlay_governance_packet_2026-04-26.md`
- `doc/q036_framing_and_feasibility_2026-04-26.md`
- `doc/q036_phase3_guardrail_refinement_2026-04-26.md`
- `doc/q036_phase4_short_gamma_guard_2026-04-26.md`
- `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
- `task/q036_quant_review_packet_2026-04-26.md`
- `RESEARCH_LOG.md`
- `PROJECT_STATUS.md`
- `sync/open_questions.md`
