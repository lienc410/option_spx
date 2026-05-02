"""BCD debit stop tightening (SPEC-080).

当 bcd_stop_tightening_mode == "active" 时，BCD debit stop loss 从 -0.50 收紧到 -0.35。
"""
from __future__ import annotations
import json
from pathlib import Path

BCD_STOP_DEFAULT  = -0.50   # legacy hardcoded value; non-BCD debit strategies
BCD_STOP_TIGHTER  = -0.35   # Q038 Phase 2C plateau; BCD when mode=active

_ENGINE_LOG = Path("data/bcd_stop_shadow_engine.jsonl")
_LIVE_LOG   = Path("data/bcd_stop_shadow_live.jsonl")


def bcd_debit_stop(mode: str) -> float:
    """Return the effective BCD debit stop ratio for the current mode."""
    if mode == "active":
        return BCD_STOP_TIGHTER
    return BCD_STOP_DEFAULT


def log_bcd_stop_event(
    date: str,
    pnl_ratio: float,
    mode: str,
    source: str = "engine",   # "engine" | "live"
) -> None:
    """Log a would-be BCD stop trigger event (shadow and active modes)."""
    path = _LIVE_LOG if source == "live" else _ENGINE_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "date": date, "pnl_ratio": round(pnl_ratio, 4),
            "mode": mode, "source": source,
            "stop_active": BCD_STOP_TIGHTER,
            "stop_legacy": BCD_STOP_DEFAULT,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass
