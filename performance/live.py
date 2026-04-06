from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _realized_pnl(trade: dict) -> float | None:
    close = trade.get("close") or {}
    open_ev = trade.get("open") or {}

    direct = _num(close.get("actual_pnl"))
    if direct is not None:
        return direct

    entry = _num(open_ev.get("actual_premium"))
    exit_premium = _num(close.get("exit_premium"))
    contracts = _num(open_ev.get("contracts"))
    if entry is None or exit_premium is None or contracts is None:
        return None
    return (entry - exit_premium) * contracts * 100.0


def _month_key(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp).strftime("%Y-%m")
    except ValueError:
        return None


def compute_live_performance(
    resolved_trades: list[dict],
    schwab_snapshot: dict | None = None,
    include_paper: bool = False,
) -> dict:
    non_voided = [t for t in resolved_trades if not t.get("voided")]
    paper_trade_count = sum(1 for t in non_voided if t.get("paper_trade"))
    included = non_voided if include_paper else [t for t in non_voided if not t.get("paper_trade")]
    closed = [t for t in included if t.get("open") and t.get("close")]
    open_only = [t for t in included if t.get("open") and not t.get("close")]

    pnls: list[float] = []
    by_strategy_raw: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0, "wins": 0, "total_pnl": 0.0})
    monthly_raw: dict[str, dict[str, float]] = defaultdict(lambda: {"realized_pnl": 0.0, "trades": 0})
    recent_closed: list[dict] = []

    for trade in closed:
        pnl = _realized_pnl(trade)
        if pnl is None:
            continue
        pnls.append(pnl)
        open_ev = trade["open"]
        close_ev = trade["close"]
        key = open_ev.get("strategy_key") or "unknown"
        stats = by_strategy_raw[key]
        stats["n"] += 1
        stats["wins"] += 1 if pnl > 0 else 0
        stats["total_pnl"] += pnl

        month = _month_key(close_ev.get("timestamp"))
        if month:
            monthly_raw[month]["realized_pnl"] += pnl
            monthly_raw[month]["trades"] += 1

        recent_closed.append({
            "id": trade["id"],
            "strategy_key": open_ev.get("strategy_key"),
            "strategy": open_ev.get("strategy"),
            "opened_at": (open_ev.get("timestamp") or "")[:10] or open_ev.get("opened_at"),
            "closed_at": (close_ev.get("timestamp") or "")[:10],
            "contracts": open_ev.get("contracts"),
            "actual_pnl": round(pnl, 2),
        })

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    closed_n = len(pnls)
    win_rate = (len(wins) / closed_n) if closed_n else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0

    by_strategy = {
        key: {
            "n": int(stats["n"]),
            "win_rate": (stats["wins"] / stats["n"]) if stats["n"] else 0.0,
            "total_pnl": round(stats["total_pnl"], 2),
            "avg_pnl": round(stats["total_pnl"] / stats["n"], 2) if stats["n"] else 0.0,
        }
        for key, stats in by_strategy_raw.items()
    }
    monthly = [
        {
            "month": month,
            "realized_pnl": round(stats["realized_pnl"], 2),
            "trades": int(stats["trades"]),
        }
        for month, stats in sorted(monthly_raw.items())
    ]

    open_positions = []
    for trade in open_only:
        open_ev = trade["open"]
        row = {
            "id": trade["id"],
            "strategy_key": open_ev.get("strategy_key"),
            "strategy": open_ev.get("strategy"),
            "paper_trade": bool(trade.get("paper_trade", False)),
            "opened_at": (open_ev.get("timestamp") or "")[:10] or open_ev.get("opened_at"),
            "contracts": open_ev.get("contracts"),
            "entry_premium": open_ev.get("actual_premium"),
            "mark": None,
            "bid": None,
            "ask": None,
            "trade_log_pnl": None,
            "unrealized_pnl": None,
            "delta": None,
            "theta": None,
            "gamma": None,
            "vega": None,
        }
        if schwab_snapshot and schwab_snapshot.get("visible"):
            row.update({
                "mark": schwab_snapshot.get("mark"),
                "bid": schwab_snapshot.get("bid"),
                "ask": schwab_snapshot.get("ask"),
                "trade_log_pnl": schwab_snapshot.get("trade_log_pnl"),
                "unrealized_pnl": schwab_snapshot.get("unrealized_pnl"),
                "delta": schwab_snapshot.get("delta"),
                "theta": schwab_snapshot.get("theta"),
                "gamma": schwab_snapshot.get("gamma"),
                "vega": schwab_snapshot.get("vega"),
            })
        open_positions.append(row)

    return {
        "summary": {
            "closed_trades": closed_n,
            "open_trades": len(open_positions),
            "win_rate": round(win_rate, 4),
            "total_realized_pnl": round(sum(pnls), 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "expectancy": round((win_rate * avg_win) + ((1 - win_rate) * avg_loss), 2) if closed_n else 0.0,
            "best_trade": round(max(pnls), 2) if pnls else 0.0,
            "worst_trade": round(min(pnls), 2) if pnls else 0.0,
        },
        "by_strategy": by_strategy,
        "monthly": monthly,
        "recent_closed": sorted(
            recent_closed,
            key=lambda t: t.get("closed_at") or "",
            reverse=True,
        )[:10],
        "open_positions": open_positions,
        "include_paper": include_paper,
        "paper_trade_count": paper_trade_count,
        "trade_count_raw": len(resolved_trades),
        "trade_count_effective": len(non_voided),
    }
