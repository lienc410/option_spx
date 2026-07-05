# Q087 A1/A3 External Review Reply

**Date**: 2026-07-05
**Reviewer**: independent external quant reviewer (same as Q085 line reviews)
**Verified by execution**: A1 script re-run (exact reproduction); A3 three-arm re-run via module patching (exact reproduction, bit-identical repeat run); signal cache, selector code, iv_rank code, Q071 P4 archive, real closed-trades ledger, and an intraday-bound study (SPX daily low × VIX daily high) all checked independently.

**Bottom line**: both audits' *numbers* reproduce exactly and both *dispositions* are endorsed. Both audits have **narrative-attribution errors that must be corrected before archive** — A1's headline "structural finding" misattributes a deliberate SPEC-060 design decision to an undiscovered gate bug, and cites a synthetic simulation as "production actual trades"; A3's option (a) is mis-specified relative to what Q071 P4 actually validated.

---

## 1. A1 — IVP dual-gate audit

### Claim (a) zero-fire HIGH cell — fact CONFIRMED, mechanism FLAWED-MATERIAL

**Fact verified**: 177 NORMAL×BULLISH×iv_signal=HIGH days in the 26y cache; `strategy_key` empty and `strategy` = "Reduce / Wait" on **all 177**; the cell never fired. IVP min is **70.1** (memo says "恰为 70" — trivially off; 0 days at exactly 70; median 80.1 ✓).

**Mechanism refuted by code truth** (`strategy/selector.py:1108-1136`): the NORMAL×HIGH×BULLISH branch returns `_reduce_wait` **unconditionally, by explicit SPEC-060 Change 3 design**, with the rationale documented in the comment: "Bootstrap matrix: BPS avg −$299 not significant (n=23) … No strategy has statistically significant alpha in this cell." There is **no IVP≤70 entry gate in this lane at all** — the only checks before the unconditional wait are backwardation and VIX-RISING, and none reference IVP. The "通用门 40-70" of the audit's framing (`IVP_HIGH_THRESHOLD=70 / IVP_LOW_THRESHOLD=40`, selector.py:182-183) is a **classification** threshold used by `_effective_iv_signal` to reclassify when IVR/IVP diverge >15pts — it is not an entry gate. That reclassification is also why the lane's observed IVP floor is ~70: divergent days with IVP≤70 get reclassified out of HIGH. So:

- "格用 IVR 尺子承诺 BPS，门用 IVP 尺子永远否决" — wrong. The cell was **deliberately parked** by SPEC-060; the IVP floor is a lane-definition artifact, not a veto.
- "矩阵展示与真实行为分裂 26 年无人发现" — refuted. The split was examined, decided, and documented in the code. What *is* real and worth fixing: the matrix **display** still shows canonical BPS for a cell whose behavior is permanently wait (cosmetic display/behavior mismatch), and the IVR-vs-IVP reclassifier is a genuine two-ruler confusion source. The Q083-pathology framing must be withdrawn; the residual finding is presentational, not structural.

The **disposition** (defer any cell re-housing to post-SPEC-120) is correct and, notably, coincides with what SPEC-060 already decided — a fact the archive should state.

### Claim (b) IVP bands carry no quality signal — CONFIRMED

Script re-run reproduces the strata table exactly (n=16/64/58/54; mean +$75/−$184/−$502/−$187; breach 0/15.6/22.4/22.2%; p 0.268–1.0). Two footnotes: (i) the normal-approx Welch p is anti-conservative, which makes the *non-significance* conclusion safe; (ii) below-band n=16 means the "no quality signal" statement is power-limited — acceptable because the decision rests on the reform economics, not on proving exact zero. Boundary detail: script's in-band `[43,55]` vs code truth `[43,55)` (selector blocks `>=55`) affects 1 day — negligible, note for the record.

### Claim (c) all three reforms worsen — CONFIRMED (and robust to the sim-vs-production level gap)

