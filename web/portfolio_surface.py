from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any


ATTRIBUTION_FILE = Path(__file__).resolve().parent.parent / "data" / "q041_portfolio_attribution_latest.json"


_SLEEVE_SOURCE = "doc/q041_execution_prep_packet_2026-05-05.md"


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _attribution_path() -> Path:
    return Path(os.environ.get("Q041_PORTFOLIO_ATTRIBUTION_FILE", ATTRIBUTION_FILE))


def sleeve_candidates_payload() -> dict:
    """Read-only Q041 candidate carrier. It does not generate trade actions."""
    executable = [
        {
            "sleeve_id": "q041_tier1_spx_csp_d20_dte30",
            "tier": "tier1",
            "underlying": "SPX",
            "strategy_type": "csp",
            "candidate_status": "watching",
            "bp_target_pct": 20.0,
            "sizing_reference": "Tier 1 SPX CSP BP <= 20%; paper-tracking only.",
            "rationale": "Formal paper-tracking candidate from Q041 execution-prep packet.",
            "caveat": "Forward-tracking observation; not an actionable trade recommendation.",
            "source": _SLEEVE_SOURCE,
        },
        {
            "sleeve_id": "q041_tier2_googl_csp_d20_dte21",
            "tier": "tier2",
            "underlying": "GOOGL",
            "strategy_type": "csp",
            "candidate_status": "watching",
            "bp_target_pct": 10.0,
            "sizing_reference": "Tier 2 single-name BP <= 10%; combined Tier 2 BP <= 15%.",
            "rationale": "Tail-caveated paper-tracking candidate from Q041 execution-prep packet.",
            "caveat": "COVID / mega-cap single-name tail not fully validated.",
            "source": _SLEEVE_SOURCE,
        },
        {
            "sleeve_id": "q041_tier2_amzn_csp_d25_dte21",
            "tier": "tier2",
            "underlying": "AMZN",
            "strategy_type": "csp",
            "candidate_status": "watching",
            "bp_target_pct": 10.0,
            "sizing_reference": "Tier 2 single-name BP <= 10%; combined Tier 2 BP <= 15%.",
            "rationale": "Tail-caveated paper-tracking candidate from Q041 execution-prep packet.",
            "caveat": "COVID / mega-cap single-name tail not fully validated.",
            "source": _SLEEVE_SOURCE,
        },
    ]
    review_only = [
        {
            "sleeve_id": "q041_tier3_cost_earnings_ic",
            "tier": "tier3",
            "underlying": "COST",
            "strategy_type": "earnings_ic",
            "candidate_status": "review_only",
            "bp_target_pct": 5.0,
            "sizing_reference": "Tier 3 combined BP <= 5%; observe-only.",
            "rationale": "Earnings IC remains observe-only because event sample is small.",
            "caveat": "VIX >= 15 gate is required before any paper event record.",
            "source": _SLEEVE_SOURCE,
        },
        {
            "sleeve_id": "q041_tier3_jpm_earnings_ic",
            "tier": "tier3",
            "underlying": "JPM",
            "strategy_type": "earnings_ic",
            "candidate_status": "review_only",
            "bp_target_pct": 5.0,
            "sizing_reference": "Tier 3 combined BP <= 5%; observe-only.",
            "rationale": "Earnings IC remains observe-only because event sample is very small.",
            "caveat": "VIX >= 15 gate is required; IMR >= 33% is optional for JPM review.",
            "source": _SLEEVE_SOURCE,
        },
    ]
    return {
        "surface": "q041_sleeve_candidates",
        "semantics": "forward-tracking observation; not actionable trade recommendation",
        "sleeve_candidates": executable,
        "review_only": review_only,
        "allowed_candidate_status": ["watching", "due", "blocked_missing_data", "review_only", "unavailable"],
    }


