# SPEC-108 Handoff — Selector-Gated SPX Execution Ladder

Date: 2026-05-28
Status: DONE
Owner: Developer

## Summary

Implemented SPEC-108 as a Stage 1 shadow-only execution ladder. The ladder consumes the existing selector verdict, applies V3 daily-cluster cadence, S3 sizing, concurrency, and BP ceiling gates, and writes shadow evidence without allowing production ladder orders unless `LADDER_MODE=active` is explicitly set.

## Files Changed

- `strategy/sleeve_governance.py`
  - Added ladder constants and `ladder_mode()` with mandatory shadow default.
  - Added read-only ladder state fields to `/api/sleeve-governance/state` payload path.
  - Added shadow decision payload and shadow-log/alert wiring.
- `strategy/q078_ladder.py`
  - New ladder domain module with `LadderState`, `v3_ladder_eligible()`, shadow JSONL writer, trading-day cadence logic, and production-order guard.
- `web/server.py`
  - Added active-mode-only ladder gate to production open path.
  - Shadow/off modes leave the existing entry path behavior unchanged.
- `web/templates/portfolio_home.html`
  - Added independent SPEC-108 ladder panel with mode badge, skip reason chip, cadence, last entry, action days YTD, and active/BP summary.
- `notify/telegram_bot.py`
  - Added scheduled shadow “would enter” Telegram alert path.
- `tests/test_spec_108.py`
  - New automated AC coverage for constants, gates, API fields, shadow default, shadow log, action-day count, and AC-108-17/18 production-disable guarantees.
- `task/SPEC-105-v2.md`
  - Appended SPEC-108 status note only; no SPEC-105 logic changed.
- `task/SPEC-108.md`
  - Marked DONE after implementation and validation.

## Acceptance Coverage

- AC-108-1 through AC-108-18 are covered by `tests/test_spec_108.py` plus adjacent regression tests.
- Stage 1 default is `shadow`.
- `production_order_allowed()` returns false unless `LADDER_MODE=active` and all gates pass.
- Shadow log schema includes `ladder_mode` and `selector_timestamp`.
- `/api/sleeve-governance/state` adds ladder fields without removing existing fields.

## Validation

Commands run locally:

```bash
arch -arm64 venv/bin/python -m py_compile strategy/sleeve_governance.py strategy/q078_ladder.py web/server.py notify/telegram_bot.py tests/test_spec_108.py
arch -arm64 venv/bin/python -m unittest tests.test_spec_108 -v
arch -arm64 venv/bin/python -m unittest tests.test_spec_103 tests.test_spec_104 tests.test_spec_105 tests.test_spec_106 tests.test_spec_107 -v
```

Results:

- `tests.test_spec_108`: 12/12 PASS
- `tests.test_spec_103` through `tests.test_spec_107`: 53/53 PASS

Runtime smoke:

- `ladder_mode()` default: `shadow`
- Current local ladder state: `selector_wait`, no would-enter, production order not allowed.

## Stage / Rollout Notes

- Initial rollout must remain Stage 1 shadow-only.
- No SPEC-104 numeric caps were changed.
- No SPEC-105 v2 Gate F logic was changed.
- No SPEC-077 exit logic was changed.
- No selector routing logic was changed.
- First real shadow event requires a future selector PASS day; current selector state may legitimately skip and produce no would-enter alert.
