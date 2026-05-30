# Q078 — Framing 2nd Quant Pre-Review Packet

**Date**: 2026-05-27
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **Pre-research framing review** (before P0 anchored memo). Mirrors Q075 framing workflow.
**Decision sought**: PASS framing scope / REVISE / REJECT, before Quant opens Q078 P0.

---

## 0. TL;DR

Q078 evaluates whether adding a **weekly cadence + sized entry queue** ("ladder") on top of current selector-gated SPX BPS entries improves **(a)** long-run BP utilization, **(b)** ROE, **(c)** tail risk metrics (W20d/W63d), and **(d)** expiry concentration — **without modifying any selector gate or strategy logic**.

**Trigger**: PM observation (2026-05-27) that current 8 SPX BPS spreads all sit at 6/18 expiry — opportunistic clustered entries during one open window. PM proposes weekly ladder with 10% BP per week.

**Architectural framing** (the most important framing decision):

```
LADDER = execution layer
  - decides WHEN (weekly cadence) + HOW MUCH (sizing target)
  - does NOT override selector gates
  - defers to selector for WHAT (strategy type) + IS-IT-OPEN (verdict)

SELECTOR = strategy/decision layer (UNCHANGED)
  - all SPEC-051/054/058/060/077 gates respected
  - WAIT cells stay WAIT
  - regime/trend/IV signals unchanged
```

**Not Q078**:
- Mechanical override of selector gates (rejected upfront)
- Changing 21 DTE roll from SPEC-077
- Modifying Q042 / HV Ladder
- Adding new strategy primitives
- Changing booster Gate F

**Q078 IS**: a research investigation into whether the *operational cadence + sizing structure* atop selector improves long-run portfolio outcomes vs current "PM opens spreads when bandwidth allows" baseline.

**Cash/BOXX is a valid endpoint** — if ladder shows no improvement, DOCUMENT the operational principle and continue current ad-hoc approach.

---

## 1. Research Target — precise definition

### 1.1 Ladder definition (the candidate)

```
Cadence:      every Monday 10am ET (or PM-chosen weekly slot)
Sizing:       target N contracts that consume ~10% NLV in BP at entry
              (subject to per-trade BP target from selector — currently 15% NLV)
Entry rule:   IF selector("today") returns BPS verdict (not REDUCE_WAIT)
                → open at 30 DTE (NORMAL) / 35 DTE (HIGH_VOL) / 45 DTE (LOW_VOL)
              ELSE
                → skip this week; queue next week
Exit rule:    PER SPEC-077 — 60% profit (min 10d held) OR 21 DTE roll
              (NOT PM-proposed 15 DTE — see §5)
Cluster rule: 1 entry per weekly cadence slot, no intra-week additional entries
              UNLESS booster transitions ON (see Q4)
Concurrency:  at steady state, ~4 weekly cohorts × (selector pass rate) parallel
              positions
```

### 1.2 Baseline (what ladder is compared against)

```
Baseline = "opportunistic ad-hoc entry":
  PM enters spreads when they happen to look at dashboard + selector permits
  Current behavior: cluster entries on one open day (see 8 spreads at 6/18)
  Cadence is irregular; sizing is PM judgment
```

Both ladder and baseline use the **same selector**. Difference is only **WHEN** entries fire.

### 1.3 Sample for P1 attribution

```
26y historical SPX (2000-01 → 2026-05)
For each Monday in sample:
  - Compute selector verdict at Monday close
  - Simulate ladder: IF BPS → open at 30 DTE with sizing rule
  - Simulate baseline: irregular entry (proxy via "every N business days" or
    sampled from historical entry frequency observed in real PM activity)
Comparison metrics:
  - BP utilization timeline (avg, max, % time at cap)
  - Cum ROE
  - MaxDD, W20d, W63d
  - Expiry concentration (single-expiry max % of total max-loss)
  - Active position count distribution
  - Realized vs theoretical fill quality
```

---

## 2. Non-Negotiable Constraints

Locked upfront. 2nd Quant can REJECT framing but cannot loosen these for "more interesting" research.

