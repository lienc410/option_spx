# SPEC-086 Handoff — /ES Short Put Credit Stop Monitor

Date: 2026-05-07
Status: DONE

## Summary

Implemented a read-only `/ES` short put credit stop monitor inside the existing Telegram `intraday_monitor` loop.

Behavior:

- WARNING when current `/ES` put mark is >= 2x entry premium.
- TRIGGER when current `/ES` put mark is >= 3x entry premium.
- Cleared message when a valid observed mark falls back below 2x.
- Schwab positions stale / unauthenticated / fetch failure fails soft without false alert.

## Files Changed

- `notify/telegram_bot.py`
- `tests/test_spec_086.py`
- `tests/test_telegram_bot.py`
- `task/SPEC-086.md`

## Implementation Notes

- Added `EsStopLevel` and `EsStopResult` to track `NONE / WARNING / TRIGGER`.
- Extended `_intraday_state` with `es_stop_level`.
- Added `_check_es_credit_stop()`:
  - Reads current strategy state.
  - Calls Schwab positions only when active state is `/ES` short put.
  - Uses `actual_premium`, falling back to `model_premium`.
  - Uses Schwab position `mark` as the current option mark.
- Added `_format_es_stop_alert()` for WARNING / TRIGGER / cleared Telegram messages.
- Added `observed` semantics so unavailable Schwab data does not produce false cleared alerts or reset an elevated in-session state.

## Validation

Passed:

```bash
arch -arm64 venv/bin/python -m py_compile notify/telegram_bot.py tests/test_spec_086.py
arch -arm64 venv/bin/python -m unittest tests.test_spec_086 tests.test_telegram_bot -v
```

## Scope Confirmation

- No broker write endpoint added or called.
- No automatic close / order behavior added.
- No changes to `strategy/selector.py`.
- No changes to `strategy/state.py`.
- No changes to SPEC-061 logic.

## Follow-Up Risk

Live Schwab `mark` unit has not been validated against a real `/ES` position during this implementation. The implementation assumes the existing positions payload `mark` is per-contract option price in the same unit as `actual_premium`, per SPEC-086.
