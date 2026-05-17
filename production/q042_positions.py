"""Q042 Position Tracking & Exit (F6)

Reads q042_paper_trades.jsonl (or q042_live_trades.jsonl) and computes
real-time position state for each sleeve:

  - is_active: bool
  - days_to_expiry: int (calendar days to 90-day expiry)
  - current_pnl: float (estimated from BS model; None until fill recorded)
  - entry_date, strikes, contracts

At market close on expiry day, marks position as settled and appends
exit_pnl to the trade record (cash-settled European — intrinsic only).

Expiry at MVP: hold to 90-calendar-day expiry (no early close).
Re-arm: after expiry, sleeve state transitions to armed=False until
        ddATH re-arm condition met (handled in q042_trigger.py).

Acceptance criteria:
  AC18: position exposes is_active, days_to_expiry, current_pnl.
  AC19: expiry P&L computed from settlement value, not intraday mid.
  AC20: after expiry, sleeve transitions to armed=False.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_LOG = REPO_ROOT / "data" / "q042_paper_trades.jsonl"
LIVE_LOG  = REPO_ROOT / "data" / "q042_live_trades.jsonl"
_SPX_MULTIPLIER = 100


@dataclass
class Q042Position:
    sleeve_id: str
    trade_id: str
    entry_date: str
    signal_date: str
    long_strike: int
    short_strike: int
    contracts: int
    est_debit_per_contract: float
    fill_debit_per_contract: Optional[float]
    expiry_date: str
    settled: bool
    exit_pnl: Optional[float]

    @property
    def is_active(self) -> bool:
        return not self.settled and date.today().isoformat() <= self.expiry_date

    @property
    def days_to_expiry(self) -> int:
        exp = datetime.strptime(self.expiry_date, "%Y-%m-%d").date()
        return max(0, (exp - date.today()).days)

    @property
    def current_pnl(self) -> Optional[float]:
        """Estimated from BS model (live); or exit_pnl once settled."""
        if self.settled:
            return self.exit_pnl
        return None  # caller can compute via q042_pricing if needed


def _load_trades(paper: bool) -> list[dict]:
    log_file = PAPER_LOG if paper else LIVE_LOG
    if not log_file.exists():
        return []
    trades = []
    for line in log_file.read_text().splitlines():
        line = line.strip()
        if line:
            trades.append(json.loads(line))
    return trades


def _expiry_from_signal(signal_date: str) -> str:
    """Compute expiry date as signal_date + 90 calendar days (matches backtest)."""
    return (datetime.strptime(signal_date, "%Y-%m-%d") + timedelta(days=90)).strftime("%Y-%m-%d")


def get_active_positions(paper: bool = True) -> dict[str, Optional[Q042Position]]:
    """
    Return the most recent active (or last settled) position for each sleeve.

    Returns:
        {"A": Q042Position or None, "B": Q042Position or None}
    """
    trades = _load_trades(paper)
    by_sleeve: dict[str, list[dict]] = {"A": [], "B": []}
    for t in trades:
        # Skip non-open events (notes, future close events) — they share the
        # ledger but aren't position records.
        event = t.get("event", "open")
        if event != "open":
            continue
        sid = t.get("sleeve_id", "")
        if sid in by_sleeve:
            by_sleeve[sid].append(t)

    result: dict[str, Optional[Q042Position]] = {"A": None, "B": None}
    for sid, sleeve_trades in by_sleeve.items():
        if not sleeve_trades:
            continue
        last = sleeve_trades[-1]
        expiry = _expiry_from_signal(last.get("signal_date", last.get("entry_target_date", "")))
        pos = Q042Position(
            sleeve_id=sid,
            trade_id=f"{sid}-{last.get('signal_date','')}",
            entry_date=last.get("entry_target_date", ""),
            signal_date=last.get("signal_date", ""),
            long_strike=int(last.get("long_strike", 0)),
            short_strike=int(last.get("short_strike", 0)),
            contracts=int(last.get("contracts", 0)),
            est_debit_per_contract=float(last.get("est_debit", 0)),
            fill_debit_per_contract=last.get("fill_debit"),
            expiry_date=expiry,
            settled=last.get("settled", False),
            exit_pnl=last.get("exit_pnl"),
        )
        result[sid] = pos

    return result


def settle_expired_positions(spx_close: float, paper: bool = True) -> list[str]:
    """
    Mark expired positions as settled using the given SPX close (AC19).

    Returns list of settled sleeve_ids.
    """
    today_str = date.today().isoformat()
    trades = _load_trades(paper)
    settled_ids: list[str] = []
    updated = False

    for t in trades:
        if t.get("settled"):
            continue
        expiry = _expiry_from_signal(t.get("signal_date", t.get("entry_target_date", "")))
        if today_str < expiry:
            continue

        # Cash-settled European: intrinsic value at expiry
        long_k  = float(t.get("long_strike", 0))
        short_k = float(t.get("short_strike", 0))
        long_payoff  = max(0.0, spx_close - long_k)
        short_payoff = max(0.0, spx_close - short_k)
        debit = float(t.get("fill_debit") or t.get("est_debit") or 0)
        pnl_per_share = (long_payoff - short_payoff) - debit / _SPX_MULTIPLIER
        exit_pnl_total = pnl_per_share * _SPX_MULTIPLIER * int(t.get("contracts", 1))

        t["settled"] = True
        t["exit_pnl"] = round(exit_pnl_total, 2)
        t["settlement_date"] = today_str
        t["settlement_spx"] = round(spx_close, 2)
        settled_ids.append(t.get("sleeve_id", "?"))
        updated = True

    if updated:
        log_file = PAPER_LOG if paper else LIVE_LOG
        with log_file.open("w") as f:
            for t in trades:
                f.write(json.dumps(t) + "\n")

        # AC20: clear active_position_id in sleeve state after expiry
        from signals.q042_trigger import load_state, save_state
        state = load_state()
        for sid in settled_ids:
            key = "sleeve_a" if sid == "A" else "sleeve_b"
            state[key]["active_position_id"] = None
            state[key]["active_position_expiry"] = None
        save_state(state)

    return settled_ids


def get_lifetime_stats(paper: bool = True) -> dict[str, dict]:
    """Return per-sleeve trade count, win rate, and total P&L for dashboard."""
    trades = _load_trades(paper)
    stats: dict[str, dict] = {
        "A": {"trades": 0, "wins": 0, "total_pnl": 0.0},
        "B": {"trades": 0, "wins": 0, "total_pnl": 0.0},
    }
    for t in trades:
        sid = t.get("sleeve_id", "")
        if sid not in stats or not t.get("settled"):
            continue
        pnl = float(t.get("exit_pnl", 0) or 0)
        stats[sid]["trades"] += 1
        stats[sid]["total_pnl"] += pnl
        if pnl > 0:
            stats[sid]["wins"] += 1

    for sid, s in stats.items():
        s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] else None
        s["total_pnl"] = round(s["total_pnl"], 2)

    return stats
