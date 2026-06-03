"""Q083 P1 — Counterfactual BPS PnL on state (c) days.

For each of 357 state (c) days (IVR-allows but IVP-blocks), synthesize a
BPS trade that WOULD have opened. Use selector's BPS NORMAL params:
  - 30 DTE entry
  - Short put δ = 0.30 (= call δ 0.70 at same strike)
  - Long put δ = 0.15 (= call δ 0.85)
  - Hold to 21 DTE roll OR 60% profit (min 10 days) OR stop
  - Width is what those deltas give (~25-50 SPX points)

BS-flat IV (σ = VIX/100) same methodology as Q082 P6. Caveats apply per
Q082 (skew underestimation, term-structure approximation) but the
comparison is relative — same methodology in both this counterfactual
and Q081's actual BPS backtest.

Output:
  q083_p1_counterfactual_trades.csv (per-trade detail)
  q083_p1_stratified.csv (by IVP zone + 252d range + forward direction)
  q083_p1_memo.md (separate)
"""
from __future__ import annotations
import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
ASSIGN = ROOT / "research" / "q083" / "q083_p0_state_assignments.csv"
TRADES_OUT = ROOT / "research" / "q083" / "q083_p1_counterfactual_trades.csv"
STRAT_OUT = ROOT / "research" / "q083" / "q083_p1_stratified.csv"

# BPS NORMAL params (per strategy/catalog.py "bull_put_spread")
DTE_ENTRY            = 30
DTE_ROLL             = 21
HOLD_PROFIT_TARGET   = 0.60   # 60% of credit
HOLD_MIN_DAYS_FOR_TP = 10     # must hold ≥10 days before profit target fires
SHORT_PUT_DELTA      = 0.30
LONG_PUT_DELTA       = 0.15

