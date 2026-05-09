"""
Lightweight Telegram push for events triggered outside the bot process.

Used by web/server.py so a frontend Close/Open click produces the same
Telegram notification the user would get from `/closed` / `/entered`.

Design notes:
- HTTP-only: no `python-telegram-bot` Application/scheduler imports (avoids
  pulling the bot's full runtime into the Flask process).
- Best-effort: failures log and return False, never raise — UI flow continues.
- Reuses telegram_bot._format_recommendation for consistent messages.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

log = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str) -> bool:
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log.debug("event_push: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping")
        return False
    try:
        r = requests.post(
            _TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
        if r.status_code != 200:
            log.warning("event_push: Telegram returned %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception:
        log.exception("event_push: Telegram send failed")
        return False


def _h(s) -> str:
    """HTML-escape — must match telegram_bot._h."""
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def notify_close(state: dict, note: Optional[str] = None) -> None:
    """
    Push 'Position closed' + post-close re-entry recommendation.
    Mirrors notify/telegram_bot.py::cmd_closed but tagged '(via web)'.
    """
    strategy   = state.get("strategy", "Position")
    underlying = state.get("underlying", "?")
    opened_at  = state.get("opened_at", "?")
    note_line  = f"\nNote: <i>{_h(note)}</i>" if note else ""

    _send(
        f"✅ <b>Position closed</b> <i>(via web)</i>\n"
        f"Strategy: <b>{_h(strategy)}</b> on <code>{_h(underlying)}</code>\n"
        f"Opened: <code>{_h(opened_at)}</code>{note_line}"
    )

    # Post-close re-entry scan — same as bot's /closed flow
    try:
        from strategy.selector import get_recommendation
        from notify.telegram_bot import _format_recommendation, is_market_open
        rec = get_recommendation(use_intraday=is_market_open())
        _send("🔄 <b>Re-entry scan</b> — fresh recommendation:\n\n" + _format_recommendation(rec))
    except Exception:
        log.exception("event_push.notify_close: re-entry scan failed (non-fatal)")


def notify_open(state: dict) -> None:
    """
    Push 'Position opened' notification when frontend submits a new trade.
    """
    strategy   = state.get("strategy", "Position")
    underlying = state.get("underlying", "?")
    short_k    = state.get("short_strike")
    long_k     = state.get("long_strike")
    contracts  = state.get("contracts", "?")
    expiry     = state.get("expiry", "?")
    premium    = state.get("actual_premium") or state.get("model_premium") or "?"

    strikes = f"{short_k}/{long_k}" if long_k else str(short_k or "?")
    _send(
        f"🟢 <b>Position opened</b> <i>(via web)</i>\n"
        f"Strategy: <b>{_h(strategy)}</b> on <code>{_h(underlying)}</code>\n"
        f"Strikes: <code>{_h(strikes)}</code>  ·  Contracts: <code>{_h(contracts)}</code>  ·  "
        f"Expiry: <code>{_h(expiry)}</code>\n"
        f"Entry premium: <code>{_h(premium)}</code>"
    )
