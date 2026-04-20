"""
Q018 Phase 1b — Ex-post cluster replay (replace $1,023 approximation).

Takes each blocked aftermath cluster found by q018_phase1_multi_slot.py
and SIMULATES what a real second-slot IC_HV entry would have realized,
using the same leg construction, pricing, and exit rules as the backtest
engine.

Method:
  1. Load SPX / VIX daily market data (same source as engine).
  2. For each blocked cluster, pick the cluster's first day as entry.
  3. Build IC_HV legs via engine._build_legs(spx, sigma=vix/100).
  4. Walk forward day-by-day using engine._current_value,
     apply the same exit rules:
       - 50% profit target after min_hold_days (10)
       - credit stop at -2× (stop_mult)
       - 21 DTE roll
       - end of data = cap at last available day
  5. Convert $pnl per contract to $ realized via account_size / bp_per_contract,
     then * 100 multiplier (same as engine._close_position).

Caveats (still approximations):
  - No BP ceiling check (we pretend the second slot has BP room).
  - No shock-engine / overlay interaction.
  - No regime-change re-routing mid-trade (engine doesn't either).
  - Uses DEFAULT_PARAMS profit_target / stop_mult / min_hold_days.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q018_phase1_cluster_replay
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

import strategy.selector as sel
from backtest.engine import (
    run_backtest,
    _build_legs,
    _entry_value,
    _current_value,
    _short_leg,
    _compute_bp,
)
from strategy.selector import StrategyName, DEFAULT_PARAMS
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history

from backtest.prototype.q018_phase1_multi_slot import (
    _find_blocked_clusters,
    _closed,
    DISASTER_WINDOWS,
    BlockedCluster,
)

START = "2000-01-01"
ACCOUNT_SIZE = 150_000.0  # engine default


# ──────────────────────────────────────────────────────────────────
# Load market data once
# ──────────────────────────────────────────────────────────────────

def _load_market_df() -> pd.DataFrame:
    vix_df = fetch_vix_history(period="max")
    spx_df = fetch_spx_history(period="max")
    vix_df.index = pd.to_datetime(vix_df.index.date)
    spx_df.index = pd.to_datetime(spx_df.index.date)
    df = pd.DataFrame({"vix": vix_df["vix"], "spx": spx_df["close"]}).dropna()
    return df


# ──────────────────────────────────────────────────────────────────
# Single-position ex-post simulator
# ──────────────────────────────────────────────────────────────────

@dataclass
class SimResult:
    entry_date: str
    exit_date: str
    entry_spx: float
    entry_vix: float
    exit_spx: float
    exit_vix: float
    days_held: int
    exit_reason: str
    pnl_per_contract: float
    contracts: float
    pnl_usd: float
    disaster: str | None


def _simulate_ic_hv(
    entry_date: pd.Timestamp,
    df: pd.DataFrame,
    *,
    disaster: str | None,
    params=DEFAULT_PARAMS,
) -> SimResult | None:
    if entry_date not in df.index:
        # Snap to next available trading day
        later = df.index[df.index >= entry_date]
        if len(later) == 0:
            return None
        entry_date = later[0]

    entry_spx = float(df.loc[entry_date, "spx"])
    entry_vix = float(df.loc[entry_date, "vix"])
    sigma = entry_vix / 100.0

    legs, _short_dte = _build_legs(StrategyName.IRON_CONDOR_HV, entry_spx, sigma, params)
    if not legs:
        return None
    ev = _entry_value(legs, entry_spx, sigma)
    sw, bp_per_c = _compute_bp(StrategyName.IRON_CONDOR_HV, legs, ev)
    short_dte = _short_leg(legs)[3]
    is_credit = ev < 0

    # Determine contract count the engine would use for this position.
    # HIGH_VOL → bp_target = params.bp_target_for_regime(HIGH_VOL) × high_vol_size
    # But _position_contracts uses position.bp_target directly (which in engine
    # is bp_target_for_regime(regime)). Use that:
    from signals.vix_regime import Regime
    bp_target = params.bp_target_for_regime(Regime.HIGH_VOL)
    contracts = ACCOUNT_SIZE * bp_target / bp_per_c if bp_per_c > 0 else 0.0

    # Walk forward
    future_dates = df.index[df.index > entry_date]
    days_held = 0
    exit_reason = "end_of_data"
    exit_date = entry_date
    exit_spx = entry_spx
    exit_vix = entry_vix
    pnl = 0.0

    for d in future_dates:
        days_held += 1
        spx = float(df.loc[d, "spx"])
        vix_now = float(df.loc[d, "vix"])
        sigma_now = vix_now / 100.0
        cur_val = _current_value(legs, spx, sigma_now, days_held)
        pnl = cur_val - ev

        short_dte_now = max(short_dte - days_held, 0)

        # Exit rules (mirror engine.py:830-840)
        exit_candidate = None
        if abs(ev) > 0:
            pnl_ratio = pnl / abs(ev)
            if pnl_ratio >= params.profit_target and days_held >= params.min_hold_days:
                exit_candidate = "50pct_profit"
            elif is_credit and pnl_ratio <= -params.stop_mult:
                exit_candidate = "stop_loss"
            elif not is_credit and pnl_ratio <= -0.50:
                exit_candidate = "stop_loss"
        if short_dte_now <= 21 and exit_candidate is None:
            exit_candidate = "roll_21dte"

        if exit_candidate:
            exit_reason = exit_candidate
            exit_date = d
            exit_spx = spx
            exit_vix = vix_now
            break
    else:
        if len(future_dates) > 0:
            exit_date = future_dates[-1]
            exit_spx = float(df.loc[exit_date, "spx"])
            exit_vix = float(df.loc[exit_date, "vix"])

    pnl_usd = pnl * contracts * 100
    return SimResult(
        entry_date=str(entry_date.date()),
        exit_date=str(exit_date.date()),
        entry_spx=round(entry_spx, 2),
        entry_vix=round(entry_vix, 2),
        exit_spx=round(exit_spx, 2),
        exit_vix=round(exit_vix, 2),
        days_held=days_held,
        exit_reason=exit_reason,
        pnl_per_contract=round(pnl, 2),
        contracts=round(contracts, 2),
        pnl_usd=round(pnl_usd, 0),
        disaster=disaster,
    )


# ──────────────────────────────────────────────────────────────────
# Report helpers
# ──────────────────────────────────────────────────────────────────

def _fmt_sim(s: SimResult) -> str:
    tag = f"[{s.disaster}]" if s.disaster else ""
    return (f"  {s.entry_date} → {s.exit_date}  "
            f"SPX {s.entry_spx:>7.1f}→{s.exit_spx:>7.1f}  "
            f"VIX {s.entry_vix:>5.1f}→{s.exit_vix:>5.1f}  "
            f"days={s.days_held:>3}  "
            f"pnl=${s.pnl_usd:>+9,.0f}  "
            f"({s.exit_reason})  {tag}")


def run_study() -> None:
    print("Q018 Phase 1b — Disaster-cluster replay")
    print()
    print("  Loading market data ...")
    df = _load_market_df()
    print(f"  market rows: {len(df)}  ({df.index[0].date()} → {df.index[-1].date()})")

    print()
    print("  Re-running baseline to recover blocked clusters ...")
    bt = run_backtest(start_date=START, verbose=False)
    base_closed = _closed(bt.trades)
    ic_hv_base = [t for t in base_closed if t.strategy.value == StrategyName.IRON_CONDOR_HV.value]
    clusters, _ = _find_blocked_clusters(bt.signals, ic_hv_base)
    print(f"  total clusters: {len(clusters)}, disaster clusters: "
          f"{sum(1 for c in clusters if c.disaster)}")

    # ── Disaster clusters first ──────────────────────────────────────
    print()
    print("=" * 100)
    print("  DISASTER-WINDOW CLUSTERS — actual simulated PnL for hypothetical 2nd slot entry")
    print("=" * 100)
    disaster_sims: list[SimResult] = []
    for c in clusters:
        if not c.disaster:
            continue
        entry = pd.Timestamp(c.first_day)
        res = _simulate_ic_hv(entry, df, disaster=c.disaster)
        if res:
            disaster_sims.append(res)
            print(_fmt_sim(res))

    total_disaster = sum(s.pnl_usd for s in disaster_sims)
    print()
    print(f"  Disaster cluster realized PnL: ${total_disaster:+,.0f}  ({len(disaster_sims)} trades)")
    wins_d = sum(1 for s in disaster_sims if s.pnl_usd > 0)
    print(f"  Win rate: {wins_d}/{len(disaster_sims)} = {wins_d/max(len(disaster_sims),1)*100:.0f}%")

    # ── All clusters ─────────────────────────────────────────────────
    print()
    print("=" * 100)
    print("  ALL CLUSTERS — realized PnL for every blocked cluster (upper-bound was $36,828)")
    print("=" * 100)
    all_sims: list[SimResult] = []
    for c in clusters:
        entry = pd.Timestamp(c.first_day)
        res = _simulate_ic_hv(entry, df, disaster=c.disaster)
        if res:
            all_sims.append(res)
            print(_fmt_sim(res))

    total_all = sum(s.pnl_usd for s in all_sims)
    wins = sum(1 for s in all_sims if s.pnl_usd > 0)
    losses = sum(s.pnl_usd for s in all_sims if s.pnl_usd < 0)
    profits = sum(s.pnl_usd for s in all_sims if s.pnl_usd > 0)
    print()
    print(f"  Total: {len(all_sims)} simulated second-slot entries")
    print(f"  Win rate: {wins}/{len(all_sims)} = {wins/max(len(all_sims),1)*100:.1f}%")
    print(f"  Profits sum: ${profits:+,.0f}")
    print(f"  Losses sum:  ${losses:+,.0f}")
    print(f"  NET PnL:     ${total_all:+,.0f}")
    print(f"  vs upper-bound approx ($36,828): "
          f"{'beats' if total_all > 36_828 else 'below'} by ${abs(total_all - 36_828):,.0f}")

    # ── Disaster vs non-disaster breakdown ───────────────────────────
    non_disaster_sims = [s for s in all_sims if not s.disaster]
    total_non = sum(s.pnl_usd for s in non_disaster_sims)
    print()
    print("  Breakdown:")
    print(f"    Non-disaster clusters: {len(non_disaster_sims):>3}  net ${total_non:+,.0f}")
    print(f"    Disaster  clusters:    {len(disaster_sims):>3}  net ${total_disaster:+,.0f}")


if __name__ == "__main__":
    run_study()
