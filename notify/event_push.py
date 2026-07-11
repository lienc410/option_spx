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
import re
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

PUSH_STATS = Path(__file__).resolve().parents[1] / "logs" / "push_stats.json"

# SPEC-139 #22 — per-delivery send ledger (one strict-JSON line per push that
# actually reached Telegram). push_stats只累加 sent/fallback/failed 计数，无法
# 溯源"每天 ~7 条无 key 静默件是谁"；此账本补齐 category/about/title/key 逐条。
# 14 日 rotation 与 push_stats 同步；写入位于 SPEC-130 主机 guard 之后（禁发即
# 禁记），且仅在真 200 送达后追加。
PUSH_LEDGER = Path(__file__).resolve().parents[1] / "logs" / "push_ledger.jsonl"

# SPEC-130 — 主机 guard 环境变量。仅 oldair 生产 launchd plists 设置为 "1"；
# 其它任何机器（dev 机、CI、误跑的脚本）deny-by-default 哑火。
PUSH_ENABLE_ENV = "SPX_PUSH_ENABLE"


def push_enabled() -> bool:
    """SPEC-130 (INCIDENT 2026-07-07) — host guard, deny-by-default.

    事故：dev 机 pytest 全量跑经未 mock 的传输层把 ~187+68 条测试夹具推送真
    发给了 PM（本机 .env 真 token + 运行时 env 读取）。"测试触碰生产资源"
    第二实例（#1 = ghost ledger rows, 47648fa）——按二次浮面规则升级为结构
    性修复：凭证在位不再意味着可以发送；只有显式声明为生产推送主机的进程
    （launchd plist 设 SPX_PUSH_ENABLE=1）才允许触达 Telegram。

    防线独立于任何 .env 止血措施（AC-4）：token 完整在位时本函数仍拦住一切
    非生产主机的发送。所有 telegram HTTP 出口（event_push._send、
    telegram_bot._safe_send、遗留直连 sender）都必须先过这里。"""
    return os.getenv(PUSH_ENABLE_ENV, "") == "1"


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


