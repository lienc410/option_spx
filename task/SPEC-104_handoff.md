# SPEC-104 Handoff — Q073 Arch-3 Portfolio Architecture

Date: 2026-05-17
Status: DONE locally; deploy/cache refresh required on old Air

## Summary

Implemented Q073 Arch-3 production posture:

- SPX governance caps: normal `80%`, stress `50%`, second-leg `40%`.
- Q042 Sleeve A Stage 1 cap: `12.5%`, with target metadata `17.5%`.
- Q042 Sleeve B remains research-only for production cap; paper draft sizing remains legacy `10%`.
- HV Ladder demoted to research-only / paper-only with production allocation `0%`.
- HV Ladder direct “Entry Signal” wording removed from production code.

## Files Changed

- `strategy/sleeve_governance.py`
- `strategy/q042_config.py`
- `strategy/q042_gate.py`
- `strategy/q042_sizing.py`
- `production/q042_positions.py`
- `notify/telegram_bot.py`
- `web/server.py`
- `web/templates/hvladder.html`
- `web/templates/q042.html`
- `web/templates/q042_backtest.html`
- `web/templates/portfolio_home.html`
- `tests/test_spec_102.py`
- `tests/test_spec_103.py`
- `tests/test_spec_104.py`
- `task/SPEC-104.md`

## Validation

- `arch -arm64 venv/bin/python -m unittest tests.test_spec_104 tests.test_spec_103 tests.test_spec_102 -v`
  - PASS, 20/20
- `arch -arm64 venv/bin/python -m py_compile strategy/sleeve_governance.py strategy/q042_config.py strategy/q042_gate.py strategy/q042_sizing.py production/q042_positions.py web/server.py notify/telegram_bot.py tests/test_spec_104.py tests/test_spec_103.py tests/test_spec_102.py`
  - PASS
- `arch -arm64 venv/bin/python main.py --dry-run`
  - PASS
- `rg -n "Entry Signal" notify web strategy production`
  - zero hits

## Deploy Notes

After push and old Air pull:

1. Restart `com.spxstrat.web` and `com.spxstrat.bot`.
2. Verify:
   - `/api/sleeve-governance/state` caps show `80 / 50 / 40`.
   - `/api/q042/state` shows Sleeve A cap `12.5`, target `17.5`.
   - `/api/hvladder/live` shows `production_status=research_only`, `production_allocation_pct=0.0`, `execution_allowed=false`.
   - `/hvladder` page shows research-only / paper-only banner.
3. Run `venv/bin/python scripts/refresh_backtest_caches.py` on old Air after restart.

## Known Limits

- Local cache refresh did not run because local Flask was not listening on `localhost:5050`; old Air is the canonical place to refresh runtime caches.
- SPX normal-to-stress transition loss monitor is a fail-soft placeholder until enough live transition ledger data exists.
