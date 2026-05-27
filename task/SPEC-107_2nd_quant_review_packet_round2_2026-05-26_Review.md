# SPEC-107 Round 2 Review — 2nd Quant Verification

**Date**: 2026-05-26
**Reviewer**: 2nd Quant
**Subject packet**: `task/SPEC-107_2nd_quant_review_packet_round2_2026-05-26.md`
**Verdict**: **PASS WITH FINAL MICRO-EDITS — R1–R7 已正确落地。可以进入 PM approval / Developer handoff after 7 small implementation-hardening edits.**

---

## Overall

SPEC-107 现在已经从 "研究结论" 变成了相对完整的 execution-governance implementation spec。最重要的是它继续守住边界：

> **SPEC-107 只管理 recommendation/actionability，不改 selector strategy semantics。Low-IVP entry-only 仍属 Q077。**

---

## V1-V10 Answers

| # | Answer |
|---|---|
| V1 | Correct. 7-layer order accepted. Stop-loss + lifecycle can remain one layer. |
| V2 | Accepted. `hard_exit=True` acceptable; add note that ordinary signal changes must not set it. |
| V3 | Accepted. `≤3h ≤4` is better than `3±1`. |
| V4 | Accepted. Boundary-grid AC8b enough. No 10K fuzz target needed. |
| V5 | Accepted with tweak. Prefer `next_actionable_decision_at` always populated; optionally add readable `final_priority_name`. |
| V6 | Accepted. Flag name OK. Add Telegram/log alert if changed from default in prod. |
| V7 | Accepted with clarification. Path OK. Half-day rule OK; specify NYSE calendar source and fail-safe state corruption behavior. |
| V8 | Accepted. §F top-level placement OK. |
| V9 | Accepted. AC9 standalone OK. |
| V10 | No major missing item. Only minor clarifications. |

---

## 7 Final Micro-Edits (E1-E7) — required before PM approval

```
E1. Add note: hard_exit=True only for immediate-risk exits, not ordinary strategy preference changes.
E2. Make next_actionable_decision_at normally non-null; after 15:30 use next trading day 10:30.
E3. Add optional/readable final_priority_name, or confirm bypass_type fully covers it.
E4. Add Telegram/log alert if INTRADAY_HYS_LOWER_FORCE_CLOSE changes from default True in production.
E5. Add state-file corruption fail-safe behavior (corrupt → fail safe to raw selector / WAIT, not stale BPS hold).
E6. Specify NYSE market calendar source for holidays / half-days.
E7. Generalize early-close rule: last actionable time at least 30 min before close; default 12:30 on 13:00 close.
```

These are implementation-hardening edits, not research changes.

---

## Specific clarifications

### E1 — hard_exit=True discipline
> `hard_exit=True` must be set only by selector/governance logic for immediate-risk exits, not by ordinary strategy preference changes.

### E2 — next_actionable_decision_at policy
```
During market hours:    next scheduled actionable bar today if remaining
After 15:30:            next trading day 10:30
On market holiday:      next valid trading day 10:30
For bypass event:       still populate (bypass itself is immediate; next sched continues)
Null only allowed:      when calendar utility fails (and must emit stale_data_failsafe log)
```

### E3 — readable priority name
Option A (preferred): add `final_priority_name` string (e.g., `"spec_103_hard_risk_daemon"`)
Option B: confirm `bypass_type` enum string fully covers audit needs

### E4 — Flag-change observability
> If `INTRADAY_HYS_LOWER_FORCE_CLOSE` changes from default True in production, emit Telegram alert AND write decision log event.

### E5 — State corruption fail-safe
> Writes must be atomic. State file corruption must fail safe to raw selector / WAIT, not stale BPS hold.

### E6 — Calendar source
Explicit reference: NYSE trading calendar (e.g., `pandas_market_calendars` NYSE, or existing project market calendar utility). Don't allow hand-written holiday lists.

### E7 — Early-close rule generalized
> On early-close days, use the last scheduled actionable time **at least 30 minutes before market close**; default 12:30 ET for 13:00 close.

---

## Final verdict (formal)

> SPEC-107 Round 2 review passes. R1–R7 have been implemented correctly. The priority stack, bypass list, AC7 tolerance, AC8 fuzz invariant, decision log fields, forward-compatible lower-force-close flag, and persistence/timezone/calendar requirements all reflect the Round 1 review intent. Before PM approval, apply minor hardening edits (E1-E7) around hard_exit metadata discipline, next_actionable_decision_at semantics, production flag-change alerting, state-file corruption fail-safe, and explicit NYSE calendar handling. No further quant research is required.
