"""Overlay-F evaluation and telemetry helpers.

Overlay-F is deliberately inert unless `overlay_f_mode` is shadow or active.
Live state failures fail closed: no would-fire, no size-up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from strategy.catalog import strategy_key as catalog_strategy_key


_ET = ZoneInfo("America/New_York")
_SHADOW_LOG = Path("data/overlay_f_shadow.jsonl")
_ALERT_LATEST = Path("data/overlay_f_alert_latest.txt")
SHORT_GAMMA_KEYS = {
    "bull_put_spread",
    "bull_put_spread_hv",
    "bear_call_spread_hv",
    "iron_condor",
    "iron_condor_hv",
}


@dataclass
class PortfolioState:
    idle_bp_pct: float | None
    sg_count: int | None
    valid: bool = True
    stale: bool = False
    reason: str = ""


@dataclass
class OverlayDecision:
    mode: str
    would_fire: bool
    effective_factor: float
    rationale: str
    idle_bp_pct: float | None
    sg_count: int | None
    fail_closed: bool = False


def _strategy_key(value) -> str:
    try:
        return catalog_strategy_key(value.value)
    except Exception:
        return catalog_strategy_key(str(value))


def _is_short_gamma_key(key: str | None) -> bool:
    return bool(key) and key in SHORT_GAMMA_KEYS


def short_gamma_count_from_positions(positions: Iterable) -> int:
    """Count short-gamma positions by position, not by strategy family."""
    count = 0
    for position in positions:
        key = getattr(position, "strategy_key", None)
        if key is None and hasattr(position, "strategy"):
            key = _strategy_key(getattr(position, "strategy"))
        if _is_short_gamma_key(key):
            count += 1
    return count


def build_portfolio_state(
    *,
    positions: Iterable,
    used_bp_pct: float,
) -> PortfolioState:
    return PortfolioState(
        idle_bp_pct=max(0.0, 1.0 - float(used_bp_pct)),
        sg_count=short_gamma_count_from_positions(positions),
    )


def build_live_portfolio_state() -> PortfolioState:
    """Build live state from Schwab. Missing/stale data fails closed."""
    try:
        from schwab.client import get_account_balances, get_account_positions
    except Exception as exc:
        return PortfolioState(None, None, valid=False, stale=True, reason=f"import_failed:{exc}")

    try:
        balances = get_account_balances()
        positions = get_account_positions()
    except Exception as exc:
        return PortfolioState(None, None, valid=False, stale=True, reason=f"schwab_failed:{exc}")

    if (
        not balances.get("configured")
        or not balances.get("authenticated")
        or balances.get("stale")
        or not positions.get("configured")
        or not positions.get("authenticated")
        or positions.get("stale")
    ):
        return PortfolioState(None, None, valid=False, stale=True, reason="live_state_unavailable")

    try:
        nlv = float(balances.get("net_liquidation") or 0.0)
        initial_margin = balances.get("initial_margin")
        maintenance_margin = balances.get("maintenance_margin")
        used_margin = max(float(v or 0.0) for v in (initial_margin, maintenance_margin))
    except (TypeError, ValueError):
        return PortfolioState(None, None, valid=False, stale=True, reason="missing_live_bp")

    if nlv <= 0:
        return PortfolioState(None, None, valid=False, stale=True, reason="missing_live_nlv")

    idle_bp_pct = max(0.0, 1.0 - (used_margin / nlv))
    sg_count = 0
    for pos in positions.get("positions", []) or []:
        text = f"{pos.get('symbol', '')} {pos.get('description', '')}".lower()
        if any(token in text for token in ("spx", "spy", "/es")) and any(
            token in text for token in ("put", "call")
        ):
            sg_count += 1
    return PortfolioState(idle_bp_pct=idle_bp_pct, sg_count=sg_count)


def evaluate_overlay_f(
    *,
    mode: str,
    strategy_key: str,
    vix: float,
    portfolio_state: PortfolioState,
) -> OverlayDecision:
    normalized_mode = str(mode or "disabled").lower()
    if normalized_mode not in {"disabled", "shadow", "active"}:
        normalized_mode = "disabled"

    if normalized_mode == "disabled":
        return OverlayDecision(normalized_mode, False, 1.0, "", None, None)

    if not portfolio_state.valid or portfolio_state.stale:
        reason = portfolio_state.reason or "live state unavailable"
        return OverlayDecision(
            normalized_mode,
            False,
            1.0,
            f"Overlay-F fail closed — {reason}",
            portfolio_state.idle_bp_pct,
            portfolio_state.sg_count,
            fail_closed=True,
        )

    idle_bp = portfolio_state.idle_bp_pct
    sg_count = portfolio_state.sg_count
    if idle_bp is None or sg_count is None:
        return OverlayDecision(
            normalized_mode,
            False,
            1.0,
            "Overlay-F fail closed — missing idle BP or SG count",
            idle_bp,
            sg_count,
            fail_closed=True,
        )

    gates = [
        strategy_key == "iron_condor_hv",
        idle_bp >= 0.70,
        float(vix) < 30.0,
        int(sg_count) < 2,
    ]
    would_fire = all(gates)
    factor = 2.0 if normalized_mode == "active" and would_fire else 1.0
    rationale = (
        f"Overlay-F {'fires' if would_fire else 'blocked'}: "
        f"strategy={strategy_key}, idle_bp={idle_bp:.2f}, vix={float(vix):.1f}, sg_count={sg_count}"
    )
    return OverlayDecision(normalized_mode, would_fire, factor, rationale, idle_bp, sg_count)


def append_overlay_f_log(*, date: str, strategy: str, vix: float, decision: OverlayDecision) -> None:
    if decision.mode not in {"shadow", "active"} or not decision.would_fire:
        return
    payload = {
        "timestamp": datetime.now(_ET).isoformat(timespec="seconds"),
        "date": date,
        "strategy": strategy,
        "vix": float(vix),
        "idle_bp_pct": decision.idle_bp_pct,
        "sg_count": decision.sg_count,
        "mode": decision.mode,
        "effective_factor": decision.effective_factor,
        "rationale": decision.rationale,
    }
    _SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _SHADOW_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")
    _ALERT_LATEST.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def decision_payload(decision: OverlayDecision) -> dict:
    return asdict(decision)
