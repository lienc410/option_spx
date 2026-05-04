"""Q041 historical Massive flat-file bulk downloader.

Downloads daily OPRA aggregates from Massive S3 flat files and writes
per-underlying parquet partitions under ``data/q041_historical/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import boto3
import pandas as pd
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.q041.whitelist import WHITELIST  # noqa: E402

ET = ZoneInfo("America/New_York")
DATA_ROOT = REPO_ROOT / "data" / "q041_historical"
LOG_DIR = REPO_ROOT / "logs"
DOWNLOAD_LOG = DATA_ROOT / "_download_log.json"

DEFAULT_START = date(2022, 5, 6)
HTTP_TIMEOUT = 30
MAX_RETRIES = 3

load_dotenv(REPO_ROOT / ".env")


def _logger(verbose: bool) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("q041_download_massive")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(LOG_DIR / "q041_download_massive.log")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log


def safe_filename(symbol: str) -> str:
    return symbol.lstrip("/").replace("/", "_")


def parse_occ_ticker(ticker: str) -> dict[str, Any] | None:
    """Parse Massive OCC ticker into raw components.

    Expected format example: ``O:AAPL220520C00120000``.
    """

    if not ticker:
        return None
    raw = ticker[2:] if ticker.startswith("O:") else ticker
    if len(raw) < 15:
        return None
    try:
        strike = int(raw[-8:]) / 1000.0
    except ValueError:
        return None
    option_type = raw[-9]
    expiry_raw = raw[-15:-9]
    if option_type not in {"C", "P"} or len(expiry_raw) != 6 or not expiry_raw.isdigit():
        return None
    try:
        expiry = datetime.strptime(expiry_raw, "%y%m%d").date().isoformat()
    except ValueError:
        return None
    underlying_raw = raw[:-15]
    if not underlying_raw:
        return None
    return {
        "underlying_raw": underlying_raw,
        "expiry": expiry,
        "option_type": option_type,
        "strike": strike,
    }


def map_underlying(underlying_raw: str, trade_date: str) -> str:
    if underlying_raw == "SPXW":
        return "SPX"
    if underlying_raw == "SPX":
        return "SPX"
    if underlying_raw == "BRKB":
        return "BRK/B"
    if underlying_raw == "FB" and trade_date <= "2022-06-08":
        return "META"
    return underlying_raw


def _date_range(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _build_s3_client():
    access_key = os.environ["MASSIVE_S3_ACCESS_KEY_ID"]
    secret_key = os.environ["MASSIVE_S3_SECRET_ACCESS_KEY"]
    endpoint = os.environ.get("MASSIVE_S3_ENDPOINT", "https://files.massive.com")
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    return session.client(
        "s3",
        endpoint_url=endpoint,
        config=Config(signature_version="s3v4", read_timeout=HTTP_TIMEOUT, connect_timeout=HTTP_TIMEOUT),
    )


def _bucket_name() -> str:
    return os.environ.get("MASSIVE_S3_BUCKET", "flatfiles")


def _key_for_day(day: date) -> str:
    return f"us_options_opra/day_aggs_v1/{day:%Y/%m/%Y-%m-%d}.csv.gz"


def _download_day_frame(day: date, client, log: logging.Logger) -> pd.DataFrame | None:
    bucket = _bucket_name()
    key = _key_for_day(day)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
            body = obj["Body"].read()
            return pd.read_csv(BytesIO(body), compression="gzip")
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"NoSuchKey", "404"} or status == 404:
                log.info("holiday_skip %s key=%s", day.isoformat(), key)
                return None
            raise
        except (ConnectTimeoutError, ReadTimeoutError, TimeoutError) as exc:
            log.warning("timeout day=%s attempt=%d/%d err=%s", day.isoformat(), attempt, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(1.0 * attempt)
    return None


def _target_symbols(symbols_override: list[str] | None) -> list[str]:
    symbols = list(symbols_override) if symbols_override else list(WHITELIST)
    return list(dict.fromkeys(symbols))


def _raw_symbol_keep_set(target_symbols: list[str]) -> set[str]:
    raw_keep = set()
    for sym in target_symbols:
        raw_keep.add(sym)
        if sym == "SPX":
            raw_keep.update({"SPX", "SPXW"})
        elif sym == "BRK/B":
            raw_keep.add("BRKB")
        elif sym == "META":
            raw_keep.update({"META", "FB"})
    return raw_keep


def _load_existing_dates(target_symbols: list[str]) -> dict[str, set[str]]:
    existing: dict[str, set[str]] = {}
    for symbol in target_symbols:
        path = DATA_ROOT / f"{safe_filename(symbol)}.parquet"
        if not path.exists():
            existing[symbol] = set()
            continue
        df = pd.read_parquet(path, columns=["date"])
        existing[symbol] = set(df["date"].astype(str).unique().tolist())
    return existing


def _load_existing_frames(processed_symbols: set[str]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in processed_symbols:
        path = DATA_ROOT / f"{safe_filename(symbol)}.parquet"
        if path.exists():
            frames[symbol] = pd.read_parquet(path)
        else:
            frames[symbol] = pd.DataFrame()
    return frames


def _should_skip_day(
    day_str: str,
    target_symbols: list[str],
    existing_dates: dict[str, set[str]],
    max_existing_date: str | None,
    force: bool,
) -> bool:
    if force:
        return False
    if max_existing_date is None:
        return False
    if day_str == max_existing_date:
        return False
    if day_str < max_existing_date:
        return all(day_str in existing_dates.get(symbol, set()) for symbol in target_symbols)
    return False


def _normalize_day_frame(
    df: pd.DataFrame,
    day_str: str,
    target_symbols: list[str],
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "date", "underlying", "option_type", "expiry", "strike", "open",
            "high", "low", "close", "volume", "transactions", "occ_ticker",
        ])

    work = df.loc[:, ["ticker", "volume", "open", "close", "high", "low", "window_start", "transactions"]].copy()
    raw = work["ticker"].astype(str)
    occ = raw.str[2:].where(raw.str.startswith("O:"), raw)
    valid_len = occ.str.len() >= 15
    work = work.loc[valid_len].copy()
    occ = occ.loc[valid_len]

    work["underlying_raw"] = occ.str.slice(stop=-15)
    raw_keep = _raw_symbol_keep_set(target_symbols)
    work = work.loc[work["underlying_raw"].isin(raw_keep)].copy()
    if work.empty:
        return pd.DataFrame(columns=[
            "date", "underlying", "option_type", "expiry", "strike", "open",
            "high", "low", "close", "volume", "transactions", "occ_ticker",
        ])

    occ = raw.loc[work.index].astype(str)
    occ_core = occ.str[2:].where(occ.str.startswith("O:"), occ)
    work["option_type"] = occ_core.str[-9]
    work["expiry"] = pd.to_datetime(occ_core.str[-15:-9], format="%y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    strikes = pd.to_numeric(occ_core.str[-8:], errors="coerce")
    work["strike"] = strikes / 1000.0
    work = work.loc[
        work["option_type"].isin(["C", "P"])
        & work["expiry"].notna()
        & work["strike"].notna()
    ].copy()
    if work.empty:
        return pd.DataFrame(columns=[
            "date", "underlying", "option_type", "expiry", "strike", "open",
            "high", "low", "close", "volume", "transactions", "occ_ticker",
        ])

    work["underlying"] = work["underlying_raw"].map(lambda raw_sym: map_underlying(raw_sym, day_str))
    work = work.loc[work["underlying"].isin(target_symbols)].copy()
    if work.empty:
        return pd.DataFrame(columns=[
            "date", "underlying", "option_type", "expiry", "strike", "open",
            "high", "low", "close", "volume", "transactions", "occ_ticker",
        ])

    if "window_start" in work.columns:
        ts = pd.to_datetime(work["window_start"], unit="ns", utc=True, errors="coerce").dt.tz_convert(ET)
        work["date"] = ts.dt.strftime("%Y-%m-%d").fillna(day_str)
    else:
        work["date"] = day_str
    work["occ_ticker"] = occ.loc[work.index].astype(str)

    for col in ["open", "high", "low", "close", "strike"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    for col in ["volume", "transactions"]:
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0).astype(int)

    out = work[[
        "date",
        "underlying",
        "option_type",
        "expiry",
        "strike",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "transactions",
        "occ_ticker",
    ]].copy()
    return out


def _merge_symbol_frame(existing: pd.DataFrame, new_rows: pd.DataFrame, overwrite_dates: set[str]) -> pd.DataFrame:
    if existing.empty:
        merged = new_rows.copy()
    else:
        base = existing.loc[~existing["date"].astype(str).isin(overwrite_dates)].copy()
        merged = pd.concat([base, new_rows], ignore_index=True)
    if merged.empty:
        return merged
    merged = merged.drop_duplicates(
        subset=["date", "occ_ticker"],
        keep="last",
    )
    merged = merged.sort_values(["date", "underlying", "expiry", "option_type", "strike", "occ_ticker"]).reset_index(drop=True)
    return merged


def _write_download_log(summary: dict[str, Any]) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    if DOWNLOAD_LOG.exists():
        try:
            payload = json.loads(DOWNLOAD_LOG.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                payload = [payload]
        except Exception:
            payload = []
    else:
        payload = []
    payload.append(summary)
    DOWNLOAD_LOG.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run(
    *,
    start: date,
    end: date,
    symbols_override: list[str] | None,
    force: bool,
    log: logging.Logger,
) -> int:
    target_symbols = _target_symbols(symbols_override)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    existing_dates = _load_existing_dates(target_symbols)
    existing_all_dates = sorted({d for dates in existing_dates.values() for d in dates})
    max_existing_date = max(existing_all_dates) if existing_all_dates else None

    log.info(
        "Q041 historical download start | %s -> %s | symbols=%d | force=%s | max_existing_date=%s",
        start.isoformat(),
        end.isoformat(),
        len(target_symbols),
        force,
        max_existing_date,
    )

    client = _build_s3_client()
    pending_by_symbol: dict[str, list[pd.DataFrame]] = defaultdict(list)
    overwrite_dates_by_symbol: dict[str, set[str]] = defaultdict(set)
    processed_symbols: set[str] = set()
    per_symbol_rows: dict[str, int] = defaultdict(int)
    skipped_dates: list[str] = []
    holiday_skips: list[str] = []
    error_dates: dict[str, str] = {}
    total_rows = 0
    total_rows_kept = 0

    for day in _date_range(start, end):
        day_str = day.isoformat()
        if _should_skip_day(day_str, target_symbols, existing_dates, max_existing_date, force):
            skipped_dates.append(day_str)
            log.info("skip %s reason=already_complete", day_str)
            continue

        try:
            raw_df = _download_day_frame(day, client, log)
        except Exception as exc:  # noqa: BLE001
            error_dates[day_str] = str(exc)
            log.error("download_failed day=%s err=%s", day_str, exc)
            continue

        if raw_df is None:
            holiday_skips.append(day_str)
            continue

        rows_total = len(raw_df)
        total_rows += rows_total
        day_df = _normalize_day_frame(raw_df, day_str, target_symbols)
        rows_kept = len(day_df)
        total_rows_kept += rows_kept

        symbols_found = sorted(day_df["underlying"].unique().tolist()) if not day_df.empty else []
        for symbol in symbols_found:
            symbol_rows = day_df.loc[day_df["underlying"] == symbol].copy()
            pending_by_symbol[symbol].append(symbol_rows)
            overwrite_dates_by_symbol[symbol].add(day_str)
            processed_symbols.add(symbol)
            per_symbol_rows[symbol] += len(symbol_rows)

        # If the day is being reprocessed, clear old rows even when now there are zero kept rows.
        if force or (max_existing_date and day_str <= max_existing_date):
            for symbol in target_symbols:
                if day_str in existing_dates.get(symbol, set()):
                    overwrite_dates_by_symbol[symbol].add(day_str)
                    processed_symbols.add(symbol)

        log.info(
            "date=%s rows_total=%d rows_kept=%d symbols_found=%s",
            day_str,
            rows_total,
            rows_kept,
            ",".join(symbols_found) if symbols_found else "-",
        )

    existing_frames = _load_existing_frames(processed_symbols)
    for symbol in processed_symbols:
        new_rows = pd.concat(pending_by_symbol.get(symbol, []), ignore_index=True) if pending_by_symbol.get(symbol) else pd.DataFrame()
        merged = _merge_symbol_frame(existing_frames.get(symbol, pd.DataFrame()), new_rows, overwrite_dates_by_symbol.get(symbol, set()))
        out_path = DATA_ROOT / f"{safe_filename(symbol)}.parquet"
        merged.to_parquet(out_path, index=False)

    summary = {
        "run_ts_et": datetime.now(ET).isoformat(timespec="seconds"),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "symbols": target_symbols,
        "force": force,
        "max_existing_date": max_existing_date,
        "rows_total_downloaded": total_rows,
        "rows_kept": total_rows_kept,
        "per_symbol_rows": dict(sorted(per_symbol_rows.items())),
        "skipped_dates": skipped_dates,
        "holiday_skips": holiday_skips,
        "errors": error_dates,
    }
    _write_download_log(summary)
    log.info(
        "Q041 historical download done | kept=%d | skipped=%d | holidays=%d | errors=%d",
        total_rows_kept,
        len(skipped_dates),
        len(holiday_skips),
        len(error_dates),
    )
    return 0 if not error_dates else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q041 Massive historical flat-file downloader")
    parser.add_argument("--start", default=DEFAULT_START.isoformat(), help="start date YYYY-MM-DD")
    parser.add_argument("--end", default=date.today().isoformat(), help="end date YYYY-MM-DD")
    parser.add_argument("--symbols", nargs="*", help="optional symbols override")
    parser.add_argument("--force", action="store_true", help="reprocess all requested dates")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        raise SystemExit("--end must be >= --start")

    log = _logger(args.verbose)
    return run(
        start=start,
        end=end,
        symbols_override=args.symbols,
        force=args.force,
        log=log,
    )


if __name__ == "__main__":
    raise SystemExit(main())
