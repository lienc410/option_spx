# Q074 — Bull Regime Booster / Layer-2 Income Optimization — FINAL MEMO

> **Status: FINAL — P5 DECISION.**
> **Recommendation: PROMOTE B4 moderate 90% as staged Bull Regime Booster overlay.**
> Pending G4 mandatory 2nd Quant final review.

**Date**: 2026-05-18
**Project**: Q074 Bull Regime Booster — Layer-2 income optimization under Q073 Arch-3 framework
**P0 anchored**: PM 2026-05-17 + Quant 2026-05-17 + 2nd Quant PASS w/ 5 revisions 2026-05-18
**Predecessors**: P1 attribution, P2 sweep, P3 transition forensic, P4 full validation

---

## 0. Executive Verdict

**PROMOTE B4 moderate 90% as staged Bull Regime Booster overlay.**

```
Base architecture (Arch-3 / SPEC-104 — UNCHANGED):
  Normal SPX cap     = 80%
  Stress SPX cap     = 50%
  Second-leg SPX cap = 40%
  HV Ladder          = 0% (research-only)
  Q042 Sleeve A      = staged target 17.5%

Q074 B4 booster overlay (NEW):
  IF benign confirmation = TRUE (all 6 conditions below):
      Normal SPX cap = 90%   (replaces 80%)
  
  Benign confirmation (all required, evaluated daily):
    - NOT stress_active        (R5 inactive)
    - NOT second_leg_active    (R6 inactive)
    - SPX close > MA50
    - ddATH > -4%
    - VIX < 22
    - VIX 5d change ≤ +1.5
    - IVP_252 < 55
  
  Hard snap-back priority (UNCHANGED from Arch-3):
    Second-leg active → SPX cap = 40%
    Stress active     → SPX cap = 50%
    Benign confirmed  → SPX cap = 90%
    Else              → SPX cap = 80%
```

**Expected impact (26y backtest, net of friction)**:
- Net Ann ROE: 7.95% → **8.20% (+0.25pp)**
- MaxDD: -8.71% → -8.71% (unchanged)
- Worst 20d: -7.04% → -7.04% (unchanged)
- Sharpe: 1.97 → 2.02
- Booster active: ~20% of trading days
- V1/V2/V3/V6/V7 all PASS

---

## 1. Why B4 (not B3 or others)

| Cand | ΔROE | Worst single | Cum incremental | Verdict |
|---|---|---|---|---|
| B1 strict 85 | +0.11pp | -0.03% NLV | +$70k | Soft pass, marginal ROE |
| B2 moderate 85 | +0.13pp | -0.07% NLV | +$107k | Soft pass |
| B3 strict 90 | +0.22pp | -0.06% NLV | +$141k | **Backup** |
| **B4 moderate 90** | **+0.25pp** | **-0.15% NLV** | **+$214k** | **PROMOTE** |

**B4 over B3**: P4.7 overlap analysis shows B4 captures 183 extra days vs B3, contributing +$52k incremental. P4.5 joint-slice confirms those 183 days are clean (VIX 20-22 + IVP < 30 + ddATH > -3% + VIX falling). B4 captures more upside without adding structural risk.

**B4 over B1/B2**: B1/B2 (cap 85%) ROE upside too small to justify SPEC effort. B4 (cap 90%) captures the regime opportunity more fully.

**B3 retained as fallback**: If PM prefers stricter filter (VIX < 20 instead of < 22) for operational caution, B3 is +0.22pp option. But P4 evidence does not require it.

---

## 2. Strong-Eligible (Not Pure Strong Pass)

| Item | Value |
|---|---|
| Point estimate ΔROE | +0.252pp |
| Strong threshold (P0) | +0.30pp |
| Gap | 0.048pp |
| Bootstrap noise σ | 0.100pp |
| Gap / noise | 0.48 |

**The 0.048pp gap is half the bootstrap noise σ** — statistically indistinguishable from being at/above Strong threshold. Per 2nd Quant G3 framework:

> "Although the point estimate is +0.25pp vs the +0.30pp Strong threshold, the gap is economically immaterial and within estimation noise; given superior transition-risk evidence, B4 is acceptable for staged production / SPEC amendment."

