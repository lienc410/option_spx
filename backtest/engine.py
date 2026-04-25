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
from dataclasses import asdict, dataclass, field
from typing import Optional
import pandas as pd
import numpy as np

from signals.vix_regime import (
    Regime, Trend, fetch_vix_history,
    fetch_vix3m_history, get_regime_history,
    _classify_regime, _classify_trend as _vix_classify_trend,
)
from signals.iv_rank  import compute_iv_rank, compute_iv_percentile, IVSignal
from signals.overlay import compute_overlay_signals
from signals.trend    import (
    ATR_THRESHOLD,
    _classify_trend_atr,
    _compute_atr14_close,
    fetch_spx_history,
    TrendSignal,
    TREND_THRESHOLD,
)
from strategy.selector import (
    StrategyName, select_strategy,
    StrategyParams, DEFAULT_PARAMS,
    VixSnapshot, IVSnapshot, TrendSnapshot,
    IVSignal as IVSig,
    IC_HV_MAX_CONCURRENT,
)
from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.portfolio import DailyPortfolioRow, PortfolioTracker
from backtest.pricer import (
    call_price, put_price, call_delta, put_delta, find_strike_for_delta,
)
from backtest.registry import config_hash, generate_experiment_id
from backtest.shock_engine import LegSnapshot, PositionSnapshot, run_shock_check
from strategy.catalog import strategy_key as catalog_key


SYNTHETIC_IC_PAIRS = {
    ("bull_put_spread_hv", "bear_call_spread_hv"),
    ("bear_call_spread_hv", "bull_put_spread_hv"),
}

SHORT_GAMMA_KEYS = {
    "bull_put_spread",
    "bull_put_spread_hv",
    "bear_call_spread_hv",
    "iron_condor",
    "iron_condor_hv",
}

HIGH_VOL_STRATEGY_KEYS = {
    "bull_put_spread_hv",
    "bear_call_spread_hv",
    "iron_condor_hv",
}


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
    exit_reason:  str = ""      # "50pct_profit" | "stop_loss" | "expiry" | "roll_21dte" | "roll_up"
    dte_at_entry: int = 0
    dte_at_exit:  int = 0

    # ── Buying Power fields (Schwab Portfolio Margin) ──────────────────────────
    spread_width:    float = 0.0  # width of the spread in SPX index points
    option_premium:  float = 0.0  # |net credit or debit| per contract in USD (×100 multiplier)
    bp_per_contract: float = 0.0  # Schwab PM buying power per 1 contract in USD
    contracts:       float = 0.0  # number of contracts traded (may be fractional in simulation)
    total_bp:        float = 0.0  # total BP consumed = contracts × bp_per_contract
    bp_pct_account:  float = 0.0  # total_bp as % of account_size

    @property
    def pnl_pct(self) -> float:
        """P&L as % of max risk (|entry_credit| = max debit or credit at stake)."""
        if self.entry_credit == 0:
            return 0.0
        return self.exit_pnl / abs(self.entry_credit) * 100

    @property
    def hold_days(self) -> int:
        """Actual holding period in calendar days."""
        return max(self.dte_at_entry - self.dte_at_exit, 1)

    @property
    def rom_annualized(self) -> float:
        """Annualised return on margin for the realized trade."""
        if self.total_bp <= 0:
            return 0.0
        return (self.exit_pnl / self.total_bp) * (365 / self.hold_days)


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

    entry_value:     float = 0.0  # net debit (positive) or credit (negative) at entry
    days_held:       int = 0
    size_mult:       float = 1.0  # position size multiplier (e.g. 0.5 for HIGH_VOL half-size)
    short_strike:    float = 0.0  # short leg strike (for roll-up delta check)
    spread_width:    float = 0.0  # spread width in SPX points (for BP calculation)
    bp_per_contract: float = 0.0  # Schwab PM buying power per contract in USD
    bp_target:       float = 0.0  # BP utilization target captured at entry (from StrategyParams)


@dataclass
class BacktestResult:
    trades: list[Trade]
    metrics: dict
    signals: list[dict]
    portfolio_rows: list[DailyPortfolioRow] = field(default_factory=list)
    shock_reports: list[dict] = field(default_factory=list)
    experiment_id: str = ""
    config_hash: str = ""
    portfolio_metrics: dict | None = None

    def __iter__(self):
        yield self.trades
        yield self.metrics
        yield self.signals


def _entry_value(legs, spx, sigma):
    """Compute net premium for a set of legs at entry. Positive = debit, negative = credit.
    Each leg is priced at its own DTE (stored in the leg tuple), so diagonal strategies
    with different DTEs per leg are priced correctly."""
    total = 0.0
    for action, is_call, strike, dte, qty in legs:
        price = call_price(spx, strike, dte, sigma) if is_call else put_price(spx, strike, dte, sigma)
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


def _position_contracts(position: Position, account_size: float) -> float:
    if position.bp_per_contract <= 0 or position.bp_target <= 0:
        return 0.0
    return account_size * position.bp_target / position.bp_per_contract


def _position_total_bp(position: Position, account_size: float) -> float:
    return _position_contracts(position, account_size) * position.bp_per_contract


def _position_unrealized_pnl(position: Position, spx: float, sigma: float, account_size: float) -> float:
    contracts = _position_contracts(position, account_size)
    current_val = _current_value(position.legs, spx, sigma, position.days_held)
    return (current_val - position.entry_value) * contracts * 100


def _position_id(position: Position) -> str:
    return f"{position.entry_date}|{position.strategy.value}|{position.entry_spx:.2f}"


def _position_snapshot(position: Position, spx: float, account_size: float) -> PositionSnapshot:
    contracts = _position_contracts(position, account_size)
    legs: list[LegSnapshot] = []
    for action, is_call, strike, dte_start, qty in position.legs:
        legs.append(
            LegSnapshot(
                option_type="call" if is_call else "put",
                strike=strike,
                dte=max(dte_start - position.days_held, 1),
                contracts=action * qty * contracts,
                current_spx=spx,
            )
        )
    strategy_key = catalog_key(position.strategy.value)
    return PositionSnapshot(
        strategy_key=strategy_key,
        is_short_gamma=strategy_key in SHORT_GAMMA_KEYS,
        legs=legs,
    )


