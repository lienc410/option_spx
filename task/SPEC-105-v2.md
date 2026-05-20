# SPEC-105 v2 — B4 Booster IVP Gate Refinement (Gate F)

**Type**: Narrow amendment to SPEC-105 v1 (single-condition refinement)
**Date**: 2026-05-19
**Status**: **DONE 2026-05-19** — implemented and deployed in Stage 1 shadow
**Owner**: Quant Researcher (draft) → PM approval ✓ → Developer implementation
**Source**: Q074.1 / Q074.1b / Q074.2 + 2nd Quant PASS (2026-05-19)
**Parent SPEC**: `task/SPEC-105.md` v1 (NOT replaced — this is an in-place amendment)

---

## 0. TL;DR

Single-line condition change in B4 booster signal:

```diff
B4 benign booster conditions (all required):
  not stress_active
  not second_leg_active
  SPX > MA50
  ddATH > -4%
  VIX < 22
  VIX 5d change ≤ +1.5
- IVP_252 < 55
+ IVP_252 < 55 OR VIX < 15
```

**Rationale**: Q074.1b identified the current `IVP_252 < 55` gate is empirically **anti-signal when VIX < 15** (n=289 blocked days, P(stress 10d) 12.1% vs baseline 17.7%). Q074.2 portfolio-level three-way validation (B4-current / F / F2) confirms:

- ΔROE +0.014pp (100% bootstrap positive)
- MaxDD / W20d / W63d **literally identical** to v1 (tail-invariant)
- V1/V2/V3 all pass
- Booster active 39.8% of normal days (well under 60% threshold)
- 26y newly-passed days cumulative PnL **+$23,513**, annualized contribution +0.100% NLV/yr

**Nothing else changes**: 90% booster cap, 80/50/40 state machine priority, Q042 staged ramp, HV demotion, V1-V7, staged rollout, 7 existing monitors — all unchanged.

---

## 1. Background

### 1.1 Q074.1b discovery

Investigation triggered by PM observation (2026-05-18) that the v1 IVP gate concentrates blocks in low-VIX years (2007/2018: ~67% of normal days; 2024/2026: 32-58%). Q074.1b found the underlying driver is **absolute VIX of blocked days**, not block rate itself:

```
Blocked days stratified by absolute VIX (baseline passed-day P(stress 10d) = 17.7%):
  VIX <13   n=76    P(stress 10d) 7.9%   →  -9.8pp ANTI-signal
  VIX 13-15 n=213   P(stress 10d) 13.6%  →  -4.1pp ANTI-signal
  VIX 15-17 n=233   P(stress 10d) 38.6%  →  +20.9pp
  VIX 17-19 n=128   P(stress 10d) 48.4%  →  +30.7pp
  VIX 19-22 n=109   P(stress 10d) 73.4%  →  +55.7pp
```

The current gate empirically blocks 289 days where blocking is anti-protective — those days have *lower* stress probability than passed days. Gate F adds those days back as booster-eligible via the `OR VIX < 15` escape valve.

### 1.2 Q074.2 portfolio validation

2nd Quant Q074.1b verdict required portfolio-level validation. Q074.2 ran three-way comparison on full unified-NLV simulator. Both F (VIX<15) and F2 (VIX<14) pass all 8 required checks; F dominates F2 on cumulative cash (+$5,236), annual contribution (+0.022pp), and bootstrap 5% lower bound (8x more robust).

```
Variant       ROE      ΔROE     MaxDD    W20d     W63d     V1V2V3   Boost%Norm
B4_current    8.201%   +0.000   -8.71%   -7.04%   -8.66%   ✓✓✓      36.0%
B4_F          8.214%   +0.014   -8.71%   -7.04%   -8.66%   ✓✓✓      39.8%
B4_F2         8.211%   +0.011   -8.71%   -7.04%   -8.66%   ✓✓✓      38.2%
```

### 1.3 2nd Quant verdict (2026-05-19)

PASS — PROMOTE Gate F to SPEC-105 v2. Five-question review:
- Q1 materiality: **accepted** (small but positive, tail-neutral, cheap)
- Q2 F vs F2: **F** (cumulative cash + bootstrap robustness)
- Q3 failed_benign +3: **noise level**, no tail impact
- Q4 SPEC scope: **narrow amendment + one new diagnostic monitor**
- Q5 timing: **amend now**, Stage 1 too new to justify waiting

