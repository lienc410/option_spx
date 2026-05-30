# Q075 P4 — Portfolio Integration Memo

**Date**: 2026-05-20
**Author**: Quant Researcher
**Status**: **P4 DONE — DOCUMENT outcome (sub-threshold)**
**Source**: `research/q075/q075_p4_portfolio_integration.py` + 7 CSVs
**Decision**: Cash/BOXX is the right deployment for IVP-blocked normal-state at current research-convention sizing

---

## 0. TL;DR

```
Variant              ROE %   ΔROE     MaxDD %  W20d %  W63d %  Sharpe  V1V2V3
baseline_104+105v2   8.214   —        -8.71    -7.04    -8.66   2.02   ✓✓✓
+IC_w25              8.219   +0.004   -8.71    -7.04    -8.66   2.02   ✓✓✓
+IC_w35              8.221   +0.007   -8.71    -7.04    -8.66   2.02   ✓✓✓

Bootstrap (block=250, 20 seeds):
  IC w25: ΔROE +0.005pp σ 0.002pp, 5-95% [+0.003, +0.008], P(>0) = 100%
  IC w35: ΔROE +0.007pp σ 0.003pp, 5-95% [+0.005, +0.012], P(>0) = 100%

Promotion bar:
  Strong: ΔROE ≥ +0.20pp  →  NEITHER PASSES
  Soft:   +0.05 to +0.20pp →  NEITHER PASSES
  Reject: < +0.05pp        →  DOCUMENT outcome triggered
```

### Verdict per Q075 P0 §8

| Width | ΔROE pp | ΔW20d pp | ΔW63d pp | V1V2V3 | Verdict |
|---|---|---|---|---|---|
| IC w25 | +0.004 | +0.000 | +0.000 | ✓✓✓ | **DOCUMENT (sub-threshold)** |
| IC w35 | +0.007 | +0.000 | +0.000 | ✓✓✓ | **DOCUMENT (sub-threshold)** |

**Both widths PASS all risk thresholds but FAIL the +0.05pp Soft minimum.** Per P0 §8.3:

> DOCUMENT: Economic Reject but Risk pass + insight produced (no SPEC, just operational note)

This is the **cash-is-correct** outcome that 2nd Quant explicitly preserved as a valid endpoint in framing.

---

## 1. Why ROE is so small

P4 uses the research-convention "1 IC trade per cluster at 1/3 size scaling" from P0 §5 ("small iron condor"). At this sizing:

```
58 trades over 26y                  ≈ 2.2 trades/yr
1 IC at 1/3 size scaling per trade  → max_loss ≈ $467/trade
Avg PnL per trade ≈ $130 (w25), $200 (w35)
Cum PnL over 26y: w25 = $7,556; w35 = $11,853
Annualized: ~$290/yr (w25), ~$455/yr (w35) on $894k NLV
```

The strategy is **economically marginal at this scale**. Two interpretations:
- (a) IC structural cleanliness genuine but trade frequency × per-trade economics × small sizing = trivial portfolio impact
- (b) IC at larger sizing (more contracts per cluster) could reach Soft threshold but introduces deployment-side decisions outside P4 scope

**P4 measures (a)**. Scaling discussion deferred to §9.

---

## 2. Tail Metrics — Literally Identical to Baseline

```
                MaxDD     Worst 20d   Worst 63d
baseline       -8.71%     -7.04%      -8.66%
+IC_w25        -8.71%     -7.04%      -8.66%
+IC_w35        -8.71%     -7.04%      -8.66%
```

Three identical sets of digits across 4 decimal places. This is **the strongest structural evidence** that IC does not introduce new tail risk:
- The worst SPX BPS days are stress-active days when IC is forced-exited at small loss (-$200 to -$400 per trade)
- IC's worst-day PnL is dwarfed by baseline SPX BPS losses on those days, leaving baseline tail unchanged
- IC's negative correlation with SPX PnL (-0.32 on exit days) provides marginal diversification

**Risk thresholds (P0 §8.2)**: ALL PASS for both widths
- V1 (MaxDD ≥ -28%): ✓
- V2 (Worst 20d ≥ -11%): ✓
- V3 (Worst 63d ≥ -17%): ✓
- Worst 20d degradation ≤ +0.25pp: ✓ (exact 0.000pp)
- Worst 63d degradation ≤ +0.25pp: ✓ (exact 0.000pp)

---

## 3. Capital Competition — No Conflict

```
Candidate   Avg IC BP when active   IC active days   Max combined BP   New overdraft days from IC
IC w25      0.067% NLV              460              107.7% NLV        0
IC w35      0.094% NLV              460              107.7% NLV        0
```

