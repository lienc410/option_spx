# MULTI_AGENT_PROTOCOL_UPDATE_PROPOSAL.md

## Purpose

This document proposes an update to the SPX Strategy multi-agent protocol.

The goal is not to add more agents or make the workflow heavier. The goal is to improve:

- token efficiency
- context discipline
- research quality control
- execution batching
- runtime safety
- model routing

The current architecture should remain **L3-lite**, but with a stronger Planner role:

> Planner = routing controller + context compressor + token governor + protocol maintainer.

---

## 1. Executive Summary

Current architecture is directionally correct.

Keep the existing agent structure:

- PM
- Planner
- Quant Researcher
- Developer
- Server Maintainer

Do **not** add a sixth default agent.

The main protocol gap is that the current system has clear roles but insufficient budget discipline.

Recommended upgrade:

```text
L3-lite + Planner Governor + Research Tiering + Batch Codex Execution + Model Routing
```

Key decisions:

1. Planner remains the default entry point.
2. Planner gains explicit authority as token / context / routing governor.
3. Quant research is divided into Tier 1 / Tier 2 / Tier 3.
4. Opus is reserved for Tier 3 and critical final review, not daily Quant work.
5. Developer should use the strongest Codex coding model for approved implementation.
6. Server Maintainer should remain lower-cost and low-risk.
7. Codex execution should be batched to reduce daily usage burn.
8. old Air remains canonical runtime but should not be used as research/debug sandbox.

---

## 2. Recommended Agent Model Allocation

### 2.1 Model Allocation Table

| Agent / Mode | Recommended Model | Default Usage | Escalation Rule |
|---|---|---|---|
| Planner / Token Governor | Codex-GPT-5.4 | task intake, routing, context compression, prompt packaging, index maintenance | escalate only for ambiguous strategic routing |
| Developer | Codex-GPT-5.5 | approved implementation, tests, debugging, batch code changes | default coding model |
| Server Maintainer | Codex-GPT-5.4 | old Air health check, logs, restart, deployment verification | escalate to Developer only if code change is required |
| Quant Researcher Tier 1 | CC Sonnet 4.6 | quick scan, initial risk read, worth-continuing decision | no Opus |
| Quant Researcher Tier 2 | CC Sonnet 4.6 | focused hypothesis analysis, test design, parameter reasoning | no Opus unless conclusion is unstable |
| Quant Researcher Tier 3 | CC Opus 4.7 | full deep dive, high-risk strategy decision, paper-trading readiness, final go/no-go | requires PM or Planner explicit approval |
| 2nd Quant Reviewer / PM Audit | GPT-5.5 Thinking | independent challenge, workflow review, decision audit | use as external reviewer |

---

### 2.2 Model Routing Principles

Do not allocate the strongest model by role prestige. Allocate by:

1. error cost
2. reasoning depth
3. reversibility
4. implementation risk
5. expected token burn

Recommended defaults:

```text
Planner: Codex-GPT-5.4
Developer: Codex-GPT-5.5
Server Maintainer: Codex-GPT-5.4
Quant default: CC Sonnet 4.6
Quant escalation: CC Opus 4.7
2nd Reviewer: GPT-5.5 Thinking
```

---

### 2.3 Opus Usage Rule

CC Opus 4.7 has 2x usage cost versus Sonnet.

Therefore:

```text
Opus is high-value ammunition, not the default Quant engine.
```

Use Opus 4.7 only when at least one of the following is true:

1. The conclusion may affect live recommendation or paper-trading route.
2. The conclusion may affect position sizing, risk limit, or strategy eligibility.
3. The strategy has material path dependency, tail risk, or volatility-regime interaction.
4. Sonnet output is unstable, internally inconsistent, or overly superficial.
5. The task is a final go / no-go review.
6. The task requires portfolio-level priority or capital-allocation judgment.
7. The task combines multiple research streams into one routing decision.

Do **not** use Opus for:

- PROJECT_STATUS.md cleanup
- RESEARCH_LOG.md maintenance
- open_questions.md updates
- simple Spec drafting
- prompt packaging
- routine bug triage
- log reading
- old Air service restart
- single-strategy quick scan

---

## 3. Planner Role Upgrade

### 3.1 Current Planner Role

Current Planner role:

- default entry point
- routes work
- compresses context
- maintains status files
- prepares next-agent prompt

This is good but incomplete.

### 3.2 New Planner Role

Planner should be upgraded to:

```text
Planner = Token Governor + Context Compressor + Routing Controller + Protocol Maintainer
```

