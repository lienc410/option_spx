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
        # NLV must include cash. E*Trade `netMv` is net market value of POSITIONS
        # only (excludes cash) — using it understated NLV by the cash balance
        # (verified 2026-06-04: netMv 604,285 vs totalAccountValue 634,843, diff
        # = 30,558 cash). `totalAccountValue` (RealTimeValues) == `liquidatingEquity`
        # (PortfolioMargin) is the true account NLV; netMv only as last resort.
        "net_liquidation": _num(
            realtime.get("totalAccountValue")
            or portfolio_margin.get("liquidatingEquity")
            or realtime.get("netMv")
        ),
        # SPEC-107 followup 2026-05-27: ETrade `totalMarginRqmts` is the
        # authoritative PM/Reg-T maintenance margin requirement (= house
        # requirement when broker applies house surcharge). DO NOT silently
        # fall back to `maintenanceCall` (which is a $ call amount, normally 0)
        # nor `marginBalance` (which is the outstanding margin LOAN balance —
        # not a margin requirement; using it would misreport maintenance by
        # 100%+ if the requirement fields go null). If both real fields are
        # absent, returning None forces downstream (portfolio_surface) to show
        # "—" rather than disguising loan balance as BP usage.
        "maintenance_margin": _num(
            portfolio_margin.get("totalMarginRqmts")
            or portfolio_margin.get("totalHouseRequirement")
        ),
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
    option_type: str = "PUT",
    long_expiry: str | None = None,
) -> dict:
    """Mark/bid/ask for a vertical or diagonal spread (PUT or CALL).
    mark = (bid+ask)/2 per leg, spread_mark = short_mid - long_mid (credit-
    spread convention, so debit spreads return a negative mark).

    `long_expiry` defaults to `expiry` (vertical); pass a later date to
    look the long leg up on a different chain (true diagonal). When the
    two legs share an expiry, both strikes are batched into a single
    get_quote call. Diagonals run two get_quote calls (one per leg).
    """
    side = "CALL" if str(option_type).upper().startswith("C") else "PUT"
    long_exp = long_expiry or expiry
    cache_key = f"optquote:{underlier}:{expiry}:{long_exp}:{side}:{short_strike}:{long_strike}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if not is_token_valid():
        return {"visible": False, "error": "token_invalid"}
    try:
        client = _market_client()
        # SPX → SPXW disambiguation per leg's own expiry (Mon/Wed weeklies on
        # one leg, monthly 3rd-Fri on the other is a real case for diagonals).
        def _sym(strike: float, exp_iso: str) -> str:
            yy, mm, dd = exp_iso.split("-")
            ticker = _etrade_spx_ticker(exp_iso) if str(underlier).upper() == "SPX" else underlier
            return f"{ticker}:{yy}:{mm}:{dd}:{side}:{int(strike)}"

        def _fetch_one(strike: float, exp_iso: str) -> dict:
            payload = client.get_quote([_sym(strike, exp_iso)],
                                       detail_flag="options", resp_format="json")
            rows = _as_list(_dig(payload, "QuoteResponse", "QuoteData"))
            row = rows[0] if rows else {}
            opt = row.get("Option") or {}
            bid = _num(opt.get("bid"))
            ask = _num(opt.get("ask"))
            mark = round((bid + ask) / 2, 2) if bid is not None and ask is not None else None
            return {
                "bid": bid, "ask": ask, "mark": mark,
                "quote_status":  row.get("quoteStatus"),
                "ah_flag":       row.get("ahFlag"),
                "date_time_utc": row.get("dateTimeUTC"),
            }

        if long_exp == expiry:
            # Vertical: batch both strikes in one call (preserves prior behavior)
            yy, mm, dd = expiry.split("-")
            ticker = _etrade_spx_ticker(expiry) if str(underlier).upper() == "SPX" else underlier
            payload = client.get_quote(
                [f"{ticker}:{yy}:{mm}:{dd}:{side}:{int(short_strike)}",
                 f"{ticker}:{yy}:{mm}:{dd}:{side}:{int(long_strike)}"],
                detail_flag="options", resp_format="json",
            )
            quotes = {
                float(q["Product"]["strikePrice"]): q
                for q in _as_list(_dig(payload, "QuoteResponse", "QuoteData"))
                if _dig(q, "Product", "strikePrice") is not None
            }
            def _extract(strike: float) -> dict:
                row = quotes.get(float(strike), {})
                opt = row.get("Option") or {}
                bid = _num(opt.get("bid")); ask = _num(opt.get("ask"))
                mark = round((bid + ask) / 2, 2) if bid is not None and ask is not None else None
                return {"bid": bid, "ask": ask, "mark": mark,
                        "quote_status":  row.get("quoteStatus"),
                        "ah_flag":       row.get("ahFlag"),
                        "date_time_utc": row.get("dateTimeUTC")}
            short = _extract(short_strike)
            long_ = _extract(long_strike)
        else:
            # Diagonal: per-leg fetches (different chains)
            short = _fetch_one(short_strike, expiry)
            long_ = _fetch_one(long_strike, long_exp)
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
        # Spread freshness = worst-of the two legs. PM sees the spread mark as a
        # single number, so its freshness can only be as good as the weaker leg.
        # Rank: lower index = better. Unknown/missing → DELAYED (safe default).
        _QS_RANK = {
            "REALTIME": 0,
            "INDICATIVE_REALTIME": 1,
            "EH_REALTIME": 2,
            "CLOSING": 3,
            "DELAYED": 4,
            "EH_BEFORE_OPEN": 5,
            "EH_CLOSED": 6,
            "INVALID": 7,
        }
        def _worse(a: str | None, b: str | None) -> str | None:
            ra = _QS_RANK.get(a, 4)  # unknown ≈ DELAYED
            rb = _QS_RANK.get(b, 4)
            return a if ra >= rb else b
        spread_status = _worse(short.get("quote_status"), long_.get("quote_status"))
        spread_dt_utc = None
        for dt in (short.get("date_time_utc"), long_.get("date_time_utc")):
            if dt is not None and (spread_dt_utc is None or dt < spread_dt_utc):
                spread_dt_utc = dt  # older of the two — matches worst-of timing
        result = {
            "visible": spread_mark is not None,
            "mark": spread_mark,
            "bid": spread_bid,
            "ask": spread_ask,
            "short_leg": short,
            "long_leg": long_,
            "source": "etrade_quote",
            "quote_status":  spread_status,
            "ah_flag":       bool(short.get("ah_flag")) or bool(long_.get("ah_flag")),
            "date_time_utc": spread_dt_utc,
        }
        _cache_put(cache_key, result)
        return result
    except Exception as exc:
        log.warning("etrade.client: get_option_spread_quote failed", exc_info=True)
        return {"visible": False, "error": str(exc)}


