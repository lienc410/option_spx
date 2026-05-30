# Q078 P0 — Anchored Memo (PM + 2nd Quant Locked Scope)

**Date**: 2026-05-27
**Author**: Quant Researcher
**Status**: **P0 LOCKED** — 9 revisions from 2nd Quant framing PASS-WITH-REVISIONS (2026-05-27) applied
**Source**: `task/q078_framing_2nd_quant_review_2026-05-27_Review.md`
**Parent**: SPEC-104 Arch-3 + SPEC-105 v2 Gate F + SPEC-077 21 DTE roll — ALL UNCHANGED
**Purpose**: Anchor Q078 scope before P1 attribution starts.

---

## 0. TL;DR (must read)

Q078 investigates whether a **selector-gated weekly entry cadence + sized queue ("ladder")** on top of current SPX BPS strategy improves: (a) BP utilization, (b) ROE, (c) tail risk, (d) expiry concentration — **vs current ad-hoc PM entry pattern**.

**Critical caveat** (R1-pivotal):

> **Ladder may improve expiry dispersion without improving average BP utilization. BP utilization improvement is an empirical question, not an assumption.** SPEC-106 audit showed 50% of selector cells gated; weekly cadence cannot fire on gated weeks. Expected steady-state BP from ladder ≈ 20%, not the "fill 80% cap" intuition PM had.

**Architectural framing** (R1 locked):

```
Ladder = EXECUTION layer
  - decides WHEN (weekly cadence) + HOW MUCH (sizing target)
  - does NOT override selector gates
  - defers to selector for WHAT (strategy type) + IS-IT-OPEN (verdict)
  - if selector says WAIT → ladder skips that slot
  - if selector says IC (not BPS) → ladder decision per P0 design (see §2.4)

Selector = STRATEGY/DECISION layer (UNCHANGED)
  - all SPEC-051/054/058/060/077 gates respected
  - WAIT cells stay WAIT
  - regime/trend/IV signals unchanged
```

**Cash / ad-hoc is a valid endpoint.** If ladder shows no improvement on (b)+(d) without degrading (c), DOCUMENT operational principle.

**Q078 is NOT**:
- Mechanical override of selector gates
- 15 DTE roll change (→ Q079)
- Booster off-ladder bonus entries (→ Q074 territory)
- New strategy primitives
- Q042 / HV / V1-V7 changes

---

## 1. Background

### 1.1 PM trigger (2026-05-27)

PM observed:
- 8 SPX BPS spreads all clustered at 2026-06-18 expiry (29 DTE entry, opened in one window)
- Current BP utilization ~38.87% (combined NLV $894k: 20.13% options + 18.74% equity)
- Research baseline target much higher (80% SPX sleeve cap)

PM proposed: weekly ladder, 10% BP per entry, 30 DTE → 15 DTE exit cycle.

### 1.2 Quant initial response

- Ladder direction = correct (solves expiry concentration + operational discipline)
- 15 DTE conflicts with SPEC-077 21 DTE roll → separate research
- Mechanical override of selector = rejected upfront
- "Fill to 80% via ladder" intuition likely wrong given 50% selector gate rate (SPEC-106 audit)

### 1.3 2nd Quant framing verdict

PASS WITH REVISIONS (2026-05-27). 9 revisions + critical additions applied to this P0.

---

## 2. Research Scope (R1-R9 applied)

### 2.1 Ladder definition

```
Cadence:        weekly (Monday morning slot, PM-chosen)
Sizing:         target consumption ~N% NLV in BP at entry
                (N varies by sizing variant — see §3.2)
Entry rule:     IF selector("Monday close") returns NON-WAIT verdict:
                  → open at selector-provided DTE
                  → sizing target = N% NLV
                ELSE:
                  → skip this slot (apply cluster rule §2.4)
Exit rule:      PER SPEC-077 — 60% profit (min 10d held) OR 21 DTE roll
                NO 15 DTE EXIT (see §2.5)
Strategy type:  PER SELECTOR — if NORMAL+NEUTRAL IV+BULLISH → BPS;
                if NORMAL+NEUTRAL IV+BEARISH/NEUTRAL → IC;
                if LOW_VOL+BULLISH → BCD (debit; ladder must decide §2.4)
Cluster rule:   strict OR catch-up — see §2.4
Concurrency:    at steady state, ~4 weekly cohorts × selector_pass_rate parallel positions
```

