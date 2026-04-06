from __future__ import annotations

import time
from datetime import datetime, time as dtime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from schwab.auth import ensure_access_token, is_configured, load_token, token_status


_ET = ZoneInfo("America/New_York")
_CACHE: dict[str, tuple[float, Any]] = {}
BASE_URL = "https://api.schwabapi.com"


def _ttl() -> int:
    now = datetime.now(_ET)
    if now.weekday() >= 5:
        return 300
    return 60 if dtime(9, 30) <= now.time() <= dtime(16, 0) else 300


def _cache_get(key: str):
    item = _CACHE.get(key)
    if item and (time.time() - item[0]) < _ttl():
        return item[1]
    return None


def _cache_put(key: str, value):
    _CACHE[key] = (time.time(), value)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ensure_access_token()}"}


def _account_number() -> str:
    token = load_token() or {}
    acct = token.get("account_number")
    if not acct:
        raise RuntimeError("auth_required")
    return str(acct)


def _extract_quote_greeks(instrument: dict) -> dict:
    return {
        "mark": instrument.get("mark") or instrument.get("marketValue"),
        "bid": instrument.get("bidPrice"),
        "ask": instrument.get("askPrice"),
        "delta": instrument.get("delta"),
        "gamma": instrument.get("gamma"),
        "theta": instrument.get("theta"),
        "vega": instrument.get("vega"),
    }


def get_account_positions() -> dict:
    if not is_configured():
      return {"configured": False, "authenticated": False, "positions": []}
    cached = _cache_get("positions")
    if cached is not None:
        return cached
    try:
        acct = _account_number()
        res = requests.get(
            f"{BASE_URL}/trader/v1/accounts/{acct}",
            params={"fields": "positions"},
            headers=_headers(),
            timeout=20,
        )
        res.raise_for_status()
        raw = res.json()
        sec_acct = raw.get("securitiesAccount", raw)
        positions = []
        for pos in sec_acct.get("positions", []) or []:
            instr = pos.get("instrument", {})
            parsed = {
                "symbol": instr.get("symbol"),
                "description": instr.get("description"),
                "quantity": pos.get("longQuantity", 0) - pos.get("shortQuantity", 0),
                "unrealized_pnl": pos.get("currentDayProfitLoss") or pos.get("marketValue") - pos.get("averagePrice", 0),
            }
            parsed.update(_extract_quote_greeks(pos))
            positions.append(parsed)
        payload = {"configured": True, "authenticated": True, "positions": positions, "stale": False}
        _cache_put("positions", payload)
        return payload
    except Exception:
        status = token_status()
        return {"configured": status["configured"], "authenticated": status["authenticated"], "positions": [], "stale": True}


def get_account_balances() -> dict:
    if not is_configured():
        return {"configured": False, "authenticated": False, "stale": False}
    cached = _cache_get("balances")
    if cached is not None:
        return cached
    try:
        acct = _account_number()
        res = requests.get(
            f"{BASE_URL}/trader/v1/accounts/{acct}",
            headers=_headers(),
            timeout=20,
        )
        res.raise_for_status()
        raw = res.json()
        sec_acct = raw.get("securitiesAccount", raw)
        balances = sec_acct.get("currentBalances", {})
        initial = balances.get("initialMarginRequirement") or balances.get("initialMargin")
        maintenance = balances.get("maintenanceRequirement") or balances.get("maintenanceMargin")
        buying_power = balances.get("buyingPower") or balances.get("availableFundsNonMarginableTrade")
        net_liq = balances.get("liquidationValue") or balances.get("netLiquidation")
        payload = {
            "configured": True,
            "authenticated": True,
            "buying_power": buying_power,
            "option_buying_power": balances.get("optionBuyingPower") or buying_power,
            "net_liquidation": net_liq,
            "initial_margin": initial,
            "maintenance_margin": maintenance,
            "stale": False,
            "updated_at": datetime.now(_ET).isoformat(timespec="seconds"),
        }
        _cache_put("balances", payload)
        return payload
    except Exception:
        status = token_status()
        return {"configured": status["configured"], "authenticated": status["authenticated"], "stale": True}


def _find_matching_position(positions: list[dict], state: dict | None) -> dict | None:
    if not positions:
        return None
    if not state:
        return positions[0]
    expiry = str(state.get("expiry") or "")
    short_strike = str(int(float(state["short_strike"]))) if state.get("short_strike") is not None else ""
    for pos in positions:
        symbol = str(pos.get("symbol") or "")
        if expiry.replace("-", "")[:6] in symbol and short_strike and short_strike in symbol:
            return pos
    return positions[0]


def live_position_snapshot(state: dict | None) -> dict:
    positions_payload = get_account_positions()
    if not positions_payload.get("configured") or not positions_payload.get("authenticated"):
        return {"visible": False, **positions_payload}
    positions = positions_payload.get("positions", [])
    pos = _find_matching_position(positions, state)
    if not pos:
        return {"visible": False, **positions_payload}
    entry = None
    if state and state.get("actual_premium") is not None and pos.get("mark") is not None:
        try:
            contracts = float(state.get("contracts", 1))
            entry = round((float(state["actual_premium"]) - float(pos["mark"])) * contracts * 100, 2)
        except Exception:
            entry = None
    return {
        "visible": True,
        "stale": positions_payload.get("stale", False),
        "mark": pos.get("mark"),
        "bid": pos.get("bid"),
        "ask": pos.get("ask"),
        "delta": pos.get("delta"),
        "gamma": pos.get("gamma"),
        "theta": pos.get("theta"),
        "vega": pos.get("vega"),
        "unrealized_pnl": pos.get("unrealized_pnl"),
        "trade_log_pnl": entry,
        "symbol": pos.get("symbol"),
    }
