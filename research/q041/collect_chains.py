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

# Schwab API gateway has a response-body size limit ("TooBigBody").
# $SPX has 5-pt increments and many weeklies; 100 strikes × 180-day window
# stays under the limit while covering 40 expirations and ±250 pts (~±4.5%).
_STRIKE_COUNT: dict[str, int] = {
    "$SPX": 100,
}
_DTE_WINDOW: dict[str, int] = {
    "$SPX": 180,
}


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


def _fetch_full_chain(symbol: str) -> tuple[list[dict], list[dict]]:
    """Pull full multi-expiry chain — both call and put exp maps in one call."""
    today = date.today()
    api_sym = _marketdata_symbol(symbol)
    params = {
        "symbol": api_sym,
        "contractType": "ALL",
        "strikeCount": _STRIKE_COUNT.get(api_sym, 500),
        "includeQuotes": "TRUE",
        "fromDate": today.isoformat(),
        "toDate": (today + timedelta(days=_DTE_WINDOW.get(api_sym, DTE_WINDOW_DAYS))).isoformat(),
    }
    res = requests.get(
        f"{BASE_URL}/marketdata/v1/chains",
        params=params,
        headers=_headers(),
        timeout=HTTP_TIMEOUT,
    )
    res.raise_for_status()
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
    ]
    df = df.reindex(columns=cols_order)
    for col in ("strike", "bid", "ask", "mid", "spread_pct", "delta"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("open_interest", "volume", "dte"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _safe_filename(symbol: str) -> str:
    # Leading slash → futures prefix (e.g. "/ES" → "ES").
    # Mid-slash → underscore (e.g. "BRK/B" → "BRK_B").
    s = symbol.lstrip("/")
    return s.replace("/", "_")


def collect_one(symbol: str, snapshot_date: str, snapshot_ts: str, log: logging.Logger) -> CollectResult:
    try:
        calls, puts = _fetch_full_chain(symbol)
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
