"""
Telegram Bot — Daily Options Recommendation Push

Commands:
  /today     — Fetch and send today's recommendation now
  /entered   — Record that you entered the recommended trade
  /closed    — Mark the current position as closed
  /backtest  — Run a 1-year quick backtest and send summary
  /status    — Show signals + current open position
  /help      — Command list

Scheduled push:
  Every US trading day at 09:35 ET (after open, after VIX settles)
  Skips weekends and US federal holidays automatically.

Setup:
  1. Message @BotFather on Telegram → /newbot → copy token
  2. Start a chat with your new bot, then run:
       python -m notify.telegram_bot --get-chat-id
  3. Copy the printed chat_id into .env
  4. Run normally:
       python -m notify.telegram_bot
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, time as dtime, timedelta
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from logs.recommendation_log_io import append_recommendation_event
from strategy.selector import (
    get_recommendation, StrategyName, Recommendation, StrategyParams,
)
from strategy.catalog import manual_entry_options, strategy_descriptor
from strategy.es_params import DEFAULT_ES_PARAMS as _ES_P

# SPEC-121: WARNING stays at a fixed 2× (early-intelligence line) — deliberately
# NOT derived from stop_mult, which moved 3× → 10× (canonical A3 stop).
ES_STOP_WARN_MULT = 2.0
from strategy.state import (
    read_state, read_all_positions, write_state, close_position, roll_position, add_note,
)
from backtest.engine import run_backtest, compute_metrics
from signals.intraday import (
    get_vix_spike, get_spx_stop, get_vix_spike_from_quote, get_spx_stop_from_quote,
    SpikeLevel, StopLevel, VixSpikeAlert, IntradayStopTrigger,
)
from schwab.client import get_spx_quote, get_vix_quote

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

# ── US Federal Holiday check (simplified) ─────────────────────────────────────

_US_HOLIDAYS_2026 = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}
_US_HOLIDAYS_2025 = {
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
}
_ALL_HOLIDAYS = _US_HOLIDAYS_2025 | _US_HOLIDAYS_2026


def is_trading_day(dt: datetime | None = None) -> bool:
    dt = dt or datetime.now(ET)
    if dt.weekday() >= 5:       # Saturday or Sunday
        return False
    if dt.strftime("%Y-%m-%d") in _ALL_HOLIDAYS:
        return False
    return True


def is_market_open(dt: datetime | None = None) -> bool:
    """True if ET time is within regular trading hours 09:30–16:00."""
    dt = dt or datetime.now(ET)
    if not is_trading_day(dt):
        return False
    return dtime(9, 30) <= dt.time() <= dtime(16, 0)


# ── Intraday monitor state ─────────────────────────────────────────────────────
# Tracks last observed levels to suppress duplicate pushes within the same session.

_SPIKE_RANK = {SpikeLevel.NONE: 0, SpikeLevel.WARNING: 1, SpikeLevel.ALERT: 2}
_STOP_RANK  = {StopLevel.NONE:  0, StopLevel.CAUTION:  1, StopLevel.TRIGGER: 2}
_STALE_QUOTE_MINUTES = 10
_ES_HV_VIX_MIN_ENTRY = 22.0
_ES_HV_ENTRY_DTE = 49
_ES_HV_TARGET_DELTA = 0.20
_ES_HV_MAX_SLOTS = 5
_ES_HV_PAPER_LOG = Path(__file__).resolve().parents[1] / "data" / "q071_hv_paper_trades.jsonl"


class EsStopLevel(str, Enum):
    NONE = "NONE"
    WARNING = "WARNING"
    TRIGGER = "TRIGGER"


@dataclass(frozen=True)
class EsStopResult:
    level: EsStopLevel
    entry_premium: float | None = None
    current_mark: float | None = None
    ratio: float | None = None
    observed: bool = False


_ES_STOP_RANK = {EsStopLevel.NONE: 0, EsStopLevel.WARNING: 1, EsStopLevel.TRIGGER: 2}

_intraday_state: dict = {
    "spike_level":      SpikeLevel.NONE,
    "stop_level":       StopLevel.NONE,
    "es_stop_level":    EsStopLevel.NONE,
    "profit_alerted":   False,   # True once profit target alert has been sent this session
    "mismatch_alerted": False,   # True once broker-state mismatch warning has been sent this session
    "es_hv_signal_alerted_date": None,
    "es_hv_stale_alerted_date": None,
}
_morning_snapshot: dict | None = None


# ── Message formatting ─────────────────────────────────────────────────────────

_ACTION_EMOJI = {
    "OPEN":           "🟢",
    "HOLD":           "🔵",
    "CLOSE_AND_OPEN": "🔄",
    "WAIT":           "⏸",
    "CLOSE_AND_WAIT": "🔴",
}


def _h(text: str) -> str:
    """Escape HTML special characters for Telegram HTML mode."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _params_hash() -> str:
    payload = asdict(StrategyParams())
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:10]


def _safe_append_recommendation_event(*, rec: Recommendation, source: str, mode: str) -> None:
    # SPEC-139 §3 — snapshot 当日 Lane B（持仓动作触发器）一并落盘，供
    # /api/decision-trace 回放历史日。快照失败 fail-soft：lane_b 保持 None，
    # 该行回放时如实标注"未存档"降级，绝不阻断推荐事件本体的落盘。
    lane_b_snapshot = None
    try:
        from strategy.decision_trace import lane_b_positions
        lane_b_snapshot = lane_b_positions(rec.vix_snapshot.date)
    except Exception:
        log.exception("lane_b snapshot failed (recommendation event still logged)")
    try:
        append_recommendation_event(
            rec=rec,
            source=source,
            mode=mode,
            timestamp=datetime.now(ET).isoformat(timespec="seconds"),
            params_hash=_params_hash(),
            lane_b=lane_b_snapshot,
        )
    except Exception:
        log.exception("recommendation log append failed")


def _format_recommendation(rec: Recommendation) -> str:
    desc         = strategy_descriptor(rec.strategy_key)
    emoji        = desc.emoji
    action_emoji = _ACTION_EMOJI.get(rec.position_action, "")
    date         = rec.vix_snapshot.date

    iv_note = ""
    if abs(rec.iv_snapshot.iv_rank - rec.iv_snapshot.iv_percentile) > 15:
        # SPEC-136 #2 — 数字带语义，贵贱刻度与 trace 同源（ivp_phrase）
        from strategy.decision_trace import ivp_phrase
        iv_note = (f"（IVR 本期失真，改用 IVP："
                   f"{ivp_phrase(rec.iv_snapshot.iv_percentile)}）")

    ts_note = ""
    if rec.vix_snapshot.vix3m is not None:
        ts_dir  = "BACKWARDATION ⚠️" if rec.vix_snapshot.backwardation else "contango"
        ts_note = f"  Term struct <code>{ts_dir}</code> (VIX3M {rec.vix_snapshot.vix3m:.2f})"

    signals = (
        f"VIX <code>{rec.vix_snapshot.vix:.1f}</code> [{rec.vix_snapshot.regime.value}]  "
        f"IVR <code>{rec.iv_snapshot.iv_rank:.0f}</code>{_h(iv_note)}  "
        f"Trend <code>{rec.trend_snapshot.signal.value}</code>"
        f"{ts_note}"
    )

    if rec.legs:
        legs_lines = "\n".join(
            f"  {l.action} {l.option:<4} {l.dte}DTE  δ{l.delta:.2f}  <i>{_h(l.note)}</i>"
            for l in rec.legs
        )
    else:
        legs_lines = "  <i>No new position</i>"

    macro = "\n⚠️ <b>SPX below 200MA</b> — reduce size 25–50% on bullish trades." if rec.macro_warning else ""
    bk    = "\n⚠️ <b>Backwardation:</b> spot VIX above VIX3M — Bull Put Spread skipped." if rec.backwardation else ""

    # SPEC-146 — 数据来源披露：盘中源回退不再静默（07-13 晨报 VIX 15.0 实为
    # 周五收盘的教训）。每条注记独立成行（feedback_multiline_notes）。
    data_notes = ""
    _notes = getattr(rec, "data_notes", None) or []
    if _notes:
        data_notes = "\n" + "\n".join(f"<i>{_h(n)}</i>" for n in _notes)

    entered_hint = ""
    if rec.position_action in ("OPEN", "CLOSE_AND_OPEN"):
        entered_hint = "\n\n<i>After executing: send /entered to record your position.</i>"

    # SPEC-136 #1 — 首行 = trace final verdict 人话锚点，与
    # /api/decision-trace final 节点逐字同源（单源原则，禁止手写第二套）
    verdict_line = ""
    _fv = next((n.get("label_human") for n in (getattr(rec, "trace", None) or [])
                if n.get("kind") == "final"), None)
    if _fv:
        verdict_line = f"<b>{_h(_fv)}</b>\n"

    return (
        f"{verdict_line}"
        f"{action_emoji} {emoji} <b>Options Recommendation — {_h(date)}</b>\n"
        f"{'─' * 32}\n"
        f"<b>Action:</b>    <code>{_h(rec.position_action)}</code>\n"
        f"<b>Strategy:</b>  {_h(desc.name)}\n"
        f"<b>Underlying:</b> {_h(rec.underlying)}\n\n"
        f"<b>Legs:</b>\n{legs_lines}\n\n"
        f"<b>Max Risk:</b>  {_h(rec.max_risk)}\n"
        f"<b>Target:</b>    {_h(rec.target_return)}\n"
        f"<b>Size Rule:</b> {_h(rec.size_rule)}\n"
        f"<b>Roll At:</b>   {_h(rec.roll_rule)}\n\n"
        f"<b>Why:</b> <i>{_h(rec.rationale)}</i>\n\n"
        f"<b>Signals:</b> {signals}"
        f"{macro}{bk}{data_notes}\n"
        f"{'─' * 32}"
        f"{entered_hint}"
    )


# Keep _esc for any legacy use; no longer used in formatting
def _esc(text: str) -> str:
    return _h(text)


def _format_spike_alert(spike: VixSpikeAlert) -> str:
    icon = "🚨" if spike.level == SpikeLevel.ALERT else "⚠️"
    # SPEC-136 #6 — advice 文案为完整中文句（英文骨架行保留，数字带上下文）
    advice = (
        "🚨 VIX 快速拉升——考虑平掉或对冲短 vol 仓位。"
        if spike.level == SpikeLevel.ALERT
        else "⚠️ VIX 上行加速——盯紧，暂不动作。"
    )
    timing = _alert_timing_label(spike.timestamp, spike.realtime)
    return (
        f"{icon} <b>VIX Spike {spike.level.value}</b>  [{_h(spike.timestamp)}{timing}]\n"
        f"Open: <code>{spike.vix_open:.2f}</code> → Now: <code>{spike.vix_current:.2f}</code>  "
        f"(<code>{spike.spike_pct*100:+.1f}%</code>)\n"
        f"{advice}"
    )