| # | Constraint | Source |
|---|---|---|
| 1 | **Ladder defers to selector gates** — no mechanical override of WAIT verdicts | Quant framing principle |
| 2 | **SPEC-077 21 DTE roll** unchanged (no 15 DTE) | Selector authoritative; PM 15 DTE proposal needs separate study |
| 3 | SPEC-104 Layer-1 (stress 50% / 2nd-leg 40%) untouched | Frozen architecture |
| 4 | SPEC-105 v2 Gate F booster untouched | Frozen |
| 5 | SPEC-103 V1-V7 vetoes untouched | Frozen |
| 6 | HV Ladder demoted (0% production) | Q073 finding |
| 7 | Q042 staged ramp unchanged | SPEC-104 governance |
| 8 | **No new strategy primitives** — only BPS in NORMAL regime, IC in NEUTRAL/HIGH IV cells | Selector existing universe |
| 9 | **Cash / BOXX is valid endpoint** — if ladder no improvement, DOCUMENT principle | Q075 lesson |
| 10 | Portfolio-level validation required before SPEC | `feedback_portfolio_level_research` |
| 11 | No candidate priority pre-decided by Quant | `feedback_layer_n_replacement_research` |
| 12 | Implementation ease ≠ research priority | Same |
| 13 | **Booster off-ladder bonus entries** are research question, not assumed | See Q4 |

---

## 3. P1 Attribution Plan (mandatory before P2)

P1 classifies ladder behavior under historical conditions. P1 does NOT promote any specific cadence.

### 3.1 Ladder cadence variants to test

```
V1: weekly (every Monday)
V2: bi-weekly (every other Monday)
V3: daily-conditional (every day selector permits, but ≤1 entry per 5d cluster)
```

V1 is PM's proposal. V2 and V3 bracket above/below for sensitivity.

### 3.2 Sizing variants

```
S1: 10% NLV BP target per entry (PM's proposal)
S2: 15% NLV (selector's bp_target_normal default)
S3: dynamic (sizing = remaining capacity to fill 35% NLV strategy ceiling)
```

### 3.3 Baseline comparison

Real PM ad-hoc entry approximated by:
- **Baseline A**: every 21 trading days (matching ~once per DTE cycle), N=1 entry
- **Baseline B**: cluster entry (3-5 entries on one day, then 30-DTE silence) — match observed 8-at-6/18 behavior
- **Baseline C**: zero (no SPX BPS at all, pure cash + Q042) — to isolate ladder's contribution

### 3.4 Metrics per ladder variant × baseline

```
Backtest 26y, compute per variant:
  - Net ann ROE
  - Cumulative PnL
  - BP utilization timeline: mean, p50, p95, max
  - MaxDD, W20d, W63d
  - Sharpe
  - Expiry concentration: max % of total max-loss in single expiration date
  - Active position count: mean, max, % time at cap
  - Selector PASS rate: % of Mondays where ladder fires vs skips
  - Forced 21 DTE roll count
  - Per-position avg PnL, hit rate
  - Booster overlap days: % time booster active
```

### 3.5 Critical comparison

```
Compare ladder vs baseline on three orthogonal axes:
  1. ROE: which adds more PnL/yr?
  2. Tail: which has tighter W20d/W63d?
  3. Diversification: which has lower single-expiry concentration?

Promote ladder ONLY IF improvements on (1) AND (3) without degrading (2)
```

### 3.6 P1 deliverables

```
research/q078/q078_p1_attribution_memo.md
research/q078/q078_p1_ladder_results.csv          (per variant × baseline)
research/q078/q078_p1_bp_utilization_timeline.csv
research/q078/q078_p1_expiry_concentration.csv
research/q078/q078_p1_selector_pass_rate.csv
research/q078/q078_p1_attribution.py
```

---

## 4. P2 Candidate Variants (priority TBD by P1)

P2 prototypes alphabetical, NOT ranked:

| Code | Variant | Description |
|---|---|---|
| L0 | Baseline ad-hoc | Current PM behavior (no ladder) |
| L1 | Weekly 10% | PM's original proposal |
| L2 | Weekly 15% | Selector default sizing |
| L3 | Bi-weekly 15% | Half-frequency, full sizing |
| L4 | Daily-conditional 5% | Daily check, smaller sizing, ≤1 per 5d cluster |
| L5 | Weekly 10% + booster bonus | L1 plus off-ladder daily check when Gate F active |

Priority decided by P1 attribution, not Quant prior.

