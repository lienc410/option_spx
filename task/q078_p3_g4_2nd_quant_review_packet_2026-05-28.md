# Q078 P3 / G4 — 2nd Quant Mandatory Final Review Packet

**Date**: 2026-05-28
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **G4 MANDATORY final review** (per P0 §10) — gate before SPEC-107 drafting
**Decision sought**: PASS / REVISE / REJECT V3 S3 PROMOTE recommendation

---

## 0. TL;DR

Q078 P3 confirms V3 daily-cluster cadence at S3 sizing (3 contracts, ≈7.5% BP per entry) is ready for SPEC-107 drafting:

```
Walk-forward consistency:    ΔROE +9.59pp (H1) / +9.66pp (H2) — Δ 0.07pp
Crisis windows:              4/5 wins materially; COVID single-trade -2.2% NLV ✓
Bias correction:             -0.86pp stratified (vs feared 1.5-2x); residual <2pp
MaxDD improvement:           V3 better than Baseline B in BOTH halves (+0.62-0.76pp)
All hard gates:              PASS on mean (V1/V2/V3 absolute + W20d/W63d Δ within noise + 5% per-trade gate)
Noise framework applied:     ΔROE >>0.5pp (signal); all tail Δ < 0.5pp (noise)
```

**Quant recommendation**: **PROMOTE V3 S3** as "selector-gated SPX execution ladder" → draft SPEC-107.

---

## 1. Full Q078 journey

| Phase | Date | Key Output |
|---|---|---|
| Framing | 2026-05-27 | PASS w/ minor revisions |
| P0 | 2026-05-27 | Anchored memo w/ 9 revisions + 5% NLV gate |
| P1a cadence | 2026-05-27 | V1b + V3 advance; V1a/V2 rejected |
| G2 | 2026-05-27 | PASS w/ 3 fixes (BCD, sizing, MTM) |
| P1b-1 model corrections | 2026-05-27 | Engine empirical pool replaces analytical |
| P1b-2 sizing sweep | 2026-05-27 | S3 (3 contracts) max sizing under 5% NLV gate |
| G2.5 | 2026-05-28 | PASS w/ 2-layer methodology |
| P2 | 2026-05-28 | Selection bias quantified; gates marginally fail |
| P0 revision | 2026-05-28 | 5% NLV gate → noise threshold framework |
| P2 REVISED | 2026-05-28 | Daily MTM smoothing flips gate verdict to PASS |
| P3 forensic | 2026-05-28 | Crisis + walk-forward + bias correction |

11 stages over 2 days. 5 2nd Quant reviews (framing, G2, G2.5 — all PASS w/ revisions). All revisions applied; nothing skipped.

---

## 2. Current state — V3 S3 Layer 2 Production

```
Cadence:    V3 daily-cluster (≤1 entry per 5-trading-day cluster, on selector PASS)
Sizing:     S3 (3 contracts per entry ≈ 7.5% BP at PM's spread width)
Strategy:   agnostic (selector-provided: BPS, IC, BCD, HV variants)
Exit:       SPEC-077 (21 DTE roll, 60% profit, min 10d held)
Production gates: concurrency (1/strategy, 2 for IC_HV) + BP ceiling (35% NLV NORMAL)

Metrics (20-seed bootstrap, mean across full 26y):
  N trades:          559 (≈ 21/yr)
  Ann ROE:           +17.03% NLV/yr (5-95% CI [+15.30, +18.96])
  MaxDD:             -4.95%
  W20d:              -2.78%
  W63d:              -3.77%
  Sharpe:            (not computed at this stage)
  Worst trade:       -$38,327 = -4.29% NLV (single IC NORMAL × 3 contracts × scale)
  Eff_count:         1.05
  Action days/yr:    ~35 (daily selector check required)

ΔROE vs Baseline B S3 (production-realistic):  +9.82pp
ΔROE walk-forward consistency:                  H1 +9.59pp / H2 +9.66pp
After bias deflation (stratified -0.86pp + residual -1 to -2pp): realistic +5.8 to +7.8pp
```

