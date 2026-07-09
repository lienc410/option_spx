"""Q041 daily forward-collection of full option chains for the whitelist.

Runs once per trading day (target 16:30 ET via launchd). For each whitelist symbol:

  1. Fetch full multi-expiry option chain (calls + puts) from Schwab.
  2. Fetch underlying EOD quote.
  3. Persist to data/q041_chains/YYYY-MM-DD/{SYMBOL}.parquet
  4. Persist underlying EOD to data/q041_chains/YYYY-MM-DD/_underlying.parquet

Boundaries:
- Reuses schwab.auth (OAuth token at ~/.spxstrat/schwab_token.json) read-only.
- Bypasses schwab.client.get_option_chain() because that helper filters to a
  single best-OI expiry and caches; Q041 needs full chains and no cache.
- Writes only under data/q041_chains/. No mutation of engine.py / strategy /
  signals / web / notify / schwab/.
- Idempotent: re-running on same date overwrites that day's parquet.
- Trading-day gate: skips weekends. Holiday calendar is intentionally not
  enforced here — empty chains on a holiday are handled gracefully and
  produce a zero-row file flagged with `is_market_open = False` in the log.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.q041.whitelist import WHITELIST  # noqa: E402
from schwab.auth import ensure_access_token, is_configured  # noqa: E402
from schwab.client import (  # noqa: E402
    BASE_URL,
    _marketdata_symbol,
    _normalize_quote,
    _parse_chain_response,
)

ET = ZoneInfo("America/New_York")
DATA_ROOT = REPO_ROOT / "data" / "q041_chains"
LOG_DIR = REPO_ROOT / "logs"

# Forward-collection window: capture every expiry from now out to ~13 months.
# Covers monthlies, weeklies, and LEAPS commonly used in CC / CSP overlays.
DTE_WINDOW_DAYS = 400
HTTP_TIMEOUT = 90
REQUEST_PAUSE_SEC = 0.4  # gentle pacing between symbols

# SPEC-114 Part B: retry guard for index symbols (SPX/QQQ high-priority signals)
INDEX_SYMBOLS: frozenset[str] = frozenset({"SPX", "QQQ"})
INDEX_RETRY_MAX = 3
INDEX_RETRY_BACKOFF_SEC = 30
COLLECTOR_ALERT_PATH = REPO_ROOT / "data" / "q041_collector_alert.jsonl"

# Schwab API gateway has a response-body size limit ("TooBigBody").
# $SPX has 5-pt increments and many weeklies. 160 strikes × 180-day window
# covers ±400 pts at $5 increments — at SPX 7400 that is ±5.4% — fully
# enclosing the +5% OTM short leg used by Q042 call spreads.
# (Prior value was 100 = ±250 pts ≈ +3.4% at current SPX levels.)
_STRIKE_COUNT: dict[str, int] = {
    "$SPX": 160,
}
_DTE_WINDOW: dict[str, int] = {
    "$SPX": 180,
}
_CHAIN_FALLBACK_PROFILES: dict[str, list[tuple[int, int]]] = {
    "$SPX": [(120, 180), (100, 180), (80, 120)],
    "QQQ": [(300, 400), (240, 300), (180, 240)],
    "_default": [(300, 300), (200, 240), (120, 180)],
}
_RETRYABLE_CHAIN_STATUS = {429, 502, 503, 504}


def _logger(verbose: bool) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("q041_collect")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(LOG_DIR / "q041_collect.log")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log


@dataclass
class CollectResult:
    symbol: str
    rows_calls: int
    rows_puts: int
    underlying_last: float | None
    error: str | None = None


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ensure_access_token()}"}


def _chain_request_profiles(api_sym: str) -> list[tuple[int, int]]:
    base = (
        _STRIKE_COUNT.get(api_sym, 500),
        _DTE_WINDOW.get(api_sym, DTE_WINDOW_DAYS),
    )
    fallbacks = _CHAIN_FALLBACK_PROFILES.get(
        api_sym,
        _CHAIN_FALLBACK_PROFILES["_default"],
    )
    profiles: list[tuple[int, int]] = []
    for profile in [base, *fallbacks]:
        if profile not in profiles:
            profiles.append(profile)
    return profiles


def _fetch_full_chain(symbol: str) -> tuple[list[dict], list[dict]]:
    """Pull full multi-expiry chain — both call and put exp maps in one call."""
    today = date.today()
    api_sym = _marketdata_symbol(symbol)
    last_error: Exception | None = None
    log = logging.getLogger("q041_collect")
    for idx, (strike_count, dte_window) in enumerate(_chain_request_profiles(api_sym)):
        params = {
            "symbol": api_sym,
            "contractType": "ALL",
            "strikeCount": strike_count,
            "includeQuotes": "TRUE",
            "fromDate": today.isoformat(),
            "toDate": (today + timedelta(days=dte_window)).isoformat(),
        }
        try:
            res = requests.get(
                f"{BASE_URL}/marketdata/v1/chains",
                params=params,
                headers=_headers(),
                timeout=HTTP_TIMEOUT,
            )
            res.raise_for_status()
            break
        except requests.HTTPError as exc:
            last_error = exc
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code not in _RETRYABLE_CHAIN_STATUS or idx == len(_chain_request_profiles(api_sym)) - 1:
                raise
            log.warning(
                "chain fetch retry symbol=%s status=%s strikeCount=%s dteWindow=%s",
                symbol,
                status_code,
                strike_count,
                dte_window,
            )
            time.sleep(1.0 + idx)
    else:
        raise last_error or RuntimeError(f"chain fetch failed for {symbol}")
    payload = res.json()
    calls = _parse_chain_response(payload, "CALL")
    puts = _parse_chain_response(payload, "PUT")

    return calls, puts


def _fetch_underlying(symbol: str) -> dict | None:
    sym = _marketdata_symbol(symbol)
    res = requests.get(
        f"{BASE_URL}/marketdata/v1/quotes",
        params={"symbols": sym, "fields": "quote"},
        headers=_headers(),
        timeout=HTTP_TIMEOUT,
    )
    res.raise_for_status()
    data = res.json()
    raw = data.get(sym)
    if not isinstance(raw, dict):
        return None
    return _normalize_quote(sym, raw)


def _is_trading_day(now_et: datetime) -> bool:
    return now_et.weekday() < 5


def _build_chain_frame(
    symbol: str,
    calls: list[dict],
    puts: list[dict],
    snapshot_date: str,
    snapshot_ts: str,
) -> pd.DataFrame:
    rows = []
    for r in calls:
        rows.append({**r, "option_type": "CALL"})
    for r in puts:
        rows.append({**r, "option_type": "PUT"})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["symbol"] = symbol
    df["snapshot_date"] = snapshot_date
    df["snapshot_ts_et"] = snapshot_ts
    cols_order = [
        "snapshot_date",
        "snapshot_ts_et",
        "symbol",
        "option_type",
        "expiry",
        "dte",
        "strike",
        "bid",
        "ask",
        "mid",
        "spread_pct",
        "delta",
        "open_interest",
        "volume",
        "iv",
        "gamma",
        "theta",
        "vega",
        "rho",
        "expiry_type",
        "open",
        "high",
        "low",
        "close",
        "last",
    ]
    df = df.reindex(columns=cols_order)
    for col in ("strike", "bid", "ask", "mid", "spread_pct", "delta"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("iv", "gamma", "theta", "vega", "rho", "open", "high", "low", "close", "last"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Schwab uses -999.0 as a sentinel for "IV unavailable"; coerce to NaN
    df["iv"] = df["iv"].where(df["iv"] > 0, other=pd.NA)
    for col in ("open_interest", "volume", "dte"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _safe_filename(symbol: str) -> str:
    # Leading slash → futures prefix (e.g. "/ES" → "ES").
    # Mid-slash → underscore (e.g. "BRK/B" → "BRK_B").
    s = symbol.lstrip("/")
    return s.replace("/", "_")


def _write_collector_alert(symbol: str, reason: str, snapshot_date: str) -> None:
    from zoneinfo import ZoneInfo as _ZI
    record = {
        "date": snapshot_date,
        "symbol": symbol,
        "reason": reason,
        "ts": datetime.now(_ZI("America/New_York")).strftime("%H:%M:%S%z"),
    }
    COLLECTOR_ALERT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with COLLECTOR_ALERT_PATH.open("a", encoding="utf-8") as f:
        import json as _json
        f.write(_json.dumps(record) + "\n")


def _send_collector_alert_telegram(symbol: str, log: logging.Logger) -> None:
    """Push an alert when an index symbol's chain fails all retries.

    SPEC-137: routes through the unified gateway (category/about/dedupe + host
    guard in the transport). Was a legacy direct Telegram sender. A collector
    failure means today's Q041 signal is missing → 🔴 ALERT."""
    from notify.gateway import escape, push as gw_push
    body = (
        f"{symbol} 期权链在 16:30 ET 连续抓取 {INDEX_RETRY_MAX} 次都失败。\n"
        f"今天的 Q041 {symbol} 信号会缺席（无数据可算）。"
    )
    try:
        gw_push("ALERT", "系统状态", "Q041 数据采集失败", escape(body),
                dedupe_key=f"q041_collector_fail_{symbol}")
    except Exception:
        log.exception("collector alert push failed")


