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
CLOSED_TRADES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "closed_trades.jsonl")


# Strategy-key → bucket label used in closed_trades.jsonl + attribution jsonl
# (matches daily_snapshot.jsonl's strategies.{bucket}.positions key).
_STRATEGY_BUCKET = {
    "bull_put_spread": "spx_spread",
    "bear_call_spread": "spx_spread",
}


def _append_closed_trade_rows(legs_to_close, *, exit_premium, exit_reason,
                              close_note, strategy_key, underlying):
    """Best-effort auto-hook: append one row per closing leg to
    data/closed_trades.jsonl so Journal Cum P&L picks up realized PnL
    without manual seeding. Per-leg fills aren't captured (broker only
    reports spread credit/debit) — compute_greek_attribution.py splits
    proportionally from chain marks on opened_at/closed_at.
    """
    if not legs_to_close or exit_premium in (None, ""):
        return
    try:
        exit_debit = float(exit_premium)
    except (TypeError, ValueError):
        return
    bucket = _STRATEGY_BUCKET.get(strategy_key, strategy_key or "unknown")
    closed_at_iso = date.today().isoformat()
    try:
        os.makedirs(os.path.dirname(CLOSED_TRADES_FILE), exist_ok=True)
        with open(CLOSED_TRADES_FILE, "a") as f:
            for leg in legs_to_close:
                try:
                    entry_credit = float(leg.get("actual_premium"))
                except (TypeError, ValueError):
                    continue
                try:
                    contracts = float(leg.get("contracts", 1))
                except (TypeError, ValueError):
                    contracts = 1
                realized = round((entry_credit - exit_debit) * contracts * 100, 2)
                row = {
                    "trade_id":     leg.get("trade_id"),
                    "strategy":     bucket,
                    "account":      leg.get("account") or "schwab",
                    "underlying":   underlying or "SPX",
                    "short_strike": leg.get("short_strike"),
                    "long_strike":  leg.get("long_strike"),
                    "contracts":    int(contracts),
                    "expiry":       leg.get("expiry"),
                    "opened_at":    leg.get("opened_at"),
                    "closed_at":    closed_at_iso,
                    "entry_credit_per_share": entry_credit,
                    "exit_debit_per_share":   exit_debit,
                    "realized_pnl":           realized,
                    "close_reason": exit_reason or close_note,
                    "seeded_from":  "auto_hook_close_position",
                }
                f.write(json.dumps(row) + "\n")
    except Exception as exc:
        import sys
        print(f"[close_position] closed_trades append failed: {exc}", file=sys.stderr)

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
    trade_id: Optional[str] = None,
    **extra_fields,
) -> None:
    """
    Close legs of the open position.

    Priority of leg-selection filters:
      trade_id=X   → close ONLY that single leg (lets caller close one at a time
                     with leg-specific exit_premium, used for the per-position
                     close UI in /spx)
      account=Y    → close all legs of broker Y (legacy single-price flow)
      both None    → close every open leg
    """
    data = _load_raw()
    if data is None:
        return

    # Capture legs about to close before mutation, then auto-append closed_trades.jsonl
    if "positions" in data:
        all_legs = list(data.get("positions") or [])
        if trade_id:
            legs_to_close = [p for p in all_legs if p.get("trade_id") == trade_id]
        elif account:
            legs_to_close = [p for p in all_legs if p.get("account") == account]
        else:
            legs_to_close = list(all_legs)
    else:
        legs_to_close = [data]  # old flat-format treated as single leg
    _append_closed_trade_rows(
        legs_to_close,
        exit_premium=extra_fields.get("exit_premium"),
        exit_reason=extra_fields.get("exit_reason"),
        close_note=note,
        strategy_key=data.get("strategy_key"),
        underlying=data.get("underlying"),
    )

    if "positions" in data:
        positions = list(data.get("positions") or [])
        if trade_id:
            positions = [p for p in positions if p.get("trade_id") != trade_id]
        elif account:
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
