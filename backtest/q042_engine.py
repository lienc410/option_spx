"""Q042 Walk-Forward Backtest Engine (F8)

Simulates dual-sleeve directional overlay from 2007-01-01 to 2026-05-10.

Design:
  Trigger detection uses the research methodology exactly
  (find_triggers_ddath + apply_no_overlap), so AC21 reproduces research counts.
  P&L calculation uses walk-forward pricing.

  Sleeve A: ddATH ≤ -4%, no MA filter, T+1 open, DTE 30, ATM/+2.5% (SPEC-094.1).
  Sleeve B: ddATH ≤ -15% outer crossing → MA10 reclaim, DTE 90, ATM/+5% (unchanged).
  Both:     10% account sizing, hold to expiry.

Acceptance criteria:
  AC21: Reproduces Tier 3 research metrics within ±2%:
    Sleeve A: n=25, win 64%, +99% / 19y, max DD -16.3%
    Sleeve B: n=5, win 100%, +41% / 19y, max DD 0%
  AC22: Outputs data/q042_backtest_trades.csv
  AC23: Outputs combined daily BP series (included in BacktestResult)

Run with: python -m backtest.q042_engine [--start 2007-01-01] [--end 2026-05-10]
"""

from __future__ import annotations

import argparse
import csv
import pickle
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SPX_PKL = REPO_ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO_ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
TRADES_CSV = REPO_ROOT / "data" / "q042_backtest_trades.csv"

_DTE_A      = 30    # Sleeve A: SPEC-094.1
_DTE_B      = 90    # Sleeve B: unchanged
_OTM_A      = 0.025 # Sleeve A: ATM/+2.5% (SPEC-094.1)
_OTM_B      = 0.05  # Sleeve B: ATM/+5%  (unchanged)
_SIZING_PCT = 0.10
_NLV_SEED   = 100_000.0
_MA10_WIN   = 10
_WATCH_DAYS = 30   # trading days for Sleeve B MA10 reclaim window


# ── Pricing ───────────────────────────────────────────────────────────────────

def _term_mult(dte: int) -> float:
    if dte <= 45:  return 1.10
    if dte <= 120: return 1.00
    return 0.95

def _skew_mult(m: float) -> float:
    if m >= 1.0: return 1.0 - 1.5 * min(m - 1.0, 0.10)
    return 1.0 + 1.5 * min(1.0 - m, 0.10)

def _bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    # SPEC-119: delegates to the unified pricing core (same scipy CDF, same
    # T-in-years / r=4% / q=0 conventions → bit-identical to the old inline copy).
    from pricing import core as _core
    return float(_core.call_price(S, K, T, sigma, r, q=0.0))

def _price_spread(S: float, K_long: float, K_short: float, vix: float, dte: int) -> float:
    T = dte / 365.0
    sigma_atm = max(vix / 100.0, 0.10) * _term_mult(dte)
    p_long  = _bs_call(S, K_long,  T, sigma_atm * _skew_mult(K_long  / S))
    p_short = _bs_call(S, K_short, T, sigma_atm * _skew_mult(K_short / S))
    return max(0.0, p_long - p_short)


# ── Trade record ──────────────────────────────────────────────────────────────

@dataclass
class Q042Trade:
    sleeve_id: str
    signal_date: str
    entry_date: str
    exit_date: str
    ath_at_signal: float
    ddath_at_signal: float
    long_strike: float
    short_strike: float
    contracts: float
    debit_per_share: float
    exit_pnl: float
    account_pct: float
    win: bool
    status: str = "CLOSED"  # "CLOSED" (expired) or "OPEN" (in-flight at backtest end, MTM)


@dataclass
class DailyRow:
    date: str
    sleeve_a_bp_pct: float
    sleeve_b_bp_pct: float
    combined_bp_pct: float
    account_equity: float


@dataclass
class BacktestResult:
    trades_a: list[Q042Trade]
    trades_b: list[Q042Trade]
    daily_rows: list[DailyRow]

    @property
    def all_trades(self) -> list[Q042Trade]:
        return self.trades_a + self.trades_b


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_history(start: str, end: str) -> pd.DataFrame:
    try:
        spx = pickle.loads(SPX_PKL.read_bytes())
        vix = pickle.loads(VIX_PKL.read_bytes())
    except FileNotFoundError:
        import yfinance as yf
        spx = yf.Ticker("^GSPC").history(period="max", interval="1d")[["Open", "High", "Low", "Close"]]
        vix = yf.Ticker("^VIX").history(period="max", interval="1d")[["Close"]]

    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    spx.columns = [c.lower() for c in spx.columns]
    spx["vix"] = vix["Close"]
    spx = spx.loc[start:end].copy()
    spx["vix"] = spx["vix"].ffill()
    spx.dropna(subset=["close", "open"], inplace=True)
    return spx