---

## 3. Hard gates status

Per P0 §7 (REVISED 2026-05-28 noise threshold framework):

| Gate | Threshold | V3 Mean | Status |
|---|---|---|---|
| V1 MaxDD | ≥ -28% | -4.95% | ✓ PASS (massive margin) |
| V2 Worst 20d | ≥ -11% | -2.78% | ✓ PASS |
| V3 Worst 63d | ≥ -17% | -3.77% | ✓ PASS |
| W20d degradation | ≤ +0.25pp (now < 0.5pp noise) | +0.08pp | ✓ PASS (within noise) |
| W63d degradation | ≤ +0.25pp (now < 0.5pp noise) | -0.06pp | ✓ PASS (within noise) |
| Per-trade worst | ≤ 5% NLV | -4.29% | ✓ PASS |
| No new crisis-window failure | — | COVID -2.2% NLV ≤ 5% gate | ✓ PASS |
| Operational burden | ≤ flag | 35 action days/yr | ✓ PASS |
| **ΔROE** | **≥ +0.5pp (per noise threshold)** | **+9.66pp wf** | **✓ STRONG SIGNAL** |

→ **All hard gates pass on mean.** ΔROE 19x noise threshold.

---

## 4. Crisis window resilience

```
DotCom 2000-03:   V3 +$24k vs Baseline +$15k    ← V3 wins
PreGFC 2007-07:   V3 +$36k vs Baseline +$7k     ← V3 wins big
Vol 2018-02:      V3 +$40k vs Baseline +$26k    ← V3 wins
COVID 2020-02:    V3 -$16k vs Baseline (none)   ← V3 single loss, -2.2% NLV worst trade
Bear 2022-01:     V3 +$27k vs Baseline +$10k    ← V3 wins

Cumulative 5 crises: V3 +$111k vs Baseline +$58k → V3 still leads by +$53k
```

**Net positive across all 5 crises.** COVID single-loss within 5% NLV per-trade gate.

---

## 5. Bias correction (P3 stratified bootstrap)

```
                   Unstratified    Stratified (year-bucket)   Δ
V3 S3 ann ROE      +17.03%         +16.17%                    -0.86pp
Baseline B S3       +7.21%          +7.22%                    +0.01pp
```

**Bias correction is small** (-0.86pp). Year-bucket stratification suggests engine empirical pool is reasonably representative across periods.

