from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
RUNTIME_STATE_PATH = DATA_DIR / "q078_ladder_runtime.json"
SHADOW_LOG_PATH = DATA_DIR / "q078_ladder_shadow.jsonl"

_HOLIDAYS = {
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}


def _constants() -> tuple[int, int, float]:
    from strategy.sleeve_governance import (
        LADDER_BP_CEILING_PCT,
        LADDER_CADENCE_CLUSTER_DAYS,
        LADDER_SIZING_CONTRACTS,
    )

    return LADDER_SIZING_CONTRACTS, LADDER_CADENCE_CLUSTER_DAYS, LADDER_BP_CEILING_PCT


def _mode() -> str:
    from strategy.sleeve_governance import ladder_mode

    return ladder_mode()


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def is_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day.isoformat() not in _HOLIDAYS


def trading_days_between(start: date | str, end: date | str) -> int:
    """Trading days after `start` through `end`, inclusive of `end`."""
    start_d = _as_date(start)
    end_d = _as_date(end)
    if start_d is None or end_d is None or end_d <= start_d:
        return 0
    cur = start_d
    count = 0
    from datetime import timedelta

    while cur < end_d:
        cur = cur + timedelta(days=1)
        if is_trading_day(cur):
            count += 1
    return count


def _strategy_name(verdict: Any) -> str:
    if verdict is None:
        return ""
    if isinstance(verdict, dict):
        value = verdict.get("strategy_name") or verdict.get("strategy") or verdict.get("strategy_value")
    else:
        value = getattr(verdict, "strategy_name", None) or getattr(verdict, "strategy", None)
    if hasattr(value, "value"):
        value = value.value
    return str(value or "")


def _strategy_key(verdict: Any) -> str:
    if verdict is None:
        return ""
    if isinstance(verdict, dict):
        value = verdict.get("strategy_key") or verdict.get("key")
    else:
        value = getattr(verdict, "strategy_key", None)
    return str(value or "")


def _max_loss_per_contract(verdict: Any) -> float:
    for key in ("max_loss_per_contract", "bp_per_contract", "requested_bp_per_contract"):
        value = verdict.get(key) if isinstance(verdict, dict) else getattr(verdict, key, None)
        try:
            if value not in (None, ""):
                return max(0.0, float(value))
        except (TypeError, ValueError):
            pass
    return 9000.0


def _entry_credit_per_contract(verdict: Any) -> float | None:
    for key in ("entry_credit_per_contract", "theoretical_entry_credit", "credit_per_contract"):
        value = verdict.get(key) if isinstance(verdict, dict) else getattr(verdict, key, None)
        try:
            if value not in (None, ""):
                return float(value)
        except (TypeError, ValueError):
            pass
    return None


def _selector_wait(strategy_name: str, strategy_key: str) -> bool:
    return strategy_name in {"Reduce / Wait", "REDUCE_WAIT"} or strategy_key == "reduce_wait"


