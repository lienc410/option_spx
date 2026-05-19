# Q074 P0 — Bull Regime Booster / Layer-2 Income Optimization

**Project**: Bull Regime Booster — Conditionally relax SPX normal cap in confirmed benign regimes
**Status**: **SIGNED 2026-05-18** — three-party sign-off complete (PM 2026-05-17 + Quant 2026-05-17 + 2nd Quant PASS WITH 5 MINOR REVISIONS 2026-05-18, all applied)
**Date**: 2026-05-17
**Parent**: SPEC-104 Arch-3 base architecture (Layer-1 survival)
**Framing principle**: `feedback_survival_vs_income_layering.md` — Layer 1 vetoes 不动, Layer 2 在 Layer 1 框架内

---

## 0. TL;DR

Q074 = **Layer-2 Income Optimization** research:

> **在 confirmed benign regime 下，临时提高 SPX BPS normal-state deployment；一旦进入 stress / second-leg，立刻回到 SPEC-104 的 50% / 40% 防守框架。**

### Non-negotiable Layer-1 constraints (UNCHANGED)

```
V1 MaxDD ≤ 28%
V2 Worst 20d ≤ 11%
V3 Worst 63d ≤ 17%
V4 governance caps (R3 60% / R4 50%)
V5 synthetic crisis no breach
V6 bootstrap sig ≥ 80%
V7 walk-forward both halves
Stress SPX cap: 50% (R5 in SPEC-104 — UNCHANGED)
Second-leg SPX cap: 40% (R6 in SPEC-104 — UNCHANGED)
HV Ladder demoted (per SPEC-104 — UNCHANGED, no re-promotion in Q074)
Q042 Sleeve A staged ramp 17.5% (per SPEC-104 — UNCHANGED)
26y window evaluation including 2000-04, 2008, 2018, 2020, 2022
```

### Only thing Q074 can modify

```
Normal SPX cap currently 80% → conditionally 85% / 90% in confirmed benign regime
Cash residual auto-adjusts accordingly
```

Three SPX cap states:
- **Booster active** (benign confirmed): 85% or 90%
- **Normal base** (default): 80% (SPEC-104 R1)
- **Stress** (R5 trigger): 50% (snap-back)
- **Second-leg** (R6 trigger): 40% (further snap-back)

---

## 1. Hypothesis

> Arch-3 is a conservative survival-first base architecture. It may under-deploy capital during confirmed benign bull regimes. A narrowly defined bull-regime booster may improve ROE by raising the SPX normal cap from 80% to 85-90%, while preserving Q073 Layer-1 survival constraints through immediate snap-back to stress / second-leg caps.

**Expected outcome estimate (Quant prior)**:
- Net ROE +0.1pp to +0.4pp likely; +1pp unlikely
- Q073 Arch-3 was already 80% normal cap, so booster space is bounded
- Transition risk is the primary failure mode (booster active → stress trigger → snap-back too late)

---

## 2. Out of Scope (Strict)

These are EXPLICITLY out of scope for Q074:

| Out-of-scope item | Why |
|---|---|
| V1-V7 relaxation | Layer 1 unchanged |
| Stress cap raise (50% → 55% / 60%) | Survival floor protection |
| Second-leg cap raise (40% → 45%+) | Survival floor protection |
| Post-2007 V2/V3 carve-out | "Removing 2000-04" wrong direction |
| HV Ladder re-promotion | Per SPEC-104, requires separate Q-research |
| Q042 Sleeve A cap change beyond 17.5% target | Per SPEC-104 staged ramp |
| Q042 Sleeve B activation | Research-only per Q073 Rule 4 |
| New strategy primitives (LOW_VOL income, butterflies, etc.) | Layer-2 booster only, not new strategies |
| ML / black-box benign regime detector | Must be explainable state machine |
| New underlying / multi-account allocator | Out of scope for Q074 |

> **WRONG anti-pattern (per `feedback_survival_vs_income_layering`)**: relax Layer 1 to gain Layer 2.
>
> **CORRECT pattern**: keep Layer 1 floor; selectively raise normal cap on multi-signal benign confirmation, with hard snap-back.

