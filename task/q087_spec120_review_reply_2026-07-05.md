# Q087 SPEC-120 Verdict Packet — External Review Reply

**Date**: 2026-07-05
**Reviewer**: independent external quant reviewer (same as Q085/Q087-A1/A3 reviews)
**Verified by execution**: compare CSV + all three trade CSVs re-derived and cross-checked; 27-cell FLAT-vs-CALIB winner analysis recomputed (13 flips reproduced exactly); behavioral routing map rebuilt from the 26y signal cache and diffed against `strategy/catalog.py` CANONICAL_MATRIX **and** `strategy/selector.py` code paths; offset dispersion computed from `data/q085_skew_monitor.jsonl`; A2 cell power computed from trade rows; engine/pricing time-convention traced through `pricing/core.py` / `backtest/engine.py` / the AC-2 gate.

**Overall: RATIFY-WITH-CONDITIONS.** Every §3 disposition (all "no live change") survives review. But the packet contains four factual claims contradicted by its own data or by code truth, one of which ("no flipped cell indicts live routing") is false for precisely the largest cell in the book. And a pricing-convention inconsistency means every CALIB absolute in the packet carries a ~+15-20% overstated haircut — which, ironically, *strengthens* the packet's central instinct (don't act on this model; arbitrate with real quotes) while weakening several of its specific sentences.

---

## Claim 1 — BCD disposition + routing map

### Routing map: FLAWED (multiple mislabels; conclusions mostly survive)

The hand-reconstructed map follows CANONICAL_MATRIX; the **behavioral** truth (26y cache + selector code) differs:

1. **Two HV cells are mislabeled**: HIGH_VOL|HIGH|BEARISH fires `iron_condor_hv` in the cache (263/263 days — the canonical `bear_call_spread_hv` path is fully consumed by the aftermath/VIX-rising/ivp63 gates) and HIGH_VOL|NEUTRAL|BULLISH fires `iron_condor_hv` (175/175 days), not the canonical `bull_put_spread_hv`. Luckily IC_HV is CALIB-robust in both cells (+$73.2k / +$39.0k), so no verdict damage — but the map must be published corrected.
2. **The cache ends 2026-05-27 and predates SPEC-113**: NORMAL|LOW|BULLISH shows 1,023 days all-EMPTY. The carve exists only in code, not in any behavioral record. Worth stating: the cache needs regeneration before it is re-used as a routing source.
3. **"21 production-routed cells" reconciles with no map I can construct** — behavioral is 18 firing cells + the carve. Publish the corrected 18+1 table (I include it below via the numbers I verified).
4. **"HV 特许经营权 CALIB 全部为正" is false** under both maps: `bear_call_spread_hv` HIGH_VOL|LOW|BEARISH (live-routed, canonical *and* behavioral) is CALIB **−$4,035** (FLAT already −$1.4k; n=6 — noise-scale, but the sentence is wrong).
5. **"IC 特许经营权基本无损" needs a named exception**: live cell `iron_condor` NORMAL|NEUTRAL|NEUTRAL is negative in all three scenarios (−$1.8k/−$9.3k/−$23.7k; 16 days/26y — tiny, but it is a live cell).
6. One live cell has **no row at all** in the compare CSV (`iron_condor_hv` HIGH_VOL|LOW|NEUTRAL — no FLAT force-entry trades, so the groupby dropped it). The live table has a hole; flag it rather than let it read as "fine".

**Corrected bottom line** (behavioral map, my recomputation): 3/18 live cells CALIB-negative (−$4.0k, −$4.3k, −$9.3k per 26y — all small-n), 7/18 PESS-negative. The franchise-level conclusion (HV/IC robust, pressure concentrated in BCD family + NNB PESS) **survives in substance** with the exceptions named.

### BCD "no live change, arbitrate via SPEC-122": CONFIRMED — and it is *not* status-quo bias, but for a reason the packet doesn't know it has

The three cited defenses are individually weak, as §5 suspects: the real ledger is n=4-5 trades (mean +$5,972, one bull half-year — no inferential weight); 2024+ CALIB n=6 is a post-hoc era slice of the same genus this program has been burned by twice. If those were the whole case, I would call motivated reasoning. They are not the whole case:

- **The model evidence against BCD is itself unvalidated in absolute terms** (see Claim 5): the engine prices at T=dte/252 while the offsets and the AC-2 gate live at T=dte/365; the offset-induced haircut is overstated by roughly √(365/252)≈1.20. Correcting it moves BCD main cell CALIB from +$5.4k to ≈ +$27k and the carve from +$4.3k toward positive. The model does not establish "BCD ≈ zero"; it establishes "BCD's FLAT number was inflated and the corrected number is somewhere between mildly positive and zero, with the widest error bars in the book."
- **The calibration is genuinely weakest exactly there** — confirmed from `spec120_offsets_stats.json`: call offsets are the largest measured (−4.7 to −6.0vp near-bucket), the far bucket has only 24 days, and B2's backfill added **zero** new dates (all 30 were dupes of production days — the "backfill" did not extend coverage; the whole calibration is still one ~31-day VIX 15-22 window).
- Under the Execution standard, changing live routing requires affirmative evidence; there is none on either side.

