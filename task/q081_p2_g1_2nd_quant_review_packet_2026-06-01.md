# Q081 G-review 1 — Left-tail Methodology

**From**: Quant Researcher (1st quant)
**To**: 2nd Quant Reviewer (continuing from Q081 pre-framing 2026-05-29)
**Subject**: Pre-P3 methodology ratification for BCD vs QQQ left-tail comparison
**Date**: 2026-06-01
**Window**: Reply by 2026-06-03 to keep P3 on schedule

---

## Context

Per Q081 framing memo §1 and your 2026-05-29 pre-framing memo §2 ("BCD vs
QQQ 必须扣掉左尾后再比"), Q081 P2 is complete. Distribution of BCD
per-trade cash-ROE is computed. Before P3 (QQQ hurdle benchmark and
BCD-vs-QQQ comparison), I need your ratification on 4 methodology
questions.

P0 + P1 + P2 status (no surprises):
- **P0**: Cash-bound confirmed by PM + live snapshot. Steady-state liquid
  cash = $37k (3% NLV) after Schwab cash → QQQ rebalance.
- **P1**: 0 historical crowd-out (sequential BCD ladder); 66% avg cash
  consumption per BCD; cumulative opp cost 6.6% of gross PnL.
- **P2**: BCD period-ROE distribution computed (n=21).

---

## Question 1 — Period-ROE vs annualized for left-tail

I propose using **period-ROE** (pnl / debit) for left-tail comparisons in
P3, not annualized.

**Rationale**: Annualizing short-hold losses inflates p05 absurdly.

| Metric | Period | Annualized |
|---|---|---|
| p05 | **-11.61%** | -454.66% |
| 95% CI | [-13.4%, -8.3%] | [-1361%, -223%] |
| Bootstrap SE | 1.72% | 430% |

The worst BCD trade (-$3,248 over 3 days = -13.4% of $24k debit)
annualizes to -1631%/yr. Real but meaningless for tail estimation.

P3 plan: for each of 21 BCD trades, compute QQQ return over the **same
hold window** (not annualized either). Then compare period distributions
directly. e.g., BCD period p05 vs QQQ same-window p05.

**Q1 to you**: Ratify period-ROE for tail comparison, or counter-propose?

---

## Question 2 — Sample expansion via Q041 reconstruction

n=21 BCD trades over 3y. Bootstrap SE on period p05 = 1.72% (15% relative
SE on -11.6% estimate). Adequate but borderline.

**Option A (current)**: stick with n=21. P3 verdict has wider CI but
defensible.

**Option B (expand)**: reconstruct synthetic BCD history via q041 chain
data 2020-2026 → potential n=60-100. Cost: 2-3 days tooling. Benefits:
tighter CI, IVP_HIGH bucket can be populated (matrix doesn't open BCD
there, but counterfactual would tell us if matrix is correctly skipping).

**Q2 to you**: stay with n=21 or invest 2-3 days for n=60-100? My weak
preference is A (n=21 already shows the structure clearly; expansion
mainly tightens CI not changes shape), but defer to your judgment on
whether the IVP_HIGH counterfactual is decisively needed.

---

## Question 3 — Empty IVP_HIGH bucket

By matrix design, BCD never opens when IVP ≥ 67 (those days route to BPS
or to other strategies). So our sample is 100% IVP < 67. Two readings:

**(a) Accept binding**: Matrix is the constraint; we evaluate "BCD as
deployed" not "BCD if forced into all IVP states". Verdict scope: should
LOW_VOL × BULLISH × {LOW or MID IVP} continue routing to BCD?

**(b) Synthesize counterfactual**: Build synthetic BCD trades for IVP ≥ 67
historical days to see if BCD edge degrades when premium IS available
(i.e., is the matrix's IVP ≥ 67 → BPS routing correct vs an
unconditional-BCD alternative?).

I lean (a) since the verdict question is about the CURRENT routing not
about a redesigned matrix. (b) is Q082-class scope.

**Q3 to you**: (a) or (b)?

---

## Question 4 — Sizing recommendation in P5

Worst trade -$3,248 hit on LOW_VOL + LOW_IVP + BULLISH cell — the cell PM
is auditing. -$3,248 / $37k cash = 8.8% of cash baseline as single-trade
draw. Per memory `feedback_strategy_metrics_pack`, max single-trade loss
as % NLV (5% gate) is sub-noise-threshold but operationally important.

Should P5 verdict include a **sizing recommendation** alongside the
matrix-selection conclusion? Even if matrix stays unchanged, "BCD debit
should not exceed X% of liquid cash" as a soft rule could prevent the
12-14k slack from being eaten by an outsized BCD.

**Q4 to you**: include sizing recommendation in P5 scope, or defer to
separate sleeve-design SPEC?

---

## Data attachments
- `research/q081/q081_p2_bcd_cash_roe.csv` — 21 trades, all fields
- `research/q081/q081_p2_bcd_roe_distribution.csv` — buckets + stats
- `research/q081/q081_p2_memo.md` — full P2 narrative

---

## Reply format

Please reply at `task/q081_p2_g1_2nd_quant_review_2026-06-XX_Review.md`
following Q078/Q079 convention. Short Q1-Q4 ratify/counter is sufficient;
no need to re-do analysis.

Reply deadline: 2026-06-03 (24-48h turnaround). P3 starts on receipt.
