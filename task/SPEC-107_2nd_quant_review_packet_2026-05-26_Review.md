# SPEC-107 — 2nd Quant Review Response (Round 1)

**Date**: 2026-05-26
**Reviewer**: 2nd Quant
**Subject packet**: `task/SPEC-107_2nd_quant_review_packet_2026-05-26.md`
**Verdict**: **PASS WITH MINOR REVISIONS — 可以进 PM approval / Developer handoff，但先补几条 AC 和 priority 说明。**

---

## Verdict

> SPEC-107 的大方向是对的：把 Q076 P3 的 A2a+B 结论落实成 **execution governance layer**，没有顺手改 selector 语义，也没把 low-IVP entry-only 问题混进来。
>
> 最大风险是 **bypass list 和 priority order 讲得还不够硬**。

可以继续，但需要在 AC3 / AC6 / AC7 / AC8 加强。

---

## Q1-Q8 Answers (summary)

| Q | Answer |
|---|---|
| Q1 Scope | Pass — add lifecycle boundary clarification |
| Q2 Bypass list | **Revise** — expand to 7 classes; trend only bypass if hard_exit metadata |
| Q3 SPEC-103 priority | **Must specify** — SPEC-103 / hard-risk always wins; add unit test |
| Q4 AC7 tolerance | **Tighten** — EOD ≥92%; ≤3h ≤4 |
| Q5 AC8 | **Strengthen** — real subset + synthetic/fuzz HIGH_VOL non-BPS test |
| Q6 Decision log | **Add fields now** — last/next actionable timestamps + priority/bypass fields |
| Q7 Bands sensitivity | Defer — make bands configurable; monitor live boundary usage |
| Q8 Q077 compat | **Add flag** — `hysteresis_lower_force_close=true` default |

---

## 7 Required Revisions (R1-R7)

### R1. Explicit priority order

```text
1. Manual PM override
2. Broker/system stop-loss and lifecycle exits
3. SPEC-103 hard-risk daemon: R5/R6
4. EXTREME_VOL / EXTREME_VIX hard exit
5. SPEC-107 scheduled actionable decision
6. SPEC-107 hysteresis state
7. Raw selector recommendation
```

Or simpler:

> Hard-risk layer always overrides intraday governance.
> SPEC-107 may delay soft selector churn.
> SPEC-107 may never delay hard-risk exits.

AC3 must include unit test:
> Given SPEC-107 says OPEN/HOLD BPS and SPEC-103 R6 says BLOCK/CLOSE,
> final action must be BLOCK/CLOSE.

### R2. Expanded bypass list (7 classes)

```text
1. Manual PM override
2. Broker / system stop-loss
3. Profit-taking / planned lifecycle exit / roll / expiration management
4. SPEC-103 daemon hard rules: R5 stress / R6 second-leg
5. EXTREME_VOL / EXTREME_VIX
6. Any selector verdict explicitly marked hard_exit=True
7. Emergency data-quality / stale-data failsafe
```

**Trend change is not a bypass unless mapped to a hard_exit flag by selector/governance metadata.**

DD Overlay armed state: NOT bypass.

Roll operations: bypass, but as **lifecycle operation**, not selector bypass.

### R3. AC7 tolerance tightened

```text
flips: 93 ± 5            (unchanged)
≤3h episodes: ≤4         (was: 3 ± 1)
round trips: 18 ± 2      (unchanged)
EOD agreement: ≥92%      (was: ≥90%)
```

Reason: 90% just barely passes PM's original hard target, no safety margin. P3 actual 93.2% — tightening to ≥92% leaves implementation 1.2pp slack while keeping real safety.

### R4. AC8 strengthened — two-layer

**AC8a — Real replay regression**:
```text
Using 12mo replay subset:
HIGH_VOL/STRESS bars must generate 0 BPS governance intervention.
```

**AC8b — Synthetic/fuzz test**:
```text
Construct synthetic inputs:
  VIX regime = HIGH_VOL or STRESS
  IVP values around 35 / 42 / 53 / 57
  prior governance state = BPS
  raw selector verdict = non-BPS / IC / Wait

Assert:
  SPEC-107 hysteresis must NOT convert non-BPS selector verdict
  into BPS hold/open in HIGH_VOL or STRESS.
```

This tests **architecture invariant**, not just historical sample.

### R5. Decision log fields added

Add immediately (avoid JSONL schema drift later):

```text
last_actionable_decision_at
next_actionable_decision_at
final_priority_layer        (which of 7 layers won the decision)
bypass_type                 (enum from R2 bypass list)
```

### R6. Forward-compat config flag

```text
hysteresis_lower_force_close: true        (default — matches A2a production semantics)
```

Spec must state:
> Default remains true under SPEC-107.
> Changing this flag requires Q077 approval / separate SPEC.

Upper-bound hysteresis (IVP > 57 close) **always active**, never gated by flag.

### R7. State persistence + timezone/calendar

Add to AC1:
```text
Hysteresis state must persist across process restart.
State key must include account / underlying / strategy / position id where applicable.
If no active position exists, state resets to WAIT.
```

Add to AC2:
```text
Scheduled times are America/New_York.
Actionable bars are nearest available aligned bar at 10:30 and 15:30 ET.
Half-days / market holidays should not generate false scheduled decisions.
```

---

## Additional clarifications (not blocking)

### Scope clarification (R1 addendum)

Add to SPEC §不在范围内:
> SPEC-107 governs recommendation/actionability only.
> It does not govern trade lifecycle operations such as profit-taking, stop-loss, roll, expiration management, or manual close.

### Hysteresis band sensitivity (Q7 deferred)

```text
Bands must be configurable via ENV/config file.
No code change required for future calibration.

After 1-3 months live shadow:
report frequency of IVP in 35-42 / 53-57 / outside bands.
If most overrides cluster at one boundary, revisit band calibration.
```

---

## Final Verdict (formal)

> SPEC-107 is directionally correct and ready for PM approval after minor revisions. It properly implements Q076 A2a+B as execution governance without modifying selector strategy semantics. The main required fixes are to hard-code priority order against SPEC-103 / hard-risk exits, expand the bypass list, tighten AC7 EOD tolerance, strengthen HIGH_VOL/STRESS regression, add actionable timestamp fields to the decision log, and add a future-compat flag for lower-IVP force-close semantics. No further quant research is required before SPEC drafting; these are implementation-spec refinements.
