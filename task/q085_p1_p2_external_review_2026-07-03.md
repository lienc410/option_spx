# Q085 P1/P2 External Methodology Review

**Date**: 2026-07-03
**Reviewer**: independent external quant reviewer (no prior project context; everything re-derived from the repository)
**Scope**: q085 fact layer (P1a–P1g, research/q085/) and slot-layer plan (task/q085_p2_plan_2026-07-03.md)
**Method**: all material claims re-verified by executing code against `data/q085_spx_ohlc_cache.json`, `data/q085_crossasset_cache.json`, `research/q078/_signal_history_cache.csv`, and fresh yfinance downloads for the replication indices. No existing files were modified.

---

## Executive summary

- **The narrow fact-claim survives adversarial re-testing**: SPX short-term oversold mean-reversion (F3: RSI(2)<10, 3-down-days, IBS<0.2) at **1–5td horizons, all-days stratum** is significant under every inference method I threw at it (raw permutation, heteroskedasticity-robust studentized permutation, episode-clustered t-test), replicates directionally on all four replication indices, and has genuine literature priors. F3's admission as "a signal with information" is justified.
- **Almost everything layered on top of that core is not evidence-grade.** Specifically: (i) the 21–31td "accumulated edge" magnitudes that upgraded P2's economics; (ii) every B-stratum (NORMAL×BULLISH) cell magnitude; (iii) the P1f allowed/blocked split that reprioritized P2 toward S2; and (iv) S6's B-layer frequency/dollar arithmetic. Each of these fails at least one direct check below.
- **The permutation test has a demonstrable anti-conservative bias for exactly this signal family** (oversold signals select high-volatility days; the raw-statistic circular-shift null does not price that). Under a studentized permutation, the 28 joint-FDR survivors collapse to ~7, and **all fwd21/fwd31 cells die**.
- **Recommendation: F3 admission stands; P2 proceeds only with modifications** (listed in §8). S6 at B-layer scope should be pre-declared arithmetic-dead unless the plan is changed; the S2-first prioritization should be withdrawn or re-based; all P2 simulations must use uncertainty-bracketed edges, not full-sample point estimates.

---

## 1. Sequential endpoint addition (P1a → P1c → P1e) — **FLAWED-MATERIAL** (as evidence accounting), fact-conclusion rescued by external evidence

**What happened**: The framing memo pre-registered a single endpoint (fwd-31td, §6). P1a returned 0/77 with an F3 near-miss cluster. The next-day endpoint (P1c), three new fast-cross signals, and then the {5,21}td ladder (P1e) were each added after seeing results, each justified by a design critique, each applied uniformly, with joint BH-FDR re-run over the pooled 329 tests.

**Verified findings**:

1. **The joint-FDR "strictest accounting" claim (P1e memo) is directionally wrong.** I re-ran the exact pooling from the committed CSVs. P1a alone: BH threshold = 0 (nothing passes). Joint pool of 329: BH threshold rises to **p ≤ 0.0085**. Pooling many highly-correlated significant F3 tests (the same ~600 days scored at 4 horizons × 2 strata) inflates the number of rejections k and *loosens* the threshold for marginal cells. Concrete demonstration: `F3_rsi2_os B fwd31` (p=0.0025) **failed** P1a's own battery and **passed** the joint battery with zero new data. Adding adaptively-chosen endpoints then FDR-pooling is not a penalty; for marginal cells it is a subsidy. The correct strict accounting would collapse the F3 family (one phenomenon) to one discovery unit, or apply hierarchical/family-level FDR.
2. **Uniform application controls per-signal cherry-picking, not the decision to expand.** The expansion happened *because* F3 near-missed. Had F3 not near-missed, K1 documentation was the pre-registered path. This is the textbook garden of forking paths; uniformity across signals does not touch it.
3. **The cross-index replication carries far less independent weight than presented.** Verified with fresh downloads: NDX and RUT daily-return correlation with SPX = 0.86/0.88; on SPX signal days, next-day return correlation = **0.89–0.91**; signal-day overlap P(also on | SPX on) = 60–70%. NDX+RUT are ~1.3 effective observations of the same US-market events, not 2 independent ones. The "≥2/3 same-sign p<0.05" gate was therefore near-guaranteed to pass *conditional on the SPX result, whether that result was real or noise-shared-across-US-indices*. The only quasi-independent market, GDAXI (return corr 0.59, signal overlap 36–44%), shows the effect at **half the SPX size** (+9.0/+10.7bp vs +22bp) with p=0.076/0.051. Note GDAXI's miss is not a power artifact: with n≈700 on-days, an SPX-sized effect would have produced p<0.001. The honest replication verdict is "same sign everywhere, quasi-independent market at half magnitude, marginal significance" — supportive of existence, unsupportive of SPX-magnitude transfer.
4. **The researcher applied the correlated-indices caveat inconsistently.** P1g's footnote (written when the replication protocol *killed* the OpEx cell) explicitly concedes "correlated US indices are weak independent evidence." The same logic was not applied retroactively to F3's admission, which rests on NDX+RUT passing. Pre-registering a weak gate does not make it strong.

