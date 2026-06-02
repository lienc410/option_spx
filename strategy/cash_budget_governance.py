"""SPEC-111 — Debit-strategy cash-budget cap + concurrent-utilization alert.

Cash-side governance layer parallel to (not replacing) SPEC-104 BP caps.
Binding constraint for debit strategies in a cash-bound account is CASH, not BP.

Rules:
  Hard cap:   Σ debit_open ≥ 60% × liquid_cash  → BLOCK new debit open
  Alert:      Σ debit_open ≥ 75% × liquid_cash  → NOTIFY (allow trade)
  Cash floor: liquid_cash < $30,000              → BLOCK regardless of cap math

Fail-safe: on any broker API failure, BLOCK (fail closed, not open).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DECISIONS_LOG = DATA_DIR / "cash_budget_decisions.jsonl"

# ── Constants ──────────────────────────────────────────────────────────────────

DEBIT_STRATEGIES: frozenset[str] = frozenset({"bull_call_diagonal"})

CASH_LIKE_SYMBOLS: frozenset[str] = frozenset({"BOXX", "SGOV", "SHV", "USFR", "BIL"})

CAP_PCT: float = 0.60          # hard cap: Σ debit / liquid ≤ 60%
ALERT_PCT: float = 0.75        # concurrent alert: warn but allow
CASH_FLOOR_USD: float = 30_000.0   # hard floor regardless of cap math


# ── Helpers ────────────────────────────────────────────────────────────────────

def _num(v: Any) -> float | None:
    try:
        if v in (None, ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_decisions_log(payload: dict) -> None:
    DECISIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISIONS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


# ── Cash reading ───────────────────────────────────────────────────────────────

def get_current_liquid_cash() -> dict:
    """Read combined liquid cash across brokers.

    Returns:
        {
          "total": float,
          "breakdown": {
            "schwab": {"raw_cash": float, "cash_like": float, "cash_like_positions": list},
            "etrade": {"raw_cash": float, "cash_like": float, "cash_like_positions": list},
          },
          "source": str,  # "live" | "partial" | "unavailable"
          "error": str | None,
        }
    Fail-safe: on any error, returns total=0 + source="unavailable".
    """
    result: dict = {
        "total": 0.0,
        "breakdown": {},
        "source": "unavailable",
        "error": None,
    }
    total = 0.0
    errors: list[str] = []

    # ── Schwab ─────────────────────────────────────────────────────────────────
    try:
        from schwab.client import get_account_balances as schwab_balances
        from schwab.client import get_account_positions as schwab_positions

        bal = schwab_balances()
        schwab_cash = _num(bal.get("cash_balance")) or 0.0

        # Cash-like positions (BOXX etc.)
        pos_data = schwab_positions()
        schwab_cl_positions: list[dict] = []
        schwab_cl_value = 0.0
        for pos in (pos_data.get("positions") or []):
            sym = str(pos.get("symbol") or "").upper()
            if sym in CASH_LIKE_SYMBOLS:
                mv = _num(pos.get("market_value")) or 0.0
                schwab_cl_positions.append({"symbol": sym, "market_value": mv})
                schwab_cl_value += mv

        schwab_total = schwab_cash + schwab_cl_value
        result["breakdown"]["schwab"] = {
            "raw_cash": round(schwab_cash, 2),
            "cash_like": round(schwab_cl_value, 2),
            "cash_like_positions": schwab_cl_positions,
        }
        total += schwab_total
    except Exception as exc:
        errors.append(f"schwab: {exc}")
        log.warning("cash_budget_governance: schwab cash read failed: %s", exc)

    # ── E-Trade ────────────────────────────────────────────────────────────────
    try:
        from etrade.client import get_account_balances as et_balances
        from etrade.client import get_account_positions as et_positions
        from etrade.auth import is_configured as et_configured

        if et_configured():
            bal = et_balances()
            et_cash = _num(bal.get("cash_balance")) or 0.0

            pos_data = et_positions()
            et_cl_positions: list[dict] = []
            et_cl_value = 0.0
            for pos in (pos_data.get("positions") or []):
                sym = str(pos.get("symbol") or "").upper()
                if sym in CASH_LIKE_SYMBOLS:
                    mv = _num(pos.get("market_value")) or 0.0
                    et_cl_positions.append({"symbol": sym, "market_value": mv})
                    et_cl_value += mv

            et_total = et_cash + et_cl_value
            result["breakdown"]["etrade"] = {
                "raw_cash": round(et_cash, 2),
                "cash_like": round(et_cl_value, 2),
                "cash_like_positions": et_cl_positions,
            }
            total += et_total
    except Exception as exc:
        errors.append(f"etrade: {exc}")
        log.warning("cash_budget_governance: etrade cash read failed: %s", exc)

    result["total"] = round(total, 2)
    result["error"] = "; ".join(errors) if errors else None
    result["source"] = "live" if not errors else ("partial" if total > 0 else "unavailable")
    return result


def get_open_debit_total_usd() -> dict:
    """Sum entry debit paid for all currently-open DEBIT_STRATEGIES positions.

    Returns:
        {
          "total": float,
          "positions": [{"trade_id": str, "strategy_key": str, "debit_usd": float}, ...],
        }
    """
    try:
        from strategy.state import read_all_positions
        all_pos = (read_all_positions() or {}).get("positions", [])
    except Exception as exc:
        log.warning("cash_budget_governance: positions read failed: %s", exc)
        return {"total": 0.0, "positions": [], "error": str(exc)}

    positions: list[dict] = []
    total = 0.0
    for pos in all_pos:
        if str(pos.get("status") or "open").lower() not in {"", "open"}:
            continue
        sk = str(pos.get("strategy_key") or "")
        if sk not in DEBIT_STRATEGIES:
            continue
        premium = _num(pos.get("actual_premium") or pos.get("model_premium")) or 0.0
        n = _num(pos.get("contracts")) or 1.0
        debit = abs(premium) * n * 100.0  # premium is debit per share × 100
        positions.append({
            "trade_id": pos.get("trade_id"),
            "strategy_key": sk,
            "debit_usd": round(debit, 2),
        })
        total += debit

    return {"total": round(total, 2), "positions": positions}


# ── Core evaluator ─────────────────────────────────────────────────────────────

def evaluate_debit_cash_budget(candidate: dict) -> dict:
    """SPEC-111: evaluate whether a new debit-strategy open is within cash budget.

    Args:
        candidate: governance candidate dict (must have strategy_key + bp/debit dollars)

    Returns:
        {
          "accepted": bool,
          "reason": str,           # populated if rejected
          "alert": bool,           # True if 75% threshold crossed (but accepted)
          "stats": {
            "current_liquid_cash": float,
            "currently_open_debit": float,
            "candidate_debit": float,
            "post_entry_total_debit": float,
            "post_entry_utilization_pct": float,
            "cap_pct": float,
            "alert_pct": float,
            "cash_floor_usd": float,
          }
        }
    Fail-safe: on liquid_cash read failure → accepted=False, reason="cash_read_unavailable".
    """
    # Candidate debit: prefer explicit `debit_usd`, else use requested_bp_dollars
    candidate_debit = _num(candidate.get("debit_usd") or candidate.get("requested_bp_dollars")) or 0.0
    candidate_debit = abs(candidate_debit)

    # Get liquid cash (fail-safe: block on unavailable)
    cash_data = get_current_liquid_cash()
    liquid_cash = cash_data.get("total") or 0.0
    if cash_data.get("source") == "unavailable":
        log.error("cash_budget_governance: liquid cash unavailable — blocking debit open (fail-safe)")
        return {
            "accepted": False,
            "reason": "cash_read_unavailable",
            "alert": False,
            "stats": {
                "current_liquid_cash": 0.0,
                "currently_open_debit": 0.0,
                "candidate_debit": candidate_debit,
                "post_entry_total_debit": candidate_debit,
                "post_entry_utilization_pct": 0.0,
                "cap_pct": CAP_PCT,
                "alert_pct": ALERT_PCT,
                "cash_floor_usd": CASH_FLOOR_USD,
            },
        }

    # Cash floor check
    if liquid_cash < CASH_FLOOR_USD:
        return {
            "accepted": False,
            "reason": f"cash_floor: liquid cash ${liquid_cash:,.0f} < ${CASH_FLOOR_USD:,.0f} floor",
            "alert": False,
            "stats": {
                "current_liquid_cash": liquid_cash,
                "currently_open_debit": 0.0,
                "candidate_debit": candidate_debit,
                "post_entry_total_debit": candidate_debit,
                "post_entry_utilization_pct": candidate_debit / max(liquid_cash, 1.0) * 100.0,
                "cap_pct": CAP_PCT,
                "alert_pct": ALERT_PCT,
                "cash_floor_usd": CASH_FLOOR_USD,
            },
        }

    # Open debit total
    debit_data = get_open_debit_total_usd()
    open_debit = debit_data.get("total") or 0.0

    post_entry = open_debit + candidate_debit
    utilization = post_entry / max(liquid_cash, 1.0)

    cap_threshold = CAP_PCT * liquid_cash
    alert_threshold = ALERT_PCT * liquid_cash

    stats = {
        "current_liquid_cash": round(liquid_cash, 2),
        "currently_open_debit": round(open_debit, 2),
        "candidate_debit": round(candidate_debit, 2),
        "post_entry_total_debit": round(post_entry, 2),
        "post_entry_utilization_pct": round(utilization * 100.0, 1),
        "cap_pct": CAP_PCT,
        "alert_pct": ALERT_PCT,
        "cash_floor_usd": CASH_FLOOR_USD,
    }

    # Hard cap check
    if post_entry > cap_threshold:
        return {
            "accepted": False,
            "reason": (
                f"debit_cash_cap: post-entry debit ${post_entry:,.0f} "
                f"= {utilization*100:.1f}% of ${liquid_cash:,.0f} liquid "
                f"(cap {CAP_PCT*100:.0f}%)"
            ),
            "alert": False,
            "stats": stats,
        }

    # Alert check (accepted but warn PM)
    alert = post_entry >= alert_threshold
    return {
        "accepted": True,
        "reason": "accepted",
        "alert": alert,
        "stats": stats,
    }


# ── Decision logging ───────────────────────────────────────────────────────────

def log_cash_budget_decision(
    candidate: dict,
    decision: dict,
    *,
    path: Path | None = None,
) -> None:
    stats = decision.get("stats") or {}
    payload = {
        "ts": _now_utc(),
        "candidate_strategy": candidate.get("strategy_key"),
        "candidate_debit_usd": stats.get("candidate_debit"),
        "currently_open_debit": stats.get("currently_open_debit"),
        "current_liquid_cash": stats.get("current_liquid_cash"),
        "post_entry_utilization_pct": stats.get("post_entry_utilization_pct"),
        "decision": "accept" if decision.get("accepted") else "reject",
        "reason": decision.get("reason"),
        "alert_threshold_crossed": bool(decision.get("alert")),
        "stats": stats,
    }
    _append_decisions_log(payload) if path is None else (
        path.parent.mkdir(parents=True, exist_ok=True),
        path.open("a").write(json.dumps(payload, sort_keys=True) + "\n"),
    )
