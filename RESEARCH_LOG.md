# RESEARCH_LOG

Last Updated: 2026-05-09 (R-20260509-08: Q019 Tier 1+2 + 2nd Quant APPROVE; Tier 2.5 next gate)
Owner: Planner or PM

---

## Entries

### R-20260509-08 — Q019 Tier 1 + Tier 2 done; 2nd Quant APPROVE; Tier 2.5 mixed-mode is next gate

- Topic: PM-authorised Tier 1 + Tier 2 to quantify the close-based (backtest) vs open-based (live) VIX timing convention impact. 2nd Quant reviewed full chain and approved with two specific wording revisions.
- Findings (Tier 1 — selector-level scan, 4868 days 2007-2026):
  - Regime flip rate: **9.48%** — replicates MC's prior 27y measurement of 9.71% (Δ 0.23pp)
  - Strategy flip rate: 14.56%; Position-action flip: 12.75%
  - VIX bucket concentration: VIX 20-25 (straddling HIGH_VOL=22 threshold) accounts for 44% of regime flips while representing 18% of days; flip rate 23.1% in this bucket
  - 60% of strategy flips are "active ↔ Reduce/Wait" — the more concerning category since open vs close changes "trade or not" decision
- Findings (Tier 2 — full backtest comparison, 19.3y, $500k start):
  - **UPPER BOUND** test (full VIX series substituted with opens, including 5d MA / IV history / peak_10d):
    - Trades: 282 → 271 (-11)
    - Win rate: 75.5% → 71.6% (-3.95pp)
    - Total PnL: $1,684,057 → $1,205,629 (-$478,428, **-28.4%**)
    - **AnnROE: 7.92% → 6.55% (-1.37pp)**
    - MaxDD: 7.92% → 12.37% (+4.45pp)
    - Worst trade: -$44,117 → -$55,489 (-$11,373)
    - Trade overlap: only 19.9% same-date+strategy
  - Per-strategy: BCD has +5 trades but -$204k PnL (counter-intuitive — open-substitution routes BCD into more low-quality entries, consistent with threshold concentration)
  - Per-year hot spots: 2018/2019/2021 each lose $77-109k under open path (years with extended VIX 15-25 ranges)
  - Caveat: this is a deliberate UPPER BOUND. Live uses close-based 5d MA / IV history with intraday-current VIX. Real live impact is bounded above by -1.37pp; lies somewhere in [0, -1.37pp].
- 2nd Quant verdict:
  - **APPROVE** Tier 1 + Tier 2 methodology as sound; **APPROVE** Tier 2.5 mixed-mode as the right next gate before any production decision
  - Q1 (Tier 1 methodology): PASS
  - Q2 (MC replication 9.48% vs 9.71%): PASS — convergence is meaningful, not coincidental
  - Q3 (Tier 2 upper-bound interpretation): PASS with caveat — rolling-stat changes may not be entirely minor; threshold systems still vulnerable to smoothed-field flips near cutoffs; that is exactly why Tier 2.5 is necessary
  - Q4 (Tier 2.5 worth doing): PASS — strongly support, decision stakes too large to skip
  - Q5 (per-year concentration interpretation): **REVISE** wording slightly. The 2018/2019/2021 effect is "likely threshold-structural in prolonged VIX 15-25 regimes, but year-level magnitude is path-dependent and should be confirmed by Tier 2.5" (not yet "reliable structural proof")
  - Q6 (Path C risk): **REVISE** — Path C risk lower than originally described. Intraday alerts (SPEC-086 etc.) remain independent, so switching daily-recommendation VIX to close-based does NOT disable spike monitoring. Real Path C tradeoff is narrower: aligns with backtest convention vs may make daily recommendation less responsive to genuine regime shifts. Path C is more viable than originally framed but still not default until Tier 2.5.
- Quant adjustments applied:
  - Q5 wording softened in this entry (no longer claiming "structural proof"; framed as "likely structural, path-dependent magnitude")
  - Q6 wording corrected: Path C does not impair intraday alerting; only affects daily recommendation responsiveness
- 2nd Quant additional contribution — **NEW Path D candidate (threshold hysteresis / buffer)**:
  - Tier 1 shows the core problem is threshold straddling around VIX 15 and 22
  - Hysteresis rule could preserve intraday responsiveness while reducing noisy open-vs-close flips
  - Example: HIGH_VOL enters only if VIX > 22.5, exits only if VIX < 21.5
  - Or: "If current VIX is within ±0.5 of threshold, defer to close-based regime context"
  - To be explored ONLY if Tier 2.5 confirms material impact
  - Not a replacement for Path C; an additional candidate to evaluate alongside C
- Decision matrix for Tier 2.5 outcome:
  - |ΔAnnROE| < 0.5pp → document negligible, no change (Path A)
  - 0.5pp ≤ |ΔAnnROE| < 1.0pp → MARGINAL, PM decides A vs C vs D (hysteresis)
  - |ΔAnnROE| ≥ 1.0pp → MATERIAL — most error from current-VIX substitution, evaluate Path C and Path D in parallel
- Risks / Counterarguments:
  - Tier 2 was a single full-substitution test; Tier 2.5 result could surprise either direction
  - Real intraday VIX behavior may not exactly match the "open" proxy (live systems use first 1h-bar or current quote, not pure open print)
  - Path D (hysteresis) is conceptually attractive but adds parameter complexity; threshold buffer values would need their own backtest validation
- Confidence: high on Tier 1+2 findings; medium on Tier 2.5 outcome direction (could be NEGLIGIBLE if rolling-stat substitution is the dominant component, or MATERIAL if current-VIX flip is the main driver)
- Next Tests:
  - **Tier 2.5 mixed-mode (PM authorisation pending)**: modify engine so `vix` (current decision) = open while `vix_window` (5d MA, IV history, peak_10d) stays close-based. ~1 day work. Single-line engine modification with monkey-patch wrapper.
- Recommendation:
  - **Do not decide Path A / C / D yet**. Wait for Tier 2.5 outcome.
  - If PM authorises, Tier 2.5 should be next active research item (ahead of Q041 paper-trading).
  - If PM defers Tier 2.5, document Q019 as "open with quantified upper bound" — known divergence ≤ -1.37pp AnnROE; production decision deferred.
- Related: `Q019`, `R-20260509-07` (Q053 closure prior), MC's prior 9.71% reference in `sync/open_questions.md`
- See: `research/q019/close_vs_open_sensitivity.py` (Tier 1), `research/q019/tier2_close_vs_open_backtest.py` (Tier 2), `task/q019_close_vs_open_2nd_quant_review_packet_2026-05-09.md` (review packet)

---

### R-20260509-08 — Q039 refresh post-SPEC-084: HC vs MC IC regular gap attribution unchanged; bp_target lift confirmed orthogonal to selector

- Topic: Q039 refresh — re-ran HC backtest with current production params (post-SPEC-084 bp_target_normal 0.10→0.15) to verify whether the IC regular HC 13 vs MC 6 gap or its attribution has changed.
- Findings:
  - Trade list and bucket attribution **identical** to original §3-§5 analysis:
    - HC 13 / MC 6 / shared 2 / HC-only 11 / MC-only 4 (same dates)
    - 9/11 HC-only = high-IVP fallback/gate (82% of gap explained)
    - 1/11 = valid trade MC-missing (2023-10-04)
    - 1/11 = low-IV bug candidate (2023-11-03)
    - 0/11 = slot blocking
  - **SPEC-084 is confirmed orthogonal to IC regular eligibility**:  acts at the sizing layer within an already-opened slot; IC regular selection happens at the strategy-routing layer. The two layers do not interact for eligibility determination.
- Confidence: high. Attribution is stable across param changes.
- Recommendation: Q039 remains research-only residual. Narrow attribution is sufficient. No upgrade to parity investigation warranted.
- Related: , , 

---

### R-20260509-07 — Q053 Tier-3+ VIX Term Structure Test: DROP; Q053 final closure with 2nd Quant APPROVE

- Topic: PM-authorised narrow Tier-2 signal test before any C3 engineering. Question: does VIX term structure (VIX − VIX3M spread) provide grinding-decline detection materially better than R1 (VIX 30d MA ≥ 22 + VIX 60d max < 35)?
- Findings:
  - **Verdict: DROP term-structure signal family.** 8/8 candidate signals tested (TS1–TS4 spread thresholds; TS6/TS7 R1+spread combined; TS8 5d-smoothed spread). None achieved ≥3/4 criteria vs R1 baseline.
  - **Best contender (TS6: R1 AND spread ≤ 0)**: scored 2/4. Marginal improvements only — FP 7.6% vs R1's 9.4%, avg flagged PnL $+2,228 vs $+2,443 ($215/trade better). 2022 loser coverage unchanged at 50%.
  - **Structural reason (decisive)**: per-window spread distribution shows 2022 grinding-bear had **elevated VIX (median 25.5) but NORMAL contango** (mean spread -1.93, more negative than baseline -1.69; %spread>0 only 6.0% vs baseline 9.9%).
  - **Mechanism**: VIX/VIX3M spread captures **acute spike / short-end panic** (e.g. 2011-Q3 with %spread>0=40%, 2018-Q1 with 27%, 2018-Q4 with 49%). It does NOT capture chronic grinding because grinding lifts the entire vol curve in unison — fear is priced into the medium-term, no short-end urgency anomaly emerges.
  - **Implication**: any further VIX curve variant (VIX9D/VIX, VIX9D/VIX3M, multi-point slope) is expected to share the same limitation, since they all reflect short-end-vs-longer-end urgency rather than chronic curve elevation. Not worth testing further within the same signal family.
- Risks / Counterarguments:
  - Single 2022 grinding-bear sample. Future grinding regimes might differ. Current data shows no signal.
  - Untested adjacent VIX variants (VIX9D/VIX, VIX9D/VIX3M, VIX3M/VIX6M) — but mechanism overlap suggests low ROI.
  - TS6's marginal FP improvement (1.8pp) is real but insufficient to make R1 cost-benefit positive.
- Confidence: high. Failure is structural (mechanism mismatch), not parametric. Two independent angles confirm: (a) 8/8 candidate scoring, (b) per-window spread distribution showing 2022 = normal contango.
- Next Tests: NONE within this signal family. Future Tier-4 candidates (cross-asset stress: HY credit spread, rates curve, DXY+SPX, realized vs implied vol, VVIX, breadth/sector rotation) are recorded for potential future investigation but **NOT actively pursued**. They would address grinding-decline through macro risk-off mechanism rather than VIX curve shape — different mechanism, theoretically more promising for 2022-style scenarios, but require Tier-4 effort (1-2 weeks, new data sources, overfit controls).
- Recommendation:
  - **Q053 final closure confirmed**. C3 (regime-conditional strategy filter) remains standing architectural candidate only — does not proceed to DRAFT or engineering.
  - Do NOT implement R1 or TS-based C3 with current cost-benefit profile.
  - Cross-asset signal family (Tier-4) should be considered ONLY if (a) standing C3 revisit trigger from R-20260509-06 fires, OR (b) PM explicitly prioritises grinding-decline mitigation over current research lanes.
- 2nd Quant verdict (final): **APPROVE — Q053 Tier-3+ confirms no narrow signal path remains.** "VIX term structure has been adequately tested and fails as a C3 signal family. The failure is structural: 2022-style grinding decline lifts the vol curve in contango rather than creating persistent short-end backwardation. R1 remains cost-benefit negative, and TS refinements do not materially improve it. Therefore C3 should not proceed to DRAFT or engineering."
- Related: `Q053`, `R-20260509-06` (2nd Quant adjustments), `R-20260509-05` (C2 reversal), `R-20260509-04` (Tier 3 baseline)
- See: `research/q053/tier3plus_term_structure.py`

---

### R-20260509-06 — 2nd Quant review verdict: APPROVE WITH ADJUSTMENTS; three adjustments applied

- Topic: 2nd Quant reviewed the full Q053 chain (R-20260509-02 through R-20260509-05) per `task/q053_full_session_2nd_quant_review_packet_2026-05-09.md`. Verdict: **APPROVE WITH ADJUSTMENTS**. All Q1-Q7 PASS individually; three adjustments required before final closure.
- Findings (per-question PASS/REVISE/REJECT):
  - **Q1 (5 principles)**: PASS with wording discipline. Principle 1 should clarify "lagging price/trend exits are unreliable as PRIMARY risk controls for IV-driven losses" rather than implying all technical signals are useless. Principle 3 should explicitly bind to "spread-based strategies; for spread-based, stop should attach to risk budget / max loss, not credit multiples."
  - **Q2 (7 actions)**: PASS. Decomposition correct. Minor improvement: REVIEW_TEMPLATE §6.1 should say "when applicable" to allow exemption for fully-automated EOD-only paths.
  - **Q3 (Tier 1+2 sample size)**: PASS with confidence caveat. 2022 finding is "evidence of vulnerability", NOT "statistical proof of universal regime rule". Pattern (3/3 grinding lose, 2/2 spike-recover win) is directionally reliable, statistically still weak — supports research conclusion, does NOT support direct production C3 rule.
  - **Q4 (Tier 3 signal verdict)**: PASS, but **do not over-close the signal universe**. Conclusion is "current tested VIX/SPX-drawdown signal family fails cost-benefit"; we did NOT test cross-asset signals (credit spreads, rates curve, sector breadth, liquidity stress, realized-vol term structure, cross-asset risk-off). The boundary matters.
  - **Q5 (C2 reversal)**: PASS. Reproduction methodology sound. "No engine bug, normal BPS regime loss" is correct.
  - **Q6 (pnl_pct fix)**: PASS with lightweight audit requested (now done — see this entry).
  - **Q7 (Q053 closure)**: PASS with adjusted revisit trigger. Original "another 2022-style year OR PM prioritization" too lax/too late.
- **Adjustments applied (this entry)**:
  - **Adjustment 1 — `entry_credit` consumer audit (Q6 follow-up)**:
    Audit results embedded in `backtest/engine.py:96-130` Trade dataclass docstring.
    - Math consumers (3) — all CORRECT use of signed per-share index points: `scripts/export_backtest_trade_detail.py:214` (price calc), `scripts/export_backtest_trade_detail.py:294` (`net_option_px_enter` field), `backtest/prototype/SPEC-030_intraday_stop.py:116, 164`.
    - Display consumers (2) — emit raw value with key "entry_credit" in JSON: `web/server.py:1548` (API), `backtest/research_views.py:43` (research view). External readers (frontend, downstream tools) may misinterpret as dollar-credit. **Future cleanup task**: rename JSON key OR add parallel dollar-credit field. Not Fast Path — needs coordinated frontend update.
  - **Adjustment 2 — Revised C3 revisit trigger (Q7 follow-up)**: replace prior single-condition trigger with four conditions, ANY of which reopens C3:
    1. PM explicitly prioritizes regime-conditional strategy filter
    2. Another 2022-style calendar-year loss emerges
    3. Rolling 3-month put-side strategy PnL falls below defined threshold (default: -1.5× per-strategy historical MAD over 3 months) in medium-VIX (VIX 30d MA in 20-30) grinding conditions
    4. Q041 / Q036 deployment increases account-level short-premium / put-side exposure materially (e.g., post-Q041 Tier 1 paper-trading activation, OR post-Q036 Overlay-F shadow→active transition)
    Trigger 3 is the standing automated check that must be applied monthly by Planner; trigger 4 is event-driven on spec progression. Triggers 1-2 are PM-driven.
  - **Adjustment 3 — Tier 3 conclusion wording boundary (Q4 follow-up)**: amend the Tier 3 verdict in R-20260509-04 to read:
    > "The tested VIX-persistence + SPX-drawdown signal family failed cost-benefit. We did NOT evaluate cross-asset signals (credit spreads, rates curve, sector breadth, liquidity stress, realized-vol term structure, cross-asset risk-off). Future C3 reopening should consider these untested families before concluding 'no signal exists'."
    Wording correction is documented here; the original R-20260509-04 entry remains as historical record (not retroactively edited).
- Risks / Counterarguments:
  - The display-consumer JSON key issue (audit finding) is a real semantic risk for any external code reading `entry_credit` from API. Documented but not yet fixed; downstream consumers may continue mis-interpreting.
  - Revised C3 trigger 3 (rolling 3-month threshold) requires Planner to define "MAD threshold" precisely; current parameter is approximate.
- Confidence: high on all adjustments. 2nd Quant review was thorough.
- Recommendation:
  - Q053 line now formally CLOSED with these three adjustments applied.
  - Carry forward as standing reference: 5 principles, 3 calibrations, A1 tool, REVIEW_TEMPLATE §6.1 checks, revised C3 trigger.
  - Planner should add monthly check for revised C3 Trigger 3 (rolling 3-month put-side PnL vs threshold) to PROJECT_STATUS update workflow.
- Related: `R-20260509-05`, `R-20260509-04`, `R-20260509-03`, `R-20260509-02`
- See: `task/q053_full_session_2nd_quant_review_packet_2026-05-09.md`, `backtest/engine.py:96-130`

---

### R-20260509-05 — C2 investigation reverses prior hypothesis: 2022 weakness is genuinely regime-driven; Trade.pnl_pct unit bug fixed

- Topic: PM authorised C2 to investigate the apparent zero-credit BPS trade (2022-04-04, displayed entry_credit -$34, contracts 6.89, exit PnL -$24,606, pnl_pct -72,058%) suspected of being an engine sizing edge case. Investigation found NO engine bug. The "anomaly" was a display artifact from misleading `Trade.entry_credit` field semantics + a unit bug in the `Trade.pnl_pct` property.
- Findings:
  - **The 2022-04-04 BPS was NOT anomalous.** Reproduction at entry conditions (SPX 4583, VIX 18.6, NORMAL regime, BPS Δ0.30/Δ0.15 DTE 30) shows:
    - Real per-share credit: $34.48 (positive)
    - Real per-contract credit: $3,448
    - Total credit collected (6.89 contracts): **$23,757**
    - Per-contract max loss: $11,052
    - Total max-loss exposure: $76,148 (sized to ~15% bp_target × $500k = $75k)
    - Risk/reward: 31.2% credit / max_loss — completely normal BPS proportions
    - Actual loss $24,606 = **32% of max loss** — within normal BPS distribution after a 9-day SPX -4.2% move
  - **Two display/semantic bugs identified (both fixable as Fast Path):**
    - **Bug A (semantic mismatch)**: `Trade.entry_credit` field comment said "positive = credit received, negative = debit paid" but field actually stores `position.entry_value` directly, which is per-share signed index points (negative = credit for spreads). Comment was misleading; actual storage is correct for engine math but confusing for any consumer reading the field.
    - **Bug B (unit bug in `pnl_pct`)**: `Trade.pnl_pct = exit_pnl / abs(entry_credit) × 100` divides total dollars (exit_pnl) by per-share signed index points, producing meaningless multi-thousand-percent values (-72,058% for our trade). The correct denominator should be `abs(entry_credit) × 100 × contracts` to match dollar units across numerator and denominator.
  - **Fix applied (Fast Path)**: `backtest/engine.py:96-117`
    - Field comment rewritten to accurately describe what's stored (per-share signed index points; "positive = credit" assumption explicitly removed)
    - `pnl_pct` property fixed to use `abs(entry_credit) * 100 * contracts` as the position-level dollar denominator
    - 270/270 tests pass after fix
    - 2022-04-04 trade now shows pnl_pct = -104.6% (lost ~1.04× credit collected; sensible BPS loss); all 282 trades fall within -211% to +95% pnl_pct range (no more extreme values)
    - Did NOT change the stored value of `entry_credit` to avoid breaking 5+ downstream consumers (web API, export script, intraday-stop prototype, tieout column reference)
- Risks / Counterarguments:
  - The 2022 grinding-decline weakness is now confirmed as **genuine regime-driven** rather than engine artifact. This means there is no narrow point-fix available; only architectural intervention (regime-conditional strategy filter, "C3" path) could improve it.
  - The display bug fix doesn't change any historical PnL or trade flow — it only fixes how `pnl_pct` is computed when displayed. The stored `entry_credit` field remains in per-share signed index-point units for backward compatibility with downstream consumers.
- Confidence: high. Reproduction matches exactly; full test regression PASS.
- Implications for Q053 absorption decisions:
  - **C1 (accept) is now the rational choice** for the 2022-style grinding-decline weakness. No narrow engine fix exists. The pattern is structural to short-premium strategies in mid-VIX persistent decline regimes.
  - **C3 (regime-conditional strategy filter) remains the only intervention path** if PM wants to actively address grinding-decline weakness. It is bigger work (Tier 4 research + architecture spec, ~2 weeks), and Tier 2/3 evidence already shows simple signals fail cost-benefit.
  - **R-20260509-04 Direction-B verdict (Tier 3 best score 9/15) stands**: no candidate signal cleanly separates grinding-decline from baseline at the entry-filter level. Strategy-level filtering (suppress put-side in 2022) would have saved $31k but requires C3-level architectural change.
- Next Tests: none for this lane. Q053 closes without an actionable engine fix.
- Recommendation:
  - Q053 / Q052 / Q012 line **fully closed**. Document the negative result thoroughly so future research doesn't re-investigate.
  - Keep `iv_expansion_stress_test` tool and `Short-Premium Risk Management Principles` (R-20260509-02) as the durable governance outputs.
  - C3 (regime-conditional strategy filter) remains a **standing research candidate** but not actively pursued. Trigger to revisit: another 2022-style year occurs, OR PM explicitly prioritizes grinding-decline mitigation over current research lanes.
  - The Trade.pnl_pct fix means future research/dashboards reading `pnl_pct` get sensible numbers. Front-end dashboards or research views that previously showed the broken values may now display differently — Planner should note this as a documentation update for any downstream artifact consumer.
