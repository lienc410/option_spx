# Q073 P1.2 — V3-A Marginal Attribution + Preliminary Combined ROE Bridge

> **Status: P1.2 partial result.**
> **Not final P1 combined portfolio result.**
> Correlation, crisis windows, idle BP, and friction still pending (P1.3 + P1.4).
> Additive estimates below assume strategy independence; real combined Sharpe may differ once cross-strategy correlation is measured.

**Date**: 2026-05-17
**Parent**: `q073_p0_anchored_memo_2026-05-17.md` + `q073_p1_rules_2026-05-17.md` (Rule 1, Rule 6)
**Predecessor**: P1.1 SPX BPS 26y baseline replay

---

## Executive Summary (PM-facing)

The current strategy menu appears stronger than expected at the core level. SPX BPS alone produces roughly **8.5% long-run ROE** in the 26y replay, and V3-A adds a small but positive permission-alpha contribution (+0.19pp). Including HV Ladder and Q042 Sleeve A, the preliminary additive combined estimate is **~10.3% ann ROE** before correlation, friction, and idle-cash treatment.

This means the **8% Q073 floor is likely achievable under the current architecture**. However, the **20% stretch target is unlikely to be reachable by squeezing existing sleeves alone**. The next important work is P1.3/P1.4, especially combined portfolio risk, idle BP attribution, friction, and account-level capital utilization.

**Working hypothesis update**:

> Current architecture likely clears the 8% floor. **Round 2 ROE upside is now mainly a capital deployment / account allocation / idle yield problem, not a "fix broken strategy" problem.** Radical Arch-3 tear-down should become **conditional**, not default.

---

## 1. SPX BPS 26y Baseline Recap (P1.1)

```
Period:           2000-01-01 → 2026-05-17 (26.34 years)
NLV basis:        $894,000 (combined)
Total trades:     372
Win rate:         75.27%
Annualized ROE:   8.52%
Total PnL:        $3,811,556
MaxDD:            -$86,146  (-9.64% NLV)
Sharpe:           1.84
Calmar:           44.25
CVaR-5:           -$39,824  (-4.46% NLV)
CVaR-10:          -$31,285  (-3.50% NLV)
```

**By-strategy WR within SPX matrix**:

| Strategy | WR |
|---|---|
| Iron Condor (HV) | 88.4% |
| Iron Condor | 82.6% |
| Bull Put Spread | 81.1% |
| Bull Put Spread (HV) | 73.8% |
| Bear Call Spread (HV) | 66.7% |
| Bull Call Diagonal | 54.3% |

**Cross-check vs P0 vetoes**:
- V1 MaxDD ≤ 28%? **PASS** (9.64% << 28%)
- V2 worst 20d? Not measured separately — proxy CVaR-5 -4.46% is well under V2 11%
- V3 worst 3m? Not measured separately — need rolling P1.3
- Sharpe 1.84 is high; needs verify if daily-based or trade-based

**Caveat**: `annualized_roe 8.52` engine output discrepancy — $3.81M / 26.34y / $894k = 16.2% arithmetic average. Engine likely uses geometric / time-weighted compounding (probably TWR). Number marked `directional_only` until formula verified.

---

## 2. V3-A With/Without Marginal Attribution (per Rule 1)

| Metric | With V3-A | Without V3-A | **Δ marginal V3-A** |
|---|---|---|---|
| Total trades | 372 | 335 | **+37 trades** |
| Win rate | 75.27% | 72.24% | +3.03pp |
| Ann ROE | 8.52% | 8.34% | **+0.185pp** |
| Total PnL (26y) | $3,811,556 | $3,621,633 | **+$189,923** ($5.1k/trade avg) |
| MaxDD | -$86,146 (-9.64%) | -$94,208 (-10.54%) | **+$8,062 less DD** |
| Sharpe | 1.84 | 1.82 | +0.02 |
| Calmar | 44.25 | 38.44 | +5.81 |

### Interpretation per Rule 1 (permission alpha framework)

V3-A is **net positive permission alpha** along three dimensions:

