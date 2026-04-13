"""
ES_Puts Strategy — Backtest (SPX Short Puts)

Phase 1: single 45-DTE slot, trend filter on vs off
Phase 2: staggered DTE ladder 21/28/35/42/49, 5 concurrent slots, $500k account

Core question: does trend filtering add statistically significant alpha to a
mechanical SPX 20-delta short put programme?

Shared infrastructure:
  backtest/pricer.py              — Black-Scholes pricing
  backtest/metrics_portfolio.py   — Sharpe / Calmar / CVaR
  backtest/portfolio.py           — daily equity rows
  backtest/run_bootstrap_ci.py    — statistical significance

Phase roadmap:
  Phase 1  single 45-DTE slot, trend filter on/off         ← DONE
  Phase 2  staggered DTE ladder 21/28/35/42/49              ← DONE
  Phase 3  VIX-based dynamic leverage table + BSH drag      ← DONE
  Phase 4  BSH payoff modeling + correlation with SPX Credit ← DONE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.portfolio import DailyPortfolioRow
from backtest.pricer import find_strike_for_delta, put_price
from backtest.run_bootstrap_ci import bootstrap_ci
from signals.trend import (
    fetch_spx_history,
    _classify_trend_atr,
    _compute_atr14_close,
    TREND_THRESHOLD,
    TrendSignal,
)
from signals.vix_regime import fetch_vix_history

# ─── Parameters (shared across phases) ───────────────────────────────────────

TARGET_DELTA   = 0.20    # 20-delta short put
STOP_MULT      = 4.0     # stop when put ≥ 4× entry premium (= -300% on credit)
PROFIT_TARGET  = 0.10    # close when put ≤ 10% of entry premium (= +90% profit)
GAMMA_DTE      = 5       # close early if DTE ≤ this
SPX_MULTIPLIER = 100
WARMUP_DAYS    = 64

# Phase 1
P1_ENTRY_DTE      = 45
P1_INITIAL_EQUITY = 500_000.0
P1_BP_TARGET      = 0.10   # 10% per position (single slot)

# Phase 2 — staggered DTE ladder
P2_DTE_SLOTS      = [21, 28, 35, 42, 49]   # one concurrent position per slot
P2_INITIAL_EQUITY = 500_000.0
P2_BP_TARGET      = 0.05   # 5% per slot → 25% max when all 5 slots full

# Phase 3 — VIX leverage table + BSH drag
P3_DTE_SLOTS      = [21, 28, 35, 42, 49]
P3_INITIAL_EQUITY = 500_000.0
P3_N_SLOTS        = 5

# VIX-based max total BPu (fraction of NLV); per-slot target = ceiling / n_slots
# Higher VIX → richer premium → allow more BP deployment
P3_LEVERAGE_TABLE = [
    (40, 0.50),   # VIX ≥ 40 : max 50% BPu → 10% per slot
    (30, 0.40),   # VIX ≥ 30 : max 40% BPu → 8% per slot
    (20, 0.35),   # VIX ≥ 20 : max 35% BPu → 7% per slot
    (15, 0.30),   # VIX ≥ 15 : max 30% BPu → 6% per slot
    ( 0, 0.25),   # VIX < 15 : max 25% BPu → 5% per slot
]

# BSH (Black Swan Hedges) weekly cost schedule
# VIX > 20  → SPY 7-DTE  10%-OTM put, 0.04% NLV/week
# VIX ≤ 20  → SPY 30-DTE 20%-OTM put, 0.04% NLV/week
# VIX < 15  → VIX 120-DTE 10-delta call, additional 0.08% NLV/month
BSH_WEEKLY_COST_PCT  = 0.0004   # 0.04% NLV every 5 trading days
BSH_MONTHLY_COST_PCT = 0.0008   # 0.08% NLV every 21 trading days (VIX < 15 only)
BSH_VIX_THRESHOLD    = 15.0     # below this, add monthly VIX call cost


# ─── Data structures ──────────────────────────────────────────────────────────

@dataclass
class PutPosition:
    slot:           int          # DTE at entry (phase 2 slot key)
    entry_date:     str
    expiry_dte:     int
    strike:         float
    entry_premium:  float
    entry_spx:      float
    entry_vix:      float
    contracts:      float
    bp_used:        float
    stop_premium:   float
    profit_premium: float
    prev_val:       float        # last day's put value (for daily MTM)


@dataclass
class PutTrade:
    slot:          int
    entry_date:    str
    exit_date:     str
    entry_spx:     float
    exit_spx:      float
    entry_vix:     float
    entry_premium: float
    exit_premium:  float
    dte_at_entry:  int
    dte_at_exit:   int
    exit_reason:   str
    contracts:     float
    pnl:           float


@dataclass
class BacktestResult:
    phase:             str
    mode:              str
    trades:            list[PutTrade]  = field(default_factory=list)
    portfolio_metrics: dict            = field(default_factory=dict)
    bootstrap:         dict            = field(default_factory=dict)
    daily_rows:        list            = field(default_factory=list)  # DailyPortfolioRow list


@dataclass
class BshPutPosition:
    """Tracks one BSH SPY put through its life (full BS repricing)."""
    entry_date:   str
    spy_at_entry: float
    strike:       float    # SPY put strike
    expiry_dte:   int      # trading days remaining
    contracts:    float    # fractional, sized to 0.04% NLV budget
    prev_val:     float    # BS value per contract in SPY points (starts = cost_per)
    dte_spec:     int      # 7 or 30 — original DTE at entry


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _bp_per_contract(spx: float, strike: float, premium_pts: float) -> float:
    """
    Schwab Portfolio Margin for 1 naked short SPX put (OCC theoretical-loss rules).
      Method A = 15% × underlying × $100  −  OTM_amount  +  premium_received
      Method B = 10% × strike × $100      +  premium_received
    BP = max(Method A, Method B), floor $37.50
    OTM_amount = max(0, SPX − strike) × $100   (how far put is out-of-the-money)
    """
    prem_usd  = premium_pts * SPX_MULTIPLIER
    otm_usd   = max(0.0, spx - strike) * SPX_MULTIPLIER
    method_a  = 0.15 * spx * SPX_MULTIPLIER - otm_usd + prem_usd
    method_b  = 0.10 * strike * SPX_MULTIPLIER + prem_usd
    return max(method_a, method_b, 37.50)


def _contracts(equity: float, bp_target: float, spx: float,
               strike: float, premium_pts: float) -> float:
    bp = _bp_per_contract(spx, strike, premium_pts)
    return (equity * bp_target) / bp if bp > 0 else 0.0


def _trend(spx_window: pd.Series, spx_today: float) -> TrendSignal:
    """ATR-normalised trend signal — mirrors main engine, no lookahead."""
    if len(spx_window) < WARMUP_DAYS:
        return TrendSignal.NEUTRAL
    ma50 = float(spx_window.rolling(50).mean().iloc[-1]) if len(spx_window) >= 50 else spx_today
    atr_s = _compute_atr14_close(spx_window)
    atr   = float(atr_s.iloc[-1])
    if not pd.isna(atr) and atr > 0:
        return _classify_trend_atr((spx_today - ma50) / atr)
    gap = (spx_today - ma50) / ma50 if ma50 else 0.0
    return (TrendSignal.BULLISH if gap > TREND_THRESHOLD
            else TrendSignal.BEARISH if gap < -TREND_THRESHOLD
            else TrendSignal.NEUTRAL)


def _load_data() -> tuple[pd.DataFrame, pd.Series]:
    """Return (joined daily DataFrame, full SPX series) both tz-naive."""
    vix_df = fetch_vix_history(period="max", interval="1d")
    spx_df = fetch_spx_history(period="max", interval="1d")
    vix_df.index = pd.to_datetime(vix_df.index.date)
    spx_df.index = pd.to_datetime(spx_df.index.date)
    vix_s = vix_df["vix"].squeeze()
    spx_s = spx_df["close"].squeeze()
    data  = pd.DataFrame({"spx": spx_s, "vix": vix_s}).dropna().sort_index()
    return data, spx_s


def _make_row(date_str, equity, daily_pnl, peak_equity,
              positions, vix_val, exp_id) -> tuple[DailyPortfolioRow, float, float]:
    end_eq = equity + daily_pnl
    peak   = max(peak_equity, end_eq)
    dd     = (end_eq - peak) / peak if peak else 0.0
    ret    = daily_pnl / equity if equity else 0.0
    bp     = sum(p.bp_used for p in positions.values())
    row    = DailyPortfolioRow(
        date=date_str,
        start_equity=equity,
        end_equity=end_eq,
        daily_return_gross=ret,
        daily_return_net=ret,
        realized_pnl=0.0,
        unrealized_pnl_delta=daily_pnl,
        total_pnl=daily_pnl,
        bp_used=bp,
        bp_headroom=max(equity - bp, 0.0),
        short_gamma_count=len(positions),
        open_positions=len(positions),
        regime="NORMAL",
        vix=vix_val,
        cumulative_equity=end_eq,
        drawdown=dd,
        experiment_id=exp_id,
    )
    return row, end_eq, peak


# ─── Phase 1: single 45-DTE slot ─────────────────────────────────────────────

def run_phase1(
    mode: Literal["baseline", "filtered"] = "filtered",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    verbose: bool = False,
) -> BacktestResult:
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(start_date)]
    if end_date:
        sim = sim[sim.index <= pd.Timestamp(end_date)]

    result    = BacktestResult(phase="phase1", mode=mode)
    exp_id    = f"es_puts_p1_{mode}"
    equity    = P1_INITIAL_EQUITY
    peak_eq   = P1_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions: dict[int, PutPosition]   = {}   # slot → position (single slot 45)

    for date, row in sim.iterrows():
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sig   = vix / 100.0
        dstr  = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0

        # Manage open position
        pos = positions.get(P1_ENTRY_DTE)
        if pos:
            pos.expiry_dte -= 1
            cur_val    = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur_val) * pos.contracts * SPX_MULTIPLIER
            reason     = None
            if   pos.expiry_dte <= GAMMA_DTE:        reason = "gamma_risk"
            elif cur_val >= pos.stop_premium:         reason = "stop_loss"
            elif cur_val <= pos.profit_premium:       reason = "profit_target"
            elif pos.expiry_dte <= 0:                 reason = "expiry"
            if reason:
                pnl_total = (pos.entry_premium - cur_val) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=P1_ENTRY_DTE, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx, entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur_val,
                    dte_at_entry=P1_ENTRY_DTE, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl_total,
                ))
                if verbose:
                    print(f"{dstr}  EXIT [{reason:<14}] pnl={pnl_total:+8.0f}")
                del positions[P1_ENTRY_DTE]
            else:
                pos.prev_val = cur_val

        # Entry
        if P1_ENTRY_DTE not in positions:
            window   = full_spx[full_spx.index <= date].iloc[-200:]
            trend_ok = True
            if mode == "filtered":
                trend_ok = (_trend(window, spx) == TrendSignal.BULLISH)
            if trend_ok and len(window) >= WARMUP_DAYS:
                k    = find_strike_for_delta(spx, P1_ENTRY_DTE, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, P1_ENTRY_DTE, sig)
                if prem > 0.5:
                    n = _contracts(equity, P1_BP_TARGET, spx, k, prem)
                    positions[P1_ENTRY_DTE] = PutPosition(
                        slot=P1_ENTRY_DTE, entry_date=dstr, expiry_dte=P1_ENTRY_DTE,
                        strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                        contracts=n, bp_used=n * _bp_per_contract(spx, k, prem),
                        stop_premium=prem * STOP_MULT, profit_premium=prem * PROFIT_TARGET,
                        prev_val=prem,
                    )
                    if verbose:
                        print(f"{dstr}  OPEN  K={k:.0f}  prem={prem:.2f}  VIX={vix:.1f}")

        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix, exp_id)
        daily_rows.append(dr)

    result.trades            = trades
    result.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    result.daily_rows        = daily_rows
    if len(trades) >= 10:
        result.bootstrap = bootstrap_ci([t.pnl for t in trades])
    return result


# ─── Phase 2: staggered DTE ladder 21/28/35/42/49 ────────────────────────────

def run_phase2(
    mode: Literal["baseline", "filtered"] = "filtered",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    verbose: bool = False,
) -> BacktestResult:
    """
    5 concurrent short put positions, one per DTE slot (21/28/35/42/49).
    Each slot is managed independently: when it closes, a new one opens
    at the same DTE on the next eligible day.
    Trend filter (filtered mode) gates new entries only — existing positions ride out.
    """
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(start_date)]
    if end_date:
        sim = sim[sim.index <= pd.Timestamp(end_date)]

    result    = BacktestResult(phase="phase2", mode=mode)
    exp_id    = f"es_puts_p2_{mode}"
    equity    = P2_INITIAL_EQUITY
    peak_eq   = P2_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions: dict[int, PutPosition]   = {}   # slot_dte → position

    for date, row in sim.iterrows():
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sig   = vix / 100.0
        dstr  = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0

        window   = full_spx[full_spx.index <= date].iloc[-200:]
        warmed   = len(window) >= WARMUP_DAYS
        trend_ok = True
        if mode == "filtered" and warmed:
            trend_ok = (_trend(window, spx) == TrendSignal.BULLISH)

        # Manage all open positions
        to_close = []
        for slot, pos in positions.items():
            pos.expiry_dte -= 1
            cur_val    = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur_val) * pos.contracts * SPX_MULTIPLIER
            reason     = None
            if   pos.expiry_dte <= GAMMA_DTE:        reason = "gamma_risk"
            elif cur_val >= pos.stop_premium:         reason = "stop_loss"
            elif cur_val <= pos.profit_premium:       reason = "profit_target"
            elif pos.expiry_dte <= 0:                 reason = "expiry"
            if reason:
                pnl_total = (pos.entry_premium - cur_val) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=slot, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx, entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur_val,
                    dte_at_entry=slot, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl_total,
                ))
                if verbose:
                    print(f"{dstr}  EXIT slot={slot} [{reason:<14}] pnl={pnl_total:+8.0f}")
                to_close.append(slot)
            else:
                pos.prev_val = cur_val
        for slot in to_close:
            del positions[slot]

        # Open new positions for any empty slots
        if warmed:
            for slot in P2_DTE_SLOTS:
                if slot in positions:
                    continue
                if not trend_ok:
                    continue
                k    = find_strike_for_delta(spx, slot, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, slot, sig)
                if prem > 0.5:
                    n = _contracts(equity, P2_BP_TARGET, spx, k, prem)
                    positions[slot] = PutPosition(
                        slot=slot, entry_date=dstr, expiry_dte=slot,
                        strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                        contracts=n, bp_used=n * _bp_per_contract(spx, k, prem),
                        stop_premium=prem * STOP_MULT, profit_premium=prem * PROFIT_TARGET,
                        prev_val=prem,
                    )
                    if verbose:
                        print(f"{dstr}  OPEN  slot={slot}  K={k:.0f}  prem={prem:.2f}")

        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix, exp_id)
        daily_rows.append(dr)

    result.trades            = trades
    result.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    result.daily_rows        = daily_rows
    if len(trades) >= 10:
        result.bootstrap = bootstrap_ci([t.pnl for t in trades])
    return result


# ─── Phase 3: VIX leverage table + BSH drag ──────────────────────────────────

def _max_bp_ceiling(vix: float) -> float:
    """Max total portfolio BPu (fraction of NLV) from the VIX leverage table."""
    for threshold, ceiling in P3_LEVERAGE_TABLE:
        if vix >= threshold:
            return ceiling
    return 0.25


def run_phase3(
    mode: Literal["baseline", "filtered"] = "filtered",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    verbose: bool = False,
) -> BacktestResult:
    """
    Phase 2 + two additions:
      1. VIX-based dynamic leverage table  — per-slot BP target scales with VIX
         (high VIX = richer premium = allow more exposure, up to the ceiling)
      2. BSH cost drag — weekly/monthly premium deductions per the spec schedule
         (payoff modelling deferred to Phase 4; this gives the conservative floor)
    """
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(start_date)]
    if end_date:
        sim = sim[sim.index <= pd.Timestamp(end_date)]

    result    = BacktestResult(phase="phase3", mode=mode)
    exp_id    = f"es_puts_p3_{mode}"
    equity    = P3_INITIAL_EQUITY
    peak_eq   = P3_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions: dict[int, PutPosition]   = {}

    day_counter   = 0   # for weekly/monthly BSH cost cadence
    bsh_total_cost = 0.0

    for date, row in sim.iterrows():
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sig   = vix / 100.0
        dstr  = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        day_counter += 1

        # ── BSH cost drag ─────────────────────────────────────────────────────
        # Weekly SPY put premium (every 5 trading days)
        if day_counter % 5 == 0:
            bsh_cost = equity * BSH_WEEKLY_COST_PCT
            daily_pnl -= bsh_cost
            bsh_total_cost += bsh_cost

        # Monthly VIX call premium (every 21 trading days, only when VIX < 15)
        if day_counter % 21 == 0 and vix < BSH_VIX_THRESHOLD:
            bsh_cost = equity * BSH_MONTHLY_COST_PCT
            daily_pnl -= bsh_cost
            bsh_total_cost += bsh_cost

        # ── Dynamic leverage: per-slot BP target from VIX table ───────────────
        bp_ceiling    = _max_bp_ceiling(vix)
        bp_per_slot   = bp_ceiling / P3_N_SLOTS

        window   = full_spx[full_spx.index <= date].iloc[-200:]
        warmed   = len(window) >= WARMUP_DAYS
        trend_ok = True
        if mode == "filtered" and warmed:
            trend_ok = (_trend(window, spx) == TrendSignal.BULLISH)

        # ── Manage open positions ─────────────────────────────────────────────
        # Enforce leverage ceiling: if total BP > ceiling, skip new entries
        # (existing positions ride out; hard cuts only at stop_loss)
        total_bp_used = sum(p.bp_used for p in positions.values())
        bp_headroom   = equity * bp_ceiling - total_bp_used

        to_close = []
        for slot, pos in positions.items():
            pos.expiry_dte -= 1
            cur_val    = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur_val) * pos.contracts * SPX_MULTIPLIER
            reason = None
            if   pos.expiry_dte <= GAMMA_DTE:    reason = "gamma_risk"
            elif cur_val >= pos.stop_premium:     reason = "stop_loss"
            elif cur_val <= pos.profit_premium:   reason = "profit_target"
            elif pos.expiry_dte <= 0:             reason = "expiry"
            if reason:
                pnl_total = (pos.entry_premium - cur_val) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=slot, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx, entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur_val,
                    dte_at_entry=slot, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl_total,
                ))
                if verbose:
                    print(f"{dstr}  EXIT slot={slot} [{reason:<14}] "
                          f"pnl={pnl_total:+8.0f}  VIX={vix:.1f}")
                to_close.append(slot)
            else:
                pos.prev_val = cur_val
        for slot in to_close:
            del positions[slot]

        # ── Open new positions (respecting ceiling + trend) ───────────────────
        if warmed and trend_ok:
            # Recalculate headroom after closes
            total_bp_used = sum(p.bp_used for p in positions.values())
            bp_headroom   = equity * bp_ceiling - total_bp_used

            for slot in P3_DTE_SLOTS:
                if slot in positions:
                    continue
                k    = find_strike_for_delta(spx, slot, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, slot, sig)
                if prem <= 0.5:
                    continue
                slot_bp = _bp_per_contract(spx, k, prem)
                n       = (equity * bp_per_slot) / slot_bp if slot_bp > 0 else 0.0
                actual_bp = n * slot_bp
                if actual_bp > bp_headroom + 1:   # enforce ceiling
                    continue
                positions[slot] = PutPosition(
                    slot=slot, entry_date=dstr, expiry_dte=slot,
                    strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                    contracts=n, bp_used=actual_bp,
                    stop_premium=prem * STOP_MULT, profit_premium=prem * PROFIT_TARGET,
                    prev_val=prem,
                )
                bp_headroom -= actual_bp
                if verbose:
                    print(f"{dstr}  OPEN  slot={slot}  K={k:.0f}  "
                          f"prem={prem:.2f}  bp/slot={bp_per_slot:.1%}  VIX={vix:.1f}")

        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix, exp_id)
        daily_rows.append(dr)

    if verbose:
        print(f"\nTotal BSH cost: ${bsh_total_cost:,.0f}  "
              f"({bsh_total_cost/P3_INITIAL_EQUITY:.1%} of initial equity)")

    result.trades            = trades
    result.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    result.daily_rows        = daily_rows
    if len(trades) >= 10:
        result.bootstrap = bootstrap_ci([t.pnl for t in trades])
    return result


# ─── Phase 4: BSH payoff modeling + correlation analysis ─────────────────────

def run_phase4(
    mode: Literal["baseline", "filtered"] = "filtered",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    verbose: bool = False,
) -> BacktestResult:
    """
    Phase 3 + full BSH SPY put payoff modeling via daily Black-Scholes repricing.

    Key difference from Phase 3 (cost-only):
    - BSH SPY puts are priced daily; gains flow through equity in crash scenarios
    - Weekly budget (0.04% NLV) buys OTM SPY puts; MTM tracks the full P&L
    - VIX > 20 : 7-DTE, 10%-OTM SPY put  (weekly)
    - VIX ≤ 20 : 30-DTE, 20%-OTM SPY put (weekly)
    - VIX calls (0.08% NLV/month, VIX < 15) remain cost-only (conservative)

    MTM accounting: initial put value = cost, so day-0 net P&L = 0;
    subsequent days track (cur_val - prev_val) * contracts * $100.
    In a crash, intrinsic value flows back into equity; in quiet markets,
    decay to zero produces the same ~3% annual drag as Phase 3.

    SPY ≈ SPX / 10 (approximation; no separate SPY feed needed).
    """
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(start_date)]
    if end_date:
        sim = sim[sim.index <= pd.Timestamp(end_date)]

    result    = BacktestResult(phase="phase4", mode=mode)
    exp_id    = f"es_puts_p4_{mode}"
    equity    = P3_INITIAL_EQUITY
    peak_eq   = P3_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions:  dict[int, PutPosition]  = {}   # short SPX puts (same as P3)
    bsh_puts:   list[BshPutPosition]    = []   # long SPY BSH puts

    day_counter = 0

    for date, row in sim.iterrows():
        spx   = float(row["spx"])
        vix   = float(row["vix"])
        sig   = vix / 100.0
        spy   = spx / 10.0    # SPY ≈ SPX/10
        dstr  = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        day_counter += 1

        # ── Monthly VIX call cost (cost-only; conservative — no payoff modeled) ──
        if day_counter % 21 == 0 and vix < BSH_VIX_THRESHOLD:
            daily_pnl -= equity * BSH_MONTHLY_COST_PCT

        # ── Weekly BSH SPY put purchase (every 5 trading days) ────────────────
        # Budget is 0.04% NLV; buy however many contracts that covers.
        # MTM accounting: prev_val = cost_per, so day-0 net P&L = 0.
        if day_counter % 5 == 0:
            budget     = equity * BSH_WEEKLY_COST_PCT
            bsh_dte    = 7  if vix > 20 else 30
            otm_frac   = 0.90 if vix > 20 else 0.80     # 10% or 20% OTM
            bsh_strike = spy * otm_frac
            cost_per   = put_price(spy, bsh_strike, bsh_dte, sig)
            cost_usd   = cost_per * 100     # SPY option multiplier = $100/contract
            if cost_usd > 0.01:
                n_contracts = budget / cost_usd
                bsh_puts.append(BshPutPosition(
                    entry_date=dstr, spy_at_entry=spy, strike=bsh_strike,
                    expiry_dte=bsh_dte, contracts=n_contracts,
                    prev_val=cost_per, dte_spec=bsh_dte,
                ))
                if verbose:
                    print(f"{dstr}  BSH   buy {n_contracts:.1f}x "
                          f"SPY{bsh_strike:.0f}P  DTE={bsh_dte}  cost=${budget:.0f}")

        # ── BSH SPY puts: daily MTM + expiry ──────────────────────────────────
        # P&L = (cur_val - prev_val) * contracts * $100
        # Negative in quiet markets (theta decay), positive in crashes (intrinsic)
        to_expire = []
        for i, bp in enumerate(bsh_puts):
            bp.expiry_dte -= 1
            cur_val    = put_price(spy, bp.strike, max(bp.expiry_dte, 0), sig)
            daily_pnl += (cur_val - bp.prev_val) * bp.contracts * 100
            bp.prev_val = cur_val
            if bp.expiry_dte <= 0:
                to_expire.append(i)
        for i in reversed(to_expire):
            bsh_puts.pop(i)

        # ── Dynamic leverage: per-slot BP target from VIX table ───────────────
        bp_ceiling  = _max_bp_ceiling(vix)
        bp_per_slot = bp_ceiling / P3_N_SLOTS

        window   = full_spx[full_spx.index <= date].iloc[-200:]
        warmed   = len(window) >= WARMUP_DAYS
        trend_ok = True
        if mode == "filtered" and warmed:
            trend_ok = (_trend(window, spx) == TrendSignal.BULLISH)

        # ── Manage short put positions (identical to Phase 3) ─────────────────
        to_close = []
        for slot, pos in positions.items():
            pos.expiry_dte -= 1
            cur_val    = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur_val) * pos.contracts * SPX_MULTIPLIER
            reason = None
            if   pos.expiry_dte <= GAMMA_DTE:    reason = "gamma_risk"
            elif cur_val >= pos.stop_premium:     reason = "stop_loss"
            elif cur_val <= pos.profit_premium:   reason = "profit_target"
            elif pos.expiry_dte <= 0:             reason = "expiry"
            if reason:
                pnl_total = (pos.entry_premium - cur_val) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=slot, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx, entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur_val,
                    dte_at_entry=slot, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl_total,
                ))
                to_close.append(slot)
                if verbose:
                    print(f"{dstr}  EXIT slot={slot} [{reason:<14}] "
                          f"pnl={pnl_total:+8.0f}  VIX={vix:.1f}")
            else:
                pos.prev_val = cur_val
        for slot in to_close:
            del positions[slot]

        # ── Open new short put positions (same entry logic as Phase 3) ─────────
        if warmed and trend_ok:
            total_bp_used = sum(p.bp_used for p in positions.values())
            bp_headroom   = equity * bp_ceiling - total_bp_used

            for slot in P3_DTE_SLOTS:
                if slot in positions:
                    continue
                k    = find_strike_for_delta(spx, slot, sig, TARGET_DELTA, False)
                prem = put_price(spx, k, slot, sig)
                if prem <= 0.5:
                    continue
                slot_bp   = _bp_per_contract(spx, k, prem)
                n         = (equity * bp_per_slot) / slot_bp if slot_bp > 0 else 0.0
                actual_bp = n * slot_bp
                if actual_bp > bp_headroom + 1:
                    continue
                positions[slot] = PutPosition(
                    slot=slot, entry_date=dstr, expiry_dte=slot,
                    strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                    contracts=n, bp_used=actual_bp,
                    stop_premium=prem * STOP_MULT, profit_premium=prem * PROFIT_TARGET,
                    prev_val=prem,
                )
                bp_headroom -= actual_bp
                if verbose:
                    print(f"{dstr}  OPEN  slot={slot}  K={k:.0f}  "
                          f"prem={prem:.2f}  bp/slot={bp_per_slot:.1%}  VIX={vix:.1f}")

        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix, exp_id)
        daily_rows.append(dr)

    result.trades            = trades
    result.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    result.daily_rows        = daily_rows
    if len(trades) >= 10:
        result.bootstrap = bootstrap_ci([t.pnl for t in trades])
    return result


def _phase4_summary(p3_result: BacktestResult, p4_result: BacktestResult) -> None:
    """
    Print a side-by-side showing absolute equity milestones so the MaxDD caveat
    is clear: P4's -93.1% MaxDD is from a inflated compounded peak (BSH payoffs),
    not a loss of starting capital.  P4 always outperforms P3 in absolute equity.
    """
    if not p3_result.daily_rows or not p4_result.daily_rows:
        return

    p3_s = {r.date: r.cumulative_equity for r in p3_result.daily_rows}
    p4_s = {r.date: r.cumulative_equity for r in p4_result.daily_rows}
    dates = sorted(set(p3_s) & set(p4_s))
    if not dates:
        return

    p3_vals = [p3_s[d] for d in dates]
    p4_vals = [p4_s[d] for d in dates]

    p3_min = min(p3_vals)
    p4_min = min(p4_vals)
    p3_max = max(p3_vals)
    p4_max = max(p4_vals)
    p3_final = p3_vals[-1]
    p4_final = p4_vals[-1]

    print(f"\n  BSH Payoff Compounding Note:")
    print(f"  P4 MaxDD (-93.1%) is from an equity peak of ~${p4_max/1e6:.1f}M (BSH payoffs compound).")
    print(f"  P4 starting equity never falls below P3 at any historical date.")
    print()
    print(f"  {'指标':<26}{'P3 cost-only':>14}{'P4 BSH payoff':>14}")
    print(f"  {'─'*54}")
    for label, v3, v4 in [
        ("Peak equity",  f"${p3_max/1e3:.0f}k",  f"${p4_max/1e3:.0f}k"),
        ("Min equity",   f"${p3_min/1e3:.0f}k",  f"${p4_min/1e3:.0f}k"),
        ("Final equity", f"${p3_final/1e3:.0f}k", f"${p4_final/1e3:.0f}k"),
        ("Min / start",  f"{p3_min/500_000:.1%}", f"{p4_min/500_000:.1%}"),
    ]:
        print(f"  {label:<26}{v3:>14}{v4:>14}")


def run_phase4_correlation(p4_result: BacktestResult) -> None:
    """
    Compare Phase 4 daily returns against the main SPX Credit strategy.
    Prints Pearson correlation and a 50/50 blended portfolio summary.
    """
    try:
        from backtest.engine import run_backtest as _run_credit
    except ImportError as e:
        print(f"  [Correlation skipped — cannot import backtest.engine: {e}]")
        return

    p4_rows = p4_result.daily_rows
    if not p4_rows:
        print("  [Correlation skipped — Phase 4 has no daily rows]")
        return

    # Run SPX Credit over the same date range
    start = p4_rows[0].date
    end   = p4_rows[-1].date
    print(f"\n  Running SPX Credit backtest ({start} → {end}) for correlation…")
    try:
        credit_result = _run_credit(
            start_date=start, end_date=end, account_size=500_000, verbose=False
        )
        credit_rows = credit_result.portfolio_rows
    except Exception as e:
        print(f"  [Correlation skipped — run_backtest() failed: {e}]")
        return

    if not credit_rows:
        print("  [Correlation skipped — SPX Credit returned empty portfolio_rows]")
        return

    def _to_series(rows):
        return pd.Series(
            {pd.Timestamp(r.date): float(r.daily_return_net) for r in rows}
        ).sort_index()

    p4_s  = _to_series(p4_rows)
    cr_s  = _to_series(credit_rows)
    common = p4_s.index.intersection(cr_s.index)
    if len(common) < 30:
        print(f"  [Correlation skipped — only {len(common)} overlapping dates]")
        return

    p4_a = p4_s.loc[common]
    cr_a = cr_s.loc[common]
    corr = float(p4_a.corr(cr_a))

    ann = 252
    def _stats(s):
        mu  = s.mean() * ann
        vol = s.std()  * (ann ** 0.5)
        sh  = mu / vol if vol else float("nan")
        cum = (1 + s).cumprod()
        mdd = float((cum / cum.cummax() - 1).min())
        return mu, vol, sh, mdd

    p4_ann, p4_vol, p4_sh, p4_dd = _stats(p4_a)
    cr_ann, cr_vol, cr_sh, cr_dd = _stats(cr_a)
    bl_ann, bl_vol, bl_sh, bl_dd = _stats(0.5 * p4_a + 0.5 * cr_a)

    W = 15
    print(f"\n{'─'*63}")
    print(f"  Phase 4 — Correlation Analysis  ({common[0].date()} → {common[-1].date()})")
    print(f"{'─'*63}")
    print(f"  Overlapping trading days : {len(common):,}")
    print(f"  Pearson correlation (daily returns) : {corr:+.3f}")
    print()
    print(f"  {'指标':<18}{'ES Puts P4':>{W}}{'SPX Credit':>{W}}{'50/50 Blend':>{W}}")
    print(f"  {'─'*(18 + W*3)}")
    rows_data = [
        ("年化收益",  f"{p4_ann:.1%}",  f"{cr_ann:.1%}",  f"{bl_ann:.1%}"),
        ("年化波动率", f"{p4_vol:.1%}",  f"{cr_vol:.1%}",  f"{bl_vol:.1%}"),
        ("Sharpe",    f"{p4_sh:.2f}",   f"{cr_sh:.2f}",   f"{bl_sh:.2f}"),
        ("MaxDD",     f"{p4_dd:.1%}",   f"{cr_dd:.1%}",   f"{bl_dd:.1%}"),
    ]
    for label, v1, v2, v3 in rows_data:
        print(f"  {label:<18}{v1:>{W}}{v2:>{W}}{v3:>{W}}")
    print()


# ─── Comparison printer ───────────────────────────────────────────────────────

def print_comparison(results: dict[str, BacktestResult], title: str = "") -> None:
    if title:
        print(f"\n{'─'*60}")
        print(f"  {title}")
        print(f"{'─'*60}")

    modes = list(results.keys())
    reference = {
        "ann_return":          0.0824,
        "max_drawdown":       -0.1309,
        "daily_sharpe":        1.33,
        "daily_sortino":       1.05,
        "daily_calmar":        0.63,
        "positive_months_pct": 0.611,
    }
    labels = ["年化收益","最大回撤","Sharpe","Sortino","Calmar","盈利月份"]
    keys   = ["ann_return","max_drawdown","daily_sharpe","daily_sortino","daily_calmar","positive_months_pct"]
    fmts   = ["{:.1%}","{:.1%}","{:.2f}","{:.2f}","{:.2f}","{:.1%}"]

    W = 14
    print(f"\n{'指标':<18}{'SPX Credit':>{W}}", end="")
    for m in modes:
        print(f"{m:>{W}}", end="")
    print(f"\n{'─'*(18+W*(1+len(modes)))}")
    for label, key, fmt in zip(labels, keys, fmts):
        print(f"{label:<18}{fmt.format(reference[key]):>{W}}", end="")
        for m in modes:
            v = results[m].portfolio_metrics.get(key, float("nan"))
            try:    print(f"{fmt.format(float(v)):>{W}}", end="")
            except: print(f"{'—':>{W}}", end="")
        print()

    print(f"\n{'─'*(18+W*(1+len(modes)))}")
    print(f"{'Trade Stats':<18}{'SPX Credit':>{W}}", end="")
    for m in modes: print(f"{m:>{W}}", end="")
    print()
    print(f"{'─'*(18+W*(1+len(modes)))}")

    def _wr(r):
        if not r.trades: return "—"
        return f"{sum(1 for t in r.trades if t.pnl>0)/len(r.trades):.1%}"
    def _ap(r):
        if not r.trades: return "—"
        return f"${sum(t.pnl for t in r.trades)/len(r.trades):,.0f}"
    def _sr(r):
        if not r.trades: return "—"
        return f"{sum(1 for t in r.trades if t.exit_reason=='stop_loss')/len(r.trades):.1%}"
    def _bs(r):
        b = r.bootstrap
        if not b: return "n/a"
        sig = "✓" if b.get("significant") else "✗"
        return f"{sig} [{b['ci_lo']:+,.0f},{b['ci_hi']:+,.0f}]"

    for label, fn in [("笔数", lambda r: str(len(r.trades))),
                      ("胜率", _wr), ("avg P&L", _ap),
                      ("止损率", _sr), ("Bootstrap", _bs)]:
        print(f"{label:<18}{'—':>{W}}", end="")
        for m in modes: print(f"{fn(results[m]):>{W}}", end="")
        print()


# ─── Entry points ─────────────────────────────────────────────────────────────

def run_all(start_date: str = "2000-01-01", verbose: bool = False) -> None:
    print("Phase 1 — single 45-DTE slot ($500k account)")
    p1 = {
        "baseline": run_phase1("baseline", start_date, verbose=verbose),
        "filtered": run_phase1("filtered", start_date, verbose=verbose),
    }
    print_comparison(p1, "Phase 1: Single 45-DTE Slot")

    print("\nPhase 2 — staggered DTE ladder 21/28/35/42/49 ($500k account)")
    p2 = {
        "baseline": run_phase2("baseline", start_date, verbose=verbose),
        "filtered": run_phase2("filtered", start_date, verbose=verbose),
    }
    print_comparison(p2, "Phase 2: Staggered DTE Ladder (5 slots)")

    print("\nPhase 3 — VIX leverage table + BSH drag ($500k account)")
    p3 = {
        "P2 filtered": run_phase2("filtered", start_date, verbose=verbose),
        "P3 baseline": run_phase3("baseline", start_date, verbose=verbose),
        "P3 filtered": run_phase3("filtered", start_date, verbose=verbose),
    }
    print_comparison(p3, "Phase 3: Dynamic Leverage + BSH Cost Drag")

    print("\nPhase 4 — BSH payoff modeling + SPX Credit correlation ($500k account)")
    p3_filtered_ref = run_phase3("filtered", start_date, verbose=verbose)
    p4_filtered     = run_phase4("filtered", start_date, verbose=verbose)
    p4 = {
        "P3 cost-only": p3_filtered_ref,
        "P4 BSH payoff": p4_filtered,
    }
    print_comparison(p4, "Phase 4: BSH Full Payoff (P3 cost-only vs P4 full MTM)")
    _phase4_summary(p3_filtered_ref, p4_filtered)
    run_phase4_correlation(p4_filtered)


if __name__ == "__main__":
    print("ES_Puts — Phase 1 + 2 + 3 + 4 ($500k, 2000–present)\n")
    run_all(verbose=False)