- Related: `Q053`, `R-20260509-04` (parent C2 hypothesis), `R-20260509-03` (Tier 1 finding), `R-20260509-02` (`/ES` absorption that started this chain)
- See: `backtest/engine.py:88-130` (Trade dataclass + fixed pnl_pct), `research/q053/tier3_signal_refinement.py` (signal evaluation that fed C2 hypothesis)

---

### R-20260509-04 — Q053 Tier 2: pattern refined; PM selects Direction B; Tier 3 opened

### R-20260509-04 — Q053 Tier 2: pattern redefined as "no-spike grind"; simple signals insufficient; PM selects Tier 3 refinement (Option B)

- Topic: Q053 Tier 2 — extended grinding-decline analysis to 2011-Q3, 2015-2016, 2018-Q1 windows + designed and back-tested candidate detection signals. Goal: determine whether main strategy's 2022 weakness is a systemic pattern and whether a usable entry-gate signal can be designed.
- Findings (pattern):
  - **Pattern correction**: the real failure mode is not "stress = loss" but **"persistent high VIX without spike = loss"**. Main strategy performs *excellently* in spike-then-recover environments (2011-Q3 Eurozone: +$97k, 100% WR; 2018-Q1 Volmageddon: +$88k, 100% WR) — `EXTREME_VOL` gate + HIGH_VOL strategies work as designed. Losses are confined to **pure grinding windows** (VIX stuck 20-30 for months, never reaching 35+).
  - Window classification (5 test windows):

    | Window | VIX behavior | Result |
    |---|---|---|
    | 2011-Q3 Eurozone | spike to 48, rapid recovery | ✓ +$97k, 100% WR |
    | 2018-Q1 Volmageddon | spike to 50+, rapid recovery | ✓ +$88k, 100% WR |
    | 2015-2016 China/oil | persistent 20-30, no spike | ⚠️ −$1k |
    | 2018-Q4 selloff | persistent 20-30, no spike | ⚠️ avg −62% per trade |
    | 2022 grinding bear | persistent 20-30 all year, no spike | ⚠️ −$26.8k |

  - Confirmed: **3/3 true grinding windows** (no spike to 35+) produce losses; **2/2 spike-recover windows** produce large profits.

- Findings (signal design):
  - Four candidate signals tested:

    | Signal | True-grinding coverage | FP rate | Selectivity (avg PnL flagged) |
    |---|---|---|---|
    | S1: VIX 30d MA ≥ 22 | 57.5% | 25.0% | −$1,850/trade |
    | R1: S1 + max(VIX, 60d) < 35 | 38.8% | 9.0% | −$3,996/trade |
    | R3: VIX ≥ 20 + no spike + SPX 60d ≤ −3% | 11.3% | 2.3% | −$4,763/trade |
    | R4: R3 + SPX 60d ≤ 0 | 7.4% | 3.5% | −$6,483/trade |

  - **R1 is the practical sweet spot**: FP rate 9% (limits ~1/11 good trading days) + −$4k/trade selectivity. S1 too blunt; R3/R4 too selective.
  - **Critical limitation**: R4 (strongest selectivity) back-tested against 2022 and flags only 1 of 18 trades — and that trade *made money* (+$5,050). The 17 losing trades (−$31,827) are all unflagged. R4 is detecting a different stress type, not 2022. **No simple signal can cleanly isolate the 2022 pattern.**
  - The 2022 failure mode requires detecting "VIX has no recovery" — a more complex temporal condition than any single-day or rolling-average filter.

- Risks / Counterarguments:
  - Sample of grinding-decline windows is small (3 windows, 40 trades total). Any signal tuned on this sample risks in-sample overfitting.
  - The spike-recover windows are also few (2 windows). Classification robustness depends on whether future stress environments follow the same bimodal pattern.
  - Option A (soft overlay with R1) would reduce 2022 losses mechanically but might also clip good years with elevated VIX without grinding dynamics.

- Confidence: high on the **pattern** (spike vs. grind distinction is clean across 5 windows); medium on **signal design** (R1 is best available but still insufficient for a hard gate).
- Recommendation (PM selected B):
  - **Option A** (R1 soft overlay, immediate candidate spec) — viable but accepts known imprecision.
  - **Option B** (Tier 3 signal refinement) — design signals that detect "no recovery" component: e.g., `VIX 30d MA ≥ 22 AND VIX 30d min ≥ 18` (no return to normal); or `SPX 200d MA flat/declining + persistent VIX`. Estimated 1-2 weeks. Likely produces cleaner detector that actually catches 2022.
  - **Option C** (accept status quo) — main strategy absorbs one −$26k loss year per ~5-7 years; +$1.7M total over 19 years, structurally tolerable.
  - **PM chose Option B**. Tier 3 opened.
- Next Tests (Tier 3 scope):
  - Design `VIX 30d min ≥ 18` and `SPX 200d MA slope ≤ 0` as additional signal components
  - Test composite signal on all 5 grinding-decline windows; target: FP rate ≤ 5%, 2022 trade coverage ≥ 50%
  - If composite signal achieves target: promote to Option-A-style candidate spec (soft overlay). If not: document which approach is closest and return to PM for C decision.
- Related: `Q053`, `Q036`, `SPEC-088`, `R-20260509-03`, `R-20260509-02`
- See: `sync/open_questions.md Q053`

---

### R-20260509-03 — Action A1/A2/A3 executed: stress test tool built, Q041 appendix attached, Q053 Tier 1 finds main strategy hidden weakness in 2022 grinding bear

- Topic: PM authorised execution of all three active actions from R-20260509-02 (`/ES` research absorption). All three completed. Most consequential outcome: Q053 Tier 1 confirms main strategy has the same hidden weakness `/ES` research predicted — grinding-decline windows produce negative PnL even though no stop_loss fires.
- **Action A1 — `iv_expansion_stress_test` tool DONE**:
  - Path: `research/tools/iv_expansion_stress_test.py`
  - v0.1 supports: naked_put / CSP, bull_put_spread (BPS), iron_condor (IC)
  - Self-validation: reproduces Phase A `/ES` SPAN expansion within tolerances (entry $20,529 ✓; VIX 39 mult 3.35× in expected 3.0–4.0 range ✓; VIX 59 mult 5.63× in expected 4.5–6.5 range ✓)
  - VIX shock grid: +10 / +20 / +40 with correlated underlying drop (-1% per +3 VIX pts, Phase A calibration)
  - Output per shock: mark_loss, stress_bp, pnl_ratio, survival classification
  - Out of v0.1 scope: BCD diagonal, calendar/ratio spreads (deferred to v0.2)
- **Action A3 — Q041 IV-expansion stress appendix DONE**:
  - Path: `doc/q041_execution_prep_packet_2026-05-05.md` §11 (appended)
  - Generation script: `research/q012/a3_q041_stress_matrix.py`
  - Tier 1 SPX CSP Δ0.20 DTE30 worst-case (+40 VIX shock from 19): mark loss $61,585 (12.3% NLV), stress BP 27.2% NLV — within tolerance for Q041 1-contract scope
  - Tier 2 GOOGL/AMZN CSP worst-case: mark loss < 1% NLV (small absolute size due to single-name BP), but pnl_ratio FAIL on reference threshold — consistent with existing Q041 §3.3 tail caveat
  - Appendix adds new paper-trading data-collection requirement: each cycle must record max observed mark loss + max observed BP for model calibration
  - Does NOT modify Q041 paper-trading scope; only adds risk-visibility dimension
- **Action A2 — Q053 Grinding Decline Regime Review Tier 1 DONE**:
  - Path: `research/q053/grinding_decline_review.py`
  - Method: Full main strategy backtest 2007-01-01 → today (282 trades), sliced into 2018-Q4 + 2022 + Other (baseline)
  - **Finding (decisive)**: Main strategy DOES exhibit grinding-decline weakness, especially severe in 2022:
    - **2022 full year**: 18 trades, total PnL **-$26,778** (negative year), WR **55.6%** (vs baseline 76.9%, **-21.4pp**), avg PnL **-$1,488** (vs baseline +$6,546, **-123% deviation**)
    - **2018-Q4**: 4 trades (small sample), avg PnL +$2,518 (vs baseline +$6,546, -61% deviation), still positive total
    - **Stop rate in both windows: 0.0%** — confirming /ES insight that grinding decline does NOT trigger pnl_ratio-based stops
    - 2022 losses concentrated in BPS (-$12.5k), IC_HV (-$11.5k), BPS_HV (-$7.4k)
  - **Tier 2 expansion now justified**: 2011 Eurozone, 2015-Q3 / 2016-Q1, 2018-Q1 mini-stress windows should be tested to confirm pattern consistency
  - **No spec recommendation yet**: Tier 1 establishes the problem exists; root-cause and remedy research belongs to Tier 2
- Risks / Counterarguments:
  - Q053 Tier 1 sample sizes are small (4 trades 2018-Q4, 18 trades 2022). 2022 evidence is robust because the deviation magnitude is large (-21pp WR), but 2018-Q4 alone could be statistical noise.
  - 2022 result may be partly driven by specific strategy mix at that time (heavy IC_HV, BPS_HV) rather than a true regime-detection failure — Tier 2 should test if mid-VIX years like 2015 show the same pattern even with different strategy mixes.
  - The stress test tool (A1) uses simplified SPX/VIX correlation; production calibration may differ.
- Confidence: high on Q053 directional finding (2022 is a clear weakness); medium on whether Tier 2 will show systematic pattern; high on A1 tool correctness.
- Next Tests:
  - Q053 Tier 2: extend windows to 2011-Q3 (Eurozone), 2015-Q3-2016-Q1 (China devaluation), 2018-Q1 (vol-mageddon prelude). Test if grinding-decline pattern is consistent across regimes or specific to 2022.
  - If Tier 2 confirms pattern: design candidate detection signal (e.g., VIX rolling-mean threshold, persistent SPX drawdown without spike). Result becomes basis for potential new SPEC.
  - A1 v0.2: add BCD diagonal support after first short-premium spec actually uses A1 in review.
- Recommendation:
  - Q053 Tier 1 closed PASS; Tier 2 should be queued behind Q041 paper-trading work but ahead of new alpha research
  - All A1/A2/A3 deliverables should remain stable references; A1 tool is now mandatory for short-premium spec reviews per `REVIEW_TEMPLATE.md` §6.1
  - **Important framing for Q053**: this is NOT a Q041 problem (Q041's CSPs are NOT the strategies that lost in 2022; main strategy's BPS/IC/BCD are). Do not conflate Q053 findings with Q041 governance. Q041 has its own IV-expansion appendix from A3.
- Related: `Q012`, `Q041`, `Q051`, `Q052`, `Q053` (Tier 1 PASS), `R-20260509-02`
- See: `research/tools/iv_expansion_stress_test.py`, `research/q012/a3_q041_stress_matrix.py`, `research/q053/grinding_decline_review.py`, `doc/q041_execution_prep_packet_2026-05-05.md` §11

---

### R-20260509-02 — `/ES` research absorption into main strategy governance: 5 must-absorb principles + 3 calibrated cautions + 3 action items (Q053 opened)

- Topic: 2nd Quant reviewed Quant's "/ES research → main strategy" knowledge absorption summary. Verdict: PASS with priority reordering and three calibration cautions. The most important spillover from /ES is not any single parameter but a system-level risk-management principle: **IV expansion / margin expansion fires faster than any lagging control, so risk management must be entry-gated and stress-capital-aware, not exit-driven.**
- Findings (must-absorb, ordered by 2nd Quant priority):
  1. **IV expansion 领先于 lagging signals** — `/ES` data confirmed that any technical/trend-based exit fires AFTER IV has already repriced the option against the position. This validates main strategy's existing entry-gated philosophy (`risk_score`, regime gating, EXTREME_VOL refusal). Future spec proposals to add holding-period technical exits to short-premium positions can be rejected by direct reference to this evidence.
  2. **Main strategy should continue entry-gated / regime-gated risk control** — not retrofit lagging exits. Codify this as a principle, not just a current implementation detail.
  3. **`pnl_ratio` stop > credit-multiple stop** — main strategy's loss-budget-relative stops are structurally more robust than mark-multiplier stops because they remain scale-invariant across premium regimes. Do not simplify BPS/IC stops into "close at 3x credit" form; that semantic fails in low-premium structures (proven by /ES H3 grid).
  4. **2018 / 2022 grinding decline is the hidden weakness, not 2008 / 2020 spike** — `/ES` research repeatedly showed worst years were grinding mid-VIX environments where EXTREME_VOL gates do not trigger and spike hedges do not pay. Same risk likely exists in main strategy. Now opened as Q053.
  5. **IV expansion stress test must become a standard spec-review tool** — Phase A SPAN model can be generalized into an `iv_expansion_stress_test` framework applied to any new short-premium spec.
- Findings (calibrated cautions, 2nd Quant adjustments):
  6. **Overlay-F scale-dependence is a revisit HYPOTHESIS, not a conclusion**. Q036 Overlay-F's low marginal contribution (+0.074pp) might be because main strategy's BP utilization is structurally too low to amortize hedge cost — but this must be re-tested rather than assumed. Trigger: revisit Q036 economics IF main-strategy BP utilization rises above 25-30% NLV after Q041 deployment. This becomes a standing revisit gate, not an immediate research action.
  7. **Capital efficiency must be evaluated on stress-capital basis, not entry-margin basis**. The /ES vs SPX naked vs SPX BPS comparison should not be read as "which has the lowest entry BP%". The correct comparison is "which has the lowest stress-capital exposure given a tail scenario". Main strategy's spread-based approach wins on this metric, not on entry BP. Apply this lens going forward.
  8. **Execution-drift / delay sensitivity must enter spec-review standards**. Any rule depending on PM manual execution (intraday alerts, EXTREME_VOL manual reduce, hedge activation) must explicitly state and test `T+0 / T+1 / T+2` execution scenarios. /ES taught that bot alert at 3× and actual closure between 3.0–4.0× can change a marginally-significant CI into a clearly-not-significant one.
- Risks / Counterarguments:
  - The "IV expansion is faster than lagging controls" principle is robust but not absolute — fast intraday auto-close mechanisms (not present in main strategy today) could in principle avoid this constraint. The principle should be read as "any human-mediated or daily-bar exit cannot preempt IV expansion", not "no exit logic ever can".
  - The Overlay-F revisit gate (BP utilization 25-30%) is itself a hypothesis based on /ES analogy; the right BP threshold for Overlay-F revisit may differ.
- Confidence: high on the must-absorb principles (1-5); medium on the calibrated cautions (6-8) which are governance hypotheses requiring future validation.
- Action Items (seven; corrected 2026-05-09 — original mapping listed only A1–A3, missing four governance codification actions):
  - **Action A1 — Build `iv_expansion_stress_test` framework** *(Planner-tracked tool; pending first use)*. Generalize Phase A SPAN model. Inputs: strategy type, entry IV/VIX, DTE, strike/delta/spread width, current BP/max-loss. Outputs: VIX +10/+20/+40 shock-projected mark loss, BP/margin expansion, stop proximity, stress survival score. Becomes mandatory for any new short-premium spec review.
  - **Action A2 — Open Q053 "Grinding Decline Regime Review"** *(research question; ✅ OPEN)*. Scope: 2018-Q4, 2022 full year, optionally 2011/2015/2016 mini stress windows. Highest-value research spillover from /ES closure — `See: sync/open_questions.md Q053`
  - **Action A3 — Q041 SPX CSP IV-expansion stress appendix** *(Q041 governance addendum; pending Q041 paper-trading activation)*. Before Tier 1 activation, attach IV-expansion stress appendix to execution-prep packet (2020-style spike, 2022-style grinding decline, IV compression trap, BP under stress). Use A1 tool when built.
  - **Action A4 — Codify 5 Short-Premium Risk Management Principles into `QUANT_RESEARCHER.md`** *(governance codify; ✅ DONE)*. New section "Short-Premium Risk Management Principles" with all 5 principles (IV expansion leads signals; entry-gated is correct; pnl_ratio > credit-multiple; grinding decline is hidden weakness; stress-capital basis) — `See: QUANT_RESEARCHER.md#short-premium-risk-management-principles`
  - **Action A5 — Set Q036 Overlay-F revisit gate trigger** *(monitoring trigger; ✅ DONE)*. Gate condition: main-strategy 60-day time-weighted avg BP utilization ≥ 25% NLV (softer) or ≥ 30% NLV (harder trigger). Planner monitors monthly; revisit is a hypothesis, not a conclusion — `See: sync/open_questions.md Q036 §Overlay-F revisit gate`
  - **Action A6 — Add stress-capital basis evaluation to `REVIEW_TEMPLATE.md` §6.1** *(process; ✅ DONE)*. Mandatory checklist: entry BP, VIX +10/+20/+40 stress BP, stress BP/NLV ratio, no entry-BP-only capital efficiency arguments — `See: REVIEW_TEMPLATE.md §6.1`
  - **Action A7 — Add T+0/T+1/T+2 execution-drift sensitivity to `REVIEW_TEMPLATE.md` §6.1** *(process; ✅ DONE)*. Mandatory for any rule depending on PM manual execution: state execution assumption, provide T+0/T+1/T+2 sensitivity test, flag if T+0 significant but T+1/T+2 not — `See: REVIEW_TEMPLATE.md §6.1`
- Recommendation:
  - A4–A7 were the missing governance codification actions. Principles not written into formal documents are not institutionally durable. Now fixed.
  - Q053 (A2) is Tier 1 research — queue behind Q041 paper-trading, ahead of any new alpha-search lanes.
  - A1 tool development is engineering-driven; discuss spec when Quant is ready to use it (likely alongside first Q053 deliverable).
  - A3 is added to Q041's existing execution-prep workflow; not a separate spec.
- Related: `Q012`, `Q036`, `Q041`, `Q050`, `Q051`, `Q052`, `Q053` (NEW), `SPEC-061`, `SPEC-086`, `SPEC-088`
- See: `research/q012/phase_a_span_model.py` (template for A1), `research/q012/h1_technical_exit.py` (evidence for principle 1), `research/q012/h3_delta_dte_grid.py` (evidence for principle 3)

---

### R-20260509-01 — Q052 CLOSED: PM's three salvage hypotheses (technical exit, roll-out, deep OTM) all fail structurally; `/ES` thesis comprehensively closed at $500k scale

- Topic: PM-proposed alternative redesigns for the `/ES` line after Q051 closed the original thesis as scale-dependent. Three new hypotheses tested:
  - H1: technical-analysis-driven exit replaces or augments credit stop
  - H2: roll-down + roll-out instead of stop-out (deferred to evidence from H1)
  - H3: deep OTM strikes (Δ≤0.05) + longer DTE (90/180 days)
- Findings:
  - **H3 grid (Δ × DTE) failed comprehensively**. All 9 configurations produced negative AnnROE; bootstrap CIs ranged from `[-466, +57]` (best, Δ=0.20 DTE=45) to `[-2444, -906]` (worst, Δ=0.20 DTE=180). Stop rate INCREASED with deeper OTM and longer DTE: Δ=0.05 DTE=180 had 48.9% stop rate vs 26.5% baseline. Win rate DROPPED at extremes: Δ=0.05 DTE=180 → 51.1% WR vs 72.6% baseline.
  - **H3 root cause**: 3x credit stop has wrong semantics for low-premium puts. A $1 entry premium reaching $3 mark only requires $2 absolute move, which is easily triggered by deep OTM puts' high gamma. Long DTE makes positions more sensitive to vol expansion. The stop methodology cannot translate across strike depths.
  - **H1 grid (3 exit modes × 4 base configs) failed comprehensively**. Trend-based exits universally underperformed credit stops. At Δ=0.20 DTE=45, switching from credit stop to trend exit changed AnnROE from -0.13% to -0.45%.
  - **H1 root cause via diagnostic**: 244 trend exits at baseline config showed 84% (204 trades) closed at a loss, with median loser -$707 and P90 worst -$3,307. The ATR-normalized trend signal that fires "BULLISH → non-BULLISH" is a LAGGING signal — it triggers AFTER IV has expanded against the position. By the time technical signal fires, the position has already taken IV expansion damage. There is no lagging technical signal that fires before the IV move that hurts a short put.
  - **H2 (roll-out) deferred but reasoned to fail**: rolling is an extension of H1 logic — it requires a trigger (typically a technical signal indicating trouble), and any such trigger fires after IV expansion. Rolling defers but does not eliminate loss; in continued multi-day declines (2008/2020/2022), each roll captures more credit but extends adverse exposure, eventually requiring capitulation at larger size.
  - **Structural conclusion**: Naked short puts at small scale ($500k account) are dominated by IV-expansion-driven loss variance. No exit methodology — credit-based, technical-based, or rolling — can preempt this because IV expansion is itself the market's reaction to the type of move that hurts the position. The position takes the hit before any signal can fire to avoid it.
- Risks / Counterarguments:
  - We tested only ATR-normalized trend filter. Other technical signals (RSI, longer MA crossovers, VIX-spike triggers) might behave differently. However, the structural argument applies broadly: any lagging signal will fire after the move it tries to detect.
  - Different rolling strategies (e.g., roll only on profit, roll on time decay) might have different properties; not all roll variants tested.
- Confidence: high. Five rounds of research (R-20260508-09 through R-20260509-01) have systematically eliminated all reasonable variations. The thesis is structurally closed at this scale.
- Next Tests: none. /ES naked put research line CLOSED.
- Recommendation:
  - **Q012, Q051, Q052 all CLOSED.** No further /ES naked put research at $500k account scale.
  - **Maintain SPEC-061/086/088** as a 1-contract live data collection cell. This continues to provide value for: fill/slippage observation, SPAN visibility calibration (SPEC-088), operational learning. Cost is minimal.
  - **Redirect all `/ES` research/spec capacity to `Q041`** (primary BP deployment efficiency axis per Q046).
  - **Future revisit trigger**: if account NLV grows to ~$1.5M+, the original Phase 4 + BSH dynamic leverage thesis (R-20260508-12, statistically significant) becomes production-viable because peak SPAN concentration drops from 36-45% NLV to 12-15% NLV. SPEC-088 visibility data accumulated until then will help calibrate the leverage table to current SPX/SPAN reality.
  - **Document the negative results** so future researchers don't waste time re-testing these dead branches.
