# PROJECT_STATUS

Last Updated: 2026-04-12
Owner: Planner or PM

## Current Phase

- `stable` + `research-driven`
- Core trading system is stable; current work is mainly research, validation, and selective Spec-driven implementation.

## Current System Snapshot

- Recommended production posture: preserve current strategy matrix and add only research-backed, low-regret changes.
- Latest full strategy status doc: `doc/strategy_status_2026-04-10.md`
- Latest system status doc: `doc/system_status_2026-04-07.md`

## Active APPROVED Specs

- None at the moment

## Top Blockers

- `B1` — `/ES` minimal production cell (`SPEC-061`) is now done, but its production safety boundary is still below PM requirements: pure manual stop monitoring is not acceptable; the minimum acceptable next step is system monitoring plus bot alerting for the stop condition — owner: PM/Planner — next action: open a narrow follow-up Spec for runtime safeguards
- `B2` — dependency-bound legacy items (`Q001`, `Q002`, `Q003`) are still unresolved and can compete for attention if not kept explicitly ordered — owner: PM/Planner — next action: preserve `/ES` as the current front-of-queue decision item unless a dependency clears

## Open Questions Summary

- `Q002` — Shock active mode still needs Phase B validation — `open`
- `Q012` — `/ES` short put path is now the preferred production candidate; remaining question is shared-BP management with SPX Credit and how far to extend the MVP beyond Layer 2 — `open`
- `Q013` — `/ES` short put runtime stop execution and post-entry management remain undefined in production — `open`
- `Q011` — regime decay DIAGONAL sample is still small — `monitoring`
- `Q003` — L3 Hedge v2 live implementation — `open`
- `Q004` — `vix_accel_1d` L4 fast-path — `open`
- `Q005` — multi-position trim refinement — `open`

## Next Priorities

- `P1` — open a narrow follow-up Spec for `/ES` runtime safeguards, with minimum scope of stop-condition monitoring plus bot alerting
- `P2` — keep index-layer summaries aligned as new HC/MC status clarifications arrive
- `P3` — continue validating dependency-bound items before promoting more sizing logic into new Specs

## Recent Meaningful Changes

- 2026-04-12 — `SPEC-044` has reached `DONE`; there are currently no remaining active approved Specs waiting for Developer implementation — `See: task/SPEC-044.md`
- 2026-04-11 — ES short put phased research was indexed as a research-track idea; current recommendation is `hold` until scope is narrowed and proxy assumptions are revisited — `See: research/strategies/ES_puts/spec.md`
- 2026-04-12 — ES short put production-path research was materially updated: `/ES` permissions and live BP were confirmed (`$20,529` per contract), XSP is no longer the preferred path, and the main remaining design question is shared-BP management versus SPX Credit rather than lot-size feasibility — `See: sync/open_questions.md`, `RESEARCH_LOG.md`
- 2026-04-12 — `/ES` minimal production cell (`SPEC-061`) reached `DONE`; latest QR review confirms the MVP entry path works, but also surfaces that runtime stop execution remains manual and Layer 1 / Layer 3 are still intentionally out of scope. PM has clarified that pure manual stop monitoring is not acceptable; minimum follow-up scope is system monitoring plus bot alerting — `See: task/SPEC-061.md`, `sync/open_questions.md`
- 2026-04-12 — HC-side planning status was clarified: Schwab Developer Portal access is no longer a top HC blocker; index-layer summaries were reconciled and the current front-of-queue decision is now the `/ES` minimal production cell — `See: sync/open_questions.md`, `RESEARCH_LOG.md`
- 2026-04-10 to 2026-04-11 — `SPEC-048` to `SPEC-055` verified as `DONE`; latest IVP / DIAGONAL research batch is implemented and no longer belongs in active approved work — `See: doc/strategy_status_2026-04-10.md`
- 2026-03-28 to 2026-03-29 — several stop-loss and entry-filter studies were either implemented or rejected based on full-history backtests — `See: doc/research_notes.md`

## Notes

- This file is the rolling index layer.
- Detailed evidence, tables, and long-form reasoning remain in `doc/` and sync artifacts.
