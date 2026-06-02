"""Q082 P6 — Full 26y synthetic BCD PnL reconstruction (B-synth-full).

Method:
  For each BCD-eligible day d in signal_history_cache (1747 days, 2003-2026):
    Spot   = SPX close on d (from q042 cache + yfinance fallback)
    Sigma  = VIX close on d / 100 (VIX as ATM 30d IV proxy, flat across strikes)
    Long  = 90 DTE call at delta 0.70 (find strike via binary search)
    Short = 45 DTE call at delta 0.30 (find strike via binary search)
    Entry debit = BS_call(long) - BS_call(short)  [per share, ×100 for contract]
    Hold:
      Walk forward day by day, refresh Spot + Sigma daily
      Reprice both legs with reduced DTE
      Exit when short leg has 21 DTE remaining (24 days elapsed)
    Exit PnL = (final_long_value - final_short_value) - entry_debit
  Output per-trade row with debit / pnl / hold_days / entry vix / ivp / regime.

Methodology caveats (flag explicitly in P7 memo):
  1. BS-flat IV (constant sigma=VIX/100 across strikes) — IGNORES SKEW.
     Real chain: deep-ITM 0.70δ call has LOWER IV than ATM (long-leg cheaper);
                 OTM 0.30δ call has HIGHER IV than ATM (short-leg richer)
     Net BCD entry debit BS-flat estimate may understate true debit by ~5-10%.
  2. VIX is 30d ATM IV; we apply it to 45d AND 90d. Term structure typically
     contango (longer IV higher) — long leg IV underestimated → long leg
     undervalued by BS-flat. Reverse for short leg.
  3. No transaction costs, no slippage, no early assignment risk.
  4. Daily mark only — no intraday short-leg punch-through detection.
  5. Constant r = 5%, q = 1.3% (per backtest.pricer defaults).

These caveats apply EQUALLY to entry and exit prices, so absolute PnL has
unknown bias but RELATIVE comparison (BCD vs same-window QQQ) is more robust
since QQQ is from market data (no model). The comparison error is BCD-side only.
"""
from __future__ import annotations
import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
TRADES_OUT = ROOT / "research" / "q082" / "q082_p6_synth_trades.csv"

# Constants matching backtest.pricer defaults
R = 0.05
Q = 0.013  # SPX dividend yield approx
SHORT_DTE = 45
LONG_DTE = 90
SHORT_DELTA_TARGET = 0.30
LONG_DELTA_TARGET = 0.70
ROLL_AT_DTE = 21  # exit when short leg has this DTE remaining


# --- BS pricing primitives (self-contained, mirrors backtest.pricer) ---

def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _d1_d2(S: float, K: float, T: float, sigma: float, r: float = R, q: float = Q):
    if T <= 0 or sigma <= 0 or K <= 0 or S <= 0:
        return None, None
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def call_price(S: float, K: float, dte: int, sigma: float) -> float:
    T = dte / 365.0
    d1, d2 = _d1_d2(S, K, T, sigma)
    if d1 is None:
        return max(S - K, 0)
    return S * math.exp(-Q * T) * _norm_cdf(d1) - K * math.exp(-R * T) * _norm_cdf(d2)


def call_delta(S: float, K: float, dte: int, sigma: float) -> float:
    T = dte / 365.0
    d1, _ = _d1_d2(S, K, T, sigma)
    if d1 is None:
        return 1.0 if S > K else 0.0
    return math.exp(-Q * T) * _norm_cdf(d1)


def find_strike_for_delta(S: float, dte: int, sigma: float, target_delta: float) -> float:
    """Binary search call strike to match target delta."""
    lo, hi = S * 0.5, S * 1.6
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        d = call_delta(S, mid, dte, sigma)
        if abs(d - target_delta) < 1e-4:
            return mid
        if d > target_delta:
            lo = mid
        else:
            hi = mid
    return mid


# --- SPX + VIX history loaders ---