# ── Trigger detection (research methodology) ──────────────────────────────────

def _find_triggers_ddath(
    ddath: pd.Series,
    thr: float,
    rearm_at: float,
) -> pd.DatetimeIndex:
    """
    Identical to research q042_ddath_full_scan.py find_triggers_ddath.
    Fires on first ddATH ≤ -thr crossing; re-arms when ddATH ≥ rearm_at.
    Position-agnostic — no-overlap applied separately.
    """
    triggers = []
    armed = True
    for dt, dd in ddath.items():
        if armed and dd <= -thr:
            triggers.append(dt)
            armed = False
        elif not armed and dd >= rearm_at:
            armed = True
    return pd.DatetimeIndex(triggers)


def _apply_no_overlap(entries: pd.DatetimeIndex, dte: int) -> pd.DatetimeIndex:
    if len(entries) == 0:
        return entries
    kept = [entries[0]]
    last_close = entries[0] + pd.Timedelta(days=dte)
    for e in entries[1:]:
        if e >= last_close:
            kept.append(e)
            last_close = e + pd.Timedelta(days=dte)
    return pd.DatetimeIndex(kept)


def _find_sleeve_b_entries(
    dd15_crossings: pd.DatetimeIndex,
    close: pd.Series,
    ma10: pd.Series,
    trading_index: pd.DatetimeIndex,
    watch_days: int = _WATCH_DAYS,
) -> pd.DatetimeIndex:
    """
    For each dd15 crossing: wait for first close > MA10 within watch_days
    trading days. Returns signal dates (MA10 reclaim dates).
    """
    entries = []
    for crossing in dd15_crossings:
        try:
            cross_i = trading_index.get_loc(crossing)
        except KeyError:
            continue
        for j in range(cross_i + 1, min(cross_i + watch_days + 1, len(trading_index))):
            dt = trading_index[j]
            c = float(close.iloc[j])
            m = float(ma10.iloc[j]) if not pd.isna(ma10.iloc[j]) else c
            if c > m:
                entries.append(dt)
                break
    return pd.DatetimeIndex(entries)


# ── Position tracker ──────────────────────────────────────────────────────────

@dataclass
class _ActivePos:
    sleeve_id: str
    signal_date: str
    entry_date: str
    ath_at_signal: float
    ddath_at_signal: float
    long_strike: float
    short_strike: float
    debit_per_share: float
    contracts: float
    expiry_date: str
    account_at_entry: float


# ── Main walk-forward ─────────────────────────────────────────────────────────

