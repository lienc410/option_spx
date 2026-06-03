# SPEC-112 — IVP gate lookback shortened from 252 to 126 trading days

**Type**: governance parameter change (single-value config swap)
**Date**: 2026-06-03
**Status**: **DRAFT** — Q083 verdict ratified by PM 2026-06-03, pending PM final sign + Developer implementation
**Owner**: Quant Researcher (draft) → PM approval → Developer implementation
**Source**: Q083 P9 verdict reversal (`research/q083/q083_p9_reversal_2026-06-03.md`)
**Parent**: SPEC-058/060 (IVP gate establishment) — modifies parameter, not structure

---

## 0. TL;DR

Change selector's IVP computation lookback from **252 → 126 trading days**. All other gate thresholds unchanged. This is a one-parameter swap with operational evidence showing pass rate, disaster rate, tail behavior, and 26y aggregate PnL all monotonically better at IVP126 vs IVP252.

**One line code change**: `IVP_LOOKBACK_DAYS = 252` → `IVP_LOOKBACK_DAYS = 126` (or equivalent in current selector).

---

## 1. Background

Q083 investigation triggered by PM operational complaint: "normal VIX 区几乎不放行" + "一次 spike 后 6-12 个月不能交易".

Q083 P3 direct diagnostics confirmed both:
- NORMAL × BULL pass rate (current IVP252): **0.8% aggregate**, 3-14% per VIX bucket
- IVP252 baseline pass rate (≥365d since last spike): **2.7%** — structurally pathological, not spike-recovery artifact
- IVP252 contamination 30-252 days post-spike: confirmed in A3

Q083 P4 head-to-head simulation 26y NORMAL × BULL:

| Design | Pass% | n trades | Win% | Mean$/trade | Worst | Disaster% | Sortino |
|---|---|---|---|---|---|---|---|
| IVP63 | 2.1% | 30 | 73.3% | +$308 | -$1,138 | 0% | +0.878 |
| **IVP126 (NEW)** | **2.3%** | **33** | **63.6%** | **+$372** | **-$1,660** | **0%** | **+0.666** |
| IVP252 (current) | 0.8% | 11 | 54.5% | -$21 | -$5,707 | 9.1% | -0.012 |

Q083 P5 sensitivity confirms IVP60-126 is a plateau, IVP180-252 is a cliff:

| Window | Sortino |
|---|---|
| IVP40 | +0.04 (too short, noisy) |
| IVP60-126 (plateau) | +0.35 to +0.97 (consistently positive) |
| IVP180-252 (cliff) | -0.34 to -0.01 (consistently negative) |

Choice of IVP126 within plateau: more noise-resistant than IVP60/63, best 2013-2026 sub-sample Sortino (+2.605), best aggregate cum PnL.

---

## 2. What changes

### Code change (single file, single constant)

**Before**:
```python
# strategy/selector.py (or wherever IVP lookback is defined)
IVP_LOOKBACK_DAYS = 252
```

**After**:
```python
IVP_LOOKBACK_DAYS = 126
```

Implementation may need:
- `signals/iv_rank.py` `compute_iv_percentile()` to accept lookback param
- `signals/iv_rank.py` `get_current_iv_snapshot()` to use 126d window for `iv_percentile`
- `ivp252` and `ivp63` fields in `IVSnapshot` already exist (kept for shadow comparison per Problem B); add `ivp126` field if not already present
- The PRIMARY IVP used by gate becomes `ivp126`

### What is NOT changing

- BPS_NNB_IVP_LOWER = 43 (unchanged)
- BPS_NNB_IVP_UPPER = 55 (unchanged)
- IVP_LOW_THRESHOLD = 40 (unchanged)
- IVP_HIGH_THRESHOLD = 70 (unchanged)
- IVP63_BCS_BLOCK = 70 (unchanged — uses 63d window already, scoped to BCS HV)
- Matrix routing (regime × iv_signal × trend) (unchanged)
- IVR computation lookback (unchanged at 252d for now; revisit if needed)
- All other selector logic (unchanged)

### Why parameter swap not deeper redesign

Per Q083 plateau finding: IVP60-126 all work, IVP180-252 doesn't. Within plateau, choice is empirical (IVP126 picked for noise-resistance + better 2013-2026 stats). This is parameter calibration, not architectural change.

---

## 3. Risk / Trade-off

### Increased pass rate

- IVP252: 0.8% aggregate → IVP126: 2.3%
- More open trades over time → roughly 4-5 BPS/year → ~13 BPS/year
- Per-trade cash usage governed by SPEC-111 (60% liquid cap)

### Tail behavior

- IVP126 worst trade $-1,660 < IVP252 worst trade $-5,707
- IVP126 disaster rate (≤ $-2,500 single trade) 0% vs IVP252 9.1%
- **Tail is STRICTLY BETTER**, not worse

### Skew haircut