def _estimate_spx_bp_usage(current_position: dict | None, basis_dollars: float) -> dict:
    if not current_position:
        return {"status": "none", "bp_usage_dollars": 0.0, "bp_usage_pct": 0.0}

    strategy_key = str(current_position.get("strategy_key") or "")
    contracts = max(1.0, _num(current_position.get("contracts")) or 1.0)
    short_strike = _num(current_position.get("short_strike"))
    long_strike = _num(current_position.get("long_strike"))
    width = abs(short_strike - long_strike) if short_strike is not None and long_strike is not None else None

    bp_per_contract: float | None = None
    if strategy_key == "bull_call_diagonal":
        # Debit diagonal: BP = net debit paid (correct for debit spreads under both Reg-T and PM)
        premium = abs(_num(current_position.get("actual_premium")) or _num(current_position.get("model_premium")) or 0.0)
        bp_per_contract = max(premium * 100.0, 0.0)
    elif width is not None:
        # PM stress-test approximation: margin ≈ max spread loss = width × $100
        # PM does not offset by opening credit (stress-test sees worst-case, not net credit)
        bp_per_contract = width * 100.0

    if bp_per_contract is None:
        return {
            "status": "insufficient_data",
            "bp_usage_dollars": None,
            "bp_usage_pct": None,
            "reason": "current_position lacks enough strike/premium data for read-only BP estimate",
        }

    dollars = round(bp_per_contract * contracts, 2)
    pct = round((dollars / basis_dollars) * 100.0, 2) if basis_dollars > 0 else None
    return {
        "status": "estimated",
        "bp_usage_dollars": dollars,
        "bp_usage_pct": pct,
        "basis_dollars": round(basis_dollars, 2),
        "source": "pm_max_loss_proxy",
    }


def _safe_q041_snapshot() -> dict:
    try:
        from logs.q041_paper_trade_io import status_snapshot

        snapshot = status_snapshot()
        return {"status": "available", **snapshot}
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": str(exc),
            "current_paper_positions": [],
            "recent_entries": [],
            "bp_usage": {
                "tier1_bp_pct": None,
                "tier2_bp_pct": None,
                "tier3_bp_pct": None,
                "total_q041_bp_pct": None,
                "within_limits": None,
                "violations": [],
            },
            "next_review_items": {"csp": None, "earnings_ic": None},
        }


def _schwab_margin_data() -> dict | None:
    """Return live Schwab NLV and maintenance_margin, or None if unavailable."""
    try:
        from schwab.client import get_account_balances
        balances = get_account_balances()
        if not balances.get("configured") or not balances.get("authenticated"):
            return None
        if balances.get("stale"):
            return None
        nlv = balances.get("net_liquidation")
        maint = balances.get("maintenance_margin")
        if nlv and float(nlv) > 0:
            return {
                "nlv": float(nlv),
                "maintenance_margin": float(maint) if maint is not None else None,
            }
    except Exception:
        pass
    return None


def _schwab_spx_bp_from_positions() -> dict | None:
    """Compute SPX spread max-loss BP directly from live Schwab option positions.
    Used as fallback when strategy state file has no open position logged.
    Parses SPXW option symbols to extract strikes, finds spread width, returns max-loss."""
    import re
    try:
        from schwab.client import get_account_positions
        pos_payload = get_account_positions()
        if pos_payload.get("stale") or not pos_payload.get("authenticated"):
            return None
        positions = pos_payload.get("positions", [])
        spx_opts = [
            p for p in positions
            if str(p.get("asset_type") or "") == "OPTION"
            and ("SPX" in str(p.get("symbol") or "").upper())
        ]
        if not spx_opts:
            return None
        # Parse strikes from OCC symbol: SPXW  YYMMDDCNNNNN (e.g. SPXW  260529P07100000)
        strikes = []
        for p in spx_opts:
            sym = str(p.get("symbol") or "")
            m = re.search(r'[CP](\d{8})$', sym.replace(" ", ""))
            if m:
                strikes.append(float(m.group(1)) / 1000.0)
        if len(strikes) < 2:
            return None
        width = abs(max(strikes) - min(strikes))
        # Count contracts from short leg quantity
        short_legs = [p for p in spx_opts if (_num(p.get("quantity")) or 0) < 0]
        contracts = max(1.0, sum(abs(_num(p.get("quantity")) or 0) for p in short_legs))
        bp_dollars = width * 100.0 * contracts
        return {
            "status": "estimated",
            "bp_usage_dollars": round(bp_dollars, 2),
            "source": "schwab_live_positions_max_loss",
            "short_strike": max(strikes),
            "long_strike": min(strikes),
            "width": width,
            "contracts": contracts,
        }
    except Exception:
        pass
    return None