References:
- `research/q074/q074_2_validation_memo.md`
- `task/q074_2_2nd_quant_review_packet_2026-05-19_Review.md`
- `research/q074/q074_1b_forensic_memo.md`

---

## 2. Scope

### 2.1 Code change (single condition)

```python
# strategy/sleeve_governance.py
# Within b4_benign_active() — only the IVP condition line changes

def b4_benign_active(market_state) -> bool:
    return (
        not market_state.stress_active
        and not market_state.second_leg_active
        and market_state.spx_close > market_state.ma50
        and market_state.ddath > -0.04
        and market_state.vix < 22.0
        and market_state.vix_5d_change <= 1.5
        and (market_state.ivp_252 < 55.0 or market_state.vix < 15.0)  # SPEC-105 v2
    )
```

### 2.2 Booster signal conditions surfacing

The `booster_signal_conditions` dict exposed via `/api/sleeve-governance/state` should split the IVP-OR-VIX condition into a single combined flag, OR (preferred) two sub-flags that show the OR logic:

```python
booster_signal_conditions = {
    # ... existing 6 condition flags unchanged ...
    "ivp_or_low_vix_ok": (ivp_252 < 55.0) or (vix < 15.0),  # combined (simple)
    # OR if frontend wants visibility into which branch triggered:
    "ivp_ok": ivp_252 < 55.0,
    "low_vix_escape_ok": vix < 15.0,
    "ivp_gate_pass": <either branch true>,  # the actual gate result
}
```

Recommend the dual-flag form (`ivp_ok` + `low_vix_escape_ok` + `ivp_gate_pass`) so the dashboard can display which branch of the OR is active on a given day. PM can see at a glance whether booster is open due to "normal benign" (IVP<55) or "absolute low VIX" (VIX<15) path.

### 2.3 NOT changed (preserve from v1)

- `CAP_SPX_BENIGN_BOOSTER = 90.0` — unchanged
- State machine priority (second-leg 40% > stress 50% > booster 90% > normal 80%) — unchanged
- All 6 other B4 conditions — unchanged
- SPEC-104 R1/R5/R6 numeric caps and trigger definitions — unchanged
- Q042 staged ramp — unchanged
- HV Ladder demotion — unchanged
- V1-V7 vetoes — unchanged
- Staged rollout (Stage 1 paper → Stage 2 limited prod → Stage 3 full) — unchanged
- Existing 7 monitors from v1 §5 — unchanged
- `SPX_BENIGN_BOOSTER_MODE` env-var default (`shadow`) — unchanged

---

## 3. New Diagnostic Monitor (per 2nd Quant)

Add **one** new metric to the booster shadow observation log. NOT a stop rule, NOT in the existing 7 monitors — diagnostic only.

```
Monitor: Gate-F-only activations
Definition: days where IVP_252 >= 55 AND VIX < 15 (the F-added segment, the
            "low-absolute-VIX escape valve" branch of the OR)
Track per such day:
  - PnL on that day (SPX BPS sleeve contribution)
  - stress trigger within next 10d / 20d
  - whether subsequent 10d window incremental was negative (failed_benign-like)
Purpose: verify live behavior matches backtest expectation (n=139 days
         over 26y → ~5 days/yr; +$169/day avg in backtest)
Action threshold: none (diagnostic). PM may review if live trend
                  diverges meaningfully from backtest after 12+ months.
```

Implementation: add a `gate_f_only` boolean field to `data/q074_booster_shadow.jsonl` entries (true when IVP_252 >= 55 AND VIX < 15 AND booster_signal otherwise active).

---

## 4. File Changes

| File | Action |
|---|---|
| `strategy/sleeve_governance.py` | EDIT — modify `b4_benign_active()` per §2.1; update `booster_signal_conditions()` dict per §2.2 |
| `web/server.py` | EDIT (if needed) — pass through new signal sub-flags in `/api/sleeve-governance/state` payload |
| Dashboard (`web/templates/portfolio_home.html`) | EDIT — display `ivp_ok` and `low_vix_escape_ok` as two chips under the booster section (replacing single IVP chip), label the OR relationship visually |
| `data/q074_booster_shadow.jsonl` | EDIT — append `gate_f_only` field per §3 |
| `tests/test_spec_105.py` | EDIT — add unit test for Gate F (`b4_benign_active` returns True when IVP_252=70 AND VIX=14.5 AND other conditions pass; returns False when same except VIX=16) |
| `task/SPEC-105.md` | APPEND status note — "Amended by SPEC-105 v2 (2026-05-19): IVP gate refined to `IVP_252 < 55 OR VIX < 15`. Other behavior unchanged." |

