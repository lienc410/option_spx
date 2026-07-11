"""Q042 Joint BP Gate (F3)

Combined-cap backstop that limits Q042's total BP to avoid crowding the
main strategy during high-utilisation periods.

Formula (from SPEC-094 F3, updated by SPEC-104):
  q042_combined_cap = min(12.5, max(0.0, 60.0 - main_bp_pct))

Per-sleeve allowance:
  - cap ≥ 12.5%: Sleeve A gets 12.5%, Sleeve B gets 0% production
  - cap < 12.5%: prorate Sleeve A only
  - cap = 0:    both sleeves blocked

Gate state is appended daily to data/q042_gate_log.jsonl (AC12).

AC9:  main_bp_pct = 30% → cap = 12.5%, A=12.5% / B=0% (gate not binding)
AC10: main_bp_pct = 55% → cap =  5%, A=5% / B=0%
AC11: main_bp_pct = 65% → cap =  0%, both blocked
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from strategy.q042_config import (
    Q042_SLEEVE_A_PRODUCTION_CAP_PCT,
    Q042_SLEEVE_B_PRODUCTION_CAP_PCT,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_LOG  = REPO_ROOT / "data" / "q042_gate_log.jsonl"
# SPEC-094.2 F3: account-level SPX PM BP% canonical source (bot cron 09:40 ET).
RUNTIME_STATE_PATH = REPO_ROOT / "data" / "sleeve_governance_runtime.json"
_STALE_TRADING_DAYS = 2

_COMBINED_CAP_MAX    = Q042_SLEEVE_A_PRODUCTION_CAP_PCT + Q042_SLEEVE_B_PRODUCTION_CAP_PCT
_MAIN_BP_BUDGET      = 60.0   # % — governance threshold for main strategy

ET = ZoneInfo("America/New_York")


@dataclass
class GateResult:
    date: str
    main_bp_pct: float
    q042_combined_cap: float
    sleeve_a_allowance: float
    sleeve_b_allowance: float
    gate_binding: bool


def compute_gate(main_bp_pct: float, date: str = "") -> GateResult:
    """
    Compute per-sleeve BP allowance for Q042 given main strategy BP usage.

    Args:
        main_bp_pct: Current main-strategy BP as % of account (0–100).
        date:        ISO date string for the log entry (defaults to today ET).

    Returns:
        GateResult with per-sleeve allowances.
    """
    if not date:
        date = datetime.now(ET).strftime("%Y-%m-%d")

    cap = min(_COMBINED_CAP_MAX, max(0.0, _MAIN_BP_BUDGET - main_bp_pct))
    binding = cap < _COMBINED_CAP_MAX

    if cap >= _COMBINED_CAP_MAX:
        allowance_a = Q042_SLEEVE_A_PRODUCTION_CAP_PCT
        allowance_b = Q042_SLEEVE_B_PRODUCTION_CAP_PCT
    elif cap > 0:
        allowance_a = cap * Q042_SLEEVE_A_PRODUCTION_CAP_PCT / _COMBINED_CAP_MAX
        allowance_b = cap * Q042_SLEEVE_B_PRODUCTION_CAP_PCT / _COMBINED_CAP_MAX
    else:
        allowance_a = 0.0
        allowance_b = 0.0

    return GateResult(
        date=date,
        main_bp_pct=round(main_bp_pct, 2),
        q042_combined_cap=round(cap, 2),
        sleeve_a_allowance=round(allowance_a, 2),
        sleeve_b_allowance=round(allowance_b, 2),
        gate_binding=binding,
    )


def log_gate(result: GateResult | None, bp_source: dict | None = None,
             date: str = "") -> None:
    """Append gate state to data/q042_gate_log.jsonl (AC12).

    SPEC-094.2 N12: attach a `bp_source` provenance dict (source id + snapshot
    timestamp) for staleness/口径 audit (AC-94.2-8). When `result` is None the
    gate BP read failed closed (F3) — a distinct unavailable row is written so
    the daily gate ledger stays continuous and the fail-closed event is
    auditable.
    """
    GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    if result is not None:
        row = asdict(result)
    else:
        row = {
            "date": date or datetime.now(ET).strftime("%Y-%m-%d"),
            "main_bp_pct": None,
            "q042_combined_cap": 0.0,
            "sleeve_a_allowance": 0.0,
            "sleeve_b_allowance": 0.0,
            "gate_binding": True,
            "gate_available": False,
        }
    if bp_source is not None:
        row["bp_source"] = bp_source
    with GATE_LOG.open("a") as f:
        f.write(json.dumps(row) + "\n")


def read_latest_gate_row() -> Optional[dict]:
    """最新一行联合门（F3）状态——SPEC-135.5 Lane D 联动线的唯一数据源。

    与写入方（log_gate）同居本文件：读的就是日度落盘的 gate ledger，装配层
    不重推 compute_gate 公式。跳过 blocked_fire 反事实行（那是漏单审计
    payload，不是门状态）与 ammo_advisory 行（SPEC-094.4 弹药路由建议，
    提示性 payload，不是门状态）。文件缺失 / 解析失败 → None（fail-soft）。
    """
    if not GATE_LOG.exists():
        return None
    latest: Optional[dict] = None
    try:
        with GATE_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "blocked_fire" in row or "ammo_advisory" in row:
                    continue
                latest = row
    except OSError:
        return None
    return latest


def log_blocked_fire(sleeve: str, reason: str, would_be_contracts: int,
                     ddath: float, date: str = "") -> None:
    """Append a counterfactual blocked-fire record (SPEC-094.2 F5.2).

    A trigger fired but was held (gate allowance 0 / F3 fail-closed / contracts
    0). Recorded to the same gate ledger with a `blocked_fire` payload so the
    漏单 is auditable (mirrors sleeve-governance blocked-candidate convention).
    """
    GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "date": date or datetime.now(ET).strftime("%Y-%m-%d"),
        "blocked_fire": {
            "sleeve": sleeve,
            "reason": reason,
            "would_be_contracts": int(would_be_contracts or 0),
            "ddath": round(ddath, 4),
        },
    }
    with GATE_LOG.open("a") as f:
        f.write(json.dumps(row) + "\n")


def log_ammo_advisory(advisory: dict, date: str = "") -> None:
    """Append an ammo-routing advisory record (SPEC-094.4 F1, AC-94.4-2).

    New OPTIONAL row type on the gate ledger — `ammo_advisory` payload:
    ``{sleeve, branch, episode_type, liquid, need, bps_strikes?}``。提示不拦
    （不改变 fire 语义），落盘目的是为突发型 n=4 的 paper 证据积累建管道
    （Quant standing obligation：每次新触发更新 P6 分层账本）。Readers of the
    gate ledger must treat rows carrying this key like blocked_fire rows —
    payload 行，不是门状态（read_latest_gate_row 已跳过）。
    """
    GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "date": date or datetime.now(ET).strftime("%Y-%m-%d"),
        "ammo_advisory": advisory,
    }
    with GATE_LOG.open("a") as f:
        f.write(json.dumps(row) + "\n")


def _to_float(value) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        n = float(value)
        if math.isnan(n) or math.isinf(n):
            return None
        return n
    except (TypeError, ValueError):
        return None


def _business_days_between(d0: date, d1: date) -> int:
    """Count weekday (Mon-Fri) days in the interval (d0, d1]. A holiday-free
    proxy for '交易日' — adequate for a >2-trading-day staleness gate."""
    if d1 <= d0:
        return 0
    days = 0
    cur = d0
    while cur < d1:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days


def read_main_bp_detail(now: datetime | None = None) -> dict:
    """Fail-closed read of account-level SPX PM BP% (SPEC-094.2 F3).

    Source: data/sleeve_governance_runtime.json → ``pools.spx_pm_bp_pct``
    (SPEC-103/118.2 canonical account-level maintenance-margin / NLV, 'all'
    view, persisted daily by the bot's record_state_snapshot cron). This
    replaces the old ``strategy.state.bp_pct_account`` read, which never exists
    in production (44/44 gate rows read 0.0 → gate永不 binding = fail-OPEN).

    Returns a provenance dict::

        {
          "value": float | None,     # None ⇒ data unavailable → gate fail-CLOSED
          "source": str,             # identifier for the gate log (N12)
          "timestamp": str | None,   # snapshot timestamp
          "reason": str | None,      # why unavailable (when value is None)
          "all_view_pct": float | None,
          "schwab_view_pct": float | None,
        }

    Fail-closed (value=None) when ANY of B1's conditions hold: missing/parse
    error; timestamp > 2 trading days stale; status != "available"; errors
    non-empty; basis_degraded true; degraded all-zero pool形态
    (pools_by_view.schwab null OR pools.nlv_basis missing/<=0); or the
    plausibility gate spx_pm_bp_pct <= 0.
    """
    now = now or datetime.now(ET)
    src = "sleeve_governance_runtime.pools.spx_pm_bp_pct(all)"

    def _fail(reason: str, *, timestamp=None, all_view=None, schwab_view=None) -> dict:
        return {
            "value": None, "source": src, "timestamp": timestamp,
            "reason": reason, "all_view_pct": all_view, "schwab_view_pct": schwab_view,
        }

    if not RUNTIME_STATE_PATH.exists():
        return _fail("missing_file")
    try:
        snap = json.loads(RUNTIME_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _fail("parse_error")

    ts = snap.get("timestamp")
    if not ts:
        return _fail("missing_timestamp")
    ts_norm = str(ts)
    try:
        ts_date = datetime.fromisoformat(ts_norm).date()
    except ValueError:
        return _fail("bad_timestamp", timestamp=ts_norm)
    if _business_days_between(ts_date, now.date()) > _STALE_TRADING_DAYS:
        return _fail("stale", timestamp=ts_norm)

    if snap.get("status") != "available":
        return _fail("status_not_available", timestamp=ts_norm)
    if snap.get("errors"):
        return _fail("errors_present", timestamp=ts_norm)
    if snap.get("basis_degraded"):
        return _fail("basis_degraded", timestamp=ts_norm)

    pools = snap.get("pools") or {}
    pools_by_view = snap.get("pools_by_view") or {}
    schwab_view = pools_by_view.get("schwab")
    nlv_basis = _to_float(pools.get("nlv_basis"))
    # degraded all-zero fallback形态 (sleeve_governance.py:804-811): timestamp
    # fresh but pools全零 / pools_by_view null — last-known回退 not introduced.
    if schwab_view is None or nlv_basis is None or nlv_basis <= 0:
        return _fail("degraded_pools", timestamp=ts_norm)

    all_bp = _to_float(pools.get("spx_pm_bp_pct"))
    schwab_bp = (_to_float(schwab_view.get("spx_pm_bp_pct"))
                 if isinstance(schwab_view, dict) else None)
    # plausibility gate: account maint is structurally >0 (equity in QQQ/SGOV +
    # BCD); a 0 read can only be an upstream broker field silently missing.
    if all_bp is None or all_bp <= 0:
        return _fail("nonpositive_bp", timestamp=ts_norm,
                     all_view=all_bp, schwab_view=schwab_bp)

    return {
        "value": round(all_bp, 4),
        "source": src,
        "timestamp": ts_norm,
        "reason": None,
        "all_view_pct": round(all_bp, 4),
        "schwab_view_pct": round(schwab_bp, 4) if schwab_bp is not None else None,
    }


def read_main_bp_pct(now: datetime | None = None) -> Optional[float]:
    """Account-level SPX PM BP% (all view), or None when the gate must fail
    closed. See read_main_bp_detail for the fail-closed conditions (F3/B1)."""
    return read_main_bp_detail(now)["value"]


def read_main_bp_source(now: datetime | None = None) -> dict:
    """Full provenance dict for the gate BP read (N12). See read_main_bp_detail."""
    return read_main_bp_detail(now)