### 2.2 R8 — Ladder uses selector-provided DTE / params

**Do NOT hard-code 30/35/45 DTE inside ladder.** Ladder consumes:
- `selector_recommendation.legs[*].dte`
- `selector_recommendation.bp_target_for_regime()`
- `selector_recommendation.strategy_name`

If selector returns BCD (debit) in LOW_VOL, ladder either:
- **(a) Follow selector**: open BCD with selector params (ladder agnostic to credit/debit)
- **(b) Filter to credit-only**: skip non-BPS strategies (ladder is "BPS-cadence" specifically)

**P0 design decision**: ladder uses **option (a) — follow selector**. Ladder is strategy-agnostic execution layer. If selector returns BCD, ladder enters BCD. If selector returns BPS, ladder enters BPS.

(Rationale: option (b) would make ladder partially selector-aware, blurring the layer boundary.)

### 2.3 R2 — Baseline tier

```
Primary canonical:   Baseline B — cluster/ad-hoc
                     (closest to observed PM behavior: 8 SPX BPS at 6/18)
                     Proxy: 4-5 entries on one day, then 30d silence

Sensitivity:         Baseline A — every 21 trading days, 1 entry
                     Baseline C — zero (no SPX BPS, pure cash + Q042 + equity)
```

Main P4 comparison: **Ladder vs Baseline B**. A/C reported for sensitivity discussion only.

### 2.4 R5 — Cluster rule variants

P1a tests 2 (rolling excluded):

```
C1 — Strict weekly:    Only Monday close eval
                       If selector WAIT → skip week
                       Next eval = next Monday

C2 — Catch-up weekly:  Monday close eval first
                       If WAIT → re-eval Tue close, then Wed close
                       Allow ≤1 entry per calendar week (Mon/Tue/Wed only)
                       No Thu/Fri catch-up

EXCLUDED — Rolling:    "next PASS after last entry + 5 trading days"
                       (blurs cadence into daily-conditional, defeats Q078 scope)
```

### 2.5 R3 — SPEC-077 21 DTE roll preserved

Q078 exit rule = SPEC-077 (60% profit OR 21 DTE). **PM's 15 DTE proposal explicitly NOT in scope.**

If PM still wants 15 DTE investigation → open **Q079 — 15 vs 21 DTE Roll / Exit Horizon Study** (separate framing). 15 DTE changes gamma exposure / theta capture / holding distribution — strategy lifecycle research, distinct from execution cadence.

---

## 3. P1 Attribution Plan (R9 staged)

### 3.1 P1a — Cadence + cluster rule

Fixed: sizing S1 (10% NLV), Baseline B
Test variants:

```
V1a — Weekly strict (C1, weekly)
V1b — Weekly catch-up (C2, weekly)
V2  — Bi-weekly strict (C1, every other Monday)
V3  — Daily-conditional (every business day, ≤1 entry per 5d cluster)
```

(V3 is V2-bandwidth-equivalent in number of entries but daily eval. Test for benchmark.)

P1a deliverables:

```
research/q078/q078_p1a_cadence_results.csv
research/q078/q078_p1a_expiry_dispersion.csv      ← R7 metrics (max conc + eff count)
research/q078/q078_p1a_selector_pass_rate.csv
research/q078/q078_p1a_entry_timing.csv
research/q078/q078_p1a_memo.md
```

### 3.2 P1b — Sizing (conditional on P1a winner)

Apply to top 1-2 cadence variants from P1a only:

```
S1 — 10% NLV BP target
S2 — 15% NLV (selector bp_target_normal default)
S3 — dynamic (fills to 35% NLV strategy ceiling)
```

S3 caveat (per R-additional): default exclude from P2 candidates unless P1b shows S3 ≠ ad-hoc-cluster-mechanism systematized. Specific S3 metrics:

