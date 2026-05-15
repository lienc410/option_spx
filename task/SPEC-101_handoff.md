# SPEC-101 Handoff — ES High-Vol Sell Put Ladder

Date: 2026-05-14
Status: DONE

## Summary

Implemented ES High-Vol Sell Put Ladder as a paper/shadow variant only. The production SPEC-061 `/ES` bot path remains unchanged.

## Files Changed

- `research/strategies/ES_puts/backtest.py`
- `web/server.py`
- `web/templates/es_backtest.html`
- `notify/telegram_bot.py`
- `tests/test_spec_101.py`
- `task/SPEC-101.md`

## Key Behavior

- Adds `V2F_VIX_MIN_ENTRY = 22.0`.
- Adds `run_phase2_hvlad(...)`.
- Adds `/api/es-backtest/hvlad`.
- Adds `HV Ladder` tab on `/es-backtest`.
- Adds paper/shadow Telegram alert helper and JSONL logging to `data/q071_hv_paper_trades.jsonl`.
- Adds stale/missing VIX guard: no paper entry when VIX quote is absent or older than one day.

## Validation

- `arch -arm64 venv/bin/python -m unittest tests.test_spec_101 -v` PASS.
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_095 -v` PASS.
- `arch -arm64 venv/bin/python -m py_compile research/strategies/ES_puts/backtest.py web/server.py notify/telegram_bot.py` PASS.

## Local Metrics Check

`run_phase2_hvlad(start_date="2000-01-01", end_date="2026-04-17")`:

- trades: 146
- ann ROE: 1.14%
- Sharpe: 0.34
- MaxDD: -9.68%
- worst trade: -4.77% NLV
- active days: 21.4%
- bootstrap sig_rate: 100%

## Known Non-Blocking Regression Note

`tests.test_telegram_bot` has existing environment/mock fragility around broker-state mismatch and profit-target checks in intraday monitor tests. SPEC-101 does not change those paths; the SPEC-101 helper is covered directly in `tests/test_spec_101.py`.

## Deployment Notes

Deploy requires web and bot restart:

- web: serves `/api/es-backtest/hvlad` and `/es-backtest` tab
- bot: activates paper/shadow alert helper

No Cloudflare restart required.
