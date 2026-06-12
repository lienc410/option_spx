"""
main.py — Entry point for the SPX/SPY Options Recommendation System

Usage:
  python main.py                 # Run the Telegram bot (requires .env)
  python main.py --dry-run       # Print today's recommendation to terminal only
  python main.py --backtest      # Run backtest and print report
  python main.py --get-chat-id   # Find your Telegram chat_id
"""

import sys


def main() -> None:
    args = sys.argv[1:]

    if "--dry-run" in args:
        from strategy.selector import get_recommendation
        print("Fetching market data...\n")
        rec = get_recommendation()
        print("=" * 60)
        print("   TODAY'S RECOMMENDATION")
        print("=" * 60)
        print(rec.signals_summary())
        print()
        print(rec.summary())
        if rec.macro_warning:
            print("\n⚠  SPX below 200MA — reduce size on bullish trades.")
        return

    if "--backtest" in args:
        from backtest.engine import run_backtest, print_report
        start = "2023-01-01"
        for a in args:
            if a.startswith("--start="):
                start = a.split("=")[1]
        print(f"Running backtest from {start}...\n")
        trades, metrics, _ = run_backtest(start_date=start, verbose="--verbose" in args)
        print_report(trades, metrics)
        return

    if "--get-chat-id" in args:
        sys.argv = [sys.argv[0], "--get-chat-id"]
        from notify.telegram_bot import main as bot_main
        bot_main()
        return

    if "--web" in args:
        from web.server import app
        port = 5050
        for a in args:
            if a.startswith("--port="):
                port = int(a.split("=")[1])
        print(f"\n🌐  Dashboard → http://localhost:{port}\n")
        try:
            # Production WSGI server. The Werkzeug dev server's keep-alive
            # handling races with cloudflared's persistent origin connections
            # (it closes idle sockets cloudflared still considers live), which
            # surfaced as intermittent Cloudflare 502s that left no tunnel log.
            # waitress handles keep-alive correctly and serves requests on a
            # thread pool so one slow endpoint can't stall the whole dashboard.
            from waitress import serve
            serve(app, host="127.0.0.1", port=port, threads=8,
                  channel_timeout=120, connection_limit=200)
        except ImportError:
            print("⚠ waitress not installed — falling back to Flask dev server")
            app.run(host="127.0.0.1", port=port, debug=False)
        return

    # Default: run the bot
    from notify.telegram_bot import main as bot_main
    bot_main()


if __name__ == "__main__":
    main()
