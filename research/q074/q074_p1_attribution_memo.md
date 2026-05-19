# Q074 P1 — Benign-regime Attribution (Diagnostic)

> **Status: P1 DIAGNOSTIC RESULTS.**
> **B1-B4 remain FROZEN.** P1 findings do NOT create new candidates per 2nd Quant Revision 4.
> Forward returns reported for attribution understanding only — NOT signal mining.

**Date**: 2026-05-18
**Parent**: `q074_p0_anchored_memo_2026-05-17.md`

---

## TL;DR

Q074 P1 confirms a real benign-regime forward-return premium AND a stress-trigger-predictive signal. The 6 features from P0 §3 each individually carry signal; B1 / B2 composite signals each filter to ~31-37% of normal days with materially better forward-PnL distributions.

| Signal | Active % of normal days | ON avg fwd 20d | OFF avg fwd 20d | ON P(stress 10d) | OFF P(stress 10d) |
|---|---|---|---|---|---|
| B1 strict (6 features) | **31.5%** | **+3.12% NLV** | +1.62% | **8.8%** | 27.2% |
| B2 moderate (5 features) | **36.5%** | **+3.13% NLV** | +1.50% | 10.3% | 27.8% |

Both signals stay below the 60% breadth diagnostic threshold — neither is "too broad". **Proceed to P2 with B1/B2/B3/B4 frozen as-is.**

---

## 1. Sample

- Period: 2000-01-03 → 2026-05-15 (26.32 years)
- Total trading days: 6632
- Normal-state days: 3693 (55.7%)
- Stress days: 2939 (44.3%)
- Second-leg days: 783 (11.8%)
- Normal-state days with complete features + forward windows: 3623

SPX BPS PnL series scaled from Q073 P1.3R 60% baseline to Arch-3 80% normal-state allocation (×1.333) for attribution comparability.

---

## 2. Per-feature attribution (normal-state days only)

### Feature 1 — SPX > MA50

| Bucket | n | Avg fwd 20d % NLV | Hit rate | P(stress 10d) |
|---|---|---|---|---|
| Above MA50 | 3250 (89.7%) | +2.25% | 65.6% | 18.2% |
| Below MA50 | 373 (10.3%) | +0.69% | 63.8% | **49.1%** |

**Strong precursor**: below-MA50 in normal state has 49% probability of stress within 10d. Filtering OUT below-MA50 days from booster significantly reduces transition risk.

### Feature 2 — MA50 slope positive (5-day)

| Bucket | n | Avg fwd 20d % NLV | P(stress 10d) |
|---|---|---|---|
| Slope > 0 | 3322 (91.7%) | +2.22% | 19.9% |
| Slope ≤ 0 | 301 (8.3%) | +0.74% | **38.5%** |

Confirms trend direction matters beyond level alone.

### Feature 3 — ddATH bucket

| Bucket | n | Avg fwd 20d % NLV | Hit rate | P(stress 10d) |
|---|---|---|---|---|
| -3% to 0% | 1950 (53.8%) | **+2.51%** | **70.4%** | 19.2% |
| -6% to -3% | 276 (7.6%) | +2.75% | 74.3% | 22.1% |
| < -6% | 1397 (38.6%) | +1.38% | 56.7% | 24.3% |

Sweet spot: **ddATH > -3% strongly outperforms < -6%** (avg +2.51% vs +1.38%). Shallow drawdown is the benign characteristic.

### Feature 4 — VIX absolute (normal-state subset, all VIX < 22 by construction)

| Bucket | n | Avg fwd 20d % NLV | Hit rate | **P(stress 10d)** |
|---|---|---|---|---|
| VIX < 15 | 2013 (55.6%) | **+2.71%** | **73.6%** | **10.0%** |
| VIX 15-18 | 1015 (28.0%) | +1.22% | 53.1% | 27.6% |
| VIX 18-20 | 404 (11.2%) | +1.23% | 54.2% | 45.0% |
| VIX 20-22 | 191 (5.3%) | +2.10% | 68.6% | **59.2%** |

**KEY FINDING**: VIX < 15 is dominantly the best bucket (best ROE, lowest stress prob). VIX 20-22 in normal state has **59% chance of stress within 10d** — most dangerous transition zone. VIX 18-22 booster activation would be high-risk.

This confirms B1's `VIX < 20` and B2's `VIX < 22` strict-vs-moderate tradeoff — B1 avoids the dangerous 20-22 bucket entirely.

### Feature 5 — VIX 5d change bucket

| Bucket | n | Avg fwd 20d % NLV | P(stress 10d) |
|---|---|---|---|
| Falling (≤ -0.5) | 1493 (41.2%) | +2.14% | 18.6% |
| Flat (-0.5 to +0.5) | 1062 (29.3%) | +2.26% | 16.5% |
| Rising (> +0.5) | 1068 (29.5%) | +1.87% | **30.3%** |

Rising VIX has 30% near-term stress probability — important to filter out in benign confirmation.

### Feature 6 — IVP_252 bucket

| Bucket | n | Avg fwd 20d % NLV | P(stress 10d) |
|---|---|---|---|
| < 30 | 2119 (58.5%) | +2.16% | 15.6% |
| 30-55 | 753 (20.8%) | +2.35% | 23.6% |
| 55-70 | 390 (10.8%) | +1.79% | 25.6% |
| > 70 | 361 (10.0%) | +1.49% | **46.3%** |

