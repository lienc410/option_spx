# Q036 Shadow Observation Review

Review window:
- Start:
- End:
- Reviewer:
- Runtime host: old Air
- Runtime posture: `overlay_f_mode = "shadow"`

## Runtime Health

- `web` status:
- `bot` status:
- `/api/recommendation` status:
- notable errors:

## Observation Scope

- This review is for **shadow governance only**.
- It is **not** an alpha-proof exercise.
- The key question is whether `Overlay-F` behaves cleanly in live runtime:
  - correct gate semantics
  - reviewable telemetry
  - no recommendation / sizing side effects
  - no stale-state false positives

## Overlay-F Shadow Evidence

- log file: `data/overlay_f_shadow.jsonl`
- alert file: `data/overlay_f_alert_latest.txt`
- new shadow rows:
- `would_fire=true` count:
- trigger dates:
- trigger strategies:
- recommendation side-effect observed: yes / no
- dashboard / bot misinterpretation observed: yes / no

## Gate-Semantics Check

- all events restricted to `IC_HV`: yes / no
- `idle_bp_pct >= 0.70` matched: yes / no / insufficient sample
- `VIX < 30` matched: yes / no / insufficient sample
- `sg_count < 2` matched: yes / no / insufficient sample
- `effective_factor = 1.0` in shadow: yes / no
- stale / missing live state false positives observed: yes / no

## Event Context Summary

- event count by date:
- event count by strategy:
- event count by `sg_count`:
- event count by `idle_bp_pct` bucket:
- event count by `VIX` bucket:
- rationale quality review:

## No-Side-Effect Check

- disabled vs shadow recommendation strategy parity:
- disabled vs shadow sizing parity:
- payload interpretation clean:
- bot interpretation clean:
- dashboard interpretation clean:

## Telemetry Quality

- JSONL schema complete: yes / no
- latest alert file updating as expected: yes / no
- duplicate / noisy writes observed: yes / no
- missing fields observed:

## Decision

- continue shadow / extend observation / revert disabled / PM active discussion

## Reason

- concise rationale

## Open Issues

- issue 1:
- issue 2:

## Next Review Date

- date:

## Notes

- A clean shadow window means:
  - events are sparse but semantically correct
  - no recommendation / dashboard / bot drift
  - no false positives from missing or stale live state
- `active` should not be discussed until there are enough real would-fire samples to review.
