"""Smoke test: pull one Schwab + one E*Trade quote and dump freshness fields.

Usage:
    venv/bin/python scripts/quote_freshness_smoke.py

PM run-at-three-timepoints check (per quote-freshness task 2026-05-21):
  - intraday  10am–3pm ET → expect Schwab realtime=true,  ETrade quote_status=REALTIME
  - 4:20pm ET              → expect ETrade quote_status=CLOSING (settlement window)
  - 5:00pm ET              → expect ETrade quote_status=EH_CLOSED
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# repo root on path so imports work when invoked from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etrade.client import get_option_spread_quote
from schwab.client import get_index_quote, spread_quote_for_strikes


def _dump(label: str, obj: dict, keys: list[str]) -> None:
    """Print a labeled subset of a dict to keep output skimmable."""
    print(f"\n--- {label} ---")
    print(json.dumps({k: obj.get(k) for k in keys}, indent=2, default=str))


def main() -> int:
    now_et = datetime.now(ZoneInfo("America/New_York"))
    print(f"=== Quote freshness smoke @ {now_et:%Y-%m-%d %H:%M:%S} ET ===")

    # --- Schwab index quote (SPX) -----------------------------------------
    try:
        schwab_idx = get_index_quote("$SPX")
        _dump("Schwab $SPX index quote",
              schwab_idx,
              ["last", "realtime", "quote_time", "security_status"])
    except Exception as exc:
        print(f"\nSchwab index quote FAILED: {exc}")

    # --- Schwab spread quote (use a likely-active strike pair) ------------
    # Customize these for the current open position; defaults match the
    # 6/18 7300/7000 BPS held on 2026-05-21.
    sw_expiry = "2026-06-18"
    sw_short, sw_long = 7300, 7000
    try:
        schwab_spread = spread_quote_for_strikes("SPX", sw_expiry, sw_short, sw_long)
        _dump(f"Schwab SPX {sw_expiry} {sw_short}/{sw_long} spread",
              schwab_spread,
              ["visible", "mark", "bid", "ask", "realtime", "quote_time"])
    except Exception as exc:
        print(f"\nSchwab spread quote FAILED: {exc}")

    # --- ETrade spread quote ---------------------------------------------
    et_expiry = "2026-06-18"
    et_short, et_long = 7300, 7000
    try:
        etrade_spread = get_option_spread_quote(
            underlier="SPX", expiry=et_expiry,
            short_strike=float(et_short), long_strike=float(et_long),
        )
        _dump(f"ETrade SPX {et_expiry} {et_short}/{et_long} spread",
              etrade_spread,
              ["visible", "mark", "bid", "ask",
               "quote_status", "ah_flag", "date_time_utc"])
        # Per-leg detail for ambiguity diagnosis
        if etrade_spread.get("visible"):
            _dump("ETrade short_leg",
                  etrade_spread.get("short_leg") or {},
                  ["bid", "ask", "mark", "quote_status", "date_time_utc"])
            _dump("ETrade long_leg",
                  etrade_spread.get("long_leg") or {},
                  ["bid", "ask", "mark", "quote_status", "date_time_utc"])
    except Exception as exc:
        print(f"\nETrade spread quote FAILED: {exc}")

    print("\n=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