def _fetch_chain_with_retry(symbol: str, log: logging.Logger) -> tuple[list, list] | None:
    """SPEC-114: retry wrapper for INDEX_SYMBOLS (SPX, QQQ); single attempt for others.

    Returns (calls, puts) on success, None on final failure.
    """
    attempts = INDEX_RETRY_MAX if symbol in INDEX_SYMBOLS else 1
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            calls, puts = _fetch_full_chain(symbol)
            if calls or puts:
                if i > 0:
                    log.info("%s: chain succeeded on attempt %d/%d", symbol, i + 1, attempts)
                return calls, puts
            log.warning("%s: empty chain on attempt %d/%d", symbol, i + 1, attempts)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("%s fetch attempt %d/%d failed: %s", symbol, i + 1, attempts, exc)
        if i < attempts - 1:
            log.info("%s: retrying in %ds...", symbol, INDEX_RETRY_BACKOFF_SEC)
            time.sleep(INDEX_RETRY_BACKOFF_SEC)
    return None


def collect_one(symbol: str, snapshot_date: str, snapshot_ts: str, log: logging.Logger) -> CollectResult:
    chain_result = _fetch_chain_with_retry(symbol, log)
    if chain_result is None:
        if symbol in INDEX_SYMBOLS:
            reason = f"empty_chain_after_{INDEX_RETRY_MAX}_retries"
            log.error("%s: chain failed all %d retries — writing alert", symbol, INDEX_RETRY_MAX)
            _write_collector_alert(symbol, reason, snapshot_date)
            _send_collector_alert_telegram(symbol, log)
        return CollectResult(symbol, 0, 0, None, error="chain:all_retries_failed")
    try:
        calls, puts = chain_result
    except Exception as exc:  # noqa: BLE001
        log.exception("chain fetch failed for %s", symbol)
        return CollectResult(symbol, 0, 0, None, error=f"chain:{exc}")

    underlying = None
    underlying_last = None
    try:
        underlying = _fetch_underlying(symbol)
        if underlying:
            underlying_last = underlying.get("last")
    except Exception as exc:  # noqa: BLE001
        log.warning("underlying quote failed for %s: %s", symbol, exc)

    df = _build_chain_frame(symbol, calls, puts, snapshot_date, snapshot_ts)
    out_dir = DATA_ROOT / snapshot_date
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = _safe_filename(symbol) + ".parquet"
    df.to_parquet(out_dir / fname, index=False)

    return CollectResult(
        symbol=symbol,
        rows_calls=len(calls),
        rows_puts=len(puts),
        underlying_last=underlying_last,
    )