def _close_position(
    *,
    position: Position,
    date: pd.Timestamp,
    spx: float,
    sigma: float,
    account_size: float,
    exit_reason: str,
) -> Trade:
    current_val = _current_value(position.legs, spx, sigma, position.days_held)
    pnl = current_val - position.entry_value
    contracts = _position_contracts(position, account_size)
    total_bp = contracts * position.bp_per_contract
    return Trade(
        strategy=position.strategy,
        underlying=position.underlying,
        entry_date=position.entry_date,
        exit_date=str(date.date()),
        entry_spx=position.entry_spx,
        exit_spx=spx,
        entry_vix=position.entry_vix,
        entry_credit=position.entry_value,
        exit_pnl=pnl * contracts * 100,
        exit_reason=exit_reason,
        dte_at_entry=_short_leg(position.legs)[3],
        dte_at_exit=max(_short_leg(position.legs)[3] - position.days_held, 0),
        spread_width=position.spread_width,
        option_premium=abs(position.entry_value) * 100,
        bp_per_contract=position.bp_per_contract,
        contracts=round(contracts, 4),
        total_bp=round(total_bp, 2),
        bp_pct_account=round(total_bp / account_size * 100, 2) if account_size else 0.0,
    )


def _short_leg(legs):
    """Return the first short leg tuple, or the first leg as fallback for malformed inputs."""
    for leg in legs:
        if leg[0] < 0:
            return leg
    return legs[0] if legs else (0, False, 0.0, 0, 0)


def _build_legs(
    strategy: StrategyName,
    spx:      float,
    sigma:    float,
    params:   StrategyParams = DEFAULT_PARAMS,
) -> tuple[list, int]:
    """
    Build leg tuples for a given strategy at the current SPX level.
    Returns (legs, dte_of_short_leg).
    Each leg: (action +1/-1, is_call bool, strike float, dte int, qty int)
    """
    if strategy == StrategyName.BULL_CALL_DIAGONAL:
        short_dte  = 45
        long_dte   = 90
        short_k    = find_strike_for_delta(spx, short_dte, sigma, 0.30, is_call=True)
        long_k     = find_strike_for_delta(spx, long_dte,  sigma, 0.70, is_call=True)
        return [
            (+1, True, long_k,  long_dte,  1),
            (-1, True, short_k, short_dte, 1),
        ], short_dte

    if strategy in (StrategyName.IRON_CONDOR, StrategyName.IRON_CONDOR_HV):
        dte = 45
        call_short = find_strike_for_delta(spx, dte, sigma, 0.16, is_call=True)
        put_short  = find_strike_for_delta(spx, dte, sigma, 0.16, is_call=False)
        # SPEC-070 v2: long legs are delta-based (δ0.08) to match selector intent.
        call_long  = find_strike_for_delta(spx, dte, sigma, 0.08, is_call=True)
        put_long   = find_strike_for_delta(spx, dte, sigma, 0.08, is_call=False)
        assert call_long > call_short, (
            f"IC long call must be above short: {call_long} <= {call_short}"
        )
        assert put_long < put_short, (
            f"IC long put must be below short: {put_long} >= {put_short}"
        )
        return [
            (-1, True,  call_short, dte, 1),
            (+1, True,  call_long,  dte, 1),
            (-1, False, put_short,  dte, 1),
            (+1, False, put_long,   dte, 1),
        ], dte

    if strategy == StrategyName.BULL_PUT_SPREAD:
        dte      = params.normal_dte
        short_k  = find_strike_for_delta(spx, dte, sigma, params.normal_delta, is_call=False)
        long_k   = find_strike_for_delta(spx, dte, sigma, params.normal_delta * 0.5, is_call=False)
        return [
            (-1, False, short_k, dte, 1),
            (+1, False, long_k,  dte, 1),
        ], dte

    if strategy == StrategyName.BULL_PUT_SPREAD_HV:
        dte      = params.high_vol_dte
        short_k  = find_strike_for_delta(spx, dte, sigma, params.high_vol_delta, is_call=False)
        long_k   = find_strike_for_delta(spx, dte, sigma, params.high_vol_delta * 0.5, is_call=False)
        return [
            (-1, False, short_k, dte, 1),
            (+1, False, long_k,  dte, 1),
        ], dte

    if strategy == StrategyName.BEAR_CALL_SPREAD_HV:
        dte      = 45
        short_k  = find_strike_for_delta(spx, dte, sigma, 0.20, is_call=True)
        long_k   = find_strike_for_delta(spx, dte, sigma, 0.10, is_call=True)
        return [
            (-1, True, short_k, dte, 1),
            (+1, True, long_k,  dte, 1),
        ], dte

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

    return [], 30   # REDUCE_WAIT or unrecognised — no legs


# ─── Buying Power (Schwab Portfolio Margin) ───────────────────────────────────