```
S3 max single-day BP add
S3 expiry concentration
S3 worst 20d contribution
```

If S3 just systematizes clustering → reject S3.

P1b deliverables:

```
research/q078/q078_p1b_sizing_results.csv
research/q078/q078_p1b_bp_utilization_timeline.csv
research/q078/q078_p1b_memo.md
```

### 3.3 Metrics per variant (full menu)

```
Net ann ROE / ΔROE vs Baseline B
MaxDD / Worst 20d / Worst 63d (V1/V2/V3 check)
Sharpe
BP utilization timeline: mean, p50, p95, max, % time at cap
Max expiry concentration (single max-loss %)
Effective expiry count (Herfindahl inverse, NEW per R7)
Active position count: mean, max, % time at cap
Selector PASS rate: % of slots ladder fires vs skips
Forced 21 DTE roll count
Per-position avg PnL, hit rate
Booster overlap days
Entries/year
Action days/week (P4 operational burden)
```

### 3.4 R7 — Effective expiry count

```
Definition:  eff_count = 1 / Σ(w_i²)
             where w_i = expiry_i max_loss / total max_loss

Examples:
  8 trades, all same expiry  → eff_count = 1 (worst, current state)
  4 expiries equal-weighted  → eff_count = 4
  2 expiries equal           → eff_count = 2
  3 expiries weights 0.6/0.3/0.1 → eff_count ≈ 1/0.46 ≈ 2.17
```

Report both `max_concentration_pct` AND `eff_count` for every variant.

---

## 4. P2 Candidate Universe (R4 + R5 applied)

P2 prototypes (alphabetical, priority TBD by P1):

```
L0 — Baseline B ad-hoc cluster (control)
L1 — Weekly strict, 10% sizing (PM original)
L2 — Weekly strict, 15% sizing (selector default)
L3 — Weekly catch-up, 10% sizing
L4 — Weekly catch-up, 15% sizing

EXCLUDED from core P2:
  L5 — Booster off-ladder bonus entries  (R4: → Q074 territory)
  Rolling cadence variants                (R5)

Diagnostic appendix only:
  S3 dynamic sizing — only if P1b indicates it ≠ cluster systematization
```

P1 result determines L1-L4 priority. No Quant pre-rank.

---

## 5. P3 Transition / Crisis Forensic

Re-use Q075 P3 framework:

```
5 named crisis windows:
  DotCom 2000-03, PreGFC 2007-07, Vol 2018-02, COVID 2020-02, Bear 2022-01

For each crisis × each ladder variant:
  entries in 10d pre-trigger window
  forced-exit count (stress → ladder skip)
  cum incremental loss in crisis window
  worst single trade per variant in crisis window
```

**Strict rejection rule** (R6 hard gate):
- Worst 20d degradation > +0.25pp → REJECT
- Worst 63d degradation > +0.25pp → REJECT
- Any crisis-window cum loss > +$10k vs Baseline B → REJECT

---

## 6. P4 Portfolio Integration

Unified-NLV combined simulator. Q078 ladder added on top of SPEC-104 + SPEC-105 v2 baseline.

```
Required metrics:
  ΔROE vs SPEC-104 + SPEC-105 v2 baseline
  MaxDD / Worst 20d / Worst 63d
  Sharpe
  Capital competition with Q042 (BP-day consumption)
  Correlation with existing sleeves
  Crisis window behavior (5 named)
  Bootstrap (block=250, 20 seeds)
  Walk-forward H1 / H2

Operational burden (NEW, per R-additional):
  entries/year
  weeks with action
  max actions in one week
  manual attention events/year
```

Soft operational threshold (P4 reports, not hard gate):

```
Preferred:        ≤ 1 new SPX BPS entry / week
Flag:             > 2 action days/week average in active months
Reject/downgrade: requires daily manual monitoring
```

---

## 7. Promotion Rule (R6 hard, full form)