**Why the fact-conclusion nonetheless stands**: (a) the F3 fwd1/fwd5 A-stratum core is at the permutation floor under both raw and studentized inference (§2), i.e., it does not depend on the pooling leniency; (b) the PM's dilution critique of fwd-31td for 1–5d signals is valid *ex ante* — the ladder is what a competent pre-registration would have contained on day 1; (c) index-level short-horizon mean reversion post-2000 (Connors RSI(2), IBS) has published out-of-sample history that predates this study. The adaptive taint attaches to the **magnitude and horizon-profile claims**, not to existence.

**Verdict**: process FLAWED-MATERIAL; the specific verdict "F3 has information at short horizons" survives on evidence that is independent of the flawed accounting. Every downstream use of P1c/P1e *magnitudes* must be treated as in-sample, adaptively-selected estimates.

---

## 2. Permutation validity — **FLAWED-MATERIAL** (anti-conservative under signal-conditioned heteroskedasticity)

**What the null preserves (verified by reading `q085_battery_lib.perm_test_generic` and the P1a/P1c scripts)**: outcome series fixed in place (outcome autocorrelation and overlapping-window structure preserved), condition circularly shifted (signal run-length/autocorrelation preserved), stratum mask fixed (stratum clustering preserved), min offset 63td (kills local alignment leakage). As a test of *any* signal→outcome dependence this is a reasonable construction, and clearly better than iid shuffling.

**What the null does not preserve — and it matters here**: F3 conditions fire on high-volatility days by construction (they select post-decline days). The observed statistic (conditional mean minus stratum mean) is computed over systematically high-variance days; the null distribution is built from placements on typical-variance days. The null therefore understates the sampling variance of the observed statistic. Measured conditional/unconditional next-day sd ratios: RSI2 1.43×, down3 1.31×, RSI14 **2.25×**, %B 1.69×.

**Quantified impact** (studentized permutation — the standard heteroskedasticity-robust fix — 4000 shifts, same protocol otherwise):

| cell | raw p | studentized p |
|---|---|---|
| F3_rsi2_os A fwd1 | 0.0002 | 0.0002 (unchanged) |
| F3_down3 A fwd1 | 0.0002 | 0.0002 (unchanged) |
| F3_ibs_low A fwd1/fwd5 | 0.0002 | 0.0002 (unchanged) |
| F3_rsi2_os A fwd21 / fwd31 | 0.0027 / 0.0032 | 0.0120 / 0.0095 |
| F3_down3 A fwd21 / fwd31 | 0.0087 / 0.0075 | 0.0197 / 0.0267 |
| F3_rsi14_os A fwd1 | 0.0002 | **0.0137** |
| F3_pctb_low A fwd1 | 0.0007 | **0.0227** |
| F3_rsi2_os B fwd31 (the +158bp cell) | 0.0022 | **0.0112** |
| F3_z5_low B fwd1 | 0.0005 | **0.1795** (dead) |
| F7_opex_wk B fwd5 | 0.0050 | 0.0120 |

