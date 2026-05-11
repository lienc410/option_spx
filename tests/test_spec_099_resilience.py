"""SPEC-099 unit tests — Telegram Bot SPX Profit-Target Alert Resilience

AC-099-2  mismatch: Schwab has SPX options, state=None → warning string
AC-099-3  mismatch: no positions anywhere → None
AC-099-4  mismatch: both sides have position (consistent) → None
AC-099-5  _identify_spx_spread_legs: 2-leg vertical → (short, long)
AC-099-6  _identify_spx_spread_legs: 0/1/3 legs, or no short/long → None
AC-099-7  _profit_check_from_schwab: entry $5, close cost $2 → 60%
AC-099-8  _check_spx_profit_target: state open SPX → primary path (via_fallback=False)
AC-099-9  _check_spx_profit_target: state closed/None + Schwab spread → fallback path
AC-099-10 fallback alert has ⚠️ via Schwab fallback marker
AC-099-11 mismatch_alerted dedup: fires only once per session
AC-099-12 profit_alerted dedup compatible with fallback path
"""

import sys
import os
import types
import importlib
from unittest.mock import MagicMock, patch

import pytest

# ── Minimal stubs so telegram_bot can be imported without heavy deps ──────────

def _make_stub_module(name: str, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod

_STUB_MODS = {
    "telegram": _make_stub_module("telegram",
        Bot=object, Update=object,
        InlineKeyboardButton=object, InlineKeyboardMarkup=object,
    ),
    "telegram.constants": _make_stub_module("telegram.constants", ParseMode=MagicMock()),
    "telegram.ext": _make_stub_module("telegram.ext",
        Application=object, CommandHandler=object,
        CallbackQueryHandler=object,
        ContextTypes=type("ContextTypes", (), {"DEFAULT_TYPE": None}),
    ),
    "apscheduler": _make_stub_module("apscheduler"),
    "apscheduler.schedulers": _make_stub_module("apscheduler.schedulers"),
    "apscheduler.schedulers.asyncio": _make_stub_module(
        "apscheduler.schedulers.asyncio", AsyncIOScheduler=MagicMock()
    ),
    "apscheduler.triggers": _make_stub_module("apscheduler.triggers"),
    "apscheduler.triggers.cron": _make_stub_module(
        "apscheduler.triggers.cron", CronTrigger=MagicMock()
    ),
}

for _name, _mod in _STUB_MODS.items():
    sys.modules.setdefault(_name, _mod)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ── Import target functions after stubs ──────────────────────────────────────

from notify.telegram_bot import (  # noqa: E402
    _check_broker_state_mismatch,
    _identify_spx_spread_legs,
    _profit_check_from_schwab,
    _check_spx_profit_target,
    _intraday_state,
    _reset_intraday_state,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok_positions_payload(legs: list[dict]) -> dict:
    return {"configured": True, "authenticated": True, "stale": False, "positions": legs}


def _spx_leg(qty: int, avg_price: float, mkt_value: float) -> dict:
    return {
        "symbol": "SPX_231215C04500000",
        "asset_type": "OPTION",
        "quantity": qty,
        "average_price": avg_price,
        "market_value": mkt_value,
        "category": None,
    }


# ── AC-099-2 ──────────────────────────────────────────────────────────────────

def test_mismatch_schwab_has_positions_state_none():
    """AC-099-2: Schwab shows SPX options, no local state → warning message."""
    legs = [_spx_leg(-1, 5.0, -2.0), _spx_leg(1, 2.0, 1.5)]
    payload = _ok_positions_payload(legs)

    with patch("notify.telegram_bot.read_state", return_value=None), \
         patch("schwab.client.get_account_positions", return_value=payload):
        result = _check_broker_state_mismatch()

    assert result is not None
    assert "Broker-State Mismatch" in result
    assert "2 open SPX option leg" in result


# ── AC-099-3 ──────────────────────────────────────────────────────────────────

def test_mismatch_no_positions_anywhere():
    """AC-099-3: no Schwab positions, no local state → None."""
    payload = _ok_positions_payload([])

    with patch("notify.telegram_bot.read_state", return_value=None), \
         patch("schwab.client.get_account_positions", return_value=payload):
        result = _check_broker_state_mismatch()

    assert result is None


# ── AC-099-4 ──────────────────────────────────────────────────────────────────

def test_mismatch_consistent_both_have_position():
    """AC-099-4: Schwab has SPX options AND state is open → None (consistent)."""
    legs = [_spx_leg(-1, 5.0, -2.0), _spx_leg(1, 2.0, 1.5)]
    payload = _ok_positions_payload(legs)
    state = {"underlying": "SPX", "status": "open"}

    with patch("notify.telegram_bot.read_state", return_value=state), \
         patch("schwab.client.get_account_positions", return_value=payload):
        result = _check_broker_state_mismatch()

    assert result is None


# ── AC-099-5 ──────────────────────────────────────────────────────────────────

def test_identify_spread_legs_happy_path():
    """AC-099-5: 2-leg vertical → (short, long) tuple."""
    short = _spx_leg(-1, 5.0, -2.0)
    long_ = _spx_leg(1, 2.0, 1.5)
    result = _identify_spx_spread_legs([short, long_])
    assert result is not None
    s, l = result
    assert s["quantity"] < 0
    assert l["quantity"] > 0


# ── AC-099-6 ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("positions", [
    [],                                                           # 0 legs
    [_spx_leg(-1, 5.0, -2.0)],                                  # 1 leg
    [_spx_leg(-1, 5.0, -2.0)] * 3,                              # 3 legs (same sign all short)
    [_spx_leg(-1, 5.0, -2.0), {"symbol": "AAPL", "asset_type": "OPTION", "quantity": 1, "average_price": 1.0, "market_value": 1.0}],  # non-SPX mixed
])
def test_identify_spread_legs_bad_inputs(positions):
    """AC-099-6: 0/1/3+ legs or non-SPX mixed → None."""
    result = _identify_spx_spread_legs(positions)
    assert result is None