def _compute_bp(
    strategy: StrategyName,
    legs: list[tuple[int, bool, float, int, int]],
    entry_value: float,
) -> tuple[float, float]:
    """
    Compute spread_width and per-contract buying power under Schwab Portfolio Margin rules
    for broad-based index options (SPX).

    Schwab PM stress-tests each position; for defined-risk spreads the PM margin
    equals the maximum possible loss (spread width minus credit received).

    Args:
        strategy:    The StrategyName enum value.
        legs:        List of (action, is_call, strike, dte, qty) tuples from _build_legs.
        entry_value: Net premium at entry in index points (negative = credit received).

    Returns:
        spread_width    : Width of the widest spread leg in SPX index points.
                          0.0 for strategies with no fixed spread (diagonal, standalone).
        bp_per_contract : Schwab PM buying power per 1 contract in USD.
                          = max_possible_loss_per_contract × $100_multiplier
    """
    credit = abs(entry_value)   # premium collected (or paid) per contract in index points

    if strategy in (
        StrategyName.BULL_PUT_SPREAD,
        StrategyName.BULL_PUT_SPREAD_HV,
        StrategyName.BEAR_CALL_SPREAD_HV,
    ):
        # legs[0] = short put (higher strike), legs[1] = long put (lower strike)
        short_k  = legs[0][2]
        long_k   = legs[1][2]
        spread_w = abs(short_k - long_k)               # e.g. 50 pts
        bp       = (spread_w - credit) * 100           # max loss × $100 multiplier
        return spread_w, max(bp, 0.0)

    if strategy in (StrategyName.IRON_CONDOR, StrategyName.IRON_CONDOR_HV):
        # legs: [short_call, long_call, short_put, long_put]
        call_short_k  = legs[0][2]
        call_long_k   = legs[1][2]
        put_short_k   = legs[2][2]
        put_long_k    = legs[3][2]
        call_spread_w = call_long_k  - call_short_k    # width of call spread
        put_spread_w  = put_short_k  - put_long_k      # width of put spread
        # PM: both sides cannot simultaneously be at max loss; use the wider side
        spread_w = max(call_spread_w, put_spread_w)
        # Full net credit (both spreads) reduces margin on the one side that matters
        bp = (spread_w - credit) * 100
        return spread_w, max(bp, 0.0)

    if strategy == StrategyName.BEAR_CALL_SPREAD:
        # Credit spread: legs[0] = short call (lower strike), legs[1] = long call (higher strike)
        short_k  = legs[0][2]
        long_k   = legs[1][2]
        spread_w = long_k - short_k
        bp       = (spread_w - credit) * 100
        return spread_w, max(bp, 0.0)

    if strategy == StrategyName.BULL_CALL_DIAGONAL:
        # Debit trade: long deep-ITM back-month call + short OTM front-month call.
        # PM treats the long back-month as collateral; max loss ≈ net debit paid.
        bp = entry_value * 100      # entry_value > 0 for debit trades
        return 0.0, max(bp, 0.0)

    if strategy == StrategyName.BULL_CALL_SPREAD:
        # Debit spread: legs[0] = long call (lower strike), legs[1] = short call (higher strike)
        long_k   = legs[0][2]
        short_k  = legs[1][2]
        spread_w = short_k - long_k
        bp       = entry_value * 100   # debit paid is max risk
        return spread_w, max(bp, 0.0)

    if strategy == StrategyName.BEAR_PUT_SPREAD:
        # Debit spread: legs[0] = long put (higher strike), legs[1] = short put (lower strike)
        long_k   = legs[0][2]
        short_k  = legs[1][2]
        spread_w = long_k - short_k
        bp       = entry_value * 100   # debit paid is max risk
        return spread_w, max(bp, 0.0)

    return 0.0, 0.0


def _block_synthetic_ic(existing_keys: set[str], new_key: str | None) -> bool:
    if not new_key:
        return False
    return any((open_key, new_key) in SYNTHETIC_IC_PAIRS for open_key in existing_keys)


def _block_short_gamma_limit(existing_keys: set[str], new_key: str | None, max_positions: int) -> bool:
    if not new_key or new_key not in SHORT_GAMMA_KEYS:
        return False
    current_sg_count = sum(1 for open_key in existing_keys if open_key in SHORT_GAMMA_KEYS)
    return current_sg_count >= max_positions


def _update_hv_spell_state(
    regime: Regime,
    vix: float,
    date: pd.Timestamp,
    hv_spell_start: Optional[pd.Timestamp],
    hv_spell_trade_count: int,
    extreme_vix: float,
) -> tuple[Optional[pd.Timestamp], int]:
    in_high_vol_spell = regime == Regime.HIGH_VOL and vix < extreme_vix
    if in_high_vol_spell:
        if hv_spell_start is None:
            hv_spell_start = date
        return hv_spell_start, hv_spell_trade_count
    return None, 0


def _block_hv_spell_entry(
    regime: Regime,
    vix: float,
    new_key: str | None,
    hv_spell_start: Optional[pd.Timestamp],
    hv_spell_trade_count: int,
    params: StrategyParams,
    date: pd.Timestamp,
) -> bool:
    if regime != Regime.HIGH_VOL or vix >= params.extreme_vix:
        return False
    if new_key not in HIGH_VOL_STRATEGY_KEYS:
        return False
    spell_age = (date - hv_spell_start).days if hv_spell_start is not None else 0
    if spell_age > params.spell_age_cap:
        return True
    if hv_spell_trade_count >= params.max_trades_per_spell:
        return True
    return False


# ─── Metrics ─────────────────────────────────────────────────────────────────