Re-running the joint FDR with studentized p substituted for the 28 surviving cells: threshold tightens to ~0.002 and **survivors collapse from 28 to ~7** — the fwd1/fwd5 core (rsi2/down3/ibs A; down3/ibs B fwd5) plus the sma5_10 mirror. Every fwd21/fwd31 cell dies. (Caveat: substituting only survivor cells slightly overstates the collapse — studentizing the full 329 would move some null cells down and loosen the threshold somewhat; the fair statement is "fwd21/31 cells are borderline-to-failing under robust inference, the 1–5td core is untouched.")

A third method (episode-clustered t-test, episodes separated by ≥ horizon so windows don't overlap) *supports* the fwd21/31 A-stratum cells strongly (t=4.5–7.9) but is itself anti-conservative in the other direction (episode edges within an era share the era's drift deviation from the global base). **Three methods, three answers for fwd21/31; one answer for fwd1/fwd5.** Conclusion: the 21–31td accumulation claim in the P1e memo — the claim that specifically revived P2's $4k feasibility — is method-dependent and must not be treated as established magnitude.

Secondary checks, all clean: the `continue`-on-sparse-shift branch (shifted placements with <30 stratum on-days are skipped but still count in the denominator, biasing p low) fires **0.0%** of the time for the sparse B-layer F3 cells — a latent bug pattern but a non-issue here. Calendar-locked conditions (F7): circular shift by uniform offsets breaks month/opex phase as intended; weak partial re-alignment at multiples of the ~21td month is possible but F7 died everywhere it mattered, so no verdict rides on it. MIN_SHIFT=63 is adequate for signals with ≤31td memory.

**Verdict**: FLAWED-MATERIAL. Not because the core F3 finding is fake — it isn't — but because the battery's published survivor list (28 cells) is inflated by an anti-conservative statistic, and downstream documents already treat the inflated cells (fwd31 B +158bp, rsi14 +311bp) as facts.

---

## 3. Look-ahead — **SOUND** (nothing flips a survival verdict)

- Full-sample median splits (acknowledged in P1a header): affect F2_d63low/d126low/swing_near and F5_vrp_rich only. All dead everywhere; no survivor uses a full-sample statistic. F3 survivors use fixed thresholds (RSI<10/<30, IBS<0.2, %B<0, 3 down days) or rolling-252d z-scores. No flip risk.
- Swing-low confirmation: `low.rolling(2k+1, center=True).min()` then `.shift(k).ffill()` — verified the flag only becomes available k bars after the swing bar; correct, no look-ahead.
- IBS/candlestick features use same-day OHLC evaluated at close for a close-execution framework — legitimate given the PM's confirmed ability to execute near close (P1e memo §3).
- One structural caveat the memos do not state: **stratum B and the P1f "allowed/blocked" labels come from `research/q078/_signal_history_cache.csv`, a reconstruction of the *current* selector/gate parameters over 26y.** This is a today's-params counterfactual, not a point-in-time record. It is acceptable for "how would today's system interact with F3" questions (which is the right question for P2), but "72% blocked" and all stratum-B results should be labeled as parameter-conditional, and any P2 adoption case must note sensitivity to future gate-parameter changes.

**Verdict**: SOUND, with the stratum-B labeling caveat to carry forward.

---

## 4. F3 admission and the K3 doubling — admission **SOUND (narrowly)**; the doubled K3 as "price of post-hoc origin" is **partially theater**

The admission chain that actually holds: fwd1/fwd5 A-stratum significance robust to studentization (§2) + directional replication on four indices incl. a half-sized quasi-independent GDAXI (§1) + literature prior + IS/OOS sign consistency. That justifies "F3 contains exploitable information at 1–5td" — an Alpha-standard pass on the narrow claim.

