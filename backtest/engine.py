"""
Backtest Engine — Precision B (Black-Scholes simulation)

Walk-forward simulation over historical SPX + VIX data.
For each trading day:
  1. Compute signals (VIX regime, IV rank, trend) — no lookahead
  2. If no open position → check if signals warrant a new entry
  3. If position open → simulate daily P&L via BS repricing; check exit rules
  4. Record completed trades with entry/exit details

Exit rules (from design doc):
  - Close at 50% of max credit / debit profit
  - Roll / close short legs at DTE = 21
  - Stop loss at 2× credit received (for credit strategies)

Precision B limitations:
  - No bid/ask spread → P&L is optimistic by ~0.1–0.3%
  - Constant IV per day (no intraday vol moves)
  - No slippage, commissions, or pin risk
  - American-style early assignment not modeled
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np

from signals.vix_regime import (
    Regime, fetch_vix_history,
    get_regime_history, _classify_regime,
)
from signals.iv_rank  import compute_iv_rank, compute_iv_percentile, IVSignal
from signals.trend    import _classify_trend, fetch_spx_history
from strategy.selector import (
    StrategyName, select_strategy,
    VixSnapshot, IVSnapshot, TrendSnapshot,
    IVSignal as IVSig,
)
from signals.vix_regime import Trend
from backtest.pricer import (
    call_price, put_price, call_delta, put_delta, find_strike_for_delta,
)


# ─── Trade record ────────────────────────────────────────────────────────────

@dataclass
class Trade:
    strategy:     StrategyName
    underlying:   str
    entry_date:   str
    exit_date:    str = ""
    entry_spx:    float = 0.0
    exit_spx:     float = 0.0
    entry_vix:    float = 0.0
    entry_credit: float = 0.0   # positive = credit received, negative = debit paid
    exit_pnl:     float = 0.0   # final P&L (positive = profit)
    exit_reason:  str = ""      # "50pct_profit" | "stop_loss" | "expiry" | "roll_21dte"
    dte_at_entry: int = 0
    dte_at_exit:  int = 0

    @property
    def pnl_pct(self) -> float:
        """P&L as % of max risk (|entry_credit| = max debit or credit at stake)."""
        if self.entry_credit == 0:
            return 0.0
        return self.exit_pnl / abs(self.entry_credit) * 100


# ─── Position (open trade) ────────────────────────────────────────────────────

@dataclass
class Position:
    strategy:     StrategyName
    underlying:   str
    entry_date:   str
    entry_spx:    float
    entry_vix:    float
    entry_sigma:  float        # IV at entry (VIX / 100)

    # Legs: each leg is (action, is_call, strike, dte_at_entry, qty)
    # action: +1 = long, -1 = short
    legs:         list[tuple[int, bool, float, int, int]] = field(default_factory=list)

    entry_value:  float = 0.0  # net debit (positive) or credit (negative) at entry
    days_held:    int = 0


def _entry_value(legs, spx, sigma, dte_start):
    """Compute net premium for a set of legs at entry. Positive = debit, negative = credit."""
    total = 0.0
    for action, is_call, strike, _, qty in legs:
        price = call_price(spx, strike, dte_start, sigma) if is_call else put_price(spx, strike, dte_start, sigma)
        total += action * price * qty
    return total


def _current_value(legs, spx, sigma, days_held):
    """Compute current net value of position. Positive = debit side, negative = credit side."""
    total = 0.0
    for action, is_call, strike, dte_start, qty in legs:
        dte_now = max(dte_start - days_held, 1)
        price = call_price(spx, strike, dte_now, sigma) if is_call else put_price(spx, strike, dte_now, sigma)
        total += action * price * qty
    return total


def _build_legs(strategy: StrategyName, spx: float, sigma: float) -> tuple[list, int]:
    """
    Build leg tuples for a given strategy at the current SPX level.
    Returns (legs, dte_of_short_leg).
    Each leg: (action +1/-1, is_call bool, strike float, dte int, qty int)
    """
    if strategy == StrategyName.BULL_CALL_DIAGONAL:
        short_dte  = 30
        long_dte   = 90
        short_k    = find_strike_for_delta(spx, short_dte, sigma, 0.30, is_call=True)
        long_k     = find_strike_for_delta(spx, long_dte,  sigma, 0.70, is_call=True)
        return [
            (+1, True, long_k,  long_dte,  1),
            (-1, True, short_k, short_dte, 1),
        ], short_dte

    if strategy == StrategyName.IRON_CONDOR:
        dte = 45
        call_short = find_strike_for_delta(spx, dte, sigma, 0.16, is_call=True)
        put_short  = find_strike_for_delta(spx, dte, sigma, 0.16, is_call=False)
        wing       = max(50, round(spx * 0.015 / 50) * 50)   # ~1.5% width, rounded to $50
        call_long  = call_short + wing
        put_long   = put_short  - wing
        return [
            (-1, True,  call_short, dte, 1),
            (+1, True,  call_long,  dte, 1),
            (-1, False, put_short,  dte, 1),
            (+1, False, put_long,   dte, 1),
        ], dte

    if strategy == StrategyName.SHORT_PUT:
        dte    = 30
        strike = find_strike_for_delta(spx, dte, sigma, 0.30, is_call=False)
        return [(-1, False, strike, dte, 1)], dte

    if strategy == StrategyName.BULL_CALL_SPREAD:
        dte    = 21
        long_k = find_strike_for_delta(spx, dte, sigma, 0.50, is_call=True)
        short_k = find_strike_for_delta(spx, dte, sigma, 0.25, is_call=True)
        return [
            (+1, True, long_k,  dte, 1),
            (-1, True, short_k, dte, 1),
        ], dte

    if strategy == StrategyName.BEAR_PUT_SPREAD:
        dte    = 21
        long_k = find_strike_for_delta(spx, dte, sigma, 0.50, is_call=False)
        short_k = find_strike_for_delta(spx, dte, sigma, 0.25, is_call=False)
        return [
            (+1, False, long_k,  dte, 1),
            (-1, False, short_k, dte, 1),
        ], dte

    if strategy == StrategyName.BEAR_CALL_SPREAD:
        dte    = 21
        short_k = find_strike_for_delta(spx, dte, sigma, 0.40, is_call=True)
        long_k  = find_strike_for_delta(spx, dte, sigma, 0.20, is_call=True)
        return [
            (-1, True, short_k, dte, 1),
            (+1, True, long_k,  dte, 1),
        ], dte

    if strategy == StrategyName.CALENDAR_SPREAD:
        dte_short = 30
        dte_long  = 60
        atm_k     = round(spx / 5) * 5
        return [
            (-1, True, atm_k, dte_short, 1),
            (+1, True, atm_k, dte_long,  1),
        ], dte_short

    # LEAP strategies — hold for 365 days, simplified as single long leg
    if strategy in (StrategyName.BUY_LEAP_CALL, StrategyName.BUY_LEAP_PUT):
        dte     = 365
        is_call = (strategy == StrategyName.BUY_LEAP_CALL)
        strike  = find_strike_for_delta(spx, dte, sigma, 0.70, is_call=is_call)
        return [(+1, is_call, strike, dte, 1)], dte

    return [], 30   # REDUCE_WAIT — no legs


# ─── Metrics ─────────────────────────────────────────────────────────────────

def compute_metrics(trades: list[Trade]) -> dict:
    if not trades:
        return {"error": "no trades"}

    pnls  = [t.exit_pnl for t in trades]
    wins  = [p for p in pnls if p > 0]
    total = len(pnls)

    equity     = np.cumsum(pnls)
    peak       = np.maximum.accumulate(equity)
    drawdowns  = equity - peak
    max_dd     = float(drawdowns.min())

    # Sharpe (annualised, assume ~252 days/year, 1 trade ~30 days → ~8.4 trades/year)
    mean_pnl   = np.mean(pnls)
    std_pnl    = np.std(pnls, ddof=1) if len(pnls) > 1 else 1e-9
    sharpe     = (mean_pnl / std_pnl) * math.sqrt(252 / 30) if std_pnl > 0 else 0.0

    by_strategy = {}
    for t in trades:
        s = t.strategy.value
        by_strategy.setdefault(s, []).append(t.exit_pnl)

    return {
        "total_trades":   total,
        "win_rate":       len(wins) / total,
        "avg_win":        float(np.mean(wins)) if wins else 0.0,
        "avg_loss":       float(np.mean([p for p in pnls if p <= 0])) if any(p <= 0 for p in pnls) else 0.0,
        "expectancy":     float(mean_pnl),
        "total_pnl":      float(sum(pnls)),
        "max_drawdown":   max_dd,
        "sharpe":         round(sharpe, 2),
        "by_strategy":    {k: {
            "n":        len(v),
            "win_rate": sum(1 for x in v if x > 0) / len(v),
            "avg_pnl":  float(np.mean(v)),
        } for k, v in by_strategy.items()},
    }


# ─── Main simulation loop ────────────────────────────────────────────────────

def run_backtest(
    start_date: str = "2023-01-01",
    end_date:   str | None = None,
    account_size: float = 150_000.0,
    risk_pct:     float = 0.02,        # 2% account risk per trade
    verbose:      bool  = False,
) -> tuple[list[Trade], dict]:
    """
    Walk-forward backtest from start_date to end_date (defaults to today).

    Returns:
        trades  : list of completed Trade objects
        metrics : summary statistics dict
    """
    # ── Load data ────────────────────────────────────────────────────
    vix_df = fetch_vix_history(period="5y")
    spx_df = fetch_spx_history(period="5y")

    # Normalise indexes to tz-naive dates — VIX uses America/Chicago,
    # SPX uses America/New_York; they can't be joined directly.
    vix_df.index = pd.to_datetime(vix_df.index.date)
    spx_df.index = pd.to_datetime(spx_df.index.date)

    df = pd.DataFrame({
        "vix": vix_df["vix"],
        "spx": spx_df["close"],
    }).dropna()

    # Apply date filter
    df = df[df.index >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df.index <= pd.Timestamp(end_date)]

    if len(df) < 60:
        raise ValueError(f"Not enough data after filtering: {len(df)} rows")

    # Lookback window for rolling signal computation (no lookahead)
    lookback_start = pd.Timestamp(start_date) - pd.Timedelta("400D")
    full_vix = vix_df[vix_df.index >= lookback_start]
    full_spx = spx_df[spx_df.index >= lookback_start]

    trades:   list[Trade]    = []
    position: Optional[Position] = None

    for i, (date, row) in enumerate(df.iterrows()):
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sigma = vix / 100.0          # annualised vol

        # ── Compute signals (no lookahead: use data up to today) ─────
        date_key   = pd.Timestamp(date)
        vix_window = full_vix[full_vix.index <= date_key]["vix"]
        spx_window = full_spx[full_spx.index <= date_key]["close"]

        if len(vix_window) < 60 or len(spx_window) < 55:
            continue

        regime   = _classify_regime(vix)
        ivr      = compute_iv_rank(vix_window.iloc[-252:] if len(vix_window) >= 252 else vix_window)
        ivp      = compute_iv_percentile(vix_window.iloc[-252:] if len(vix_window) >= 252 else vix_window)

        iv_eff   = IVSig.HIGH if ivp > 70 else (IVSig.LOW if ivp < 40 else IVSig.NEUTRAL)

        ma20_val = float(spx_window.rolling(20).mean().iloc[-1]) if len(spx_window) >= 20 else spx
        ma50_val = float(spx_window.rolling(50).mean().iloc[-1]) if len(spx_window) >= 50 else spx
        ma200_val= float(spx_window.rolling(200).mean().iloc[-1]) if len(spx_window) >= 200 else spx
        gap      = (ma20_val - ma50_val) / ma50_val if ma50_val else 0
        from signals.trend import TrendSignal, TREND_THRESHOLD
        trend    = TrendSignal.BULLISH if gap > TREND_THRESHOLD else (
                   TrendSignal.BEARISH if gap < -TREND_THRESHOLD else TrendSignal.NEUTRAL)

        # Assemble snapshot objects for selector
        vix_snap   = VixSnapshot(
            date=str(date.date()), vix=vix, regime=regime,
            trend=Trend.RISING, vix_5d_avg=vix, vix_5d_ago=vix,
            transition_warning=False,
        )
        iv_snap    = IVSnapshot(
            date=str(date.date()), vix=vix,
            iv_rank=ivr, iv_percentile=ivp, iv_signal=iv_eff,
            iv_52w_high=float(vix_window.max()), iv_52w_low=float(vix_window.min()),
        )
        trend_snap = TrendSnapshot(
            date=str(date.date()), spx=spx,
            ma20=ma20_val, ma50=ma50_val, ma_gap_pct=gap, signal=trend,
            above_200=(spx > ma200_val),
        )
        rec = select_strategy(vix_snap, iv_snap, trend_snap)

        # ── Manage open position ─────────────────────────────────────
        if position is not None:
            position.days_held += 1
            current_val  = _current_value(position.legs, spx, sigma, position.days_held)
            # P&L = current_val - entry_value
            # Credit trade: entry_value=-500, current_val=-250 → pnl=+250 (profit) ✓
            # Debit  trade: entry_value=+500, current_val=+700 → pnl=+200 (profit) ✓
            pnl          = current_val - position.entry_value

            short_dte    = max(position.legs[0][3] - position.days_held, 0)

            # Exit conditions
            exit_reason  = None
            if abs(position.entry_value) > 0:
                pnl_ratio = pnl / abs(position.entry_value)
                if pnl_ratio >= 0.50:
                    exit_reason = "50pct_profit"
                elif pnl_ratio <= -2.0 and position.entry_value < 0:   # credit trade stop
                    exit_reason = "stop_loss"

            if short_dte <= 21 and exit_reason is None:
                exit_reason = "roll_21dte"

            if exit_reason:
                t = Trade(
                    strategy     = position.strategy,
                    underlying   = position.underlying,
                    entry_date   = position.entry_date,
                    exit_date    = str(date.date()),
                    entry_spx    = position.entry_spx,
                    exit_spx     = spx,
                    entry_vix    = position.entry_vix,
                    entry_credit = position.entry_value,
                    exit_pnl     = pnl * account_size * risk_pct / abs(position.entry_value) if position.entry_value else 0,
                    exit_reason  = exit_reason,
                    dte_at_entry = position.legs[0][3],
                    dte_at_exit  = short_dte,
                )
                trades.append(t)
                if verbose:
                    print(f"  EXIT  {t.exit_date}  {t.strategy.value:<25}  "
                          f"PnL: {t.exit_pnl:+.0f}  ({exit_reason})")
                position = None

        # ── Open new position (only if none open, skip LEAP for efficiency) ──
        if position is None and rec.strategy != StrategyName.REDUCE_WAIT:
            # Rate-limit: enter at most once per week (every 5 trading days)
            if i % 5 == 0:
                legs, short_dte = _build_legs(rec.strategy, spx, sigma)
                if legs:
                    ev = _entry_value(legs, spx, sigma, short_dte)
                    position = Position(
                        strategy     = rec.strategy,
                        underlying   = rec.underlying,
                        entry_date   = str(date.date()),
                        entry_spx    = spx,
                        entry_vix    = vix,
                        entry_sigma  = sigma,
                        legs         = legs,
                        entry_value  = ev,
                        days_held    = 0,
                    )
                    if verbose:
                        print(f"  ENTER {date.date()}  {rec.strategy.value:<25}  "
                              f"value: {ev:+.2f}  VIX:{vix:.1f}")

    # Close any still-open position at last price
    if position is not None:
        current_val = _current_value(position.legs, spx, sigma, position.days_held)
        pnl = current_val - position.entry_value
        trades.append(Trade(
            strategy=position.strategy, underlying=position.underlying,
            entry_date=position.entry_date, exit_date=str(df.index[-1].date()),
            entry_spx=position.entry_spx, exit_spx=float(df["spx"].iloc[-1]),
            entry_vix=position.entry_vix, entry_credit=position.entry_value,
            exit_pnl=pnl * account_size * risk_pct / abs(position.entry_value) if position.entry_value else 0,
            exit_reason="end_of_backtest",
            dte_at_entry=position.legs[0][3], dte_at_exit=0,
        ))

    metrics = compute_metrics(trades)
    return trades, metrics


# ─── Report ──────────────────────────────────────────────────────────────────

def print_report(trades: list[Trade], metrics: dict) -> None:
    print("\n" + "=" * 65)
    print("  BACKTEST REPORT")
    print("=" * 65)

    if "error" in metrics:
        print(f"  No trades generated: {metrics['error']}")
        return

    print(f"  Period       : {trades[0].entry_date} → {trades[-1].exit_date}")
    print(f"  Total trades : {metrics['total_trades']}")
    print(f"  Win rate     : {metrics['win_rate']*100:.1f}%")
    print(f"  Avg win      : ${metrics['avg_win']:+.0f}")
    print(f"  Avg loss     : ${metrics['avg_loss']:+.0f}")
    print(f"  Expectancy   : ${metrics['expectancy']:+.0f} / trade")
    print(f"  Total P&L    : ${metrics['total_pnl']:+,.0f}")
    print(f"  Max drawdown : ${metrics['max_drawdown']:+,.0f}")
    print(f"  Sharpe (ann) : {metrics['sharpe']:.2f}")

    print("\n  By strategy:")
    for name, s in metrics["by_strategy"].items():
        print(f"    {name:<28}  n={s['n']:>3}  win={s['win_rate']*100:.0f}%  avg=${s['avg_pnl']:+.0f}")

    print("\n  Exit breakdown:")
    from collections import Counter
    reasons = Counter(t.exit_reason for t in trades)
    for reason, count in reasons.most_common():
        print(f"    {reason:<20} {count:>3} ({count/len(trades)*100:.0f}%)")

    print()
    print("  ⚠  Precision B (Black-Scholes simulation).")
    print("     P&L is theoretical mid-market. Actual results will differ")
    print("     due to bid/ask spread, slippage, and vol-surface effects.")
    print("=" * 65)


if __name__ == "__main__":
    print("Running backtest: 2023-01-01 → today  (Precision B)\n")
    trades, metrics = run_backtest(start_date="2023-01-01", verbose=False)
    print_report(trades, metrics)
