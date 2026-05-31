"""SPEC-110 T1 — E*Trade monthly NLV statement importer.

CLI:
  venv/bin/python scripts/etrade_import_monthly_statements.py \\
      --input ~/Downloads/etrade_monthly.csv [--format csv|json|tab] \\
      [--dry-run] [--overwrite]

CSV format (header required):
  month_end_date,nlv,cash,maint_margin,bp,notes
  2024-06-28,452000.00,8500.00,28000.00,890000.00,

JSON format:
  [{"month_end_date": "2024-06-28", "nlv": 452000.00, ...}, ...]

Idempotency: unique key = month_end_date.
  - Without --overwrite: duplicate month_end_date → skip + log.
  - With --overwrite: replace existing row for that date.
  - Re-running same import produces no change (idempotent).
Priority: manual_import rows are never overwritten by T2 aggregator.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
MONTHLY_NLV_PATH = DATA_DIR / "etrade_monthly_nlv.jsonl"


# ── helpers ────────────────────────────────────────────────────────────────────

def _num(v: Any) -> float | None:
    try:
        if v in (None, "", "null", "NULL", "N/A"):
            return None
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _validate_date(s: str) -> str:
    """Validate ISO date string YYYY-MM-DD; raise ValueError if invalid."""
    try:
        from datetime import date as _d
        _d.fromisoformat(str(s).strip()[:10])
        return str(s).strip()[:10]
    except (ValueError, TypeError):
        raise ValueError(f"Invalid date: {s!r} — expected YYYY-MM-DD")


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── data store ─────────────────────────────────────────────────────────────────

def load_existing(path: Path = MONTHLY_NLV_PATH) -> dict[str, dict]:
    """Load all monthly NLV records keyed by month_end_date."""
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


def save_all(records: dict[str, dict], path: Path = MONTHLY_NLV_PATH) -> None:
    """Write all records to jsonl, sorted ascending by month_end_date."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(records.values(), key=lambda r: r.get("month_end_date", ""))
    with path.open("w", encoding="utf-8") as f:
        for row in sorted_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


# ── parsers ────────────────────────────────────────────────────────────────────

def _build_record(
    month_end_date: str,
    nlv: float,
    *,
    cash: float | None = None,
    maintenance_margin: float | None = None,
    total_buying_power: float | None = None,
    notes: str | None = None,
    source_file: str | None = None,
) -> dict:
    return {
        "month_end_date": month_end_date,
        "account": "etrade",
        "nlv": round(nlv, 2),
        "cash": round(cash, 2) if cash is not None else None,
        "maintenance_margin": round(maintenance_margin, 2) if maintenance_margin is not None else None,
        "total_buying_power": round(total_buying_power, 2) if total_buying_power is not None else None,
        "source": "manual_import",
        "source_file": source_file,
        "imported_at": _now_utc(),
        "month_pnl": None,
        "month_cash_flow": None,
        "notes": notes or None,
    }


def parse_csv(path: Path, *, delimiter: str = ",") -> list[dict]:
    """Parse CSV/tab-separated monthly statement file."""
    rows: list[dict] = []
    errors: list[str] = []
    fname = path.name

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        fields = [str(h).strip().lower() for h in reader.fieldnames]
        if "month_end_date" not in fields:
            raise ValueError(f"CSV missing required column 'month_end_date' (found: {reader.fieldnames})")
        if "nlv" not in fields:
            raise ValueError(f"CSV missing required column 'nlv' (found: {reader.fieldnames})")

        for i, row in enumerate(reader, start=2):
            norm = {str(k).strip().lower(): str(v).strip() for k, v in row.items()}
            try:
                date_val = _validate_date(norm["month_end_date"])
                nlv_val = _num(norm["nlv"])
                if nlv_val is None:
                    raise ValueError(f"row {i}: nlv is required and must be numeric")
                rows.append(_build_record(
                    date_val, nlv_val,
                    cash=_num(norm.get("cash")),
                    maintenance_margin=_num(norm.get("maint_margin") or norm.get("maintenance_margin")),
                    total_buying_power=_num(norm.get("bp") or norm.get("total_buying_power")),
                    notes=norm.get("notes") or None,
                    source_file=fname,
                ))
            except ValueError as exc:
                errors.append(str(exc))

    if errors:
        raise ValueError("CSV parse errors:\n" + "\n".join(f"  {e}" for e in errors))
    return rows


