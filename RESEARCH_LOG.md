# RESEARCH_LOG

Last Updated: 2026-05-02 (R-20260502-08)
Owner: Planner or PM

---

## Entries

### R-20260502-08 — Post-sync Quant prioritization: investigate SPEC-077 AC3 magnitude gap before widening Q039; keep Q039 narrow as an IC-regular attribution pack

- Topic: HC post-reproduction triage between `SPEC-077 AC3` magnitude-gap attribution and `Q039` residual tieout attribution
- Findings: Quant’s new synthesis is that the two remaining HC-side follow-ups are not equally urgent. `Q039` still looks like a real residual tieout problem, but its current shape is much narrower than a full parity investigation: the clearest fingerprint is still `IC regular` entry-count drift (`HC 13` vs `MC 6`), which points first to entry-gate / persistence attribution rather than broad parameter sweeping. Quant’s recommended first move is **not** an `IVP` sweep, but a compact `IC regular trade-level divergence pack` covering the HC-only trades and labeling their selector inputs, `IVP252/IVP63`, trend / persistence state, open-position state, and likely MC reject / alternate reasons. In contrast, the `SPEC-077 AC3` magnitude gap now deserves **higher priority** because it affects how HC should interpret every cross-engine annualized-ROE comparison. Quant’s current ordering of likely causes is: `(1)` compounding / annualized-ROE metric semantics, `(2)` true strategy-path differences (including permanent `SPEC-056c` vs `SPEC-054` divergence), and only then `(3)` the previously suspected debit-side hardcode issue, which is now largely neutralized by `SPEC-080`
- Risks / Counterarguments: this does not demote `Q039` to noise. The residual gap remains real and could still later justify a stronger parity investigation if the narrow divergence pack shows the drift comes from non-PM-approved implementation differences rather than accepted permanent divergence or research variance. But Quant’s current view is that widening into threshold sweeps too early would be low-efficiency. The more immediate risk is misreading HC vs MC ROE uplift numbers as if they were already on the same accounting basis, when the present evidence suggests they may still be a mixed metric/path artifact
- Confidence: medium-high. Quant is not claiming the final root cause is settled, but the prioritization logic is strong: `SPEC-077 AC3` now gates cross-engine result interpretation, while `Q039` can remain a deliberately narrow research track
- Next Tests: `(1)` run the minimum `SPEC-077 AC3` attribution pass on the same `2007-01-01` full-sample ledgers, with metric-only recomputation plus path split by strategy / exit reason; `(2)` keep `Q039` at research scope and produce only an `IC regular trade-level divergence pack`; `(3)` do **not** launch an `IVP` threshold sweep unless that pack shows the drift clusters around `IVP` boundary conditions
- Recommendation: prioritize `SPEC-077 AC3` attribution first; keep `Q039` open but narrowed to `IC regular` divergence analysis rather than escalating it into a broader HC↔MC parity investigation
- Related Question: `Q037`, `Q039`
- See: `sync/open_questions.md`, `PROJECT_STATUS.md`, `sync/hc_to_mc/HC_return_2026-05-02.md`

### R-20260502-07 — Tieout #3 PASS: batch 2 (SPEC-079/080) introduces no regression; SPEC-079 blocks 2026-04-30 BCD in D_pt050; main HC↔MC gap unchanged