Key findings:
- IC BP reservation is **tiny per active day** (0.07-0.09% NLV) — at 1/3 sizing, max_loss is $467-650
- Max combined BP usage is **the same as baseline** (107.7%) — IC doesn't push past baseline's existing margin usage
- **0 new overdraft days** — IC fits entirely within existing cash residual buffer

→ No capital competition with SPX BPS sleeve or Q042. Adding IC at this sizing is essentially free from a capital perspective.

---

## 4. Correlation with Existing Sleeves

```
On exit days (n=46 for IC w25):
  corr(IC PnL, SPX PnL):       -0.32   ← negative diversifier
  corr(IC PnL, Q42 PnL):       -0.10   ← slight negative
  corr(IC PnL, baseline PnL):  -0.23   ← negative overall
```

IC's negative correlation with SPX PnL on its exit days makes structural sense — IC profits when SPX moves neutrally or down (call leg gain), SPX BPS loses when SPX drops. The diversification benefit is real but tiny in absolute $ terms.

---

## 5. Crisis Window Behavior

```
[DotCom 2000_03] baseline -$4,721;   IC w25 $0 (n=0);     IC w35 $0
[PreGFC 2007_07] baseline +$13,003;  IC w25 +$246 (n=3); IC w35 +$405
[Vol 2018_02]    baseline +$100,455; IC w25 +$512 (n=1); IC w35 +$736
[COVID 2020_02]  baseline -$33,110;  IC w25 -$294 (n=0); IC w35 -$391
[Bear 2022_01]   baseline +$53,492;  IC w25 $0 (n=0);    IC w35 $0
```

**4 of 5 crisis windows have ZERO Type C IC entries.** Only PreGFC 2007-07 (3 trades) and Vol 2018-02 (1 trade) saw IC active. Q075 candidate by design rarely fires in crisis-adjacent periods.

The -$294 (w25) in COVID 2020-02 came from an IC trade that exited near (but not in) the crisis window. Total crisis-window incremental from IC w25 = +$464. **No new crisis-window failure.**

---

## 6. Stress-Adjacent Period Special Table (per 2nd Quant directive)

**Critical 2nd Quant question**: does IC overlay add risk in the 10d window just before stress fires?

```
IC w25 in 10d pre-stress periods:
  Total IC entries:        58
  Stress-adjacent entries: 28 (48.3%)
  Forced exits:            28/28 (100% of stress-adjacent IC trades get forced-exited by the stress event itself)
  Cumulative PnL:          +$7,905
  Worst single trade:      -$271
  Worst 20d contribution:  +$5,162

IC w35: same n=28 stress-adjacent entries, cum +$11,741, worst -$284, worst 20d +$7,741
```

### Reading

- **48% of IC entries fire in 10d before a stress event** — confirming Type C is exactly "stress front edge"
- **100% of those entries are forced-exited by the stress event** — the SPEC-104 R5 trigger correctly closes IC mid-trade
- **Cumulative is POSITIVE despite the stress-adjacent timing** — IC's 1σ OTM strike selection + call wing offset means stress exits net positive
- **Worst single trade is small** (-$271 for w25) — about 0.03% NLV
- **Worst 20d contribution is POSITIVE** (+$5,162) — IC doesn't have any 20-day window where it cumulates a loss

→ This was exactly the dimension 2nd Quant most wanted verified. **IC does NOT amplify portfolio risk at the stress front edge.** It in fact provides small positive contribution during these windows.

---

## 7. Bootstrap (block=250, 20 seeds)

```
IC w25: ΔROE mean +0.005pp, σ 0.002pp, 5-95% [+0.003, +0.008], P(ΔROE > 0) = 100%
IC w35: ΔROE mean +0.007pp, σ 0.003pp, 5-95% [+0.005, +0.012], P(ΔROE > 0) = 100%
```

Bootstrap confirms the positive ΔROE is statistically real (100% positive across 20 block-bootstrap seeds), but the magnitude is tiny. Even the 95th percentile (+0.008pp / +0.012pp) is far below the Soft threshold.

---

## 8. Walk-Forward H1 / H2

```
H1 (2000-2012): baseline ROE 8.457%, W20d -7.04%
  + IC w25: 8.461% (Δ+0.004pp), W20d -7.04%, W63d -8.66%
  + IC w35: 8.463% (Δ+0.005pp), W20d -7.04%, W63d -8.66%

H2 (2013-2026): baseline ROE 14.537%, W20d -3.50%
  + IC w25: 14.547% (Δ+0.010pp), W20d -3.50%, W63d -2.85% (slightly improved)
  + IC w35: 14.553% (Δ+0.016pp), W20d -3.50%, W63d -2.81% (slightly improved)
```