Planner must decide before routing:

1. What type of task this is.
2. Which path applies.
3. Which research tier applies.
4. Which model should be used.
5. Which files are required.
6. Which files should not be read.
7. Whether the task is worth doing now.
8. Whether the task should be batched.
9. Whether the task should stop before implementation.
10. What the next agent should output.

---

## 4. Task Intake Header

Planner should start non-trivial tasks with a structured intake.

Add this section to `PLANNER.md` or shared rules.

```markdown
## Task Intake Header

For every non-trivial task, Planner must classify the work before routing.

### Required Fields

Task Type:
- research only
- planning / status update
- draft Spec
- implementation
- runtime maintenance
- review

Recommended Route:
- Path A: Spec → Developer → Quant Review
- Path B: Fast Path
- Path C: Research / Planning
- Runtime Maintenance

Research Tier:
- Tier 1 Quick Scan
- Tier 2 Focused Analysis
- Tier 3 Full Deep Dive
- N/A

Primary Agent:
- Planner
- Quant Researcher
- Developer
- Server Maintainer
- 2nd Reviewer

Recommended Model:
- Codex-GPT-5.4
- Codex-GPT-5.5
- CC Sonnet 4.6
- CC Opus 4.7
- GPT-5.5 Thinking

Context Needed:
- files to read
- files not to read
- prior conclusions to reuse

Token Budget:
- low
- medium
- high

Expected Output:
- deliverable format

Stop / Escalation Condition:
- when to ask PM
- when to stop
- when to create DRAFT Spec
- when to request APPROVED Spec
- when to escalate model
```

---

## 5. Research Tiering

Add the following to `QUANT_RESEARCHER.md` and the shared rules.

```markdown
## Research Tiering

Quant Researcher must use a tiered research mode.

The default research level is Tier 1 unless Planner or PM explicitly requests a deeper tier.

### Tier 1 — Quick Scan

Purpose:
- decide whether a direction is worth deeper work
- identify obvious flaws
- identify obvious edge
- identify implementation burden
- identify risk flags

Model:
- CC Sonnet 4.6

Restrictions:
- do not perform full literature review
- do not write full research memo
- do not draft implementation Spec
- do not modify production code
- do not expand into adjacent strategy trees

Output:
1. One-line verdict
2. Core intuition
3. Main risk
4. Worth continuing? Yes / No / Maybe
5. Recommended next tier

### Tier 2 — Focused Analysis

Purpose:
- analyze one clear hypothesis
- design a testable research plan
- define parameter ranges
- define failure modes
- assess implementation readiness

Model:
- CC Sonnet 4.6

Restrictions:
- do not expand into unrelated research branches
- do not assume implementation approval
- do not modify production code
- do not convert to Spec unless requested

Output:
1. Hypothesis
2. Mechanism
3. Required data
4. Test design
5. Parameter candidates
6. Failure modes
7. Recommendation
8. Whether this is ready for DRAFT Spec

### Tier 3 — Full Deep Dive

Purpose:
- major strategy direction
- high-capital-risk decision
- production routing impact
- paper-trading readiness
- final go / no-go review
- portfolio interaction or overlap decision

Model:
- CC Opus 4.7 preferred

Trigger:
- PM or Planner must explicitly approve Tier 3
- Quant Researcher may recommend Tier 3 but should not self-escalate by default

Output:
1. Full research memo
2. External research absorption if applicable
3. Mechanism and edge thesis
4. Data and test design
5. Parameter design
6. Risk framework
7. Failure modes
8. Implementation readiness
9. Final routing recommendation
```

---

## 6. Quant Context Fidelity Rule

Replace the current loose “fidelity first” language with a more precise rule.

```markdown
## Quant Context Fidelity Rule

Quant channel uses fidelity-first context management, but fidelity does not mean full forwarding.

Planner must preserve:
- PM's original research intent
- risk preference
- decision boundary
- abnormal examples
- counterexamples
- known failure paths
- relevant prior conclusions

Planner may remove:
- repeated status descriptions
- unrelated historical context
- implementation trivia not relevant to the research question
- long logs already summarized in index files
- duplicated background already captured in PROJECT_STATUS.md or RESEARCH_LOG.md

Goal:
- preserve research direction
- avoid context-induced research drift
- avoid unnecessary Claude token burn
```

---

## 7. Developer and Codex Batch Execution Rule

Add this to `DEVELOPER.md`.

