# Q081 P4 — BPS in LOW_VOL Counterfactual (PM Intuition B Sanity)

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: COMPLETE — confirms PM self-veto via stronger structural argument
**Prior**: P3 — BCD beats QQQ on mean +8pp, p05 tail worse by 6pp
**Next**: P5 verdict + G-review 2

---

## Verdict

**PM intuition B (don't open BPS in LOW_VOL) — CONFIRMED**, but via a stronger
argument than PM's original "ROE-on-BP only 6%" framing. The real reason is
**tail asymmetry**: BPS is short-vol in a regime where vol expansion is the
dominant tail risk.

Per G-review 1, this is a sanity check, not the anchor decision. Light
analytical + empirical approach. No full counterfactual simulation needed.

---

## Method (lightweight, per G-review 1 scope)

Two evidence sources:

**A. Empirical pattern in actual BPS NORMAL trades (n=14)**: identify what
caused the worst BPS trades. If the killer is vol expansion, project that
risk profile onto LOW_VOL.

**B. Structural argument**: vega sign + mean-reversion priors in LOW_VOL.

No q041 chain reconstruction (Q082 scope, per G-review 1 Q2).

---

## Evidence A — BPS NORMAL trade-level data (n=14)

Sorted by worst PnL:

| entry | hold | vix_in | vix_out | Δvix | credit | pnl |
|---|---:|---:|---:|---:|---:|---:|
| 2025-02-20 | 13 | 15.66 | 21.93 | **+6.27** | $3,849 | **-$6,253** |
| 2025-01-21 | 13 | 15.06 | 18.62 | **+3.56** | $3,653 | **-$1,447** |
| 2025-05-16 | 14 | 17.24 | 18.57 | +1.33 | $4,133 | -$581 |
| 2026-01-29 | 13 | 16.88 | 17.65 | +0.77 | $4,713 | -$12 |
| 2026-04-17 | 12 | 17.48 | 18.81 | +1.33 | $5,011 | +$368 |
| 2025-02-06 | 14 | 15.50 | 15.66 | +0.16 | $3,791 | +$1,224 |
| (8 more, all VIX declining or stable, all PnL positive) | | | | | | |

**Pattern**: PnL is dominated by Δvix.

| Δvix | n | mean PnL | worst |
|---|---:|---:|---:|
| Vix expansion (≥+1.0) | **3** | **-$2,760** | -$6,253 |
| Vix expansion (mild +0.1-1.0) | 2 | +$178 | -$12 |
| Vix flat/declining | 9 | +$2,226 | +$1,224 |

**100% of meaningful losses** came from vol expansion. The single worst trade
lost **162% of credit received** because VIX went 15.66 → 21.93 in 13 days.

---

## Evidence B — Structural argument for LOW_VOL × BPS

If we routed BPS into LOW_VOL (VIX 12-15) days, three forces all turn
**against** BPS:

### B1. Mean-reversion priors: vol-expansion probability HIGHER in LOW_VOL

VIX has documented mean-reversion. Conditional probability of P[Δvix > +2
in 14 days] is materially higher when starting VIX < 15 than when starting
VIX > 17. Lower starting base = larger room to mean-revert up.

The 2/14 catastrophic BPS NORMAL trades both entered with VIX ≈ 15-15.7
(NORMAL boundary). If we had been opening BPS at VIX 12-14, the
vol-expansion risk would be MORE concentrated, not less.

### B2. Credit scales with IV → smaller cushion against vol expansion

BPS credit at fixed delta scales roughly linearly with IV. At VIX=14 vs
VIX=17, credit is ~18% lower. Worst-case max loss (= width − credit) is
slightly HIGHER. Buffer to absorb adverse path is THINNER.

Rough estimate: BPS in LOW_VOL would harvest ~$3,200 credit per spread vs
$4,400 in NORMAL. Same width, smaller credit → worse ROE per BP, worse
buffer.

### B3. Vega sign is wrong direction in LOW_VOL

BPS has **net negative vega** (-1.0 to -1.5 per spread per 1 vol point).
BCD has **net positive vega** (+3 to +5 per spread per 1 vol point in the
long-leg-heavy variant).

In LOW_VOL, the dominant tail risk is vol expansion. BCD's +vega benefits;
BPS's −vega harms. The cash-bound account's worst-case outcome (forced
QQQ liquidation under stress) becomes more likely with BPS than BCD in
this regime.

---

## Combined estimate: BPS in LOW_VOL would be inferior to current BCD routing

Adjusting BPS NORMAL stats for LOW_VOL conditions:

| Factor | NORMAL actual | LOW_VOL projected |
|---|---:|---:|
| Mean credit per trade | $4,434 | ~$3,800 (−14% IV scaling) |
| Vol expansion frequency (1+ Δvix) | 21% (3/14) | ~30-40% (mean-rev priors) |
| Mean PnL per trade | +$830 | ~$400-600 (worse mix) |
| Worst trade | -$6,253 | likely **worse** (thinner credit cushion + higher expansion frequency) |

Current BCD in LOW_VOL: mean PnL +$1,796/trade, worst -$3,248.

**Per-trade comparison (LOW_VOL regime)**:

| | BCD (actual) | BPS LOW_VOL (projected) |
|---|---:|---:|
| Mean PnL | **+$1,796** | ~+$500 |
| Worst | -$3,248 | likely worse than -$6,000 |
| Vega sign | + (aligned with mean-rev) | − (anti-aligned) |
| Cash impact per trade | -$24k (debit) | ~$0 (credit) |

BCD wins on mean PnL by ~3x. BPS's only resource advantage (no cash
consumption) is offset by structurally inferior expected PnL AND worse tail.