```
PROMOTE only if ALL hard gates pass:
  V1 (MaxDD ≥ -28%)
  V2 (Worst 20d ≥ -11%)
  V3 (Worst 63d ≥ -17%)
  Worst 20d degradation ≤ +0.25pp vs Baseline B (HARD)
  Worst 63d degradation ≤ +0.25pp vs Baseline B (HARD)
  **Worst single trade ≤ 5% NLV (≈ $44,700 on $894k NLV)** (HARD, REVISED 2026-05-27)
  No new crisis-window failure
  Operational burden ≤ flag threshold

Worst-trade gate revision (2026-05-27): raised from 1% NLV → 5% NLV to match
PM's empirical risk tolerance. PM's current 4-contract 7300/7000 entry has
empirical worst case ≈ -$38k = -4.3% NLV. Original 1% NLV gate was inconsistent
with PM's actual production behavior. Engine 26y worst BPS scaled to today's
SPX 7400 = -$9,591 per contract → 4 contracts = -$38,365 fits within 5% gate.
"Worst single trade" semantics: empirical -41.7% × max_loss × n_contracts (engine
26y worst pct), not theoretical absolute max_loss.

AND meets at least one improvement:
  ΔROE ≥ +0.5pp annualized (above noise per feedback_noise_threshold 2026-05-28)

Verdict mapping (REVISED 2026-05-28 per noise threshold):
  PROMOTE:        all hard gates + ΔROE ≥ +0.5pp annualized
  DOCUMENT:       ΔROE < +0.5pp (sub-noise, operational principle only, no SPEC)
  REJECT:         any hard gate fail

Noise threshold (per feedback_noise_threshold 2026-05-28):
  Any annualized ROE / portfolio metric delta < 0.5pp is noise, not signal.
  Soft +0.05pp / Strong +0.20pp distinctions from earlier framework are
  sub-noise and not used as verdict criteria.
```

---

## 8. Non-Negotiable Constraints

| # | Constraint | Source |
|---|---|---|
| 1 | **Ladder is EXECUTION layer — no selector gate override** | R1 / Quant framing |
| 2 | SPEC-077 21 DTE roll preserved (not 15 DTE) | R3 / SPEC-077 |
| 3 | SPEC-104 Layer-1 caps (80/50/40) unchanged | Frozen |
| 4 | SPEC-105 v2 Gate F booster unchanged | Frozen |
| 5 | SPEC-103 V1-V7 vetoes unchanged | Frozen |
| 6 | HV Ladder demoted (0% production) | Q073 |
| 7 | Q042 staged ramp unchanged | SPEC-104 |
| 8 | No new strategy primitives | Selector universe |
| 9 | **Cash / Baseline-B is valid endpoint** | R-additional |
| 10 | Portfolio-level validation required before SPEC | `feedback_portfolio_level_research` |
| 11 | No candidate priority pre-decided by Quant | `feedback_layer_n_replacement_research` |
| 12 | Implementation ease ≠ research priority | Same |
| 13 | Booster off-ladder bonus entries excluded from core | R4 |
| 14 | Rolling cadence excluded from core | R5 |
| 15 | Ladder uses selector-provided DTE / params (no hard-code) | R8 |
| 16 | Tail = HARD gate (≤ +0.25pp degradation) | R6 |

---

## 9. Caveats (carried + sharpened)

1. **BP utilization improvement is empirical, NOT assumed**. 50% selector gate rate means ladder fires on ~half weeks. Steady-state SPX BPS BP from ladder ≈ 20%, not 40%. PM's "fill 80%" intuition needs reality check.

2. **Q078 is restructure, not new alpha source**. Expected ROE improvement small. Real value (if any) is in expiry dispersion + operational discipline.

3. **Operational discipline is hard to measure**. P4 simulates perfect execution; real PM may not follow ladder strictly. Buffer this in P4 sensitivity.

4. **Baseline B is single observation**. Real PM ad-hoc pattern is irregular. Baselines A/C bracket above/below for sensitivity.

5. **15 DTE exit deferred to Q079**. If PM still wants this study, open separate framing.

6. **Booster ROE small (+0.014pp at $894k)**. L5 excluded from core not because booster is bad, but because Q074 already owns it.