- Topic: HC reproduction sprint tieout #3 (post-batch-2 regression + SPEC-079/080 preview + gap convergence measurement), window `2023-04-29 → 2026-05-02`
- Findings: **Q-A regression**: scenario A (both toggles `disabled`, PT=0.60) yields 57 trades / $79,933.69 total_pnl — byte-identical to tieout #2 Q-C baseline. **REGRESSION_PASS = True**: SPEC-079/080 in `disabled` mode introduce zero trade flow changes. **B/C/D preview (PT=0.60)**: all three toggle-active scenarios (B = comfort_active, C = stop_active, D = both_active) are identical to A — neither SPEC-079 nor SPEC-080 triggered once in the 3y PT=0.60 window. This is expected: the `2023-04-29 → 2026-05-02` window is a "low-stress" environment; the comfort filter's VIX≤15 + dist_30d_high≤-1% + ma_gap>1.5pp triple condition never fired simultaneously at BCD entry dates in this period; the stop tightening's pnl_ratio [-0.50, -0.35) zone was likewise never hit — all positions either hit their profit target or stopped at ≥50% loss. **D_pt050 gap measurement (PT=0.50, both active)**: 57 trades / $76,450 vs tieout #2's 58 trades / $75,570 → Δ = -1 trade / +$880. The missing trade is 2026-04-30 BCD entry: that day had VIX=14.x (≤15 ✓), dist_30d_high ≤ -1% (✓), and ma_gap > 1.5pp (✓), giving risk_score=3 → SPEC-079 comfort filter blocked it under `active` mode. The 2026-04-30 entry did not appear as a PT=0.60 trade because it was `open_at_end` there — PT=0.60 trade count is unaffected. Gap vs MC@PT=0.50: trade delta improved +6 → +5; PnL delta expanded +$29,648 → +$30,528 (the blocked trade was a profitable one). Main gap contributors remain unchanged: IC regular HC 13 vs MC 6 and BPS/BCD strategy-mix structural differences — these are outside SPEC-079/080 scope
- Risks / Counterarguments: the tieout #3 window being "trigger-free" for SPEC-079/080 in the PT=0.60 scenario is a real limitation — the 3y lookback is a relatively calm period. True pressure testing requires `start=2007-01-01` full-sample with both toggles active; the 2008/2020/2022 high-stress years are expected to show materially more comfort filter triggers and pnl_ratio zone hits. PM should not treat the B/C/D=A result as evidence that the filters never fire
- Confidence: high on regression PASS (byte-identical); high on the 2026-04-30 SPEC-079 block attribution (risk_score=3 conditions confirmed); medium on gap convergence prognosis (main gap is structurally explained by IC regular gate differences, not SPEC-079/080 scope)
- Next Tests: (1) optional full-sample `start=2007-01-01` both-active run to observe 2008/2020/2022 trigger behavior; (2) Q037/Q038 open_questions.md index entries (unblocked per assessment §4); (3) HC return package to MC (batch 1+2 + tieout #2/#3 complete); (4) PM shadow flip decision for `bcd_comfort_filter_mode` / `bcd_stop_tightening_mode` (MC target 4-8 week observation before shadow mode)
- Recommendation: declare batch 2 reproduction complete; main HC↔MC gap is structurally explained and out of SPEC-079/080 scope; proceed to HC return package and Q037/Q038 open_questions indexing
- Related Question: HC reproduction sprint (batch 2 closure + tieout #3)
- See: `doc/tieout_3_2026-05-02/README.md`, `doc/tieout_3_2026-05-02/tieout3_summary.json`, `task/SPEC-079.md`, `task/SPEC-080.md`

### R-20260502-06 — Tieout #2 PASS: batch 1 introduces no trade flow regression; HC↔MC gap unchanged as predicted; Q-C baseline established at PT=0.60

- Topic: HC reproduction sprint tieout #2 (post-batch-1 self-consistency + new PT=0.60 baseline), window `2023-04-29 → 2026-05-02`
- Findings: Q-A self-consistency check (HC@PT=0.50 today vs tieout #1 CSV `data/backtest_trades_3y_2026-04-29.csv`): scripted verdict was `SELF_CONSISTENT = False` (98.28% match, threshold 99%), but this is a **date-boundary false alarm** — the one new entry (`2026-04-30`) was impossible in tieout #1 which was generated on 2026-04-29; all 57 original entry dates are 100% preserved; PnL delta +\,618 equals exactly that one new trade. **Adjusted Q-A verdict: PASS — batch 1 (SPEC-074 / SPEC-077 / SPEC-078) introduced zero unintended trade flow changes.** Q-B HC↔MC gap is essentially unchanged (HC 58 / ,570 vs MC 52 / ,922; Δ +6 trades / +\9,648 vs tieout #1 Δ +5 / +\8,030; entire delta explained by the 2026-04-30 date expansion). Per-strategy gap structure is structurally identical to tieout #1: IC regular HC 13 vs MC 6 remains the largest single contributor (IVP gate / persistence filter difference); BCD HC 20 vs MC 15 (debit-side stop not yet wired via SPEC-080); BPS HC 15 vs MC 21 (SPEC-079 comfort filter not yet wired). Q-C new PT=0.60 baseline: 57 trades (2 open_at_end), total_pnl +\9,934 (BCD 20/+\8,571, IC 13/+\9,329, BPS 15/+,538, IC_HV 8/+\,767, BPS_HV 1/+\,728)
- Risks / Counterarguments: the gap non-convergence is structurally clean — it was predicted before running and is entirely explained by batch 1 not touching selector / IVP gate / persistence. The IC regular HC 13 vs MC 6 gap is the reproduction community's known open item (Q039 candidate: IVP gate sensitivity). Two Q-C open_at_end trades inflate the realized PnL understated figure; full Q-C PnL will land once those exit
- Confidence: high on Q-A PASS (date-boundary explanation is definitive); high on Q-B unchanged gap (all three batch-1 specs are confirmed not to touch trade-path code); medium on per-strategy gap attribution (IC vs BPS vs BCD splits are directionally right but exact root cause needs batch-2 instrumentation)
- Next Tests: **Tieout #3** — after SPEC-079 (BCD comfort filter) and SPEC-080 (BCD debit stop tightening + stop_mult wiring) land, rerun `2023-04-29 → current` to measure how much of the HC↔MC gap closes. Acceptance gate for tieout #3 convergence: trade delta ≤ +2 (versus current +6), PnL delta <  k (versus current +\9.6k). Also: per assessment §4, Q037 / Q038 open_questions.md index entries are now unblocked (tieout #2 complete); Q020 deferred until tieout #3 (HC↔MC gap still material)
- Recommendation: declare batch 1 reproduction complete (self-consistency PASS); do not block batch 2 on gap convergence; open Q037 / Q038 index entries in sync/open_questions.md as next Planner action
- Related Question: HC reproduction sprint (batch 1 closure + tieout #2)
- See: `doc/tieout_2_2026-05-02/README.md`, `doc/tieout_2_2026-05-02/tieout2_summary.json`, `data/backtest_trades_3y_2026-04-29.csv`, `task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md` §3 / §4 / §5.1

### R-20260502-05 — SPEC-078 closed DONE: server `annualized_roe` is now authoritative on the backtest dashboard; AC1-AC7 all PASS

- Topic: SPEC-078 closure (backtest dashboard metrics single-source-of-truth)
- Findings: All seven acceptance criteria now PASS. Codex executed the scriptable portion ([task/SPEC-078_handoff.md](task/SPEC-078_handoff.md)) — AC1 confirmed `metrics.annualized_roe` / `metrics.annualized_roe_basis = "final_equity_compound"` / `metrics.period_years` present and well-typed across two windows (`start=2023-01-01` and `start=2007-01-01`); AC4 byte-identical reverify against the JS formula `((100000 + total_pnl)/100000) ** (1/years) - 1) * 100` came in at `|Δ| = 3.1e-07` (3.3y window) and `1.2e-07` (19.3y window), both well inside the `1e-6` tolerance. Cross-check: the 19.32y window's `annualized_roe = 8.0358%` matches the SPEC-077 AC3 PT=0.60 rerun byte-for-byte, confirming the server-side metric is genuinely computed, not stubbed. PM completed the browser portion: AC2 normal path (dashboard reads `metrics.annualized_roe` directly, no fallback warning) and AC2 fallback path (DevTools Local Overrides → delete `metrics.annualized_roe` → Console emits `[SPEC-078] server metrics.annualized_roe missing — JS fallback` and the ROE card continues to display via `impliedAnnualizedRoe` JS fallback with values matching the server) both PASS. AC5 (RESEARCH_LOG / PROJECT_STATUS index) / AC6 (`@deprecated SPEC-078` JSDoc) / AC7 (`computeSubsetMetrics` untouched) PASS by inspection
- Risks / Counterarguments: the JS fallback path remains live by design — disk-cached payloads written before SPEC-078 (TTL-bounded) will trigger the `console.warn` until they expire. This is the spec's documented "fallback 期限" boundary condition and not a regression. P12 Fast Path (research view subset metrics realtime computation) remains deferred per spec; revisit after 4-8 weeks of SoT operation
- Confidence: high on the closure verdict — all numeric, structural, and behavioral checks PASS with cross-spec self-consistency
- Next Tests: none specific to SPEC-078. Server-side metrics SoT is now ready for tieout #2 to consume directly
- Recommendation: SPEC-078 DONE recorded; PM may now proceed with tieout #2 (`2023-04-29 → 2026-04-29` rerun) which is no longer blocked by either batch-1 spec
- Related Question: HC reproduction sprint (batch 1)
- See: `task/SPEC-078.md`, `task/SPEC-078_handoff.md`, `tests/test_metrics_annualized_roe.py`, `backtest/engine.py`, `web/templates/backtest.html`

### R-20260502-04 — PM closes SPEC-077 DONE under option (2): operational MC parity with documented AC3 full-sample shortfall; HC↔MC magnitude-gap investigation deferred to post-SPEC-080

- Topic: SPEC-077 closure decision following the AC3 full-sample failure recorded in R-20260502-03
- Findings: PM selected option (2) from R-20260502-03 — accept SPEC-077 operationally for MC parity (rule lift `profit_target=0.60` + credit-side `params.stop_mult` wiring lock) and explicitly acknowledge that AC3's `≥+0.5pp` full-sample threshold was not met (HC produced `+0.0856pp`, far below Q037 Phase 2A's published `+0.91~+1.03pp` band). SPEC-077 status moved APPROVED → DONE on 2026-05-02. AC1 / AC2 / AC4 / AC5 / AC6 PASS; AC3 is recorded as a documented failure in `task/SPEC-077.md` 변경 record rather than silently masked. The HC↔MC ~10× magnitude gap is **not** abandoned: Quant's recommendation is to revisit it after SPEC-080 wires debit-side `params.stop_mult` (currently hardcoded `-0.50` at [backtest/engine.py:882](backtest/engine.py#L882)), at which point the three candidate causes (compounding-baseline口径, debit-side stop hardcoding, SPEC-054 / SPEC-056c permanent divergence) can be disambiguated with cleaner attribution
- Risks / Counterarguments: closing SPEC-077 with a known full-sample shortfall is operationally fine because (a) the rule lift direction matches MC qualitatively and credit-side wiring lock is independently valuable, (b) tieout #2 is no longer blocked, and (c) the magnitude-gap investigation has lower marginal value before SPEC-080 lands. But it does mean PM should treat HC dashboard `annualized_roe` deltas as **not directly comparable** to MC's Q037 numbers until the gap is closed; any cross-engine ROE comparison must explicitly note the open gap
- Confidence: high on the closure decision being internally consistent with the evidence; medium on the gap actually resolving cleanly post-SPEC-080 (compounding-baseline口径 alone could explain most of the 10× factor, but only direct attribution will confirm)
- Next Tests: tieout #2 (`2023-04-29 → 2026-04-29` rerun) once SPEC-078 PM browser smoke clears; SPEC-080 implementation will inject the debit-side `params.stop_mult` wiring; after that, an HC↔MC `profit_target=0.50` vs `0.60` re-comparison can isolate which of (a)/(b)/(c) drives the magnitude gap. Indexed for follow-up under post-SPEC-080 work (provisionally Q040 if needed)
- Recommendation: SPEC-077 DONE recorded; do not block on the AC3 shortfall; flag the HC↔MC magnitude question for post-SPEC-080 attribution
- Related Question: HC reproduction sprint (batch 1)
- See: `task/SPEC-077.md`, `doc/baseline_2026-05-02/ac3_summary.json`, `RESEARCH_LOG.md` R-20260502-03

### R-20260502-03 — SPEC-077 AC3 full-sample HC rerun FAILS the `+0.5pp` threshold and the Q037 Phase 2A `+0.91~+1.03pp` band; ~10× magnitude gap suggests an HC↔MC engine-level divergence

- Topic: SPEC-077 AC3 full-sample HC rerun per PM directive 2026-05-02
- Findings: Reran HC backtest with `profit_target=0.50` and `0.60` from `2007-01-01` (~19.32y, full VIX3M coverage; runner at [doc/baseline_2026-05-02/run_ac3_fullsample.py](doc/baseline_2026-05-02/run_ac3_fullsample.py)). Δ ann_roe = `+0.0856pp` (309 → 302 trades, +$6,772 total PnL), Δ sharpe = `+0.00` (non-degrade ✓), Δ max_dd = `-$850` (slight worsening). Per-strategy: every credit strategy avg PnL improves modestly (+$12 BC_HV, +$50 IC_HV, +$134 IC, +$0 BPS), BCD avg +$26 with 2 fewer trades. Direction matches MC qualitatively (lift > 0, sharpe stable, max_dd marginal) but magnitude is ~10× short of Q037 Phase 2A's `+0.91~+1.03pp` reported band and well below SPEC-077 AC3's `+0.5pp` threshold. **AC3 FAIL** as written
- Risks / Counterarguments: three candidate sources of the HC↔MC magnitude gap. (a) HC's `annualized_roe` formula uses a **fixed** `$100k` baseline ([backtest/engine.py](backtest/engine.py) helper `_annualized_roe_pct` mirroring `web/templates/backtest.html:1965`); if MC compounds equity year-over-year, the same `+$6,772` over 19y reads as a much larger compound-rate delta. (b) debit-side stop is still hardcoded `-0.50` ([backtest/engine.py:882](backtest/engine.py#L882)) — Bull Call Diagonal positions never read `params.stop_mult`, so any MC-side asymmetry there changes the BCD ↔ profit_target interaction. SPEC-080 BCD scope explicitly punts this. (c) SPEC-054 / SPEC-056c divergence (HC removed both-high DIAG gate, MC retained) shifts the BCD ↔ IC fire mix; HC has fewer BCD-blocked days, so the profit_target sensitivity reads through differently. Cannot disambiguate without engine-level instrumentation
- Confidence: high on the failure verdict as written; medium on the root cause (likely (a) compounding-baseline mismatch is dominant, but HC has no MC source for direct verification)
- Next Tests: PM must choose path before SPEC-077 closes — (1) pause DONE and open a narrow HC↔MC magnitude-gap investigation (compounding口径 + per-trade size attribution); (2) accept SPEC-077 operationally for MC parity (rule lift + wiring) and explicitly acknowledge AC3 full-sample shortfall with documented gap; (3) revert default to `0.50`. Quant recommendation: (2) — the rule lift is qualitatively in the right direction, the wiring lock is independently valuable, and the HC magnitude-gap investigation is more efficiently scoped after SPEC-080 wires debit-side `params.stop_mult`
- Recommendation: do **not** silently close SPEC-077 DONE; surface AC3 failure to PM with the three options above
- Related Question: HC reproduction sprint (batch 1)
- See: `task/SPEC-077.md`, `doc/baseline_2026-05-02/ac3_summary.json`, `doc/baseline_2026-05-02/ac3_metrics_pt050.json`, `doc/baseline_2026-05-02/ac3_metrics_pt060.json`

### R-20260502-02 — SPEC-078 dashboard metrics SoT: server `annualized_roe` is now authoritative; JS path becomes deprecated fallback

- Topic: HC reproduction sprint batch 1 — `SPEC-078` (backtest dashboard metrics single-source-of-truth) implementation closure
- Findings: Server `compute_metrics` now emits three SPEC-078 fields — `annualized_roe` (float %), `annualized_roe_basis` (`"final_equity_compound"`), `period_years` (float) — at [backtest/engine.py](backtest/engine.py) (helper `_annualized_roe_pct` ports the JS formula line-for-line). Frontend [web/templates/backtest.html](web/templates/backtest.html#L2028) now reads `metrics.annualized_roe` directly when present and falls back to `impliedAnnualizedRoe(...)` with `console.warn` only when the server omits the field. The JS function carries an `@deprecated SPEC-078` JSDoc note. New unit test `tests/test_metrics_annualized_roe.py` (5 testcases, all PASS) locks server-vs-JS parity within 1e-6, the empty-trades branch, and the single-day no-divide-by-zero edge. `computeSubsetMetrics` (research subset path) is intentionally untouched per AC7. P12 Fast Path remains deferred per spec
- Risks / Counterarguments: the fallback path remains live for one rollout cycle so cached `result` payloads (from disk cache) without `annualized_roe` will still render; the `console.warn` lets PM see those drop off as cache TTLs expire. If the disk cache is large and PM wants to force a refresh, the cache directory can be cleared. The 1e-6 parity tolerance is byte-identical for the formula but ignores future change to `BACKTEST_BASELINE_EQUITY` (still 100k both sides; SPEC out-of-scope for configurable equity)
- Confidence: high on F1/F2/F3/F4 implementation; medium-high on PM dashboard rendering until manually browser-verified
- Next Tests: PM smoke on dashboard ann ROE field with API live + with API stubbed (force fallback)
- Recommendation: SPEC-078 ready to mark DONE pending PM browser smoke
- Related Question: HC reproduction sprint (batch 1)
- See: `task/SPEC-078.md`, `tests/test_metrics_annualized_roe.py`, `backtest/engine.py`, `web/templates/backtest.html`

### R-20260502-01 — SPEC-077 default lift: HC `profit_target` raised 0.50 → 0.60 to match MC; baseline rerun shows directional caveat on the 3.3y release window

- Topic: HC reproduction sprint batch 1 — closing the residual `profit_target` divergence between HC default `0.50` and MC `SPEC-077 DONE` production default `0.60`
- Findings: SPEC-077 is now landed at the code level. `StrategyParams.profit_target` default is `0.60` ([strategy/selector.py:68](strategy/selector.py#L68)); two `web/server.py` fallback overrides (lines 1272, 1309) were synced to `0.60`; `tests/test_engine_stop_wiring.py` locks credit-side `params.stop_mult` wiring (line 880) and documents that the debit-side hardcoded `-0.50` (line 882) remains until SPEC-080. Five testcases pass. New baseline `doc/baseline_2026-05-02/` shows: 58 closed + 2 open trades vs 59 closed in `doc/baseline_2026-04-24/`; win rate +1.3pp (74.6% → 75.9%); max DD improved by $958; but realized total PnL on the 3.3y window is -$13,276 and Sharpe -0.29. Two of the three "missing" `50pct_profit` exits are now `open_at_end` (unrealized winners excluded from `total_pnl`)
- Risks / Counterarguments: SPEC-077 AC3 specifies "ann ROE 改善 ≥ +0.5pp **全样本**, sharpe 不退化". The 2026-05-02 baseline is the 3.3y release-comparison window, not the full sample. The Q037 Phase 2A full-sample evidence (+0.91~+1.03pp ann ROE, sharpe / drawdown improvement) remains the primary AC3 verification; the 3.3y window is operational (lock MC parity in prod config) rather than statistical. PM call needed on whether AC3 should be re-verified by a full-sample HC rerun before SPEC-077 marks DONE
- Confidence: high on code-level F1/F2 implementation; medium-high on full-sample AC3 still holding because Q037 Phase 2A was already on a 20y horizon; medium on whether the 3.3y window divergence is purely "2 unrealized winners" vs a structural exposure-window effect
- Next Tests: optional Q037 Phase 2A rerun under HC engine if PM wants AC3 re-verified end-to-end, otherwise SPEC-077 closes once F4 docs (this entry + PROJECT_STATUS) and AC3 sign-off land
- Recommendation: surface the 3.3y window divergence to PM transparently; do NOT mark SPEC-077 DONE silently. If PM accepts Q037 Phase 2A as AC3 evidence, close to DONE; otherwise schedule a full-sample HC rerun
- Related Question: HC reproduction sprint (batch 1)
- See: `task/SPEC-077.md`, `doc/baseline_2026-05-02/README.md`, `doc/baseline_2026-04-24/`, `tests/test_engine_stop_wiring.py`, `task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md`

### R-20260502-00 — SPEC-074 closed: HC `select_strategy` snapshot path verified parity-equivalent to MC backtest_select; F5 SPEC-054 vs SPEC-056c divergence resolved as Option A (HC retains SPEC-056c removal)

- Topic: HC reproduction sprint batch 1 — SPEC-074 backtest_select parity vs MC `MC_Spec-074_short_summary_v3.md` 7-gate × 6-component cross-check
- Findings: SPEC-074 reached DONE on 2026-05-02. F2 cross-check confirmed all 7 MC gates (BACKWARDATION, VIX_RISING, IVP63≥70, IC IVP 20-50, DIAG IV-high SPEC-051, DIAG both-high SPEC-054, aftermath bypass) are present in HC `select_strategy` except DIAG both-high which HC removed via SPEC-056c. F5 PM裁定 = Option A: HC keeps SPEC-056c removal as the canonical posture; MC's retention is a documented HC/MC permanent divergence, not a reproduction defect. F4 parity test `tests/test_backtest_select_parity.py` was added (22 PARITY_DATES across 2008/2018/2020/2022, threshold ≥95%; result 22/22 = 100% PASS). Because HC `engine.py:835/1252` calls live `select_strategy` directly (no `_backtest_select` wrapper), the parity test reduced to a snapshot-construction regression guard (5 testcases: field population, no-exception threshold, canonical strategy field set, backwardation flag consistency, known 2020-03-16 backwardation case)
- Risks / Counterarguments: parity is asserted on snapshot construction + selector behaviour, not on bar-by-bar trade outcomes (those will be re-verified by tieout #2 once batch 1 fully closes). The HC ↔ MC SPEC-054 / SPEC-056c divergence is now a **permanent** documented divergence, not a known bug; if MC ever decides to retire SPEC-054, HC has nothing to do, but if MC keeps it, HC will continue to behave more permissively in the both-high state
- Confidence: high on the code-level parity verification; medium-high that the snapshot-only parity test catches the regressions it needs to catch (the threshold ≥95% gives margin for edge cases in the canonical_strategy field)
- Next Tests: tieout #2 once SPEC-077 closes; if tieout #2 residual is still material on the both-high days, revisit F5 with the empirical evidence
- Recommendation: SPEC-074 DONE (already recorded); proceed with SPEC-077 → SPEC-078 → batch 2
- Related Question: HC reproduction sprint (batch 1)
- See: `task/SPEC-074.md`, `tests/test_backtest_select_parity.py`, `sync/mc_to_hc/MC_Spec-074_short_summary_v3.md`, `task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md`

### R-20260426-14 — Quant delivers the PM-facing productization decision packet for `Q036` and recommends hold, not productization

- Topic: Final PM-facing decision packet after the governance / prerequisite planning stage of `Q036`
- Findings: Quant has now delivered the PM-facing decision packet for `Q036` in `task/q036_pm_decision_packet_2026-04-26.md`. The core recommendation is explicit and narrower than either `drop` or `escalate`: **hold as research candidate, do not productize now**. Quant’s reasoning is that the branch has crossed the threshold for serious governance review, but not the threshold for productization. `Overlay-F_sglt2` still shows real positive economics (`+9,005` total PnL, `+0.074pp` annualized ROE full sample, `+0.040pp` recent), and its governance cleanliness remains acceptable under the disclosed `PASS WITH CAVEAT` framing. However, the uplift is still modest relative to the cost of productization: gate-alignment rerun would still be mandatory before any spec path, the branch would create a new capital-allocation layer with real monitoring / governance burden, and the economic gain is not “knockout” enough to justify that cost now. At the same time, Quant explicitly rejects `drop`: yearly attribution is dispersed rather than single-year-driven, disaster-window net is intact, and the branch is still a legitimate future candidate if better triggering conditions arise
- Risks / Counterarguments: this recommendation intentionally keeps the branch in an unresolved but structured state. The main risk of `hold` is opportunity cost (`~$334 / year` full sample, `~$549 / year` recent), plus the possibility that without explicit indexing the branch would silently decay into a de facto `drop`. The main risk of disregarding the recommendation and escalating anyway is over-investing productization effort into a candidate that still has thin uplift and only partial tail improvement. Quant therefore argues the current evidence supports disciplined preservation, not immediate promotion
- Confidence: high on the packet recommendation as a faithful synthesis of the current evidence; medium on the eventual long-run answer because that depends on future sleeves, future data, or future regime shifts rather than on unresolved current-branch confusion
- Next Tests: no new variant research is recommended. The next meaningful action is PM’s final decision on whether to (a) hold `Q036` as a documented research candidate with explicit re-trigger conditions, or (b) override the Quant recommendation and move into productization-oriented follow-up despite the thin uplift
- Recommendation: PM should review the packet and decide; Quant recommends **hold as research candidate, do not productize now**
- Related Question: `Q036`
- See: `task/q036_pm_decision_packet_2026-04-26.md`, `PROJECT_STATUS.md`, `sync/open_questions.md`

### R-20260426-13 — PM chooses Option B on `Q036`: advance `Overlay-F_sglt2` into a more formal overlay-governance discussion, but not into DRAFT-spec territory

- Topic: PM decision on the completed `Q036` packet
- Findings: PM has now chosen **Option B** from the `Q036` decision packet. This is a meaningful governance advancement, but it is intentionally narrower than spec approval. The practical meaning is that `Overlay-F_sglt2` has cleared the bar for continued structured planning and governance review: the branch is no longer just an exploratory research thread or a packet waiting for judgment. At the same time, PM did **not** choose to jump to a DRAFT overlay spec, and did **not** authorize implementation. The packet’s disclosed methodology caveat remains in force: the current cleanliness claim is already reported on the stricter position-count metric, but any future productization path must align the actual gate to that same position-count semantics. So the project’s new posture is “formal overlay discussion approved,” not “overlay approved for build”
- Risks / Counterarguments: the core caution remains unchanged. `Overlay-F` is still a thin-uplift candidate (`+0.074pp` annualized ROE full sample, `+0.040pp` in `2018+`), not a strong alpha source. Tail improvement is partial rather than universal, and the methodology caveat is still real. That is why Option B should be read as a governance / planning authorization, not as evidence that implementation is now the default next move
- Confidence: high on the meaning of the PM decision; medium-high on downstream productization prospects because those still depend on a further governance layer rather than purely on research evidence
- Next Tests: no blind expansion of the research tree. The next artifact should define the exact governance / monitoring / productization-readiness questions for `Overlay-F_sglt2`, while preserving the rule that any eventual implementation path must first align gate semantics to position-count short-gamma measurement
- Recommendation: keep `Q036` open, but reclassify it from “decision packet ready” to “formal overlay discussion approved”; do not open a DRAFT overlay spec yet
- Related Question: `Q036`
- See: `doc/q036_pm_decision_packet_2026-04-26.md`, `sync/open_questions.md`, `PROJECT_STATUS.md`

### R-20260426-12 — Quant reconciles the 2nd/3rd external reviews: `Q036` is now PASS WITH CAVEAT and may proceed to PM decision packet

- Topic: Final packet-readiness ruling for `Q036` after conflicting external review outcomes
- Findings: Quant has now reconciled the two outside review opinions on `Q036`. 2nd Quant had issued a `CHALLENGE`, arguing that the branch should not advance because the `Overlay-F` gate uses family-deduplicated short-gamma counting while the framing / cleanliness metrics were stated in position-count terms. 3rd Quant instead issued `PASS — ready for PM decision packet`, arguing that the branch had already answered the real governance question even if it remained far from DRAFT-spec quality. Quant’s integrated ruling is **PASS WITH CAVEAT**. The key factual resolution is that the packet’s headline cleanliness claim (`SG>=2 = 0 / 23`) is already measured on the stricter engine-level position-count metric, not the more permissive family-deduplicated gate metric. That means the inconsistency is real, but it is a **presentation / governance caveat**, not a numerical invalidation of the current result. Quant therefore chose the minimum corrective action: add a post-review methodology note to the review packet, explicitly disclose the gate-vs-metric split, document that this sample’s cleanliness claim still holds under the stricter metric, and state that any future productization path must align the gate to position-count semantics
- Risks / Counterarguments: this does not erase the underlying methodological tension. If the branch were to move toward implementation, the gate cannot be left family-deduplicated while the control metric remains position-count based. So the caveat is not cosmetic; it is simply no longer large enough to block PM governance review. The economic and risk conclusions also remain modest rather than overwhelming: `Overlay-F` is still a small positive overlay, not a strong alpha source or a ready-made production candidate
- Confidence: high on packet readiness with caveat; medium-high on the eventual promote/stop decision because that still depends on PM’s governance tolerance for a thin uplift and a disclosed methodology note
- Next Tests: no further research-tree expansion is justified before PM review. The next step should be the PM decision packet. If PM later chooses to formalize the branch, the first technical hygiene task must be aligning the overlay gate to position-count short-gamma semantics and rerunning the narrow confirmation under the unified metric
- Recommendation: PASS WITH CAVEAT — ready for PM decision packet, not ready for DRAFT overlay spec discussion
- Related Question: `Q036`
- See: `task/q036_quant_review_packet_2026-04-26.md`, `sync/open_questions.md`, `PROJECT_STATUS.md`

### R-20260426-11 — 2nd Quant challenges Q036 packet readiness on a narrow but real methodological inconsistency: gate short-gamma count and reported cleanliness metric do not currently use the same semantics

- Topic: 2nd Quant review of `Q036` packet readiness after `Overlay-F_sglt2` final confirmation
- Findings: 2nd Quant’s overall review is materially supportive of the branch, but not yet a clean pass. Framing is accepted: `Q036` is correctly treated as a capital-allocation question with idle-capital baseline economics, not as a `Q021` rule-replacement branch. Lead-candidate selection also stands: `Overlay-F_sglt2` remains the best current frontier point, and the yearly attribution / disaster posture / recent-slice story are all considered directionally credible. The single blocker is methodological consistency. In the current research implementation, the `Overlay-F` gate counts pre-existing short-gamma exposure using a family-deduplicated method, while the framing and cleanliness claims (`SG>=2 = 0`, Phase 1 stacking language, Phase 5 fire-distribution reporting) are expressed in position-count terms. In the reviewed sample this mismatch does not appear to have changed the top-line economic result, but it creates a legitimate trust gap: an external reviewer can reasonably ask whether the gate is actually looser than the cleanliness claim implies. 2nd Quant’s recommended fix is narrow and low-cost: align the gate and metric semantics first, ideally by switching the gate to position-counting, then rerun the Phase 4 / Phase 5 `Overlay-F` confirmation and refresh the packet
- Risks / Counterarguments: this is not a branch-level invalidation. 2nd Quant explicitly did **not** challenge the candidate ranking, the disaster-window interpretation, or the yearly-attribution logic. The risk is narrower but still important: if the branch advances to PM with an avoidable semantic mismatch at the core of its cleanliness claim, confidence in the whole packet will drop disproportionately. A weaker alternative would be to keep the family-dedup gate but disclose the dual metric clearly and prove equivalence on this sample, but 2nd Quant recommends semantic unification rather than explanatory footnotes
- Confidence: high on the existence of the inconsistency; medium-high that the branch remains economically intact after the fix, though that still needs rerun confirmation
- Next Tests: do one targeted repair only. Align gate and metric short-gamma counting semantics, rerun the narrow `Overlay-F` confirmation pack, and check whether the key Phase 4 / Phase 5 outputs materially change: fire count, `SG` distribution, `+0.074pp` annualized ROE uplift, disaster-window net, and recent-slice behavior. If those remain stable, the branch can move back to `ready for PM decision packet`
- Recommendation: challenge packet readiness, not branch validity; fix the semantic mismatch first, then re-issue the PM packet
- Related Question: `Q036`
- See: `task/q036_2nd_quant_review_packet_2026-04-26.md`, `doc/q036_phase4_short_gamma_guard_2026-04-26.md`, `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`, `sync/open_questions.md`

### R-20260426-10 — Q036 final confirmation completes: `Overlay-F_sglt2` is robust enough for a PM decision packet, but still not naturally DRAFT-ready

- Topic: `Q036` final narrow confirmation on the single lead candidate `Overlay-F_sglt2`
- Findings: Quant completed the last PM-approved confirmation pass and the result is strong enough to end exploratory research, though not strong enough to auto-promote into spec discussion. `Overlay-F_sglt2` keeps the same definition: `2x` iff `idle BP >= 70%`, `VIX < 30`, and `pre-existing short-gamma count < 2`. Full-sample top line remains positive at `+$412,855` versus baseline `+$403,850`, for `+$9,005` incremental PnL and `+0.074pp` annualized ROE uplift. The yearly attribution result is the most important new evidence: the uplift is “sparse but distributed,” not a single-year artifact. `11/27` years are positive, `4/27` are negative, `12/27` are flat, and the largest annual contributor (`2022`, `+$1,896`) is only `17.6%` of the absolute yearly delta. Even removing the top one or two years leaves the branch positive (`+$7,111` after removing 2022; `+$5,285` after removing 2022 and 2008). Fire distribution is also fully coherent with the design: all `23` overlay fires occur in `HIGH_VOL`, mostly in `VIX 25-30` (`18/23`), with the rest in `20-25` (`5/23`), and none occur when pre-existing short-gamma count is `>= 2` (`0 / 23`). Mean idle BP at fire is about `80.5%`, which supports the intended account-level guardrail logic rather than exposing hidden stacking leakage. The `2018+` slice remains positive too: `+$4,395` incremental PnL and `+0.040pp` annualized ROE uplift, with tail behavior essentially stable in that slice and fire distribution still aligned with the guardrails
- Risks / Counterarguments: the branch still does not clear the bar for automatic DRAFT-spec escalation. The uplift remains small in absolute account terms, and recent-era benefit is thinner than the full-sample result. Full-sample `CVaR 5%` also remains slightly worse (`-4,382` vs baseline `-4,309`), so the result is not “free alpha.” The right interpretation is not that `Overlay-F` has won by knockout, but that it has survived every narrowing pass and now deserves a PM judgment packet rather than more open-ended prototype branching
- Confidence: medium-high
- Next Tests: stop expanding the research tree. The next artifact should be a PM decision packet that forces the practical governance question: is this a sufficiently clean and meaningful account-level overlay improvement to justify a more formal overlay discussion, or should the branch stop at research? Any further analysis should be support for that packet, not another family of variants
- Recommendation: ready for PM decision packet
- Related Question: `Q036`
- See: `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`, `backtest/prototype/q036_phase5_overlay_f_confirmation.py`, `sync/open_questions.md`, `PROJECT_STATUS.md`

### R-20260426-09 — PM approved a final narrow confirmation pass for `Overlay-F_sglt2`; the branch is now near a decision packet rather than open-ended exploration

- Topic: Governance decision after `Q036` lead-candidate emergence
- Findings: PM has now approved one final narrow confirmation round for `Q036`, focused only on `Overlay-F_sglt2`. This is a meaningful status change even though it is not yet a production decision. It means the branch has crossed from “broad overlay exploration” into “single-candidate confirmation.” The current interpretation is that `Overlay-F` already represents the best observed compromise on the branch: positive account-level ROE uplift, no realized `SG>=2` stacking, preserved disaster-window net, and moderated peak BP. The remaining work is no longer exploratory variant search; it is confirmation quality work intended to support a PM judgment packet
- Risks / Counterarguments: this approval should not be misread as a soft green light for a future spec. It is specifically a narrowing instruction. If the confirmation round weakens the case, PM may still choose to stop the branch with no overlay promotion at all. The main remaining risk is not technical novelty but insufficient conviction: uplift may still be too small, too regime-specific, or too concentrated to justify governance complexity
- Confidence: high on branch state; medium on eventual promote/drop outcome
- Next Tests: complete only the three already-authorized checks on `Overlay-F_sglt2`: yearly attribution, fire distribution by regime / VIX bucket / pre-existing short-gamma count, and recent-era robustness. After that, the expected next artifact should be a PM decision packet, not another widening prototype round
- Recommendation: continue research, but treat this as the final confirmation leg before PM judgment
- Related Question: `Q036`
- See: `PROJECT_STATUS.md`, `sync/open_questions.md`

### R-20260426-08 — Q036 Phase 4 finds the first credible lead candidate: `Overlay-F_sglt2` improves on the hybrid without bringing back visible stacking

- Topic: `Q036` Phase 4 guardrail refinement around account-level short-gamma risk
- Findings: Quant narrowed the branch exactly as planned and tested one more guardrail idea: relax the overly blunt “no `IC_HV` open at all” rule into a more account-level condition, `pre-existing short-gamma count < 2`. The resulting candidate, `Overlay-F_sglt2`, is the first genuinely interesting compromise in the whole overlay line. Its definition is: `2x` iff `idle BP >= 70%`, `VIX < 30`, and `pre-existing short-gamma count < 2`. Relative to baseline it reaches total PnL `+412,855` and annualized ROE uplift `+0.074pp`, which is clearly better than the prior hybrid `Overlay-D` (`+0.046pp`) and reasonably close to `Overlay-B` (`+0.088pp`). At the same time it keeps the most important governance constraints clean: realized `SG>=2` is still `0%`, disaster-window net remains `+301`, and peak system `BP%` is `34%`, below `Overlay-B`’s `38%`. This is the first point on the branch that looks like a real compromise rather than a tradeoff dominated by either weak uplift or weak guardrails
- Risks / Counterarguments: this still does **not** make the branch spec-ready. The uplift remains small in absolute account terms, and the result has only just crossed from “diffuse positive branch” into “one plausible lead candidate.” The remaining risk is concentration of benefit: the branch could still be overly dependent on a small number of years, a narrow regime slice, or a small subset of overlay fires. Quant therefore still recommends `continue research`, not DRAFT-spec escalation
- Confidence: medium-high on the ranking of `Overlay-F` versus prior overlay candidates; medium on whether the branch will eventually justify production promotion
- Next Tests: if PM wants one more round, do not widen the tree. Only confirm `Overlay-F_sglt2` on three dimensions: yearly attribution, overlay-fire distribution by regime / VIX bucket / pre-existing short-gamma count, and recent-era robustness (`2018+`). The question is no longer “which family is best,” but “is `Overlay-F` robust enough to survive a final confirmation pass?”
- Recommendation: continue research, but collapse the branch to a single lead candidate rather than expanding more variants
- Related Question: `Q036`
- See: `doc/q036_phase4_short_gamma_guard_2026-04-26.md`, `backtest/prototype/q036_phase4_short_gamma_guard.py`, `sync/open_questions.md`

### R-20260426-07 — Q036 Phase 2 finds positive idle-capital return, but not enough yet to justify a DRAFT overlay spec

- Topic: `Q036` Phase 2 narrow conditional overlay study
- Findings: Quant completed the PM-approved Phase 2 shortlist and the result is meaningful but not promotable. All three conditional overlay candidates produce positive account-level incremental return on otherwise idle capital. Relative to the baseline (`+403,850`, annualized ROE `8.67%`), `Overlay-A` reaches `+410,630` (`+0.054pp` annualized ROE), `Overlay-B` reaches `+414,556` (`+0.088pp`), and `Overlay-C` reaches `+413,214` (`+0.077pp`). Positive-year proportion does not improve (`25/27` throughout). Max drawdown does not worsen in the raw summary, but all three variants slightly degrade `CVaR 5%` (from `-4,309` to `-4,382`), so the branch still pays a real tail-cost. Disaster-window net is the cleanest for `Overlay-B` (`+302`, same as baseline), worse for `Overlay-C` (`-99`), and clearly worse for `Overlay-A` (`-561`). Peak system `BP%` rises from `30%` to `31% / 38% / 34%` for `A / B / C`. Idle-BP utilization remains extremely low (`0.39%` to `0.46%` of the idle budget), crowd-out is reported as clean, and realized short-gamma stacking strongly differentiates the candidates: `Overlay-C` eliminates it (`0%` in pre-existing `>= 2` short-gamma environments), while `A` and `B` still stack into such environments (`16%` and `20%`)
- Risks / Counterarguments: the branch should not be dropped, because the return on idle capital is genuinely positive and the opportunity-cost baseline is still roughly `$0 / BP-day`. But the branch also should not be promoted to DRAFT spec because the uplift is small in absolute account terms and every candidate still pays a price in either tail behavior, peak BP, or stacking risk. Quant’s conclusion is therefore appropriately in the middle: the branch remains economically interesting, but not yet decision-grade for production. Another caution is governance drift: a positive overlay result must still not be misread as a rule-layer argument against `V_A SPEC-066`
- Confidence: medium-high on the comparative ranking; medium on the decision because the economic edge is narrow
- Next Tests: if PM wants to continue, the scope should narrow rather than widen. `Overlay-A` can largely be retired. Any next phase should focus only on `Overlay-B` (best raw uplift, best disaster net, but highest peak BP) and `Overlay-C` (strongest stacking guardrail, slightly weaker uplift). The decision threshold for further work should now be whether one of those two can improve the incremental return / incremental tail-cost tradeoff enough to become spec-worthy
- Recommendation: continue research, but do **not** move to DRAFT overlay spec discussion yet
- Related Question: `Q036`
- See: `sync/open_questions.md`, `PROJECT_STATUS.md`

### R-20260426-06 — PM approved `Q036 Phase 2`: proceed with a narrow conditional overlay study, not a broad strategy rewrite

- Topic: Governance decision after `Q036 Phase 1`
- Findings: PM has now approved `Q036 Phase 2`. This does not change the branch’s meaning: `Q036` remains a capital-allocation study, not a reopened `Q021` rule fight, and still does not authorize any production change or Spec. What the approval does settle is the next research scope. The project should now test only the three minimum pilot variants already identified by Quant: `Overlay-A 1.5x conditional`, `Overlay-B 2x + disaster cap`, and `Overlay-C 2x + no-overlap`. All three must keep idle-BP threshold gating as a hard prerequisite. The reason for the narrow scope is now explicit: Phase 1 already proved deploy capacity is abundant, while the real new risk is short-gamma stacking, so the next iteration should be designed to answer account-level ROE and tail-cost questions rather than reopen wide semantic branches
- Risks / Counterarguments: PM approval here is permission to research, not evidence that overlay is economically justified. The same branch could still fail if ROE uplift is weak, if disaster-window damage widens too much, or if the overlay mostly creates more short-gamma crowding than useful account-level return. The governance risk remains the same as before: no one should reinterpret a positive Phase 2 result as proof that `SPEC-066` should be rewritten or that a production overlay is automatically warranted
- Confidence: high on scope clarity; economic verdict still pending
- Next Tests: Quant should now run the approved Phase 2 shortlist and report account-level `ROE`, annualized `ROE`, positive-year proportion, incremental `MaxDD`, incremental `CVaR 5%`, disaster-window net, peak system `BP%`, crowd-out checks, and realized short-gamma stacking. Only after that should PM decide whether to drop `Q036`, continue research, or authorize a DRAFT overlay spec
- Recommendation: continue research under the approved narrow Phase 2 scope; no Spec, no production change yet
- Related Question: `Q036`
- See: `doc/q036_framing_and_feasibility_2026-04-26.md`, `sync/open_questions.md`, `PROJECT_STATUS.md`

### R-20260426-05 — Q036 Phase 1 confirms idle BP capacity is abundant; the real constraint is short-gamma stacking, not deployability

- Topic: `Q036` Phase 1 feasibility measurement for idle-BP deployment / capital allocation
- Findings: Quant completed the first real `Q036` measurement pass and the core capacity question is now answered: under the `V_A SPEC-066` baseline, account BP usage is structurally low, with average BP used only `8.68%`, average idle BP `91.32%`, and maximum BP used just `30%` across the full sample. The deployability result is especially strong in the pilot context: aftermath days show essentially the same idle-BP profile as the rest of the sample, and `100%` of aftermath days still have at least `70%` idle BP available. Even disaster windows remain far from forced-liquidation conditions (`2008 GFC` mean idle `97.2%`, `2020 COVID` `92.3%`, `2025 Tariff` `86.5%`). This means capacity is not the bottleneck. The decisive new risk finding is elsewhere: on aftermath days the account is already carrying `>= 2` short-gamma positions on about `47%` of the full sample and `54%` of the recent slice, so an overlay would often stack rather than diversify risk
- Risks / Counterarguments: Phase 1 does **not** prove that overlay improves account-level ROE. It only proves that idle BP is persistently available and that baseline margin stress is low. The actual economic question remains open because account-level return uplift, incremental drawdown, `CVaR 5%`, disaster-window damage, and margin-stress / forced-liquidation proxies under overlay have not yet been computed. Another important caution is that the raw Phase 4 sizing numbers cannot simply be reused as the final answer: once idle-BP threshold gating is added, both PnL and tail shape will change. Quant also notes that even if overlay is economically positive, the ultimate uplift may still be small relative to governance and monitoring complexity
- Confidence: medium-high on deployability and framing; low-medium on final economics pending overlay prototype
- Next Tests: move to `Q036 Phase 2` only if PM approves. The recommended minimum pilot remains narrow and fully conditional: `Overlay-A 1.5x first-entry`, `Overlay-B 2x + disaster cap`, and `Overlay-C 2x + no-overlap`, all with idle-BP threshold gating as a hard precondition. Phase 2 must report account-level `ROE`, annualized `ROE`, positive-year rate, incremental `MaxDD`, incremental `CVaR 5%`, disaster-window net, peak system `BP%`, crowd-out checks, and realized short-gamma stacking
- Recommendation: keep `Q036` open and advance to Phase 2 **only pending PM approval**; do not open a Spec, do not alter production, and do not reopen `Q021`
- Related Question: `Q036`, `Q021`
- See: `doc/q036_framing_and_feasibility_2026-04-26.md`, `backtest/prototype/q036_phase1_idle_bp_baseline.py`, `sync/open_questions.md`

### R-20260426-04 — Q036 feasibility framing: idle BP overlay should be judged against the idle-capital baseline, not against `V_A`’s rule-layer efficiency

- Topic: First formal Quant framing pass for `Q036` idle-BP deployment / capital allocation
- Findings: Quant’s first-pass conclusion is that `Q036` is correctly framed as a **capital-allocation** problem with a different objective function from `Q021`. The right benchmark is not whether an overlay beats `V_A`’s `+$4.85 / BP-day` as a rule, but whether deploying otherwise idle BP improves **account-level ROE** under explicit guardrails. On that framing, the baseline comparator is effectively idle capital at about `$0 / BP-day`, not `V_A`. Quant also reports a strong early feasibility signal: under the current baseline, BP usage appears structurally low, around `12.5%` average and `14%` max, leaving idle BP at `>= 86%` for much of the sample. That means the question is economically worth testing. Phase 4’s rule-layer numbers also become reinterpretable under this new lens: every tested sizing-up branch still had positive marginal dollars, so none are automatically disqualified on idle-baseline economics alone. However, Quant explicitly does **not** treat that as approval. Tail cost and account-level feasibility are still unmeasured
- Risks / Counterarguments: the current argument is still only a framing and feasibility signal. It does not yet include the real account-level answers: incremental max drawdown, incremental `CVaR 5%`, disaster-window damage, margin-stress proxy, forced-liquidation proxy, or the true regime-conditional shape of idle BP. Another major caveat is that directly reusing Phase 4 results could mislead if conditional idle-BP gating materially changes which trades fire; such gating should both reduce PnL and reduce tail exposure. Quant also notes that the eventual ROE uplift may be economically small (for example, low tenths of annualized ROE points), which means governance and monitoring cost must be part of the decision
- Confidence: medium overall; high on the framing, low on the economic answer pending prototype
- Next Tests: `Q036 Phase 1` should first measure idle-BP baseline and regime-conditional distribution. Only then should a narrow Phase 2 candidate set be tested, with idle-BP threshold gating as a hard precondition. Quant’s recommended shortlist is limited to three overlay forms: `1.5x` first-entry overlay, `2x disaster-cap`, and `2x no-overlap`
- Recommendation: continue research; enter `Q036 Phase 1 feasibility prototype`; do not open a Spec, do not alter production, and do not reopen the `Q021` semantic dispute
- Related Question: `Q036`, `Q021`
- See: `task/IDLE_BP_OVERLAY_RESEARCH_NOTE.md`, `sync/open_questions.md`, `PROJECT_STATUS.md`

### R-20260426-03 — PM reset the top-level objective: the next sizing question is account-level ROE under guardrails, not another rule-replacement contest

- Topic: Objective reset from rule-local optimization to account-level capital allocation
- Findings: PM explicitly clarified that the project’s primary objective is now to **reasonably maximize account-level ROE**. “Reasonably” means the optimization target must remain constrained by explicit concern for drawdown, margin stress / forced-liquidation risk, hidden concentration, and the opportunity cost of deploying scarce BP. This reframes the aftermath sizing discussion. `Q021 Phase 4` still stands: `V_D` / `V_E` / `V_J` / `V_G` do **not** beat `V_A` as canonical rules, and `SPEC-066` remains the right rule-layer baseline. But that result does not end the higher-level question of whether persistently idle BP should sometimes be deployed through a controlled overlay to improve account-level ROE. The correct next question is therefore not “should `V_D` replace `V_A`?” but “should the system add a guarded idle-BP deployment overlay, modeled at the combination-level capital pool, with `IC_HV aftermath` as an initial pilot use case if needed?”
- Risks / Counterarguments: this is a broader scope than `Q021`, and it introduces a governance risk if the team blurs rule quality with capital deployment. If handled carelessly, a positive overlay result could be misread as proof that a lower-quality rule should replace the baseline. PM has explicitly rejected that conflation. Another risk is premature local optimization: today the opportunity-cost baseline is intentionally simple (`A`: idle BP is allowed to remain idle), but future multi-strategy capital allocation may change the correct answer once `/ES` or other deployable sleeves mature
- Confidence: high on the framing reset; low on the economic answer until account-level idle-BP evidence is produced
- Next Tests: open a distinct research branch for idle-BP deployment / capital allocation. First pass should stay at feasibility level and answer: whether idle BP is persistent enough to matter, whether a guarded overlay improves account-level ROE, what incremental tail cost it creates, and whether that beats the current opportunity-cost baseline of leaving BP unused. `Q021` should be retained as an evidence base and pilot input, not as the parent framing
- Recommendation: treat this as a new system-level research question, not as a reopened `SPEC-066` rule fight
- Related Question: `Q036`, `Q021`
- See: `task/IDLE_BP_OVERLAY_RESEARCH_NOTE.md`, `doc/q021_phase4_sizing_curve_2026-04-26.md`, `doc/q021_variant_matrix_2026-04-26.md`, `sync/open_questions.md`

### R-20260426-01 — Q021 Phase 4 closes the sizing-up branch: no smart edge exists anywhere on the aftermath first-entry sizing curve

- Topic: Final Phase 4 sizing-curve review for `Q021`
- Findings: Quant completed the 6-variant aftermath first-entry sizing-curve study (`V_A baseline / V_D 2x full / V_E 1.5x / V_J 2x no-overlap / V_H split-entry / V_G 2x disaster-cap`). The core result is decisive: every sizing-up variant underperformed the `SPEC-066` baseline on marginal `$ / BP-day`. Baseline `V_A` runs at `+$4.85 / BP-day`, while the best sizing-up path only reaches `V_G +$3.83`, with `V_D +$3.37`, `V_J +$2.98`, and `V_E +$2.70`. This means the apparent `V_D` uplift (`+6.9%` PnL) is leverage drag rather than a smarter rule. Additional decomposition sharpened the conclusion: `V_J` and `V_E` earn almost the same extra dollars, which isolates most of `V_D`’s extra `+$17K` as distinct-cluster overlapping leverage; `V_G` is the cleanest doubler but still fails to cross baseline efficiency; and `V_H` is effectively just `V_A - 1 trade`, so split-entry has no independent alpha
- Risks / Counterarguments: this is a strong close recommendation, not yet a PM-final close. The study rules out the tested sizing-up branch, but it does not prove no future conditioned 2x idea could ever work; it only shows there is no smart edge anywhere on the tested `[1x, 2x]` curve. Quant also explicitly treats `V_G` as a possible future research note rather than a current candidate, because even its cleaner disaster behavior still fails the marginal-efficiency bar
- Confidence: high
- Next Tests: Planner should now treat `Q021` as `ready to close pending PM final approval`. No new `SPEC-067` should be opened from this branch. If PM wants a future revisit, the only candidate worth remembering is `V_G`, and even that should remain a note rather than a promoted backlog item unless new evidence appears
- Recommendation: close `Q021` with `SPEC-066` unchanged, pending PM signoff
- Related Question: `Q021`
- See: `doc/q021_phase4_sizing_curve_2026-04-26.md`, `doc/q021_variant_matrix_2026-04-26.md`, `backtest/prototype/q021_phase4_sizing_curve.py`, `sync/open_questions.md`

### R-20260426-02 — PM established a permanent “full metrics pack” rule for all future strategy/spec comparisons

- Topic: New standing research-governance rule triggered by the Q021 Phase 4 debate
- Findings: PM accepted 2nd Quant’s critique that `PnL / Sharpe / MaxDD` alone are insufficient for variant promotion decisions and established a permanent rule: all future strategy / spec / variant / prototype / quant-review comparisons must include the full metrics pack, at minimum `PnL/BP-day`, `marginal $/BP-day`, `worst trade`, `disaster window`, `max BP%`, `concurrent 2x days`, and `CVaR 5%`. This is a cross-project research convention, not a one-off preference for `Q021`. The rule has been stored in persistent memory as `feedback_strategy_metrics_pack.md`
- Risks / Counterarguments: this increases review overhead slightly, especially for fast iterations, but the project has now seen enough cases where raw PnL or Sharpe could mask leverage drag or tail concentration. The governance cost is justified by the reduction in false promotions
- Confidence: high
- Next Tests: none as a research question; the next requirement is operational discipline. Future specs, research packets, and review handoffs should be checked against this rule by default
- Recommendation: treat as permanent project convention
- See: `doc/q021_phase4_sizing_curve_2026-04-26.md`, `~/.claude/projects/.../memory/feedback_strategy_metrics_pack.md`

### R-20260425-01 — `SPEC-072` closes the reporting-layer piece of Q029 without escalating to backend changes

- Topic: Final outcome of the HC-side `SPEC-072` reproduction task
- Findings: `SPEC-072` is now `DONE` on HC (`main` / `3fca17a`). The implementation stayed frontend-only and landed exactly where the HC mapping expected: shared helpers in `web/static/spec072_helpers.js`, dual BP badge + broken-wing BUY-leg emphasis in `web/templates/index.html`, aftermath view disclaimer + HIGH_VOL dual-stack trade-log rendering + `SPEC-071` addendum legend in `web/templates/backtest.html`, and HIGH_VOL BP dual-text in `web/templates/margin.html`. Quant’s code-level review passed all static acceptance criteria (`AC1–AC7`, `AC9`), while PM smoke was accepted through helper console checks plus browser-level visual probes rather than waiting for a naturally occurring live HIGH_VOL recommendation. This means the project has now shipped the reporting-layer mitigation implied by `Q029`: HC can display `research_1spx` alongside `live_scaled_est` without touching backend, engine, selector, or artifacts
- Risks / Counterarguments: this closes the SPEC, not the deeper parity question. The implementation still couples broken-wing visual emphasis and dual-scale display behind the same `isAftermathHighVol` gate, and the margin dual-text path still awaits a naturally surfacing HIGH_VOL live position to be observed in production. More importantly, `SPEC-072` does **not** solve the underlying engine-level notional mismatch; it only makes the difference explicit in the UI
- Confidence: high
- Next Tests: no immediate frontend follow-up is required. The next meaningful decision is strategic: whether `Q029` remains sufficiently handled by UI/reporting-layer dual columns, or whether PM wants to promote a deeper live-scale engine branch (`Q035`). Separate from that, the main aftermath research question is now back to `Q021`, not more frontend work
- Recommendation: done at the UI layer; hold deeper engine work until PM asks for it
- Related Spec: `SPEC-072`
- Related Question: `Q029`, `Q035`
- See: `task/SPEC-072.md`, `doc/quant_review_spec072_2026-04-25.md`, `task/SPEC-072_handoff.md`

### R-20260424-03 — MC aftermath stack converged on broken-wing `IC_HV`, but HC still needs its own reproduction pass

- Topic: Accepted MC sync result for the post-`SPEC-066` aftermath line
- Findings: `MC_Handoff_2026-04-24_v3.md` reports that MC has carried the aftermath stack beyond HC’s current indexed state: `SPEC-068` closes the spell-throttle gap by moving `hv_spell_trade_count` from a scalar to a per-strategy dict; `SPEC-070 v2` resolves the legacy selector/engine long-leg convention mismatch by aligning engine long legs to delta-based lookup; and `SPEC-071` lands on a broken-wing aftermath `IC_HV` shape (`LC 0.04 / LP 0.08`, `DTE 45` unchanged) after rejecting the richer-wing / tail-put alternatives and the `DTE = 60` branch. `SPEC-072` is frontend-only and still pending HC deploy, while `SPEC-073` is a dead-code cleanup. This is enough to define a clean HC reproduction queue, but not enough to treat the whole MC stack as already canonical on HC
- Risks / Counterarguments: this is a sync-planning conclusion, not a direct strategy endorsement by itself. MC-side `DONE` does not automatically mean HC-side code, artifacts, and live runtime are aligned. The most fragile items are the production-affecting ones (`SPEC-068`, `SPEC-070 v2`, `SPEC-071`) because they change aftermath routing semantics or leg construction rather than just display or cleanup
- Confidence: medium-high
- Next Tests: reproduce the stack on HC in order of strategy impact: `SPEC-068`, `SPEC-069`, `SPEC-070 v2`, `SPEC-071`, then `SPEC-072` deploy and `SPEC-073`; verify selector output, artifacts, and old Air runtime separately rather than assuming a single bulk sync is sufficient
- Recommendation: reproduce on HC
- Related Spec: `SPEC-068`, `SPEC-069`, `SPEC-070`, `SPEC-071`, `SPEC-072`, `SPEC-073`
- See: `sync/mc_to_hc/MC_Handoff_2026-04-24_v3.md`

### R-20260424-02 — Q029 identifies one material research/live parity gap, but MC chose reporting-layer containment rather than engine rewrite

- Topic: MC 5-dimension parity audit on aftermath research versus live-scale execution
- Findings: MC reports that most parity dimensions came back as `no issue / minor drift`, but one material gap remained: the backtest engine hardcodes `qty = 1` and therefore ignores selector `SizeTier`. For HIGH_VOL aftermath work, this means research PnL is expressed as `1 SPX` while live implementation may be `1 XSP`, roughly a `10x` notional mismatch in some cases. MC did **not** resolve this by rewriting the engine. Instead, `Q033` chose an interim governance path (`Option B+E`): keep engine outputs in `research_1spx` terms, and require `live_scaled_est` alongside `PnL / worst / SegMaxDD / BP` in handoffs, specs, and RDD-style outputs, with aftermath HIGH_VOL defaulting to the agreed scale factors
- Risks / Counterarguments: this is a pragmatic reporting fix, not a true model unification. It lowers the risk of over-reading research magnitudes, but it does not eliminate the architectural mismatch. A future live-scale engine (`Q035`) remains a separate long-term design problem and should not be smuggled in as a “small cleanup”
- Confidence: high on the existence of the mismatch; medium on the durability of the reporting-only mitigation
- Next Tests: first reproduce the parity audit and reporting convention on HC; only after that should PM decide whether the reporting-layer answer is sufficient or whether the project needs a deeper engine/RDD branch
- Recommendation: reproduce in HC, no engine rewrite yet
- Related Question: `Q029`, `Q033`, `Q035`
- See: `sync/mc_to_hc/MC_Handoff_2026-04-24_v3.md`, `sync/open_questions.md`

### R-20260424-01 — Q019 Phase 1 materially upgrades the close/open VIX mismatch from intuition to measured drift, but PM decision remains deferred

- Topic: MC Phase 1 measurement of close-based versus open-based VIX semantics
- Findings: MC reports a full-period Bloomberg OHLC study over `27` years and finds the mismatch is real enough to matter: `aftermath` flips on about `4.63%` of days, regime classification on about `9.71%`, and trend-layer outcomes on about `31.54%`. Inside the aftermath subset, MC reports `319` flips, split roughly `179` cases of `close=False / open=True` versus `140` in the opposite direction. This means HC can no longer treat the VIX time-basis issue as a vague modeling concern; it now has measured drift large enough to affect the interpretation of `SPEC-064 / SPEC-066 / SPEC-068 / SPEC-070 v2 / SPEC-071`
- Risks / Counterarguments: Phase 1 still does not answer the PM question of what to do with the new evidence. A measured mismatch is not yet a mandate to reinterpret historical backtests, ship open-based logic, or retroactively discredit close-based specs. MC explicitly leaves that as a PM choice among follow-up paths `A / B / C`
- Confidence: medium-high on the measurement; low on the policy conclusion
- Next Tests: wait for PM direction before escalating implementation. If PM wants action, the most disciplined HC next step is to reproduce the measurement on HC and then choose between closing the question, re-running key aftermath samples open-based, or codifying a future dual-sensitivity rule
- Recommendation: defer decision, keep evidence indexed
- Related Question: `Q019`
- See: `sync/mc_to_hc/MC_Handoff_2026-04-24_v3.md`, `sync/open_questions.md`

### R-20260420-03 — Q021 opened (originally `Q020` in HC; renumbered 2026-04-25 to align with MC convention, since MC's `Q020` covers the `backtest_select` simplification): the real follow-up to Q018 may be peak-separation semantics, not slot count alone

- Topic: Whether `Q018 / SPEC-066` captured the right phenomenon or accidentally monetized semantically wrong back-to-back `IC_HV` re-entry
- Findings: PM clarified that the desired behavior in a double-spike sequence is not “take two `IC_HV` trades in quick succession after the first peak,” but “take one trade after the first peak fails to complete the opportunity, then re-arm and capture the second peak’s subsequent mean reversion.” This creates a new research problem that is adjacent to, but not the same as, `Q018`: the historical `cap=2 + B` result may mix together two very different sources of alpha — true second-peak capture versus immediate back-to-back re-entry after the first peak. Until that decomposition is measured, it would be premature to treat the existing `SPEC-066` economics as the final semantic answer for double-spike handling
- Risks / Counterarguments: this does **not** yet prove `SPEC-066` is wrong or should be rolled back. The current shipped rule may still be profitable and robust enough in aggregate, and the observed `2026-03-09 / 2026-03-10` pair may simply expose that the research objective was framed too loosely. The key open question is attribution: how much of the measured gain disappears if the second slot is constrained to require a distinct new peak or minimum re-arm distance
- Confidence: medium
- Next Tests: quantify the `SPEC-066` trade set in three buckets: (1) immediate back-to-back re-entries after the same peak, (2) true distinct-second-peak aftermath trades, and (3) all other multi-slot aftermath cases; then compare PnL, Sharpe, drawdown, and historical trigger count. A useful control variant is “single-slot + re-arm only after new peak,” which should be compared directly against current `cap=2 + B`
- Recommendation: research
- Related Question: `Q021` (HC originally `Q020`)
- See: `sync/open_questions.md`, `task/SPEC-066.md`

### R-20260420-02 — `SPEC-066` passed review with spec adjustment and is now DONE

- Topic: Final review outcome for `SPEC-066` after Developer implementation
- Findings: Quant completed the final review and closed `SPEC-066` as **PASS with spec adjustment**. No additional code changes were required. The implementation itself already met the strategy intent: `IC_HV_MAX_CONCURRENT = 2`, `AFTERMATH_OFF_PEAK_PCT = 0.10`, the `2026-03-09 / 2026-03-10` double-spike pair is captured, `2008-09` remains filtered, and system-level PnL / Sharpe / MaxDD all land within the intended target band. The two apparent failures were both specification issues rather than implementation defects. `AC4` had been written too strictly by requiring non-`IC_HV` trade-set identity; Quant revised it to the correct logic-level invariant that non-`IC_HV` strategies still use the original single-slot `_already_open` branch, while accepting natural trade-date cascade under shared BP and serial engine behavior. `AC10`’s old expected artifact-count range `[33,40]` was also corrected to `[45,55]`, after confirming the observed count `49` is fully consistent with the actual `IC_HV` delta and that all trades remain `Iron Condor (High Vol)`
- Risks / Counterarguments: this is a clean closure, but it also clarifies an important review lesson: for specs that modify shared-capital or shared-timeline behavior, trade-set identity can be the wrong acceptance criterion even when branch-local logic is correct. Similar future specs should prefer logic invariants and targeted regression tests over global trade-set equality when cascade effects are expected
- Confidence: high
- Next Tests: no immediate research follow-up is required for `Q018`; if PM wants to push the HIGH_VOL line further, the next open problem is `Q019`, not more rework on `SPEC-066`
- Recommendation: done
- Related Spec: `SPEC-066`
- Related Question: `Q018`
- See: `task/SPEC-066.md`, `task/SPEC-066_handoff.md`

### R-20260420-01 — Q018 Phase 2 closes the branch-selection question and makes `cap=2 + B` a credible DRAFT candidate

- Topic: Final Phase 2 results for the `Q018` aftermath single-slot question
- Findings: Quant completed the full Phase 2 sweep and the answer is no longer “which research branch should we test next,” but “is the selected combination narrow enough for a Spec.” The decisive result is `cap=2 + B`: allow up to `2` concurrent `IC_HV` aftermath positions and tighten `AFTERMATH_OFF_PEAK_PCT` from `0.05` to `0.10`. This combined shape clearly beats either component alone. Variant A by itself (`cap=2`) still adds real alpha but worsens max drawdown materially (`-43%`); Variant B by itself lowers drawdown sharply but leaves much of the second-peak alpha uncaptured. The combination delivers the full practical point of the research: about `+$47K` additional system PnL, Sharpe about `+0.02`, and max drawdown only about `+4%` worse than baseline. It also fully resolves the original `2026-03` double-spike trigger case with two captured aftermath entries (`2026-03-09` and `2026-03-10`). Cap sweep results further show that `cap=3` is strictly unattractive on a risk-adjusted basis, while higher caps do not add enough certainty to justify losing the “small and controlled” character of `cap=2`
- Risks / Counterarguments: this is still not “no-risk alpha.” The `+$47K` is backtest-driven over a sparse historical sample, and Phase 2 did not add a bootstrap CI. The chosen `0.10` threshold was selected by PM rather than by a full sensitivity grid, so it should be treated as a pragmatic rule choice rather than a proven global optimum. Engine-level changes are also more sensitive than the prior SPEC-064 selector-only bypass, because the implementation touches concurrency behavior in `backtest/engine.py` and therefore needs explicit regression protection to guarantee non-`IC_HV` strategies remain single-slot
- Confidence: medium-high
- Next Tests: the natural next step is no longer another research branch, but a narrow DRAFT Spec (`SPEC-066`) with strong acceptance criteria: `IC_HV` concurrent cap default `2`, `AFTERMATH_OFF_PEAK_PCT = 0.10`, expected PnL uplift around `+$47K` within tolerance, max drawdown no worse than about `+10%`, explicit reproduction of the `2026-03-09 / 2026-03-10` double-spike case, and explicit regression checks that non-`IC_HV` strategies remain single-slot. Optional hardening such as bootstrap CI can be added in Spec review if PM wants extra rigor
- Recommendation: ready for DRAFT Spec
- Related Question: `Q018`
- See: `sync/open_questions.md`, `doc/research_notes.md`

### R-20260419-10 — Q018 Phase 1 produced two credible directions, but not a decisive remedy

- Topic: Phase 1 prototype for the `Q018` aftermath single-slot question
- Findings: Quant completed the first real prototype round and the result is more interesting than a simple “allow two slots” answer. Variant A (multi-slot aftermath replay) identified `36` blocked clusters and, under ex-post trade replay, produced about `+$47,735` total PnL with `86.1%` win rate. The gains were stronger than the earlier rough approximation suggested because `IC_HV` often reaches `50%` profit quickly in high-VIX aftermath environments. Tail losses were real but concentrated, especially `2008-09` (`-$7,968` single-trade worst case), while `2020-03` was only mildly negative and `2025-04` was actually profitable. Variant B (tightening `AFTERMATH_OFF_PEAK_PCT` from `0.05` to `0.10`) looked attractive for a different reason: it cut max drawdown by about `36%` (`-$20,464` to `-$13,187`) and improved `IC_HV` Sharpe with almost no engineering cost, while only dropping two trades. This means the two directions are not obvious substitutes: A captures more missed alpha, B reduces risk cheaply, and the best answer may even be a combination
- Risks / Counterarguments: Variant A is still materially approximate. The big missing pieces are BP ceiling, shock-engine / overlay interactions, and the fact that only one day per blocked cluster was replayed. Any of those could reduce the apparent `+$47,735`. Variant B’s drawdown improvement may also be partly path luck because the specific removed trades have not yet been stress-tested by year or bootstrap. Phase 1 therefore upgrades Q018 from a “single anecdote” to a real research branch, but it does not yet justify a DRAFT Spec
- Confidence: medium
- Next Tests: the most valuable next step is Phase 2-A — re-run the multi-slot path with BP ceiling, shock engine, and overlay constraints so the core `+$47,735` claim gets a more realistic answer. If PM prefers a cheaper / safer path, Phase 2-C can instead scan tighter aftermath thresholds first. The “multi-slot + tighter threshold” combo is also plausible, but only after the realism gap in A is narrowed
- Recommendation: continue research
- Related Question: `Q018`
- See: `sync/open_questions.md`, `doc/research_notes.md`

### R-20260419-09 — Q019 opened: the project may have a material VIX time-basis mismatch between backtest and live recommendation

- Topic: Whether using end-of-day VIX in backtests while making live recommendation decisions from opening / early-session VIX materially changes routing and gate behavior
- Findings: PM identified a structural modeling mismatch worth separate study: historical backtests and much of the research stack rely on daily close-based VIX time series, while live recommendation decisions are taken near the open, when VIX is often materially above its later close and may even mark the intraday high. If this mismatch is large enough, it could alter regime classification (`HIGH_VOL` vs `NORMAL`), `VIX_RISING` logic, IVP-like high-vol gates, and the aftermath condition used in `SPEC-064` / `Q017`. This is not yet a strategy conclusion; it is a new measurement problem
- Risks / Counterarguments: not every intraday-open/close difference matters strategically. The relevant question is not whether VIX opens above its close in general, but whether using open-based VIX would have changed actual selector outputs, blocked trades, or realized backtest path decisions in a non-trivial number of cases. Without that quantification, the issue could be either a real blind spot or just a plausible-sounding source of noise
- Confidence: medium on the importance of the question; low on the size or direction of the effect
- Next Tests: compare close-based versus open-based (or earliest available live-time) VIX inputs on historical recommendation paths, starting with high-volatility and post-spike windows; quantify how often route, gate, or aftermath outcomes would have changed
- Recommendation: research
- Related Question: `Q019`
- See: `PROJECT_STATUS.md`, `sync/open_questions.md`

### R-20260419-08 — `SPEC-064` shipped; the first real double-spike review surfaces a new single-slot aftermath question (`Q018`)

- Topic: Post-ship review of the first real-world double-VIX-spike case after `SPEC-064` / `SPEC-065`
- Findings: `SPEC-064` (`HIGH_VOL Aftermath IC_HV Bypass`) shipped to production and passed review, and `SPEC-065` added a durable research-view pill for the same path. The shipped artifact matches the backtest trigger set exactly enough for audit use. PM review of the real `2026-03` double-spike sequence then surfaced a new phenomenon: the first peak opened an `IC_HV` aftermath trade, but the second peak’s aftermath dates (`2026-03-31`, `2026-04-01`, `2026-04-02`) were blocked by the engine’s `_already_open` single-slot constraint even though offline selector replay says they otherwise would have routed to `IC_HV` again. This does not prove that multi-slot opening is the right remedy, but it does establish a concrete research trigger for a new question about single-slot aftermath misses
- Risks / Counterarguments: the current evidence is still only a trigger case. The missing second-peak trade could mean “allow two aftermath slots,” but it could also mean “tighten the first aftermath trigger so the slot is preserved for the later, better peak.” The historical gap between the `73` research aftermath windows and the `32` shipped `IC_HV` aftermath entries likely contains multiple causes, not just `_already_open`, and none of that has been quantified yet. Any multi-slot idea would also be a risk-structure change, not a mere routing tweak
- Confidence: medium on the phenomenon; low on the remedy
- Next Tests: if PM wants to advance `Q018`, start with a strict Phase 1 prototype comparing (A) `IC_HV` aftermath with two concurrent slots versus (B) a tighter aftermath threshold such as `off_peak >= 10%`, then compare incremental trade count, PnL / CI, Sharpe, drawdown in `2008-10` and `2020-03`, and BP utilization
- Recommendation: research
- Related Question: `Q018`
- See: `task/SPEC-064.md`, `doc/research_notes.md`

### R-20260419-07 — Q017 Phase 2 closes the ex-ante question and makes `HIGH_VOL aftermath IC_HV bypass` a credible DRAFT candidate

- Topic: Whether Q017 has a live-usable, non-hindsight recognition rule that is strong enough to support a narrow HIGH_VOL bypass design
- Findings: Phase 2 shows that the ex-ante signal is simply the aftermath condition itself: trailing-10d VIX peak `>= 28`, current VIX at least `5%` below that peak, and still below `EXTREME_VOL`. Additional filters do not help. Across the `22` `IC_HV` aftermath trades identified in Phase 1, performance is positive in every decade bucket, with only one losing trade (`2002-08-23`). Threshold scans for `peak_drop_pct` remain broadly flat and significant, which means the feature is redundant rather than discriminative. `vix_3d_roc` also fails as a better recognizer; like the current `vix_rising_5d` logic, it ends up filtering out some of the best aftermath trades. The existing `EXTREME_VOL` threshold (`VIX >= 40`) is what keeps the core `2008-10` disaster regime out of sample, so the proposed path does not need to defeat that protection to capture the observed edge
- Risks / Counterarguments: the sample is still small (`22` trades over `25` years), and the evidence is specific to `IC_HV`; it should not be generalized to `BPS_HV` or `BCS_HV`. The proposed bypass also still needs one last system-level sanity check if PM wants extra rigor, especially around the single `2002-08-23` loser and around ensuring the protection story remains intact under full selector behavior
- Confidence: medium-high
- Next Tests: if PM wants a final pre-Spec check, do a focused fast-path-style prototype that only opens the `IC_HV` path under the aftermath condition while preserving `EXTREME_VOL`, then confirm system Sharpe / PnL / drawdown stay aligned with the Phase 1 broad-gate results. Otherwise, the next step is to draft the narrow Spec
- Recommendation: enter Spec
- Related Question: `Q017`
- See: `doc/research_notes.md`

### R-20260419-06 — Q017 Phase 1 confirms the aftermath-window leak is real in strategy PnL, with `IC_HV` carrying most of the edge

- Topic: Re-testing `Q017` with real strategy PnL and event-removal robustness instead of SPX forward-return proxies
- Findings: Phase 1 materially strengthens the case for `Q017`. Three gate-lift variants all produced significantly positive aftermath-window trades using real strategy PnL: `ivp63` gate off (`n=16`, avg about `+$1,477`, CI positive), `VIX_RISING` off (`n=10`, avg about `+$2,080`, CI positive), and both gates off (`n=24`, avg about `+$1,772`, CI positive). Removing the recent `2020-03 / 2025-04 / 2026-04` V-shaped events barely changed the result because those episodes only contributed `1/24` of the relevant trade sample. The edge is overwhelmingly carried by `IC_HV` (`22/24` trades, about `+$1,841` average, `95.5%` win rate). System-level Sharpe in the broad “both gates off” variant stayed flat at about `0.41` while total PnL rose materially, so this is no longer just a proxy-level suspicion
- Risks / Counterarguments: this is still not ready for implementation. The sample is small (`24` trades over `26` years), and the strongest evidence sits in `IC_HV`, not across all HIGH_VOL structures. Ex-ante recognition is still unresolved, and `2008`-style disaster continuation has not yet been explicitly separated from the positive aftermath trades. So the result upgrades confidence that the leak is real, but not confidence that we already know the safe live rule
- Confidence: medium-high
- Next Tests: proceed to Phase 2 rather than jumping to Spec. The two most useful next steps are ex-ante recognition work (`peak_drop_pct` / faster VIX-ROC logic) and narrower gate-specific tests that preserve the finding that `IC_HV` is the main alpha carrier
- Recommendation: continue research (upgrade confidence)
- Related Question: `Q017`
- See: `doc/research_notes.md`

### R-20260419-04 — Early post-peak VIX-reversal windows are a real HIGH_VOL phenomenon, but still too ambiguous for action

- Topic: Whether the system structurally misses opportunities in the first post-peak VIX pullback window while trend is still not `BULLISH`
- Findings: Quant identified `73` aftermath windows from `2000–2026` where VIX had peaked at `>= 28` within the prior `10` days and had already retraced by at least `5%`, producing `458` wait-days with non-`BULLISH` trend. The blockade is overwhelmingly a `HIGH_VOL` problem (`441/458`, about `96%`), dominated by two filters: `HIGH_VOL + VIX_RISING` (`208` days) and `HIGH_VOL + BEARISH + ivp63>=70` (`162` days). Forward SPX returns after these blocked days are directionally positive versus baseline wait-days, but all bootstrap confidence intervals still cross zero. The event split is highly bimodal: `2008-10` strongly supports current caution, while `2020-03`, `2025-04`, and `2026-04` look like meaningful missed rebounds
- Risks / Counterarguments: this result is still too proxy-driven for implementation decisions. SPX forward return is not strategy PnL, especially under `HIGH_VOL` where vega and path matter. The averages are also heavily influenced by a few modern V-shaped reversal episodes, while `2008` remains a strong counterexample showing the current filters can be genuinely protective. Live-identifiable peak logic is also unresolved, so the apparent “post-peak” state is not yet an ex-ante trading signal
- Confidence: medium
- Next Tests: prioritize real strategy-PnL tests inside the aftermath window (`BPS_HV` / `IC_HV` / `BCS_HV`) and test whether a live-usable peak-drop metric can separate `2008`-style continuation from `2020`-style reversal. Until then, no HIGH_VOL gate change should advance toward Spec
- Recommendation: hold
- Related Question: `Q017`
- See: `doc/research_notes.md`

### R-20260419-05 — Q017 should be advanced in strict phases, not as a parallel three-tier bundle

- Topic: Planning order for the `Q017` aftermath-window research stack
- Findings: the three proposed tiers do not have equal value. `Tier 1` is the gating phase because it answers whether the apparent opportunity survives replacement of the SPX proxy with real strategy PnL and whether the result still exists after removing the recent V-shaped reversals (`2020-03`, `2025-04`, `2026-04`). Only if that phase remains directionally positive should `Tier 2` search for ex-ante recognition features such as `peak_drop_pct` or faster VIX-ROC logic. `Tier 3` is explicitly downstream because it starts asking which concrete HIGH_VOL gate to alter, which would be premature before the alpha itself is established
- Risks / Counterarguments: this sequencing may feel slower, but it is the cleanest way to avoid optimizing a gate-level fix around a proxy-driven effect. Running all tiers in parallel would create pressure to explain or patch filters before the underlying edge is confirmed
- Confidence: high
- Next Tests: Phase 1 only for now — `T1.1` real strategy PnL, then `T1.2` event-removal robustness. Reassess after that phase before authorizing Tier 2 or Tier 3
- Recommendation: hold / phase-gate
- Related Question: `Q017`
- See: `PROJECT_STATUS.md`, `sync/open_questions.md`

### R-20260419-03 — Research view tooling shipped; exposed a generator semantic trap for future Fast Path visualizations

- Topic: Making completed research artifacts (`Q015` IVP<55 marginal trades, `Q016` Dead Zone A recovery BPS trades) persistently viewable on the backtest page
- Findings: `SPEC-062` and `SPEC-063` are now effectively complete from the research-tooling side. The resulting views reproduce the known study outputs closely enough for PM review: `Q015` shows `17` marginal trades (near the original `18`; one-trade difference comes from `_trade_identity` dedupe boundary), and `Q016` shows the expected `12` recovery-context BPS trades with total `+$2,643`. During rollout, Quant found and fixed a semantic bug in the generator: using “baseline == current production” as the only comparison reference causes any already-landed Fast Path change to collapse its own marginal diff to zero. The corrected logic explicitly compares current production against the old behavior snapshot
- Risks / Counterarguments: this is an engineering / observability lesson, not a new strategy conclusion. It should not be turned into a new open question by itself. The broader rule is simply that future Fast Path visualizations need an explicit two-snapshot baseline definition when the researched behavior is already live
- Confidence: high
- Next Tests: no immediate strategy-side follow-up is required. PM may still visually inspect the SPX-timeline distribution for `Q016`, and browser-level AC checks for `SPEC-063` remain useful, but neither should block current project-state conclusions
- Recommendation: tooling complete
- Related Spec: `SPEC-062`, `SPEC-063`
- Related Question: `Q015`, `Q016`
- See: `doc/dead_zone_a_trade_visualization.html`, `doc/research_notes.md`

### R-20260419-01 — `IVP < 55` passed the key OOS check and is now a credible narrow BPS improvement candidate

- Topic: Out-of-sample validation of relaxing the BPS `NORMAL + BULLISH` upper IVP gate from `IVP < 50` to `IVP < 55`
- Findings: the OOS check came back directionally clean across all three slices. Full history improves from system Sharpe `0.40` to `0.41` with about `+$18,107` more PnL; the in-sample split (`2000–2018`) keeps system Sharpe flat (`0.37` to `0.37`) with about `+$8,087`; the OOS split (`2019–2026`) also keeps system Sharpe flat (`0.48` to `0.48`) with about `+$10,020`. BPS sub-strategy Sharpe improves in every slice (`+0.03` IS, `+0.05` OOS). The marginal `IVP [50,55)` trades remain small (`n=18`) and individually non-significant, but the direction is consistent and no slice shows degradation
- Risks / Counterarguments: this is still a modest edge, not a strong alpha discovery. System Sharpe only improves by `+0.00` to `+0.01`, and the marginal-trade bootstrap CI still crosses zero. A single tail loss (`2025-02-20`, about `-$6,253`) reminds us that the new pocket is not risk-free. So the case is best understood as “safe micro-improvement with moderate confidence,” not “high-conviction new filter”
- Confidence: medium-high
- Next Tests: PM can now decide whether this is enough to promote into a narrow Spec or Fast Path. Optional extra hardening could include cross-validation or focused analysis of the `2025-02-20` tail event, but these are no longer required to justify the move from pure research into implementation candidacy
- Recommendation: near-spec / fast-path candidate
- Related Question: `Q015`
- See: `doc/research_notes.md`

### R-20260419-02 — Q015 narrow BPS gate relaxation was implemented via Fast Path

- Topic: Production follow-through on the `IVP < 55` BPS candidate after OOS validation
- Findings: Quant applied the narrow change directly in `strategy/selector.py`, raising `BPS_NNB_IVP_UPPER` from `50` to `55` and adding an inline note referencing the Q015 OOS evidence. This means the specific “BPS `IVP < 55`” path is no longer an open planning candidate; it is now active production logic via Fast Path
- Risks / Counterarguments: this does not resolve the broader IVP / IC redesign question. The implemented change is deliberately narrow and should not be misread as proof that wider IVP relaxation, IC gate changes, or VIX-joint filters are now approved. Tail-risk reminders from the OOS work still stand, especially the `2025-02-20` style loss case
- Confidence: high
- Next Tests: let normal live / retrospective monitoring accumulate under the new `55` threshold; if future research reopens IVP redesign, treat it as a new question rather than extending the meaning of this Fast Path
- Recommendation: implemented via Fast Path
- Related Question: `Q015`
- See: `strategy/selector.py`, `doc/research_notes.md`

### R-20260418-02 — Dead Zone B does not justify a recovery override; `IVP < 55` is the only near-spec candidate and still needs OOS proof

- Topic: Whether IVP-gate behavior inside VIX recovery windows supports a safe `IVP + VIX` redesign for BPS / IC routing
- Findings: recovery-window analysis shows IVP gates blocked `62` recovery-context days (`38` BPS + `24` IC), and BPS blocks were concentrated in `VIX 18–22` rather than only low-vol conditions. But gate-lifted recovery BPS still failed to show special alpha (`n=14`, avg about `-$12`, Sharpe `0.00`, CI crossing zero), so recovery context itself is not a useful override. The strongest concrete result is narrower: relaxing the BPS gate from `IVP < 50` to `IVP < 55` is the only apparent Pareto improvement, lifting system PnL from about `$359,799` to `$377,906` while keeping system Sharpe flat-to-slightly-up (`0.40` to `0.41`). Beyond `55`, the same old cliff reappears and Sharpe drops
- Risks / Counterarguments: the `IVP [50,55)` “good pocket” is still only `n=8`, so the observed Sharpe improvement may be noise rather than a durable edge. VIX-only or compound `IVP OR VIX` filters remain post-hoc and are not ready for production use. IC-side `IVP [20,50]` gate behavior was observed but not fully isolated yet, and slot sharing means the true opportunity value remains smaller than raw blocked-day counts suggest
- Confidence: high for “recovery is not a special alpha source”; medium for “`IVP < 55` is truly better rather than sample luck”
- Next Tests: OOS validation has now passed; remaining next step is PM decision on whether to promote this into a narrow Spec / Fast Path. IC gate evaluation can continue later under the same methodology, but VIX-joint-filter exploration should stay paused
- Recommendation: superseded by `R-20260419-01`
- Related Question: `Q015`
- See: `doc/research_notes.md`, `doc/strategy_status_2026-04-16.md`

### R-20260418-01 — VIX recovery-window dead zone is systemic, but still lacks “fix without Sharpe decay” evidence

- Topic: Post-spike premium-selling windows being blocked after HIGH_VOL→NORMAL transitions
- Findings: across `66` historical HIGH_VOL→NORMAL transition windows with elevated IVP, `34` lasted at least `>=3` days; `64%` (`214/336`) of candidate trading days were blocked, and `14` windows had zero entry opportunity throughout. The blockade is not a single-gate issue: Dead Zone A is a route hole (`NORMAL + HIGH + BULLISH`, from `SPEC-060 Change 3`) and accounts for `37%` (`80` days), while Dead Zone B comes from IVP gates (`BPS >= 50` plus IC `[20,50]`) and accounts for `41%` (`87` days). `VIX_RISING` safety filtering explains the remaining `22%` and still looks like reasonable protection
- Risks / Counterarguments: the original follow-up hypothesis was that Dead Zone A might hide conditional alpha inside recovery windows. That hypothesis has now failed: recovery-window `NORMAL + HIGH + BULLISH` BPS produced only `n=12`, avg `+$220`, bootstrap CI crossing zero, and did not outperform non-recovery samples. This means the “systemic dead zone” observation is still real, but Dead Zone A is not the fix path
- Confidence: high for “dead zone exists”; high for “drop Dead Zone A as an independent fix candidate”
- Next Tests: no further validation is needed for Dead Zone A. Research focus should return to Dead Zone B only: how IVP gates behave inside recovery windows, and whether any joint `IVP + VIX` redesign can recover opportunities without Sharpe decay
- Recommendation: hold
- Related Question: `Q015`
- See: `doc/research_notes.md`, `doc/strategy_status_2026-04-16.md`

### R-20260415-01 — DIAGONAL Gate 1 (`ivp252` 30–50 marginal zone) is net harmful and should be removed

- Topic: Net value of `SPEC-049` DIAGONAL Gate 1
- Findings: sensitivity analysis first showed the Gate 1 upper bound is highly robust across `40/45/50/55/60/65`, with Sharpe staying around `0.41–0.43` and all bootstrap results significant. Follow-up net-value analysis then showed the gate itself is harmful: removing Gate 1 increases DIAGONAL trades from `115` to `119`, raises DIAGONAL total PnL by about `$11,146`, and improves total system PnL by the same amount. The gate blocked `47` trades whose total PnL was `+$46,403`, with bootstrap CI significantly positive, so it is filtering out good trades rather than protecting the system
- Risks / Counterarguments: this should be treated as a rule-removal conclusion, not threshold optimization. The lesson is not “find a better number,” but “the gate has no net value under full-history validation.” As with the former both-high gate, the original rule appears to have been built on a negatively selected subset rather than a true system-wide edge
- Confidence: high
- Next Tests: keep the detailed-layer strategy snapshot aligned so Gate 1 no longer appears as current active logic; use this case as one of the confirmed negative-selection-bias examples when evaluating future integer threshold gates
- Recommendation: implemented via Fast Path
- Related Spec: `SPEC-049`
- Related Question: `Q014`, `Q015`
- See: `task/SPEC-049.md`, `doc/strategy_status_2026-04-10.md`, `strategy/selector.py`

### R-20260416-01 — BPS IVP≥50 gate is NOT the same problem as Gate 1; gate should be retained but IVP alone is a flawed filter

- Topic: Full evaluation of `NORMAL + BULLISH` `IVP >= 50` entry gate using same methodology as Gate 1
- Findings: (1) Sensitivity is NOT flat — real cliff at IVP 55→60 where Sharpe drops from 0.53 to 0.23. (2) Blocked trades are NOT significantly profitable (avg +$7, CI [-$601, +$1,062]). (3) Gate deletion would halve BPS Sharpe (0.49→0.22) and worsen MaxDD by 70%. (4) System cost of $6,690 traces to slot-occupancy displacement (6/6 explained), not quality filtering. (5) IVP and VIX are weakly negatively correlated (r=-0.154) in NNB regime; 68% of IVP≥50 blocks happen at VIX<18. The gate's “stressed vol” rationale is conceptually wrong, but it accidentally protects a real Sharpe cliff
- Risks / Counterarguments: cross-tab analysis shows VIX [18,20) × IVP [55,65) is the actual danger zone, while VIX [16,18) is safe regardless of IVP — but any compound filter (e.g. `VIX<18 OR IVP<50`) would be post-hoc optimization. IVP<55 also looks attractive (Sharpe 0.64) but sits at the sample-internal optimum, high overfit risk
- Confidence: high (for “retain gate” conclusion); medium (for IVP+VIX joint filter as research direction)
- Next Tests: accumulate live BPS trades to validate VIX×IVP cross-tab OOS; research IVP+VIX compound filter and VIX-trend conditioning; consider BPS dual-slot architecture to eliminate displacement artifact
- Recommendation: retain gate=50, research redesign via `Q015`
- Related Question: `Q015`
- See: `research_notes.md` §55, `strategy_status_2026-04-16.md`, `backtest/prototype/bps_ivp_gate_sensitivity.py`, `backtest/prototype/bps_gate_vix_vs_ivp.py`

### R-20260412-03 — `SPEC-061` 只建立了 SoMuchRanch 三层体系中的最小 Layer 2 生产 cell，主要剩余缺口是运行时风控而不是入场逻辑

- Topic: `/ES short put` 三层体系与当前测试 / 生产覆盖状态盘点
- Findings: `SPEC-061` 已把 Layer 2 的最小生产 cell 落地到单槽、`1` 张、`45 DTE`、`20 delta`、`trend filter`、`BP <= NLV 20%` 的入场路径；但 SoMuchRanch 原始三层体系中的 Layer 1（核心 SPY/VTI 持仓）与 Layer 3（BSH）在当前生产系统中仍不存在，Strategy #3（long `/ES` calls）也尚未进入研究实现。对当前最小 cell 而言，最大剩余缺口不是入场逻辑，而是运行时风控：`-300%` stop 在生产中仍是文档化规则，未实现自动触发；趋势转负后的持仓行为也未定义
- Risks / Counterarguments: 当前 `/ES` 路径是在“无 Layer 1 缓冲、无 Layer 3 对冲”的条件下独立运行；再加上止损当前缺少系统化监控，这意味着 `SPEC-061` 虽可视为 MVP 成立，但生产安全边界仍偏薄。PM 已明确：不能接受纯人工盯仓止损，最低要求是系统监控 stop 条件并触发 bot 提醒。另一方面，Layer 1 / Layer 3 缺失是有意缩 scope，而非实现遗漏，不应把所有未覆盖项都立即提升为实现需求
- Confidence: high
- Next Tests: 优先考虑一个狭窄 follow-up Spec 来补运行时止损监控、bot alert 与 post-entry 管理定义；其余 Layer 1 / Layer 3 / Strategy #3 保持 research track；低优先级测试补全包括 `/api/es/recommendation`、`live_delta=None` 分支与 SPAN 动态扩张 stress test
- Recommendation: hold
- Related Spec: `SPEC-061`
- Related Question: `Q012`, `Q013`
- See: `task/SPEC-061.md`

### R-20260412-01 — `/ES` is now the preferred ES short put production path, but shared buying power becomes the main constraint

- Topic: ES short put production-path feasibility at ~$500k account size
- Findings: live account confirmation shows `/ES` short put buying power effect is about `$20,529` per contract, making 1-contract single-slot deployment feasible at current account size; round-trip friction appears acceptable relative to collected premium; compared with XSP, `/ES` now looks structurally superior on execution quality and lot sizing
- Risks / Counterarguments: `/ES` margin is not isolated from SPX options buying power in the current account view, so ES puts and SPX Credit compete for the same BP pool; SPAN margin can also expand sharply during volatility spikes, creating simultaneous mark-to-market loss plus BP compression
- Confidence: high
- Next Tests: define a shared-BP budgeting rule for `/ES` plus SPX Credit; confirm whether standard quarterly `/ES` options differ materially from the observed EOM weekly series in margin/liquidity; if PM agrees, narrow to a minimal DRAFT Spec
- Recommendation: enter Spec
- Related Spec: `N/A`
- Related Question: `Q012`
- See: `sync/open_questions.md`

### R-20260412-02 — current HC planning blocker is documentation drift, not Schwab access

- Topic: HC-side planning status after Schwab connectivity confirmation
- Findings: HC has already connected successfully to Schwab Developer Portal, so `Q009` should no longer be treated as the top HC blocker; the more immediate planning risk is stale or mixed indexing across `PROJECT_STATUS.md`, `RESEARCH_LOG.md`, and `sync/open_questions.md`
- Risks / Counterarguments: MC may still remain blocked on its own environment path, so this is a cross-environment status clarification rather than a full project-wide resolution
- Confidence: high
- Next Tests: keep HC and MC environment status explicitly separated in the index layer; avoid carrying MC blockers into HC priority summaries unless they block shared work
- Recommendation: hold
- Related Spec: `N/A`
- Related Question: `Q009`
- See: `PROJECT_STATUS.md`, `sync/open_questions.md`

### R-20260411-01 — ES short put trend filter looks promising, but remains research-only

- Topic: ES short put system research using SPX proxy data
- Findings: across the phased study, the trend filter consistently improved average trade outcomes and reduced drawdowns; significance became visible only after moving from a single 45 DTE slot to a multi-DTE ladder
- Risks / Counterarguments: the core results still rely on SPX proxy assumptions rather than /ES option history, and the full system mixes naked puts, leverage management, and hedges
- Confidence: medium
- Next Tests: narrow scope to one minimal production-relevant cell before any Spec work
- Recommendation: hold
- Related Spec: `N/A`
- Related Question: `Q012`
- See: `research/strategies/ES_puts/spec.md`

### R-20260411-02 — Dynamic leverage for ES puts only works with a trend filter

- Topic: Interaction between VIX-based leverage sizing and trend gating
- Findings: leverage-table baseline behavior produced collapse-like drawdowns, while the filtered version materially improved bootstrap significance and contained damage; the leverage model should not be evaluated independently from the trend gate
- Risks / Counterarguments: BSH payoff assumptions materially affect tail outcomes, so Phase 3 without full hedge payoff modeling is still incomplete
- Confidence: medium
- Next Tests: treat leverage as a second-stage feature only after the single-cell trend-filter result is accepted
- Recommendation: hold
- Related Spec: `N/A`
- Related Question: `Q012`
- See: `research/strategies/ES_puts/spec.md`

### R-20260411-03 — ES puts may diversify SPX Credit more than they outperform it standalone

- Topic: Portfolio-level value of the ES short put system
- Findings: the strongest late-stage result may be diversification rather than standalone return, with modeled daily return correlation versus SPX Credit near zero and BSH improving survivability once payoff is included
- Risks / Counterarguments: this conclusion depends on proxy data, hedge modeling assumptions, and a still-unresolved production scope
- Confidence: medium
- Next Tests: confirm whether diversification survives a narrower, more realistic implementation model
- Recommendation: hold
- Related Spec: `N/A`
- Related Question: `Q012`
- See: `research/strategies/ES_puts/spec.md`

### R-20260410-01 — DIAGONAL favors structured entry alpha, not generic size-up

- Topic: Recent event-study and IVP regime work around DIAGONAL entry conditions
- Findings: DIAGONAL is the only strategy with clear entry-signal alpha in recent event-study work. This research batch supported tighter DIAGONAL-specific controls and size logic, especially keeping `regime_decay` size-up limited to DIAGONAL rather than broad premium-selling strategies.
- Risks / Counterarguments: sample sizes remain small in some sub-regimes, especially regime_decay and local_spike live tracking
- Confidence: medium
- Next Tests: keep monitoring `Q011` and observed local_spike live outcomes before promoting further sizing changes
- Recommendation: hold
- Related Spec: `SPEC-048` to `SPEC-055`
- Related Question: `Q011`
- See: `doc/strategy_status_2026-04-10.md`

### R-20260410-02 — both-high tested as a DIAGONAL risk regime, but the gate was later removed

- Topic: IVP dual-horizon classification for DIAGONAL entry filtering
- Findings: both-high (`ivp63 >= 50` and `ivp252 >= 50`) tested as negative alpha in the original audit and initially motivated `SPEC-054`. However, this should now be read as a historical research result rather than current live logic, because the DIAGONAL both-high gate was later removed by `SPEC-056c`.
- Risks / Counterarguments: evidence remains directionally useful as a caution flag, but sample size was limited and proved insufficient to keep the gate in the final routing state
- Confidence: medium
- Next Tests: re-evaluate only if future live or out-of-sample evidence rebuilds the case for reinstating a both-high restriction
- Recommendation: hold
- Related Spec: `SPEC-054`, `SPEC-056c`
- Related Question: `Q011`
- See: `doc/strategy_status_2026-04-10.md`

### R-20260410-03 — local_spike began as tag-only, but later moved into DIAGONAL full size-up

- Topic: Whether local_spike should change sizing or only be tracked diagnostically
- Findings: the initial decision was to keep `local_spike` as a diagnostic tag only (`SPEC-055`). This should now be read as an intermediate step, not the final state: later strategy updates moved `local_spike` into DIAGONAL full size-up via `SPEC-055b`.
- Risks / Counterarguments: the original live-sample caution still matters, so this remains a regime worth monitoring even though the production sizing rule has already advanced
- Confidence: low
- Next Tests: monitor live outcomes under the implemented `SPEC-055b` behavior and revisit only if realized results diverge from the research expectation
- Recommendation: hold
- Related Spec: `SPEC-055`, `SPEC-055b`
- Related Question: `N/A`
- See: `doc/strategy_status_2026-04-10.md`

### R-20260329-01 — BPS holding-period IVP stop losses are harmful

- Topic: BPS and BPS_HV holding-period exits based on high IVP
- Findings: both generic `IVP > threshold` exits and IVP spike exits degraded global PnL in full-history tests
- Risks / Counterarguments: individual loss cases can still look compelling, which may tempt overfitting on memorable examples
- Confidence: high
- Next Tests: focus BPS risk management research on entry filtering rather than holding-period panic exits
- Recommendation: drop
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260329-02 — Bear Call Diagonal has no useful bullish trend-flip exit

- Topic: Testing a symmetric exit rule for Bear Call Diagonal
- Findings: bullish trend signals appeared in both winners and losers, so the rule could not separate good trades from bad ones
- Risks / Counterarguments: small sample size means nuance may still exist, but current evidence does not justify a production rule
- Confidence: medium
- Next Tests: if revisited, focus on entry filters rather than holding-period trend exits
- Recommendation: drop
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-01 — BPS_HV DTE must remain well above exit threshold

- Topic: HIGH_VOL BPS_HV DTE correction
- Findings: entering at the same DTE as the roll threshold caused near-immediate exits; increasing `high_vol_dte` from 21 to 35 materially improved results
- Risks / Counterarguments: the rule is robust, but future parameter tuning should still be checked against actual effective holding days
- Confidence: high
- Next Tests: treat `DTE_entry - DTE_exit_threshold` as a required validation check for future strategy variants
- Recommendation: hold
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-02 — HIGH_VOL should use BPS_HV, not LEAP

- Topic: Strategy choice in HIGH_VOL environments
- Findings: replacing directional LEAP exposure with `BPS_HV` aligned the system with theta-income logic, reduced model fragility, and produced controllable risk under stressed vol
- Risks / Counterarguments: HIGH_VOL remains inherently harder to trade, so even the improved structure still needs tighter risk posture and size discipline
- Confidence: high
- Next Tests: keep the `EXTREME_VOL` hard stop and validate any future HIGH_VOL changes against stressed periods first
- Recommendation: hold
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-03 — IVR and IVP disagreements should defer to IVP

- Topic: Handling IV regime misclassification after extreme volatility spikes
- Findings: when `|IVR - IVP| > 15`, IVR can be distorted by old regime peaks; IVP gave more reliable current-state classification and should drive the decision with adjusted thresholds
- Risks / Counterarguments: threshold choice may still need revision if future VIX regimes differ materially from the calibration period
- Confidence: medium
- Next Tests: monitor future misclassification cases and revisit the divergence threshold only if repeated false regime calls appear
- Recommendation: hold
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-04 — min_hold_days and 50 percent profit target are structural, not cosmetic

- Topic: Why early profit capture still needs a minimum holding window
- Findings: the 50 percent profit target remains reasonable for premium-selling logic, but `min_hold_days = 10` is needed to prevent luck-driven 1 to 3 day exits from distorting utilization and Sharpe
- Risks / Counterarguments: fixed holding windows can occasionally delay legitimate exits, so future exceptions should only be added with strong evidence
- Confidence: medium
- Next Tests: any proposal to bypass `min_hold_days` should be validated with sequential trade behavior, not just static snapshots
- Recommendation: hold
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-05 — SPEC-1B seven-day fast exit should stay rejected

- Topic: Evaluating a true 7-day fast exit path for DIAGONAL
- Findings: after fixing `_entry_value`, the seven-day fast-exit rule never triggered in the examined sample; the study also exposed that the previous pricing bug had artificially inflated early DIAGONAL pnl
- Risks / Counterarguments: the result depends on correct pricing logic, so future engine regressions could create misleading support for the rule again
- Confidence: high
- Next Tests: keep `_entry_value` correctness part of regression checks before reconsidering any fast-exit variant
- Recommendation: drop
- Related Spec: `SPEC-1B`
- See: `doc/research_notes.md`

### R-20260329-03 — Sequential replacement breaks naive entry-confirmation filters

- Topic: Bear Call Diagonal filter based on five consecutive bullish days
- Findings: static prototype logic suggested filtering could help, but sequential backtests showed the rule mainly delayed entry into the same regime at worse prices rather than removing bad trades
- Risks / Counterarguments: this lesson is strategy-structure dependent, but it is a strong warning against promoting static feature correlations directly into production filters
- Confidence: high
- Next Tests: for future entry filters, require sequential replacement analysis before approval
- Recommendation: drop
- Related Spec: `SPEC-005`
- See: `doc/research_notes.md`
