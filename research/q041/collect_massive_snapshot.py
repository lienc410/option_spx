"""Q041 daily Massive option-chain snapshot collector.

Collects delayed option-chain snapshots from Massive REST and writes per-symbol
parquet partitions under ``data/q041_massive_snapshot/YYYY-MM-DD/``.

Captured fields focus on Q041 Gate 0 / alignment needs:
- Greeks (delta/gamma/theta/vega)
- implied volatility
- open interest
- latest daily/session snapshot fields when available

This script does not mutate production strategy/runtime code.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.q041.whitelist import WHITELIST  # noqa: E402

ET = ZoneInfo("America/New_York")
BASE_URL = "https://api.massive.com"
DATA_ROOT = REPO_ROOT / "data" / "q041_massive_snapshot"
LOG_DIR = REPO_ROOT / "logs"
HTTP_TIMEOUT = 30
REQUEST_PAUSE_SEC = 0.35
PAGE_LIMIT = 250
INTEGRITY_AUDIT_PATH = REPO_ROOT / "data" / "q041_massive_snapshot_integrity.jsonl"
INTEGRITY_ALERT_STATE_PATH = REPO_ROOT / "data" / "q041_massive_snapshot_integrity_alerts.jsonl"
INTEGRITY_LOOKBACK_DAYS = 5

_US_HOLIDAYS_2025 = {
    "2025-01-01",
    "2025-01-20",
    "2025-02-17",
    "2025-04-18",
    "2025-05-26",
    "2025-07-04",
    "2025-09-01",
    "2025-11-27",
    "2025-12-25",
}
_US_HOLIDAYS_2026 = {
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",
    "2026-05-25",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
}
_ALL_HOLIDAYS = _US_HOLIDAYS_2025 | _US_HOLIDAYS_2026

load_dotenv(REPO_ROOT / ".env")


def _logger(verbose: bool) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("q041_massive_snapshot")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(LOG_DIR / "q041_massive_snapshot.log")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log


def safe_filename(symbol: str) -> str:
    return symbol.lstrip("/").replace("/", "_")


def massive_underlying_symbol(symbol: str) -> str:
    if symbol == "BRK/B":
        return "BRK.B"
    return symbol


def _target_symbols(symbols_override: list[str] | None) -> list[str]:
    symbols = list(symbols_override) if symbols_override else list(WHITELIST)
    return list(dict.fromkeys(symbols))


def _ensure_api_key() -> str:
    api_key = os.environ.get("MASSIVE_API_KEY")
    if not api_key:
        raise RuntimeError("MASSIVE_API_KEY not configured")
    return api_key


def _trading_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in _ALL_HOLIDAYS


def _recent_trading_days(day: date, n: int) -> list[date]:
    out: list[date] = []
    cursor = day
    while len(out) < n:
        if _trading_day(cursor):
            out.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(out)


def _with_api_key(next_url: str, api_key: str) -> str:
    parts = urlparse(next_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("apiKey", api_key)
    return urlunparse(parts._replace(query=urlencode(query)))


def _get_json(session: requests.Session, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    res = session.get(url, params=params, timeout=HTTP_TIMEOUT)
    res.raise_for_status()
    body = res.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"unexpected Massive response type: {type(body)!r}")
    return body


def _ns_to_et_str(value: Any) -> str | None:
    if value in (None, "", 0):
        return None
    try:
        ts = pd.to_datetime(int(value), unit="ns", utc=True)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts.tz_convert(ET).isoformat()


def _normalize_result(symbol: str, snapshot_date: str, result: dict[str, Any]) -> dict[str, Any]:
    details = result.get("details") or {}
    greeks = result.get("greeks") or {}
    day = result.get("day") or {}
    last_trade = result.get("last_trade") or {}
    last_quote = result.get("last_quote") or {}
    underlying_asset = result.get("underlying_asset") or {}

    return {
        "snapshot_date": snapshot_date,
        "symbol": symbol,
        "api_symbol": massive_underlying_symbol(symbol),
        "occ_ticker": details.get("ticker"),
        "underlying_ticker": underlying_asset.get("ticker"),
        "contract_type": details.get("contract_type"),
        "exercise_style": details.get("exercise_style"),
        "expiration_date": details.get("expiration_date"),
        "strike_price": details.get("strike_price"),
        "shares_per_contract": details.get("shares_per_contract"),
        "break_even_price": result.get("break_even_price"),
        "implied_volatility": result.get("implied_volatility"),
        "open_interest": result.get("open_interest"),
        "delta": greeks.get("delta"),
        "gamma": greeks.get("gamma"),
        "theta": greeks.get("theta"),
        "vega": greeks.get("vega"),
        "rho": greeks.get("rho"),
        "day_open": day.get("open"),
        "day_high": day.get("high"),
        "day_low": day.get("low"),
        "day_close": day.get("close"),
        "day_volume": day.get("volume"),
        "day_vwap": day.get("vwap"),
        "day_change": day.get("change"),
        "day_change_percent": day.get("change_percent"),
        "day_previous_close": day.get("previous_close"),
        "day_last_updated_et": _ns_to_et_str(day.get("last_updated")),
        "last_trade_price": last_trade.get("price"),
        "last_trade_size": last_trade.get("size"),
        "last_trade_exchange": last_trade.get("exchange"),
        "last_trade_timeframe": last_trade.get("timeframe"),
        "last_trade_ts_et": _ns_to_et_str(last_trade.get("sip_timestamp")),
        "last_quote_bid": last_quote.get("bid"),
        "last_quote_ask": last_quote.get("ask"),
        "last_quote_bid_size": last_quote.get("bid_size"),
        "last_quote_ask_size": last_quote.get("ask_size"),
        "last_quote_timeframe": last_quote.get("timeframe"),
        "last_quote_ts_et": _ns_to_et_str(last_quote.get("last_updated")),
        "underlying_price": underlying_asset.get("price"),
        "underlying_change_to_break_even": underlying_asset.get("change_to_break_even"),
        "underlying_last_updated_et": _ns_to_et_str(underlying_asset.get("last_updated")),
    }


def _normalize_frame(symbol: str, snapshot_date: str, results: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [_normalize_result(symbol, snapshot_date, r) for r in results]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    numeric_cols = [
        "strike_price",
        "shares_per_contract",
        "break_even_price",
        "implied_volatility",
        "open_interest",
        "delta",
        "gamma",
        "theta",
        "vega",
        "rho",
        "day_open",
        "day_high",
        "day_low",
        "day_close",
        "day_volume",
        "day_vwap",
        "day_change",
        "day_change_percent",
        "day_previous_close",
        "last_trade_price",
        "last_trade_size",
        "last_trade_exchange",
        "last_quote_bid",
        "last_quote_ask",
        "last_quote_bid_size",
        "last_quote_ask_size",
        "underlying_price",
        "underlying_change_to_break_even",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["expiration_date", "contract_type", "strike_price", "occ_ticker"]).reset_index(drop=True)


def _day_partition_ok(day: date) -> bool:
    day_dir = DATA_ROOT / day.isoformat()
    return (
        day_dir.exists()
        and (day_dir / "_summary.json").exists()
        and (day_dir / "SPX.parquet").exists()
    )


def _integrity_record(day: date) -> dict[str, Any]:
    recent_days = _recent_trading_days(day, INTEGRITY_LOOKBACK_DAYS)
    missing = [d.isoformat() for d in recent_days if not _day_partition_ok(d)]
    return {
        "date": day.isoformat(),
        "status": "warning" if missing else "ok",
        "lookback_days": INTEGRITY_LOOKBACK_DAYS,
        "checked_days": [d.isoformat() for d in recent_days],
        "missing_days": missing,
    }


def _append_integrity_record(record: dict[str, Any]) -> None:
    INTEGRITY_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INTEGRITY_AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_integrity_alerted_days() -> set[str]:
    """Return the set of ALL missing-day strings that have ever been alerted, across all runs."""
    if not INTEGRITY_ALERT_STATE_PATH.exists():
        return set()
    out: set[str] = set()
    with INTEGRITY_ALERT_STATE_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.update(str(v) for v in (payload.get("missing_days") or []) if str(v))
    return out


def _append_integrity_alert_state(day: str, missing_days: list[str]) -> None:
    INTEGRITY_ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INTEGRITY_ALERT_STATE_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"date": day, "missing_days": missing_days}, ensure_ascii=False) + "\n")


def _send_telegram_message(text: str, log: logging.Logger) -> bool:
    """SPEC-137: route through the unified gateway (category/about/dedupe +
    host guard in the transport). Was a legacy direct Telegram sender with no
    host guard at all. A missing-partition integrity gap is a 🟡 ACTION."""
    try:
        from notify.gateway import escape, push as gw_push
        return gw_push("ACTION", "系统状态", "", escape(text))
    except Exception:
        log.exception("telegram send failed")
        return False


def _build_integrity_alert_text(record: dict[str, Any]) -> str | None:
    missing = [str(v) for v in (record.get("missing_days") or []) if str(v)]
    if not missing:
        return None
    prior = _load_integrity_alerted_days()   # global set — never re-alert same missing day
    fresh = [d for d in missing if d not in prior]
    if not fresh:
        return None
    _append_integrity_alert_state(str(record.get("date") or ""), fresh)
    lines = [
        f"⚠️ Q041 Massive snapshot integrity warning {record['date']}",
        f"Recent trading-day partitions missing under data/q041_massive_snapshot/",
    ]
    lines.extend(f"- {day}" for day in fresh)
    return "\n".join(lines)


@dataclass
class CollectResult:
    symbol: str
    rows: int
    pages: int | None
    reused: bool = False
    error: str | None = None


def _fetch_symbol_snapshot(
    session: requests.Session,
    symbol: str,
    snapshot_date: str,
    force: bool,
    log: logging.Logger,
) -> CollectResult:
    day_dir = DATA_ROOT / snapshot_date
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{safe_filename(symbol)}.parquet"
    if path.exists() and not force:
        existing = pd.read_parquet(path)
        log.info("symbol=%s rows=%d reused_existing=1 out=%s", symbol, len(existing), path)
        return CollectResult(symbol=symbol, rows=len(existing), pages=None, reused=True)

    api_key = _ensure_api_key()
    api_symbol = massive_underlying_symbol(symbol)
    next_url: str | None = f"{BASE_URL}/v3/snapshot/options/{api_symbol}"
    params: dict[str, Any] | None = {"apiKey": api_key, "limit": PAGE_LIMIT, "sort": "ticker"}
    results: list[dict[str, Any]] = []
    pages = 0

    while next_url:
        body = _get_json(session, next_url, params=params)
        pages += 1
        page_rows = body.get("results") or []
        if not isinstance(page_rows, list):
            raise RuntimeError(f"unexpected results payload for {symbol}")
        results.extend(page_rows)
        next_val = body.get("next_url")
        next_url = _with_api_key(next_val, api_key) if next_val else None
        params = None
        if next_url:
            time.sleep(REQUEST_PAUSE_SEC)

    frame = _normalize_frame(symbol, snapshot_date, results)
    frame.to_parquet(path, index=False)
    log.info("symbol=%s rows=%d pages=%d out=%s", symbol, len(frame), pages, path)
    return CollectResult(symbol=symbol, rows=len(frame), pages=pages)


def run(*, snapshot_day: date, symbols: list[str], force: bool, verbose: bool, send_telegram: bool = True) -> int:
    log = _logger(verbose)
    if not _trading_day(snapshot_day):
        log.info("non-trading day (%s) — skipping", snapshot_day.strftime("%a"))
        return 0

    _ensure_api_key()
    snapshot_date = snapshot_day.isoformat()
    day_dir = DATA_ROOT / snapshot_date
    day_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    ok = 0
    errors = 0
    results: list[CollectResult] = []

    for symbol in symbols:
        try:
            result = _fetch_symbol_snapshot(session, symbol, snapshot_date, force, log)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            log.exception("snapshot fetch failed for %s", symbol)
            result = CollectResult(symbol=symbol, rows=0, pages=None, error=str(exc))
            errors += 1
        results.append(result)
        time.sleep(REQUEST_PAUSE_SEC)

    summary = {
        "snapshot_date": snapshot_date,
        "symbols_requested": symbols,
        "ok": ok,
        "errors": errors,
        "total_rows": sum(r.rows for r in results),
        "results": [
            {
                "symbol": r.symbol,
                "rows": r.rows,
                "pages": r.pages,
                "reused": r.reused,
                "error": r.error,
            }
            for r in results
        ],
    }
    (day_dir / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("done snapshot_date=%s ok=%d errors=%d total_rows=%d", snapshot_date, ok, errors, summary["total_rows"])
    integrity = _integrity_record(snapshot_day)
    _append_integrity_record(integrity)
    if integrity["missing_days"]:
        log.warning("snapshot integrity warning date=%s missing=%s", snapshot_date, ",".join(integrity["missing_days"]))
        alert_text = _build_integrity_alert_text(integrity)
        if alert_text and send_telegram:
            _send_telegram_message(alert_text, log)
    return 0 if errors == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Massive options chain snapshots for Q041 whitelist")
    parser.add_argument("--date", default=None, help="Snapshot day label YYYY-MM-DD (default: today ET)")
    parser.add_argument("--symbols", nargs="*", help="Override whitelist symbols")
    parser.add_argument("--force", action="store_true", help="Overwrite existing symbol parquet for the day")
    parser.add_argument("--skip-telegram", action="store_true", help="Do not send integrity Telegram alerts")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    snapshot_day = datetime.now(ET).date() if not args.date else date.fromisoformat(args.date)
    symbols = _target_symbols(args.symbols)
    return run(
        snapshot_day=snapshot_day,
        symbols=symbols,
        force=args.force,
        verbose=args.verbose,
        send_telegram=not args.skip_telegram,
    )


if __name__ == "__main__":
    raise SystemExit(main())
