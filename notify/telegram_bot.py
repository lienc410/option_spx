"""
Telegram Bot — Daily Options Recommendation Push

Commands:
  /today     — Fetch and send today's recommendation now
  /backtest  — Run a 1-year quick backtest and send summary
  /status    — Show system status (last signal values)
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
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from strategy.selector import (
    get_recommendation, StrategyName, Recommendation,
)
from backtest.engine import run_backtest, compute_metrics

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


# ── Message formatting ─────────────────────────────────────────────────────────

_STRATEGY_EMOJI = {
    StrategyName.BULL_CALL_DIAGONAL: "📈",
    StrategyName.BEAR_CALL_DIAGONAL: "📉",
    StrategyName.IRON_CONDOR:        "🦅",
    StrategyName.SHORT_PUT:          "💰",
    StrategyName.BULL_CALL_SPREAD:   "🐂",
    StrategyName.BEAR_PUT_SPREAD:    "🐻",
    StrategyName.BEAR_CALL_SPREAD:   "🐻",
    StrategyName.CALENDAR_SPREAD:    "📅",
    StrategyName.BUY_LEAP_CALL:      "🚀",
    StrategyName.BUY_LEAP_PUT:       "🛡",
    StrategyName.REDUCE_WAIT:        "⏸",
}


def _h(text: str) -> str:
    """Escape HTML special characters for Telegram HTML mode."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_recommendation(rec: Recommendation) -> str:
    emoji = _STRATEGY_EMOJI.get(rec.strategy, "📊")
    date  = rec.vix_snapshot.date

    iv_note = ""
    if abs(rec.iv_snapshot.iv_rank - rec.iv_snapshot.iv_percentile) > 15:
        iv_note = f" (IVP {rec.iv_snapshot.iv_percentile:.0f} used — IVR distorted)"

    signals = (
        f"VIX <code>{rec.vix_snapshot.vix:.1f}</code> [{rec.vix_snapshot.regime.value}]  "
        f"IVR <code>{rec.iv_snapshot.iv_rank:.0f}</code>{_h(iv_note)}  "
        f"Trend <code>{rec.trend_snapshot.signal.value}</code>"
    )

    if rec.legs:
        legs_lines = "\n".join(
            f"  {l.action} {l.option:<4} {l.dte}DTE  δ{l.delta:.2f}  <i>{_h(l.note)}</i>"
            for l in rec.legs
        )
    else:
        legs_lines = "  <i>No new position</i>"

    macro = "\n⚠️ <b>SPX below 200MA</b> — reduce size 25–50% on bullish trades." if rec.macro_warning else ""

    return (
        f"{emoji} <b>Options Recommendation — {_h(date)}</b>\n"
        f"{'─' * 32}\n"
        f"<b>Strategy:</b>   {_h(rec.strategy.value)}\n"
        f"<b>Underlying:</b> {_h(rec.underlying)}\n\n"
        f"<b>Legs:</b>\n{legs_lines}\n\n"
        f"<b>Max Risk:</b>  {_h(rec.max_risk)}\n"
        f"<b>Target:</b>    {_h(rec.target_return)}\n"
        f"<b>Size Rule:</b> {_h(rec.size_rule)}\n"
        f"<b>Roll At:</b>   {_h(rec.roll_rule)}\n\n"
        f"<b>Why:</b> <i>{_h(rec.rationale)}</i>\n\n"
        f"<b>Signals:</b> {signals}"
        f"{macro}\n"
        f"{'─' * 32}\n"
        f"<i>Verify strikes on your broker before executing.</i>"
    )


# Keep _esc for any legacy use; no longer used in formatting
def _esc(text: str) -> str:
    return _h(text)


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
        f"Sharpe:     <code>{metrics['sharpe']:.2f}</code>\n\n"
        f"<b>By strategy:</b>\n<pre>{by_strat}</pre>\n"
        f"<i>Precision B (Black-Scholes, no slippage)</i>"
    )


# ── Command handlers ───────────────────────────────────────────────────────────

async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Fetching signals…")
    try:
        rec = get_recommendation()
        await update.message.reply_text(
            _format_recommendation(rec),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.exception("cmd_today failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def cmd_backtest(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Running 1-year backtest… (~30 sec)")
    try:
        from datetime import date, timedelta
        start = (date.today() - timedelta(days=365)).isoformat()
        trades, metrics = run_backtest(start_date=start, verbose=False)
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
        ivp_warn   = f" \\(IVP {iv_snap.iv_percentile:.0f} preferred\\)" if abs(iv_snap.iv_rank - iv_snap.iv_percentile) > 15 else ""

        msg = (
            f"📡 <b>Market Status — {_h(vix_snap.date)}</b>\n"
            f"{'─' * 28}\n"
            f"VIX:   <code>{vix_snap.vix:.2f}</code> → <code>{vix_snap.regime.value}</code> ({vix_snap.trend.value})\n"
            f"IVR:   <code>{iv_snap.iv_rank:.1f}</code> / IVP <code>{iv_snap.iv_percentile:.1f}</code>{_h(ivp_warn)}\n"
            f"Trend: SPX <code>{tr_snap.spx:,.0f}</code>  gap <code>{tr_snap.ma_gap_pct*100:+.2f}%</code> → <code>{tr_snap.signal.value}</code>{_h(trend_warn)}\n"
            f"20MA:  <code>{tr_snap.ma20:,.0f}</code>  50MA: <code>{tr_snap.ma50:,.0f}</code>\n"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("cmd_status failed")
        await update.message.reply_text(f"⚠️ Error: {e}")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>SPX Strategy Bot</b>\n\n"
        "/today — Today's strategy recommendation\n"
        "/status — Current VIX / IVR / Trend signals\n"
        "/backtest — 1-year backtest summary\n"
        "/help — This message\n\n"
        "<i>Recommendations are signals only. Always verify strikes and execute manually.</i>",
        parse_mode=ParseMode.HTML,
    )


# ── Scheduled push ─────────────────────────────────────────────────────────────

async def scheduled_push(bot: Bot, chat_id: str) -> None:
    if not is_trading_day():
        log.info("Not a trading day — skipping push.")
        return
    log.info("Sending daily recommendation…")
    try:
        rec = get_recommendation()
        await bot.send_message(
            chat_id=chat_id,
            text=_format_recommendation(rec),
            parse_mode=ParseMode.HTML,
        )
        log.info("Daily recommendation sent.")
    except Exception:
        log.exception("Scheduled push failed")


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

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("today",    cmd_today))
    app.add_handler(CommandHandler("backtest", cmd_backtest))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("start",    cmd_help))

    # Scheduler: 09:35 ET, Mon–Fri
    scheduler = AsyncIOScheduler(timezone=ET)
    scheduler.add_job(
        scheduled_push,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=35, timezone=ET),
        args=[app.bot, chat_id],
        id="daily_push",
        name="Daily recommendation push",
    )
    scheduler.start()
    log.info("Scheduler started — daily push at 09:35 ET (Mon–Fri, trading days only)")

    print("\n🤖 Bot is running. Commands: /today /status /backtest /help")
    print("   Press Ctrl+C to stop.\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