1. **PnL**: enables 37 incremental trades in aftermath windows, each averaging +$5.1k PnL = +$190k over 26y / ~$7.3k/year
2. **MaxDD reduction**: -0.90pp improvement to combined portfolio tail
3. **WR lift**: 3pp uplift in matrix-level WR

But ROE contribution is **<0.2pp** — V3-A is **not transformative** as a ROE engine. It's a marginal positive that supports its existing classification as **permission/bypass module**.

### V3-A Verdict (Final, per Q064 + Q073 P1.2 confirmation)

```
Keep V3-A. Do not retire.
But do not treat it as a transformational ROE lever.

P3 architecture: V3-A = keep as default in all Arch-0/1/2/3 candidates.
Not a retire candidate unless P1.4 friction or operational burden evidence
turns surprisingly negative.
```

---

## 3. Combined-NLV Contribution (per Rule 6)

| Strategy | PnL source | NLV basis | Years | Combined-NLV ann ROE | Data quality |
|---|---|---|---|---|---|
| **SPX BPS engine (incl V3-A)** | P1.1 26y replay | $894k | 26.34 | **+8.52%** | usable_now |
| **HV Ladder /ES** | Q071 P5: $173k total | $500k (Q071 internal) → $894k | 26.31 | **+0.74%** | usable_now |
| **Q042 Sleeve A (dd4)** | SPEC-094.1: 9.94% sleeve-only × 10% sleeve sizing of $894k | $89.4k sleeve | 19 | **~+1.0%** | directional_only |
| Q042 Sleeve B (dd15) | n=5, research-only (Rule 4) | — | — | **0** (excluded) | not_decision_grade |
| Cash yield on idle BP | per Rule 3, on idle period only | — | — | TBD (待 P1.4) | TBD |
| Friction (estimated) | live SPX BPS data + Q042 paper | — | — | TBD (negative) | TBD |
| Idle yield gap (vs cash baseline) | LOW_VOL + IVP-gate idle periods | — | — | TBD (待 P1.4) | TBD |

### ROE Bridge v0 (Preliminary, additive)

```
SPX BPS engine                                  +8.52%
  其中 V3-A marginal alpha (per Rule 1)         (+0.19% included above)
HV Ladder /ES                                   +0.74%
Q042 Sleeve A (combined-NLV 口径, per Rule 6)   +1.0%
Q042 Sleeve B                                   +0 (research-only)
─────────────────────────────────────────────
Strategy total (additive estimate)              ~10.3%
+ Cash yield on idle BP (待 P1.4)               TBD
- Friction (live data 待 P1.4)                  TBD
- Idle yield gap (待 P1.4)                      TBD
─────────────────────────────────────────────
Preliminary Total Account Return                ~10.3% ± P1.4 adjustments
Excess over BOXX 4.3% cash baseline             ~6.0pp
```

---

## 4. 20% Stretch Feasibility Note

| Target | Status | Reasoning |
|---|---|---|
| Floor 8% | **Likely achievable** | SPX BPS engine alone hits 8.52% on 26y baseline |
| Stretch 20% | **Unlikely achievable from existing strategy menu** | Gap from 10.3% to 20% = +9.7pp. Existing 4 active sleeves max contribute ~10.3pp combined. To reach 20% requires either (a) 2× existing strategy size (likely breaches V1 MaxDD veto), (b) cash baseline 4.3% utilization on full $894k (max +4.3pp), or (c) new strategy primitives (out of Q073 scope per P0 §6). |

Conservative architecture (Arch-1) likely ceiling: **12-14%** (capital efficiency improvements only)
Moderate architecture (Arch-2) likely ceiling: **13-16%** (+ idle BP fallback C1 cash, but cash 4.3% upside is small)
Radical architecture (Arch-3) likely ceiling: **12-15%** (retire operational complexity, redesign matrix — but max strategy alpha is bounded by ~10.3% additive)

**Reaching 20% likely requires Q074+ new strategy primitives** (e.g., butterflies / calendars / new underlyings), which are explicitly out of Q073 scope.

