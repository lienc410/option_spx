from __future__ import annotations

import time
from datetime import date, datetime, time as dtime, timedelta
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


def _marketdata_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    if raw in {"SPX"} and not raw.startswith("$"):
        return f"${raw}"
    return raw


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


def _quote_cache_key(symbol: str) -> str:
    return f"quote:{symbol}"


def _normalize_quote(symbol: str, payload: dict) -> dict:
    quote = payload.get("quote") or {}
    trade_time_raw = quote.get("tradeTime")
    quote_time = None
    if trade_time_raw not in (None, ""):
        try:
            quote_time = datetime.fromtimestamp(
                float(trade_time_raw) / 1000.0,
                tz=ZoneInfo("UTC"),
            ).astimezone(_ET).isoformat(timespec="seconds")
        except (TypeError, ValueError, OSError):
            quote_time = None
    return {
        "symbol": payload.get("symbol") or symbol,
        "last": quote.get("lastPrice"),
        "open": quote.get("openPrice"),
        "high": quote.get("highPrice"),
        "low": quote.get("lowPrice"),
        "close": quote.get("closePrice"),
        "quote_time": quote_time,
        "security_status": quote.get("securityStatus"),
        "realtime": payload.get("realtime"),
    }


def get_index_quote(symbol: str) -> dict:
    if not is_configured():
        raise RuntimeError("not_configured")
    normalized_symbol = str(symbol or "").strip().upper()
    cache_key = _quote_cache_key(normalized_symbol)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    res = requests.get(
        f"{BASE_URL}/marketdata/v1/quotes",
        params={"symbols": normalized_symbol, "fields": "quote"},
        headers=_headers(),
        timeout=20,
    )
    res.raise_for_status()
    data = res.json()
    if data.get("errors", {}).get("invalidSymbols"):
        raise RuntimeError(f"invalid_symbol:{normalized_symbol}")
    raw = data.get(normalized_symbol)
    if not isinstance(raw, dict):
        raise RuntimeError(f"quote_unavailable:{normalized_symbol}")
    normalized = _normalize_quote(normalized_symbol, raw)
    _cache_put(cache_key, normalized)
    return normalized


def get_vix_quote() -> dict:
    return get_index_quote("$VIX")


def get_spx_quote() -> dict:
    return get_index_quote("$SPX")


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
                "asset_type": instr.get("assetType"),
                "quantity": pos.get("longQuantity", 0) - pos.get("shortQuantity", 0),
                "market_value": pos.get("marketValue"),
                "average_price": pos.get("averagePrice"),
                "unrealized_pnl": pos.get("marketValue", 0) - pos.get("averagePrice", 0) * abs(pos.get("longQuantity", 0) - pos.get("shortQuantity", 0)),
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
        cash_bal = balances.get("cashBalance") or balances.get("availableFunds") or 0.0
        payload = {
            "configured": True,
            "authenticated": True,
            "buying_power": buying_power,
            "option_buying_power": balances.get("optionBuyingPower") or buying_power,
            "net_liquidation": net_liq,
            "initial_margin": initial,
            "maintenance_margin": maintenance,
            "cash_balance": float(cash_bal),
            "stale": False,
            "updated_at": datetime.now(_ET).isoformat(timespec="seconds"),
        }
        _cache_put("balances", payload)
        return payload
    except Exception:
        status = token_status()
        return {"configured": status["configured"], "authenticated": status["authenticated"], "stale": True}


def _chain_cache_key(
    symbol: str,
    option_type: str,
    target_dte: int,
    dte_range: int,
    center_strike: float | None = None,
    strike_window: int | None = None,
) -> str:
    if center_strike is None:
        return f"chain:{symbol}:{option_type}:{target_dte}:{dte_range}"
    center_key = int(round(float(center_strike)))
    window_key = int(strike_window) if strike_window is not None else 0
    return f"chain:{symbol}:{option_type}:{target_dte}:{dte_range}:{center_key}:{window_key}"


