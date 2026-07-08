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
        # SPEC-135 — Decision Trace（生产代码自吐的评估节点链，strict-JSON；
        # /api/decision-trace 的历史数据源）
        "trace": list(getattr(rec, "trace", None) or []),
    }
    _assert_finite(event)

    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")


def _assert_finite(obj, path: str = "event") -> None:
    """SPEC-135: trace 落盘前 strict-JSON 断言（NaN/Inf 不入 jsonl）。"""
    import math
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError(f"non-finite at {path}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_finite(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_finite(v, f"{path}[{i}]")


def read_events(dates: set[str] | None = None) -> list[dict]:
    """SPEC-135 — 读回推荐事件（可按日期集过滤）。坏行跳过。"""
    path = _log_path()
    out: list[dict] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if dates is None or ev.get("date") in dates:
                out.append(ev)
    return out