def _etrade_spx_ticker(expiry: str) -> str:
    """ETrade splits SPX into two distinct option tickers; Schwab does not.

    - SPX  = AM-settled monthly, listed ONLY on 3rd Friday of each month
    - SPXW = PM-settled weeklies, listed on all other Mon/Wed/Fri dates
            (and ALSO on 3rd Friday as a separate PM-settled product)
    Schwab returns AM-settled (3rd Fri) data under SPX symbol; PM-settled
    weeklies also under SPX. We must disambiguate when querying ETrade.

    Returns "SPX" for 3rd-Friday expiries, "SPXW" otherwise.
    """
    try:
        y, m, d = expiry.split("-")
        dt = datetime(int(y), int(m), int(d))
    except (ValueError, TypeError):
        return "SPXW"
    if dt.weekday() != 4:  # not Friday → must be SPXW
        return "SPXW"
    return "SPX" if 15 <= dt.day <= 21 else "SPXW"


def get_option_quotes_by_strike(
    underlier: str,
    expiry: str,
    option_type: str,
    strikes: list[float],
) -> dict[float, dict]:
    """Batch-fetch ETrade bid/ask/mark for a list of strikes at one expiry+type.

    Returns {strike_float: {bid, ask, mid, quote_status, ah_flag, date_time_utc}}.
    Empty dict if token invalid or call fails — caller must treat absence as
    'no ETrade data', not error.
    """
    if not strikes:
        return {}
    cleaned: list[float] = []
    for s in strikes:
        try:
            cleaned.append(float(s))
        except (TypeError, ValueError):
            continue
    if not cleaned:
        return {}
    side = "CALL" if str(option_type).upper().startswith("C") else "PUT"
    # ETrade SPX→SPXW disambiguation: caller passes Schwab's underlier
    # ('SPX'), we pick the right ETrade ticker per expiry.
    etrade_ticker = _etrade_spx_ticker(expiry) if str(underlier).upper() == "SPX" else underlier
    cache_key = f"optquotes:{etrade_ticker}:{expiry}:{side}:{','.join(f'{s:.0f}' for s in sorted(cleaned))}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    if not is_token_valid():
        return {}
    try:
        y, m, d = expiry.split("-")
        symbols = [f"{etrade_ticker}:{y}:{m}:{d}:{side}:{int(round(s))}" for s in cleaned]
        client = _market_client()
        payload = client.get_quote(symbols, detail_flag="options", resp_format="json")
        out: dict[float, dict] = {}
        for q in _as_list(_dig(payload, "QuoteResponse", "QuoteData")):
            strike = _dig(q, "Product", "strikePrice")
            if strike is None:
                continue
            opt = q.get("Option") or {}
            bid = _num(opt.get("bid"))
            ask = _num(opt.get("ask"))
            mid = round((bid + ask) / 2, 2) if bid is not None and ask is not None else None
            out[float(strike)] = {
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "quote_status": q.get("quoteStatus"),
                "ah_flag": q.get("ahFlag"),
                "date_time_utc": q.get("dateTimeUTC"),
            }
        _cache_put(cache_key, out)
        return out
    except Exception:
        log.warning("etrade.client: get_option_quotes_by_strike failed", exc_info=True)
        return {}


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


