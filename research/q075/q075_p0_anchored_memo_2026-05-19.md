# Q075 P0 — Anchored Memo (PM + 2nd Quant Locked Scope)

**Date**: 2026-05-19
**Author**: Quant Researcher
**Status**: **P0 LOCKED** — applying 6 revisions from 2nd Quant framing review (PASS 2026-05-19)
**Source**: `task/q075_framing_2nd_quant_review_packet_2026-05-19_Review.md`
**Parent**: SPEC-104 Arch-3 (Layer 1) + SPEC-105 v2 Gate F (Layer 2) — UNCHANGED
**Purpose**: Anchor Q075 scope before P1 attribution starts. No P1 work until this is acknowledged.

---

## 0. TL;DR (must read)

Q075 studies whether the "IVP-blocked normal-state" days have a defined-risk replacement payoff that beats cash/BOXX without disturbing Layer-1 or Layer-2.

> **Cash / BOXX is a valid winning outcome.** This research is NOT biased toward "must find a trade." If P1 attribution shows the blocked subset is dominated by transition-warning or trend-deteriorated regimes where every replacement candidate underperforms cash on risk-adjusted basis, the correct conclusion is "do nothing" — and that conclusion will be promoted to a documented operational principle rather than a SPEC.

```
Layer 1 (survival, SPEC-104): stress 50%, second-leg 40%, V1-V7
Layer 2 (income, SPEC-105 v2): normal cap 80→90 when Gate F active
Layer 3 (THIS RESEARCH):       replacement payoff when Gate F is correctly off
                               AND BPS_NNB entry is correctly blocked
                               AND Layer-1 is not yet engaged
```

**Sequence**: P0 (this) → P1 attribution → P2 candidate prototypes (priority decided by P1 data) → P3 transition forensic → P4 portfolio integration → P5 PROMOTE / DEFER / REJECT.

**No candidate ranking before P1 data.** No "implementation cost" priority bias (per `feedback_layer_n_replacement_research`).

---

## 1. Layer-3 Framing (locked by 2nd Quant Q1 PASS)

| Layer | Owner SPEC | Status |
|---|---|---|
| Layer 1 — Survival | SPEC-104 / SPEC-103 V1-V7 | UNCHANGED, untouchable by Q075 |
| Layer 2 — Benign income | SPEC-105 v2 Gate F | UNCHANGED, untouchable by Q075 |
| **Layer 3 — IVP-blocked replacement** | **Q075 → potential future SPEC** | Research scope |

Layer 3 is a **regime-conditional payoff library** that activates only when Layer-2 is correctly off and Layer-1 not yet engaged. It is structurally distinct from "loosening Gate F" or "adding HV-style short-vol."

---

## 2. Research Sample (Revision 1 applied)

### 2.1 Primary sample — Q075 main target

```
Daily filter (all must hold):
  normal_state == True
  stress_active == False
  second_leg_active == False
  BPS_NNB new entry blocked (BPS_NNB_IVP_UPPER = 55 entry filter trips)
  Gate F inactive BECAUSE:
    IVP_252 >= 55 AND VIX >= 15
  AND the other 5 benign conditions OTHERWISE pass:
    SPX > MA50
    ddATH > -4%
    VIX < 22
    VIX_5d_change <= +1.5
    (above_ma50 + ddath + vix + vix_5d_change all clear)
```

This is "pure IVP/vol-blocked, otherwise benign." This is the only sample on which Q075 candidate research is conducted.

**Estimated size**: ~10% of total trading days (~25 days/yr) per Q074.1b cross-reference. P1 will report exact count.

### 2.2 Secondary sample — diagnostic only

```
Gate F inactive BECAUSE one of:
  SPX <= MA50
  OR ddATH <= -4%
  OR VIX >= 22         (this would also flip stress_active in most cases)
  OR VIX_5d_change > +1.5
```

Secondary sample is reported in P1 attribution **only for diagnostic comparison**. No Q075 candidate is designed for this regime. Trend-already-broken / drawdown / VIX-rising states are closer to stress, handled by Layer-1 mechanisms (or by NOT trading).

**Critical rule**: P1 must report Primary and Secondary as separate tables, NEVER aggregated. P2 candidates only consume Primary.

---

## 3. Non-Negotiable Constraints

Carried from framing packet §2, all locked:

