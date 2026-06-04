"""Compute daily greek-decomposed PnL attribution for open SPX positions.

Path A (BS reverse-solve) — used for historical backfill until path B
(broker chain greeks captured at snapshot time) is wired in.

Reads:
  data/daily_snapshot.jsonl       (latest row → open SPX positions)
  data/q041_massive_snapshot/{d}/SPX.parquet  (per-leg day_close per day)
  data/q042_spx_history_cache.json (SPX close per day; source of truth)

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
COMPUTE_METHOD = "bs_call_put_pathB_v3"   # v3: CALL support + per-leg expiry (BCD)


# ── data loaders ─────────────────────────────────────────────────────────────

@dataclass
class Position:
    trade_id: str
    account: str
    strategy: str
    short_strike: float
    long_strike: float
    contracts: int
    expiry: date                                 # short-leg expiry for diagonals
    opened_at: date
    option_type: str = "PUT"                     # "PUT" (BPS) | "CALL" (BCD, bear-call)
    long_expiry: Optional[date] = None           # long-leg expiry when diagonal; None = vertical
    closed_at: Optional[date] = None             # None when still open
    entry_credit_per_share: Optional[float] = None  # broker spread credit (signed: + = received, − = paid)
    exit_debit_per_share: Optional[float] = None    # broker spread debit on close
    entry_short_fill: Optional[float] = None     # per-leg broker fill at open (manually seeded)
    entry_long_fill: Optional[float] = None
    exit_short_fill: Optional[float] = None      # per-leg broker fill at close
    exit_long_fill: Optional[float] = None
    realized_pnl: Optional[float] = None         # broker-reported, for chart reconciliation


# Strategy → option_type. PUT default for bull put credit spreads (BPS).
_STRATEGY_OPTION_TYPE = {
    "bull_put_spread":     "PUT",
    "bull_put_spread_hv":  "PUT",
    "bear_call_spread_hv": "CALL",
    "bull_call_diagonal":  "CALL",
    "iron_condor":         "PUT",  # IC uses both; treat as put-side dominant for now
    "iron_condor_hv":      "PUT",
}


def _strategy_key_for(p: dict) -> str:
    """Best-effort pull of strategy_key from snapshot position dict or
    daily_snapshot record. Falls back to bull_put_spread (legacy default).
    """
    return str(p.get("strategy_key") or p.get("strategy") or "bull_put_spread").lower()


CURRENT_POSITION_FILE = REPO / "logs" / "current_position.json"


def _current_state() -> dict:
    """Read logs/current_position.json — has strategy_key, long_expiry per
    position. daily_snapshot.jsonl doesn't currently carry those fields, so
    we cross-reference live state for open-position metadata.
    """
    try:
        with open(CURRENT_POSITION_FILE) as f:
            return json.load(f) or {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_open_positions() -> list[Position]:
    """Pull currently-open SPX positions from latest daily_snapshot row,
    enriched with strategy_key + long_expiry from current_position.json.
    """
    with open(DAILY_SNAPSHOT) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows:
        return []
    latest = rows[-1]
    state = _current_state()
    state_strategy_key = str(state.get("strategy_key") or "").lower()
    state_positions = {p.get("trade_id"): p for p in (state.get("positions") or [])}
    positions = []
    for p in (latest.get("strategies", {}).get("spx_spread", {}).get("positions") or []):
        ep = p.get("entry_premium")
        tid = p.get("trade_id")
        live = state_positions.get(tid, {})
        # Strategy key — fallback chain: snapshot field → state file → BPS default
        strat_key = str(p.get("strategy_key") or state_strategy_key or "bull_put_spread").lower()
        # Option type from strategy_key, falling back to sign of entry premium
        # (negative = debit = call spread; positive = credit = put spread).
        option_type = _STRATEGY_OPTION_TYPE.get(strat_key)
        if option_type is None:
            option_type = "CALL" if (ep is not None and float(ep) < 0) else "PUT"
        long_exp_iso = p.get("long_expiry") or live.get("long_expiry")
        positions.append(Position(
            trade_id=tid,
            account=p["account"],
            strategy="spx_spread",
            option_type=option_type,
            short_strike=float(p["short_strike"]),
            long_strike=float(p["long_strike"]),
            contracts=int(p["contracts"]),
            expiry=date.fromisoformat(p["expiry"]),
            long_expiry=date.fromisoformat(long_exp_iso) if long_exp_iso else None,
            opened_at=date.fromisoformat(p["opened_at"]),
            entry_credit_per_share=float(ep) if ep is not None else None,
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
            # Option type from explicit field, strategy_key, or entry_credit sign
            opt = r.get("option_type")
            if not opt:
                sk = str(r.get("strategy_key") or "").lower()
                opt = _STRATEGY_OPTION_TYPE.get(sk)
                if opt is None:
                    ec = r.get("entry_credit_per_share")
                    opt = "CALL" if (ec is not None and float(ec) < 0) else "PUT"
            long_exp_iso = r.get("long_expiry")
            positions.append(Position(
                trade_id=r["trade_id"],
                account=r["account"],
                strategy=r["strategy"],
                option_type=str(opt).upper(),
                short_strike=float(r["short_strike"]),
                long_strike=float(r["long_strike"]),
                contracts=int(r["contracts"]),
                expiry=date.fromisoformat(r["expiry"]),
                long_expiry=date.fromisoformat(long_exp_iso) if long_exp_iso else None,
                opened_at=date.fromisoformat(r["opened_at"]),
                closed_at=date.fromisoformat(r["closed_at"]),
                entry_credit_per_share=float(r.get("entry_credit_per_share")) if r.get("entry_credit_per_share") is not None else None,
                exit_debit_per_share=float(r.get("exit_debit_per_share")) if r.get("exit_debit_per_share") is not None else None,
                entry_short_fill=float(r.get("entry_short_fill")) if r.get("entry_short_fill") is not None else None,
                entry_long_fill=float(r.get("entry_long_fill")) if r.get("entry_long_fill") is not None else None,
                exit_short_fill=float(r.get("exit_short_fill")) if r.get("exit_short_fill") is not None else None,
                exit_long_fill=float(r.get("exit_long_fill")) if r.get("exit_long_fill") is not None else None,
                realized_pnl=float(r.get("realized_pnl")) if r.get("realized_pnl") is not None else None,
            ))
    return positions


def load_spx_history() -> dict[str, float]:
    """Date ISO → SPX close. q042 cache is primary; daily_snapshot.market.spx
    fills the trailing window (q042 cache refresh lags, but daily_snapshot
    writes the current SPX every market-close run).
    """
    out: dict[str, float] = {}
    try:
        with open(SPX_HIST) as f:
            d = json.load(f)
        for row in d["full"]["payload"]["history"]:
            out[row["date"]] = float(row["close"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    # Trailing fallback from daily_snapshot
    try:
        with open(DAILY_SNAPSHOT) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                iso = r.get("date")
                spx = (r.get("market") or {}).get("spx")
                if iso and spx and iso not in out:
                    out[iso] = float(spx)
    except FileNotFoundError:
        pass
    return out


def load_broker_greeks() -> dict[tuple[str, str], dict]:
    """Path B: load broker chain greeks captured at daily_snapshot time.
    Returns {(date_iso, trade_id): {"short": {delta,gamma,theta,vega,iv,mark},
                                     "long":  {...}}}. Empty when v3/v4 snapshot
    rows haven't been written yet (deployed mid-2026-05-28).

    Broker conventions converted to internal:
      theta_yr  = broker_theta_per_day × 365
      vega_dec  = broker_vega_per_1pct × 100
      iv        = broker_iv (already decimal if < 1 else /100)
    """
    out: dict[tuple[str, str], dict] = {}
    with open(DAILY_SNAPSHOT) as f:
        for line in f:
            r = json.loads(line)
            iso = r.get("date")
            for p in (r.get("strategies", {}).get("spx_spread", {}).get("positions") or []):
                tid = p.get("trade_id")
                gs = p.get("greeks_short")
                gl = p.get("greeks_long")
                if not (tid and iso and gs and gl):
                    continue
                if any(gs.get(k) is None for k in ("delta", "gamma", "theta", "vega", "iv", "mark")):
                    continue
                if any(gl.get(k) is None for k in ("delta", "gamma", "theta", "vega", "iv", "mark")):
                    continue
                out[(iso, tid)] = {
                    "short": {
                        "delta":    float(gs["delta"]),
                        "gamma":    float(gs["gamma"]),
                        "theta_yr": float(gs["theta"]) * 365.0,
                        "vega_dec": float(gs["vega"]) * 100.0,
                        "iv":       (float(gs["iv"]) / 100.0) if float(gs["iv"]) > 1 else float(gs["iv"]),
                        "mark":     float(gs["mark"]),
                    },
                    "long": {
                        "delta":    float(gl["delta"]),
                        "gamma":    float(gl["gamma"]),
                        "theta_yr": float(gl["theta"]) * 365.0,
                        "vega_dec": float(gl["vega"]) * 100.0,
                        "iv":       (float(gl["iv"]) / 100.0) if float(gl["iv"]) > 1 else float(gl["iv"]),
                        "mark":     float(gl["mark"]),
                    },
                }
    return out


def trading_days(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def load_chain_mark(snapshot_date: date, strike: float, expiry: date,
                    option_type: str = "PUT") -> Optional[float]:
    """Per-leg day_close from q041 SPX parquet. Prefer SPXW (PM trades weeklies).
    option_type: 'PUT' or 'CALL' — was hard-coded 'put' before generalization.
    """
    p = SNAPSHOT_DIR / snapshot_date.isoformat() / "SPX.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=["occ_ticker", "strike_price", "contract_type",
                                     "expiration_date", "day_close"])
    ct = str(option_type).lower()
    m = ((df.contract_type == ct) &
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


# ── BS math (PUT + CALL) ─────────────────────────────────────────────────────

def bs_put(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    if sigma <= 0 or T <= 0:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def bs_call(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    if sigma <= 0 or T <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def _bs_price(opt: str, S, K, T, r, q, sigma):
    return bs_call(S, K, T, r, q, sigma) if str(opt).upper() == "CALL" else bs_put(S, K, T, r, q, sigma)


def solve_iv(target: float, S: float, K: float, T: float, r: float, q: float,
             option_type: str = "PUT") -> Optional[float]:
    if target <= 0 or T <= 0:
        return None
    opt = str(option_type).upper()
    if opt == "CALL":
        intrinsic = max(S * math.exp(-q * T) - K * math.exp(-r * T), 0.0)
    else:
        intrinsic = max(K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)
    if target <= intrinsic + 1e-6:
        return 0.01
    try:
        f = lambda s: _bs_price(opt, S, K, T, r, q, s) - target
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
    theta_yr = (-S * math.exp(-q * T) * norm.pdf(d1) * sigma / (2 * sqT)
                + r * K * math.exp(-r * T) * norm.cdf(-d2)
                - q * S * math.exp(-q * T) * norm.cdf(-d1))
    vega_dec = S * math.exp(-q * T) * norm.pdf(d1) * sqT
    return {"delta": delta, "gamma": gamma, "theta_yr": theta_yr, "vega_dec": vega_dec}


def bs_greeks_call(S: float, K: float, T: float, r: float, q: float, sigma: float) -> dict:
    if sigma <= 0 or T <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta_yr": 0.0, "vega_dec": 0.0}
    sqT = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqT)
    d2 = d1 - sigma * sqT
    delta = math.exp(-q * T) * norm.cdf(d1)
    gamma = math.exp(-q * T) * norm.pdf(d1) / (S * sigma * sqT)
    # Call theta per year, calendar-time convention (negative for long ATM call)
    theta_yr = (-S * math.exp(-q * T) * norm.pdf(d1) * sigma / (2 * sqT)
                - r * K * math.exp(-r * T) * norm.cdf(d2)
                + q * S * math.exp(-q * T) * norm.cdf(d1))
    vega_dec = S * math.exp(-q * T) * norm.pdf(d1) * sqT
    return {"delta": delta, "gamma": gamma, "theta_yr": theta_yr, "vega_dec": vega_dec}


def _bs_greeks(opt: str, S, K, T, r, q, sigma):
    return bs_greeks_call(S, K, T, r, q, sigma) if str(opt).upper() == "CALL" else bs_greeks_put(S, K, T, r, q, sigma)


# ── per-day per-leg state ────────────────────────────────────────────────────

def day_state(pos: Position, d: date, spx_hist: dict[str, float],
              broker_greeks: Optional[dict] = None,
              override_ms: Optional[float] = None,
              override_ml: Optional[float] = None) -> Optional[dict]:
    """Build per-day state. Supports PUT (BPS) and CALL (BCD, bear-call) plus
    per-leg expiry for true diagonals (pos.long_expiry > pos.expiry).
    """
    iso = d.isoformat()
    S = spx_hist.get(iso)
    if S is None:
        return None
    opt = (pos.option_type or "PUT").upper()
    short_exp = pos.expiry
    long_exp  = pos.long_expiry or pos.expiry
    T_s = max((short_exp - d).days, 1) / DAYS_PER_YEAR
    T_l = max((long_exp  - d).days, 1) / DAYS_PER_YEAR
    # Path B: prefer broker chain greeks (when not overriding marks for fills)
    if override_ms is None and override_ml is None and broker_greeks is not None:
        bg = broker_greeks.get((iso, pos.trade_id))
        if bg:
            return {
                "date": iso, "S": S, "T_s": T_s, "T_l": T_l,
                "ms": bg["short"]["mark"], "ml": bg["long"]["mark"],
                "iv_s": bg["short"]["iv"], "iv_l": bg["long"]["iv"],
                "gs": {"delta": bg["short"]["delta"], "gamma": bg["short"]["gamma"],
                       "theta_yr": bg["short"]["theta_yr"], "vega_dec": bg["short"]["vega_dec"]},
                "gl": {"delta": bg["long"]["delta"], "gamma": bg["long"]["gamma"],
                       "theta_yr": bg["long"]["theta_yr"], "vega_dec": bg["long"]["vega_dec"]},
                "broker": True,
            }
    # Path A: chain mark + BS reverse-solve (per-leg expiry for diagonals)
    ms = override_ms if override_ms is not None else load_chain_mark(d, pos.short_strike, short_exp, opt)
    ml = override_ml if override_ml is not None else load_chain_mark(d, pos.long_strike,  long_exp,  opt)
    if ms is None or ml is None:
        return None
    iv_s = solve_iv(ms, S, pos.short_strike, T_s, R, Q, option_type=opt)
    iv_l = solve_iv(ml, S, pos.long_strike,  T_l, R, Q, option_type=opt)
    if iv_s is None or iv_l is None:
        return None
    gs = _bs_greeks(opt, S, pos.short_strike, T_s, R, Q, iv_s)
    gl = _bs_greeks(opt, S, pos.long_strike,  T_l, R, Q, iv_l)
    return {"date": iso, "S": S, "T_s": T_s, "T_l": T_l, "ms": ms, "ml": ml,
            "iv_s": iv_s, "iv_l": iv_l, "gs": gs, "gl": gl, "broker": False}


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
        "option_type":  pos.option_type,
        "account":      pos.account,
        "short_strike": pos.short_strike,
        "long_strike":  pos.long_strike,
        "contracts":    pos.contracts,
        "expiry":       pos.expiry.isoformat(),
        "long_expiry":  pos.long_expiry.isoformat() if pos.long_expiry else None,
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
        "synthetic_t0": bool(t0.get("synthetic")),
        "synthetic_t1": bool(t1.get("synthetic")),
        "greek_source_t0": "broker_chain" if t0.get("broker") else "bs_reverse_solve",
        "greek_source_t1": "broker_chain" if t1.get("broker") else "bs_reverse_solve",
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
    broker_greeks = load_broker_greeks()
    done = existing_keys()
    print(f"[greek-attr] open={len(open_pos)} closed={len(closed_pos)} "
          f"broker_greek_rows={len(broker_greeks)} existing_rows={len(done)}")

    today = max(
        date.fromisoformat(d.name)
        for d in SNAPSHOT_DIR.iterdir()
        if d.name[:1].isdigit()
    )

    def synth_state(pos: Position, d: date, S: float, iv_s: float, iv_l: float) -> dict:
        """Gap-day synthesis: hold IV constant, recompute marks + greeks via BS
        at actual S and per-leg T. Per-option-type (CALL/PUT) and per-leg
        expiry (diagonals).
        """
        opt = (pos.option_type or "PUT").upper()
        long_exp = pos.long_expiry or pos.expiry
        T_s = max((pos.expiry - d).days, 1) / DAYS_PER_YEAR
        T_l = max((long_exp   - d).days, 1) / DAYS_PER_YEAR
        ms = _bs_price(opt, S, pos.short_strike, T_s, R, Q, iv_s)
        ml = _bs_price(opt, S, pos.long_strike,  T_l, R, Q, iv_l)
        gs = _bs_greeks(opt, S, pos.short_strike, T_s, R, Q, iv_s)
        gl = _bs_greeks(opt, S, pos.long_strike,  T_l, R, Q, iv_l)
        return {"date": d.isoformat(), "S": S, "T_s": T_s, "T_l": T_l,
                "ms": ms, "ml": ml, "iv_s": iv_s, "iv_l": iv_l,
                "gs": gs, "gl": gl, "synthetic": True}

    def process(pos: Position, out_f) -> int:
        end = pos.closed_at if pos.closed_at else today
        # Path B continuity rule: for each transition (t0, t1), only use broker
        # greeks if BOTH endpoints have broker support AND neither is an edge
        # day (override). Otherwise both endpoints fall back to BS reverse-solve
        # so mark/IV/greek scales stay internally consistent.
        td_list = trading_days(pos.opened_at, end)
        def _is_edge(d: date) -> bool:
            if d == pos.opened_at and (pos.entry_short_fill is not None or pos.entry_credit_per_share is not None):
                return True
            if pos.closed_at and d == pos.closed_at and (pos.exit_short_fill is not None or pos.exit_debit_per_share is not None):
                return True
            return False
        broker_ok = {
            d: (not _is_edge(d)) and ((d.isoformat(), pos.trade_id) in broker_greeks)
            for d in td_list
        }
        # Per-day decision: use broker only if today AND the neighbor we'll
        # transition with also has broker. For each day, we look at next day.
        # First day of a broker stream propagates via "prev was broker" anchor.
        use_broker_for_day: dict[date, bool] = {}
        for i, d in enumerate(td_list):
            prev_was_broker = i > 0 and use_broker_for_day.get(td_list[i-1], False)
            next_has_broker = i + 1 < len(td_list) and broker_ok[td_list[i+1]]
            use_broker_for_day[d] = broker_ok[d] and (prev_was_broker or next_has_broker)
        states = []
        last_iv_s, last_iv_l = None, None
        for d in td_list:
            # Override marks at edge days so IV/greeks are solved at broker
            # truth, eliminating the "instant repricing" jump between chain
            # mark and broker fill on opened_at/closed_at days.
            #
            # Closed trades: PM provides per-leg fills (cleanest).
            # Open trades: only broker spread credit is logged — split adj
            #              into both legs so ms-ml equals broker credit while
            #              keeping each leg close to chain mark (IV preserved).
            om, ol = None, None
            opt = (pos.option_type or "PUT").upper()
            long_exp = pos.long_expiry or pos.expiry
            if d == pos.opened_at:
                if pos.entry_short_fill is not None:
                    om, ol = pos.entry_short_fill, pos.entry_long_fill
                elif pos.entry_credit_per_share is not None:
                    cm = load_chain_mark(d, pos.short_strike, pos.expiry, opt)
                    cl = load_chain_mark(d, pos.long_strike,  long_exp,   opt)
                    if cm is not None and cl is not None:
                        adj = ((cm - cl) - pos.entry_credit_per_share) / 2.0
                        om = max(cm - adj, 0.01)
                        ol = max(cl + adj, 0.01)
            elif pos.closed_at and d == pos.closed_at:
                if pos.exit_short_fill is not None:
                    om, ol = pos.exit_short_fill, pos.exit_long_fill
                elif pos.exit_debit_per_share is not None:
                    cm = load_chain_mark(d, pos.short_strike, pos.expiry, opt)
                    cl = load_chain_mark(d, pos.long_strike,  long_exp,   opt)
                    if cm is not None and cl is not None:
                        adj = ((cm - cl) - pos.exit_debit_per_share) / 2.0
                        om = max(cm - adj, 0.01)
                        ol = max(cl + adj, 0.01)
            s = day_state(pos, d, spx_hist,
                          broker_greeks=broker_greeks if use_broker_for_day.get(d) else None,
                          override_ms=om, override_ml=ol)
            if s is not None:
                last_iv_s, last_iv_l = s["iv_s"], s["iv_l"]
                states.append(s)
            elif last_iv_s is not None:
                S = spx_hist.get(d.isoformat())
                if S is not None:
                    states.append(synth_state(pos, d, S, last_iv_s, last_iv_l))
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