- **Closure framing (2nd Quant confirmed)**: This closure is **account-size conditional, not an absolute denial of /ES put-selling economics**. The thesis is rejected for the current $500k account and 1-contract production sizing, but may be revisited as a full dynamic-leverage + BSH system when account NLV reaches $1.5M+. Do not interpret this entry as "/ES naked puts永远不能做"; interpret it as "current account scale is structurally insufficient for this payoff family."
- **Hard revisit gate (do not reopen between $500k–$1.5M)**:
  - account NLV ≥ $1.5M, preferably $2M
  - SPEC-088 has accumulated meaningful live SPAN observations across at least one stress event
  - PM is willing to evaluate dynamic leverage table + BSH as **one inseparable system** (not as separate components)
- **Most valuable structural insight from this research line**:
  > IV expansion reprices tail risk faster than any lagging control system can respond.
  This invalidates not just the current /ES variants, but applies broadly to **any naked-short-option strategy at small scale that relies on lagging price-based or trend-based exits**. Future researchers proposing new naked short option lines (e.g., XSP, futures options on other indices) should explicitly address this constraint before opening a research lane.
- Related: `Q012`, `Q013`, `Q050`, `Q051`, `Q052`, `Q041`, `Q046`, `SPEC-061`, `SPEC-086`, `SPEC-088`
- See: `research/q012/h3_delta_dte_grid.py`, `research/q012/h1_technical_exit.py`

---

### R-20260508-14 — Q052 opened: future `/ES` redesign branch after closure of the original thesis line

- Topic: PM opened a new `/ES` redesign branch after `Q012/Q051` were formally closed at the current `$500k` account scale.
- Findings:
  - The original `/ES` thesis line is now closed for current-scale production ambition. The thesis is statistically valid only in its larger full-system form and is not production-plausible at the current account size.
  - PM nevertheless identified three fresh future directions that are materially different from the original thesis and should be preserved as a separate branch rather than folded back into the closed line:
    1. technical-risk-off exits instead of passive `3x / 4x credit` waiting
    2. roll-down / roll-out management after those technical exits
    3. very-far-OTM long-dated short puts as a different structural design
  - Planner interpretation: this is a **new hypothesis family**, not a parameter tweak on the old thesis. It therefore deserves its own identifier (`Q052`) and should not keep `Q012/Q051` artificially open.
- Risks / Counterarguments:
  - None of the three directions has yet been validated; this is only a seed memo, not a near-spec finding.
  - The branch should remain low priority behind `Q041` and current active implementation / runtime work.
- Confidence: high on the branching decision; low on any one redesign direction until researched.
- Next Tests:
  - none by default
  - if PM later promotes `/ES` redesign back into the active queue, Quant should choose one of the three directions as the first narrow research unit rather than mixing all three at once
- Recommendation:
  - Keep `Q052` open as a low-priority future research seed
  - Keep `Q012/Q051` closed
  - Keep active ROE-expansion focus on `Q041`
- Related: `Q012`, `Q013`, `Q041`, `Q050`, `Q051`, `Q052`, `SPEC-061`, `SPEC-086`, `SPEC-088`

---

### R-20260508-13 — Q051 CLOSED: leverage-table recalibration FAILED; `/ES` thesis is scale-dependent, not production-viable at $500k account

- Topic: Final outcome of the leverage-table recalibration study triggered by R-20260508-12. PM authorised the larger research path; this entry closes the question definitively.
- Findings:
  - **The thesis is statistically validated but scale-dependent**. The original Phase 4 + BSH (STOP=3.5) significance came from peak position sizes (22.4 contracts on 2008-12-31 at SPX 903, VIX 40) corresponding to **peak /ES SPAN ≈ $179k = 36–45% NLV** at $500k account size. This is the level required to make the thesis statistically work.
  - **All conservative recalibrations (V1–V6) failed bootstrap significance**:
    - V1 static 20% NLV SPAN cap → AnnROE -0.49%, CI [-464, +389] ❌
    - V2 tiered 12-30% → AnnROE +0.61%, CI [-152, +400] ❌
    - V4 very-conservative 6-15% → AnnROE +0.06%, CI [-45, +206] ❌
    - V5 moderate 8-22% → AnnROE +0.41%, CI [-55, +291] ❌
    - V6 V5 + $100k absolute cap → AnnROE +0.40%, CI [-56, +291] ❌
  - **Root cause diagnosis**: The original thesis's significance was tied to the SPX OCC PM sizing model, which produced larger position sizes in low-SPX historical periods relative to the current /ES SPAN model (Phase A). When sizing is constrained to production-realistic SPAN budgets (≤ 35% NLV), the resulting per-trade contract counts are insufficient to overcome BSH cost drag and stop-loss variance. The thesis's alpha is not "VIX leverage scaling" per se, but rather "OCC-PM-permissive sizing in low-SPX historical regimes" — a regime that does not translate to current $500k production reality.
  - **The thesis IS production-viable at larger scale**. The same absolute peak SPAN ($179k) becomes:
    - 36% NLV at $500k (current) → unacceptable
    - 18% NLV at $1M → borderline
    - 9% NLV at $2M → fully viable
  - **No further recalibration variant is likely to recover significance** without violating the SPAN concentration cap. The structural mismatch between OCC-PM-derived alpha and SPAN-realistic sizing is fundamental, not parametric.
- Risks / Counterarguments:
  - Research still uses SPX proxy infrastructure rather than true /ES historical options data; the SPAN model is calibrated to a single observed Schwab data point ($20,529 at VIX 19, SPX 5400) and may differ in extreme regimes.
  - The "scale-dependent" conclusion assumes Schwab PM SPAN behaviour; broker-specific differences could shift the threshold account size.
  - The thesis statistical validity is from a 26-year window dominated by historical low-SPX data; modern SPX-only validation would be a separate study.
- Confidence: high on the structural conclusion (no recalibration recovers significance under reasonable SPAN caps); high on the scale-dependence framing.
- Next Tests: none. This research line is closed.
- Recommendation:
  - **Q012/Q051 closed.** No further research investment in `/ES` thesis at current account size.
  - **Maintain 1-contract observation cell** (SPEC-061/086/088 already deployed). This is the correct posture: low cost, generates real-fill data, calibrates SPAN visibility, and remains in place if account scales to $1.5–2M+ later.
  - **Do not pursue Option B** (accept high peak SPAN at $500k). Margin call risk in 2008/2020-style events is unacceptable for the modest expected ROE benefit.
  - **Q041 remains the primary BP deployment efficiency axis** (Q046 mechanism ranking confirmed). All `/ES` research/spec resources should redirect there.
  - If account grows to $1.5–2M+ in the future, this research can be revisited; the SPEC-088 visibility surface will provide data to recalibrate parameters at that point.
- Related: `Q012`, `Q013`, `Q050`, `Q051`, `Q041`, `Q046`, `SPEC-061`, `SPEC-086`, `SPEC-088`
- See: `research/q012/full_thesis_rerun.py`, `research/q012/leverage_recalibration.py`

---

### R-20260508-12 — Q051 full-thesis rerun PASS: thesis validated in full-system form; leverage-table recalibration is the next blocker

- Topic: final `/ES` full-thesis rerun after PM selected the larger research path rather than keeping the line at the 1-contract live-data-cell posture.
- Findings:
  - The thesis now **does validate statistically in full-system form**. Under the full dynamic system (`P4 + BSH`), bootstrap CI is positive-significant at:
    - `STOP = 3.5x` → `[+31, +460]`
    - `STOP = 4.0x` → `[+80, +515]`
  - `STOP = 3.0x` remains borderline (`[-12, +404]`), which supports the idea that the full thesis is real but its economic robustness is sensitive near the tighter production stop.
  - BSH economics are reversed relative to the `1`-contract path. At larger dynamic scale, BSH annual drag is only about `19%` of theta income and becomes economically sustainable. This confirms the earlier structural conclusion: BSH is not universally good or bad; it is **scale-dependent**.
  - The line's bottleneck is no longer “is there any thesis left?” The new blocker is **production plausibility of the old leverage table**. Under current SPX / SPAN levels, the old table can imply `19–22` contracts, which is far too much concentrated SPAN exposure for a `$500k` account.
  - Worst-year risk remains material: about `-19%` to `-26%` depending on config. This is not a rounding issue; it is a real PM risk-acceptance question.
- Risks / Counterarguments:
  - Research still depends on SPX proxy infrastructure rather than true historical `/ES` options data.
  - A statistically valid full-system thesis is not yet a production-ready sleeve because leverage sizing remains mis-scaled for today's SPX level and margin reality.
- Confidence: high on the thesis-validation result; medium-high on the next blocker identification.
- Next Tests:
  - a narrow Tier 1–2 recalibration study for the VIX leverage table under current SPX / SPAN conditions
  - explicit outputs should include peak SPAN usage, contract-cap recommendations, and worst-year trade-offs
- Recommendation:
  - do not continue patching the current `1`-contract cell as if it were the thesis
  - if PM wants to continue the `/ES` line, the next legitimate research unit is **leverage-table recalibration**, not another generic alpha pass
- Related: `Q012`, `Q013`, `Q050`, `Q051`, `SPEC-061`, `SPEC-086`, `SPEC-088`

### R-20260508-11 — Q051 final conclusion: `/ES` thesis survives only as a full-system hypothesis; current 1-contract path is a live-data cell

- Topic: final research consolidation for the `/ES` line after the honest-parameter salvage pass, including STOP sensitivity, BSH economics, and the 2nd Quant review.
- Findings:
  - The most important conclusion is structural, not parametric: the current `1`-contract live deployment is **not the same strategy** as the original `/ES` thesis. The thesis depended on a larger integrated system (dynamic leverage + hedge financing + multi-slot structure). The current production path is best understood as a live-data / visibility / operational-calibration cell.
  - BSH economics are now explicitly quantified as **scale-dependent**. At approximately `1` contract × `5` slots, annual theta income (`~$5k–$8k`) is not enough to economically carry annual BSH drag (`~$10k`). This means BSH is not a universal tail remedy for the `/ES` line; it only makes sense once the theta engine is large enough to finance it.
  - Statistical significance does not recover under the current honest scale. `STOP = 3.0 / 3.5 / 4.0` remains non-significant; 2-contract diagnostics scale returns and variance proportionally and do not fix the distribution shape. The problem is therefore not “choose a slightly better parameter,” but “the current low-scale naked-put slice is structurally too weak.”
  - Final high-level verdict: **the original `/ES` thesis is still alive only as a full-system hypothesis, while the current 1-contract path should be treated as a low-priority live-data / visibility cell**.
- Risks / Counterarguments:
  - This does not prove the full original thesis works. It only proves the current minimal cell is not a valid proxy for it.
  - Any future full-thesis rerun still depends on SPX-proxy-based research infrastructure unless a truer `/ES` historical options path is added later.
- Confidence: high on the structural conclusion; medium on the economic attractiveness of a future full-thesis rerun until it is actually executed.
- Next Tests:
  - only if PM authorizes it: full-thesis rerun with dynamic VIX leverage + STOP grid + BSH under the honest assumptions
- Recommendation:
  - PM should now choose between two explicit postures:
    - **A)** keep `/ES` as a low-priority `1`-contract live-data / visibility cell
    - **B)** authorize a full-thesis rerun as a real Tier 2–3 research investment
  - do not continue incremental salvage patching on the current `1`-contract cell
- Related: `Q012`, `Q013`, `Q050`, `Q051`, `SPEC-061`, `SPEC-086`, `SPEC-088`

### R-20260508-10 — Q012/Q051 CLOSED: `/ES` thesis alive only as full-system hypothesis; 1-contract path reclassified as live-data cell

- Topic: Final research conclusion from Phase 2 rerun + STOP sensitivity + Phase 4 BSH rerun + 2nd Quant review (two rounds). Q012 `/ES` shared-BP governance and Q051 `/ES` performance salvage now jointly closed as research-side completed questions.
- Findings:
  - **STOP sensitivity (Phase 2 filtered, 1 contract/slot, STOP = 3.0/3.5/4.0)**: Direction consistent across all three stops; STOP is not the primary bottleneck. STOP=4.0 CI nearly touches zero ([-20, +337]) but remains not significant. Thesis does not depend excessively on STOP assumption — the direction is robust, the scale is not.
  - **Phase 4 BSH at 1-contract scale**: BSH is a net economic drag at 1-contract scale. Estimated annual BSH cost ≈ $10k vs annual theta income ≈ $5–8k at 1 contract × 5 slots. AnnROE drops from 1.08% (naked) to 0.34% (+ BSH) at STOP=3.0. Bootstrap CI is unchanged because BSH PnL flows through equity curve only, not through trade samples. BSH is not a universal tail remedy — it requires sufficient theta scale to be economically viable.
  - **2-contract diagnostic**: Adding contracts scales PnL and variance proportionally; distribution shape (CI lower-bound sign) does not change. Statistical weakness is not a scale problem — it is a per-unit distribution quality problem.
  - **Structural conclusion**: The original `/ES` thesis (trend-filtered short puts + VIX dynamic leverage table + BSH) cannot be separated into components. BSH requires the leverage table's scaling to be economically financed; the leverage table's alpha requires the full multi-slot system; neither survives in isolation at 1-contract production scale.
  - **1-contract production deployment reclassified**: Current SPEC-061 1-contract cell is correctly understood as a live data collection / visibility cell, NOT a thesis validation path. It serves: fill/slippage observation, bot-alert behavior calibration, SPAN stress calibration (SPEC-088), and operational familiarity. It should not be cited as evidence for or against the full `/ES` thesis.
  - **2nd Quant verdict (two rounds)**: B-minus / Conditional Alive. Thesis alive only in original full-system form (dynamic VIX leverage + BSH + trend filter + stop discipline). Current production-scale is structurally disconnected from thesis requirements.
- Risks / Counterarguments:
  - The full-thesis rerun (Phase 3/4 with STOP=3.0 grid) has not been executed. It remains possible that the full system still produces bootstrap-significant results under honest stop parameters — this would be a material positive finding.
  - All research continues to use SPX proxy, not true `/ES` historical options data.
- Confidence: high on the structural conclusion (1-contract is not the thesis). Medium on full-system potential — genuinely unknown until full-thesis rerun is done.
- Next Tests (only if PM authorizes):
  - Full-thesis rerun: Phase 3/4 dynamic leverage + STOP grid (3.0 / 3.5 / 4.0) + BSH payoff
  - Must include: bootstrap CI, worst-year, stress windows (2008/2020/2022), BSH annual cost vs theta income, peak SPAN stress
  - This is a PM-level research investment decision, not a default next step
- Recommendation:
  - **If PM does not authorize full-thesis rerun**: maintain 1-contract `/ES` as low-priority live-data cell; do not invest in governance complexity or treat it as ROE engine; keep Q050 as a standing governance research lane for when `/ES` scales materially.
  - **If PM authorizes full-thesis rerun**: scope it as a single Tier 2–3 Quant study; do not open a Developer spec until bootstrap results are known.
  - Either way: `/ES` should remain behind `Q041` in ROE priority (Q046 mechanism ranking confirmed Q041 as the primary BP deployment efficiency axis).
- Related: `Q012`, `Q013`, `Q050`, `Q051`, `SPEC-061`, `SPEC-086`, `SPEC-088`
- See: `research/q012/phase_sensitivity_and_bsh.py`, `task/q012_es_phase2_2nd_quant_review_packet_2026-05-08.md`

---

### R-20260508-09 — Q051 initial judgment: original `/ES` thesis may survive, but the current minimal cell is the wrong implementation

- Topic: Quant-side initial judgment on whether the weak current `/ES` page result should be interpreted as a thesis failure or a cell-level implementation failure.
- Findings:
  - The weak current `/es-backtest` result should be treated as **real enough to matter**. Under the newly aligned assumptions — `3.0x` stop, fixed `1` contract, hybrid pricing, single-source `EsShortPutParams` — the current minimal `/ES` cell no longer looks statistically compelling.
  - But this does **not** yet kill the broader original `/ES` thesis. Quant's current reading is: **original thesis still alive but current cell is the wrong implementation**.
  - The weak result mainly invalidates the narrow current production-comparable slice:
    - `45 DTE`
    - `Δ0.20`
    - single slot
    - `1` contract
    - `STOP_MULT = 3.0`
  - The broader research idea still has plausible surviving components:
    - trend filter as risk-control gate
    - DTE laddering as the first place where old evidence became statistically positive
    - BSH / Layer-3 tail payoff effects
    - low-correlation diversification value relative to SPX Credit
  - The biggest driver of the current weakness is not just the tighter stop. It is the combination of:
    - tighter stop semantics (`4.0 -> 3.0`)
    - and, more importantly, production-comparable downsizing from roughly `~2.44` implied contracts to `1` contract
  - The most valuable next research step is therefore a **Phase 2 DTE ladder rerun under the honest assumptions**. This is the cleanest test of whether the broader thesis survives once the production-comparable constraints are enforced.
- Risks / Counterarguments:
  - The current page is still a proxy/hybrid research surface and not a full `/ES` historical options truth engine.
  - A successful ladder rerun would not automatically justify implementation; it would only prove the thesis still has recoverable research value.
- Confidence: medium-high. Strong enough to reprioritize the `/ES` research branch, not strong enough to open a new Spec.
- Next Tests:
  - rerun original Phase 2 DTE ladder under:
    - `STOP_MULT = 3.0`
    - `1` contract per slot
    - hybrid pricing
  - if needed after that:
    - stop-level sensitivity (`3.0 / 3.5 / 4.0`)
    - delta/DTE reselection
- Recommendation:
  - keep `Q051` research-only
  - make the honest-parameter Phase 2 ladder rerun the next `/ES` branch-point question
  - do not open a new `/ES` implementation Spec before that result exists
- Related: `Q012`, `Q013`, `Q050`, `SPEC-061`, `SPEC-086`

### R-20260508-08 — Q051 opened: reassess whether `/ES` still has salvageable edge under the new honest assumptions

- Topic: the current `/es-backtest` surface now shows near-zero or slightly negative standalone performance for the minimal `/ES` cell (`45 DTE / Δ0.20 / trend filter ON`) after recent semantic-alignment work made the line more production-comparable.
- Findings:
  - The current weak page result appears directionally real, not cosmetic. Planner-side direct checks of the current backtest path are consistent with the displayed “Sharpe ~0 / ROE slightly negative” story.
  - What this most directly invalidates is the **current minimal cell**, not necessarily the full original `/ES` thesis. The original research in `research/strategies/ES_puts` was broader: it included trend filtering, DTE laddering, leverage framing, and a larger multi-layer intuition rather than just “45d Δ0.20 single-slot always-on sleeve.”
  - The recent `/ES` alignment changes matter here. The strategy is now being judged under stricter and more honest assumptions:
    - `stop_mult = 3.0`
    - `n_contracts = 1`
    - shared parameter source via `strategy/es_params.py`
    - current hybrid actual-pricing surface
  - The right next question is therefore a salvage question, not a restart question: is there still a recoverable structural edge, and if so does it most likely live in DTE laddering, delta/DTE reselection, exit redesign, or narrower regime gating?
- Risks / Counterarguments:
  - The current page is still a proxy research surface and not a perfect `/ES` historical options truth engine.
  - This entry should not be read as proof that the full `/ES` program is dead; only that the current production-comparable minimal implementation is weak enough to require a narrower Quant rethink.
- Confidence: medium-high. Strong enough to open a dedicated research lane, not strong enough to close the `/ES` line entirely.
- Next Tests:
  - Quant should explicitly reassess the original `/ES` thesis under the new honest assumptions
  - Priority should go to: DTE ladder revalidation, delta/DTE reselection, exit-structure review, and narrower regime gating
- Recommendation:
  - open a narrow Quant research lane (`Q051`) focused on `/ES` performance salvage
  - do not open a new implementation Spec until Quant first determines whether there is still a real edge worth rescuing
- Related: `Q012`, `Q013`, `Q050`, `SPEC-061`, `SPEC-086`

### R-20260508-07 — SPEC-087 nav-label test debt cleaned up; no product behavior change

- Topic: maintenance-only cleanup of the pre-existing `SPEC-087` test drift after nav wording had already moved from `Backtest` to `Port BT`.
- Findings:
  - The drift was real but narrow: two nav-related assertions in `tests/test_spec_087.py` still expected the old label even though the portfolio-home nav had already been intentionally simplified.
  - The cleanup is now complete and should be treated as **test alignment only**, not as a product or routing change. No runtime behavior, write path, recommendation shape, or UI structure changed as part of this step.
- Risks / Counterarguments:
  - None material. This was straightforward pre-existing test debt and not evidence of a new regression.
- Confidence: high.
- Next Tests: none beyond the normal regression path; the important outcome is that this debt no longer distracts from the `/ES` / `Q012` / `SPEC-088` line.
- Recommendation: treat the `SPEC-087` nav-label mismatch as closed maintenance debt.
- Related: `SPEC-087`, `SPEC-088`

### R-20260508-06 — /ES parameter unification implemented: 3.0x stop, fixed 1-contract sizing, single-source EsShortPutParams

