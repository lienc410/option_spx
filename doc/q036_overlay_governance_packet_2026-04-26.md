# Q036 Overlay Governance Packet v1

- Date: 2026-04-26
- Owner: Planner / PM
- Topic: `Q036 — Idle BP Deployment / Capital Allocation`
- Packet status: PM reviewed — governance Option B selected
- Current candidate: `Overlay-F_sglt2`
- Research posture entering this packet: **PASS WITH CAVEAT**

---

## 1. Purpose

This packet is the governance-stage follow-up to PM’s earlier `Option B` decision on `Q036`.

The prior packet answered:

> Is there now a sufficiently credible overlay candidate to deserve PM governance judgment?

PM’s answer was **yes**.

This packet answers the next question:

> Given that `Overlay-F_sglt2` is worth continued governance attention, what exact prerequisites, guardrails, and monitoring requirements must be satisfied before the project should even consider a DRAFT overlay spec?

This packet is therefore:

- later than pure research
- earlier than DRAFT-spec discussion
- strictly about governance readiness

---

## 2. Current PM Position

PM has already chosen:

> Advance `Overlay-F_sglt2` into a more formal overlay discussion under the capital-allocation layer.

Current meaning:

- `Q036` remains open
- `Overlay-F_sglt2` remains the lead candidate
- the branch is beyond exploratory research
- we are now defining what “promotion readiness” would actually require

This still does **not** mean:

- no DRAFT overlay spec is open
- no Developer implementation is authorized
- no live rollout is authorized
- `SPEC-066` remains unchanged
- `Q021` remains a rule-layer evidence base, not an active semantic dispute

## PM Decision

PM has now selected **Option B** at this governance stage:

> Authorize a **Productization Prerequisite Memo** for `Overlay-F_sglt2`.

Operational meaning:

- `Q036` remains in structured governance / planning
- the branch advances one narrow step beyond general governance review
- the next artifact should define exact blockers between `Overlay-F` and any future DRAFT overlay spec

This still does **not** mean:

- no DRAFT overlay spec is open yet
- no implementation is authorized
- no runtime or live behavior should change

---

## 3. Candidate In Scope

### `Overlay-F_sglt2`

Current research definition:

- `2x` iff `idle BP >= 70%`
- `VIX < 30`
- `pre-existing short-gamma count < 2`

Current meaning:

- capital-allocation overlay on top of baseline behavior
- judged against idle-capital baseline
- not a rule replacement
- strongest current compromise between uplift and cleanliness

Current top-line result:

- full-sample annualized ROE uplift: `+0.074pp`
- recent-era (`2018+`) annualized ROE uplift: `+0.040pp`
- disaster-window net: unchanged at `+301`
- peak BP: `34%` vs baseline `30%`
- reported `SG>=2` fires: `0 / 23`

Interpretation:

- good enough to keep alive
- not strong enough to self-justify productization

---

## 4. What Is Already Settled

The following should now be treated as established inputs, not reopened research questions:

1. `Q036` is a **capital-allocation** problem, not a `Q021` rule-replacement problem.
2. Idle BP is structurally abundant under the baseline.
3. `Overlay-F_sglt2` is the correct lead candidate.
4. The branch should not be widened with more horizontal variant search.
5. The branch is not DRAFT-spec ready.
6. There is a disclosed methodology caveat:
   - reported cleanliness is on stricter `position-count`
   - gate still uses `family-deduplicated` counting
   - any future productization path must align the gate to `position-count`

References:

