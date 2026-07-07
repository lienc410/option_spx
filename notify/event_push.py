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

import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

PUSH_STATS = Path(__file__).resolve().parents[1] / "logs" / "push_stats.json"


def _record_push(outcome: str) -> None:
    """H-4: per-day send counters {date: {sent, fallback, failed}} — surfaced
    by ops_heartbeat so a silently-eaten ALERT can never hide again."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        day = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        stats = {}
        if PUSH_STATS.exists():
            try:
                stats = json.loads(PUSH_STATS.read_text())
            except json.JSONDecodeError:
                stats = {}
        d = stats.setdefault(day, {"sent": 0, "fallback": 0, "failed": 0})
        d[outcome] = d.get(outcome, 0) + 1
        for k in sorted(stats)[:-14]:   # keep last 14 days
            stats.pop(k, None)
        PUSH_STATS.parent.mkdir(parents=True, exist_ok=True)
        PUSH_STATS.write_text(json.dumps(stats, indent=1, sort_keys=True))
    except Exception:
        log.exception("event_push: stats record failed")


def _send(text: str) -> bool:
    """H-4 (2026-07-06 incident): the 16:50 governance push contained a raw
    '< 0' comparison, Telegram's HTML parser returned 400, and the message
    vanished with only a log line — no retry, no fallback, no operator
    visibility. Today it was an FYI; on a credit-stop TRIGGER day it would
    be an incident. Policy now: try HTML; on ANY non-200 retry once as PLAIN
    TEXT (delivery beats formatting); count every outcome for the heartbeat."""
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
        if r.status_code == 200:
            _record_push("sent")
            return True
        log.warning("event_push: Telegram returned %s: %s — retrying as plain text",
                    r.status_code, r.text[:200])
        r2 = requests.post(
            _TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": text},
            timeout=8,
        )
        if r2.status_code == 200:
            _record_push("fallback")
            return True
        log.error("event_push: plain-text retry also failed %s: %s",
                  r2.status_code, r2.text[:200])
        _record_push("failed")
        return False
    except Exception:
        log.exception("event_push: Telegram send failed")
        _record_push("failed")
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
