"""SPEC-110 T2 — Monthly E*Trade NLV aggregator from daily_snapshot.jsonl.

Reads data/daily_snapshot.jsonl, picks the last trading day per calendar month,
promotes it to data/etrade_monthly_nlv.jsonl with source="daily_snapshot_eom".

Rules:
  - Skips months already covered by a manual_import row (manual wins).
  - Skips months where daily snapshot has etrade.nlv = null (partial run / no auth).
  - Idempotent: re-running on same dataset produces same result.
  - Cron: run on 1st of each month at 06:00 ET → covers prior month's last trading day.

Usage:
  venv/bin/python scripts/etrade_monthly_aggregator.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DAILY_SNAPSHOT_PATH = DATA_DIR / "daily_snapshot.jsonl"
MONTHLY_NLV_PATH = DATA_DIR / "etrade_monthly_nlv.jsonl"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _year_month(date_str: str) -> str:
    """Extract YYYY-MM from YYYY-MM-DD."""
    return str(date_str)[:7]


def load_daily_snapshots(path: Path = DAILY_SNAPSHOT_PATH) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_existing_monthly(path: Path = MONTHLY_NLV_PATH) -> dict[str, dict]:
    """Load monthly records keyed by month_end_date."""
    records: dict[str, dict] = {}
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            key = r.get("month_end_date")
            if key:
                records[key] = r
        except json.JSONDecodeError:
            continue
    return records


def save_all_monthly(records: dict[str, dict], path: Path = MONTHLY_NLV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(records.values(), key=lambda r: r.get("month_end_date", ""))
    with path.open("w", encoding="utf-8") as f:
        for row in sorted_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def pick_month_end_candidates(snapshots: list[dict]) -> dict[str, dict]:
    """For each year-month, pick the last date's snapshot (latest = last trading day of month)."""
    by_month: dict[str, dict] = {}
    for snap in snapshots:
        date_str = str(snap.get("date") or "")
        if len(date_str) < 10:
            continue
        ym = _year_month(date_str)
        existing = by_month.get(ym)
        if existing is None or date_str > str(existing.get("date") or ""):
            by_month[ym] = snap
    return by_month


def build_monthly_record(snap: dict) -> dict | None:
    """Build a monthly NLV record from a daily snapshot row."""
    date_str = str(snap.get("date") or "")
    accounts = snap.get("accounts") or {}
    etrade = accounts.get("etrade") or {}
    nlv = etrade.get("nlv")
    maint = etrade.get("maint")

    if nlv is None:
        return None  # etrade data unavailable this day (partial snapshot)
    try:
        nlv = float(nlv)
    except (TypeError, ValueError):
        return None

    return {
        "month_end_date": date_str,
        "account": "etrade",
        "nlv": round(nlv, 2),
        "cash": None,
        "maintenance_margin": round(float(maint), 2) if maint is not None else None,
        "total_buying_power": None,
        "source": "daily_snapshot_eom",
        "source_file": None,
        "imported_at": _now_utc(),
        "month_pnl": None,
        "month_cash_flow": None,
        "notes": None,
    }


def run_aggregator(
    *,
    dry_run: bool = False,
    daily_path: Path = DAILY_SNAPSHOT_PATH,
    monthly_path: Path = MONTHLY_NLV_PATH,
) -> dict:
    """Promote month-end daily snapshots → monthly NLV store.

    Returns summary: {processed, promoted, skipped_manual, skipped_no_etrade, dry_run}.
    """
    snapshots = load_daily_snapshots(daily_path)
    if not snapshots:
        return {"processed": 0, "promoted": 0, "skipped_manual": 0,
                "skipped_no_etrade": 0, "dry_run": dry_run, "note": "no_daily_snapshots"}

    existing = load_existing_monthly(monthly_path)
    manual_months = {
        _year_month(k)
        for k, v in existing.items()
        if v.get("source") == "manual_import"
    }

    candidates = pick_month_end_candidates(snapshots)
    merged = dict(existing)

    n_promoted = 0
    n_skipped_manual = 0
    n_skipped_no_etrade = 0

    # Only promote complete months (not the current in-progress month)
    from datetime import date as _date
    current_ym = _year_month(_date.today().isoformat())

    for ym, snap in sorted(candidates.items()):
        if ym >= current_ym:
            continue  # skip current month — not complete yet

        # Manual import wins
        if ym in manual_months:
            n_skipped_manual += 1
            continue

        record = build_monthly_record(snap)
        if record is None:
            n_skipped_no_etrade += 1
            continue

        month_end_date = record["month_end_date"]
        # Only add if not already a daily_snapshot_eom for this month
        existing_for_month = existing.get(month_end_date)
        if existing_for_month and existing_for_month.get("source") == "daily_snapshot_eom":
            # Already recorded — check if same date, skip if yes
            if existing_for_month.get("month_end_date") == month_end_date:
                continue  # already recorded, skip (idempotent)

        merged[month_end_date] = record
        n_promoted += 1

    if not dry_run and n_promoted > 0:
        save_all_monthly(merged, monthly_path)

    return {
        "processed": len(candidates),
        "promoted": n_promoted,
        "skipped_manual": n_skipped_manual,
        "skipped_no_etrade": n_skipped_no_etrade,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SPEC-110 T2 — Aggregate daily snapshots → monthly E*Trade NLV"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute without writing")
    args = parser.parse_args(argv)

    result = run_aggregator(dry_run=args.dry_run)
    dr = " [DRY RUN]" if result["dry_run"] else ""
    print(
        f"SPEC-110 T2 aggregator{dr}:\n"
        f"  Months processed:     {result['processed']}\n"
        f"  Promoted (eom):       {result['promoted']}\n"
        f"  Skipped (manual win): {result['skipped_manual']}\n"
        f"  Skipped (no E*Trade): {result['skipped_no_etrade']}\n"
        + (f"  Note: {result.get('note')}\n" if result.get("note") else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
