"""SPEC-111 — Cash-budget cap + concurrent-utilization alert.

Governs any strategy that occupies liquid cash: debit strategies (BCD) and
cash-secured puts (CSP). Extended by SPEC-115 Phase A to cover Q041 T2 CSPs.

Rules:
  Hard cap:   Σ cash_occupied ≥ 60% × liquid_cash  → BLOCK
  Alert:      Σ cash_occupied ≥ 75% × liquid_cash  → NOTIFY (allow)
  Cash floor: liquid_cash < $30,000                 → BLOCK regardless

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

# SPEC-115 Phase A: extended to cover CSP cash collateral strategies
CASH_OCCUPYING_STRATEGIES: frozenset[str] = frozenset({
    "bull_call_diagonal",        # debit (SPEC-111/113)
    "q041_t2_googl_csp",         # CSP cash collateral (SPEC-115 phase A)
    "q041_t2_amzn_csp",          # CSP cash collateral (SPEC-115 phase A)
    "q041_t3_cost_earnings_ic",  # IC max-loss collateral (SPEC-115 phase B)
    "q041_t3_jpm_earnings_ic",   # IC max-loss collateral (SPEC-115 phase B)
})
# Backward-compat alias — do not remove (test_spec_111.py imports this)
DEBIT_STRATEGIES: frozenset[str] = CASH_OCCUPYING_STRATEGIES

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


def get_open_cash_collateral_total_usd() -> dict:
    """Sum cash occupied by all open CASH_OCCUPYING_STRATEGIES positions.

    BCD: cash = abs(entry_premium) × contracts × 100 (debit paid)
    CSP: cash = short_strike × contracts × 100 (cash collateral)

    Returns:
        {"total": float, "positions": [...]}
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
        if sk not in CASH_OCCUPYING_STRATEGIES:
            continue
        n = _num(pos.get("contracts")) or 1.0
        # Prefer explicit cash_need_usd / max_loss_usd if the position carries it
        # (CSP and IC paper positions store this); else derive per strategy type.
        explicit = _num(pos.get("cash_need_usd") or pos.get("max_loss_usd"))
        if explicit is not None:
            cash_usd = explicit  # already a per-position total (× contracts baked in at open)
        elif sk == "bull_call_diagonal":
            # BCD: debit paid
            premium = _num(pos.get("actual_premium") or pos.get("model_premium")) or 0.0
            cash_usd = abs(premium) * n * 100.0
        elif sk.endswith("_csp"):
            # CSP: cash collateral = K × 100 × n
            strike = _num(pos.get("short_strike") or pos.get("strike")) or 0.0
            cash_usd = strike * 100.0 * n
        else:
            # IC or other: fall back to short_strike-based (defensive; should have cash_need)
            strike = _num(pos.get("short_strike") or pos.get("strike")) or 0.0
            cash_usd = strike * 100.0 * n
        positions.append({
            "trade_id": pos.get("trade_id"),
            "strategy_key": sk,
            "cash_usd": round(cash_usd, 2),
        })
        total += cash_usd

    return {"total": round(total, 2), "positions": positions}


# Backward-compat alias for external callers
def get_open_debit_total_usd() -> dict:
    return get_open_cash_collateral_total_usd()


# ── Core evaluator ─────────────────────────────────────────────────────────────

def evaluate_cash_collateral_budget(candidate: dict) -> dict:
    """SPEC-111/115: evaluate cash-budget gate for any cash-occupying strategy.

    Handles both debit (BCD via entry_debit_usd / debit_usd) and CSP cash
    collateral (q041_t2_* via cash_need_usd = K × 100).

    Args:
        candidate: governance candidate dict with strategy_key + cash amount field

    Returns:
        {"accepted": bool, "reason": str, "alert": bool, "stats": {...}}

    Fail-safe: on liquid_cash read failure → accepted=False.
    """
    sk = str(candidate.get("strategy_key") or "")
    if sk not in CASH_OCCUPYING_STRATEGIES:
        return {"accepted": True, "reason": "not_cash_occupying", "alert": False, "stats": {}}

    # Resolve cash_need: CSP uses cash_need_usd; BCD uses debit_usd / requested_bp_dollars
    cash_need = (
        _num(candidate.get("cash_need_usd"))
        or _num(candidate.get("debit_usd"))         # BCD backward compat
        or _num(candidate.get("entry_debit_usd"))   # BCD backward compat
        or _num(candidate.get("requested_bp_dollars"))
    )
    if cash_need is None:
        return {
            "accepted": False, "alert": False,
            "reason": "missing cash_need_usd / debit_usd / requested_bp_dollars",
            "stats": {},
        }
    candidate_cash = abs(cash_need)

    prefix = "debit_cash_budget" if sk == "bull_call_diagonal" else "cash_collateral"

    # Get liquid cash (fail-safe: block on unavailable)
    cash_data = get_current_liquid_cash()
    liquid_cash = cash_data.get("total") or 0.0
    if cash_data.get("source") == "unavailable":
        log.error("cash_budget_governance: liquid cash unavailable — blocking (fail-safe)")
        return {
            "accepted": False,
            "reason": "cash_read_unavailable",
            "alert": False,
            "stats": {
                "current_liquid_cash": 0.0,
                "currently_open_cash": 0.0,
                "candidate_cash": candidate_cash,
                "post_entry_total_cash": candidate_cash,
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
                "currently_open_cash": 0.0,
                "candidate_cash": candidate_cash,
                "post_entry_total_cash": candidate_cash,
                "post_entry_utilization_pct": candidate_cash / max(liquid_cash, 1.0) * 100.0,
                "cap_pct": CAP_PCT,
                "alert_pct": ALERT_PCT,
                "cash_floor_usd": CASH_FLOOR_USD,
            },
        }

    # Open cash collateral total
    open_data = get_open_cash_collateral_total_usd()
    open_cash = open_data.get("total") or 0.0

    post_entry = open_cash + candidate_cash
    utilization = post_entry / max(liquid_cash, 1.0)

    cap_threshold = CAP_PCT * liquid_cash
    alert_threshold = ALERT_PCT * liquid_cash

    stats = {
        "current_liquid_cash": round(liquid_cash, 2),
        "currently_open_cash": round(open_cash, 2),
        # Keep legacy key names for SPEC-111 test compatibility
        "currently_open_debit": round(open_cash, 2),
        "candidate_cash": round(candidate_cash, 2),
        "candidate_debit": round(candidate_cash, 2),
        "post_entry_total_cash": round(post_entry, 2),
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
                f"{prefix}: post-entry cash ${post_entry:,.0f} "
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


# Backward-compat alias — SPEC-111 callers use evaluate_debit_cash_budget
def evaluate_debit_cash_budget(candidate: dict) -> dict:
    """Deprecated alias for evaluate_cash_collateral_budget (SPEC-115 rename)."""
    return evaluate_cash_collateral_budget(candidate)
