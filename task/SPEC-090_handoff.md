# SPEC-090 Handoff

## Summary

`SPEC-090` is implemented and operationally registered on old Air.

New read-only monitor:

- `research/q041/daily_alignment_check.py`

New test coverage:

- `tests/test_spec_090.py`

Operational surface:

- daily JSONL log: `data/q041_overlap_daily.jsonl`
- alert dedupe state: `data/q041_overlap_alert_state.jsonl`
- local log: `logs/q041_alignment.log`
- old Air launchd job: `com.spxstrat.q041align`

## Metric Semantics

The implementation intentionally uses the narrowed operational subset already accepted during Q041 overlap cleanup:

- `M1` = Schwab traded subset (`volume > 0`) 4-key match rate against Massive same-day snapshot
- `M4` = matched liquid subset share with `|Schwab last - Massive day_close| / Massive day_close > 2%`
  - liquid subset = `|delta| 0.10–0.50`, Massive `day_close > 1.0`, Schwab `last > 0`
- `M6` = Schwab near-money IV validity rate
  - near-money subset = `|delta| 0.25–0.75`, valid when `iv > 0`

This keeps the runtime alert aligned to the accepted traded / price-bearing denominator, not the deprecated raw full-chain denominator.

## Telegram Behavior

The script sends:

1. one daily report message
2. one follow-up alert message only if any threshold breaches

Thresholds:

- `M1 < 95%`
- `M4 > 5%`
- `M6 < 95%`

If either source is missing, the script fail-softs and sends:

- `Q041 数据对齐：今日无数据`

Same-day duplicate alerts are suppressed per metric using:

- `data/q041_overlap_alert_state.jsonl`

## old Air Registration

Registered plist:

- `~/Library/LaunchAgents/com.spxstrat.q041align.plist`

Schedule:

- `17:00 ET`

Command:

```text
/Users/macbook/SPX_strat/venv/bin/python -m research.q041.daily_alignment_check
```

Stdout / stderr:

- `/Users/macbook/SPX_strat/logs/q041_alignment.out.log`
- `/Users/macbook/SPX_strat/logs/q041_alignment.err.log`

Manual verification completed:

- `launchctl list | grep q041` shows all four jobs
- `launchctl print gui/$(id -u)/com.spxstrat.q041align` shows:
  - `runs = 1`
  - `last exit code = 0`
- weekend manual kickstart produced the expected `skipped:non_trading_day` log line

## Validation

Local:

- `arch -arm64 venv/bin/python -m py_compile research/q041/daily_alignment_check.py tests/test_spec_090.py`
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_090 -v`
- `arch -arm64 venv/bin/python -m unittest tests.test_q041_massive_snapshot -v`
- `arch -arm64 venv/bin/python -m unittest tests.test_telegram_bot -v`
- `arch -arm64 venv/bin/python -m research.q041.daily_alignment_check --date 2026-05-04 --skip-telegram --force`

old Air:

- `cd ~/SPX_strat && venv/bin/python -m research.q041.daily_alignment_check --date 2026-05-04 --skip-telegram --force`
- launchd registration + `kickstart`

## Known Limits

- Holiday guard is implemented in-script for the current operational calendar set (`2025/2026`) rather than depending on launchd behavior.
- `M6` is Schwab-only validity monitoring, per the narrowed runtime requirement. It does not attempt the full historical Massive-IV overlap comparison from the larger research protocol.
- The alert state file is runtime-only and expected to evolve daily. It is not a research artifact.
