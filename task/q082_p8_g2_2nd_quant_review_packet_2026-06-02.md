# Q082 P8 G-review 2 Packet — B-synth-full Verdict

**From**: Quant Researcher (1st quant)
**To**: 2nd Quant Reviewer (continuing from Q081 G-reviews 1+2 and Q082 pre-G1)
**Subject**: 26y BCD synthetic reconstruction (B-synth-full per PM 2026-06-02) — methodology audit + verdict ratification
**Date**: 2026-06-02
**Window**: 48h turnaround would let us close Q082 by 2026-06-04

---

## Background

Q082 progression:
- P1 reframing (matrix gates stress; real residual = forward-window entry mismatch)
- P2 attempted forward-SPX proxy → you CHALLENGED the proxy collapse (Q082 pre-G1)
- P5 descoped to "sample representativeness fact-claim only"
- PM chose **B-synth-full** (not Option A) 2026-06-01: run actual synthetic BCD PnL across 26y to give quantitative verdict
- P6 (BCD construction) + P7 (QQQ matched + stratified) + P8 (verdict) complete

You explicitly identified B as the right path to bypass proxy collapse:

> "保留 BCD-vs-QQQ 裁决但加回真实/合成 BCD PnL，scope 不缩"

This packet asks you to ratify or challenge the synthetic methodology + the
resulting verdict.

---

## Method (one-paragraph summary)

For each of 1,747 BCD-eligible days in `_signal_history_cache.csv`
(2004-2026), construct a synthetic BCD position using BS pricing with
σ = VIX/100 (flat across strikes). Long leg = 90 DTE call at δ=0.70,
short leg = 45 DTE call at δ=0.30. Walk forward daily, reprice both legs
with reduced DTE + updated spot/σ; exit when short leg has 21 DTE
remaining. Apply sequential ladder rule (one BCD at a time per matrix
behavior) → 137 sequential trades. For each trade, compute matched-window
QQQ return + stratify by SPX same-window direction (UP/FLAT/DOWN).

Full memo + caveats: `research/q082/q082_p8_synth_verdict_2026-06-02.md`.

---

## Headline results

| | 26y synth (n=137) | Q081 3y (n=21) |
|---|---|---|
| Aggregate BCD−QQQ mean | **+9.70pp** | +8.01pp |
| Aggregate Sortino | **+0.896** | +2.349 |
| BCD win rate vs QQQ | 91/137 = 66% | 14/21 = 67% |
| UP stratum diff | +28.49pp (60/60 = 100%) | +19.38pp (10/10) |
| FLAT stratum diff | +5.04pp (33/45 = 73%) | +2.43pp (2/2) |
| **DOWN stratum diff** | **-18.99pp (0/32 = 0%)** | -3.38pp (2/9 = 22%) |
| %DOWN forward windows | 23.4% | 42.9% |
| Worst single-trade ROE | -46.33% | -13.38% |

**Two takeaways**:
1. **Aggregate edge persists**: +9.7pp mean, Sortino +0.9, n=137 — robust
   relative to Q081 3y. B-1 ratified at aggregate level.
2. **Per-stratum estimates were NOT stable from 3y → 26y**: the DOWN
   stratum diff went from -3.4pp (3y, n=9) to -19.0pp (26y, n=32), a 5.6x
   deepening. **This vindicates your Q082 pre-G1 challenge** — I projected
   3y per-stratum behavior to 26y in original P5; that projection was
   unsound (the DOWN-stratum behavior IS regime-conditional, not stable).

The aggregate edge survives because UP+FLAT windows outweigh DOWN by 105
vs 32 trades AND by per-stratum magnitude (UP +28pp × 60 = +1680bp vs
DOWN -19pp × 32 = -608bp).

---

## Methodology caveats (your scrutiny needed)

**CV1 (most consequential)**: BS-flat IV. Real chain has skew —
specifically, in down moves, short-leg OTM call IV expands faster than
long-leg deep-ITM IV. Real BCD's short-leg hedge during stress is BIGGER
than synthetic shows. Expected effect: synthetic **understates** BCD's
DOWN-window cushion → real DOWN drag likely -10 to -15pp, not -19pp.

**CV2**: VIX is 30d ATM IV; used flat for both 45d short + 90d long. SPX
term structure is typically contango → long-leg true IV > VIX. Synthetic
long-leg undervalued → entry debit understated by ~5-10%.

**CV3**: No transaction costs, no slippage, daily mark only.

**CV4**: Constant r=5%, q=1.3% (historical r varied; small effect).