### Trigger immutability (per 2nd Quant Revision 1, 2026-05-18)

> **Q074 may not modify `stress_active` or `second_leg_active` trigger definitions OR their timing.** Any proposal to change R5 / R6 trigger conditions (e.g., delaying stress detection to make booster look better, smoothing the activation, or relaxing the trigger thresholds) must be moved to a SEPARATE governance research item, NOT included in Q074. Modifying trigger timing is structurally equivalent to relaxing Layer-1 — same anti-pattern.

### Booster cap upper bound locked (per 2nd Quant Revision 5, 2026-05-18)

> **Booster cap upper bound = 90% for Q074. 95% and 100% are NOT tested.** Rationale: 95%+ leaves near-zero cash buffer and induces unacceptable transition risk severity. Aggressive leverage testing is out of Q074 scope.

---

## 3. Benign Regime Definition (Candidate Feature Set)

**Critical PM principle**: Do NOT use only `SPX > MA50` — too coarse. Multi-condition benign confirmation required. Bull market top often satisfies single-signal "bullish" criteria but is not truly benign.

### Candidate features

| Feature | Purpose | Candidate values |
|---|---|---|
| **SPX trend** | Confirm uptrend not just at-the-money | `SPX close > MA50 AND MA50 slope > 0` |
| **Drawdown from ATH** | Confirm shallow drawdown | `ddATH > -3%` (strict) or `ddATH > -4%` (moderate) |
| **VIX absolute** | Avoid vol re-pricing regime | `VIX < 20` (strict) or `VIX < 22` (moderate). Note: VIX too low (< 15) ≠ best (premium too thin); test bucketed |
| **VIX trend** | Avoid early-stage VIX rise | `VIX 5d change ≤ +1.0` (strict) or `≤ +1.5` (moderate) |
| **IVP_252** | Per Q063 evidence, IVP gate has value | `IVP_252 < 55` (consistent with current BPS NNB gate) |

### 4 candidate booster definitions (B1-B4)

**Booster activation gate (UNIVERSAL, applies to B1-B4)** — explicit Layer-1 exclusion:

```
Booster can activate ONLY IF:
  not stress_active        AND
  not second_leg_active    AND
  benign criteria all true
```

State priority ensures stress / second-leg take precedence, but this is made explicit in booster definition to prevent implementation drift.

| Candidate | Benign criteria | Booster cap |
|---|---|---|
| **B0 (control)** | None (Arch-3 baseline) | Normal SPX = 80% |
| **B1 strict + 85%** | NOT stress AND NOT 2nd_leg AND SPX > MA50 AND MA50_slope > 0 AND ddATH > -3% AND VIX < 20 AND VIX_5d_change ≤ +1.0 AND IVP < 55 | Normal SPX 80 → **85%** |
| **B2 moderate + 85%** | NOT stress AND NOT 2nd_leg AND SPX > MA50 AND ddATH > -4% AND VIX < 22 AND VIX_5d_change ≤ +1.5 AND IVP < 55 | Normal SPX 80 → **85%** |
| **B3 strict + 90%** | Same as B1 | Normal SPX 80 → **90%** |
| **B4 moderate + 90%** | Same as B2 | Normal SPX 80 → **90%** |

---

## 4. Snap-back Rule (Hard, Non-negotiable)

```
State priority (highest priority overrides lower):
  1. Second-leg active     → SPX cap = 40%  (R6 / SPEC-104)
  2. Stress active         → SPX cap = 50%  (R5 / SPEC-104)
  3. Booster active (B1-B4 criteria all true)  → SPX cap = 85% or 90%
  4. Normal base default   → SPX cap = 80%  (SPEC-104 R1)
```

**No smoothing transitions**. State changes are immediate. If booster active 90% on Day T, and stress triggers Day T+1, cap drops 90% → 50% same day (no ramp-down period).

Why no smoothing: per Q072 / Q073 lessons, smoothing introduces lag (Q069 SMA/EWM IVP variants failed for this reason). Production trading layer enforces hard state machine.

