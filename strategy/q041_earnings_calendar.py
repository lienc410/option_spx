"""SPEC-115 Phase B — Q041 earnings calendar via yfinance.

Caches next-earnings-date per T3 symbol. Stale guard rejects past dates
(yfinance sometimes returns the last reported earnings date).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = REPO_ROOT / "data" / "q041_earnings_calendar.json"
ALERT_PATH = REPO_ROOT / "data" / "q041_earnings_alert.jsonl"
T3_SYMBOLS = ["COST", "JPM"]


def _coerce_date(val) -> date | None:
    """Normalize a yfinance calendar value to a date."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def get_next_earnings_date(symbol: str) -> date | None:
    """Next upcoming earnings date for symbol, or None if missing/stale/error.

    Stale guard: if yfinance returns a date < today, treats it as stale → None.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        cal = t.calendar
    except Exception as e:
        log.warning("yfinance calendar fetch for %s failed: %s", symbol, e)
        _emit_alert(symbol, f"yfinance_error:{e}")
        return None

    if not cal or "Earnings Date" not in cal:
        return None
    dates = cal["Earnings Date"]
    if not dates:
        return None
    raw = dates[0] if isinstance(dates, (list, tuple)) else dates
    next_date = _coerce_date(raw)
    if next_date is None:
        return None
    # Stale guard
    if next_date < date.today():
        log.info("%s yfinance returned stale date %s < today; skipping", symbol, next_date)
        return None
    return next_date


def refresh_cache() -> dict:
    """Refresh cache for all T3 symbols, write to CACHE_PATH. Returns the cache dict."""
    cache: dict = {"refreshed_at": datetime.now(ET).isoformat(timespec="seconds")}
    for sym in T3_SYMBOLS:
        d = get_next_earnings_date(sym)
        cache[sym] = d.isoformat() if d else None
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return cache


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _emit_alert(symbol: str, reason: str) -> None:
    rec = {
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "symbol": symbol,
        "reason": reason,
    }
    ALERT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ALERT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    try:
        from notify.gateway import push as gw_push
        gw_push("ACTION", "系统状态", "Q041 earnings calendar",
                f"⚠ {symbol} {reason}", dedupe_key=f"q041_earncal_{symbol}")
    except Exception:
        pass


def main() -> int:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="SPEC-115 Q041 earnings calendar")
    p.add_argument("--refresh", action="store_true")
    args = p.parse_args()
    if args.refresh:
        c = refresh_cache()
        print(json.dumps(c, indent=2))
    else:
        print(json.dumps(load_cache(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