**Conditions**: (i) relabel the three §2 defenses as "evidence insufficient in either direction," not as support for BCD health; (ii) SPEC-122 must pre-register its pass/fail criteria and a decision deadline **before** quote collection starts (house post-withdrawal rule — otherwise SPEC-122 becomes the next revive lever); (iii) note that BCD signal-day frequency (~52/yr main cell) makes 4-8 weeks genuinely adequate for quote-level calibration — unlike the Q085 S2 case, this timeline is not theater.

## Claim 2 — A1/A2 CLOSED: A1 CONFIRMED; A2 should be DEFER-CLOSED

**A2's cited evidence is a −0.35σ number.** From the trade rows: n=41 (memo says 40), net −$11,157, per-trade sd $4,962 → se(net) ≈ **$31.8k**. The −$11.2k is indistinguishable from zero *and* from ±$40k; citing it as "力入为 −$11.2k → 开格无支持" implies measured harm where there is none. The closure is still *defensible* — under the Execution standard, not-opening a boundary needs no affirmative evidence, and the burden was on the reform — but the framing must be corrected to "no affirmative case, CI ±$63k wide," not "negative result."

**Consistency defect**: A2's object cell (NORMAL|LOW|BULLISH) is the carve's parent cell — its economics are arbitrated by the same SPEC-122 real-quote data as the §2 BCD family and A4. A4 got DEFER-CLOSED on exactly that dependency; A2 got CLOSED. Same dependency structure, different disposition. **Recommend: A2 → DEFER-CLOSED**, re-check in the same post-SPEC-122 review as A4 and the carve. (A1's closure is unaffected: reform candidates worsened under both calibration generations, and my A1 review conditions — SPEC-060 attribution rewrite, +$33 relabel — carry over unchanged.)

## Claim 3 — NNB BPS PESS bracket: disposition CONFIRMED; the bracket is neither a worst case nor an overstatement — it answers one specific question

What the static bracket (short −1vp / long +1vp, entry **and** exit alike) actually models is a **persistent offset-miscalibration**: entry-adverse, partially self-refunding at exit (the cheap short leg is also cheaper to buy back). Two quantified observations:

- Vs **sampling error** it is generous: measured day-to-day offset sd ≈ 0.60vp → se of the 30-day mean ≈ **0.11vp**; a ±1vp persistent error is ~9σ of estimation noise.
- Vs **adverse skew dynamics** it understates: a bracket that flips sign at exit (short leg marked +1vp at buyback under skew steepening) is the true adversarial case and is strictly worse than the static reading; and the offsets are measured in a single VIX 15-22 month, so regime-shift risk is entirely outside the bracket.

Additional context the packet omits: NNB CALIB "+$15.7k 存活" is itself only **1.2σ from zero** (se $13.3k), the trade set drifts across modes (n=36/34/37 — mode deltas are not matched-pairs), and the T-convention correction moves the CALIB point estimate to ≈ +$24k. Net: "current healthy, PESS sensitivity on record, no action" is the right disposition; **conditions**: state explicitly that PESS ≠ worst case (name the flip-at-exit variant and regime-shift as unmodeled, register the flip-at-exit variant into Q088's test list), and confirm the standing quarterly re-measurement trigger is the actual guard for this cell.

## Claim 4 — "no flipped cell directly indicts current live routing": FLAWED — false for exactly one cell, the biggest one

13 flips reproduced exactly (13/27 = 48% ✓). Cross-checked against the behavioral map: for 12 of 13, the claim holds (flips occur in wait cells, or live routing ≠ the deposed FLAT winner, or live was already the CALIB winner). The exception: **LOW_VOL|LOW|BULLISH — live = bull_call_diagonal = FLAT winner, deposed under CALIB** (CALIB winner: bull_put_spread_hv force-entry). That is the main BCD cell: **1,382 days, ~21% of all trading days, the single largest routing decision in the book**. The sentence must be corrected to: "exactly one flip touches live routing — the BCD main cell, already quarantined under §2/SPEC-122." Note this *raises* SPEC-122's stakes: the real-quote shadow is no longer just checking a marginal franchise, it is arbitrating the largest cell's routing.

The **Q088-not-now disposition is CONFIRMED** and I'll state the case harder than the packet does: (i) single ~31-day calibration window; (ii) CALIB absolutes carry the ~20% convention bias; (iii) several "CALIB winners" are off-regime hypotheticals (bull_put_spread_hv inside LOW_VOL is an HV-parameterized structure entering a regime it never trades — force-entry artifacts, not candidate routings); (iv) per-cell n of 3-24 for most flips. Rerouting 27 cells on this would be exactly the cutpoint/overfit pattern the house has archived twice. Q088's three-gate design (per-cell significance + real-quote anchor + era stability) is the correct standard.

## Claim 5 — Engine implementation: isolation argument PARTIALLY SOUND; one convention inconsistency must be fixed before any absolute is quoted again

What's right: explicit `SigmaMode` enum with loud failures, no library-default brackets (my C-series condition, honored), per-leg offset lookup keyed by FLAT-delta with a common strike ladder across modes — strike selection is mode-invariant, so mode deltas isolate pricing, not positioning. AC-5 merge accounting is honest (it exposes that B2 added zero days). NaN gates (AC-3) pass.

What's not:

1. **T-convention inconsistency (material)**: the matrix engine prices at **T=dte/252** (`pricing/core.py` documents this as the backtest convention); the offsets are chain-measured and the AC-2 gate validates at **T=dte/365**. Applying 365-measured vol-point offsets on a 252-convention baseline inflates the offset's price impact by ≈√(365/252) ≈ **+20%** (first-order vega scaling). Consequences: (i) **AC-2 does not validate the engine** — it validates the sigma resolver under a different time convention; the packet's header "AC-2 real-chain pricing error −10.4%" implies engine-level fidelity it doesn't have; (ii) every CALIB−FLAT delta in the compare CSV is overstated ~15-20% in magnitude — BCD main ≈ +$27k not +$5.4k, NNB ≈ +$24k not +$15.7k, A2 ≈ −$1k not −$11k (all still consistent with the packet's dispositions, none consistent with its more confident sentences); (iii) cross-strategy *rankings* (the flip analysis) are mostly unaffected — the bias is multiplicative on all offset effects — so §4 survives. **Condition**: run the cheap sensitivity (offsets ×√(252/365)≈0.831, or a 365-convention rerun) and attach it to the packet before any cell-level absolute is quoted downstream; state the AC-2 scope correctly.
2. **Mode trade-set drift**: n differs across modes (NNB 36/34/37, carve 19/20/20, totals 3316/3366/3438) because credit>0/stop paths alter position lifecycles. Mode deltas on small-n cells mix pricing with entry-composition. Fine for franchise-level reading; not fine for small-margin cells — which is another reason the BCD/carve absolutes cannot be sign-resolved by this engine.
3. Missing compare row for a live cell (ic_hv HIGH_VOL|LOW|NEUTRAL) — emit empty-cell rows explicitly.

## Verdict summary

| Packet claim | Verdict |
|---|---|
| Routing map (hand-reconstructed) | FLAWED — 2 HV cells mislabeled vs behavior; cache predates SPEC-113; "21 格" unreconcilable; "HV CALIB 全部为正" false (BCS_HV LOW\|BEARISH −$4.0k); IC exception unnamed (NNN cell); 1 live cell missing from CSV |
| BCD family: no live change, SPEC-122 arbitration | CONFIRMED (not status-quo bias — the adverse model evidence is itself unvalidated; conditions: relabel weak defenses, pre-register SPEC-122 criteria + deadline) |
| A1 CLOSED | CONFIRMED (A1-review conditions carry over) |
| A2 CLOSED | FLAWED framing (−0.35σ cited as harm) — change to **DEFER-CLOSED** for consistency with A4 (same SPEC-122 dependency) |
| SPEC-060 dead cell "no strategy meaningfully positive under CALIB" | FLAWED as stated — own CSV shows ic_hv +$50.6k (n=24), bps_hv +$21.0k (n=11) force-entry; off-regime artifacts, so *wait stands*, but route these to Q088's list and fix the sentence |
| NNB PESS recorded, no action | CONFIRMED with caveats (PESS = persistent-miscalibration band, not worst case; flip-at-exit variant to Q088; +$15.7k is 1.2σ) |
| 48% instability → Q088, "no flip indicts live routing" | Flip count CONFIRMED (13/27); the no-indictment claim **FALSE for LOW_VOL\|LOW\|BULLISH (main BCD cell, 1,382 days)** — correct the sentence, raise SPEC-122 stakes; Q088-not-now CONFIRMED |
| Engine isolation argument | PARTIALLY SOUND — T=252 vs 365 convention mismatch overstates all CALIB haircuts ~15-20%; AC-2 validates the resolver, not the engine; mode trade-set drift on small-n cells |

**RATIFY-WITH-CONDITIONS.** Blocking conditions before the packet seals: (C1) publish the corrected behavioral routing table with the named exceptions and fix the four false/overstated sentences (§1 HV/IC claims, §3 SPEC-060 sentence, §4 no-indictment sentence); (C2) A2 → DEFER-CLOSED; (C3) SPEC-122 pre-registered pass/fail criteria + deadline before quote collection; (C4) T-convention sensitivity rerun attached, AC-2 scope restated. Non-blocking: regenerate the stale signal cache (post-SPEC-113) before its next use as a routing source; emit missing live-cell rows; register the PESS flip-at-exit variant in Q088.

None of the conditions changes a disposition — every "no live change" verdict is correct, and in three places the corrected numbers make the packet's caution *better* justified than its own text does.