Reproduced exactly: R1 −$1,852 / R2 −$3,219 / R3 −$3,033 per yr vs incumbent in-band −$582. On the coordinator's question — does the mechanical sim's divergence from "production" undermine this? No, for two reasons: (i) reforms are evaluated with the same engine on both sides, so model level-bias largely differences out; (ii) even granting the marginal strata the *entire* +$217/trade day-selection uplift observed between raw-band and selector-approved day sims (see (d)), the 55-70 stratum stays negative (−$502+217=−$285) and >70 goes to ≈+$30 ≈ zero — under the Execution standard (challenger must beat incumbent *significantly*), every reform still clearly fails. Gates stay.

### Claim (d) "production's 48 actual trades were +$33/trade" — FLAWED-MATERIAL (mislabeled evidence)

The real ledger (`data/closed_trades.jsonl`) contains **4-5 closed spread trades total** (mean ≈ +$5,972, 2026-era). "48 trades, +$33/trade" is **exactly** the Q085 P3 synthetic INCUMBENT arm under CALIB (n=48, mean $33 — reproduced by me on 2026-07-04). It is a *simulation of selector-approved days*, not production fills. The corrected — and actually stronger — statement: *under the identical CALIB engine, selector-approved days yield +$33/trade vs raw in-band days −$184/trade, so the selector's additional filters (macro/throttle/dedup/backwardation/VIX-rising) add ≈ +$217/trade of day-quality within the model.* The escalation to SPEC-120 survives and is well-motivated; the label "生产实际成交" must be corrected before archive, and the (n=5) real-fill record cited for what it is.

### A1 recommendation

**CONFIRM verdict** (IVP gates unchanged; conditional close pending SPEC-120; dead-cell re-housing deferred) **subject to two archive corrections**: rewrite §1 mechanism (SPEC-060 deliberate parking + display/behavior mismatch + reclassifier confusion; drop the undiscovered-dual-ruler-bug claim) and relabel §3's +$33 evidence as the synthetic incumbent sim. Neither correction changes the disposition; both change what the archive teaches future readers.

---

## 2. A3 — V2f stop-convention audit

### Reproduction and state leakage — CLEAN

All three rows reproduce **exactly** (15×: n=147, 0 stops, $180,903; 3×: n=149, 23 stops, $120,018, worst −$15,053, CVaR10 −$9,320; 5×: n=147, 7 stops, $152,431). Monkey-patch leakage: none — re-running 15× after the 3×/5× runs is bit-identical to the first 15× run. The n=147→149 difference is mechanically real: stops free ladder slots earlier, the cadence admits 2 extra entries. The −$61k cost decomposition verified at trade level: the stopped entries realize −$159.9k under 3× vs −$92.5k for the same 22 matched entries held under 15×.

### "3× never backtested / 15× never lived" — CONFIRMED, with an attribution correction

Code truth confirms both sides (`es_params.stop_mult=3.0` "Matches bot trigger (SPEC-086)"; `V2F_STOP_MULT=15.0` in the promoted phase). **However**: Q071 P4 (`q071_p4_stop_interaction.py`, memo §P4) *did* run a stop grid {no_stop, 10×, 15×, 20×} on the promoted G6 gate and documented at promotion time that "STOP=15 was **unused** in the G6 sample" plus the caveat "**the gate cannot fully substitute for the stop as a fail-safe**." So (i) "15× 在回测里是装饰性的" is a re-confirmation of a documented Q071 fact, not a new discovery — credit it; (ii) the genuinely new A3 content is the 3× costing; (iii) the mismatch origin is sharper than "无人调和": the promotion study examined stops explicitly and still nobody put the live 3× in the grid — a checklist lesson for Track E.

### Daily-close marking understatement — quantified; does NOT change the verdict