What the K3 doubling ($2k→$4k/yr) does and does not do:

- It raises the *monetization* bar, which guards against adopting an economically trivial slot. Fine.
- It does **nothing** about the actual risk created by the post-hoc origin: **effect-size overstatement**. P2 simulations fed with full-sample, adaptively-selected point estimates (fwd31 B +158bp; fwd21 +76–271bp) will overstate $/yr, and a doubled threshold applied to an overstated number is not a safeguard — it can even *pass more easily* than an honest threshold applied to an honest number. Measured overstatement risks: B-cell standard errors are ~50% of point estimates (e.g., composite event edge +42bp ± 20bp, §6c); era decay is real (fwd1 edge 2013–2019: **+4.5bp** rsi2 / +4.8bp down3 — indistinguishable from zero for seven years — vs +27–39bp in 2007–13/2020+); GDAXI transfer at half size.
- The binding protection must therefore live in the *edge inputs*, not the threshold: P2 sims should run the adoption gate on (a) the OOS-half estimate, (b) the studentized-CI lower bound, and (c) the worst contiguous 7-year era — and pass K3 on the pessimistic member of that set. The pre-registered "pessimistic bracket" currently means pricing/skew brackets, not edge-estimate brackets; that is the gap.

**Verdict**: admission SOUND for the family at 1–5td; K3-doubling-as-price FLAWED-MINOR (necessary but not sufficient; add edge-uncertainty bracketing or it is mostly optics).

---

## 5. P1f as basis for P2 reprioritization — **FLAWED-MATERIAL** (the split is noise)

P1f is self-labeled descriptive ("formal inference in P2"), but the P2 plan *already acted on it*: S2 promoted to primary slot, S3 demoted to "expected dead." I ran the inference P1f skipped (circular-shift permutation of the oversold composite within fixed state masks, 4000 shifts):

| state | n_os | fwd21 edge | perm p |
|---|---|---|---|
| allowed & NORMAL | 48 | −0.24pp | **0.74** |
| allowed & HIGH_VOL | 100 | +0.99pp | 0.062 |
| blocked & NORMAL | 267 | +0.59pp | 0.055 |
| **blocked−allowed difference (NORMAL)** | | +0.82pp | **0.28** |

The claim "edge lives HERE (blocked stratum)" versus "no edge in allowed&NORMAL" is a difference with p=0.28 — pure noise, on 33 vs 77 episodes. This is precisely the stratum-slice pattern the house's own `feedback_stratum_cutpoint_overfit` and `feedback_circular_metric_validation` memos warn about: a 3-way state split of a real aggregate effect, with the smallest cell (n=48) driving a "no edge" conclusion. The data are fully consistent with a uniform F3 edge across all three states.

What survives of P1f: the **feasibility** facts are real and useful — oversold days have median IVP 72 vs a gate upper bound of 70, 72% are blocked, and the S3-as-designed trigger fires usefully only 17.4% of the time. S3's demotion can rest on feasibility alone. S2's *promotion over S5-HV and S3* cannot rest on the edge-location claim, and S2 is the arm that takes on the blocked stratum's fatter unconditional left tail. Prioritizing the highest-tail-risk arm on a p=0.28 split is exactly backwards from a risk standpoint.

**Verdict**: FLAWED-MATERIAL for the reprioritization; the P2 plan should treat S2/S3/S5-HV as a priori co-equal candidates distinguished by feasibility and tail cost, not by P1f edge location.

---

## 6. P2 plan soundness — **proceed only with modifications**

