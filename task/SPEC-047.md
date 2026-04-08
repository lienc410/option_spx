# SPEC-047 Draft

## Title
Adaptive Multi-Pass Delta-Seeking Scan

## Status
DONE

## Review
- 结论：PASS
- AC1–AC9 全部通过
- `_is_boundary_hit()` 正确：min/max strike 返回 True，内部 strike 返回 False，空链返回 True
- `_DELTA_SCAN_WINDOWS = (80, 140, 220)` 确保最多 3 次 API 调用（AC3）
- `build_strike_scan()` 循环逻辑：boundary hit 继续，内部 crossing 或 `sought_strike is None` 时 break（AC1、AC2、AC4、AC5）
- T1（pass1 boundary → pass2，call_count=2，recommended=7190）、T2（pass2 boundary → pass3，call_count=3，recommended=7090）、T3/T4（interior crossing stops early）、T5（pass3 boundary no crash，scan_fallback=False）均在 tests/test_schwab_scanner.py 中覆盖
- SPEC-045 的 `delta_gap` / `interpolated_center` 字段在第 175–178 行正确保留

## Summary
Extend `SPEC-045` so that when the interpolated target-delta strike lands on the current chain boundary, the scanner automatically widens the chain up to two additional rounds before accepting a boundary fallback. This keeps the interpolation-based design while avoiding false edge fallbacks when the true `delta≈target` strike lies just outside the initial wide window.

## Motivation
`SPEC-045` improved the short-leg scanner by replacing iterative neighborhood search with:

1. one wide chain pull
2. delta crossing interpolation
3. local scoring around the interpolated strike

That works well when the initial wide window actually contains the target delta crossing. In live SPX high-vol cases, however, the current `_WIDE_STRIKE_WINDOW = 80` can still be too narrow. We observed cases where:

- the minimum strike in the fetched chain still had `delta < 0.20`
- `_seek_target_delta_strike()` correctly returned the nearest boundary
- the recommended candidate improved materially, but was still below the true target delta region

This is not an interpolation bug. It is a boundary-coverage problem. The scanner should therefore distinguish:

- "target genuinely near this boundary" vs
- "target is outside the current window"

## Goals
- Preserve the `SPEC-045` interpolation-first design
- Avoid accepting a boundary fallback too early
- Add at most two additional widening rounds
- Stop immediately once a non-boundary crossing is found
- Keep API / frontend schema compatible

## Non-Goals
- Do not change front-end rendering
- Do not change score formula
- Do not change option-chain cache format beyond what is needed for wider windows
- Do not modify selector, engine, or backtest
- Do not add unlimited or recursive widening

## Scope

### In Scope
- `schwab/scanner.py`
  - adaptive widening control flow
  - boundary-hit detection
- `schwab/client.py`
  - existing `strike_window` cache key behavior remains sufficient; reuse it
- tests for adaptive widening behavior

### Out of Scope
- `web/server.py`
- `web/templates/index.html`
- Telegram / bot
- Backtest / research code

## Design

### 1. Replace single fixed window with staged widening

Instead of one hardcoded window:

```python
_WIDE_STRIKE_WINDOW = 80
```

use staged windows:

```python
_DELTA_SCAN_WINDOWS = (80, 140, 220)
```

Interpretation:
- pass 1: normal wide scan
- pass 2: widen if pass 1 still lands on left/right boundary
- pass 3: widen again if pass 2 still lands on boundary

No further passes after pass 3.

### 2. Boundary-hit detection

Add helper:

```python
def _is_boundary_hit(
    chain: list[dict],
    sought_strike: float | None,
) -> bool:
    """
    True when the interpolated/fallback strike equals the min or max strike
    available in the current chain.
    """
```

Rules:
- empty chain → treat as boundary/fallback case
- `sought_strike is None` → treat as fallback case
- if `sought_strike == min(strikes)` or `== max(strikes)` → boundary hit