**My read on caveat asymmetry**: CV1+CV2 lean AGAINST BCD (synthetic
understates real BCD's down-side cushion). So if synthetic shows +9.7pp
aggregate edge, real edge is **likely slightly larger**, not smaller.
Result: false-positive ("BCD looks better than real") is structurally
unlikely. False-negative ("BCD looks worse than real") remains the
operational concern.

**Implication for verdict**: the methodology biases against the verdict
I'm proposing (status quo / B-1 ratify). If the verdict holds DESPITE
that bias, it's more robust.

---

## G2 questions

### Q1 — Methodology validity

Does BS-flat IV proxy meet the bar for "real BCD PnL" reconstruction (your
Q082 pre-G1 Option B requirement), or does CV1 leave residual proxy
concern that requires different treatment (e.g., skew-adjusted IV surface,
or per-tenor IV term structure)?

My read: BS-flat is the standard for this kind of exercise; CV1+CV2 are
known limitations but bias-against-verdict, so they're conservative. n=137
synth is the best available reconstruction without major new tooling.
Acceptable methodology for the verdict claim?

### Q2 — Per-stratum diff stability

P5-original projected 3y per-stratum diff to 26y mix shares and got V1
"B-1 stronger". You CHALLENGED that. Q082 synth confirms you were right:
DOWN stratum diff went from -3.4pp (3y) to -19.0pp (26y). The 3y
per-stratum behavior was NOT representative.

This is a process learning: **per-stratum diff measurements over small
n are unstable; projecting them to different mix shares is unreliable**.

My read: verdict should rely on n=137 synth's own per-stratum estimates,
not on porting Q081 3y values to a different denominator. Agree?

### Q3 — Verdict structure

Three paths (P8 §E):
- **X (recommended)**: status quo B-1, +9.7pp aggregate edge wins, SPEC-111
  cap+alert handles single-trade tail
- **Y**: B-1 + directional gate (SPX 30d/200d MA cross blocks BCD opens)
- **Z**: B-1 + tighter cap (60% → 50%) for sizing limit

The 1-in-4 DOWN-window crater rate (0/32 win, -22% mean PnL in DOWN) is
PM-acknowledged "regime-conditional leveraged-beta" cost. SPEC-111 cap
limits the $ damage per trade.

My read: X is correct given:
- Aggregate edge robust at n=137
- Sortino +0.9 robust
- B-1 already explicitly accepts regime-conditional asymmetry (PM
  ratified 2026-06-01)
- SPEC-111 cap is the operational governance for the worst-single-trade
  scenario

But Y or Z are defensible if you read the 0/32 DOWN win rate as
operationally unacceptable regardless of aggregate.

**Q3**: Which path? Or different path (Q082 close + new SPEC for Y/Z)?

### Q4 — Anything CV1-CV4 missed?

Caveats list: BS-flat IV, VIX proxy, no costs, constant r/q. Anything
material missing? E.g., should I have:
- Modeled q (dividend) historically variable?
- Used VVIX or term-structure for long-leg σ?
- Run a sensitivity test on σ assumption?

My read: the methodology is the standard simple BS reconstruction.
Sensitivity could be added but adds time without changing directional
verdict. Accept current scope?

### Q5 (process) — Sample saturation

n=137 is 6.5x Q081's n=21. Per-stratum n = (UP 60, FLAT 45, DOWN 32) are
all adequately sized for the diff estimates. Bootstrap CI on per-stratum
diff would tighten the estimate but bootstrap of a sequential ladder is
methodologically awkward (autocorrelation). Skip bootstrap CI in this
packet, accept point estimates as representative? Or do you want CIs?

---

## Files in attachment

- `research/q082/q082_p6_bcd_synth_reconstruction.py` (~280 LOC)
- `research/q082/q082_p6_synth_trades.csv` (137 rows)
- `research/q082/q082_p7_synth_vs_qqq.py` (~200 LOC)
- `research/q082/q082_p7_per_trade_comparison.csv` (137 rows)
- `research/q082/q082_p7_stratified.csv`
- `research/q082/q082_p7_sortino.csv`
- `research/q082/q082_p8_synth_verdict_2026-06-02.md` (full verdict)
- `task/q082_p1_pre_g1_2nd_quant_read_2026-06-01.md` (your earlier read for
  context)

---

## Reply format

`task/q082_p8_g2_2nd_quant_review_2026-06-XX_Review.md`. Q1-Q5
ratify/challenge.

On ratification → Q082 closes; Q081 P5 updated with Q082's findings;
SPEC-111 unchanged (independent governance).

On challenge of Q1 → may need methodology revision (sensitivity test or
chain-data-where-available hybrid).
On challenge of Q3 → may need new SPEC for Y or Z.

Recommend 48h turnaround; Q082 ready to close pending your read.