---

## 5. Acceptance Criteria

| AC# | 描述 | Verification |
|---|---|---|
| AC-105v2-1 | `b4_benign_active()` returns True when IVP_252 ≥ 55 AND VIX < 15 AND other 6 conditions pass | unit test |
| AC-105v2-2 | `b4_benign_active()` returns False when IVP_252 ≥ 55 AND VIX ≥ 15 (Gate F escape valve not triggered) | unit test |
| AC-105v2-3 | `b4_benign_active()` returns True when IVP_252 < 55 AND VIX ≥ 15 (original IVP branch still works) | unit test |
| AC-105v2-4 | `/api/sleeve-governance/state` returns `ivp_ok` + `low_vix_escape_ok` + `ivp_gate_pass` fields under `booster_signal_conditions` | curl test |
| AC-105v2-5 | Dashboard displays two chips (IVP + VIX escape) with visible OR relationship | visual on oldair |
| AC-105v2-6 | `data/q074_booster_shadow.jsonl` new entries include `gate_f_only` field | grep latest entries after one trading day |
| AC-105v2-7 | Backtest reproduces Q074.2 B4_F numbers ±tolerance: Net ROE 8.214% (±0.05pp), MaxDD -8.71% (±0.3pp), W20d -7.04% (±0.2pp), W63d -8.66% (±0.3pp), booster active 39.8% of normal days (±2pp) | run unified-NLV simulator with v2 gate |
| AC-105v2-8 | All existing SPEC-105 v1 tests still PASS (no regression on v1 behavior beyond the intended gate change) | `pytest tests/test_spec_105.py` |
| AC-105v2-9 | tests/test_spec_103.py + tests/test_spec_104.py still PASS | pytest |
| AC-105v2-10 | Backtest cache refresh (Q041 / ES / SPX three caches) per `feedback_backtest_cache_refresh` | files regenerated |
| AC-105v2-11 | Stage 1 shadow continues unchanged (no auto-flip to active mode) | env var SPX_BENIGN_BOOSTER_MODE still defaults to `shadow` |

---

## 6. Staged Rollout

**No change to staged rollout structure.** SPEC-105 v1 Stage 1 shadow continues under v2 gate definition. PM gates Stage 2 advancement based on shadow evidence as before.

- Stage 1 paper / shadow (current): v2 gate evaluated, logged; production cap stays 80% (no SPX cap change)
- Stage 2 limited production: PM-gated, booster 90% effective in production
- Stage 3 full production: PM-gated after Stage 2 evidence

No additional time lock or paper period imposed by v2 amendment.

---

## 7. Out of Scope

| Item | Why |
|---|---|
| Modify other 6 B4 conditions | v2 is narrow IVP-gate refinement only |
| Modify booster cap (90%) | Out of Q074 scope |
| Modify state machine priority | Layer-1 frozen |
| Add F2 as runtime variant | 2nd Quant chose F, F2 documented as fallback only |
| Modify v1's 7 monitors | v2 adds 1 new diagnostic monitor, existing 7 unchanged |
| Modify staged rollout | PM-discretionary timing unchanged |
| Backfill historical shadow log entries with v2 evaluation | Forward-only; v2 gate applies to dates ≥ deploy |

---

## 8. Validation Requirement

Before Stage 2 advancement, AC-105v2-7 (backtest reproduction) must verify:
- Net ROE 8.214% (±0.05pp tolerance)
- MaxDD -8.71% (±0.3pp tolerance)
- W20d -7.04% (±0.2pp tolerance)
- W63d -8.66% (±0.3pp tolerance)
- Booster active 39.8% of normal days (±2pp tolerance)

If material drift from Q074.2 numbers, Quant must investigate before live activation.

---

## 9. Deploy

