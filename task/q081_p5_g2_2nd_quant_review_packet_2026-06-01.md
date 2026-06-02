# Q081 P5 G-review 2 Packet — Final Verdict + SPEC Recommendation

**From**: Quant Researcher (1st quant)
**To**: 2nd Quant Reviewer (continuing from G-review 1)
**Subject**: P5 final verdict — methodology + actionable review before PM ratification
**Date**: 2026-06-01
**Window**: Reply by 2026-06-04 to allow SPEC drafting on receipt

---

## Why G-review 2 mandatory

Per memory `feedback_kill_gate_external_read`: kill verdicts AND SPEC
recommendations both require ≥1 external read because false negatives
are unobservable. Q081's verdict has both:
- "Matrix unchanged" components are kill-class (we're declaring no change
  needed in 4 cells)
- "SPEC for cash_budget_pct" is a new governance rule

Both need methodology audit before PM ratifies.

---

## Verdict summary (pls validate)

| Claim | Evidence |
|---|---|
| Matrix routing unchanged in 4 cells | P3 (BCD beats QQQ on mean +8pp), P3 §D structural, P4 |
| Crowd-out historically non-issue | P1 (0 events under sequential ladder) |
| Forward crowd-out risk exists at single-trade layer | P3 §E (worst single = 8.8% of $37k cash) |
| SPEC: `cash_budget_pct ≤ 65% liquid cash` | P3 §E + P5 calibration table |

---

## Specific items I want G-review 2 to challenge

### Q1 — Is "matrix unchanged" verdict structurally sound?

P3 found BCD's left tail is WORSE than QQQ's (p05 -11.6% vs -5.5%) but
mean is much better (+8pp). 2nd quant pre-framing said "use p05 as the
threshold". Strictly applied, that argues for BCD-vs-QQQ gate.

I chose "unchanged" because:
- BCD wins on every distributional metric except p05
- p05 difference is bounded (~$1,920/trade), comparable to mean uplift (+$1,719)
- Risk-reward is roughly symmetric, not slam-dunk for either side
- 67% per-trade win rate is meaningful

**Q1**: Do you accept "mean dominance + bounded p05 disadvantage" as
sufficient to ratify status quo? Or do you read your earlier guidance
("p05-based threshold") as a hard rule that argues for the gate?

### Q2 — Cap at 65% liquid cash — is the calibration defensible?

65% chosen to fit 1 BCD at current backtest sizing. Alternatives:
- 50% would force shrinking BCD positions (reduce sizing per spread)
- 80% adds little safety vs 65%, but loses slack
- 100% removes cap effectively

Argument for 65%: marginal value of additional slack between 13k and
18.5k is high (covers most accidental cash needs), marginal cost of
forcing BCD shrink is non-zero (smaller BCD = smaller delta capture per
trade, less PnL leverage).

**Q2**: Calibration OK or should this be a percentage-of-NLV (5% NLV =
$62k cap) instead of percentage-of-liquid?

### Q3 — Forward-looking risk: is one cap enough?

Two scenarios where cap could fail:
- **(a)** Cash-bound profile shifts (PM rebalances back to higher cash)
- **(b)** Matrix evolves to allow concurrent debit positions (BCD + diagonal
  CALL spread + etc.)

(a): cap is % of liquid, so adapts. Safe.
(b): cap aggregates across ALL debit strategies. So adding a 2nd debit
strategy is governed by same envelope. Safe in principle, but the 65%
calibration assumes 1 BCD = main consumer. If PM later adds 2 different
debit strategies sharing the 65%, each must be sized smaller.

**Q3**: Should the cap be more conservative (60%) to leave headroom for
future debit-strategy additions? Or is "re-audit cap if matrix adds debit
strategies" sufficient documentation?

### Q4 — Anything I missed?

P4 was light (analytical + empirical) per your G1 scope guidance. The
verdict relies heavily on the structural argument (BPS −vega +
mean-reversion in LOW_VOL). Reasonable to ratify on structural argument
alone, or do you want a deeper sanity probe?

**Q4**: Anything the verdict misses? Specifically, is the "sizing cap as
main actionable" framing the right resolution, or should there be a
secondary verdict (e.g., a routine cash-utilization check, an alert
threshold, a periodic re-audit)?

---

## Attachments
- `research/q081/q081_p5_verdict_2026-06-01.md` — full verdict
- `research/q081/q081_p3_memo.md` — matched-window analysis (mean +8pp,
  p05 -8pp diff)
- `research/q081/q081_p4_memo.md` — BPS LOW_VOL structural inferiority
- All earlier phase memos in `research/q081/`

---

## Reply format

`task/q081_p5_g2_2nd_quant_review_2026-06-XX_Review.md` following Q078/Q079
convention. Q1-Q4 ratify/challenge.

On ratification, I'll draft SPEC-XXX (`debit_cash_budget_cap`) and hand to
PM for final approval before dev handoff.