**(a) S2 tail accounting — FLAWED-MINOR, wrong tail numbers cited.** The plan cites P0's p5 −12.6% vs −8.8%, which describes *IVP-upper-blocked windows in NORMAL×BULLISH at fwd31* — a different stratum than S2's actual candidate set. I computed the actual S2 entry-day-conditional distribution (blocked & NORMAL & oversold, fwd21, n=267): mean +0.86%, p5 **−5.45%**, p1 −10.27%, worst −16.42% — a *thinner* tail than the blocked&NORMAL baseline (p5 −7.73%, worst −32.97%). Two implications: (i) the plan's tail premise is stale — replace it with the entry-day-conditional distribution; (ii) the real danger is not the average tail but the cascade path: P1f itself notes 47% of oversold days drift into HIGH_VOL, and the Layer-1 EXTREME_VOL veto is *reactive* — it classifies after the regime has escalated, i.e., after an S2 entry is already on. The plan needs an explicit crash-cascade test: what do S2 entries opened in the 21td preceding each historical EXTREME_VOL onset do? A blanket "Layer-1 screening" citation does not answer that.

**(b) S6's 5td exit — mitigation acceptable in form, insufficient in placement.** The plan self-reports that 5td was read off the in-sample cumulative-edge curve. A 3-point pre-registered grid {2td, 5td, mirror-signal} with a robustness-across-grid requirement is the right *shape* of mitigation, but the grid is anchored at the in-sample optimum, and "robust across grid" on the same sample that chose the anchor is weak. Fix: choose the exit arm on the first-half sample only, confirm on the second half; or require the adoption case to clear K3 at *all three* grid points, not "robustly" (undefined) across them.

**(c) S6 event frequency and dollar arithmetic — FLAWED-MATERIAL: the B-layer slot is doomed by arithmetic before simulation.** Verified counts: the B-layer composite (RSI2<10 ∨ down3) has **102** raw days 2000–2026 (plan says ~110 ✓), but after 5td-hold dedup only **68 events = 2.6/yr**, not the plan's "~4/yr" (the plan's number appears to be days÷26, i.e., dedup not actually applied). Event-level fwd5: mean edge **+42bp, se 20bp** (a 2.1σ estimate), sd 165bp, win rate 63%, p5 −1.71%, worst −5.2%. At 2.6 events/yr, K3 = $4,000/yr requires ~$1,540/event; at +42bp that is **~$368k notional ≈ 10 MES contracts per event** (SPX 7483). For a cash-bound retail PM account this is not a plausible sizing; and at that size the p5 event is −$6.3k and the historical worst −$19k — on a 2σ edge. No cost model rescues this; the frequency×edge product is simply too small. Options: (i) pre-declare S6-B dead and save the simulation effort, or (ii) re-scope S6 to the A-layer with survival vetoes (16 events/yr, edge +35bp, needs ~$71k ≈ 2 MES/event — arithmetically alive, but now includes HIGH_VOL days with p5 −4.15% and crash-era worst cases, so the tail work transfers there). The plan must do this arithmetic *in the plan*, per the house's own today-scale-absolute rule.

**(d) Transaction costs — SOUND-to-optimistic.** MES $1.5 commission + 0.25pt slippage/side ≈ 1–2bp round trip on today's notional: realistic for a liquid front-month micro. SPX debit-spread half-spread $0.25–0.50/leg: plausible for tight verticals executed patiently, optimistic for fast tactical entries near the close on oversold (wide-market) days; the pessimistic bracket should use ≥$0.75/leg for entries made under elevated vol. Early-close overlay on existing BPS: crossing two spreads twice — same comment.

**(e) Missing from the plan** —
1. **Unified portfolio-level simulation.** S2, S5-HV, and S6 all trigger on the *same F3 days*. Adopting two or three of them stacks long-delta adds on identical dates. The house's own `feedback_portfolio_level_research` lesson (unified-NLV simulator from the start) is not reflected: the plan lists per-slot sims and per-slot K3 gates. Correlated-slot stacking is exactly how a benign per-slot verdict hides a portfolio tail.
2. **Era/regime dependence kill-switch.** The fwd1 edge was ≈0 for 2013–2019 (+4.5bp). A production overlay needs a pre-registered condition for "the regime that pays this signal is absent" (e.g., trailing realized-vol floor), or at minimum the adoption memo must show K3 clears on the worst 7-year era, not the 26y average.
3. **Point-in-time caveat** on all "blocked/allowed" reconstructions (§3).
4. Capacity: non-issue at this scale (correctly ignorable). Overnight gap risk for the MES arm: deferred to a separate SPEC per the plan — acceptable, but the deferral must be binding (no interim futures trading on this signal).