- P7 skew bracket: BPS short-vega means real-chain DOWN trades may lose ~30% more than BS-flat synth shows
- IVP126 baseline mean +$372 → skew-haircut estimate ~$260 per trade
- Still positive, still > $-21 IVP252 mean

### Caveat: post-2013 concentration

- 2000-2013: IVP126 and IVP252 had similar Sortino (~0.04-0.40)
- 2013-2026: IVP126 dominates (Sortino +2.605 vs -0.095)
- Decision: accept some recency bias. If regime shifts back to pre-2013 pattern, both designs will underperform similarly. No design dominates pre-2013.

### Comparison standard (per memory feedback_decision_type_governs_significance_standard)

This is an **execution-constraint decision**, not alpha decision. Standard: comparative, not vs zero. Both IVP126 and IVP252 have per-trade CI crossing zero (per memory neither passes the "alpha" bar). But IVP126 is comparatively better on 6/6 operational dimensions (pass rate, disaster rate, worst trade, win rate, Sortino, cum PnL).

---

## 4. Acceptance Criteria

### AC1 — Code change unit-tested

`tests/test_spec_112.py`:
- AC1.1: IVP for known VIX series with lookback=126 matches manual computation
- AC1.2: IVP for known VIX series with lookback=252 matches old behavior (test as regression)
- AC1.3: Gate decision on a day with VIX=16, IVP126=43 → passes (BPS_NNB_LOWER met); same day with IVP252=26 → blocks
- AC1.4: Snapshot fields `ivp` (= ivp126 going forward) and `ivp252` (kept for shadow) and `ivp63` (kept) all present

### AC2 — Integration smoke test

- Live `/api/recommendation` after deploy shows new IVP value with 126d basis
- Existing fields backward-compatible

### AC3 — Backtest non-regression

- Re-run 3y backtest with IVP126 active
- Compare to Q083 P4 results — should match (n=33 BPS trades expected, mean ~$372)
- Per memory `feedback_backtest_cache_refresh`: refresh three caches (Q041, ES, SPX) after SPEC-112 deploy

### AC4 — Shadow infrastructure (parallel, for Problem B)

- Daily snapshot adds `ivp60`, `ivp63`, `ivp90` fields (in addition to existing `ivp63` and new `ivp126`)
- Each field logs the "would-pass-gate" decision separately
- 6-12 month collection target

### AC5 — Q083 trail closure

- Update `research/q083/q083_p9_reversal_2026-06-03.md` with deployed commit hash
- Update Q081 P5 + Q082 P10 cross-references if needed

---

## 5. Out of scope

- Regime-conditional gate logic (Problem B exploration only)
- IVR cell-routing change (P0 confirmed nested, not the binding constraint)
- BPS_NNB threshold change (separate decision)
- Adding entry-signal gates (per memory `feedback_short_dte_entry_signal_cannot_gate_forward` — no entry signal predicts forward direction for short-DTE)
- Cash budget cap parameter (SPEC-111 owns this; separate live-test running)

---

## 6. Deployment plan

```bash
# 1. Dev implements + tests on local
git checkout -b spec-112
# ... implementation: change IVP_LOOKBACK_DAYS, add ivp126 field ...
pytest tests/test_spec_112.py -v
pytest tests/test_spec_*.py  # full regression
git commit -m "feat(selector): SPEC-112 IVP gate lookback 252→126"
git push

# 2. Deploy to old Air
ssh oldair 'cd ~/SPX_strat && git pull origin main && launchctl kickstart -k gui/$(id -u)/com.spxstrat.web'

# 3. Backtest cache refresh (per memory)
ssh oldair '~/SPX_strat/venv/bin/python -m backtest.refresh_caches --all'

# 4. Smoke test live
curl 'http://oldair.local:5050/api/recommendation' | jq '.iv_snapshot.iv_percentile'

# 5. Verify recommendation logic
# If current VIX 16.13 and IVP126 = ?, gate decision should match expectation
```

---

## 7. Estimated effort

| Task | Hours |
|---|---|
| Code change + new field plumbing | 2 |
| Unit tests | 1.5 |
| Backtest regression | 1 |
| Frontend (display IVP126 in snapshot) | 1 |
| Backtest cache refresh | 0.5 |
| Manual smoke + Q083 trail close | 1 |
| **Total** | **~7 hours** (~1 dev day) |

---

## 8. PM ratification needed

- Code change scope: parameter swap only — accept?
- AC list complete — accept?
- Backtest sizing implications: pass rate ~3x increase, but each trade still bounded by SPEC-111 cap — accept?
- Shadow infrastructure (AC4) parallel deployment — accept?

---

## 9. Q083 close

On SPEC-112 deploy:
- Q083 closes with verdict: SPEC-112 (Problem A) + shadow infrastructure design (Problem B follow-up)
- Q083 P9 marked DONE
- Memory entries (`feedback_circular_metric_validation`, `feedback_stratum_cutpoint_overfit`, `feedback_decision_type_governs_significance_standard`) preserved as cross-session learning
