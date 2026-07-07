"""SPEC-107 intraday recommendation governance.

This module wraps the raw SPX selector recommendation with execution
governance only. It does not change selector semantics.

Default posture:
- A2a IVP hysteresis: entry [42, 53], hold [35, 57]
- Actionable decisions only at 10:30 / 15:30 ET
- Hard-risk bypasses may be actionable immediately

Changing INTRADAY_HYS_LOWER_FORCE_CLOSE away from the SPEC default True
requires Q077 approval / a separate SPEC.
"""

from __future__ import annotations

import json
import math
import os
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

from strategy.selector import DEFAULT_PARAMS

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
STATE_PATH = DATA_DIR / "intraday_governance_state.json"
DECISION_LOG_PATH = DATA_DIR / "intraday_governance_log.jsonl"

ET = ZoneInfo("America/New_York")

INTRADAY_HYS_ENTRY_LOW = float(os.getenv("INTRADAY_HYS_ENTRY_LOW", "42.0"))
INTRADAY_HYS_ENTRY_HIGH = float(os.getenv("INTRADAY_HYS_ENTRY_HIGH", "53.0"))
INTRADAY_HYS_HOLD_LOW = float(os.getenv("INTRADAY_HYS_HOLD_LOW", "35.0"))
INTRADAY_HYS_HOLD_HIGH = float(os.getenv("INTRADAY_HYS_HOLD_HIGH", "57.0"))
INTRADAY_HYS_LOWER_FORCE_CLOSE = os.getenv("INTRADAY_HYS_LOWER_FORCE_CLOSE", "true").strip().lower() not in {
    "0",
    "false",
    "no",
}
INTRADAY_SCHED_BARS_ET = tuple(
    s.strip()
    for s in os.getenv("INTRADAY_SCHED_BARS_ET", "10:30,15:30").split(",")
    if s.strip()
)

BYPASS_TYPES = {
    "manual_override",
    "broker_stop_loss",
    "lifecycle_exit",
    "spec_103_r5",
    "spec_103_r6",
    "extreme_vol",
    "selector_hard_exit",
    "stale_data_failsafe",
    None,
}


@dataclass
class GovernanceDecision:
    timestamp: str
    bar_hm: str
    is_scheduled_bar: bool
    is_bypass_event: bool
    bypass_reason: str | None
    bypass_type: str | None
    vix: float | None
    ivp252: float | None
    regime: str
    selector_baseline_strategy: str
    selector_baseline_position_action: str
    selector_baseline_rationale: str
    hysteresis_state_prev: str
    hysteresis_state_new: str
    governed_strategy: str
    governed_position_action: str
    actionable: bool
    override_baseline: bool
    last_actionable_decision_at: str | None
    next_actionable_decision_at: str | None
    final_priority_layer: int
    final_priority_name: str
    state_key: str
    state_corrupt: bool = False
    event: str = "decision"


def _now() -> datetime:
    return datetime.now(ET)


def _bool_payload(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "active"}


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        number = float(value)
        return number if not math.isnan(number) else None
    except (TypeError, ValueError):
        return None


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value) or "")


def _strategy_value(rec: Any) -> str:
    strategy = getattr(rec, "strategy", None)
    return str(getattr(strategy, "value", strategy) or "")


def _state_key(rec: Any, position: dict | None = None) -> str:
    # SPEC-107 hysteresis tracks the per-strategy IVP state machine, NOT
    # per-position lifecycle. There is at most one BPS-Normal position at a
    # time on SPX, so the state key must remain stable across:
    #   - position-open ↔ position-closed transitions
    #   - baseline regime changes (BPS ↔ Wait ↔ Iron Condor) which would
    #     otherwise flip rec.underlying from "SPX" to "—" and lose memory
    # Hence the key is fixed to (account, underlying, strategy) only.
    position = position or {}
    account = str(position.get("account") or "spx")
    underlying = str(position.get("underlying") or "SPX")
    strategy = str(position.get("strategy_key") or "bull_put_spread")
    return "|".join([account, underlying, strategy])


