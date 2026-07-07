"""Q019 settled-VIX Signal 2 production support.

Independent production sidecar:
- leaves Signal 1 paths untouched
- polls Yahoo Finance hourly VIX bars
- writes read-only state artifact for web UI
- appends one daily JSONL paper-trading record
- sends a Telegram confirmation/diff message when Signal 2 finalizes
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy.catalog import strategy_descriptor  # noqa: E402
from strategy.selector import (  # noqa: E402
    DEFAULT_PARAMS,
    Recommendation,
    _eval_overlay_f_live,
    fetch_spx_history,
    fetch_vix_history,
    get_current_iv_snapshot,
    get_current_snapshot,
    get_current_trend,
    select_strategy,
)

ET = ZoneInfo("America/New_York")
SETTLING_INTERVAL = os.getenv("SETTLING_INTERVAL", "1h")
SETTLING_THRESHOLD = float(os.getenv("SETTLING_THRESHOLD", "0.5"))
SETTLING_TIMEOUT_MIN = int(os.getenv("SETTLING_TIMEOUT_MIN", "180"))
SETTLING_DATA_SOURCE = os.getenv("SETTLING_DATA_SOURCE", "yfinance:^VIX")

STATE_FILE = Path(os.getenv("Q019_SETTLING_STATE_FILE", str(REPO_ROOT / "logs" / "q019_settling_state.json")))
LOG_FILE = Path(os.getenv("Q019_SETTLING_LOG_FILE", str(REPO_ROOT / "data" / "q019_settling_log.jsonl")))
RUN_LOG = REPO_ROOT / "logs" / "q019_settling.log"

TELEGRAM_TIMEOUT = 20

_US_HOLIDAYS_2026 = {
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",
    "2026-05-25",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
}
_US_HOLIDAYS_2025 = {
    "2025-01-01",
    "2025-01-20",
    "2025-02-17",
    "2025-04-18",
    "2025-05-26",
    "2025-07-04",
    "2025-09-01",
    "2025-11-27",
    "2025-12-25",
}
_ALL_HOLIDAYS = _US_HOLIDAYS_2025 | _US_HOLIDAYS_2026

load_dotenv(REPO_ROOT / ".env")


SettlingStatus = Literal["waiting", "stable", "timeout", "skipped", "unavailable"]


@dataclass
class SignalSummary:
    strategy_key: str
    strategy: str
    position_action: str
    vix: float


@dataclass
class SettlingState:
    date: str
    status: SettlingStatus
    data_source: str
    interval: str
    threshold: float
    timeout_min: int
    elapsed_min: int
    checked_at: str
    current_vix: float | None
    prev_vix: float | None
    delta_vix: float | None
    signal1: dict | None
    signal1_captured_at: str | None
    signal2: dict | None
    changed: bool | None
    note: str | None


def _logger(verbose: bool) -> logging.Logger:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("q019_settling")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(RUN_LOG)
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log


def _now_et() -> datetime:
    return datetime.now(ET)


def _session_start(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET)


def _session_timeout(day: date) -> datetime:
    return _session_start(day) + timedelta(minutes=SETTLING_TIMEOUT_MIN)


def _is_trading_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    return day.isoformat() not in _ALL_HOLIDAYS


def _telegram_creds() -> tuple[str, str]:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _send_telegram_message(text: str, log: logging.Logger) -> bool:
    # SPEC-126: through the gateway. Settling is the SPX morning 2nd-signal —
    # its pushes advise entry decisions (ACTION 关于新开仓).
    try:
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
        from notify.gateway import push as gw_push
        return gw_push("ACTION", "新开仓", "Settled VIX 2nd signal", text)
    except Exception:
        log.exception("telegram send failed")
        return False


def _fetch_hourly_vix_frame() -> pd.DataFrame:
    df = yf.Ticker("^VIX").history(period="5d", interval=SETTLING_INTERVAL)
    if df.empty:
        return pd.DataFrame(columns=["vix"])
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(ET).tz_localize(None)
    # Use .values to drop the original tz-aware index so pandas aligns positionally
    # with idx (tz-naive ET); passing the Series directly causes index mismatch → all NaN.
    out = pd.DataFrame({"vix": pd.to_numeric(df["Close"].values, errors="coerce")}, index=idx)
    out = out.dropna(subset=["vix"]).sort_index()
    out["date"] = out.index.normalize()
    return out


def _latest_vix_rows(frame: pd.DataFrame, day: date) -> tuple[pd.Series | None, pd.Series | None]:
    if frame.empty:
        return None, None
    day_rows = frame[frame["date"] == pd.Timestamp(day)]
    if len(day_rows) >= 2:
        return day_rows.iloc[-1], day_rows.iloc[-2]
    if len(day_rows) == 1:
        prev = frame.iloc[-2] if len(frame) >= 2 else None
        return day_rows.iloc[-1], prev
    if len(frame) >= 2:
        return frame.iloc[-1], frame.iloc[-2]
    return frame.iloc[-1], None


def _minutes_elapsed(now: datetime, day: date) -> int:
    return max(0, int((now - _session_start(day)).total_seconds() // 60))


def _evaluate_settling(now: datetime, frame: pd.DataFrame) -> tuple[SettlingStatus, float | None, float | None, float | None, int, str | None]:
    day = now.date()
    if not _is_trading_day(day):
        return "skipped", None, None, None, 0, "non_trading_day"

    current, prev = _latest_vix_rows(frame, day)
    current_vix = float(current["vix"]) if current is not None else None
    prev_vix = float(prev["vix"]) if prev is not None else None
    delta_vix = None
    if current_vix is not None and prev_vix is not None:
        delta_vix = abs(current_vix - prev_vix)

    elapsed = _minutes_elapsed(now, day)
    if current_vix is None:
        return "waiting", None, prev_vix, None, elapsed, "no_intraday_bar_yet"

    day_rows = frame[frame["date"] == pd.Timestamp(day)]
    if len(day_rows) >= 2 and delta_vix is not None and delta_vix < SETTLING_THRESHOLD:
        return "stable", current_vix, prev_vix, delta_vix, elapsed, None
    if now >= _session_timeout(day):
        return "timeout", current_vix, prev_vix, delta_vix, SETTLING_TIMEOUT_MIN, None
    return "waiting", current_vix, prev_vix, delta_vix, elapsed, None


def _build_signal1() -> SignalSummary:
    from strategy.selector import get_recommendation

    rec = get_recommendation(use_intraday=True)
    return SignalSummary(
        strategy_key=rec.strategy_key,
        strategy=rec.strategy.value,
        position_action=rec.position_action,
        vix=float(rec.vix_snapshot.vix),
    )


def _build_signal2(vix_value: float) -> SignalSummary:
    vix_data = fetch_vix_history(period="2y")
    spx_data = fetch_spx_history(period="2y")

    current_spx = None
    try:
        spx_5m = fetch_spx_history(period="1d", interval="5m")
        current_spx = float(spx_5m["close"].iloc[-1])
    except Exception:
        current_spx = None

    vix_snap = get_current_snapshot(vix_data, current_vix=vix_value)
    iv_snap = get_current_iv_snapshot(vix_data, current_vix=vix_value)
    trend_snap = get_current_trend(spx_data, current_spx=current_spx)
    rec = select_strategy(vix_snap, iv_snap, trend_snap, DEFAULT_PARAMS)
    rec = _eval_overlay_f_live(rec, DEFAULT_PARAMS)
    return SignalSummary(
        strategy_key=rec.strategy_key,
        strategy=rec.strategy.value,
        position_action=rec.position_action,
        vix=float(rec.vix_snapshot.vix),
    )


def _short_label(strategy_key: str, action: str) -> str:
    if action in {"WAIT", "CLOSE_AND_WAIT"}:
        return "WAIT"
    key = (strategy_key or "").lower()
    if "iron_condor" in key:
        return "IC"
    if "bull_put_spread" in key:
        return "BPS"
    if "bear_call_spread" in key:
        return "BCS"
    if "diagonal" in key:
        return "DIAG"
    if "aftermath" in key:
        return "AFTERMATH"
    if "es_short_put" in key:
        return "/ES PUT"
    try:
        return strategy_descriptor(strategy_key).name
    except Exception:
        return strategy_key.upper() or "UNKNOWN"


def _signals_changed(signal1: SignalSummary, signal2: SignalSummary) -> bool:
    return (
        signal1.strategy_key != signal2.strategy_key
        or signal1.position_action != signal2.position_action
    )


def _diff_message(signal1: SignalSummary, signal2: SignalSummary, status: SettlingStatus, elapsed_min: int) -> str:
    prefix = f"🔄 VIX 稳定信号更新（耗时 {elapsed_min} 分钟）"
    if status == "timeout":
        prefix = f"🔄 VIX 稳定信号更新（timeout 12:30 ET，耗时 {elapsed_min} 分钟）"
    return (
        f"{prefix}\n"
        f"开盘时 VIX {signal1.vix:.1f} → 推荐: {_short_label(signal1.strategy_key, signal1.position_action)}\n"
        f"{'早盘 VIX 未稳定，按 12:30 当前值' if status == 'timeout' else '稳定后 VIX'} {signal2.vix:.1f} "
        f"→ 推荐: {_short_label(signal2.strategy_key, signal2.position_action)}（已变化）"
    )


def _same_message(signal1: SignalSummary, signal2: SignalSummary, status: SettlingStatus, elapsed_min: int) -> str:
    header = f"✅ VIX 稳定确认（耗时 {elapsed_min} 分钟）"
    if status == "timeout":
        header = f"✅ VIX 稳定确认（timeout 12:30 ET，耗时 {elapsed_min} 分钟）"
        return (
            f"{header}\n"
            f"早盘 VIX 未稳定，按 12:30 当前值 {signal2.vix:.1f} 决策\n"
            f"开盘推荐 {_short_label(signal1.strategy_key, signal1.position_action)} 维持不变"
        )
    return (
        f"{header}\n"
        f"VIX 稳定于 {signal2.vix:.1f}，开盘推荐 {_short_label(signal1.strategy_key, signal1.position_action)} 维持不变"
    )


def _write_state(state: SettlingState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(asdict(state), ensure_ascii=False, default=str), encoding="utf-8")


def read_settling_state(now: datetime | None = None) -> dict[str, object]:
    now = now or _now_et()
    if not STATE_FILE.exists():
        return {
            "date": now.date().isoformat(),
            "status": "unavailable",
            "note": "state_file_missing",
            "signal1": None,
            "signal2": None,
        }
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "date": now.date().isoformat(),
            "status": "unavailable",
            "note": "state_file_unreadable",
            "signal1": None,
            "signal2": None,
        }
    if str(payload.get("date") or "") != now.date().isoformat() and _is_trading_day(now.date()):
        payload["status"] = "unavailable"
        payload["note"] = "stale_state"
    return payload


def _append_daily_log(
    *,
    day: date,
    signal1: SignalSummary,
    signal2: SignalSummary,
    settling_status: SettlingStatus,
    elapsed_min: int,
    changed: bool,
) -> None:
    payload = {
        "date": day.isoformat(),
        "vix_signal1": signal1.vix,
        "rec_signal1": signal1.strategy_key,
        "vix_signal2": signal2.vix,
        "rec_signal2": signal2.strategy_key,
        "settling_status": settling_status,
        "elapsed_min": elapsed_min,
        "changed": changed,
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _next_check_time(now: datetime) -> datetime:
    start = _session_start(now.date())
    checks = [
        start,
        start + timedelta(hours=1),
        start + timedelta(hours=2),
        start + timedelta(hours=3),
    ]
    for check in checks:
        if check > now:
            return check
    return _session_timeout(now.date())


def _sleep_seconds(now: datetime) -> float:
    nxt = _next_check_time(now)
    return max(1.0, (nxt - now).total_seconds())


def run_settling_process(*, now_fn=_now_et, sleep_fn=time.sleep, send_telegram: bool = True, verbose: bool = False) -> int:
    log = _logger(verbose)
    now = now_fn()
    today = now.date()

    if not _is_trading_day(today):
        state = SettlingState(
            date=today.isoformat(),
            status="skipped",
            data_source=SETTLING_DATA_SOURCE,
            interval=SETTLING_INTERVAL,
            threshold=SETTLING_THRESHOLD,
            timeout_min=SETTLING_TIMEOUT_MIN,
            elapsed_min=0,
            checked_at=now.isoformat(),
            current_vix=None,
            prev_vix=None,
            delta_vix=None,
            signal1=None,
            signal1_captured_at=None,
            signal2=None,
            changed=None,
            note="non_trading_day",
        )
        _write_state(state)
        log.info("q019 settling skipped: non-trading day")
        return 0

    signal1 = _build_signal1()
    signal1_captured_at = now.isoformat()
    frame = pd.DataFrame()
    first_state = SettlingState(
        date=today.isoformat(),
        status="waiting",
        data_source=SETTLING_DATA_SOURCE,
        interval=SETTLING_INTERVAL,
        threshold=SETTLING_THRESHOLD,
        timeout_min=SETTLING_TIMEOUT_MIN,
        elapsed_min=_minutes_elapsed(now, today),
        checked_at=now.isoformat(),
        current_vix=signal1.vix,
        prev_vix=None,
        delta_vix=None,
        signal1=asdict(signal1),
        signal1_captured_at=signal1_captured_at,
        signal2=None,
        changed=None,
        note="awaiting_first_stable_check",
    )
    _write_state(first_state)

    while True:
        now = now_fn()
        try:
            frame = _fetch_hourly_vix_frame()
            status, current_vix, prev_vix, delta_vix, elapsed_min, note = _evaluate_settling(now, frame)
        except Exception as exc:
            status, current_vix, prev_vix, delta_vix, elapsed_min, note = (
                "unavailable",
                None,
                None,
                None,
                _minutes_elapsed(now, today),
                f"fetch_error:{exc}",
            )

        state = SettlingState(
            date=today.isoformat(),
            status=status,
            data_source=SETTLING_DATA_SOURCE,
            interval=SETTLING_INTERVAL,
            threshold=SETTLING_THRESHOLD,
            timeout_min=SETTLING_TIMEOUT_MIN,
            elapsed_min=elapsed_min,
            checked_at=now.isoformat(),
            current_vix=current_vix,
            prev_vix=prev_vix,
            delta_vix=delta_vix,
            signal1=asdict(signal1),
            signal1_captured_at=signal1_captured_at,
            signal2=None,
            changed=None,
            note=note,
        )

        if status in {"stable", "timeout"} and current_vix is not None:
            signal2 = _build_signal2(current_vix)
            changed = _signals_changed(signal1, signal2)
            state.signal2 = asdict(signal2)
            state.changed = changed
            _write_state(state)
            _append_daily_log(
                day=today,
                signal1=signal1,
                signal2=signal2,
                settling_status=status,
                elapsed_min=elapsed_min,
                changed=changed,
            )
            if send_telegram:
                msg = _diff_message(signal1, signal2, status, elapsed_min) if changed else _same_message(signal1, signal2, status, elapsed_min)
                _send_telegram_message(msg, log)
            log.info("q019 settling finalized status=%s changed=%s elapsed=%s", status, changed, elapsed_min)
            return 0

        _write_state(state)
        if status == "unavailable" and now >= _session_timeout(today):
            log.warning("q019 settling unavailable through timeout window")
            return 1
        sleep_fn(_sleep_seconds(now))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q019 settled-VIX Signal 2 runner")
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    return run_settling_process(send_telegram=not args.skip_telegram, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
