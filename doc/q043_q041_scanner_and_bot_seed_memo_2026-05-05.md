# Q043 — Q041 Scanner and Bot Support Seed Memo

Status: seed / low-to-medium priority future support branch

## Purpose

Preserve a bounded next-step idea for `Q041` after the current paper-trading support surface is stable:

- automatic scan for `Tier 1 / Tier 2 / Tier 3` entry windows
- optional close / review reminders for existing paper trades
- bot-based delivery of **recommendation / reminder only**

This memo is intentionally **not** a production-trading proposal and **not** an expansion of `SPEC-083`.

## Why This Exists

`SPEC-083` deliberately stopped at:

- paper-trade ledger
- manual logging
- BP budget tracking
- review export
- minimal visibility

That was the right first step. But once paper trading begins, the next obvious operator pain point is:

- remembering when `SPX CSP` / `GOOGL` / `AMZN` monthly windows are live
- remembering when `COST / JPM` earnings `T-3` windows are near
- checking budget / gate status before acting
- surfacing close / expiry review items without manual scanning

This branch exists to support those workflows without turning `Q041` into a second live strategy engine.

## Scope Principle

Treat `Q043` as a **recommendation and reminder support layer**, not a new execution engine.

The intended posture is:

- scanner first
- shadow output first
- dev-facing notification surface first
- no automatic order placement
- no merge into current SPX recommendation engine

## Proposed Phasing

### Phase A — Shadow Scanner

Run a read-only scanner that evaluates whether current market state matches known `Q041` candidate entry rules:

- Tier 1: `SPX CSP Δ0.20 DTE30`
- Tier 2: `GOOGL CSP Δ0.20 DTE21`, `AMZN CSP Δ0.25 DTE21`
- Tier 3: `COST / JPM` earnings IC with `VIX >= 15`

Output should be structured and auditable, for example:

- `candidate_found`
- `tier`
- `symbol`
- `why`
- `hard_gate_passed`
- `bp_impact_est`
- `suggested_dte`
- `suggested_delta_or_structure`

No user-facing action should happen yet beyond logging or a dev-facing surface.

### Phase B — Dev Bot / Shadow Notification

After the scanner is semantically stable, route candidate messages to:

- either a dedicated dev bot / dev chat
- or a clearly segregated dev-mode branch of the existing bot

The goal is to evaluate:

- message frequency
- false positives
- whether the recommendation format is actually usable
- whether budget and tier context are sufficient

This phase should still be treated as **shadow**.

### Phase C — Paper-Trade Reminder Support

Add reminder-only support for already recorded paper trades:

- upcoming CSP expiry / monthly roll review
- upcoming `earnings_date - 3` for `COST/JPM`
- possible close / expiry bookkeeping reminder

This is still support tooling, not trade automation.

## In Scope (Future Candidate)

- read-only scanner for Q041 entry windows
- bot/dev-bot recommendation messages
- reminder / review prompts for existing paper trades
- structured candidate audit log
- budget-aware candidate surfacing

## Out of Scope

- automatic order placement
- automatic close execution
- broker write integration
- auto-promotion of candidates
- full live mark-to-market engine
- full live Greeks dashboard
- integration into current SPX main recommendation engine

## Preferred Delivery Order

1. Scanner + audit log
2. Dev bot / shadow notifications
3. Existing-paper-trade reminders
4. Only then consider broader surfacing in main runtime

## Key Risk

The main failure mode is product creep:

- turning a support tool into a second live strategy system
- mixing `Q041` paper-trading signals with current SPX production recommendation paths
- pushing noisy recommendations into the main bot before shadow quality is understood

## Current Planner Position

`Q043` is worth preserving, but it should remain **behind**:

- `Q041` paper-trading start-up
- ongoing `Q041` overlap validation
- `Q036` / `Q038` monitoring
- `/ES` runtime-safeguard follow-up

The likely next formal step, when promoted, would be a narrow DRAFT spec around:

- `Q041 shadow scanner + bot recommendation support`

not a large multi-surface product build.
