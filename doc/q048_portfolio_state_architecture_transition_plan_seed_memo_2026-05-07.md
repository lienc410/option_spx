# Q048 — Portfolio-State Architecture Transition Plan

Date: 2026-05-07
Owner: Planner / PM
Status: Planning item / not a Spec

## Trigger

After `Q045` and `Q046`, the project is no longer just optimizing a single SPX strategy matrix. The top-level objective is now explicitly **account-level deployment efficiency and ROE under risk guardrails**. At the same time, `Q041` has introduced a second rail:

- core SPX live recommendation / current-position system
- separate multi-record paper-trade ledger for broader underlying coverage

This means the project has entered a transition stage from a **single-strategy execution platform** toward a **portfolio research platform**.

## Core Diagnosis

The current codebase still treats the following as canonical:

- one primary recommendation
- one current live position
- one SPX-centered backtest / research surface

That assumption now conflicts with the emerging research program:

- `Q041` is the primary post-`Q045` deployment-efficiency axis
- `Q046` concluded that broader strategy / underlying coverage is the most important next mechanism for filling idle BP
- paper-trading, review-only sleeves, and future non-SPX sleeves need a common portfolio language

This is not yet a request for a large implementation spec. It is a planning problem:

> what must be abstracted first so that portfolio-level research can proceed cleanly without destabilizing the current SPX live rail?

## What Makes This Different From “Add One More Strategy”

Adding another SPX strategy would preserve the old assumptions:

- same underlying
- same recommendation surface
- same current-position model
- same backtest narration

The current transition breaks those assumptions. The relevant unit is no longer just trade quality; it is:

- sleeve-level BP contribution
- idle-day capture
- overlap with incumbent sleeves
- marginal account-level ROE
- concentration vs diversification role

## Main Architecture Gaps

### 1. Single-position state model

Current live state is still anchored on one `current_position.json` and a single `position_action` loop. This is insufficient for:

- live positions + paper positions + observe-only records
- multiple underlyings
- more than one active sleeve

### 2. Single-answer recommendation model

Current recommendation semantics produce one canonical recommendation. Portfolio research requires a separation between:

- candidate generation
- portfolio actioning / selection

### 3. Split bookkeeping models

Current live SPX state and `Q041` paper ledger already behave like two different systems. Without a shared portfolio abstraction, future work will continue to fork.

### 4. SPX-centric frontend and backtest information architecture

Current dashboard and backtest surfaces narrate:

- one main strategy recommendation
- one current position
- one SPX-centric trade / price / signal universe

Portfolio research needs:

- current book summary
- BP usage by bucket
- idle capacity
- sleeve contribution and overlap views

### 5. Missing portfolio governance vocabulary

The project now implicitly distinguishes:

- production SPX sleeves
- capital-fill sleeves
- tail-caveated sleeves
- observe-only sleeves

But that taxonomy is not yet a formal platform/governance object.

## Recommended Planning Boundary

Q048 should remain a **planning / architecture item**, not an implementation spec.

### In Scope

- define the minimum portfolio-state abstraction needed for future work
- define how live / paper / observe-only rails should share bookkeeping semantics
- define what should remain research-only vs what should become platform infrastructure
- define a staged transition plan that preserves the current SPX live runtime

### Out of Scope

- no immediate large frontend rewrite
- no immediate “multi-strategy product launch”
- no broker write integration changes
- no automatic candidate scanner / event scheduler work
- no attempt to unify SPX live recommendation and Q041 paper rails into one runtime engine yet
- no promise of full multi-underlying joint backtest simulation in this planning item

## Recommended Staging

### Stage 0 — Explicit dual-rail acknowledgement

Formally acknowledge:

- SPX main system = canonical live production rail
- Q041 ledger = portfolio-expansion experiment rail

Do not merge prematurely.

### Stage 1 — Portfolio state abstraction

Define minimal shared abstractions such as:

- `PortfolioPosition`
- `PortfolioBook`
- `BookEntrySource` (`live`, `paper`, `observe_only`)
- `BudgetSnapshot`

This is the first foundational step.

### Stage 2 — Recommendation model split

Internally separate:

- `candidates[]`
- `selected_primary`
- `portfolio_constraints`

Retain current `/api/recommendation` compatibility while planning the split.

### Stage 3 — Minimal portfolio summary surface

Before any full dashboard redesign, define a minimal read-only surface for:

- current positions list
- BP usage by bucket
- idle capacity
- recent candidate captures
- next review item

### Stage 4 — Portfolio attribution research surface

Add research-facing interfaces for:

- BP utilization by time
- idle-day capture
- overlap matrix
- per-underlying contribution
- fill contribution

Do this before attempting a full multi-asset simulator redesign.

### Stage 5 — Decide whether unified portfolio routing is needed

Only after the prior stages stabilize should the project decide whether to unify:

- SPX live recommendation
- Q041 paper candidates
- future non-SPX sleeves

into one portfolio action engine.

## Immediate Next Step

Do not open a large implementation spec yet.

Instead, use Q048 as the planning container to decide:

1. what the minimum shared portfolio abstractions are
2. what should be implemented first as infrastructure
3. which future spec(s) should be opened, if any

## Recommended Follow-up Split

- **Planner / architecture work**: finish Q048 planning and propose one or two narrow future specs
- **Quant work**: keep `Q041` on the current evidence-accumulation path; do not reopen broad platform research
- **Developer work**: do not start implementation until Q048 is narrowed into an approved, staged spec
