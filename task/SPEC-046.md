# SPEC-046 Draft

## Title
Schwab Intraday Alert Source for VIX Spike and SPX Stop

## Status
DONE

## Review
- 结论：PASS
- F1–F8 全部通过
- tradeTime 毫秒转换正确（/1000.0）；realtime=None（Yahoo fallback 路径）走时间差逻辑，行为正确
- _STALE_QUOTE_MINUTES = 10 常量已定义，符合 SPEC

## Summary
Replace the current Yahoo-based intraday alert source for `VIX spike` and `SPX stop` with Schwab real-time quote data on the live alert path only, while retaining Yahoo as a fallback. Do not change backtest, daily regime/trend history, or selector/backtest data plumbing.

## Motivation
The current live alert path uses Yahoo intraday history:

- `signals/intraday.py:get_vix_spike()`
- `signals/intraday.py:get_spx_stop()`
- `notify/telegram_bot.py:intraday_monitor()`

This is acceptable for research and replay, but it is not reliable enough for timely live alerting. A recent production example showed the bot sending a `VIX spike` warning at approximately `15:12 ET` while the message timestamp reflected a much older `13:55` VIX bar. The bot itself was polling on schedule; the bottleneck was intraday data freshness.

Schwab quote data is already configured in the project and was verified to return real-time `$VIX` quotes with valid `tradeTime`. This makes Schwab a better primary source for live alerting.

## Goals
- Use Schwab real-time quote data as the primary source for live `VIX spike` alerts.
- Use Schwab real-time quote data as the primary source for live `SPX stop` alerts.
- Preserve existing alert semantics:
  - same thresholds
  - same escalation logic
  - same duplicate suppression behavior
- Keep Yahoo as a fallback if Schwab is unavailable.
- Continue sending delayed/stale alerts rather than suppressing them; lateness should be labeled, not blocked.

## Non-Goals
- Do not replace Yahoo in:
  - `signals/vix_regime.py`
  - `signals/trend.py`
  - `strategy/selector.py` daily/intraday recommendation fetch path
  - `backtest/engine.py`
  - any research/backtest prototype
- Do not rework backtest to use Schwab historical data.
- Do not change alert thresholds.
- Do not redesign Telegram alert formatting beyond adding quote freshness labeling.

## Scope

### In Scope
- `schwab/client.py`
  - add quote fetch helpers for `$VIX` and `$SPX`
- `signals/intraday.py`
  - allow live alert helpers to consume quote snapshots instead of only Yahoo history frames
- `notify/telegram_bot.py`
  - live alert monitor uses Schwab primary / Yahoo fallback
  - alert message includes quote time and send time
  - if quote time is stale, label it but still send

### Out of Scope
- Changing selector intraday recommendation source
- Replacing daily VIX/SPX history
- Replacing `^VIX3M`
- Any changes to option chain scanner

## Design

### 1. New Schwab quote helpers
Add quote fetch functions in `schwab/client.py`:

- `get_index_quote(symbol: str) -> dict`
- `get_vix_quote() -> dict`  — thin wrapper: `get_index_quote("$VIX")`
- `get_spx_quote() -> dict`  — thin wrapper: `get_index_quote("$SPX")`

**Endpoint**: `GET /marketdata/v1/quotes?symbols={symbol}` (same base URL as chains, same `_headers()` auth). Symbol normalization: pass `$VIX` / `$SPX` directly (no further `_marketdata_symbol()` conversion needed for quote lookup).

Expected normalized quote shape:

```python
{
    "symbol": "$VIX",
    "last": 25.78,
    "open": 25.09,
    "high": 28.00,
    "low": 24.34,
    "close": 24.17,
    "quote_time": "2026-04-07T16:15:01-04:00",
    "security_status": "Closed",
    "realtime": True,   # False if account has delayed (non-realtime) quote entitlement
}
```

Notes:
- `$VIX` is the valid Schwab symbol for VIX quote lookup.
- `$SPX` should be used for SPX quote lookup if supported by the same quote endpoint (see Risks).
- Reuse the existing in-memory Schwab cache TTL logic (60s market-hours TTL is acceptable for 5-min polling cycle).