```markdown
## Batch Execution Rule

Developer should avoid micro-task execution.

Before calling Codex for implementation, Planner or PM should batch related work into one implementation packet whenever possible.

A Codex batch must include:

1. Approved Spec reference
2. Target files
3. Exact required changes
4. Files not to touch
5. Tests to run
6. Expected output format
7. Rollback or verification notes, if relevant

Developer must not:
- implement without APPROVED Spec, except Fast Path
- expand strategy scope
- perform speculative refactor
- convert implementation discussion into research
- make production-impacting logic changes without explicit approval

Developer may:
- implement approved changes
- add or update tests
- run local verification
- report blockers
- suggest follow-up Spec if scope expands
```

---

## 8. Fast Path Tightening

Current Fast Path rule:

```text
single file, ≤15 lines, selector routing branch or parameter constant, low risk
```

This is useful but should be tightened.

Add:

```markdown
## Fast Path Risk Limits

Fast Path is allowed only when all conditions are true:

- single file
- ≤15 changed lines
- low-risk change
- easily reversible
- no strategy thesis change
- no production recommendation logic change

Fast Path is not allowed for changes that affect:

- position sizing
- risk limits
- signal eligibility
- recommendation routing
- entry / exit criteria
- capital allocation
- alert behavior
- live trading or paper-trading route

Risk is determined by semantic impact, not line count.
```

---

## 9. Server Maintainer Mode

Developer and Server Maintainer may use the same Codex environment, but they should be separate modes.

Add to `doc/old_air_server_maintainer.md`.

```markdown
## Server Maintainer Mode

Server Maintainer is responsible for old Air production runtime health.

Default model:
- Codex-GPT-5.4

Allowed tasks:
- inspect service health
- inspect runtime logs
- verify Telegram bot status
- verify Flask dashboard status
- verify Cloudflare Tunnel status
- restart known services
- check disk / memory / process state
- confirm deployment state

Not allowed by default:
- quant research
- strategy design
- speculative coding
- direct production strategy logic changes
- secret modification
- unapproved config changes
- broad refactor

Escalation:
- If a code change is required, stop and route to Developer.
- If a strategy logic change is required, stop and route to Planner / PM.
- If production behavior differs from local behavior, document the difference before changing anything.
```

---

## 10. Runtime Validation Rule

old Air is canonical production runtime. But it should not become the default research or debug sandbox.

Add to `SERVER_RUNTIME.md`.

```markdown
## Runtime Validation Rule

old Air is the production runtime source of truth.

Canonical live components:
- Telegram bot
- Flask web dashboard
- Cloudflare Tunnel
- runtime logs

Default workflow:
1. Research and strategy design happen outside old Air.
2. Implementation and local tests happen on the main machine.
3. Only after local validation should changes be deployed or verified on old Air.
4. old Air is used for production health, integration behavior, live logs, Telegram validation, dashboard validation, and Cloudflare validation.

Do not use old Air for:
- exploratory coding
- large research runs
- broad debugging experiments
- unapproved strategy logic trials
- long-running backtests unless explicitly approved

If local behavior and old Air behavior differ:
- old Air is authoritative for live behavior.
- local environment is authoritative for development tests.
- document the mismatch before changing production runtime.
```

---

## 11. Index Update Rule

Add to shared rules or `PLANNER.md`.

```markdown
## Index Update Rule

Planner owns the index layer.

After Tier 2 or Tier 3 research, Planner must update the index layer if the result changes project understanding.

Index layer files:
- PROJECT_STATUS.md
- RESEARCH_LOG.md
- sync/open_questions.md

Update conditions:

Update RESEARCH_LOG.md when:
- a research conclusion is reached
- a hypothesis is rejected
- a test plan is proposed
- a risk or failure mode is identified
- confidence level changes

Update sync/open_questions.md when:
- a blocker remains unresolved
- a hypothesis needs validation
- a data issue remains open
- a PM decision is required

Update PROJECT_STATUS.md when:
- module status changes
- priority changes
- implementation readiness changes
- production / runtime status changes
- current bottleneck changes

Quant Researcher should produce research content.
Planner should maintain global project state.
Developer should update project docs only when required by APPROVED Spec.
```

---

## 12. Spec Entry Discipline

Current rule is good:

```text
Developer starts only after Status: APPROVED.
```

Preserve this.

Add clarification:

```markdown
## Spec Entry Discipline

A DRAFT Spec is not permission to implement.

Only PM can change Spec status to:
- APPROVED
- REJECTED

Developer may implement only when:
- the task has a SPEC file
- the SPEC file status is APPROVED
- the requested change is inside Spec scope

If Developer discovers missing requirements:
- stop
- report blocker
- ask Planner or PM to update Spec
- do not self-expand scope
```

