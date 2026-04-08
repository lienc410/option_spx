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
import logging
import os
import sys
from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from strategy.selector import (
    get_recommendation, StrategyName, Recommendation,
)
from strategy.catalog import manual_entry_options, strategy_descriptor
from strategy.state import (
    read_state, write_state, close_position, roll_position, add_note,
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

_intraday_state: dict = {
    "spike_level": SpikeLevel.NONE,
    "stop_level":  StopLevel.NONE,
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


def _format_recommendation(rec: Recommendation) -> str:
    desc         = strategy_descriptor(rec.strategy_key)
    emoji        = desc.emoji
    action_emoji = _ACTION_EMOJI.get(rec.position_action, "")
    date         = rec.vix_snapshot.date

    iv_note = ""
    if abs(rec.iv_snapshot.iv_rank - rec.iv_snapshot.iv_percentile) > 15:
        iv_note = f" (IVP {rec.iv_snapshot.iv_percentile:.0f} used — IVR distorted)"

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

    entered_hint = ""
    if rec.position_action in ("OPEN", "CLOSE_AND_OPEN"):
        entered_hint = "\n\n<i>After executing: send /entered to record your position.</i>"

    return (
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
        f"{macro}{bk}\n"
        f"{'─' * 32}"
        f"{entered_hint}"
    )


# Keep _esc for any legacy use; no longer used in formatting
def _esc(text: str) -> str:
    return _h(text)


def _format_spike_alert(spike: VixSpikeAlert) -> str:
    icon = "🚨" if spike.level == SpikeLevel.ALERT else "⚠️"
    advice = (
        "🚨 VIX surging — consider closing or hedging short vol positions."
        if spike.level == SpikeLevel.ALERT
        else "⚠️ VIX rising fast — monitor closely."
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
    advice = (
        "🚨 -2% trigger: close or reduce credit spreads immediately."
        if stop.level == StopLevel.TRIGGER
        else "⚠️ -1% caution: tighten mental stops."
    )
    timing = _alert_timing_label(stop.timestamp, stop.realtime)
    return (
        f"{icon} <b>SPX Drop {stop.level.value}</b>  [{_h(stop.timestamp)}{timing}]\n"
        f"Open: <code>{stop.spx_open:,.0f}</code> → Now: <code>{stop.spx_current:,.0f}</code>  "
        f"(<code>{stop.drop_pct*100:+.1f}%</code>)\n"
        f"{advice}"
    )


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
    action = str(morning.get("position_action") or "").upper()
    strategy_key = str(morning.get("strategy_key") or "").upper()
    if action == "WAIT":
        return strategy_key or action
    return " ".join(part for part in (action, strategy_key) if part)


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
            f"  EOD     → {_h(rec.position_action)} {_h(rec.strategy_key.upper())}  "
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
    _intraday_state["spike_level"] = SpikeLevel.NONE
    _intraday_state["stop_level"]  = StopLevel.NONE
    _morning_snapshot = None
    log.info("Intraday state reset for new session.")


async def intraday_monitor(bot: Bot, chat_id: str) -> None:
    """
    Polls VIX and SPX intraday signals every 5 minutes during market hours.
    Pushes only when a signal level escalates (NONE→WARNING, WARNING→ALERT, etc.)
    or when elevated conditions clear back to normal.
    """
    if not is_market_open():
        return

    try:
        try:
            spike = get_vix_spike_from_quote(get_vix_quote())
            stop = get_spx_stop_from_quote(get_spx_quote())
        except Exception:
            spike = get_vix_spike(interval="5m")
            stop = get_spx_stop(interval="5m")
    except Exception:
        log.exception("intraday_monitor: failed to fetch signals")
        return

    prev_spike = _intraday_state["spike_level"]
    prev_stop  = _intraday_state["stop_level"]

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

    # Persist new state
    _intraday_state["spike_level"] = spike.level
    _intraday_state["stop_level"]  = stop.level

    for msg in msgs:
        try:
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML)
        except Exception:
            log.exception("intraday_monitor: failed to send message")


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

async def cmd_entered(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Record a new position.
      /entered         → use current recommendation (auto)
      /entered manual  → show strategy keyboard for manual selection
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
        write_state(rec.strategy.value, rec.underlying, strategy_key=rec.strategy_key)
        await update.message.reply_text(
            f"✅ <b>Position recorded</b>\n"
            f"Strategy: <b>{_h(rec.strategy.value)}</b> on <code>{_h(rec.underlying)}</code>\n"
            f"<i>Use /entered manual to record a different strategy.</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.exception("cmd_entered failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


_VALID_MANUAL_PAIRS = {(k, u) for k, _, u in _MANUAL_ENTRY_OPTIONS}
_MANUAL_NAME_BY_KEY = {k: n for k, n, _ in _MANUAL_ENTRY_OPTIONS}


async def handle_manual_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for inline keyboard strategy selection in /entered manual."""
    query = update.callback_query
    await query.answer()
    _, strategy_key, underlying = query.data.split(":", 2)
    if (strategy_key, underlying) not in _VALID_MANUAL_PAIRS:
        await query.edit_message_text("⚠️ Invalid strategy selection.")
        return
    try:
        strategy = _MANUAL_NAME_BY_KEY[strategy_key]
        write_state(strategy, underlying, strategy_key=strategy_key)
        await query.edit_message_text(
            f"✅ <b>Position recorded (manual)</b>\n"
            f"Strategy: <b>{_h(strategy)}</b> on <code>{_h(underlying)}</code>\n"
            f"<i>Use /rolled to log a roll, /note to add a remark, /closed when done.</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.exception("handle_manual_entry failed")
        await query.edit_message_text(f"⚠️ Error recording position: {e}")


async def cmd_closed(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Mark the current position as closed.
      /closed               → no reason recorded
      /closed 50pct profit  → stores the note alongside the close
    """
    note = " ".join(ctx.args) if ctx.args else None
    try:
        state = read_state()
        if state is None:
            await update.message.reply_text("ℹ️ No open position on record to close.")
            return
        close_position(note=note)
        note_line = f"\nNote: <i>{_h(note)}</i>" if note else ""
        await update.message.reply_text(
            f"✅ <b>Position closed</b>\n"
            f"Strategy: <b>{_h(state['strategy'])}</b> on <code>{_h(state['underlying'])}</code>\n"
            f"Opened: <code>{_h(state.get('opened_at', '?'))}</code>{note_line}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.exception("cmd_closed failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


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
      /note took 50% off table at 21 DTE
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
        "/closed &lt;reason&gt; — Close with a note (e.g. 50pct profit)\n\n"
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
        await bot.send_message(
            chat_id=chat_id,
            text=_format_recommendation(rec),
            parse_mode=ParseMode.HTML,
        )
        _morning_snapshot = {
            "strategy_key": rec.strategy_key,
            "position_action": rec.position_action,
            "date": rec.vix_snapshot.date,
            "vix_trend": rec.vix_snapshot.trend.value,
        }
        log.info("Daily recommendation sent.")
    except Exception:
        log.exception("Scheduled push failed")


async def scheduled_eod_push(bot: Bot, chat_id: str) -> None:
    if not is_trading_day():
        log.info("Not a trading day — skipping EOD push.")
        return
    try:
        rec = get_recommendation(use_intraday=False)
        state = read_state()
        await bot.send_message(
            chat_id=chat_id,
            text=_format_eod_snapshot(rec, _morning_snapshot, state),
            parse_mode=ParseMode.HTML,
        )
        log.info("EOD snapshot sent.")
    except Exception:
        log.exception("EOD push failed")


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

        scheduler.add_job(
            scheduled_eod_push,
            CronTrigger(day_of_week="mon-fri", hour=16, minute=3, timezone=ET),
            args=[application.bot, chat_id],
            id="eod_push",
            name="EOD signal snapshot push",
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

        scheduler.start()
        log.info("Scheduler started — daily push 09:35 ET, intraday monitor every 5 min")

    app = Application.builder().token(token).post_init(post_init).build()
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
    app.add_handler(CallbackQueryHandler(handle_manual_entry, pattern=r"^enter:"))

    print("\n🤖 Bot running. Commands: /today /entered /position /rolled /note /closed /status /backtest /help")
    print("   Press Ctrl+C to stop.\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