---

## 5. Research Phases (per PM brief)

### P1 — Benign-regime Attribution (no booster yet)

> **LOOK-AHEAD WARNING**: Forward returns in P1 are used **only for research attribution**, NOT for signal construction. P1 must NOT result in a booster definition that bucket-optimizes on observed forward returns (that would be look-ahead overfit). Booster B1-B4 features are PM-anchored ex-ante in §3; P1 only reports per-bucket forward distributions to assess existence of edge, not to design new gates.
>
> **B1-B4 FROZEN BEFORE P1 (per 2nd Quant Revision 4, 2026-05-18)**: P1 attribution is diagnostic only. Candidate definitions B1-B4 are FROZEN before P1 results are observed. Any new candidate (B5, B6, etc.) derived from forward-return bucket observations requires a separate P0 amendment and 2nd Quant review — cannot be added mid-research.

Question: Within Arch-3 26y, which normal days had highest forward returns?

Approach: classify each normal-state day by feature buckets, compute forward 20d / 63d PnL of SPX BPS sleeve at 80% allocation.

Output:
- Per-bucket avg forward 20d PnL
- Per-bucket hit rate
- Per-bucket worst forward 20d
- Per-bucket probability of stress trigger within next 10d / 20d (critical — predicts transition risk)

**Bucket dimensions**:
- SPX trend (above MA50 or not)
- MA50 slope (positive / negative)
- ddATH (4 buckets)
- VIX absolute (4 buckets)
- VIX 5d change (3 buckets: falling / flat / rising)
- IVP_252 (3 buckets: < 30 / 30-55 / 55-70 / > 70)

### P2 — Booster Candidate Sweep

Test B1, B2, B3, B4 on 26y combined-NLV unified-NLV simulator. Apply per-day SPX allocation policy:
```
if second_leg_active:    spx_alloc = 0.40
elif stress_active:      spx_alloc = 0.50
elif benign_all_true:    spx_alloc = booster_cap (0.85 or 0.90)
else:                    spx_alloc = 0.80
```

Output per candidate: Net ROE, MaxDD, Worst 20d, Worst 63d, Sharpe, Calmar, V1/V2/V3 status, Floor 8% status.

**Booster breadth diagnostic (NEW per PM revision)**:
- Compute `booster_active_days_pct` = % of normal days where booster activates
- If `booster_active_days_pct > 60%` → candidate is too broad; effectively a permanent normal cap raise rather than regime-conditional booster → flag for review
- Strict candidates (B1, B3) likely have lower active%; moderate (B2, B4) likely higher
- Diagnostic is informational, NOT a hard veto; PM + 2nd Quant judge in context

### P3 — Transition-Risk Forensic (CORE)

> **Q074's primary failure mode**: booster active in benign window → stress trigger fires → snap-back too late → losses from inflated booster sizing.

Per booster candidate, identify all "transition windows":

**Primary transition window (10d) — per PM brief**:
```
transition window = booster active in previous 10 trading days
                    AND stress state triggers today
```

**Secondary diagnostic (20d) — per 2nd Quant Revision 2, 2026-05-18**:
```
secondary diagnostic = booster active in previous 20 trading days
                       AND stress state triggers today
```

Rationale: 10d catches fast rollovers (2020-02 COVID); 20d catches slow rollovers (2000, 2007, 2022). If 10d looks safe but 20d shows concentrated losses → booster is fragile to slow regime shifts.

**Transition severity classification (per 2nd Quant Revision 3, 2026-05-18)**:

For each transition (within either 10d or 20d window), classify as:

| Severity | Definition |
|---|---|
| **mild transition** | stress triggers without second-leg within next 20d |
| **acute transition** | stress triggers AND second-leg triggers within next 20d |
| **failed benign** | booster active, stress triggers, incremental booster PnL < 0 (defined below) |

For each transition window (both 10d primary and 20d secondary):
- PnL from booster-on date to stress trigger
- PnL first 5 days after stress trigger
- PnL first 20 days after stress trigger
- Maximum adverse excursion
- Severity classification

