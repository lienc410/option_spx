# Q075 Framing — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-19
**Source**: `task/q075_framing_2nd_quant_review_packet_2026-05-19.md`
**Verdict**: **PASS WITH MINOR REVISIONS** — proceed to P0 anchored memo after applying 6 revisions

---

## Final verdict statement

> Q075 framing is directionally correct and ready for P0 after revisions. It correctly treats IVP-blocked normal-state deployment as Layer-3 replacement research, preserves Layer-1 and Layer-2, prohibits uncapped short-vol, and makes cash/BOXX a valid endpoint. Before P0, refine the blocked-day sample definition, separate pure IVP/vol-blocked days from broader failed-benign days, add a trend-deteriorated Type D, adjust Q075-specific success thresholds, and clarify short-DTE BPS gamma risk.

---

## 6 questions — 2nd Quant answers

| Q | Verdict |
|---|---|
| Q1 Layer-3 framing | **PASS** — concept is correct |
| Q2 sample definition | **REVISE** — split pure IVP/vol-blocked vs other-condition-failed days |
| Q3 attribution-first | **PASS** — correct sequence |
| Q4 candidate universe | **PASS w/ wording fix** — add C0/do-nothing clarity; fix short-DTE gamma wording |
| Q5 calendar/diagonal | **PASS** — seed-only treatment is right |
| Q6 success criteria | **REVISE** — lower ROE bar for narrow subset, tighten tail degradation tolerance |

---

## 6 required revisions before P0

### Revision 1 — Sample split (Q2)
Split blocked-day sample into two:

**Primary sample (Q075 main target)**:
```
normal_state == True
not stress_active
not second_leg_active
BPS_NNB entry blocked
Gate F inactive BECAUSE: (IVP_252 >= 55 AND VIX >= 15)
other 5 benign conditions otherwise pass (SPX > MA50, ddATH > -4%,
  VIX < 22, VIX_5d <= +1.5)
```

**Secondary sample (diagnostic only, NOT main target)**:
```
Gate F inactive BECAUSE one of the other 5 benign conditions fails:
  SPX <= MA50
  OR ddATH <= -4%
  OR VIX >= 22 (would also trigger stress)
  OR VIX 5d > +1.5
```

Reason: secondary sample is closer to trend-broken / drawdown / stress-warning states, NOT pure IVP-blocked. Conflating them in P1 attribution would mix three different underlying problems.

### Revision 2 — Add Type D (Q3)
4-Type partition (was 3-Type):

```
A: False block             — VIX low absolute, IVP high only because past year quiet
B: Transition warning      — VIX 15-22, IVP high, VIX 5d rising, ddATH expanding
C: High-vol controlled     — VIX elevated, IVP high, VIX flat/falling, SPX stabilizing
D: Trend-deteriorated      — SPX <= MA50 OR MA50 slope negative OR ddATH <= -6%
                             (avoid; not a replacement-opportunity regime)
```

Type D is for completeness — likely the answer is "do nothing." But it must be classified, not silently mixed into B.

### Revision 3 — C2 gamma wording (Q4)
Original C2 description: "low-delta short-DTE BPS, reduced gamma exposure"

**Correct**: short-DTE has **HIGHER** gamma, not lower. The benefit is shorter time-at-risk and lower starting delta. Gamma sensitivity is a risk, not a benefit.

Revised wording: **"low-delta short-DTE BPS: lower starting delta and shorter time-at-risk, but higher gamma sensitivity; must be tested carefully."**

### Revision 4 — Success criteria (Q6)
Replace Q074-style bars (which were calibrated to full normal-day population):

**Economic threshold (Q075-specific, accounting for narrow ~10% of total trading days subset)**:
```
Strong: ΔROE ≥ +0.20pp annualized
Soft:   +0.05 to +0.20pp
Reject: < +0.05pp unless materially reduces risk
```

**Risk threshold (Q075 must be MORE strict than Q074 because operating in vol-warning regime)**:
```
V1/V2/V3 all pass
Worst 20d degradation must be ≤ 0.25pp vs baseline
Worst 63d degradation must be ≤ 0.25pp vs baseline
No transition-loss concentration
No new crisis-window failure
```

### Revision 5 — C0/C1 split (Q4)
```
C0: literally do nothing beyond existing held positions
C1: intentional cash / BOXX active allocation treatment
```

If model treats them equivalently (BOXX yield already in account cash baseline), state explicitly in P0 that C0 == C1 economically. Otherwise distinguish.

### Revision 6 — P1 capital context per bucket
Add to P1 attribution output (per bucket):

```
average BP utilization on blocked days
existing SPX exposure (held positions)
Q042 active or not
cash residual (after held + Q042 + replacement candidate)
```

Reason: replacement trade may compete for capital with existing safety buffer. P4 portfolio integration too late to discover this; record from P1.

---

## Additional emphasis (not numbered revision)

**"Cash / BOXX is a valid endpoint"** must appear in P0 TL;DR, not only in §2 constraints table. This framing principle is the entire reason Q075 exists as research (not just "find a replacement trade").

---

## 2nd Quant Sign-off

- [x] Q075 framing approved
- [x] Layer-3 conceptual handle confirmed
- [x] 6 revisions specified for P0
- [x] No additional research blockers
- [x] Cash/BOXX endpoint principle reinforced

→ Quant proceeds to draft Q075 P0 anchored memo with 6 revisions applied.