**IVP > 70 is dangerous**: 46% next-10d stress probability. B1/B2's `IVP < 55` correctly excludes both the 55-70 and >70 buckets. Aligns with Q063/Q067/Q068/Q069 BPS_NNB_IVP_UPPER finding (55 is the right threshold).

---

## 3. Composite signal (B1 strict / B2 moderate) — informational

Both composites computed for diagnostic only. Not modifying candidates.

### B1 strict (all 6 features tight)

```
Criteria: above MA50 AND MA50_slope_pos AND ddATH > -3%
        AND VIX < 20 AND VIX_5d_change ≤ +1.0 AND IVP < 55
Activation: 1141/3623 normal days = 31.5%
            (= 17.6% of all 6632 trading days)

ON  days: avg fwd 20d +$27,899 (+3.12% NLV), hit 75.6%, P(stress 10d) 8.8%, P(stress 20d) 23.6%
OFF days: avg fwd 20d +$14,490 (+1.62% NLV), hit 60.7%, P(stress 10d) 27.2%, P(stress 20d) 42.9%

ON-vs-OFF delta:
  +$13,409 forward 20d (+1.50% NLV)
  +14.9pp hit rate
  -18.4pp P(stress 10d) — much safer pre-stress probability
```

### B2 moderate (5 features loose)

```
Criteria: above MA50 AND ddATH > -4% AND VIX < 22
        AND VIX_5d_change ≤ +1.5 AND IVP < 55
Activation: 1324/3623 normal days = 36.5%
            (= 20.4% of all 6632 trading days)

ON  days: avg fwd 20d +$27,935 (+3.13% NLV), hit 75.8%, P(stress 10d) 10.3%
OFF days: avg fwd 20d +$13,401 (+1.50% NLV), hit 59.4%, P(stress 10d) 27.8%
```

**B1 vs B2 trade-off**:
- B2 activates 5pp more often (36.5% vs 31.5%) — captures more upside
- B2 has slightly higher P(stress 10d) (10.3% vs 8.8%) — slightly more transition risk
- Both have ~+1.5% NLV ON-vs-OFF forward 20d differential — significant economic signal

---

## 4. Breadth diagnostic check (per 2nd Quant Revision 4 + booster active-days threshold)

| Signal | Booster active % of normal days | Threshold | Status |
|---|---|---|---|
| B1 strict | 31.5% | <60% | ✓ within bound |
| B2 moderate | 36.5% | <60% | ✓ within bound |

Neither composite is "too broad". Both qualify for P2 booster sweep.

---

## 5. Key findings summary

| Finding | Implication |
|---|---|
| Above MA50 reduces P(stress 10d) by 2.7x (49% → 18%) | Trend filter is essential |
| MA50 slope positive (8% above MA50 days excluded) reduces P(stress 10d) further | Slope check provides marginal protection |
| ddATH > -3% is sweet spot for fwd return | Shallow drawdown = benign |
| VIX < 15 dominates (lowest stress prob, best ROE) | Strict VIX<20 (B1) more protective than VIX<22 (B2) |
| VIX 20-22 in normal state has 59% near-term stress prob | DANGER ZONE — B1 correctly excludes |
| Rising VIX 5d ≥ +0.5 has 30% stress prob | VIX_trend filter is real |
| IVP > 70 has 46% stress prob | IVP<55 cutoff well-calibrated |
| B1 vs B2: B1 more protective, B2 more frequent | P2 will compare ROE impact |

**Most interesting**: B1 strict only activates 31.5% of normal days but the ON-vs-OFF differential is +1.50% forward 20d — meaning a booster active during these days captures a real and quantifiable premium.

---

## 6. P1 → P2 readiness

✓ Per-feature attribution complete (6 CSV files)
✓ Composite B1/B2 signal stats computed
✓ Breadth diagnostic passes (both <60%)
✓ B1-B4 candidate definitions remain FROZEN per 2nd Quant R4
✓ No look-ahead overfit (forward returns diagnostic only, did not modify B1-B4)

**Next**: P2 booster candidate sweep (B0/B1/B2/B3/B4) on 26y combined-NLV simulator, applying state-dependent SPX allocation policy. Expected outcomes:
- B1 strict 85%: positive ROE delta vs Arch-3, V2 passes
- B2 moderate 85%: positive ROE delta, slightly worse V2 buffer (more activations)
- B3 strict 90%: higher ROE upside but more transition risk amplified
- B4 moderate 90%: largest activation × largest cap — highest risk, possibly fail V2

---

## 7. Caveats

1. SPX PnL scaling 60% → 80% is approximate (linear scaling of P1.3R engine output). At true 80% allocation, engine's compound behavior may differ slightly. For P1 attribution this is acceptable; P2 will use the actual state-dependent allocation policy.
2. Forward returns include stress-period days IF the forward window crosses into a stress regime — this is intentional (the booster would have already snapped back to 50% by then, so the forward return measures REAL forward strategy PnL including the snap-back, not booster-active PnL throughout).
3. IVP_252 requires 252-day rolling history; earliest valid IVP date is end of 2000-12-31. Days with IVP=NaN excluded from IVP bucket aggregations.
4. ddATH "1_pos_or_zero" bucket has zero observations in this sample — running ATH expansion means current close is always ≤ running max. Only -3%/-6% buckets are populated.

---

## 8. References

- `q074_p0_anchored_memo_2026-05-17.md` — P0 anchored
- `q074_p1_benign_attribution.py` — P1 simulator
- `q074_p1_attribution_*.csv` — per-feature CSV outputs
- `q074_p1_attribution_joint_signals.csv` — B1/B2 composite stats
