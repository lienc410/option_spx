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


def _send(text: str, *, disable_notification: bool = False) -> bool:
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
    stays a clean production-delivery ledger)."""
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
            return True
        log.warning("event_push: Telegram returned %s: %s — retrying as plain text",
                    r.status_code, r.text[:200])
        r2 = requests.post(
            _TELEGRAM_API.format(token=token),
            json=payload,
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