def compute_metrics(trades: list[Trade]) -> dict:
    if not trades:
        return {
            "error": "no trades",
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "calmar": 0.0,
            "cvar5": 0.0,
            "cvar10": 0.0,
            "skew": 0.0,
            "kurt": 0.0,
            "by_strategy": {},
        }

    pnls  = [t.exit_pnl for t in trades]
    wins  = [p for p in pnls if p > 0]
    total = len(pnls)
    pnls_arr = np.array(pnls, dtype=float)
    sorted_pnl = np.sort(pnls_arr)

    equity     = np.cumsum(pnls)
    peak       = np.maximum.accumulate(equity)
    drawdowns  = equity - peak
    max_dd     = float(drawdowns.min())

    # Sharpe (annualised, using actual average holding period)
    mean_pnl   = np.mean(pnls)
    std_pnl    = np.std(pnls, ddof=1) if len(pnls) > 1 else 1e-9
    avg_hold   = sum(t.dte_at_entry - t.dte_at_exit for t in trades) / len(trades) if trades else 30
    sharpe     = (mean_pnl / std_pnl) * math.sqrt(252 / max(avg_hold, 1)) if std_pnl > 0 else 0.0
    total_pnl  = float(pnls_arr.sum())
    calmar     = total_pnl / abs(max_dd) if max_dd != 0 else 0.0
    cvar5      = float(sorted_pnl[:max(1, int(len(pnls_arr) * 0.05))].mean())
    cvar10     = float(sorted_pnl[:max(1, int(len(pnls_arr) * 0.10))].mean())
    skew_val   = float(pd.Series(pnls_arr).skew())
    kurt_val   = float(pd.Series(pnls_arr).kurtosis())
    skew_val   = 0.0 if math.isnan(skew_val) else skew_val
    kurt_val   = 0.0 if math.isnan(kurt_val) else kurt_val

    by_strategy = {}
    strategy_trades = {}
    for t in trades:
        s = t.strategy.value
        by_strategy.setdefault(s, []).append(t.exit_pnl)
        strategy_trades.setdefault(s, []).append(t)

    return {
        "total_trades":   total,
        "win_rate":       len(wins) / total,
        "avg_win":        float(np.mean(wins)) if wins else 0.0,
        "avg_loss":       float(np.mean([p for p in pnls if p <= 0])) if any(p <= 0 for p in pnls) else 0.0,
        "expectancy":     float(mean_pnl),
        "total_pnl":      total_pnl,
        "max_drawdown":   max_dd,
        "sharpe":         float(round(float(sharpe), 2)),
        "calmar":         float(round(float(calmar), 2)),
        "cvar5":          cvar5,
        "cvar10":         cvar10,
        "skew":           round(skew_val, 3),
        "kurt":           round(kurt_val, 3),
        "by_strategy":    {k: {
            "n":        len(v),
            "win_rate": sum(1 for x in v if x > 0) / len(v),
            "avg_pnl":  float(np.mean(v)),
            "avg_rom":    round(float(np.mean([t.rom_annualized for t in strategy_trades[k]])), 3),
            "median_rom": round(float(np.median([t.rom_annualized for t in strategy_trades[k]])), 3),
        } for k, v in by_strategy.items()},
    }


# ─── Main simulation loop ────────────────────────────────────────────────────

