"""Q042 Dual-Sleeve Directional Trigger (F1)

Two independent state machines:

  Sleeve A — q042_sleeve_a_dd4_lenient
    Trigger : ddATH ≤ -4% (first crossing)
    Re-arm  : ddATH ≥ -2% after position closes
    MA filter: none — T+1 open immediately

  Sleeve B — q042_sleeve_b_ladder (SPEC-094.7, Q102 P2 门槛判定落地)
    Rungs   : ddATH ≤ {-15%, -25%, -35%, -45%} — 每档独立 armed，touch 即
              fire（T+1，immediate；MA10 reclaim 机制已删——Q102 P1 证明
              深档 reclaim 全部踩在熊市反弹顶）
    Re-arm  : ddATH ≥ -2% → 全体 rung 复位（每档每周期一发）
    结构路由 : rung -15% → SPX ATM/+5% spread D90；rung ≤ -25% →
              XSP ITM85 LEAP D730（strategy/q042_sizing 单真值）

ddATH = SPX_close / running_ATH_since_2007 - 1

State is persisted to data/q042_state.json so that process restarts
do not reset the armed flags. sleeve_b schema v2 (rungs dict)；v1 →
v2 迁移在 load 路径完成。
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = REPO_ROOT / "data" / "q042_state.json"

# ATH seed: SPX all-time-high as of 2026-05-10
_ATH_SEED_DATE = "2007-01-01"
_REARM_THRESHOLD = -0.02   # ddATH ≥ -2% to re-arm
_DD4_THRESHOLD   = -0.04   # Sleeve A trigger
# SPEC-094.7 Sleeve B ladder（结构性 10pp 步长，Q102 预注册值，禁拟合调整）
_B_RUNGS         = (-0.15, -0.25, -0.35, -0.45)
_B_STOP_FLOOR    = -0.55   # 最深档的击穿告警下界（F3）
_DD15_THRESHOLD  = _B_RUNGS[0]   # legacy alias（浅档 = 原 outer trigger）
_WATCH_DAYS      = 30      # legacy（v1 reclaim 机制已删；保留常量防外部 import 断裂）
_MA10_WINDOW     = 10      # legacy（同上）


def _rung_key(rung: float) -> str:
    """-0.15 → \"-15\"（state JSON 键；整数百分比，阶梯为结构性整数步长）。"""
    return str(int(round(rung * 100)))


def rung_breach_level(rung: float) -> float:
    """持仓 rung 的击穿告警线 = 下一档 rung（最深档 → _B_STOP_FLOOR）。"""
    idx = _B_RUNGS.index(rung)
    return _B_RUNGS[idx + 1] if idx + 1 < len(_B_RUNGS) else _B_STOP_FLOOR


@dataclass
class SleeveState:
    sleeve_id: str
    armed: bool
    in_watching: bool
    watch_start_date: Optional[str]
    active_position_id: Optional[str]
    active_position_expiry: Optional[str]


@dataclass
class Q042Snapshot:
    date: str
    spx_close: float
    ath_running_max: float
    ddath: float
    sleeve_a: SleeveState
    sleeve_b: SleeveState
    combined_bp_pct: float
    ath_degraded: bool = False   # SPEC-094.2 F7: state ATH missing/0 (see snapshot)
    sleeve_b_rungs: dict = None  # SPEC-094.7: 阶梯全量 {"-15": {...}, ...}

    def __str__(self) -> str:
        return (
            f"[{self.date}] SPX {self.spx_close:.0f} | ATH {self.ath_running_max:.0f} | "
            f"ddATH {self.ddath*100:+.2f}% | "
            f"A={self.sleeve_a.armed}/pos={self.sleeve_a.active_position_id} | "
            f"B={self.sleeve_b.armed}/watch={self.sleeve_b.in_watching}/pos={self.sleeve_b.active_position_id}"
        )


# ── State persistence ────────────────────────────────────────────────────────

