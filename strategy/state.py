"""
Position State Tracker

Persists the current open position to disk so the recommendation engine
can determine whether to OPEN, HOLD, CLOSE_AND_OPEN, or WAIT.

State file: logs/current_position.json

New multi-account schema (SPEC-090):
  {
    "strategy_key": "bull_put_spread",
    "strategy":   "Bull Put Spread",
    "underlying": "SPX",
    "opened_at":  "2025-01-15",
    "status":     "open",
    "roll_count": 0,
    "rolled_at":  null,
    "notes":      [],
    "closed_at":  null,
    "close_note": null,
    "positions": [
      {
        "account":      "schwab",        // "schwab" | "etrade"
        "short_strike": 5300,
        "long_strike":  5200,
        "contracts":    1,
        "actual_premium": 8.50,
        "expiry":       "2026-06-20",
        "opened_at":    "2026-05-09"
        // ... other position-level fields
      }
    ]
  }

Backward compat: old flat-field states (no "positions" key) are read as if
they were a single Schwab position.  read_state() always returns a flat dict
(strategy metadata + first/primary position merged) so all existing callers
work unchanged.  Use read_all_positions() for multi-account access.
"""

import fcntl
import json
import os
import tempfile
from datetime import date
from typing import Optional

from strategy.catalog import strategy_key as catalog_strategy_key

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "current_position.json")

# Fields that belong to the strategy envelope, not to individual positions.
_META_KEYS = frozenset({
    "strategy", "strategy_key", "underlying", "opened_at", "status",
    "roll_count", "rolled_at", "notes", "closed_at", "close_note",
    "positions",
})


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


def _normalise(data: dict) -> dict:
    """
    Ensure strategy_key is populated and old flat-field states are left as-is.
    Does not convert old states to new format — that happens in read_state().
    """
    if not data.get("strategy_key"):
        try:
            data["strategy_key"] = catalog_strategy_key(data["strategy"])
        except Exception:
            pass
    return data


def _to_flat(data: dict) -> dict:
    """
    Return a flat dict (strategy metadata + primary position fields merged).
    Works for both new-format (has positions[]) and old-format states.
    """
    if "positions" not in data:
        return _normalise(dict(data))
    positions = data.get("positions") or []
    if not positions:
        return _normalise({k: v for k, v in data.items() if k != "positions"})
    # Merge strategy metadata with first position fields.
    # Position fields win on collision (e.g. opened_at is per-position for new states).
    primary = positions[0]
    merged = {k: v for k, v in data.items() if k != "positions"}
    merged.update(primary)
    return _normalise(merged)


def read_state() -> Optional[dict]:
    """
    Return the current open position as a flat dict (backward-compatible).
    For multi-account states returns the primary (first / Schwab) position
    merged with strategy metadata.  Returns None when no open position.
    """
    data = _load_raw()
    if data and data.get("status") == "open":
        return _to_flat(data)
    return None


def read_all_positions() -> Optional[dict]:
    """
    Return the full state dict with positions[].
    Old flat-field states are wrapped as positions=[{account:'schwab', ...}].
    Returns None when no open position.
    """
    data = _load_raw()
    if not data or data.get("status") != "open":
        return None
    if "positions" in data:
        _normalise(data)
        return data
    # Wrap old format
    pos_fields = {k: v for k, v in data.items() if k not in _META_KEYS}
    pos_fields.setdefault("account", "schwab")
    wrapped = {k: v for k, v in data.items() if k in _META_KEYS and k != "positions"}
    wrapped["positions"] = [pos_fields]
    _normalise(wrapped)
    return wrapped


