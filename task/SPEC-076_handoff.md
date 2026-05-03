# SPEC-076 Handoff — Overlay-F Monitoring And Review Support

Date: 2026-05-03

## Scope

Implemented HC-local Overlay-F telemetry, dashboard display support, and review helper tooling while leaving runtime posture disabled by default.

SPEC-076 is shadow-ready, but this handoff does not flip `overlay_f_mode` to `shadow` or `active`.

## Files Changed

- `strategy/overlay.py` — added JSONL telemetry writer and latest-alert artifact writer.
- `strategy/selector.py` — added Overlay-F recommendation payload fields for dashboard/API visibility.
- `web/server.py` — exposes `entry_reason` in backtest API trade rows for future active reproduction review.
- `web/templates/index.html` — displays Overlay-F panel only when payload contains a rationale; shows `F×2` badge only when effective factor is greater than 1.
- `scripts/overlay_f_review_reports.py` — new compact review report generator for `data/overlay_f_shadow.jsonl`.
- `doc/OVERLAY_F_REVIEW_PROTOCOL.md` — review protocol for disabled, shadow, and active rollout stages.
- `tests/test_overlay_f_monitoring.py` — telemetry schema and no-log-when-blocked tests.

## Shadow Evidence Schema

`data/overlay_f_shadow.jsonl` rows include:

- `date`
- `strategy`
- `vix`
- `idle_bp_pct`
- `sg_count`
- `mode`
- `effective_factor`
- `rationale`

Rows also include `timestamp` for review convenience.

`data/overlay_f_alert_latest.txt` stores the latest would-fire payload as formatted JSON.

## Dashboard Behavior

- Disabled mode: no Overlay-F panel or badge should appear because the payload is inert.
- Shadow mode: panel may show would-fire evidence, but factor remains `1.0`; dashboard must not treat it as an actual size-up.
- Active mode: `F×2` badge appears only when `overlay_f_factor > 1`.

## Validation

- `arch -arm64 venv/bin/python -m unittest tests.test_overlay_f_gate tests.test_overlay_f_monitoring -v` — PASS, 10 tests.
- Flask smoke via test client:
  - `/` — 200
  - `/api/recommendation` — 200
- `arch -arm64 venv/bin/python -m compileall strategy backtest web scripts tests` — PASS.

## Rollout State

Current state: shadow-ready implementation complete, still disabled by default.

No old Air deployment, service restart, or runtime telemetry collection has been performed for SPEC-076.