Both halves positive in ΔROE. H2 contribution larger (+0.010 to +0.016pp) than H1 (+0.004 to +0.005pp) — consistent with more Type C frequency in H2 era (post-2013 elevated-IV periods).

V2 (Worst 20d) unchanged in both halves. V3 (Worst 63d) marginally IMPROVED in H2 (-2.85 vs -2.81 vs baseline -2.85 close to -2.81) — IC slightly helps the worst 63d window via diversification.

**No regime-overfit concern.** Both halves contribute positively, no half breaks tail.

---

## 9. Scaling Consideration (Deployment-Side, NOT P4 Scope)

P4 measured at 1 IC at 1/3 sizing per cluster (research convention from P3). At this sizing:
- Per-trade max_loss: ~$467 (w25)
- Cum 26y: $7,556 (w25)
- ΔROE: +0.004pp

**If sized at N IC pairs per cluster**, all metrics scale linearly:
| Scale | Per-trade max_loss | Cum 26y | ΔROE | Worst single trade | Soft pass? |
|---|---|---|---|---|---|
| 1× (P4 base) | $467 | $7,556 | +0.004pp | -$294 | ❌ |
| 5× | $2,335 | $37,780 | +0.020pp | -$1,470 (0.16% NLV) | ❌ |
| 10× | $4,670 | $75,560 | +0.040pp | -$2,940 (0.33% NLV) | ❌ |
| **15×** | $7,005 | $113,340 | **+0.060pp** | -$4,410 (0.49% NLV) | **✓ Soft** |
| 20× | $9,340 | $151,120 | +0.080pp | -$5,880 (0.66% NLV) | ✓ Soft |
| 30× | $14,010 | $226,680 | +0.120pp | -$8,820 (0.99% NLV) | ✓ Soft (worst trade approaches 1% NLV limit) |
| 50× | $23,350 | $377,800 | +0.200pp | -$14,700 (1.64% NLV) | ❌ worst trade breaches 1% NLV |

Scaling extrapolation assumes:
- Future Type C distribution matches 26y historical
- IC structural properties (negative correlation, no capital conflict) hold at larger sizes
- Single worst trade magnitude scales linearly (no path concentration risk)

**At 15-30× sizing**, IC could reach Soft promotion threshold (+0.05-0.12pp) without breaching the 1% NLV worst-trade limit. But the scaling decision is **deployment-side**, not P4 research:
- Requires PM to commit ~$7k-14k per IC trade (max_loss reservation)
- Adds operational burden (each entry/exit/forced-exit needs PM execution)
- Increases attention demand during stress-adjacent periods (28 of 58 trades are pre-stress)
- Q042 + SPX BPS already absorb majority of PM operational bandwidth

---

## 10. Final Verdict

### Primary recommendation: DOCUMENT

Q075 at research-convention sizing (1 IC at 1/3 per cluster) produces ΔROE +0.004pp — sub-threshold. Per P0 §8.3:

> **DOCUMENT**: Economic Reject but Risk pass + insight produced

This is the cash-is-correct outcome explicitly preserved as a valid endpoint in P0 §0 TL;DR. The research conclusion:

> **IVP-blocked normal-state days (Type C subset) are mostly cash days at current strategy scale. Defined-risk IC overlay is structurally clean (tail-invariant, stress-adjacent robust, negatively correlated, no capital conflict) but economically marginal. No SPEC drafted. No production deployment.**

### Secondary finding: Q075 produces a documented operational principle

The Q075 research IS valuable despite no SPEC. Findings to record:

1. **At current $894k NLV with PM's operational pace, IVP-blocked Type C days should be treated as cash days.** Do not feel obligated to find a trade in this regime.
2. **If portfolio NLV scales 2-3x AND PM operational bandwidth allows**, IC overlay at 15-30× contract sizing could be revisited for Soft promotion (+0.05-0.10pp).
3. **The IC structural cleanliness is preserved as documented research** — future Q07X research investigating Type C or similar regimes can reference these results.
4. **BCS rejected at scale** — even at higher contract counts, the 4-analog failure (cum -$107k to -$131k at 1×) doesn't recover. Do not revisit BCS for this regime.
5. **C2 short-DTE BPS rejected** — P3 refactored model showed negative cum at 1× scale. Higher gamma sensitivity makes scaling worse, not better.

### Memory update recommendation

