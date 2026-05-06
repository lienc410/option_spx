"""Q041 Gate 0 — Massive.com Basic (free) tier data coverage validation.

Usage:
    MASSIVE_API_KEY=your_key python -m research.q041.validate_massive
    # or:
    python research/q041/validate_massive.py --api-key YOUR_KEY

What this tests (all within Basic $0 rate limits: 5 calls/min):
  1. Reference data — option contracts exist for all 12 whitelist symbols
  2. Daily OHLCV history — can we pull 2 years of daily bars for a sample contract?
  3. Snapshot availability — expected FAIL on Basic (documents the tier limit)
  4. SPX index options — confirm $SPX / I:SPX symbol format works

Expected results per tier:
  Basic ($0):  Reference=PASS, Aggregates=PASS, Snapshot=FAIL (plan gate)
  Starter($29)+: all PASS, Snapshot 15-min delayed
  Developer($79)+: + Trades in response
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.q041.whitelist import WHITELIST  # noqa: E402

BASE_URL = "https://api.massive.com"
PAUSE = 13.0  # >12s between calls to stay under 5/min rate limit


def _get(api_key: str, path: str, params: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    p = {"apiKey": api_key, **(params or {})}
    r = requests.get(url, params=p, timeout=20)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:200]}
    return r.status_code, body


def _pause(label: str) -> None:
    print(f"  [rate-limit pause {PAUSE:.0f}s after {label}]", flush=True)
    time.sleep(PAUSE)


def test_reference_contracts(api_key: str, symbol: str) -> dict:
    """Check that option contracts exist for this underlying."""
    status, body = _get(
        api_key,
        "/v3/reference/options/contracts",
        {"underlying_ticker": symbol, "limit": 5, "sort": "expiration_date"},
    )
    count = len(body.get("results", []))
    return {
        "test": "reference_contracts",
        "symbol": symbol,
        "status_code": status,
        "contract_count": count,
        "pass": status == 200 and count > 0,
        "detail": body.get("status") or body.get("error") or f"{count} contracts",
    }


def test_daily_aggregates(api_key: str, option_ticker: str) -> dict:
    """Pull 30 days of daily OHLCV for a specific option contract."""
    end = (date.today() - timedelta(days=5)).isoformat()
    start = (date.today() - timedelta(days=35)).isoformat()
    status, body = _get(
        api_key,
        f"/v2/aggs/ticker/{option_ticker}/range/1/day/{start}/{end}",
        {"adjusted": "true", "sort": "asc", "limit": 50},
    )
    bars = body.get("resultsCount", 0) or len(body.get("results", []))
    sample = body.get("results", [None])[0]
    fields = set(sample.keys()) if sample else set()
    return {
        "test": "daily_aggregates",
        "ticker": option_ticker,
        "status_code": status,
        "bars": bars,
        "fields": sorted(fields),
        "has_greeks": any(f in fields for f in ("delta", "gamma", "iv", "implied_volatility")),
        "pass": status == 200 and bars > 0,
        "detail": body.get("status") or body.get("error") or f"{bars} daily bars",
    }


def test_chain_snapshot(api_key: str, symbol: str) -> dict:
    """Option chain snapshot — expected FAIL on Basic (plan gate)."""
    status, body = _get(
        api_key,
        f"/v3/snapshot/options/{symbol}",
        {"limit": 5, "sort": "ticker"},
    )
    count = len(body.get("results", []))
    sample = body.get("results", [None])[0] or {}
    has_greeks = "greeks" in sample
    has_iv = "implied_volatility" in sample
    has_oi = "open_interest" in sample
    return {
        "test": "chain_snapshot",
        "symbol": symbol,
        "status_code": status,
        "contract_count": count,
        "has_greeks": has_greeks,
        "has_iv": has_iv,
        "has_oi": has_oi,
        "pass": status == 200 and count > 0,
        "detail": body.get("status") or body.get("error") or f"{count} contracts, greeks={has_greeks}",
        "note": "Expected FAIL on Basic (plan gate). PASS here = upgrade may not be needed for snapshot.",
    }


def test_historical_depth(api_key: str, option_ticker: str, years_back: int = 2) -> dict:
    """Check data availability at the claimed historical depth."""
    end = (date.today() - timedelta(days=365 * years_back - 5)).isoformat()
    start = (date.today() - timedelta(days=365 * years_back + 30)).isoformat()
    status, body = _get(
        api_key,
        f"/v2/aggs/ticker/{option_ticker}/range/1/day/{start}/{end}",
        {"adjusted": "true", "sort": "asc", "limit": 10},
    )
    bars = body.get("resultsCount", 0) or len(body.get("results", []))
    return {
        "test": f"history_depth_{years_back}y",
        "ticker": option_ticker,
        "window": f"{start} → {end}",
        "status_code": status,
        "bars": bars,
        "pass": status == 200 and bars > 0,
        "detail": body.get("status") or body.get("error") or f"{bars} bars in {years_back}y-ago window",
    }


def run(api_key: str) -> None:
    results = []
    print(f"\n{'='*60}")
    print("Q041 — Massive.com Basic Tier Data Coverage Validation")
    print(f"{'='*60}\n")

    # --- Phase 1: Reference data for all whitelist symbols ---
    print("Phase 1: Reference contracts (all 12 symbols)")
    print("-" * 40)
    ref_symbols_ok = []
    for sym in WHITELIST:
        r = test_reference_contracts(api_key, sym)
        results.append(r)
        status_str = "PASS" if r["pass"] else "FAIL"
        print(f"  {sym:<8} {status_str}  {r['detail']}")
        if r["pass"]:
            ref_symbols_ok.append((sym, r))
        _pause(sym)

    # Pick sample contracts for deeper tests: AAPL + SPX
    sample_contracts: dict[str, str] = {}

    # --- Phase 2: Get a live option ticker for AAPL and SPX to use in deeper tests ---
    print("\nPhase 2: Resolve sample option tickers for aggregate + snapshot tests")
    print("-" * 40)
    for sym in ("AAPL", "SPX"):
        status, body = _get(
            api_key,
            "/v3/reference/options/contracts",
            {
                "underlying_ticker": sym,
                "contract_type": "call",
                "limit": 1,
                "sort": "expiration_date",
                "order": "asc",
            },
        )
        contracts = body.get("results", [])
        if contracts:
            ticker = contracts[0].get("ticker", "")
            sample_contracts[sym] = ticker
            print(f"  {sym}: {ticker}")
        else:
            print(f"  {sym}: no contracts found (status={status})")
        _pause(f"resolve-{sym}")

    # --- Phase 3: Daily aggregates + historical depth ---
    print("\nPhase 3: Daily OHLCV aggregates + historical depth")
    print("-" * 40)
    for sym, ticker in sample_contracts.items():
        if not ticker:
            continue
        r = test_daily_aggregates(api_key, ticker)
        results.append(r)
        print(f"  {sym} ({ticker}): {'PASS' if r['pass'] else 'FAIL'} — {r['detail']}")
        print(f"    fields: {r['fields']}")
        print(f"    has_greeks_in_ohlcv: {r['has_greeks']}")
        _pause(f"aggs-{sym}")

        r2 = test_historical_depth(api_key, ticker, years_back=2)
        results.append(r2)
        print(f"  {sym} 2yr history: {'PASS' if r2['pass'] else 'FAIL'} — {r2['detail']}")
        _pause(f"hist-{sym}")

    # --- Phase 4: Chain snapshot (expected to fail on Basic) ---
    print("\nPhase 4: Chain snapshot with Greeks/IV/OI (plan-gated)")
    print("-" * 40)
    for sym in ("AAPL", "SPX"):
        r = test_chain_snapshot(api_key, sym)
        results.append(r)
        status_str = "PASS" if r["pass"] else "FAIL (plan gate — expected on Basic)"
        print(f"  {sym}: {status_str}")
        if r["pass"]:
            print(f"    greeks={r['has_greeks']} iv={r['has_iv']} oi={r['has_oi']}")
        _pause(f"snapshot-{sym}")

    # --- Summary ---
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    all_ref_ok = sum(1 for r in results if r["test"] == "reference_contracts" and r["pass"])
    all_ref_total = sum(1 for r in results if r["test"] == "reference_contracts")
    agg_ok = sum(1 for r in results if r["test"] == "daily_aggregates" and r["pass"])
    hist_ok = sum(1 for r in results if "history_depth" in r["test"] and r["pass"])
    snap_ok = sum(1 for r in results if r["test"] == "chain_snapshot" and r["pass"])

    print(f"  Reference coverage:  {all_ref_ok}/{all_ref_total} symbols OK")
    print(f"  Daily aggregates:    {agg_ok}/2 sample symbols OK")
    print(f"  Historical depth 2y: {hist_ok}/2 sample symbols OK")
    print(f"  Snapshot (Greeks):   {snap_ok}/2 (0 expected on Basic)")

    # Verdict
    print()
    if all_ref_ok == all_ref_total and agg_ok >= 1:
        print("VERDICT: PASS — Symbol coverage confirmed. Safe to buy Developer ($79).")
        if snap_ok > 0:
            print("         Bonus: Snapshot also works on Basic — Greeks available NOW.")
    elif all_ref_ok >= 10:
        print("VERDICT: PARTIAL — Most symbols covered. Check failed symbols before purchase.")
    else:
        print("VERDICT: FAIL — Significant coverage gaps. Investigate before buying.")

    # Failed symbols
    failed = [r["symbol"] for r in results if r["test"] == "reference_contracts" and not r["pass"]]
    if failed:
        print(f"\n  Missing symbols: {failed}")

    print()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Massive.com Basic tier data coverage validation")
    p.add_argument("--api-key", default=os.environ.get("MASSIVE_API_KEY"), help="Massive API key (or set MASSIVE_API_KEY env var)")
    args = p.parse_args(argv)
    if not args.api_key:
        print("ERROR: set MASSIVE_API_KEY env var or pass --api-key")
        sys.exit(1)
    run(args.api_key)


if __name__ == "__main__":
    main()