def portfolio_summary_payload() -> dict:
    from strategy.selector import DEFAULT_PARAMS
    from strategy.state import read_state

    current_position = read_state()
    q041 = _safe_q041_snapshot()

    # Prefer live Schwab NLV + maintenance as basis; fall back to strategy default
    schwab = _schwab_margin_data()
    live_nlv = schwab["nlv"] if schwab else None
    live_maint = schwab["maintenance_margin"] if schwab else None
    basis = live_nlv if live_nlv is not None else float(DEFAULT_PARAMS.initial_equity)

    spx_usage = _estimate_spx_bp_usage(current_position, basis)
    # Fallback: if state has no position but Schwab shows live SPX options, compute from live
    if spx_usage.get("status") == "none":
        live_spx = _schwab_spx_bp_from_positions()
        if live_spx:
            live_spx_dollars = live_spx["bp_usage_dollars"]
            spx_usage = {
                **live_spx,
                "bp_usage_pct": round(live_spx_dollars / basis * 100.0, 2) if basis > 0 else None,
                "basis_dollars": round(basis, 2),
            }
    spx_dollars = _num(spx_usage.get("bp_usage_dollars")) or 0.0
    spx_pct = _num(spx_usage.get("bp_usage_pct")) or 0.0

    # Equity margin: Schwab total maintenance minus SPX spread max-loss
    # Residual reflects the PM 15% haircut on equity positions
    equity_margin_dollars: float | None = None
    equity_margin_pct: float | None = None
    if live_maint is not None and basis > 0:
        equity_margin_dollars = round(max(0.0, live_maint - spx_dollars), 2)
        equity_margin_pct = round(equity_margin_dollars / basis * 100.0, 2)

    q041_total = _num(q041.get("bp_usage", {}).get("total_q041_bp_pct"))
    # Total used = real margin (SPX + equity) + paper Q041
    total_real = round(spx_pct + (equity_margin_pct or 0.0), 2)
    total_used = round(total_real + (q041_total or 0.0), 2)
    idle = round(max(0.0, 100.0 - total_used), 2)

    return {
        "surface": "portfolio_summary",
        "semantics": "read-only SPX live rail + Q041 paper rail summary; not unified portfolio state",
        "as_of": date.today().isoformat(),
        "bp_basis": round(basis, 0),
        "bp_basis_source": "schwab_nlv" if live_nlv is not None else "default_params",
        "rails": {
            "spx_live": {
                "status": "open" if current_position else "none",
                "current_position": current_position,
                "bp_usage": spx_usage,
            },
            "q041_paper": q041,
        },
        "bp_usage_by_bucket": {
            "spx_live_bp_pct": spx_usage.get("bp_usage_pct"),
            "equity_margin_bp_pct": equity_margin_pct,
            "equity_margin_dollars": equity_margin_dollars,
            "q041_tier1_bp_pct": q041.get("bp_usage", {}).get("tier1_bp_pct"),
            "q041_tier2_bp_pct": q041.get("bp_usage", {}).get("tier2_bp_pct"),
            "q041_tier3_bp_pct": q041.get("bp_usage", {}).get("tier3_bp_pct"),
            "q041_total_bp_pct": q041.get("bp_usage", {}).get("total_q041_bp_pct"),
        },
        "total_real_margin_pct": total_real,
        "total_used_bp_pct": total_used,
        "idle_capacity_pct": idle,
        "next_review_item": _next_review_item(q041),
    }


def _next_review_item(q041: dict) -> dict:
    if q041.get("status") != "available":
        return {"status": "unavailable", "reason": q041.get("reason")}
    items = q041.get("next_review_items") or {}
    if items.get("csp"):
        return {"status": "available", "type": "csp", "item": items["csp"]}
    if items.get("earnings_ic"):
        return {"status": "available", "type": "earnings_ic", "item": items["earnings_ic"]}
    return {"status": "none"}


def attribution_payload() -> dict:
    path = _attribution_path()
    if not path.exists():
        return {
            "surface": "portfolio_attribution",
            "status": "pending_quant_input",
            "source": str(path),
            "semantics": "read-only carrier for Quant-provided attribution artifact",
            "idle_day_capture": {"status": "pending_quant_input", "value": None},
            "delta_avg_bp": {"status": "pending_quant_input", "value": None},
            "bp_fill_contribution": {"status": "pending_quant_input", "value": None},
            "worst_day_overlap": {"status": "pending_quant_input", "value": None},
            "notes": "No Quant-provided attribution artifact is available yet.",
        }
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        return {
            "surface": "portfolio_attribution",
            "status": "unavailable",
            "source": str(path),
            "error": str(exc),
            "idle_day_capture": {"status": "unavailable", "value": None},
            "delta_avg_bp": {"status": "unavailable", "value": None},
            "bp_fill_contribution": {"status": "unavailable", "value": None},
            "worst_day_overlap": {"status": "unavailable", "value": None},
            "notes": "Attribution artifact could not be parsed.",
        }
    return {
        "surface": "portfolio_attribution",
        "status": "available",
        "source": str(path),
        "semantics": "read-only carrier for Quant-provided attribution artifact",
        **payload,
    }