# ── SPEC-110 T3 transaction helpers ────────────────────────────────────────────

# E*Trade transaction type → 5-bucket classification
_TX_BUCKET: dict[str, str] = {
    # Cash inflows
    "ATNM": "cash_flow_in",
    "BAL": "cash_flow_in",
    "CONT": "cash_flow_in",
    "DPO": "cash_flow_in",
    "FRMBNK": "cash_flow_in",
    "FRCES": "cash_flow_in",
    "FRTBK": "cash_flow_in",
    "PTC": "cash_flow_in",
    "MR": "cash_flow_in",
    # Cash outflows
    "PTD": "cash_flow_out",
    "TOBNK": "cash_flow_out",
    "TOCES": "cash_flow_out",
    "TOTBK": "cash_flow_out",
    "WITHDRW": "cash_flow_out",
    # Realized trade P&L (net of buy cost + sell proceeds)
    "BUY": "realized_trade_pnl",
    "SELL": "realized_trade_pnl",
    "COMP": "realized_trade_pnl",
    "CONV": "realized_trade_pnl",
    "ESPP": "realized_trade_pnl",
    "SWAP": "realized_trade_pnl",
    # Fees / interest / margin charges (typically negative)
    "INR": "fees",
    "INT": "fees",
    "JRNLM": "fees",
    "JRNL": "fees",
    # Dividends / reinvestment
    "CSD": "dividends",
    "DIV": "dividends",
    "MMF": "dividends",
    "REINV": "dividends",
    "SDRSP": "dividends",
}