| # | Constraint | Source |
|---|---|---|
| 1 | SPEC-104 Layer-1 caps (80/50/40) unchanged | SPEC-104 frozen |
| 2 | SPEC-104 R5/R6 trigger definitions unchanged | Trigger immutability |
| 3 | SPEC-105 v2 Gate F unchanged | Q074.2 just deployed |
| 4 | V1-V7 vetoes unchanged | SPEC-103 frozen |
| 5 | HV Ladder remains demoted (production = 0%) | SPEC-104 + Q073 finding |
| 6 | Q042 staged ramp unchanged (target 17.5%) | SPEC-104 governance |
| 7 | No naked / uncapped short-vol | PM account discipline |
| 8 | Defined-risk only (explicit max loss per trade) | Operating principle |
| 9 | **Cash / BOXX is valid endpoint** | Q075 framing principle |
| 10 | Portfolio-level validation required before SPEC | `feedback_portfolio_level_research` |
| 11 | No candidate priority pre-decided | `feedback_layer_n_replacement_research` |
| 12 | Implementation ease ≠ research priority | Same |

---

## 4. P1 Attribution Plan (mandatory before any P2 work)

P1 classifies the blocked regime. P1 does NOT promote any strategy. P1 does NOT construct SPEC candidates.

### 4.1 Four-Type partition (Revision 2 applied)

| Type | Characteristic | Hypothesized payoff |
|---|---|---|
| **A: False block** | VIX < 15 absolute (already handled by Gate F v2 escape) — should be ~empty in Primary sample by construction | If non-empty: debug Gate F deployment |
| **B: Transition warning** | VIX 15-22, IVP ≥ 70, VIX_5d_change > +0.5, ddATH expanding (≥ +1pp worsening in 5d) | DANGER zone — cash likely best |
| **C: Elevated-IV pre-stress controlled** *(renamed per G2 review 2026-05-19; P1 measured P(stress 10d)=50% — original "high-vol controlled" label too optimistic)* | VIX 15-22, IVP ≥ 55, VIX flat or falling (VIX_5d_change ≤ +0.5), ddATH stable or improving | Premium harvest opportunity IF candidate survives forced-exit-on-stress simulation |
| **D: Trend-deteriorated** | SPX ≤ MA50 OR MA50 slope ≤ 0 OR ddATH ≤ -6% | Avoid; should be ~empty in Primary by construction (SPX > MA50 in Primary), reported for diagnostic completeness only |

Note: Type A and Type D should be near-empty in Primary sample by construction (Primary requires VIX ≥ 15 and SPX > MA50). They are listed for completeness — if P1 finds non-zero population in Primary Type A or D, it indicates a sample-construction bug or edge case worth investigating.

**Sanity check (per 2nd Quant P0 review 2026-05-19)**: If Type A or Type D exceeds **5% of Primary sample**, pause and review sample construction before P2. This is a guardrail, not a blocker — non-zero counts may exist as edge cases (e.g., same-day MA50 cross, ddATH boundary days), but >5% indicates upstream bug (Gate F deploy drift, IVP_252 calculation issue, sample filter mistake).

The two operational types are **B and C**. Q075 candidates will be evaluated separately within B and C.

### 4.2 Bucketing axes (for both Primary and Secondary)

```
VIX absolute:        15-17 / 17-19 / 19-22
IVP_252:             55-70 / 70-85 / 85+
VIX 5d trend:        falling (<-0.5) / flat (-0.5 to +0.5) / rising (+0.5 to +1.5)
SPX trend:           above MA50 (Primary always true) / below MA50 (Secondary only)
MA50 slope:          positive (5d) / negative
ddATH:               0 to -2 / -2 to -4 (Primary stops here; Secondary continues -4 to -6, below -6)
```

### 4.3 Forward measures per bucket

```
Forward SPX return:        5d / 10d / 20d
Forward VIX change:        5d / 10d / 20d
P(stress trigger):         5d / 10d / 20d
P(second-leg in window):   20d / 60d
Worst 10d / 20d realized PnL (held-position baseline)
Mean forward 20d PnL (held-position baseline)
```

### 4.4 Hypothetical payoff PnL per bucket (alphabetical — NOT ranked)

```
H1: cash / BOXX yield baseline (= 4.3% annualized daily accrual)
H2: BPS_NNB current spec — counterfactual (informational only, not actually entered)
H3: low-delta short-DTE BPS (e.g., 0.10-0.15 delta, 7-21 DTE, defined risk)
H4: small iron condor (defined-risk, neutral, sub-baseline size)
H5: bear call spread (call-side premium, defined-risk)
H6: calendar / diagonal SEED ONLY (compute hypothetical PnL; P2 prototype only if Type C explicitly supports)
```