def _load_state() -> tuple[dict, bool]:
    if not STATE_PATH.exists():
        return {"schema": 1, "positions": {}, "last_actionable_decision_at": None}, False
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != 1 or not isinstance(payload.get("positions"), dict):
            return {"schema": 1, "positions": {}, "last_actionable_decision_at": None}, True
        return payload, False
    except Exception:
        return {"schema": 1, "positions": {}, "last_actionable_decision_at": None}, True


def _write_state(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def _append_jsonl(path: Path, payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def _telegram_alert(text: str) -> bool:
    # SPEC-126: hard-exit bypasses ring as ALERT; other decisions ACTION.
    try:
        from notify.gateway import push as gw_push
        cat = "ALERT" if ("🚨" in text or "Hard Exit" in text) else "ACTION"
        return bool(gw_push(cat, "系统状态", "", text))
    except Exception:
        return False


@lru_cache(maxsize=256)
def _nyse_schedule(start_day: date, end_day: date):
    cal = mcal.get_calendar("NYSE")
    return cal.schedule(start_date=start_day.isoformat(), end_date=end_day.isoformat())


def _as_et(ts: Any) -> datetime:
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(ET)


@lru_cache(maxsize=512)
def scheduled_bars_for_day(day: date) -> list[datetime]:
    schedule = _nyse_schedule(day, day)
    if schedule.empty:
        return []
    row = schedule.iloc[0]
    close_et = _as_et(row["market_close"])
    bars: list[datetime] = []
    for hm in INTRADAY_SCHED_BARS_ET:
        hh, mm = [int(x) for x in hm.split(":", 1)]
        candidate = datetime.combine(day, time(hh, mm), ET)
        if candidate <= close_et - timedelta(minutes=30):
            bars.append(candidate)
    if close_et.time() < time(16, 0):
        fallback = close_et - timedelta(minutes=30)
        if fallback.date() == day and fallback not in bars:
            bars.append(fallback)
    bars.sort()
    return bars


def is_scheduled_bar(now: datetime | None = None, tolerance_min: int = 30) -> bool:
    now = now or _now()
    for bar in scheduled_bars_for_day(now.date()):
        delta = abs((now - bar).total_seconds()) / 60.0
        if delta < tolerance_min and now >= bar:
            return True
    return False


def next_actionable_time(now: datetime | None = None) -> datetime | None:
    now = now or _now()
    for offset in range(0, 14):
        day = now.date() + timedelta(days=offset)
        for bar in scheduled_bars_for_day(day):
            if bar > now:
                return bar
    return None


def _is_bps(rec: Any) -> bool:
    return str(getattr(rec, "strategy_key", "") or "") == "bull_put_spread"


def _wait_strategy() -> str:
    return "Reduce / Wait"


def _apply_hysteresis(
    rec: Any,
    *,
    state_payload: dict,
    key: str,
    active_position: bool,
) -> tuple[str, str, str, bool]:
    """Return prev_state, new_state, governed_strategy, override_baseline."""
    baseline_strategy = _strategy_value(rec)
    baseline_action = str(getattr(rec, "position_action", "") or "")
    baseline_is_bps = _is_bps(rec) and baseline_action in {"OPEN", "HOLD"}
    ivp = _safe_float(getattr(getattr(rec, "iv_snapshot", None), "iv_percentile", None))
    regime = _enum_value(getattr(getattr(rec, "vix_snapshot", None), "regime", ""))

    # Hysteresis state is independent of broker active_position (SPEC-107 §A
    # state persistence). Reading it directly lets the state machine remember
    # BPS hold across transient WAIT decisions and across position-open ↔
    # position-closed boundaries (e.g., sched-bar decides to open BPS; broker
    # opens position downstream; next bar must see prev=BPS, not WAIT).
    positions = state_payload.setdefault("positions", {})
    prev = str((positions.get(key) or {}).get("state") or "WAIT")

    # SPEC-107 is SPX BPS hysteresis only. It must not convert HIGH_VOL/STRESS
    # non-BPS selector verdicts into BPS holds.
    if regime != "NORMAL":
        new = "WAIT" if not baseline_is_bps else "Bull Put Spread"
        governed = baseline_strategy
    elif ivp is None:
        new = "WAIT"
        governed = baseline_strategy
    elif prev == "Bull Put Spread":
        upper_close = ivp > INTRADAY_HYS_HOLD_HIGH
        lower_close = ivp < INTRADAY_HYS_HOLD_LOW and INTRADAY_HYS_LOWER_FORCE_CLOSE
        if upper_close or lower_close:
            new = "WAIT"
            governed = _wait_strategy()
        elif INTRADAY_HYS_HOLD_LOW <= ivp <= INTRADAY_HYS_HOLD_HIGH:
            new = "Bull Put Spread"
            governed = "Bull Put Spread"
        else:
            new = "WAIT"
            governed = baseline_strategy
    elif baseline_is_bps and INTRADAY_HYS_ENTRY_LOW <= ivp <= INTRADAY_HYS_ENTRY_HIGH:
        new = "Bull Put Spread"
        governed = "Bull Put Spread"
    else:
        new = "WAIT"
        # SPEC-107 §A entry band: refuse BPS open when IVP outside [ENTRY_LOW, ENTRY_HIGH].
        # If baseline pushes BPS but entry band rejects, governed must be Wait, NOT baseline.
        # Only defer to baseline when baseline itself is not BPS (e.g., Iron Condor / BCD).
        governed = _wait_strategy() if baseline_is_bps else baseline_strategy

    # SPEC-107 hysteresis state must persist independently of broker
    # active_position: when hysteresis transitions to BPS at a sched bar but the
    # broker position is not yet open (opens downstream after the actionable
    # signal), the state still needs to be recorded so the next bar can read it.
    # Only clear the state when hysteresis itself returns to WAIT.
    if new == "WAIT":
        positions.pop(key, None)
    else:
        positions[key] = {
            "state": new,
            "updated_at": _now().isoformat(timespec="seconds"),
        }

    return prev, new, governed, governed != baseline_strategy


def _detect_bypass(rec: Any, context: dict | None = None) -> tuple[int | None, str | None, str | None]:
    context = context or {}
    if _bool_payload(context.get("manual_override")):
        return 1, "manual_override", "manual_override"
    if _bool_payload(context.get("broker_stop_loss")):
        return 2, "broker_stop_loss_or_lifecycle", "broker_stop_loss"
    if _bool_payload(context.get("lifecycle_exit")):
        return 2, "broker_stop_loss_or_lifecycle", "lifecycle_exit"
    if _bool_payload(context.get("spec_103_r5")):
        return 3, "spec_103_hard_risk_daemon", "spec_103_r5"
    if _bool_payload(context.get("spec_103_r6")):
        return 3, "spec_103_hard_risk_daemon", "spec_103_r6"
    if _bool_payload(context.get("stale_data_failsafe")):
        return 1, "manual_override", "stale_data_failsafe"
    vix = _safe_float(getattr(getattr(rec, "vix_snapshot", None), "vix", None))
    if vix is not None and vix >= float(DEFAULT_PARAMS.extreme_vix):
        return 4, "extreme_vol", "extreme_vol"
    if _bool_payload(getattr(rec, "hard_exit", False)) or _bool_payload(context.get("selector_hard_exit")):
        return 4, "extreme_vol", "selector_hard_exit"
    return None, None, None


def evaluate_recommendation(
    rec: Any,
    *,
    now: datetime | None = None,
    position: dict | None = None,
    context: dict | None = None,
    write_log: bool = True,
) -> GovernanceDecision:
    now = now or _now()
    context = context or {}
    state_payload, corrupt = _load_state()
    key = _state_key(rec, position)
    active_position = bool(position and position.get("status", "open") != "closed")
    nxt = None
    stale_calendar = False
    try:
        nxt = next_actionable_time(now)
    except Exception:
        stale_calendar = True
        context = {**context, "stale_data_failsafe": True}

    bypass_layer, bypass_name, bypass_type = _detect_bypass(rec, context)
    baseline_strategy = _strategy_value(rec)
    baseline_action = str(getattr(rec, "position_action", "") or "")

    if corrupt:
        _telegram_alert("🚨 <b>SPEC-107 state corruption</b> — falling back to raw selector / WAIT-safe governance.")

    if INTRADAY_HYS_LOWER_FORCE_CLOSE is not True and not state_payload.get("flag_override_alerted"):
        _telegram_alert(
            "⚠️ <b>SPEC-107 config override</b>: INTRADAY_HYS_LOWER_FORCE_CLOSE is not True. Q077 approval required."
        )
        _append_jsonl(DECISION_LOG_PATH, {
            "timestamp": now.isoformat(timespec="seconds"),
            "event": "flag_override_detected",
            "flag": "INTRADAY_HYS_LOWER_FORCE_CLOSE",
            "value": INTRADAY_HYS_LOWER_FORCE_CLOSE,
        })
        state_payload["flag_override_alerted"] = True

    previous_actionable_at = state_payload.get("last_actionable_decision_at")
    scheduled = False if stale_calendar else is_scheduled_bar(now)
    calc_payload = state_payload if (scheduled or bypass_layer is not None) else deepcopy(state_payload)
    if corrupt:
        prev_state = "WAIT"
        new_state = "WAIT"
        governed_strategy = baseline_strategy
        override = False
    else:
        prev_state, new_state, governed_strategy, override = _apply_hysteresis(
            rec,
            state_payload=calc_payload,
            key=key,
            active_position=active_position,
        )

    if bypass_layer is not None:
        priority_layer = bypass_layer
        priority_name = bypass_name or "raw_selector"
        actionable = True
        final_strategy = baseline_strategy
        final_action = baseline_action
    elif scheduled:
        priority_layer = 5
        priority_name = "spec_107_scheduled_actionable"
        actionable = True
        final_strategy = governed_strategy
        final_action = baseline_action if governed_strategy == baseline_strategy else "WAIT"
    elif override:
        priority_layer = 6
        priority_name = "spec_107_hysteresis"
        actionable = False
        final_strategy = state_payload.get("last_actionable_strategy") or governed_strategy
        final_action = state_payload.get("last_actionable_position_action") or (
            baseline_action if governed_strategy == baseline_strategy else "WAIT"
        )
    else:
        priority_layer = 7
        priority_name = "raw_selector"
        actionable = False
        final_strategy = state_payload.get("last_actionable_strategy") or baseline_strategy
        final_action = state_payload.get("last_actionable_position_action") or baseline_action

    if actionable:
        state_payload["last_actionable_decision_at"] = now.isoformat(timespec="seconds")
        state_payload["last_actionable_strategy"] = final_strategy
        state_payload["last_actionable_position_action"] = final_action
    state_payload["last_seen_at"] = now.isoformat(timespec="seconds")
    _write_state(state_payload)

    decision = GovernanceDecision(
        timestamp=now.isoformat(timespec="seconds"),
        bar_hm=now.strftime("%H:%M"),
        is_scheduled_bar=scheduled,
        is_bypass_event=bypass_layer is not None,
        bypass_reason=bypass_name,
        bypass_type=bypass_type if bypass_type in BYPASS_TYPES else "stale_data_failsafe",
        vix=_safe_float(getattr(getattr(rec, "vix_snapshot", None), "vix", None)),
        ivp252=_safe_float(getattr(getattr(rec, "iv_snapshot", None), "iv_percentile", None)),
        regime=_enum_value(getattr(getattr(rec, "vix_snapshot", None), "regime", "")),
        selector_baseline_strategy=baseline_strategy,
        selector_baseline_position_action=baseline_action,
        selector_baseline_rationale=str(getattr(rec, "rationale", "") or ""),
        hysteresis_state_prev=prev_state,
        hysteresis_state_new=new_state,
        governed_strategy=final_strategy,
        governed_position_action=final_action,
        actionable=actionable,
        override_baseline=override or final_strategy != baseline_strategy or final_action != baseline_action,
        last_actionable_decision_at=previous_actionable_at,
        next_actionable_decision_at=nxt.isoformat(timespec="seconds") if nxt else None,
        final_priority_layer=priority_layer,
        final_priority_name=priority_name,
        state_key=key,
        state_corrupt=corrupt or stale_calendar,
    )
    if write_log:
        _append_jsonl(DECISION_LOG_PATH, asdict(decision))
    return decision


def decision_payload(decision: GovernanceDecision) -> dict:
    return asdict(decision)