_EMPTY_MONTH: dict[str, float] = {
    "cash_flow_in": 0.0,
    "cash_flow_out": 0.0,
    "realized_trade_pnl": 0.0,
    "fees": 0.0,
    "dividends": 0.0,
}


def _normalize_transaction(raw: Any) -> dict | None:
    """Normalize one PyEtrade transaction dict."""
    if not isinstance(raw, dict):
        return None
    tx_type = str(raw.get("transactionType") or raw.get("type") or "").upper()
    amount = _num(raw.get("amount") or raw.get("netAmount"))
    date_str = str(raw.get("transactionDate") or raw.get("date") or "")[:10]
    if not date_str:
        return None
    return {
        "date": date_str,
        "type": tx_type,
        "amount": amount or 0.0,
        "description": str(raw.get("description") or raw.get("desc") or ""),
        "bucket": _TX_BUCKET.get(tx_type, "other"),
    }


def list_transactions_for_period(
    start_date: str,
    end_date: str,
    account_id: str | None = None,
) -> list[dict]:
    """SPEC-110 T3: page through PyEtrade list_transactions; return normalized list.

    Uses 50-per-page paging. PyEtrade supports up to 2 years of history.
    On token invalid / API failure: returns empty list (fail-soft).
    """
    if not is_token_valid():
        log.warning("etrade.client: list_transactions_for_period — token invalid, returning empty")
        return []
    try:
        client = _accounts_client()
        acct = _resolve_account_id(client, account_id)
        if not acct:
            log.warning("etrade.client: list_transactions_for_period — account_id unavailable")
            return []

        all_txs: list[dict] = []
        marker = None
        max_pages = 40  # safety cap against paging loops

        for _ in range(max_pages):
            kwargs: dict = {
                "account_id_key": acct,
                "start_date": start_date,
                "end_date": end_date,
                "sort_order": "ASC",
                "count": 50,
            }
            if marker:
                kwargs["marker"] = marker

            payload = client.list_transactions(**kwargs)
            response = _dig(payload, "TransactionListResponse") or payload

            tx_list = response.get("Transaction") or response.get("transaction") or []
            if not isinstance(tx_list, list):
                tx_list = [tx_list] if tx_list else []

            for raw in tx_list:
                normed = _normalize_transaction(raw)
                if normed:
                    all_txs.append(normed)

            # Paging marker
            marker = response.get("marker") or response.get("Marker")
            if not marker or not tx_list:
                break

        return all_txs
    except Exception as exc:
        log.warning("etrade.client: list_transactions_for_period failed", exc_info=True)
        return []


def derive_monthly_pnl_from_transactions(
    start_date: str,
    end_date: str,
    account_id: str | None = None,
) -> dict[str, dict]:
    """SPEC-110 T3: group transactions by month; classify into 5 buckets.

    Returns: {YYYY-MM: {cash_flow_in, cash_flow_out, realized_trade_pnl,
                        fees, dividends, net_change}}

    NOT a source-of-truth for NLV — used as audit cross-check only.
    """
    txs = list_transactions_for_period(start_date, end_date, account_id)

    by_month: dict[str, dict[str, float]] = {}
    for tx in txs:
        ym = str(tx.get("date") or "")[:7]  # YYYY-MM
        if not ym:
            continue
        if ym not in by_month:
            by_month[ym] = dict(_EMPTY_MONTH)
        bucket = tx.get("bucket", "other")
        amount = float(tx.get("amount") or 0.0)
        if bucket in by_month[ym]:
            by_month[ym][bucket] += amount

    # Compute net_change per month
    for ym, m in by_month.items():
        m["net_change"] = round(
            m["cash_flow_in"]
            + m["cash_flow_out"]  # typically negative
            + m["realized_trade_pnl"]
            + m["fees"]
            + m["dividends"],
            2,
        )
        for k in list(m.keys()):
            if k != "net_change":
                m[k] = round(m[k], 2)

    return by_month
