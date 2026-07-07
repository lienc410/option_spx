"""SPEC-115 Phase A — Q041 T2 paper signal daily job.

Runs once per trading day (16:50 ET via launchd, after q041_chain_sanity 16:45).
For each T2 candidate strategy:
  1. select_t2_csp(strategy_key, today)
  2. evaluate_candidate(candidate)  # SPEC-111/115 cash gate via sleeve_governance
  3. append event to data/q041_paper_log.jsonl
  4. push one Telegram daily message covering both candidates

PM-ratified expectation: most days emit `blocked` events (GOOGL $36.6k / AMZN
$25.2k cash need > $22.2k SPEC-111 cap). 0 fire in observation week = success.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy.q041_selector import select_t2_csp  # noqa: E402
from strategy.sleeve_governance import evaluate_candidate  # noqa: E402
from notify.gateway import push as _gw_push  # noqa: E402


def _telegram_send(msg: str) -> bool:
    return _gw_push("FYI", "系统状态", "", msg)

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

log = logging.getLogger("q041_paper_telegram")

ET = ZoneInfo("America/New_York")
PAPER_LOG = REPO_ROOT / "data" / "q041_paper_log.jsonl"
T2_STRATEGIES = ["q041_t2_googl_csp", "q041_t2_amzn_csp"]

_US_HOLIDAYS: frozenset[str] = frozenset({
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26",
    "2027-05-31", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
})


def _is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in _US_HOLIDAYS


def _decision_summary(decision) -> dict:
    """Compact, JSON-serializable view of a GovernanceDecision (drop the big state blob)."""
    return {
        "accepted": bool(getattr(decision, "accepted", False)),
        "rule": getattr(decision, "rule", None),
        "reason": getattr(decision, "reason", None),
        "requested_bp_dollars": getattr(decision, "requested_bp_dollars", None),
        "requested_bp_pct": getattr(decision, "requested_bp_pct", None),
    }


def _emit_log(event_type: str, strategy_key: str, candidate: dict, decision: dict, asof_date: str) -> None:
    PAPER_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "event": event_type,
        "strategy_key": strategy_key,
        "asof_date": asof_date,
        "candidate": candidate,
        "governance_decision": decision,
    }
    with PAPER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def _format_telegram(date_str: str, results: list[dict]) -> str:
    lines = [f"📋 Q041 T2 Paper Signal {date_str}"]
    for r in results:
        sym = r["underlying"]
        c = r["candidate"]
        if c is None:
            lines.append(f"\n{sym} CSP: no chain candidate (Δ/DTE/close out of band or chain missing)")
            continue
        lines.append(
            f"\n{sym} CSP Δ{c['delta']:.2f} DTE{c['dte']}:\n"
            f"  K=${c['short_strike']:.0f}  close=${c['close']:.2f}  cash_need=${c['cash_need_usd']:,.0f}"
        )
        d = r["decision"]
        if d and d.get("accepted"):
            lines.append("  Decision: ✅ PAPER OPEN")
        else:
            reason = (d or {}).get("reason", "unknown")
            lines.append(f"  Decision: ❌ blocked — {reason}")
    return "\n".join(lines)


def run(asof: str, *, force: bool, dry_run: bool) -> list[dict]:
    day = date.fromisoformat(asof)
    if not force and not _is_trading_day(day):
        log.info("non-trading day %s — skipping", asof)
        return []

    results: list[dict] = []
    for sk in T2_STRATEGIES:
        underlying = "GOOGL" if "googl" in sk else "AMZN"
        candidate = select_t2_csp(sk, asof)
        if candidate is None:
            results.append({"underlying": underlying, "candidate": None, "decision": None})
            continue
        decision = evaluate_candidate(candidate)
        decision_dict = _decision_summary(decision)
        event = "open" if decision_dict["accepted"] else "blocked"
        if not dry_run:
            _emit_log(event, sk, candidate, decision_dict, asof)
        results.append({
            "underlying": candidate["underlying"],
            "candidate": candidate,
            "decision": decision_dict,
        })
    return results


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    p = argparse.ArgumentParser(description="SPEC-115 Q041 T2 paper signal daily job")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today ET)")
    p.add_argument("--force", action="store_true", help="run on non-trading days")
    p.add_argument("--dry-run", action="store_true", help="print but do not log/push")
    args = p.parse_args(argv)

    asof = args.date or datetime.now(ET).date().isoformat()
    results = run(asof, force=args.force, dry_run=args.dry_run)

    if not results:
        log.info("no results (non-trading day)")
        return 0

    msg = _format_telegram(asof, results)
    if args.dry_run:
        print(msg)
    else:
        _telegram_send(msg)
        log.info("pushed daily T2 paper signal for %s", asof)

    return 0


if __name__ == "__main__":
    sys.exit(main())
