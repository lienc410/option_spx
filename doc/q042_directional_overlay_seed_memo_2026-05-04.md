# Q042 — Directional Overlay Seed Memo

**Date:** 2026-05-04  
**Type:** low-priority research seed  
**Status:** indexed only; not in active queue

## One-line framing

Current strategy research is still dominated by non-directional / weakly directional premium-harvest logic.  
`Q042` is a placeholder for a future branch that would test **explicit directional overlays** on major SPX drawdowns or post-technical reversals.

## Why this exists

- Most current production and research candidates are income / carry / overlay variants with limited directional expression.
- The main existing directional exception is the aftermath branch (`SPEC-064` lineage), which is still structurally narrow.
- This seed is meant to preserve a future idea without interrupting:
  - `Q041` Phase 2
  - `Q036` shadow observation
  - `Q038` shadow monitoring

## Candidate sub-branches

### A. Drawdown-triggered convex upside

Example frame:
- buy `LEAP call` or `call spread` after `SPX` draws down by `x%` from a recent high

Core questions:
- what drawdown thresholds are worth testing (`5% / 8% / 10% / 15%` style buckets)
- whether entry should be:
  - one-shot
  - staged
  - gated by realized-vol / VIX context
- whether expression should be:
  - outright LEAP call
  - call spread
  - defined-risk vertical ladder

### B. Technical reversal / base-formation timing

Example frame:
- enter after a stop-falling / reclaim / base-confirmation event rather than on raw drawdown alone

Core questions:
- does technical confirmation materially reduce “too early” entries
- what confirmation is most defensible:
  - reclaim of moving average
  - breadth / vol normalization
  - multi-day higher-low structure
- how much upside is lost by waiting for confirmation

## Initial research questions

1. After which `SPX` drawdown depths does `3–12` month convex upside become most attractive on a risk-adjusted basis?
2. Which payoff expression is most suitable for account-level ROE:
   - LEAP call
   - call spread
   - another defined-risk convex structure
3. Is a pure drawdown trigger good enough, or does technical confirmation materially improve entry quality?

## Out of scope for now

- no DRAFT spec
- no implementation work
- no new runtime/deployment path
- no interruption of `Q041 / Q036 / Q038`
- no assumption that directional overlays should replace the current income-first stack

## Revisit trigger

Reopen this seed only after current top-line research pressure eases, most likely when:
- `Q041` Phase 2 has a stable shortlist and fewer P0/P1 unknowns
- `Q036` shadow observation has produced enough runtime evidence
- `/ES` runtime-safeguard backlog is no longer the highest practical blocker

## Current planner status

- keep as **future research seed**
- low priority
- do not route to Quant yet unless PM explicitly promotes it
