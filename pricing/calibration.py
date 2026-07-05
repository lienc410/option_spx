"""SPEC-119 — dynamic offsets from the daily skew monitor JSONL.

Reads data/q085_skew_monitor.jsonl (SPEC-116, extended by SPEC-119 with call
legs and the 80-100 DTE bucket) and produces per-(type, dte-bucket) offset
curves as rolling medians. NOT hardcoded: the acceptance-baseline table in
task/SPEC-119.md §2 is for validation only — this module always computes from
the file.

CONVENTION (AC-3 finding, 2026-07-05): offsets are built from the *_moff
fields — mid-implied IV solved through pricing.core (T=dte/365, r=0.045,
q=0) — NOT from the vendor-iv *_off fields. The vendor iv column runs
1-2.5vp below the vol that reproduces the chain's own mids under our pricer;
offsets built from it systematically underprice real credits (~-26% on a
BPS net credit, 2026-07-02). CALIB sigma is therefore only valid when the
consumer prices with the same conventions (see q085 _MIV_CONV).

Minimum-sample gate: fewer than MIN_DAYS rows in the window → raises
InsufficientCalibration. Callers must then EXPLICITLY choose FLAT (and the
daily job alerts) — a silent fallback would defeat the calibration program.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKEW_MONITOR = ROOT / "data" / "q085_skew_monitor.jsonl"

MIN_DAYS = 10
DEFAULT_WINDOW_DAYS = 60

# JSONL field → (option_type, abs_delta, dte_bucket). All fields are the
# SPEC-119 mid-implied offsets (*_moff); suffix _far marks the 80-100 DTE
# bucket. Legacy vendor-iv *_off fields are deliberately NOT consumed.
_LEG_FIELDS: dict[str, tuple[str, float, str]] = {
    "atm_moff":      ("PUT", 0.50, "25-35"),
    "d30_moff":      ("PUT", 0.30, "25-35"),
    "d15_moff":      ("PUT", 0.15, "25-35"),
    "c70_moff":      ("CALL", 0.70, "25-35"),
    "c30_moff":      ("CALL", 0.30, "25-35"),
    "c16_moff":      ("CALL", 0.16, "25-35"),
    "c08_moff":      ("CALL", 0.08, "25-35"),
    "atm_moff_far":  ("PUT", 0.50, "80-100"),
    "d30_moff_far":  ("PUT", 0.30, "80-100"),
    "d15_moff_far":  ("PUT", 0.15, "80-100"),
    "c70_moff_far":  ("CALL", 0.70, "80-100"),
    "c30_moff_far":  ("CALL", 0.30, "80-100"),
    "c16_moff_far":  ("CALL", 0.16, "80-100"),
    "c08_moff_far":  ("CALL", 0.08, "80-100"),
}


class InsufficientCalibration(RuntimeError):
    """Raised when the skew monitor has too few rows for a trustworthy offset."""


# Offset conventions. Offsets are measured by solving mid-implied IV at
# T=dte/365 (r=0.045, q=0) — CONV_ACT365. A consumer pricing at T=dte/252
# (the matrix engine) must first convert: same price impact requires
# sigma_252 = sigma_365 * sqrt(252/365) (equal total variance sigma^2*T).
# Q087 C4 post-mortem: this trap was documented in memory and still got hit
# (all CALIB haircuts overstated 15-20%) — hence the tag + engine assertion.
CONV_ACT365 = "r045_q0_act365"
CONV_TD252 = "r045_q0_td252"
_TD252_SCALE = (252.0 / 365.0) ** 0.5


class OffsetCurves(dict):
    """offsets[(TYPE, bucket)] -> [(abs_delta, offset_vp), ...] plus a
    `convention` tag consumers can assert against."""

    def __init__(self, data: dict, convention: str):
        super().__init__(data)
        self.convention = convention


def to_trading_day_convention(offsets: "OffsetCurves") -> "OffsetCurves":
    """Scale ACT/365-measured offsets for a T=dte/252 consumer (x sqrt(252/365)).
    The VIX baseline itself is NOT scaled — feeding raw VIX/100 into dte/252
    pricing is the engine's historical FLAT convention; only the calibration
    delta on top must be made variance-equivalent."""
    conv = getattr(offsets, "convention", None)
    if conv == CONV_TD252:
        return offsets
    if conv != CONV_ACT365:
        raise ValueError(f"cannot convert offsets with convention {conv!r}")
    scaled = {k: [(d, o * _TD252_SCALE) for d, o in v] for k, v in offsets.items()}
    return OffsetCurves(scaled, CONV_TD252)


def _read_rows(p: Path) -> list[dict]:
    rows: list[dict] = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _offsets_from_rows(rows: list[dict], *, window_days: int, min_days: int) -> dict:
    rows = rows[-window_days:]
    samples: dict[str, list[float]] = {}
    for r in rows:
        for field in _LEG_FIELDS:
            v = r.get(field)
            if isinstance(v, (int, float)):
                samples.setdefault(field, []).append(float(v))

    curves: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for field, (ot, ad, bucket) in _LEG_FIELDS.items():
        vals = samples.get(field, [])
        if len(vals) < min_days:
            continue
        curves.setdefault((ot, bucket), []).append((ad, statistics.median(vals)))

    offsets = {k: sorted(v) for k, v in curves.items() if len(v) >= 2}

    if ("PUT", "25-35") not in offsets:
        raise InsufficientCalibration(
            f"skew monitor has {len(rows)} usable rows (< {min_days} per leg) — "
            f"CALIB unavailable; choose FLAT explicitly and keep collecting"
        )
    return OffsetCurves(offsets, CONV_ACT365)


def load_offsets(path: Path | None = None, *, window_days: int = DEFAULT_WINDOW_DAYS,
                 min_days: int = MIN_DAYS) -> dict:
    """offsets[(TYPE, bucket)] = ascending [(abs_delta, median_offset_vp), ...]

    Rolling median over the last `window_days` rows per leg field. A leg is
    included only if it individually has >= min_days samples; a (type, bucket)
    curve is included only if it has >= 2 legs (interpolation needs a segment).
    Raises InsufficientCalibration if NO near-bucket put curve qualifies (the
    minimum viable calibration for existing credit-structure research).
    """
    return _offsets_from_rows(_read_rows(path or SKEW_MONITOR),
                              window_days=window_days, min_days=min_days)


def load_offsets_merged(paths: list, *, window_days: int = DEFAULT_WINDOW_DAYS,
                        min_days: int = MIN_DAYS) -> tuple[dict, dict]:
    """SPEC-120 AC-5 — offsets from several JSONL sources (production monitor
    plus research backfills). Rows are deduped by date with EARLIER paths
    winning (pass the production monitor first). Days missing moff fields are
    skipped fail-soft, and the returned stats dict reports the counts so the
    caller can surface them instead of silently thinning the calibration.

    Returns (offsets, stats)."""
    by_date: dict[str, dict] = {}
    stats: dict = {"sources": [], "dupes_dropped": 0,
                   "days_total": 0, "days_no_moff": 0, "per_leg_days": {}}
    for p in paths:
        p = Path(p)
        rows = _read_rows(p)
        kept = 0
        for r in rows:
            d = str(r.get("date", ""))
            if not d:
                continue
            if d in by_date:
                stats["dupes_dropped"] += 1
                continue
            by_date[d] = r
            kept += 1
        stats["sources"].append({"path": str(p), "rows": len(rows), "kept": kept})

    merged = [by_date[d] for d in sorted(by_date)]
    stats["days_total"] = len(merged)
    stats["days_no_moff"] = sum(
        1 for r in merged if not any(f in r for f in _LEG_FIELDS))
    for field in _LEG_FIELDS:
        n = sum(1 for r in merged if isinstance(r.get(field), (int, float)))
        if n:
            stats["per_leg_days"][field] = n

    offsets = _offsets_from_rows(merged, window_days=window_days, min_days=min_days)
    return offsets, stats
