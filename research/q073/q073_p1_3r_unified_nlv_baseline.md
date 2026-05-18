# Q073 P1.3R — Unified-NLV Combined Baseline (DECISION-GRADE)

> **Status: P1.3R DECISION-GRADE BASELINE.**
> Supersedes P1.3 inflated estimate.
> This baseline anchors all downstream P1.4 / P2 / P3 / P5 work.

**Date**: 2026-05-17
**Parent**: `q073_p0_anchored_memo_2026-05-17.md` + `q073_p1_rules_2026-05-17.md`
**Predecessors**: P1.1 SPX BPS 26y baseline, P1.2 V3-A marginal attribution
**Supersedes**: P1.3 raw output (methodology issue documented below)

---

## TL;DR (PM-facing reframe)

```
Before P1.3R (P1.2 additive estimate):
  Combined ann ROE ≈ 10.3%
  Stretch 20% target seemed plausibly distant

After P1.3R (unified-NLV simulation):
  Combined ann ROE (geometric) = 7.50%
  Floor 8% NOT YET achieved (gap +0.5pp)
  V2 worst-20d MARGINALLY FAILS (-12.46% vs -11% limit)
```

**Q073 focus update**:

> The architecture is close to but not through the 8% floor, and it marginally fails the worst-20d V2 veto due to a 2000 DotCom window. The next research question is no longer "how close to stretch 20%?" — it is: **how do we add ~+0.5pp ROE while pulling worst-20d back from -12.46% to ≤ -11%?**

Major modern crises (GFC / COVID / Bear 2022) all show **positive PnL** on unified-NLV basis — diversification is working post-2007. The single largest residual risk is **2000-2002 DotCom**, when the architecture had only SPX BPS (no HV Ladder, no Q042).

---

## 1. Why P1.3 was inflated (methodology issue)

### 1.1 Bug found

P1.3 (raw) was a naive sum of each engine's daily PnL stream:

```python
combined.total_pnl = spx_daily + hv_daily + q42a_daily
```

Each engine ran on **full $894k NLV as account_size**. Because engines size positions as a percentage of equity (and equity compounds internally), summing 3 such streams effectively models:

```
SPX BPS  on $894k full ──┐
HV Ladder on $894k full ──┼─→ sum
Q042 Sleeve A on its base ─┘
```

Equivalent to running 3 × $894k accounts and adding outputs. This is **NOT production reality** — in production, all strategies share the same $894k pool.

### 1.2 Resulting overstate (P1.3 raw)

| Metric | P1.3 raw (wrong) | P1.3R unified (correct) | Δ |
|---|---|---|---|
| Final equity (from $894k) | $8.65M | $6.00M | -$2.65M |
| Ann ROE (geometric) | 9.01% | **7.50%** | -1.51pp |
| MaxDD | -21.17% | -14.03% | +7.14pp |
| Worst 20d (point-in-time) | -19.20% | -12.46% | +6.74pp |
| Sharpe | 2.10 | 1.66 | -0.44 |

All P1.3 numbers were inflated. PM correctly flagged this before P1.4.

---

## 2. Unified-NLV Allocations (P1.3R simulator)

Strategy allocations chosen to reflect actual production sizing:

| Strategy | % NLV | $ Budget | Rationale |
|---|---|---|---|
| **SPX BPS Main** | 60% | $536,400 | Core income engine peak BP utilization (per Q072 P4 / SPEC-103) |
| **HV Ladder /ES** | 5% | $44,700 | Opportunistic, occupancy 21% (peak SPAN modest, per Q071 P5) |
| **Q042 Sleeve A** | 10% | $89,400 | SPEC-094 sleeve cap |
| **Cash baseline (BOXX)** | 25% | $223,500 | Idle reserve earning ~4.3% (per PM 2026-05-17) |
| **Sum** | 100% | $894,000 | Full allocation |

Each engine ran on its allocated budget as `account_size`. Daily PnL streams summed to combined portfolio path on shared $894k base.

---

## 3. Combined Portfolio Metrics (DECISION-GRADE)

```
Period:               2000-01-01 → 2026-05-17  (26.32 years)
Combined NLV start:   $894,000
Combined NLV end:     $5,996,189   (6.7x growth)
Total PnL:            $5,102,189

ROE:
  Geometric (true):   7.50%
  Arithmetic:         21.69%   (reflects engine internal compounding)

Risk-adjusted:
  Sharpe (daily ann): 1.66
  Sortino:            1.45

P0 Veto check (point-in-time):
  V1 MaxDD     ≤ 28%   :  -14.03%        PASS (14pp buffer)
  V2 worst-20d ≤ 11%   :  -12.46%        FAIL ⚠️  (1.46pp over, window 2000-04-14)
  V3 worst-63d ≤ 17%   :  -12.46%        PASS (4.54pp buffer, same window)
  V4 BP / SPAN cap     :  not modeled here (per SPEC-103 governance)
  V5 stress paths      :  see §5 crisis windows
  V6 bootstrap sig     :  not run (per Rule, V6/V7 are promotion-level)
  V7 walk-forward      :  not run (no learned allocator)
```