- `doc/q036_pm_decision_packet_2026-04-26.md`
- `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
- `task/q036_quant_review_packet_2026-04-26.md`

---

## 5. Governance Question Now in Front of PM

At this stage PM is no longer deciding whether `Overlay-F` “works.”

PM is deciding:

> Is `Overlay-F_sglt2` strong enough, and clean enough, to justify a formal productization-prerequisite phase?

That is a narrower and more practical question than:

- “Should we ship it?”
- “Should we open a spec tomorrow?”

This distinction matters because the current evidence supports:

- governance attention

but does **not** yet support:

- automatic implementation work

---

## 6. Non-Negotiable Boundaries

Any next-stage work must preserve these boundaries unless PM explicitly changes them:

1. `SPEC-066` stays unchanged.
2. `Q021` stays closed / closing as rule-layer evidence base.
3. Overlay remains a **capital-allocation layer** concept.
4. No silent conversion into a rule-layer size rewrite.
5. No silent removal of the methodology caveat.
6. No productization framing that overstates the current evidence.

---

## 7. Mandatory Pre-Spec Prerequisites

Before any DRAFT overlay spec discussion, the following should be explicitly settled.

### 7.1 Gate / Metric Semantic Alignment

Current state:

- gate uses `family-deduplicated short-gamma count`
- cleanliness / framing metric is reported in `position-count` terms

Current packet posture:

- this is disclosed
- it is no longer a PM-packet blocker
- it is still a real productization issue

Required before serious spec promotion:

- gate must align to `position-count`
- packet language must describe one canonical semantic only

Planner view:

- this should be treated as a **pre-spec hygiene requirement**
- not as optional polish

### 7.2 Canonical Risk Policy

Before any spec promotion, the project needs explicit policy for:

- what counts as unacceptable short-gamma stacking
- what counts as unacceptable peak BP%
- what counts as unacceptable disaster-window degradation
- what counts as margin-stress / forced-liquidation warning territory

Without this, even a technically clean candidate would still lack a governance contract.

### 7.3 Opportunity-Cost Policy

Current baseline is still:

- if no better use exists, idle BP may remain idle

But pre-spec planning should define:

- when `/ES` or another sleeve would outrank `Overlay-F`
- whether future multi-sleeve competition should block overlay deployment
- whether `Overlay-F` is a default idle-capital consumer or only a fallback

This does not need to be solved now across all future strategies, but the project needs a minimal stated policy before productization.

---

## 8. Monitoring / Telemetry Requirements

If the branch ever advances beyond governance discussion, the following observability must exist first.

### 8.1 Entry-Time Context Logging

Need durable logging of:

- idle BP at fire
- VIX bucket
- pre-existing short-gamma count
- disaster-cap state
- whether a boosted overlay fire occurred

### 8.2 Exposure / Concentration Monitoring

Need account-level observability for:

- total short-gamma count
- overlay-specific exposure share
- peak BP%
- overlay contribution to drawdown windows

### 8.3 Risk Alerts

Minimum candidate alerts:

- overlay fired near concentration threshold
- overlay + baseline pushed BP above policy threshold
- repeated overlay clustering in a short window
- overlay fires entering a near-disaster context

### 8.4 Review Loop

Need a defined review cadence for:

- realized uplift
- realized tail contribution
- realized stacking incidents
- disaster-window behavior

Planner view:

- if the project cannot describe these monitoring requirements concretely, it is not ready to discuss a spec

---

## 9. Open Governance Questions

These are the right next questions. They are governance questions, not open-ended research questions.

1. What minimum uplift is enough to justify an overlay governance layer?
2. How much tail deterioration is acceptable for a thin ROE gain?
3. Should recent-era evidence carry more weight than full-sample evidence?
4. Is `Overlay-F` merely a monitored candidate, or a realistic future implementation candidate?
5. Must semantic alignment happen before DRAFT, or can DRAFT open with that as a named blocker?

Planner view:

- none of these require reopening the variant tree
- all of them affect whether the branch should remain governance-only or move toward spec discussion

---

## 10. Recommended Immediate Next Artifact

Planner recommendation:

> The next artifact should be a **Productization Prerequisite Memo**.

Why this is the right next step:

- the branch is already beyond “does the candidate exist?”
- it is not yet at “open a spec”
- the highest-value missing information is now governance / telemetry / semantic-cleanup structure

What that memo should do:

- define the exact blockers between `Overlay-F` and any future DRAFT spec
- separate hard blockers from soft monitoring expectations
- state the minimum semantic cleanup needed
- define minimum telemetry and review loop requirements
- define the minimum safe first scope if the project ever promotes the branch

What it should **not** do:

- reopen new variants
- rewrite `SPEC-066`
- imply that implementation is already expected

---

## 11. Option Set for PM

At this governance stage, PM’s meaningful options are now:

### Option A — Stop at governance-reviewed research

Meaning:

- `Overlay-F` stays as a documented positive research result
- no further promotion work
- no productization-prerequisite phase

Use this if PM decides:

- uplift is too thin
- governance cost is not worth it

### Option B — Authorize a Productization Prerequisite Memo

Meaning:

- continue the branch one narrow step
- do not open a DRAFT spec yet
- formalize exact blockers, telemetry, semantic cleanup, and minimum-first-scope conditions

Use this if PM decides:

- the candidate is strong enough to deserve structured readiness work
- but not strong enough to justify spec promotion today

### Option C — Directly authorize a Narrow DRAFT-Readiness Review

Meaning:

- skip the broader prerequisite memo
- immediately ask what exact blockers remain before DRAFT

Planner caution:

- this is probably too aggressive at the current evidence level
- it risks compressing governance and productization questions into one step

---

## 12. Planner Recommendation

Current planner recommendation:

> **Option B** — authorize a Productization Prerequisite Memo for `Overlay-F_sglt2`.

Reasoning:

- stronger than mere research curiosity
- weaker than implementation-ready
- exactly in the zone where governance structure matters most

This keeps momentum without overstating readiness.

---

## 13. PM Decision Block

PM has chosen:

- `B` — authorize a Productization Prerequisite Memo for `Overlay-F_sglt2`

This means the next planning artifact should be a narrower memo focused on:

- semantic cleanup prerequisites
- telemetry / monitoring requirements
- hard blockers vs soft readiness items
- minimum safe first scope if the branch ever advances toward DRAFT

---

## 14. Historical Decision Block

Please choose one:

- `A` — stop at governance-reviewed research; no further promotion
- `B` — authorize a Productization Prerequisite Memo for `Overlay-F_sglt2`
- `C` — authorize a narrow DRAFT-readiness review immediately

If `C`, confirm that PM accepts the risk of compressing governance and pre-spec questions into one step.

---

## 15. Source Pack

- `doc/q036_pm_decision_packet_2026-04-26.md`
- `doc/q036_framing_and_feasibility_2026-04-26.md`
- `doc/q036_phase3_guardrail_refinement_2026-04-26.md`
- `doc/q036_phase4_short_gamma_guard_2026-04-26.md`
- `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
- `task/q036_quant_review_packet_2026-04-26.md`
- `RESEARCH_LOG.md`
- `PROJECT_STATUS.md`
- `sync/open_questions.md`
