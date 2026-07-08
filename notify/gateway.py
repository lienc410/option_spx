"""SPEC-126 — unified notification gateway. THE single send entrance.

Every push to the PM goes through push() (sync processes: web, launchd jobs)
or apush() (bot process). Direct sends are CI-banned outside the two
transports (event_push._send / telegram_bot._safe_send), which only this
module and the transports' own modules may call.

Message contract (both enforced, missing → raise):
  category — 🔴 ALERT   needs PM action now (credit stop TRIGGER, halt)
             🟡 ACTION  suggested action (OPEN/CLOSE/ROLL, reviews)
             🔵 STATE   position state (HOLD, watch cleared)
             ⚪ FYI     verdicts / snapshots / routine (paper, digests)
  about    — first-line self-identification, one of the ratified forms:
             "新开仓" / "持仓 <标识>" / "系统状态" (rendered as 关于新开仓 /
             关于持仓 X / 系统状态). Kills the HOLD-vs-NO ENTRY ambiguity: the
             reader always knows which object a state word refers to.

Vocabulary: new-entry verdict pushes use the DESIGN.md action-state words
(NO ENTRY, not WAIT / 观望 / free text) — see DESIGN.md §Push Vocabulary.

Policies:
  dedupe    — dedupe_key sends once per ET day; a later push with the same
              key only goes out if its category priority is HIGHER
              (upgrade-only resend: WARNING→TRIGGER passes, repeats drop).
  clears    — a clearing message (mark fell back, watch over) only follows
              a key that actually fired today, and goes out silent.
  quiet     — FYI/STATE default disable_notification=True (no bell);
              ALERT/ACTION ring.
  delivery  — transports retry HTML→plain text (H-4) and count outcomes in
              logs/push_stats.json for the heartbeat.

Body is sent with parse_mode=HTML. Callers composing PLAIN TEXT must wrap the
whole body with escape() — never escape fragments (the 7/6 push died on a raw
'<' in a gate detail; the 7/7 push died AGAIN on a raw '<0' two lines below
the fragment-level fix). Callers using intentional tags (<b>/<code>) escape
their dynamic fields themselves.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEDUPE_PATH = ROOT / "data" / ".push_dedupe.json"
ET = ZoneInfo("America/New_York")

CATEGORY_EMOJI = {"ALERT": "🔴", "ACTION": "🟡", "STATE": "🔵", "FYI": "⚪"}
_PRIORITY = {"FYI": 0, "STATE": 1, "ACTION": 2, "ALERT": 3}

log = logging.getLogger("gateway")


def escape(s) -> str:
    """HTML-escape a whole plain-text body at the push boundary (matches
    telegram_bot._h / event_push._h). State files and logs keep plain text —
    only what goes to the transport is escaped."""
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _today() -> str:
    return datetime.now(ET).date().isoformat()


def _load_dedupe() -> dict:
    if DEDUPE_PATH.exists():
        try:
            d = json.loads(DEDUPE_PATH.read_text())
            if d.get("date") == _today():
                return d
        except json.JSONDecodeError:
            pass
    return {"date": _today(), "keys": {}}


def _save_dedupe(d: dict) -> None:
    DEDUPE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEDUPE_PATH.write_text(json.dumps(d, sort_keys=True))


def _compose(category: str, about: str, title: str, body: str) -> str:
    about = about.strip()
    first = about if about == "系统状态" else (
        about if about.startswith("关于") else f"关于{about}")
    parts = [f"{CATEGORY_EMOJI[category]} [{category}] {first}"]
    if title:
        parts.append(f"<b>{title}</b>")
    if body:
        parts.append(body)
    return "\n".join(parts)


def prepare(category: str, about: str, title: str, body: str = "", *,
            dedupe_key: str | None = None, clears: str | None = None,
            disable_notification: bool | None = None):
    """Shared policy core. Returns (text, disable_notification) when the
    message should go out, or None when policy suppresses it. Raises on a
    missing/unknown category or empty about (AC: contract violations are
    loud, never silently reformatted)."""
    if category not in CATEGORY_EMOJI:
        raise ValueError(f"gateway: unknown category {category!r} "
                         f"(must be one of {sorted(CATEGORY_EMOJI)})")
    if not (about or "").strip():
        raise ValueError("gateway: 'about' is required — 新开仓 / 持仓 <标识> / 系统状态")

    d = _load_dedupe()
    if clears is not None:
        # clearing messages only follow an alert that fired today, quietly
        if clears not in d["keys"]:
            log.info("gateway: clear for %r suppressed (nothing fired today)", clears)
            return None
        disable_notification = True
    if dedupe_key is not None:
        prev = d["keys"].get(dedupe_key)
        if prev is not None and _PRIORITY[category] <= _PRIORITY.get(prev, 3):
            log.info("gateway: dedupe %r (already sent as %s today)", dedupe_key, prev)
            return None
        d["keys"][dedupe_key] = category
        _save_dedupe(d)

    if disable_notification is None:
        disable_notification = category in ("FYI", "STATE")
    return _compose(category, about, title, body), disable_notification


def push(category: str, about: str, title: str, body: str = "", *,
         dedupe_key: str | None = None, clears: str | None = None,
         disable_notification: bool | None = None) -> bool:
    """Sync entrance (web / launchd / scripts processes)."""
    prepared = prepare(category, about, title, body, dedupe_key=dedupe_key,
                       clears=clears, disable_notification=disable_notification)
    if prepared is None:
        return False
    text, quiet = prepared
    from notify.event_push import _send
    return _send(text, disable_notification=quiet)


async def apush(bot, chat_id: str, category: str, about: str, title: str,
                body: str = "", *, dedupe_key: str | None = None,
                clears: str | None = None,
                disable_notification: bool | None = None) -> bool:
    """Async entrance (bot process)."""
    prepared = prepare(category, about, title, body, dedupe_key=dedupe_key,
                       clears=clears, disable_notification=disable_notification)
    if prepared is None:
        return False
    text, quiet = prepared
    from notify.telegram_bot import _safe_send
    return await _safe_send(bot, chat_id, text, disable_notification=quiet)
