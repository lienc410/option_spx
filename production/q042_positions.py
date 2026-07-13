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
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_LOG = REPO_ROOT / "data" / "q042_paper_trades.jsonl"
LIVE_LOG  = REPO_ROOT / "data" / "q042_live_trades.jsonl"
_SPX_MULTIPLIER = 100

_log = logging.getLogger("q042_positions")


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
    instrument: str = "SPREAD"     # SPEC-094.7: SPREAD | XSP_LEAP
    rung: Optional[float] = None   # SPEC-094.7: B 阶梯档位（A 为 None）

    @property
    def is_active(self) -> bool:
        if not self.expiry_date:
            return not self.settled
        return not self.settled and date.today().isoformat() <= self.expiry_date

    @property
    def days_to_expiry(self) -> int:
        if not self.expiry_date:
            return 0
        exp = datetime.strptime(self.expiry_date[:10], "%Y-%m-%d").date()
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
    """Legacy fallback: signal_date + 90 calendar days (empty-ledger compat)."""
    return (datetime.strptime(signal_date[:10], "%Y-%m-%d") + timedelta(days=90)).strftime("%Y-%m-%d")


def _derive_expiry(record: dict) -> Optional[str]:
    """SPEC-094.2 F2 three-tier expiry derivation (anchor R-20260510-15;
    expiry starts at entry T+1 + DTE, not signal+90).

    1. explicit `expiry` field (manual open endpoint always writes it) → use it;
    2. else `entry_target_date + dte` calendar days (executor records carry dte:
       A=30 / B=90 since SPEC-094.1) — fixes Sleeve A off-by-61d AND Sleeve B
       off-by-1d (2nd Quant C3);
    3. else legacy `signal_date + 90` (historical empty ledgers only).

    B4: returns None for a row with no usable date field (e.g. a note row that
    slipped the event filter) and logs a warning instead of raising —
    strptime("") ValueError previously killed the whole EOD eval silently.
    """
    exp = record.get("expiry")
    if exp:
        return str(exp)[:10]

    entry = record.get("entry_target_date")
    dte = record.get("dte")
    if entry and dte is not None:
        try:
            return (datetime.strptime(str(entry)[:10], "%Y-%m-%d")
                    + timedelta(days=int(dte))).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    sig = record.get("signal_date")
    if sig:
        try:
            return _expiry_from_signal(str(sig))
        except ValueError:
            pass

    _log.warning(
        "q042_positions: expiry underivable, skipping record trade_id=%r sleeve=%r event=%r",
        record.get("trade_id"), record.get("sleeve_id"), record.get("event"),
    )
    return None


