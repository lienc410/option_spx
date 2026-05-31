"""SPEC-110 T3 — E*Trade monthly NLV audit via transaction cross-check.

Compares month-over-month NLV delta from manual_import entries against
transaction-derived net_change from PyEtrade list_transactions.
Flags discrepancies > $1,000 as audit_warning.

Usage:
  venv/bin/python scripts/etrade_audit_monthly.py [--months N] [--output report.json]

This is AUDIT ONLY — not a source-of-truth. Never overwrites manual_import rows.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
MONTHLY_NLV_PATH = DATA_DIR / "etrade_monthly_nlv.jsonl"
AUDIT_THRESHOLD = 1000.0  # $1k


def load_monthly(path: Path = MONTHLY_NLV_PATH) -> list[dict]:
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
    return sorted(rows, key=lambda r: r.get("month_end_date", ""))


def run_audit(months: int = 24, output_path: Path | None = None) -> dict:
    """Cross-check manual_import NLV deltas vs transaction-derived net_change.

    Returns audit report with discrepancies flagged.
    """
    rows = load_monthly()
    if not rows:
        return {"records": 0, "audit_warnings": [], "note": "no_monthly_data"}

    # Only audit manual_import rows (those have statement-quality NLV)
    manual_rows = [r for r in rows if r.get("source") in ("manual_import", "daily_snapshot_eom")]
    if len(manual_rows) < 2:
        return {"records": len(manual_rows), "audit_warnings": [], "note": "insufficient_data_for_delta"}

    # Determine date range for transaction fetch
    today = date.today()
    lookback = date(max(today.year - (months // 12 + 1), today.year - 2), 1, 1)
    start_date = lookback.isoformat()
    end_date = today.isoformat()

    # Fetch transaction-derived monthly P&L
    transaction_data: dict[str, dict] = {}
    try:
        from etrade.client import derive_monthly_pnl_from_transactions
        transaction_data = derive_monthly_pnl_from_transactions(start_date, end_date)
    except Exception as exc:
        print(f"[audit] Transaction fetch failed: {exc}", file=sys.stderr)

    # Compute month-over-month NLV delta from manual rows
    warnings: list[dict] = []
    for i in range(1, len(manual_rows)):
        prev = manual_rows[i - 1]
        curr = manual_rows[i]
        try:
            prev_nlv = float(prev["nlv"])
            curr_nlv = float(curr["nlv"])
        except (TypeError, ValueError, KeyError):
            continue

        nlv_delta = curr_nlv - prev_nlv
        curr_ym = str(curr.get("month_end_date") or "")[:7]
        tx_month = transaction_data.get(curr_ym) or {}
        tx_net = float(tx_month.get("net_change") or 0.0)

        if tx_net == 0.0 and not transaction_data:
            # No transaction data available; skip comparison
            continue

        discrepancy = abs(nlv_delta - tx_net)
        if discrepancy > AUDIT_THRESHOLD:
            warnings.append({
                "month": curr_ym,
                "month_end_date": curr.get("month_end_date"),
                "nlv_delta": round(nlv_delta, 2),
                "transaction_net_change": round(tx_net, 2),
                "discrepancy": round(discrepancy, 2),
                "source": curr.get("source"),
                "note": f"NLV delta ${nlv_delta:,.0f} vs tx-derived ${tx_net:,.0f} — diff ${discrepancy:,.0f}",
            })

    report = {
        "records": len(manual_rows),
        "months_audited": len(manual_rows) - 1,
        "audit_warnings": warnings,
        "warning_count": len(warnings),
        "threshold": AUDIT_THRESHOLD,
        "transaction_months_available": len(transaction_data),
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SPEC-110 T3 — Audit E*Trade monthly NLV vs transaction-derived net change"
    )
    parser.add_argument("--months", type=int, default=24,
                        help="Lookback months for transactions (default 24)")
    parser.add_argument("--output", help="Write JSON report to this path")
    args = parser.parse_args(argv)

    output_path = Path(args.output) if args.output else None
    report = run_audit(months=args.months, output_path=output_path)

    print(
        f"SPEC-110 T3 audit:\n"
        f"  Records:            {report['records']}\n"
        f"  Months audited:     {report.get('months_audited', 0)}\n"
        f"  Audit warnings:     {report['warning_count']}\n"
        f"  TX months avail:    {report.get('transaction_months_available', 0)}\n"
        + (f"  Note: {report.get('note')}\n" if report.get("note") else "")
    )
    if report["audit_warnings"]:
        print("\nWARNINGS:")
        for w in report["audit_warnings"]:
            print(f"  {w['month']}: {w['note']}")
    if output_path:
        print(f"\n  Report written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
