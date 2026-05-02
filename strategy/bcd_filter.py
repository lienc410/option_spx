"""BCD comfortable-top entry filter (SPEC-079)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import json
from pathlib import Path

# Risk-score thresholds (来自 Q038 walk-forward, 不允许修改)
_VIX_HIGH   = 15.0    # VIX ≤ this = complacent (condition 1)
_DIST_HIGH  = -0.01   # dist_30d_high_pct ≤ this = pulled back ≥1% from 30d high (condition 2)
_MA50_GAP   = 0.015   # ma_gap_pct > this = >1.5pp above MA50 (condition 3)

_SHADOW_LOG = Path("data/bcd_filter_shadow.jsonl")


def bcd_risk_score(vix: float, dist_30d_high_pct: Optional[float], ma_gap_pct: float) -> int:
    """Return risk score 0-3; score == 3 triggers filter."""
    score = 0
    if vix <= _VIX_HIGH:
        score += 1
    if dist_30d_high_pct is not None and dist_30d_high_pct <= _DIST_HIGH:
        score += 1
    if ma_gap_pct > _MA50_GAP:
        score += 1
    return score


def should_block_bcd(
    mode: str,          # "disabled" | "shadow" | "active"
    vix: float,
    dist_30d_high_pct: Optional[float],
    ma_gap_pct: float,
    date: str = "",
) -> bool:
    """
    Returns True if BCD entry should be blocked.
    Shadow mode: logs but returns False (does not actually block).
    Active mode: logs and returns True when risk_score == 3.
    """
    if mode == "disabled":
        return False
    score = bcd_risk_score(vix, dist_30d_high_pct, ma_gap_pct)
    would_block = (score == 3)
    if mode in ("shadow", "active"):
        _log_shadow(date, vix, dist_30d_high_pct, ma_gap_pct, score, would_block, mode)
    return would_block and (mode == "active")


def _log_shadow(date, vix, dist, gap, score, would_block, mode):
    try:
        _SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "date": date, "mode": mode, "vix": vix,
            "dist_30d_high_pct": dist, "ma_gap_pct": gap,
            "risk_score": score, "would_block": bool(would_block),
        }
        with _SHADOW_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass
