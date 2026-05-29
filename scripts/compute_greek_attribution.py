"""Compute daily greek-decomposed PnL attribution for open SPX positions.

Path A (BS reverse-solve) — used for historical backfill until path B
(broker chain greeks captured at snapshot time) is wired in.

Reads:
  data/daily_snapshot.jsonl       (latest row → open SPX positions)
  data/q041_massive_snapshot/{d}/SPX.parquet  (per-leg day_close per day)
  data/q042_spx_history_cache.json (SPX close per day; primary)
  + daily_snapshot.market.spx (recent fallback)

Writes:
  data/strategy_pnl_attribution.jsonl  (append-only, idempotent on
                                        (date, trade_id))

Per trading-day pair (t0, t1) per position, decomposes:
  ΔPnL_actual = Δ·ΔS + 0.5·Γ·ΔS² + Θ·Δt + V·ΔIV + Residual

Spread side convention: short put → side=-1; long put → side=+1.
Theta is per-year, ∂V/∂(calendar time), negative for long ATM options.
Vega is per-decimal-vol-unit.
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
SNAPSHOT_DIR = DATA / "q041_massive_snapshot"
DAILY_SNAPSHOT = DATA / "daily_snapshot.jsonl"
CLOSED_TRADES = DATA / "closed_trades.jsonl"
SPX_HIST = DATA / "q042_spx_history_cache.json"
OUT_PATH = DATA / "strategy_pnl_attribution.jsonl"

R = 0.05            # 1-yr T-bill ~
Q = 0.013           # SPX dividend yield ~
DAYS_PER_YEAR = 365.0
COMPUTE_METHOD = "bs_reverse_solve_v1"


# ── data loaders ─────────────────────────────────────────────────────────────

@dataclass
class Position:
    trade_id: str
    account: str
    strategy: str
    short_strike: float
    long_strike: float
    contracts: int
    expiry: date
    opened_at: date
    closed_at: Optional[date] = None         # None when still open
    entry_short_fill: Optional[float] = None # broker fill at open (overrides chain day_close)
    entry_long_fill: Optional[float] = None
    exit_short_fill: Optional[float] = None  # broker fill at close
    exit_long_fill: Optional[float] = None
    realized_pnl: Optional[float] = None     # broker-reported, for chart reconciliation


def load_open_positions() -> list[Position]:
    """Pull currently-open SPX positions from latest daily_snapshot row."""
    with open(DAILY_SNAPSHOT) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows:
        return []
    latest = rows[-1]
    positions = []
    for p in (latest.get("strategies", {}).get("spx_spread", {}).get("positions") or []):
        positions.append(Position(
            trade_id=p["trade_id"],
            account=p["account"],
            strategy="spx_spread",
            short_strike=float(p["short_strike"]),
            long_strike=float(p["long_strike"]),
            contracts=int(p["contracts"]),
            expiry=date.fromisoformat(p["expiry"]),
            opened_at=date.fromisoformat(p["opened_at"]),
        ))
    return positions


def load_closed_trades() -> list[Position]:
    """Pull closed-trade ledger. PM seeds historic trades manually; future
    closes will be appended by strategy/state.py.
    """
    if not CLOSED_TRADES.exists():
        return []
    positions = []
    with open(CLOSED_TRADES) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            positions.append(Position(
                trade_id=r["trade_id"],
                account=r["account"],
                strategy=r["strategy"],
                short_strike=float(r["short_strike"]),
                long_strike=float(r["long_strike"]),
                contracts=int(r["contracts"]),
                expiry=date.fromisoformat(r["expiry"]),
                opened_at=date.fromisoformat(r["opened_at"]),
                closed_at=date.fromisoformat(r["closed_at"]),
                entry_short_fill=float(r.get("entry_short_fill")) if r.get("entry_short_fill") is not None else None,
                entry_long_fill=float(r.get("entry_long_fill")) if r.get("entry_long_fill") is not None else None,
                exit_short_fill=float(r.get("exit_short_fill")) if r.get("exit_short_fill") is not None else None,
                exit_long_fill=float(r.get("exit_long_fill")) if r.get("exit_long_fill") is not None else None,
                realized_pnl=float(r.get("realized_pnl")) if r.get("realized_pnl") is not None else None,
            ))
    return positions


def load_spx_history() -> dict[str, float]:
    """Date ISO → SPX close. Primary q042 cache; recent fallback from daily_snapshot."""
    out: dict[str, float] = {}
    with open(SPX_HIST) as f:
        d = json.load(f)
    for row in d["full"]["payload"]["history"]:
        out[row["date"]] = float(row["close"])
    with open(DAILY_SNAPSHOT) as f:
        for line in f:
            r = json.loads(line)
            iso = r.get("date")
            spx = (r.get("market") or {}).get("spx")
            if iso and spx and iso not in out:
                out[iso] = float(spx)
    return out


def trading_days(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def load_chain_mark(snapshot_date: date, strike: float, expiry: date) -> Optional[float]:
    """Per-leg day_close from q041 SPX parquet. Prefer SPXW (PM trades weeklies)."""
    p = SNAPSHOT_DIR / snapshot_date.isoformat() / "SPX.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=["occ_ticker", "strike_price", "contract_type",
                                     "expiration_date", "day_close"])
    m = ((df.contract_type == "put") &
         (df.expiration_date == expiry.isoformat()) &
         (df.strike_price == strike))
    rows = df[m]
    if rows.empty:
        return None
    spxw = rows[rows.occ_ticker.str.contains("SPXW")]
    pick = spxw if not spxw.empty else rows
    mk = pick.day_close.dropna()
    if mk.empty:
        return None
    return float(mk.iloc[0])


# ── BS math ──────────────────────────────────────────────────────────────────

def bs_put(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    if sigma <= 0 or T <= 0:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def solve_iv(target: float, S: float, K: float, T: float, r: float, q: float) -> Optional[float]:
    if target <= 0 or T <= 0:
        return None
    intrinsic = max(K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)
    if target <= intrinsic + 1e-6:
        return 0.01
    try:
        f = lambda s: bs_put(S, K, T, r, q, s) - target
        return brentq(f, 1e-4, 5.0, xtol=1e-5)
    except (ValueError, RuntimeError):
        return None


def bs_greeks_put(S: float, K: float, T: float, r: float, q: float, sigma: float) -> dict:
    if sigma <= 0 or T <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta_yr": 0.0, "vega_dec": 0.0}
    sqT = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqT)
    d2 = d1 - sigma * sqT
    delta = -math.exp(-q * T) * norm.cdf(-d1)
    gamma = math.exp(-q * T) * norm.pdf(d1) / (S * sigma * sqT)
    # Theta per year, calendar-time convention (negative for long ATM put)
    theta_yr = (-S * math.exp(-q * T) * norm.pdf(d1) * sigma / (2 * sqT)
                + r * K * math.exp(-r * T) * norm.cdf(-d2)
                - q * S * math.exp(-q * T) * norm.cdf(-d1))
    vega_dec = S * math.exp(-q * T) * norm.pdf(d1) * sqT
    return {"delta": delta, "gamma": gamma, "theta_yr": theta_yr, "vega_dec": vega_dec}


# ── per-day per-leg state ────────────────────────────────────────────────────

def day_state(pos: Position, d: date, spx_hist: dict[str, float]) -> Optional[dict]:
    iso = d.isoformat()
    S = spx_hist.get(iso)
    if S is None:
        return None
    ms = load_chain_mark(d, pos.short_strike, pos.expiry)
    ml = load_chain_mark(d, pos.long_strike, pos.expiry)
    if ms is None or ml is None:
        return None
    T = max((pos.expiry - d).days, 1) / DAYS_PER_YEAR
    iv_s = solve_iv(ms, S, pos.short_strike, T, R, Q)
    iv_l = solve_iv(ml, S, pos.long_strike, T, R, Q)
    if iv_s is None or iv_l is None:
        return None
    gs = bs_greeks_put(S, pos.short_strike, T, R, Q, iv_s)
    gl = bs_greeks_put(S, pos.long_strike, T, R, Q, iv_l)
    return {"date": iso, "S": S, "T": T, "ms": ms, "ml": ml,
            "iv_s": iv_s, "iv_l": iv_l, "gs": gs, "gl": gl}


def attribute_pair(pos: Position, t0: dict, t1: dict) -> dict:
    """Return per-greek dollar attribution for the spread holder."""
    mult = 100 * pos.contracts
    dS = t1["S"] - t0["S"]
    dt_yr = (date.fromisoformat(t1["date"]) - date.fromisoformat(t0["date"])).days / DAYS_PER_YEAR
    dIV_s = t1["iv_s"] - t0["iv_s"]
    dIV_l = t1["iv_l"] - t0["iv_l"]

    # short put side -1; long put side +1
    delta_attr = mult * ((-1) * t0["gs"]["delta"] * dS + 1 * t0["gl"]["delta"] * dS)
    gamma_attr = mult * 0.5 * ((-1) * t0["gs"]["gamma"] * dS * dS + 1 * t0["gl"]["gamma"] * dS * dS)
    theta_attr = mult * ((-1) * t0["gs"]["theta_yr"] * dt_yr + 1 * t0["gl"]["theta_yr"] * dt_yr)
    vega_attr  = mult * ((-1) * t0["gs"]["vega_dec"] * dIV_s + 1 * t0["gl"]["vega_dec"] * dIV_l)
    actual_pnl = mult * ((-1) * (t1["ms"] - t0["ms"]) + 1 * (t1["ml"] - t0["ml"]))
    residual = actual_pnl - (delta_attr + gamma_attr + theta_attr + vega_attr)
    return {
        "actual_pnl": round(actual_pnl, 2),
        "delta_attr": round(delta_attr, 2),
        "gamma_attr": round(gamma_attr, 2),
        "theta_attr": round(theta_attr, 2),
        "vega_attr":  round(vega_attr, 2),
        "residual":   round(residual, 2),
    }


# ── append-only output ───────────────────────────────────────────────────────

def existing_keys() -> set[tuple[str, str]]:
    if not OUT_PATH.exists():
        return set()
    keys = set()
    with open(OUT_PATH) as f:
        for line in f:
            try:
                r = json.loads(line)
                keys.add((r["date"], r["trade_id"]))
            except Exception:
                continue
    return keys


def emit_row(out_f, pos: Position, t0: dict, t1: dict, attr: dict) -> None:
    row = {
        "date":         t1["date"],
        "prev_date":    t0["date"],
        "trade_id":     pos.trade_id,
        "strategy":     pos.strategy,
        "account":      pos.account,
        "short_strike": pos.short_strike,
        "long_strike":  pos.long_strike,
        "contracts":    pos.contracts,
        "expiry":       pos.expiry.isoformat(),
        "dte":          (pos.expiry - date.fromisoformat(t1["date"])).days,
        "S_t0":         round(t0["S"], 2),
        "S_t1":         round(t1["S"], 2),
        "iv_s_t0":      round(t0["iv_s"], 4),
        "iv_l_t0":      round(t0["iv_l"], 4),
        "iv_s_t1":      round(t1["iv_s"], 4),
        "iv_l_t1":      round(t1["iv_l"], 4),
        "mark_s_t0":    round(t0["ms"], 2),
        "mark_l_t0":    round(t0["ml"], 2),
        "mark_s_t1":    round(t1["ms"], 2),
        "mark_l_t1":    round(t1["ml"], 2),
        **attr,
        "compute_method": COMPUTE_METHOD,
    }
    out_f.write(json.dumps(row) + "\n")


def compute() -> int:
    open_pos = load_open_positions()
    closed_pos = load_closed_trades()
    if not open_pos and not closed_pos:
        print("[greek-attr] no positions to compute")
        return 0
    spx_hist = load_spx_history()
    done = existing_keys()
    print(f"[greek-attr] open={len(open_pos)} closed={len(closed_pos)} existing_rows={len(done)}")

    today = max(
        date.fromisoformat(d.name)
        for d in SNAPSHOT_DIR.iterdir()
        if d.name[:1].isdigit()
    )

    def process(pos: Position, out_f) -> int:
        end = pos.closed_at if pos.closed_at else today
        states = []
        for d in trading_days(pos.opened_at, end):
            s = day_state(pos, d, spx_hist)
            if s is not None:
                states.append(s)
        # For closed trades: override the edge marks (opened_at and closed_at)
        # with actual broker fills so the cumulative actual_pnl reconciles to
        # broker realized PnL. Without this, the chain end-of-day mark on the
        # entry/exit day can differ from broker fill by 20-30% (intraday move
        # between fill and close). Greeks stay at chain end-of-day BS-solved
        # values — slight mismatch absorbed in residual.
        if states:
            if pos.exit_short_fill is not None and pos.exit_long_fill is not None and pos.closed_at:
                last = states[-1]
                if date.fromisoformat(last["date"]) == pos.closed_at:
                    last["ms"] = pos.exit_short_fill
                    last["ml"] = pos.exit_long_fill
            entry_short = getattr(pos, "entry_short_fill", None)
            entry_long  = getattr(pos, "entry_long_fill", None)
            if entry_short is not None and entry_long is not None:
                first = states[0]
                if date.fromisoformat(first["date"]) == pos.opened_at:
                    first["ms"] = entry_short
                    first["ml"] = entry_long
        n_written = 0
        for i in range(1, len(states)):
            t0, t1 = states[i-1], states[i]
            key = (t1["date"], pos.trade_id)
            if key in done:
                continue
            attr = attribute_pair(pos, t0, t1)
            emit_row(out_f, pos, t0, t1, attr)
            n_written += 1
        return n_written

    written = 0
    with open(OUT_PATH, "a") as out_f:
        for pos in open_pos + closed_pos:
            written += process(pos, out_f)
    print(f"[greek-attr] appended {written} rows → {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(compute())
