# SPEC-108.1 Developer Handoff

**Commit**: `221ef5c`
**Deployed**: 2026-05-29 (Old Air, commit confirmed via git pull)
**Status**: All 13 ACs PASS; all 39 parent SPEC regressions PASS

---

## Files Modified

| File | Action | Key change |
|---|---|---|
| `strategy/sleeve_governance.py` | EDIT | `LADDER_V1B_MODE_DEFAULT`, `ladder_v1b_mode()`, `_bs_put()`, `portfolio_stress_overnight_gap()`, `ladder_v1b_shadow_decision_payload()`, `_ladder_v1b_state_fields()`, updated `current_governance_state()` + `record_state_snapshot()` |
| `strategy/q078_ladder_v1b.py` | **NEW** | V1b weekly Wed anchor ladder; `LadderV1bState`, `v1b_ladder_eligible()`, `production_order_allowed_v1b()`, shadow log functions |
| `strategy/q078_ladder_monitors.py` | **NEW** | `strategy_distribution_check()` — rolling 90d strategy distribution drift, historical bands from 26y CSV |
| `notify/telegram_bot.py` | EDIT | `_format_ladder_v1b_shadow_message()`, V1b branch in `scheduled_ladder_shadow_push()`, drift line in `scheduled_eod_push()` |
| `web/templates/portfolio_home.html` | EDIT | V1b panel CSS + JS below V3 panel; drift chip on V3 panel head |
| `task/SPEC-108.md` | EDIT | §6 Stage 2 advancement gate — added condition #8 (stress gate) + #9 (regime/strategy coverage R3) |
| `task/SPEC-108.1.md` | NEW | This revision SPEC |
| `tests/test_spec_108_1.py` | **NEW** | 13 ACs × 40 test methods |

---

## R1 — Portfolio Stress Gate

**Function**: `strategy.sleeve_governance.portfolio_stress_overnight_gap(state)`

**Logic**: SPX -7%, IV ×1.5 → BS reprice each open put spread leg → aggregate mark-loss % NLV. gate_pass = mark_loss < 12%.

**Behaviour by mode**:
- `shadow`: computes, attaches to payload as `portfolio_stress_gate`, does NOT block
- `active`: if gate_pass=False → eligible=False, skip_reason="portfolio_stress_block"

**Safe fallback**: any exception → `{mark_loss=0, gate_pass=True, source="safe_fallback"}` + error log.

---

## R2 — V1b Parallel Shadow

**Files**: `strategy/q078_ladder_v1b.py`, `data/q078_ladder_v1b_shadow.jsonl` (runtime), `data/q078_ladder_v1b_runtime.json` (runtime)

**Cadence**: Wednesday only (`weekday == 2`). Non-Wed → `not_weekly_anchor`. No catch-up.

**Env var**: `LADDER_V1B_MODE` (default `shadow`). Set `LADDER_V1B_MODE=active` to enable production (Stage 2 V1b signoff required).

**Mutual exclusion**: `production_order_allowed_v1b()` checks `_v3_mode() == "active"` → if both active, logs warning + returns False.

**API fields added**: `ladder_v1b_mode`, `ladder_v1b_last_entry_date`, `ladder_v1b_cadence_eligible`, `ladder_v1b_strategy_eligible`, `ladder_v1b_concurrency_block`, `ladder_v1b_bp_ceiling_block`, `ladder_v1b_skip_reason`, `ladder_v1b_active_positions`, `ladder_v1b_active_total_bp`, `ladder_v1b_action_days_ytd`, `ladder_v1b_would_enter`

---

## R3 — Stage 2 Gate Text Update

`task/SPEC-108.md` §6 Stage 2 advancement gate now has 9 conditions (was 7):
- #8: `portfolio_stress_overnight_gap()` mark_loss < 12% NLV  
- #9: regime/strategy coverage profile (i/ii/iii) OR PM waiver

---

## R4 — Drift Monitor

**File**: `strategy/q078_ladder_monitors.py`

**Historical bands** (derived from `research/q078/_signal_history_cache.csv`, 3119 PASS days, NOT spec estimates):

| Strategy | Actual % | Band |
|---|---|---|
| bull_call_diagonal | 56.0% | 51–61% |
| iron_condor_hv | 19.5% | 14.5–24.5% |
| iron_condor | 9.5% | 4.5–14.5% |
| bull_put_spread_hv | 9.3% | 4.3–14.3% |
| bull_put_spread | 3.1% | 0–8.1% |
| bear_call_spread_hv | 2.6% | 0–7.6% |

**Deviation trigger**: > 15pp from band edge.

**API fields**: `ladder_strategy_drift_alert` (bool), `ladder_strategy_distribution_90d` (dict), `ladder_strategy_drift_detail` (dict)

---

## Test Results

```
tests/test_spec_108_1.py   40 passed  (40/40 AC-108.1-1 to -13)
tests/test_spec_108.py     10 passed  (18 original ACs — no regression)
tests/test_spec_103.py      9 passed
tests/test_spec_104.py      7 passed
tests/test_spec_105.py     13 passed
─────────────────────────────
Total                       79 passed
```

---

## Smoke Test (oldair 2026-05-29)

```
curl /api/sleeve-governance/state | jq '.state.ladder_v1b_mode'     → "shadow"
curl /api/sleeve-governance/state | jq '.state.ladder_strategy_drift_alert' → false
curl /api/sleeve-governance/state | jq '.state.portfolio_stress_gate.gate_pass' → true
```

---

## Standing Obligations (post-deploy)

- **V1b shadow stream running**: check `data/q078_ladder_v1b_shadow.jsonl` populates on next Wed selector PASS
- **Drift monitor**: check `ladder_strategy_drift_alert` in API weekly
- **Stage 2 V3 unfreeze criteria** (per SPEC-108.md §6):
  - condition #8: stress gate < 12% NLV ✓ (computed daily)
  - condition #9: regime/strategy coverage — needs live shadow entries across ≥2 VIX regimes or ≥2 strategy branches
- **V1b production promotion**: separate PM signoff; DO NOT activate until Stage 2 V1b review

---

## Notes

- Spec-estimated strategy bands (BPS 45-55%) were significantly wrong vs actual data (BPS 3.1%); used actual 26y measured distribution per Developer Prompt instructions.
- `bull_call_diagonal` is the dominant strategy at 56% — not `bull_put_spread` as originally estimated.
- Backtest cache not refreshed (no algorithm or param change; R1-R4 are monitoring/gate additions only; no P&L impact on existing backtest results).

---

待 Quant Researcher review，结论写回 `task/SPEC-108.1.md` `## Review` 字段。