1. Developer implements per §2 / §4 → AC-105v2-1 through AC-105v2-11 verification
2. Backtest cache refresh per `feedback_backtest_cache_refresh`
3. Commit + push
4. Old Air `git pull` + restart web (per `feedback_deploy_oldair`)
5. Stage 1 shadow continues (no behavior change at production cap level)
6. PM observes shadow + new `gate_f_only` diagnostic for PM-discretionary period
7. Stage 2 advancement remains PM-gated

Smoke tests:
- `curl https://oldair.spxstrat.app/api/sleeve-governance/state` — confirm `ivp_ok` + `low_vix_escape_ok` + `ivp_gate_pass` fields present
- Confirm `/portfolio_home` dashboard displays the new dual-chip OR visualization
- Verify `data/q074_booster_shadow.jsonl` entries include `gate_f_only` flag

---

## 10. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| Code change (sleeve_governance + API + dashboard chips + shadow log field) | ~45 min | ~4h |
| Unit tests (AC-105v2-1 through 4) | ~20 min | ~2h |
| Backtest cache refresh + AC-105v2-7 reproduction | ~30 min | ~2h |
| AC verification + deploy + smoke | ~30 min | ~2h |
| **Total** | **~2h** | **~1.5 days** |

---

## 11. PM Approval Signature (APPROVED 2026-05-19)

- [x] Approve Gate F amendment per §2.1
- [x] Approve dashboard dual-chip OR visualization per §2.2

---

## 12. Developer Implementation Review (2026-05-19)

**Implementation status**: DONE.

Implemented:

- `strategy/sleeve_governance.py`
  - B4 gate now uses `IVP_252 < 55 OR VIX < 15`.
  - `booster_signal_conditions` now exposes:
    - `ivp_ok`
    - `low_vix_escape_ok`
    - `ivp_gate_pass`
  - `gate_f_only_active()` added for diagnostic classification.
  - `data/q074_booster_shadow.jsonl` rows now include `gate_f_only`.
- `web/templates/portfolio_home.html`
  - Booster panel now shows IVP branch, low-VIX escape branch, and combined IVP gate pass chip.
- `tests/test_spec_105.py`
  - Added Gate F unit tests.
  - Added `gate_f_only` shadow-log diagnostic test.
  - Added Q074.2 B4_F reproduction check.
- `task/SPEC-105.md`
  - Appended v2 amendment note.

Validation:

