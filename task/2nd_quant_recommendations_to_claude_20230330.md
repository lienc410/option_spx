# 2nd Quant Strategic Review — Next Phase Recommendations

**Date:** 2026-03-30  
**From:** 2nd Quant Reviewer  
**To:** Claude Quant Researcher  

---

## Executive Summary

The system has successfully evolved into a **structured short-vol engine with regime filters and basic portfolio constraints**.

However, the current architecture still lacks **true risk-awareness in dynamic environments**. The largest remaining risks are not in entry selection, but in:

1. In-position risk under rapid volatility transitions  
2. Lack of probabilistic regime modeling (vol persistence)  
3. Exposure control based on count rather than risk  

---

## 1. Priority #1 — VIX Acceleration Risk (CRITICAL)

### Problem

System does NOT handle:

> Fast VIX expansion (e.g., 25 → 50) while positions are already open

This is the most dangerous region:
- short gamma + short vega exposure
- exit rules lag
- losses accelerate non-linearly

---

### Key Insight

risk ≠ high VIX  
risk = fast change in VIX  

---

### Required Upgrade

Define:

    vix_accel = (VIX_today - VIX_3d_ago) / VIX_3d_ago

Trigger:

    if vix_accel > threshold:
        reduce exposure (NOT full exit)

---

### Design

- apply in-position
- prefer scaling over binary exit

---

## 2. Priority #2 — Vol Persistence Model

### Problem

Current:

    spell_age → reactive control

Missing:

    entry-time risk assessment

---

### Required

Define:

    prob_sticky = f(VIX level, slope, term structure)

Use for:

    position sizing

Example:

    size = base * (1 - prob_sticky)

---

## 3. Priority #3 — Exposure-Based Risk Control

### Problem

Current:

    max_short_gamma_positions = 3

But:

    count ≠ risk

---

### Required

Define:

    total_risk = Σ (gamma_weighted exposure)

Constraint:

    total_risk < threshold

---

### Proxy (if needed)

- delta distance
- premium / width

---

## 4. Trend Signal Clarification

MA50 is valid as filter.

But:

    entry timing still degrades at extreme gaps

Recommendation:

    monitor, not redesign

---

## 5. System Status

Current:

    Version 2.3 (Protected short-vol)

Target:

    Version 3.0 (Risk-aware adaptive)

---

## Final Recommendation

If only one change:

    implement VIX acceleration module

---

## Closing

System already proves:

    positive expectancy

Next step:

    survive adverse regimes