def _default_sleeve_b() -> dict:
    return {
        "schema": 2,
        "rungs": {_rung_key(r): {"armed": True, "active_position_id": None,
                                 "active_position_expiry": None}
                  for r in _B_RUNGS},
        "breach_alerted": [],
    }


def _default_state() -> dict:
    return {
        "ath_running_max": 0.0,
        "ath_last_update": "",
        "sleeve_a": {
            "armed": True,
            "active_position_id": None,
            "active_position_expiry": None,
        },
        "sleeve_b": _default_sleeve_b(),
        "combined_bp_pct": 0.0,
    }


def migrate_sleeve_b(sb: dict) -> dict:
    """v1（armed/in_watching/单仓）→ v2（rungs 阶梯）。幂等；v2 原样返回。

    映射：v1 的 armed 与在场仓位归 -15 档（v1 只有一个 outer trigger）；
    深档全新 armed=True；in_watching 丢弃（reclaim 机制已删——若正处
    watching，v1 语义下 armed 已 False，migration 后 -15 档不 armed，
    与"本周期已触发过"一致）。
    """
    if not isinstance(sb, dict) or sb.get("schema") == 2:
        return sb if isinstance(sb, dict) else _default_sleeve_b()
    v2 = _default_sleeve_b()
    shallow = v2["rungs"][_rung_key(_B_RUNGS[0])]
    shallow["armed"] = bool(sb.get("armed", True)) and not sb.get("in_watching", False)
    shallow["active_position_id"] = sb.get("active_position_id")
    shallow["active_position_expiry"] = sb.get("active_position_expiry")
    return v2


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text())
            st["sleeve_b"] = migrate_sleeve_b(st.get("sleeve_b", {}))
            return st
        except Exception:
            pass
    return _default_state()


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── Trading-day helpers ──────────────────────────────────────────────────────

def _trading_days_between(start: str, end: str, calendar: pd.DatetimeIndex) -> int:
    """Count trading days in `calendar` strictly between start and end dates."""
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    mask = (calendar > s) & (calendar <= e)
    return int(mask.sum())


# ── Core update functions ─────────────────────────────────────────────────────

def update_sleeve_a(
    state_a: dict,
    ddath: float,
    today: str,
) -> dict:
    """
    Advance Sleeve A state machine one day.

    Re-arm: if not armed AND ddATH ≥ -2%  (position-status independent —
            matches research find_triggers_ddath; no-overlap is enforced by
            the fire-condition's `not has_pos` check below).
    Fire:   if armed AND ddATH ≤ -4% AND no active position.

    Returns action dict: {"action": "fire_A"|"none", "date": today}
    """
    has_pos = bool(state_a.get("active_position_id"))

    # Re-arm when ddATH recovers, regardless of whether a position is open.
    # This matches the research baseline methodology (see q042_ddath_full_scan.py
    # find_triggers_ddath): re-arm is position-agnostic; the no-overlap constraint
    # is enforced purely by the fire condition below.
    if not state_a["armed"] and ddath >= _REARM_THRESHOLD:
        state_a["armed"] = True

    if state_a["armed"] and ddath <= _DD4_THRESHOLD and not has_pos:
        state_a["armed"] = False
        return {"action": "fire_A", "date": today}

    return {"action": "none"}


