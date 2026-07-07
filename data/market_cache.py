from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import pandas as pd


_CACHE_DIR = Path(__file__).parent / "market_cache"


@dataclass(frozen=True)
class CachePolicy:
    ttl: timedelta


def _cache_disabled() -> bool:
    return os.getenv("SPX_DISABLE_YF_CACHE", "").strip().lower() in {"1", "true", "yes"}


def _cache_refresh_requested() -> bool:
    return os.getenv("SPX_REFRESH_YF_CACHE", "").strip().lower() in {"1", "true", "yes"}


def _sanitize(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", token)


def _policy_for_interval(interval: str) -> CachePolicy:
    if interval == "5m":
        return CachePolicy(ttl=timedelta(minutes=15))
    if interval == "1h":
        return CachePolicy(ttl=timedelta(hours=6))
    return CachePolicy(ttl=timedelta(hours=18))


def _cache_path(source: str, symbol: str, period: str, interval: str) -> Path:
    fname = "__".join([
        _sanitize(source),
        _sanitize(symbol),
        _sanitize(period),
        _sanitize(interval),
    ]) + ".pkl"
    return _CACHE_DIR / fname


def _is_fresh(path: Path, interval: str) -> bool:
    if not path.exists():
        return False
    age = pd.Timestamp.utcnow() - pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC")
    return age <= _policy_for_interval(interval).ttl


def _expected_last_daily_bar() -> "datetime.date":
    """Most recent US session date whose daily bar should exist by now (ET).

    Before ~17:00 ET the current session's bar may not be published yet, so
    expect the prior weekday. Holidays aren't modeled — on a holiday this
    expects a bar that doesn't exist, which just forces one refetch per TTL
    window (fetch failure falls back to the stale frame, so it's harmless).
    """
    now = datetime.now(ZoneInfo("America/New_York"))
    d = now.date()
    if now.hour < 17:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _content_stale(df: pd.DataFrame, interval: str) -> bool:
    """Wall-clock TTL alone is not enough for daily bars: a pre-market fetch
    (e.g. 08:14 ET) caches a frame whose last row is the PRIOR session, and
    an 18h TTL then serves that prior close as "fresh" for the entire trading
    day — 2026-07-06 the recommendation engine quoted SPX 7,483 (7/02 close)
    all evening while the market closed at 7,537. For 1d frames, also require
    the last bar to be the most recent expected session.
    """
    if interval != "1d" or df.empty:
        return False
    try:
        last = pd.Timestamp(df.index[-1]).date()
    except Exception:
        return False
    return last < _expected_last_daily_bar()


def _load_cached_df(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    cached = pd.read_pickle(path)
    if isinstance(cached, pd.DataFrame) and not cached.empty:
        return cached
    return None


def load_or_fetch_history(
    *,
    source: str,
    symbol: str,
    period: str,
    interval: str,
    fetcher: Callable[[], pd.DataFrame],
) -> pd.DataFrame:
    """
    Cache Yahoo Finance history on disk so repeated backtests and prototypes
    do not re-download the same market data on every process start.

    Environment variables:
      SPX_DISABLE_YF_CACHE=1  -> bypass local cache completely
      SPX_REFRESH_YF_CACHE=1  -> force refresh and overwrite cache
    """
    if _cache_disabled():
        return fetcher()

    path = _cache_path(source, symbol, period, interval)
    if not _cache_refresh_requested() and _is_fresh(path, interval):
        cached = _load_cached_df(path)
        if cached is not None and not _content_stale(cached, interval):
            return cached

    stale = None if _cache_refresh_requested() else _load_cached_df(path)
    try:
        df = fetcher()
    except Exception:
        if stale is not None:
            return stale
        raise
    if df.empty:
        if stale is not None:
            return stale
        return df

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df