### 3. Adaptive build_strike_scan flow

Pseudo-code:

```python
def build_strike_scan(...):
    if center_strike is None:
        # unchanged legacy path
        ...

    selected_chain = []
    selected_center = center_strike

    for window in _DELTA_SCAN_WINDOWS:
        chain = get_option_chain(
            symbol,
            option_type,
            target_dte,
            center_strike=center_strike,
            strike_window=window,
        )

        sought = _seek_target_delta_strike(chain, abs(float(target_delta)))

        if sought is None:
            selected_chain = chain
            selected_center = center_strike
            break

        rounded_center = round(sought / 5.0) * 5.0
        selected_chain = chain
        selected_center = rounded_center

        if not _is_boundary_hit(chain, sought):
            break

    candidate_chain = _slice_chain_around_center(selected_chain, selected_center)
    rows = scan_strikes(candidate_chain, target_delta=target_delta, symbol=symbol)
    return {"rows": rows, "scan_fallback": not bool(rows)}
```

### 4. Stop condition

Important behavior:
- If a pass finds a genuine interior crossing, stop immediately
- Only widen when the interpolated result is pinned to the chain boundary
- After the third pass, accept the boundary result and proceed

### 5. Local scoring window unchanged

Continue using the same scoring neighborhood behavior from `SPEC-045`, e.g.:

```python
_SCORE_WINDOW = 10
```

`_slice_chain_around_center(chain, center)` in the pseudocode refers to the SPEC-045 inline slice logic — sort `chain` by strike, find the index closest to `center`, take `[idx - _SCORE_WINDOW : idx + _SCORE_WINDOW + 1]`. Codex should inline this or extract it as a helper; it is not new logic.

No score-model changes in this spec.

### 6. Preserve SPEC-045 extra fields

`build_strike_scan()` in SPEC-045 attaches `delta_gap` and `interpolated_center` to the result rows. These fields must be preserved in the SPEC-047 implementation — they are not removed or modified by this spec.

## Acceptance Criteria

### Functional
- AC1. If the first pass lands on the chain boundary, scanner widens to pass 2
- AC2. If pass 2 still lands on the boundary, scanner widens to pass 3
- AC3. Scanner never performs more than 3 total chain requests for one centered scan
- AC4. If pass 1 or pass 2 finds an interior crossing, later passes are skipped
- AC5. If pass 3 still lands on the boundary, scanner accepts it without crashing
- AC6. `center_strike=None` path remains unchanged
- AC7. Response schema remains unchanged: `{"rows": [...], "scan_fallback": bool}`

### Quality / Effectiveness
- AC8. In a case where `window=80` misses the target but `window=140` contains it, the final recommended row is closer to `target_delta` than the pass-1 boundary recommendation
- AC9. In a case where both `80` and `140` miss but `220` contains the crossing, the third pass improves target-delta alignment

## Testing
- T1. Unit test: boundary hit on pass 1 triggers second request
- T2. Unit test: boundary hit on pass 2 triggers third request
- T3. Unit test: interior crossing on pass 1 stops without further requests
- T4. Unit test: interior crossing on pass 2 stops before pass 3
- T5. Unit test: pass 3 boundary fallback does not crash
- T6. Unit test: `center_strike=None` still uses single legacy path
- T7. Unit test: different windows still remain isolated by cache key

## Risks
- More requests in extreme cases: up to 3 chain pulls instead of 1
- Wider windows can increase response payload size, though still bounded
- SPX live data quality issues such as `open_interest = 0` remain separate from this spec

## Implementation Notes
- Keep changes limited to `schwab/scanner.py`
- Reuse existing `get_option_chain(..., strike_window=...)`
- Reuse `SPEC-045` interpolation helper rather than replacing it

## Rollout Notes
- After implementation, restart web only if you want `Open Position` modal to reflect the new scan behavior immediately:

```bash
launchctl kickstart -k gui/$(id -u)/com.spxstrat.web
```
