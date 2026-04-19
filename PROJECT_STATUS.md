# PROJECT_STATUS

Last Updated: 2026-04-19
Owner: Planner or PM

## Current Phase

- `stable` + `research-driven`
- Core trading system is stable; current work is mainly research, validation, and selective Spec-driven implementation.

## Current System Snapshot

- Recommended production posture: preserve current strategy matrix and add only research-backed, low-regret changes.
- Latest full strategy status doc: `doc/strategy_status_2026-04-16.md`
- Latest system status doc: `doc/system_status_2026-04-07.md`
- Live runtime host has moved to `old Air`; canonical running services now live there, not on the main machine
- Canonical runtime services on old Air:
  - `com.spxstrat.bot`
  - `com.spxstrat.web`
  - `com.spxstrat.cloudflared`
- New operational role exists: Codex `Server Maintainer` on old Air, responsible for runtime health, logs, and low-risk service recovery
- Fast runtime reference: `SERVER_RUNTIME.md`
- Reference: `doc/old_air_server_maintainer.md`

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
- `P2` — keep the next strategy-change queue narrow after `Q015` Fast Path landed; the remaining front-of-queue research work is `/ES` runtime safeguards plus dependency-bound legacy items, not another broad IVP redesign
- `P3` — continue validating dependency-bound items before promoting more sizing logic into new Specs

## Recent Meaningful Changes

- 2026-04-19 — Quant completed a Fast Path implementation for `Q015`: `BPS_NNB_IVP_UPPER` in `strategy/selector.py` was raised from `50` to `55` with a code comment pointing back to the OOS evidence. This closes the narrow BPS gate-relaxation candidate and leaves broader IVP / IC redesign questions for future research — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — Quant completed the OOS validation for the narrow BPS gate relaxation from `IVP < 50` to `IVP < 55`: full-history, IS, and OOS slices all showed non-degrading system Sharpe and positive PnL deltas, so `Q015` is no longer just exploratory research and now qualifies as a near-spec / Fast Path candidate — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-18 — Quant completed the Dead Zone B follow-up study inside VIX recovery windows: recovery itself is not a useful conditioning variable, VIX-only / joint filters are not ready, and the only near-spec candidate is a narrow BPS gate relaxation from `IVP < 50` to `IVP < 55` pending out-of-sample confirmation — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-18 — Quant completed the follow-up test on Dead Zone A inside VIX recovery windows and found no significant conditional alpha: `NORMAL + HIGH + BULLISH` recovery-window BPS remains non-significant, so `SPEC-060 Change 3` should stay `REDUCE_WAIT`; the “dead zone” investigation now collapses back into `Q015` / Dead Zone B only — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-18 — Quant confirmed a systemic “VIX recovery window dead zone”: across 66 HIGH_VOL→NORMAL transitions with elevated IVP, 64% of candidate days were blocked by two independent mechanisms (`NORMAL + HIGH + BULLISH` route hole plus IVP gates). Conclusion is `hold`, not Spec: the next required proof is whether Dead Zone A has real conditional alpha without reducing Sharpe — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-17 — `SPEC-060` (`Recommendation Event Log`) completed review and is now `DONE`; structured live recommendation logging is available for bot-triggered recommendation events, and there are still no active approved specs waiting for Developer implementation — `See: task/SPEC-060.md`
- 2026-04-18 — Live runtime was migrated from the main machine to old Air. `bot`, `web`, and `cloudflared` are now `launchd`-managed on old Air, and a dedicated Codex `Server Maintainer` role was defined for runtime operations. All agents should treat old Air as the canonical live host — `See: doc/old_air_server_maintainer.md`
- 2026-04-16 — Quant completed the first full BPS gate study (`Q015`): unlike DIAGONAL Gate 1, the `NORMAL + BULLISH` `IVP >= 50` gate shows a real Sharpe cliff and should be retained for now; the open research question has shifted from “remove or keep” to “how to redesign the filter’s concept basis beyond IVP alone” — `See: RESEARCH_LOG.md`, `sync/open_questions.md`, `doc/strategy_status_2026-04-16.md`
- 2026-04-15 — Quant completed a Fast Path removal of DIAGONAL Gate 1 in `strategy/selector.py`; the former `SPEC-049` `ivp252` marginal-zone gate is no longer active production logic, and the next threshold study has shifted to the `NORMAL + BULLISH` `IVP >= 50` entry gate — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-15 — Quant research on DIAGONAL Gate 1 (`SPEC-049`) concluded the gate is net harmful rather than protective; PM agreed to move toward a narrow follow-up Spec to remove it — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
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
