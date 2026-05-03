# SPEC-075 Handoff — Overlay-F Core Logic

Date: 2026-05-03

## Scope

Implemented HC-local Overlay-F core logic with initial rollout posture `overlay_f_mode = "disabled"`.

This handoff covers the SPEC-075 implementation unit only. SPEC-076 telemetry/dashboard support is tracked separately in `task/SPEC-076_handoff.md`.

## Files Changed

- `strategy/overlay.py` — new Overlay-F state, gate evaluation, live/backtest portfolio-state helpers, telemetry writer.
- `strategy/selector.py` — added `overlay_f_mode`, inert recommendation payload fields, and live recommendation evaluation hook.
- `backtest/engine.py` — added overlay factor support for IC_HV sizing in shadow/active simulations while disabled remains inert.
- `tests/test_overlay_f_gate.py` — SPEC-075 gate, fail-closed, position-count, default-disabled, and sizing tests.

## Guardrails Implemented

- Short-gamma count uses position-count semantics, not strategy-family deduplication.
- Live state missing, stale, unauthenticated, or malformed fails closed with `effective_factor = 1.0`.
- Disabled mode skips live state evaluation and keeps recommendation payload inert.
- Backtest and live both use `PortfolioState` + `evaluate_overlay_f(...)` as the common decision path.
- Active size-up is limited to Overlay-F evaluation output; no other strategy sizing logic changed.

## Validation

- `arch -arm64 venv/bin/python -m unittest tests.test_overlay_f_gate tests.test_overlay_f_monitoring -v` — PASS, 10 tests.
- `arch -arm64 venv/bin/python -m unittest tests.test_state_and_api tests.test_bcd_filter tests.test_bcd_stop tests.test_engine_stop_wiring -v` — PASS, 36 tests.
- `arch -arm64 venv/bin/python main.py --dry-run` — PASS, recommendation path does not crash.
- 3y disabled parity spot, `start_date=2023-04-29` — PASS:
  - `57` trades
  - `$79,933.69` total PnL
  - matches tieout #3 disabled baseline.
- `arch -arm64 venv/bin/python -m compileall strategy backtest web scripts tests` — PASS.

## Full Regression Note

`arch -arm64 venv/bin/python -m unittest discover -s tests -v` ran 202 tests with 3 legacy failures in DIAGONAL Gate 1 expectations:

- `test_spec_048_055.Spec048055Tests.test_t16_gate_order_gate1_blocks_before_others`
- `test_spec_048_055.Spec048055Tests.test_t5_low_vol_bullish_ivp252_35_waits_gate1`
- `test_spec_056.Spec056Tests.test_t9_gates_still_active_when_not_disabled`

These failures are tied to previously removed DIAGONAL Gate 1 behavior and are outside SPEC-075/076.

## Rollout State

Current state: local implementation complete, `overlay_f_mode = "disabled"`.

No old Air deployment, service restart, or runtime posture change has been performed for SPEC-075.

