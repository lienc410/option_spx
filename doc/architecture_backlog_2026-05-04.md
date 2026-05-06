# Architecture Backlog (Future Review)

**Date:** 2026-05-04  
**Source:** external system-architecture review synthesized by Planner  
**Intent:** capture absorbable architecture improvements as **medium / low priority** future work, without changing current project routing or promoting them into active blockers

---

## 1. Current Reading

The external review is directionally accepted:

- the current system is **good enough for a small-user, operator-centric quant platform**
- it is **not** yet a production-grade, service-separated, high-SLA platform
- the biggest architectural gaps are **runtime engineering**, not strategy engineering

The most useful framing to preserve is:

- current system = **single-runtime, operator-centric, research-first platform**
- current strengths = strong strategy core, good research traceability, practical runtime/compute split
- current weaknesses = single-node runtime, file-heavy state, fuzzy service boundaries, weak reconciliation semantics

This document records what we should keep as a **future architecture backlog**, not as an immediate execution queue.

---

## 2. What We Accept

### A. Keep the platform identity explicit

Absorb:

- treat the platform as **single-runtime**
- treat it as **operator-centric**
- treat it as **research-first, product-second**
- optimize first for:
  - correctness
  - auditability
  - safe runtime behavior
  - recoverability

Why this is worth keeping:

- it matches current reality
- it reduces accidental over-promising
- it gives a cleaner basis for future architectural decisions

Status:

- accepted as a planning principle
- no immediate implementation needed

### B. Preserve the three-layer target architecture

Absorb the target layering as a gradual direction:

1. **Layer 1 — Strategy Core**
   - signals
   - selector
   - params
   - portfolio-state model
   - risk overlays
   - shared backtest logic

2. **Layer 2 — Execution / Integration**
   - broker adapters
   - quotes / chains / balances / positions
   - live valuation
   - reconciliation
   - market-session semantics
   - alerting adapters

3. **Layer 3 — Runtime Surfaces**
   - Flask dashboard
   - Telegram bot
   - public ingress
   - scheduled jobs
   - research-view exposure

Why this is worth keeping:

- it is compatible with the current repo shape
- it does not require a rewrite
- it gives us a stable way to judge future refactors

Status:

- accepted as a long-term direction
- not an active refactor program

---

## 3. Medium-Priority Backlog

These are the highest-value architecture improvements we should revisit later, once current research and runtime priorities are calmer.

### M1. Formal live position valuation model

Goal:

- promote current broker/live valuation patches into a first-class module

Desired outputs:

- normalized live position snapshot
- source / confidence / stale reason
- mismatch reason against recorded trade state

Why it matters:

- recent live risk-panel issues exposed this gap clearly
- this is the most concrete runtime-architecture weakness today

Suggested shape:

- input:
  - recorded trade state
  - broker positions
  - quotes / chains
- output:
  - normalized valuation object
  - reconciliation flags

Priority:

- medium

Not now because:

- current priority remains Q041 research flow and runtime observation tracks

### M2. Explicit reconciliation semantics for live state

Goal:

- move from “file state exists” to “file state plus reconciliation meaning”

Key questions to formalize:

- what is the recorded canonical state
- what is the broker-observed state
- which side wins in each conflict class
- when do we fail closed
- how does UI show confidence / mismatch

Why it matters:

- current file-based state is workable but too implicit
- it increases runtime ambiguity during incidents

Priority:

- medium

### M3. Incident-grade runtime observability

Goal:

- systematize runtime health and failure snapshots

Desired coverage:

- local service health
- tunnel health
- recommendation health
- broker-auth health
- stale-data health
- last-failure snapshot artifacts

Why it matters:

- for a small-user platform, observability is higher ROI than heavyweight orchestration

Priority:

- medium

### M4. Tighten research/runtime boundary

Goal:

- reduce shared blast radius between heavy research artifacts and live runtime surfaces

Direction:

- heavy compute stays on main machine
- old Air only serves runtime-required artifacts
- web may display research outputs, but should not compute them on old Air

Why it matters:

- current split is directionally right but still soft at the repo/runtime boundary

Priority:

- medium

### M5. Broker integration as a more explicit subdomain

Goal:

- stop treating broker JSON payloads as ad hoc data blobs

Desired sub-areas:

- quotes
- chains
- positions
- balances
- auth status

Potential normalized models:

- spread quote snapshot
- condor quote snapshot
- live position reconciliation snapshot

Why it matters:

- this reduces the cost of future live bug fixes
- this is a precondition for more reliable runtime valuation and reconciliation

Priority:

- medium

---

## 4. Low-Priority Backlog

These are useful, but should stay clearly behind the medium-priority items above.

### L1. Partial database adoption

Direction:

- use lightweight storage such as SQLite for a subset of operational state

Best first candidates:

- open-position state
- trade-log events
- recommendation events
- incident snapshots

Why it is useful:

- stronger atomicity and queryability than scattered files

Why it is not urgent:

- current file model still works for the current scale
- reconciliation semantics matter more than storage choice right now

Priority:

- low

### L2. Read vs write API boundary for web

Direction:

- separate read models from mutating actions more explicitly

Useful split:

- read-only API
- mutating API
- audit-event log

Why it is useful:

- helps prevent dashboard from becoming a monolithic control surface

Why it is not urgent:

- current scale is still small
- this matters more after runtime / reconciliation hardening

Priority:

- low

### L3. Host-access / addressing cleanup

Direction:

- normalize runtime access assumptions around Tailscale first
- treat LAN IP as optional optimization, not canonical path

Why it matters:

- reduces ops noise

Why it is low priority:

- useful but narrow
- not a core architecture risk by itself

Priority:

- low

---

## 5. What We Explicitly Do Not Promote Now

The review contained ideas that are directionally correct but should **not** become current work items.

Do not promote now:

- host-level HA / multi-node runtime redesign
- generalized multi-user / multi-tenant platformization
- large service-splitting or microservice-style refactor
- broad database migration
- runtime container/orchestration push

Reason:

- these do not match current scale
- they would compete with higher-value near-term work
- they risk over-optimizing architecture ahead of product need

---

## 6. Relationship To Current Priorities

These backlog items are intentionally **below** the current active lines:

- `Q041` overlap validation / Phase 2
- `Q036` shadow observation
- `Q038` shadow monitoring
- `/ES` runtime safeguards follow-up

This document should therefore be read as:

- “worth remembering”
- “worth revisiting”
- “not currently blocking delivery”

---

## 7. Suggested Future Review Order

If we revisit this backlog later, the recommended order is:

1. `M1` live position valuation model
2. `M2` reconciliation semantics
3. `M3` runtime observability
4. `M4` research/runtime boundary tightening
5. `M5` broker integration subdomain cleanup
6. `L1` partial SQLite adoption
7. `L2` read/write API boundary
8. `L3` host-access cleanup

---

## 8. Verdict

Planner takeaway:

- the architecture review is **worth absorbing**
- it does **not** imply a near-term re-architecture
- the most valuable retained insight is:
  - future improvement should focus on **runtime engineering, reconciliation, and observability**
  - not on broad strategy-core rewrites or premature platformization