def _parse_chain_response(payload: dict, option_type: str) -> list[dict]:
    chain_key = "callExpDateMap" if option_type.upper() == "CALL" else "putExpDateMap"
    exp_map = payload.get(chain_key) or {}
    rows: list[dict] = []
    for expiry_key, strike_map in exp_map.items():
        expiry = str(expiry_key).split(":", 1)[0]
        dte_raw = str(expiry_key).split(":", 1)[1] if ":" in str(expiry_key) else None
        try:
            dte = int(float(dte_raw)) if dte_raw is not None else None
        except ValueError:
            dte = None
        for strike_key, contracts in (strike_map or {}).items():
            for contract in contracts or []:
                bid = contract.get("bid")
                ask = contract.get("ask")
                mark = contract.get("mark")
                try:
                    strike = float(strike_key)
                except (TypeError, ValueError):
                    strike = contract.get("strikePrice")
                mid = mark
                if mid in (None, "") and bid not in (None, "") and ask not in (None, ""):
                    try:
                        mid = (float(bid) + float(ask)) / 2.0
                    except (TypeError, ValueError):
                        mid = None
                try:
                    spread_pct = ((float(ask) - float(bid)) / float(mid)) if mid not in (None, 0, "0") else None
                except (TypeError, ValueError, ZeroDivisionError):
                    spread_pct = None
                rows.append({
                    "expiry": expiry,
                    "strike": strike,
                    "bid": bid,
                    "ask": ask,
                    "mid": round(float(mid), 4) if mid not in (None, "") else None,
                    "spread_pct": round(float(spread_pct), 6) if spread_pct is not None else None,
                    "delta": contract.get("delta"),
                    "gamma": contract.get("gamma"),
                    "theta": contract.get("theta"),
                    "vega": contract.get("vega"),
                    "open_interest": contract.get("openInterest"),
                    "volume": contract.get("totalVolume"),
                    "dte": dte if dte is not None else contract.get("daysToExpiration"),
                    "iv": contract.get("volatility"),
                    "rho": contract.get("rho"),
                    "expiry_type": contract.get("expirationType"),
                    "open": contract.get("openPrice"),
                    "high": contract.get("highPrice"),
                    "low": contract.get("lowPrice"),
                    "close": contract.get("closePrice"),
                    "last": contract.get("last"),
                    "quote_time_in_long": contract.get("quoteTimeInLong"),
                    "trade_time_in_long": contract.get("tradeTimeInLong"),
                })
    return rows


_FUTURES_MONTH_CODES = "FGHJKMNQUVXZ"  # Jan-Dec → F G H J K M N Q U V X Z


def _is_futures_symbol(symbol: str) -> bool:
    return str(symbol or "").strip().startswith("/")


def _futures_option_symbol(future_root: str, expiry_iso: str, option_type: str, strike: float) -> str:
    """Build a Schwab futures-option symbol: ./<ROOT><MONTH_CODE><YY><P|C><STRIKE>."""
    y, m, _ = expiry_iso.split("-")
    month_code = _FUTURES_MONTH_CODES[int(m) - 1]
    yy = y[-2:]
    cp = "P" if option_type.upper() == "PUT" else "C"
    return f"./{future_root}{month_code}{yy}{cp}{int(strike)}"