- Topic: Developer implemented the `/ES` semantic-alignment conclusions from the recent Quant audit so research, runtime, and monitoring now read the same core assumptions.
- Findings:
  - **Decision A is now implemented**: `backtest.py` stop semantics were aligned from `STOP_MULT = 4.0` to **`3.0`**, matching both `SPEC-061` (`-300% credit`) and the live alert semantics from `SPEC-086`. As expected, this makes the backtest more honest rather than “worse”: stop rate rose from `15.9%` to `27.8%`, which is the correct directional effect when the stop is no longer overly permissive.
  - **Decision B is now implemented**: `/ES` research sizing for the production-comparable path is now fixed at **`1` contract** rather than inferred from `P1_BP_TARGET`. This closes the main production-vs-backtest mismatch for the current live scale and makes `/ES` replay outputs directly interpretable without hidden `~2.4x` contract assumptions.
  - A new single-source parameter layer now exists at `strategy/es_params.py`. It defines the canonical `/ES` assumptions:
    - `entry_dte = 45`
    - `target_delta = 0.20`
    - `stop_mult = 3.0`
    - `profit_target = 0.10`
    - `n_contracts = 1`
    - `bp_limit_fraction = 0.20`
  - Three consumer layers now read from the same source:
    - `research/strategies/ES_puts/backtest.py`
    - `notify/telegram_bot.py`
    - `web/server.py`
  - This is the first real closure of the “same `/ES` strategy described three different ways” problem. Future `/ES` parameter changes now have a clean single place to land.
- Risks / Counterarguments:
  - The first live `/ES` position is still needed to validate Schwab `mark` unit behavior and to compare real broker behavior against the newly aligned assumptions.
  - Fixed `1`-contract sizing is the correct production-comparable mode for now, but future research sensitivity scans may still deliberately use alternate BP%-mode sizing; those should now be explicitly labeled as such.
- Confidence: high. The semantic mismatch is now reduced materially at the code level, not only in documentation.
- Next Tests:
  - validate the first real `/ES` live position against the aligned `3.0x` stop semantics and `1`-contract sizing assumptions
  - keep the future `/ES` stressed-SPAN visibility surface (`SPEC-088`) anchored to `EsShortPutParams`
- Recommendation:
  - treat `strategy/es_params.py` as the canonical `/ES` parameter source
  - treat older `/ES` backtest outputs generated under `STOP_MULT = 4.0` or BP%-mode sizing as non-production-comparable history
- Related: `Q012`, `Q013`, `SPEC-061`, `SPEC-086`

### R-20260508-05 — /ES alignment audit: stop semantics must unify at 3.0, and production-comparable sizing is a 1-contract problem

- Topic: Quant review of `/ES` parameter consistency across research, runtime, and support surfaces after the recent `/ES` implementation / monitoring work.
- Findings:
  - The alignment review is broadly **PASS** on the text/value cleanup side, with one implementation-sensitive caveat: if the server-side auto-search route was previously hardcoding `21` as the HIGH_VOL entry DTE while `StrategyParams` defaults imply `35`, then moving that path to the canonical default is the correct fix — but the next comparison run should explicitly confirm that HIGH_VOL search behavior still matches intent because this changes the parameter scan range.
  - **Decision A** is now clear: `/ES` stop semantics should unify at **`3.0x credit`**, not `4.0x`. This is the only reading that is self-consistent across `SPEC-061` (“-300% credit / 3× premium”) and `SPEC-086` (bot TRIGGER at `ratio >= 3.0`). Any backtest still using `STOP_MULT = 4.0` is optimistic relative to production semantics and will understate stop frequency while overstating win rate and PnL.
  - **Decision B** is also clearer after the audit: the real mismatch is not “10% vs 20%” in a simple sense, but **BP%-sized backtest versus production single-contract execution**. `P1_BP_TARGET = 0.10` is a research-side sizing target; `_ES_BP_LIMIT_FRACTION = 0.20` is a production account-level ceiling. Current production is effectively `1` contract (`~$20,529`, about `4.1%` NLV on `$500k`), so a backtest that sizes to `10%` is implicitly simulating about `2.4` contracts. That means current backtest results are not directly production-comparable unless they are explicitly normalized or rerun in a fixed-`1`-contract mode.
  - The best long-run hardening move is not more checklist prose but a single `/ES` parameter source. Quant recommends introducing an `EsShortPutParams` dataclass so that backtest, selector/runtime, and bot/monitoring all read the same stop / DTE / delta / sizing / BP-limit assumptions.
- Risks / Counterarguments:
  - This is a semantic-alignment result, not yet an implementation result. The index should not imply that `STOP_MULT = 3.0` or fixed-1-contract replay is already live everywhere.
  - The `high_vol_dte` alignment item still needs a next-run sanity check because parameter-source cleanup can change search surfaces even when it is conceptually correct.
- Confidence: high on the semantic conclusions; medium on the exact implementation landing until the relevant engineering changes are made and rerun.
- Next Tests:
  - next `/ES` backtest comparison should verify the HIGH_VOL auto-search behavior after `high_vol_dte` default alignment
  - a future engineering follow-up should align `/ES` backtest stop semantics to `3.0x`
  - production-comparable `/ES` reporting should prefer fixed `1`-contract replay or make BP%-mode assumptions explicit
- Recommendation:
  - treat `/ES` stop semantics as canonically `3.0x credit`
  - treat the sizing mismatch as a **1-contract-vs-BP%-mode** issue, not a “20% limit means double the current target” issue
  - consider a future engineering hardening follow-up around `EsShortPutParams`
- Related: `Q012`, `Q013`, `SPEC-061`, `SPEC-086`

### R-20260508-04 — Q050 opened: preserve the full portfolio-level shared-BP governance question as its own research lane

- Topic: PM correctly pushed back on a purely patchwise interpretation of `/ES` follow-up work. After `Q012 Phase C` narrowed the **current** `/ES` implementation target to stressed-SPAN visibility, the project still needed a separate place to hold the **larger** portfolio-governance question: how should scarce PM buying power be governed once multiple sleeves materially compete for it?
- Findings:
  - `Q012` and the future `SPEC-088` are now the right home for the current-scale `/ES` problem only: a live `1`-contract `/ES` sleeve needs better post-entry SPAN visibility, not a full allocator.
  - That narrowing should **not** be mistaken for a dismissal of the global research problem. The platform is already moving toward a multi-sleeve posture (`Q041`, `Q045`, `Q046`, `Q048`), and future coexistence among `/ES`, SPX Credit, capital-fill sleeves, and later candidates will eventually require an explicit governance philosophy.
  - The right planning move is therefore separation, not expansion: keep the current implementation narrow, and open a distinct research lane (`Q050`) for portfolio-level shared-BP governance principles, sleeve taxonomy, scale triggers, stress hierarchy, and research-vs-platform boundary decisions.
- Risks / Counterarguments:
  - Opening `Q050` should not be misread as reopening a large implementation project or as a reason to widen `Q012`.
  - The governance philosophy is not yet frozen, and forcing it into current runtime code would prematurely harden research-side semantics.
- Confidence: high. Strong enough to change planning structure now by separating the narrow implementation target from the long-horizon research question.
- Next Tests: none immediately required for implementation. `Q050` should remain a standing Quant-side global research lane until live scale or multi-sleeve coexistence materially increases.
- Recommendation: preserve `Q050` as the explicit home for full portfolio-level shared-BP thinking while letting `Q012/SPEC-088` remain deliberately small and current-scale.
- Related: `Q012`, `Q041`, `Q045`, `Q046`, `Q048`
- See: `doc/q050_portfolio_shared_bp_governance_framework_seed_memo_2026-05-08.md`

### R-20260508-03 — Q012 Phase C reframed the `/ES` lane: current-scale need is SPAN visibility, not a full shared-BP governance engine

- Topic: Quant Phase C on `/ES` vs SPX Credit shared-BP governance — compare architecture choices at current live scale and decide whether a true governance framework is justified now.
- Findings:
  - Phase C produced the key reframing. At current size (`1` `/ES` contract on a `$500k` account), governance architecture choice barely moves account-level outcomes. The tested architectures (`Arch-1` simple overlay, `Arch-2` dynamic-budget stress-adjusted, `Arch-3` regime-gated) all land within about `±0.01pp` of baseline account-level ROE. This is not a “pick the best rule” problem; it is a “the sleeve is too small for architecture to matter much” problem.
  - The most counterintuitive result is that the earlier Phase B intuition does **not** survive when tested at book level. `HIGH_VOL` collision is real and structurally dangerous in the abstract, but the regime-gated architecture (`Arch-3`) performs worst because it removes the very periods where `/ES` premium is richest while not delivering a meaningful account-level improvement at current size.
  - SPAN expansion risk remains real and visible: `82 / 158` `/ES` trades see SPAN expansion beyond `1.5x`, and the maximum observed expansion reaches `6.74x` (`~$138k`, roughly `27%` NLV) in COVID-style stress. But at current `1`-contract size this is primarily a **monitoring / visibility** problem, not yet a full governance-architecture problem.
  - The real threshold question is scale. For `1` contract (`~4%` NLV) the governance complexity is not justified. Around `3` contracts (`~12%`) simple rules may become warranted. Around `5` contracts (`~20%`) or more, a true shared-BP governance framework becomes justified, and `Arch-2` (dynamic budget + stress correction) is the preferred candidate for that future state.
- Risks / Counterarguments:
  - Phase C still depends on modeled rather than broker-certified real-time Schwab behavior.
  - The precise threshold bands from Phase A (`VIX 22/30/40`, `1.3x/1.6x/2.0x`) still need real live calibration before being treated as production-grade control parameters.
  - This conclusion is valid for current size; it should not be overgeneralized to a future `/ES` sleeve that is materially larger.
- Confidence: medium-high. Strong enough to change planning posture now: shrink the implementation target from “governance framework” to “SPAN post-entry visibility.”
- Next Tests: first real `/ES` live position remains the best calibration source for Schwab `mark` semantics and practical stressed-BP behavior. Future governance-spec work should reopen only if `/ES` scales up materially or live Schwab data exposes materially different stress dynamics.
- Recommendation: do **not** open a broad shared-BP governance spec now. Open only a narrow monitoring-layer spec: when an `/ES` live position exists, show current estimated stressed SPAN versus static entry SPAN. Defer the full governance framework until `/ES` grows into a materially competing sleeve (`3–5+` contracts) and live Schwab behavior has been observed.
- Related: `Q012`, `Q013`, `SPEC-061`, `SPEC-086`
- See: `doc/q012_shared_bp_governance_clarification_seed_memo_2026-05-08.md`

### R-20260508-02 — Q012 Phase A+B: shared-BP governance between `/ES` and SPX Credit is now clear enough for a narrow DRAFT Spec

- Topic: Quant Phase A+B on `/ES` shared-BP governance — convert SPAN expansion and same-day collision from a vague runtime concern into a concrete rule recommendation.
- Findings:
  - **Phase A (SPAN expansion)** now provides a usable stress model. New-entry `/ES` SPAN rises from about `$20,529` at `VIX 19` to `$33,853` at `VIX 30`, `$46,541` at `VIX 40`, and `$73,367` at `VIX 60`. On a held position, 10-day stressed SPAN rises even more sharply (`$46,107` at `VIX 30`, `$70,533` at `VIX 40`, `$117,456` at `VIX 60`). This is enough to justify explicit stress-adjusted BP estimation rather than static `$20,529` usage.
  - Recommended **pre-entry** BP estimates are now regime-banded: `VIX < 22` use static `$20,529`; `VIX 22–30` use `1.3x`; `VIX 30–40` use `1.6x`; `VIX > 40` use `2.0x`.
  - Recommended **post-entry** SPAN correction is also explicit: no correction below `VIX 22`; `1.4x` in `VIX 22–30`; `1.8x` above `VIX 30`.
  - **Phase B (same-day collision)** invalidates the old “collision is probably rare” instinct. Under the tested overlap logic, `/ES` bullish days occur `62.1%` of the time, SPX Credit entry days `71.9%`, and collisions on `39.1%` of days (`~1,901`, roughly `98`/year). More importantly, modeled cap breach on collision is `100%` in `HIGH_VOL (VIX 25–35)` and `EXTREME_VOL (VIX > 35)`, `21.1%` in `NORMAL`, and `0%` in `LOW_VOL`.
  - This is strong enough to change the governance recommendation itself. The correct narrow landing shape is now:
    - `VIX < 25` → **Rule A+**: preserve shared-BP cap, but evaluate new `/ES` entries with stress-adjusted BP
    - `VIX >= 25` → **Rule D**: if SPX Credit already has an active position, `/ES` must not newly open
    - if `/ES` is already open and VIX rises, enforce the post-entry SPAN correction before allowing new SPX Credit usage against the same pool
  - **Rule B (reserved sub-budget)** is not preferred. The main issue is not “`/ES` needs a permanent bucket,” but “simultaneous activity becomes structurally unsafe once volatility crosses into `HIGH_VOL`.”
- Risks / Counterarguments:
  - Phase B still used an SPX Credit **proxy model**, not the final canonical engine path.
  - The thresholds (`VIX 25`, `1.4x`, etc.) are now implementation-ready in direction, but should be treated as calibratable rather than sacred constants.
  - First-live `/ES` runtime data is still useful to validate Schwab `mark` unit and the practical BP stress posture against real broker behavior.
- Confidence: medium-high. Strong enough for a narrow governance spec; not a reason to widen into a joint allocator or to reopen `/ES` alpha research.
- Next Tests: package the rule set into a narrow DRAFT Spec; preserve live Schwab calibration as a runtime follow-up rather than as a blocker to spec entry.
- Recommendation: `Q012` is now **ready for a narrow DRAFT Spec** centered on three rules only: pre-entry stress-adjusted BP, `VIX >= 25` regime-priority block on new `/ES` entries when SPX Credit is active, and post-entry SPAN correction for already-open `/ES` positions.
- Related: `Q012`, `Q013`, `SPEC-061`, `SPEC-086`
- See: `doc/q012_shared_bp_governance_clarification_seed_memo_2026-05-08.md`

### R-20260508-01 — PM-accurate margin breakdown: homepage BP must use PM-style max-loss/equity proxies, not Reg-T spread math

- Topic: PM-facing portfolio margin decomposition on the homepage and command-center surfaces.
- Findings:
  - The previous homepage BP display materially overstated usage (`~33.6%`) because it treated the SPX spread like a Reg-T debit `(width - credit) * 100` object. For the current Schwab PM account, the practical approximation is much closer to **max-loss**: SPX spread BP should be proxied as `width * 100 * contracts`.
  - For equities, the most useful operational proxy is an **equity PM haircut** around `market_value * 0.85`, i.e. an implied `15%` haircut, derived from reconciling the TOS margin screenshot against the Schwab account-level maintenance total.
  - Schwab’s API is not giving a reliable per-position PM decomposition: `maintenanceRequirement` is effectively zero at the position level, so the only trustworthy maintenance number is the **account-level total**. Any portfolio surface that wants rail/bucket breakdown must therefore infer it from account totals plus strategy-specific proxies rather than expect per-position truth from the broker payload.
- Risks / Counterarguments:
  - These are still operational proxies, not broker-certified per-position PM formulas. They are good enough for homepage / command-center truthfulness and for research-facing BP reasoning, but should not be mistaken for an exact broker liquidation model.
  - The approximation is currently strongest for the present SPX spread + equity mix; if the live book changes materially, the decomposition assumptions may need to be revisited.
- Confidence: medium-high for current operational use. Strong enough to replace the old homepage display and to serve as the default PM-facing BP interpretation layer.
- Next Tests: validate the proxy again after the next meaningful live position mix change, especially if `/ES` and SPX options coexist more actively in the same BP pool.
- Recommendation: treat the PM-aware homepage decomposition as canonical for UI and planning purposes: SPX spread BP via `width * 100`, equity margin as `maintenance_total - spx_max_loss`, and cash / money-market / cash-ETF buckets explicitly separated.
- Related: `SPEC-087`, `Q012`
- See: `schwab/client.py`, `web/portfolio_surface.py`, `web/templates/portfolio_home.html`

---

### R-20260507-05 — SPEC-086 DONE: /ES short put credit stop monitor live; B1 closed

- Topic: `SPEC-086` implemented and reviewed; top blocker B1 formally closed.
- Outcome: `/ES` put mark monitor now runs inside the existing Telegram `intraday_monitor` loop — WARNING at ≥ 2× entry premium, TRIGGER at ≥ 3× (the SPEC-061 credit stop line). Escalation-only logic with fail-soft on Schwab unavailability; `observed` flag prevents false "cleared" alerts. AC1–AC8 all PASS, 15/15 tests pass, Quant Researcher independent review PASS.
- B1 status: **CLOSED**. The prior minimum-acceptable requirement (system monitoring + bot alerting for the `/ES` credit stop condition) is now met.
- Known open item (non-blocking): Schwab `mark` field per-share unit not yet validated against a real `/ES` position — to be confirmed when the first live `/ES` position is opened.
- Related: `Q013`, `SPEC-061`, `notify/telegram_bot.py`, `tests/test_spec_086.py`, `task/SPEC-086.md`, `task/SPEC-086_handoff.md`

---

### R-20260507-04 — Q041 Tier 3 portfolio-attribution prototype accepted as SPEC-085 F3 source; long paper-trading path materially collapsed

- Topic: Quant completed the `Q041` Tier 3 portfolio-attribution prototype and PM decided to accept its artifact as the formal `SPEC-085 F3` attribution input, while explicitly declining both the original 12-month paper-trading path and the intermediate `4–6` week live signal forward-tracking observation window.
- Findings:
  - The Tier 3 prototype now provides a concrete portfolio-value artifact for `Q041`: `idle_day_capture = 132 days` (`86.8%` of J3 fully-idle days), `delta_avg_bp = +22.21pp`, `bp_fill_contribution = +22.21pp`, `joint mean BP = 38.04%`, and `excess_overlap_vs_occupancy = +4.5pp`.
  - This is strong enough to answer the research-side `A/C/D/E` questions ex ante: cycle quality, idle-day capture, BP-fill contribution, and worst-day overlap are now materially quantified.
  - The remaining realism gap is no longer broad paper-trading evidence accumulation; it is narrowly the single-name fill/slippage realism question for Tier 2 (`GOOGL` / `AMZN`). PM chose **not** to require an additional generic forward-tracking observation phase before using the artifact as the canonical `SPEC-085 F3` source.
  - Operationally, this changes `Q041` from “paper-trading support first” to “visualization / attribution first, with any later live or calibration need judged as a narrower follow-up rather than as the default next gate.”
- Risks / Counterarguments:
  - The artifact is still based on a bounded `3.3y` window, excludes COVID 2020, approximates CSP BP as `K*100`, and does not perform fill calibration. It should be treated as a strong portfolio-deployment prior, not as a substitute for every future live-validation question.
  - Because PM declined the generic `4–6` week forward-tracking window, any future request for Tier 2 single-name realism evidence should be framed as a narrow follow-up question rather than assumed to be part of the current path.
- Confidence: medium-high. Strong enough to change planning posture and to serve as the formal `SPEC-085 F3` input; not a reason by itself to auto-promote any sleeve into production trading.
- Next Tests: none required as a default gating step. Keep overlap validation running on its own track and let `SPEC-085` consume the accepted artifact. Only reopen live calibration if PM later asks a narrower Tier 2 fill/slippage question.
- Recommendation: treat `data/q041_portfolio_attribution_latest.json` as the canonical `SPEC-085 F3` source, drop the old 12-month paper-trading path as the main route, and do not impose a new generic `4–6` week live signal forward-tracking requirement.
- Related Question: `Q041`, `Q046`, `Q048`, `Q049`, `SPEC-085`
- See: `doc/q041_portfolio_attribution_results_2026-05-07.md`, `data/q041_portfolio_attribution_latest.json`

---

### R-20260507-03 — Q048 opened: architecture-planning lane for the transition from single-SPX execution platform to portfolio research platform

- Topic: Planner-led architecture review after `Q041` / `Q045` / `Q046` concluded that the project is no longer just adding more SPX strategies; it is entering a portfolio-research stage that needs new state, bookkeeping, and recommendation abstractions.
- Findings:
  - The current live system still assumes one canonical recommendation, one current live position, and one SPX-centered backtest / dashboard universe.
  - `Q041` already introduced a second rail — a multi-record paper ledger with its own budget and review logic — which now coexists alongside the single-position SPX live rail.
  - Quant-side review concluded that the research object has changed from isolated strategy quality to **capital deployment across interacting sleeves**, and that the platform now needs a formal distinction between production SPX sleeves, capital-fill sleeves, tail-caveated sleeves, and observe-only sleeves.
  - Developer-side review concluded that the deepest technical seam is not UI cosmetics but the continued dependence on `current_position.json`, single-answer recommendation semantics, split ledgers, and SPX-centric information architecture.
- Risks / Counterarguments: Opening a large “multi-strategy platform rewrite” now would be premature and could contaminate the stable SPX live rail. The near-term risk is architectural overbuild before the portfolio research model and sleeve-governance vocabulary stabilize.
- Confidence: high on the diagnosis; medium on exact future implementation slicing, because the right spec boundaries should follow from a dedicated planning pass rather than be improvised inside a live feature branch.
- Next Tests: keep `Q041` on its current evidence-accumulation path; use `Q048` to define the minimum portfolio-state / unified-ledger / candidate-set abstractions and then decide whether one or two narrow future specs should be opened.
- Recommendation: keep `Q048` as a planning / architecture item, not a DRAFT Spec. The correct next move is staged design: explicit dual-rail acknowledgement, portfolio-state abstraction, recommendation split, minimal portfolio summary surface, then attribution-first research interfaces.
- Related Question: `Q048`, `Q041`, `Q045`, `Q046`
- See: `doc/q048_portfolio_state_architecture_transition_plan_seed_memo_2026-05-07.md`

---

### R-20260507-02 — Q046 benchmark-normalization result: the remaining post-SPEC-084 BP gap is moderate, and Q041 is the primary next mechanism axis

