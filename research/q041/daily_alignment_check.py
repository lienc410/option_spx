"""Q041 daily dual-source alignment check.

Reads same-day Schwab chain parquet and Massive REST snapshot parquet, computes
three operational alignment checks, appends one JSONL record, sends a Telegram
daily report, and optionally sends threshold alerts.

This is a read-only monitoring job. It does not mutate strategy/runtime state.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
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
MASSIVE_ROOT = REPO_ROOT / "data" / "q041_massive_snapshot"
OUTPUT_PATH = REPO_ROOT / "data" / "q041_overlap_daily.jsonl"
ALERT_STATE_PATH = REPO_ROOT / "data" / "q041_overlap_alert_state.jsonl"
LOG_DIR = REPO_ROOT / "logs"

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
_ALL_HOLIDAYS = _US_HOLIDAYS_2025 | _US_HOLIDAYS_2026

load_dotenv(REPO_ROOT / ".env")


@dataclass
class AlignmentRecord:
    date: str
    m1_match_pct: float | None
    m4_deviation_pct: float | None
    m6_iv_completeness_pct: float | None
    alert_fired: bool
    notes: str


@dataclass
class AlignmentResult:
    record: AlignmentRecord
    report_text: str
    alert_texts: list[str]
    status: str


def _logger(verbose: bool) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("q041_alignment")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(LOG_DIR / "q041_alignment.log")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log


def _safe_filename(symbol: str) -> str:
    return symbol.lstrip("/").replace("/", "_")


def _is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in _ALL_HOLIDAYS


def _day_dir(root: Path, day: date) -> Path:
    return root / day.isoformat()


def _available_symbol_files(day_dir: Path) -> set[str]:
    if not day_dir.exists():
        return set()
    out: set[str] = set()
    for path in day_dir.glob("*.parquet"):
        if path.name.startswith("_"):
            continue
        out.add(path.stem)
    return out


def _load_day_frame(root: Path, day: date, columns: list[str], log: logging.Logger) -> pd.DataFrame:
    day_dir = _day_dir(root, day)
    if not day_dir.exists():
        log.info("missing day dir: %s", day_dir)
        return pd.DataFrame(columns=columns)

    rows: list[pd.DataFrame] = []
    for symbol in WHITELIST:
        path = day_dir / f"{_safe_filename(symbol)}.parquet"
        if not path.exists():
            continue
        try:
            rows.append(pd.read_parquet(path))
        except Exception:
            log.exception("failed to read parquet: %s", path)
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.concat(rows, ignore_index=True, sort=False)


def _normalize_schwab(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "expiry",
                "contract_type",
                "strike_price",
                "volume",
                "delta",
                "iv",
                "last",
            ]
        )
    out = df.copy()
    out["symbol"] = out["symbol"].astype(str)
    out["expiry"] = out["expiry"].astype(str)
    out["contract_type"] = out["option_type"].astype(str).str.lower()
    out["strike_price"] = pd.to_numeric(out["strike"], errors="coerce")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce")
    out["delta"] = pd.to_numeric(out["delta"], errors="coerce")
    out["iv"] = pd.to_numeric(out["iv"], errors="coerce")
    out["last"] = pd.to_numeric(out["last"], errors="coerce")
    return (
        out[
            [
                "symbol",
                "expiry",
                "contract_type",
                "strike_price",
                "volume",
                "delta",
                "iv",
                "last",
            ]
        ]
        .dropna(subset=["symbol", "expiry", "contract_type", "strike_price"])
        .drop_duplicates(subset=["symbol", "expiry", "contract_type", "strike_price"], keep="last")
        .reset_index(drop=True)
    )


def _normalize_massive(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "expiry",
                "contract_type",
                "strike_price",
                "day_close",
            ]
        )
    out = df.copy()
    out["symbol"] = out["symbol"].astype(str)
    out["expiry"] = out["expiration_date"].astype(str)
    out["contract_type"] = out["contract_type"].astype(str).str.lower()
    out["strike_price"] = pd.to_numeric(out["strike_price"], errors="coerce")
    out["day_close"] = pd.to_numeric(out["day_close"], errors="coerce")
    return (
        out[
            [
                "symbol",
                "expiry",
                "contract_type",
                "strike_price",
                "day_close",
            ]
        ]
        .dropna(subset=["symbol", "expiry", "contract_type", "strike_price"])
        .drop_duplicates(subset=["symbol", "expiry", "contract_type", "strike_price"], keep="last")
        .reset_index(drop=True)
    )


def _key_columns() -> list[str]:
    return ["symbol", "expiry", "contract_type", "strike_price"]


def _compute_m1(schwab: pd.DataFrame, massive: pd.DataFrame) -> tuple[float | None, int, int]:
    key_cols = _key_columns()
    schwab_traded = schwab[schwab["volume"].fillna(0) > 0][key_cols].drop_duplicates().reset_index(drop=True)
    if schwab_traded.empty:
        return None, 0, 0
    massive_keys = massive[key_cols].drop_duplicates().reset_index(drop=True)
    matched = schwab_traded.merge(massive_keys, on=key_cols, how="inner")
    return round(len(matched) / len(schwab_traded) * 100.0, 1), len(matched), len(schwab_traded)


def _compute_m4(schwab: pd.DataFrame, massive: pd.DataFrame) -> tuple[float | None, float | None, int]:
    key_cols = _key_columns()
    merged = schwab.merge(massive, on=key_cols, how="inner", suffixes=("_schwab", "_massive"))
    liquid = merged[
        merged["delta"].abs().between(0.10, 0.50, inclusive="both")
        & merged["day_close"].notna()
        & (merged["day_close"] > 1.0)
        & merged["last"].notna()
        & (merged["last"] > 0.0)
    ].copy()
    if liquid.empty:
        return None, None, 0
    liquid["deviation_pct"] = ((liquid["last"] - liquid["day_close"]).abs() / liquid["day_close"]) * 100.0
    over_2pct = float((liquid["deviation_pct"] > 2.0).mean() * 100.0)
    under_or_eq_2pct = float((liquid["deviation_pct"] <= 2.0).mean() * 100.0)
    return round(over_2pct, 1), round(under_or_eq_2pct, 1), len(liquid)


def _compute_m6(schwab: pd.DataFrame) -> tuple[float | None, int]:
    near_money = schwab[schwab["delta"].abs().between(0.25, 0.75, inclusive="both")].copy()
    if near_money.empty:
        return None, 0
    valid = near_money["iv"].notna() & (near_money["iv"] > 0.0)
    return round(float(valid.mean() * 100.0), 1), len(near_money)


def _build_notes(
    *,
    m1_matched: int,
    m1_total: int,
    m4_count: int,
    m6_count: int,
    missing: list[str] | None = None,
    skipped: str | None = None,
) -> str:
    if skipped:
        return skipped
    if missing:
        return "missing_data:" + ",".join(sorted(missing))
    return f"m1={m1_matched}/{m1_total};m4_n={m4_count};m6_n={m6_count}"


def _build_report_text(record: AlignmentRecord, m4_under_or_eq_2pct: float | None) -> str:
    if record.notes.startswith("missing_data:"):
        return f"⚪ Q041 数据对齐：今日无数据 {record.date}\n原因: {record.notes.removeprefix('missing_data:')}"
    if record.notes.startswith("skipped:"):
        return f"⏭️ Q041 数据对齐：非交易日跳过 {record.date}"
    m1_icon = "✅" if record.m1_match_pct is not None and record.m1_match_pct >= 95.0 else "⚠️"
    m4_icon = "✅" if record.m4_deviation_pct is not None and record.m4_deviation_pct <= 5.0 else "⚠️"
    m6_icon = "✅" if record.m6_iv_completeness_pct is not None and record.m6_iv_completeness_pct >= 95.0 else "⚠️"
    m4_tail = "n/a" if m4_under_or_eq_2pct is None else f"(<2% 占 {m4_under_or_eq_2pct:.1f}%)"
    return (
        f"📊 Q041 数据对齐日报 {record.date}\n"
        f"M1 key match:    {record.m1_match_pct:.1f}% {m1_icon}\n"
        f"M4 price dev:     {record.m4_deviation_pct:.1f}% {m4_icon}  {m4_tail}\n"
        f"M6 IV complete:  {record.m6_iv_completeness_pct:.1f}% {m6_icon}"
    )


def _breached_metrics(record: AlignmentRecord) -> list[str]:
    breaches: list[str] = []
    if record.m1_match_pct is not None and record.m1_match_pct < 95.0:
        breaches.append("M1")
    if record.m4_deviation_pct is not None and record.m4_deviation_pct > 5.0:
        breaches.append("M4")
    if record.m6_iv_completeness_pct is not None and record.m6_iv_completeness_pct < 95.0:
        breaches.append("M6")
    return breaches


def _load_alert_state() -> dict[str, set[str]]:
    if not ALERT_STATE_PATH.exists():
        return {}
    out: dict[str, set[str]] = {}
    with ALERT_STATE_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            when = str(payload.get("date") or "")
            metrics = payload.get("metrics") or []
            if when:
                out.setdefault(when, set()).update(str(metric) for metric in metrics)
    return out


def _append_alert_state(day: str, metrics: list[str]) -> None:
    ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ALERT_STATE_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"date": day, "metrics": metrics}, ensure_ascii=False) + "\n")


def _build_alert_texts(record: AlignmentRecord) -> list[str]:
    breaches = _breached_metrics(record)
    if not breaches:
        return []
    prior = _load_alert_state().get(record.date, set())
    fresh = [metric for metric in breaches if metric not in prior]
    if not fresh:
        return []
    lines = [f"🚨 Q041 数据对齐告警 {record.date}"]
    for metric in fresh:
        if metric == "M1":
            lines.append(f"M1 key match {record.m1_match_pct:.1f}% < 95.0%")
        elif metric == "M4":
            lines.append(f"M4 price dev {record.m4_deviation_pct:.1f}% > 5.0%")
        elif metric == "M6":
            lines.append(f"M6 IV complete {record.m6_iv_completeness_pct:.1f}% < 95.0%")
    _append_alert_state(record.date, fresh)
    return ["\n".join(lines)]


def _append_daily_record(record: AlignmentRecord) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def _send_telegram_message(text: str, log: logging.Logger, *, category: str = "FYI") -> bool:
    """SPEC-137: route through the unified gateway (category/about/dedupe +
    host guard in the transport). Was a legacy direct Telegram sender with no
    host guard at all. Daily report → ⚪ FYI (quiet); alignment alert → 🔴
    ALERT (rings)."""
    try:
        from notify.gateway import escape, push as gw_push
        return gw_push(category, "系统状态", "", escape(text))
    except Exception:
        log.exception("telegram send failed")
        return False


def evaluate_day(day: date, *, force: bool, log: logging.Logger) -> AlignmentResult:
    if not force and not _is_trading_day(day):
        record = AlignmentRecord(
            date=day.isoformat(),
            m1_match_pct=None,
            m4_deviation_pct=None,
            m6_iv_completeness_pct=None,
            alert_fired=False,
            notes=_build_notes(m1_matched=0, m1_total=0, m4_count=0, m6_count=0, skipped="skipped:non_trading_day"),
        )
        return AlignmentResult(
            record=record,
            report_text=_build_report_text(record, None),
            alert_texts=[],
            status="skipped",
        )

    schwab_dir = _day_dir(SCHWAB_ROOT, day)
    massive_dir = _day_dir(MASSIVE_ROOT, day)
    schwab_files = _available_symbol_files(schwab_dir)
    massive_files = _available_symbol_files(massive_dir)
    missing: list[str] = []
    if not schwab_files:
        missing.append("schwab")
    if not massive_files:
        missing.append("massive")
    if missing:
        record = AlignmentRecord(
            date=day.isoformat(),
            m1_match_pct=None,
            m4_deviation_pct=None,
            m6_iv_completeness_pct=None,
            alert_fired=False,
            notes=_build_notes(m1_matched=0, m1_total=0, m4_count=0, m6_count=0, missing=missing),
        )
        return AlignmentResult(
            record=record,
            report_text=_build_report_text(record, None),
            alert_texts=[],
            status="missing_data",
        )

    schwab = _normalize_schwab(
        _load_day_frame(
            SCHWAB_ROOT,
            day,
            ["symbol", "expiry", "option_type", "strike", "volume", "delta", "iv", "last"],
            log,
        )
    )
    massive = _normalize_massive(
        _load_day_frame(
            MASSIVE_ROOT,
            day,
            ["symbol", "expiration_date", "contract_type", "strike_price", "day_close"],
            log,
        )
    )

    if schwab.empty or massive.empty:
        missing = []
        if schwab.empty:
            missing.append("schwab")
        if massive.empty:
            missing.append("massive")
        record = AlignmentRecord(
            date=day.isoformat(),
            m1_match_pct=None,
            m4_deviation_pct=None,
            m6_iv_completeness_pct=None,
            alert_fired=False,
            notes=_build_notes(m1_matched=0, m1_total=0, m4_count=0, m6_count=0, missing=missing),
        )
        return AlignmentResult(
            record=record,
            report_text=_build_report_text(record, None),
            alert_texts=[],
            status="missing_data",
        )

    m1_pct, m1_matched, m1_total = _compute_m1(schwab, massive)
    m4_pct, m4_under_or_eq_2pct, m4_count = _compute_m4(schwab, massive)
    m6_pct, m6_count = _compute_m6(schwab)
    record = AlignmentRecord(
        date=day.isoformat(),
        m1_match_pct=m1_pct,
        m4_deviation_pct=m4_pct,
        m6_iv_completeness_pct=m6_pct,
        alert_fired=False,
        notes=_build_notes(
            m1_matched=m1_matched,
            m1_total=m1_total,
            m4_count=m4_count,
            m6_count=m6_count,
        ),
    )
    alert_texts = _build_alert_texts(record)
    record.alert_fired = bool(alert_texts)
    return AlignmentResult(
        record=record,
        report_text=_build_report_text(record, m4_under_or_eq_2pct),
        alert_texts=alert_texts,
        status="ok",
    )


def run(*, day: date | None = None, force: bool = False, send_telegram: bool = True, verbose: bool = False) -> int:
    log = _logger(verbose)
    target_day = day or datetime.now(ET).date()
    try:
        result = evaluate_day(target_day, force=force, log=log)
        _append_daily_record(result.record)
        if send_telegram:
            _send_telegram_message(result.report_text, log)
            for alert_text in result.alert_texts:
                _send_telegram_message(alert_text, log, category="ALERT")
        log.info("q041 alignment status=%s date=%s record=%s", result.status, target_day.isoformat(), asdict(result.record))
        return 0
    except Exception:
        log.exception("q041 alignment check failed")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q041 daily dual-source alignment check")
    parser.add_argument("--date", help="ET trading date, YYYY-MM-DD")
    parser.add_argument("--force", action="store_true", help="Run even on non-trading day")
    parser.add_argument("--skip-telegram", action="store_true", help="Do not send Telegram messages")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    target_day = date.fromisoformat(args.date) if args.date else None
    return run(day=target_day, force=args.force, send_telegram=not args.skip_telegram, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