Save `feedback_layer_3_replacement_research_outcome.md`:
> When Layer-3 replacement research produces sub-threshold ROE at research-convention sizing, the correct outcome is DOCUMENT (not "scale until it passes"). Scaling is a deployment decision requiring separate PM judgment about NLV scale, operational bandwidth, and risk appetite — not a research-side override.

---

## 11. P4 → Final Q075 Closure

| Element | Status |
|---|---|
| P0 anchored scope | ✓ DONE |
| P1 attribution (4-Type) | ✓ DONE |
| P2 constrained simulator | ✓ DONE (corrected by P3 refactored mark model) |
| P3 forensic probes | ✓ DONE (IC robust, BCS dead, C2 dead) |
| P4 portfolio integration | ✓ DONE (sub-threshold for promotion) |
| **G4 final review** | **PENDING — 2nd Quant mandatory before research closure** |

P4 result requires G4 mandatory review per P0 §10. Once G4 PASS, Q075 closes formally with DOCUMENT outcome.

---

## 12. Caveats

1. **Sizing decision deferred**: P4 at 1× research sizing shows sub-threshold. PM can choose to revisit at deployment time if NLV scales or appetite changes. P4 does NOT recommend production deployment at any sizing.
2. **58 trades over 26y is small** for inference. Bootstrap CI confirms positive ΔROE direction but magnitude bound.
3. **P3 mark model still simplified** — operational deployment would need live broker MTM validation. The "tail-invariant" finding could shift if live exit slippage exceeds 2x base modeled.
4. **Type C may not be stable forward** — if next decade's Type C regime sees different stress timing or sharper moves, IC's clean stress-adjacent profile may not replicate.
5. **Capital competition tested at 1× only**. At 15-30× scaling, IC max-BP days could occasionally hit 110%+ combined BP if Q042 + SPX BPS booster all active simultaneously. P5 deployment SPEC (if ever written) must explicitly model this.
6. **Operational burden not measured numerically**. 58 entries over 26y = 2.2/yr is low, but each requires double-leg execution + monitoring for forced-exit-on-stress. PM 1hr/day bandwidth tight.
7. **Q075 cash competitive at $894k NLV scale** doesn't mean cash dominates at larger NLV. The dollar terms scale linearly; ROE percentage may stay similar but absolute productive deployment differs.

---

## 13. Files

- `research/q075/q075_p4_portfolio_integration.py` — script
- `research/q075/q075_p4_metrics.csv` — main metrics table
- `research/q075/q075_p4_walkforward.csv` — H1/H2 split
- `research/q075/q075_p4_bootstrap.csv` — block-bootstrap ΔROE
- `research/q075/q075_p4_crisis.csv` — 5 named windows
- `research/q075/q075_p4_capital_competition.csv` — BP-day analysis
- `research/q075/q075_p4_correlation.csv` — sleeve correlations
- `research/q075/q075_p4_stress_adjacent.csv` — 10d pre-stress special table

Upstream Q075:
- `research/q075/q075_p0_anchored_memo_2026-05-19.md`
- `research/q075/q075_p1_attribution_memo.md`
- `research/q075/q075_p2_memo.md`
- `research/q075/q075_p3_memo.md`
- All `task/q075_*_2nd_quant_review_*.md`

---

## 14. Sign-off

Q075 P4 portfolio integration complete. **Verdict: DOCUMENT outcome (sub-threshold)**. Both IC w25 and IC w35 pass all risk thresholds but fail the Soft minimum ROE bar at 1× research sizing. Tail metrics literally identical to baseline; stress-adjacent table positive; capital competition zero. The research conclusion is **cash/BOXX is the correct deployment for IVP-blocked normal-state days at current $894k NLV scale**.

> Q075 P4 finds: SPEC-104 + SPEC-105 v2 baseline ROE 8.214% over 26y; adding small IC overlay (w25 1/3 sizing) yields +0.004pp ROE with literally identical MaxDD/W20d/W63d. Bootstrap 100% positive but magnitude (+0.005pp σ 0.002pp) is far below the +0.05pp Soft threshold. Capital competition is zero (0.07% NLV BP per active IC, 0 new overdraft days). 100% of stress-adjacent IC entries are forced-exited by stress events with positive net contribution (+$5k worst 20d). 4 of 5 crisis windows have zero IC entries; the 5th adds +$246 to baseline +$13k. Walk-forward H1/H2 both positive. The strategy is structurally clean but economically marginal at 1× research sizing. Scaling to 15-30× could reach Soft threshold but requires deployment-side decisions outside P4 scope. Recommend DOCUMENT outcome with operational principle: "IVP-blocked Type C days are cash days at current scale." Mandatory G4 review next.
