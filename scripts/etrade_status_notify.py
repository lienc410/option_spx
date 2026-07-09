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


def _send_telegram(text: str) -> bool:
    """SPEC-137: route through the unified gateway (category/about/dedupe +
    host guard live in the transport). Was a legacy direct Telegram sender.

    E-Trade re-auth is a 🔴 ALERT (PM must act now, before the market open);
    dedupe_key keeps it to one nudge per ET day even if the check re-runs."""
    from notify.gateway import escape, push as gw_push
    return gw_push(
        "ALERT", "系统状态", "E-Trade 登录已过期", escape(text),
        dedupe_key="etrade_reauth",
    )


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
    expired = remaining is not None and remaining <= 0
    reason_cn = "已过期" if expired else "即将过期"
    expired_ago = abs(int(remaining / 60)) if remaining is not None and remaining < 0 else None

    msg_lines = [
        f"E-Trade 令牌{reason_cn}" + (f"（{expired_ago} 分钟前）" if expired_ago is not None else "") + "，账户数据这一轨暂时缺席。",
        "",
        "打开这个链接，30 秒重新登录即可恢复：",
        reauth_url,
        "",
        "（E-Trade 令牌每天美东午夜硬过期，属正常机制，不是故障。）",
    ]
    text = "\n".join(msg_lines)
    log.info("Sending E-Trade re-auth notification to Telegram")
    ok = _send_telegram(text)
    if not ok:
        log.error("Notification send failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
