# Q073 P5 Final — 2nd Quant Review Packet

**Date**: 2026-05-17
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **Final P5 review — Q073 PROMOTE recommendation**
**Decision sought**: PASS / REVISE / REJECT Arch-3 promote + SPEC handoff scope

---

## 0. TL;DR

Q073 (Round 2 ROE Optimization) recommends **Arch-3** as the new portfolio architecture:

```
Normal SPX cap   : 80%
Stress SPX cap   : 50%   (R5 trigger reduces 70 → 50, tightening from SPEC-103)
Second-leg cap   : 40%   (R6 trigger, tightening from SPEC-103)
HV Ladder /ES    : 0%    (DEMOTE to research-only / paper-only)
Q042 Sleeve A    : 17.5% (CAP INCREASE from SPEC-094 10%)
Cash (BOXX)      : residual

Result (Net, 26y, P4 validated):
  Ann ROE         : 7.95%  (vs P0 floor 8%, in rounding)
  MaxDD           : -8.71%  (V1 28% ✓)
  Worst 20d       : -7.04%  (V2 11% ✓, buffer 3.96pp)
  Worst 63d       : -6.94%  (V3 17% ✓)
  Sharpe          : 1.97
  V6 bootstrap    : 100%
  V7 walk-forward : both halves pass floor 8%
```

**Fallback (Arch-2)** if PM refuses HV demote OR Q042 cap increase:
```
Normal SPX 80% / Stress 50% / 2nd-leg 40%, HV Ladder 5%, Q042 12.5%
Net ROE 7.99%, but worst 20d -10.25% (V2 buffer only 0.75pp)
```

Final memo: `research/q073/q073_final_memo.md`.
Evidence layer: `research/q073/q073_p4_validation_results.md`.

---

## 1. Q073 Journey Recap

| Phase | Setup | Net ROE | Worst 20d | V2 |
|---|---|---|---|---|
| P0 anchored | floor 8% / stretch 20% / V1-V7 | — | — | — |
| P1.3R unified-NLV (Arch-0) | static 60% SPX, no governance | 7.50% | -12.46% | FAIL |
| P1.5a actual R5/R6 (Arch-1) | normal 70 / stress 60 / R6 50 | 7.87% | -11.82% | FAIL |
| P1.5b enhanced stress cap 50% | stress 50 / 2nd-leg 40 | 7.76% | -10.18% | **PASS** |
| P2A original (Candidate E5) | + SPX 80% normal | 7.99% gross | -10.25% | PASS |
| P2A+ friction-corrected (Arch-2) | full friction model | 7.99% net | -10.25% | PASS, floor ≈ |
| **P3 Arch-3** | **demote HV, Q42 17.5%** | **7.95%** | **-7.04%** | **PASS, big buffer** |
| P4 validation | bootstrap / WF / concentration / friction / synthetic | passes all | passes | **robust** |

Key finding: **Arch-3 sacrifices 0.04pp ROE for 3.21pp worst-20d improvement** — one-sided trade.

---

## 2. Six Pre-emptive Questions for 2nd Quant

### Q1 — Arch-3 vs Arch-2 framing correct?

I recommend **Arch-3 as preferred, Arch-2 as fallback** (single recommendation with backup) rather than "both promoted as parallel candidates". Reason: Arch-3 dominates Arch-2 on every risk dimension while sacrificing 0.04pp ROE (in bootstrap noise). Presenting them as parallel candidates would be false equivalence.

**Question for 2nd Quant**: Do you agree with single-recommendation framing, or should the SPEC offer both as PM-selectable options?

### Q2 — HV Ladder demotion language

I propose **"demote to research-only / paper-only"** rather than "retire" or "delete". This:
- Preserves Q071 P5 standalone validity (Sharpe 0.34, sig 100%)
- Makes clear the demotion is portfolio-level fit, not standalone strategy failure
- Leaves door open for re-promotion if future HV-specific tail gating is researched
- Avoids the awkward optics of demoting SPEC-101/102 within 3 days of their deployment

**Question**: Is the framing transparent enough about the Q071 → Q073 transition (single-strategy promote → portfolio demote)?

### Q3 — Q042 17.5% cap increase — staged or direct?

P4.3 shows Q042 concentration is robust (top-5 only 32% of total, removing top-5 drops ROE 0.06pp). So 17.5% is **not concentration-fragile**.

Options:
- **Direct**: 10% → 17.5% in one SPEC amendment
- **Staged**: 10% → 12.5% → 15% → 17.5% over 3-6 months with live trade monitor
- **Hybrid**: SPEC amendment direct, but production deployment ramps over time

PM may prefer staged for operational caution (Q042 is paper, live forward sample minimal). I default to **direct SPEC amendment + staged operational ramp**, but defer to 2nd Quant on robustness threshold.

**Question**: Should P5 force a staged ramp, or leave operational pacing to PM?

### Q4 — SPEC-103 R5/R6 numeric tightening — sub-SPEC of Q073 or separate?

Arch-3 requires:
- R1 normal cap 70% → 80%
- R5 stress cap 60% → 50%
- R6 second-leg cap 50% → 40%

