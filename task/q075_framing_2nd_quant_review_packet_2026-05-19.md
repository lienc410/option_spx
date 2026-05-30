# Q075 — Framing 2nd Quant Pre-Review Packet

**Date**: 2026-05-19
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **Pre-research framing review** (before P0 anchored memo). Mirrors Q074 framing PASS workflow.
**Decision sought**: PASS framing scope / REVISE / REJECT, before Quant opens Q075 P0.

---

## 0. TL;DR

Q075 studies whether the days where the SPEC-105 v2 Gate F booster is correctly OFF have a better deployment than waiting / cash.

**Layer framing**:
```
Layer 1 (survival): SPEC-104 Arch-3 — stress 50%, second-leg 40%, V1-V7
Layer 2 (benign income): SPEC-105 v2 Gate F — normal cap 80→90 when conditions safe
Layer 3 (THIS RESEARCH): regime-conditional replacement when Layer-2 is correctly off but Layer-1 is not yet engaged
```

**Q075 is NOT**:
- A Gate F relaxation
- An HV Ladder re-promotion
- A Q042 cap expansion
- A change to any Layer-1 trigger
- A naked / uncapped short-vol experiment

**Q075 IS**: a research investigation into whether the "IVP-blocked normal-state" subset has a defined-risk replacement payoff that improves portfolio ROE without disturbing Layer-1 tail or Layer-2 booster behavior. **Cash / BOXX is an explicit valid winning outcome** — research is not biased toward "must find a trade."

---

## 1. Research Target

Precise blocked-day sample definition:

```
normal_state == True
stress_active == False
second_leg_active == False
SPEC-105 v2 Gate F b4_benign_active() == False
  → because (IVP_252 >= 55 AND VIX >= 15)
     AND/OR one of the other booster conditions fails
new SPX BPS_NNB entry blocked
  → BPS_NNB_IVP_UPPER (=55) entry filter (Q063/Q067/Q068/Q069)
```

→ These are days when **both** the booster cap promotion AND the main BPS new-entry are off. Account is genuinely "waiting" except for held positions + Q042 + cash.

**Estimated subset size**: ~21% of normal-state days per Q074.1b (≈ 10% of total trading days, ≈ 25-30 days/yr).

---

## 2. Non-Negotiable Constraints

| Constraint | Source | Why |
|---|---|---|
| SPEC-104 Layer-1 caps (80/50/40) unchanged | SPEC-104 frozen | Q074 design contract |
| SPEC-104 R5/R6 trigger definitions unchanged | SPEC-104 frozen | Trigger immutability principle |
| SPEC-105 v2 Gate F unchanged | Q074.2 PASS | Just deployed; not revisitable here |
| V1-V7 vetoes unchanged | SPEC-103 frozen | Survival guarantees |
| HV Ladder remains demoted (production = 0%) | SPEC-104 + Q073 portfolio finding | HV tail cost confirmed unprofitable in portfolio |
| Q042 staged ramp unchanged (target 17.5%) | SPEC-104 | Q042 has its own SPEC path |
| No naked / uncapped short-vol | Operating principle | PM account discipline |
| **Defined-risk only** | Operating principle | All Q075 candidates must have explicit max loss per trade |
| **Cash / BOXX is valid endpoint** | Q075 framing principle | Research must not bias toward "find a trade" |
| **Portfolio-level validation required before SPEC** | feedback_portfolio_level_research | Q073 lesson: unified-NLV from start |

---

## 3. P1 Attribution (NOT Strategy Construction)

P1 classifies the blocked regime. P1 does NOT promote any strategy. P1 does NOT create SPEC candidates.

### 3.1 Three regime types to test (per 2nd Quant initial framing 2026-05-19)

| Type | Characteristic | Hypothesized payoff |
|---|---|---|
| **A: False block** | VIX low absolute, IVP high because past year quiet, SPX trend OK, ddATH shallow | Possibly continuation; Gate F may already handle (via VIX<15) |
| **B: Transition warning** | VIX 15-22, IVP high, VIX 5d rising, ddATH expanding | DANGER zone — cash likely best |
| **C: High-vol controlled** | VIX elevated, IVP high, VIX flat/falling, SPX stabilizing | Possible premium harvest opportunity |

P1 must measure which Type dominates the blocked-day subset, and what forward behavior each Type produces.

### 3.2 Bucketing axes

```
VIX absolute:    <15 / 15-17 / 17-19 / 19-22
IVP_252:         55-70 / 70-85 / 85+
VIX 5d trend:    rising (>+1.5) / flat (-0.5 to +1.5) / falling (<-0.5)
SPX trend:       above MA50 / below MA50
MA50 slope:      positive (5d) / negative
ddATH:           0 to -3 / -3 to -6 / below -6
```

### 3.3 Forward measures (per bucket)

```
forward 5d / 10d / 20d SPX return
forward 5d / 10d / 20d VIX change
P(stress trigger in 5d / 10d / 20d)
P(second-leg in 20d / 60d)
worst 10d / 20d realized PnL hypothetical
```

