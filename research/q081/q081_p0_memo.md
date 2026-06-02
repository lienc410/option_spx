# Q081 P0 — Cash-bound Premise Verification

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: COMPLETE — verdict ratifies framing premise with nuance
**Anchor snapshot**: 2026-06-01 21:02 ET (Schwab + E-Trade live pull)

---

## Verdict

**Cash-bound premise CONFIRMED, with operational nuance.**

PM verbal confirmation 2026-06-01 + live data both support that idle cash is
actively managed, not sitting fallow. Any new BCD debit DOES displace
yield-bearing capital. Q081 proceeds to P1.

But the picture is asymmetric across brokers, which affects the cap design
in §3 below.

---

## Data snapshot

(Full numbers in `q081_p0_cash_bound.csv`. Headlines:)

| Metric | Schwab | E-Trade | Combined |
|---|---|---|---|
| NLV | $631,728 | $608,037 | $1,239,765 |
| Cash (raw) | $205,254 (32.5%) | $37,046 (6.1%) | $242,299 (19.5%) |
| Cash-like (BOXX) | $96,217 (15.2%) | 0 | $96,217 (7.8%) |
| **Total liquid** | **$301,471 (47.7%)** | **$37,046 (6.1%)** | **$338,516 (27.3%)** |
| Beta deployed (QQQ+SPY) | 0 | $447,188 (73.5%) | $447,188 (36.1%) |
| Individual stocks | $330,365 (52.3%) | $160,848 (26.5%) | $491,213 (39.6%) |
| Maintenance margin | $63,971 (10.1%) | $105,607 (17.4%) | $169,578 (13.7%) |
| BP headroom | $567,924 (89.9%) | $123,431 (20.3%) | $691,789 (55.8%) |

---

## Observations

### 1. The two brokers run very different resource profiles
- **Schwab is BP-loose AND cash-loose** (89.9% BP headroom, 47.7% liquid). Cash management via BOXX (1-3mo T-bill ETF, ~5% yield).
- **E-Trade is BP-tight AND cash-tight** (20.3% BP headroom, 6.1% raw cash). Heavily deployed in QQQ + SPY (73.5% of NLV).
- **Combined**: BP overall loose (55.8% headroom), but cash actively put to work — $543k in QQQ/SPY/BOXX = 43.8% of NLV is yield-bearing-but-not-idle.

### 2. Cash-bound premise holds operationally, not literally
PM does NOT have $0 idle cash. PM HAS actively managed all idle cash into yield instruments. **Premise correctly translates to**: any new debit must displace BOXX (5% hurdle) or beta exposure (~10% QQQ hurdle, per PM ratification).

### 3. BCD opening creates asymmetric drag depending on broker
- BCD on Schwab → likely displaces BOXX or raw cash. Hurdle ≈ 5%.
- BCD on E-Trade → no room to add debit without liquidating QQQ/SPY. Hurdle ≈ QQQ rolling return (~10%, per PM ratification).
- PM ratified hurdle = QQQ → use **conservative case (QQQ)** as the single hurdle in P2-P3.

### 4. BP-utilization argument is correct at COMBINED level
SPEC-104 sleeve caps measured against combined BP (or per-broker BP). Combined BP utilization is 13.7%, vs 55.8% headroom — vast BP slack. A pure BP-utilization cap will not bite a BCD stack until cash is depleted, supporting framing memo §0 thesis.

### 5. Concentration risk to flag (Q081 out of scope, but noted)
E-Trade SPY $310k + QQQ $137k = $447k beta. ~37% of total NLV is beta-deployed via E-Trade alone. Worth a separate sleeve-level review at some point.

---

## Implications for P1-P5

- **Use QQQ rolling return as hurdle** per PM ratification — even though some
  cash would actually displace BOXX (lower hurdle). This is conservative.
- **Combined-account treatment in P1**: model "available cash for BCD debit"
  as Schwab liquid + E-Trade liquid combined, not per-broker. PM can move
  cash between brokers; the constraint is total liquid.
- **Cap design (if Conclusion 1 wins)**: a `cash_budget_pct` cap on
  debit-strategy footprint should be set against **combined NLV** (not
  per-broker), with X% chosen via P3 hurdle-vs-BCD analysis.
- **Historical reconstruction caveat**: today's snapshot is one
  point-in-time. Daily snapshot history (data/daily_snapshot.jsonl) has NLV
  but not the cash/beta breakdown. P1 will need either PM to confirm the
  profile is stable, or accept this single anchor as representative.

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
