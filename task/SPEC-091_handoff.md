# SPEC-091 Handoff

## Summary

`SPEC-091` is implemented as a narrow, read-only Signal 2 sidecar.

Core principle preserved:

- **Signal 1 remains canonical and unchanged**
- **Signal 2 is observational / informational only**

Implemented files:

- `production/vix_settling.py`
- `web/server.py`
- `web/templates/portfolio_home.html`
- `tests/test_spec_091.py`

Operational files:

- `logs/q019_settling_state.json`
- `data/q019_settling_log.jsonl`
- `logs/q019_settling.log`

old Air launchd:

- `com.spxstrat.signal_settling`

## Runtime Design

The implementation deliberately avoids touching the existing Telegram bot push path.

Current division:

- **Signal 1**
  - source: existing `notify.telegram_bot.scheduled_push`
  - route: existing `/api/recommendation`
  - semantics: unchanged intraday-current recommendation

- **Signal 2**
  - source: `production.vix_settling`
  - schedule: separate launchd job at `09:30 ET`
  - semantics: wait for hourly VIX stabilization, then emit one confirmation/diff message
  - no write-path into position state, no routing back into Signal 1

This was chosen to satisfy `AC1` and `AC10` cleanly.

## Settling Rule

Locked parameters used in production:

- `SETTLING_INTERVAL = "1h"`
- `SETTLING_THRESHOLD = 0.5`
- `SETTLING_TIMEOUT_MIN = 180`
- `SETTLING_DATA_SOURCE = "yfinance:^VIX"`

Interpretation:

- compare the latest two hourly VIX closes for the current ET trading day
- if `abs(delta) < 0.5` → `stable`
- if not stable by `12:30 ET` → `timeout`
- timeout fallback still produces Signal 2 using the latest available intraday VIX

## Web Surface

New API:

- `/api/recommendation/settling`

Fail-soft semantics:

- missing state file → `status = "unavailable"`
- stale state on a trading day → `status = "unavailable"`
- non-trading day → `status = "skipped"`

Homepage surface:

- added a small read-only panel under the SPX card
- shows:
  - waiting state
  - stable/timeout final state
  - Signal 1 vs Signal 2 comparison
  - explicit disclaimer that this is forward-tracking observation only

No changes were made to:

- `/api/recommendation`
- SPX recommendation card action semantics
- bot command handlers
- intraday alert logic

## Logging

Daily finalization appends one row to:

- `data/q019_settling_log.jsonl`

Fields:

- `date`
- `vix_signal1`
- `rec_signal1`
- `vix_signal2`
- `rec_signal2`
- `settling_status`
- `elapsed_min`
- `changed`

Current-session state is stored separately in:

- `logs/q019_settling_state.json`

This separation keeps the JSONL paper-trading log append-only while giving the web UI a simple latest-state artifact.

## old Air Registration

Registered plist:

- `~/Library/LaunchAgents/com.spxstrat.signal_settling.plist`

Command:

```text
/Users/macbook/SPX_strat/venv/bin/python -m production.vix_settling
```

Schedule:

- `09:30 ET`

Verification completed:

- `launchctl list | grep signal_settling`
- `launchctl print gui/$(id -u)/com.spxstrat.signal_settling`
  - `runs = 1`
  - `last exit code = 0`
- manual kickstart on a non-trading day produced:
  - state file with `status = skipped`
  - local API payload with `status = skipped`

## Validation

Local:

- `arch -arm64 venv/bin/python -m py_compile production/vix_settling.py web/server.py tests/test_spec_091.py`
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_091 -v`
- `arch -arm64 venv/bin/python -m unittest tests.test_telegram_bot -v`

old Air:

- `git pull --ff-only`
- `source venv/bin/activate && pip install -e .`
- restart `com.spxstrat.web`
- register + kickstart `com.spxstrat.signal_settling`
- curl local `/api/recommendation/settling`

## Known Limits

- This implementation does **not** suppress the existing Signal 1 09:35 Telegram message. It adds a later Signal 2 message only. That matches the current approved spec wording and preserves `AC1`.
- On non-trading days the sidecar only publishes `skipped`; there is no Signal 1 / Signal 2 payload.
- The settling sidecar currently uses direct Telegram HTTP sends rather than reusing the bot polling process. This is intentional isolation, not a missing integration.