def run_backtest(start: str = "2007-01-01", end: str = "2026-05-10") -> BacktestResult:
    df  = _load_history(start, end)
    idx = df.index
    ma10 = df["close"].rolling(_MA10_WIN).mean()
    ath  = df["close"].cummax()
    ddath = df["close"] / ath - 1.0

    # ── Step 1: compute trigger sets using research methodology ───────────────
    raw_a  = _find_triggers_ddath(ddath, 0.04, -0.02)
    sig_a  = _apply_no_overlap(raw_a, _DTE_A)

    raw_b_cross = _find_triggers_ddath(ddath, 0.15, -0.02)
    raw_b_entry = _find_sleeve_b_entries(raw_b_cross, df["close"], ma10, idx, _WATCH_DAYS)
    sig_b  = _apply_no_overlap(raw_b_entry, _DTE_B)

    sig_a_set = set(d for d in sig_a)
    sig_b_set = set(d for d in sig_b)

    # ── Step 2: walk-forward pricing and P&L ─────────────────────────────────
    active_a: Optional[_ActivePos] = None
    active_b: Optional[_ActivePos] = None
    trades_a: list[Q042Trade] = []
    trades_b: list[Q042Trade] = []
    daily_rows: list[DailyRow] = []
    account = _NLV_SEED

    def _exp_date(entry_str: str, dte: int) -> str:
        # Expiry is DTE calendar days from entry (T+1 open), not signal (T close).
        # Live PM buys spread on entry day with X-DTE listed contract, then holds X days.
        # Pre-fix used signal+DTE, causing trades to exit ~1 trading day early (Q062 R-20260510-15).
        return (datetime.strptime(entry_str, "%Y-%m-%d") + timedelta(days=dte)).strftime("%Y-%m-%d")

    def _maybe_expire(pos: Optional[_ActivePos], trades: list, today: str, close: float) -> Optional[_ActivePos]:
        if pos is None or today < pos.expiry_date:
            return pos
        long_payoff  = max(0.0, close - pos.long_strike)
        short_payoff = max(0.0, close - pos.short_strike)
        pnl_ps = long_payoff - short_payoff - pos.debit_per_share  # per share, net
        pnl    = pnl_ps * 100 * pos.contracts                      # total dollar P&L
        # account_pct matches research: (pnl_pct_debit / 100) * sizing_pct * 100
        # = pnl_ps / debit_per_share * sizing_pct
        pct    = (pnl_ps / pos.debit_per_share) * _SIZING_PCT
        trades.append(Q042Trade(
            sleeve_id=pos.sleeve_id, signal_date=pos.signal_date,
            entry_date=pos.entry_date, exit_date=today,
            ath_at_signal=pos.ath_at_signal, ddath_at_signal=pos.ddath_at_signal,
            long_strike=pos.long_strike, short_strike=pos.short_strike,
            contracts=pos.contracts, debit_per_share=pos.debit_per_share,
            exit_pnl=round(pnl, 2), account_pct=round(pct, 4), win=pnl_ps > 0,
        ))
        return None

    def _enter(sleeve_id: str, signal_dt, i: int) -> Optional[_ActivePos]:
        if i + 1 >= len(df): return None
        next_row = df.iloc[i + 1]
        S_entry   = float(next_row["open"])
        sig_close = float(df.iloc[i]["close"])
        vix_val   = float(df.iloc[i]["vix"]) if not pd.isna(df.iloc[i]["vix"]) else 20.0
        ath_val   = float(ath.iloc[i])
        dd_val    = float(ddath.iloc[i])
        dte = _DTE_A if sleeve_id == "A" else _DTE_B
        otm = _OTM_A if sleeve_id == "A" else _OTM_B
        K_long    = round(sig_close / 5) * 5
        K_short   = round(sig_close * (1 + otm) / 5) * 5
        debit_ps  = _price_spread(S_entry, float(K_long), float(K_short), vix_val, dte)
        if debit_ps <= 0: return None
        # Use fractional contracts (1.0) — research does not filter by affordability.
        # P&L is computed as % of debit (research methodology), so integer contracts
        # are not needed for metric reproduction.
        return _ActivePos(
            sleeve_id=sleeve_id,
            signal_date=signal_dt.strftime("%Y-%m-%d"),
            entry_date=df.index[i + 1].strftime("%Y-%m-%d"),
            ath_at_signal=ath_val, ddath_at_signal=dd_val,
            long_strike=float(K_long), short_strike=float(K_short),
            debit_per_share=debit_ps, contracts=1.0,
            expiry_date=_exp_date(df.index[i + 1].strftime("%Y-%m-%d"), dte),
            account_at_entry=_NLV_SEED,
        )

    for i, (dt, row) in enumerate(df.iterrows()):
        today_str = dt.strftime("%Y-%m-%d")
        close = float(row["close"])
        vix   = float(row["vix"]) if not pd.isna(row["vix"]) else 20.0

        active_a = _maybe_expire(active_a, trades_a, today_str, close)
        active_b = _maybe_expire(active_b, trades_b, today_str, close)

        # Enter on signal dates (positions must be closed — no-overlap already guaranteed)
        if dt in sig_a_set and active_a is None:
            active_a = _enter("A", dt, i)

        if dt in sig_b_set and active_b is None:
            active_b = _enter("B", dt, i)

        bp_a = (active_a.debit_per_share * 100 * active_a.contracts / account * 100
                if active_a else 0.0)
        bp_b = (active_b.debit_per_share * 100 * active_b.contracts / account * 100
                if active_b else 0.0)
        daily_rows.append(DailyRow(
            date=today_str,
            sleeve_a_bp_pct=round(bp_a, 2),
            sleeve_b_bp_pct=round(bp_b, 2),
            combined_bp_pct=round(bp_a + bp_b, 2),
            account_equity=round(account, 2),
        ))

    # ── Step 3: mark in-flight positions as OPEN (mark-to-market) ─────────────
    # Trades whose expiry > backtest end never trip _maybe_expire. Without this
    # step they vanish from the CSV — see RESEARCH_LOG R-20260510-11.
    end_dt = df.index[-1]
    end_str = end_dt.strftime("%Y-%m-%d")
    end_close = float(df.iloc[-1]["close"])
    end_vix = float(df.iloc[-1]["vix"]) if not pd.isna(df.iloc[-1]["vix"]) else 20.0

    def _record_open(pos: Optional[_ActivePos], trades: list) -> None:
        if pos is None:
            return
        expiry_dt = datetime.strptime(pos.expiry_date, "%Y-%m-%d")
        dte_remaining = max(1, (expiry_dt - end_dt).days)
        mtm_ps = _price_spread(end_close, pos.long_strike, pos.short_strike, end_vix, dte_remaining)
        pnl_ps = mtm_ps - pos.debit_per_share
        pnl = pnl_ps * 100 * pos.contracts
        pct = (pnl_ps / pos.debit_per_share) * _SIZING_PCT
        trades.append(Q042Trade(
            sleeve_id=pos.sleeve_id, signal_date=pos.signal_date,
            entry_date=pos.entry_date, exit_date=end_str,
            ath_at_signal=pos.ath_at_signal, ddath_at_signal=pos.ddath_at_signal,
            long_strike=pos.long_strike, short_strike=pos.short_strike,
            contracts=pos.contracts, debit_per_share=pos.debit_per_share,
            exit_pnl=round(pnl, 2), account_pct=round(pct, 4),
            win=pnl_ps > 0, status="OPEN",
        ))

    _record_open(active_a, trades_a)
    _record_open(active_b, trades_b)

    return BacktestResult(trades_a=trades_a, trades_b=trades_b, daily_rows=daily_rows)