This is **NOT a Q073 failure** — Q073 is succeeding by establishing the realistic feasibility envelope. PM should consider 8-12% as the validated achievable range and 12-15% as the architecture-optimum range.

---

## 5. Q073 Working Hypothesis Update

Original framing (P0): "Find higher ROE architecture, risk-constrained, willing to tear down."

**Updated framing (after P1.1/P1.2 evidence)**:

> Current architecture has a healthy 8-10% core ROE engine. Round 2's main opportunity is **capital deployment / account allocation / idle yield**, NOT strategy mix changes. Radical Arch-3 should be **conditional on capital lever failure**, not the default research path.

### Implications for P2/P3 design

| Phase | Original (P0) | Updated (per P1.2 findings) |
|---|---|---|
| **P2A** (capital) | Run | **Still RUN — now central, not preliminary** |
| **P2B** (cap numeric) | Light Q072 follow-up | Stay light |
| **P2C** (matrix retire/redesign) | Run if P2A insufficient | **Run only if P2A+P2B can't push beyond 12-14%** — conditional, not default |
| **Arch-3 radical** | Default candidate | **Drop to "if needed" candidate** |

PM may update Q073 lever priority post-review.

---

## 6. Next Steps (P1.3 + P1.4)

### P1.3 — Combined Portfolio Risk + Correlation + ROE Bridge

Required outputs (per P0 §7 + 2nd Quant Blind Spot 4):
1. Daily PnL series extraction for each active strategy (SPX BPS + HV Ladder + Q042 Sleeve A + V3-A marginal)
2. Cross-strategy PnL correlation matrix
3. Combined portfolio MaxDD / Sharpe / worst rolling 20d / worst rolling 3m (against V1/V2/V3 vetoes)
4. Crisis-window combined PnL: 2008 GFC / 2020 COVID / 2022 bear
5. ROE bridge (full) replacing preliminary additive estimate

**ETA**: 0.5 day

### P1.4 — Idle BP + Friction

Required outputs (per P0 §7 + Rule 3):
1. Idle BP rolling distribution (30/90/365d mean / 5%-tile / 95%-tile)
2. Idle reason attribution by 6 categories:
   - no signal (策略未触发)
   - IVP block (BPS_NNB_IVP_UPPER ≥ 55)
   - cap block (R1-R6 governance)
   - account split (SPX-only Schwab vs /ES-only ETrade product separation)
   - paper-only strategy (HV Ladder, Q042 not yet production)
   - operational/manual limitation
3. LOW_VOL regime days quantification (per Rule 3 — fillable opportunity)
4. IVP-gate days quantification (per Rule 3 — risk avoidance)
5. Friction adjustment per strategy (live data where available, N/A otherwise per Rule)

**ETA**: 0.5 day

### After P1 Done → P2A (Capital Levers)

Per updated framing, P2A is now the central optimization phase. Focus:
- C1 (cash/T-bill on idle): how much idle BP × 4.3% recovers?
- D (multi-account): is E-Trade $293k under-utilized? Account-specific margin / product split optimization?
- F (sizing): can SPX BPS / HV Ladder sizing be increased without breaching V1-V5?

---

## 7. Caveats (重要)

1. ROE additive 10.3% **未考虑 cross-strategy correlation**. If positive, portfolio Sharpe lower than sum; if negative (hedge-style), portfolio Sharpe higher than sum. P1.3 measures this.
2. SPX BPS engine `annualized_roe 8.52%` engine 口径需 verify (arithmetic / geometric / TWR)
3. HV Ladder $173k Q071 P5 was computed on $500k internal NLV — re-scaling to $894k combined NLV assumes no per-trade sizing change
4. Q042 Sleeve A combined-NLV contribution **~1.0%** is approximate from 9.94% sleeve-only × 10% sizing. Real number needs daily PnL extraction in P1.3
5. Q042 Sleeve B excluded from this estimate per Rule 4 (research-only, n=5 too thin)
6. Friction (live execution slippage / commissions / margin financing) entirely missing — likely negative 0.3-1pp adjustment
7. Idle cash yield not yet credited — could add 0.5-2pp depending on idle %
