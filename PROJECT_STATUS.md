# PROJECT_STATUS

Last Updated: 2026-04-24
Owner: Planner or PM

## Current Phase

- `stable` + `research-driven`
- Core trading system is stable; current work is mainly research, validation, and selective Spec-driven implementation.

## Current System Snapshot

- Recommended production posture: preserve current strategy matrix and add only research-backed, low-regret changes.
- Latest full strategy status doc: `doc/strategy_status_2026-04-20.md`
- Latest system status doc: `doc/system_status_2026-04-20.md`
- Live runtime host has moved to `old Air`; canonical running services now live there, not on the main machine
- Canonical runtime services on old Air:
  - `com.spxstrat.bot`
  - `com.spxstrat.web`
  - `com.spxstrat.cloudflared`
- Default compute host for heavy jobs remains the main machine; old Air is runtime-first, not compute-first
- New operational role exists: Codex `Server Maintainer` on old Air, responsible for runtime health, logs, and low-risk service recovery
- Fast runtime reference: `SERVER_RUNTIME.md`
- Reference: `doc/old_air_server_maintainer.md`

## Active APPROVED Specs

- None at the moment

## Top Blockers

- `B1` — `/ES` minimal production cell (`SPEC-061`) is now done, but its production safety boundary is still below PM requirements: pure manual stop monitoring is not acceptable; the minimum acceptable next step is system monitoring plus bot alerting for the stop condition — owner: PM/Planner — next action: open a narrow follow-up Spec for runtime safeguards
- `B2` — HC has now accepted `MC_Handoff_2026-04-24_v3` as the authoritative MC sync package, but HC has not yet reproduced the new aftermath stack and related tooling findings in its own environment. Until `SPEC-068 / SPEC-069 / SPEC-070 v2 / SPEC-071 / SPEC-072 / SPEC-073` are checked or replayed on HC, PARAM/master-doc drift risk remains high — owner: PM/Planner — next action: treat HC reproduction as the immediate sync-track priority rather than assuming MC-side DONE equals HC-side canonical
- `B3` — dependency-bound legacy items (`Q001`, `Q002`, `Q003`) are still unresolved and can compete for attention if not kept explicitly ordered — owner: PM/Planner — next action: preserve `/ES` as the current front-of-queue decision item unless a dependency clears

## Open Questions Summary

- `Q002` — Shock active mode still needs Phase B validation — `open`
- `Q012` — `/ES` short put path is now the preferred production candidate; remaining question is shared-BP management with SPX Credit and how far to extend the MVP beyond Layer 2 — `open`
- `Q013` — `/ES` short put runtime stop execution and post-entry management remain undefined in production — `open`
- `Q029` — MC found one material research/live parity issue: backtest engine hardcodes `qty = 1` and ignores selector `SizeTier`; HC now needs to reproduce the audit and decide whether to adopt the `research_1spx + live_scaled_est` reporting convention before any engine rewrite — `open`
- `Q020` — `Q018 / SPEC-066` may have optimized the wrong aftermath semantic: the second `IC_HV` should likely target a distinct second VIX peak, not a back-to-back re-entry immediately after the first peak — `research`
- `Q019` — MC Phase 1 now reports non-trivial close/open VIX drift (`aftermath 4.63%`, `regime 9.71%`, `trend 31.54%` flips), but PM has not yet chosen between the proposed follow-up paths `A / B / C`; HC should not silently reinterpret existing specs until that decision is made — `research`
- `Q032` — after MC selected aftermath broken-wing `V3-A` (`LC 0.04 / LP 0.08`), `V3-C` (`LC 0.03`) stays as a monitor-only revisit candidate after `5–10` live aftermath trades — `monitoring`
- `Q011` — regime decay DIAGONAL sample is still small — `monitoring`
- `Q003` — L3 Hedge v2 live implementation — `open`
- `Q004` — `vix_accel_1d` L4 fast-path — `open`
- `Q005` — multi-position trim refinement — `open`

## Next Priorities