7. **Ladder cadence = weekly is PM-chosen**. Could be Tue/Wed/Fri etc. Choice is operational convenience, not research-derived.

8. **Strategy-agnostic ladder (R8 option a)**. If selector returns BCD instead of BPS, ladder enters BCD. PM should know this — ladder isn't "BPS-only-ladder".

---

## 10. Phase Schedule (PM-discretionary timing)

```
P0  this memo — DONE 2026-05-27
P1a cadence + cluster rule attribution → memo + 4 CSVs
G2  2nd Quant P1a light review (optional)
P1b sizing attribution (conditional on P1a result) → memo + 2 CSVs
G2.5 light review
P2  candidate prototype based on P1a/b priority → memo + per-candidate CSVs
G3  2nd Quant P2 review (mandatory)
P3  transition forensic → memo + 4 CSVs
P4  portfolio integration → memo + 6 CSVs
P5  final PROMOTE / SOFT / DOCUMENT / REJECT decision
G4  2nd Quant final review (mandatory before any SPEC draft)
```

No time locks. PM may pause at any G-review.

---

## 11. PM Acknowledge Checklist (informal, not blocking)

- [x] PM proposed ladder (2026-05-27)
- [x] Quant clarified ladder = execution layer (rejected mechanical override)
- [x] PM accepted 15 DTE → Q079 separate study
- [x] 9 revisions from 2nd Quant applied
- [x] Cash / Baseline-B valid endpoint preserved
- [x] BP utilization improvement empirical not assumed
- [ ] Open P1a cadence script work (NEXT — Quant action)

---

## 12. Files index

- `research/q078/q078_p0_anchored_memo_2026-05-27.md` (this file)
- `task/q078_framing_2nd_quant_review_packet_2026-05-27.md` — framing packet
- `task/q078_framing_2nd_quant_review_2026-05-27_Review.md` — 2nd Quant PASS w/ 9 revisions

Predecessor context:
- `research/q075/q075_p4_memo.md` — Q075 DOCUMENT precedent
- `strategy/selector.py:38,68` — SPEC-077 21 DTE roll
- `strategy/selector.py:60-83` — DTE + BP target/ceiling per regime
- `task/SPEC-104.md` / `task/SPEC-105-v2.md` — frozen baseline
- `task/SPEC-106.md` — matrix consistency (shipped 2026-05-26; 50% gate rate finding)

Memory references:
- `feedback_layer_n_replacement_research.md`
- `feedback_layer_n_replacement_outcome.md`
- `feedback_portfolio_level_research.md`
- `feedback_spec_review_obligation.md`

---

## 13. Quant Sign-off

Q078 P0 anchored memo locks scope per:
- 2nd Quant framing PASS WITH REVISIONS (2026-05-27), 9 revisions all applied
- Ladder strictly execution layer (R1)
- 21 DTE roll preserved; 15 DTE → Q079 (R3)
- L5 booster bonus excluded from core (R4)
- Cluster rule: strict + catch-up only, rolling excluded (R5)
- Tail = hard gate (R6)
- Effective expiry count metric added (R7)
- Ladder uses selector-provided params (R8)
- P1 staged P1a → P1b (R9)
- BP utilization improvement empirical, not assumed (R-add)
- Operational burden as P4 output (R-add)
- 16 non-negotiable constraints (§8)

Quant ready to open P1a cadence script work upon PM acknowledge.

> Q078 is execution-layer ladder research — testing whether systematic selector-gated weekly cadence with sized queue improves long-run BP utilization, ROE, tail risk, and expiry concentration vs current ad-hoc clustered entries. Ladder is strictly execution layer with no override authority; selector remains decision authority. Cash/ad-hoc remains valid endpoint. PM-proposed 15 DTE exit deferred to Q079. Booster off-ladder bonus excluded from core. P1 staged: P1a cadence first (4 variants × Baseline B fixed sizing), P1b sizing conditional. Tail degradation ≤ +0.25pp is hard gate; effective expiry count (Herfindahl inverse) added as diversification metric.