def _format_stop_alert(stop: IntradayStopTrigger) -> str:
    icon = "🚨" if stop.level == StopLevel.TRIGGER else "⚠️"
    # SPEC-136 #6 — advice 文案为完整中文句
    advice = (
        "🚨 日内跌破 -2% 触发线：立即平掉或减仓 credit spread。"
        if stop.level == StopLevel.TRIGGER
        else "⚠️ 日内跌破 -1% 警戒线：收紧心理止损，准备行动。"
    )
    timing = _alert_timing_label(stop.timestamp, stop.realtime)
    return (
        f"{icon} <b>SPX Drop {stop.level.value}</b>  [{_h(stop.timestamp)}{timing}]\n"
        f"Open: <code>{stop.spx_open:,.0f}</code> → Now: <code>{stop.spx_current:,.0f}</code>  "
        f"(<code>{stop.drop_pct*100:+.1f}%</code>)\n"
        f"{advice}"
    )


def _is_es_short_put_state(state: dict | None) -> bool:
    if not state:
        return False
    strategy_key = str(state.get("strategy_key") or "").strip().lower()
    if strategy_key == "es_short_put":
        return True
    underlying = str(state.get("underlying") or "").upper()
    strategy = str(state.get("strategy") or "").lower()
    return underlying == "/ES" and "short put" in strategy


def _is_es_put_position(position: dict) -> bool:
    text = f"{position.get('symbol', '')} {position.get('description', '')}".upper()
    quantity = _num(position.get("quantity")) or 0.0
    return abs(quantity) > 0 and "/ES" in text and "PUT" in text


def _num(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_es_credit_stop() -> EsStopResult:
    state = read_state()
    if not _is_es_short_put_state(state):
        return EsStopResult(level=EsStopLevel.NONE, observed=True)

    entry_premium = _num(state.get("actual_premium")) or _num(state.get("model_premium"))
    if entry_premium is None or entry_premium <= 0:
        return EsStopResult(level=EsStopLevel.NONE, observed=True)

    try:
        from schwab.client import get_account_positions

        positions_payload = get_account_positions()
    except Exception:
        return EsStopResult(level=EsStopLevel.NONE)

    if (
        not positions_payload.get("configured")
        or not positions_payload.get("authenticated")
        or positions_payload.get("stale")
    ):
        return EsStopResult(level=EsStopLevel.NONE)

    position = next((_pos for _pos in positions_payload.get("positions", []) if _is_es_put_position(_pos)), None)
    if position is None:
        return EsStopResult(level=EsStopLevel.NONE)

    mark = _num(position.get("mark"))
    if mark is None:
        return EsStopResult(level=EsStopLevel.NONE)

    _trigger = _ES_P.stop_mult          # 10.0 — from EsShortPutParams (SPEC-121)
    _warn    = ES_STOP_WARN_MULT        # 2.0 — fixed early-warning line, decoupled from trigger

    ratio = mark / entry_premium
    if ratio >= _trigger:
        level = EsStopLevel.TRIGGER
    elif ratio >= _warn:
        level = EsStopLevel.WARNING
    else:
        level = EsStopLevel.NONE
    return EsStopResult(level=level, entry_premium=entry_premium, current_mark=mark, ratio=ratio, observed=True)


def _format_es_stop_alert(result: EsStopResult) -> str:
    entry    = result.entry_premium or 0.0
    mark     = result.current_mark or 0.0
    ratio    = result.ratio or 0.0
    _trigger = _ES_P.stop_mult
    _warn    = ES_STOP_WARN_MULT
    # SPEC-136 #3 — 数字带语义（入场 → 现在几倍）；标题保留英文 token
    # （_classify_intraday 按 TRIGGERED / Stop Watch / cleared 路由类别）
    if result.level == EsStopLevel.TRIGGER:
        return (
            f"🚨 <b>/ES Short Put — Credit Stop TRIGGERED [×{_trigger:.0f} mark]</b>\n"
            f"止损触发：权利金已翻至入场价 {ratio:.1f} 倍"
            f"（入场 <code>{entry:.2f}</code> → 现在 <code>{mark:.2f}</code>，"
            f"触发线 ×{_trigger:.0f}）——规则要求平仓。\n"
            "<i>/closed after exiting.</i>"
        )
    if result.level == EsStopLevel.WARNING:
        stop_mark = entry * _trigger
        return (
            f"⚠️ <b>/ES Short Put — Stop Watch [×{_warn:.0f} mark]</b>\n"
            f"接近止损线：权利金已到入场价 {ratio:.2f} 倍"
            f"（入场 <code>{entry:.2f}</code> → 现在 <code>{mark:.2f}</code>）。\n"
            f"权利金到 ×{_trigger:.0f}（mark ≥ <code>{stop_mark:.2f}</code>）即触发止损——"
            "盯紧，继续上行就准备平仓。"
        )
    return (
        f"✅ <b>/ES Short Put — Stop watch cleared</b>\n"
        f"止损观察解除：权利金已回落到 ×{_warn:.0f} 观察线以下"
        f"（现在 <code>{mark:.2f}</code>）。"
    )


def _parse_quote_time(quote: dict) -> datetime | None:
    raw = quote.get("quote_time")
    if raw in (None, ""):
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ET)
    return ts.astimezone(ET)


def _is_quote_stale_daily(quote: dict, now: datetime) -> bool:
    ts = _parse_quote_time(quote)
    if ts is None:
        return True
    return ts.date() < (now.date() - timedelta(days=1))


