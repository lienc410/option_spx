# SPEC-093 Handoff

Status: DONE

## Scope Delivered

Implemented Q041 matrix/backtest surface refresh with existing data sources only:

- `GET /api/q041/overview` aggregate read-only payload
- `/q041` strategy matrix refresh
- `/q041/backtest` chart expansion
- no broker reads/writes added
- no Q041 recommendation or paper-ledger write-path changes

## Files Changed

- `web/server.py`
- `web/templates/q041.html`
- `web/templates/q041_backtest.html`
- `tests/test_spec_093.py`
- `task/SPEC-093.md`

## Key Delivery Notes

### Strategy Matrix

- Tier 1 `SPX CSP` is rendered as a gray `ELIMINATED` card
- Tier 2 `GOOGL / AMZN CSP` remains active and carries a visible tail-caveat banner
- Tier 3 `COST / JPM` remains review-only / observe-only
- core metrics are sourced from existing backtest payload + attribution artifact
- Tier 2 paper progress is shown against goal `20`
- Tier 1 progress is intentionally not shown

### Backtest Page

- cumulative P&L chart now supports historical curves plus paper curves when ledger data exists
- VIX regime distribution added
- IV-at-entry distribution carrier added with fail-soft empty state when paper data is unavailable
- P&L by DTE at close uses backtest data and is explicitly labeled
- BP utilization timeline added with main-strategy overlay toggle

## Fail-Soft Behavior

- missing `data/q041_paper_trades.jsonl` does not break `/q041` or `/q041/backtest`
- overview route returns structured fallback JSON on failure
- charts that need paper data degrade to empty-state text instead of breaking page render

## Verification

- `arch -arm64 venv/bin/python -m py_compile web/server.py tests/test_spec_093.py`
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_093 -v`
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_085 tests.test_state_and_api -v`
- `git diff --check -- web/server.py web/templates/q041.html web/templates/q041_backtest.html tests/test_spec_093.py task/SPEC-093.md task/SPEC-093_handoff.md`

## Follow-up / Known Limits

- current repo state does not include live `data/q041_paper_trades.jsonl`, so paper-dependent charts render in fail-soft / zero-sample mode
- Tier 3 does not enter executable candidate logic and has no dedicated backtest sleeve in this delivery
- this spec does not change nav architecture outside existing Q041 entry points already present in the app