def load_spx_history() -> dict[str, float]:
    cache = ROOT / "data" / "q042_spx_history_cache.json"
    if cache.exists():
        try:
            with open(cache) as f:
                d = json.load(f)
            hist = d["full"]["payload"]["history"]
            return {r["date"]: float(r["close"]) for r in hist}
        except (KeyError, json.JSONDecodeError):
            pass
    import yfinance as yf
    df = yf.Ticker("^GSPC").history(start="2003-01-01", end="2026-06-15", auto_adjust=True)
    return {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}


def load_vix_history() -> dict[str, float]:
    cache = ROOT / "data" / "q042_vix_history_cache.json"
    if cache.exists():
        try:
            with open(cache) as f:
                d = json.load(f)
            key = "full" if "full" in d else list(d.keys())[0]
            payload = d[key]["payload"]
            hist = payload.get("history") or (payload.get("payload") or {}).get("history") or []
            return {r["date"]: float(r["close"]) for r in hist}
        except (KeyError, json.JSONDecodeError):
            pass
    import yfinance as yf
    df = yf.Ticker("^VIX").history(start="2003-01-01", end="2026-06-15", auto_adjust=True)
    return {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}


# --- BCD trade simulation ---

def find_next_trading_day(target: date, hist: dict[str, float], max_skip: int = 5) -> str | None:
    d = target
    for _ in range(max_skip):
        iso = d.isoformat()
        if iso in hist:
            return iso
        d += timedelta(days=1)
    return None


def simulate_bcd_trade(entry_iso: str, spx: dict, vix: dict) -> dict | None:
    """Construct and walk forward a BCD position."""
    if entry_iso not in spx or entry_iso not in vix:
        return None
    S0 = spx[entry_iso]
    sigma0 = vix[entry_iso] / 100.0
    if sigma0 <= 0:
        return None

    long_K = find_strike_for_delta(S0, LONG_DTE, sigma0, LONG_DELTA_TARGET)
    short_K = find_strike_for_delta(S0, SHORT_DTE, sigma0, SHORT_DELTA_TARGET)
    long_K_r = round(long_K / 5) * 5  # SPX strikes are multiples of 5
    short_K_r = round(short_K / 5) * 5

    long_premium_entry = call_price(S0, long_K_r, LONG_DTE, sigma0)
    short_premium_entry = call_price(S0, short_K_r, SHORT_DTE, sigma0)
    entry_debit_per_share = long_premium_entry - short_premium_entry
    if entry_debit_per_share <= 0:
        return None  # degenerate

    # Walk forward day by day
    entry_dt = date.fromisoformat(entry_iso)
    exit_dt = None
    exit_long_value = None
    exit_short_value = None
    hold_days = 0
    short_dte_remaining = SHORT_DTE
    long_dte_remaining = LONG_DTE
    cur_S = S0
    cur_sigma = sigma0

    cur_dt = entry_dt
    for delta_days in range(1, 50):  # max 50 calendar days
        cur_dt = entry_dt + timedelta(days=delta_days)
        cur_iso = cur_dt.isoformat()

        # Decrement DTE
        short_dte_remaining = max(0, SHORT_DTE - delta_days)
        long_dte_remaining = max(0, LONG_DTE - delta_days)

        # Update spot + sigma if data exists; otherwise hold
        if cur_iso in spx:
            cur_S = spx[cur_iso]
        if cur_iso in vix:
            cur_sigma = vix[cur_iso] / 100.0

        # Roll trigger: short DTE reaches ROLL_AT_DTE
        if short_dte_remaining <= ROLL_AT_DTE:
            # Only execute exit on a trading day
            if cur_iso in spx:
                exit_dt = cur_dt
                exit_long_value = call_price(cur_S, long_K_r, long_dte_remaining, cur_sigma)
                exit_short_value = call_price(cur_S, short_K_r, short_dte_remaining, cur_sigma)
                hold_days = delta_days
                break

    if exit_dt is None:
        return None

    # PnL per share: SELL short (short_premium_entry) - close short at exit_short_value;
    # BUY long (long_premium_entry) - close long at exit_long_value.
    # Net PnL = (long_exit - long_entry) - (short_exit - short_entry)
    pnl_per_share = (exit_long_value - long_premium_entry) - (exit_short_value - short_premium_entry)

    # Per-contract = per_share × 100
    return {
        "entry_date":         entry_iso,
        "exit_date":          exit_dt.isoformat(),
        "hold_days":          hold_days,
        "entry_spx":          round(S0, 2),
        "exit_spx":           round(cur_S, 2),
        "entry_vix":          round(sigma0 * 100, 2),
        "exit_vix":           round(cur_sigma * 100, 2),
        "long_strike":        long_K_r,
        "short_strike":       short_K_r,
        "long_entry_prem":    round(long_premium_entry, 2),
        "short_entry_prem":   round(short_premium_entry, 2),
        "long_exit_prem":     round(exit_long_value, 2),
        "short_exit_prem":    round(exit_short_value, 2),
        "entry_debit_per_share": round(entry_debit_per_share, 2),
        "entry_debit_usd":    round(entry_debit_per_share * 100, 2),
        "pnl_per_share":      round(pnl_per_share, 2),
        "pnl_usd":            round(pnl_per_share * 100, 2),
        "period_roe":         round(pnl_per_share / entry_debit_per_share, 4),
    }


