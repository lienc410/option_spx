# Q078 P1b / G2.5 — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-28
**Source**: `task/q078_p1b_g2_5_2nd_quant_review_packet_2026-05-28.md`
**Verdict**: **PASS TO P2** — but only after fixing selection-bias methodology

---

## Final verdict statement

> Q078 P1b passes as an attribution and sizing stage. It fixes the P1a BCD placeholder and sizing issues, confirms that S3 is the sustainable mixed-strategy ladder sizing under the 5% NLV worst-trade gate, and reinforces that Q078 is a strategy-agnostic selector-gated execution ladder rather than a BPS-only ladder. However, current PnL magnitudes are not decision-grade because survivor-trade bootstrap extrapolates filtered engine-quality PnL to all selector PASS days. P2 may proceed only after correcting this selection bias via shadow PnL for all selector-PASS entries, while preserving all real production gates separately. V1b and V3 should both advance, with V1b as the likely production candidate and V3 as the higher-burden benchmark.

---

## 3 decisions — 2nd Quant answers

| Decision | Answer |
|---|---|
| **D1 selection-bias** | **REVISE D1(a) — shadow PnL YES, but distinguish sampling filters vs production gates**. Two-layer P2: Layer 1 unbiased shadow PnL for all selector PASS; Layer 2 apply real production gates separately. **Reject D1(c) disclaimer-only**. |
| **D2 framing** | **Confirm strategy-agnostic ladder** (not BPS-only, not credit-only). PM-facing language MUST change from "weekly BPS ladder" to "selector-gated SPX execution ladder". |
| **D3 sizing** | **Confirm S3 (3 contracts / 7.5% BP). Keep 5% NLV gate.** Do NOT loosen to 6% to keep S2. Note: PM's separate BPS-only 4-contract entries may remain acceptable; the ladder (mixed-strategy) is S3. |

---

## Critical methodology refinement (D1 detail)

**The distinction 2nd Quant added**:

```
SHADOW VALUATION ENGINE (Layer 1):
  estimates what trade WOULD have done if entered
  → disable backtest sampling filters
  → generate PnL for all selector PASS days

PRODUCTION ELIGIBILITY GATES (Layer 2):
  decide whether ladder is ALLOWED to enter
  → preserve real live constraints
  → concurrency caps, regime stops, HV spell gates, risk constraints
```

**If filter is "backtest sampling"**: disable for shadow PnL (no effect on production behavior; just affects whether engine recorded a trade).

**If filter is "production gate"**: PRESERVE — disabling would silently turn Q078 into a selector override and violate framing.

Quant must explicitly classify each engine filter before P2:
- HV spell trade count limit → likely production gate (preserve)
- Concurrency limit → production gate (preserve)
- Regime stops → production gate (preserve)
- Cluster gate → backtest sampling? need to check
- ATR trend filter → check
- BCD filter → check

If after classification all filters are production gates → Layer 1 and Layer 2 outputs are identical. Document explicitly.

---

## Updated framing language (D2)

| Old (rejected) | New (mandatory) |
|---|---|
| "weekly BPS ladder" | "selector-gated SPX execution ladder" |
| "BPS sizing study" | "mixed-strategy ladder sizing study" |
| "10% BP BPS target" | "7.5% BP mixed-strategy target" |
| "PM's weekly entries" | "PM's weekly selector-PASS execution slot" |

All future Q078 memos, packets, SPEC drafts MUST use new language. PM mental model update: ladder runs whatever selector approves — BCD (LOW_VOL), IC (NORMAL/HV), BPS (NORMAL/HV), BCS (HV) — NOT BPS only.

---

## P2 design requirements (2nd Quant prescribed)

```
1. Correct selection bias (D1 revised):
   Generate shadow PnL for ALL selector-PASS ladder entries
   Separately identify which entries would fail real production gates
   Report two-layer view

2. Keep strategy-agnostic ladder (D2):
   Use selector-provided: strategy type, DTE, BP target, exit logic

3. Use S3 sizing (D3):
   3 contracts / approx 7.5% BP for mixed-strategy ladder
   Match PM's separate BPS-only behavior remains 4 contracts (acceptable)

4. Carry V1b AND V3:
   V1b weekly catch-up — production candidate (PM bandwidth fit)
   V3 daily-cluster — upper-bound benchmark (higher attention burden)

5. Portfolio-level metrics:
   Net ann ROE (+ ΔROE vs Baseline B)
   MaxDD / W20d / W63d / Sharpe
   Expiry concentration + effective expiry count
   Action days/year, max actions/week
   Capital competition with Q042
   Telegram alert load (operational realism)

6. Crisis and walk-forward:
   5 named crisis windows
   H1 (2000-2012) / H2 (2013-2026)
   Bootstrap (block=250, 20 seeds)

7. Hard gates (REJECT if any fails):
   V1 (MaxDD ≥ -28%)
   V2 (W20d ≥ -11%)
   V3 (W63d ≥ -17%)
   W20d degradation ≤ +0.25pp vs Baseline B
   W63d degradation ≤ +0.25pp vs Baseline B
   Worst single trade ≤ 5% NLV
   No new crisis-window failure
```

---

## Baseline B caveat (2nd Quant added)

> "Baseline B is the concentration-risk comparator, not a perfect reconstruction of PM behavior."

P2 should show:
```
Baseline A — cycle-based entry (every 21d)
Baseline B — cluster/ad-hoc (primary canonical)
Baseline C — zero / cash (sanity floor)
```

Avoid overclaiming "ladder vs PM actual behavior".

---

## What's NOT decision-grade yet (until D1 implemented)

P1b conclusion language should be SOFTENED to:
```
1. S3 is the max safe sizing under 5% worst-trade gate ✓ DECISION-GRADE
2. Strategy-agnostic ladder is the correct framing ✓ DECISION-GRADE
3. Ladder improves expiry diversification ✓ DECISION-GRADE
4. PnL magnitude (3-4x baseline) ⚠ UPPER BOUND ONLY — pending P2 D1 correction
```

P2 must resolve #4 before any SPEC-level PROMOTE/REJECT decision.

---

## 2nd Quant Sign-off

- [x] G2.5 PASS to P2 conditional on D1 correction
- [x] D1: shadow PnL methodology + filter classification required before P2 starts
- [x] D2: strategy-agnostic ladder confirmed, PM language update mandatory
- [x] D3: S3 confirmed, 5% NLV gate preserved
- [x] V1b + V3 both advance (V1b production, V3 benchmark)
- [x] P2 hard gates locked
- [x] Baseline B framing caveat noted

→ Quant proceeds to: (1) classify engine filters as sampling vs production, (2) implement shadow PnL Layer 1, (3) preserve production gates as Layer 2, (4) re-run sizing sweep with unbiased Layer 1 data, (5) advance to P2 portfolio integration.