---

## 7. Additional findings

1. **The F4 control family produced a joint-FDR survivor, and the calibration claim was never retracted.** P1a memo §2: "F4 zero false positives — evidence the battery is well calibrated." After P1c, `F4_rev3` (A, fwd1, −12bp, p=0.004) *survives the joint FDR* and is re-narrated as "the same MR phenomenon expressed inversely." That reinterpretation is economically plausible (a bounce day is the tail end of an oversold episode) — but you cannot both use F4 as a false-positive calibration control and post-hoc reclassify its survivor as signal. Either the control family was mis-designed (rev3 is mechanically MR-adjacent, unlike engulf/hammer) or the battery produced a false positive; the archive should say which, and the "well calibrated" sentence in the P1a memo is stale either way.
2. **P1e memo's economics-upgrade sentence overreaches its own table.** "B 层 RSI(2)<10 ... +158bp" is presented as the S3/S5 value anchor; that cell is n=71 days / 33 episodes, studentized p=0.011 (fails the tightened threshold), episode-t p=0.18. The upgrade from "$1–3k/yr, not optimistic" (P1c/P1d memo) to "P2 有真实机会过线" (P1e memo) rests substantially on this one fragile cell plus method-dependent fwd21/31 cells (§2).
3. **Numbers audit** (memos vs CSVs vs my recomputation): P1a "0/77, min p 0.0025" ✓; P1c "82 tests / 10 survive" ✓ (86 next-day rows, 4 invalid); P1d "159 joint / 15 survive" ✓; P1e "329 joint / 28 survive" ✓ reproduced exactly from committed CSVs; P1f state means/counts ✓ reproduced. Two misstatements found: (i) P2 plan's S6 frequency "~4 events/yr after 5td dedup" — actual dedup gives 2.6/yr (§6c); (ii) P1e memo's "最严记账" characterization of the joint FDR (§1, demonstrably looser for marginal cells).
4. **P1g is the methodological high point of the line** — a pre-registered replication gate applied to an isolated survivor, allowed to kill it, with an honest footnote about correlated-index weakness. The same footnote's logic should be echoed into the F3 admission record (§1.4).
5. **Minor latent bug** (no current impact): the skipped-sparse-shift branch in all three permutation implementations biases p low whenever skips occur (denominator counts skipped draws as non-exceedances). Measured 0% skip rate on every surviving cell, so no verdict is affected — but the next battery with a rarer signal × smaller stratum will silently benefit. Worth a one-line fix (count only valid draws).
6. **P1b (Tier-3: FOMC/COT/AAII/PC) remains unrun** while the joint-FDR "ledger" has already been closed twice (P1d, P1e). The framing memo's own protocol says the joint accounting closes at P1b. Adding ~10–16 more tests will move the BH threshold again; if any F3-adjacent marginal cell's survival flips at P1b close, the P1e catalog must be republished, not amended in place.

---

## 8. Overall verdict

**F3 admission: JUSTIFIED — narrowly.** The defensible, evidence-grade claim is: *SPX oversold days (RSI(2)<10 / 3-down / IBS<0.2) carry a positive short-horizon (1–5td) conditional edge, present in both sample halves, directionally replicated abroad at reduced size.* The following are **not** evidence-grade and must not be load-bearing in P2: the 21–31td accumulated magnitudes, all B-stratum cell magnitudes, the P1f state-split, and the fwd31 B +158bp anchor.

**P2: PROCEED WITH MODIFICATIONS** — the plan as written should not be executed unmodified. Required changes:

