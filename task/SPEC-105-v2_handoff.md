# SPEC-105 v2 Handoff — B4 Booster IVP Gate Refinement

**Date**: 2026-05-19
**Status**: DONE locally; old Air deploy pending
**Scope**: narrow amendment to SPEC-105 v1 Gate F

## Summary

SPEC-105 v2 refines the B4 booster IVP gate from:

```text
IVP_252 < 55
```

to:

```text
IVP_252 < 55 OR VIX < 15
```

The change keeps the existing Stage 1 shadow posture. Production SPX cap remains `80%` in shadow mode; the `90%` booster cap is still not live unless PM separately approves active mode.

## Files Changed

- `strategy/sleeve_governance.py`
- `web/templates/portfolio_home.html`
- `tests/test_spec_105.py`
- `task/SPEC-105.md`
- `task/SPEC-105-v2.md`
- `task/SPEC-105-v2_handoff.md`

Research artifacts added:

- `research/q074/q074_1*`
- `research/q074/q074_2*`
- `task/q074_1b_2nd_quant_review_packet_2026-05-19.md`
- `task/q074_2_2nd_quant_review_packet_2026-05-19.md`
- `task/q074_2_2nd_quant_review_packet_2026-05-19_Review.md`

## Implemented Behavior

- `booster_signal_conditions()` now exposes:
  - `ivp_ok`
  - `low_vix_escape_ok`
  - `ivp_gate_pass`
- `b4_benign_active()` now requires `ivp_gate_pass`, not `ivp_ok` alone.
- Added `gate_f_only_active()` diagnostic helper.
- `data/q074_booster_shadow.jsonl` new rows now include:
  - `gate_f_only`
- Dashboard booster panel now shows:
  - `IVP252 < 55`
  - `OR VIX < 15`
  - `IVP gate pass`

## Explicit Non-Changes

- Did not change `CAP_SPX_BENIGN_BOOSTER = 90.0`.
- Did not change Stage 1 shadow default.
- Did not change SPEC-104 caps `80 / 50 / 40`.
- Did not change R5/R6 trigger definitions.
- Did not change Q042 / HV Ladder behavior.
- Did not add F2 runtime variant.
- Did not backfill historical shadow logs.

## Validation

Commands run locally:

```bash
arch -arm64 venv/bin/python -m unittest tests.test_spec_105 -v
arch -arm64 venv/bin/python -m unittest tests.test_spec_103 tests.test_spec_104 tests.test_spec_105 -v
arch -arm64 venv/bin/python -m py_compile strategy/sleeve_governance.py web/server.py tests/test_spec_105.py
```

Results:

- `tests.test_spec_105` → 10/10 PASS
- `tests.test_spec_103 + tests.test_spec_104 + tests.test_spec_105` → 27/27 PASS
- `py_compile` → PASS

API local smoke:

- `/api/sleeve-governance/state` → 200
- `booster_signal_conditions` includes `ivp_ok`, `low_vix_escape_ok`, `ivp_gate_pass`

Q074.2 reference row checked from `research/q074/q074_2_portfolio_metrics.csv`:

- B4_F Net ROE `8.2143%`
- MaxDD `-8.715%`
- W20d `-7.042%`
- W63d `-8.656%`
- Booster active `39.805%` of normal days

## Deployment Notes

Deploy to old Air with existing Stage 1 shadow posture:

- do not set `SPX_BENIGN_BOOSTER_MODE=active`
- restart `com.spxstrat.web`
- restart `com.spxstrat.bot`
- verify `/api/sleeve-governance/state` contains the three new condition fields
- run `scripts/refresh_backtest_caches.py`

## Follow-Up Risk

`gate_f_only` is diagnostic only. It is not a stop rule and should not affect production cap, routing, or PM gates.