These are governance amendments. Q072 / SPEC-103 was originally 2nd-Quant-reviewed; tightening caps further could be:
- **Sub-SPEC under Q073 promote**: bundled in Arch-3 SPEC
- **Separate governance SPEC**: requires its own 2nd Quant approval

I default to **single integrated SPEC with sub-section** for governance cap tightening, but defer to 2nd Quant on whether governance changes need separate review process (per Q072 precedent).

**Question**: Single integrated SPEC OK, or governance tightening separate SPEC?

### Q5 — Forward monitoring triggers reasonable?

I proposed PM-discretionary triggers (per `feedback_spec_review_obligation`):
- Single rolling 20d loss > -8%
- Cumulative 90d ROE < 0
- HV-specific re-promotion signal
- Q042 cap utilization breach
- R5/R6 trigger frequency change

**Question**: Are these triggers appropriate, or should specific quantitative thresholds be added (e.g., 12-month formal review)?

### Q6 — Methodology completeness

P4 covered:
- V6 bootstrap (Q071 method, block=250, 20 seeds)
- V7 walk-forward split-sample (2000-2013 vs 2013-2026)
- Q042 concentration analysis (top-N contribution)
- Friction sensitivity (±50%)
- Synthetic crisis stress (-2% NLV injection)

**Question**: Anything missed that should be in P4 before SPEC handoff?
- Specific concern: I did NOT do 2008 / 2020 / 2022-style synthetic shock injection (just a -2% calm-period shock); historical crises are already covered in crisis windows.
- Specific concern: I did NOT do correlated model error stress (slippage + fills + margin estimate all bad at once) — covered conceptually by friction ±50% but not jointly.
- Specific concern: I did NOT run V6 / V7 on Arch-2 + Arch-3 separately for Q042 contribution sensitivity at intermediate sizing (15% vs 17.5%).

If any of these are decision-critical for 2nd Quant, P4 can be extended.

---

## 3. Caveats Self-Disclosed

### Caveat 1 — Q071 → Q073 framing optics
HV Ladder demoted within 3 days of SPEC-101 / SPEC-102 deployment. Honest framing required.

### Caveat 2 — Q042 17.5% > current SPEC-094 cap
Requires PM acceptance per Rule 4 + P0 §5 (cap **数值** allowed under "可调" tier).

### Caveat 3 — Q042 live forward sample minimal
5 paper-trade entries since 2026-05-10. Friction estimate for 17.5% allocation extrapolated from 10% baseline.

### Caveat 4 — SPEC-103 R5/R6 tightening governance precedent
Q072 originally 2nd-Quant-reviewed; tightening may need its own governance review.

### Caveat 5 — 20% stretch not achievable from current menu
Q073 reaches floor 8%, not stretch 20%. P0 framed stretch as aspirational per 2nd Quant P0 review.

### Caveat 6 — Forward-sample reliance
Q042 / HV Ladder / V3-A Aftermath all have limited live evidence. Production deployment will accumulate sample over months. 12-month live review recommended per PM discretion (not time-locked per memory).

---

## 4. Decision Matrix for 2nd Quant

| Reviewer verdict | Action |
|---|---|
| **PASS** Arch-3 + framing acceptable | PM drafts integrated SPEC; Quant implements + deploy |
| **REVISE** specific points | Quant updates final memo + P4 (if methodology), re-submit |
| **REJECT** Arch-3 promote | Quant defaults to Arch-2 + reframes SPEC; or re-opens P2C strategy matrix redesign |
| **REVISE** to require parallel Arch-2 + Arch-3 promote | Quant rewrites SPEC for dual candidate, PM selects |

---

## 5. Supporting Files

| File | Purpose |
|---|---|
| `research/q073/q073_final_memo.md` | Decision layer (P5) |
| `research/q073/q073_p4_validation_results.md` | Evidence layer (P4) |
| `research/q073/q073_p3_architecture_candidates.md` | Arch-2 vs Arch-3 comparison |
| `research/q073/q073_p2a_plus_e5_candidate_memo.md` | Friction model + E5 origin |
| `research/q073/q073_p1_5_governance_baseline.md` | P2A anchor (stress 50/2nd-leg 40) |
| `research/q073/q073_p1_3r_unified_nlv_baseline.md` | unified-NLV baseline |
| `research/q073/q073_p1_2_marginal_attribution.md` | V3-A marginal alpha |
| `research/q073/q073_p0_anchored_memo_2026-05-17.md` | P0 sign-off |
| `research/q073/q073_p1_rules_2026-05-17.md` | 7 binding rules |
| `task/q073_p0_2nd_quant_review_2026-05-17_Review.md` | P0 framing review |
| `task/q073_roe_round2_framing_2nd_quant_review_packet_2026-05-17_Review.md` | Framing review |

All compute scripts in `research/q073/q073_p*_*.py`. Data outputs in `research/q073/*.csv`.

---

## 6. Quant Researcher Sign-off

Quant submits Q073 final to 2nd Quant for review 2026-05-17. Awaiting verdict.

> **Q073 finds the realistic risk-constrained portfolio ROE ceiling at ~8% net under the current strategy menu. Arch-3 (demote HV, raise Q042) is the recommended architecture, achieving the floor with materially better tail than Arch-2.**
