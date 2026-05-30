"""Reconcile SPX position daily PnL via BS reverse-solve greek attribution.

One-shot diagnostic. Validates path A (compute greeks ourselves) before
wiring it into a production pipeline. Path B (broker chain greeks) takes
over for live positions going forward.

For each open SPX put credit spread:
  1. Load mark per leg per day from data/q041_massive_snapshot/{date}/SPX.parquet
  2. Pull SPX underlying close per day from data/q042_spx_history_cache.json
  3. Reverse-solve IV per leg per day from mark via BS (brentq)
  4. Compute BS greeks at solved IV
  5. Decompose day-to-day mark change into Δ·ΔS, 0.5·Γ·ΔS², Θ·Δt, V·ΔIV
  6. Print per-day table with residual

Assumptions:
  - SPX is European, cash-settled
  - r = 0.05 (1-yr T-bill ~)
  - q = 0.013 (SPX div yield ~)
  - Δt is calendar days / 365 (covers weekend decay)
  - Mark = day_close column (most stable across snapshot timings)
  - Default to SPXW ticker (PM trades weeklies, expiry 6-18 is Thursday)
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

DATA_DIR = "data"
SNAPSHOT_DIR = f"{DATA_DIR}/q041_massive_snapshot"
DAILY_SNAPSHOT = f"{DATA_DIR}/daily_snapshot.jsonl"
SPX_HIST = f"{DATA_DIR}/q042_spx_history_cache.json"

R = 0.05       # risk-free rate (1-yr T-bill ~5%)
Q = 0.013      # SPX dividend yield
DAYS_PER_YEAR = 365.0


@dataclass
class Position:
    trade_id: str
    account: str
    short_strike: float
    long_strike: float
    contracts: int
    expiry: date
    opened_at: date


def load_positions() -> list[Position]:
    """Pull positions from latest daily_snapshot row."""
    with open(DAILY_SNAPSHOT) as f:
        lines = [json.loads(l) for l in f if l.strip()]
    latest = lines[-1]
    out = []
    for p in latest["strategies"]["spx_spread"]["positions"]:
        out.append(Position(
            trade_id=p["trade_id"],
            account=p["account"],
            short_strike=float(p["short_strike"]),
            long_strike=float(p["long_strike"]),
            contracts=int(p["contracts"]),
            expiry=date.fromisoformat(p["expiry"]),
            opened_at=date.fromisoformat(p["opened_at"]),
        ))
    return out


def load_spx_history() -> dict[str, float]:
    """Date ISO → SPX close. Primary: q042 cache. Fallback for recent days:
    daily_snapshot.jsonl `market.spx`.
    """
    with open(SPX_HIST) as f:
        d = json.load(f)
    hist = d["full"]["payload"]["history"]
    out = {row["date"]: float(row["close"]) for row in hist}
    # Fill recent days from daily_snapshot
    with open(DAILY_SNAPSHOT) as f:
        for line in f:
            r = json.loads(line)
            iso = r.get("date")
            spx = (r.get("market") or {}).get("spx")
            if iso and spx and iso not in out:
                out[iso] = float(spx)
    return out


def trading_days(start: date, end: date) -> list[date]:
    """List trading days inclusive of start..end (Mon-Fri, no holiday filter)."""
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def load_chain_mark(snapshot_date: date, strike: float, expiry: date,
                    prefer: str = "SPXW") -> float | None:
    """Pull put day_close for (strike, expiry) from snapshot parquet.
    Prefer SPXW (weekly) ticker over SPX (monthly) — PM trades weeklies.
    """
    p = f"{SNAPSHOT_DIR}/{snapshot_date.isoformat()}/SPX.parquet"
    if not os.path.exists(p):
        return None
    df = pd.read_parquet(p, columns=["occ_ticker", "strike_price", "contract_type",
                                     "expiration_date", "day_close"])
    m = ((df.contract_type == "put") &
         (df.expiration_date == expiry.isoformat()) &
         (df.strike_price == strike))
    rows = df[m]
    if rows.empty:
        return None
    # Prefer SPXW (occ_ticker contains "SPXW") if both exist
    spxw = rows[rows.occ_ticker.str.contains("SPXW")]
    pick = spxw if not spxw.empty else rows
    mk = pick.day_close.dropna()
    if mk.empty:
        return None
    return float(mk.iloc[0])


def bs_put(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    if sigma <= 0 or T <= 0:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def solve_iv(target: float, S: float, K: float, T: float, r: float, q: float) -> float | None:
    if target <= 0 or T <= 0:
        return None
    # Intrinsic floor — if mark < intrinsic + tiny, return very low IV
    intrinsic = max(K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)
    if target <= intrinsic + 1e-6:
        return 0.01
    try:
        f = lambda s: bs_put(S, K, T, r, q, s) - target
        return brentq(f, 1e-4, 5.0, xtol=1e-5)
    except (ValueError, RuntimeError):
        return None


def bs_greeks_put(S: float, K: float, T: float, r: float, q: float, sigma: float) -> dict:
    """Greeks per-$1, per-year (Theta), per-decimal-vol (Vega)."""
    if sigma <= 0 or T <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta_yr": 0.0, "vega_dec": 0.0}
    sqT = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqT)
    d2 = d1 - sigma * sqT
    delta = -math.exp(-q * T) * norm.cdf(-d1)
    gamma = math.exp(-q * T) * norm.pdf(d1) / (S * sigma * sqT)
    theta_yr = (-S * math.exp(-q * T) * norm.pdf(d1) * sigma / (2 * sqT)
                + r * K * math.exp(-r * T) * norm.cdf(-d2)
                - q * S * math.exp(-q * T) * norm.cdf(-d1))
    vega_dec = S * math.exp(-q * T) * norm.pdf(d1) * sqT
    return {"delta": delta, "gamma": gamma, "theta_yr": theta_yr, "vega_dec": vega_dec}


def reconcile_position(pos: Position, spx_hist: dict[str, float]) -> None:
    print(f"\n{'='*100}")
    print(f"Position: {pos.account}/{pos.trade_id}  short {pos.short_strike:.0f}P  long {pos.long_strike:.0f}P"
          f"  x{pos.contracts}  exp {pos.expiry}  opened {pos.opened_at}")
    print(f"{'='*100}")

    today = max(date.fromisoformat(d) for d in os.listdir(SNAPSHOT_DIR) if d[0].isdigit())
    days = trading_days(pos.opened_at, today)

    # Per day, pull marks + S + DTE + reverse-solve IV + greeks per leg
    daily = []
    for d in days:
        iso = d.isoformat()
        S = spx_hist.get(iso)
        if S is None:
            continue
        ms = load_chain_mark(d, pos.short_strike, pos.expiry)
        ml = load_chain_mark(d, pos.long_strike, pos.expiry)
        if ms is None or ml is None:
            continue
        T = max((pos.expiry - d).days, 1) / DAYS_PER_YEAR
        iv_s = solve_iv(ms, S, pos.short_strike, T, R, Q)
        iv_l = solve_iv(ml, S, pos.long_strike, T, R, Q)
        if iv_s is None or iv_l is None:
            continue
        gs = bs_greeks_put(S, pos.short_strike, T, R, Q, iv_s)
        gl = bs_greeks_put(S, pos.long_strike, T, R, Q, iv_l)
        daily.append({
            "date": d, "S": S, "T": T,
            "ms": ms, "ml": ml,
            "iv_s": iv_s, "iv_l": iv_l,
            "gs": gs, "gl": gl,
        })

    if len(daily) < 2:
        print("  ! insufficient daily snapshots — abort")
        return

    # Pairwise attribution
    mult = 100 * pos.contracts  # SPX multiplier × contracts
    # Convention: short the spread → side_short = -1, side_long = +1 (we own the long put)
    print(f"  {'date':<12} {'S':>8} {'iv_s':>6} {'iv_l':>6} "
          f"{'ms':>6} {'ml':>6} "
          f"{'ΔPnL':>9} {'Δattr':>8} {'Γattr':>8} {'Θattr':>8} {'Vattr':>8} {'Resid':>8} {'Resid%':>7}")
    cum = {"actual": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "resid": 0.0}
    for i in range(1, len(daily)):
        t0, t1 = daily[i-1], daily[i]
        dS  = t1["S"] - t0["S"]
        # theta_yr is ∂V/∂(calendar time), per year. Use calendar Δt (positive).
        dt_yr = (t1["date"] - t0["date"]).days / DAYS_PER_YEAR
        dIV_s = t1["iv_s"] - t0["iv_s"]
        dIV_l = t1["iv_l"] - t0["iv_l"]

        # Spread-level greeks at t0 (we attribute forward using t0 greeks)
        # Short put: side = -1; Long put: side = +1
        # Net spread = -short + long
        # Daily PnL attribution per greek, in dollars
        delta_attr = mult * ((-1) * t0["gs"]["delta"] * dS + 1 * t0["gl"]["delta"] * dS)
        gamma_attr = mult * 0.5 * ((-1) * t0["gs"]["gamma"] * dS * dS + 1 * t0["gl"]["gamma"] * dS * dS)
        theta_attr = mult * ((-1) * t0["gs"]["theta_yr"] * dt_yr + 1 * t0["gl"]["theta_yr"] * dt_yr)
        vega_attr  = mult * ((-1) * t0["gs"]["vega_dec"] * dIV_s + 1 * t0["gl"]["vega_dec"] * dIV_l)

        # Actual PnL for spread holder (short the spread): -Δms + Δml
        actual = mult * ((-1) * (t1["ms"] - t0["ms"]) + 1 * (t1["ml"] - t0["ml"]))

        attributed = delta_attr + gamma_attr + theta_attr + vega_attr
        resid = actual - attributed
        resid_pct = (resid / actual * 100.0) if abs(actual) > 1.0 else 0.0

        cum["actual"] += actual; cum["delta"] += delta_attr; cum["gamma"] += gamma_attr
        cum["theta"] += theta_attr; cum["vega"] += vega_attr; cum["resid"] += resid

        print(f"  {t1['date'].isoformat():<12} {t1['S']:>8.1f} "
              f"{t1['iv_s']*100:>6.2f} {t1['iv_l']*100:>6.2f} "
              f"{t1['ms']:>6.1f} {t1['ml']:>6.1f} "
              f"{actual:>9.0f} {delta_attr:>8.0f} {gamma_attr:>8.0f} "
              f"{theta_attr:>8.0f} {vega_attr:>8.0f} "
              f"{resid:>8.0f} {resid_pct:>6.1f}%")

    print(f"  {'CUM':<12} {'':>8} {'':>6} {'':>6} {'':>6} {'':>6} "
          f"{cum['actual']:>9.0f} {cum['delta']:>8.0f} {cum['gamma']:>8.0f} "
          f"{cum['theta']:>8.0f} {cum['vega']:>8.0f} "
          f"{cum['resid']:>8.0f} "
          f"{cum['resid']/cum['actual']*100 if abs(cum['actual'])>1 else 0:>6.1f}%")


def main() -> int:
    positions = load_positions()
    spx_hist = load_spx_history()
    print(f"Loaded {len(positions)} positions, SPX history covers {len(spx_hist)} days")
    for pos in positions:
        reconcile_position(pos, spx_hist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
