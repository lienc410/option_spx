from __future__ import annotations

import json
import logging
import math
import os
from datetime import date
from pathlib import Path
from typing import Any

from backtest.pricer import find_strike_for_delta, put_price

log = logging.getLogger(__name__)


ATTRIBUTION_FILE = Path(__file__).resolve().parent.parent / "data" / "q041_portfolio_attribution_latest.json"


_SLEEVE_SOURCE = "doc/q041_execution_prep_packet_2026-05-05.md"
_ES_BP_PER_CONTRACT = 20_529.0
_ES_MULTIPLIER = 50.0
_ES_CALIB_VIX = 19.0
_ES_CALIB_SPAN = 20_529.0
_ES_CALIB_PRICE = 5_400.0
_ES_TARGET_DELTA = 0.20
_ES_ENTRY_DTE = 45
_ES_VOL_SHOCK = 0.50
_ES_SCAN_EXPONENT = 1.10
_ES_VISIBILITY_NOTE = (
    "This is a model-based stress estimate only. It is not a trade recommendation "
    "or a risk management directive."
)
_ES_VISIBILITY_NOTE_ZH = "以下数据为基于 Q012 模型的估算值，仅供参考。不构成任何交易建议或风险管理指令。"


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    return int(number)


def _days_to_expiry(value: Any) -> int | None:
    if not value:
        return None
    try:
        return max((date.fromisoformat(str(value)) - date.today()).days, 0)
    except ValueError:
        return None


def _is_es_short_put_state(state: dict | None) -> bool:
    if not state:
        return False
    strategy_key = str(state.get("strategy_key") or "").strip().lower()
    if strategy_key == "es_short_put":
        return True
    underlying = str(state.get("underlying") or "").strip().upper()
    strategy = str(state.get("strategy") or "").lower()
    return underlying == "/ES" and "short put" in strategy


def _es_stress_band(vix: float | None) -> str:
    if vix is None:
        return "unavailable"
    if vix < 22.0:
        return "normal"
    if vix <= 30.0:
        return "stress"
    if vix <= 40.0:
        return "extreme"
    return "crisis"


def _es_stress_status(ratio: float | None) -> str:
    if ratio is None:
        return "unavailable"
    if ratio < 1.3:
        return "ok"
    if ratio <= 1.8:
        return "elevated"
    return "high_stress"


def _es_base_scan_pct() -> float:
    """
    Back out the implied price-shock fraction (`scan_pct`) that, combined with
    the volatility shock at the calibration VIX (19), reproduces the observed
    Schwab SPAN baseline ($20,529 per /ES contract). Binary-searched once at
    first use; result is cached in `_ES_BASE_SCAN_PCT_CACHE`.
    Used as the calibration anchor for `_estimate_es_existing_span`.
    """
    sigma0 = _ES_CALIB_VIX / 100.0
    strike = find_strike_for_delta(_ES_CALIB_PRICE, _ES_ENTRY_DTE, sigma0, _ES_TARGET_DELTA, is_call=False)
    premium = put_price(_ES_CALIB_PRICE, strike, _ES_ENTRY_DTE, sigma0)
    target = _ES_CALIB_SPAN / _ES_MULTIPLIER
    lo, hi = 0.01, 0.35
    for _ in range(80):
        mid = (lo + hi) / 2.0
        stressed_sigma = sigma0 * (1.0 + _ES_VOL_SHOCK)
        stressed_price = _ES_CALIB_PRICE * (1.0 - mid)
        stressed_premium = put_price(stressed_price, strike, _ES_ENTRY_DTE, stressed_sigma)
        value = max(stressed_premium - premium, 0.0) + premium
        if value < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# Lazy-cached: avoids module-import-time crash if pricer raises with edge inputs.
_ES_BASE_SCAN_PCT_CACHE: float | None = None


def _get_es_base_scan_pct() -> float:
    global _ES_BASE_SCAN_PCT_CACHE
    if _ES_BASE_SCAN_PCT_CACHE is None:
        try:
            _ES_BASE_SCAN_PCT_CACHE = _es_base_scan_pct()
        except Exception:
            log.exception("portfolio_surface: _es_base_scan_pct failed; falling back to 0.07")
            _ES_BASE_SCAN_PCT_CACHE = 0.07  # ~7% empirical default; surface falls back gracefully
    return _ES_BASE_SCAN_PCT_CACHE


def _estimate_es_existing_span(*, current_price: float, current_vix: float, strike: float, dte: int) -> float:
    """Q012 Phase A Model A2: re-mark an existing fixed-strike /ES short put."""
    sigma = max(current_vix / 100.0, 0.01)
    dte = max(int(dte), 1)
    current_premium = put_price(current_price, strike, dte, sigma)
    scan_pct = _get_es_base_scan_pct() * (current_vix / _ES_CALIB_VIX) ** _ES_SCAN_EXPONENT
    stressed_sigma = sigma * (1.0 + _ES_VOL_SHOCK)
    stressed_price = current_price * (1.0 - scan_pct)
    stressed_premium = put_price(stressed_price, strike, dte, stressed_sigma)
    return max(stressed_premium - current_premium, 0.0) * _ES_MULTIPLIER + current_premium * _ES_MULTIPLIER