- `P1` — reproduce the accepted MC 2026-04-24 stack on HC in a narrow, ordered way: `SPEC-068` (per-strategy spell throttle), `SPEC-069` (open-at-end artifact/UI field), `SPEC-070 v2` (delta-based long-leg alignment), `SPEC-071` (aftermath broken-wing IC), `SPEC-072` (frontend deploy), and `SPEC-073` (dead-code cleanup)
- `P2` — ask PM to choose whether `Q019` stays deferred or advances via one of MC’s proposed paths `A / B / C`; until then, keep the new close/open VIX evidence indexed but non-binding
- `P3` — open a narrow follow-up Spec for `/ES` runtime safeguards, with minimum scope of stop-condition monitoring plus bot alerting
- `P4` — after the HC reproduction pass, revisit `Q020`: whether `SPEC-066` alpha is materially driven by semantically wrong back-to-back `IC_HV` entries rather than true second-peak aftermath capture
- `P5` — continue validating dependency-bound items before promoting broader sizing logic or additional HIGH_VOL changes into new Specs

## Recent Meaningful Changes

- 2026-04-24 — `MC_Handoff_2026-04-24_v3.md` has now been accepted as the authoritative MC sync package. It materially extends the aftermath stack beyond HC’s current indexed state: MC reports `SPEC-068 DONE` (per-strategy spell throttle), `SPEC-069 DONE` (`open_at_end` artifact/UI support), `SPEC-070 v2 DONE` (delta-based long-leg alignment), `SPEC-071 DONE` (aftermath broken-wing IC, `LC 0.04 / LP 0.08`, `DTE 45` unchanged), `SPEC-072 MC-side DONE` (frontend dual-scale display, still pending HC deploy), and `SPEC-073 DONE` (dead-code cleanup). These should be treated as HC reproduction targets, not yet HC-canonical facts — `See: sync/mc_to_hc/MC_Handoff_2026-04-24_v3.md`
- 2026-04-24 — MC also surfaced two planning-relevant research governance findings that HC had not yet indexed. First, `Q029` found one material parity issue: the engine hardcodes `qty = 1` and therefore overstates live aftermath notional relative to `SizeTier`; MC’s chosen interim resolution is reporting-layer dual columns (`research_1spx` + `live_scaled_est`), not immediate engine rewrite. Second, `Q019 Phase 1` measured a non-trivial close/open VIX mismatch (`aftermath 4.63%`, `regime 9.71%`, `trend 31.54%` flips), but PM has not yet chosen whether to close, reproduce, or codify that evidence — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-20 — PM surfaced a new follow-up concern on the `Q018 / SPEC-066` line: the intended behavior in a double-spike pattern is not “allow two back-to-back `IC_HV` entries,” but “allow a second `IC_HV` only after a distinct second VIX peak begins to mean-revert.” This raises the possibility that part of the `cap=2 + B` alpha was earned under the wrong semantic, so a new research item `Q020` has been opened to measure how much of the result depends on back-to-back re-entry versus genuine second-peak capture — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-20 — `SPEC-066` review is now closed with **PASS with spec adjustment**, and the spec has been moved to `DONE`. No code changes were needed after Developer handoff: Quant concluded `AC4` was over-constrained at the trade-set level and correctly rewrote it as a logic-level invariant, and `AC10`’s original `[33,40]` artifact-count expectation was simply miscalculated and has been corrected to `[45,55]`. Core implementation stands: `IC_HV_MAX_CONCURRENT = 2`, `AFTERMATH_OFF_PEAK_PCT = 0.10`, the `2026-03-09 / 2026-03-10` double-spike pair is captured, and `2008-09` remains filtered — `See: task/SPEC-066.md`
- 2026-04-20 — Developer implemented `SPEC-066`, regenerated local artifacts, and wrote handoff. Core intent is working: `IC_HV_MAX_CONCURRENT = 2`, `AFTERMATH_OFF_PEAK_PCT = 0.10`, the `2026-03-09 / 2026-03-10` double-spike pair is captured, `2008-09` remains filtered, and system-level PnL / Sharpe / MaxDD all land near target. However, two acceptance criteria remain open: `AC4` (non-`IC_HV` trade-set drift) and `AC10` (research-view count now `49`, above the old expected range). This means `SPEC-066` is implemented but not yet closed — `See: task/SPEC-066_handoff.md`
- 2026-04-20 — `SPEC-066` has been moved to `APPROVED`. The selected `Q018` landing shape is now fixed as `cap=2 + B` (`IC_HV` max concurrent = 2 plus `AFTERMATH_OFF_PEAK_PCT 0.10`), and the next step is standard Developer implementation rather than further Planner-side branch selection — `See: task/SPEC-066.md`, `RESEARCH_LOG.md`
- 2026-04-20 — Quant completed `Q018 Phase 2` and PM selected the final research outcome: `cap=2 + B` (`IC_HV` max concurrent = 2 plus `AFTERMATH_OFF_PEAK_PCT 0.10`). The combined shape materially outperformed either component alone, with expected system improvement around `+$47K`, Sharpe about `+0.02`, and max drawdown nearly flat. This is now strong enough to justify a narrow DRAFT candidate, though it still sits behind `/ES` runtime safeguards in queue priority — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — Quant completed `Q018 Phase 1`: the single-slot aftermath question now has two credible but unresolved directions. Variant A (aftermath multi-slot replay) produced about `+$47,735` across `36` replayed trades with concentrated tail risk in `2008-09`, while Variant B (`AFTERMATH_OFF_PEAK_PCT 0.05 -> 0.10`) improved max drawdown by about `36%` at very low implementation cost. This is still research, not Spec, because the key realism gaps (BP ceiling, shock / overlay interaction, and significance hardening) remain open — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — PM opened a new research track `Q019` around time-basis mismatch: backtests use end-of-day VIX, while live recommendation uses opening / early-session VIX context. This may affect HIGH_VOL / NORMAL routing, `VIX_RISING`, `ivp63`-style gates, and aftermath detection, so it should be studied before any production reinterpretation of recent live behavior — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — `SPEC-064` (`HIGH_VOL Aftermath IC_HV Bypass`) shipped to production and passed review, and `SPEC-065` (`Research View Pill for SPEC-064`) also shipped and passed review. PM review of the real 2026-03 double-VIX-spike case surfaced a new research track `Q018`: the single-slot engine constraint appears to have blocked the second peak’s aftermath opportunity, but that is still a research question rather than a new Spec candidate — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — Quant completed `Q017 Phase 2` and closed the ex-ante recognition question: the live-usable signal is simply the aftermath condition itself, while `peak_drop_pct` and `vix_3d_roc` add no value. Evidence is now strong enough to support a narrow DRAFT candidate focused only on `HIGH_VOL aftermath IC_HV bypass`, with `EXTREME_VOL` preserved as the hard protection layer — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — Quant completed `Q017 Phase 1` and materially upgraded the evidence level: replacing SPX proxies with real strategy PnL produced significantly positive aftermath-window results, and removing the recent `2020-03 / 2025-04 / 2026-04` V-shaped events barely changed the conclusion. The alpha appears concentrated in `IC_HV`, and `Q017` now deserves Phase 2 ex-ante recognition work rather than continued `hold` status — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — Planner formalized `Q017` sequencing: Tier 1 is mandatory first (`real strategy PnL` + `remove 2020/2025/2026 V-shaped events`), Tier 2 only runs if Tier 1 still shows positive evidence, and Tier 3 gate-specific work is explicitly last — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — Quant opened a new research track `Q017` around early post-peak VIX-reversal windows: the phenomenon is structurally real and concentrated in HIGH_VOL filters, but current evidence still relies on SPX forward-return proxies and is dominated by a few modern V-shaped reversals, so the result is `hold`, not Spec — `See: RESEARCH_LOG.md`, `sync/open_questions.md`
- 2026-04-19 — Quant shipped the backtest research view (`SPEC-062`) and SPX-chart linkage (`SPEC-063`): historical Q015 marginal trades and Q016 Dead Zone A trades are now persistently viewable on the backtest page. The rollout also exposed and fixed a generator semantic trap where “baseline == current production” collapses marginal-trade diffs once a Fast Path change is already live — `See: RESEARCH_LOG.md`
- 2026-04-19 — Runtime/compute split was clarified as a project rule: old Air remains the canonical live runtime host, but heavy backtests, research view generation, and similar long-running artifact generation should default back to the main machine, with generated artifacts published to old Air only when needed by live web — `See: SERVER_RUNTIME.md`
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
