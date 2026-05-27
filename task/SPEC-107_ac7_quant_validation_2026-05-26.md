# SPEC-107 AC7 — Quant Validation & Joint Resolution

**Date**: 2026-05-26
**Author**: Quant Researcher
**Subject**: AC7 12mo replay drift root-cause analysis and fixes
**Status**: **AC7 PASS** after 3 bug fixes. SPEC-107 ready for DONE/deploy.

---

## TL;DR

Developer's initial AC7 replay missed the P3 envelope (flips=101, ≤3h=7, RT=24). After Quant root-cause diagnosis, three structural bugs in `strategy/intraday_governance.py` were identified and fixed. Re-run AC7 now PASSES all 4 metrics, hitting P3's 93.2% EOD agreement exactly.

| Metric | P3 envelope | Dev v1 | After Quant fix | Status |
|---|---|---|---|---|
| `intraday_flips` | 93 ± 5 (88-98) | 101 | **92** | ✅ PASS |
| `episodes_le_3h` | ≤ 4 | 7 | **3** | ✅ PASS |
| `round_trips` | 18 ± 2 (16-20) | 24 | **20** | ✅ PASS |
| `eod_agreement_pct` | ≥ 92% | 96.8% | **93.2%** | ✅ PASS |

`tests/test_spec_107.py` 11/11 PASS. Adjacent SPEC suites (103/104/105/106) regression 42/42 PASS. Combined 53/53 PASS.

---

## 3 Bugs Identified

### Bug 1: Entry-band else clause emitted `governed = baseline_strategy`

**Location**: `strategy/intraday_governance.py` `_apply_hysteresis` final `else` clause.

**Symptom**: When `prev=WAIT`, `baseline=Bull Put Spread`, but IVP outside entry band [42, 53] (e.g., IVP=53.8), code emitted `governed = baseline_strategy = "Bull Put Spread"` — opening BPS in violation of SPEC-107 §A entry band.

**Fix**:
```python
else:
    new = "WAIT"
    # SPEC-107 §A: refuse BPS open when IVP outside [42, 53]. If baseline
    # pushes BPS but entry band rejects, governed must be Wait, NOT baseline.
    # Only defer to baseline when baseline itself is not BPS (e.g., IC, BCD).
    governed = _wait_strategy() if baseline_is_bps else baseline_strategy
```

**Impact**: Eliminated 2-4 spurious BPS opens per quarter where IVP barely outside entry band but baseline still pushed BPS.

---

### Bug 2: `_state_key` used `rec.underlying` fallback → key drift on baseline regime change

**Location**: `_state_key` function.

**Symptom**: When baseline switched from "Bull Put Spread" (rec.underlying = "SPX") to "Reduce / Wait" (rec.underlying = "—"), the state key changed from `spx|SPX|...` to `spx|—|...`. State lookup at next bar missed → `prev` defaulted to "WAIT" → hysteresis lost memory of BPS hold.

**Fix**:
```python
def _state_key(rec, position=None):
    # SPEC-107 govern SPX intraday recs only. Underlying must be a constant
    # ("SPX") for state-key stability, NOT rec.underlying which flips to "—"
    # when baseline turns to "Reduce / Wait".
    position = position or {}
    account = str(position.get("account") or "spx")
    underlying = str(position.get("underlying") or "SPX")  # constant fallback
    strategy = str(position.get("strategy_key") or "bull_put_spread")
    return "|".join([account, underlying, strategy])
```

Also removed `position_id` from key (per Bug 3 below).

**Impact**: Recovered ~10-15 lost-state events per year where baseline temporarily switched to Wait while position was still open.

---

### Bug 3: State coupled to `active_position` + `position_id` in key

**Location**: `_state_key` + `_apply_hysteresis` initial branch.

**Symptom**: Two-fold:

1. `_state_key` included `position_id` (= `trade_id`). State key at "no position" = `...|no-position`; at "position open with trade_id=T1" = `...|T1`. Different keys → state lookup never found.

