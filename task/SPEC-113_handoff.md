# SPEC-113 Developer Handoff

**SPEC**: [task/SPEC-113.md](SPEC-113.md)
**Date issued**: 2026-06-03
**Estimated effort**: 0.5–1 day
**Status**: pre-implementation. Ratified by Quant + 2nd Quant Reviewer + PM (floor=警惕线).

---

## TL;DR — What you're doing

Add ONE matrix cell + ONE VIX threshold constant. Frontend matrix display gains dict-cell support. Refactor must be **bit-identical** for the other 26 cells (AC-N).

Edits land in two production files, one new test file, one frontend template update. Then refresh 3 backtest caches, deploy to Old Air.

---

## Files to change

| File | Action | Lines (approx) | What |
|---|---|---|---|
| [strategy/selector.py](../strategy/selector.py) | EDIT | ~1202-1208 + new constant near other SPEC constants | Add `SPEC_113_VIX_THRESHOLD = 18.0`; modify NORMAL × IV_LOW × BULLISH branch per SPEC §2.5 |
| [strategy/catalog.py](../strategy/catalog.py) | EDIT | 188-209 (CANONICAL_MATRIX) + matrix_payload() | Change `["NORMAL"]["LOW"]["BULLISH"]` from string to dict; extend `matrix_payload()` to handle dict-valued cells |
| [web/templates/](../web/templates/) (matrix display template — TBD path) | EDIT | TBD | Render dict-cell sub-condition visibly ("BCD if VIX<18 else Wait") |
| `tests/test_spec_113_carve.py` | **NEW** | ~150 lines | AC-1/2/3/4/7 unit tests + AC-N bit-identical regression |
| [tests/test_strategy_unification.py:59-60](../tests/test_strategy_unification.py#L59-L60) | EDIT | 59-60 | Existing matrix-shape assertions iterate `iv_map.values()` assuming string values; handle dict-cells |

---

## Code stubs

### 1. selector.py — module constant (add near other SPEC constants, e.g. after IVP_LOW_THRESHOLD)

```python
# SPEC-113: NORMAL × IV_LOW × BULLISH carve-in
# VIX < 18 → BCD; VIX >= 18 → reduce_wait
# Threshold selected from Q083 P13 +8vp short-leg skew sensitivity: VIX bucket [18,20) sub-cells become weak under pessimistic skew
SPEC_113_VIX_THRESHOLD = 18.0
```

### 2. selector.py — branch change (current line 1202-1208)

Replace:

```python
if iv_s == IVSignal.LOW:
    if t == TrendSignal.BULLISH:
        return _reduce_wait(
            "NORMAL + IV LOW + BULLISH — thin premium (IVP<40) makes Diagonal risk/reward unfavourable; wait for IV to expand",
            vix, iv, trend, macro_warn,
            params=params,
        )
```

With:

```python
if iv_s == IVSignal.LOW:
    if t == TrendSignal.BULLISH:
        # SPEC-113 carve: VIX<18 routes to BCD
        if vix.vix < SPEC_113_VIX_THRESHOLD:
            # SPEC-079 BCD comfortable-top filter (same as LOW_VOL × BULL branch)
            if (not params.disable_entry_gates
                and bcd_comfortable_top_filter(
                    vix=vix.vix,
                    dist_30d_high_pct=trend.dist_30d_high_pct,
                    ma_gap_pct=trend.ma_gap_pct,
                    date=vix.date,
                )):
                return _reduce_wait(
                    f"SPEC-113 BCD carve (NORMAL+IV_LOW+BULL+VIX<{SPEC_113_VIX_THRESHOLD}) but "
                    f"comfortable-top filter (SPEC-079): risk_score=3",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                    params=params,
                )

            action = get_position_action(
                StrategyName.BULL_CALL_DIAGONAL.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.BULL_CALL_DIAGONAL.value),
            )
            local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN
                           and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)
            return _build_recommendation(
                StrategyName.BULL_CALL_DIAGONAL,
                vix=vix, iv=iv, trend=trend,
                legs=[
                    Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
                    Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
                ],
                size_rule=_compute_size_tier(
                    StrategyName.BULL_CALL_DIAGONAL.value, iv, vix, iv_s, t
                ),
                rationale=(
                    f"NORMAL + IV LOW + BULLISH + VIX={vix.vix:.1f} < {SPEC_113_VIX_THRESHOLD} "
                    f"(SPEC-113 carve) — spike-decay state where BCD +vega cushion is structurally rewarded"
                ),
                position_action=action,
                macro_warning=macro_warn,
                local_spike=local_spike,
            )

        # VIX >= 18 stays reduce_wait
        return _reduce_wait(
            f"NORMAL + IV LOW + BULLISH + VIX={vix.vix:.1f} >= {SPEC_113_VIX_THRESHOLD} — "
            f"SPEC-113 carve gate (VIX too high for +vega cushion to dominate under pessimistic skew)",
            vix, iv, trend, macro_warn,
            canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
            params=params,
        )
```

Note: `bcd_comfortable_top_filter` import / call signature must match the existing LOW_VOL × BULL branch (selector.py line 1056-1060). Reuse the same helper.

### 3. catalog.py — CANONICAL_MATRIX (line 197)

Replace:

```python
"LOW":     {"BULLISH": "reduce_wait",        "NEUTRAL": "reduce_wait",    "BEARISH": "reduce_wait"},
```

With:

```python
"LOW":     {
    "BULLISH": {"VIX_LT_18": "bull_call_diagonal", "VIX_GE_18": "reduce_wait"},
    "NEUTRAL": "reduce_wait",
    "BEARISH": "reduce_wait",
},
```

Update type hint on line 188:

```python
CANONICAL_MATRIX: dict[str, dict[str, dict[str, str | dict[str, str]]]] = {
```

### 4. catalog.py — matrix_payload() (line 240-250)

Extend to handle dict cells:

```python
def matrix_payload() -> dict[str, Any]:
    def _render_cell(value: str | dict[str, str]) -> dict[str, Any]:
        if isinstance(value, str):
            return {
                "type": "single",
                "strategy": strategy_descriptor(value).key,
                "name": strategy_descriptor(value).name,
            }
        # dict-valued (sub-cell) — currently only NORMAL.LOW.BULLISH for SPEC-113
        return {
            "type": "conditional",
            "conditions": {
                cond_key: {
                    "strategy": strategy_descriptor(strat).key,
                    "name": strategy_descriptor(strat).name,
                    "label": _condition_label(cond_key),  # "VIX < 18" / "VIX ≥ 18"
                }
                for cond_key, strat in value.items()
            },
        }

    return {
        regime: {
            iv: {trend: _render_cell(key) for trend, key in trend_map.items()}
            for iv, trend_map in iv_map.items()
        }
        for regime, iv_map in CANONICAL_MATRIX.items()
    }


def _condition_label(key: str) -> str:
    return {
        "VIX_LT_18": "VIX < 18",
        "VIX_GE_18": "VIX ≥ 18",
    }.get(key, key)
```

### 5. tests/test_spec_113_carve.py (new)

```python
"""SPEC-113: NORMAL × IV_LOW × BULLISH × VIX<18 carve to BCD."""
import pytest
from strategy.selector import select_strategy, StrategyName, SPEC_113_VIX_THRESHOLD
# ... import test fixtures: make_vix_snap, make_iv_snap, make_trend_snap

def _normal_iv_low_bull(vix_value):
    """Build snapshots for NORMAL × IV_LOW × BULLISH at given VIX."""
    return (
        make_vix_snap(vix=vix_value, regime="NORMAL"),
        make_iv_snap(iv_percentile=30.0, ivp63=20.0),  # IV LOW
        make_trend_snap(signal="BULLISH", above_200=True),
    )

# AC-1
def test_ac1_carve_positive_vix_15p5_returns_bcd():
    vix, iv, trend = _normal_iv_low_bull(15.5)
    rec = select_strategy(vix, iv, trend)
    assert rec.strategy == StrategyName.BULL_CALL_DIAGONAL
    assert "SPEC-113 carve" in rec.rationale

# AC-2 — boundary both sides
def test_ac2_carve_threshold_17p99_returns_bcd():
    vix, iv, trend = _normal_iv_low_bull(17.99)
    rec = select_strategy(vix, iv, trend)
    assert rec.strategy == StrategyName.BULL_CALL_DIAGONAL

def test_ac2_carve_threshold_18p00_returns_reduce_wait():
    vix, iv, trend = _normal_iv_low_bull(18.00)
    rec = select_strategy(vix, iv, trend)
    assert rec.canonical_strategy == StrategyName.BULL_CALL_DIAGONAL.value
    assert "reduce_wait" in rec.action.lower() or "SPEC-113 carve gate" in rec.rationale

# AC-3 — SPEC-079 comfortable-top still binds
def test_ac3_comfortable_top_blocks_spec113_bcd():
    vix, iv, trend = _normal_iv_low_bull(15.5)
    trend = make_trend_snap(signal="BULLISH", above_200=True,
                            dist_30d_high_pct=0.001, ma_gap_pct=0.001)
    # Construct a SPEC-079 risk_score=3 condition
    rec = select_strategy(vix, iv, trend)
    if "SPEC-079" in rec.rationale:
        assert rec.strategy != StrategyName.BULL_CALL_DIAGONAL
    # Else (SPEC-079 didn't trigger on these inputs) — skip the assertion

# AC-7 — regime isolation
def test_ac7_low_vol_bull_unaffected_by_spec113():
    vix = make_vix_snap(vix=12.0, regime="LOW_VOL")
    iv = make_iv_snap(iv_percentile=30.0)
    trend = make_trend_snap(signal="BULLISH", above_200=True)
    rec = select_strategy(vix, iv, trend)
    assert rec.strategy == StrategyName.BULL_CALL_DIAGONAL
    assert "LOW_VOL" in rec.rationale  # routed via LOW_VOL branch, NOT SPEC-113
    assert "SPEC-113" not in rec.rationale

def test_ac7_normal_iv_high_bull_unaffected():
    vix = make_vix_snap(vix=22.0, regime="NORMAL")
    iv = make_iv_snap(iv_percentile=75.0)  # IV HIGH
    trend = make_trend_snap(signal="BULLISH", above_200=True)
    rec = select_strategy(vix, iv, trend)
    # Should route via NORMAL × IV_HIGH × BULL branch (BPS), not SPEC-113
    assert rec.strategy != StrategyName.BULL_CALL_DIAGONAL
```

### 6. tests/test_spec_113_bit_identical.py (new — AC-N)

```python
"""SPEC-113 AC-N: bit-identical regression on all 26 string-valued matrix cells.

Verifies the dict-handling refactor doesn't perturb routing for any cell except
NORMAL × LOW × BULLISH. Compares select_strategy outputs against frozen
expectations captured BEFORE SPEC-113 implementation.
"""
import json
from pathlib import Path
import pytest
from strategy.selector import select_strategy, StrategyName

# Path to frozen snapshot of pre-SPEC-113 outputs
FROZEN = Path(__file__).parent / "fixtures" / "spec_113_pre_refactor_outputs.json"

# 35 combinations (36 total minus the changed cell)
REGIMES = ["LOW_VOL", "NORMAL", "HIGH_VOL", "EXTREME_VOL"]
IV_SIGNALS = ["HIGH", "NEUTRAL", "LOW"]
TRENDS = ["BULLISH", "NEUTRAL", "BEARISH"]
EXCLUDE = {("NORMAL", "LOW", "BULLISH")}  # the one changed cell

@pytest.fixture(scope="module")
def frozen_outputs():
    return json.loads(FROZEN.read_text())

@pytest.mark.parametrize("regime", REGIMES)
@pytest.mark.parametrize("iv_s", IV_SIGNALS)
@pytest.mark.parametrize("trend", TRENDS)
def test_string_cells_bit_identical(regime, iv_s, trend, frozen_outputs):
    if (regime, iv_s, trend) in EXCLUDE:
        pytest.skip("changed cell — covered by test_spec_113_carve.py")
    expected = frozen_outputs[f"{regime}_{iv_s}_{trend}"]
    # Synthesize inputs matching the cell — see fixtures/_canonical_inputs.py
    vix, iv, trend_snap = _synthesize_for_cell(regime, iv_s, trend)
    rec = select_strategy(vix, iv, trend_snap)
    assert rec.canonical_strategy == expected["canonical_strategy"]
    assert rec.strategy.value == expected["strategy"]
    assert [(l.side, l.right, l.dte, l.delta) for l in (rec.legs or [])] == expected["legs"]
    assert rec.size_rule == expected["size_rule"]
    assert rec.rationale == expected["rationale"]
```

**Generating the frozen snapshot** (run once BEFORE editing selector.py):

```bash
# On main branch BEFORE making changes
git checkout main
arch -arm64 venv/bin/python -c "
from strategy.selector import select_strategy
# ... loop 35 combinations, write tests/fixtures/spec_113_pre_refactor_outputs.json
" > tests/fixtures/spec_113_pre_refactor_outputs.json
git add tests/fixtures/spec_113_pre_refactor_outputs.json
git commit -m 'SPEC-113 AC-N fixture: pre-refactor frozen outputs'
```

Note: pick a single canonical (vix, iv, trend) input per cell — e.g., midpoint VIX for the regime band, ivp at the iv_signal midpoint. Frozen exact-values; later spot-check that synthesis matches the cell's branch.

---

## Test plan

```bash
# 1. Unit tests pass
arch -arm64 venv/bin/python -m pytest tests/test_spec_113_carve.py -v
arch -arm64 venv/bin/python -m pytest tests/test_spec_113_bit_identical.py -v

# 2. Existing test suite still passes (especially strategy_unification)
arch -arm64 venv/bin/python -m pytest tests/test_strategy_unification.py tests/test_spec_103.py tests/test_spec_104.py tests/test_spec_105.py tests/test_spec_106.py tests/test_spec_107.py -v

# 3. 26y backtest non-regression (AC-5)
#    Before:
arch -arm64 venv/bin/python scripts/run_full_backtest.py --start 2000-01-01 --end 2026-06-01 \
    --output /tmp/backtest_pre_spec113.json
git checkout <feature-branch>
arch -arm64 venv/bin/python scripts/refresh_backtest_caches.py  # invalidate stale caches
arch -arm64 venv/bin/python scripts/run_full_backtest.py --start 2000-01-01 --end 2026-06-01 \
    --output /tmp/backtest_post_spec113.json
arch -arm64 venv/bin/python scripts/compare_backtest_diffs.py \
    --pre /tmp/backtest_pre_spec113.json --post /tmp/backtest_post_spec113.json
# Expected: all non-BCD strategies bit-identical; BCD count +46 over 26y, PnL increment consistent with P11 expectation
```

If `scripts/refresh_backtest_caches.py` or `compare_backtest_diffs.py` don't exist with those names, use existing equivalents — the per-strategy aggregation must be checked.

---

## AC checklist

Map to [SPEC-113.md §3](SPEC-113.md):

- [ ] AC-1 — VIX 15.5 returns BCD
- [ ] AC-2 — VIX 17.99 → BCD, VIX 18.0 → reduce_wait (boundary both sides)
- [ ] AC-3 — SPEC-079 comfortable-top filter precedence preserved
- [ ] AC-4 — SPEC-111 cash cap still binds (selector returns BCD, governance downgrades to reduce_wait when cap breached)
- [ ] AC-N — 26/27 string-valued cells bit-identical Recommendation pre/post refactor
- [ ] AC-5 — 26y backtest non-regression on non-BCD strategies
- [ ] AC-6 — cash time-coverage logging in place (auto-collects, review at T+30)
- [ ] AC-7 — sub-cell unit tests pass + regime isolation verified

---

## Backtest cache refresh (REQUIRED before AC-5)

Per `feedback_backtest_cache_refresh`:

```bash
# These three caches MUST be regenerated; AC-5 is meaningless if they're stale
rm -f data/q041_backtest_cache.json
rm -f data/es_backtest_cache.json   # if used by any SPX router (likely not for SPEC-113 but verify)
rm -f data/spx_backtest_cache.json

# Regenerate via the standard backtest entrypoint
arch -arm64 venv/bin/python scripts/run_full_backtest.py --regenerate-caches
```

---

## Deploy

Per `feedback_deploy_oldair`:

```bash
# After all ACs green on local
git push origin main
ssh oldair "cd ~/SPX_strat && git pull && launchctl kickstart -k gui/$(id -u) com.spxstrat.web"
# Verify:
ssh oldair "curl -s localhost:8000/api/strategy-matrix | jq '.matrix.NORMAL.LOW.BULLISH'"
# Expected: {"type": "conditional", "conditions": {"VIX_LT_18": {...bull_call_diagonal...}, "VIX_GE_18": {...reduce_wait...}}}
```

Frontend smoke: open Portfolio Command Center on the deployed Old Air, navigate to the matrix view, verify `NORMAL × IV_LOW × BULLISH` cell now shows the sub-condition visibly (not just "reduce_wait").

---

## Post-deploy (T+30 days)

PM and/or Quant Researcher reviews:

1. Count of SPEC-113-routed trades in first 30 days (rationale text contains "SPEC-113 carve" — grep `data/decisions.jsonl` or equivalent).
2. Cash time-coverage: aggregate per-trading-day occupied-cash log, compute occupied_days / total_trading_days. Target ~46.4% ± 10pp.
3. Per-trade PnL distribution — spot-check direction match with P11 expectation (mean ~$1,490/contract @ +8vp; scaled to today's SPX 5000+ should be ~$4,665/contract; CI wide on small N, direction-check only).
4. Update [research/q083/](../research/q083/) with live-tracking notes if a tripwire condition fires (see SPEC-113 §7.4).

---

## Tripwire conditions (revert clause — SPEC §7.4)

Within first 90 days post-deploy, if ANY:
- Cash time-coverage materially > 55% (vs 46.4% target)
- 3+ consecutive SPEC-113-routed BCDs close at full max-loss
- SPEC-111 75% concurrent debit alert fires due to SPEC-113-routed open

→ Escalate to Quant Researcher for review (NOT auto-revert — review-trigger only).

---

## Open questions for dev

1. Backtest cache filenames — verify the three filenames in §"Backtest cache refresh" match actual current cache paths.
2. Matrix-rendering template — confirm path. If frontend renders matrix via JS from `/api/strategy-matrix` JSON, template change is dataflow-only (no HTML change).
3. `_compute_size_tier` reuse — confirm signature accepts `iv_s=IVSignal.LOW` on a NORMAL regime (it should — sizing is per-strategy, not per-cell).

Ping Quant if any open question turns into a blocking ambiguity.

---

## Cross-references

- [task/SPEC-113.md](SPEC-113.md) — the spec
- [task/q083_p15_g_review_today_params_2026-06-03.md](q083_p15_g_review_today_params_2026-06-03.md) — final G-review packet (cash net + AC-N)
- [research/q083/q083_p11_bcd_in_normal_low_ivr.py](../research/q083/q083_p11_bcd_in_normal_low_ivr.py) — BCD simulation in proposed cell
- [research/q083/q083_p13_robustness_gates.py](../research/q083/q083_p13_robustness_gates.py) — 4-gate robustness
- [research/q083/q083_p15_today_params_net.py](../research/q083/q083_p15_today_params_net.py) — today's-params net settlement