def _atomic_write_jsonl(path: Path, rows: list[dict]) -> None:
    """N11: full-file ledger rewrite via tempfile + os.replace (the ledger is
    the 6-month review's single truth source; a partial open('w') is unsafe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
        if t.get("phantom"):
            continue   # SPEC-094.3 AC-4: phantom (released slot) ≡ void
        sid = t.get("sleeve_id", "")
        if sid in by_sleeve:
            by_sleeve[sid].append(t)

    result: dict[str, Optional[Q042Position]] = {"A": None, "B": None}
    for sid, sleeve_trades in by_sleeve.items():
        if not sleeve_trades:
            continue
        last = sleeve_trades[-1]
        expiry = _derive_expiry(last) or ""
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


def get_active_positions_list(paper: bool = True,
                              today: Optional[str] = None) -> list[Q042Position]:
    """SPEC-094.7 — 全部未结算未到期 open 仓（B 阶梯可多仓并发；A 至多一仓）。"""
    today_str = today or date.today().isoformat()
    out: list[Q042Position] = []
    for t in _load_trades(paper):
        if t.get("event", "open") != "open" or t.get("phantom") or t.get("settled"):
            continue
        expiry = _derive_expiry(t)
        if expiry is not None and today_str >= expiry:
            continue
        out.append(Q042Position(
            sleeve_id=t.get("sleeve_id", "?"),
            trade_id=t.get("trade_id") or f"{t.get('sleeve_id','?')}-{t.get('signal_date','')}",
            entry_date=t.get("entry_target_date", ""),
            signal_date=t.get("signal_date", ""),
            long_strike=int(t.get("long_strike", 0) or 0),
            short_strike=int(t.get("short_strike", 0) or 0),
            contracts=int(t.get("contracts", 0) or 0),
            est_debit_per_contract=float(t.get("est_debit", 0) or 0),
            fill_debit_per_contract=t.get("fill_debit"),
            expiry_date=expiry or "",
            settled=False,
            exit_pnl=None,
            instrument=t.get("instrument", "SPREAD"),
            rung=t.get("rung"),
        ))
    return out


def settle_expired_positions(
    spx_close: float,
    today: Optional[str] = None,
    paper: bool = True,
    dry_run: bool = False,
) -> list[str]:
    """
    Mark expired positions as settled using the given SPX close (AC19).

    SPEC-094.2:
      - N9: `today` is passed by the executor as the data-date so holiday /
        data-lag skew doesn't misalign against a wall-clock date.today().
      - B4: skip `event != "open"` rows (notes share the ledger) and use the
        three-tier expiry derivation (None → skip + warn, never raise).
      - B6: `dry_run` computes the would-settle list but writes neither the
        ledger nor the sleeve state.
      - N11: ledger rewrite is atomic (tempfile + os.replace).

    Returns list of settled sleeve_ids.
    """
    today_str = today or date.today().isoformat()
    trades = _load_trades(paper)
    settled_ids: list[str] = []
    settled_trade_ids: list[str] = []      # SPEC-094.7: rung-aware state 清仓
    updated = False

    for t in trades:
        if t.get("event", "open") != "open":   # B4: note/close rows aren't positions
            continue
        if t.get("phantom"):
            continue   # SPEC-094.3 AC-4: phantom rows are never settled (≡ void)
        if t.get("settled"):
            continue
        expiry = _derive_expiry(t)              # F2/B4
        if expiry is None:
            continue
        if today_str < expiry:
            continue

        # Cash-settled European: intrinsic value at expiry.
        # SPEC-094.7: XSP_LEAP 行 = 单腿 long call、XSP 尺度（underlying =
        # spx/10）——绝不可走 get("short_strike", 0) 默认路径（0 默认会把
        # 整个标的当 short 腿赔付）。
        debit = float(t.get("fill_debit") or t.get("est_debit") or 0)
        if t.get("instrument") == "XSP_LEAP":
            underlying = spx_close / 10.0
            long_k = float(t.get("long_strike", 0))
            pnl_per_share = max(0.0, underlying - long_k) - debit / _SPX_MULTIPLIER
        else:
            long_k  = float(t.get("long_strike", 0))
            short_k = float(t.get("short_strike", 0))
            long_payoff  = max(0.0, spx_close - long_k)
            short_payoff = max(0.0, spx_close - short_k)
            pnl_per_share = (long_payoff - short_payoff) - debit / _SPX_MULTIPLIER
        exit_pnl_total = pnl_per_share * _SPX_MULTIPLIER * int(t.get("contracts", 1))

        settled_ids.append(t.get("sleeve_id", "?"))
        settled_trade_ids.append(
            t.get("trade_id") or f"{t.get('sleeve_id', '?')}-{t.get('signal_date', '')}")
        if not dry_run:
            t["settled"] = True
            t["exit_pnl"] = round(exit_pnl_total, 2)
            t["settlement_date"] = today_str
            t["settlement_spx"] = round(spx_close, 2)
            updated = True

    if updated and not dry_run:
        log_file = PAPER_LOG if paper else LIVE_LOG
        _atomic_write_jsonl(log_file, trades)   # N11

        # AC20: clear active_position_id in sleeve state after expiry.
        # SPEC-094.7: A = 扁平槽；B = rungs 阶梯，按 trade_id 匹配对应档清仓
        # （settled_ids 只有 sleeve 粒度，直接清 sleeve_b 会误伤并发档）。
        from signals.q042_trigger import load_state, save_state
        state = load_state()
        for sid, tid in zip(settled_ids, settled_trade_ids):
            if str(sid).upper() == "A":
                if state.get("sleeve_a"):
                    state["sleeve_a"]["active_position_id"] = None
                    state["sleeve_a"]["active_position_expiry"] = None
            else:
                for rs in state.get("sleeve_b", {}).get("rungs", {}).values():
                    if rs.get("active_position_id") == tid:
                        rs["active_position_id"] = None
                        rs["active_position_expiry"] = None
        save_state(state)

    return settled_ids


def get_active_committed_debit_usd(today: Optional[str] = None) -> float:
    """SPEC-094.2 F6 helper: Σ (fill_debit or est_debit) × contracts across
    BOTH ledgers (PAPER_LOG + LIVE_LOG) for unsettled, unexpired open records.

    B2 — unit contract: `est_debit`/`fill_debit` are already PER-CONTRACT USD
    (q042_sizing multiplies by 100 at source). DO NOT multiply by the SPX
    multiplier again; `debit × contracts` is total committed dollars. The caller
    divides by NLV ×100 to get combined_bp_pct.

    Account reality: /api/q042/position/open writes every manual open to
    PAPER_LOG (paper_trade flag distinguishes live); LIVE_LOG has zero writers
    today. Scanning both future-proofs it and mirrors the F1 settle口径.
    """
    today_str = today or date.today().isoformat()
    total = 0.0
    for paper in (True, False):
        for t in _load_trades(paper):
            if t.get("event", "open") != "open":
                continue
            if t.get("phantom"):
                continue  # SPEC-094.3 AC-4: phantom ≡ void, never committed
            if t.get("settled"):
                continue
            expiry = _derive_expiry(t)
            if expiry is not None and today_str >= expiry:
                continue  # already expired (awaiting settle) — not committed
            debit = t.get("fill_debit")
            if debit in (None, ""):
                debit = t.get("est_debit")
            debit = float(debit or 0.0)
            contracts = int(t.get("contracts", 0) or 0)
            total += debit * contracts
    return round(total, 2)


def get_lifetime_stats(paper: bool = True) -> dict[str, dict]:
    """Return per-sleeve trade count, win rate, and total P&L for dashboard."""
    trades = _load_trades(paper)
    stats: dict[str, dict] = {
        "A": {"trades": 0, "wins": 0, "total_pnl": 0.0},
        "B": {"trades": 0, "wins": 0, "total_pnl": 0.0},
    }
    for t in trades:
        if t.get("phantom"):
            continue   # SPEC-094.3 AC-4: phantom ≡ void, excluded from stats
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


def q042_concentration_monitor(paper: bool = True, threshold_pct: float = 50.0) -> dict:
    """Return top-3 settled-trade P&L concentration for Q042 monitoring.

    SPEC-104 uses this as an observation metric only. If there are not enough
    settled profitable trades, the monitor fails soft instead of inventing a
    conclusion.
    """
    trades = [
        t for t in _load_trades(paper)
        if t.get("event", "open") == "open" and t.get("settled") and t.get("exit_pnl") not in (None, "")
    ]
    pnls = [float(t.get("exit_pnl") or 0.0) for t in trades]
    positive = [p for p in pnls if p > 0]
    total_positive = sum(positive)
    if len(positive) < 3 or total_positive <= 0:
        return {
            "status": "insufficient_data",
            "threshold_pct": threshold_pct,
            "sample_size": len(trades),
            "profitable_sample_size": len(positive),
            "top3_contribution_pct": None,
        }
    top3 = sum(sorted(positive, reverse=True)[:3])
    pct = top3 / total_positive * 100.0
    return {
        "status": "breach" if pct > threshold_pct else "ok",
        "threshold_pct": threshold_pct,
        "sample_size": len(trades),
        "profitable_sample_size": len(positive),
        "top3_contribution_pct": round(pct, 2),
    }