2. `_apply_hysteresis` initial branch:
   ```python
   if not active_position:
       positions.pop(key, None)
       prev = "WAIT"
   ```
   This **purged hysteresis state whenever broker position was closed**. But SPEC-107 §A hysteresis must persist independent of broker lifecycle — at sched bar 10:30 we decide "open BPS" BEFORE broker opens position; state must be storable at that moment.

**Fix**:

State key now: `(account, underlying, strategy)` — no position_id (only one BPS-Normal position at a time on SPX, so position_id offers no disambiguation).

State read independent of position:
```python
positions = state_payload.setdefault("positions", {})
prev = str((positions.get(key) or {}).get("state") or "WAIT")
```

State write controlled by hysteresis output:
```python
if new == "WAIT":
    positions.pop(key, None)
else:
    positions[key] = {"state": new, "updated_at": ...}
```

**Impact**: This was the dominant drift source. Recovered the bulk of P3-aligned hold periods that were getting prematurely re-evaluated.

---

## Why These Bugs Were Subtle

Each bug looked locally reasonable:

- Bug 1: "When baseline says BPS, emit BPS" — but ignored entry-band gate
- Bug 2: "Fall back to rec.underlying" — looked defensive, but rec.underlying is regime-dependent
- Bug 3: "Position-keyed state for multi-position support" + "purge state when no position" — defensible for general portfolio tracking, but over-engineered for SPEC-107's single-strategy hysteresis

P3 simulator (Q076 P3 replay) doesn't have these because it tracks hysteresis as pure state machine over output sequence, with no position/key concept. Replicating that semantic in production code required collapsing the keying and decoupling from broker activity.

---

## Test Updates

Two tests in `tests/test_spec_107.py` had assertions encoding the previous behavior:

1. `test_entry_band_allows_bps_only_when_baseline_bps`: previously asserted `persisted["positions"] == {}` (state NOT stored when no position). Updated to verify state IS persisted with BPS regardless of position — matches corrected design.

2. `test_hold_band_preserves_active_bps_state`: fixture wrote state under key `spx|SPX|bull_put_spread|T1` (old position_id format). Updated to new key `spx|SPX|bull_put_spread`.

All 11 SPEC-107 tests pass after updates. AC8 HIGH_VOL/STRESS regression tests (already in place) still pass — invariant intact.

---

## Files Touched

```
strategy/intraday_governance.py
  - _state_key: drop position_id from key; constant underlying fallback
  - _apply_hysteresis: read state independent of active_position; entry-band else clause emits Wait correctly; persist state when new != WAIT regardless of active_position

tests/test_spec_107.py
  - Two assertions updated to match corrected design

research/intraday/q076_ac7_replay.py  (new — AC7 verification harness)
research/intraday/q076_ac7_replay.csv (new — full 12mo bar-by-bar replay output)
```

---

## Recommendation

1. **SPEC-107 should be marked DONE** by Developer after applying the 3 fixes above (already in repo, awaiting commit + push)
2. **Deploy old Air** per `task/SPEC-107_handoff.md` Implementation Plan F7
3. **Frontend / Telegram** unchanged — no further work needed
4. **Decision log retrospective** scheduled at 30 days post-deploy per SPEC §Deferred Validation 1

---

## Joint Validation Sign-off

| Track | Owner | Result |
|---|---|---|
| F1 Hysteresis state machine | Developer | ✅ Implemented (post-fix matches SPEC-107 §A) |
| F2 NYSE calendar + sched bars | Developer | ✅ Implemented |
| F3 Decision log | Developer | ✅ Implemented |
| F4 Frontend State Observation / Actionable | Developer | ✅ Implemented |
| **AC7 12mo replay envelope** | **Quant + Developer joint** | **✅ PASS after 3 bug fixes** |
| AC8 HIGH_VOL/STRESS regression | Quant + Developer joint | ✅ PASS (both real subset + synthetic fuzz) |
| F5 Backtest replay smoke | Quant | ✅ Verified via `research/intraday/q076_ac7_replay.py` |
| F6 Regression test | Quant | ✅ 53/53 PASS |
| F7 Deploy + 30-day live review | Developer + PM | Pending (post-DONE) |

**SPEC-107 is now ready for DONE designation and deployment.**
