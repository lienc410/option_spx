from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


_ET = ZoneInfo("America/New_York")
TRADE_LOG_FILE = Path(__file__).resolve().parent / "trade_log.jsonl"


def _log_path() -> Path:
    return TRADE_LOG_FILE


def append_event(event: dict) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")


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
        base_rolls = [dict(e) for e in ordered if e.get("event") == "roll"]
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
        resolved.append({
            "id": trade_id,
            "voided": voided,
            "paper_trade": paper_trade,
            "open": base_open,
            "close": base_close,
            "rolls": base_rolls,
            "notes": notes,
            "corrections": corrections,
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