- Topic: Quant follow-up on `Q046` — normalize external BP-usage benchmarks against our post-`SPEC-084` book and decide which mechanism family should be promoted next.
- Findings:
  - The raw external headline (`~25%–30%` or wider `25%–50%` allocation frameworks) is not directly comparable to our single-trade `bp_target`; the correct comparison layer is **portfolio-level average BP usage**.
  - After normalizing for **PM vs Reg-T** and **defined-risk strategy structure**, our post-`SPEC-084` level (`~15.93%`) is not dramatically under-deployed relative to a conservative-to-neutral PM defined-risk book; the real gap compresses to roughly `~5–10pp`, not `15pp+`.
  - `Q045` already exhausted most of the sizing axis: A (more sizing) has limited remaining value and runs into cliff / tail issues; B (more concurrency) cannot touch the `17%` fully idle days and increases concentration; D (higher ceiling) is an enabler rather than a standalone axis.
  - **Mechanism C (broader strategy / underlying coverage)** is the clear next step because it is the only family that can directly attack the fully idle days. `Q041` already exists as the live carrier for this axis through paper trading.
- Risks / Counterarguments: This conclusion is a framing / prioritization result, not a new simulation result; the real validation now depends on actual `Q041` paper-trading accumulation because the current backtest framework does not support a full joint multi-underlying account simulation. External benchmarks remain heterogeneous and should not be over-literalized.
- Confidence: medium-high. Strong enough to reprioritize the next research axis; not strong enough to justify another live sizing lift or a ceiling change today.
- Next Tests: do not open a new sizing/ceiling Spec. Let `Q041` advance through the accepted attribution artifact plus the still-separate overlap-monitoring track, and only reopen a narrower follow-up if PM later asks a specific Tier 2 fill/slippage realism question.
- Recommendation: treat `Q041` as the **primary post-`Q045` account-level deployment-efficiency mechanism axis**. Keep `Q046` as completed benchmark / mechanism map. Defer A/B/D unless PM later explicitly reopens sizing or ceiling governance.
- Related Question: `Q046`, `Q041`, `Q045`, `Q036`, `Q044`
- See: `doc/q046_bp_utilization_external_benchmark_seed_memo_2026-05-07.md`

---

### R-20260507-01 — Q046 opened: external BP-utilization benchmark and deployment-efficiency research seed

- Topic: After `SPEC-084`/`Q045 J3` went live, PM raised a new account-level question: even with average BP usage lifted to only `~15.9%`, is the system still materially under-deployed relative to mainstream short-premium practice? The research problem is not to raise live sizing immediately, but to benchmark current book-level deployment against external practitioner norms and decide which mechanism family should be researched next.
- Findings: Initial external scan suggests common practitioner discussion clusters around portfolio-level usage in the `~20%–30%` range, with broader retail-PM allocation frameworks often discussed in the `25%–50%` total-buying-power-at-work range. This benchmark is not directly comparable to a single-trade `bp_target`; the right comparison layer is account-level average BP utilization. Our internal post-`SPEC-084` level (`~15.9%`) therefore looks conservative enough to justify deeper study.
- Risks / Counterarguments: External sources mix Reg-T and PM, defined-risk and undefined-risk books, and retail anecdote with formal guidance. A naive “market uses 30%, so we should too” inference would be invalid. The next research step must normalize account type, strategy type, and risk posture before drawing implementation conclusions.
- Confidence: medium. The benchmark direction is clear enough to open a research lane, but not yet strong enough to justify another sizing lift or a ceiling change.
- Next Tests: Quant should compare external benchmark ranges against our internal baseline/post-`SPEC-084` deployment profile, then rank the next mechanism family: more sizing, more overlap, broader strategy set (`Q041`), or ceiling changes.
- Recommendation: keep this as a research seed / benchmark study, not a new Spec entry. The immediate output should be a benchmark-and-mechanism map.
- Related Question: `Q046`, `Q045`, `Q041`, `Q036`, `Q044`
- See: `doc/q046_bp_utilization_external_benchmark_seed_memo_2026-05-07.md`

---

### R-20260506-05 — Q045 Tier 3 PASS: joint NORMAL+HIGH_VOL bp_target lift delivers +5.48pp account-level AnnROE on 19y sample; supersedes Q044, partially supersedes Q036

- Topic: Account-level ROE optimization across the full strategy matrix (Q045). Reframes piecemeal Q036/Q044/SPEC-077 work into a single joint optimization. PM observation triggered the reframe: "we are doing this one strategy at a time, not ideal."
- Findings:
  - **Phase 1 (baseline mapping)**: System is structurally under-utilized. Time-weighted avg BP = 11.09% out of 35% NORMAL ceiling; 17% of trading days have zero positions; 61% have only one strategy open; peak BP never exceeds 30% in baseline. The bottleneck is not "make each position bigger" but "the system doesn't fire on most days."
  - **Phase 2A (NORMAL regime sweep)**: Lifting `bp_target_normal` from 10% to 15% gives +4.15pp account-level AnnROE — far more than Q044's BPS-only +1.51pp because the parameter is regime-level, not strategy-level. All three NORMAL strategies (BCD +0.85pp, IC +1.79pp, BPS +1.51pp) scale together. Sharpe nearly unchanged (2.18 → 2.14). 20% has cliff effect (BPS -113% marginal decay) due to ceiling crowding.
  - **Phase 2B (HIGH_VOL regime sweep)**: Lifting `bp_target_high_vol` from 7% to 14% gives +1.97pp account-level AnnROE on 3y window. Sharpe IMPROVES (2.18 → 2.35). IC_HV is the biggest beneficiary (+2.06pp), with 100% WR maintained.
  - **Phase 2C (joint optimum)**: J3 (NORMAL=15%, HIGH_VOL=14%) delivers +6.12pp AnnROE = exact sum of N1+H2 alone. Interaction effect = +0.000pp — the two regimes are perfectly independent (different market conditions trigger them). Sharpe 2.18 → 2.31. Peak BP 43% within HIGH_VOL ceiling 50%. NO ceiling change needed.
  - **Phase 2D (idle BP analysis)**: Even at J3, avg BP utilization is 15.93% out of 35% ceiling = 19pp idle. 17% of days fully idle, 61% single-strategy days. Theoretical upper bound if 50% of remaining idle BP could be filled: another +20.7pp AnnROE. This frames Q041 paper trading as the diversification axis to capture the remaining gap.
  - **19-year robustness check**: J3 holds up over 2007-2026. AnnROE 11.94% → 17.41% (+5.48pp). Sharpe 1.78 → 1.83 (+0.05). All 6 strategies contribute positive uplift. BCS_HV concern from 3y window (N=1) is unfounded on full sample (N=9, WR=55.6%, +0.07pp uplift). Worst trade scales 1.57x (-$8,456 → -$13,235 = -8.82% account). Trade count drops 304→282 from BCD ceiling crowding; remaining trades scale up to compensate.
  - **vs Q036 Overlay-F**: Q036's full-sample uplift is +0.074pp; Q045 J3's HIGH_VOL component delivers +1.96pp on the same 19y sample = 26x more. Q036's selectivity (short-gamma guard) may still have value as a tail-event safety layer but its base contribution is largely captured by the simpler J3 lift.
  - **vs Q044 BPS-only**: Q044 A1 delivered +1.51pp; Q045 J3 delivers +5.48pp via joint scaling. Same implementation effort. Q044 is superseded.
