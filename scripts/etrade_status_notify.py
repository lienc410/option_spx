#!/usr/bin/env python3
"""
E-Trade daily token check + Telegram notification.

Runs via launchd at 06:00 ET. If E-Trade token is expired/invalid, sends a
Telegram message with a link to the /etrade/reauth web UI. If the token is
still valid (e.g. user already re-auth'd this morning), exits silently.

Reads:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  from .env  (existing pattern)
  ETRADE_REAUTH_URL                      optional; defaults to the public
                                        Cloudflare tunnel /etrade/reauth
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from urllib.parse import quote

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("etrade_notify")

DEFAULT_REAUTH_URL = "https://www.portimperialventures.com/etrade/reauth"


def _telegram_creds() -> tuple[str, str]:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _send_telegram(text: str) -> bool:
    import requests
    # SPEC-130 host guard — 遗留直连 sender 也必须 deny-by-default
    # （长期应迁移到 notify.gateway；guard 先封口）
    from notify.event_push import push_enabled
    if not push_enabled():
        log.info("etrade_status_notify: SPX_PUSH_ENABLE != 1 — send suppressed (SPEC-130)")
        return False
    token, chat_id = _telegram_creds()
    if not token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — cannot send notification")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown",
                  "disable_web_page_preview": True},
            timeout=15,
        )
        if r.ok:
            log.info("Telegram sent")
            return True
        log.error("Telegram send failed %d: %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        log.error("Telegram error: %s", e)
        return False


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    from etrade.auth import is_configured, token_status

    if not is_configured():
        log.error("ETRADE_CONSUMER_KEY / ETRADE_CONSUMER_SECRET not set — skipping check")
        sys.exit(0)

    status = token_status()
    remaining = status.get("token_expires_in")

    if status.get("authenticated") and remaining and remaining > 600:
        log.info("E-Trade token valid (%.1f h remaining) — no notification needed", remaining / 3600)
        sys.exit(0)

    reauth_url = os.getenv("ETRADE_REAUTH_URL", DEFAULT_REAUTH_URL)
    reason = "expired" if (remaining is not None and remaining <= 0) else "expiring soon"
    expired_ago = abs(int(remaining / 60)) if remaining is not None and remaining < 0 else None

    msg_lines = [
        "🔑 *E-Trade re-auth needed*",
        "",
        f"Token {reason}" + (f" ({expired_ago} min ago)" if expired_ago is not None else ""),
        "",
        f"Open this link to re-auth in 30 seconds:",
        f"[{reauth_url}]({reauth_url})",
        "",
        "_E-Trade tokens hard-expire at midnight ET daily; this is by design._",
    ]
    text = "\n".join(msg_lines)
    log.info("Sending E-Trade re-auth notification to Telegram")
    ok = _send_telegram(text)
    if not ok:
        log.error("Notification send failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
