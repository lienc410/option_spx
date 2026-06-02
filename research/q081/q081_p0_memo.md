# Q081 P0 — Cash-bound Premise Verification

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: COMPLETE — verdict ratifies framing premise with nuance
**Anchor snapshot**: 2026-06-01 21:02 ET (Schwab + E-Trade live pull)

---

## Verdict

**Cash-bound premise CONFIRMED, and ACUTE in steady-state.**

PM ratification 2026-06-01 + live data + PM correction (Schwab $301k liquid
moves to QQQ tomorrow → treat as already-QQQ for steady-state baseline) all
support the framing thesis. Effective liquid cash collapses to E-Trade's
$37k = **3.0% of combined NLV**. Median BCD debit ($23.9k) consumes 65% of
total available cash. Two typical BCD positions exhaust all cash, forcing
QQQ/SPY liquidation. Q081 proceeds to P1 with steady-state baseline.

---

## Data — steady-state baseline (PM correction applied)

PM 2026-06-01: Schwab cash $205k + BOXX $96k → QQQ tomorrow. Steady-state
treats Schwab liquid as already-QQQ. Today's literal snapshot lives in
`q081_p0_cash_bound_today_snapshot.csv` for audit; analysis below uses the
post-rebalance baseline (`q081_p0_cash_bound.csv`).

| Metric | Schwab | E-Trade | Combined |
|---|---|---|---|
| NLV | $631,728 | $608,037 | $1,239,765 |
| Cash | 0 (moves to QQQ) | $37,046 (6.1%) | **$37,046 (3.0%)** |
| Beta deployed (QQQ+SPY) | $301,471 (47.7%) | $447,188 (73.5%) | **$748,659 (60.4%)** |
| Individual stocks | $330,365 (52.3%) | $160,848 (26.5%) | $491,213 (39.6%) |
| Maintenance margin | $63,971 (10.1%) | $105,607 (17.4%) | $169,578 (13.7%) |
| BP headroom | $567,924 (89.9%) | $123,431 (20.3%) | $691,789 (55.8%) |

**Sharpened picture**: BP is grossly under-utilized (combined 13.7% maint
margin, 56% headroom), while liquid cash is 3% of NLV. The asymmetry that
the framing memo flagged — BCD consuming the bottleneck resource and not
touching the slack resource — is **structural** in this account.

---

## Observations

### 1. Steady-state profile is uniformly QQQ-displacing
After PM's rebalance, both brokers run heavy beta + low cash. Schwab beta
goes from 0 → $301k; combined beta becomes 60.4% of NLV. Any new BCD MUST
come from either (a) E-Trade's $37k cash or (b) liquidating QQQ/SPY. Both
displace QQQ exposure. Hurdle = QQQ rolling return universally applies.

### 2. Cash-bound premise holds operationally AND sharply
PM does NOT have $0 idle cash. PM HAS actively put all idle cash into beta.
Effective cash for new debit is $37k = 3.0% of NLV. Median BCD debit
($23.9k) is 65% of all available cash. **Two BCD positions exhaust all
liquid cash; subsequent positions require QQQ sales.**

### 3. BP-utilization argument is structurally correct
Combined BP utilization 13.7%, headroom 56% — vast BP slack. A pure
BP-based cap (current SPEC-104 design) would allow ~$300k more BCD debit
before approaching margin limits. But this would require liquidating
~$260k of QQQ/SPY to fund. SPEC-104 has zero language about this trade.
**Framing memo §0 thesis is structurally validated**: BP cap does not
constrain BCD's true bottleneck.

### 4. Concentration risk to flag (Q081 out of scope, but noted)
Post-rebalance, combined beta is $749k = 60.4% of NLV concentrated in
QQQ + SPY (with $447k on E-Trade alone). Worth a separate sleeve-level
review at some point — single broker, single beta. Not Q081's scope.

---

## Implications for P1-P5

- **Hurdle = QQQ rolling return** (PM ratification). After Schwab rebalance,
  there is no longer a "lower hurdle BOXX path" — all displacement is QQQ.
- **Effective cash for BCD = $37k**. Sizing analysis in P1 must show how
  the 21 historical BCD trades would have stacked against $37k available
  cash if PM's current steady-state had been in force.
- **Cap design (if Conclusion 1 wins)**: a `cash_budget_pct ≤ X%` cap on
  combined NLV would have bitten well before BP cap ever did. Likely
  X ≤ 5% NLV gives ~2 BCD positions; X ≤ 10% gives ~5. P3 will choose X
  via hurdle-adjusted ROE.
- **Historical reconstruction caveat**: today's snapshot is point-in-time.
  Daily snapshot history (data/daily_snapshot.jsonl) has NLV but not
  cash/beta breakdown. P1 will project today's profile back as
  representative, or PM can flag historical regime shifts.

---

## Files
- `q081_p0_cash_bound.py` — categorization script
- `q081_p0_cash_bound.csv` — per-broker + combined breakdown
- `q081_p0_memo.md` — this file

---

## Next step

Proceed to **P1** — BCD historical cash deployment timeline. Use the 21 BCD
trades in `data/backtest_trades_3y_2026-04-29.csv` as the trade set; map
each to its actual debit + hold window; check whether any historical date
had BCD aggregate debit > available combined cash (= QQQ/SPY/BOXX would
have been forcibly displaced).

PM ratification not needed before P1 (P0 verdict not "kill"; framing memo §1
G-review 0 is informational only when verdict = continue).