def _bsm_delta_put(spot: float, strike: float, dte: int, sigma: float, r: float = 0.04) -> float:
    """Black-Scholes put delta. Returns negative value in [-1, 0]."""
    import math
    if dte <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    T = dte / 365.0
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    # N(d1) via erf
    def _N(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    return _N(d1) - 1.0


def get_futures_option_chain(
    symbol: str,
    option_type: str,
    target_dte: int,
    dte_range: int = 21,
    center_strike: float | None = None,
    strike_window: int = 30,
    spot: float | None = None,
    sigma: float | None = None,
) -> list[dict]:
    """Build a futures option chain via expirationchain + bulk quotes.

    Schwab's marketdata/v1/chains endpoint does NOT support futures (returns
    400). Instead we list expirations via expirationchain, construct option
    symbols, and bulk-quote them. Greeks are computed via BSM since quotes
    don't include delta/gamma/theta for futures options.

    spot + sigma are required for BSM delta. If omitted, delta will be None
    and downstream scan_strikes will filter those rows out.
    """
    if not is_configured():
        return []
    if not _is_futures_symbol(symbol):
        return []

    cache_key = _chain_cache_key(
        symbol, option_type.upper(), int(target_dte), int(dte_range),
        center_strike=center_strike, strike_window=int(strike_window),
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 1) List available expirations
    res = requests.get(
        f"{BASE_URL}/marketdata/v1/expirationchain",
        params={"symbol": symbol},
        headers=_headers(), timeout=15,
    )
    res.raise_for_status()
    exps = (res.json() or {}).get("expirationList") or []
    if not exps:
        _cache_put(cache_key, [])
        return []

    # 2) Sort candidates by DTE distance to target — try in order, first one
    #    with at least one valid quote wins (some expirations are reported by
    #    Schwab but options don't actually exist for them).
    target = int(target_dte)
    candidates = sorted(exps, key=lambda e: abs(int(e.get("daysToExpiration", 0)) - target))

    # 3) Strike grid (shared across attempts). /ES monthlies use 25-pt grid
    #    across the body of the chain (5-pt grids exist only at the
    #    immediate money on some weeklies, so 25 is the safe default for
    #    49-DTE targets).
    if center_strike is None or center_strike <= 0:
        center_strike = 5000.0
    step = 25
    half = max(int(strike_window), 5)
    center_rounded = int(round(float(center_strike) / step) * step)
    strikes = list(range(center_rounded - half * step, center_rounded + (half + 1) * step, step))

    # 4) Probe candidates until one returns valid quotes
    expiry_iso = None
    actual_dte = target
    future_root = "ES"
    quotes: dict = {}
    symbols: list[str] = []
    for cand in candidates:
        cand_expiry = cand.get("expirationDate")
        cand_dte = int(cand.get("daysToExpiration", target))
        cand_root = cand.get("optionRoots") or symbol.lstrip("/").split()[0] or "ES"
        # Skip if DTE too far from target unless we've exhausted closer options
        if abs(cand_dte - target) > int(dte_range) and expiry_iso is not None:
            break
        cand_symbols = [_futures_option_symbol(cand_root, cand_expiry, option_type, k) for k in strikes]
        # Probe: quote just the center strike first (cheap canary)
        canary = cand_symbols[len(cand_symbols) // 2]
        try:
            cq = requests.get(
                f"{BASE_URL}/marketdata/v1/quotes",
                params={"symbols": canary, "fields": "quote"},
                headers=_headers(), timeout=15,
            )
            cq.raise_for_status()
            cjson = cq.json() or {}
        except Exception:
            continue
        if not (isinstance(cjson.get(canary), dict) and "quote" in cjson[canary]):
            continue
        # Canary valid → bulk-quote full grid
        try:
            q = requests.get(
                f"{BASE_URL}/marketdata/v1/quotes",
                params={"symbols": ",".join(cand_symbols), "fields": "quote"},
                headers=_headers(), timeout=20,
            )
            q.raise_for_status()
            full_quotes = q.json() or {}
        except Exception:
            continue
        # Check how many valid
        valid_count = sum(1 for s in cand_symbols if isinstance(full_quotes.get(s), dict) and "quote" in full_quotes[s])
        if valid_count == 0:
            continue
        expiry_iso = cand_expiry
        actual_dte = cand_dte
        future_root = cand_root
        symbols = cand_symbols
        quotes = full_quotes
        break

    if not symbols or not quotes:
        _cache_put(cache_key, [])
        return []

    # 5) Parse rows
    rows: list[dict] = []
    for sym, strike in zip(symbols, strikes):
        entry = quotes.get(sym)
        if not isinstance(entry, dict) or "quote" not in entry:
            continue
        qd = entry["quote"]
        bid = qd.get("bidPrice")
        ask = qd.get("askPrice")
        try:
            bid_f = float(bid) if bid not in (None, "") else None
            ask_f = float(ask) if ask not in (None, "") else None
        except (TypeError, ValueError):
            bid_f = ask_f = None
        # Mid = (bid + ask) / 2 when both > 0; otherwise use mark / last
        # Drop broken quotes (typically stale weekend/after-hours data):
        # ask=0 or bid>ask means no real market — skip the row.
        if bid_f is None or ask_f is None or ask_f <= 0 or bid_f > ask_f:
            continue
        mid = (bid_f + ask_f) / 2.0
        spread_pct = (ask_f - bid_f) / mid if mid > 0 else None
        # Compute BSM delta when spot + sigma given (futures quotes have no greeks)
        delta = None
        if spot is not None and sigma is not None:
            try:
                if option_type.upper() == "PUT":
                    delta = _bsm_delta_put(float(spot), float(strike), int(actual_dte), float(sigma))
                else:
                    delta = _bsm_delta_put(float(spot), float(strike), int(actual_dte), float(sigma)) + 1.0
            except Exception:
                delta = None
        rows.append({
            "symbol":        sym,
            "expiry":        expiry_iso,
            "strike":        float(strike),
            "bid":           bid_f,
            "ask":           ask_f,
            "mid":           round(mid, 4) if mid is not None else None,
            "spread_pct":    round(spread_pct, 6) if spread_pct is not None else None,
            "delta":         round(delta, 4) if delta is not None else None,
            "gamma":         None,
            "theta":         None,
            "vega":          None,
            "open_interest": qd.get("openInterest"),
            "volume":        qd.get("totalVolume"),
            "dte":           actual_dte,
            "iv":            None,
            "last":          qd.get("lastPrice"),
        })

    _cache_put(cache_key, rows)
    return rows


def get_option_chain(
    symbol: str,
    option_type: str,
    target_dte: int,
    dte_range: int = 7,
    center_strike: float | None = None,
    strike_window: int = 10,
    spot: float | None = None,
    sigma: float | None = None,
) -> list[dict]:
    # Futures symbols (/ES, /NQ, ...) need a separate API path — equity chains endpoint rejects them.
    if _is_futures_symbol(symbol):
        return get_futures_option_chain(
            symbol, option_type, target_dte, dte_range=max(int(dte_range), 14),
            center_strike=center_strike, strike_window=int(strike_window),
            spot=spot, sigma=sigma,
        )
    if not is_configured():
        return []
    cache_key = _chain_cache_key(
        symbol,
        option_type.upper(),
        int(target_dte),
        int(dte_range),
        center_strike=center_strike,
        strike_window=int(strike_window),
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    target_date = date.today() + timedelta(days=int(target_dte))
    from_date = (target_date - timedelta(days=int(dte_range))).isoformat()
    to_date = (target_date + timedelta(days=int(dte_range))).isoformat()

    requested_strike_count = 20 if center_strike is None else max(300, int(strike_window) * 20)
    res = requests.get(
        f"{BASE_URL}/marketdata/v1/chains",
        params={
            "symbol": _marketdata_symbol(symbol),
            "contractType": option_type.upper(),
            "strikeCount": requested_strike_count,
            "includeQuotes": "TRUE",
            "fromDate": from_date,
            "toDate": to_date,
        },
        headers=_headers(),
        timeout=20,
    )
    res.raise_for_status()
    rows = _parse_chain_response(res.json(), option_type)
    if not rows:
        _cache_put(cache_key, [])
        return []

    expiry_totals: dict[str, float] = {}
    for row in rows:
        expiry = str(row.get("expiry") or "")
        expiry_totals.setdefault(expiry, 0.0)
        try:
            expiry_totals[expiry] += float(row.get("open_interest") or 0)
        except (TypeError, ValueError):
            continue

    best_expiry = max(expiry_totals.items(), key=lambda item: item[1])[0]
    filtered = [row for row in rows if row.get("expiry") == best_expiry]
    if filtered:
        deduped_by_strike: dict[float, dict] = {}
        for row in filtered:
            try:
                strike_key = float(row.get("strike"))
            except (TypeError, ValueError):
                continue
            current = deduped_by_strike.get(strike_key)
            if current is None:
                deduped_by_strike[strike_key] = row
                continue
            current_oi = float(current.get("open_interest") or 0)
            row_oi = float(row.get("open_interest") or 0)
            current_spread = float(current.get("spread_pct") or 99)
            row_spread = float(row.get("spread_pct") or 99)
            current_bid = float(current.get("bid") or 0)
            row_bid = float(row.get("bid") or 0)
            if (row_oi, -row_spread, row_bid) > (current_oi, -current_spread, current_bid):
                deduped_by_strike[strike_key] = row
        filtered = list(deduped_by_strike.values())
    if center_strike is not None and filtered:
        filtered = sorted(
            filtered,
            key=lambda row: abs(float(row.get("strike") or 0) - float(center_strike)),
        )[: max(int(strike_window), 1)]
        filtered = sorted(filtered, key=lambda row: float(row.get("strike") or 0))
    _cache_put(cache_key, filtered)
    return filtered


def _find_matching_position(positions: list[dict], state: dict | None) -> dict | None:
    if not positions:
        return None
    if not state:
        return positions[0]
    expiry = str(state.get("expiry") or "")
    expiry_digits = expiry.replace("-", "")
    expiry_token = expiry_digits[-6:] if len(expiry_digits) >= 6 else expiry_digits
    short_strike = str(int(float(state["short_strike"]))) if state.get("short_strike") is not None else ""
    for pos in positions:
        symbol = str(pos.get("symbol") or "")
        if expiry_token and expiry_token in symbol and short_strike and short_strike in symbol:
            return pos
    # Fail closed when the live account positions do not match the recorded trade
    # state. Falling back to an unrelated position can corrupt the dashboard risk
    # panel with bogus mark/PnL data.
    return None


def _get_option_chain_exact_expiry(
    symbol: str,
    option_type: str,
    expiry: str,
    center_strike: float | None = None,
    strike_window: int = 40,
) -> list[dict]:
    if not is_configured():
        return []
    expiry_date = str(expiry or "")
    cache_key = f"chain-exact:{symbol}:{option_type.upper()}:{expiry_date}:{int(round(float(center_strike or 0)))}:{int(strike_window)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    requested_strike_count = 20 if center_strike is None else max(300, int(strike_window) * 20)
    res = requests.get(
        f"{BASE_URL}/marketdata/v1/chains",
        params={
            "symbol": _marketdata_symbol(symbol),
            "contractType": option_type.upper(),
            "strikeCount": requested_strike_count,
            "includeQuotes": "TRUE",
            "fromDate": expiry_date,
            "toDate": expiry_date,
        },
        headers=_headers(),
        timeout=20,
    )
    res.raise_for_status()
    rows = _parse_chain_response(res.json(), option_type)
    filtered = [row for row in rows if str(row.get("expiry") or "") == expiry_date]
    if center_strike is not None and filtered:
        filtered = sorted(
            filtered,
            key=lambda row: abs(float(row.get("strike") or 0) - float(center_strike)),
        )[: max(int(strike_window), 1)]
    _cache_put(cache_key, filtered)
    return filtered


def _find_chain_row(rows: list[dict], strike: float | int | str | None) -> dict | None:
    try:
        strike_f = float(strike)
    except (TypeError, ValueError):
        return None
    for row in rows:
        try:
            if float(row.get("strike")) == strike_f:
                return row
        except (TypeError, ValueError):
            continue
    return None


def _strategy_quote_layout(state: dict | None) -> list[dict] | None:
    if not state:
        return None
    strategy_key = str(state.get("strategy_key") or "")
    if strategy_key in {"bull_put_spread", "bull_put_spread_hv"}:
        return [
            {"name": "short_put", "option_type": "PUT", "strike": state.get("short_strike"), "multiplier": -1.0},
            {"name": "long_put", "option_type": "PUT", "strike": state.get("long_strike"), "multiplier": 1.0},
        ]
    if strategy_key in {"bear_call_spread_hv"}:
        return [
            {"name": "short_call", "option_type": "CALL", "strike": state.get("short_strike"), "multiplier": -1.0},
            {"name": "long_call", "option_type": "CALL", "strike": state.get("long_strike"), "multiplier": 1.0},
        ]
    if strategy_key in {"iron_condor", "iron_condor_hv"}:
        return [
            {"name": "short_put", "option_type": "PUT", "strike": state.get("short_put_strike") or state.get("short_strike"), "multiplier": -1.0},
            {"name": "long_put", "option_type": "PUT", "strike": state.get("long_put_strike") or state.get("long_strike"), "multiplier": 1.0},
            {"name": "short_call", "option_type": "CALL", "strike": state.get("short_call_strike"), "multiplier": -1.0},
            {"name": "long_call", "option_type": "CALL", "strike": state.get("long_call_strike"), "multiplier": 1.0},
        ]
    return None


def _spread_live_snapshot_from_chain(state: dict | None, positions_payload: dict) -> dict | None:
    leg_specs = _strategy_quote_layout(state)
    if not state or not leg_specs:
        return None
    expiry = str(state.get("expiry") or "")
    underlying = str(state.get("underlying") or "SPX")
    if not expiry:
        return None

    def _f(row: dict, key: str) -> float | None:
        try:
            value = row.get(key)
            return None if value in (None, "") else float(value)
        except (TypeError, ValueError):
            return None

    for spec in leg_specs:
        option_type = str(spec.get("option_type") or "").upper()
        strike = spec.get("strike")
        if option_type not in {"PUT", "CALL"} or strike is None:
            return None

    # Fetch chain per-leg with each leg's own strike as center so dense SPX
    # strike lists don't push the far leg out of the strike_window cutoff.
    leg_rows: list[dict] = []
    for spec in leg_specs:
        option_type = str(spec["option_type"]).upper()
        leg_chain = _get_option_chain_exact_expiry(
            underlying, option_type, expiry,
            center_strike=spec["strike"], strike_window=20,
        )
        row = _find_chain_row(leg_chain, spec["strike"])
        if not row:
            return None
        leg_rows.append({"spec": spec, "row": row})

    def _net_price(key_for_short: str, key_for_long: str) -> float | None:
        total = 0.0
        for item in leg_rows:
            spec = item["spec"]
            row = item["row"]
            multiplier = float(spec["multiplier"])
            if multiplier < 0:
                val = _f(row, key_for_short)
                signed = 1.0
            else:
                val = _f(row, key_for_long)
                signed = -1.0
            if val is None:
                return None
            total += signed * val
        return round(total, 4)

    spread_mark = 0.0
    for item in leg_rows:
        mid = _f(item["row"], "mid")
        if mid is None:
            return None
        spread_mark += (1.0 if float(item["spec"]["multiplier"]) < 0 else -1.0) * mid
    spread_mark = round(spread_mark, 4)
    spread_bid = _net_price("bid", "ask")
    spread_ask = _net_price("ask", "bid")

    def _net_greek(key: str) -> float | None:
        total = 0.0
        seen = False
        for item in leg_rows:
            val = _f(item["row"], key)
            if val is None:
                continue
            total += float(item["spec"]["multiplier"]) * val
            seen = True
        return round(total, 6) if seen else None

    try:
        contracts = float(state.get("contracts", 1))
        entry_credit = float(state.get("actual_premium"))
    except (TypeError, ValueError):
        contracts = None
        entry_credit = None

    trade_log_pnl = None
    if contracts is not None and entry_credit is not None:
        trade_log_pnl = round((entry_credit - spread_mark) * contracts * 100, 2)

    structure = "4-leg condor" if len(leg_rows) == 4 else "2-leg spread"
    leg_payload = {str(item["spec"]["name"]): item["row"] for item in leg_rows}

    # Freshness: take the *oldest* leg quote_time_in_long (worst-of, matches
    # the ETrade convention) so PM sees the weaker side, not the optimistic
    # one. Field is normalized from Schwab's quoteTimeInLong (ms unix) at
    # chain-row build time (see _get_option_chain_exact_expiry rows.append).
    leg_quote_times = []
    for item in leg_rows:
        raw = item["row"].get("quote_time_in_long") or item["row"].get("quoteTimeInLong")
        try:
            if raw not in (None, ""):
                leg_quote_times.append(int(raw))
        except (TypeError, ValueError):
            pass
    quote_time = None
    if leg_quote_times:
        worst_ms = min(leg_quote_times)
        try:
            quote_time = datetime.fromtimestamp(
                worst_ms / 1000.0, tz=ZoneInfo("UTC"),
            ).astimezone(_ET).isoformat(timespec="seconds")
        except (TypeError, ValueError, OSError):
            quote_time = None

    return {
        "visible": True,
        "stale": positions_payload.get("stale", False),
        "mark": spread_mark,
        "bid": spread_bid,
        "ask": spread_ask,
        "delta": _net_greek("delta"),
        "gamma": _net_greek("gamma"),
        "theta": _net_greek("theta"),
        "vega": _net_greek("vega"),
        "unrealized_pnl": trade_log_pnl,
        "trade_log_pnl": trade_log_pnl,
        "symbol": f"{underlying} {expiry} {structure}",
        "pricing_source": "spread_quote",
        "structure": structure,
        "legs": leg_payload,
        # Freshness (Schwab convention — boolean realtime + ISO quote_time)
        "realtime":   None,   # chain-level flag not preserved by chain helper yet
        "quote_time": quote_time,
    }


def _spread_mark_from_positions(state: dict, positions: list[dict], positions_payload: dict) -> dict | None:
    """
    Fallback: compute spread mark from per-leg market values when the chain
    API has no mid (SPX often returns null bid/ask from the positions endpoint).
    Returns a visible=True snapshot with mark + trade_log_pnl but no Greeks.
    """
    leg_specs = _strategy_quote_layout(state)
    if not leg_specs:
        return None
    expiry = str(state.get("expiry") or "")
    expiry_token = expiry.replace("-", "")[-6:]
    if not expiry_token:
        return None
    net_mv = 0.0
    for spec in leg_specs:
        strike = spec.get("strike")
        if strike is None:
            return None
        strike_str = str(int(float(strike)))
        leg_pos = next(
            (p for p in positions
             if expiry_token in str(p.get("symbol") or "")
             and strike_str in str(p.get("symbol") or "")),
            None,
        )
        if leg_pos is None or leg_pos.get("mark") is None:
            return None
        net_mv += float(leg_pos["mark"])
    try:
        contracts = float(state.get("contracts", 1))
        # Credit spread: net_mv < 0 (short leg dominates); spread_mark = cost to close per contract
        spread_mark = round(-net_mv / (contracts * 100), 4)
        entry_credit = float(state.get("actual_premium") or 0)
        trade_log_pnl = round((entry_credit - spread_mark) * contracts * 100, 2)
    except Exception:
        return None
    return {
        "visible": True,
        "pricing_source": "positions_mark",
        "stale": positions_payload.get("stale", False),
        "mark": spread_mark,
        "bid": None,
        "ask": None,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "unrealized_pnl": None,
        "trade_log_pnl": trade_log_pnl,
    }


def spread_quote_for_strikes(
    underlying: str,
    expiry: str,
    short_strike: float,
    long_strike: float,
) -> dict:
    """Mark/bid/ask for a specific put spread via Schwab chain (no Greeks, lightweight)."""
    cache_key = f"swquote:{underlying}:{expiry}:{short_strike}:{long_strike}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    mock_state = {
        "strategy_key": "bull_put_spread",
        "underlying": underlying,
        "expiry": expiry,
        "short_strike": short_strike,
        "long_strike": long_strike,
    }
    result = _spread_live_snapshot_from_chain(mock_state, {})
    if result:
        out = {k: result[k] for k in ("visible", "mark", "bid", "ask", "quote_time", "realtime")
               if k in result}
        out.setdefault("visible", True)
        _cache_put(cache_key, out)
        return out
    return {"visible": False}


def live_position_snapshot(state: dict | None) -> dict:
    positions_payload = get_account_positions()
    if not positions_payload.get("configured") or not positions_payload.get("authenticated"):
        return {"visible": False, **positions_payload}
    # Tier 1: full chain snapshot (Greeks + bid/ask)
    chain_snapshot = _spread_live_snapshot_from_chain(state, positions_payload)
    if chain_snapshot is not None:
        return chain_snapshot
    positions = positions_payload.get("positions", [])
    # Tier 2: positions mark fallback (spread mark + trade-log P&L, no Greeks)
    if state:
        fallback = _spread_mark_from_positions(state, positions, positions_payload)
        if fallback is not None:
            return fallback
    # Tier 3: single-leg position match
    pos = _find_matching_position(positions, state)
    if not pos:
        return {"visible": False, **positions_payload}
    has_quote_fields = any(
        pos.get(field) is not None
        for field in ("bid", "ask", "delta", "gamma", "theta", "vega")
    )
    if state and not has_quote_fields:
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
        # Positions endpoint doesn't expose per-quote freshness; mark "unknown"
        # so the chip falls through to grey rather than green/yellow.
        "realtime":   None,
        "quote_time": None,
    }