@dataclass
class LadderState:
    last_entry_date: date | str | None = None
    active_positions: list[dict] = field(default_factory=list)
    current_bp_pct_nlv_value: float = 0.0
    nlv: float = 100_000.0
    action_days_ytd: int = 0
    path: Path = RUNTIME_STATE_PATH

    @classmethod
    def load(
        cls,
        path: Path = RUNTIME_STATE_PATH,
        *,
        active_positions: list[dict] | None = None,
        current_bp_pct_nlv: float | None = None,
        nlv: float | None = None,
    ) -> "LadderState":
        payload: dict[str, Any] = {}
        try:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        return cls(
            last_entry_date=payload.get("last_entry_date"),
            active_positions=active_positions if active_positions is not None else list(payload.get("active_positions") or []),
            current_bp_pct_nlv_value=float(current_bp_pct_nlv if current_bp_pct_nlv is not None else payload.get("current_bp_pct_nlv", 0.0) or 0.0),
            nlv=float(nlv if nlv is not None else payload.get("nlv", 100_000.0) or 100_000.0),
            action_days_ytd=int(payload.get("action_days_ytd", 0) or 0),
            path=path,
        )

    def same_strategy_position_count(self, strategy_name: str, strategy_key: str = "") -> int:
        name = str(strategy_name or "").strip()
        key = str(strategy_key or "").strip()
        return sum(
            1
            for pos in self.active_positions
            if str(pos.get("strategy") or pos.get("strategy_name") or pos.get("name") or "").strip() == name
            or (key and str(pos.get("strategy_key") or "").strip() == key)
            or (not key and str(pos.get("strategy_key") or "").strip() == name)
        )

    def current_bp_used_pct_nlv(self) -> float:
        return float(self.current_bp_pct_nlv_value or 0.0)

    def existing_spx_positions(self) -> int:
        return len(self.active_positions)

    def mark_entry(self, entry_date: date | str, strategy_name: str, *, mode: str) -> None:
        entry = _as_date(entry_date)
        if entry is None:
            return
        year = entry.year
        last = _as_date(self.last_entry_date)
        if last != entry:
            self.action_days_ytd = 1 if last is None or last.year != year else int(self.action_days_ytd or 0) + 1
        self.last_entry_date = entry
        payload = {
            "last_entry_date": entry.isoformat(),
            "last_entry_strategy": strategy_name,
            "last_entry_mode": mode,
            "action_days_ytd": self.action_days_ytd,
            "current_bp_pct_nlv": self.current_bp_used_pct_nlv(),
            "nlv": self.nlv,
            "updated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)


def v3_ladder_eligible(market_state: Any, ladder_state: LadderState) -> tuple[bool, str]:
    sizing_contracts, cluster_days, bp_ceiling = _constants()
    if not isinstance(market_state, dict):
        market_state = vars(market_state)
    today = _as_date(market_state.get("date")) or date.today()
    last_entry = _as_date(ladder_state.last_entry_date)
    if last_entry is not None and trading_days_between(last_entry, today) < cluster_days:
        return False, "cadence_gap"

    selector_verdict = market_state.get("selector_verdict") or {}
    strategy_name = _strategy_name(selector_verdict)
    strategy_key = _strategy_key(selector_verdict)
    if _selector_wait(strategy_name, strategy_key):
        return False, "selector_wait"

    cap = 2 if strategy_name == "Iron Condor (High Vol)" or strategy_key == "iron_condor_hv" else 1
    if ladder_state.same_strategy_position_count(strategy_name, strategy_key) >= cap:
        return False, "concurrency_block"

    max_loss = _max_loss_per_contract(selector_verdict)
    nlv = max(float(ladder_state.nlv or 100_000.0), 1.0)
    new_max_loss_pct = sizing_contracts * max_loss / nlv * 100.0
    if ladder_state.current_bp_used_pct_nlv() + new_max_loss_pct > bp_ceiling:
        return False, "bp_ceiling_block"

    return True, ""


def production_order_allowed(eligible: bool, mode: str | None = None) -> bool:
    return bool(eligible and (mode or _mode()) == "active")


def append_shadow_log(payload: dict, path: Path | None = None) -> None:
    path = path or SHADOW_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(payload, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def has_shadow_log_for_date(log_date: date | str, path: Path | None = None) -> bool:
    path = path or SHADOW_LOG_PATH
    target = (_as_date(log_date) or date.today()).isoformat()
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in reversed(f.readlines()[-25:]):
                try:
                    if json.loads(line).get("date") == target:
                        return True
                except json.JSONDecodeError:
                    continue
    except OSError:
        return False
    return False


def shadow_payload(market_state: dict, ladder_state: LadderState, *, eligible: bool, skip_reason: str, mode: str) -> dict:
    sizing_contracts, _, _ = _constants()
    selector_verdict = market_state.get("selector_verdict") or {}
    max_loss = _max_loss_per_contract(selector_verdict)
    nlv = max(float(ladder_state.nlv or 100_000.0), 1.0)
    strategy_name = _strategy_name(selector_verdict)
    return {
        "date": (_as_date(market_state.get("date")) or date.today()).isoformat(),
        "ladder_mode": mode,
        "selector_timestamp": market_state.get("selector_timestamp") or datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "selector_strategy": strategy_name,
        "would_enter": bool(eligible),
        "skip_reason": skip_reason or None,
        "sizing_contracts": sizing_contracts,
        "theoretical_max_loss": round(sizing_contracts * max_loss, 2),
        "theoretical_max_loss_pct_nlv": round(sizing_contracts * max_loss / nlv * 100.0, 2),
        "theoretical_entry_credit": _entry_credit_per_contract(selector_verdict),
        "theoretical_exit_rule": "SPEC-077",
        "current_bp_pct_nlv": round(ladder_state.current_bp_used_pct_nlv(), 2),
        "q042_active": bool(market_state.get("q042_active", False)),
        "existing_spx_positions": ladder_state.existing_spx_positions(),
        "ladder_action_days_ytd": int(ladder_state.action_days_ytd or 0) + (1 if eligible else 0),
    }
