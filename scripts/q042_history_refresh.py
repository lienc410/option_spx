#!/usr/bin/env python3
"""Refresh Q042 SPX and VIX history caches through local Flask endpoints.

Scheduled on old Air after the market close so attribution consumers read a
single SPX/VIX source of truth from q042_*_history_cache.json.
"""

from __future__ import annotations

import json
import sys
import urllib.request


BASE_URL = "http://127.0.0.1:5050"
ENDPOINTS = (
    "/api/q042/spx-history?full=1",
    "/api/q042/vix-history?full=1",
)


def _fetch(path: str) -> dict:
    url = BASE_URL + path
    with urllib.request.urlopen(url, timeout=90) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(f"{path} returned error: {payload.get('error')}")
    rows = payload.get("history") or []
    if not rows:
        raise RuntimeError(f"{path} returned no history rows")
    return payload


def main() -> int:
    for path in ENDPOINTS:
        payload = _fetch(path)
        rows = payload.get("history") or []
        current = payload.get("current") or {}
        print(
            "[q042_history_refresh] "
            f"{path} ok rows={len(rows)} latest={rows[-1].get('date')} "
            f"current={current.get('close')}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[q042_history_refresh] ERROR {exc}", file=sys.stderr)
        raise SystemExit(1)