---

## 5. P3 Transition / Crisis Forensic

Same framework as Q075 P3:
- 5 named crisis windows (DotCom 2000-03, PreGFC 2007-07, Vol 2018-02, COVID 2020-02, Bear 2022-01)
- Ladder behavior during stress front-edge (10d pre-trigger)
- Forced-exit handling (when selector says stress, ladder skips that week)
- Worst single trade per variant

---

## 6. P4 Portfolio Integration

Unified-NLV combined simulator from start (`feedback_portfolio_level_research`).

```
Metrics:
  ΔROE vs SPEC-104 + SPEC-105 v2 baseline (current production)
  MaxDD, W20d (V2), W63d (V3)
  Sharpe
  Capital competition with Q042
  Operational burden (entries/year per variant)
  Bootstrap (block=250, 20 seeds)
  Walk-forward H1 (2000-2012) / H2 (2013-2026)
  Crisis window behavior

Pass bar (Q078-specific, per Q075 §8 framework):
  Strong:  ΔROE ≥ +0.20pp + risk thresholds pass
  Soft:    +0.05 to +0.20pp + risk thresholds pass
  Reject:  < +0.05pp OR any risk threshold fail
  DOCUMENT: < +0.05pp but operational discipline value documented

Risk thresholds:
  V1/V2/V3 pass mandatory
  Worst 20d degradation ≤ +0.25pp vs baseline
  Worst 63d degradation ≤ +0.25pp vs baseline
  Expiry concentration (any single expiry > 60% total max-loss) → flag
```

---

## 7. Six Questions for 2nd Quant

### Q1 — Architectural framing correct?

Ladder as execution layer (defers to selector) vs strategy layer (mechanical override). Quant prior: execution layer only; mechanical override pre-rejected.

**2nd Quant: confirm execution-layer framing, or any case for partial override?**

### Q2 — Baseline definition adequate?

Three baseline options (A: every 21d, B: cluster, C: zero). Quant prior: use all three for sensitivity. The "right" baseline is question of what we're trying to improve.

**2nd Quant: confirm 3-baseline approach, or pick one as canonical?**

### Q3 — 21 DTE roll (SPEC-077) vs PM's proposed 15 DTE

PM proposed 15 DTE exit. Quant kept SPEC-077 21 DTE in framing. **15 vs 21 is a separate research question** (different gamma exposure window, would need its own attribution).

**2nd Quant: confirm Q078 keeps 21 DTE; suggest opening Q079 for "15 vs 21 DTE roll" study? Or fold into Q078 as a 4th axis (variant set × roll horizon)?**

### Q4 — Booster off-ladder bonus entry (variant L5)

Q074.2 showed booster ΔROE = +0.014pp at $894k NLV. Adding "off-ladder bonus entries when Gate F active" might capture more booster benefit but adds operational complexity.

**2nd Quant: include L5 in P2, or reject as scope creep (Gate F is Q074 territory)?**

### Q5 — Cluster rule strictness

Ladder = "1 entry per weekly cadence". But what if a Monday entry is skipped (selector WAIT) and Tuesday/Wednesday becomes a clear PASS — does ladder catch up?

Three approaches:
- **strict**: missed Monday = missed week, wait until next Monday
- **catch-up**: if selector PASS on Tue/Wed of same week and Monday was skipped, allow that week's entry
- **rolling**: cadence is "next selector PASS day after last entry + 5 trading days"

Quant prior: **strict** preserves clean structure but loses optionality. **catch-up** is compromise. **rolling** breaks cadence concept.

**2nd Quant: pick one or have P1 test all three?**

### Q6 — Success criteria — what wins?

Three axes (ROE / Tail / Diversification). If ladder improves (1) ROE +0.05pp AND (3) Diversification (max single-expiry drops from 100% to 30%), but (2) Tail degrades by +0.20pp W20d (within 0.25pp limit) — is that promote or reject?

Quant prior: framing in §6 promotes if (1) AND (3) without degrading (2). But "without degrading" is binary; what's the trade-off weight?

**2nd Quant: confirm "no Tail degradation" is strict gate, or weighted vs ROE/Diversification improvement?**

---

## 8. Caveats Self-Disclosed