**Critical**: H1 cash is the hurdle. H2 is informational (we do NOT actually re-enable BPS_NNB entry in blocked days — that would violate the entry-filter integrity). H3-H6 are candidate payoffs whose priority is decided by P1 data per Type B / C subset.

### 4.5 Capital context per bucket (Revision 5 applied)

P1 must also report, per bucket on Primary sample:

```
Average BP utilization on these days (from historical state)
Existing SPX exposure on these days (held positions $ + delta)
Q042 active or not on these days (active/inactive count)
Cash residual on these days (post-held-positions, pre-replacement)
```

Reason: replacement trade may compete for capital with existing safety buffer. Capturing this from P1 (not P4) prevents wasted prototyping if blocked days routinely have low cash residual.

### 4.6 P1 deliverables

```
research/q075/q075_p1_attribution_memo.md
research/q075/q075_p1_primary_sample_buckets.csv
research/q075/q075_p1_secondary_sample_buckets.csv
research/q075/q075_p1_type_classification.csv     (A/B/C/D counts per year)
research/q075/q075_p1_hypothetical_pnl.csv        (H1-H6 per bucket per Type)
research/q075/q075_p1_capital_context.csv         (BP / SPX / Q042 / cash per bucket)
research/q075/q075_p1_attribution.py
```

---

## 5. P2 Candidate Universe (priority TBD by P1)

Candidates listed alphabetically with C0/C1 split (Revision 6) and C2 wording fix (Revision 3):

| Code | Candidate | Notes |
|---|---|---|
| **C0** | **Do nothing beyond existing held positions** | Literal inaction; held SPX + Q042 + cash already producing PnL |
| **C1** | **Cash / BOXX active reserve** | Intentional reserve allocation; if model treats cash as BOXX-yielding (which it does per Q073/Q074 simulator), C0 == C1 economically. State this equivalence explicitly in P2 if confirmed. |
| **C2** | **Low-delta short-DTE BPS** | **Lower starting delta (0.10-0.15) and shorter time-at-risk (7-21 DTE), BUT HIGHER gamma sensitivity than 30-45 DTE baseline.** Must test carefully — short-DTE is more pin-risk + gap-down sensitive. Defined risk via spread width. |
| **C3** | **Small iron condor** | Defined-risk, neutral, sub-baseline size (e.g., 1/3 of normal BPS size). Both wings of premium. |
| **C4** | **Bear call spread** | Call-side premium when SPX extended, defined-risk. |
| **C5** | **Calendar / diagonal** | SEED ONLY in P1. P2 prototype only if Type C attribution explicitly supports term-structure logic. Default: skip to P3. |

### 5.1 Hard requirements for ALL non-cash candidates

```
Defined risk per trade (explicit max loss in $)
Small position size (≤ 1/3 of baseline BPS sleeve allocation)
Short holding (≤ 21 DTE preferred, 30 max)
Hard stop on losing side (no rescue rolls)
VIX rising guard: block entry if VIX_5d_change > +1.5
ddATH expanding guard: block entry if ddATH worsens ≥ +1pp in 5d
No second entry per blocked-day cluster (cluster = consecutive blocked days)
No averaging down
```

### 5.2 P2 priority decision

After P1 attribution, Quant proposes priority order in P2 memo. Priority is determined by:

```
- Which Type (B vs C) dominates Primary sample
- Which payoff (H3-H6) shows positive hypothetical PnL in dominant Type without large worst-case
- Capital context (don't prototype candidates that always conflict with cash residual constraint)
```

Implementation cost is NOT a priority criterion.

### 5.3 P2 deliverables

```
research/q075/q075_p2_candidate_priority_memo.md  (ranking rationale from P1 data)
research/q075/q075_p2_prototype_C[X]_results.csv  (per prototyped candidate)
research/q075/q075_p2_sweep.py
```

---

## 6. P3 Transition / Crisis Forensic

Re-use Q073/Q074 forensic framework with Q075-specific candidate substitution:

```
Replacement strategy active in prior 10d / 20d before stress trigger
Failed-benign count (replacement active + subsequent stress + incremental loss)
Worst single transition incremental loss
Crisis windows: 2000-03, 2007-07, 2018-02, 2020-02, 2022-01
```