def _record_ledger(meta: Optional[dict], *, quiet: bool, fallback: bool) -> None:
    """SPEC-139 #22 — append one strict-JSON line per delivered push. Fields:
    {ts, category, about, title_head(前40字), dedupe_key(或 null), quiet, fallback}.
    Called ONLY on a real 200 delivery (sent or plain-text fallback), i.e. strictly
    after the SPEC-130 host guard — so a non-production host writes zero ledger
    rows (禁发即禁记), same posture as push_stats. Naked _send(text) callers pass
    meta=None → row is still recorded with null category/about/title/key.
    Rotation keeps the most recent 14 distinct ET days (mirrors _record_push)."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        meta = meta or {}
        title = meta.get("title")
        row = {
            "ts": datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds"),
            "category": meta.get("category"),
            "about": meta.get("about"),
            "title_head": (str(title)[:40] if title else None),
            "dedupe_key": meta.get("dedupe_key"),
            "quiet": bool(quiet),
            "fallback": bool(fallback),
        }
        rows = []
        if PUSH_LEDGER.exists():
            for line in PUSH_LEDGER.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue   # skip a corrupt line, never crash the send path
        rows.append(row)
        # keep rows from the most recent 14 distinct ET dates (== push_stats window)
        keep = set(sorted({r.get("ts", "")[:10] for r in rows if r.get("ts")})[-14:])
        rows = [r for r in rows if r.get("ts", "")[:10] in keep]
        PUSH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        PUSH_LEDGER.write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                    for r in rows))
    except Exception:
        log.exception("event_push: ledger record failed")


_HTML_TAG_RE = re.compile(r"</?(?:b|strong|i|em|u|s|code|pre|a)(?:\s[^>]*)?>",
                          re.IGNORECASE)


def _to_plain(text: str) -> str:
    """Convert an HTML-mode message to readable plain text for the fallback
    resend. H-4 second surfacing (2026-07-07): the fallback used to resend the
    HTML string verbatim, so the PM received literal '&lt;' entities
    ("$-6,006 &lt; 0"). Strip the known formatting tags first, then unescape
    entities (that order, so unescaped '<' can't form fake tags)."""
    out = _HTML_TAG_RE.sub("", text)
    return out.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _send(text: str, *, disable_notification: bool = False,
          meta: Optional[dict] = None) -> bool:
    """H-4 (2026-07-06 incident): the 16:50 governance push contained a raw
    '< 0' comparison, Telegram's HTML parser returned 400, and the message
    vanished with only a log line — no retry, no fallback, no operator
    visibility. Today it was an FYI; on a credit-stop TRIGGER day it would
    be an incident. Policy now: try HTML; on ANY non-200 retry once as PLAIN
    TEXT (delivery beats formatting); count every outcome for the heartbeat.

    SPEC-126: transport ONLY — new callers go through notify.gateway.push
    (category/about contract, dedupe, quiet levels).

    SPEC-130: host guard FIRST — non-production hosts return False with zero
    HTTP and zero stats writes (stats live behind the guard so push_stats
    stays a clean production-delivery ledger).

    SPEC-139 #22: optional `meta` (category/about/title/dedupe_key, supplied by
    gateway.push) is written to logs/push_ledger.jsonl on a real 200 delivery
    for per-send tracing. `meta` is fully optional — legacy naked _send(text)
    callers are unaffected (row recorded with null fields)."""
    if not push_enabled():
        log.info("event_push: %s != 1 — push suppressed (SPEC-130 host guard, "
                 "deny-by-default; only oldair production plists enable it)",
                 PUSH_ENABLE_ENV)
        return False
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log.debug("event_push: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping")
        return False
    payload = {"chat_id": chat_id, "text": text}
    if disable_notification:
        payload["disable_notification"] = True
    try:
        r = requests.post(
            _TELEGRAM_API.format(token=token),
            json={**payload, "parse_mode": "HTML"},
            timeout=8,
        )
        if r.status_code == 200:
            _record_push("sent")
            _record_ledger(meta, quiet=disable_notification, fallback=False)
            return True
        log.warning("event_push: Telegram returned %s: %s — retrying as plain text",
                    r.status_code, r.text[:200])
        r2 = requests.post(
            _TELEGRAM_API.format(token=token),
            json={**payload, "text": _to_plain(text)},
            timeout=8,
        )
        if r2.status_code == 200:
            _record_push("fallback")
            _record_ledger(meta, quiet=disable_notification, fallback=True)
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

    # SPEC-126: PM-initiated action confirmations are STATE (quiet)
    from notify.gateway import push as _gw
    tid = state.get("trade_id", "?")
    _gw("STATE", f"持仓 {tid}", "Position closed (via web)",
        f"Strategy: <b>{_h(strategy)}</b> on <code>{_h(underlying)}</code>\n"
        f"Opened: <code>{_h(opened_at)}</code>{note_line}")

    # Post-close re-entry scan — same as bot's /closed flow. A fresh OPEN
    # candidate is actionable; NO ENTRY is quiet FYI.
    try:
        from strategy.selector import get_recommendation
        from notify.telegram_bot import _format_recommendation, is_market_open
        rec = get_recommendation(use_intraday=is_market_open())
        cat = "FYI" if rec.strategy_key == "reduce_wait" else "ACTION"
        title = ("Re-entry scan · NO ENTRY" if rec.strategy_key == "reduce_wait"
                 else f"Re-entry scan · OPEN 候选 {rec.strategy}")
        _gw(cat, "新开仓", title, _format_recommendation(rec))
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
    from notify.gateway import push as _gw
    tid = state.get("trade_id", "?")
    _gw("STATE", f"持仓 {tid}", "Position opened (via web)",
        f"Strategy: <b>{_h(strategy)}</b> on <code>{_h(underlying)}</code>\n"
        f"Strikes: <code>{_h(strikes)}</code>  ·  Contracts: <code>{_h(contracts)}</code>  ·  "
        f"Expiry: <code>{_h(expiry)}</code>\n"
        f"Entry premium: <code>{_h(premium)}</code>")
