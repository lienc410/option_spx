#!/usr/bin/env python3
"""
E-Trade idle-timer keepalive — runs hourly during RTH+extended via
launchd. Calls renew_access_token() to reset the server-side 2h idle
clock without requiring user interaction.

Renew is idempotent and cheap. If the token is already dead (e.g.
midnight rollover missed, ETrade revoked, machine was off), this exits
non-zero silently — the morning nag cron (etrade_status_notify) is the
canonical alert channel.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("etrade_keepalive")


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    from etrade.auth import is_configured, renew_access_token, token_status

    if not is_configured():
        log.info("ETRADE_CONSUMER_KEY not set — keepalive skipped")
        sys.exit(0)

    status = token_status()
    if not status.get("authenticated"):
        log.info("Token already expired — keepalive cannot help, awaiting manual re-auth")
        sys.exit(0)

    result = renew_access_token()
    if result.get("ok"):
        log.info("keepalive ✓ — new expiry: %s", result.get("expires_at"))
        sys.exit(0)

    log.warning("keepalive renew failed: %s", result.get("reason"))
    sys.exit(0)


if __name__ == "__main__":
    main()