- Risks / Counterarguments: Worst-trade % account rises from -5.64% to -8.82% (1.57x scaling — proportional but visible). CVaR 5% scales 1.61x. BCD's long hold (17d avg) causes ceiling crowding that drops trade count by ~7% (304→282) in 19y sample — minor adverse selection but compensated by larger remaining trades. Live size rule "≤ 3% of account" needs updating to "≤ 4.5%" on Spec implementation.
- Confidence: high. 19-year robustness, all 6 strategies positive, perfectly additive across regimes, Sharpe improves. The result is structural (regimes don't compete for BP), not regime-window dependent.
- Next Tests: only Spec-implementation regression (verify default-baseline byte-identical; verify lift produces expected behavior).
- Recommendation: **Open DRAFT Spec for joint bp_target lift (Q045 J3)**. Single Spec scope: `bp_target_normal` 0.10→0.15, `bp_target_high_vol` 0.07→0.14, `bp_target_low_vol` 0.10→0.15, plus `_size_rule()` text updates. Q044 to be closed as superseded. Q036 Overlay-F kept in shadow but deprioritized.
- Related Question: `Q045`, `Q044` (superseded), `Q036` (partially superseded), `Q041` (complementary)
- See: `task/q045_pm_decision_packet_2026-05-06.md`, `backtest/prototype/q045_phase1_baseline.py`, `backtest/prototype/q045_phase2{a,b,c,d}_*.py`

---

### R-20260506-04 — Q044 Tier 2 PASS: A1 (bp_target 15%) clears all checks; ready for Spec discussion

- Topic: Q044 Tier 2 deep dive — year-by-year attribution, full PM metrics pack, A2 ceiling cliff autopsy, Q036 combined ceiling stress test
- Findings:
  - **Year-by-year attribution (Part 1)**: A1 improvement is uniformly distributed — 2024 +$1,781, 2025 +$3,021, 2026 +$2,770. Same trade count each year, same win rate. Not a single-year artifact.
  - **Full metrics pack (Part 2)**: Sharpe unchanged (0.91 → 0.91); peak concurrent BP% unchanged (30.0% → 30.0%, within 35% ceiling); AnnROE +1.510pp (3.042%→4.552%); marginal $/BP-day decay -0.3%; worst trade scales to -6.25% of account (vs -4.17% at baseline); CVaR5% and disaster window scale proportionally. All risk metrics are proportional — pure linear scaling confirmed.
  - **A2 ceiling cliff autopsy (Part 3)**: Of 8 blocked trades at A2 ceiling=35%, 7 were profitable (avg +$2,513). Adverse selection confirmed: ceiling blocks BPS exactly in favorable NORMAL+BULLISH environments when other positions are concurrent. Lifting ceiling to 40% recovers 5 blocked trades; A2+ceiling40% generates $27,332 (>A1 $22,823). Ceiling 40% is a valid secondary research direction but outside A1 Spec scope.
  - **Q036 combined stress test (Part 4)**: BPS A1 (15%) + IC_HV Overlay-F 2x concurrent peak = 29.0% vs HIGH_VOL ceiling 50%. 21pp headroom. One concurrent episode (2025-04-24): 15%+14%=29% — safe. Q036 active decision is fully compatible with A1.
- Risks / Counterarguments: N=15 BPS trades over 3y is a small sample — the $7,571 uplift represents ~2 full-size trades worth of incremental PnL. Worst trade rises to -6.25% of account (from -4.17%), which must be disclosed in Spec. Live size rule ("≤ 3% of account") needs updating to "≤ 4.5% of account" if A1 is implemented.
- Confidence: high (Tier 2, all checks clear, attribution robust)
- Next Tests: none required for A1 direction. Spec can begin. If ceiling study is desired, separate Tier 2 for A2+ceiling40% warranted.
- Recommendation: **advance A1 (bp_target_normal = 0.15) to DRAFT Spec**. Key Spec scope: change `bp_target_normal` and `bp_target_low_vol` from 0.10 to 0.15; update live size rule text; add risk disclosure (worst trade -6.25% acct). No ceiling change needed. Note A2+ceiling40% as a deferred follow-up.
- Related Question: `Q044`, `Q036`
- See: `doc/q044_bps_tier2_results_2026-05-06.md`, `backtest/prototype/q044_bps_sizing_tier2.py`

---

### R-20260506-03 — Q044 Tier 1 PASS: A1 (bp_target 15%) is viable; Axis B closed; A2 cliff identified

- Topic: BPS spread sizing Tier 1 Quick Scan — tested 6 variants across two axes (bp_target scale-up and spread-width expansion), 3-year window 2023-01-01→2026-05-06, $150K account
- Findings:
  - **Axis A (bp_target variants, same δ0.30/0.15 structure)**: A1 (15% bp_target) near-linear scaling — marginal $/BP-day decay only -0.3% (0.00782 → 0.00780), BPS AnnROE +1.5pp (3.0% → 4.6%), worst trade scales proportionally. A2 (20% bp_target) hits a BP ceiling cliff — N drops from 15 to 9 because BPS entries are blocked when concurrent IC/Diagonal positions push total above `bp_ceiling_normal=35%`. The 6 blocked trades are in the most favorable NORMAL+BULLISH environments; adverse selection causes total PnL to turn negative at A2. **A1 is the viable direction; A2 is not viable without also adjusting bp_ceiling.**
  - **Axis B (spread-width variants, same bp_target=10%)**: Going wider (δ0.25 or δ0.20 for short leg) uniformly degrades $/BP-day by 14% and 37% respectively, despite improving win rate from 73% to 80%. Mechanism: more OTM short put collects less premium per BP-day consumed. **Axis B direction closed — current δ0.30/0.15 structure is optimal for BPS premium efficiency.**
  - **Q036 dependency revised**: A1 and Q036 Overlay-F are regime-separated (BPS in NORMAL; Overlay-F in IC_HV aftermath). Combined BP at simultaneous open would be ~15% + 20% = 35%, within HIGH_VOL ceiling (50%). No need to wait for Q036 active decision to proceed to Tier 2 on A1.
- Risks / Counterarguments: 3-year sample has only 15 BPS trades; A1 vs A0 PnL difference ($7,571) could be one or two trades. Year-by-year attribution needed before treating A1 as robust. A2 cliff mechanism (ceiling blocking favorable entries) is a real governance risk that would need ceiling adjustment if 20% is ever revisited.
- Confidence: medium (Tier 1 directional, small sample). A1 direction is clear; Axis B closure is conclusive.
- Next Tests: Tier 2 for A1 — year-by-year attribution, combined BPS+Overlay-F ceiling stress test, live Schwab PM margin check for actual BP consumed per BPS contract
- Recommendation: advance A1 (bp_target 15%) to Tier 2. Close Axis B. Flag A2 as blocked until ceiling governance is resolved. No Spec yet.
- Related Question: `Q044`, `Q036`
- See: `doc/q044_bps_tier1_results_2026-05-06.md`, `backtest/prototype/q044_bps_sizing_tier1.py`

---

### R-20260506-02 — Q044 seed opened: BPS spread sizing and account-level ROE

- Topic: Whether current BPS single-position BP target (10% of account, NORMAL regime) is optimally sized for account-level ROE, or leaves structural idle BP that could be deployed
- Findings: Code inspection confirms `bp_target_normal = 0.10`, `bp_ceiling_normal = 0.35` (SPEC-024, "2× scale" design). In typical NORMAL environment with one BPS open, structural idle BP ≈ 25% (ceiling minus current usage). Live sizing rule ("risk ≤ 3% of account") and backtest bp_target (10%) are separate parameters with different semantics. Two sizing paths identified: (1) widen spread (e.g. 70pt → 120pt, same contracts) — more premium but higher absolute tail loss; (2) increase contracts (same width, 2× contracts) — more linear scaling. Both compete for the same idle BP as Q036 Overlay-F. The ROE research (SPEC-077 profit_target lift) already applies to all credit strategies including BPS. Q036 is the current designed answer for the idle BP gap but remains in shadow.
- Risks / Counterarguments: Wider spreads likely have lower credit/width ratio (nonlinear gamma pricing), meaning marginal $/BP-day may be lower than expected. Absolute tail loss increases. Q036 Overlay-F and larger BPS compete for the same ~25% idle BP — both cannot be at full size simultaneously without risk of approaching the ceiling.
- Confidence: low (seed level, no backtest run yet)
- Next Tests: Tier 1 Quick Scan — run 3 spread width variants in existing backtest framework, read marginal $/BP-day and CVaR. Only after Q036 shadow outcome is clearer.
- Recommendation: hold at seed / not in active queue. Q036 active decision is the gating dependency. Do not spec before Tier 1 scan.
- Related Question: `Q044`, `Q036`
- See: `doc/q044_bps_sizing_roe_seed_memo_2026-05-06.md`, `strategy/selector.py:75–77`

---

### R-20260506-01 — Q041 overlap-validation: first same-day comparison (May 4); M3/M6 cleanup completed; protocol corrections encoded; old Air three-feed automation now live

- Topic: Q041 dual-source overlap-validation — first true same-day Schwab vs Massive comparison after incremental download; M3 script bug fixed; M6 iv=-999 handling confirmed; M9 protocol text corrected
- Findings:
  - **Massive incremental download**: ran `download_massive.py --start 2026-05-02 --end 2026-05-05` successfully; parquet now covers through 2026-05-05 (May 4: 40,478 rows, May 5: 39,534 rows, all 17 symbols)
  - **M4 (same-day, May 4)**: first true same-day comparison using Schwab `last` vs Massive `close` — the protocol-specified comparison. All matched contracts (n=29,733): median `|Δ|` = **0.000%**, >2% = 2.3%, >10% = 0.7% → **STRONG PASS**. SPX ATM (|δ| 0.20–0.75, n=4,144): median 0.000%, >2% = 13.9%. The 14% tail for SPX ATM is structural: reflects that for lower-volume strikes, the Schwab “last trade” occurred at a different time than Massive's EOD close (which is the official CBOE settlement). This is a timing/settlement methodology difference, not a data source error. Q041 target |δ| 0.18–0.28, vol≥5: n=398, median 0.000%, >2% = 9.8%. M4 **PASS**. Protocol note: Schwab `close` field = previous day's settlement (cannot be used for same-day comparison); always use Schwab `last`.
  - **M3 (strike match, merge-based fix)**: the prior set-based implementation gave 0% due to a code bug. Merge-based per-expiry comparison shows: SPX 99.8% (STRONG PASS), GOOGL 83.6%, AMZN 85.8% (PASS), COST 74.4%, JPM 71.5% (below threshold — Tier 3 observe-only, acceptable), overall mean 80.3% (PASS at protocol ≥80%).
  - **M6 (IV completeness, near-money)**: iv=-999 sentinel count = 0 in May 4 Schwab snapshot. Near-money (|δ| 0.25–0.75) completeness = **100% across all 17 symbols** → STRONG PASS. Protocol note: -999 sentinel (unusable contracts, zero bid/ask) does not appear at near-money range; document in pipeline null-handling policy and filter at ingestion.
  - **M7/M8 (Greeks/OI completeness)**: delta/gamma/theta/vega/OI all 100% in near-money range → PASS.
  - **M9 (expiry_type clarification)**: confirmed from live data. SPX ATM matched contracts: W=2,993 (weekly), S=1,684 (standard monthly = third-Friday), M=138 (special month-end product). Correct mapping: Schwab `S` ↔ standard monthly (Q041 paper-trading target, DTE30 third-Friday roll). Protocol text correction needed: replace “W vs M” ratio with “W vs S” ratio as the stability check.
- Risks / Counterarguments: SPX ATM M4 >2% tail (14%) is higher than hoped for the ATM range; it's not a blocker but should be monitored as volume conditions change. COST/JPM M3 below protocol threshold (Tier 3 only). The operational risk is no longer “manual download drift”; with all three old Air feeds now scheduled, the remaining risk is monitoring launchd health and interpreting the tail behavior correctly.
- Confidence: high that same-day comparison confirms pipeline alignment. M4 median 0.000% is a strong result. No blocker-grade issue found.
- Next Tests: (1) monitor M4 daily as the 20-day formal window runs, (2) monitor the scheduled old Air jobs (`Schwab chain`, `Massive REST snapshot`, `Massive historical T+1`) for continuity, (3) preserve the protocol corrections (`M4 = Schwab last`, `M6 = Massive IV ×100`, `M9 = Schwab expiry_type S`) in downstream review scripts, (4) keep accumulating same-day reads for the final Reconciliation Report
- Recommendation: overlap validation status remains **converging as expected**, now with first same-day evidence and all three old Air data feeds in scheduled operation. No protocol gates are failing. Proceed through the formal 20-day window without resetting the clock; remaining work is monitoring and final reconciliation packaging, not collector setup.
- Related Question: `Q041`
- See: `data/q041_chains/2026-05-04/`, `data/q041_historical/*.parquet`, `doc/q041_overlap_validation_protocol_2026-05-03.md`

---

### R-20260505-04 — Q041 overlap-validation checkpoint upgrades to “converging as expected”; remaining work is cleanup-level, not blocker-grade

- Topic: Quant checkpoint review of the ongoing `Q041` dual-source overlap-validation program
- Findings: Quant now judges the current checkpoint **converging as expected**, which is a meaningful upgrade from the earlier `mixed but acceptable` read. The main reason is that the economically relevant comparable subset is now clearly strong enough on multiple dimensions: `M1` traded-key match is `99.2%` on the `volume > 0` subset, `M2` expiry match is `97.5%`, `M5` volume rank-correlation is `0.879`, `M6` near-money IV completeness is effectively `100%`, and both `M7` Greeks and `M8` open-interest completeness are `100%`. `M9` SPX/SPXW classification is also now semantically resolved: Schwab `expiry_type` should be interpreted as `W = weekly`, `S = standard monthly`, `M = special month-end`, so the correct monthly comparison is `Schwab S` versus the Massive monthly bucket rather than the older `W vs M` shorthand. The currently visible “bad” metrics are no longer interpreted as data-source failure. Raw full-chain key match (`58.7%`) is now explicitly treated as a denominator issue because Schwab exposes a broader quoted universe than Massive historical day-aggs; the correct formal gate is the traded / price-bearing subset. Likewise, the current `M4` tail with some `>2%` price deviations is not yet a formal fail because the latest exact same-day comparison has not occurred: Massive is still at `2026-05-01` while the Schwab forward snapshot already includes `2026-05-04`, so the first true same-day `M4` read should happen only after the next Massive daily download lands. A second narrow cleanup point is Schwab’s `iv = -999` sentinel on some unusable contracts; this should be treated as null in the pipeline and excluded from formal `M6` completeness math
- Risks / Counterarguments: the biggest risk now is governance misread, not data weakness. If the project continues to interpret the raw full-chain denominator as the official hard match gate, it will overstate divergence and manufacture a false blocker. Similarly, if the current non-same-day `M4` tail is read as a formal price-alignment failure, the branch would be paused for the wrong reason. There is still real work left before the formal `20`-day window is complete: fix the `M3` strike-match script bug, document / encode the `iv = -999` null policy, and update wording around the corrected `S/W/M` semantics
- Confidence: high that the stitched dataset is converging in the contracts that matter; medium-high that the remaining issues are protocol / cleanup only rather than structural data blockers
- Next Tests: `(1)` run the first true same-day `M4` comparison once Massive `2026-05-04` data lands, `(2)` update the overlap scripts to treat `iv = -999` as null, `(3)` repair the `M3` strike-match script to use merge-based comparison rather than the current broken set logic, `(4)` continue into the formal Day 6–25 overlap window without resetting the clock
- Recommendation: reclassify the current `Q041` overlap-validation state from `mixed but acceptable` to **converging as expected**. Keep overlap validation as an admission / reconciliation track for the stitched dataset, but do not let it block the already-approved `Tier 1 / Tier 2 / Tier 3` paper-trading routing
- Related Question: `Q041`
- See: `doc/q041_overlap_validation_protocol_2026-05-03.md`, `doc/q041_execution_prep_packet_2026-05-05.md`, `sync/open_questions.md`

---

### R-20260505-03 — Q041 execution-prep packet written; paper trading start-up now unblocked across all three tiers

- Topic: Quant / Planner production of `Q041` paper-trading execution-prep packet following 2nd Quant PASS Routing B
- Findings: `doc/q041_execution_prep_packet_2026-05-05.md` is the canonical paper-trading reference for all three tiers. Tier 1 (`SPX CSP Δ0.20 DTE30`): entry via BS-delta strike selection (`|Δ|≈0.20`) on third-Friday roll, DTE 25–40, non-overlapping, BP ≤20% per cycle. Back-test baseline: N=30, WR=97%, Sharpe=2.18, MaxDD=−2.84%, mean net_prem=$31.33/cycle (~6.2% annualized ROE). Tier 2 (`GOOGL CSP Δ0.20 DTE21` + `AMZN CSP Δ0.25 DTE21`): same roll logic, combined BP ≤15% (≤10% per name), explicit COVID-tail caveat mandatory in all downstream documents. Tier 3 (`COST/JPM IC`): VIX≥15 mandatory entry filter, JPM optional IMR≥33%, combined BP ≤5%, 1 contract/quarter per name. Cross-tier total Q041 budget ≤40% BP. Per-cycle recording fields standardized across all tiers. Upgrade-to-production condition: ≥12 months paper trading, ≥10 CSP cycles or ≥4 IC events, WR/MaxDD/Sharpe ≥80% of back-test baseline, at least one VIX>25 episode, PM approval. Downgrade triggers: ≥3 consecutive losses, single cycle exceeding 2× historical MaxDD, WR<70% for 6 months (CSP), VIX>40 for 2 weeks (Tier 2 reduce 50%)
- Risks / Counterarguments: paper-trading benchmark values are derived from 2022-05 → 2026-04 back-test and will be naturally harder to replicate in live markets due to bid-ask slippage, roll timing, and any regime change. The 2022 Jan–Apr data gap for SPX CSP remains a caveat even in paper trading. Tier 2 and Tier 3 candidates remain undersized in event history; a few bad outcomes could trigger downgrade rules prematurely
- Confidence: high on the execution framework; medium on whether paper-trading results will track back-test within the stated tolerances across all three tiers simultaneously
- Next Tests: begin paper-trading roll on the next third-Friday entry date; record all fields as defined in §6.1; evaluate monthly checklist after first cycle
- Recommendation: treat `doc/q041_execution_prep_packet_2026-05-05.md` as the single authoritative reference for Q041 paper trading. Do not reopen Phase 2 research scan. Overlap validation continues on its own parallel track
- Related Question: `Q041`
- See: `doc/q041_execution_prep_packet_2026-05-05.md`, `doc/q041_2nd_quant_review_feedback.md`

---

### R-20260505-02 — Q041 2nd Quant review PASS Routing B: tiered candidate routing confirmed; SPX CSP Tier 1 formal, GOOGL/AMZN Tier 2 tail-caveated, COST/JPM Tier 3 observe-only

- Topic: 2nd Quant formal review of `Q041 Phase 2` candidate governance and next-stage routing
- Findings: 2nd Quant issued **PASS — Routing B** on all five review questions. (1) `SPX CSP DTE30` is ready for paper trading / execution prep; the 2022 bear-stress read is accepted; IV compression trap is not a filter problem but a sizing / risk-budget problem; 2022 Jan–Apr data gap remains a caveat but not a blocker. (2) `GOOGL/AMZN CSP` confirmed as "borderline formal / tail-caveated" — signal is too strong to downgrade, but COVID-era single-name tail is insufficiently validated and sizing should be kept below Tier 1. (3) `COST/JPM IC` observe-only routing is correct; `VIX≥15` is a real governance / entry candidate; `JPM IMR≥33%` is optional paper-trading refinement only (not a unified rule; hurts COST). (4) Overlap validation separation from candidate promotion is endorsed: overlap work continues as stitched-dataset admission track, does not reopen historical candidate ranking. (5) Routing B selected: single packet covering SPX + GOOGL/AMZN together with tiered caveats, plus Tier 3 observe-only lane for COST/JPM
- Risks / Counterarguments: 2nd Quant maintains that SPX CSP is not yet production-ready (only paper-trading ready); the 2022 Jan–Apr gap is documented explicitly. GOOGL/AMZN's confidence tier is explicitly lower than SPX CSP, so any inadvertent equal-sizing would violate the packet intent
- Confidence: high on tiering verdict; 2nd Quant judgment aligns with planner's prior routing on all five questions
- Next Tests: execute paper trading per the execution-prep packet; keep overlap validation running to 20-day formal window endpoint
- Recommendation: proceed to paper trading under the tiered structure. Do not treat 2nd Quant PASS as production approval — it is routing into the paper-trading lane only
- Related Question: `Q041`
- See: `doc/q041_2nd_quant_review_feedback.md`, `task/q041_2nd_quant_review_packet_2026-05-05.md`

---

### R-20260505-01 — Q041 Phase 2 is now complete: SPX CSP DTE30 stays the lead formal candidate, GOOGL/AMZN CSP are borderline formal, and earnings IC shifts to observe-only with a VIX>=15 governance clue

- Topic: Quant final `Q041 Phase 2` synthesis across `P0-1 / P0-2 / P1-1 / P1-2 / P2-1 / P2-2`
- Findings: `Q041 Phase 2` is now fully closed, and the branch has moved from “candidate queue still under active triage” into a more stable **candidate-stratification** state. The most important conclusion is that the shortlist is no longer symmetric. `SPX CSP Δ0.20 DTE30` remains the cleanest formal candidate after surviving the `2022` bear-stress read with only one losing cycle and strong full-window behavior. `GOOGL CSP Δ0.20 DTE21` and `AMZN CSP Δ0.25 DTE21` are now upgraded to **borderline formal candidates**: their Sharpe signals remain strong enough for paper-trading progression, but they still lack `2019–2021 / COVID` tail coverage because Massive pre-2022 history is unavailable. `COST` / `JPM` earnings iron condors are now explicitly downgraded to **observe-only candidates**: alpha signal exists, but the event counts remain too small and the missing pre-2022 / COVID regime means confidence is not high enough for immediate production promotion. `SPX CC DTE45` is fully eliminated and `SPX CSP DTE45` remains observe-only after the overlap-corrected rerun. A separate benchmark-relative comparison further hardens the `CC DTE45` elimination by showing it is not competitive versus either `BXM` or `SPX buy-and-hold` on the tested window. Phase 2 also surfaces one actionable governance clue rather than a full production parameter: `VIX >= 15` improves earnings-IC behavior, while `VIX < 15` behaves like a distinct weak-loss zone
- Risks / Counterarguments: the largest unresolved constraint is still data coverage, not internal inconsistency. Massive pre-2022 S3 access remains blocked by `403 Forbidden`, so `GOOGL / AMZN` and `COST / JPM` cannot yet be promoted with full crisis-history confidence. The earnings-IC branch also remains structurally more fragile than the CSP branch because event counts are small and single earnings gaps can dominate the sample. Finally, overlap validation still matters for the stitched dual-source dataset even though the Phase 2 research queue itself is closed
- Confidence: high on the final candidate ordering for this data window; medium-high on `GOOGL / AMZN` staying interesting but still caveated; medium on earnings-IC promotion potential until either paper-trading evidence or longer history exists
- Next Tests: keep overlap validation running to its formal reconciliation endpoint; prepare paper-trading / monitoring rules for `SPX CSP Δ0.20 DTE30`; if PM wants the next bounded research step inside `Q041`, treat `VIX >= 15` earnings-IC gating and ongoing paper-trading evidence collection as the most practical follow-ons rather than opening another broad scan
- Recommendation: reclassify `Q041` from “Phase 2 queue execution” to **candidate governance and paper-trading preparation**. The leading production-facing order is now: `(1)` `SPX CSP Δ0.20 DTE30`, `(2)` `GOOGL / AMZN CSP` with explicit tail caveat, `(3)` `COST / JPM` earnings IC as observe-only, `(4)` `SPX DTE45` no longer in the active candidate track
- Related Question: `Q041`
- See: `doc/q041_phase2_summary_2026-05-05.md`, `task/q041_phase2_planner_context.md`, `sync/open_questions.md`

### R-20260504-07 — Q041 first formal M1–M10 overlap read is mixed but acceptable; the core comparable subset is converging and the remaining gaps are protocol / semantic cleanup, not source failure

- Topic: Quant first formal `Q041` dual-source overlap assessment under the `M1–M10` protocol
- Findings: The first formal overlap read is **mixed but acceptable**. Both sides landed cleanly at the file / symbol layer: Massive historical parquet is present for `17/17` symbols, and the Schwab forward directory also contains `17/17` symbol parquet plus `_summary.json` and `_underlying.parquet`. The key timing clarification is that although the Schwab directory is stamped `2026-05-03`, the actual comparable session in `_underlying.parquet` maps to the `2026-05-01` post-close state, so the true overlap day for today’s read is `2026-05-01`. Raw full-chain contract-key match is only about `49%`, but Quant’s interpretation is that this is a denominator problem, not a parser or collector failure: Schwab exposes a quoted full chain, while Massive historical behaves more like a traded-only universe. On the economically relevant comparable subset, convergence is already strong: `volume > 0` 4-key match is `99.87%`, `open_interest > 0` 4-key match is `100%`, matched near-ATM / liquid price deviation has median `0.00%` and max `0.13%`, and volume rank correlation is extremely high. Two semantic clarifications are now fixed. First, the apparent `M4` “large price deviation” issue is caused by stale deep-ITM Massive `day_close` rows rather than systematic pricing disagreement, so the `<=2%` gate should be applied only to liquid / price-bearing contracts (for example a `delta 0.10–0.50` region), not the entire chain. Second, Massive IV is stored in **decimal** units while Schwab IV is in **percentage** units, so normalization (`×100`) is required before any direct `M6` numerical comparison. Finally, `SPX` Massive Greeks / IV all-null is now treated as a structural provider limitation for delayed index-option data, not as a correctable collector bug
- Risks / Counterarguments: the main risk is governance, not data loss. If the project keeps using raw full-chain key-match denominator as a hard formal gate, today’s result would be misclassified as non-convergent. That would be the wrong operational read. There are also a few narrower open items left: `M5` still needs same-day rather than cross-day confirmation, historical `SPX/SPXW` should be preserved or reconstructed explicitly instead of inferred only from `underlying`, and Schwab’s `open` field still needs semantic confirmation because it appears all-zero in today’s sample
- Confidence: high that the dual-source path is converging in the contracts that matter for stitching; medium-high that the remaining differences are protocol / semantics cleanup rather than blocker-grade failures
- Next Tests: revise the formal overlap denominator to use traded / price-bearing subsets, normalize Massive IV before `M6` comparison, document or patch the current log-path behavior, confirm Schwab `open` semantics, and continue the overlap clock rather than resetting it
- Recommendation: continue overlap validation. Do **not** treat today as a blocker. Reclassify the active issues as `(1)` denominator / gate cleanup, `(2)` IV-unit normalization, and `(3)` explicit SPX single-source handling for Greeks / IV where Massive structurally cannot supply them
- Related Question: `Q041`
- See: `doc/q041_overlap_validation_protocol_2026-05-03.md`, `sync/open_questions.md`

### R-20260504-06 — Q041 P0-1 benchmark cross-check: corrected SPX CC DTE45 is not competitive versus either BXM or SPX buy-and-hold; this strengthens the elimination decision

- Topic: Quant comparative read of corrected `SPX CC DTE45` against the `D2` benchmark frame (`BXM` and `SPX buy-and-hold`) on the common `2022-05-20 → 2026-04-17` window with `3%` slippage
- Findings: Quant’s follow-up comparison strengthens the `P0-1` decision rather than changing it. On raw `D3 / overlap` numbers, `CC DTE45` looked superficially strong (`Sharpe 1.33–1.48`, cumulative roughly `+102%` to `+114%`), but after overlap correction the strategy falls back to about `Sharpe 1.19–1.25`, annualized return around `10–11%`, cumulative return around `+47%` to `+52%`, and MaxDD around `-15%`. Against `BXM`, that is not a compelling trade: corrected `CC DTE45` produces only slightly higher cumulative return than the official / replicated ATM-call benchmark, but with materially worse drawdown (`~ -15%` versus `~ -9%`) and no clean Sharpe edge over the benchmark frame (`BXM official 1.23`, replicated 1.22). Against `SPX buy-and-hold`, the result is more damaging: corrected `CC DTE45` gives up a large amount of cumulative upside (`~ +47% to +52%` vs buy-and-hold `+82.7%`) while still suffering deeper drawdown (`~ -15%` vs `-12.2%`). Quant’s interpretation is that the apparent OTM covered-call advantage was mostly an artifact of overlap plus a structurally weak tradeoff: the premium is too small to protect downside meaningfully, but assignment / capped-upside still strips away a large share of the bull-market upside
- Risks / Counterarguments: this comparison is still bounded by the same short 2022–2026 window and by close-like execution assumptions. In another regime, covered calls could still look different. But the current decision is not “CC DTE45 is universally impossible”; it is “CC DTE45 is not competitive enough in this tested window to justify keeping it in the formal Phase 2 candidate set.” On that narrower question, the evidence is strong
- Confidence: high. This is not an isolated internal-rule failure anymore; it is a benchmark-relative failure as well
- Next Tests: none for `CC DTE45` in the active candidate queue. Future work, if any, would require a meaningfully different module hypothesis rather than another minor DTE45 tuning pass
- Recommendation: keep `SPX CC DTE45` fully eliminated. Use this benchmark-relative comparison as supporting evidence when explaining why the `P0-1` decision is not just “it missed an internal threshold,” but “it also failed to beat the obvious alternatives on the tested window”
- Related Question: `Q041`
- See: `doc/q041_p2_p01_dte45_overlap_corrected_2026-05-04.md`, `doc/q041_d2_benchmark_replication_2026-05-04.md`

### R-20260504-05 — Q041 Phase 2 P0-1 complete: overlap-corrected rerun eliminates SPX DTE45 covered calls and downgrades SPX DTE45 CSP to observe-only; shortlist remains unchanged

- Topic: Quant completion of `Q041 Phase 2 / P0-1` — overlap-corrected rerun for `SPX DTE45` covered-call / cash-secured-put combinations
- Findings: `doc/q041_p2_p01_dte45_overlap_corrected_2026-05-04.md` closes `P0-1` with a clean directional result. The earlier `DTE45` Sharpe uplift was partly real but materially contaminated by overlap artifact. After re-running all `6` SPX `DTE45` combinations under non-overlapping monthly roll logic and averaging the two relevant alignments, **all covered-call variants fail decisively**: `CC Δ0.20 / 0.25 / 0.30` land around Sharpe `1.19–1.25` with MaxDD near `-15%`, versus the required `Sharpe >= 1.33` and `MaxDD <= -8.96%`. That is enough to eliminate `SPX CC DTE45` from the candidate pool. `CSP DTE45` is more subtle: its mean corrected Sharpe still clears the formal `0.83` line (`1.57 / 1.35 / 1.34` for `Δ0.20 / 0.25 / 0.30`), but the result is **extremely alignment-sensitive**. The decisive example is the `2025-04` tariff-crash cycle: one deep loss (`-$624` on the `Δ0.20` path) is enough to flip one alignment from very strong (`Sharpe 3.22`) to essentially flat (`Sharpe -0.08`). Quant’s interpretation is that this is not production robustness; it is timing luck. Therefore `SPX CSP DTE45` should be downgraded from candidate to **observe-only**, not promoted into production planning
- Risks / Counterarguments: the CSP conclusion is intentionally conservative. Mean Sharpe does pass, so a more risk-seeking interpretation could argue for conditional retention. But the project’s current objective is account-level ROE with explicit stability / tail-cost guardrails, and the one-cycle sensitivity shown here is exactly the kind of fragility that should keep a strategy out of the formal shortlist. The result also depends on a limited four-year regime window, so future longer-history work could still revisit DTE45, but it no longer deserves “active candidate” status now
- Confidence: high on `CC DTE45` elimination; medium-high on `CSP DTE45` downgrade to observe-only; high on the statement that the official Phase 2 shortlist should remain unchanged
- Next Tests: move immediately to `P0-2` (extend COST/JPM earnings-condor history) while keeping `P1-1` IVR filter work and `P1-2` GOOGL/AMZN longer-history validation queued behind it. `DTE45 CSP` can remain in the notebook as an observe-only reference, not a production track
- Recommendation: close `P0-1` as resolved. Remove all SPX `DTE45` combinations from the formal candidate path: `CC` eliminated, `CSP` observe-only. Keep the active shortlist unchanged: `SPX CSP Δ0.20 DTE30`, `GOOGL CSP Δ0.20 DTE21`, and `COST/JPM` earnings iron condors
- Related Question: `Q041`
- See: `doc/q041_p2_p01_dte45_overlap_corrected_2026-05-04.md`, `task/q041_phase2_planner_context.md`

### R-20260504-04 — Q041 Phase 2 P0-1 triage: SPX DTE45 CC/CSP high Sharpe is almost certainly an overlap artifact; mandatory overlap-corrected rerun is now required before any DTE45 candidate can stay in the pool

- Topic: Quant `P0-1` triage on the `Q041 Phase 2` question of whether `SPX DTE45` covered-call / cash-secured-put results are real or inflated by cycle overlap
- Findings: Quant’s conclusion is strong enough to treat the current `DTE45` numbers as **not production-usable yet**. The artifact source is now explicit: the D3 prototype enters a new cycle every monthly `3rd Friday` regardless of whether the prior `45-DTE` position is still open. Because a typical monthly spacing is only `28–35` days, adjacent `DTE45` cycles overlap by roughly `15` days. That means the current `DTE45` accounting effectively lets one BP pool support two partially concurrent cycles without explicitly charging for the second capital commitment. Quant’s read is that this behaves like an implicit `~1.5x` leverage assumption. The most distorted metrics are `(1)` `BP-day ROE` (worst), `(2)` cumulative / annualized return, `(3)` Sharpe, and then `(4)` portfolio-level `MaxDD / CVaR`; `win rate` is largely unaffected. Current standout figures such as `SPX CSP Δ0.20 DTE45 Sharpe 3.03` and `SPX CC DTE45 Sharpe 1.46–1.48` should therefore be treated as provisional only
- Risks / Counterarguments: this does not prove that all `DTE45` alpha is fake; it proves that the current accounting path is contaminated enough that no production or shortlist decision should rely on it. A cleaned rerun may still leave some `DTE45` combinations viable. The main uncertainty after correction is sample size: Quant expects effective cycle count to fall from about `46` to roughly `23–24`, which is still usable but materially weaker statistically
- Confidence: high. The monthly-roll vs `45-DTE` geometry is mechanical, not interpretive, and the direction of distortion is clear
- Next Tests: run a **mandatory overlap-corrected rerun** for exactly `6` SPX combinations: `CC/CSP × Δ0.20 / 0.25 / 0.30`, using the unique recommended rule: only enter a new `DTE45` cycle if the prior cycle has fully expired; otherwise skip that month’s roll date. Keep `DTE21 / DTE30`, single-stock modules, and Module C out of scope. Evaluate `CC` against `Sharpe >= 1.33` and `MaxDD <= -8.96%`, and evaluate `CSP` against `Sharpe >= 0.83` plus `BP-day ROE >= 4.0%`; any corrected run with `N < 20` is automatically downgraded to observe-only
- Recommendation: treat `P0-1` as the immediate `Q041 Phase 2` fast-path task. No `DTE45` candidate should remain on the production-candidate shortlist until the overlap-corrected rerun is complete and written up in a short note / comparison table
- Related Question: `Q041`
- See: `task/q041_phase2_planner_context.md`, `doc/q041_d3_module_ab_backtest_2026-05-04.md`

### R-20260504-03 — Q041 D4 Module C Earnings IV Crush passes conditional; iron condor ex-META viable; implied move premium statistically significant at T-3; META excluded as structural outlier

- Topic: Quant completion of `Q041 Phase 1 / D4 Module C — Earnings Short-Vol Event Study`
- Findings: `doc/q041_d4_module_c_earnings_2026-05-04.md` closes D4 with **Conditional PASS**. The study covered 8 Tier-1 stocks, 120 earnings events from 2022-07 to 2026-03, across entry lags T-1 / T-3 / T-7 and spread types put-spread / iron-condor / condor. Key results: (1) **Implied move premium is statistically significant at T-3**: t-stat 2.67, p=0.009, N=113, mean premium +1.00%. T-1 is borderline (p=0.076). D4 acceptance criterion of t > 2 is met. (2) **Put spread fails across all configurations** — despite 58–65% win rates, directional bets lose because earnings are bidirectional; even ex-META, all put-spread Sharpe are negative. (3) **Iron condor (all stocks) is slightly positive** but weak (Sharpe ~0.2–0.4). (4) **Iron condor ex-META is meaningfully positive**: T-1 w=1.0× Sharpe 0.91, T-3 w=0.5× Sharpe 0.89, ROE/event 8–11%. COST (ROE 25.6%, WR 66.7%) and JPM (ROE 32.8%, WR 77.8%) are the standout candidates. (5) **META is a structural negative outlier**: three historical single-day moves of 21–29% (2022-10-26, 2023-02-01, 2024-02-01) destroy any credit-spread structure; implied-move premium for META is −2.29% (options systematically underestimate META's moves). META is excluded from the production candidate pool. CVaR check for iron condor passes (0.76–1.32× max-loss, all < 3× D4 threshold). (6) Best production candidates entering Phase 2: COST and JPM condors (T-3, width=1.0× implied move)
- Risks / Counterarguments: Phase 1 earnings study relies on hardcoded earnings dates (yfinance API unavailable); dates are cross-validated via large realized moves but a 1-day error on any event would skew results. N per stock is 8–15 events — very small; COST and JPM outstanding results rest on thin statistical power and contain survivorship bias from selecting post-hoc based on performance. The 4-year window has a marked regime shift (2022 bear → 2023–2025 bull) that complicates IV crush consistency inference. Year-over-year instability is real (2024 premium ≈ 0). The condor's correct max-loss calculation required a post-hoc fix; the original script had a max-loss accounting error (double-counting both-sides credit vs single-side spread width) that was corrected in the analysis but not backpropagated to the raw pickle
- Confidence: high on the statistical significance of the implied move premium at T-3; medium on iron condor production viability (COST/JPM only, requires Phase 2 longer-history validation); high on META exclusion as a principled decision; low on the year-to-year stability of the effect
- Next Tests: Phase 2 should extend earnings history to pre-2022 (e.g. using CBOE or alternative data) to confirm premium stability; re-run COST/JPM condor with corrected max-loss formula in the script; add an IV-rank filter (only trade if IVR > 30–50% at T-3) to see if high-IV environments improve the ROE
- Recommendation: advance `Q041 Phase 1` to **COMPLETE** with all four deliverables conditional pass. Production candidate shortlist: (1) SPX CSP Δ0.20 DTE30, (2) GOOGL CSP Δ0.20 DTE21, (3) COST/JPM earnings iron condor T-3 w=1.0×. Full Phase 1 conclusion: PASS WITH CONDITIONS
- Related Question: `Q041`
- See: `doc/q041_d4_module_c_earnings_2026-05-04.md`, `doc/q041_d3_module_ab_backtest_2026-05-04.md`

### R-20260504-02 — Q041 D3 Module A/B Conservative Backtest completes; SPX CSP Δ0.20 DTE30 edges past Sharpe target; GOOGL/AMZN CSP are standout individual-stock candidates; JPM CC high return explained; JPM CSP is a cautionary negative

- Topic: Quant completion of `Q041 Phase 1 / D3 Module A/B Conservative Backtest`
- Findings: `doc/q041_d3_module_ab_backtest_2026-05-04.md` closes D3 with a **Conditional PASS**. The sweep covered 3 × delta (0.20/0.25/0.30) × 3 × DTE (21/30/45) for both CC and CSP on SPX (18 combos), plus 12 combos × 9 Tier-1 stocks and ETFs (108 combos). Key results: (1) SPX CC — DTE21/30 all fail the Sharpe ≥ 1.33 target (max 0.99); DTE45 passes (1.46–1.48) but introduces ~15-day cycle overlaps that inflate the reported Sharpe. (2) SPX CSP Δ0.20 DTE30 — Sharpe 0.85, just over the 0.83 target, with MaxDD −4.6% and CVaR −3.5%, but BP-day ROE ~3.4% is slightly below the 4.0% threshold; a marginal pass on 3/4 criteria. (3) SPX CSP DTE45 — dominates all metrics (Sharpe 3.03 for Δ0.20) but requires overlap-corrected roll logic before production use. (4) Individual stocks — GOOGL CSP Δ0.20 DTE21 is the standout (Sharpe 2.28, MaxDD −4.7%, WR 91%); AMZN CSP DTE21 close behind (Sharpe 1.49–1.50). (5) JPM CC +328–400% cumulative is verified legitimate: JPM rose $109 → $312 (+187%), very OTM calls almost never exercised, stock appreciation + premium compound to outsized returns — this is bull-market beta, not premium alpha. (6) JPM CSP is consistently negative (Sharpe −0.80 to −0.97, DTE21) due to asymmetric bank-sector drawdowns in the 2023 regional banking crisis; confirmed that financial-sector single-stock CSP carries idiosyncratic tail risk absent from index strategies
- Risks / Counterarguments: D3 carries forward the same bull-market-regime caveat from D2 — the entire 2022-05 → 2026-04 window is net strongly bullish and the CSP strategies structurally benefit from it. DTE45 overlap is a real accounting artifact that needs an explicit non-overlapping roll model before these numbers can be trusted in production. Individual-stock CC returns are dominated by stock appreciation and should not be read as evidence that OTM call selling alone adds Sharpe; they are better interpreted as a "reduced-drag overlay on a long stock position." The WMT results rest on only N=25 cycles (~2 years) and have low statistical power. The N=47 sample for most combos also gives wide confidence intervals on Sharpe
- Confidence: high on SPX CSP Δ0.20 DTE30 as a viable Module B candidate; medium-high on GOOGL/AMZN CSP as elevated-Sharpe individual-stock candidates pending longer sample; medium on overall regime stability outside this specific bull window; high on the JPM CSP negative result as a real risk signal for financial-sector CSP
- Next Tests: (a) enter D4 Module C Earnings IV Crush Event Study using the same historical pipeline; (b) add non-overlapping roll logic to re-run DTE45 combos properly; (c) validate GOOGL/AMZN CSP with a longer historical sample if data can be extended pre-2022
- Recommendation: advance `Q041 Phase 1` from **D3-ready** to **D3 CONDITIONAL PASS / D4-ready**. Production candidate pool: SPX CSP Δ0.20 DTE30 as baseline; GOOGL Δ0.20 DTE21 CSP as high-Sharpe satellite. Exclude JPM from the CSP pool. Defer DTE45 combos until overlap logic is fixed
- Related Question: `Q041`
- See: `doc/q041_d3_module_ab_backtest_2026-05-04.md`, `doc/q041_d2_benchmark_replication_2026-05-04.md`

### R-20260504-01 — Q041 D2 benchmark replication passes; BXM/ATM-CSP baselines are now fixed and D3 can start

- Topic: Quant completion of `Q041 Phase 1 / D2 Benchmark Replication`
- Findings: `doc/q041_d2_benchmark_replication_2026-05-04.md` closes D2 with an explicit **PASS**. The core result is that the historical SPX benchmark pipeline is now validated strongly enough to support D3 module work. The replicated monthly `ATM covered call` track (`BXM` analog) achieves `0.9715` monthly return correlation to the official benchmark, `0.43%` MAE per cycle, and only `-1.24%` cumulative drift over roughly four years. That is good enough to treat the data pipeline, ATM strike selection, and P&L accounting as operationally trustworthy for Phase 1 comparisons. The report also fixes the concrete baseline numbers that D3 must now beat: official `BXM` Sharpe `1.23`, replicated `BXM` Sharpe `1.22` un-slipped / `1.14` at `3%` slippage, and `ATM CSP` Sharpe `0.81` un-slipped / `0.73` at `3%` slippage. Structural interpretation is also now cleaner: in this bull-biased `2022-05 → 2026-04` window, covered-call overlays lagged SPX in absolute return every year but delivered higher Sharpe and shallower drawdown, while ATM CSP produced a cleaner premium-harvest profile with `76.6%` win rate and annualized BP-day ROE around `+4.15%` before slippage
- Risks / Counterarguments: D2 passing does not mean the benchmark is perfect or production-executable. The replication still uses `PM close` rather than the official BXM `AM settlement`, has no historical bid/ask, and lives inside a short `47-cycle` sample dominated by a strong bull regime after the 2022 drawdown. So the benchmark is good enough for relative module comparison, but not a claim of institutional-grade index replication. D3 comparisons must continue to state that benchmark PnL is based on close-like execution assumptions and a limited four-year window
- Confidence: high on D2 as a benchmark-validation gate; medium-high on the baseline Sharpe / drawdown numbers as planning anchors for D3; medium on the long-run stability of conclusions outside this specific market regime
- Next Tests: start `D3 Module A/B` with the newly fixed benchmark thresholds. Current target gates are now explicit: covered-call module should aim to exceed the benchmark by about `+0.10` Sharpe (`>= 1.33` target vs official `1.23`), while the CSP branch should target at least `0.83` Sharpe and `>= 4.0%` annualized BP-day ROE under the stated slippage assumptions
- Recommendation: advance `Q041 Phase 1` from **D2-ready** to **D2 PASS / D3-ready**. Treat the new BXM / ATM-CSP results as the canonical comparison frame for Module A / B work, while keeping overlap validation for the stitched dual-source dataset running in parallel on its own schedule
- Related Question: `Q041`
- See: `doc/q041_d2_benchmark_replication_2026-05-04.md`, `doc/q041_d1_data_sanity_report_2026-05-03.md`, `doc/q041_phase1_design_GPTreview.md`, `sync/open_questions.md`

### R-20260503-13 — Q041 D1 Data Sanity passes; historical parquet is clean enough to enter D2 benchmark replication

- Topic: Quant completion of `Q041 Phase 1 / D1 Data Sanity` on `data/q041_historical/`
- Findings: `doc/q041_d1_data_sanity_report_2026-05-03.md` now closes D1 with an explicit **PASS**. Across the full 17-symbol whitelist, historical Massive `day_aggs_v1` parquet coverage is effectively complete at the current Phase 1 horizon: `17/17` symbols have ~`1,000` trading-day coverage, with zero null closes, zero negative prices, and zero OHLC ordering violations. The report identifies three SPX holiday anomalies (`2022-05-30`, `2022-06-20`, `2022-07-04`) and records them as a market-calendar filtering issue rather than a dataset failure. Stale-price behavior is present but bounded: after excluding penny contracts, stale-close incidence is roughly `0.78%–2.60%`, with about `65%` of stale rows concentrated in very low-priced contracts. BS IV inversion in the intended liquid region is judged operationally viable (`92.8%` valid on the AAPL sample, no `>200%` outliers, plausible `18%–76%` range), and the structure checks also pass: call-delta monotonicity holds and put-call parity error remains `<2%`. One AMZN single-day anomaly (`2025-10-31`, only `37` rows, 0-DTE only) is now explicitly recorded as non-blocking. Quant also fixed four practical Phase 1 filtering rules (`F1–F4`) to carry into downstream work
- Risks / Counterarguments: this is a D1 cleanliness pass, not a green light to ignore the larger dual-source caveats. The report does not change the prior conclusion that historical Massive data still lacks native `Greeks / IV / OI`, and it does not replace the stitched-dataset overlap validation work. The BS/BAW path is promising in the target region, but derived IV / Greeks remain model-based estimates, not newly discovered historical truth. The identified holiday rows and sparse-name anomalies also mean downstream modules must actually honor the new filters rather than merely cite them
- Confidence: high on D1 passing as a historical-data sanity gate; medium-high on BS IV reconstruction being good enough for the intended liquid near-ATM use cases; medium on how much later modules will need additional model-based enrichment beyond D1
- Next Tests: start `D2` benchmark replication immediately on the historical parquet using filters `F1–F4`; preserve overlap validation as the stitched-dataset admission track in parallel. Keep the AMZN anomaly and SPX holiday dates in the benchmark / module-A validation notebook so any concentrated effect can be traced back cleanly
- Recommendation: advance `Q041 Phase 1` from **D1-ready** to **D1 PASS / D2-ready**. Treat `D2 BXM/PUT benchmark replication` as the next active research deliverable while keeping the dual-source overlap-validation program running on its own schedule
- Related Question: `Q041`
- See: `doc/q041_d1_data_sanity_report_2026-05-03.md`, `doc/q041_phase1_design_GPTreview.md`, `sync/open_questions.md`

### R-20260503-12 — Q041 dual-source final reading: historical Greeks/IV/OI remain unavailable; recent snapshot fields can accumulate forward; BS/BAW backfill is feasible but should stay on hold

- Topic: Quant final synthesis on the practical meaning of the Massive historical path plus daily snapshot accumulation for `Q041`
- Findings: Quant’s latest conclusion does **not** overturn the current alignment or overlap-validation framing; it sharpens it. The project now has a clean two-source interpretation. For the **historical segment** (`~2022–2026`), Massive `day_aggs` provides usable `OHLCV` but still does **not** provide historical `Greeks / IV / OI`, and the Developer plan cannot backfill them. For the **recent segment** (from now forward), `Greeks / IV / OI` can accumulate day by day through current snapshot sources (Massive current snapshot or Schwab forward collection under `SPEC-082`). `open_interest` is specifically an end-of-day snapshot value, so it can build a forward history from today onward, but it cannot be retroactively reconstructed for the historical window. Quant also confirms a technically credible fallback: historical `IV` and Greeks can be numerically inferred from option close, underlying close, strike, expiry, and a risk-free-rate assumption using `Black-Scholes` for European contracts and `Barone-Adesi-Whaley` for American equity options. This is expected to be usable on liquid contracts in the intended research zone (`ATM ±20%`, moderate `DTE`), but not reliable for deep `ITM/OTM`, zero-volume, or stale-close contracts
- Risks / Counterarguments: this should not trigger immediate scope expansion. The same facts that make BS/BAW inversion possible also make it fragile: option close is not guaranteed to be executable mid, American exercise premia matter on single-name equity options, and bad closes can make IV inversion fail entirely. Schwab’s own `-999` IV sentinel is a useful warning that naive inversion can break. For that reason, Quant’s recommendation is to **hold** the historical-greeks backfill idea for now. The current alignment note and overlap protocol remain correct as written, and the project should not add a derived-greeks layer until Phase 1 design explicitly proves it is needed
- Confidence: high on the source split (`historical OHLCV only` vs `recent snapshot fields accumulate forward`); medium-high on BS/BAW feasibility in the intended liquid near-ATM region; medium on whether Phase 1 will actually require the inferred-greeks layer
- Next Tests: keep overlap validation and historical data sanity as the active work. During Phase 1 design, decide whether any module truly needs historical Greeks / IV. If yes, open a separate prototype path (for example `enrich_greeks.py`) rather than modifying the current dual-source collection flow
- Recommendation: keep `Q041` in **overlap validation**, but allow `Phase 1 / D1 Data Sanity` to proceed now on `data/q041_historical/`. Preserve the current constraints explicitly: historical `Greeks / IV / OI` unavailable, recent snapshot fields forward-only, and BS/BAW enrichment deferred
- Related Question: `Q041`
- See: `doc/q041_data_alignment_note_2026-05-03.md`, `doc/q041_overlap_validation_protocol_2026-05-03.md`, `doc/q041_phase1_design_GPTreview.md`, `sync/open_questions.md`

### R-20260503-11 — Q041 Phase 1 design reviewed by external Quant; restructured into 4 deliverables with module order A→B→C; D1 Data Sanity is next

- Topic: Quant review of GPT external quant review of `doc/q041_phase1_design_2026-05-03.md`; Phase 1 restructuring and D1 entry
- Findings: Phase 1 design document was submitted to GPT for external quant review. Quant has now reviewed the GPT findings and accepted the substantive changes. The key structural change is that Phase 1 is now formally restructured into **4 sequential deliverables**: `D1 Data Sanity Report` → `D2 Benchmark Replication` → `D3 Module A/B Conservative Backtest` → `D4 Module C Event Study`. Module ordering is now `A (Covered Call) → B (CSP) → C (Earnings IV Crush)`, reversing the original C-first plan. Module C was correctly identified by the GPT review as requiring the most data infrastructure (IV surface, accurate spread pricing) and should be addressed after the simpler modules validate the data pipeline. Additional accepted changes: (1) slippage/transaction cost model required before any backtest — option close ≠ executable mid; (2) 3-layer BP definition (standalone BP / sleeve BP / account marginal BP) must be explicit, with marginal $/BP-day as the primary ROE metric; (3) whitelist split into Tier 1 core (`AAPL MSFT AMZN GOOGL META JPM WMT COST QQQ SPX`), Tier 2 high-vol (`NVDA TSLA AMD PANW`), Tier 3 observe (`ASML TSM BRK/B`); (4) Module C CVaR rule corrected — defined-risk spread cannot exceed max loss by design; position-sizing constraint rewritten as account-level earnings-week exposure cap. **Quant minor disagreement**: `BRK/B` should remain Tier 2 (liquidity check pending), not Tier 3. Vol surface flagged as significant issue for Module B put-skew analysis but not a full blocker at Phase 1 level. Overlap validation note: Quant confirmed Phase 1 historical-only backtest does NOT require completion of the 20-day overlap reconciliation window — that window applies only to forward stitching. D1 can proceed now using `data/q041_historical/` only
- Risks / Counterarguments: the 4-year window (2022-05 to 2026-05) remains a structural risk; this dataset contains one significant bear market (2022) and a strong bull market (2023–2025), so any parameter conclusions will require explicit out-of-sample caveats. The lack of historical bid/ask means all backtest PnL numbers are best-case estimates that will overstate alpha vs. real execution. Historical Greeks / IV / OI are unavailable from Massive day_aggs — confirmed definitively by live testing (Developer plan: all non-day_aggs S3 paths return 403; REST API snapshot endpoint is current-only, no `as_of` support). BAW imputation will be needed for any delta or IV targeting in Phase 1
- Confidence: high that the 4-deliverable structure is correct; high that D1 Data Sanity is the right entry point; medium on whether 4 years of data will produce statistically robust conclusions for all three modules
- Next Tests: execute D1 Data Sanity Report against `data/q041_historical/` parquet files — option close abnormality check, stale price detection, moneyness-DTE coverage map, zero/low-volume filter thresholds, BAW IV reconstruction sanity range, delta monotonicity check, put-call parity spot-check
- Recommendation: treat `Q041` as now in **Phase 1 / D1 Data Sanity** stage. Overlap validation continues in background (target `2026-05-30` Reconciliation Report) but is not a blocker for D1 work on historical parquet data. All Phase 1 reports must include the standard metrics pack: PnL/BP-day, marginal $/BP-day, win rate, avg win/loss, worst trade, disaster window, max BP%, CVaR 5%, Sharpe, benchmark alpha
- Related Question: `Q041`
- See: `doc/q041_phase1_design_2026-05-03.md`, `doc/q041_phase1_design_GPTreview.md`, `task/SPEC-081.md`, `task/SPEC-082.md`, `sync/open_questions.md`

### R-20260503-10 — SPEC-081 and SPEC-082 are now closed DONE; Q041 moves from schema build-out into formal overlap validation

- Topic: Quant review of `SPEC-081` / `SPEC-082` and final readiness state for the `Q041` hybrid data path
- Findings: Quant has now reviewed both implementation branches and judged them closed enough to treat as **DONE**. `SPEC-081` passes its intended role as the Massive historical bulk-download path; `SPEC-082` also passes at the code / collection level, but with an important interpretation update: the previously reported AC3/AC4 failures were not implementation failures, they were spec-level assumption errors. Quant has already applied a Fast Path cleanup in `collect_chains.py` to null out Schwab’s `iv=-999` sentinel values, and the current expiry-type interpretation is now updated to Schwab’s actual semantics: `W = Weekly`, `S = Standard monthly`, `Q = Quarterly`, and `M = End-of-month` (rare). The practical consequence is that `Q041` should no longer be framed as “waiting for SPEC-081/082”; those collection specs are closed, and the branch has now advanced into the formally defined overlap-validation stage
- Risks / Counterarguments: closing `SPEC-081/082` does not mean the full `Q041` dataset is already PM-ready. The remaining work is no longer collection plumbing but reconciliation discipline: daily / weekly overlap checks, symbol normalization stability, price / volume behavior, and ensuring the newly clarified IV / expiry_type semantics are reflected consistently in downstream validation scripts and reports. The project should also keep the historical-data limitation explicit: Massive historical `day_aggs` still does not provide historical Greeks / IV / OI, so “SPEC done” does not mean “full Phase 1 substrate complete”
- Confidence: high on the closure of the two specs as implementation tasks; high that the remaining blocker is now the overlap-reconciliation program rather than missing collector capability
- Next Tests: run the overlap-validation protocol for the defined `20` trading-day window, apply the `10` day remediation buffer if needed, and produce the per-symbol `Q041 Reconciliation Report` for PM review
- Recommendation: mark `SPEC-081` and `SPEC-082` as **DONE** and treat `Q041` as fully in **overlap validation / reconciliation mode**. Future indexing should stop describing Schwab IV as “not collected” and instead describe it as “collected, sentinel-cleaned, and semantically constrained”
- Related Question: `Q041`
- See: `doc/q041_overlap_validation_protocol_2026-05-03.md`, `doc/q041_data_alignment_note_2026-05-03.md`, `task/SPEC-081.md`, `task/SPEC-082.md`, `task/SPEC-082_handoff.md`, `sync/open_questions.md`

### R-20260503-09 — Q041 overlap validation should run as a 20-trading-day formal check plus a 10-day remediation buffer

- Topic: Quant `Q041` overlap validation / reconciliation protocol for Massive historical data plus Schwab forward collection
- Findings: Quant has now fixed the operational shape of the `Q041` alignment phase. The recommended overlap program is not a vague “watch both feeds for a while,” but a specific **20 trading day formal validation window** followed by a **10 calendar / trading day remediation-and-recheck buffer** before Massive access expires. Quant’s key reasoning is that `10–15` trading days is too short to cover month-roll and lower-frequency names (`ASML / TSM / PANW`), while using the full `30` trading days as pure observation leaves too little room to correct discovered schema issues. The most important continuous metrics are no longer just “did files land,” but `(1)` symbol / expiry / strike match rates, `(2)` price deviation behavior, and `(3)` volume rank correlation, with weekly manual checks for IV-unit semantics and DST / timestamp consistency. The intended PM-facing artifact at the end of the window is a per-symbol **Reconciliation Report / Table** that becomes the sole admission document for Phase 1
- Risks / Counterarguments: the main risk is conflating field presence with field trustworthiness. Even after `SPEC-082`, Schwab forward parquet now contains IV / full Greeks locally, but the data is not yet semantically clean enough to be trusted automatically (`iv=-999` sentinels, large IV outliers, and `expiry_type` reinterpretation still open). Another risk is allowing overlap to drift without fixed acceptance gates; Quant’s protocol explicitly says some differences are absorbable (e.g. volume level mismatch handled by rank, Massive T+1 delay, expected historical nulls), while others should block stitching outright (e.g. symbol match `<85%`, price gap `>5%`, expiry/strike key errors, unresolved IV-unit confusion, large SPX/SPXW row-count divergence)
- Confidence: high on the overlap-window design and reconciliation categories; medium-high that this is enough to decide Phase 1 entry once the current IV / expiry-type semantic cleanup finishes
- Next Tests: start the overlap clock immediately after `SPEC-081/082` outputs are available, run daily automated checks on match rates / price / volume behavior, perform weekly manual reviews on IV units and DST handling, and target a formal `Q041 Reconciliation Report` around `2026-05-30`
- Recommendation: keep `Q041` in **Gate 0 pass with constraints / alignment phase**, but now treat that phase as operationally defined: `20` trading days of formal overlap validation, then `10` days reserved for fixes and re-validation. Phase 1 should not begin before the Reconciliation Report clears all checklist items
- Related Question: `Q041`
- See: `doc/q041_overlap_validation_protocol_2026-05-03.md`, `doc/q041_data_alignment_note_2026-05-03.md`, `sync/open_questions.md`

### R-20260503-08 — Q041 hybrid path is ready to collect and align, but IV remains a hard pre-Phase-1 constraint

- Topic: Quant `Q041` data-alignment / stitching note for Massive historical data plus Schwab forward collection
- Findings: Quant has now moved `Q041` one step past raw Gate-0 feasibility and into a concrete **alignment phase**. The hybrid path itself is judged workable: Massive can serve as the historical canonical source and Schwab as the recent forward canonical source, with an overlap window used only for reconciliation. Symbol / contract normalization is now explicit enough to be operationalized, including `SPX` vs `SPXW`, `BRK/B` file naming, and `FB -> META` rename handling. This is enough to say the project is **ready to collect and align** rather than merely waiting on provider access. However, the most important new result is a field-level constraint: Massive `day_aggs` historical data does **not** provide historical Greeks / IV / OI, and the current Schwab forward collector parquet also does **not yet surface IV**. So the real blocker before any IV-sensitive Phase-1 modeling is no longer account access, but schema completeness and explicit downgrade rules
- Risks / Counterarguments: the danger now is a category mistake: assuming “two sources can be stitched” means “the resulting research dataset is complete.” It is not. The current hybrid path is sufficient for OHLCV / close / volume-based constrained research, but not yet for any design that implicitly assumes historical IV, historical delta targeting, or OI-based filters. Another risk is starting downloads before the canonical stitching rules are fixed; that would create avoidable rework and muddy later overlap validation
- Confidence: high that the stitching design is directionally correct; high that IV is the next hard issue to resolve; medium on whether the final hybrid dataset will be enough for the full intended Q041 scope without later supplementation
- Next Tests: `(1)` execute the Massive historical bulk download and local conversion path, `(2)` verify whether Schwab raw chain responses already contain IV / full Greeks fields that are currently being dropped, and `(3)` run the overlap validation window before allowing Phase 1 modeling to begin
- Recommendation: keep `Q041` at **Gate 0 pass with constraints / alignment phase**. Allow bounded data collection now, but do not yet declare the branch ready for Phase 1 backtesting until the IV/schema question is explicitly resolved
- Related Question: `Q041`
- See: `doc/q041_data_alignment_note_2026-05-03.md`, `research/q041/collect_chains.py`, `task/SPEC-081.md`, `task/SPEC-082.md`, `sync/open_questions.md`

### R-20260503-07 — Q041 Gate 0 now passes with constraints via a hybrid Massive historical path plus Schwab forward collection

- Topic: Quant / PM update on `Q041` historical-data sourcing
- Findings: `Q041` has now moved beyond pure data-feasibility uncertainty into an executable acquisition path. PM opened a Massive.com `Options Developer` account on `2026-05-03` with the explicit strategy of using it as a one-time historical download source, then canceling. This changes the practical Gate 0 answer from “still unproven” to **PASS WITH CONSTRAINTS**. Massive now provides a viable historical path for the whitelist using U.S. options-market coverage (via `OPRA`), with EOD aggregates and S3 flat-file delivery. **[Correction added R-20260503-11: the original claim "with greeks, IV, OI" was based on the Massive product description and was wrong. Live testing confirmed that the Developer plan `day_aggs_v1` path contains only OHLCV + volume + transactions — no Greeks, no IV, no OI. All non-day_aggs S3 paths return 403 on Developer plan. Massive REST snapshot API returns current-data Greeks/IV/OI only, with no historical `as_of` support.]** In parallel, the Schwab-based forward collector already deployed on old Air continues to accumulate fresh daily chain snapshots from `2026-05-03` onward. Quant’s intended research path is therefore hybrid: Massive for bounded historical backfill (`~2022–2026`) and Schwab for forward continuation. Pre-upgrade validation already confirmed that symbol reference coverage works for the full 17-symbol candidate set, including `SPXW` and `BRK/B`
- Risks / Counterarguments: the constraint is substantial and must remain explicit. Massive’s Developer plan currently provides only about `4` years of historical depth rather than the originally preferred `~2004–2026` span, and it does **not** include historical bid/ask quote history on this plan. This means Gate 0 is not a full institutional-history green light; it is a bounded pass that enables Phase 1 only if the project is willing to accept a shorter historical window and use trade-based / aggregate substitutes where quote history would otherwise be ideal. `/ES` also remains outside this path because Schwab’s chains endpoint rejects futures options and the Massive decision here does not solve that separate futures-options sourcing problem
- Confidence: medium-high that the hybrid data path is sufficient to begin a constrained Phase 1; medium that it will be sufficient for the final intended research scope without later supplementation
- Next Tests: perform the Massive bulk download, convert/store into `data/q041_historical/`, validate field completeness for greeks / IV / OI, run the first weekday Schwab collector auto-cycle, and document the combined data window before any real Phase-1 backtest claims are made
- Recommendation: treat `Q041 Gate 0` as **PASS WITH CONSTRAINTS**. Allow bounded historical acquisition and Phase-1 preparation to start, but keep the shorter window and lack of historical bid/ask quotes explicit in every future result
- Related Question: `Q041`
- See: `research/q041/collect_chains.py`, `research/q041/whitelist.py`, `.env`, `sync/open_questions.md`

### R-20260503-06 — Q041 Gate 0 forward collection is now technically viable for equities plus SPX/QQQ, but still does not clear the historical-data gate

- Topic: Quant refinement of the `Q041` forward-collection scaffold
- Findings: Quant has advanced `Q041 Gate 0` beyond the initial scaffold by resolving the largest practical collection issue on the HC path. The main bug was `SPX` chain collection through Schwab: the default request shape overflowed the gateway body buffer because `$SPX` combines very dense strike spacing (`5-point` increments) with a large multi-expiry window. This is now fixed by giving `$SPX` its own narrower request envelope (`strikeCount=100`, `DTE=180d`), which still returns enough useful structure for main-strategy chain accumulation (`~40` expiries, `4159` calls). At the same time, Quant confirmed that `/ES` futures options should be removed from this Schwab-based forward path entirely: Schwab’s `/marketdata/v1/chains` endpoint rejects futures option symbols with `400 Bad Request`, so any `/ES` options work would require a separate data source such as CME DataSuite or a third-party vendor. The active forward whitelist is therefore now `12` symbols: the `10` large-cap equity-income candidates plus `SPX` and `QQQ`. Estimated collection scale is about `45K` rows and `~800KB` parquet per day
- Risks / Counterarguments: this is still only a forward-collection result, not a historical-feasibility result. `Q041` remains blocked on the deeper Gate 0 question: whether acceptable long-history per-name options data exists for the intended research horizon. There are also a few operational unknowns left for first real runs, including `BRK/B` symbol handling, weekday scheduler behavior, and whether any symbols intermittently produce sparse or malformed outputs
- Confidence: high that the forward-collection path itself is now workable for equities plus `SPX/QQQ`; low-to-medium that Gate 0 as a whole is cleared
- Next Tests: let the weekday `16:30 ET` collector run, verify all `12` symbols write successfully, confirm `BRK/B -> BRK_B.parquet`, inspect structured logs, and keep `/ES` explicitly out of this Schwab-based path until a separate data-source decision is made
- Recommendation: keep `Q041` at **Gate 0 in progress**. Do not allocate Phase 1 modeling yet, but treat the forward collector as a meaningful infrastructure step rather than a pure placeholder
- Related Question: `Q041`
- See: `research/q041/collect_chains.py`, `research/q041/whitelist.py`, `sync/open_questions.md`

### R-20260503-05 — Q041 Gate 0 moves from pure theory to active data-infrastructure work, but historical feasibility is still unproven

- Topic: Quant forward-collection scaffold for `Q041` / `Large-Cap Equity Option Income Overlay`
- Findings: Quant has now completed the HC-side forward-collection scaffold for `Q041`. The delivered package includes a fixed 10-name whitelist (`AAPL / MSFT / AMZN / GOOGL / META / NVDA / BRK_B / WMT / COST / JPM`), a daily chain collector (`research/q041/collect_chains.py`), a host-local weekday `16:30` launchd schedule, parquet output under `data/q041_chains/YYYY-MM-DD/`, and the required environment support (`pyarrow>=15`, `.gitignore` rule). The scaffold stays within the agreed fence: no changes to `engine.py`, strategy logic, signals, web, bot, or Schwab trading code; only read-only reuse of Schwab auth / chain-parsing helpers. Smoke test on `AAPL --force` succeeded with `2462` rows across `20` expiries and realistic storage sizing (`~700 KB/day` full whitelist, `~175 MB/year`). This is enough to move `Q041 Gate 0` from a purely conceptual blocker into active data-infrastructure work
- Risks / Counterarguments: this does **not** yet prove the full Gate 0. The current scaffold only establishes that forward collection on HC is feasible. The branch still lacks confirmed historical per-name options coverage for the intended `~2004–2026` research window, which remains the actual gating requirement before any Phase 1 modeling. There are also operational caveats: `BRK/B` symbol-format handling still needs first-run confirmation, launchd will still fire on market holidays unless later filtered, and current Schwab-returned expiry depth is closer to ~10 months than long-dated LEAPS
- Confidence: high that the forward-collection scaffold itself is sound; low-to-medium that Gate 0 is fully cleared until real weekday runs and the historical-data question are both resolved
- Next Tests: manually load the launch agent, observe the first weekday run, confirm 10-symbol parquet coverage plus `_summary.json`, inspect `logs/q041_collect*.log`, and separately resolve whether acceptable historical per-name options data exists for the intended long window
- Recommendation: treat `Q041` as **Gate 0 in progress**, not Gate 0 passed. Do not allocate Phase 1 modeling bandwidth yet
- Related Question: `Q041`
- See: `research/q041/collect_chains.py`, `research/q041/whitelist.py`, `research/strategies/Large-Cap Equity Option Income Overlay/Large-Cap Equity Option Income Overlay.md`, `sync/open_questions.md`

### R-20260503-04 — Q038 shadow should be governed as a live-observability check, not as an alpha proof

- Topic: Quant shadow-monitoring protocol for `Q038` / Path C after old Air moved to live `shadow`
- Findings: Quant’s conclusion is that the current `Q038` observation period has a narrow governance purpose: validate that the Path C logic behaves correctly inside the live recommendation path, produces reviewable artifacts, avoids false positives, and introduces no side effects to recommendation / bot / web behavior. The shadow period is **not** meant to prove strategy alpha or justify `active` on economics alone. For `SPEC-079`, the live-observable target is clear: `data/bcd_filter_shadow.jsonl` should show semantically correct `risk_score` evaluation, with `would_block=true` only when the three intended conditions are jointly satisfied (`VIX <= 15`, `dist_30d_high_pct <= -1%`, `ma_gap_pct > 1.5pp`). Quant explicitly notes that “having logs” is not enough; the important question is whether the logs correspond to the intended BCD risk environment and whether recommendation outcomes stay unchanged under `shadow`. For `SPEC-080`, Quant sets a strict boundary: current HC shadow there is posture alignment plus engine/backtest observability, not a naturally rich live stop-event stream. Absence of live stop-shadow events should therefore be treated as expected, not as deployment failure
- Risks / Counterarguments: the main governance risk is not missing logs but misreading them. Shadow evidence can be misleading if bot / dashboard interpret would-fire as actual size-up, or if PM infers too much from a small number of events. Another risk is that a short observation window may yield too few BCD candidates to judge edge cases; Quant recommends treating sparse-but-clean logs as healthier than high-volume noisy triggers
- Confidence: high. This is a governance and observability protocol, not a new hypothesis test
- Next Tests: use a minimum 4-week observation window (ideally 4–8 weeks), review weekly plus event-driven quick checks on BCD candidate days or near-threshold market days, and summarize each window with runtime health, `risk_score` distribution, `would_block=true` count, false-positive scan, and side-effect scan. Only discuss `active` if the observation window is clean, semantically correct, and side-effect free
- Recommendation: keep `Q038` strictly in monitoring governance. Do not reinterpret the branch, do not treat shadow logs as alpha proof, and do not use `SPEC-080` live-stop silence as evidence either way
- Related Question: `Q038`
- See: `task/SPEC-079.md`, `task/SPEC-080.md`, `SERVER_RUNTIME.md`, `doc/old_air_server_maintainer.md`, `sync/open_questions.md`

### R-20260503-03 — Q036 adoption-fit review: MC core structure is adoptable, but HC should add one more local clarification layer before Developer planning

- Topic: Quant adoption-fit / acceptance-clarification review for `SPEC-075 / SPEC-076`
- Findings: Quant’s verdict is neither “not ready” nor “hand it directly to Developer.” The MC package is directionally correct and structurally usable, but HC should not implement it as an unchanged bundle. `SPEC-075` should keep MC’s core logic shape — `Overlay-F` restricted to `IC_HV`, `idle_bp_pct >= 0.70`, `VIX < 30`, `short-gamma count < 2`, with `disabled / shadow / active` posture and active-envelope tolerance bands — while HC adds stricter local adoption guardrails: `(1)` productization semantics must use **position-count** short-gamma, not family-dedup; `(2)` any missing / stale live state must **fail closed**; `(3)` disabled mode must remain fully inert in recommendation behavior; `(4)` the MC-to-HC file-path mapping must be explicitly written down; and `(5)` backtest vs live portfolio-state builders need consistency checking. For `SPEC-076`, telemetry / dashboard / review-protocol adoption is also judged structurally correct, but Quant requires that shadow evidence be explicit before any future active discussion: shadow fires should stay log-only, produce complete context (`date`, `strategy`, `VIX`, `idle BP`, `SG count`, `mode`, `effective factor`, rationale), and never be misrepresented by bot / dashboard as actual size-up. The net result is: **one more Quant clarification pass is needed**, but it is an HC-local acceptance / guardrail pass, not a reopened research branch
- Risks / Counterarguments: the largest remaining risk is not alpha validity but rollout inconsistency. If overlay hook, runtime payload, telemetry, dashboard, and bot do not share the same overlay-state interpretation, HC could pass backtests while still drifting in live recommendation behavior. Another risk is that stale or missing live state could accidentally produce false positives unless the branch is explicitly fail-closed
- Confidence: high. This is a clean boundary-setting review rather than an open-ended strategy argument
- Next Tests: update the HC local `SPEC-075 / SPEC-076` skeletons and adoption note to encode the clarified guardrails, then route the batch to Developer planning. No new overlay-alpha research is needed first
- Recommendation: keep `Q036` on the implementation-planning track, but do not yet call it `ready for Developer planning` until the local acceptance / evidence layer is written down
- Related Question: `Q036`
- See: `task/SPEC-075.md`, `task/SPEC-076.md`, `sync/mc_to_hc/SPEC-075_076_adoption_note.md`, `sync/mc_to_hc/MC Response 2026-05-02_v2.md`

### R-20260503-02 — Q041 passes theory screening and enters the research pool, but only behind a Gate 0 data-feasibility check

- Topic: Formal Quant evaluation of `Large-Cap Equity Option Income Overlay`
- Findings: Quant’s conclusion is that the source material is not just social-media noise, but it is also not a directly actionable strategy package. Three components are worth institutional research treatment: `(1)` mega-cap covered call overlay on core holdings, `(2)` cash-secured put writing on a tightly governed high-quality whitelist, and `(3)` defined-risk earnings short-vol structures that monetize post-earnings IV crush. At the same time, several elements are explicitly not admissible into formal research: naked earnings short options, discretionary `RSI 99` reversal shorts, single-name event reversal bets, and “monthly premium harvested” as a KPI. The key reframing is that this should be treated as a separate `equity-income sleeve`, not as an extension of the current SPX engine. However, the branch is not yet ready for Phase 1 modeling because the project currently lacks confirmed historical per-name options data infrastructure. Quant therefore sets a hard **Gate 0**: first determine whether historical per-name options pricing / IV / OI data for a manageable whitelist and sufficiently long history are actually available
- Risks / Counterarguments: the most immediate risk is allocation of research bandwidth before confirming that the basic data substrate exists. Without historical per-name options data, any “research” would collapse into literature review or narrative speculation, not testable strategy work. There is also a design risk: once admitted into the pool, this branch must remain operationally separate from the SPX mainline until and unless a later capital-allocation comparison is explicitly requested under the `Q036` framework
- Confidence: medium-high on the conceptual decomposition; low on practical feasibility until Gate 0 passes
- Next Tests: Gate 0 only — determine whether HC can source historical per-name options data (`~2004–2026`, whitelist coverage, options OHLC / IV / OI depth) from an acceptable provider. If Gate 0 fails, `Q041` pauses. If Gate 0 passes, the recommended Phase 1 is still narrow: `(a)` benchmark analysis using `BXM / PUT / WRIT` public evidence and `(b)` a covered-call-only pilot on a whitelist universe before any CSP / earnings expansion
- Recommendation: enter the research pool, but do not allocate full modeling bandwidth until Gate 0 data feasibility is explicitly cleared
- Related Question: `Q041`
- See: `research/strategies/Large-Cap Equity Option Income Overlay/Large-Cap Equity Option Income Overlay.md`, `sync/open_questions.md`, `PROJECT_STATUS.md`

### R-20260503-01 — AC3 gap is explained enough for planning; Q039 stays narrow and should not begin with an IVP sweep

- Topic: Post-MC-response Quant synthesis on `SPEC-077 AC3` and `Q039`
- Findings: Quant now judges the `SPEC-077 AC3` magnitude gap to be explained far enough for planning purposes. HC is not showing a metric bug: under the HC / `SPEC-078` final-equity-compound reading, `+0.0856pp` is the correct number. Recomputing the same HC ledger under MC-style simple annual ROE expands the uplift only to about `+0.3504pp`, which confirms that metric semantics explain part, but not all, of the gap to MC's `+0.9088pp`. The remaining gap is best read as a mixed effect of `(1)` longer MC sample window (`1999-01-01 → 2026-05-02` vs HC `2007-01-01 → today`), `(2)` different strategy/path mix (MC's largest uplift contribution sits in `bull_put_spread`, while HC's positive contribution is concentrated in `Iron Condor / IC_HV`), and `(3)` exit-timing taxonomy differences. `SPEC-080` / debit-side stop hardcode is now effectively removed from the main-cause list because HC's `bcd_stop_tightening_mode=disabled` and `active` runs produce identical PT deltas. For `Q039`, the new MC 6-trade `IC regular` ledger sharpens the interpretation: the residual gap looks primarily like a high-IVP `NORMAL IC` fallback/gate difference, not slot blocking and not a mild threshold-boundary issue. HC's `13` IC-regular trades contain `9/13` with `ivp252 >= 55`, `0/13` in the `50~65` "border" band, and `0/13` with a same-class IC slot already occupied
- Risks / Counterarguments: the AC3 gap is not mathematically "fully closed"; it is simply explained enough that more blind HC reruns are now low value until MC wants a tighter accounting/path reconciliation. Likewise, `Q039` remains a real residual attribution issue, but Quant's reading is that widening immediately into an IVP sweep would be premature and likely low-information
- Confidence: medium-high. The synthesis is strong enough to reprioritize work even if a future cross-engine deep dive still becomes necessary
- Next Tests: for `Q037`, only a compact attribution note is recommended: document HC's displayed `+0.0856pp`, same-ledger simple `+0.3504pp`, and the residual explanation via sample-window / path mix. For `Q039`, build only a compact mini attribution table using the MC 6-trade ledger and the HC-only 11-trade set; do not start an IVP sweep unless that table shows many HC-only trades falling into the `<30` or `[30,55)` buckets
- Recommendation: de-escalate `Q037` from high-priority investigation to explained post-spec attribution; keep `Q039` open but explicitly narrow, research-only, and mini-table first
- Related Question: `Q037`, `Q039`
- See: `sync/open_questions.md`, `PROJECT_STATUS.md`, `sync/mc_to_hc/MC Response 2026-05-02_v2.md`

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

---

> **Archive note (2026-05-09):** Entries from 2026-03 and earlier have been moved to
> `doc/research_log_archive_pre_2026-04.md` to keep this file scannable.
> The archived entries are: R-20260328-01 through R-20260329-03 (8 entries).
