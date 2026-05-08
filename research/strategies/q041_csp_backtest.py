"""
Q041 CSP Backtest — per-sleeve simulation using actual option prices.

Sleeves:
  SPX   Tier-1: 30 DTE, ~Δ0.20 (5% OTM proxy), SPX × $100/pt
  GOOGL Tier-2: 21 DTE, ~Δ0.20 (4% OTM proxy), 100 shares/contract
  AMZN  Tier-2: 21 DTE, ~Δ0.25 (4.5% OTM proxy), 100 shares/contract

Data source: data/q041_historical/{symbol}.parquet (2022-05-06 to 2026-05-05)
Underlying prices: yfinance

Pricing methodology:
  - Entry + daily MTM: actual market close prices from parquet (tracks by OCC ticker)
  - Fallback when option leaves parquet: Black-Scholes with per-asset IV proxy
  - Exit: 50% profit captured OR DTE ≤ 3 (gamma risk) OR 3× credit stop
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtest.pricer import put_price

_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"

STOP_MULT      = 3.0
PROFIT_TARGET  = 0.50   # close at 50% of credit retained
GAMMA_DTE      = 3
MULTIPLIER     = 100

_IV_PROXY = {"SPX": 0.18, "GOOGL": 0.28, "AMZN": 0.35}   # fallback IV per asset


@dataclass
class CspTrade:
    symbol:        str
    entry_date:    str
    exit_date:     str
    entry_price:   float
    strike:        float
    dte_at_entry:  int
    dte_at_exit:   int
    entry_premium: float
    exit_premium:  float
    exit_reason:   str
    pnl:           float


@dataclass
class CspBacktestResult:
    symbol:  str
    label:   str
    trades:  list[CspTrade] = field(default_factory=list)
    equity:  list[dict]     = field(default_factory=list)


def _fetch_underlying(symbol: str) -> pd.Series:
    yt = "^GSPC" if symbol == "SPX" else symbol
    df = yf.Ticker(yt).history(period="max", interval="1d")
    idx = df.index
    df.index = pd.to_datetime(idx.date if hasattr(idx, "date") else idx).normalize()
    return df["Close"].sort_index()


def _load_puts(symbol: str) -> pd.DataFrame:
    """Load puts parquet and index by (date, occ_ticker) for fast daily lookups."""
    path = _DATA_ROOT / "q041_historical" / f"{symbol}.parquet"
    df = pd.read_parquet(path)
    puts = df[df["option_type"] == "P"][
        ["date", "expiry", "strike", "close", "occ_ticker"]
    ].copy()
    puts["date"]   = pd.to_datetime(puts["date"])
    puts["expiry"] = pd.to_datetime(puts["expiry"])
    puts["dte"]    = (puts["expiry"] - puts["date"]).dt.days
    return puts


def run_csp_sleeve(
    symbol: str,
    label: str,
    target_dte: int = 21,
    otm_fraction: float = 0.04,
    dte_window: int = 5,
    start_date: str = "2022-05-06",
    end_date: str | None = None,
) -> CspBacktestResult:
    result     = CspBacktestResult(symbol=symbol, label=label)
    underlying = _fetch_underlying(symbol)
    puts_all   = _load_puts(symbol)
    iv_proxy   = _IV_PROXY.get(symbol, 0.25)

    # Build a date → {occ_ticker → close} dict for fast daily MTM lookup
    daily_px: dict[pd.Timestamp, dict[str, float]] = {}
    for row in puts_all.itertuples(index=False):
        d = row.date
        if d not in daily_px:
            daily_px[d] = {}
        if row.close and float(row.close) > 0:
            daily_px[d][row.occ_ticker] = float(row.close)

    sim = underlying[underlying.index >= pd.Timestamp(start_date)]
    if end_date:
        sim = sim[sim.index <= pd.Timestamp(end_date)]

    equity  = 50_000.0
    peak_eq = equity
    pos: dict | None = None   # open position

    for date, price in sim.items():
        dstr      = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        closed    = False

        if pos is not None:
            pos["dte"] -= 1

            # Look up actual market price for this option today
            today_prices = daily_px.get(date, {})
            cur_val = today_prices.get(pos["occ_ticker"])
            if cur_val is None:
                # fallback to BS
                cur_val = put_price(price, pos["strike"], max(pos["dte"], 0), iv_proxy)

            reason = None
            if   pos["dte"] <= GAMMA_DTE:           reason = "gamma_risk"
            elif cur_val >= pos["stop_prem"]:        reason = "stop_loss"
            elif cur_val <= pos["profit_prem"]:      reason = "profit_target"
            elif pos["dte"] <= 0:                    reason = "expiry"

            if reason:
                pnl = (pos["entry_prem"] - cur_val) * MULTIPLIER
                result.trades.append(CspTrade(
                    symbol=symbol, entry_date=pos["entry_date"], exit_date=dstr,
                    entry_price=pos["entry_px"], strike=pos["strike"],
                    dte_at_entry=pos["dte_at_entry"], dte_at_exit=pos["dte"],
                    entry_premium=pos["entry_prem"], exit_premium=cur_val,
                    exit_reason=reason, pnl=pnl,
                ))
                equity  += pnl
                peak_eq  = max(peak_eq, equity)
                pos      = None
                closed   = True

        if pos is None:
            # Find entry: put near target_dte and otm_fraction below price
            target_k  = price * (1 - otm_fraction)
            day_puts  = puts_all[
                (puts_all["date"] == date)
                & puts_all["dte"].between(target_dte - dte_window, target_dte + dte_window)
                & (puts_all["close"] > 0.05)
            ].copy()
            if not day_puts.empty:
                day_puts["kdist"] = (day_puts["strike"] - target_k).abs()
                best = day_puts.nsmallest(1, "kdist").iloc[0]
                if float(best["kdist"]) <= target_k * 0.10:   # within 10%
                    prem = float(best["close"])
                    pos = {
                        "entry_date":  dstr,
                        "entry_px":    price,
                        "strike":      float(best["strike"]),
                        "occ_ticker":  best["occ_ticker"],
                        "dte":         int(best["dte"]),
                        "dte_at_entry": int(best["dte"]),
                        "entry_prem":  prem,
                        "stop_prem":   prem * STOP_MULT,
                        "profit_prem": prem * (1 - PROFIT_TARGET),
                    }

        result.equity.append({"date": dstr, "equity": round(equity, 2)})

    return result


def run_q041_backtest(start_date: str = "2022-05-06") -> dict:
    sleeves_cfg = [
        dict(symbol="SPX",   label="SPX Tier-1 CSP",  target_dte=30, otm_fraction=0.05),
        dict(symbol="GOOGL", label="GOOGL Tier-2 CSP", target_dte=21, otm_fraction=0.04),
        dict(symbol="AMZN",  label="AMZN Tier-2 CSP",  target_dte=21, otm_fraction=0.045),
    ]

    results = []
    for cfg in sleeves_cfg:
        r     = run_csp_sleeve(start_date=start_date, **cfg)
        wins  = [t for t in r.trades if t.pnl > 0]
        stops = [t for t in r.trades if t.exit_reason == "stop_loss"]
        profits = [t for t in r.trades if t.exit_reason == "profit_target"]
        total = sum(t.pnl for t in r.trades)
        results.append({
            "symbol":            r.symbol,
            "label":             r.label,
            "n_trades":          len(r.trades),
            "win_rate_pct":      round(len(wins) / len(r.trades) * 100, 1) if r.trades else 0,
            "stop_rate_pct":     round(len(stops) / len(r.trades) * 100, 1) if r.trades else 0,
            "profit_target_pct": round(len(profits) / len(r.trades) * 100, 1) if r.trades else 0,
            "total_pnl":         round(total, 0),
            "equity_curve":      r.equity[::5],
            "trades": [
                {
                    "entry_date":    t.entry_date,
                    "exit_date":     t.exit_date,
                    "strike":        t.strike,
                    "dte_at_entry":  t.dte_at_entry,
                    "dte_at_exit":   t.dte_at_exit,
                    "entry_premium": round(t.entry_premium, 2),
                    "exit_premium":  round(t.exit_premium, 2),
                    "exit_reason":   t.exit_reason,
                    "pnl":           round(t.pnl, 2),
                }
                for t in r.trades
            ],
        })

    return {"status": "ok", "start_date": start_date, "sleeves": results}