def parse_json(path: Path) -> list[dict]:
    """Parse JSON list-of-objects monthly statement file."""
    fname = path.name
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("JSON input must be a list of objects")
    rows: list[dict] = []
    errors: list[str] = []
    for i, obj in enumerate(raw):
        if not isinstance(obj, dict):
            errors.append(f"item {i}: not an object")
            continue
        norm = {str(k).strip().lower(): v for k, v in obj.items()}
        try:
            date_val = _validate_date(str(norm.get("month_end_date") or ""))
            nlv_raw = norm.get("nlv")
            nlv_val = _num(nlv_raw)
            if nlv_val is None:
                raise ValueError(f"item {i}: nlv is required")
            rows.append(_build_record(
                date_val, nlv_val,
                cash=_num(norm.get("cash")),
                maintenance_margin=_num(norm.get("maint_margin") or norm.get("maintenance_margin")),
                total_buying_power=_num(norm.get("bp") or norm.get("total_buying_power")),
                notes=str(norm.get("notes") or "") or None,
                source_file=fname,
            ))
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("JSON parse errors:\n" + "\n".join(f"  {e}" for e in errors))
    return rows


# ── main import logic ──────────────────────────────────────────────────────────

def run_import(
    input_path: Path,
    *,
    fmt: str = "csv",
    dry_run: bool = False,
    overwrite: bool = False,
    output_path: Path = MONTHLY_NLV_PATH,
) -> dict:
    """Parse input file and import into monthly NLV store.

    Returns summary dict: {parsed, imported, skipped, overwritten, errors}.
    On error: raises ValueError (no partial write).
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Parse
    if fmt == "json":
        parsed_rows = parse_json(input_path)
    elif fmt == "tab":
        parsed_rows = parse_csv(input_path, delimiter="\t")
    else:
        parsed_rows = parse_csv(input_path, delimiter=",")

    # Load existing
    existing = load_existing(output_path)

    n_imported = 0
    n_skipped = 0
    n_overwritten = 0
    merged = dict(existing)

    for row in parsed_rows:
        key = row["month_end_date"]
        if key in existing:
            if overwrite:
                merged[key] = row
                n_overwritten += 1
            else:
                n_skipped += 1
        else:
            merged[key] = row
            n_imported += 1

    if not dry_run:
        save_all(merged, output_path)

    return {
        "parsed": len(parsed_rows),
        "imported": n_imported,
        "skipped": n_skipped,
        "overwritten": n_overwritten,
        "dry_run": dry_run,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SPEC-110 T1 — Import E*Trade monthly NLV from CSV/JSON statement"
    )
    parser.add_argument("--input", required=True, help="Path to CSV or JSON input file")
    parser.add_argument("--format", choices=["csv", "json", "tab"], default="csv",
                        help="Input format (default: csv)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and validate without writing to data store")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing rows for matching month_end_date")
    parser.add_argument("--output", default=str(MONTHLY_NLV_PATH),
                        help="Path to output jsonl (default: data/etrade_monthly_nlv.jsonl)")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()

    try:
        result = run_import(
            input_path,
            fmt=args.format,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            output_path=output_path,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    dr = " [DRY RUN]" if result["dry_run"] else ""
    print(
        f"SPEC-110 T1 import{dr}:\n"
        f"  Parsed:      {result['parsed']}\n"
        f"  Imported:    {result['imported']}\n"
        f"  Skipped:     {result['skipped']}\n"
        f"  Overwritten: {result['overwritten']}\n"
        f"  Output:      {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