def run_backtest(
    start_date: str = "2023-01-01",
    end_date:   str | None = None,
    account_size: float = 150_000.0,
    risk_pct:     float = 0.02,        # 2% account risk per trade
    verbose:      bool  = False,
    interval:     str   = "1d",        # "1d" or "1h" — affects current VIX/SPX only
    params:       StrategyParams = DEFAULT_PARAMS,
    collect_shock_reports: bool = False,
) -> BacktestResult:
    """
    Walk-forward backtest from start_date to end_date (defaults to today).

    Args:
        interval: Bar size for current VIX/SPX price input. "1d" uses daily EOD close
                  for all inputs. "1h" substitutes the first 1h bar of each day for
                  current VIX and current SPX only; all rolling windows (IVR 252-day,
                  MA50, MA200) continue to use the EOD daily series.

    Returns:
        trades  : list of completed Trade objects
        metrics : summary statistics dict
    """
    # ── Load EOD data (always needed for rolling windows) ────────────
    vix_df = fetch_vix_history(period="max")
    spx_df = fetch_spx_history(period="max")
    try:
        vix3m_df = fetch_vix3m_history(period="max")
    except Exception:
        vix3m_df = pd.DataFrame(columns=["vix3m"])

    # Normalise indexes to tz-naive dates — VIX uses America/Chicago,
    # SPX uses America/New_York; they can't be joined directly.
    vix_df.index = pd.to_datetime(vix_df.index.date)
    spx_df.index = pd.to_datetime(spx_df.index.date)
    if not vix3m_df.empty:
        vix3m_df.index = pd.to_datetime(vix3m_df.index.date)

    # ── Optionally load 1h bars for current-value override ──────────
    # Maps date → (vix_open, spx_open) using first 1h bar of each day.
    # Only VIX level and SPX price are overridden; rolling windows stay EOD.
    intraday_current: dict[pd.Timestamp, tuple[float, float]] = {}
    if interval == "1h":
        try:
            vix_1h = fetch_vix_history(period="2y", interval="1h")
            spx_1h = fetch_spx_history(period="2y", interval="1h")
            # Take first bar of each calendar day (earliest timestamp per date)
            vix_1h["_date"] = pd.to_datetime(vix_1h.index.date)
            spx_1h["_date"] = pd.to_datetime(spx_1h.index.date)
            vix_first = vix_1h.groupby("_date")["vix"].first()
            spx_first = spx_1h.groupby("_date")["close"].first()
            for d in vix_first.index.intersection(spx_first.index):
                intraday_current[d] = (float(vix_first[d]), float(spx_first[d]))
        except Exception:
            pass  # Fall back to EOD silently

    df = pd.DataFrame({
        "vix": vix_df["vix"],
        "spx": spx_df["close"],
    })
    if not vix3m_df.empty:
        df["vix3m"] = vix3m_df["vix3m"]
    df = df.dropna(subset=["vix", "spx"])

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

    trades: list[Trade] = []
    signal_history: list[dict] = []
    shock_reports: list[dict] = []
    positions: list[Position] = []
    experiment_id = generate_experiment_id()
    tracker = PortfolioTracker(
        initial_equity=params.initial_equity,
        experiment_id=experiment_id,
        account_size=account_size,
    )
    hv_spell_start: Optional[pd.Timestamp] = None
    hv_spell_trade_count = 0
    bearish_streak = 0

    for i, (date, row) in enumerate(df.iterrows()):
        realized_pnl_today = 0.0
        # EOD values (used for rolling windows in all cases)
        spx_eod = float(row["spx"])
        vix_eod = float(row["vix"])

        # Current-value override: substitute 1h first-bar if available
        if interval == "1h" and date in intraday_current:
            vix, spx = intraday_current[date]
        else:
            vix, spx = vix_eod, spx_eod
        vix3m = None if pd.isna(row.get("vix3m", np.nan)) else float(row["vix3m"])

        sigma = vix / 100.0          # annualised vol

        # ── Compute signals (no lookahead: use data up to today) ─────
        date_key   = pd.Timestamp(date)
        vix_window = full_vix[full_vix.index <= date_key]["vix"]
        spx_window = full_spx[full_spx.index <= date_key]["close"]

        if len(vix_window) < 60 or len(spx_window) < 55:
            continue

        regime   = _classify_regime(vix)
        hv_spell_start, hv_spell_trade_count = _update_hv_spell_state(
            regime,
            vix,
            date,
            hv_spell_start,
            hv_spell_trade_count,
            params.extreme_vix,
        )
        iv_window = (vix_window.iloc[-252:] if len(vix_window) >= 252 else vix_window).copy()
        iv_window.iloc[-1] = vix
        ivr      = compute_iv_rank(iv_window)
        ivp      = compute_iv_percentile(iv_window)
        # SPEC-056 F1: ivp63 for IVP four-quadrant tagging
        _w63 = (vix_window.iloc[-63:] if len(vix_window) >= 63 else vix_window).copy()
        _w63.iloc[-1] = vix
        if len(_w63) < 63:
            ivp63_val: float = float(ivp)
        else:
            ivp63_val = round(
                float((_w63.iloc[:-1] < float(_w63.iloc[-1])).mean()) * 100.0, 1
            )
        _regime_decay = (float(ivp) >= 50.0) and (ivp63_val < 50.0)
        _local_spike = (ivp63_val >= 50.0) and (float(ivp) < 50.0)

        iv_eff   = IVSig.HIGH if ivp > 70 else (IVSig.LOW if ivp < 40 else IVSig.NEUTRAL)

        ma20_val = float(spx_window.rolling(20).mean().iloc[-1]) if len(spx_window) >= 20 else spx
        ma50_val = float(spx_window.rolling(50).mean().iloc[-1]) if len(spx_window) >= 50 else spx
        ma200_val= float(spx_window.rolling(200).mean().iloc[-1]) if len(spx_window) >= 200 else spx
        gap = (spx - ma50_val) / ma50_val if ma50_val else 0
        atr14 = None
        gap_sigma = None
        if len(spx_window) >= 64:
            atr_series = _compute_atr14_close(spx_window)
            latest_atr = atr_series.iloc[-1]
            if pd.notna(latest_atr):
                atr14 = float(latest_atr)
                gap_sigma = (spx - ma50_val) / max(atr14, 1.0)
        if params.use_atr_trend and gap_sigma is not None:
            trend = _classify_trend_atr(gap_sigma)
        else:
            trend = TrendSignal.BULLISH if gap > TREND_THRESHOLD else (
                TrendSignal.BEARISH if gap < -TREND_THRESHOLD else TrendSignal.NEUTRAL
            )
        bearish_streak = bearish_streak + 1 if trend == TrendSignal.BEARISH else 0

        # VIX 5-day trend (no lookahead)
        vix_5d_avg = float(vix_window.iloc[-5:].mean()) if len(vix_window) >= 5 else vix
        vix_5d_ago = float(vix_window.iloc[-10:-5].mean()) if len(vix_window) >= 10 else vix_5d_avg
        vix_trend  = _vix_classify_trend(vix_5d_avg, vix_5d_ago)
        vix_peak_10d = float(vix_window.iloc[-10:].max()) if len(vix_window) >= 10 else None

        # Assemble snapshot objects for selector
        vix_snap   = VixSnapshot(
            date=str(date.date()), vix=vix, regime=regime,
            trend=vix_trend, vix_5d_avg=vix_5d_avg, vix_5d_ago=vix_5d_ago,
            transition_warning=False,
            vix3m=vix3m,
            backwardation=(vix3m is not None and vix > vix3m),
            vix_peak_10d=vix_peak_10d,
        )
        iv_snap    = IVSnapshot(
            date=str(date.date()), vix=vix,
            iv_rank=ivr, iv_percentile=ivp, iv_signal=iv_eff,
            iv_52w_high=float(iv_window.max()), iv_52w_low=float(iv_window.min()),
            ivp63=ivp63_val,
            ivp252=float(ivp),
            regime_decay=_regime_decay,
        )
        trend_snap = TrendSnapshot(
            date=str(date.date()), spx=spx,
            ma20=ma20_val, ma50=ma50_val, ma_gap_pct=gap, signal=trend,
            above_200=(spx > ma200_val),
            atr14=atr14,
            gap_sigma=gap_sigma,
        )
        rec = select_strategy(vix_snap, iv_snap, trend_snap, params)
        rec_key = catalog_key(rec.strategy.value) if rec.strategy != StrategyName.REDUCE_WAIT else None
        spell_age = (date - hv_spell_start).days if hv_spell_start is not None else 0

        # Record signal snapshot for time-series output
        signal_history.append({
            "date":         str(date.date()),
            "vix":          round(vix, 2),
            "regime":       regime.value,
            "ivr":          round(float(ivr), 1),
            "ivp":          round(float(ivp), 1),
            "spx":          round(spx, 2),
            "trend":        trend.value,
            "trend_gap":    round(gap * 100, 2),   # % above/below MA50
            "vix_5d_avg":   round(vix_5d_avg, 2),
            "strategy":     rec.strategy.value,
            "strategy_key": rec_key,
            "hv_spell_age": spell_age if rec_key in HIGH_VOL_STRATEGY_KEYS or regime == Regime.HIGH_VOL else 0,
            "bearish_streak": bearish_streak,
            "ivp63": round(ivp63_val, 1),
            "ivp252": round(float(ivp), 1),
            "regime_decay": _regime_decay,
            "local_spike": _local_spike,
            "iv_signal": iv_eff.value,
        })

        # ── Manage open positions ────────────────────────────────────
        for position in list(positions):
            position.days_held += 1
            current_val  = _current_value(position.legs, spx, sigma, position.days_held)
            # P&L = current_val - entry_value
            # Credit trade: entry_value=-500, current_val=-250 → pnl=+250 (profit) ✓
            # Debit  trade: entry_value=+500, current_val=+700 → pnl=+200 (profit) ✓
            pnl          = current_val - position.entry_value

            short_leg    = _short_leg(position.legs)
            short_dte    = max(short_leg[3] - position.days_held, 0)

            # Exit conditions
            exit_reason  = None
            is_credit    = position.entry_value < 0
            if abs(position.entry_value) > 0:
                pnl_ratio = pnl / abs(position.entry_value)
                if pnl_ratio >= params.profit_target and position.days_held >= params.min_hold_days:
                    exit_reason = "50pct_profit"
                elif is_credit and pnl_ratio <= -params.stop_mult:   # credit trade stop
                    exit_reason = "stop_loss"
                elif not is_credit and pnl_ratio <= -0.50:           # debit trade stop at 50% loss
                    exit_reason = "stop_loss"

            if short_dte <= 21 and exit_reason is None:
                exit_reason = "roll_21dte"

            # Roll Up: SPX has rallied ≥3% since entry, making the short put far OTM.
            # Close and re-enter at current price to restore theta efficiency.
            # Conditions: BPS strategy, enough DTE remaining, regime not LOW_VOL, IVP ≥ 30.
            # Note: delta-based condition was removed because it is structurally mutually
            # exclusive with IVP>=40 (SPX rally → VIX falls → IVP drops below 40).
            if (exit_reason is None
                    and short_dte > 14
                    and position.strategy in (StrategyName.BULL_PUT_SPREAD,
                                              StrategyName.BULL_PUT_SPREAD_HV)):
                spx_gain = (spx - position.entry_spx) / position.entry_spx
                if (spx_gain >= 0.03
                        and regime != Regime.LOW_VOL
                        and ivp >= 30):
                    exit_reason = "roll_up"

            # Trend flip exit: Bull Call Diagonal — BEARISH trend breaks the bullish premise.
            # Analysis (2026-03-28): all 8 historical diagonal losses had BEARISH flip within
            # days 1-8; min day=3 avoids noise from single-day oscillations.
            if (exit_reason is None
                    and position.days_held >= 3
                    and position.strategy == StrategyName.BULL_CALL_DIAGONAL
                    and bearish_streak >= max(params.bearish_persistence_days, 1)):
                exit_reason = "trend_flip"


            if exit_reason:
                t = _close_position(
                    position=position,
                    date=date,
                    spx=spx,
                    sigma=sigma,
                    account_size=account_size,
                    exit_reason=exit_reason,
                )
                realized_pnl_today += t.exit_pnl
                trades.append(t)
                if verbose:
                    print(f"  EXIT  {t.exit_date}  {t.strategy.value:<25}  "
                          f"PnL: {t.exit_pnl:+.0f}  ({exit_reason})")
                positions.remove(position)

        _used_bp_usd = sum(_position_total_bp(position, account_size) for position in positions)
        _used_bp = _used_bp_usd / account_size if account_size else 0.0
        book_positions = [_position_snapshot(position, spx, account_size) for position in positions]
        book_report = run_shock_check(
            positions=book_positions,
            current_spx=spx,
            current_vix=vix,
            date=str(date.date()),
            params=params,
            candidate_position=None,
            account_size=account_size,
            is_high_vol=(regime == Regime.HIGH_VOL),
        )
        bp_headroom_pct = max(0.0, 1.0 - _used_bp)
        vix_3d_ago = float(vix_window.iloc[-4]) if len(vix_window) >= 4 else vix
        overlay = compute_overlay_signals(
            vix=vix,
            vix_3d_ago=vix_3d_ago,
            book_core_shock=book_report.pre_max_core_loss_pct,
            bp_headroom=bp_headroom_pct,
            params=params,
        )
        signal_history[-1]["overlay_level"] = int(overlay.level)
        signal_history[-1]["overlay_reason"] = overlay.trigger_reason
        signal_history[-1]["book_core_shock"] = round(book_report.pre_max_core_loss_pct, 5)

        if overlay.force_trim and positions:
            trim_reason = "overlay_emergency" if overlay.force_emergency else "overlay_trim"
            for position in list(positions):
                trade = _close_position(
                    position=position,
                    date=date,
                    spx=spx,
                    sigma=sigma,
                    account_size=account_size,
                    exit_reason=trim_reason,
                )
                realized_pnl_today += trade.exit_pnl
                trades.append(trade)
                positions.remove(position)
            _used_bp_usd = 0.0
            _used_bp = 0.0
            bp_headroom_pct = 1.0

        # ── Open new position (if BP ceiling and dedup allow) ───────────────────
        _new_bp_target = params.bp_target_for_regime(regime)
        _ceiling = params.bp_ceiling_for_regime(regime)
        _already_open = (
            sum(1 for p in positions if p.strategy == rec.strategy) >= IC_HV_MAX_CONCURRENT
            if rec.strategy == StrategyName.IRON_CONDOR_HV
            else any(p.strategy == rec.strategy for p in positions)
        )
        _existing_keys = {catalog_key(p.strategy.value) for p in positions}
        _synthetic_block = _block_synthetic_ic(_existing_keys, rec_key)
        _sg_block = _block_short_gamma_limit(_existing_keys, rec_key, params.max_short_gamma_positions)
        _spell_block = _block_hv_spell_entry(
            regime,
            vix,
            rec_key,
            hv_spell_start,
            hv_spell_trade_count,
            params,
            date,
        )

        candidate_report = None
        bp_headroom_breach = False

        if (rec.strategy != StrategyName.REDUCE_WAIT
                and not overlay.block_new_entries
                and not _already_open
                and not _synthetic_block
                and not _sg_block
                and not _spell_block
                and _used_bp + _new_bp_target <= _ceiling):
            legs, short_dte = _build_legs(rec.strategy, spx, sigma, params)
            if legs:
                ev = _entry_value(legs, spx, sigma)
                size_mult = params.high_vol_size if rec.strategy in (
                    StrategyName.BULL_PUT_SPREAD_HV,
                    StrategyName.BEAR_CALL_SPREAD_HV,
                    StrategyName.IRON_CONDOR_HV,
                ) else 1.0
                short_k_new = _short_leg(legs)[2] if legs else 0.0
                sw, bp_per_c = _compute_bp(rec.strategy, legs, ev)
                candidate_position = Position(
                    strategy=rec.strategy,
                    underlying=rec.underlying,
                    entry_date=str(date.date()),
                    entry_spx=spx,
                    entry_vix=vix,
                    entry_sigma=sigma,
                    legs=legs,
                    entry_value=ev,
                    days_held=0,
                    size_mult=size_mult,
                    short_strike=short_k_new,
                    spread_width=sw,
                    bp_per_contract=bp_per_c,
                    bp_target=params.bp_target_for_regime(regime),
                )
                candidate_snapshot = _position_snapshot(candidate_position, spx, account_size)
                candidate_report = run_shock_check(
                    positions=[_position_snapshot(position, spx, account_size) for position in positions],
                    current_spx=spx,
                    current_vix=vix,
                    date=str(date.date()),
                    params=params,
                    candidate_position=candidate_snapshot,
                    account_size=account_size,
                    is_high_vol=(regime == Regime.HIGH_VOL),
                )
                post_bp_used_pct = _used_bp + _new_bp_target
                bp_headroom_breach = (1.0 - post_bp_used_pct) < params.shock_budget_bp_headroom
                if collect_shock_reports:
                    report_payload = candidate_report.to_dict()
                    report_payload.update(
                        {
                            "regime": regime.value,
                            "strategy_key": rec_key,
                            "bp_headroom_pct": max(0.0, 1.0 - post_bp_used_pct),
                            "bp_headroom_budget": params.shock_budget_bp_headroom,
                        }
                    )
                    shock_reports.append(report_payload)
                if candidate_report.approved and not bp_headroom_breach:
                    positions.append(candidate_position)
                    if verbose:
                        print(f"  ENTER {date.date()}  {rec.strategy.value:<25}  "
                              f"value: {ev:+.2f}  VIX:{vix:.1f}")
                    if rec_key in HIGH_VOL_STRATEGY_KEYS:
                        hv_spell_trade_count += 1

        open_marks = {
            _position_id(position): _position_unrealized_pnl(position, spx, sigma, account_size)
            for position in positions
        }
        used_bp_usd = sum(_position_total_bp(position, account_size) for position in positions)
        tracker.update_day(
            date=str(date.date()),
            realized_pnl=realized_pnl_today,
            open_position_marks=open_marks,
            bp_used=used_bp_usd,
            bp_headroom=max(account_size - used_bp_usd, 0.0),
            short_gamma_count=sum(1 for position in positions if catalog_key(position.strategy.value) in SHORT_GAMMA_KEYS),
            open_positions=len(positions),
            regime=regime.value,
            vix=vix,
        )

    # Close all still-open positions at last price
    for position in positions:
        trades.append(
            _close_position(
                position=position,
                date=df.index[-1],
                spx=float(df["spx"].iloc[-1]),
                sigma=sigma,
                account_size=account_size,
                exit_reason="end_of_backtest",
            )
        )

    portfolio_rows = tracker.get_rows()
    metrics = compute_metrics(trades)
    portfolio_metrics = compute_portfolio_metrics(portfolio_rows).to_dict() if portfolio_rows else None
    return BacktestResult(
        trades=trades,
        metrics=metrics,
        signals=signal_history,
        portfolio_rows=portfolio_rows,
        shock_reports=shock_reports,
        experiment_id=experiment_id,
        config_hash=config_hash(params),
        portfolio_metrics=portfolio_metrics,
    )