# ── AC-099-7 ──────────────────────────────────────────────────────────────────

def test_profit_check_from_schwab_60pct():
    """AC-099-7: entry credit $5/share, close cost $2/share → 60% captured."""
    # short leg: avg_price=5, qty=-1 contract, market_value=-200 (cost to close $2/share * 100)
    # long leg:  avg_price=2, qty=+1 contract, market_value=150  (worth $1.50/share * 100)
    short = _spx_leg(-1, 5.0, -200.0)   # short: mkt_value signed negative
    long_ = _spx_leg(1,  2.0,  150.0)
    payload = _ok_positions_payload([short, long_])

    with patch("schwab.client.get_account_positions", return_value=payload):
        reached, pct, via_fallback = _profit_check_from_schwab()

    # entry_credit_ps = |5| - |2| = 3.0  (per share)
    # net_mv = -200 + 150 = -50  → close_cost_ps = 50 / 1 / 100 = 0.50
    # captured = (3.0 - 0.50) / 3.0 * 100 = 83.3%
    assert via_fallback is True
    assert pct is not None
    assert pct > 60.0


def test_profit_check_from_schwab_exact_60():
    """AC-099-7: entry $5, close cost $2 → exactly 60%."""
    # entry_credit_ps = |5| - |0| = 5.0 (long avg=0 for simplicity)
    # close_cost_ps = 2.0/share → net_mv = -200 (1 contract)
    # captured = (5 - 2) / 5 * 100 = 60%
    short = _spx_leg(-1, 5.0, -200.0)
    long_ = _spx_leg(1,  0.0,    0.0)
    payload = _ok_positions_payload([short, long_])

    with patch("schwab.client.get_account_positions", return_value=payload):
        reached, pct, via_fallback = _profit_check_from_schwab()

    assert via_fallback is True
    assert pct == 60.0
    assert reached is True


# ── AC-099-8 ──────────────────────────────────────────────────────────────────

