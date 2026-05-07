# SPEC-084 Handoff: Q045 Joint `bp_target` Lift

Date: 2026-05-07
Status: DONE

## Summary

Implemented the approved Q045 J3 parameter lift as a narrow parameter/display change:

- `bp_target_low_vol`: `0.10 -> 0.15`
- `bp_target_normal`: `0.10 -> 0.15`
- `bp_target_high_vol`: `0.07 -> 0.14`
- `_size_rule()` display text: `3% / 1.5% -> 4.5% / 2.25%`

No strategy matrix, bot, runtime, broker, Q036, or Q041 code was changed.

## Files Changed

- `strategy/selector.py`
- `tests/test_spec_084.py`
- `tests/test_state_and_api.py`
- `task/SPEC-084.md`
- `task/SPEC-084_handoff.md`

## Validation

Command:

```bash
arch -arm64 venv/bin/python -m unittest tests.test_spec_084 tests.test_state_and_api -v
```

Result: PASS, 22 tests.

Coverage:

- New default values are `0.15 / 0.15 / 0.14`.
- `_size_rule()` text contains `4.5%` and `2.25%`.
- Explicit old baseline override `0.10 / 0.10 / 0.07` returns `10.0` on the BP target preview path and runs `run_backtest(...)` without crashing.
- `bp_ceiling_normal == 0.35` and `bp_ceiling_high_vol == 0.50` remain unchanged.
- Existing open-draft API BP preview assertion updated from `10.0` to `15.0`.

## Risk Disclosure

- Worst trade: `-8.82% acct`.
- Peak BP: `43%`.
- This implementation did not adjust any ceiling.
- This implementation did not modify Q036 or Q041.

## Scope Notes

`_size_rule()` was confirmed to be display text only for this change. No deeper sizing logic was modified there.
