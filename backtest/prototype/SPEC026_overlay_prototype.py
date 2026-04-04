"""
VIX Acceleration Overlay — SPEC-026

4-level state machine driven by VIX acceleration and portfolio shock sensitivity.
Replaces single-trade panic stop (proven ineffective) with portfolio-level
pre-emptive risk management.

Design rationale:
  - L2/L3 use AND logic: prevents false positives when VIX rises but portfolio
    is unexposed (e.g. all long-vega positions would benefit from VIX rise)
  - L1/L4 use OR logic: either signal alone warrants immediate protective action
  - book_core_shock MUST be computed independently every day (see fix below)

Critical bug fix: book_core_shock path
  The initial implementation computed book_core_shock only when a candidate
  entry existed (via ShockReport from the entry path). When L1 freeze triggered
  and there was no entry candidate, book_core_shock defaulted to 0, preventing
  L2 from ever firing. Fix: compute existing-book shock independently every day
  in the main engine loop, before the entry decision path.

Levels:
  L0  Normal    — no restriction
  L1  Freeze    — block new short-vol entries
  L2  Freeze+Trim — block new entries AND close all open positions
  L3  Freeze+Trim+Hedge — same as L2 in v1; long put spread in v2
  L4  Emergency — close all positions immediately
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy.selector import StrategyParams


class OverlayLevel(IntEnum):
    L0_NORMAL    = 0
    L1_FREEZE    = 1
    L2_TRIM      = 2
    L3_HEDGE     = 3
    L4_EMERGENCY = 4


@dataclass
class OverlayResult:
    """Output of compute_overlay_signals() for one trading day."""
    level:            OverlayLevel
    vix_accel_3d:     float    # (VIX_t / VIX_{t-3}) - 1  (fraction, e.g. 0.15 = +15%)
    book_core_shock:  float    # worst core-scenario loss as fraction of NAV (≤ 0)
    vix:              float
    bp_headroom:      float    # remaining BP as fraction of NAV

    # Derived flags for engine logic
    block_new_entries:  bool   # True when level >= L1
    force_trim:         bool   # True when level >= L2
    force_emergency:    bool   # True when level == L4

    # Reason string for audit log
    trigger_reason: str = ""


def compute_overlay_signals(
    *,
    vix: float,
    vix_3d_ago: float,
    book_core_shock: float,   # fraction of NAV (≤ 0); computed independently each day
    bp_headroom: float,       # fraction of NAV remaining after current positions
    params: "StrategyParams",
) -> OverlayResult:
    """
    Compute the current overlay level and required actions.

    Args:
        vix:              Today's VIX close.
        vix_3d_ago:       VIX close 3 trading days ago (for acceleration).
        book_core_shock:  Worst core-scenario (S1-S4) loss as fraction of NAV.
                          Must be computed independently every day by the engine,
                          regardless of whether an entry candidate exists.
        bp_headroom:      Remaining buying power as fraction of account NAV.
        params:           StrategyParams with overlay_* threshold fields.

    Returns:
        OverlayResult with level, action flags, and trigger_reason.
    """
    mode = getattr(params, "overlay_mode", "disabled")

    # If overlay is disabled, always return L0
    if mode == "disabled":
        vix_accel = _compute_accel(vix, vix_3d_ago)
        return OverlayResult(
            level=OverlayLevel.L0_NORMAL,
            vix_accel_3d=vix_accel,
            book_core_shock=book_core_shock,
            vix=vix,
            bp_headroom=bp_headroom,
            block_new_entries=False,
            force_trim=False,
            force_emergency=False,
            trigger_reason="overlay disabled",
        )

    vix_accel = _compute_accel(vix, vix_3d_ago)
    abs_shock = abs(book_core_shock)   # shock is ≤ 0; compare magnitude

    # ── Level 4 Emergency (OR logic) ──────────────────────────────────────────
    l4_vix    = vix >= params.overlay_emergency_vix
    l4_shock  = abs_shock >= params.overlay_emergency_shock
    l4_bp     = bp_headroom < params.overlay_emergency_bp

    if l4_vix or l4_shock or l4_bp:
        reasons = []
        if l4_vix:   reasons.append(f"VIX {vix:.1f} >= {params.overlay_emergency_vix}")
        if l4_shock: reasons.append(f"book_shock {abs_shock*100:.2f}% >= {params.overlay_emergency_shock*100:.2f}%")
        if l4_bp:    reasons.append(f"bp_headroom {bp_headroom*100:.1f}% < {params.overlay_emergency_bp*100:.1f}%")
        return OverlayResult(
            level=OverlayLevel.L4_EMERGENCY,
            vix_accel_3d=vix_accel,
            book_core_shock=book_core_shock,
            vix=vix,
            bp_headroom=bp_headroom,
            block_new_entries=True,
            force_trim=True,
            force_emergency=True,
            trigger_reason="L4: " + "; ".join(reasons),
        )

    # ── Level 3 Freeze+Trim+Hedge (AND logic) ─────────────────────────────────
    l3_accel = vix_accel > params.overlay_hedge_accel
    l3_shock = abs_shock >= params.overlay_hedge_shock

    if l3_accel and l3_shock:
        return OverlayResult(
            level=OverlayLevel.L3_HEDGE,
            vix_accel_3d=vix_accel,
            book_core_shock=book_core_shock,
            vix=vix,
            bp_headroom=bp_headroom,
            block_new_entries=True,
            force_trim=True,
            force_emergency=False,
            trigger_reason=(
                f"L3: accel {vix_accel*100:.1f}% > {params.overlay_hedge_accel*100:.0f}%"
                f" AND shock {abs_shock*100:.2f}% >= {params.overlay_hedge_shock*100:.2f}%"
            ),
        )

    # ── Level 2 Freeze+Trim (AND logic) ───────────────────────────────────────
    l2_accel = vix_accel > params.overlay_trim_accel
    l2_shock = abs_shock >= params.overlay_trim_shock

    if l2_accel and l2_shock:
        return OverlayResult(
            level=OverlayLevel.L2_TRIM,
            vix_accel_3d=vix_accel,
            book_core_shock=book_core_shock,
            vix=vix,
            bp_headroom=bp_headroom,
            block_new_entries=True,
            force_trim=True,
            force_emergency=False,
            trigger_reason=(
                f"L2: accel {vix_accel*100:.1f}% > {params.overlay_trim_accel*100:.0f}%"
                f" AND shock {abs_shock*100:.2f}% >= {params.overlay_trim_shock*100:.2f}%"
            ),
        )

    # ── Level 1 Freeze (OR logic) ─────────────────────────────────────────────
    l1_accel = vix_accel > params.overlay_freeze_accel
    l1_vix   = vix >= params.overlay_freeze_vix

    if l1_accel or l1_vix:
        reasons = []
        if l1_accel: reasons.append(f"accel {vix_accel*100:.1f}% > {params.overlay_freeze_accel*100:.0f}%")
        if l1_vix:   reasons.append(f"VIX {vix:.1f} >= {params.overlay_freeze_vix}")
        return OverlayResult(
            level=OverlayLevel.L1_FREEZE,
            vix_accel_3d=vix_accel,
            book_core_shock=book_core_shock,
            vix=vix,
            bp_headroom=bp_headroom,
            block_new_entries=True,
            force_trim=False,
            force_emergency=False,
            trigger_reason="L1: " + "; ".join(reasons),
        )

    # ── Level 0 Normal ────────────────────────────────────────────────────────
    return OverlayResult(
        level=OverlayLevel.L0_NORMAL,
        vix_accel_3d=vix_accel,
        book_core_shock=book_core_shock,
        vix=vix,
        bp_headroom=bp_headroom,
        block_new_entries=False,
        force_trim=False,
        force_emergency=False,
    )


def _compute_accel(vix_today: float, vix_3d_ago: float) -> float:
    """
    3-day VIX acceleration: (VIX_t / VIX_{t-3}) - 1.

    Returns 0.0 if vix_3d_ago is 0 (avoid division by zero).
    """
    if vix_3d_ago <= 0:
        return 0.0
    return (vix_today / vix_3d_ago) - 1.0


if __name__ == "__main__":
    from strategy.selector import StrategyParams
    params = StrategyParams()
    params.overlay_mode = "active"

    # Normal conditions → L0
    r = compute_overlay_signals(
        vix=18.0, vix_3d_ago=17.5,
        book_core_shock=0.0,
        bp_headroom=0.85,
        params=params,
    )
    assert r.level == OverlayLevel.L0_NORMAL, f"Expected L0, got {r.level}"
    print(f"Normal: {r.level.name}  accel={r.vix_accel_3d*100:.2f}%")

    # VIX jumps → L1 Freeze
    r = compute_overlay_signals(
        vix=31.0, vix_3d_ago=20.0,
        book_core_shock=-0.005,
        bp_headroom=0.80,
        params=params,
    )
    assert r.level == OverlayLevel.L1_FREEZE, f"Expected L1, got {r.level} ({r.trigger_reason})"
    assert r.block_new_entries is True
    print(f"Freeze: {r.level.name}  reason={r.trigger_reason}")

    # Strong accel + shock → L2
    r = compute_overlay_signals(
        vix=28.0, vix_3d_ago=20.0,
        book_core_shock=-0.012,
        bp_headroom=0.70,
        params=params,
    )
    assert r.level == OverlayLevel.L2_TRIM, f"Expected L2, got {r.level} ({r.trigger_reason})"
    assert r.force_trim is True
    print(f"Trim:   {r.level.name}  reason={r.trigger_reason}")

    # VIX emergency → L4
    r = compute_overlay_signals(
        vix=42.0, vix_3d_ago=25.0,
        book_core_shock=-0.01,
        bp_headroom=0.70,
        params=params,
    )
    assert r.level == OverlayLevel.L4_EMERGENCY, f"Expected L4, got {r.level}"
    assert r.force_emergency is True
    print(f"Emergency: {r.level.name}  reason={r.trigger_reason}")

    print("overlay.py OK")