---

## 13. Recommended File-Level Changes

Planner should modify the project protocol files as follows.

### 13.1 Shared Agent Rules

Add sections:

1. Planner as Token Governor
2. Task Intake Header
3. Research Tiering summary
4. Quant Context Fidelity Rule
5. Fast Path Risk Limits
6. Index Update Rule
7. Model Routing Summary

### 13.2 `PLANNER.md`

Add:

1. Planner as Token Governor
2. Task Intake Header
3. Context Compression rules
4. Model routing responsibility
5. Index Update Rule
6. Next-agent prompt format

### 13.3 `QUANT_RESEARCHER.md`

Add:

1. Research Tiering
2. Sonnet vs Opus routing
3. Tier 1 / Tier 2 / Tier 3 output formats
4. No self-escalation to Tier 3 unless approved
5. No implementation without approved Spec

### 13.4 `DEVELOPER.md`

Add:

1. Codex-GPT-5.5 as default Developer model
2. Batch Execution Rule
3. Approved Spec boundary
4. No strategy design
5. No speculative refactor
6. Fast Path constraints

### 13.5 `doc/old_air_server_maintainer.md`

Add:

1. Server Maintainer Mode
2. Codex-GPT-5.4 default model
3. allowed / not allowed tasks
4. escalation rules
5. no strategy logic changes

### 13.6 `SERVER_RUNTIME.md`

Add:

1. Runtime Validation Rule
2. old Air production-only boundary
3. local validation before production verification
4. mismatch handling

---

## 14. Suggested Planner Prompt to Apply These Changes

Planner can use the following instruction.

```text
You are the Planner / Token Governor for the SPX Strategy project.

Please update the project protocol files using MULTI_AGENT_PROTOCOL_UPDATE_PROPOSAL.md.

Goals:
1. Keep the existing L3-lite architecture.
2. Do not add new default agents.
3. Upgrade Planner into token governor / context compressor / routing controller.
4. Add Research Tiering to Quant Researcher.
5. Add Codex batch execution discipline to Developer.
6. Tighten Fast Path risk boundaries.
7. Separate Developer mode from Server Maintainer mode.
8. Add runtime validation boundaries for old Air.
9. Add model allocation guidance:
   - Planner: Codex-GPT-5.4
   - Developer: Codex-GPT-5.5
   - Server Maintainer: Codex-GPT-5.4
   - Quant Tier 1 / 2: CC Sonnet 4.6
   - Quant Tier 3 / final review: CC Opus 4.7
   - 2nd reviewer / PM audit: GPT-5.5 Thinking
10. Preserve PM as the only final decision maker.
11. Preserve APPROVED Spec as the only Developer implementation entry point, except explicitly defined Fast Path.

Please modify the relevant files:
- shared agent rules file
- PLANNER.md
- QUANT_RESEARCHER.md
- DEVELOPER.md
- doc/old_air_server_maintainer.md
- SERVER_RUNTIME.md

Do not change unrelated strategy logic.
Do not rewrite unrelated sections unless required for consistency.
At the end, report:
1. files changed
2. sections added
3. any conflicts or ambiguities
4. any recommended PM decisions
```

---

## 15. Final Recommended Operating Model

Final recommended structure:

```text
Architecture:
- Keep L3-lite

Default entry:
- Planner

Planner:
- Codex-GPT-5.4
- token governor
- context compressor
- routing controller
- index maintainer

Quant:
- CC Sonnet 4.6 default
- CC Opus 4.7 for Tier 3 / final review only

Developer:
- Codex-GPT-5.5
- approved implementation
- batch execution
- tests and local verification

Server Maintainer:
- Codex-GPT-5.4
- old Air production health
- no strategy logic changes

2nd Reviewer:
- GPT-5.5 Thinking
- independent challenge and decision audit

Runtime:
- old Air is production source of truth
- main machine is development / research / testing source
- old Air is not exploratory sandbox

Spec discipline:
- DRAFT is not implementation permission
- APPROVED is required for Developer
- PM is final decision maker
```

---

## 16. One-Line Conclusion

The current multi-agent system should remain L3-lite, but Planner must become the explicit token governor and context compressor; Quant should be tiered with Sonnet as daily driver and Opus reserved for high-value escalation; Developer should move to Codex-GPT-5.5 with batch execution discipline; Server Maintainer should remain low-risk and separate from coding mode.
