"""Q042 Dual-Sleeve Directional Trigger (F1)

Two independent state machines:

  Sleeve A — q042_sleeve_a_dd4_lenient
    Trigger : ddATH ≤ -4% (first crossing)
    Re-arm  : ddATH ≥ -2% after position closes
    MA filter: none — T+1 open immediately

  Sleeve B — q042_sleeve_b_dd15_lenient_ma10reclaim
    Trigger (outer): ddATH ≤ -15% → enters "watching" mode
    Trigger (inner): first close > MA10 within 30 trading days
    Re-arm  : ddATH ≥ -2% after position closes

ddATH = SPX_close / running_ATH_since_2007 - 1

State is persisted to data/q042_state.json so that process restarts
do not reset the armed / in_watching flags.
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
_DD15_THRESHOLD  = -0.15   # Sleeve B outer trigger
_WATCH_DAYS      = 30      # trading days in Sleeve B watch window
_MA10_WINDOW     = 10


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

    def __str__(self) -> str:
        return (
            f"[{self.date}] SPX {self.spx_close:.0f} | ATH {self.ath_running_max:.0f} | "
            f"ddATH {self.ddath*100:+.2f}% | "
            f"A={self.sleeve_a.armed}/pos={self.sleeve_a.active_position_id} | "
            f"B={self.sleeve_b.armed}/watch={self.sleeve_b.in_watching}/pos={self.sleeve_b.active_position_id}"
        )


# ── State persistence ────────────────────────────────────────────────────────

def _default_state() -> dict:
    return {
        "ath_running_max": 0.0,
        "ath_last_update": "",
        "sleeve_a": {
            "armed": True,
            "active_position_id": None,
            "active_position_expiry": None,
        },
        "sleeve_b": {
            "armed": True,
            "in_watching": False,
            "watch_start_date": None,
            "active_position_id": None,
            "active_position_expiry": None,
        },
        "combined_bp_pct": 0.0,
    }


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
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
    spx_close: float,
    ma10: float,
    today: str,
    trading_calendar: pd.DatetimeIndex,
) -> dict:
    """
    Advance Sleeve B state machine one day.

    Re-arm  : not armed AND no active position AND no watching AND ddATH ≥ -2%.
    Outer   : armed AND ddATH ≤ -15% → enter watching.
    Inner   : in watching AND close > MA10 → fire.
    Expire  : watching > 30 trading days → drop trigger.

    Returns action dict: {"action": "enter_watching"|"fire_B"|"watch_expired"|"none"}
    """
    has_pos = bool(state_b.get("active_position_id"))

    # Re-arm: position-agnostic (same rationale as Sleeve A).
    if (
        not state_b["armed"]
        and not state_b["in_watching"]
        and ddath >= _REARM_THRESHOLD
    ):
        state_b["armed"] = True

    if (
        state_b["armed"]
        and not state_b["in_watching"]
        and ddath <= _DD15_THRESHOLD
        and not has_pos
    ):
        state_b["in_watching"] = True
        state_b["watch_start_date"] = today
        state_b["armed"] = False
        return {"action": "enter_watching"}

    if state_b["in_watching"]:
        days_in_watch = _trading_days_between(
            state_b["watch_start_date"], today, trading_calendar
        )
        if days_in_watch > _WATCH_DAYS:
            state_b["in_watching"] = False
            state_b["watch_start_date"] = None
            return {"action": "watch_expired"}
        if spx_close > ma10:
            state_b["in_watching"] = False
            state_b["watch_start_date"] = None
            return {"action": "fire_B", "date": today}

    return {"action": "none"}


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
        sleeve_b=SleeveState(
            sleeve_id="B",
            armed=bool(sb.get("armed", True)),
            in_watching=bool(sb.get("in_watching", False)),
            watch_start_date=sb.get("watch_start_date"),
            active_position_id=sb.get("active_position_id"),
            active_position_expiry=sb.get("active_position_expiry"),
        ),
        combined_bp_pct=float(state.get("combined_bp_pct", 0.0)),
        ath_degraded=ath_degraded,
    )


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
        {signal_date, entry_date, ath_at_signal, ddath_at_signal}.
    """
    df = spx_df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    cols = {c.lower(): c for c in df.columns}
    if "close" not in cols:
        df = df.rename(columns={v: k for k, v in cols.items()})
    df = df.loc[start:end].copy()

    trading_calendar = df.index
    ma10 = df["close"].rolling(_MA10_WINDOW).mean()

    # Running ATH from 2007-01-01 (cumulative max)
    ath_series = df["close"].cummax()

    state_a: dict = {"armed": True, "active_position_id": None, "active_position_expiry": None}
    state_b: dict = {
        "armed": True,
        "in_watching": False,
        "watch_start_date": None,
        "active_position_id": None,
        "active_position_expiry": None,
    }

    entries_a: list[dict] = []
    entries_b: list[dict] = []

    for i, (dt, row) in enumerate(df.iterrows()):
        today_str = dt.strftime("%Y-%m-%d")
        spx_close = float(row["close"])
        ath = float(ath_series.iloc[i])
        ddath = spx_close / ath - 1.0
        ma10_val = float(ma10.iloc[i]) if not pd.isna(ma10.iloc[i]) else spx_close

        # Check expiry for Sleeve A
        if state_a["active_position_expiry"] and today_str >= state_a["active_position_expiry"]:
            state_a["active_position_id"] = None
            state_a["active_position_expiry"] = None

        # Check expiry for Sleeve B
        if state_b["active_position_expiry"] and today_str >= state_b["active_position_expiry"]:
            state_b["active_position_id"] = None
            state_b["active_position_expiry"] = None

        act_a = update_sleeve_a(state_a, ddath, today_str)
        act_b = update_sleeve_b(state_b, ddath, spx_close, ma10_val, today_str, trading_calendar)

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

        if act_b["action"] == "fire_B":
            entry_date = (dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            expiry = (dt + pd.Timedelta(days=91)).strftime("%Y-%m-%d")  # entry+90 DTE (Sleeve B unchanged)
            entries_b.append({
                "signal_date": today_str,
                "entry_date": entry_date,
                "ath_at_signal": ath,
                "ddath_at_signal": ddath,
            })
            state_b["active_position_id"] = f"B-{today_str}"
            state_b["active_position_expiry"] = expiry

    return entries_a, entries_b


if __name__ == "__main__":
    snap = get_current_q042_snapshot()
    print(snap)
