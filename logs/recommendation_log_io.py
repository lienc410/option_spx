from __future__ import annotations

import json
from pathlib import Path

from strategy.selector import Recommendation


RECOMMENDATION_LOG_FILE = Path(__file__).resolve().parent / "recommendation_log.jsonl"


def _log_path() -> Path:
    return RECOMMENDATION_LOG_FILE


def _serialize_legs(rec: Recommendation) -> list[dict]:
    return [
        {
            "action": leg.action,
            "option": leg.option,
            "dte": leg.dte,
            "delta": leg.delta,
            "note": leg.note,
        }
        for leg in rec.legs
    ]


def append_recommendation_event(
    *,
    rec: Recommendation,
    source: str,
    mode: str,
    timestamp: str,
    params_hash: str,
) -> None:
    """Append one recommendation event to logs/recommendation_log.jsonl."""
    event = {
        "timestamp": timestamp,
        "source": source,
        "mode": mode,
        "date": rec.vix_snapshot.date,
        "underlying": rec.underlying,
        "position_action": rec.position_action,
        "strategy": rec.strategy.value,
        "strategy_key": rec.strategy_key,
        "rationale": rec.rationale,
        "macro_warning": rec.macro_warning,
        "backwardation": rec.backwardation,
        "vix": rec.vix_snapshot.vix,
        "regime": rec.vix_snapshot.regime.value,
        "vix3m": rec.vix_snapshot.vix3m,
        "iv_rank": rec.iv_snapshot.iv_rank,
        "iv_percentile": rec.iv_snapshot.iv_percentile,
        "iv_signal": rec.iv_snapshot.iv_signal.value,
        "spx": rec.trend_snapshot.spx,
        "trend_signal": rec.trend_snapshot.signal.value,
        "legs": _serialize_legs(rec),
        "params_hash": params_hash,
    }

    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")
