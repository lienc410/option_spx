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
    lane_b: list[dict] | None = None,
) -> None:
    """Append one recommendation event to logs/recommendation_log.jsonl.

    SPEC-139 §3 — optional `lane_b` snapshot (当日持仓动作触发器读数，
    lane_b_positions 输出的同形 list) 一并落盘，使 /api/decision-trace 回放历史日
    时 Lane B 有据可依。纯附加字段：只有显式传入时才写 key，既有行逐字节不变；
    未传入的旧行回放时如实标注降级。"""
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
    # SPEC-139 §3 — Lane B 历史快照（纯附加；None 时不写 key → 旧行语义不变）
    if lane_b is not None:
        event["lane_b"] = list(lane_b)
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