**Rejection rule** (revised per 2nd Quant P0 review 2026-05-19): any candidate with **material or repeated** transition-loss concentration is rejected, per §8.2 thresholds (i.e., at most 1 episode > -0.50% NLV per 5y window; no new crisis-window failure; worst 20d/63d degradation ≤ +0.25pp vs baseline). Single small transition losses are acceptable if §8.2 thresholds hold (Q074 B4 precedent: failed-benign episodes existed but were small + total contribution positive). Q075 operates in vol-warning regime by design — tail behavior is more important than mean improvement, but the bar must be quantitative not absolute.

### 6.1 P3 deliverables

```
research/q075/q075_p3_transition_forensic_memo.md
research/q075/q075_p3_transition_events.csv
research/q075/q075_p3_crisis_breakdown.csv
research/q075/q075_p3_severity_summary.csv
research/q075/q075_p3_top_losses.csv
```

---

## 7. P4 Portfolio Integration

Per `feedback_portfolio_level_research`: unified-NLV combined simulator from start. Q075 candidate added on top of SPEC-104 + SPEC-105 v2 baseline.

### 7.1 Metrics required

```
Net ann ROE (vs SPEC-104 + SPEC-105 v2 baseline)
ΔROE pp
MaxDD
Worst 20d  (V2 ≥ -11%)
Worst 63d  (V3 ≥ -17%)
Sharpe
Capital competition with SPX / Q042 (BP-day consumption profile)
Correlation matrix vs existing sleeves
Operational burden (entries/year, avg holding days)
Crisis window behavior (all 5 named windows)
Bootstrap (block=250, 20 seeds) — Q074-style
Walk-forward H1 (2000-2012) / H2 (2013-2026)
```

### 7.2 P4 deliverables

```
research/q075/q075_p4_validation_memo.md
research/q075/q075_p4_portfolio_metrics.csv
research/q075/q075_p4_walkforward.csv
research/q075/q075_p4_bootstrap.csv
research/q075/q075_p4_crisis.csv
research/q075/q075_p4_capital_competition.csv
research/q075/q075_p4_validation.py
```

---

## 8. Success Criteria (Revision 4 applied — Q075-specific bars)

### 8.1 Economic threshold (lower than Q074 because narrower subset)

```
Strong:   ΔROE ≥ +0.20pp annualized
Soft:     +0.05 to +0.20pp
Reject:   < +0.05pp UNLESS materially reduces risk (e.g., negative correlation with stress)
```

### 8.2 Risk threshold (STRICTER than Q074 because operating in vol-warning regime)

```
V1 (MaxDD ≥ -28%):              pass mandatory
V2 (Worst 20d ≥ -11%):          pass mandatory
V3 (Worst 63d ≥ -17%):          pass mandatory
Worst 20d degradation:           ≤ +0.25pp vs SPEC-104+105v2 baseline (mandatory)
Worst 63d degradation:           ≤ +0.25pp vs SPEC-104+105v2 baseline (mandatory)
No transition-loss concentration: at most 1 episode > -0.50% NLV per 5y window
No new crisis-window failure:    all 5 crisis incremental ≥ -$2k per window
```

### 8.3 PROMOTE rules

```
PROMOTE Strong: Economic Strong + ALL Risk thresholds pass
PROMOTE Soft:   Economic Soft + ALL Risk thresholds pass (staged rollout required)
DOCUMENT:       Economic Reject but Risk pass + insight produced (no SPEC, just operational note)
REJECT:         ANY Risk threshold fails (regardless of Economic)
```

---

## 9. Caveats (carried + sharpened)