**Status**: floor 8% **NOT yet achieved**. V2 **marginally fails**. V1/V3 pass with buffer.

---

## 4. Strategy Contribution Bridge (per Rule 6, combined-NLV)

| Source | Allocation | Total PnL (26y) | Ann arith % | Geometric impact |
|---|---|---|---|---|
| **SPX BPS (incl V3-A)** | 60% | $4.50M | 19.14% | Dominant driver |
| **HV Ladder /ES** | 5% | $173k | 0.74% | Small positive |
| **Q042 Sleeve A** | 10% | $172k | 0.73% | Small positive, low correlation |
| **Cash baseline (BOXX 4.3%)** | 25% | $253k | 1.07% | Stable filler |
| **Sum (arithmetic)** | 100% | $5.10M | **21.69%** | — |
| **Combined geometric** | — | — | — | **7.50%** |

### Why geometric << arithmetic (14pp gap)

Each engine internally compounds: as equity grows, trade sizing grows, dollar PnL inflates. The 21.69% arithmetic is the *cumulative dollar PnL divided by initial NLV × years*. The 7.50% geometric is the *TWR* of the combined path. Geometric is the PM-experience number.

### Cross-strategy daily PnL correlation

| | SPX | HV | Q42A |
|---|---|---|---|
| SPX | 1.00 | 0.28 | 0.02 |
| HV | 0.28 | 1.00 | 0.00 |
| Q42A | 0.02 | 0.00 | 1.00 |

**Diversification is real**. SPX×HV mild positive (both option sellers), SPX×Q42A and HV×Q42A near zero (Q042 is convex / counter-trend).

---

## 5. Crisis Window Behavior (point-in-time, unified-NLV)

| Window | days | Total PnL | % then-equity | Worst DD in window |
|---|---|---|---|---|
| **DotCom 2000-2002** (3y) | 671 | +$280k | +31.6% | **-14.03%** ⚠️ |
| GFC 2008 (full) | 377 | +$7k | +0.4% | -4.2% |
| GFC 2008 acute | 167 | -$53k | -2.7% | -4.1% |
| Flash 2010 | 69 | +$49k | +2.3% | -1.1% |
| Aug 2011 (debt ceiling) | 76 | -$17k | -0.8% | -4.0% |
| Vol 2015 Aug | 43 | +$7k | +0.2% | -3.0% |
| Vol 2018 Q4 | 63 | -$20k | -0.5% | -0.9% |
| **COVID 2020** | 72 | +$15k | +0.3% | -1.1% |
| **Bear 2022** | 251 | -$4k | -0.1% | -2.2% |

### Key findings

1. **Major modern crises (GFC / COVID / Bear 2022) all positive or near-zero**. Diversification + V3-A permission alpha + Q042 convex overlay 都在 post-2007 起效。
2. **DotCom 2000-2002 is the architecture's single largest weakness** — combined -14% MaxDD entirely within this window. At that time, only SPX BPS was running (HV Ladder needed 2009+ live VIX data, Q042 needed ddATH ≤ -4% triggers).
3. **V2 worst-20d -12.46% occurs in 2000-04-14 window** — same DotCom early-bust period. This is the binding V2 violation.

---

## 6. P1.3R-anchored Q073 Updated Objectives

### Originally (P0):
- Stretch 20%, Floor 8%
- Risk vetoes V1-V7

### Now (post-P1.3R reality):
- **Floor 8% remains target but is NOT YET achieved (gap +0.5pp from 7.50%)**
- **Stretch 20% is functionally aspirational** — even hypothetical "all-in" allocation cannot reach 20% based on observed strategy economics
- **V2 marginal fail requires remediation** — any architecture move that worsens V2 is veto-blocked

### Refocused Q073 task:

> **Find architecture changes that:**
> 1. **Add ≥ +0.5pp combined ann ROE** (7.50% → ≥ 8.00%)
> 2. **Pull worst-20d from -12.46% back to ≥ -11%** (V2 PASS)
> 3. **Preserve V1 MaxDD ≤ 28% pass** (currently has 14pp buffer)
> 4. **Don't break V3 / V5 stress / V6 sig / V7 walk-forward**