def write_underlying_frame(
    snapshot_date: str,
    snapshot_ts: str,
    results: list[CollectResult],
    underlying_records: list[dict],
) -> None:
    if not underlying_records:
        return
    df = pd.DataFrame(underlying_records)
    df["snapshot_date"] = snapshot_date
    df["snapshot_ts_et"] = snapshot_ts
    out = DATA_ROOT / snapshot_date / "_underlying.parquet"
    df.to_parquet(out, index=False)


def run(symbols: list[str], force: bool, log: logging.Logger) -> int:
    if not is_configured():
        log.error("schwab auth not configured — aborting")
        return 2

    now_et = datetime.now(ET)
    snapshot_date = now_et.date().isoformat()
    snapshot_ts = now_et.isoformat(timespec="seconds")

    if not _is_trading_day(now_et) and not force:
        log.info("non-trading day (%s) — skipping. Use --force to override.", now_et.strftime("%a"))
        return 0

    log.info("Q041 collect start | %s | %d symbols", snapshot_ts, len(symbols))

    results: list[CollectResult] = []
    underlying_records: list[dict] = []
    for sym in symbols:
        try:
            u = _fetch_underlying(sym)
        except Exception as exc:  # noqa: BLE001
            log.warning("underlying pre-fetch failed %s: %s", sym, exc)
            u = None
        if u:
            underlying_records.append(u)

        res = collect_one(sym, snapshot_date, snapshot_ts, log)
        results.append(res)
        log.info(
            "  %-6s calls=%d puts=%d underlying=%s%s",
            sym,
            res.rows_calls,
            res.rows_puts,
            res.underlying_last,
            f" ERROR={res.error}" if res.error else "",
        )
        time.sleep(REQUEST_PAUSE_SEC)

    write_underlying_frame(snapshot_date, snapshot_ts, results, underlying_records)

    summary = {
        "snapshot_date": snapshot_date,
        "snapshot_ts_et": snapshot_ts,
        "symbols": [r.symbol for r in results],
        "ok": [r.symbol for r in results if r.error is None],
        "errors": {r.symbol: r.error for r in results if r.error},
        "totals": {
            "rows_calls": sum(r.rows_calls for r in results),
            "rows_puts": sum(r.rows_puts for r in results),
        },
    }
    summary_path = DATA_ROOT / snapshot_date / "_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))

    log.info(
        "Q041 collect done | ok=%d errors=%d total_rows=%d",
        len(summary["ok"]),
        len(summary["errors"]),
        summary["totals"]["rows_calls"] + summary["totals"]["rows_puts"],
    )
    return 0 if not summary["errors"] else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Q041 daily option-chain forward-collection")
    p.add_argument("--symbols", nargs="*", help="override whitelist (space-separated tickers)")
    p.add_argument("--force", action="store_true", help="run even on weekends/holidays")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    log = _logger(args.verbose)
    symbols = list(args.symbols) if args.symbols else list(WHITELIST)
    return run(symbols, force=args.force, log=log)


if __name__ == "__main__":
    sys.exit(main())
