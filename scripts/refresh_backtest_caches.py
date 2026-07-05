#!/usr/bin/env python3
"""Overnight backtest cache refresh — runs at 02:00 ET via launchd.

Calls the local Flask server endpoints to force-recompute all backtest
disk caches with the current day's market data.  Designed to run while
the server is idle so morning users hit warm caches instead of waiting
for the 52-second cold-start recomputation.

Endpoints refreshed (in order):
  1. /api/backtest/stats       — matrix win-rate cells (3y + 10y + all, ~52s)
  2. /api/backtest?start=3y    — SPX strategy backtest 3-year view (~4s)
  3. /api/backtest?start=5y    — SPX strategy backtest 5-year view (~7s)
  4. /api/q041/backtest        — Q041 CSP backtest (if stale)
  5. /api/es/backtest          — ES Short Put backtest (if stale)
"""

from __future__ import annotations

import sys
import time
import urllib.request
import urllib.error
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "http://localhost:5050"
# SPEC-117.4: the stats endpoint (matrix win-rate cells, 3y+10y+all) takes
# minutes on a cold cache since the 26y window grew — 180s timed out nightly,
# silently leaving matrix win-rates stale (exit=1, no alerting).
# SPEC-119 follow-up: algo-hash cache keys (SPEC-118.3) mean EVERY algorithm
# commit forces a fully-cold recompute on the next refresh.
# SPEC-124 follow-up: cold runs are trending up on the old Air (438s on
# 2026-07-05 morning; >900s that evening when the rebuild raced a yahoo
# history refresh). The server finishes server-side even when this client
# times out (the disk cache still lands — verify with a warm re-hit), so a
# timeout here is a REPORTING failure, not a data failure. Budget = worst
# observed + headroom; if this keeps growing the real fix is hardware or an
# incremental stats computation, not a bigger number here.
TIMEOUT  = 1200  # seconds per request
LOG      = Path("/Users/macbook/Library/Logs/spx-strat/refresh_backtest.log")


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def fetch(path: str, label: str) -> bool:
    url = BASE_URL + path
    log(f"→ {label}  ({url})")
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"X-Refresh-Source": "overnight-cron"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(256)
            elapsed = time.time() - t0
            ok = resp.status == 200 and b'"error"' not in body[:64]
            status = "OK" if ok else "WARN (error in body)"
            log(f"   {status}  {elapsed:.1f}s  HTTP {resp.status}")
            return ok
    except urllib.error.URLError as e:
        log(f"   FAIL  {time.time()-t0:.1f}s  {e}")
        return False
    except Exception as e:
        log(f"   FAIL  {time.time()-t0:.1f}s  {e}")
        return False


def main() -> int:
    log("=" * 60)
    log("Overnight backtest cache refresh starting")
    log("=" * 60)

    today = date.today()
    start_3y = (today - timedelta(days=365 * 3)).isoformat()
    start_5y = (today - timedelta(days=365 * 5)).isoformat()

    tasks = [
        ("/api/backtest/stats",                        "SPX stats (matrix win-rate cells, 3y+10y+all)"),
        (f"/api/backtest?start={start_3y}",            "SPX results 3-year view"),
        (f"/api/backtest?start={start_5y}",            "SPX results 5-year view"),
        ("/api/q041/backtest?start=2022-05-06",        "Q041 CSP backtest"),
        ("/api/es/backtest?use_hybrid=1&start=2022-05-01", "ES Short Put backtest"),
    ]

    results = []
    for path, label in tasks:
        ok = fetch(path, label)
        results.append((label, ok))
        time.sleep(1)   # brief pause between heavy endpoints

    log("-" * 60)
    passed = sum(1 for _, ok in results if ok)
    log(f"Refresh complete: {passed}/{len(results)} endpoints OK")
    for label, ok in results:
        log(f"  {'✓' if ok else '✗'}  {label}")
    log("=" * 60)

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
