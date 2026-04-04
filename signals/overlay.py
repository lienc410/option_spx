"""
VIX acceleration overlay state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class OverlayLevel(IntEnum):
    L0_NORMAL = 0
    L1_FREEZE = 1
    L2_TRIM = 2
    L3_HEDGE = 3
    L4_EMERGENCY = 4


@dataclass
class OverlayResult:
    level: OverlayLevel
    vix_accel_3d: float
    book_core_shock: float
    vix: float
    bp_headroom: float
    block_new_entries: bool
    force_trim: bool
    force_emergency: bool
    trigger_reason: str = ""


def _compute_accel(vix: float, vix_3d_ago: float) -> float:
    if vix_3d_ago <= 0:
        return 0.0
    return (vix / vix_3d_ago) - 1.0


def compute_overlay_signals(*, vix: float, vix_3d_ago: float, book_core_shock: float, bp_headroom: float, params) -> OverlayResult:
    mode = getattr(params, "overlay_mode", "disabled")
    accel = _compute_accel(vix, vix_3d_ago)
    abs_shock = abs(book_core_shock)

    if mode == "disabled":
        return OverlayResult(OverlayLevel.L0_NORMAL, accel, book_core_shock, vix, bp_headroom, False, False, False, "overlay disabled")

    if (
        vix >= params.overlay_emergency_vix
        or abs_shock >= params.overlay_emergency_shock
        or bp_headroom < params.overlay_emergency_bp
    ):
        return OverlayResult(
            OverlayLevel.L4_EMERGENCY,
            accel,
            book_core_shock,
            vix,
            bp_headroom,
            True,
            True,
            True,
            "L4 emergency",
        )

    if accel > params.overlay_hedge_accel and abs_shock >= params.overlay_hedge_shock:
        return OverlayResult(
            OverlayLevel.L3_HEDGE,
            accel,
            book_core_shock,
            vix,
            bp_headroom,
            True,
            True,
            False,
            "L3 hedge",
        )

    if accel > params.overlay_trim_accel and abs_shock >= params.overlay_trim_shock:
        return OverlayResult(
            OverlayLevel.L2_TRIM,
            accel,
            book_core_shock,
            vix,
            bp_headroom,
            True,
            True,
            False,
            "L2 trim",
        )

    if accel > params.overlay_freeze_accel or vix >= params.overlay_freeze_vix:
        return OverlayResult(
            OverlayLevel.L1_FREEZE,
            accel,
            book_core_shock,
            vix,
            bp_headroom,
            True,
            False,
            False,
            "L1 freeze",
        )

    return OverlayResult(OverlayLevel.L0_NORMAL, accel, book_core_shock, vix, bp_headroom, False, False, False, "L0 normal")