1. **Elevated forward stress on blocked days**: Q074 P1 data shows IVP 55-70 → 25.6% next-10d stress; IVP >70 → 46.3%. Any candidate that profits from these days carries asymmetric tail risk. P3 forensic is mandatory.
2. **Topping regime overlap**: Q074.1b showed slow-bull years (2007/2018) had high block rates. Walk-forward H1/H2 must show improvement in BOTH halves; H2-only improvement is rejected (Q074 G3 lesson).
3. **Cash is competitive**: BOXX yield ≥ 4.3% in current environment. Replacement must beat risk-adjusted, not just nominal.
4. **Partial waiting only**: Q042 + held SPX positions still produce PnL on blocked days. Q075 measures **incremental contribution above existing held-position PnL**, not total PnL.
5. **Operational burden constraint**: PM trades ~1hr/day. Any new strategy must have low monitoring burden; clear stop/exit rules. If P2 candidate requires complex monitoring, P4 must penalize.
6. **Q075 inherently more dangerous than Q074**: Q074 raised cap in benign regimes (additive risk to existing benign exposure). Q075 enters NEW positions in IVP-elevated regimes, closer to stress front. Risk thresholds are stricter (§8.2) accordingly.
7. **Short-DTE gamma**: C2 has higher gamma than 30-45 DTE baseline. Short DTE reduces time-at-risk but increases pin-risk and gap-down sensitivity. P3 transition forensic must specifically examine C2's gap-day behavior.
8. **Cash / BOXX endpoint validity**: If P1 + P2 + P3 + P4 collectively show no candidate beats C0/C1 on risk-adjusted basis with risk thresholds satisfied, the PROMOTE-equivalent outcome is **DOCUMENT** ("blocked days are correctly cash days, no SPEC needed"). This is a successful research outcome, not a failure.

---

## 10. Phase Schedule (PM-discretionary timing, per `feedback_spec_review_obligation`)

```
P0: this memo — DONE 2026-05-19
P1: blocked-day attribution → memo + 6 CSVs → Quant decides ready-for-G2 review
G2: 2nd Quant P1 attribution review (light review, optional)
P2: candidate prototype based on P1 priority → memo + per-candidate CSVs
G3: 2nd Quant P2 review (mandatory)
P3: transition forensic → memo + 4 CSVs
P4: portfolio integration → memo + 6 CSVs
P5: final PROMOTE / SOFT / DOCUMENT / REJECT decision → final memo
G4: 2nd Quant final review (mandatory before any SPEC draft)
```

No time locks. PM may pause at any G-review.

---

## 11. PM Acknowledge Checklist (informal, not blocking)

- [x] Layer-3 framing accepted (PM 2026-05-19)
- [x] Cash / BOXX is valid endpoint (PM emphasized 2026-05-19)
- [x] P1 attribution FIRST, no pre-ranking (PM corrected Quant 2026-05-19, memory saved)
- [x] 6 framing revisions applied per 2nd Quant
- [x] 2nd Quant P0 review PASS (2026-05-19), §6 wording softened + Type A/D 5% sanity check added
- [ ] Open P1 attribution script work (NEXT — Quant action)

---

## 12. Files index for this phase

- `research/q075/q075_p0_anchored_memo_2026-05-19.md` (this file)
- `task/q075_framing_2nd_quant_review_packet_2026-05-19.md` — framing packet
- `task/q075_framing_2nd_quant_review_packet_2026-05-19_Review.md` — 2nd Quant PASS w/ 6 revisions

Upstream context:
- `research/q074/q074_1b_forensic_memo.md` — IVP gate dilution discovery (the motivation)
- `research/q074/q074_2_validation_memo.md` — current baseline (SPEC-105 v2 deployed)
- `research/q073/q073_final_memo.md` — Q073 portfolio framework (HV demote rationale)
- `task/SPEC-104.md` / `task/SPEC-105-v2.md` / `task/SPEC-103.md`
- `signals/selector.py` — `BPS_NNB_IVP_UPPER = 55` entry gate

Memory references:
- `feedback_layer_n_replacement_research.md`
- `feedback_survival_vs_income_layering.md`
- `feedback_portfolio_level_research.md`
- `feedback_spec_review_obligation.md`

---

## 13. Quant Sign-off

Q075 P0 anchored memo locks scope per:
- 2nd Quant framing review PASS w/ 6 revisions (all applied)
- PM Layer-3 framing acceptance (2026-05-19)
- Cash/BOXX endpoint validity (2026-05-19)
- All 12 non-negotiable constraints (§3)
- Four-Type partition with B/C operational + A/D diagnostic
- Primary vs Secondary sample separation (§2)
- Q075-specific success criteria (§8)

Quant ready to open P1 attribution script work upon PM acknowledge.

> Q075 is Layer-3 IVP-blocked normal-state replacement research. The starting hypothesis is *neutral* — Cash / BOXX may be the correct answer. P1 attribution will decide whether any defined-risk replacement (C2/C3/C4/C5) shows positive risk-adjusted contribution in the Primary blocked-day sample. No candidate priority is pre-decided. Implementation cost is irrelevant to research priority. If no candidate beats cash with risk thresholds intact, the research conclusion is "blocked days are correctly cash days" — documented as operational principle, no SPEC drafted.
