"""SPEC-114 Part A — Q041 Chain Sanity Monitor (replaces dual-source alignment check).

Schwab-only chain quality check. Runs daily at 16:45 ET after collect_chains.
Appends one JSONL record to data/q041_chain_sanity_daily.jsonl, sends daily
Telegram report, and sends an alert if any check fails.

Checks:
  S1 symbol completeness  — which whitelist symbols have parquet files today
  S2 row count anomaly    — per-symbol row count vs 7-day rolling median (±50%)
  S3 IV completeness      — 0.25–0.75 |delta| IV non-null rate (target ≥ 95%)
  S4 EOD underlying presence — _underlying.parquet exists with 17 rows
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.q041.whitelist import WHITELIST  # noqa: E402

ET = ZoneInfo("America/New_York")
SCHWAB_ROOT = REPO_ROOT / "data" / "q041_chains"
OUTPUT_PATH = REPO_ROOT / "data" / "q041_chain_sanity_daily.jsonl"
LOG_DIR = REPO_ROOT / "logs"

N_WHITELIST = len(WHITELIST)

# S2 row-count anomaly bounds
S2_LOW_FACTOR = 0.50   # < 50% of median → anomaly
S2_HIGH_FACTOR = 2.0   # > 200% of median → anomaly
S2_ROLLING_DAYS = 7

# S3 IV completeness threshold
S3_IV_MIN_PCT = 95.0
S3_DELTA_LOW = 0.25
S3_DELTA_HIGH = 0.75

_US_HOLIDAYS: frozenset[str] = frozenset({
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26",
    "2027-05-31", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
})

load_dotenv(REPO_ROOT / ".env")


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class SanityRecord:
    date: str
    s1_present: int
    s1_total: int
    s1_missing: list[str]
    s2_anomaly_count: int
    s2_anomalies: list[dict]
    s3_iv_completeness_pct: float | None
    s4_eod_present: int
    s4_eod_total: int
    alert_fired: bool
    notes: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in _US_HOLIDAYS


def _safe_filename(symbol: str) -> str:
    return symbol.lstrip("/").replace("/", "_")


def _day_dir(day: date) -> Path:
    return SCHWAB_ROOT / day.isoformat()


def _available_symbols(day: date) -> set[str]:
    d = _day_dir(day)
    if not d.exists():
        return set()
    out: set[str] = set()
    for p in d.glob("*.parquet"):
        if not p.name.startswith("_"):
            out.add(p.stem)
    return out


def _symbol_row_count(sym: str, day: date) -> int | None:
    path = _day_dir(day) / f"{_safe_filename(sym)}.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path, columns=["symbol"])
        return len(df)
    except Exception:
        return None


def _rolling_median_rows(sym: str, end_day: date, window: int = S2_ROLLING_DAYS) -> float | None:
    """Compute median row count for sym over the last `window` trading days before end_day."""
    counts: list[int] = []
    d = end_day - timedelta(days=1)
    attempts = 0
    while len(counts) < window and attempts < window * 3:
        attempts += 1
        if _is_trading_day(d):
            n = _symbol_row_count(sym, d)
            if n is not None and n > 0:
                counts.append(n)
        d -= timedelta(days=1)
    if not counts:
        return None
    counts_sorted = sorted(counts)
    mid = len(counts_sorted) // 2
    if len(counts_sorted) % 2 == 0:
        return (counts_sorted[mid - 1] + counts_sorted[mid]) / 2.0
    return float(counts_sorted[mid])


def _check_s3_iv(day: date) -> float | None:
    """IV completeness for 0.25–0.75 |delta| contracts across all present symbols."""
    total = 0
    non_null = 0
    for sym in WHITELIST:
        path = _day_dir(day) / f"{_safe_filename(sym)}.parquet"
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path, columns=["delta", "iv"])
            mask = df["delta"].abs().between(S3_DELTA_LOW, S3_DELTA_HIGH)
            band = df[mask]
            if len(band) == 0:
                continue
            total += len(band)
            non_null += int(band["iv"].notna().sum())
        except Exception:
            continue
    if total == 0:
        return None
    return round(non_null / total * 100.0, 1)


def _check_s4_eod(day: date) -> int:
    """Count of symbols present in _underlying.parquet for the given day."""
    path = _day_dir(day) / "_underlying.parquet"
    if not path.exists():
        return 0
    try:
        df = pd.read_parquet(path, columns=["symbol"])
        return int(df["symbol"].nunique())
    except Exception:
        return 0


# ── Telegram ───────────────────────────────────────────────────────────────────

def _send_telegram(text: str, log: logging.Logger, *, category: str = "FYI") -> bool:
    # SPEC-126: through the gateway (was the last legacy direct sender in the
    # daily path — its pushes arrived without the category/about header and
    # never entered logs/push_stats.json). Host guard lives in the transport.
    try:
        from notify.gateway import escape, push as gw_push
        return gw_push(category, "系统状态", "", escape(text))
    except Exception:
        log.exception("telegram send failed")
        return False


def _build_report(rec: SanityRecord) -> str:
    s1_ok = "✅" if rec.s1_present == rec.s1_total else "❌"
    s2_ok = "✅" if rec.s2_anomaly_count == 0 else "❌"
    s3_ok = "✅" if (rec.s3_iv_completeness_pct is not None and rec.s3_iv_completeness_pct >= S3_IV_MIN_PCT) else "❌"
    s4_ok = "✅" if rec.s4_eod_present == rec.s4_eod_total else "❌"
    s3_str = f"{rec.s3_iv_completeness_pct:.1f}%" if rec.s3_iv_completeness_pct is not None else "—"
    # SPEC-136 — S1-S4 内部代号移出主文案（代码/日志层标识保留）
    return (
        f"📋 期权链数据体检 {rec.date}（sleeves）\n"
        f"标的覆盖:   {rec.s1_present}/{rec.s1_total} {s1_ok}\n"
        f"行数异常:   {rec.s2_anomaly_count} 个标的越界 {s2_ok}\n"
        f"IV 完整度: {s3_str} {s3_ok}\n"
        f"收盘数据:   {rec.s4_eod_present}/{rec.s4_eod_total} {s4_ok}"
    )


def _build_alert(rec: SanityRecord) -> str:
    lines = [f"⚠ 期权链数据体检告警 {rec.date}（sleeves）"]
    if rec.s1_missing:
        lines.append(f"标的缺失: {rec.s1_missing}")
    for a in rec.s2_anomalies:
        lines.append(
            f"行数异常: {a['symbol']} 今日 {a['rows']} 行 "
            f"vs 常态中位 {a['median']:.0f} 行（{a['pct_of_median']:.0f}%）"
        )
    if rec.s3_iv_completeness_pct is not None and rec.s3_iv_completeness_pct < S3_IV_MIN_PCT:
        lines.append(f"IV 完整度 {rec.s3_iv_completeness_pct:.1f}% 低于 {S3_IV_MIN_PCT:.0f}% 门槛")
    if rec.s4_eod_present < rec.s4_eod_total:
        lines.append(f"收盘数据仅 {rec.s4_eod_present}/{rec.s4_eod_total} 个标的齐全")
    return "\n".join(lines)


# ── Output ─────────────────────────────────────────────────────────────────────

def _append_record(rec: SanityRecord) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), default=str) + "\n")


# ── Core evaluation ────────────────────────────────────────────────────────────

def evaluate_day(day: date, *, force: bool, log: logging.Logger) -> SanityRecord:
    if not force and not _is_trading_day(day):
        rec = SanityRecord(
            date=day.isoformat(),
            s1_present=0, s1_total=N_WHITELIST, s1_missing=[],
            s2_anomaly_count=0, s2_anomalies=[],
            s3_iv_completeness_pct=None,
            s4_eod_present=0, s4_eod_total=N_WHITELIST,
            alert_fired=False,
            notes="skipped:non_trading_day",
        )
        return rec

    # S1 — symbol completeness
    present = _available_symbols(day)
    expected = {_safe_filename(sym) for sym in WHITELIST}
    raw_missing = sorted(sym for sym in WHITELIST if _safe_filename(sym) not in present)
    s1_present = len(expected & present)
    log.info("S1: %d/%d symbols present; missing=%s", s1_present, N_WHITELIST, raw_missing or "none")

    # S2 — row count anomaly
    s2_anomalies: list[dict] = []
    for sym in WHITELIST:
        rows = _symbol_row_count(sym, day)
        if rows is None:
            continue
        med = _rolling_median_rows(sym, day)
        if med is None or med == 0:
            continue
        pct = rows / med
        if pct < S2_LOW_FACTOR or pct > S2_HIGH_FACTOR:
            s2_anomalies.append({
                "symbol": sym, "rows": rows,
                "median": med, "pct_of_median": pct * 100.0,
            })
    log.info("S2: %d row anomalies", len(s2_anomalies))

    # S3 — IV completeness
    s3_pct = _check_s3_iv(day)
    log.info("S3: IV completeness = %s%%", s3_pct)

    # S4 — EOD underlying presence
    s4_present = _check_s4_eod(day)
    log.info("S4: EOD underlying %d/%d", s4_present, N_WHITELIST)

    alert = bool(
        raw_missing
        or s2_anomalies
        or (s3_pct is not None and s3_pct < S3_IV_MIN_PCT)
        or s4_present < N_WHITELIST
    )

    rec = SanityRecord(
        date=day.isoformat(),
        s1_present=s1_present,
        s1_total=N_WHITELIST,
        s1_missing=raw_missing,
        s2_anomaly_count=len(s2_anomalies),
        s2_anomalies=s2_anomalies,
        s3_iv_completeness_pct=s3_pct,
        s4_eod_present=s4_present,
        s4_eod_total=N_WHITELIST,
        alert_fired=alert,
        notes="",
    )
    return rec


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "q041_chain_sanity.log"),
        ],
    )
    log = logging.getLogger("q041_chain_sanity")

    p = argparse.ArgumentParser(description="SPEC-114 Q041 chain sanity monitor")
    p.add_argument("--date", help="YYYY-MM-DD (default: today ET)")
    p.add_argument("--force", action="store_true", help="run on non-trading days")
    p.add_argument("--dry-run", action="store_true", help="skip Telegram + jsonl write")
    args = p.parse_args(argv)

    if args.date:
        day = date.fromisoformat(args.date)
    else:
        day = datetime.now(ET).date()

    log.info("Chain sanity: date=%s force=%s dry_run=%s", day, args.force, args.dry_run)
    rec = evaluate_day(day, force=args.force, log=log)

    if not args.dry_run:
        _append_record(rec)
        report_text = _build_report(rec)
        _send_telegram(report_text, log)
        if rec.alert_fired:
            alert_text = _build_alert(rec)
            _send_telegram(alert_text, log, category="ACTION")
            log.warning("Alert fired:\n%s", alert_text)
    else:
        log.info("[dry-run] report:\n%s", _build_report(rec))
        if rec.alert_fired:
            log.warning("[dry-run] alert:\n%s", _build_alert(rec))

    log.info(
        "Done: S1=%d/%d S2_anomaly=%d S3_iv=%s%% S4_eod=%d/%d alert=%s",
        rec.s1_present, rec.s1_total,
        rec.s2_anomaly_count,
        rec.s3_iv_completeness_pct,
        rec.s4_eod_present, rec.s4_eod_total,
        rec.alert_fired,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
