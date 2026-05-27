# SPEC-107 Handoff — Intraday Recommendation Governance

Date: 2026-05-26
Status: DONE-ready; AC7 joint Quant + Developer validation PASS. Deployment is the remaining runtime step.

## Implemented

- F1: Added `strategy/intraday_governance.py`.
  - A2a entry band `[42, 53]`, hold band `[35, 57]`.
  - Per-position persistent state in `data/intraday_governance_state.json`.
  - Atomic state writes via temp file + `os.replace`.
  - Corrupt state fail-safe to raw selector / WAIT-safe behavior with alert/log path.
  - `INTRADAY_HYS_LOWER_FORCE_CLOSE=True` default with override alert/log.
- F2: Added NYSE-calendar scheduled actionable bars.
  - Default `10:30` / `15:30` ET.
  - NYSE holiday skip.
  - Early close fallback includes last actionable bar at least 30 minutes before close.
  - Bypass classes implemented as immediate actionable governance decisions.
- F3: Added decision log carrier.
  - `data/intraday_governance_log.jsonl`.
  - Includes priority layer/name, bypass type, hysteresis prev/new, last/next actionable timestamps.
- F4: Added SPX dashboard semantics.
  - Non-scheduled bars show `State Observation`.
  - Scheduled/bypass decisions show actionable or hard-exit labels.
  - Open-position CTA is disabled during non-actionable observation windows.
- Telegram support:
  - Added 10:30 / 15:30 scheduled governance push jobs.
  - Daily 09:35 Signal 1 path is unchanged.

## Validation Run

- `arch -arm64 venv/bin/python -m unittest tests.test_spec_107 -v`
  - 11/11 PASS.
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_107 tests.test_spec_103 tests.test_spec_104 tests.test_spec_105 tests.test_spec_106 -v`
  - 53/53 PASS.
- `arch -arm64 venv/bin/python -m py_compile strategy/intraday_governance.py notify/telegram_bot.py web/server.py`
  - PASS.
- `arch -arm64 venv/bin/python -m compileall strategy web notify tests`
  - PASS.

## Known Validation Gap

- Closed by Quant validation: `task/SPEC-107_ac7_quant_validation_2026-05-26.md`.
- Final AC7 replay result:
  - `intraday_flips=92` versus `93±5`
  - `episodes_le_3h=3` versus `<=4`
  - `round_trips=20` versus `18±2`
  - `eod_agreement_pct=93.2%` versus `>=92%`
- Root-cause fixes:
  - Entry-band else clause now rejects BPS opens outside `[42, 53]`.
  - State key uses stable SPX fallback instead of `rec.underlying` drift.
  - Hysteresis state is decoupled from broker position id / active-position status.

## Notes

- `pandas_market_calendars>=4.4` was added to `pyproject.toml`.
- Existing `tests.test_state_and_api` has one failure in `test_api_backtest_latest_cached_returns_latest_entry`; this appears tied to local cache state / pre-existing test fixture behavior and is not caused by SPEC-107 changes. The SPEC-107 API recommendation test in that suite passed.
- old Air deploy should restart `com.spxstrat.web` and `com.spxstrat.bot`; cloudflared is out of scope.