I bounded intraday triggering by re-marking every hold-day at **SPX daily low × VIX daily high** (a pessimistic co-location bound). On the 15× run's natural holds: close-mark ever ≥3× on 19 trades; intraday bound ≥3× on **23** (+4, ≈+20%). So the real 3× discipline stops somewhat more often than the close-marked 23 — the memo's direction flag is right and the magnitude is modest; it cannot rescue 3× (more triggers = more cost; the partial offset is that intraday exits cap near 3.0× while close-marked exits overshoot). Verdict unchanged.

### Gap-risk caveat for option (a) — now quantified, and option (a) needs restating

Under the same pessimistic intraday bound, **15× was never touched in 26 years — max intraday mark ratio 6.7×** (2008/2020 included). This bounds option (a)'s unmodeled exposure meaningfully and should be in the PM packet. Residual honesty: marks are BS-flat@VIX; panic put-skew inflates real deep-OTM marks (B1's own finding), so the true worst intraday ratio is somewhat above 6.7× — a 10× trigger is therefore not paranoid. Which leads to the substantive amendment:

**Option (a) as written ("撤销 TRIGGER 或改 15×") is mis-specified.** Q071 P4's validated grid is {10×, 15×, 20×} — all three are historically identical on G6 (0 hits, identical PnL) — and P4's own caveat argues *against* full TRIGGER removal. The dominated-choice analysis: within the validated grid, **10× is strictly the better fail-safe** (identical 26y economics, tighter protection against skew-inflated marks), and it is *not* a post-hoc cutpoint — it was in the pre-registered P4 grid. Restate option (a) as: "align live TRIGGER to a P4-validated far trigger (10× recommended, 15× acceptable), retain 2× WARNING as intelligence." Removing TRIGGER outright should not be on the menu.

### Era clustering of the 23 stops — material PM input, currently missing

The 23 stops form **9 episodes**, all in VIX 22-43 entry regimes, none in 2012-2019 or 2023+ ("2024+ 五笔两口径完全相同" verified — identical PnL lists). Critically, they arrive as **same-day multi-rung cluster events**: 2000-04-14 ×4 rungs (−$27.1k in one day), 2020-06-11 ×2 (−$20.9k), 2022-04-26 ×2 (−$27.7k), 2022-09-21 ×2 (−$22.9k); yearly stop losses: 2020 −$43.9k, 2022 −$50.6k. Two implications for the PM decision: (i) the 3× rule converts recoverable drawdowns into single-day realized cluster losses — the per-trade CVaR10 worsening *understates* the portfolio-day concentration; (ii) symmetrically, under 15×/10× those same clusters ride as multi-rung *unrealized* drawdowns — the PM is choosing between realized cluster losses and deeper unrealized excursions, not between "risk" and "no risk". This exhibit should be added to the packet.

### A3 recommendation

**CONFIRM** the governance conclusion (mismatch must be eliminated; direction is a PM risk decision; 5× correctly excluded as post-hoc) **with amendments**: (1) restate option (a) per above (validated-grid trigger, keep 2× WARNING; drop "撤销 TRIGGER" variant); (2) add the era-clustering/same-day-rung exhibit and the intraday-bound numbers (+4 touches at 3×; 0 touches at 15×, max 6.7×, skew caveat) to the PM packet; (3) credit Q071 P4's prior findings and record the checklist lesson; (4) **commit the runner script** — A3 currently has no committed executable (the runs were session monkey-patches); this is the third instance of results-only artifacts in this program line (P2e, P3b previously) and it keeps costing external-review time to reconstruct.

---

## 3. Cross-cutting note for the program board

Both audits are quantitatively solid — every number I attacked reproduced exactly, which is a real improvement over the pre-protocol era. The systematic weakness is now in the **narrative layer**: A1 attributes a documented design decision to an undiscovered bug and mislabels a simulation as production data; A3 under-credits its own prior art and offers a menu option its cited validation doesn't support. Recommend Track E encode two rules: (i) any "X was never examined/discovered" claim requires a grep of code comments + SPEC/Q archives before publication; (ii) any number presented as "production/actual" must cite the ledger row count it comes from.