### 2. Live intraday signal helpers
Extend `signals/intraday.py` with quote-driven helpers for live usage only:

- `get_vix_spike_from_quote(quote: dict) -> VixSpikeAlert`
- `get_spx_stop_from_quote(quote: dict) -> IntradayStopTrigger`

Computation rules:
- `vix_open` comes from Schwab quote `open`
- `vix_current` comes from Schwab quote `last`
- `spx_open` comes from Schwab quote `open`
- `spx_current` comes from Schwab quote `last`
- timestamp in the signal object should reflect quote time, not poll time

Fallback rules:
- If Schwab quote fetch fails or quote fields are missing, keep the current Yahoo path:
  - `get_vix_spike(interval="5m")`
  - `get_spx_stop(interval="5m")`

### 3. Freshness labeling, not blocking
Add a freshness label helper in `notify/telegram_bot.py`:

- compare `quote_time` vs current ET send time
- if delayed beyond **10 minutes**, mark the alert as stale — still send
- if `realtime == False`, label unconditionally as `[delayed — non-realtime quote]` without computing time delta (non-realtime accounts have 15-20 min structural delay that makes quote_time unreliable as a freshness indicator)

Example message fragments:

```text
⚠️ VIX Spike WARNING [bar 2026-04-07 13:55 | sent 2026-04-07 15:12 | delayed 77m]
⚠️ VIX Spike WARNING [delayed — non-realtime quote]
```

Important:
- Do not suppress alerting due to stale data
- Only annotate
- Freshness threshold: **10 minutes** (hardcoded constant `_STALE_QUOTE_MINUTES = 10`)

### 4. Bot monitor integration
Update `intraday_monitor()` so the live path becomes:

1. try Schwab quote for VIX and SPX
2. if successful, compute quote-based alerts
3. if not, fall back to current Yahoo intraday fetch

Duplicate suppression remains unchanged:
- escalate only on level increase
- send clear message when conditions normalize

## API / Interface Impact
- No public API changes required
- Telegram message text will include more precise timing metadata

## Acceptance Criteria

### Functional
- F1. `get_vix_quote()` successfully returns normalized `$VIX` quote data when Schwab is configured.
- F2. `get_spx_quote()` successfully returns normalized SPX quote data when Schwab is configured.
- F3. `intraday_monitor()` uses Schwab quote data as the primary live source for VIX/SPX alerts.
- F4. If Schwab quote fetch fails, the bot falls back to the existing Yahoo path without crashing.
- F5. Existing thresholds and escalation behavior remain unchanged.
- F6. Alert messages show both market-data time and actual send time.
- F7. Stale quote data is still delivered; it is labeled, not suppressed.
- F8. If `realtime == False`, alert is labeled `[delayed — non-realtime quote]` unconditionally.

### Testing
- T1. Unit test: VIX quote normalization from Schwab response
- T2. Unit test: SPX quote normalization from Schwab response
- T3. Unit test: quote-based spike calculation uses `open` and `last`
- T4. Unit test: quote-based stop calculation uses `open` and `last`
- T5. Unit test: `intraday_monitor()` prefers Schwab when configured
- T6. Unit test: `intraday_monitor()` falls back to Yahoo on Schwab failure
- T7. Unit test: stale label appears when quote/send timestamps diverge beyond **10 minutes**
- T8. Unit test: `realtime=False` quote always gets `[delayed — non-realtime quote]` label regardless of quote_time

## Risks
- Schwab quote symbol support for `$SPX` must be confirmed in the target account/environment.
- Quote field availability may differ by session state (`Open`, `Closed`, holiday, entitlement).
- The project will temporarily operate with mixed sources:
  - Schwab for live alerts
  - Yahoo for history/research/backtest
  This is intentional and acceptable.

## Implementation Notes
- Prefer minimal surface-area changes:
  - add quote helpers in `schwab/client.py`
  - add quote-driven intraday helpers in `signals/intraday.py`
  - update `notify/telegram_bot.py`
- Do not change selector or backtest logic in this spec.

## Rollout Notes
- After implementation, restart:

```bash
launchctl kickstart -k gui/$(id -u)/com.spxstrat.bot
```

- Web restart is not required unless the implementation also exposes new status fields on a web endpoint.