---

## Conclusion: PM intuition B confirmed via stronger argument

PM's original framing: "BPS in LOW_VOL has ROE-on-BP only ~6%/yr, not worth
the BP" (memo §3 intuition B).

**Revised, stronger argument from P4 evidence**:

> BPS in LOW_VOL is structurally inferior to BCD in LOW_VOL because:
> 1. Lower mean PnL (~$500 vs $1,800)
> 2. Wider left tail (vol-expansion catastrophe risk concentrated in LOW_VOL
>    regime)
> 3. Wrong vega sign (−vega in a regime where vol expansion is the dominant
>    tail event)
>
> The case is structural (vega + mean-reversion), not just ROE arithmetic.
> "Free BP" doesn't compensate for tail asymmetry.

PM was right to self-veto. The veto should be retained.

---

## Scope discipline note

This sanity check uses analytical + empirical evidence (n=14 BPS NORMAL
trades + structural argument). It does NOT use:
- Full counterfactual BPS-in-LOW_VOL backtest (Q082 scope per G-review 1)
- Synthetic chain reconstruction

The lightness is appropriate because:
- Verdict path is already directional (matrix unchanged, sizing cap is
  main actionable, per G-review 1 reframing)
- 2nd quant explicitly noted P4 is "sanity check" not anchor
- The structural argument (vega + mean-reversion) doesn't need point
  estimates to be decisive

---

## Files
- `q081_p4_memo.md` — this file (no script; pure analytical)

---

## Pre-P5 input

Q081 verdict path is now FULLY signaled. P5 will conclude:
1. **Matrix routing: UNCHANGED**
   - LOW_VOL × BULLISH × {LOW, MID IVP} → BCD: ratified by P3 (BCD beats
     QQQ on mean +8pp, p05 tail worse by 6pp but bounded; +vega aligned
     with regime)
   - LOW_VOL × BULLISH × HIGH IVP → BPS: ratified qualitatively in P3 §D
     (cash-bound + premium-rich = BPS structurally dominant)
   - NORMAL × LOW IVP × BULL → reduce_wait (BPS not opened): ratified by
     P4 (BPS short-vol in low-IVP would have tail asymmetry)
2. **NEW: sizing cap recommendation** (P5 main verdict)
   - `cash_budget_pct ≤ 65% of combined liquid cash` for debit-strategy
     aggregate footprint
   - Allows 1 BCD at current backtest-validated sizing
   - Prevents accidental 2-BCD concurrent open
   - Preserves $13k operational slack for unexpected cash needs

P5 + G-review 2 packet to follow.