# ── Output & metrics ──────────────────────────────────────────────────────────

def _metrics(trades: list[Q042Trade], years: float) -> dict:
    # AC21 reproduction: count and win-rate use CLOSED trades only
    # (OPEN positions are MTM snapshots, not realized outcomes).
    closed = [t for t in trades if t.status == "CLOSED"]
    open_trades = [t for t in trades if t.status == "OPEN"]
    if not closed:
        return {"n": 0, "n_open": len(open_trades)}
    wins  = [t for t in closed if t.win]
    total_pnl_pct = sum(t.account_pct for t in closed) * 100
    equity = [1.0]
    for t in closed:
        equity.append(equity[-1] * (1 + t.account_pct))
    peak = 1.0; max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = min(max_dd, (v - peak) / peak)
    return {
        "n": len(closed),
        "n_open": len(open_trades),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1),
        "total_pnl_pct": round(total_pnl_pct, 1),
        "annualized_pct": round(total_pnl_pct / years, 2),
        "max_dd_pct": round(max_dd * 100, 1),
    }


def write_trades_csv(result: BacktestResult) -> None:
    TRADES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with TRADES_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "sleeve_id", "signal_date", "entry_date", "exit_date",
            "ath_at_signal", "ddath_at_signal",
            "long_strike", "short_strike", "contracts",
            "debit_per_share", "exit_pnl", "account_pct", "status",
        ])
        for t in result.all_trades:
            w.writerow([
                t.sleeve_id, t.signal_date, t.entry_date, t.exit_date,
                round(t.ath_at_signal, 2), round(t.ddath_at_signal, 4),
                int(t.long_strike), int(t.short_strike), round(t.contracts, 0),
                round(t.debit_per_share, 4), round(t.exit_pnl, 2), round(t.account_pct, 4),
                t.status,
            ])
    print(f"  wrote {TRADES_CSV}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Q042 walk-forward backtest")
    p.add_argument("--start", default="2007-01-01")
    p.add_argument("--end",   default="2026-05-10")
    args = p.parse_args()
    print(f"running Q042 backtest {args.start} → {args.end} …")
    result = run_backtest(args.start, args.end)
    years = (datetime.strptime(args.end, "%Y-%m-%d") - datetime.strptime(args.start, "%Y-%m-%d")).days / 365.25
    print(f"\n── Sleeve A ──")
    for k, v in _metrics(result.trades_a, years).items():
        print(f"  {k}: {v}")
    print(f"\n── Sleeve B ──")
    for k, v in _metrics(result.trades_b, years).items():
        print(f"  {k}: {v}")
    write_trades_csv(result)
    print(f"\nAC22 trades CSV: {TRADES_CSV}")
    print(f"AC23 daily BP rows: {len(result.daily_rows)}")