def _current_vix_value() -> tuple[float | None, str | None]:
    try:
        from schwab.client import get_vix_quote

        quote = get_vix_quote()
        vix = _num(quote.get("last")) or _num(quote.get("close"))
        if vix is not None and vix > 0:
            return vix, "schwab_vix_quote"
    except Exception:
        log.warning("portfolio_surface: schwab VIX quote failed", exc_info=True)
    return None, None


def _current_es_price_value(state: dict) -> tuple[float | None, str | None]:
    for key in ("current_es", "current_underlying_price"):
        value = _num(state.get(key))
        if value is not None and value > 0:
            return value, f"state.{key}"
    try:
        from schwab.client import get_spx_quote

        quote = get_spx_quote()
        price = _num(quote.get("last")) or _num(quote.get("close"))
        if price is not None and price > 0:
            return price, "schwab_spx_quote_proxy"
    except Exception:
        log.warning("portfolio_surface: schwab SPX quote failed", exc_info=True)
    entry_price = _num(state.get("entry_spx"))
    if entry_price is not None and entry_price > 0:
        return entry_price, "state.entry_spx_fallback"
    return None, None


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


def es_stressed_span_payload() -> dict:
    """Read-only /ES stressed-SPAN visibility surface. No gating or broker action."""
    from strategy.state import read_state

    base = {
        "surface": "es_stressed_span",
        "semantics": "post-entry stress visibility only; not trade instruction",
        "model": "Q012 Phase A Model A2 existing-position SPAN estimate",
        "disclaimer": _ES_VISIBILITY_NOTE,
        "disclaimer_zh": _ES_VISIBILITY_NOTE_ZH,
        "has_es_live_position": False,
        "entry_static_span": None,
        "current_estimated_stressed_span": None,
        "stress_ratio": None,
        "stress_band": "unavailable",
        "status": "unavailable",
        "notes": [],
    }

    state = read_state()
    if not _is_es_short_put_state(state):
        return {
            **base,
            "reason": "no_active_es_short_put",
            "notes": ["No active /ES short put state is recorded."],
        }

    contracts = max(_num(state.get("contracts")) or 1.0, 1.0)
    entry_static_span = _ES_BP_PER_CONTRACT * contracts
    strike = _num(state.get("short_strike"))
    dte = _days_to_expiry(state.get("expiry"))
    if dte is None:
        dte = _int(state.get("dte_at_entry"))
    current_vix, vix_source = _current_vix_value()
    current_price, price_source = _current_es_price_value(state)

    missing = []
    if strike is None or strike <= 0:
        missing.append("short_strike")
    if dte is None:
        missing.append("dte")
    if current_vix is None:
        missing.append("current_vix")
    if current_price is None:
        missing.append("current_es_price")

    if missing:
        return {
            **base,
            "has_es_live_position": True,
            "entry_static_span": round(entry_static_span, 2),
            "status": "insufficient_data",
            "reason": "missing_inputs",
            "missing_inputs": missing,
            "inputs": {
                "short_strike": strike,
                "dte": dte,
                "current_vix": current_vix,
                "current_es_price": current_price,
                "contracts": contracts,
                "vix_source": vix_source,
                "price_source": price_source,
            },
            "notes": ["Insufficient inputs to estimate current stressed SPAN."],
        }

    stressed_span_per_contract = _estimate_es_existing_span(
        current_price=float(current_price),
        current_vix=float(current_vix),
        strike=float(strike),
        dte=int(dte),
    )
    if not math.isfinite(stressed_span_per_contract) or stressed_span_per_contract <= 0:
        return {
            **base,
            "has_es_live_position": True,
            "entry_static_span": round(entry_static_span, 2),
            "status": "insufficient_data",
            "reason": "invalid_model_output",
            "notes": ["Model output was invalid for the current input set."],
        }

    stressed_span = stressed_span_per_contract * contracts
    ratio = stressed_span / entry_static_span if entry_static_span > 0 else None
    band = _es_stress_band(float(current_vix))
    status = _es_stress_status(ratio)
    return {
        **base,
        "has_es_live_position": True,
        "entry_static_span": round(entry_static_span, 2),
        "current_estimated_stressed_span": round(stressed_span, 2),
        "stress_ratio": round(ratio, 3) if ratio is not None else None,
        "stress_band": band,
        "status": status,
        "inputs": {
            "short_strike": float(strike),
            "dte": int(dte),
            "current_vix": round(float(current_vix), 2),
            "current_es_price": round(float(current_price), 2),
            "contracts": contracts,
            "vix_source": vix_source,
            "price_source": price_source,
        },
        "notes": [
            "Uses static entry SPAN baseline $20,529 per contract.",
            "Uses SPX quote as /ES proxy when no direct /ES price is recorded.",
        ],
    }