def write_state(
    strategy: str,
    underlying: str = "SPX",
    strategy_key: Optional[str] = None,
    account: str = "schwab",
    add_tranche: bool = False,
    **extra_fields,
) -> None:
    """
    Persist a newly opened position for the given account.

    If the same strategy is already open (multi-account execution):
      - appends (or replaces) the position for this account
      - strategy metadata (opened_at, roll_count, etc.) is unchanged

    If a different strategy is open, or no strategy is open:
      - creates a fresh state with this as the first position
    """
    if strategy_key is None:
        try:
            strategy_key = catalog_strategy_key(strategy)
        except Exception:
            strategy_key = None

    pos_fields = {k: v for k, v in extra_fields.items()
                  if k not in _META_KEYS and v is not None}
    pos_fields["account"] = account
    pos_fields["opened_at"] = date.today().isoformat()

    existing = _load_raw()
    same_strategy = (
        existing
        and existing.get("status") == "open"
        and (
            (strategy_key and existing.get("strategy_key") == strategy_key)
            or existing.get("strategy") == strategy
        )
    )

    if same_strategy and "positions" in existing:
        if add_tranche:
            # Always append — supports multiple tranches per account with different strikes
            existing["positions"].append(pos_fields)
        else:
            # Default: replace existing entry for this account (same-strike update)
            positions = [p for p in (existing.get("positions") or [])
                         if p.get("account") != account]
            positions.append(pos_fields)
            existing["positions"] = positions
        _save(existing)
        return

    if same_strategy and "positions" not in existing:
        # Migrate old flat-field state: wrap existing flat fields + add new account
        old_pos = {k: v for k, v in existing.items() if k not in _META_KEYS}
        old_pos.setdefault("account", "schwab")
        new_state = {k: v for k, v in existing.items() if k in _META_KEYS and k != "positions"}
        new_state["positions"] = [old_pos, pos_fields]
        _save(new_state)
        return

    # Fresh state
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
        "positions":  [pos_fields],
    }
    _save(payload)


def close_position(
    note: Optional[str] = None,
    account: Optional[str] = None,
    **extra_fields,
) -> None:
    """
    Close the position for a specific account (or all accounts).

    account=None  → close all accounts; marks strategy status='closed'
    account='schwab' → remove Schwab leg; strategy stays open if other legs remain
    """
    data = _load_raw()
    if data is None:
        return

    if "positions" in data:
        positions = list(data.get("positions") or [])
        if account:
            positions = [p for p in positions if p.get("account") != account]
        else:
            positions = []
        data["positions"] = positions
        if not positions:
            data["status"]     = "closed"
            data["closed_at"]  = date.today().isoformat()
            data["close_note"] = note or None
        data.update({k: v for k, v in extra_fields.items() if v is not None})
        _save(data)
    else:
        # Old flat-format
        data["status"]     = "closed"
        data["closed_at"]  = date.today().isoformat()
        data["close_note"] = note or None
        data.update({k: v for k, v in extra_fields.items() if v is not None})
        _save(data)


def roll_position(**extra_fields) -> None:
    """
    Record a roll: increments roll_count and updates rolled_at.
    Position-level fields (strikes, expiry, etc.) are updated inside positions[].
    """
    data = _load_raw()
    if data is None or data.get("status") != "open":
        return
    data["roll_count"] = data.get("roll_count", 0) + 1
    data["rolled_at"]  = date.today().isoformat()
    if "positions" in data:
        for pos in data.get("positions") or []:
            pos.update({k: v for k, v in extra_fields.items() if v is not None})
    else:
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
    if "positions" in data:
        for pos in data.get("positions") or []:
            pos.update({k: v for k, v in fields.items() if v is not None})
    else:
        data.update({k: v for k, v in fields.items() if v is not None})
    _save(data)


def get_position_action(new_strategy: str, is_wait: bool, strategy_key: Optional[str] = None) -> str:
    """
    Compare the new recommendation against the stored open position.

    Returns one of:
        "OPEN"           — no position open, enter the new trade
        "HOLD"           — same strategy, keep current position
        "CLOSE_AND_OPEN" — different strategy, close current then open new
        "WAIT"           — no position open, no new trade
        "CLOSE_AND_WAIT" — position open but new signal says wait; close it
    """
    current = read_state()

    if current is None:
        return "WAIT" if is_wait else "OPEN"

    if is_wait:
        return "CLOSE_AND_WAIT"

    current_key = current.get("strategy_key")
    if strategy_key and current_key:
        if current_key == strategy_key:
            return "HOLD"
    elif current["strategy"] == new_strategy:
        return "HOLD"

    return "CLOSE_AND_OPEN"
