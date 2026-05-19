# SPEC-105 Handoff — Q074 Bull Regime Booster Overlay

**Date**: 2026-05-18
**Status**: DONE + deployed old Air in Stage 1 shadow
**Scope**: Q074 B4 moderate 90% booster overlay on SPEC-104 Arch-3

## Summary

SPEC-105 is implemented as a narrow additive overlay in `strategy/sleeve_governance.py`.

The implementation evaluates the Q074 B4 benign-regime booster signal and surfaces it through the governance API, dashboard, shadow log, and transition alert hook. Stage 1 shadow is the default and mandatory initial posture: booster can become `booster_shadow`, but effective production SPX cap remains `80%`.

## Files Changed

- `strategy/sleeve_governance.py`
- `web/templates/portfolio_home.html`
- `tests/test_spec_105.py`
- `task/SPEC-104.md`
- `task/SPEC-105.md`
- `task/SPEC-105_handoff.md`

Research artifacts added:

- `research/q074/`
- `task/q074_*_review_packet_2026-05-17*.md`
- `task/q074_*_review_packet_2026-05-18*.md`

## Implemented Behavior

- Added `CAP_SPX_BENIGN_BOOSTER = 90.0`.
- Added B4 gate:
  - no stress
  - no second-leg
  - SPX close > MA50
  - ddATH > `-4%`
  - VIX < `22`
  - VIX 5d change <= `+1.5`
  - IVP252 < `55`
- Added `active_spx_cap()` priority:
  - second-leg `40%`
  - stress `50%`
  - active booster `90%`
  - normal `80%`
- Default rollout mode is `shadow`, via `SPX_BENIGN_BOOSTER_MODE`.
- In shadow mode:
  - signal is visible as `booster_shadow`
  - shadow log writes to `data/q074_booster_shadow.jsonl`
  - effective production cap remains `80%`
- Dashboard shows:
  - active cap badge
  - booster status badge
  - individual condition chips
  - explicit Stage 1 shadow wording

## Explicit Non-Changes

- Did not modify SPEC-104 numeric caps:
  - normal `80%`
  - stress `50%`
  - second-leg `40%`
- Did not modify R5/R6 trigger definitions.
- Did not add B3 runtime toggle.
- Did not smooth snap-back behavior.
- Did not test or expose booster cap above `90%`.
- Did not change Q042 / HV Ladder / Q041 strategy semantics.

## Validation

Commands run locally:

```bash
arch -arm64 venv/bin/python -m unittest tests.test_spec_105 -v
arch -arm64 venv/bin/python -m unittest tests.test_spec_103 tests.test_spec_104 tests.test_spec_105 -v
arch -arm64 venv/bin/python -m py_compile strategy/sleeve_governance.py web/server.py
```

Results:

- `tests.test_spec_105` → 7/7 PASS
- `tests.test_spec_103 + tests.test_spec_104 + tests.test_spec_105` → 24/24 PASS
- `py_compile` → PASS

Q074 reproduction reference:

- Source: `research/q074/q074_p2_candidate_results.csv`
- Row: `B4_moderate_90`
- Net ROE: `8.2007%`
- MaxDD: `-8.715%`
- Worst 20d: `-7.042%`

These match AC-105-5 tolerance.

## Deployment Notes

Deployed to old Air with Stage 1 shadow posture. Do not set:

```bash
SPX_BENIGN_BOOSTER_MODE=active
```

unless PM approves a separate Stage 2 gate.

After deploy/restart:

1. Verify `/api/sleeve-governance/state` returns booster fields.
2. Verify Portfolio Command Center renders booster status / condition chips.
3. Confirm `active_spx_pm_cap_pct` remains `80%` when booster is shadow.
4. Restart only `com.spxstrat.web` and `com.spxstrat.bot`.
5. Refresh SPX / ES / Q041 backtest caches on old Air.

Deployment verification completed 2026-05-18:

- old Air HEAD: `c7f7da1`
- `com.spxstrat.web` restarted
- `com.spxstrat.bot` restarted
- `venv/bin/python -m unittest tests.test_spec_105 -v` → 7/7 PASS on old Air
- `booster_mode()` → `shadow`
- `CAP_SPX_PM / CAP_STRESS_EPISODE / CAP_SECOND_LEG_EPISODE / CAP_SPX_BENIGN_BOOSTER` → `80 / 50 / 40 / 90`
- `/api/sleeve-governance/state` → 200
- Current runtime payload:
  - `booster_mode = shadow`
  - `active_spx_pm_cap_pct = 80.0`
  - `active_spx_pm_cap_regime = normal`
  - `booster_active = false`
  - `booster_signal_conditions` present
- `/` Portfolio Command Center → 200 and contains booster panel markup
- `/api/recommendation` → 200
- `data/q074_booster_shadow.jsonl` write smoke PASS
- `scripts/refresh_backtest_caches.py` → 5/5 endpoints OK

## Follow-Up Risk

The live booster signal depends on current SPX cache, VIX quote, VIX history, and IVP252. If any input is unavailable, the gate fails closed via `warmed=false`, which is intended.