Critical periods to examine: 2000-03, 2007-07, 2018-02, 2020-02, 2022-01.

Also compute:
- **False-benign count**: booster active within 10d before stress trigger AND **incremental booster PnL** < 0
- **CRITICAL definition** (per PM revision): `incremental booster PnL = candidate PnL − Arch-3 baseline PnL over the same window`. Measures ONLY the additional loss caused by booster's higher SPX allocation, NOT total strategy PnL (which would conflate booster effect with base SPX BPS).

If false-benign count is concentrated in 1-2 episodes → booster fragile.
If incremental false-benign losses dominate incremental booster gains → booster not worth deploying.

### P4 — Validation (mirror Q073 P4)

For top 1-2 booster candidates:
- V6 Bootstrap (block=250, 20 seeds)
- V7 Walk-forward split-sample (2000-2013 vs 2013-2026)
- Friction sensitivity (±50%)
- Crisis windows side-by-side (Arch-3 vs Arch-3 + booster)
- Synthetic crisis stress injection

### P5 — Decision

| Outcome | Verdict |
|---|---|
| ≥ Strong pass criteria | Promote booster to SPEC (amend SPEC-104 R1 cap state machine) |
| Soft pass | **Paper / shadow only; cannot amend SPEC-104 production caps.** Booster definition + simulator stay in research, no production rollout |
| Fail | Reject, keep Arch-3 unchanged |

---

## 6. Success Criteria

### Strong pass

Requires **BOTH absolute AND relative pass** on tail metrics:

- **Absolute**: V1/V2/V3 all pass (worst 20d ≥ -11%)
- **Relative**: Worst 20d no worse than Arch-3 (-7.04%) by > 0.5pp (i.e. candidate worst 20d ≥ -7.54%)

Without BOTH:
- Pure absolute pass (e.g. candidate worst 20d -10.9%) → V2 passes but relative deterioration is 3.86pp → NOT strong pass
- Pure relative pass (e.g. candidate worst 20d -7.5% but ROE only +0.05pp) → relative ok but ROE marginal → NOT strong pass

Plus:
- Net ROE +0.30pp or more vs Arch-3
- Transition losses bounded (any single transition window incremental loss < 2% NLV)
- Walk-forward both halves pass floor 8%
- Bootstrap sig ≥ 80%

### Soft pass

- Net ROE +0.10 to +0.30pp
- V1/V2/V3 all pass
- Worst 20d roughly unchanged
- Transition losses small (any single transition < 1.5% NLV)
- → **Paper / shadow only**, not full production SPEC

### Fail

- V2 fail (worst 20d > -11%), OR
- Worst 20d worsens by > 1pp vs Arch-3, OR
- Transition losses concentrated in 1-2 episodes, OR
- ROE improvement only in recent 2y (not in walk-forward halves), OR
- V1 / V3 fail

---

## 7. Methodology (from Q073 lessons, per `feedback_portfolio_level_research`)

- **Unified-NLV simulator** from start (NOT naive per-engine PnL sum)
- **Friction model**: constant daily $ drag = annual_friction × NLV × allocation / 252 (NOT % of daily PnL)
- **V2 / V3 worst-rolling**: point-in-time equity denominator (NOT initial NLV)
- **Hypothesis-driven** 4 candidate booster definitions (B1-B4), NOT brute-force grid
- **Q074 P1 START** with P1.3R unified-NLV daily PnL series + apply day-by-day SPX allocation policy
- Each engine sized to its allocation (Q042 17.5%, HV 0%) per SPEC-104

---

## 8. Stopping Conditions

| Phase | Stop if … |
|---|---|
| **P1** | No benign-feature bucket shows materially different forward PnL distribution → booster has no signal to exploit, close Q074 |
| **P2** | No booster candidate has Net ROE > Arch-3 baseline → no economic incentive, close Q074 |
| **P2** | All booster candidates fail V2 — booster is fundamentally incompatible with survival layer, close Q074 |
| **P3** | False-benign count concentrates in 1-2 episodes contributing > 50% of booster losses → fragile, fail |
| **P4** | Walk-forward only passes in recent half → over-fit to AI-bull regime, fail or paper-only |