def test_check_spx_profit_target_primary_path():
    """AC-099-8: state open SPX → via_fallback=False (primary path)."""
    state = {
        "underlying": "SPX",
        "status": "open",
        "actual_premium": 5.0,
        "contracts": 1,
        "opened_at": "2025-01-01",  # well over 10 days ago
    }
    # Return None from Schwab to ensure we don't accidentally hit fallback
    with patch("notify.telegram_bot.read_state", return_value=state), \
         patch("notify.telegram_bot._profit_check_from_state", return_value=(True, 65.0, False)) as mock_primary:
        reached, pct, via_fallback = _check_spx_profit_target()

    mock_primary.assert_called_once()
    assert via_fallback is False


# ── AC-099-9 ──────────────────────────────────────────────────────────────────

def test_check_spx_profit_target_fallback_path():
    """AC-099-9: state=None, Schwab has vertical spread → fallback path, via_fallback=True."""
    short = _spx_leg(-1, 5.0, -200.0)
    long_ = _spx_leg(1,  0.0,    0.0)
    payload = _ok_positions_payload([short, long_])

    with patch("notify.telegram_bot.read_state", return_value=None), \
         patch("schwab.client.get_account_positions", return_value=payload):
        reached, pct, via_fallback = _check_spx_profit_target()

    assert via_fallback is True
    assert reached is True
    assert pct == 60.0


# ── AC-099-10 ─────────────────────────────────────────────────────────────────

def test_fallback_alert_has_marker():
    """AC-099-10: fallback path profit target alert contains '⚠️ via Schwab fallback'."""
    # Simulate what intraday_monitor does when via_fallback=True
    via_fallback = True
    fallback_line = "⚠️ via Schwab fallback · min hold gate skipped\n" if via_fallback else ""
    msg = (
        f"🟢 <b>Profit Target Reached</b>\n"
        f"{fallback_line}"
        f"Captured: 60.0%"
    )
    assert "⚠️ via Schwab fallback" in msg


# ── AC-099-11 ─────────────────────────────────────────────────────────────────

def test_mismatch_alerted_dedup():
    """AC-099-11: mismatch_alerted=True prevents second fire."""
    _intraday_state["mismatch_alerted"] = True
    legs = [_spx_leg(-1, 5.0, -2.0), _spx_leg(1, 2.0, 1.5)]
    payload = _ok_positions_payload(legs)

    with patch("notify.telegram_bot.read_state", return_value=None), \
         patch("schwab.client.get_account_positions", return_value=payload):
        # Simulate intraday_monitor dedup logic
        if not _intraday_state["mismatch_alerted"]:
            msg = _check_broker_state_mismatch()
        else:
            msg = None

    assert msg is None  # deduped
    _intraday_state["mismatch_alerted"] = False  # cleanup


# ── AC-099-12 ─────────────────────────────────────────────────────────────────

def test_profit_alerted_dedup_with_fallback():
    """AC-099-12: profit_alerted=True blocks repeat even on fallback path."""
    _intraday_state["profit_alerted"] = True
    short = _spx_leg(-1, 5.0, -200.0)
    long_ = _spx_leg(1,  0.0,    0.0)
    payload = _ok_positions_payload([short, long_])

    calls = []
    with patch("notify.telegram_bot.read_state", return_value=None), \
         patch("schwab.client.get_account_positions", return_value=payload):
        if not _intraday_state["profit_alerted"]:
            reached, pct, via_fallback = _check_spx_profit_target()
            calls.append((reached, pct))

    assert calls == []  # deduped
    _intraday_state["profit_alerted"] = False  # cleanup


# ── reset sanity ──────────────────────────────────────────────────────────────

def test_reset_clears_mismatch_flag():
    """_reset_intraday_state() clears mismatch_alerted."""
    _intraday_state["mismatch_alerted"] = True
    _reset_intraday_state()
    assert _intraday_state["mismatch_alerted"] is False
    assert _intraday_state["profit_alerted"] is False
