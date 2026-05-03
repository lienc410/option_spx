# Overlay-F Review Protocol

Overlay-F rollout is staged: `disabled -> shadow -> active`.

## Disabled

- Expected behavior: no trade flow, sizing, recommendation, dashboard, or telemetry effect.
- Required check: full backtest trade list and metrics match the pre-overlay baseline.

## Shadow

- Expected behavior: evaluate would-fire events and write telemetry only.
- Required artifacts:
  - `data/overlay_f_shadow.jsonl`
  - `data/overlay_f_alert_latest.txt`
- Each event must include: `date`, `strategy`, `vix`, `idle_bp_pct`, `sg_count`, `mode`, `effective_factor`, and `rationale`.
- Dashboard and bot must not present shadow as actual size-up.

## Active

- Expected behavior: `IC_HV` entries that pass Overlay-F use `effective_factor = 2.0`.
- Active is allowed only after PM approval following a shadow observation period.
- Roll back to `shadow` or `disabled` if fire count, disaster-window behavior, drawdown, or active envelope metrics diverge materially from review expectations.