def run_signals_only(
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    interval: str = "1d",
    params: StrategyParams = DEFAULT_PARAMS,
) -> list[dict]:
    """
    Generate historical signal snapshots without running trade simulation.
    """
    vix_df = fetch_vix_history(period="max")
    spx_df = fetch_spx_history(period="max")
    try:
        vix3m_df = fetch_vix3m_history(period="max")
    except Exception:
        vix3m_df = pd.DataFrame(columns=["vix3m"])

    vix_df.index = pd.to_datetime(vix_df.index.date)
    spx_df.index = pd.to_datetime(spx_df.index.date)
    if not vix3m_df.empty:
        vix3m_df.index = pd.to_datetime(vix3m_df.index.date)

    intraday_current: dict[pd.Timestamp, tuple[float, float]] = {}
    if interval == "1h":
        try:
            vix_1h = fetch_vix_history(period="2y", interval="1h")
            spx_1h = fetch_spx_history(period="2y", interval="1h")
            vix_1h["_date"] = pd.to_datetime(vix_1h.index.date)
            spx_1h["_date"] = pd.to_datetime(spx_1h.index.date)
            vix_first = vix_1h.groupby("_date")["vix"].first()
            spx_first = spx_1h.groupby("_date")["close"].first()
            for d in vix_first.index.intersection(spx_first.index):
                intraday_current[d] = (float(vix_first[d]), float(spx_first[d]))
        except Exception:
            pass

    df = pd.DataFrame({
        "vix": vix_df["vix"],
        "spx": spx_df["close"],
    })
    if not vix3m_df.empty:
        df["vix3m"] = vix3m_df["vix3m"]
    df = df.dropna(subset=["vix", "spx"])
    df = df[df.index >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df.index <= pd.Timestamp(end_date)]

    if len(df) < 60:
        raise ValueError(f"Not enough data after filtering: {len(df)} rows")

    lookback_start = pd.Timestamp(start_date) - pd.Timedelta("400D")
    full_vix = vix_df[vix_df.index >= lookback_start]
    full_spx = spx_df[spx_df.index >= lookback_start]

    signal_history: list[dict] = []
    hv_spell_start: Optional[pd.Timestamp] = None
    hv_spell_trade_count = 0
    bearish_streak = 0

    for date, row in df.iterrows():
        spx_eod = float(row["spx"])
        vix_eod = float(row["vix"])
        if interval == "1h" and date in intraday_current:
            vix, spx = intraday_current[date]
        else:
            vix, spx = vix_eod, spx_eod
        vix3m = None if pd.isna(row.get("vix3m", np.nan)) else float(row["vix3m"])

        date_key = pd.Timestamp(date)
        vix_window = full_vix[full_vix.index <= date_key]["vix"]
        spx_window = full_spx[full_spx.index <= date_key]["close"]

        if len(vix_window) < 60 or len(spx_window) < 55:
            continue

        regime = _classify_regime(vix)
        hv_spell_start, hv_spell_trade_count = _update_hv_spell_state(
            regime,
            vix,
            date,
            hv_spell_start,
            hv_spell_trade_count,
            params.extreme_vix,
        )
        iv_window = (vix_window.iloc[-252:] if len(vix_window) >= 252 else vix_window).copy()
        iv_window.iloc[-1] = vix
        ivr = compute_iv_rank(iv_window)
        ivp = compute_iv_percentile(iv_window)
        # SPEC-056 F1: ivp63 for IVP four-quadrant tagging
        _w63 = (vix_window.iloc[-63:] if len(vix_window) >= 63 else vix_window).copy()
        _w63.iloc[-1] = vix
        if len(_w63) < 63:
            ivp63_val: float = float(ivp)
        else:
            ivp63_val = round(
                float((_w63.iloc[:-1] < float(_w63.iloc[-1])).mean()) * 100.0, 1
            )
        _regime_decay = (float(ivp) >= 50.0) and (ivp63_val < 50.0)
        _local_spike = (ivp63_val >= 50.0) and (float(ivp) < 50.0)
        iv_eff = IVSig.HIGH if ivp > 70 else (IVSig.LOW if ivp < 40 else IVSig.NEUTRAL)

        ma20_val = float(spx_window.rolling(20).mean().iloc[-1]) if len(spx_window) >= 20 else spx
        ma50_val = float(spx_window.rolling(50).mean().iloc[-1]) if len(spx_window) >= 50 else spx
        ma200_val = float(spx_window.rolling(200).mean().iloc[-1]) if len(spx_window) >= 200 else spx
        gap = (spx - ma50_val) / ma50_val if ma50_val else 0

        atr14 = None
        gap_sigma = None
        if len(spx_window) >= 64:
            atr_series = _compute_atr14_close(spx_window)
            latest_atr = atr_series.iloc[-1]
            if pd.notna(latest_atr):
                atr14 = float(latest_atr)
                gap_sigma = (spx - ma50_val) / max(atr14, 1.0)
        if params.use_atr_trend and gap_sigma is not None:
            trend = _classify_trend_atr(gap_sigma)
        else:
            trend = TrendSignal.BULLISH if gap > TREND_THRESHOLD else (
                TrendSignal.BEARISH if gap < -TREND_THRESHOLD else TrendSignal.NEUTRAL
            )
        bearish_streak = bearish_streak + 1 if trend == TrendSignal.BEARISH else 0

        vix_5d_avg = float(vix_window.iloc[-5:].mean()) if len(vix_window) >= 5 else vix
        vix_5d_ago = float(vix_window.iloc[-10:-5].mean()) if len(vix_window) >= 10 else vix_5d_avg
        vix_trend = _vix_classify_trend(vix_5d_avg, vix_5d_ago)
        vix_peak_10d = float(vix_window.iloc[-10:].max()) if len(vix_window) >= 10 else None

        vix_snap = VixSnapshot(
            date=str(date.date()), vix=vix, regime=regime,
            trend=vix_trend, vix_5d_avg=vix_5d_avg, vix_5d_ago=vix_5d_ago,
            transition_warning=False, vix3m=vix3m,
            backwardation=(vix3m is not None and vix > vix3m),
            vix_peak_10d=vix_peak_10d,
        )
        iv_snap = IVSnapshot(
            date=str(date.date()), vix=vix,
            iv_rank=ivr, iv_percentile=ivp, iv_signal=iv_eff,
            iv_52w_high=float(iv_window.max()), iv_52w_low=float(iv_window.min()),
            ivp63=ivp63_val,
            ivp252=float(ivp),
            regime_decay=_regime_decay,
        )
        trend_snap = TrendSnapshot(
            date=str(date.date()), spx=spx,
            ma20=ma20_val, ma50=ma50_val, ma_gap_pct=gap, signal=trend,
            above_200=(spx > ma200_val), atr14=atr14, gap_sigma=gap_sigma,
        )
        rec = select_strategy(vix_snap, iv_snap, trend_snap, params)
        rec_key = catalog_key(rec.strategy.value) if rec.strategy != StrategyName.REDUCE_WAIT else None
        spell_age = (date - hv_spell_start).days if hv_spell_start is not None else 0

        signal_history.append({
            "date": str(date.date()),
            "vix": round(vix, 2),
            "regime": regime.value,
            "ivr": round(float(ivr), 1),
            "ivp": round(float(ivp), 1),
            "spx": round(spx, 2),
            "trend": trend.value,
            "trend_gap": round(gap * 100, 2),
            "vix_5d_avg": round(vix_5d_avg, 2),
            "strategy": rec.strategy.value,
            "strategy_key": rec_key,
            "hv_spell_age": spell_age if rec_key in HIGH_VOL_STRATEGY_KEYS or regime == Regime.HIGH_VOL else 0,
            "bearish_streak": bearish_streak,
            "ivp63": round(ivp63_val, 1),
            "ivp252": round(float(ivp), 1),
            "regime_decay": _regime_decay,
            "local_spike": _local_spike,
            "iv_signal": iv_eff.value,
        })

    return signal_history


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
    print(f"  Calmar       : {metrics['calmar']:.2f}")
    print(f"  CVaR 5%      : ${metrics['cvar5']:+,.0f}")
    print(f"  CVaR 10%     : ${metrics['cvar10']:+,.0f}")
    print(f"  Skew / Kurt  : {metrics['skew']:+.2f} / {metrics['kurt']:+.2f}")

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
    trades, metrics, _ = run_backtest(start_date="2023-01-01", verbose=False)
    print_report(trades, metrics)