**B4 = "Strong-eligible / production-acceptable"** — NOT pure Strong Pass on literal P0 criterion, but economically equivalent. Staged production preferred over one-shot full deployment.

---

## 3. Why Tail is Preserved (key Q074 invariant)

P4 systematically verified that B4 booster does NOT degrade Layer-1 survival:

| Tail metric | Arch-3 | B4 | Δ |
|---|---|---|---|
| MaxDD | -8.71% | -8.71% | **0.00pp** |
| Worst 20d | -7.04% | -7.04% | **0.00pp** |
| Worst 63d | -6.94% | -6.94% | **0.00pp** |
| V1 buffer (from 28%) | 19.3pp | 19.3pp | unchanged |
| V2 buffer (from 11%) | 3.96pp | 3.96pp | unchanged |
| V3 buffer (from 17%) | 10.06pp | 10.06pp | unchanged |

**Mechanism**: Multi-condition benign signal turns booster OFF before stress fires. State machine priority enforces hard snap-back to 50%/40% during stress/2nd-leg, leaving no room for booster to participate in tail losses.

This is the design pillar — Layer-1 survival floor PRESERVED while Layer-2 captures benign-regime upside.

---

## 4. VIX 20-22 Surprise — RESOLVED

**P1 attribution finding**: VIX 20-22 normal-state has **59.2%** next-10d stress probability (most dangerous VIX bucket). B4 (VIX < 22) includes this bucket; B3 (VIX < 20) excludes.

**P4.5 joint-slice finding**: B4 only activates at VIX 20-22 in **20 days over 26y** (very rare). ALL 20 days share:
- IVP_252 < 30 (mean 14.1) — non-stressed IVP environment
- ddATH > -3% (mean -0.43%) — very shallow drawdown
- VIX_5d_change ≤ 0 (mean -1.41) — VIX FALLING from spike, not rising

**Conclusion**: B4's multi-condition filter cuts VIX 20-22 into a "transient spike in calm IVP regime" subset, NOT a "approaching structural stress" subset. The IVP < 30 dominance is decisive. Q1 (G3) concern resolved.

---

## 5. Walk-Forward Robustness

P4.2 H1/H2 split shows:

| Cand | H1 ROE (2000-2012) | H2 ROE (2013-2026) | Both halves ≥ 8% |
|---|---|---|---|
| B0 (Arch-3) | 8.42% | 13.83% | ✓ |
| B3 | 8.42% | 14.43% | ✓ |
| **B4** | **8.42%** | **14.52%** | **✓** |

**B4 floor 8% passes in both halves individually** — V7 walk-forward PASS.

Booster contribution by half:
- H1 (DotCom + GFC era): +0.00pp — booster effectively off
- H2 (post-2013 bull regime): +0.69pp — booster active and contributing

**This is design-correct, not regime over-fit**: booster is supposed to be a Layer-2 OPTIONAL income enhancement that activates only in benign regimes. H1 was hostile → booster correctly off → no benefit (and no harm). H2 was benign → booster active → benefit. If next 10-15y resemble H1, booster contributes 0 (graceful degradation). If like H2, booster contributes +0.5pp.

---

## 6. Funding Stress (Critical for B4 90% Cap)

When B4 booster active at 90% SPX + 17.5% Q42 = 107.5% exposure → cash residual -7.5% (effective margin loan).

P4.6 stress test (+300bp / +600bp on negative-cash days):

| +bps neg-cash stress | B0 ROE | B4 ROE | ΔB4-B0 |
|---|---|---|---|
| +0bp (base) | 7.95% | 8.20% | +0.252pp |
| +300bp (realistic) | 7.95% | 8.19% | +0.246pp |
| +600bp (severe) | 7.95% | 8.19% | +0.239pp |

**Even at +600bp funding stress, B4 advantage degrades by only 0.013pp**. Realistic margin loan cost (typically +200-400bp above BOXX) won't change B4 promote decision.

**Note**: SPEC implementation should still report actual margin financing cost as monitoring metric.

---

## 7. SPEC Handoff

**Recommended SPEC**: SPEC-105 — Q074 Bull Regime Booster Overlay

This is an **amendment** layered on top of SPEC-104 Arch-3, not a replacement architecture.

### Scope
1. Define B4 benign condition as state-evaluation logic
2. SPX cap state machine extension:
   - Add "booster" state (cap = 90%) above "normal base" state (cap = 80%)
   - Priority: second_leg > stress > booster > normal_base
