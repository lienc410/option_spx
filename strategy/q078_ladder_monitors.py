"""SPEC-108.1 R4 — Per-strategy ladder trigger distribution drift monitor.

Monitor #9: Rolling 90-day strategy share vs historical baseline.
Alert trigger: any strategy share deviates > 15pp from its historical band edge.

Historical bands derived from research/q078/_signal_history_cache.csv (26y, 3119 PASS days):
  bull_call_diagonal: 56.0%  → band 51-61%
  iron_condor_hv:     19.5%  → band 14.5-24.5%
  iron_condor:         9.5%  → band 4.5-14.5%
  bull_put_spread_hv:  9.3%  → band 4.3-14.3%
  bull_put_spread:     3.1%  → band 0.0-8.1%
  bear_call_spread_hv: 2.6%  → band 0.0-7.6%
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
SHADOW_LOG_PATH = DATA_DIR / "q078_ladder_shadow.jsonl"

DRIFT_THRESHOLD_PP = 15.0
ROLLING_WINDOW_DAYS = 90

# Historical bands (low, high) derived from 26y signal cache
# Computed as centre_pct ± 5pp, floor 0.
HISTORICAL_STRATEGY_BANDS: dict[str, tuple[float, float]] = {
    "bull_call_diagonal": (51.0, 61.0),
    "iron_condor_hv":     (14.5, 24.5),
    "iron_condor":        (4.5,  14.5),
    "bull_put_spread_hv": (4.3,  14.3),
    "bull_put_spread":    (0.0,   8.1),
    "bear_call_spread_hv":(0.0,   7.6),
}


def _read_jsonl_tail(path: Path, days: int = ROLLING_WINDOW_DAYS) -> list[dict]:
    if not path.exists():
        return []
    cutoff = date.today() - timedelta(days=days)
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    row_date_str = row.get("date") or ""
                    try:
                        row_date = date.fromisoformat(row_date_str[:10])
                    except ValueError:
                        continue
                    if row_date >= cutoff:
                        rows.append(row)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows


def strategy_distribution_check(shadow_log_path: Path | None = None) -> dict:
    """SPEC-108.1 R4: rolling 90-day strategy distribution vs historical bands.

    Returns:
        {
          "drift_alert": bool,
          "distribution_90d": {strategy_key: pct_float},
          "drift_detail": {strategy_key: {"share": pct, "band": (lo, hi), "deviation_pp": float}},
          "total_entries_90d": int,
        }
    """
    path = shadow_log_path or SHADOW_LOG_PATH
    rows = _read_jsonl_tail(path)

    # Only count would-enter=True rows (actual shadow firings, not skips)
    entries = [r for r in rows if r.get("would_enter")]
    total = len(entries)

    if total == 0:
        return {
            "drift_alert": False,
            "distribution_90d": {},
            "drift_detail": {},
            "total_entries_90d": 0,
            "note": "no_shadow_entries_in_window",
        }

    from collections import Counter
    counts: Counter[str] = Counter()
    for row in entries:
        key = str(row.get("selector_strategy_key") or row.get("strategy_key") or "unknown")
        if not key or key == "reduce_wait":
            continue
        counts[key] += 1

    distribution: dict[str, float] = {k: round(v / total * 100.0, 1) for k, v in counts.items()}
    drift_detail: dict[str, Any] = {}
    drift_alert = False

    for strategy, band in HISTORICAL_STRATEGY_BANDS.items():
        share = distribution.get(strategy, 0.0)
        lo, hi = band
        dev_below = max(0.0, lo - share - DRIFT_THRESHOLD_PP)  # how far below band-lo-15pp
        dev_above = max(0.0, share - hi - DRIFT_THRESHOLD_PP)  # how far above band-hi+15pp
        # Actual deviation from nearest band edge
        if share < lo:
            dev_pp = lo - share  # below lower edge
        elif share > hi:
            dev_pp = share - hi  # above upper edge
        else:
            dev_pp = 0.0
        triggered = dev_below > 0 or dev_above > 0
        if triggered:
            drift_alert = True
        drift_detail[strategy] = {
            "share": share,
            "band": list(band),
            "deviation_pp": round(dev_pp, 1),
            "alert": triggered,
        }

    # Also flag strategies not in bands that appear significantly (> 15pp)
    for key, share in distribution.items():
        if key not in HISTORICAL_STRATEGY_BANDS and share > DRIFT_THRESHOLD_PP:
            drift_alert = True
            drift_detail[key] = {
                "share": share,
                "band": None,
                "deviation_pp": share,
                "alert": True,
                "note": "not_in_historical_bands",
            }

    return {
        "drift_alert": drift_alert,
        "distribution_90d": distribution,
        "drift_detail": drift_detail,
        "total_entries_90d": total,
    }
