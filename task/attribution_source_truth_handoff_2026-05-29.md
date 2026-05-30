# Developer Handoff — Attribution Data Source-of-Truth
**Date**: 2026-05-29
**Reporter**: PM via Quant Researcher
**Severity**: Medium — table currently shows correct values after manual
  rebuild this morning, but the underlying data plumbing is brittle and
  will silently drift again within days.

## 1. What happened today

PM noticed the Journal `Strategy PnL Attribution` table showed
`dS = 0.00` for 2026-05-21 (impossible) and other suspicious daily SPX
deltas. Investigation found two cooperating bugs:

### Bug A — daily_snapshot.jsonl SPX values are off-by-one-trading-day
`scripts/daily_snapshot.py` writes `market.spx` from `trend_snap.spx`
(line ~271) at the 16:30 ET cron firing. At that time the trend snap
source (yfinance-backed) has NOT yet posted today's EOD bar, so the
value captured is yesterday's close — but the row date stamp is
today (`_today_et()`). Result: every snapshot row's SPX is labeled
**one trading day late**.

Evidence (overlap with q042 history, where each date = that date's
real close):

| Date | q042 close (canonical) | daily_snapshot.spx |
|---|---|---|
| 2026-05-18 | 7403.05 | 7408.50 ← stale Fri 5/15 |
| 2026-05-19 | 7353.61 | 7403.05 ← was 5/18 |
| 2026-05-20 | 7432.97 | 7353.61 ← was 5/19 |
| 2026-05-21 | 7445.72 | 7432.97 ← was 5/20 |

VIX likely has the same problem but harder to verify because q042 has
no VIX history (yet).

