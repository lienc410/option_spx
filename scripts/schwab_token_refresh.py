#!/usr/bin/env python3
"""
Schwab token keep-alive — runs via launchd every 6 hours on oldair.

Schwab's refresh_token rotates on each use, resetting the 7-day TTL.
As long as this script runs at least once within any 7-day window the
session stays alive indefinitely — no browser re-auth ever needed.

If the refresh fails (token already expired), logs a warning so the user
knows to run schwab_reauth.py manually.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("schwab_refresh")

_ET = ZoneInfo("America/New_York")


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    from schwab.auth import (
        ensure_access_token,
        is_configured,
        load_token,
        token_status,
    )

    if not is_configured():
        log.error("SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET not set — skipping")
        sys.exit(0)

    status = token_status()
    ref_in = status.get("refresh_expires_in")

    if ref_in is not None and ref_in < 0:
        log.error(
            "Schwab refresh_token expired %d seconds ago — "
            "run scripts/schwab_reauth.py to re-authenticate",
            abs(ref_in),
        )
        sys.exit(1)

    try:
        token = ensure_access_token()
        updated = load_token() or {}
        ref_left = status.get("refresh_expires_in", "?")
        log.info(
            "Schwab access_token refreshed OK | "
            "refresh_expires_in=%s s (~%.1f days)",
            ref_left,
            (ref_left / 86400) if isinstance(ref_left, (int, float)) else 0,
        )
    except RuntimeError as e:
        if "auth_required" in str(e):
            log.error("Schwab auth_required — run scripts/schwab_reauth.py")
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
