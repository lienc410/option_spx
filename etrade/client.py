from __future__ import annotations

import logging
import time
from datetime import datetime, time as dtime
from typing import Any
from zoneinfo import ZoneInfo

from etrade.auth import (
    account_id as configured_account_id,
    clear_token_issue,
    consumer_key,
    consumer_secret,
    is_configured,
    is_token_valid,
    load_token,
    record_token_issue,
    token_status,
)


log = logging.getLogger(__name__)
_ET = ZoneInfo("America/New_York")
_CACHE: dict[str, tuple[float, Any]] = {}


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


def _cache_put(key: str, value) -> None:
    _CACHE[key] = (time.time(), value)


def _load_pyetrade():
    try:
        import pyetrade  # type: ignore

        return pyetrade
    except Exception as exc:  # pragma: no cover - exercised via fail-soft tests
        raise RuntimeError("pyetrade_missing") from exc


def _accounts_client():
    pyetrade = _load_pyetrade()
    token = load_token() or {}
    return pyetrade.ETradeAccounts(
        consumer_key(),
        consumer_secret(),
        token.get("oauth_token"),
        token.get("oauth_token_secret"),
        dev=False,
    )


def _fail_soft_positions() -> dict:
    status = token_status()
    return {
        "configured": status["configured"],
        "authenticated": status["authenticated"],
        "positions": [],
        "stale": True,
    }


def _fail_soft_balances() -> dict:
    status = token_status()
    return {
        "configured": status["configured"],
        "authenticated": status["authenticated"],
        "stale": True,
    }


def _invalid_token_positions() -> dict:
    status = token_status()
    return {
        "configured": status["configured"],
        "authenticated": False,
        "positions": [],
        "stale": True,
    }


def _invalid_token_balances() -> dict:
    status = token_status()
    return {
        "configured": status["configured"],
        "authenticated": False,
        "stale": True,
    }


def _dig(payload: Any, *keys: str) -> Any:
    cur = payload
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _resolve_account_id(client: Any, account_id: str | None = None) -> str | None:
    if account_id:
        return account_id
    if configured_account_id():
        return configured_account_id()
    try:
        payload = client.list_accounts()
    except Exception:
        return None
    accounts = _as_list(_dig(payload, "AccountListResponse", "Accounts", "Account"))
    for item in accounts:
        for key in ("accountIdKey", "accountId", "account_id"):
            value = item.get(key) if isinstance(item, dict) else None
            if value:
                return str(value)
    return None


def _normalize_balance_payload(payload: dict) -> dict:
    response = _dig(payload, "BalanceResponse") or payload
    computed = _dig(response, "Computed", "marginBuyingPowerDetails") or {}
    account_balance = _dig(response, "Computed", "cashAvailableForInvestment") or {}
    return {
        "configured": True,
        "authenticated": True,
        "net_liquidation": _dig(response, "accountValue", "netMv"),
        "maintenance_margin": computed.get("maintenanceCall") or computed.get("marginBalance"),
        "cash_balance": account_balance.get("cashAvailableForWithdrawal")
        or account_balance.get("totalAvailableForWithdrawal"),
        "margin_balance": computed.get("marginBalance"),
        "option_buying_power": computed.get("optionLevel3OptionBuyingPower")
        or computed.get("optionBuyingPower"),
        "buying_power": computed.get("marginBuyingPower")
        or computed.get("cashBuyingPower"),
        "updated_at": datetime.now(_ET).isoformat(timespec="seconds"),
        "stale": False,
        "raw": response,
    }


def _normalize_position_rows(payload: dict) -> list[dict]:
    response = _dig(payload, "PortfolioResponse") or payload
    accounts = _as_list(response.get("AccountPortfolio"))
    rows: list[dict] = []
    for acct in accounts:
        for pos in _as_list(acct.get("Position")):
            product = pos.get("Product") or {}
            quantity = pos.get("quantity") or pos.get("quantityAvailable") or pos.get("qty")
            rows.append({
                "symbol": product.get("symbol") or product.get("securityType"),
                "description": product.get("description") or product.get("callPut"),
                "asset_type": product.get("securityType"),
                "quantity": quantity,
                "market_value": pos.get("marketValue"),
                "unrealized_pnl": pos.get("totalGain"),
                "price_paid": pos.get("pricePaid"),
                "position_type": pos.get("positionType"),
            })
    return rows


def get_account_balances(account_id: str | None = None) -> dict:
    if not is_configured():
        return {"configured": False, "authenticated": False, "stale": False}
    cached = _cache_get(f"balances:{account_id or 'default'}")
    if cached is not None:
        return cached
    if not is_token_valid():
        record_token_issue("token_invalid")
        return _invalid_token_balances()
    try:
        client = _accounts_client()
        acct = _resolve_account_id(client, account_id)
        if not acct:
            record_token_issue("account_missing")
            return _fail_soft_balances()
        payload = _normalize_balance_payload(client.get_account_balance(acct))
        clear_token_issue()
        _cache_put(f"balances:{acct}", payload)
        return payload
    except Exception:
        log.warning("etrade.client: get_account_balances failed", exc_info=True)
        record_token_issue("balances_failed")
        return _fail_soft_balances()


def get_account_positions(account_id: str | None = None) -> dict:
    if not is_configured():
        return {"configured": False, "authenticated": False, "positions": [], "stale": False}
    cached = _cache_get(f"positions:{account_id or 'default'}")
    if cached is not None:
        return cached
    if not is_token_valid():
        record_token_issue("token_invalid")
        return _invalid_token_positions()
    try:
        client = _accounts_client()
        acct = _resolve_account_id(client, account_id)
        if not acct:
            record_token_issue("account_missing")
            return _fail_soft_positions()
        payload = {
            "configured": True,
            "authenticated": True,
            "positions": _normalize_position_rows(client.get_account_portfolio(acct)),
            "stale": False,
            "updated_at": datetime.now(_ET).isoformat(timespec="seconds"),
        }
        clear_token_issue()
        _cache_put(f"positions:{acct}", payload)
        return payload
    except Exception:
        log.warning("etrade.client: get_account_positions failed", exc_info=True)
        record_token_issue("positions_failed")
        return _fail_soft_positions()
