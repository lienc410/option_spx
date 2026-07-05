"""SPEC-119 — explicit sigma modes. No default mode; no library-baked brackets.

FLAT  : sigma = vix/100 for every strike (historical convention; bit-identical
        reproduction path).
CALIB : sigma = (vix + offset)/100, offset measured from the live skew monitor
        (pricing.calibration) for (option_type, |delta|, dte bucket).
PESS  : CALIB shifted in the direction ADVERSE to the caller's position by a
        caller-supplied bracket (vol points). bracket_vp is REQUIRED — the
        library refuses to invent a robustness margin (external review C-series
        condition: bracket parameters are a research decision, never a library
        default).
"""
from __future__ import annotations

from enum import Enum


class SigmaMode(str, Enum):
    FLAT = "FLAT"
    CALIB = "CALIB"
    PESS = "PESS"


def sigma_for(
    mode: SigmaMode,
    *,
    vix: float,
    option_type: str | None = None,
    abs_delta: float | None = None,
    dte: int | None = None,
    offsets: "dict | None" = None,
    adverse_sign: int | None = None,
    bracket_vp: float | None = None,
) -> float:
    """Annualized sigma for one leg under an EXPLICIT mode.

    FLAT  needs: vix
    CALIB needs: vix, option_type ('CALL'|'PUT'), abs_delta, dte, offsets
                 (from pricing.calibration.load_offsets)
    PESS  needs: CALIB inputs + adverse_sign (+1 = higher vol hurts the
                 position, -1 = lower vol hurts) + bracket_vp (vol points)

    Raises ValueError on any missing requirement — misconfiguration must be
    loud, not silently FLAT.
    """
    if not isinstance(mode, SigmaMode):
        raise ValueError(f"mode must be a SigmaMode, got {mode!r}")
    if vix is None or vix <= 0:
        raise ValueError(f"vix must be positive, got {vix!r}")

    if mode is SigmaMode.FLAT:
        return vix / 100.0

    # CALIB / PESS share the offset lookup
    if offsets is None:
        raise ValueError(f"{mode.value} mode requires offsets (pricing.calibration.load_offsets)")
    if option_type is None or abs_delta is None or dte is None:
        raise ValueError(f"{mode.value} mode requires option_type, abs_delta and dte")
    off = _lookup_offset(offsets, option_type, abs_delta, dte)
    sigma_vp = vix + off

    if mode is SigmaMode.CALIB:
        return max(sigma_vp, 1.0) / 100.0

    # PESS
    if bracket_vp is None:
        raise ValueError("PESS mode requires bracket_vp — the adverse bracket is a "
                         "caller decision, the library has no default")
    if adverse_sign not in (+1, -1):
        raise ValueError("PESS mode requires adverse_sign of +1 or -1")
    return max(sigma_vp + adverse_sign * bracket_vp, 1.0) / 100.0


def _lookup_offset(offsets: dict, option_type: str, abs_delta: float, dte: int) -> float:
    """Offset (vol points) for a leg. Buckets from calibration.load_offsets:
    offsets[(type, dte_bucket)] = sorted list of (abs_delta, offset_vp).
    Linear interpolation in |delta| inside the bucket; clamped at the edges."""
    ot = option_type.upper()
    bucket = "25-35" if dte <= 55 else "80-100"
    key = (ot, bucket)
    if key not in offsets:
        raise ValueError(f"no calibration for {key} — extend the skew monitor "
                         f"or fall back to FLAT explicitly")
    pts = offsets[key]  # [(abs_delta, off_vp), ...] ascending by abs_delta
    if abs_delta <= pts[0][0]:
        return pts[0][1]
    if abs_delta >= pts[-1][0]:
        return pts[-1][1]
    for (d0, o0), (d1, o1) in zip(pts, pts[1:]):
        if d0 <= abs_delta <= d1:
            w = (abs_delta - d0) / (d1 - d0)
            return o0 + w * (o1 - o0)
    return pts[-1][1]  # unreachable
