# Q050 — Portfolio-Level Shared-BP Governance Framework Seed Memo

Status: open (research seed; not ready for DRAFT Spec)

## One-Line Conclusion

`Q012` now has a correct narrow implementation target at current `/ES` size: stressed-SPAN visibility only.  
That does **not** eliminate the broader portfolio-governance problem. It only means the full problem should be carried as a separate research lane rather than forced into the current `/ES` monitoring spec.

## Why Q050 Exists

Recent work created a useful but important split:

- `Q012` answered the **current-scale** `/ES` question
- `Q041` established a second portfolio-deployment rail
- `Q045` and `SPEC-084` lifted the baseline book into a higher-capital-utilization posture
- `Q046` reframed the main account-level objective around deployment efficiency, not only per-strategy quality
- `Q048` opened the architecture lane for portfolio-state transition

Together, these make one thing clear:

> The project now needs a higher-level research lane for **portfolio-wide shared-BP governance**, separate from any one sleeve’s current implementation target.

`Q050` is that lane.

## What Q050 Is

`Q050` is a **research-driven governance framework question**, not an implementation spec and not a single-strategy follow-up.

Core question:

> As the platform evolves from a single-SPX execution system into a multi-sleeve portfolio research platform, what are the correct account-level governance principles for sharing scarce PM buying power across materially different sleeves?

This includes future coexistence questions such as:

- SPX Credit sleeves
- `/ES` short put sleeves
- `Q041` capital-fill sleeves
- future directional or alternative sleeves

## What Q050 Is Not

`Q050` is **not**:

- a request to widen `SPEC-088`
- a request to reopen `/ES` alpha research
- a request to immediately implement a portfolio allocator
- a request to merge live and paper write paths
- a request to define new runtime broker automation

It is a higher-order research lane whose output may later justify:

- one or more governance specs
- a platform-side budget / allocation abstraction
- a future multi-sleeve research interface

## Why Q012 Is Not Enough

`Q012 Phase C` was valuable precisely because it proved a limit:

- at current live scale (`1` `/ES` contract on `$500k`)
- full shared-BP governance architecture is overdesigned
- the right implementation target is post-entry SPAN visibility

But that conclusion is **local**, not global.

It does not answer:

- what happens when `/ES` scales to `3–5+` contracts
- how `/ES` should coexist with `Q041` if both become material
- whether future sleeves should be prioritized by regime, by capital efficiency, by tail correlation, or by operational simplicity
- what should remain research-governed versus platform-governed

Those are `Q050` questions.

## Candidate Research Questions

### 1. Governance Principle

What should be the top-level governance philosophy when multiple sleeves compete for the same PM BP?

Candidate framings:

- capital-efficiency first
- production-priority first
- regime-priority first
- stress-survivability first
- idle-capacity-first with strict tail guardrails

### 2. Sleeve Role Taxonomy

How should materially different sleeves be categorized once they start competing for real account capacity?

Examples:

- production-alpha sleeve
- capital-fill sleeve
- opportunistic sleeve
- stress-contingent sleeve
- observe-only sleeve

### 3. Scale Triggers

At what scale should a sleeve stop being governed by monitoring-only logic and start being governed by explicit shared-BP rules?

Examples:

- `/ES` at `1` contract vs `3` vs `5+`
- `Q041` Tier 1 only vs Tier 1+2 together

### 4. Stress Hierarchy

When stress arrives, what should compress first?

Examples:

- `/ES`
- SPX Credit
- capital-fill sleeves
- directional sleeves

### 5. Platform Boundary

Which parts of shared-BP governance should remain research-side judgment, and which parts are mature enough to become platform behavior?

## Current Recommended Posture

For now:

- let `Q012` stay narrow and current-scale
- let `SPEC-088` solve the immediate `/ES` monitoring problem
- do **not** widen current implementation to impersonate a full allocator
- keep `Q050` as the explicit home for the broader “don’t think patchwise; think portfolio-wide” requirement

## Not Ready for DRAFT Spec Because

`Q050` is not yet ready for a DRAFT Spec because:

1. the governance principle itself is not frozen
2. sleeve taxonomy is still evolving
3. real coexistence between future materially competing sleeves is still sparse
4. platform-side abstractions should follow, not precede, the research-side governance model

## Recommended Next Step

Treat `Q050` as a standing Quant-side global research lane.

Near-term implication:

- do **not** block `Q012/SPEC-088`
- do **not** force `Q050` into a current implementation scope

Future implication:

- once `/ES` grows materially, or once multiple sleeves begin to compete for capacity in a non-trivial way, `Q050` becomes the correct umbrella for a true shared-BP governance framework study.