def main():
    print("Loading SPX history...")
    spx_hist = load_spx_history()
    print(f"  SPX rows: {len(spx_hist)}")

    print("Loading VIX history...")
    vix_hist = load_vix_history()
    print(f"  VIX rows: {len(vix_hist)}")

    print("Loading signal history...")
    bcd_days = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            if r["strategy_key"] == "bull_call_diagonal":
                bcd_days.append(r)
    print(f"  BCD-eligible days: {len(bcd_days)}")

    # Apply sequential ladder logic: only open a NEW BCD if previous one's exit
    # date has passed. This mirrors the matrix-deployed behavior (one BCD at a time).
    trades = []
    last_exit_date = None
    skipped_overlap = 0
    skipped_missing = 0
    for r in bcd_days:
        entry_iso = r["date"]
        if last_exit_date is not None and entry_iso <= last_exit_date:
            skipped_overlap += 1
            continue
        trade = simulate_bcd_trade(entry_iso, spx_hist, vix_hist)
        if trade is None:
            skipped_missing += 1
            continue
        # Enrich with signal_history regime info
        trade["ivp"] = float(r["ivp"]) if r["ivp"] else None
        trade["iv_signal"] = r["iv_signal"]
        trade["regime"] = r["regime"]
        trade["trend"] = r["trend"]
        trades.append(trade)
        last_exit_date = trade["exit_date"]

    print(f"  Skipped (overlap with prior trade): {skipped_overlap}")
    print(f"  Skipped (missing data): {skipped_missing}")
    print(f"  Total synthetic BCD trades: {len(trades)}")

    if not trades:
        print("ERROR: no trades produced")
        return

    # Save trade-level CSV
    with open(TRADES_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
        w.writeheader()
        w.writerows(trades)
    print(f"\nwrote {TRADES_OUT}")

    # Summary stats
    pnls = [t["pnl_usd"] for t in trades]
    rois = [t["period_roe"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"Trades: {len(trades)}  Date range: {trades[0]['entry_date']} → {trades[-1]['entry_date']}")
    print(f"Win rate:    {wins}/{len(trades)} = {100*wins/len(trades):.1f}%")
    print(f"PnL ($):     mean={mean(pnls):>+8,.0f}  median={median(pnls):>+8,.0f}  worst={min(pnls):>+8,.0f}")
    print(f"Period ROE:  mean={mean(rois):>+7.2%}  median={median(rois):>+7.2%}  worst={min(rois):>+7.2%}")
    print(f"Hold days:   median={median([t['hold_days'] for t in trades])}")
    print(f"Entry debit: median=${median([t['entry_debit_usd'] for t in trades]):,.0f}")


if __name__ == "__main__":
    main()
