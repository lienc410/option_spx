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
    expire_token_on_401,
    is_configured,
    is_token_valid,
    load_token,
    record_token_issue,
    token_status,
)


log = logging.getLogger(__name__)
_ET = ZoneInfo("America/New_York")
_CACHE: dict[str, tuple[float, Any]] = {}


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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
        if not isinstance(item, dict):
            continue
        desc = str(item.get("accountDesc") or item.get("accountName") or "").lower()
        if "pm brokerage" in desc or desc == "pm":
            value = item.get("accountIdKey") or item.get("accountId")
            if value:
                return str(value)
    for item in accounts:
        for key in ("accountIdKey", "accountId", "account_id"):
            value = item.get(key) if isinstance(item, dict) else None
            if value:
                return str(value)
    return None


def _normalize_balance_payload(payload: dict) -> dict:
    response = _dig(payload, "BalanceResponse") or payload
    computed = response.get("Computed") or {}
    realtime = computed.get("RealTimeValues") or {}
    portfolio_margin = computed.get("PortfolioMargin") or {}
    return {
        "configured": True,
        "authenticated": True,
        "net_liquidation": _num(realtime.get("netMv") or portfolio_margin.get("liquidatingEquity")),
        "maintenance_margin": _num(portfolio_margin.get("totalMarginRqmts")
        or portfolio_margin.get("totalHouseRequirement")
        or computed.get("maintenanceCall")
        or computed.get("marginBalance")),
        "cash_balance": _num(computed.get("cashAvailableForWithdrawal")
        or computed.get("totalAvailableForWithdrawal")
        or computed.get("cashBalance")),
        "margin_balance": _num(computed.get("marginBalance")),
        "option_buying_power": _num(computed.get("optionLevel3OptionBuyingPower")
        or computed.get("optionBuyingPower")
        or computed.get("marginBuyingPower")),
        "buying_power": _num(computed.get("marginBuyingPower")
        or computed.get("cashBuyingPower")),
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
    except Exception as exc:
        log.warning("etrade.client: get_account_balances failed", exc_info=True)
        _resp = getattr(exc, "response", None)
        if _resp is not None and getattr(_resp, "status_code", 0) == 401:
            expire_token_on_401()
        else:
            record_token_issue("balances_failed")
        return _fail_soft_balances()


def _market_client():
    pyetrade = _load_pyetrade()
    token = load_token() or {}
    return pyetrade.ETradeMarket(
        consumer_key(),
        consumer_secret(),
        token.get("oauth_token"),
        token.get("oauth_token_secret"),
        dev=False,
    )


def get_option_spread_quote(
    underlier: str,
    expiry: str,
    short_strike: float,
    long_strike: float,
) -> dict:
    """Mark/bid/ask for a put spread. mark = (bid+ask)/2 per leg, spread_mark = short - long."""
    cache_key = f"optquote:{underlier}:{expiry}:{short_strike}:{long_strike}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if not is_token_valid():
        return {"visible": False, "error": "token_invalid"}
    try:
        y, m, d = expiry.split("-")

        def sym(strike: float) -> str:
            return f"{underlier}:{y}:{m}:{d}:PUT:{int(strike)}"

        client = _market_client()
        payload = client.get_quote(
            [sym(short_strike), sym(long_strike)],
            detail_flag="options",
            resp_format="json",
        )
        # Key by strikePrice (float) — Product.symbol is just "SPX" for all rows
        quotes = {
            float(q["Product"]["strikePrice"]): q
            for q in _as_list(_dig(payload, "QuoteResponse", "QuoteData"))
            if _dig(q, "Product", "strikePrice") is not None
        }

        def extract(strike: float) -> dict:
            row = quotes.get(float(strike), {})
            opt = row.get("Option") or {}  # E-Trade puts bid/ask under "Option", not "All"
            bid = _num(opt.get("bid"))
            ask = _num(opt.get("ask"))
            mark = round((bid + ask) / 2, 2) if bid is not None and ask is not None else None
            return {"bid": bid, "ask": ask, "mark": mark}

        short = extract(short_strike)
        long_ = extract(long_strike)
        spread_bid = (
            round(short["bid"] - long_["ask"], 2)
            if short["bid"] is not None and long_["ask"] is not None
            else None
        )
        spread_ask = (
            round(short["ask"] - long_["bid"], 2)
            if short["ask"] is not None and long_["bid"] is not None
            else None
        )
        spread_mark = (
            round((spread_bid + spread_ask) / 2, 2)
            if spread_bid is not None and spread_ask is not None
            else None
        )
        result = {
            "visible": spread_mark is not None,
            "mark": spread_mark,
            "bid": spread_bid,
            "ask": spread_ask,
            "short_leg": short,
            "long_leg": long_,
            "source": "etrade_quote",
        }
        _cache_put(cache_key, result)
        return result
    except Exception as exc:
        log.warning("etrade.client: get_option_spread_quote failed", exc_info=True)
        return {"visible": False, "error": str(exc)}


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
            "positions": _normalize_position_rows(client.get_account_portfolio(acct, resp_format="json")),
            "stale": False,
            "updated_at": datetime.now(_ET).isoformat(timespec="seconds"),
        }
        clear_token_issue()
        _cache_put(f"positions:{acct}", payload)
        return payload
    except Exception as exc:
        log.warning("etrade.client: get_account_positions failed", exc_info=True)
        _resp = getattr(exc, "response", None)
        if _resp is not None and getattr(_resp, "status_code", 0) == 401:
            expire_token_on_401()
        else:
            record_token_issue("positions_failed")
        return _fail_soft_positions()