1. **Selector PASS rate matters**. SPEC-106 audit showed ~50% of cells gated. Realistic ladder fire rate is much lower than "every Monday". Expected steady-state BP from SPX BPS via ladder ≈ 20%, not 40%. Q078 must verify this empirically.

2. **PM 1hr/day bandwidth**. Weekly ladder cadence is good fit. Daily-conditional (V3) might exceed bandwidth even with simple "open if selector PASS" rule.

3. **Backtest entry-cadence assumptions**. Real PM ad-hoc entries don't follow a clean pattern. Baseline B (cluster) is closest to observed reality but only 1 data point (8 at 6/18). Baselines A and C bracket above/below.

4. **Operational discipline is hard to measure**. "Ladder enforces discipline" is qualitative. P4 should not assume PM follows ladder perfectly in production — but historical simulation does assume perfect execution.

5. **No new alpha source**. Q078 is restructuring EXISTING strategy entries, not finding new ROE source. Pre-decision the prior: ROE improvement is mechanical (closer to selector's intended ROE), not magic.

6. **PM 15 DTE proposal not adopted**. If 2nd Quant pushes for it, opens scope creep + conflicts with SPEC-077. Quant recommends Q079 separate study.

7. **Booster overlay timing**. Currently Gate F fires ~22% of normal days. Ladder fires weekly Monday. Probability that "Monday is a booster day" is ~22% × 1/5 = ~4.4% per Monday. Booster contribution via L5 may be small.

8. **Expiry concentration penalty quantification**. We hand-wave "concentration bad" but don't have explicit cost. Need to model how single-expiry concentration translates to tail risk.

---

## 9. Decision Matrix

| 2nd Quant verdict | Action |
|---|---|
| **PASS framing** + Q1-Q6 accepted | Quant opens Q078 P0 anchored memo with this scope |
| **REVISE** (specific scope / question changes) | Quant re-submits framing packet |
| **REJECT framing** (Q078 wrong concept) | Q078 closes; current ad-hoc approach remains |
| **PASS with revisions** | Quant proceeds with logged revisions |
| **REQUIRE Q079 split** | Open Q079 for 15-vs-21 DTE roll study before/alongside Q078 |

---

## 10. Quant Sign-off

Quant submits Q078 framing pre-review 2026-05-27. Awaiting 2nd Quant verdict before opening P0.

> Q078 framing investigates whether systematic weekly-cadence + sized-entry queue ("ladder") on top of selector-gated SPX BPS entries improves long-run BP utilization, ROE, tail risk, and expiry concentration vs current ad-hoc PM entry pattern. Constraints freeze SPEC-104 / SPEC-105 v2 / SPEC-077 21 DTE roll / Q042 / HV / V1-V7. P1 attribution decides cadence + sizing variant priority. Cash/baseline-ad-hoc is a valid winning outcome. PM-proposed 15 DTE exit deferred to potential Q079. Ladder is strictly execution layer — no override of selector gates.

---

## 11. Supporting Files

- `strategy/selector.py:38,68` — SPEC-077 21 DTE roll rule
- `strategy/selector.py:60-83` — DTE + BP target/ceiling per regime
- `strategy/selector.py:1060-1180` — NORMAL regime selector logic
- `strategy/selector.py:949-1058` — LOW_VOL regime
- `task/SPEC-077.md` — 21 DTE roll (if exists)
- `task/SPEC-104.md` — Arch-3 baseline (unchanged)
- `task/SPEC-105-v2.md` — Gate F booster (unchanged)
- `task/SPEC-106.md` — matrix consistency (in flight)
- `research/q074/q074_final_memo.md` — booster baseline ROE +0.014pp at $894k
- `research/q075/q075_p4_memo.md` — Q075 closure precedent (DOCUMENT)
- `~/.claude/.../memory/feedback_layer_n_replacement_research.md`
- `~/.claude/.../memory/feedback_layer_n_replacement_outcome.md`
- `~/.claude/.../memory/feedback_portfolio_level_research.md`

PM trigger context:
- 2026-05-27 PM observation: 8 SPX BPS spreads all at 6/18 expiry, BP utilization ~35% vs research 80% cap
- Proposed weekly 10% BP ladder, 30→15 DTE
- Quant flagged 15 DTE conflicts SPEC-077; framing kept 21 DTE