Residual bias (from engine's overall filter survivorship, not addressed by year-bucket stratification): estimate -1 to -2pp additional inflation.

**Realistic ΔROE (after all bias corrections)**: +5.8 to +7.8pp annualized — still 12-15x noise threshold.

---

## 6. Noise threshold framework applied (per PM 2026-05-28)

All Δ measurements < 0.5pp annualized = noise, not signal.

```
Metric                        V3 Δ                Verdict under noise
ΔROE 26y full                +9.82pp             SIGNAL (19x noise)
ΔROE H1 walk-forward         +9.59pp             SIGNAL
ΔROE H2 walk-forward         +9.66pp             SIGNAL
ΔROE after bias deflation    +5.8-7.8pp          SIGNAL (12-15x noise)
MaxDD H1 improvement         +0.62pp             SIGNAL (V3 BETTER)
MaxDD H2 improvement         +0.76pp             SIGNAL (V3 BETTER)
W20d Δ                       +0.08pp             noise (no concern)
W63d Δ                       -0.06pp             noise (no concern)
Eff_count Δ                  +0.05               noise (no diversification benefit)
```

**Robust signal**: ROE + MaxDD improvement. **Not gate-relevant**: tail metric Δ (all noise). **Not a diversification strategy**.

---

## 7. PM-facing reframing (per G2.5 R2)

Q078 has been REFRAMED throughout:

| Old (rejected) | New (mandatory) |
|---|---|
| "weekly BPS ladder" | "selector-gated SPX execution ladder" |
| "BPS sizing study" | "mixed-strategy ladder sizing" |
| "Improves expiry diversification" | "Captures more selector-PASS opportunities for ROE" |
| "Replace cluster entries with weekly entries" | "Daily-cluster cadence at production-gated sizing" |

PM mental model update: ladder runs **selector-recommended strategy on selector-PASS days** with cadence rule preventing same-week duplicates. Strategy mix dominated by BCD (LOW_VOL, 26% of PASS days) and IC HV (9%).

---

## 8. SPEC-107 draft outline (if G4 PASS)

```
SPEC-107: Q078 Selector-Gated SPX Execution Ladder

Scope:
  Add weekly cadence + sized queue ("V3 daily-cluster S3") on top of
  SPEC-104 + SPEC-105 v2 baseline. Strategy-agnostic per P0 R8.

Implementation:
  - Daily selector PASS check
  - Skip if last entry within 5 trading days
  - Skip if same-strategy position open (per IC_HV_MAX_CONCURRENT or 1)
  - Skip if BP utilization + new max_loss > 35% NLV (NORMAL ceiling)
  - Enter 3 contracts at selector-provided strikes / DTE
  - Exit per SPEC-077 (21 DTE roll, 60% profit, min 10d held)

Monitoring obligations:
  - Daily action log (which selector PASS days fired vs skipped)
  - Per-trade PnL tracking
  - Concurrent BP utilization timeline
  - Per-month expiry concentration (eff_count snapshot)
  - Per-crisis-window PnL (5 named windows + ongoing)
  - Operational burden: action days/year

Acceptance criteria (~10 ACs)
Staged rollout: paper/shadow → limited prod → full prod (PM-discretionary)
```

---

## 9. Caveats explicitly disclosed

1. **COVID 2020-02 single trade -$20k** is the largest crisis loss. Within 5% NLV gate but real.
2. **Bias residual <2pp not fully resolved** — would require engine modification to disable filters entirely.
3. **Eff_count Δ 0.05** = essentially no diversification benefit at S3 sizing.
4. **Daily MTM linear distribution** is simplification of theta decay.
5. **Operational discipline assumed perfect** — real adherence may slip.
6. **No P4 portfolio integration** — Q078 standalone analyzed; combined with SPEC-104+105v2 dynamics not yet validated.
7. **PnL inflation post-bias is real but small** — realistic ΔROE +5.8-7.8pp not reported +9.8pp.
8. **20-seed bootstrap CI is wide for W20d/W63d** — but noise threshold framework neutralizes this (Δ already within noise on mean).

---

## 10. Six questions for 2nd Quant

### Q1 — Noise threshold framework adoption
PM established < 0.5pp = noise on 2026-05-28. P0 §7 verdict mapping revised accordingly. Under this framework, V3 ΔROE +9.66pp is clear SIGNAL (19x noise) while all tail Δ are noise-equivalent.

**2nd Quant: confirm noise threshold framework + verdict V3 PROMOTE under it?**

### Q2 — Bias residual acceptance
Year-bucket stratification only changed ROE by -0.86pp. Residual bias from engine's overall filter survivorship estimated -1 to -2pp. Realistic ΔROE +5.8 to +7.8pp still signal.

**2nd Quant: accept current bias estimate or require engine-modification full bias correction before SPEC?**

### Q3 — COVID crisis acceptance
COVID 2020-02 was the only crisis where V3 lost net (avg -$16k). Worst trade -$20k = -2.2% NLV within 5% per-trade gate.

**2nd Quant: COVID acceptable, or require additional sharp-shock stress test?**

### Q4 — Eff_count Δ 0.05 framing
After metric correction (monthly bucketing), V3's diversification benefit is essentially zero. PM's original "8-at-6/18 expiry concentration" problem is empirical for cluster behavior, but ladder at S3 doesn't materially improve it because 14-day holds mostly fit in single monthly bucket.

**2nd Quant: confirm "Q078 is ROE-cadence, NOT diversification" reframing for SPEC language?**

### Q5 — SPEC-107 scope
Proposed SPEC scope (§8):
- V3 daily-cluster cadence
- S3 sizing (3 contracts)
- Strategy-agnostic
- SPEC-077 exit unchanged
- Concurrency + BP ceiling per current engine
- No new strategy primitives

**2nd Quant: scope right, or any additional elements needed?**

### Q6 — Staged rollout
Q078 ladder is operational discipline change. Stage 1 paper would log "what V3 would do" vs actual PM behavior. Stage 2 limited prod activates ladder cadence with monitoring. Stage 3 full prod after PM observation.

**2nd Quant: this staged structure adequate, or require additional gate at Stage 2 advancement?**

---

## 11. Decision Matrix

| 2nd Quant verdict | Action |
|---|---|
| **PASS G4** + Q1-Q6 satisfactorily answered | Quant proceeds to draft SPEC-107 |
| **REVISE** (specific wording / scope) | Quant updates P3 memo + re-submits |
| **REJECT** (V3 ladder not acceptable for production) | Q078 closes; SPEC-104 + 105 v2 baseline stays |
| **PROMOTE V1b instead** | Quant adjusts SPEC-107 to V1b weekly catch-up |
| **REVISE to require additional pre-SPEC checks** | Quant defers SPEC-107 drafting (e.g., full bias correction) |

---

## 12. Supporting Files

- `research/q078/q078_p3_memo.md` — P3 forensic memo (this packet's evidence)
- `research/q078/q078_p2r_memo.md` — P2 REVISED with daily MTM fix
- `research/q078/q078_p2_memo.md` — original P2 (superseded by P2R for gate verdict)
- `research/q078/q078_p1b_2_memo.md` — sizing sweep
- `research/q078/q078_p1b_1_memo.md` — model corrections
- `research/q078/q078_p1a_memo.md` — cadence attribution
- `research/q078/q078_p0_anchored_memo_2026-05-27.md` — P0 (with 5% NLV gate + noise threshold revisions)

Task files (5 2nd Quant review packets + replies):
- `task/q078_framing_2nd_quant_review_packet_2026-05-27.md` + reply
- `task/q078_p1a_g2_2nd_quant_review_packet_2026-05-27.md` + reply
- `task/q078_p1b_g2_5_2nd_quant_review_packet_2026-05-28.md` + reply
- `task/q078_p3_g4_2nd_quant_review_packet_2026-05-28.md` (this file)

Memory:
- `feedback_noise_threshold.md` (NEW 2026-05-28)

---

## 13. Sign-off

Quant submits Q078 P3 G4 final review 2026-05-28. Recommends **PROMOTE V3 S3** as "selector-gated SPX execution ladder" under noise-threshold framework. All hard gates pass on mean across walk-forward halves; crisis-resilient (4/5 wins, 1 acceptable COVID loss); bias correction small (-0.86pp stratified); realistic ΔROE +5.8-7.8pp annualized after all corrections. SPEC-107 drafting upon G4 PASS.

> Q078 P3 G4 packet: V3 daily-cluster cadence at S3 (3 contracts) sizing recommended for PROMOTE. ΔROE +9.66pp annualized, robust across H1/H2 walk-forward; crisis-resilient (cumulative +$53k advantage across 5 named windows despite COVID -$16k); MaxDD improvement (V3 better than Baseline B in both halves); all hard gates pass on mean (V1/V2/V3 absolute + tail Δ within 0.5pp noise + 5% per-trade gate). Bias residual small (year-bucket stratification only -0.86pp); realistic post-bias ΔROE +5.8 to +7.8pp still 12-15x noise threshold. Strategy is "selector-gated SPX execution ladder" (NOT BPS ladder); not a diversification strategy (eff_count Δ 0.05 noise); ROE-cadence value comes from capturing more selector-PASS opportunities at production sizing. SPEC-107 draft outline ready upon G4 PASS.