### 3.4 Hypothetical payoff PnL (per bucket, all alphabetically listed — NOT ranked)

```
H1: cash / BOXX yield baseline
H2: BPS_NNB current spec (would-be entry if not blocked) — counterfactual
H3: low-delta short-DTE BPS (e.g., 0.10-0.15 delta, 7-21 DTE)
H4: small iron condor (defined-risk, neutral)
H5: bear call spread (call-side premium)
H6: calendar / diagonal seed (only if data supports term-structure logic in Type C)
```

H1 cash baseline is the hurdle. H2 is informational only (we don't actually re-enable BPS_NNB in blocked days). H3-H6 are candidate payoffs.

**No ranking until P1 attribution data shows which Type dominates and which payoff dominates within Type.**

---

## 4. P2 Candidate Universe (NOT Priority-Ranked)

P2 prototypes are conditional on P1 attribution. Initial universe (alphabetical, NOT ranked):

| Code | Candidate | Hypothesis |
|---|---|---|
| C1 | Cash / BOXX | Hurdle; valid winning outcome |
| C2 | Low-delta short-DTE BPS | Reuse BPS framework with reduced gamma exposure |
| C3 | Small iron condor (defined-risk, neutral) | Non-directional premium harvest |
| C4 | Bear call spread | Call-side premium when SPX extended |
| C5 | Calendar / diagonal | Only if P1 supports term-structure logic |

**Priority ranking decided ONLY after P1 attribution result.** Implementation ease is NOT a priority criterion (per feedback_layer_n_replacement_research).

### Candidate hard requirements (apply to ALL non-cash candidates)
```
defined risk per trade (explicit max loss)
small position size (sub-baseline cap allocation)
short holding (≤ 21 DTE preferred)
hard stop (no rescue rolls)
VIX rising guard (block entry if VIX_5d_change > +1.5)
ddATH expanding guard (block entry if ddATH worsens >1pp in 5d)
no second entry per blocked-day cluster
```

---

## 5. P3 Transition / Crisis Forensic

Re-use Q073/Q074 forensic framework:

```
booster (in blocked days) active prior 10d / 20d before stress trigger
failed-benign count (replacement strategy active + subsequent stress)
worst single transition incremental loss
crisis windows: 2000-03, 2007-07, 2018-02, 2020-02, 2022-01
```

Any candidate that **loses money on the way into stress** (Type B days that materialize) is REJECTED regardless of mean PnL.

---

## 6. P4 Portfolio Integration

Per feedback_portfolio_level_research: unified-NLV combined simulator from start, friction = constant daily drag, V2/V3 = point-in-time equity.

Metrics required for any PROMOTE recommendation:

```
Net ann ROE (vs current SPEC-104 + SPEC-105 v2 baseline)
MaxDD
Worst 20d (V2 ≥ -11%)
Worst 63d (V3 ≥ -17%)
Sharpe
Capital competition with SPX / Q042 (BP-day consumption)
Correlation with existing sleeves
Operational burden (entries/year, monitoring complexity)
Crisis window behavior
Bootstrap (block=250, 20 seeds)
Walk-forward H1 / H2
```

PROMOTE bar (Q074-style):
```
Strong: ΔROE ≥ +0.30pp, V1-V3 pass, transitions clean, walk-forward both halves positive
Soft / Strong-eligible: +0.10 to +0.30pp, V1-V3 pass, gap within bootstrap noise
Reject: < +0.10pp OR breaks V1-V3 OR worsens worst-tail OR adds correlated failure mode
```

---

## 7. Six Questions for 2nd Quant (Framing PASS Decision)

### Q1 — Layer-3 framing correct?

Proposed framing positions Q075 as regime-conditional payoff library that activates only when Layer-2 (Gate F) is correctly off and Layer-1 not yet engaged. This is structurally distinct from "loosening Gate F" or "adding HV-style short-vol."

**2nd Quant: confirm Layer-3 framing, or require different conceptual handle?**

### Q2 — Blocked-day sample definition precise enough?

§1 defines blocked days as: normal_state AND not stress AND not 2nd-leg AND Gate F inactive AND BPS_NNB entry blocked. This deliberately excludes:
- Stress days (Layer-1 owns)
- Gate F active days (Layer-2 owns)
- BPS_NNB entry-allowed days (existing matrix owns)

**2nd Quant: is sample definition complete, or should additional exclusions/inclusions be specified upfront?**

### Q3 — P1 attribution sufficient before candidate ranking?

P1 does only classification + hypothetical PnL side-by-side. No candidate gets ranked or promoted before P1 attribution result is reviewed. Three-Type framework (A/B/C) is the proposed regime partition.

**2nd Quant: accept P1 attribution-first sequence, or require additional pre-attribution work (e.g., literature review on slow-bull-topping regimes)?**

### Q4 — Candidate universe complete?

C1 cash, C2 low-delta short-DTE BPS, C3 small IC, C4 BCS, C5 calendar (P1-conditional). All defined-risk. All sub-baseline size.

Notable exclusions:
- Naked short put / uncapped short call — forbidden by constraint
- HV-Ladder-style heavy short vol — forbidden by Q073 finding
- Long-only directional bets — out of strategy framework
- Pure long vol (long call / long put) — possible hedge, NOT income

**2nd Quant: any candidate that should be added or pre-excluded?**

### Q5 — Calendar / diagonal scope

Calendar / diagonal has higher data + implementation complexity than C1-C4. Quant proposal: include as P1 hypothetical (alongside H1-H5) but treat as seed-only in P2 (skip prototype unless P1 attribution explicitly supports term-structure logic for Type C high-vol-controlled).

**2nd Quant: agree with seed-only treatment, or include / exclude entirely upfront?**

### Q6 — Success criteria

Q074-style PROMOTE bar (§6) is proposed: ΔROE ≥ +0.30pp Strong, +0.10 to +0.30pp Soft-eligible, all subject to V1-V3 pass + transition clean.

Notable: at Q074's NLV ($894k), the blocked-day subset is ~10% of total trading days. Even an aggressive ΔROE per blocked day (~+0.3% NLV/day = highly optimistic) would only add ~30 × 0.003 × 100 = ~+0.9pp annual ROE at most — likely much less. So Q075 will likely produce small absolute gains, justified by ROI on bypass-cost-of-waiting.

**2nd Quant: accept these promotion thresholds, or want different bars given the lower expected absolute magnitude?**

---

## 8. Caveats Self-Disclosed

1. Blocked-day subset (~21% of normal days) has elevated forward stress probability per Q074 P1 (IVP 55-70: 25.6%, IVP > 70: 46.3%). Any candidate that profits from those days carries asymmetric tail risk. P3 forensic is mandatory.
2. The sample partially overlaps "topping regimes" (slow-bull years 2007/2018 had high block rate per Q074.1b). Walk-forward H1/H2 must show improvement in BOTH halves to avoid regime over-fit (Q074 G3 lesson).
3. Cash / BOXX is competitive (≥ 4.3% annualized in current environment). Replacement strategy must beat this on risk-adjusted basis, not just nominal PnL.
4. Q042 + held SPX positions still produce PnL on blocked days. The "waiting" is partial — only NEW entry is blocked. Q075 must measure incremental contribution above existing held-position PnL.
5. Operational complexity matters: PM trades ~1hr/day. Any new strategy must have low monitoring burden and clear stop/exit rules.
6. Q075 has higher inherent danger than Q074: Q074 raised cap in benign regimes (additive risk to existing exposure); Q075 enters new positions in IVP-elevated regimes (closer to stress front).

---

## 9. Decision Matrix

| 2nd Quant verdict | Action |
|---|---|
| **PASS framing** + Q1-Q6 accepted | Quant opens Q075 P0 anchored memo with this scope |
| **REVISE** (specific scope / candidate / question changes) | Quant re-submits framing packet |
| **REJECT framing** (Layer-3 wrong concept, or research not justified) | Q075 closes; no P0 |
| **PASS with revisions** | Quant proceeds with logged revisions |

---

## 10. Quant Sign-off

Quant submits Q075 framing pre-review 2026-05-19. Awaiting 2nd Quant verdict before opening P0.

> Q075 framing positions this as Layer-3 regime-conditional replacement research: when SPEC-105 v2 Gate F is correctly off and BPS_NNB entry is blocked, is there a defined-risk payoff that beats cash without disturbing Layer-1 / Layer-2? Constraints freeze SPEC-104 / SPEC-105 v2 / HV / Q042 / V1-V7. P1 attribution decides candidate priority — NOT pre-decided by Quant. Cash / BOXX is a valid winning outcome. PM-corrected from earlier B>A>C ranking misfire (per feedback_layer_n_replacement_research).

---

## 11. Supporting Files

- `research/q074/q074_1b_forensic_memo.md` — Q074.1b IVP gate dilution discovery (motivation for Q075)
- `research/q074/q074_2_validation_memo.md` — Q074.2 portfolio validation (current SPEC-105 v2 baseline)
- `task/SPEC-104.md` — Layer-1 architecture (Arch-3) — UNCHANGED
- `task/SPEC-105-v2.md` — Layer-2 booster Gate F — UNCHANGED
- `task/SPEC-103.md` — V1-V7 vetoes — UNCHANGED
- `research/q073/q073_final_memo.md` — Q073 portfolio framework (HV Ladder demote rationale)
- `signals/selector.py` — `BPS_NNB_IVP_UPPER = 55` (BPS_NNB entry gate, separate from booster gate)
- `~/.claude/.../memory/feedback_layer_n_replacement_research.md` — research sequencing principle
- `~/.claude/.../memory/feedback_survival_vs_income_layering.md` — Layer-1/Layer-2 framing
- `~/.claude/.../memory/feedback_portfolio_level_research.md` — unified-NLV requirement
