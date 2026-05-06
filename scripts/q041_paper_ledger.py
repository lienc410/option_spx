from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from logs.q041_paper_trade_io import (
    budget_status,
    close_trade,
    create_trade,
    export_csp_review,
    export_ic_review,
    status_snapshot,
    update_trade,
)


def _parse_flags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Q041 paper trade ledger CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    csp = sub.add_parser("add-csp")
    csp.add_argument("--symbol", required=True)
    csp.add_argument("--tier", required=True)
    csp.add_argument("--entry-date", required=True)
    csp.add_argument("--expiry", required=True)
    csp.add_argument("--act-dte", required=True, type=int)
    csp.add_argument("--s-entry", required=True, type=float)
    csp.add_argument("--iv-entry", required=True, type=float)
    csp.add_argument("--vix-entry", required=True, type=float)
    csp.add_argument("--net-prem", required=True, type=float)
    csp.add_argument("--bp-reserved", required=True, type=float)
    csp.add_argument("--contracts", default=1, type=int)
    csp.add_argument("--strike", required=True, type=float)
    csp.add_argument("--pct-otm", required=True, type=float)
    csp.add_argument("--delta-actual", required=True, type=float)
    csp.add_argument("--flags")
    csp.add_argument("--notes", default="")

    ic = sub.add_parser("add-ic")
    ic.add_argument("--symbol", required=True)
    ic.add_argument("--tier", required=True)
    ic.add_argument("--entry-date", required=True)
    ic.add_argument("--expiry", required=True)
    ic.add_argument("--act-dte", required=True, type=int)
    ic.add_argument("--s-entry", required=True, type=float)
    ic.add_argument("--iv-entry", required=True, type=float)
    ic.add_argument("--vix-entry", required=True, type=float)
    ic.add_argument("--net-prem", required=True, type=float)
    ic.add_argument("--bp-reserved", required=True, type=float)
    ic.add_argument("--contracts", default=1, type=int)
    ic.add_argument("--k-put-short", required=True, type=float)
    ic.add_argument("--k-put-long", required=True, type=float)
    ic.add_argument("--k-call-short", required=True, type=float)
    ic.add_argument("--k-call-long", required=True, type=float)
    ic.add_argument("--event-name", required=True)
    ic.add_argument("--earnings-date", required=True)
    ic.add_argument("--implied-move-pct", required=True, type=float)
    ic.add_argument("--vix-gate-passed", required=True)
    ic.add_argument("--flags")
    ic.add_argument("--notes", default="")

    close = sub.add_parser("close")
    close.add_argument("--record-id", required=True)
    close.add_argument("--s-exit", required=True, type=float)
    close.add_argument("--pnl", required=True, type=float)
    close.add_argument("--hit", required=True)
    close.add_argument("--close-date")
    close.add_argument("--settle-cost", type=float)
    close.add_argument("--status", choices=["closed", "expired"], default="closed")

    update = sub.add_parser("update")
    update.add_argument("--record-id", required=True)
    update.add_argument("--notes")
    update.add_argument("--flags")

    budget = sub.add_parser("budget")

    export_csp = sub.add_parser("export-csp")
    export_csp.add_argument("--month", required=True)

    export_ic = sub.add_parser("export-ic")
    export_ic.add_argument("--symbol", required=True)
    export_ic.add_argument("--year", required=True, type=int)

    status = sub.add_parser("status")
    status.add_argument("--today")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.cmd == "add-csp":
            record = create_trade({
                "tier": args.tier,
                "strategy_type": "csp",
                "symbol": args.symbol,
                "entry_date": args.entry_date,
                "expiry": args.expiry,
                "act_dte": args.act_dte,
                "S_entry": args.s_entry,
                "iv_entry": args.iv_entry,
                "vix_entry": args.vix_entry,
                "net_prem": args.net_prem,
                "bp_reserved": args.bp_reserved,
                "contracts": args.contracts,
                "flags": _parse_flags(args.flags),
                "notes": args.notes,
                "strike": args.strike,
                "pct_otm": args.pct_otm,
                "delta_actual": args.delta_actual,
            })
            _print_json(record)
            return 0

        if args.cmd == "add-ic":
            record = create_trade({
                "tier": args.tier,
                "strategy_type": "earnings_ic",
                "symbol": args.symbol,
                "entry_date": args.entry_date,
                "expiry": args.expiry,
                "act_dte": args.act_dte,
                "S_entry": args.s_entry,
                "iv_entry": args.iv_entry,
                "vix_entry": args.vix_entry,
                "net_prem": args.net_prem,
                "bp_reserved": args.bp_reserved,
                "contracts": args.contracts,
                "flags": _parse_flags(args.flags),
                "notes": args.notes,
                "k_put_short": args.k_put_short,
                "k_put_long": args.k_put_long,
                "k_call_short": args.k_call_short,
                "k_call_long": args.k_call_long,
                "event_name": args.event_name,
                "earnings_date": args.earnings_date,
                "implied_move_pct": args.implied_move_pct,
                "vix_gate_passed": args.vix_gate_passed,
            })
            _print_json(record)
            return 0

        if args.cmd == "close":
            record = close_trade(
                args.record_id,
                s_exit=args.s_exit,
                pnl=args.pnl,
                hit=args.hit,
                close_date=args.close_date,
                settle_cost=args.settle_cost,
                status=args.status,
            )
            _print_json(record)
            return 0

        if args.cmd == "update":
            record = update_trade(args.record_id, notes=args.notes, flags=_parse_flags(args.flags) if args.flags is not None else None)
            _print_json(record)
            return 0

        if args.cmd == "budget":
            _print_json(budget_status())
            return 0

        if args.cmd == "export-csp":
            path = export_csp_review(args.month)
            print(path)
            return 0

        if args.cmd == "export-ic":
            path = export_ic_review(args.symbol, args.year)
            print(path)
            return 0

        if args.cmd == "status":
            snapshot = status_snapshot(today=args.today)
            print("Q041 Paper Trade Status")
            print("=======================")
            print("Open Positions")
            for row in snapshot["current_paper_positions"]:
                print(
                    f"- {row['record_id']} {row['symbol']} {row['tier']} {row['strategy_type']} "
                    f"entry={row['entry_date']} expiry={row['expiry']} bp={row['bp_reserved']} net_prem={row['net_prem']} "
                    f"flags={','.join(row.get('flags') or []) or '-'}"
                )
            if not snapshot["current_paper_positions"]:
                print("- none")

            print("\nRecent Entries")
            for row in snapshot["recent_entries"]:
                print(f"- {row['record_id']} {row['entry_date']} {row['symbol']} {row['tier']} {row['status']}")

            usage = snapshot["bp_usage"]
            print(
                f"\nBP Usage: tier1={usage['tier1_bp_pct']:.1f}% "
                f"tier2={usage['tier2_bp_pct']:.1f}% tier3={usage['tier3_bp_pct']:.1f}% "
                f"total={usage['total_q041_bp_pct']:.1f}% within_limits={usage['within_limits']}"
            )
            if usage["violations"]:
                for violation in usage["violations"]:
                    print(f"  violation: {violation}")

            print("\nNext Review Item")
            csp = snapshot["next_review_items"]["csp"]
            ic = snapshot["next_review_items"]["earnings_ic"]
            print(f"- csp: {csp['record_id'] if csp else 'none'}")
            print(f"- earnings_ic: {ic['record_id'] if ic else 'none'}")
            return 0

    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