---

## 9. Mid-Review Gates

| Gate | Trigger | Reviewer |
|---|---|---|
| **G1 P0 sign-off** | This memo signed | PM + Quant + **2nd Quant framing review** |
| **G2 P1 attribution review** | P1 buckets output | PM (decision) + Quant + 2nd Quant (light) |
| **G3 P3 transition-risk review** | Top 1-2 booster candidates identified, before P4 | **2nd Quant mid-review** (mandatory) |
| **G4 P5 final review** | Promote / paper / reject decision | **2nd Quant final review** (mandatory) |

G3 is necessary because Q074 promotion (if reached) would amend SPEC-104 R1 normal cap — this is governance-adjacent and demands 2nd Quant audit.

---

## 10. Estimated Effort

| Phase | Quant time | 2nd Quant time | Wall clock |
|---|---|---|---|
| P0 sign-off | done | 1 day (framing review) | 1 day |
| P1 attribution | 1-2 days | 0.5 day | 1.5-2.5 days |
| P2 booster sweep | 1-2 days | — | 1-2 days |
| P3 transition forensic | 1-2 days | 1 day (G3) | 2-3 days |
| P4 validation | 2-3 days | — | 2-3 days |
| P5 + final review | 1 day + 2 day review | 2 days (G4) | 3-4 days |
| **Total** | **~7-10 days Quant** | **~5 days 2nd Quant** | **~2 weeks wall** |

---

## 11. Three-Party Sign-Off

### PM Sign-off
- [x] Anchor Layer-1 constraints unchanged (per `feedback_survival_vs_income_layering`)
- [x] Approve booster definition framework (5 features, 4 candidates B1-B4)
- [x] Approve research phase structure (P1-P5 per brief)
- [x] Approve success criteria (Strong / Soft / Fail thresholds)
- [x] Anchor SPX normal cap 80% as base; booster goes to 85% / 90% conditionally

### Quant Researcher Sign-off
- [x] Methodology aligned with Q073 lessons (unified-NLV, constant friction, point-in-time)
- [x] Hypothesis-driven 4 candidates, not grid
- [x] Transition-risk forensic as P3 core
- [x] Stop conditions defined per phase
- [x] G3 mid-review + G4 final 2nd Quant gates accepted

### 2nd Quant Sign-off — PASS WITH MINOR REVISIONS 2026-05-18
- [x] P0 anchored Layer-1/Layer-2 framing acceptable
- [x] B1-B4 booster definitions acceptable
- [x] P1-P5 plan acceptable
- [x] Success criteria thresholds acceptable (Strong +0.30pp / Soft +0.10pp / Fail various)
- [x] G3 / G4 review scope acceptable
- [x] Methodology pitfalls addressed (no time-locked, no Layer-1 relaxation, transition-risk as P3 core)
- [x] 5 minor revisions applied to P0:
  - R1 trigger immutability statement (§2)
  - R2 20d transition diagnostic window added (§5 P3)
  - R3 mild/acute/failed-benign severity classification added (§5 P3)
  - R4 B1-B4 frozen-before-P1 statement (§5 P1)
  - R5 90% upper bound locked (§2)

---

## 12. References

- `task/SPEC-104.md` §13 — Q074 forward research seed
- `research/q073/q073_final_memo.md` — base architecture (Arch-3)
- `research/q073/q073_p1_3r_unified_nlv_baseline.md` — unified-NLV simulator base
- `research/q073/q073_p1_rules_2026-05-17.md` — 7 Q073 rules (still apply)
- `/Users/lienchen/.claude/projects/.../memory/feedback_survival_vs_income_layering.md` — two-layer framing principle
- `/Users/lienchen/.claude/projects/.../memory/feedback_portfolio_level_research.md` — Q073 methodology lessons
- PM brief 2026-05-17 verbatim (this memo captures all material points)