3. No changes to:
   - SPEC-104 R1/R5/R6 stress and second-leg caps (50% / 40% / triggers)
   - SPEC-104 Q042 staged ramp (17.5% target)
   - SPEC-104 HV Ladder demotion
   - V1-V7 vetoes
4. Add monitoring (see §8)

### Implementation locations
- `strategy/sleeve_governance.py` — add booster cap constant + state evaluation
- Q074 benign signal evaluator (new file or module)
- Production trading engine — consume booster cap when entering new SPX BPS positions
- Dashboard — display current state (booster / normal / stress / 2nd-leg)
- Telegram alerts — notify on booster state transitions

---

## 8. Monitoring Obligations (post-promotion)

| Monitor | Trigger | Action |
|---|---|---|
| Booster active days % (live) | > 60% of normal days | Review — booster definition may be too broad |
| Booster transition incremental loss | Single 10d episode incremental loss > 1% NLV | Review — booster signal failed |
| VIX 20-22 booster activations | Count + IVP distribution | Track if joint-slice characteristic changes |
| Funding cost on negative-cash days | Live actual vs P4 estimate (+0 / +300bp) | Calibration check |
| Normal→stress transition losses | Booster active in prior 10d before stress trigger, incremental < -0.5% NLV | Review |
| H2-style regime vs H1-style regime | Quarterly: classify recent quarter | Forward expectation calibration |
| Rolling 20d / 63d loss | > -7.5% / > -10% | Layer-1 protection check |

All monitors are PM-discretionary triggers (per `feedback_spec_review_obligation`), NOT time-locked obligations.

---

## 9. Caveats Self-Disclosed

1. **All ROE upside concentrated in H2 (post-2013)**: Per P4.2 walk-forward. If next 10-15y look like H1 era (DotCom-style or 2008-style), booster contribution will be close to 0. This is by design — booster is Layer-2 OPTIONAL upside, not core ROE.

2. **VIX 20-22 sample is small (n=20 days over 26y)**: B4-only contribution from VIX 20-22 days is robust per P4.5, but the sample is sparse. Live monitoring should track if joint-slice characteristic (IVP<30 dominant) holds going forward.

3. **Negative cash assumed financed at BOXX yield (+ optional stress) base case**: Real margin loan cost depends on broker. Monitor live actual cost.

4. **Q42 simultaneously at 17.5% target during booster days**: combined exposure 107.5% (SPX 90% + Q42 17.5%). Operational coordination required — PM dashboard should flag combined-exposure days.

5. **B4 promotes to SPEC-105**, but P0 staging: implementation should be **staged** (paper/shadow first 1-3 months), not one-shot production. Per 2nd Quant Q5 alignment with B3 backup option, fallback to B3 always available.

6. **B1/B2 NOT promoted**: ROE upside too small for SPEC effort, but P3/P4 evidence is on file if future research wants weaker booster variants.

---

## 10. P5 Decision

**PROMOTE B4 moderate 90%** as Q074 Bull Regime Booster overlay.

Implementation path:
1. PM approves Q074 final memo (this document)
2. Send to G4 mandatory 2nd Quant final review (per P0 §9)
3. Upon 2nd Quant PASS: draft SPEC-105 amendment
4. PM approves SPEC-105
5. Developer implements (staged rollout: paper → shadow → production)
6. Monitoring (per §8)

Estimated total Quant + Developer time: ~1 week for SPEC + 2-3 days for implementation + 1-3 months staged validation.

---

## 11. References

- `q074_p0_anchored_memo_2026-05-17.md` — P0 (three-party anchored 2026-05-17/18)
- `q074_p1_attribution_memo.md` — P1 diagnostic
- `q074_p2_booster_sweep_memo.md` — P2 sweep
- `q074_p3_transition_forensic_memo.md` — P3 transition forensic
- `q074_p4_validation_memo.md` — P4 evidence layer
- `task/q074_framing_2nd_quant_review_packet_2026-05-17_Review.md` — 2nd Quant pre-research PASS
- `task/q074_p3_g3_2nd_quant_review_packet_2026-05-18_Review.md` — 2nd Quant G3 PASS w/ revisions