def update_sleeve_b(
    state_b: dict,
    ddath: float,
    today: str,
) -> list[dict]:
    """
    Advance Sleeve B ladder state machine one day (SPEC-094.7).

    Re-arm : ddATH ≥ -2% → 全体 rung armed=True（position-agnostic，同 A：
             闩锁语义——armed 期间被在场仓位挡住的触发，仓位一到期即补发）。
    Fire   : 对每个 rung r：armed AND ddATH ≤ r AND 该档无在场仓 → fire。
             gap 崩盘单日可跨多档 → 返回多个 fire。armed 在 fire 时消耗。

    Returns list of action dicts: [{"action": "fire_B", "rung": -0.25,
    "date": today}, ...]（无动作 → 空表）。调用方按 rung 路由结构
    （strategy.q042_sizing：-15 → spread，≤ -25 → XSP LEAP）。
    """
    actions: list[dict] = []
    rungs = state_b["rungs"]
    if ddath >= _REARM_THRESHOLD:
        for rk in rungs:
            rungs[rk]["armed"] = True
    for r in _B_RUNGS:
        rs = rungs[_rung_key(r)]
        has_pos = bool(rs.get("active_position_id"))
        if rs["armed"] and ddath <= r and not has_pos:
            rs["armed"] = False
            actions.append({"action": "fire_B", "rung": r, "date": today})
    return actions


# ── Live snapshot ─────────────────────────────────────────────────────────────

def get_current_q042_snapshot(
    spx_df: Optional[pd.DataFrame] = None,
) -> Q042Snapshot:
    """
    Return the current Q042 state snapshot based on latest SPX close.

    Args:
        spx_df: Optional pre-fetched SPX daily DataFrame with column 'close'
                (or 'Close'). If None, fetches from Yahoo Finance.

    The function does NOT advance the state machine (read-only for UI).
    Use advance_state_eod() in production/q042_executor.py for EOD updates.
    """
    if spx_df is None:
        import yfinance as yf
        # F7: window lengthened for display; ATH truth is state, not this window.
        raw = yf.Ticker("^GSPC").history(period="6mo", interval="1d")
        spx_df = raw[["Close"]].rename(columns={"Close": "close"})
        spx_df.index = pd.to_datetime(spx_df.index).tz_localize(None)

    state = load_state()

    spx_close = float(spx_df["close"].iloc[-1])
    today_str = spx_df.index[-1].strftime("%Y-%m-%d")

    # F7: ATH真值源 = state (executor日度维护). When state ATH is missing/0, mark
    # degraded EXPLICITLY rather than silently substituting a short-window max
    # (which understates the true ATH → understates the drawdown). Fall back to
    # spx_close so ddath reads a neutral 0 and consumers can skip the row.
    state_ath = float(state.get("ath_running_max", 0.0) or 0.0)
    ath_degraded = state_ath <= 0.0
    if ath_degraded:
        ath = spx_close
    else:
        ath = max(state_ath, spx_close)
    ddath = spx_close / ath - 1.0

    sa = state.get("sleeve_a", {})
    sb = state.get("sleeve_b", {})

    return Q042Snapshot(
        date=today_str,
        spx_close=spx_close,
        ath_running_max=ath,
        ddath=ddath,
        sleeve_a=SleeveState(
            sleeve_id="A",
            armed=bool(sa.get("armed", True)),
            in_watching=False,
            watch_start_date=None,
            active_position_id=sa.get("active_position_id"),
            active_position_expiry=sa.get("active_position_expiry"),
        ),
        sleeve_b=_sleeve_b_snapshot(sb),
        combined_bp_pct=float(state.get("combined_bp_pct", 0.0)),
        ath_degraded=ath_degraded,
        sleeve_b_rungs=sb.get("rungs", {}),
    )


def _sleeve_b_snapshot(sb: dict) -> SleeveState:
    """v2 rungs → 向后兼容的聚合 SleeveState（armed = 任一 rung armed；
    position 取最浅在场档；in_watching 恒 False——reclaim 机制已删）。"""
    rungs = sb.get("rungs", {})
    armed_any = any(r.get("armed", True) for r in rungs.values()) if rungs else True
    pos_id, pos_exp = None, None
    for r in _B_RUNGS:
        rs = rungs.get(_rung_key(r), {})
        if rs.get("active_position_id"):
            pos_id, pos_exp = rs["active_position_id"], rs.get("active_position_expiry")
            break
    return SleeveState(sleeve_id="B", armed=armed_any, in_watching=False,
                       watch_start_date=None, active_position_id=pos_id,
                       active_position_expiry=pos_exp)