# BS constants
R = 0.05
Q_DIV = 0.013


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _d1_d2(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or K <= 0 or S <= 0:
        return None, None
    d1 = (math.log(S/K) + (R - Q_DIV + 0.5*sigma*sigma)*T) / (sigma*math.sqrt(T))
    return d1, d1 - sigma*math.sqrt(T)


def call_price(S, K, dte, sigma):
    T = dte / 365.0
    d1, d2 = _d1_d2(S, K, T, sigma)
    if d1 is None:
        return max(S - K, 0)
    return S*math.exp(-Q_DIV*T)*_norm_cdf(d1) - K*math.exp(-R*T)*_norm_cdf(d2)


def put_price(S, K, dte, sigma):
    T = dte / 365.0
    d1, d2 = _d1_d2(S, K, T, sigma)
    if d1 is None:
        return max(K - S, 0)
    return K*math.exp(-R*T)*_norm_cdf(-d2) - S*math.exp(-Q_DIV*T)*_norm_cdf(-d1)


def call_delta(S, K, dte, sigma):
    T = dte / 365.0
    d1, _ = _d1_d2(S, K, T, sigma)
    if d1 is None:
        return 1.0 if S > K else 0.0
    return math.exp(-Q_DIV*T) * _norm_cdf(d1)


def find_strike_for_put_delta(S, dte, sigma, target_put_delta_abs):
    """Find put strike where |put_delta| = target_put_delta_abs.

    For put, delta is negative. |Δ_put| = 1 - Δ_call (when q≈0).
    So we want call_delta = 1 - target_put_delta_abs.
    """
    target_call_delta = 1.0 - target_put_delta_abs
    lo, hi = S * 0.5, S * 1.1
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        d = call_delta(S, mid, dte, sigma)
        if abs(d - target_call_delta) < 1e-4:
            return mid
        if d > target_call_delta:
            lo = mid  # need lower strike → higher call delta (counterintuitive: lower K = higher call delta)
        else:
            hi = mid
    return mid


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
    df = yf.Ticker("^GSPC").history(start="1999-01-01", end="2026-06-15", auto_adjust=True)
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
    df = yf.Ticker("^VIX").history(start="1999-01-01", end="2026-06-15", auto_adjust=True)
    return {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}


def simulate_bps_trade(entry_iso, spx, vix):
    """Construct + walk forward a BPS position. Return None if can't price."""
    if entry_iso not in spx or entry_iso not in vix:
        return None
    S0 = spx[entry_iso]
    sigma0 = vix[entry_iso] / 100.0
    if sigma0 <= 0:
        return None

    short_K = find_strike_for_put_delta(S0, DTE_ENTRY, sigma0, SHORT_PUT_DELTA)
    long_K  = find_strike_for_put_delta(S0, DTE_ENTRY, sigma0, LONG_PUT_DELTA)
    short_K_r = round(short_K / 5) * 5
    long_K_r  = round(long_K / 5) * 5
    width = short_K_r - long_K_r
    if width <= 0:
        return None

    short_entry_prem = put_price(S0, short_K_r, DTE_ENTRY, sigma0)
    long_entry_prem  = put_price(S0, long_K_r, DTE_ENTRY, sigma0)
    credit = short_entry_prem - long_entry_prem  # per share, positive
    if credit <= 0:
        return None
    max_loss = width - credit  # per share

    # Walk forward
    entry_dt = date.fromisoformat(entry_iso)
    cur_S = S0
    cur_sigma = sigma0
    short_dte = DTE_ENTRY
    long_dte = DTE_ENTRY

    exit_reason = None
    exit_pnl_per_share = None
    hold_days = 0

    for delta_days in range(1, 50):
        cur_dt = entry_dt + timedelta(days=delta_days)
        cur_iso = cur_dt.isoformat()
        if cur_iso in spx:
            cur_S = spx[cur_iso]
        if cur_iso in vix:
            cur_sigma = vix[cur_iso] / 100.0
        short_dte = max(0, DTE_ENTRY - delta_days)
        long_dte = max(0, DTE_ENTRY - delta_days)

        if cur_iso not in spx:
            continue

        # Mark to market
        short_now = put_price(cur_S, short_K_r, short_dte, cur_sigma)
        long_now  = put_price(cur_S, long_K_r, long_dte, cur_sigma)
        mtm_credit = short_now - long_now  # cost to close
        # PnL per share = credit_received - cost_to_close
        mtm_pnl = credit - mtm_credit

        # Exit rule 1: 60% profit after min 10 days
        if delta_days >= HOLD_MIN_DAYS_FOR_TP and mtm_pnl >= HOLD_PROFIT_TARGET * credit:
            exit_reason = "profit_target"
            exit_pnl_per_share = mtm_pnl
            hold_days = delta_days
            break

        # Exit rule 2: short DTE reaches roll threshold (21 DTE)
        if short_dte <= DTE_ROLL:
            exit_reason = "dte_roll"
            exit_pnl_per_share = mtm_pnl
            hold_days = delta_days
            break

        # Exit rule 3: stop at 2× credit loss (per BPS_HV convention; not in BPS NORMAL spec but conservative)
        if mtm_pnl <= -2.0 * credit:
            exit_reason = "stop_loss"
            exit_pnl_per_share = mtm_pnl
            hold_days = delta_days
            break

    if exit_pnl_per_share is None:
        return None

    return {
        "entry":               entry_iso,
        "exit_days":           hold_days,
        "exit_reason":         exit_reason,
        "entry_spx":           round(S0, 2),
        "entry_vix":           round(sigma0 * 100, 2),
        "exit_spx":            round(cur_S, 2),
        "exit_vix":            round(cur_sigma * 100, 2),
        "short_strike":        short_K_r,
        "long_strike":         long_K_r,
        "width":               width,
        "credit_per_share":    round(credit, 2),
        "max_loss_per_share":  round(max_loss, 2),
        "pnl_per_share":       round(exit_pnl_per_share, 2),
        "pnl_usd":             round(exit_pnl_per_share * 100, 2),
        "roe_on_max_loss":     round(exit_pnl_per_share / max_loss, 4),
        "win":                 exit_pnl_per_share > 0,
    }


def _252d_range_at(date_iso, vix):
    """Compute 252d VIX range width as of date_iso."""
    d = date.fromisoformat(date_iso)
    # Get up to 252 prior values
    iso_list = sorted([k for k in vix.keys() if k < date_iso])[-252:]
    if len(iso_list) < 100:
        return None
    vals = [vix[i] for i in iso_list]
    return max(vals) - min(vals)


def main():
    print("Loading state (c) days from P0 assignments...")
    state_c_days = []
    with open(ASSIGN) as f:
        for r in csv.DictReader(f):
            if r["state"] == "c_ivp_blocks":
                state_c_days.append(r)
    print(f"  state (c) days: {len(state_c_days)}")

    print("Loading SPX + VIX history...")
    spx = load_spx_history()
    vix = load_vix_history()
    print(f"  SPX: {len(spx)} rows, VIX: {len(vix)} rows")

    print("Simulating counterfactual BPS trades...")
    trades = []
    skipped = 0
    for r in state_c_days:
        t = simulate_bps_trade(r["date"], spx, vix)
        if t is None:
            skipped += 1
            continue
        # Enrich with state-day metadata
        try:
            ivp = float(r["ivp"])
            ivr = float(r["ivr"]) if r["ivr"] else None
        except (TypeError, ValueError):
            ivp = None
            ivr = None
        range_252d = _252d_range_at(r["date"], vix)
        t["state_ivp"]    = round(ivp, 1) if ivp is not None else None
        t["state_ivr"]    = round(ivr, 1) if ivr is not None else None
        t["state_iv_signal"] = r["iv_signal"]
        t["range_252d"]   = round(range_252d, 2) if range_252d else None
        t["year"]         = r["year"]
        trades.append(t)
    print(f"  trades synthesized: {len(trades)}  (skipped {skipped} due to missing data)")

    with open(TRADES_OUT, "w", newline="") as f:
        if trades:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
            w.writeheader()
            w.writerows(trades)
    print(f"wrote {TRADES_OUT}")

    if not trades:
        print("ERROR: no trades produced")
        return

    # Aggregate stats
    pnls = [t["pnl_per_share"] for t in trades]
    rois = [t["roe_on_max_loss"] for t in trades]
    wins = sum(1 for t in trades if t["win"])
    print()
    print("=" * 80)
    print("AGGREGATE COUNTERFACTUAL BPS PnL (state (c) days, n={})".format(len(trades)))
    print("=" * 80)
    print(f"  Win rate:       {wins}/{len(trades)} = {100*wins/len(trades):.1f}%")
    print(f"  Mean PnL/share: {mean(pnls):>+8.2f}  (×100 = ${mean(pnls)*100:>+8.0f} per contract)")
    print(f"  Median:         {median(pnls):>+8.2f}")
    print(f"  Std:            {stdev(pnls):>8.2f}")
    print(f"  Worst:          {min(pnls):>+8.2f}  (${min(pnls)*100:>+8.0f})")
    print(f"  Best:           {max(pnls):>+8.2f}")
    print(f"  Mean ROE (on max_loss): {mean(rois):>+7.2%}")
    print(f"  Median ROE:             {median(rois):>+7.2%}")

    # Stratification
    print()
    print("=" * 80)
    print("STRATIFIED (per memory feedback_strategy_metrics_pack)")
    print("=" * 80)
    strat_rows = []

    def show(label, ts):
        if not ts:
            print(f"  {label:<45} (empty)")
            return
        p = [t["pnl_per_share"] for t in ts]
        r = [t["roe_on_max_loss"] for t in ts]
        wr = sum(1 for t in ts if t["win"]) / len(ts)
        print(f"  {label:<45} n={len(ts):>3} mean={mean(p):>+7.2f} med={median(p):>+7.2f} "
              f"worst={min(p):>+7.2f} win_rate={wr:>5.1%} ROE={mean(r):>+6.2%}")
        strat_rows.append({
            "stratum":     label,
            "n":           len(ts),
            "mean_pnl":    round(mean(p), 4),
            "median_pnl":  round(median(p), 4),
            "worst_pnl":   round(min(p), 4),
            "best_pnl":    round(max(p), 4),
            "win_rate":    round(wr, 4),
            "mean_roe":    round(mean(r), 4),
        })

    print("\nBy IVP zone (the blocked band):")
    for lo, hi in [(0, 15), (15, 25), (25, 33), (33, 40)]:
        sub = [t for t in trades if t["state_ivp"] is not None and lo <= t["state_ivp"] < hi]
        show(f"IVP [{lo}, {hi})", sub)

    print("\nBy 252d VIX range width:")
    valid = [t for t in trades if t["range_252d"] is not None]
    if valid:
        widths = sorted(t["range_252d"] for t in valid)
        q33 = widths[len(widths)//3]
        q67 = widths[2*len(widths)//3]
        print(f"  range tertiles: narrow < {q33:.1f}, mid {q33:.1f}-{q67:.1f}, wide ≥ {q67:.1f}")
        for label, fn in [
            (f"narrow (252d width < {q33:.1f})", lambda t: t["range_252d"] < q33),
            (f"mid    (252d width {q33:.1f}-{q67:.1f})", lambda t: q33 <= t["range_252d"] < q67),
            (f"wide   (252d width ≥ {q67:.1f})", lambda t: t["range_252d"] >= q67),
        ]:
            sub = [t for t in valid if fn(t)]
            show(label, sub)

    print("\nBy year (top 10 years by n):")
    by_year = defaultdict(list)
    for t in trades:
        by_year[t["year"]].append(t)
    for yr in sorted(by_year, key=lambda y: -len(by_year[y]))[:10]:
        show(f"year {yr}", by_year[yr])

    print("\nAll aggregate (baseline)")
    show("ALL n=" + str(len(trades)), trades)

    with open(STRAT_OUT, "w", newline="") as f:
        if strat_rows:
            w = csv.DictWriter(f, fieldnames=list(strat_rows[0].keys()))
            w.writeheader()
            w.writerows(strat_rows)
    print(f"\nwrote {STRAT_OUT}")

    # Verdict signal
    print()
    print("=" * 80)
    print("VERDICT SIGNAL (H1 / H2 / H3 indicator)")
    print("=" * 80)
    mean_pnl = mean(pnls)
    sortino_thresh = math.sqrt(sum(min(p, 0)**2 for p in pnls) / len(pnls))
    sortino = mean_pnl / sortino_thresh if sortino_thresh > 0 else float("inf")
    sharpe = mean_pnl / stdev(pnls) if stdev(pnls) > 0 else float("inf")
    print(f"  Aggregate mean PnL: ${mean_pnl*100:>+7.0f} per contract")
    print(f"  Sharpe: {sharpe:+.3f}")
    print(f"  Sortino: {sortino:+.3f}")
    print()
    if mean_pnl < 0 or sharpe < 0.2:
        print("  → H1 INDICATED: gate appears to be real protection (counterfactual PnL ≤ 0 / Sharpe weak)")
    elif mean_pnl > 0 and sortino > 0.5:
        print("  → H2 or H3 INDICATED: counterfactual edge positive AND tail acceptable → gate over-restrictive")
    else:
        print("  → MIXED: P2 stratification needed to determine H2 vs H3")


if __name__ == "__main__":
    main()
