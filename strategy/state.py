"""
Position State Tracker

Persists the current open position to disk so the recommendation engine
can determine whether to OPEN, HOLD, CLOSE_AND_OPEN, or WAIT.

State file: logs/current_position.json
Schema:
  {
    "strategy_key": "bull_put_spread", // stable internal key
    "strategy":   "Bull Put Spread",  // StrategyName value
    "underlying": "SPX",
    "opened_at":  "2025-01-15",       // ISO date of initial entry
    "status":     "open",             // "open" | "closed"
    "roll_count": 0,                  // number of times rolled
    "rolled_at":  null,               // ISO date of last roll (or null)
    "notes":      [],                 // list of free-text notes added via /note
    "closed_at":  null,               // ISO date when closed (or null)
    "close_note": null                // optional reason/note at close
  }

Actions returned by get_position_action():
  OPEN           — no position open, new trade recommended
  HOLD           — same strategy recommended again, keep current position
  CLOSE_AND_OPEN — different strategy recommended, close current and open new
  WAIT           — no new trade recommended (REDUCE_WAIT signal)
  CLOSE_AND_WAIT — position open but new signal says wait; close it
"""

import fcntl
import json
import os
import tempfile
from datetime import date
from typing import Optional

from strategy.catalog import strategy_key as catalog_strategy_key

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "current_position.json")


def _state_path() -> str:
    return os.path.normpath(STATE_FILE)


def _load_raw() -> Optional[dict]:
    """Load state file as-is (regardless of open/closed status)."""
    path = _state_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except (json.JSONDecodeError, OSError):
        return None


def _save(data: dict) -> None:
    """Write atomically: write to a temp file then os.replace() to avoid corruption."""
    path = _state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dir_ = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_state() -> Optional[dict]:
    """
    Return the current position state dict, or None if no state file exists
    or if the stored position is closed.
    """
    data = _load_raw()
    if data and data.get("status") == "open":
        if not data.get("strategy_key"):
            try:
                data["strategy_key"] = catalog_strategy_key(data["strategy"])
            except Exception:
                pass
        return data
    return None


def write_state(
    strategy: str,
    underlying: str = "SPX",
    strategy_key: Optional[str] = None,
    **extra_fields,
) -> None:
    """
    Persist a newly opened position. Initialises all extended fields.
    Creates the logs/ directory if needed.
    """
    if strategy_key is None:
        try:
            strategy_key = catalog_strategy_key(strategy)
        except Exception:
            strategy_key = None
    payload = {
        "strategy_key": strategy_key,
        "strategy":   strategy,
        "underlying": underlying,
        "opened_at":  date.today().isoformat(),
        "status":     "open",
        "roll_count": 0,
        "rolled_at":  None,
        "notes":      [],
        "closed_at":  None,
        "close_note": None,
    }
    payload.update({k: v for k, v in extra_fields.items() if v is not None})
    _save(payload)


def close_position(note: Optional[str] = None, **extra_fields) -> None:
    """
    Mark the current position as closed.
    Optionally records a close reason/note.
    Safe to call even if no position is open.
    """
    data = _load_raw()
    if data is None:
        return
    data["status"]     = "closed"
    data["closed_at"]  = date.today().isoformat()
    data["close_note"] = note or None
    data.update({k: v for k, v in extra_fields.items() if v is not None})
    _save(data)


def roll_position(**extra_fields) -> None:
    """
    Record a roll: increments roll_count and updates rolled_at.
    The position remains open with the same strategy/underlying.
    """
    data = _load_raw()
    if data is None or data.get("status") != "open":
        return
    data["roll_count"] = data.get("roll_count", 0) + 1
    data["rolled_at"]  = date.today().isoformat()
    data.update({k: v for k, v in extra_fields.items() if v is not None})
    _save(data)


def add_note(note: str, **extra_fields) -> None:
    """Append a free-text note to the current open position."""
    data = _load_raw()
    if data is None or data.get("status") != "open":
        return
    notes = data.get("notes") or []
    notes.append(f"{date.today().isoformat()}: {note}")
    data["notes"] = notes
    data.update({k: v for k, v in extra_fields.items() if v is not None})
    _save(data)


def update_open_position(**fields) -> None:
    """Patch the current open position in place without resetting identity fields."""
    data = _load_raw()
    if data is None or data.get("status") != "open":
        return
    data.update({k: v for k, v in fields.items() if v is not None})
    _save(data)


def get_position_action(new_strategy: str, is_wait: bool, strategy_key: Optional[str] = None) -> str:
    """
    Compare the new recommendation against the stored open position.

    Args:
        new_strategy: StrategyName value of the new recommendation.
        is_wait: True if the recommendation is REDUCE_WAIT (no trade).

    Returns one of:
        "OPEN"           — no position open, enter the new trade
        "HOLD"           — same strategy, keep current position
        "CLOSE_AND_OPEN" — different strategy, close current then open new
        "WAIT"           — no position open, no new trade
        "CLOSE_AND_WAIT" — position open but new signal says wait; close it
    """
    current = read_state()

    if current is None:
        # No open position
        return "WAIT" if is_wait else "OPEN"

    # Position is open
    if is_wait:
        return "CLOSE_AND_WAIT"

    current_key = current.get("strategy_key")
    if strategy_key and current_key:
        if current_key == strategy_key:
            return "HOLD"
    elif current["strategy"] == new_strategy:
        return "HOLD"

    return "CLOSE_AND_OPEN"
