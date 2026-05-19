# Q074 P3 / G3 — 2nd Quant Mid-Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-18
**Source**: `task/q074_p3_g3_2nd_quant_review_packet_2026-05-18.md`
**Verdict**: **PASS WITH REVISIONS — proceed to P4, scope expanded**

---

## Final verdict statement

> P3 methodology is acceptable. Results are unusually clean but not obviously flawed. B4 is the leading candidate and B3 is the backup. Proceed to P4 on B4 + B3, adding episode-level transition diagnostics, B4 VIX20–22 joint-slice analysis, and negative-cash funding stress. Do not run B1/B2 full P4. Do not change B1–B4 definitions. Do not elevate B4 to Strong Pass until P4 validation confirms robustness.

---

## 6 questions — 2nd Quant answers

| Q | Verdict |
|---|---|
| Q1 — POSITIVE transition incremental real or artifact? | **Mostly real**, but ON-day incremental ≠ full episode. P4 must add episode-level diagnostic. |
| Q2 — 41-43 events sufficient? | **Enough for P3 screening; not for promotion alone**. P4 bootstrap/walk-forward still required. |
| Q3 — Worst loss -0.15% too optimistic? | **Possibly optimistic**. Add **negative-cash funding stress +300bp / +600bp** beyond friction ±50%. |
| Q4 — VIX 20-22 surprise needs deeper analysis? | **YES — add joint-slice analysis**, but don't block P4. |
| Q5 — Run B4 alone or B4 + B3? | **B4 + B3 parallel** (Quant proposal accepted). |
| Q6 — Elevate B4 to Strong on +0.25pp? | **NO — "borderline strong / Strong-eligible pending P4"**. Don't write Strong Pass yet. |

---

## 4 P4 scope additions (per G3)

### P4 add-on 1: Episode-level transition incremental

Beyond ON-day incremental (already in P3), add full episode incremental:

```
For each transition episode:
  total candidate portfolio PnL over 10d / 20d episode
  total Arch-3 baseline PnL over same episode
  incremental = candidate - baseline (FULL episode, not just booster-on days)
```

Validates that "ON-day positive" doesn't mask OFF-day hidden losses.

### P4 add-on 2: B4 VIX 20-22 joint-slice analysis

For B4 booster-active days with VIX 20-22:

```
count
IVP bucket distribution
ddATH bucket distribution
VIX_5d_change bucket distribution
forward / incremental PnL
stress within 10d / 20d
failed-benign count
```

Hypothesis: multi-condition filtering (IVP < 55 + ddATH > -4% + VIX_trend not rising + above MA50) cuts VIX 20-22 into a "still compensated" subset.

### P4 add-on 3: Negative-cash funding stress

When booster active 90% + Q42 17.5% = 107.5% exposure, cash residual = -7.5% (margin loan). Test sensitivity:

```
Base funding cost: BOXX 4.3%
Stress: BOXX + 300bp = 7.3%
Severe: BOXX + 600bp = 10.3%
```

Apply additional cost ONLY on negative-cash days. Confirms B4 vs B3 ordering robust under realistic funding stress.

### P4 add-on 4: B4 vs B3 active-day overlap + incremental delta

```
days where B4 active AND B3 active
days where B4 active AND B3 inactive (B4-only)
B4 vs B3 incremental PnL on overlap vs non-overlap days
```

Quantifies how much of B4's edge comes from VIX 20-22 inclusion (B4-only days) vs shared signal (overlap).

---

## P4 core scope (unchanged)

- B4 primary + B3 backup
- V6 bootstrap (block=250, 20 seeds)
- V7 walk-forward H1/H2 (2000-2013 vs 2013-2026)
- Friction sensitivity ±50%
- Crisis windows comparison (Arch-3 vs B4 vs B3)
- Synthetic crisis injection

---

## 2nd Quant Sign-off Status

- [x] P3 methodology acceptable
- [x] Results unusually clean but not flawed
- [x] B4 + B3 parallel P4 approved
- [revise → applied] Add episode-level transition diagnostic
- [revise → applied] Add B4 VIX 20-22 joint-slice analysis
- [revise → applied] Add negative-cash funding stress +300bp / +600bp
- [x] B1 / B2 skipped from P4 (too small ROE for SPEC effort)
- [x] B4 status = "borderline strong / Strong-eligible pending P4", NOT yet Strong Pass

→ Quant adds 4 P4 scope items to standard validation suite, then runs P4.
