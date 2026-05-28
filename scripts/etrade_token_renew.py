#!/usr/bin/env python3
"""
E-Trade token renewal — runs via launchd at 23:30 ET daily on oldair.

Calls E-Trade's renew_access_token API while the current token is still
valid (before midnight ET). This extends the token for another 24 hours
with zero user interaction — no password, no browser, no verifier.

Only requires full re-auth (etrade_reauth.py) if:
  - This cron fails AND the token expires (e.g. machine was off at 23:30)
  - OR the oauth_token is revoked on E-Trade's side
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
log = logging.getLogger("etrade_renew")


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    from etrade.auth import is_configured, renew_access_token, token_status

    if not is_configured():
        log.error("ETRADE_CONSUMER_KEY / ETRADE_CONSUMER_SECRET not set — skipping")
        sys.exit(0)

    status = token_status()
    if not status.get("authenticated"):
        remaining = status.get("token_expires_in", 0) or 0
        log.error(
            "E-Trade token already expired (%ds ago) — "
            "cannot renew, full re-auth required via etrade_reauth.py",
            abs(remaining),
        )
        sys.exit(1)

    remaining = status.get("token_expires_in", 0) or 0
    log.info("Current token valid, expires in %ds (~%.1fh)", remaining, remaining / 3600)

    result = renew_access_token()
    if result.get("ok"):
        log.info("E-Trade token renewed ✓ — new expiry: %s", result.get("expires_at"))
    else:
        log.error("Renewal failed: %s", result.get("reason"))
        sys.exit(1)


if __name__ == "__main__":
    main()
