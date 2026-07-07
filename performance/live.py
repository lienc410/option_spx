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


def _campaign_id_of(trade: dict) -> str:
    open_ev = trade.get("open") or {}
    return str(trade.get("campaign_id") or open_ev.get("campaign_id") or trade.get("id"))


def compute_live_performance(
    resolved_trades: list[dict],
    schwab_snapshot: dict | None = None,
    include_paper: bool = False,
) -> dict:
    non_voided = [t for t in resolved_trades if not t.get("voided")]
    paper_trade_count = sum(1 for t in non_voided if t.get("paper_trade"))
    included = non_voided if include_paper else [t for t in non_voided if not t.get("paper_trade")]
    open_only = [t for t in included if t.get("open") and not t.get("close")]

    # ── SPEC-127 §1 — campaign 为统计单元（一个 campaign = 一笔 trade）────────
    # 单 member、零 roll 的 campaign 退化为原逐-trade 口径（回归零行为变更）。
    # 部分平仓的 campaign（仍有 member open）不进 closed 统计——campaign 未完结。
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in included:
        if t.get("open"):
            groups[_campaign_id_of(t)].append(t)

    pnls: list[float] = []
    by_strategy_raw: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0, "wins": 0, "total_pnl": 0.0})
    monthly_raw: dict[str, dict[str, float]] = defaultdict(lambda: {"realized_pnl": 0.0, "trades": 0})
    recent_closed: list[dict] = []

    from strategy.campaign import trade_roll_income_usd

    for cid, members in groups.items():
        if any(t.get("close") is None for t in members):
            continue  # campaign not finished yet
        member_pnls = [_realized_pnl(t) for t in members]
        if any(p is None for p in member_pnls):
            continue  # legacy semantics: unknown-pnl trades stay out of stats
        roll_income = sum(trade_roll_income_usd(t) for t in members)
        pnl = sum(member_pnls) + roll_income
        pnls.append(pnl)

        members = sorted(members, key=lambda t: str(t.get("id")))
        open_ev = members[0]["open"]
        last_close = max(members, key=lambda t: str((t.get("close") or {}).get("timestamp") or ""))["close"]
        key = open_ev.get("strategy_key") or "unknown"
        stats = by_strategy_raw[key]
        stats["n"] += 1
        stats["wins"] += 1 if pnl > 0 else 0
        stats["total_pnl"] += pnl

        month = _month_key(last_close.get("timestamp"))
        if month:
            monthly_raw[month]["realized_pnl"] += pnl
            monthly_raw[month]["trades"] += 1

        n_rolls = sum(len(t.get("rolls") or []) for t in members)
        contracts_total = sum(float(t["open"].get("contracts") or 0) for t in members)
        if contracts_total and float(contracts_total).is_integer():
            contracts_total = int(contracts_total)
        row = {
            "id": cid,
            "strategy_key": open_ev.get("strategy_key"),
            "strategy": open_ev.get("strategy"),
            "opened_at": min(((t["open"].get("timestamp") or "")[:10] or t["open"].get("opened_at") or "")
                             for t in members) or None,
            "closed_at": (last_close.get("timestamp") or "")[:10],
            "contracts": contracts_total or open_ev.get("contracts"),
            "actual_pnl": round(pnl, 2),
        }
        if n_rolls > 0 or len(members) > 1:
            # campaign 下钻数据（cycle 层）；fail-soft — 元数据缺失不掩盖统计行
            try:
                from strategy.campaign import build_campaigns
                camp = build_campaigns(members)[0]
                row["campaign"] = {
                    "members": camp["members"],
                    "n_cycles": camp["n_cycles"],
                    "n_rolls": camp["n_rolls"],
                    "initial_debit_usd": camp["initial_debit_usd"],
                    "roll_income_usd": camp["roll_income_usd"],
                    "adjusted_basis_usd": camp["adjusted_basis_usd"],
                    "cycles": camp["cycles"],
                }
            except Exception:
                row["campaign"] = {"members": [t["id"] for t in members],
                                   "n_rolls": n_rolls, "error": "campaign_meta_unavailable"}
        recent_closed.append(row)

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