# ── Walk-forward history (for backtest / AC1 verification) ───────────────────

def get_q042_history(
    spx_df: pd.DataFrame,
    vix_df: Optional[pd.DataFrame] = None,
    start: str = _ATH_SEED_DATE,
    end: str = "2026-05-10",
) -> tuple[list[dict], list[dict]]:
    """
    Walk-forward simulation of both sleeves from `start` to `end`.

    Args:
        spx_df: DataFrame with columns ['open', 'close', 'high', 'low'].
        vix_df: Optional VIX series; not needed for trigger logic.
        start:  First date (ATH resets to 2007-01-01 baseline).
        end:    Last date inclusive.

    Returns:
        (sleeve_a_entries, sleeve_b_entries) — each entry is a dict with
        {signal_date, entry_date, ath_at_signal, ddath_at_signal}；B 侧另含
        {rung, instrument, dte}（SPEC-094.7 阶梯）。
    """
    from strategy.q042_sizing import b_rung_structure   # 结构路由单真值（lazy）

    df = spx_df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    cols = {c.lower(): c for c in df.columns}
    if "close" not in cols:
        df = df.rename(columns={v: k for k, v in cols.items()})
    df = df.loc[start:end].copy()

    # Running ATH from 2007-01-01 (cumulative max)
    ath_series = df["close"].cummax()

    state_a: dict = {"armed": True, "active_position_id": None, "active_position_expiry": None}
    state_b: dict = _default_sleeve_b()

    entries_a: list[dict] = []
    entries_b: list[dict] = []

    for i, (dt, row) in enumerate(df.iterrows()):
        today_str = dt.strftime("%Y-%m-%d")
        spx_close = float(row["close"])
        ath = float(ath_series.iloc[i])
        ddath = spx_close / ath - 1.0

        # Check expiry for Sleeve A
        if state_a["active_position_expiry"] and today_str >= state_a["active_position_expiry"]:
            state_a["active_position_id"] = None
            state_a["active_position_expiry"] = None

        # Check expiry per Sleeve B rung
        for rs in state_b["rungs"].values():
            if rs["active_position_expiry"] and today_str >= rs["active_position_expiry"]:
                rs["active_position_id"] = None
                rs["active_position_expiry"] = None

        act_a = update_sleeve_a(state_a, ddath, today_str)
        acts_b = update_sleeve_b(state_b, ddath, today_str)

        if act_a["action"] == "fire_A":
            entry_date = (dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            # Expiry from entry (T+1), not signal (T). Backtest engine fix R-20260510-15.
            expiry = (dt + pd.Timedelta(days=31)).strftime("%Y-%m-%d")  # SPEC-094.1: entry+30 DTE
            entries_a.append({
                "signal_date": today_str,
                "entry_date": entry_date,
                "ath_at_signal": ath,
                "ddath_at_signal": ddath,
            })
            state_a["active_position_id"] = f"A-{today_str}"
            state_a["active_position_expiry"] = expiry

        for act in acts_b:
            rung = act["rung"]
            struct = b_rung_structure(rung)
            entry_date = (dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            expiry = (dt + pd.Timedelta(days=1 + struct["dte"])).strftime("%Y-%m-%d")
            entries_b.append({
                "signal_date": today_str,
                "entry_date": entry_date,
                "ath_at_signal": ath,
                "ddath_at_signal": ddath,
                "rung": rung,
                "instrument": struct["instrument"],
                "dte": struct["dte"],
            })
            rs = state_b["rungs"][_rung_key(rung)]
            rs["active_position_id"] = f"B{_rung_key(rung)}-{today_str}"
            rs["active_position_expiry"] = expiry

    return entries_a, entries_b


if __name__ == "__main__":
    snap = get_current_q042_snapshot()
    print(snap)