1. **Withdraw the P1f-based prioritization.** Treat S2 / S3 / S5-HV as co-equal; rank by feasibility (S3's 17.4% trigger rate is a legitimate demotion ground) and tail cost (S2 highest), not by the p=0.28 edge-location split. If a state-conditional edge claim is to survive into any adoption memo, it must first pass its own inference test.
2. **Edge-uncertainty bracketing everywhere.** Every K3 evaluation runs on three edge inputs — OOS-half estimate, robust-CI lower bound, worst contiguous 7-year era — and the gate passes only on the pessimistic member. Full-sample point estimates (especially anything derived from fwd21/31 or B-stratum cells) are disallowed as sole inputs. This, not the K3 doubling, is the real price of the post-hoc origin.
3. **S6: fix the arithmetic before simulating.** B-layer scope is dead at 2.6 events/yr × (+42±20)bp (needs ~10 MES/event to reach $4k/yr). Either pre-declare it dead or re-scope to A-layer-with-survival-vetoes and do the tail work there. Correct the "~4/yr" figure. Move the exit-grid selection to the first-half sample with second-half confirmation (or require K3 pass at all three grid points).
4. **S2: replace the stale tail citation** with the entry-day-conditional distribution (fwd21 p5 −5.45%, p1 −10.3%, worst −16.4%) and add the explicit crash-cascade test (S2 entries within 21td of historical EXTREME_VOL onsets), since the Layer-1 veto is reactive and 47% of oversold days drift into HIGH_VOL.
5. **One unified-NLV simulation** covering every adopted combination of S2/S5-HV/S6 (they trigger on the same days), with the portfolio-level worst-trade/CVaR/disaster-window pack — per the house's own portfolio-level-research lesson. Per-slot K3 gates alone are insufficient.
6. **Bookkeeping**: retract/annotate the P1a "well calibrated" claim (§7.1); correct the P1e "strictest accounting" characterization (§1.1); add the point-in-time caveat to all stratum-B/blocked-allowed results; close the joint-FDR ledger only once, at P1b, as pre-registered; fix the skipped-shift denominator.

If modifications 1–5 are accepted, the residual research risk is ordinary estimation risk, and the K3 pessimistic gate becomes meaningful. If they are refused, my verdict on P2 would be HALT, because every dollar figure the plan would produce inherits the inflated magnitudes documented in §2 and §6.

---

### Appendix: reproduction notes

All checks run 2026-07-03 against the committed caches; key scripts inline in this review's session. Core reproducible facts:

- Joint-FDR pooling from committed CSVs: 329 tests, thr 0.0085, 28 survivors (matches P1e memo exactly); P1a-alone thr 0 (matches P1a memo).
- Studentized permutation (4000 shifts, seed 12345): table in §2; substituted joint FDR → ~7 survivors, all fwd1/fwd5.
- Episode-clustered t-tests: fwd1 A-cells t≈3.4 (p<0.001); fwd21/31 A-cells t=4.5–7.9 (era-confounded, see §2); rsi2 B fwd31 t=1.38 p=0.18.
- Era decay (A, fwd1): rsi2 +19.3/+26.5/+4.5/+38.6bp and down3 +28.6/+23.8/+4.8/+33.1bp over 2000-07/07-13/13-20/20-26.
- Replication geometry (yfinance, 2000–2026): NDX/RUT next-day return corr on SPX-signal days 0.89–0.91, signal overlap 60–70%; GDAXI 0.57–0.58 corr, 36–44% overlap, effect ≈ half of SPX.
- P1f inference: blocked−allowed (NORMAL) difference +0.82pp, perm p=0.28.
- S6 arithmetic: 68 dedup B-events (2.6/yr), event edge +42bp (se 20bp), $4k/yr ⇒ ~$368k notional ≈ 10 MES/event at SPX 7483; A-layer 423 events (16/yr), +35bp, ~$71k ≈ 2 MES/event.
- S2 stratum tails: n=267, fwd21 mean +0.86%, p5 −5.45%, p1 −10.27%, worst −16.42%.
