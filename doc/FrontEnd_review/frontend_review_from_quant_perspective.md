# Frontend Review from Quant Perspective

**Date:** 2026-03-30  
**Reviewer:** 2nd Quant  

---

## Executive Summary

The current frontend has evolved into a **functional research + decision support console**.  
It is well-structured and aligned with the strategy framework.

However, it remains **research-oriented rather than execution-oriented**.

> Current state: supports understanding  
> Missing: supports fast decision-making under risk  

Overall Rating: **B+**

---

## Core Evaluation Framework (Quant Trader View)

A strong trading frontend must answer:

1. Should I trade today?
2. Where is the current risk?
3. How will this fail?

Current system:
- Q1: mostly covered  
- Q2: partially covered  
- Q3: largely missing  

---

## Page-by-Page Review

---

## 1. Dashboard

### Strengths
- Signal Strip aligns with decision factors (VIX / IV / Trend)
- Recommendation Card is correctly centered
- Intraday Alert Bar is useful for monitoring

---

### Issues

#### 1. Missing “Change Detection”
No clear view of:
- what changed vs yesterday
- signal transitions
- recommendation shifts

---

#### 2. Recommendation Card is descriptive, not decisive
Needs stronger structure:
- Do / Don’t Do
- Why now
- Failure mode
- What to watch

---

#### 3. Open Position Panel is too shallow
Missing:
- PnL
- holding duration
- risk state
- proximity to exit

---

### Recommendations

- Add **What Changed Since Yesterday**
- Restructure Recommendation Card into decision format
- Add **Position Health / Risk State**

---

## 2. Matrix

### Strengths
- Correct abstraction (Regime × IV × Trend)
- Trade drill-down is valuable
- Time horizon toggle (3Y / 10Y / All) is appropriate

---

### Issues

#### 1. No confidence layer
WR alone is misleading without:
- sample size
- regime stability
- tail risk

---

#### 2. No risk labeling
Cells should distinguish:
- stable
- fragile
- avoid

---

### Recommendations

- Add **confidence / quality labels**
- Add **cell summary before trade list**
- Improve override transparency

---

## 3. Backtest

### Strengths
- Full research loop (metrics + equity + signals)
- Experiment runner is powerful
- Grid search is well implemented

---

### Issues

#### 1. Too researcher-oriented
Missing:
- decision impact summary
- what actually improved

---

#### 2. Encourages parameter search
Risk of overfitting without guardrails

---

#### 3. Weak failure attribution
Missing:
- which regimes lose money
- which strategies fail
- where tail comes from

---

### Recommendations

- Add **Experiment Verdict**
- Add **research guardrails**
- Add **PnL attribution / failure mode analysis**

---

## 4. Margin

### Strengths
- Correct to separate BP logic
- Good documentation structure

---

### Issues

#### 1. Static, not actionable
Does not answer:
- current BP usage
- risk buffer
- impact of new trade

---

#### 2. No live account state
Feels like reference, not tool

---

### Recommendations

- Add **Current BP Snapshot**
- Add **What-if trade impact**
- Integrate with Dashboard decisions

---

## System-Level Assessment

### Strengths
- Clean architecture
- Strong alignment with strategy logic
- Full research-to-decision pipeline
- Suitable for single-user quant workflow

---

### Weaknesses
- Weak “delta awareness” (change over time)
- Weak position monitoring
- Limited failure mode visibility

---

## Priority Improvements (Top 3)

### 1. What Changed (Highest ROI)
Add daily delta view:
- signal transitions
- recommendation changes
- risk changes

---

### 2. Position Health Module
Add:
- PnL
- duration
- risk status
- exit proximity

---

### 3. Failure Mode Visibility
Add:
- current risk regime similarity
- stress indicators
- scenario awareness

---

## Final Positioning

This system should be viewed as:

> Strategy Decision Console for a Single-Manager Volatility System

---

## Final Conclusion

The frontend is:
- Already **functional and usable**
- Strong in **research support**
- Not yet optimized for **real-time trading decisions**

Next evolution:

> From “showing the system”  
> To “guiding the trader under uncertainty”