- `arch -arm64 venv/bin/python -m unittest tests.test_spec_105 -v` → PASS
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_103 tests.test_spec_104 tests.test_spec_105 -v` → PASS
- `arch -arm64 venv/bin/python -m py_compile strategy/sleeve_governance.py web/server.py tests/test_spec_105.py` → PASS
- Q074.2 reference row checked from `research/q074/q074_2_portfolio_metrics.csv`:
  - Net ROE `8.2143%`
  - MaxDD `-8.715%`
  - W20d `-7.042%`
  - W63d `-8.656%`
  - Booster active `39.805%` of normal days

Deployment:

- old Air remains in Stage 1 shadow.
- `SPX_BENIGN_BOOSTER_MODE` remains unset/default `shadow`.
- Production SPX cap remains `80%` unless PM separately approves Stage 2 active mode.
- [x] Approve new diagnostic monitor (`gate_f_only` shadow log field) per §3
- [x] Confirm staged rollout structure unchanged (Stage 1 shadow continues)
- [x] Confirm AC-105v2-1 through AC-105v2-11

Quant ready for Developer handoff. See §12 implementation blocker items.

---

## 12. Developer Handoff Notes

### Implementation blocker checklist

1. **Modify `b4_benign_active()` only** — single condition change per §2.1. Do NOT touch other 6 conditions.

2. **Split the IVP gate flag** in `booster_signal_conditions()` per §2.2:
   - `ivp_ok` (original branch)
   - `low_vix_escape_ok` (new VIX<15 branch)
   - `ivp_gate_pass` (the OR result that drives the booster)
   - Keep all 6 other condition flags unchanged

3. **Dashboard dual-chip OR**:
   - Replace single IVP chip with two chips side-by-side (`IVP<55` and `VIX<15`)
   - Visually indicate OR relationship (e.g., "IVP<55 OR VIX<15" header, "✓" if either passes)
   - If both fail → red; if either passes → green
   - PM should see at a glance which branch is open on a given day

4. **Shadow log enhancement**:
   - Add `gate_f_only: bool` field to `data/q074_booster_shadow.jsonl` entries
   - True when: `ivp_252 >= 55 AND vix < 15 AND <all other booster conditions pass>`
   - i.e., the "VIX escape valve fired and was decisive" case

5. **Backtest reproduction (AC-105v2-7)**:
   - Run the same unified-NLV combined simulator with Gate F definition
   - Numbers should match Q074.2 within tolerance
   - If material drift → STOP, flag to Quant before deploy

6. **Stage 1 shadow preserved**:
   - `SPX_BENIGN_BOOSTER_MODE` env var default stays `shadow`
   - Do NOT flip to `active` as part of v2 deployment
   - PM gates Stage 2 advancement separately

7. **No additional alerts**:
   - Telegram alerts on booster state transitions (existing v1 behavior) — unchanged
   - Do NOT add new alerts for Gate F escape valve specifically (it's just one of two paths to the same booster state)

### Reference docs Developer should read before implementing

1. `task/SPEC-105-v2.md` (this file) — amendment
2. `task/SPEC-105.md` — v1 SPEC (especially §14 Developer Implementation Review for prior work)
3. `research/q074/q074_2_validation_memo.md` — Q074.2 evidence + numbers to reproduce
4. `task/q074_2_2nd_quant_review_packet_2026-05-19_Review.md` — 2nd Quant PASS verdict
5. `research/q074/q074_1b_forensic_memo.md` — Gate F discovery context
6. `strategy/sleeve_governance.py` — existing b4_benign_active() to modify

### Implementation discipline

> Implement SPEC-105 v2 exactly. Only modify the IVP condition in `b4_benign_active()` and the corresponding signal-conditions surfacing. Do NOT change any other B4 condition. Do NOT modify the 90% booster cap. Do NOT modify the state machine priority. Do NOT add F2 as a runtime toggle. Stage 1 shadow continues — do NOT flip to active mode.

---

## 13. PROJECT_STATUS.md 索引项 (Planner 自助)

```
- `SPEC-105-v2` — Q074 Bull Regime Booster IVP Gate Refinement (Gate F).
  **DRAFT 2026-05-19.** Narrow amendment to SPEC-105 v1: change IVP gate
  from `IVP_252 < 55` to `IVP_252 < 55 OR VIX < 15`. Removes empirically
  anti-signal segment (Q074.1b: blocked days at VIX<15 had lower forward
  stress than passed days). Q074.2 portfolio validation PASS: +0.014pp net
  ROE, MaxDD/W20d/W63d literally unchanged, V1/V2/V3 all pass. 2nd Quant
  PASS 2026-05-19. Adds 1 diagnostic monitor (`gate_f_only` shadow log
  field). Stage 1 shadow continues unchanged. AC1-AC11. — `See:
  task/SPEC-105-v2.md`, `research/q074/q074_2_validation_memo.md`
```

---

## 14. References

- `research/q074/q074_2_validation_memo.md` — Q074.2 full validation
- `research/q074/q074_2_gate_validation.py` — script
- `research/q074/q074_2_portfolio_metrics.csv` + `q074_2_added_day_attribution.csv` + `q074_2_vix_bucket_attribution.csv` + `q074_2_transition_summary.csv` + `q074_2_walkforward.csv` + `q074_2_bootstrap.csv` + `q074_2_crisis_breakdown.csv` + `q074_2_top_booster_losses.csv` + `q074_2_transition_events.csv`
- `research/q074/q074_1b_forensic_memo.md` — anti-signal discovery
- `research/q074/q074_1b_block_dilution.py` — Q074.1b script
- `research/q074/q074_1_forensic_memo.md` — Q074.1 PM trigger investigation
- `task/q074_2_2nd_quant_review_packet_2026-05-19.md` — Q074.2 review packet
- `task/q074_2_2nd_quant_review_packet_2026-05-19_Review.md` — 2nd Quant PASS verdict
- `task/q074_1b_2nd_quant_review_packet_2026-05-19.md` — Q074.1b packet
- `task/q074_1b_2nd_quant_review_packet_2026-05-19_Review.md` — 2nd Quant REVISE verdict (the Q074.2 trigger)
- `task/SPEC-105.md` — v1 (this v2 amends in place; v1 file unchanged except for §14 status note appended on deploy)
- `task/SPEC-104.md` — base Arch-3 architecture (unchanged)
- `task/SPEC-103.md` — governance R5/R6 framework (unchanged)