### Bug B — q042 SPX history cache is *request-driven*, no auto-refresh
`data/q042_spx_history_cache.json` is filled by `/api/q042/spx-history`
([web/server.py:1729](web/server.py#L1729)) with a 24h TTL. It only
refreshes if PM (or a backtest user) hits the endpoint AND the cache
has expired. PM hadn't visited the relevant page in 8 days → cache
stopped at 2026-05-20.

When the attribution loader fell off the end of q042 (5/21+) it
fell back to daily_snapshot (Bug A) and the off-by-one error became
visible.

## 2. Quant's temporary stop-gap (already applied)

This morning I ran:
```bash
# 1. Force q042 refresh
curl -s 'http://localhost:5050/api/q042/spx-history?full=1' >/dev/null
# 2. Drop bad attribution rows
ssh oldair "cd ~/SPX_strat && cp data/strategy_pnl_attribution.jsonl{,.bak.2026-05-29}"
# (drop rows date >= 2026-05-21, see full snippet in chat log)
# 3. Re-emit
ssh oldair "~/SPX_strat/venv/bin/python scripts/compute_greek_attribution.py"
```
This restored correct attribution through today (2026-05-29). But
both bugs will re-emerge within ~24h:
- Tomorrow's daily_snapshot row will again store yesterday's SPX
- q042 cache will become stale again as soon as 24h passes without
  someone calling `/api/q042/spx-history`

## 3. Root-cause fix (PM-approved: route B)

### B1 — Fix daily_snapshot SPX/VIX source

**Goal**: `market.spx` and `market.vix` in `daily_snapshot.jsonl` must
equal that calendar day's official close, not "whatever stale value
trend_snap had at 16:30 ET".

**Recommended source**: Schwab Marketdata API. After 16:15 ET (SPX
settlement) Schwab returns the official EOD index value via
`get_quote("$SPX.X")` (already wired in `schwab/client.py`). Same for
`$VIX.X`.

**Changes**:
- `scripts/daily_snapshot.py` line ~271:
  ```python
  # Replace:
  "spx": _r(trend_snap.get("spx") if trend_snap.get("spx") is not None
            else q042.get("spx_close"), 2),
  # With:
  "spx": _r(_authoritative_spx_close(), 2),
  ```
  where `_authoritative_spx_close()` calls
  `schwab.client.get_index_quote("$SPX.X")` and returns the `last`/
  `closePrice` field. Fall back to `trend_snap.spx` only if Schwab
  fails AND log a WARNING (so it's visible in cron err log).
- Same for VIX.
- **Move cron from 16:30 → 17:00 ET** in
  `~/Library/LaunchAgents/com.spxstrat.daily_snapshot.plist` (15-min
  buffer past 16:15 SPX settlement).
- After deploy, **clean up the 12 days of bad snapshot rows**
  (2026-05-18 onward — see §6 backfill).

**Acceptance**:
- AC1: After deploy, next day's daily_snapshot row has SPX matching
  q042's same-date close (cross-check via `diff <(q042 today) <(snap today)`).
- AC2: One full week of agreement.
- AC3: VIX backfilled for 2026-05-05 → 2026-05-16 (currently None,
  see §6).

### B2 — q042 cache nightly auto-refresh cron

**Goal**: `q042_spx_history_cache.json` always has data through the
most recent completed trading day, with no dependency on user
browsing.

**Changes**:
- New script `scripts/q042_history_refresh.py`:
  ```python
  """Force-refresh the q042 SPX (and VIX, see B4) history cache.
     Runs daily at 17:30 ET on weekdays."""
  import requests
  requests.get("http://localhost:5050/api/q042/spx-history?full=1",
               timeout=60).raise_for_status()
  ```
  Logs success/failure to
  `~/Library/Logs/spx-strat/q042_history_refresh.{log,err.log}`.
- New launchd plist
  `~/Library/LaunchAgents/com.spxstrat.q042_history_refresh.plist`:
  Mon-Fri 17:30 ET, runs `scripts/q042_history_refresh.py`.

**Acceptance**:
- AC4: `~/Library/Logs/spx-strat/q042_history_refresh.log` shows
  daily success entry.
- AC5: 7-day live test — q042 cache age via
  `python3 -c "import json,time; d=json.load(open('data/q042_spx_history_cache.json')); print((time.time()-d['full']['ts'])/3600)"`
  should never exceed 24h on a weekday.

### B3 — Attribution loader: drop daily_snapshot fallback for SPX

**Goal**: `load_spx_history()` in
[scripts/compute_greek_attribution.py:132](scripts/compute_greek_attribution.py#L132)
uses **q042 only**. Eliminates the cross-source label drift that
caused this bug.

**Changes**:
- Remove the daily_snapshot fallback block (lines ~139-145).
- If q042 is missing a date the attribution loop needs, the loop
  already handles missing data via `synth_state` (holds IV constant
  + recomputes mark from BS). Just log a WARN per missing date.
- Same change in `web/server.py /api/strategy/greek-attribution`:
  build `vix_by_date` from a new dedicated VIX history cache (see B4),
  not from `daily_snapshot.jsonl`.

**Acceptance**:
- AC6: Search the codebase confirms no remaining reads of
  `daily_snapshot.jsonl` for SPX/VIX values inside attribution code
  paths.
- AC7: Re-run `compute_greek_attribution.py` against the existing
  jsonl after B1+B2 are deployed — no row should change (data is
  consistent across sources).

### B4 — VIX history cache (new, parallel to q042 SPX)

**Goal**: dVIX column populates for all dates, including the current
gap 2026-05-05 → 2026-05-16.

**Changes**:
- New endpoint `/api/q042/vix-history` mirroring SPX endpoint, fetching
  via `yfinance.download("^VIX", period="1y")`.
- New disk cache `data/q042_vix_history_cache.json` same structure as
  SPX cache.
- `scripts/q042_history_refresh.py` (B2) also hits this endpoint.
- `web/server.py /api/strategy/greek-attribution` uses VIX cache
  instead of `daily_snapshot.jsonl` for `vix_by_date`.
- On first deploy, run the endpoint once with `full=1` to backfill
  6-12 months of VIX.

**Acceptance**:
- AC8: After deploy + first refresh, attribution rows from 2026-05-05
  onward have non-null `dVIX` values.

## 4. Out of scope

- No change to attribution math (Δ·ΔS + ½Γ·ΔS² + Θ·Δt + V·ΔIV).
- No change to how `iv_s` / `iv_l` are BS-reverse-solved.
- No change to how broker_greeks are loaded (path B, separate stream).
- No change to closed_trades / edge fills.

## 5. Risk

- **Risk**: Schwab API rate limits if `_authoritative_spx_close()` is
  called from multiple places.
  - **Mitigation**: daily_snapshot is the only new caller. The
    existing in-memory `_quote_cache` in schwab/client absorbs
    duplicate calls within the same cron invocation.
- **Risk**: Schwab returns 0 / null for `$SPX.X` if hit too soon after
  16:15 settlement.
  - **Mitigation**: cron at 17:00 ET (45min after settlement) — well
    inside Schwab's settlement window.
- **Risk**: yfinance changes its VIX symbol format (`^VIX` vs `VIX`).
  - **Mitigation**: catch `KeyError` / empty-frame and fail gracefully
    with no row written that day. Existing snapshot remains source of
    last resort.

## 6. Backfill plan (one-time, post-deploy)

After B1 lands and the new SPX/VIX sources are working:

1. **Rebuild daily_snapshot.spx and .vix for 2026-05-18 → 2026-05-28**:
   ```bash
   ssh oldair "~/SPX_strat/venv/bin/python -c '
   from schwab.client import get_index_quote  # or whatever B1 lands
   # iterate dates 2026-05-18..2026-05-28
   # update each line in data/daily_snapshot.jsonl in place
   '"
   ```
   (Write a one-shot script `scripts/backfill_snapshot_spx_vix.py` and
   delete after use — don't leave permanently in `scripts/`.)
2. **Drop & rebuild attribution rows for affected dates**:
   ```bash
   # Already documented in §2 — same recipe applies.
   ```

## 7. Deployment

```bash
# 1. dev machine
git add scripts/daily_snapshot.py \
        scripts/q042_history_refresh.py \
        scripts/compute_greek_attribution.py \
        web/server.py \
        task/attribution_source_truth_handoff_2026-05-29.md
git commit -m "fix(attribution): single source of truth via Schwab close + q042 daily cron"
git push origin main

# 2. old Air
ssh oldair 'cd ~/SPX_strat && git pull origin main \
            && chmod +x scripts/q042_history_refresh.py'

# 3. Install/update plists
scp ~/Library/LaunchAgents/com.spxstrat.daily_snapshot.plist oldair:~/Library/LaunchAgents/
scp ~/Library/LaunchAgents/com.spxstrat.q042_history_refresh.plist oldair:~/Library/LaunchAgents/
ssh oldair 'launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.spxstrat.daily_snapshot.plist 2>/dev/null
            launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spxstrat.daily_snapshot.plist
            launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spxstrat.q042_history_refresh.plist'

# 4. Smoke
ssh oldair 'launchctl kickstart -k gui/$(id -u)/com.spxstrat.q042_history_refresh
            tail ~/Library/Logs/spx-strat/q042_history_refresh.log'

# 5. Backfill (one-shot, see §6)
# 6. Verify Journal page table
```

## 8. PM rollback

If the new Schwab-sourced snapshot starts disagreeing with q042 by >1%
(meaning Schwab is now lying or there's a settlement-timing issue):
```bash
ssh oldair 'launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.spxstrat.daily_snapshot.plist'
git revert <B1 commit hash>
```
Then re-deploy. q042 nightly refresh (B2) is safe to keep regardless.

## 9. Estimated dev work
- B1: 2 hours (Schwab client integration + cron schedule change + test)
- B2: 30 min (script + plist + test)
- B3: 30 min (delete fallback paths + verify)
- B4: 2 hours (mirror SPX cache pattern for VIX)
- Backfill (§6): 1 hour
- Total: ~6 hours of dev work