---

## 7. Initial P2A Directions (per PM 2026-05-17)

Based on P1.3R bridge, the highest-leverage levers for ROE improvement:

| Lever | Hypothesis | Expected Δ ROE | Risk to V2 |
|---|---|---|---|
| **A. SPX BPS allocation 60% → 65% / 70%** | SPX BPS 19% / $1 → +0.5-1pp combined | +0.5 to +1.0pp | Likely worsens V2 (DotCom 2000 was SPX-only) |
| **B. Q042 Sleeve A 10% → 12.5% / 15%** | Q042 has low SPX correlation, adds without correlation-induced tail | +0.2-0.4pp | Likely V2 NEUTRAL (Q042 didn't exist in 2000 anyway) |
| **C. Cash 25% → 20% / 15%** | Free capital for strategy deployment, sacrifices 4.3% baseline yield for higher-ROE strategies | Mixed — depends on redirected target | Depends |
| **D. HV Ladder 5% → 7.5% / 10%** | Low correlation to SPX, but small total contribution (0.74% on 5%) | +0.4-0.7pp | V2 unlikely affected (HV Ladder didn't exist in 2000) |

### Worst-20d (V2) remediation candidates

Critical observation: **V2 fail is from 2000-04-14 (DotCom early bust)**. At that time only SPX BPS was active. Therefore:
- **Reducing SPX BPS allocation** OR
- **Adding pre-2009 hedge** (only conceptual — no real strategy available pre-2009 due to data gaps)

likely improves V2. But reducing SPX hurts ROE. P2A must explore this tradeoff explicitly.

---

## 8. P1.4 Refocused Scope

P1.4 (idle BP + friction) must now answer two specific questions:

### Q1 — Capital deployment gap (the +0.5pp ROE source)

```
Current avg BP utilization across strategies = ?
What % of trading days had SPX BPS / HV Ladder / Q042 simultaneously idle?
Cash 25% is currently sized — is actual idle BP higher than 25%?
Could allocation rebalance recapture some idle without breaching V2?
```

### Q2 — V2 worst-20d remediation (the V2 fail source)

```
Specific to 2000-04-14 window: which strategy contributed how much to that 20d?
Was V2 fail driven by SPX BPS losses or sizing?
Would lower SPX allocation in similar future window improve V2?
Is there a regime indicator that flags DotCom-like windows?
```

### Q3 — Friction adjustment

```
SPX BPS has live data (recent trades) — estimate friction haircut
HV Ladder: live=0 → N/A explicit
Q042: paper mode — N/A or proxy from SPX BPS friction rate?
Cash BOXX yield: PM verify trailing 12m actual
```

---

## 9. Caveats & Open Methodology Questions

1. **Strategy allocations 60/5/10/25 are ESTIMATES** based on Q072 + SPEC-094 + Q071 P5 sizing intent. Real production allocation may differ. P2A will sensitivity-test these specific %.
2. **Engine compounding within allocated budget still happens** — geometric 7.50% reflects engine's internal compounding within each strategy's allocation. This is a fair model of "rebalance allocations annually as account grows".
3. **Q042 Sleeve A rescale** used `account_pct × Q42A_BUDGET` (= 89.4k constant). Real Q042 sleeve compounds — slight understatement, but close.
4. **Cash daily yield $38/day = $223.5k × 4.3% / 252** is CONSTANT — does not compound. Reality: cash compounds too, slight understate over 26y.
5. **HV Ladder pre-2009** had no data; allocation effectively idle pre-2009. Same for Q042 pre-2007.
6. **V3-A Aftermath included inside SPX BPS engine** (per Rule 1, V3-A is permission module not standalone). Its +0.19pp contribution shows up inside SPX BPS 19.14% arithmetic.

---

## 10. References

- `q073_p0_anchored_memo_2026-05-17.md` — P0 objectives
- `q073_p1_rules_2026-05-17.md` — 7 binding rules
- `q073_p1_2_marginal_attribution.md` — V3-A marginal attribution
- `q073_p1_3R_unified_nlv.py` — simulator code
- `q073_p1_3R_unified_daily_pnl.csv` — daily PnL series (~$6M cum on $894k)
- `q073_p1_3R_unified_correlation.csv` — cross-strategy correlation
- `q073_p1_3R_unified_crisis.csv` — crisis window outcomes
- `task/q073_p0_2nd_quant_review_2026-05-17_Review.md` — 2nd Quant framing audit

---

**Next**: P1.4 idle BP + friction + V2 remediation forensic, then P2A allocation sweep.