def _read_es_hv_paper_records(path: Path = _ES_HV_PAPER_LOG) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _append_es_hv_paper_record(record: dict, path: Path = _ES_HV_PAPER_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _business_days_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    days = 0
    cur = start
    while cur < end:
        cur += timedelta(days=1)
        if cur.weekday() < 5 and cur.strftime("%Y-%m-%d") not in _ALL_HOLIDAYS:
            days += 1
    return days


def _es_hv_active_slots(records: list[dict], today: date) -> int:
    active = 0
    for row in records:
        raw = row.get("signal_date")
        if not raw:
            continue
        try:
            signal_date = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        if 0 <= (today - signal_date).days <= _ES_HV_ENTRY_DTE:
            active += 1
    return min(active, _ES_HV_MAX_SLOTS)


def _es_hv_cadence_ok(records: list[dict], today: date, active_slots: int) -> bool:
    signal_dates: list[date] = []
    for row in records:
        raw = row.get("signal_date")
        if not raw:
            continue
        try:
            signal_dates.append(date.fromisoformat(str(raw)[:10]))
        except ValueError:
            continue
    if not signal_dates:
        return True
    min_gap = 10 if active_slots >= 4 else 5
    return _business_days_between(max(signal_dates), today) >= min_gap


def _format_es_hv_stale_alert(vix_quote: dict) -> str:
    return (
        "⚠️ <b>/ES HV Ladder — VIX data unavailable/stale</b>\n"
        f"Quote time: <code>{_h(vix_quote.get('quote_time') or 'missing')}</code>\n"
        "No paper entry evaluated. Production /ES logic unchanged."
    )


def _format_es_hv_paper_signal(record: dict) -> str:
    return (
        "📡 <b>/ES HV Ladder — Paper / Research Signal</b>\n"
        f"Date: <code>{_h(record['signal_date'])}</code>\n"
        f"VIX: <code>{record['vix_at_signal']:.1f}</code> (gate ≥ {_ES_HV_VIX_MIN_ENTRY:.0f})\n"
        f"Trend: <code>{_h(record.get('trend', 'BULLISH'))}</code>\n"
        f"Active slots: <code>{record['active_slots']}/{_ES_HV_MAX_SLOTS}</code>\n"
        f"Entry DTE: <code>{_ES_HV_ENTRY_DTE}</code> · target |delta| <code>{_ES_HV_TARGET_DELTA:.2f}</code>\n"
        f"Est. strike: <code>{record['est_strike']:.0f}</code> · est. premium: <code>{record['est_premium']:.2f}</code>\n"
        "纸面研究信号——不会下任何真实单。"
    )


def _check_es_hv_ladder_paper_signal(
    *,
    now: datetime | None = None,
    vix_quote: dict | None = None,
    spx_quote: dict | None = None,
    paper_log_path: Path = _ES_HV_PAPER_LOG,
) -> str | None:
    now = now or datetime.now(ET)
    today_str = now.strftime("%Y-%m-%d")
    vix_quote = vix_quote if vix_quote is not None else get_vix_quote()
    if _is_quote_stale_daily(vix_quote, now):
        if _intraday_state.get("es_hv_stale_alerted_date") == today_str:
            return None
        _intraday_state["es_hv_stale_alerted_date"] = today_str
        return _format_es_hv_stale_alert(vix_quote)

    vix = _num(vix_quote.get("last"))
    if vix is None or vix < _ES_HV_VIX_MIN_ENTRY:
        return None
    if _intraday_state.get("es_hv_signal_alerted_date") == today_str:
        return None

    spx_quote = spx_quote if spx_quote is not None else get_spx_quote()
    spx = _num(spx_quote.get("last"))
    if spx is None or spx <= 0:
        return None

    try:
        from backtest.pricer import find_strike_for_delta, put_price
        from signals.trend import TrendSignal, fetch_spx_history, get_current_trend

        trend = get_current_trend(fetch_spx_history(period="2y"), current_spx=spx)
        if trend.signal != TrendSignal.BULLISH:
            return None
        sigma = vix / 100.0
        strike = float(find_strike_for_delta(spx, _ES_HV_ENTRY_DTE, sigma, _ES_HV_TARGET_DELTA, is_call=False))
        premium = float(put_price(spx, strike, _ES_HV_ENTRY_DTE, sigma))
    except Exception:
        log.exception("_check_es_hv_ladder_paper_signal: failed to evaluate paper signal")
        return None

    records = _read_es_hv_paper_records(paper_log_path)
    active_slots = _es_hv_active_slots(records, now.date())
    if active_slots >= _ES_HV_MAX_SLOTS or not _es_hv_cadence_ok(records, now.date(), active_slots):
        return None

    record = {
        "signal_date": today_str,
        "timestamp": now.isoformat(timespec="seconds"),
        "vix_at_signal": round(vix, 4),
        "active_slots": active_slots,
        "entry_dte": _ES_HV_ENTRY_DTE,
        "target_delta": _ES_HV_TARGET_DELTA,
        "est_spx": round(spx, 4),
        "est_strike": round(strike, 4),
        "est_premium": round(premium, 4),
        "trend": trend.signal.value,
        "status": "signal",
    }
    _append_es_hv_paper_record(record, paper_log_path)
    _intraday_state["es_hv_signal_alerted_date"] = today_str
    return _format_es_hv_paper_signal(record)


def _check_spx_profit_target() -> tuple[bool, float | None, bool]:
    """
    Return (target_reached, captured_pct, via_fallback).
    Primary path: state.json open SPX position (min_hold_days gate enforced).
    Fallback path: Schwab-direct averagePrice calculation (min_hold gate skipped).
    via_fallback=True when fallback path was used.
    """
    state = read_state()
    if state and state.get("underlying") == "SPX":
        entry_premium = _num(state.get("actual_premium")) or _num(state.get("model_premium"))
        if entry_premium and entry_premium > 0:
            return _profit_check_from_state(state, entry_premium)

    return _profit_check_from_schwab()


def _profit_check_from_state(state: dict, entry_premium: float) -> tuple[bool, float | None, bool]:
    """Primary path: compute capture% from state.json + Schwab market_value."""
    contracts = _num(state.get("contracts")) or 1
    opened_at = state.get("opened_at")

    days_held = 0
    if opened_at:
        try:
            days_held = (date.today() - date.fromisoformat(str(opened_at))).days
        except Exception:
            pass

    try:
        from schwab.client import get_account_positions
        positions_payload = get_account_positions()
    except Exception:
        return False, None, False

    if (not positions_payload.get("configured")
            or not positions_payload.get("authenticated")
            or positions_payload.get("stale")):
        return False, None, False

    # SPEC-099 follow-up fix: schwab/client.py never sets a `category` field;
    # the legacy `category == "spx_options"` filter never matched real Schwab data.
    # Match SPX option legs by asset_type + symbol (same as fallback path) and
    # sum market_value across all legs to get the spread's net close cost.
    spx_legs = [
        p for p in positions_payload.get("positions", [])
        if p.get("asset_type") == "OPTION" and "SPX" in (p.get("symbol") or "")
    ]
    if not spx_legs:
        return False, None, False

    net_mv = sum((_num(p.get("market_value")) or 0.0) for p in spx_legs)

    # market_value is negative for a short spread (cost to close = abs(mv))
    close_cost_pts = abs(net_mv) / contracts / 100
    captured_pct   = (entry_premium - close_cost_pts) / entry_premium * 100

    PROFIT_TARGET_PCT = 60.0
    MIN_HOLD_DAYS     = 10
    reached = captured_pct >= PROFIT_TARGET_PCT and days_held >= MIN_HOLD_DAYS
    return reached, round(captured_pct, 1), False


def _identify_spx_spread_legs(positions: list[dict]) -> tuple[dict, dict] | None:
    """Pair short and long SPX option legs into a vertical spread, or None."""
    spx_opts = [
        p for p in positions
        if p.get("asset_type") == "OPTION" and "SPX" in (p.get("symbol") or "")
    ]
    if len(spx_opts) != 2:
        return None
    short = next((p for p in spx_opts if (p.get("quantity") or 0) < 0), None)
    long_ = next((p for p in spx_opts if (p.get("quantity") or 0) > 0), None)
    if short is None or long_ is None:
        return None
    return short, long_


def _profit_check_from_schwab() -> tuple[bool, float | None, bool]:
    """
    Fallback path: compute capture% directly from Schwab averagePrice + marketValue.
    Skips min_hold_days gate (no opened_at ground truth when state.json is missing).
    """
    try:
        from schwab.client import get_account_positions
        positions_payload = get_account_positions()
    except Exception:
        return False, None, True

    if (not positions_payload.get("configured")
            or not positions_payload.get("authenticated")
            or positions_payload.get("stale")):
        return False, None, True

    legs = _identify_spx_spread_legs(positions_payload.get("positions", []))
    if legs is None:
        return False, None, True

    short_leg, long_leg = legs
    entry_credit_ps = abs(short_leg.get("average_price") or 0) - abs(long_leg.get("average_price") or 0)
    if entry_credit_ps <= 0:
        return False, None, True

    contracts = abs(short_leg.get("quantity") or 0)
    if contracts == 0:
        return False, None, True

    net_mv = (short_leg.get("market_value") or 0) + (long_leg.get("market_value") or 0)
    close_cost_ps = abs(net_mv) / contracts / 100
    captured_pct  = (entry_credit_ps - close_cost_ps) / entry_credit_ps * 100

    PROFIT_TARGET_PCT = 60.0
    reached = captured_pct >= PROFIT_TARGET_PCT
    return reached, round(captured_pct, 1), True


def _check_broker_state_mismatch() -> str | None:
    """
    Return a warning message if Schwab shows open SPX option positions but local
    state.json has no matching open record. Returns None when consistent or broker unavailable.
    """
    state = read_state()
    try:
        from schwab.client import get_account_positions
        positions_payload = get_account_positions()
    except Exception:
        return None

    if (not positions_payload.get("configured")
            or not positions_payload.get("authenticated")
            or positions_payload.get("stale")):
        return None

    spx_options = [
        p for p in positions_payload.get("positions", [])
        if p.get("asset_type") == "OPTION" and "SPX" in (p.get("symbol") or "")
    ]
    if state is None and spx_options:
        return (
            "⚠️ <b>Broker-State Mismatch</b>\n"
            f"Schwab shows {len(spx_options)} open SPX option leg(s) but "
            f"local state has no open position recorded.\n"
            f"<i>Run /opened to register, or /sync to auto-import.</i>"
        )
    return None


def _alert_timing_label(timestamp: str, realtime: bool | None) -> str:
    sent_at = datetime.now(ET).strftime("%Y-%m-%d %H:%M")
    if realtime is False:
        return f" | sent {_h(sent_at)} | delayed — non-realtime quote"
    try:
        bar_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        sent_dt = datetime.now(ET)
        delay_minutes = max(int((sent_dt - bar_time).total_seconds() // 60), 0)
    except ValueError:
        return f" | sent {_h(sent_at)}"
    if delay_minutes > _STALE_QUOTE_MINUTES:
        return f" | sent {_h(sent_at)} | delayed {delay_minutes}m"
    return f" | sent {_h(sent_at)}"


def _days_held(state: dict | None) -> int | None:
    if not state or not state.get("opened_at"):
        return None
    try:
        return max((date.today() - date.fromisoformat(str(state["opened_at"]))).days, 0)
    except ValueError:
        return None


def _position_tenor(state: dict | None) -> str | None:
    if not state:
        return None
    if state.get("expiry"):
        try:
            return f"{max((date.fromisoformat(str(state['expiry'])) - date.today()).days, 0)} DTE remaining"
        except ValueError:
            pass
    held = _days_held(state)
    if held is not None:
        return f"opened {held}d ago"
    return None


def _morning_label(morning: dict) -> str:
    # SPEC-136 词表合规：WAIT 不在 Action State 词表 → NO ENTRY；
    # 裸 strategy_key 大写 → catalog 人话名（label_human 单源）
    action = str(morning.get("position_action") or "").upper()
    key = str(morning.get("strategy_key") or "")
    if action == "WAIT" or key == "reduce_wait":
        return "NO ENTRY"
    try:
        name = strategy_descriptor(key).name
    except Exception:
        name = key.upper()
    return " ".join(part for part in (action, name) if part)


def _format_eod_snapshot(
    rec: Recommendation,
    morning: dict | None,
    state: dict | None,
) -> str:
    desc = strategy_descriptor(rec.strategy_key)
    term_dir = "backwardation ⚠️" if rec.vix_snapshot.backwardation else "contango"
    if morning is None:
        comparison = "ℹ️ Morning snapshot unavailable (bot restarted today)."
    elif (
        morning.get("strategy_key") != rec.strategy_key
        or morning.get("position_action") != rec.position_action
    ):
        comparison = (
            "⚠️ Signal changed from morning:\n"
            f"  Morning → {_h(_morning_label(morning))}  [VIX Trend {_h(morning.get('vix_trend', '?'))}]\n"
            f"  EOD     → {_h(_morning_label({'position_action': rec.position_action, 'strategy_key': rec.strategy_key}))}  "
            f"[VIX Trend {_h(rec.vix_snapshot.trend.value)}]\n"
            "  Re-evaluate before tomorrow's open."
        )
    else:
        comparison = "✅ Signal confirmed — same as morning push."

    position_line = ""
    if state:
        bits = [state.get("strategy", "?"), state.get("underlying", "?")]
        tenor = _position_tenor(state)
        if tenor:
            bits.append(tenor)
        position_line = f"\n📋 Open Position: {' | '.join(_h(bit) for bit in bits if bit)}"

    vix3m_value = "n/a" if rec.vix_snapshot.vix3m is None else f"{rec.vix_snapshot.vix3m:.2f}"
    return (
        f"🌙 <b>EOD Signal Snapshot — {_h(rec.vix_snapshot.date)}</b>\n"
        f"{'─' * 32}\n"
        f"VIX Close  <code>{rec.vix_snapshot.vix:.2f}</code> [{_h(rec.vix_snapshot.regime.value)}]  "
        f"Trend: {_h(rec.vix_snapshot.trend.value)}\n"
        f"IVR  <code>{rec.iv_snapshot.iv_rank:.0f}</code>  IVP  <code>{rec.iv_snapshot.iv_percentile:.0f}</code>\n"
        f"SPX Trend  <code>{_h(rec.trend_snapshot.signal.value)}</code>  "
        f"(<code>{rec.trend_snapshot.ma_gap_pct*100:+.1f}%</code> vs 50MA)\n"
        f"Term struct  <code>{_h(term_dir)}</code>  (VIX3M <code>{vix3m_value}</code>)\n\n"
        f"Recommendation:  <b>{_h(desc.name)}</b>\n"
        f"Action:  <code>{_h(rec.position_action)}</code>\n\n"
        f"{comparison}"
        f"{position_line}\n"
        f"{'─' * 32}\n"
        "SPX options tradeable until 4:15pm ET"
    )


# ── Intraday monitor ───────────────────────────────────────────────────────────

def _reset_intraday_state() -> None:
    """Reset per-session state at market open each day."""
    global _morning_snapshot
    _intraday_state["spike_level"]      = SpikeLevel.NONE
    _intraday_state["stop_level"]       = StopLevel.NONE
    _intraday_state["es_stop_level"]    = EsStopLevel.NONE
    _intraday_state["profit_alerted"]   = False
    _intraday_state["mismatch_alerted"] = False
    _intraday_state["es_hv_signal_alerted_date"] = None
    _intraday_state["es_hv_stale_alerted_date"] = None
    _morning_snapshot = None
    log.info("Intraday state reset for new session.")


def _format_etrade_reauth_message() -> str:
    from etrade.auth import public_auth_url

    return (
        "⚠️ <b>E-Trade token expired</b>\n"
        f"Please visit <a href=\"{_h(public_auth_url())}\">/etrade/auth</a> to complete manual authorization."
    )


async def _safe_send(bot: Bot, chat_id: str, text: str, *,
                     meta: dict | None = None, **kwargs) -> bool:
    """H-4 (2026-07-06): unattended sends must never die on a formatting 400.
    Try HTML; on BadRequest (parse failure) resend as plain text — delivery
    beats formatting. Outcomes feed logs/push_stats.json via event_push so the
    heartbeat surfaces failures. Interactive command replies keep their direct
    reply_* calls (a user watching the chat sees those fail).

    SPEC-130: host guard first — same deny-by-default as event_push._send.
    Unattended bot sends only fire on hosts whose launchd plist declares
    SPX_PUSH_ENABLE=1 (oldair production); everywhere else they go dark.

    SPEC-139 #22 缺口修复（2026-07-13）：本异步通道此前只记 push_stats、
    从不写 send-ledger——bot 进程的全部排程推送（晨报 09:35 / digest 15:55 /
    E-Trade / ladder / 盘中）在台账上隐身，只有同步 gateway.push（web/launchd
    脚本）有记录。现完整镜像 event_push._send 的契约：真实送达（sent 或
    plain fallback）后写 _record_ledger；`meta` 由 gateway.apush 组装传入，
    裸调用 meta=None 仍记 null 字段行（与同步侧同语义）。台账写入严格位于
    host guard 之后（禁发即禁记）。"""
    from telegram.error import BadRequest
    from notify.event_push import (PUSH_ENABLE_ENV, _record_ledger,
                                   _record_push, _to_plain, push_enabled)
    if not push_enabled():
        log.info("telegram_bot: %s != 1 — unattended send suppressed "
                 "(SPEC-130 host guard)", PUSH_ENABLE_ENV)
        return False
    quiet = bool(kwargs.get("disable_notification"))
    try:
        await bot.send_message(chat_id=chat_id, text=text,
                               parse_mode=ParseMode.HTML, **kwargs)
        _record_push("sent")
        _record_ledger(meta, quiet=quiet, fallback=False)
        return True
    except BadRequest as exc:
        log.warning("telegram send BadRequest (%s) — retrying as plain text", exc)
        try:
            await bot.send_message(chat_id=chat_id, text=_to_plain(text), **kwargs)
            _record_push("fallback")
            _record_ledger(meta, quiet=quiet, fallback=True)
            return True
        except Exception:
            log.exception("telegram plain-text retry failed")
            _record_push("failed")
            return False
    except Exception:
        log.exception("telegram send failed")
        _record_push("failed")
        return False


async def _maybe_send_etrade_token_alert(bot: Bot, chat_id: str) -> None:
    from etrade.auth import clear_token_issue, is_token_valid, load_alert_state, mark_token_alert_sent

    if is_token_valid():
        clear_token_issue()
        return
    state = load_alert_state()
    if not state.get("invalid") or state.get("alert_sent"):
        return
    from notify.gateway import apush
    await apush(bot, chat_id, "ACTION", "系统状态", "E-Trade 需要重新授权",
                _format_etrade_reauth_message(), dedupe_key="etrade_reauth")
    mark_token_alert_sent()


async def scheduled_etrade_token_renewal(bot: Bot, chat_id: str) -> None:
    from etrade.auth import renew_access_token

    result = renew_access_token()
    if result.get("ok"):
        log.info("E-Trade token renewed successfully.")
        return
    log.warning("E-Trade token renewal failed: %s", result.get("reason"))
    try:
        await _maybe_send_etrade_token_alert(bot, chat_id)
    except Exception:
        log.exception("scheduled_etrade_token_renewal: failed to send alert")


def _classify_intraday(msg: str) -> tuple[str, str, str | None]:
    """SPEC-126 transitional: (category, about, clears_key) from message text."""
    about = "持仓 /ES Short Put" if "/ES Short Put" in msg else "系统状态"
    if "TRIGGERED" in msg or "🚨" in msg:
        return "ALERT", about, None
    if "Stop Watch" in msg:
        # dedupe-free (repeat watches escalate by design) but keyed for clears
        return "ACTION", about, None
    if "cleared" in msg or "✅" in msg:
        return "STATE", about, None
    if "⚠" in msg or "mismatch" in msg or "profit target" in msg.lower():
        return "ACTION", about, None
    return "STATE", about, None


async def intraday_monitor(bot: Bot, chat_id: str) -> None:
    """
    Polls VIX and SPX intraday signals every 5 minutes during market hours.
    Pushes only when a signal level escalates (NONE→WARNING, WARNING→ALERT, etc.)
    or when elevated conditions clear back to normal.
    """
    if not is_market_open():
        return

    vix_quote = None
    spx_quote = None
    try:
        try:
            vix_quote = get_vix_quote()
            spx_quote = get_spx_quote()
            spike = get_vix_spike_from_quote(vix_quote)
            stop = get_spx_stop_from_quote(spx_quote)
        except Exception:
            spike = get_vix_spike(interval="5m")
            stop = get_spx_stop(interval="5m")
    except Exception:
        log.exception("intraday_monitor: failed to fetch signals")
        return

    prev_spike = _intraday_state["spike_level"]
    prev_stop  = _intraday_state["stop_level"]
    prev_es_stop = _intraday_state["es_stop_level"]

    msgs: list[str] = []

    # VIX escalation
    if _SPIKE_RANK[spike.level] > _SPIKE_RANK[prev_spike]:
        msgs.append(_format_spike_alert(spike))

    # SPX stop escalation
    if _STOP_RANK[stop.level] > _STOP_RANK[prev_stop]:
        msgs.append(_format_stop_alert(stop))
        # Open position + TRIGGER → add close recommendation
        if stop.level == StopLevel.TRIGGER:
            state = read_state()
            if state:
                msgs.append(
                    f"🔴 <b>Close Signal:</b> SPX -2% from open.\n"
                    f"You have an open position: <b>{_h(state['strategy'])}</b> on {_h(state['underlying'])} "
                    f"(since {_h(state.get('opened_at', '?'))}).\n"
                    f"<i>Consider closing. Send /closed after exiting.</i>"
                )

    # Conditions cleared after being elevated
    was_elevated = (prev_spike != SpikeLevel.NONE or prev_stop  != StopLevel.NONE)
    now_clear    = (spike.level == SpikeLevel.NONE and stop.level  == StopLevel.NONE)
    if was_elevated and now_clear:
        msgs.append(
            f"✅ <b>Intraday conditions cleared</b>\n"
            f"VIX and SPX back to normal levels. "
            f"Run /today to re-check entry conditions."
        )

    es_stop = _check_es_credit_stop()
    if es_stop.observed:
        if _ES_STOP_RANK[es_stop.level] > _ES_STOP_RANK[prev_es_stop]:
            msgs.append(_format_es_stop_alert(es_stop))
        elif (
            prev_es_stop != EsStopLevel.NONE
            and es_stop.level == EsStopLevel.NONE
            and es_stop.current_mark is not None
        ):
            msgs.append(_format_es_stop_alert(es_stop))

    if vix_quote is not None and spx_quote is not None and vix_quote.get("quote_time"):
        try:
            hv_ladder_msg = _check_es_hv_ladder_paper_signal(vix_quote=vix_quote, spx_quote=spx_quote)
            if hv_ladder_msg:
                msgs.append(hv_ladder_msg)
        except Exception:
            log.exception("intraday_monitor: ES HV Ladder paper check failed")

    # Broker-state mismatch check — fires once per session (SPEC-099 Layer B)
    if not _intraday_state["mismatch_alerted"]:
        try:
            mismatch_msg = _check_broker_state_mismatch()
            if mismatch_msg:
                msgs.append(mismatch_msg)
                _intraday_state["mismatch_alerted"] = True
        except Exception:
            log.exception("intraday_monitor: broker state mismatch check failed")

    # SPX profit target check — fires once per session when ≥60% captured (SPEC-099 Layer C adds fallback)
    if not _intraday_state["profit_alerted"]:
        try:
            reached, captured_pct, via_fallback = _check_spx_profit_target()
            if reached and captured_pct is not None:
                state = read_state()
                strategy = (state or {}).get("strategy", "SPX Credit Spread")
                fallback_line = "⚠️ via Schwab fallback · min hold gate skipped\n" if via_fallback else ""
                hold_note = "" if via_fallback else " · min hold: 10d ✓"
                msgs.append(
                    f"🟢 <b>Profit Target Reached — {_h(strategy)}</b>\n"
                    f"{fallback_line}"
                    f"Captured: <code>{captured_pct:.1f}%</code> of credit "
                    f"(target: 60%{hold_note})\n"
                    f"<i>Consider closing. Send /closed after exiting.</i>"
                )
                _intraday_state["profit_alerted"] = True
        except Exception:
            log.exception("intraday_monitor: profit target check failed")

    # Persist new state
    _intraday_state["spike_level"] = spike.level
    _intraday_state["stop_level"]  = stop.level
    if es_stop.observed:
        _intraday_state["es_stop_level"] = es_stop.level

    for msg in msgs:
        try:
            # SPEC-126 transitional classification: constructors still build
            # plain strings; the signature map below routes them until each
            # site passes categories natively. TRIGGER/spike = ALERT (rings),
            # watch/mismatch/profit-target = ACTION, cleared = STATE (quiet,
            # follows today's alert via `clears`).
            from notify.gateway import apush
            cat, about, clears = _classify_intraday(msg)
            await apush(bot, chat_id, cat, about, "", msg, clears=clears)
        except Exception:
            log.exception("intraday_monitor: failed to send message")
    try:
        await _maybe_send_etrade_token_alert(bot, chat_id)
    except Exception:
        log.exception("intraday_monitor: E-Trade token alert check failed")


def _format_backtest_summary(trades, metrics: dict) -> str:
    if "error" in metrics:
        return f"⚠️ Backtest error: {metrics['error']}"

    by_strat = "\n".join(
        f"  {n:<28} n={s['n']:>2}  win={s['win_rate']*100:.0f}%  avg=${s['avg_pnl']:+.0f}"
        for n, s in metrics["by_strategy"].items()
    )
    return (
        f"📈 <b>Backtest Summary (1 year)</b>\n"
        f"{'─' * 32}\n"
        f"Trades:     <code>{metrics['total_trades']}</code>\n"
        f"Win rate:   <code>{metrics['win_rate']*100:.1f}%</code>\n"
        f"Expectancy: <code>${metrics['expectancy']:+.0f}</code> / trade\n"
        f"Total P&amp;L: <code>${metrics['total_pnl']:+,.0f}</code>\n"
        f"Max DD:     <code>${metrics['max_drawdown']:+,.0f}</code>\n"
        f"Sharpe:     <code>{metrics['sharpe']:.2f}</code>\n"
        f"Calmar:     <code>{metrics['calmar']:.1f}</code>\n"
        f"CVaR 5%:    <code>${metrics['cvar5']:+,.0f}</code>\n"
        f"Skew:       <code>{metrics['skew']:+.2f}</code>\n\n"
        f"<b>By strategy:</b>\n<pre>{by_strat}</pre>\n"
        f"<i>Precision B (Black-Scholes, no slippage)</i>"
    )


# ── Command handlers ───────────────────────────────────────────────────────────

async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Fetching signals…")
    try:
        rec = get_recommendation(use_intraday=True)
        _safe_append_recommendation_event(rec=rec, source="telegram_today", mode="intraday")
        await update.message.reply_text(
            _format_recommendation(rec),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.exception("cmd_today failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


# ── Strategy options for manual entry keyboard ────────────────────────────────

_MANUAL_ENTRY_OPTIONS = [
    (item["key"], item["name"], item["underlying"])
    for item in manual_entry_options()
]


def _manual_entry_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard listing all tradeable strategies for manual /entered."""
    buttons = [
        [InlineKeyboardButton(
            f"{strat} ({und})",
            callback_data=f"enter:{key}:{und}",
        )]
        for key, strat, und in _MANUAL_ENTRY_OPTIONS
    ]
    return InlineKeyboardMarkup(buttons)


# ── Position formatting helper ─────────────────────────────────────────────────

def _format_position(state: dict) -> str:
    roll_line = ""
    if state.get("roll_count", 0) > 0:
        roll_line = (
            f"Rolls:    <code>{state['roll_count']}</code> "
            f"(last: {_h(state.get('rolled_at', '?'))})\n"
        )
    notes = state.get("notes") or []
    notes_line = ""
    if notes:
        notes_block = "\n".join(f"  • {_h(n)}" for n in notes)
        notes_line = f"\nNotes:\n{notes_block}\n"

    return (
        f"📋 <b>Open Position</b>\n"
        f"{'─' * 28}\n"
        f"Strategy:  <b>{_h(state['strategy'])}</b>\n"
        f"Underlying: <code>{_h(state['underlying'])}</code>\n"
        f"Opened:    <code>{_h(state.get('opened_at', '?'))}</code>\n"
        f"{roll_line}"
        f"{notes_line}"
        f"{'─' * 28}\n"
        f"<i>/rolled — log a roll  |  /note — add remark  |  /closed — exit</i>"
    )


# ── Command handlers ───────────────────────────────────────────────────────────

def _account_keyboard(mode: str) -> InlineKeyboardMarkup:
    """Inline keyboard for account selection. mode: 'enter' | 'close'."""
    if mode == "close":
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("Schwab",  callback_data="aclose:schwab"),
            InlineKeyboardButton("E-Trade", callback_data="aclose:etrade"),
            InlineKeyboardButton("Both",    callback_data="aclose:all"),
        ]])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Schwab",  callback_data="aenter:schwab"),
        InlineKeyboardButton("E-Trade", callback_data="aenter:etrade"),
        InlineKeyboardButton("Both",    callback_data="aenter:both"),
    ]])


async def cmd_entered(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Record a new position.
      /entered         → use current recommendation (auto) → asks account
      /entered manual  → show strategy keyboard → asks account
    """
    args = ctx.args or []
    if args and args[0].lower() == "manual":
        await update.message.reply_text(
            "Select the strategy you entered:",
            reply_markup=_manual_entry_keyboard(),
        )
        return

    # Auto mode: use current recommendation
    try:
        rec = get_recommendation(use_intraday=True)
        if rec.strategy == StrategyName.REDUCE_WAIT:
            await update.message.reply_text(
                "ℹ️ Current recommendation is <b>Reduce / Wait</b> — no position to record.\n"
                "Use <code>/entered manual</code> to record a position regardless.",
                parse_mode=ParseMode.HTML,
            )
            return
        ctx.user_data["pending_entry"] = {
            "strategy": rec.strategy.value,
            "underlying": rec.underlying,
            "strategy_key": rec.strategy_key,
        }
        await update.message.reply_text(
            f"Strategy: <b>{_h(rec.strategy.value)}</b> — which account?",
            parse_mode=ParseMode.HTML,
            reply_markup=_account_keyboard("enter"),
        )
    except Exception as e:
        log.exception("cmd_entered failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def handle_entry_account_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: account selection after /entered."""
    query = update.callback_query
    await query.answer()
    _, account = query.data.split(":", 1)
    pending = ctx.user_data.get("pending_entry")
    if not pending:
        await query.edit_message_text("⚠️ Session expired — run /entered again.")
        return
    accounts = ["schwab", "etrade"] if account == "both" else [account]
    for acct in accounts:
        write_state(
            pending["strategy"], pending["underlying"],
            strategy_key=pending["strategy_key"], account=acct,
        )
    ctx.user_data.pop("pending_entry", None)
    acct_label = "Schwab + E-Trade" if account == "both" else account.capitalize()
    await query.edit_message_text(
        f"✅ <b>Position recorded</b> [{acct_label}]\n"
        f"Strategy: <b>{_h(pending['strategy'])}</b> on <code>{_h(pending['underlying'])}</code>\n"
        f"<i>Use /note to add details, /closed when done.</i>",
        parse_mode=ParseMode.HTML,
    )


_VALID_MANUAL_PAIRS = {(k, u) for k, _, u in _MANUAL_ENTRY_OPTIONS}
_MANUAL_NAME_BY_KEY = {k: n for k, n, _ in _MANUAL_ENTRY_OPTIONS}


async def handle_manual_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for inline keyboard strategy selection in /entered manual → asks account."""
    query = update.callback_query
    await query.answer()
    _, strategy_key, underlying = query.data.split(":", 2)
    if (strategy_key, underlying) not in _VALID_MANUAL_PAIRS:
        await query.edit_message_text("⚠️ Invalid strategy selection.")
        return
    try:
        strategy = _MANUAL_NAME_BY_KEY[strategy_key]
        ctx.user_data["pending_entry"] = {
            "strategy": strategy,
            "underlying": underlying,
            "strategy_key": strategy_key,
        }
        await query.edit_message_text(
            f"Strategy: <b>{_h(strategy)}</b> — which account?",
            parse_mode=ParseMode.HTML,
            reply_markup=_account_keyboard("enter"),
        )
    except Exception as e:
        log.exception("handle_manual_entry failed")
        await query.edit_message_text(f"⚠️ Error: {e}")


async def _do_close_and_rescan(
    reply_fn,
    state: dict,
    note: str | None,
    account: str | None,
) -> None:
    """Close position and send re-entry scan. Shared by cmd_closed and handle_close_account_cb."""
    close_position(note=note, account=account)
    acct_label = f" [{account.capitalize()}]" if account else ""
    note_line = f"\nNote: <i>{_h(note)}</i>" if note else ""
    await reply_fn(
        f"✅ <b>Position closed</b>{acct_label}\n"
        f"Strategy: <b>{_h(state['strategy'])}</b> on <code>{_h(state['underlying'])}</code>\n"
        f"Opened: <code>{_h(state.get('opened_at', '?'))}</code>{note_line}",
        parse_mode=ParseMode.HTML,
    )
    # Only run re-scan when strategy is fully closed (no accounts remain)
    if read_state() is None:
        try:
            rec = get_recommendation(use_intraday=is_market_open())
            _safe_append_recommendation_event(rec=rec, source="post_close_rescan", mode="intraday")
            await reply_fn(
                "🔄 <b>Re-entry scan</b> — fresh recommendation:\n\n" + _format_recommendation(rec),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            log.exception("_do_close_and_rescan: rescan failed (non-fatal)")


async def cmd_closed(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Mark the current position as closed.
      /closed               → no reason recorded
      /closed 60pct profit  → stores the note alongside the close

    When multiple accounts are open, asks which account to close.
    After fully closing, immediately pushes a fresh recommendation.
    """
    note = " ".join(ctx.args) if ctx.args else None
    try:
        state = read_state()
        if state is None:
            await update.message.reply_text("ℹ️ No open position on record to close.")
            return
        all_pos = read_all_positions()
        positions = (all_pos or {}).get("positions", [])
        if len(positions) > 1:
            ctx.user_data["pending_close_note"] = note
            accounts = ", ".join(p.get("account", "?").capitalize() for p in positions)
            await update.message.reply_text(
                f"<b>{_h(state['strategy'])}</b> open in: {accounts}\nWhich account to close?",
                parse_mode=ParseMode.HTML,
                reply_markup=_account_keyboard("close"),
            )
            return
        await _do_close_and_rescan(update.message.reply_text, state, note, account=None)
    except Exception as e:
        log.exception("cmd_closed failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def handle_close_account_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: account selection after /closed with multiple open legs."""
    query = update.callback_query
    await query.answer()
    _, account_raw = query.data.split(":", 1)
    account = None if account_raw == "all" else account_raw
    state = read_state()
    if state is None:
        await query.edit_message_text("ℹ️ No open position found.")
        return
    note = ctx.user_data.pop("pending_close_note", None)
    await _do_close_and_rescan(
        query.edit_message_text, state, note, account=account,
    )
    if read_state() is not None:
        # Re-scan only fires when fully closed; for partial close, confirm leg removed
        pass


async def cmd_rolled(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Record that you rolled the current position (e.g. extended expiry).
    Keeps strategy/underlying unchanged; increments roll count.
    """
    try:
        state = read_state()
        if state is None:
            await update.message.reply_text(
                "ℹ️ No open position on record.\n"
                "Use /entered or <code>/entered manual</code> first.",
                parse_mode=ParseMode.HTML,
            )
            return
        roll_position()
        new_state = read_state()
        count = new_state.get("roll_count", 1) if new_state else 1
        await update.message.reply_text(
            f"🔁 <b>Roll recorded</b>  (roll #{count})\n"
            f"Strategy: <b>{_h(state['strategy'])}</b> on <code>{_h(state['underlying'])}</code>\n"
            f"<i>Position remains open. Use /note to add details about the new expiry.</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.exception("cmd_rolled failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def cmd_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Attach a free-text note to the current open position.
      /note took 60% off table at 21 DTE
    """
    if not ctx.args:
        await update.message.reply_text(
            "Usage: <code>/note &lt;text&gt;</code>\n"
            "Example: <code>/note rolled to next week, +0.35 credit</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    note = " ".join(ctx.args)
    try:
        state = read_state()
        if state is None:
            await update.message.reply_text(
                "ℹ️ No open position on record. Use /entered first.",
                parse_mode=ParseMode.HTML,
            )
            return
        add_note(note)
        await update.message.reply_text(
            f"📝 <b>Note saved</b>\n<i>{_h(note)}</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.exception("cmd_note failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def cmd_position(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the current open position with full details."""
    try:
        state = read_state()
        if state is None:
            await update.message.reply_text(
                "ℹ️ No open position on record.\n"
                "Use /entered or <code>/entered manual</code> to record one.",
                parse_mode=ParseMode.HTML,
            )
            return
        await update.message.reply_text(_format_position(state), parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("cmd_position failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def cmd_backtest(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Running 1-year backtest… (~30 sec)")
    try:
        from datetime import date, timedelta
        start = (date.today() - timedelta(days=365)).isoformat()
        trades, metrics, _ = run_backtest(start_date=start, verbose=False)
        await update.message.reply_text(
            _format_backtest_summary(trades, metrics),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.exception("cmd_backtest failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Checking market status…")
    try:
        from signals.vix_regime import get_current_snapshot, fetch_vix_history
        from signals.iv_rank    import get_current_iv_snapshot
        from signals.trend      import get_current_trend, fetch_spx_history

        vix_df   = fetch_vix_history(period="2y")
        spx_df   = fetch_spx_history(period="2y")
        vix_snap = get_current_snapshot(vix_df)
        iv_snap  = get_current_iv_snapshot(vix_df)
        tr_snap  = get_current_trend(spx_df)

        trend_warn = " ⚠️ below 200MA" if not tr_snap.above_200 else ""
        ivp_warn   = f" (IVP {iv_snap.iv_percentile:.0f} preferred)" if abs(iv_snap.iv_rank - iv_snap.iv_percentile) > 15 else ""

        ts_line = ""
        if vix_snap.vix3m is not None:
            ts_status = "BACKWARDATION ⚠️" if vix_snap.backwardation else "contango"
            ts_line = f"Term:  VIX3M <code>{vix_snap.vix3m:.2f}</code> → <code>{ts_status}</code>\n"

        # Current open position from state file
        state = read_state()
        if state:
            rolls = f"  rolls: {state.get('roll_count', 0)}" if state.get("roll_count") else ""
            pos_line = (
                f"\n<b>Open Position:</b> <b>{_h(state['strategy'])}</b> on <code>{_h(state['underlying'])}</code> "
                f"since <code>{_h(state.get('opened_at', '?'))}</code>{_h(rolls)}\n"
                f"<i>/position for details  |  /rolled  |  /note  |  /closed</i>"
            )
        else:
            pos_line = "\n<i>No open position. Use /entered after executing a trade.</i>"

        msg = (
            f"📡 <b>Market Status — {_h(vix_snap.date)}</b>\n"
            f"{'─' * 28}\n"
            f"VIX:   <code>{vix_snap.vix:.2f}</code> → <code>{vix_snap.regime.value}</code> ({vix_snap.trend.value})\n"
            f"IVR:   <code>{iv_snap.iv_rank:.1f}</code> / IVP <code>{iv_snap.iv_percentile:.1f}</code>{_h(ivp_warn)}\n"
            f"Trend: SPX <code>{tr_snap.spx:,.0f}</code>  vs 50MA <code>{tr_snap.ma_gap_pct*100:+.2f}%</code> → <code>{tr_snap.signal.value}</code>{_h(trend_warn)}\n"
            f"50MA:  <code>{tr_snap.ma50:,.0f}</code>\n"
            f"{ts_line}"
            f"{pos_line}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("cmd_status failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>SPX Strategy Bot</b>\n\n"
        "<b>Strategy</b>\n"
        "/today         — Today's recommendation (5m intraday)\n"
        "/status        — Market signals + open position\n"
        "/backtest      — 1-year backtest summary\n\n"
        "<b>Position tracking</b>\n"
        "/entered       — Record entry (uses today's recommendation)\n"
        "/entered manual — Pick strategy manually via keyboard\n"
        "/position      — Show current position details\n"
        "/rolled        — Log a roll (same strategy, new expiry)\n"
        "/note &lt;text&gt; — Attach a remark to current position\n"
        "/closed        — Mark position closed\n"
        "/closed &lt;reason&gt; — Close with a note (e.g. 60pct profit)\n\n"
        "<i>Signals are for reference only. Execute and manage trades manually.</i>",
        parse_mode=ParseMode.HTML,
    )


# ── Scheduled push ─────────────────────────────────────────────────────────────

async def scheduled_push(bot: Bot, chat_id: str) -> None:
    global _morning_snapshot
    if not is_trading_day():
        log.info("Not a trading day — skipping push.")
        return
    log.info("Sending daily recommendation…")
    try:
        rec = get_recommendation(use_intraday=True)
        _safe_append_recommendation_event(rec=rec, source="scheduled_push", mode="intraday")
        # SPEC-126: morning plan = ACTION 关于新开仓 (rings); vocabulary note —
        # a Reduce/Wait rec is titled NO ENTRY (DESIGN.md push vocabulary)
        from notify.gateway import apush
        _title = ("NO ENTRY" if rec.strategy_key == "reduce_wait"
                  else f"OPEN 候选 · {rec.strategy}")
        _category = "ACTION"
        _body = _format_recommendation(rec)
        # SPEC-131 — 敞口感知降级（显示/推送层，PM ratify T=40%）：目标家族
        # 并发 max loss / 流动现金 ≥ 阈值 → ACTION 降 STATE 语气，正文置顶
        # 降级文案（与推荐卡逐字同源 exposure.degrade_copy）。分母不可用 →
        # fail-soft 照常推荐 + 标注 n/a。selector 信号逻辑零改动。
        if rec.strategy_key and rec.strategy_key != "reduce_wait":
            try:
                from strategy.exposure import evaluate_exposure_degrade
                deg = evaluate_exposure_degrade(rec.strategy_key)
                if deg.get("degraded"):
                    # SPEC-140 §4 — outcome↔category 显式断言：敞口满 =
                    # advisory（提示不拦）→ 语气降级 STATE（SPEC-131 先例）
                    from notify.gateway import assert_outcome_category
                    _category = assert_outcome_category("advisory", "STATE")
                    _title = f"条件满足，敞口已满 · {rec.strategy}"
                    _body = f"{_h(deg['copy'])}\n{'─' * 32}\n{_body}"
                elif deg.get("note"):
                    _body = f"{_body}\n<i>{_h(deg['note'])}</i>"
            except Exception:
                log.exception("SPEC-131 exposure degrade check failed (fail-soft)")
        # SPEC-140 §3 — 晨报尾部深链（推送永远是摘要+深链）
        from notify.gateway import TRACE_DEEPLINK
        _body = f"{_body}\n{TRACE_DEEPLINK}"
        await apush(bot, chat_id, _category, "新开仓", f"晨报 · {_title}",
                    _body, dedupe_key="morning_push")
        _morning_snapshot = {
            "strategy_key": rec.strategy_key,
            "position_action": rec.position_action,
            "date": rec.vix_snapshot.date,
            "vix_trend": rec.vix_snapshot.trend.value,
        }
        log.info("Daily recommendation sent.")
    except Exception:
        log.exception("Scheduled push failed")


def _format_governance_decision(rec: Recommendation, decision) -> str:
    label = "🚨 Hard Exit" if decision.is_bypass_event else "⚡ Actionable Decision"
    if decision.is_bypass_event and decision.bypass_type:
        label += f" · {_h(decision.bypass_type)}"
    override = ""
    if decision.override_baseline:
        override = (
            f"\n<b>Baseline:</b> {_h(decision.selector_baseline_position_action)} "
            f"{_h(decision.selector_baseline_strategy)}"
        )
    next_line = (
        f"\n<b>Next:</b> <code>{_h(decision.next_actionable_decision_at)}</code>"
        if decision.next_actionable_decision_at else ""
    )
    return (
        f"{label}\n"
        f"{'─' * 32}\n"
        f"<b>Final:</b> <code>{_h(decision.governed_position_action)}</code> "
        f"{_h(decision.governed_strategy)}{override}\n"
        f"<b>Rule:</b> {_h(decision.final_priority_name)}（第 {decision.final_priority_layer} 优先层）\n"
        f"<b>Signals:</b> VIX <code>{decision.vix}</code> · IVP <code>{decision.ivp252}</code> · "
        f"Regime <code>{_h(decision.regime)}</code>\n"
        f"<b>Why:</b> <i>{_h(getattr(rec, 'rationale', '') or '')}</i>"
        f"{next_line}"
    )


async def scheduled_intraday_governance_push(bot: Bot, chat_id: str) -> None:
    if not is_trading_day():
        log.info("Not a trading day — skipping SPEC-107 governance push.")
        return
    try:
        from strategy.intraday_governance import evaluate_recommendation

        rec = get_recommendation(use_intraday=True)
        decision = evaluate_recommendation(rec, position=read_state())
        if not decision.actionable:
            log.info("SPEC-107 governance push skipped — observation bar only.")
            return
        await _safe_send(bot, chat_id, _format_governance_decision(rec, decision))
        log.info("SPEC-107 governance decision sent.")
    except Exception:
        log.exception("SPEC-107 governance push failed")


def _format_ladder_shadow_message(payload: dict) -> str:
    # SPEC-136：主文案零 SPEC 代号（原 SPEC-108 标题）
    return (
        "🪜 <b>Ladder 分层建仓 · 模拟入场记录（纸面）</b>\n"
        f"{'─' * 32}\n"
        f"<b>Would enter:</b> <code>{_h(payload.get('selector_strategy') or '—')}</code>\n"
        f"<b>Sizing:</b> <code>{payload.get('sizing_contracts')} contracts</code>\n"
        f"<b>Max loss:</b> <code>${payload.get('theoretical_max_loss')}</code> "
        f"({payload.get('theoretical_max_loss_pct_nlv')}% NLV)\n"
        f"<b>BP now:</b> <code>{payload.get('current_bp_pct_nlv')}%</code>\n"
        "仅模拟记录——未下任何真实单。"
    )


def _format_ladder_v1b_shadow_message(payload: dict) -> str:
    """V1b weekly-anchor shadow alert (mirror of V3) — V1b 仅作尾注溯源标识。"""
    return (
        "🪜 <b>Ladder 周三锚定版 · 模拟入场记录（纸面）</b>\n"
        f"{'─' * 32}\n"
        f"<b>Would enter:</b> <code>{_h(payload.get('selector_strategy') or '—')}</code>\n"
        f"<b>Sizing:</b> <code>{payload.get('sizing_contracts')} contracts</code>\n"
        f"<b>Max loss:</b> <code>${payload.get('theoretical_max_loss')}</code> "
        f"({payload.get('theoretical_max_loss_pct_nlv')}% NLV)\n"
        f"<b>BP now:</b> <code>{payload.get('current_bp_pct_nlv')}%</code>\n"
        "周三锚定并行 shadow——未下任何真实单。（V1b）"
    )


async def scheduled_ladder_shadow_push(bot: Bot, chat_id: str) -> None:
    if not is_trading_day():
        log.info("Not a trading day — skipping SPEC-108 ladder shadow push.")
        return
    try:
        from strategy.sleeve_governance import record_state_snapshot

        state = record_state_snapshot(send_alerts=False)

        # V3 shadow alert
        payload = state.get("ladder_shadow_payload") or {}
        if payload.get("shadow_log_written") and payload.get("would_enter") and payload.get("ladder_mode") == "shadow":
            from notify.gateway import apush
            await apush(bot, chat_id, "FYI", "系统状态", "Ladder shadow 记录",
                        _format_ladder_shadow_message(payload))
            log.info("SPEC-108 ladder shadow alert sent.")

        # SPEC-108.1 R2: V1b shadow alert
        v1b_payload = state.get("ladder_v1b_shadow_payload") or {}
        if v1b_payload.get("shadow_log_written") and v1b_payload.get("would_enter") and v1b_payload.get("ladder_v1b_mode") == "shadow":
            from notify.gateway import apush
            await apush(bot, chat_id, "FYI", "系统状态", "Ladder 周三锚定版 shadow 记录",
                        _format_ladder_v1b_shadow_message(v1b_payload))
            log.info("SPEC-108.1 V1b ladder shadow alert sent.")

        if not payload.get("shadow_log_written") and not v1b_payload.get("shadow_log_written"):
            log.info("SPEC-108/V1b ladder shadow push skipped — no new would-enter events.")
    except Exception:
        log.exception("SPEC-108 ladder shadow push failed")


async def scheduled_eod_push(bot: Bot, chat_id: str) -> None:
    if not is_trading_day():
        log.info("Not a trading day — skipping EOD push.")
        return
    try:
        rec = get_recommendation(use_intraday=False)
        _safe_append_recommendation_event(rec=rec, source="scheduled_eod_push", mode="eod")
        state = read_state()
        eod_text = _format_eod_snapshot(rec, _morning_snapshot, state)

        # SPEC-108.1 R4: append ladder drift status to EOD summary
        try:
            from strategy.q078_ladder_monitors import strategy_distribution_check
            drift = strategy_distribution_check()
            if drift.get("drift_alert"):
                # SPEC-136 #5 — 数字带语义 + 策略人话名（catalog 单源）
                def _drift_label(k: str, v: dict) -> str:
                    try:
                        name = strategy_descriptor(k).name
                    except Exception:
                        name = k
                    return (f"{name} 占比高出 90 天常态 "
                            f"{v['deviation_pp']:+.0f} 个百分点")
                worst = next(
                    (_drift_label(k, v) for k, v in (drift.get("drift_detail") or {}).items() if v.get("alert")),
                    "检测到分布漂移",
                )
                eod_text += f"\n📊 <b>策略分布漂移提醒</b>：{_h(worst)}——建议看一眼分布"
            else:
                eod_text += f"\n📊 <b>策略分布</b>：正常（90 天占比无漂移）"
        except Exception:
            pass

        await _safe_send(bot, chat_id, eod_text)
        log.info("EOD snapshot sent.")
    except Exception:
        log.exception("EOD push failed")


# ── SPEC-126: 15:55 pre-close digest ──────────────────────────────────────────
# Merges the retired 15:30 governance / 16:03 snapshot / 16:15 overlay
# scheduled pushes into ONE PM-ratified daily mail. SPEC-140 §2 起结构为
# Decision Trace 四泳道镜像（见 build_preclose_digest docstring）。

def _digest_health_bits(now, hb_path: Path | None = None,
                        cs_path: Path | None = None) -> tuple[list[str], bool]:
    """SPEC-117.2 — digest 健康令牌（ops 心跳 + 链体检）。

    返回 (bits, escalate)：escalate=True 仅当 ops 心跳过期 >26h（反向心跳
    唯一信号，digest 升 ACTION）。路径参数仅测试注入。
    """
    root = Path(__file__).resolve().parents[1]
    hb_path = hb_path or root / "logs" / "ops_heartbeat_state.json"
    cs_path = cs_path or root / "data" / "q041_chain_sanity_daily.jsonl"
    bits: list[str] = []
    escalate = False
    try:
        if hb_path.exists():
            hb = json.loads(hb_path.read_text())
            hb_ts = datetime.fromisoformat(hb["ts"])
            age_h = (now - hb_ts).total_seconds() / 3600.0
            if age_h > 26:
                bits.append(f"⚠ ops 心跳过期（最后 {hb_ts:%m-%d %H:%M}——监控进程疑似停摆）")
                escalate = True
            elif int(hb.get("violations", 0)):
                bits.append(f"⚠ ops {hb['violations']} 项违规（{hb_ts:%m-%d %H:%M}，详见当日 ACTION）")
            else:
                bits.append(f"ops {hb['total']}/{hb['total']} ✓（{hb_ts:%m-%d %H:%M}）")
        else:
            bits.append("⚠ ops 心跳状态缺失（升级部署后首日属正常，次日仍缺失请查）")
    except Exception:
        bits.append("ops 心跳读取失败")
    try:
        cs_lines = [l for l in cs_path.read_text().splitlines() if l.strip()] if cs_path.exists() else []
        if cs_lines:
            cs = json.loads(cs_lines[-1])
            tok = "⚠" if cs.get("alert_fired") else "✓"
            bits.append(f"链体检 {cs.get('s1_present', '—')}/{cs.get('s1_total', '—')} "
                        f"{tok}（{cs.get('date', '—')}）")
    except Exception:
        pass                                     # 链体检令牌缺失不影响 digest
    return bits, escalate


def build_preclose_digest() -> tuple[str, str, str]:
    """Returns (category, title, body). Category is ACTION when anything is
    actionable today, else FYI (quiet).

    SPEC-140 §2 — 四泳道镜像（内容同源，不新增信息量）：
      A 今日新仓结论一行（trace final 同源，SPEC-136 沿用）
      B 每个 open 仓一行（Lane B label 同源 strategy.decision_trace.
        lane_b_positions——与 /api/decision-trace 同一函数；无仓写
        "今天没有 open 仓位"）
      D 引擎状态一行（lane_d_sleeves().summary_line 同源）＋ 联动线仅在非
        "未压缩"档（advisory/veto）附一行；治理位（BCD halt / quote-gate，
        系统状态）归 D 泳道渲染，halt 升 ACTION 现行为不变
      异常区保留（reauth/推送失败等 actionable 才升 ACTION，现行为不变）
    Lane C 明确不推（Q090 封账口径）：地形/Structure Map 描述层永不进
    digest 或任何推送——状态活在网页（Decision Trace / State Map）。
    收件预算不变（SPEC-140 AC）：仍是单条 digest（dedupe_key=
    preclose_digest），分类规则（OPEN / dte≤7 / halt / 异常 → ACTION，否则
    FYI）与 SPEC-126 行为零变化——B/D 泳道镜像行与尾部深链永不改变
    category 或 dedupe。
    """
    lines: list[str] = []
    actionable = False

    # A. 今日新仓结论一行 — DESIGN.md push vocabulary: NO ENTRY, never WAIT
    try:
        rec = get_recommendation(use_intraday=True)
        if rec.strategy_key == "reduce_wait":
            verdict = f"NO ENTRY（{_h(rec.canonical_strategy or 'Reduce / Wait')}）"
        else:
            _sname = getattr(rec.strategy, "value", str(rec.strategy))
            verdict = f"OPEN 候选 · {_h(_sname)}"
            actionable = True
        lines.append(f"<b>今日新仓裁决</b>：{verdict}")
    except Exception as exc:
        lines.append(f"<b>今日新仓裁决</b>：获取失败（{_h(exc)}）")

    # B. 每个 open 仓一行 — Lane B label 同源（SPEC-140 §1/§2：触发器语义
    # 入 digest，与 /api/decision-trace Lane B 节点同一 copy 源）。
    lane_b_by_tid: dict[str, dict] = {}
    lane_b_extra: list[dict] = []
    try:
        from strategy.decision_trace import lane_b_positions
        for row in lane_b_positions(datetime.now(ET).date().isoformat()):
            if row.get("trade_id"):
                lane_b_by_tid[str(row["trade_id"])] = row
            else:
                lane_b_extra.append(row)      # fail-soft info 行，如实透传
    except Exception:
        log.exception("digest lane_b assembly failed (fail-soft)")
    try:
        from strategy.state import read_all_positions
        _all = read_all_positions() or {}
        pos = _all.get("positions", [])
        _state_sk = _all.get("strategy_key") or ""
        rendered_tids: set[str] = set()
        if pos:
            for p in pos:
                dte = ""
                if p.get("expiry"):
                    try:
                        d = (datetime.strptime(p["expiry"], "%Y-%m-%d").date()
                             - datetime.now(ET).date()).days
                        dte = f" · 还剩 {d} 天"
                        if d <= 7:
                            actionable = True
                    except ValueError:
                        pass
                _sk = p.get("strategy_key") or p.get("strategy") or _state_sk or "?"
                # SPEC-136 — 裸 strategy_key → catalog 人话名（label_human 单源）
                try:
                    _sk = strategy_descriptor(_sk).name
                except Exception:
                    pass
                tid = str(p.get("trade_id", "?"))
                rendered_tids.add(tid)
                line = f"  · 持仓 {_h(tid)}（{_h(_sk)}{dte}）"
                lb = lane_b_by_tid.get(tid)
                if lb and lb.get("label_human"):
                    line += f"：{_h(lb['label_human'])}"
                lines.append(line)
        # ledger 侧有 open BCD 而 state 缺席的行照发（真值不静默丢）
        for tid, lb in lane_b_by_tid.items():
            if tid not in rendered_tids and lb.get("label_human"):
                lines.append(f"  · 持仓 {_h(tid)}：{_h(lb['label_human'])}")
        for lb in lane_b_extra:
            if lb.get("label_human"):
                lines.append(f"  · {_h(lb['label_human'])}")
        if not pos and not lane_b_by_tid:
            # 排版注记（PM 2026-07-13）：此行是持仓清单为空的占位，不是上一行
            # NO ENTRY 的理由——加"持仓："前缀消除缩进歧义
            lines.append("  · 持仓：今天没有 open 仓位")
    except Exception:
        lines.append("  · 持仓读取失败")

    # D. 引擎状态一行 — Lane D 摘要条同源（SPEC-135.5 lane_d_sleeves，唯一
    # copy 源）；联动线仅在非"未压缩"档（advisory/veto）附一行，行文 =
    # 联动线节点 label_human 逐字（SPEC-140 §1 lane_d_linkage_label）。
    try:
        from strategy.decision_trace import lane_d_sleeves
        _ld = lane_d_sleeves()
        lines.append(f"<b>引擎</b>：{_h(_ld.get('summary_line') or '引擎状态不可用')}")
        _link = next((n for n in (_ld.get("engines") or [])
                      if n.get("check") == "dd_overlay_main_linkage"), None)
        if _link and _link.get("outcome") in ("advisory", "veto"):
            lines.append(f"  {_h(_link.get('label_human'))}")
    except Exception:
        log.exception("digest lane_d assembly failed (fail-soft)")
        lines.append("<b>引擎</b>：引擎状态读取失败")

    # D(治理位). 治理状态一行（系统状态；halt 升 ACTION 现行为不变）
    gov_bits: list[str] = []
    try:
        from strategy.bcd_governance import is_halted, quote_gate_status
        halt = is_halted()
        gov_bits.append("Bull Call Diagonal（BCD）：已暂停开新仓（待 PM 复审）"
                        if halt else "BCD（Bull Call Diagonal）：正常")
        qg = quote_gate_status()
        if not qg["unlocked"]:
            # SPEC-136 单源：文案来自 quote_gate_status().label_human
            gov_bits.append(qg.get("label_human")
                            or f"真实报价已积累 {qg['days']}/{qg['needed']} 天")
        if halt:
            actionable = True
    except Exception:
        gov_bits.append("治理状态读取失败")
    lines.append("<b>治理</b>：" + " · ".join(gov_bits))

    # D(健康位). SPEC-117.2（PM 2026-07-13）：每日绿线推送退役，状态令牌并入
    # digest。反向心跳搬家：ops state 过期 >26h = "监控自己死了"的唯一信号 →
    # 本 digest 升 ACTION（原绿线的 dead-man 语义由 PM 必读的这条承接）。
    health_bits, health_escalate = _digest_health_bits(datetime.now(ET))
    if health_escalate:
        actionable = True
    if health_bits:
        lines.append("<b>健康</b>：" + " · ".join(health_bits))

    # 4. 异常区 — omitted entirely when clean
    anomalies: list[str] = []
    try:
        stats_path = Path(__file__).resolve().parents[1] / "logs" / "push_stats.json"
        if stats_path.exists():
            d = json.loads(stats_path.read_text()).get(
                datetime.now(ET).date().isoformat(), {})
            if int(d.get("failed", 0)):
                anomalies.append(f"推送 {d['failed']} 条两次发送均失败")
    except Exception:
        pass
    try:
        st = read_state()
        if st and st.get("requires_reauth"):
            anomalies.append("Schwab 需要重新授权")
    except Exception:
        pass
    if anomalies:
        lines.append("<b>异常</b>：\n" + "\n".join(f"  ⚠ {_h(a)}" for a in anomalies))
        actionable = True

    # 尾部深链（SPEC-140 §3：推送永远是摘要+深链）；Lane C 不出现在上面任何
    # 一节——地形只描述不决策，永不推送（Q090 封账口径）。
    from notify.gateway import TRACE_DEEPLINK
    lines.append(TRACE_DEEPLINK)

    return ("ACTION" if actionable else "FYI",
            f"收盘前 digest · {datetime.now(ET):%m-%d %H:%M}",
            "\n".join(lines))


async def scheduled_preclose_digest(bot: Bot, chat_id: str) -> None:
    if not is_trading_day():
        log.info("Not a trading day — skipping pre-close digest.")
        return
    try:
        from notify.gateway import apush
        category, title, body = build_preclose_digest()
        await apush(bot, chat_id, category, "系统状态", title, body,
                    dedupe_key="preclose_digest")
        log.info("Pre-close digest sent (%s).", category)
    except Exception:
        log.exception("pre-close digest failed")


# ── Entry point ────────────────────────────────────────────────────────────────

def _get_env() -> tuple[str, str]:
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token:
        sys.exit("❌ TELEGRAM_BOT_TOKEN not set. Copy .env.example → .env and fill in your token.")
    return token, chat_id


async def _print_chat_id(token: str) -> None:
    """Helper to find your chat_id after starting the bot."""
    bot = Bot(token=token)
    print("Waiting for a message… Send any message to your bot now.")
    updates = await bot.get_updates(timeout=30)
    if updates:
        chat_id = updates[-1].message.chat.id
        print(f"\n✅ Your chat_id is: {chat_id}")
        print("Add this to your .env file as TELEGRAM_CHAT_ID=", chat_id)
    else:
        print("No messages received. Make sure you sent a message to the bot first.")


def main() -> None:
    # log hygiene: httpx logs every 10s getUpdates poll at INFO — 119MB
    # err.log observed. Keep our own INFO, silence the pollers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    token, chat_id = _get_env()

    # -- Helper mode: print chat_id --
    if "--get-chat-id" in sys.argv:
        asyncio.run(_print_chat_id(token))
        return

    if not chat_id:
        sys.exit("❌ TELEGRAM_CHAT_ID not set. Run with --get-chat-id first.")

    # Start scheduler inside the running event loop via post_init hook
    async def post_init(application: Application) -> None:
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = AsyncIOScheduler(timezone=ET)

        # 09:35 ET daily recommendation push
        scheduler.add_job(
            scheduled_push,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=35, timezone=ET),
            args=[application.bot, chat_id],
            id="daily_push",
            name="Daily recommendation push",
        )

        # SPEC-126 时段重构 (PM 2026-07-06): the 16:03 EOD snapshot and the
        # 10:30/15:30 SPEC-107 governance pushes are RETIRED as standalone
        # mails — their content folds into the single 15:55 pre-close digest.
        # Governance/overlay routine decisions no longer push individually;
        # state CHANGES still push event-driven (ALERT/ACTION) from their own
        # modules. Functions kept for /commands and reuse.
        scheduler.add_job(
            scheduled_preclose_digest,
            CronTrigger(day_of_week="mon-fri", hour=15, minute=55, timezone=ET),
            args=[application.bot, chat_id],
            id="preclose_digest",
            name="SPEC-126 pre-close digest 15:55",
        )

        scheduler.add_job(
            scheduled_ladder_shadow_push,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=40, timezone=ET),
            args=[application.bot, chat_id],
            id="spec108_ladder_shadow",
            name="SPEC-108 ladder shadow alert",
        )

        # 09:30 ET: reset intraday state for the new session
        scheduler.add_job(
            _reset_intraday_state,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=30, timezone=ET),
            id="reset_intraday",
            name="Reset intraday state",
        )

        # Every 5 minutes: poll intraday signals (function guards its own market-hours check)
        scheduler.add_job(
            intraday_monitor,
            IntervalTrigger(minutes=5),
            args=[application.bot, chat_id],
            id="intraday_monitor",
            name="Intraday signal monitor",
        )

        scheduler.add_job(
            scheduled_etrade_token_renewal,
            CronTrigger(hour=23, minute=0, timezone=ET),
            args=[application.bot, chat_id],
            id="etrade_token_renewal",
            name="E-Trade token renewal",
        )

        scheduler.start()
        log.info("Scheduler started — daily push 09:35 ET, intraday monitor every 5 min, E-Trade renew 23:00 ET")

    app = Application.builder().token(token).post_init(post_init).build()

    # Ops hardening (2026-07-07): two graceful self-exits in one evening from
    # Telegram 502 bursts, each logged as "No error handlers are registered".
    # A registered handler lets PTB treat transient network errors as handled
    # (log-and-continue) instead of escalating to shutdown; KeepAlive remains
    # the backstop.
    async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.warning("bot error handler: %s", context.error)
    app.add_error_handler(_on_error)
    app.add_handler(CommandHandler("today",    cmd_today))
    app.add_handler(CommandHandler("entered",  cmd_entered))
    app.add_handler(CommandHandler("closed",   cmd_closed))
    app.add_handler(CommandHandler("rolled",   cmd_rolled))
    app.add_handler(CommandHandler("note",     cmd_note))
    app.add_handler(CommandHandler("position", cmd_position))
    app.add_handler(CommandHandler("backtest", cmd_backtest))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("start",    cmd_help))
    app.add_handler(CallbackQueryHandler(handle_manual_entry,     pattern=r"^enter:"))
    app.add_handler(CallbackQueryHandler(handle_entry_account_cb, pattern=r"^aenter:"))
    app.add_handler(CallbackQueryHandler(handle_close_account_cb, pattern=r"^aclose:"))

    print("\n🤖 Bot running. Commands: /today /entered /position /rolled /note /closed /status /backtest /help")
    print("   Press Ctrl+C to stop.\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
