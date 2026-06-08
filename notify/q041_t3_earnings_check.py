"""SPEC-115 Phase B — Q041 T3 earnings IC event-driven daily check.

Runs each trading day 16:55 ET (after Phase A T2 16:50). For each T3 symbol:
  - days_to == 3  → T-3 entry flow (build IC, governance, open/blocked event)
  - days_to == -1 → T+1 close flow (paper close using next-day spot, PnL)
  - else          → silent

Also refreshes the yfinance earnings calendar cache (folded into this job).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy.q041_earnings_calendar import T3_SYMBOLS, refresh_cache, load_cache  # noqa: E402
from strategy.q041_t3_selector import (  # noqa: E402
    select_t3_earnings_ic,
    compute_ic_close_pnl,
    VIX_GATE,
    CHAINS_ROOT,
    _safe_filename,
)
from strategy.sleeve_governance import evaluate_candidate  # noqa: E402
from notify.event_push import _send as _telegram_send  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

log = logging.getLogger("q041_t3_earnings_check")
ET = ZoneInfo("America/New_York")
PAPER_LOG = REPO_ROOT / "data" / "q041_paper_log.jsonl"
SK_BY_SYM = {"COST": "q041_t3_cost_earnings_ic", "JPM": "q041_t3_jpm_earnings_ic"}

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


def trading_days_until(target: date, today: date | None = None) -> int:
    """NYSE trading days from today (exclusive) to target (inclusive).

    Positive if target is in the future, negative if in the past, 0 if same day.
    """
    today = today or date.today()
    if target == today:
        return 0
    direction = 1 if target > today else -1
    count = 0
    d = today
    while d != target:
        d += timedelta(days=direction)
        if _is_trading_day(d):
            count += direction
    return count


def _get_current_vix() -> float | None:
    try:
        from signals.vix_regime import get_current_snapshot
        snap = get_current_snapshot()
        return float(snap.vix) if snap else None
    except Exception as exc:
        log.warning("VIX snapshot read failed: %s", exc)
        return None


def _read_spot(sym: str, date_str: str) -> float | None:
    und_path = CHAINS_ROOT / date_str / "_underlying.parquet"
    if not und_path.exists():
        return None
    try:
        import pandas as pd
        und = pd.read_parquet(und_path)
        row = und[und["symbol"] == sym]
        if row.empty:
            return None
        val = row.iloc[0].get("close") or row.iloc[0].get("last")
        return float(val) if val else None
    except Exception:
        return None


def _emit_log(event_type: str, strategy_key: str, candidate, decision, **extra) -> None:
    PAPER_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(ET).isoformat(timespec="seconds"),
        "event": event_type,
        "strategy_key": strategy_key,
        "candidate": candidate,
        "governance_decision": decision,
        **extra,
    }
    with PAPER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def _find_last_open(strategy_key: str) -> dict | None:
    """Most recent `open` event candidate for a strategy from paper_log."""
    if not PAPER_LOG.exists():
        return None
    last = None
    for line in PAPER_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("strategy_key") == strategy_key and rec.get("event") == "open":
            last = rec
    return last


# ── Telegram formatting ──────────────────────────────────────────────────────

def _format_t_minus_3(cand: dict, decision: dict) -> str:
    accepted = decision.get("accepted")
    decision_line = (
        "✅ PAPER OPEN" if accepted
        else "❌ blocked — " + str(decision.get("reason", "unknown"))
    )
    vix_ok = "✅" if cand["vix_entry"] >= VIX_GATE else "❌"
    return (
        f"📅 Q041 T3 Paper Signal: {cand['underlying']} T-3 (earn_date {cand['earn_date']})\n"
        f"  Spot: ${cand['spot']:.2f}  VIX: {cand['vix_entry']:.1f} {vix_ok} (≥15)\n"
        f"  ATM straddle: ${cand['implied_move_usd']:.2f} "
        f"(IV-implied move: {cand['implied_move_pct']*100:.2f}%)\n"
        f"  Spread width: ${cand['spread_width_usd']:.2f}\n"
        f"  K_short_put: {cand['K_short_put']:.0f}  K_long_put: {cand['K_long_put']:.0f}  "
        f"K_short_call: {cand['K_short_call']:.0f}  K_long_call: {cand['K_long_call']:.0f}\n"
        f"  Net credit: ${cand['net_credit_usd']:.0f}  Max loss: ${cand['max_loss_usd']:.0f}\n"
        f"  Cash need: ${cand['cash_need_usd']:.0f}\n"
        f"  Decision: {decision_line}"
    )


def _format_t_plus_1(cand: dict, close: dict) -> str:
    held = "✅ both strikes held" if close["strikes_held"] else f"❌ {close['breached']} breached"
    return (
        f"📅 Q041 T3 Paper Close: {cand['underlying']} T+1 (earn {cand['earn_date']})\n"
        f"  S_exit: ${close['s_exit']:.2f}  "
        f"[K_put {cand['K_short_put']:.0f}, K_call {cand['K_short_call']:.0f}] {held}\n"
        f"  Paper PnL: {'+' if close['paper_pnl_usd'] >= 0 else ''}${close['paper_pnl_usd']:.0f} "
        f"(net credit ${close['net_credit_usd']:.0f}, max loss ${close['max_loss_usd']:.0f})"
    )


# ── Event handlers ───────────────────────────────────────────────────────────

def _handle_t_minus_3(sym: str, earn_date: date, vix: float | None,
                      today: date, *, dry_run: bool) -> dict | None:
    sk = SK_BY_SYM[sym]
    asof = today.isoformat()

    # VIX gate first (explicit blocked event with vix_gate reason — AC-3)
    if vix is None or vix < VIX_GATE:
        decision = {"accepted": False, "reason": f"vix_gate: {vix} < {VIX_GATE}"}
        if not dry_run:
            _emit_log("blocked", sk, None, decision, asof=asof, earn_date=earn_date.isoformat())
        msg = (f"📅 Q041 {sym} T-3 ({earn_date.isoformat()}): "
               f"blocked — VIX {vix} < {VIX_GATE}")
        return {"underlying": sym, "candidate": None, "decision": decision, "msg": msg}

    cand = select_t3_earnings_ic(sk, asof, earn_date, vix)
    if cand is None:
        decision = {"accepted": False, "reason": "no_candidate (chain/expiry/strike/credit missing)"}
        if not dry_run:
            _emit_log("blocked", sk, None, decision, asof=asof, earn_date=earn_date.isoformat())
        msg = f"📅 Q041 {sym} T-3 ({earn_date.isoformat()}): no candidate (chain/expiry missing)"
        return {"underlying": sym, "candidate": None, "decision": decision, "msg": msg}

    dec = evaluate_candidate(cand)
    decision = {"accepted": dec.accepted, "reason": getattr(dec, "reason", None)}
    event = "open" if dec.accepted else "blocked"
    if not dry_run:
        _emit_log(event, sk, cand, decision, imr_check=cand.get("imr_check", "skipped"))
    return {"underlying": sym, "candidate": cand, "decision": decision,
            "msg": _format_t_minus_3(cand, decision)}


def _handle_t_plus_1(sym: str, earn_date: date, today: date, *, dry_run: bool) -> dict | None:
    sk = SK_BY_SYM[sym]
    open_rec = _find_last_open(sk)
    if open_rec is None or not open_rec.get("candidate"):
        log.info("%s T+1: no prior open event — nothing to close", sym)
        return None
    cand = open_rec["candidate"]

    s_exit = _read_spot(sym, today.isoformat())
    if s_exit is None:
        log.warning("%s T+1: no T+1 spot available — deferring close", sym)
        return None

    close = compute_ic_close_pnl(cand, s_exit)
    if not dry_run:
        _emit_log("close", sk, cand,
                  {"accepted": True, "reason": "t+1_auto_close"},
                  close=close, earn_date=earn_date.isoformat())
    return {"underlying": sym, "candidate": cand, "close": close,
            "msg": _format_t_plus_1(cand, close)}


def run(today: date, *, dry_run: bool, mock_earn: dict | None = None,
        vix_override: float | None = None) -> list[dict]:
    # Refresh / load calendar
    if mock_earn is not None:
        cache = dict(mock_earn)
    elif dry_run:
        cache = load_cache()
    else:
        try:
            cache = refresh_cache()
        except Exception as exc:
            log.error("calendar refresh failed: %s", exc)
            cache = load_cache()

    vix = vix_override if vix_override is not None else _get_current_vix()
    results: list[dict] = []

    for sym in T3_SYMBOLS:
        earn_iso = cache.get(sym)
        if not earn_iso:
            continue
        earn_date = date.fromisoformat(str(earn_iso)[:10])
        days_to = trading_days_until(earn_date, today)
        if days_to == 3:
            r = _handle_t_minus_3(sym, earn_date, vix, today, dry_run=dry_run)
            if r:
                results.append(r)
        elif days_to == -1:
            r = _handle_t_plus_1(sym, earn_date, today, dry_run=dry_run)
            if r:
                results.append(r)
        # else: silent
    return results


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="SPEC-115 Q041 T3 earnings IC event check")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default today ET)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--mock-earn", default=None,
                   help="Override earnings: COST:YYYY-MM-DD,JPM:YYYY-MM-DD")
    p.add_argument("--mock-vix", type=float, default=None, help="Override VIX for test")
    args = p.parse_args(argv)

    today = date.fromisoformat(args.date) if args.date else datetime.now(ET).date()

    mock_earn = None
    if args.mock_earn:
        mock_earn = {}
        for kv in args.mock_earn.split(","):
            k, v = kv.split(":")
            mock_earn[k.strip()] = v.strip()

    results = run(today, dry_run=args.dry_run, mock_earn=mock_earn, vix_override=args.mock_vix)

    for r in results:
        msg = r.get("msg")
        if not msg:
            continue
        if args.dry_run:
            print(msg)
        else:
            _telegram_send(msg)

    if not results:
        log.info("no T-3/T+1 events for %s (silent)", today.isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
