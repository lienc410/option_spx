from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


_ET = ZoneInfo("America/New_York")
TRADE_LOG_FILE = Path(__file__).resolve().parent / "trade_log.jsonl"

# SPEC-123 §4a — trade-id allocation and the append of its open event must sit
# in ONE critical section. Production incident 2026-06-03: two concurrent
# /api/position/open requests both allocated 2026-06-03_bcd_001 (allocation
# happened BEFORE the multi-second governance evaluation, append after) — two
# distinct BCD positions shared one id, resolve_log() silently swallowed the
# second open, and a later correction targeting _001 became ambiguous.
# Endpoints hold this lock from next_trade_id() through append_event().
ID_ALLOC_LOCK = threading.Lock()


def _log_path() -> Path:
    return TRADE_LOG_FILE


def append_event(event: dict) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")


def append_events(events: list[dict]) -> None:
    """SPEC-127 §2 — append a batch of events in ONE buffered write + fsync.

    Used by the atomic roll flow: all per-leg roll events of one submission
    either land together or (on an I/O error before the write completes) not
    at all. This is deliberately a single fh.write of the joined lines, not a
    loop of append_event calls — a mid-loop failure would leave a partial
    roll in the ledger with no rollback handle."""
    if not events:
        return
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(e, default=str) + "\n" for e in events)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(payload)
        fh.flush()
        import os
        os.fsync(fh.fileno())


def load_log() -> list[dict]:
    path = _log_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def load_log_by_id(trade_id: str) -> list[dict]:
    return [row for row in load_log() if row.get("id") == trade_id]


def resolve_log() -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    raw = load_log()
    for row in raw:
        trade_id = row.get("id")
        if not trade_id:
            continue
        grouped.setdefault(trade_id, []).append(row)

    resolved: list[dict] = []
    for trade_id, events in grouped.items():
        ordered = sorted(events, key=lambda r: (str(r.get("timestamp", "")), str(r.get("event", ""))))
        voided = any(e.get("event") == "void" for e in ordered)
        corrections = [e for e in ordered if e.get("event") == "correction"]
        base_open = next((dict(e) for e in ordered if e.get("event") == "open"), None)
        base_close = next((dict(e) for e in ordered if e.get("event") == "close"), None)
        # SPEC-127 §2: a roll_void event (written only by the atomic-roll
        # rollback path) removes the roll it targets from resolution. Legacy
        # rolls without roll_id are never voidable.
        voided_roll_ids = {e.get("roll_id") for e in ordered
                           if e.get("event") == "roll_void" and e.get("roll_id")}
        base_rolls = [dict(e) for e in ordered if e.get("event") == "roll"
                      and (e.get("roll_id") is None or e.get("roll_id") not in voided_roll_ids)]
        notes = [dict(e) for e in ordered if e.get("event") == "note"]

        for corr in corrections:
            fields = corr.get("fields") or {}
            target = corr.get("target_event")
            if target == "open" and base_open:
                base_open.update(fields)
            elif target == "close" and base_close:
                base_close.update(fields)
            elif target == "roll" and base_rolls:
                # SPEC-036 assumption confirmed by PM: patch the most recent roll.
                base_rolls[-1].update(fields)

        paper_trade = bool((base_open or {}).get("paper_trade", False))
        # SPEC-123 §4a integrity flag: >1 open under one id means a historical
        # id collision (see ID_ALLOC_LOCK note). The extra opens are NOT merged
        # or dropped silently anymore — downstream consumers can see the flag.
        open_events = [e for e in ordered if e.get("event") == "open"]
        resolved.append({
            "id": trade_id,
            "voided": voided,
            "paper_trade": paper_trade,
            "open": base_open,
            "close": base_close,
            "rolls": base_rolls,
            "notes": notes,
            "corrections": corrections,
            "duplicate_open_count": len(open_events) if len(open_events) > 1 else 0,
            # SPEC-127 §1: campaign_id defaults to the trade's own id — every
            # legacy trade is a degenerate one-member campaign.
            "campaign_id": (base_open or {}).get("campaign_id") or trade_id,
        })

    return sorted(resolved, key=lambda r: r["id"])


def strategy_abbrev(strategy_key: str) -> str:
    parts = [p for p in str(strategy_key or "").split("_") if p]
    if not parts:
        return "trade"
    return "".join(p[0] for p in parts)


def next_trade_id(strategy_key: str, now: datetime | None = None) -> str:
    ts = now or datetime.now(_ET)
    day = ts.date().isoformat()
    prefix = f"{day}_{strategy_abbrev(strategy_key)}_"
    seq = 1
    for row in load_log():
        rid = str(row.get("id", ""))
        if rid.startswith(prefix):
            try:
                seq = max(seq, int(rid.rsplit("_", 1)[-1]) + 1)
            except ValueError:
                continue
    return f"{prefix}{seq:03d}"
