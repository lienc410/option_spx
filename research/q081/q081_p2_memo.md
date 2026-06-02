# Q081 P2 — BCD Cash-ROE Distribution + Left Tail

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: COMPLETE — awaiting G-review 1
**Prior**: P1 — 0 historical crowd-out; opp cost 6.6% of gross PnL
**Next**: G-review 1 (left-tail methodology) → P3 (QQQ hurdle benchmark)

---

## Verdict

**Use period-ROE (not annualized) for left-tail comparisons.** Annualizing
short-hold losses (worst trade exits in 3 days) creates absurd tail values
(p05 = -454%) that pollute the distribution. Period-ROE p05 = **-11.61%**
is bounded, interpretable, and ready for hurdle comparison in P3.

**Headline left tail**: 5% of BCDs lose ≥11.6% of debit per trade. Mean
gain +8.32%, median +4.35%. Bootstrap 95% CI on period-ROE p05:
**[-13.38%, -8.28%]** (boot SE 1.72%).

---

## Critical methodology flag (G-review 1 input)

The annualization convention amplifies short-hold losses. Worst BCD trade:
-$3,248 over 3 days against $24k debit = **-13.4% period**. Annualizing:
−13.4% × 365/3 = **−1631%/yr**. This is mathematically valid but
statistically meaningless for left-tail estimation:

- Period-ROE p05 = -11.6% (CI [-13.4%, -8.3%], SE 1.7%)
- Annualized p05 = -454% (CI [-1361%, -223%], SE 430%)

The annualized SE is 430% → garbage signal. For tail comparison against
QQQ in P3, **use period-ROE with matched-window QQQ returns** (compute
QQQ return over each BCD's actual hold window). Do NOT compare BCD
annualized vs QQQ annualized.

This is a methodology call I want G-review 1 to ratify before P3.

---

## Distribution table (period-ROE = pnl ÷ debit per trade)

| Bucket | n | mean | median | p05 | p01 | min | p05 95% CI |
|---|---:|---:|---:|---:|---:|---:|---|
| all | 21 | +8.32% | +4.35% | **-11.61%** | -13.03% | -13.38% | [-13.4%, -8.3%] |
| ivp_LOW (<33) | 15 | +11.11% | +8.81% | -12.14% | -13.13% | -13.38% | [-13.4%, -8.5%] |
| ivp_MID (33-67) | 6 | +1.36% | -0.44% | -8.11% | -8.60% | -8.72% | [-8.7%, -3.3%] |
| ivp_HIGH (≥67) | 0 | empty (BCD never opens in HIGH IVP per matrix) | | | | | |
| vix_[12,13) | 3 | +17.10% | +28.25% | -7.63% | -10.82% | -11.61% | n too small |
| vix_[13,14) | 3 | +4.23% | +2.45% | -11.80% | -13.07% | -13.38% | n too small |
| vix_[14,15.5) | 15 | +7.39% | +4.35% | -9.46% | -10.84% | -11.19% | [-11.2%, -7.0%] |

Worst trade absolute: **-$3,248** (2023-08-14 → 2023-08-17, 3 days, IVP=8.8,
VIX=14.84, BULLISH trend). LOW_VOL + LOW_IVP + BULLISH cell — exactly the
cell PM is questioning.

---

## Observations

### 1. Mean and median are positive in every sub-bucket where n ≥ 6
BCD edge is real: mean +8.3% period, median +4.4% over ~34 day hold. Even
in the borderline MID IVP sub-bucket (n=6), median is only barely negative
(-0.4%).

### 2. Left tail is materially wider than typical mean-reverting strategy
p05 at -11.6% means: if you run 20 BCDs, expect one to lose ≥11.6% of
debit. Worst-case observed is -13.4%. For comparison, BPS in NORMAL
(separate sample) had worst trade -$6,253, but that's against $4.4k credit
(margin/cash impact differs) so direct comparison requires care.

### 3. IVP gradient: lower IVP = wider distribution
- IVP_LOW (n=15): mean +11.1%, p05 -12.1% — high-mean, wider tail
- IVP_MID (n=6): mean +1.4%, p05 -8.1% — modest mean, tighter tail
- IVP_HIGH: BCD never opens (matrix routes elsewhere)

Pattern: BCD's positive vega is most valuable in low-IV environments where
vol can expand from already-low levels. But low-IV is also where short-leg
gamma risk bites if SPX dumps.

### 4. n=21 is borderline for p05 estimation but acceptable
Bootstrap SE on period p05 = 1.72%. CI half-width = 5.1pp on a -11.6%
estimate (relative SE ≈ 15%). Sub-buckets with n=3 are unreliable; n=6
sub-bucket is borderline; n=15 sub-bucket (LOW IVP, VIX [14,15.5)) is the
operational data.

---

## G-review 1 questions for 2nd quant

1. **Methodology**: Period-ROE for left-tail comparison (not annualized) —
   ratify or counter-propose?
2. **Sample expansion**: Should we synthesize more BCD history via q041
   chain reconstruction? n=21 → potential n=60-100 over 6y. Cost: 2-3 days
   tooling, may be redundant with broker fills.
3. **Empty IVP_HIGH bucket**: Per matrix, BCD never opens in HIGH_IVP. Do
   we need a counterfactual BCD-in-HIGH-IVP backtest to ensure verdict
   isn't blind to that regime? Or accept matrix as binding constraint?
4. **Worst trade pattern**: -$3,248 in 3 days hit on LOW_VOL+LOW_IVP+BULLISH
   cell. Should P5 verdict include sizing recommendation (e.g., "BCD debit
   should not exceed X% of liquid cash") even if matrix-selection verdict
   is "status quo"?

---

## Files
- `q081_p2_bcd_cash_roe.py` — script
- `q081_p2_bcd_cash_roe.csv` — per-trade ROE table (entry, exit, hold,
  vix, ivp, debit, pnl, period+annualized cash-ROE)
- `q081_p2_bcd_roe_distribution.csv` — distribution stats per bucket
- `q081_p2_memo.md` — this file
- `task/q081_p2_g1_2nd_quant_review_packet_2026-06-01.md` — G-review 1
  packet (to be created next)
