"""Q083 P7 — Skew bracket on IVP63 trades (G1 Q1 outstanding).

Per Q082 P10 lesson + G1 Q1: BPS is net SHORT vega (opposite Q082 BCD).
Skew steepening in DOWN moves: real short-put IV expands faster than long-put IV.
- Short put: vega ~2-3 per vp, IV expands +Y vp → short-leg cost increases more
- Long put: vega ~1-2 per vp, IV expands +X vp (X < Y due to skew curve)
- For BPS holder (SHORT short put + LONG long put), net effect = MORE loss
- So real BPS edge in DOWN windows is OVERSTATED by BS-flat synth

Bracket: re-simulate IVP63 trades with short-leg σ +5vp at EXIT if SPX
return < -1% (DOWN window). Compare aggregate Sortino & mean.

Method differs from P5's attempt: simulate from scratch with adjusted
σ during exit pricing, not adjust pre-computed PnL.
"""
from __future__ import annotations
import csv
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
OUT = ROOT / "research" / "q083" / "q083_p7_skew_bracket.csv"

# BPS params (mirror P1)
DTE_ENTRY = 30
DTE_ROLL = 21
HOLD_PROFIT_TARGET = 0.60
HOLD_MIN_DAYS_FOR_TP = 10
SHORT_PUT_DELTA = 0.30
LONG_PUT_DELTA = 0.15
R = 0.05
Q_DIV = 0.013


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _d1_d2(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or K <= 0 or S <= 0:
        return None, None
    d1 = (math.log(S/K) + (R - Q_DIV + 0.5*sigma*sigma)*T) / (sigma*math.sqrt(T))
    return d1, d1 - sigma*math.sqrt(T)


def call_delta(S, K, dte, sigma):
    T = dte / 365.0
    d1, _ = _d1_d2(S, K, T, sigma)
    if d1 is None:
        return 1.0 if S > K else 0.0
    return math.exp(-Q_DIV*T) * _norm_cdf(d1)


def put_price(S, K, dte, sigma):
    T = dte / 365.0
    d1, d2 = _d1_d2(S, K, T, sigma)
    if d1 is None:
        return max(K - S, 0)
    return K*math.exp(-R*T)*_norm_cdf(-d2) - S*math.exp(-Q_DIV*T)*_norm_cdf(-d1)


def find_strike_put_delta(S, dte, sigma, target_put_delta_abs):
    target_call_delta = 1.0 - target_put_delta_abs
    lo, hi = S * 0.5, S * 1.1
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        d = call_delta(S, mid, dte, sigma)
        if abs(d - target_call_delta) < 1e-4:
            return mid
        if d > target_call_delta:
            lo = mid
        else:
            hi = mid
    return mid


def simulate_bps_with_skew(entry_iso, spx, vix, skew_short_bump=0.0):
    """Walk-forward BPS sim. If skew_short_bump > 0, bump short-leg σ by
    that amount (in absolute vp/100) WHEN EXIT condition encounters DOWN move."""
    if entry_iso not in spx or entry_iso not in vix:
        return None
    S0 = spx[entry_iso]
    sigma0 = vix[entry_iso] / 100.0
    if sigma0 <= 0:
        return None

    short_K = round(find_strike_put_delta(S0, DTE_ENTRY, sigma0, SHORT_PUT_DELTA) / 5) * 5
    long_K = round(find_strike_put_delta(S0, DTE_ENTRY, sigma0, LONG_PUT_DELTA) / 5) * 5
    width = short_K - long_K
    if width <= 0:
        return None

    short_entry = put_price(S0, short_K, DTE_ENTRY, sigma0)
    long_entry = put_price(S0, long_K, DTE_ENTRY, sigma0)
    credit = short_entry - long_entry
    if credit <= 0:
        return None

    entry_dt = date.fromisoformat(entry_iso)
    cur_S = S0
    cur_sigma = sigma0
    short_dte = DTE_ENTRY
    long_dte = DTE_ENTRY

    exit_pnl = None
    hold = 0
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

        # Determine if this is a DOWN move from entry for skew adjustment
        spx_return = (cur_S - S0) / S0
        is_down = spx_return < -0.01
        short_sigma_eff = cur_sigma + (skew_short_bump if is_down else 0.0)

        short_now = put_price(cur_S, short_K, short_dte, short_sigma_eff)
        long_now = put_price(cur_S, long_K, long_dte, cur_sigma)
        mtm_credit = short_now - long_now
        mtm_pnl = credit - mtm_credit

        if delta_days >= HOLD_MIN_DAYS_FOR_TP and mtm_pnl >= HOLD_PROFIT_TARGET * credit:
            exit_pnl = mtm_pnl; hold = delta_days; break
        if short_dte <= DTE_ROLL:
            exit_pnl = mtm_pnl; hold = delta_days; break
        if mtm_pnl <= -2.0 * credit:
            exit_pnl = mtm_pnl; hold = delta_days; break

    if exit_pnl is None:
        return None
    return {
        "entry": entry_iso, "hold_days": hold,
        "spx_return": round((cur_S - S0) / S0, 4),
        "is_down": (cur_S - S0) / S0 < -0.01,
        "credit_per_share": round(credit, 2),
        "pnl_per_share": round(exit_pnl, 2),
    }


def compute_ivp(vix_values, current_vix):
    if not vix_values: return 50.0
    return 100 * sum(1 for v in vix_values if v < current_vix) / len(vix_values)


def compute_ivr(vix_values, current_vix):
    if not vix_values: return 50.0
    lo, hi = min(vix_values), max(vix_values)
    return 100 * (current_vix - lo) / (hi - lo) if hi > lo else 50.0


def passes_ivp63_gate(iv_signal, ivp):
    if iv_signal not in ("HIGH", "NEUTRAL"): return False
    if iv_signal == "NEUTRAL": return 43 <= ivp <= 55
    return 40 < ivp <= 70


def sortino(values, threshold=0):
    if not values: return float("nan")
    mu = mean(values)
    dd = math.sqrt(sum(min(v-threshold, 0)**2 for v in values) / len(values))
    if dd == 0: return float("inf") if mu > threshold else 0
    return (mu - threshold) / dd


def load_history(ticker):
    import yfinance as yf
    df = yf.Ticker(ticker).history(start="1999-01-01", end="2026-06-15", auto_adjust=True)
    return {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}


def main():
    print("Loading signal + price history...")
    sig_rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            try:
                sig_rows.append({"date": r["date"], "vix": float(r["vix"]),
                                  "regime": r["regime"], "trend": r["trend"]})
            except (ValueError, TypeError):
                continue
    sig_rows.sort(key=lambda r: r["date"])
    spx = load_history("^GSPC")
    vix = load_history("^VIX")
    vix_by_date = {r["date"]: r["vix"] for r in sig_rows}
    dates_sorted = sorted(vix_by_date)
    date_to_idx = {d: i for i, d in enumerate(dates_sorted)}

    # Identify IVP63-allowed days
    print("Identifying IVP63-allowed days...")
    ivp63_days = []
    for r in sig_rows:
        idx = date_to_idx[r["date"]]
        if idx < 252: continue
        if r["regime"] != "NORMAL" or r["trend"] != "BULLISH": continue
        window = [vix_by_date[dates_sorted[j]] for j in range(idx-63, idx)]
        ivp = compute_ivp(window, r["vix"])
        ivr = compute_ivr(window, r["vix"])
        iv_sig = "HIGH" if ivr > 50 else ("LOW" if ivr < 30 else "NEUTRAL")
        if passes_ivp63_gate(iv_sig, ivp):
            ivp63_days.append(r["date"])
    print(f"  IVP63 allowed: {len(ivp63_days)} days")

    # Run baseline (no skew bump) and bracket (+5vp on DOWN short-leg)
    print()
    print("Running baseline (BS-flat) and skew bracket (+5vp short-leg in DOWN)...")
    baseline = []
    bracketed = []
    for d in ivp63_days:
        t_base = simulate_bps_with_skew(d, spx, vix, skew_short_bump=0.0)
        t_brkt = simulate_bps_with_skew(d, spx, vix, skew_short_bump=0.05)
        if t_base and t_brkt:
            baseline.append(t_base)
            bracketed.append(t_brkt)

    print(f"  {len(baseline)} trades in both")
    print()
    print("=" * 78)
    print("Q1 SKEW BRACKET — IVP63 trades")
    print("=" * 78)

    for label, trades in [("BASELINE (BS-flat)", baseline), ("BRACKET (+5vp short σ in DOWN)", bracketed)]:
        if not trades:
            print(f"  {label}: (empty)")
            continue
        pnls = [t["pnl_per_share"] for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        print(f"\n  {label}:")
        print(f"    n={len(trades)} win_rate={100*wins/len(trades):.1f}%")
        print(f"    mean/share = {mean(pnls):>+6.2f}  (${mean(pnls)*100:>+5.0f}/contract)")
        print(f"    median     = {median(pnls):>+6.2f}")
        print(f"    worst      = {min(pnls):>+6.2f}  (${min(pnls)*100:>+5.0f})")
        print(f"    Sortino    = {sortino(pnls):>+6.3f}")

    # Decompose: DOWN-only effect
    down_baseline = [t["pnl_per_share"] for t in baseline if t["is_down"]]
    down_bracket = [t["pnl_per_share"] for t in bracketed if t["is_down"]]
    up_baseline = [t["pnl_per_share"] for t in baseline if not t["is_down"]]
    up_bracket = [t["pnl_per_share"] for t in bracketed if not t["is_down"]]

    print()
    print("Decomposition (DOWN windows are where skew bracket applies):")
    print(f"  Total trades: {len(baseline)}, DOWN: {len(down_baseline)}, UP/FLAT: {len(up_baseline)}")
    if down_baseline:
        print(f"  DOWN windows:")
        print(f"    baseline:  n={len(down_baseline)} mean=${mean(down_baseline)*100:>+5.0f}  Sortino={sortino(down_baseline):>+5.3f}")
        print(f"    bracket:   n={len(down_bracket)} mean=${mean(down_bracket)*100:>+5.0f}  Sortino={sortino(down_bracket):>+5.3f}")
        print(f"    shift: mean ${(mean(down_bracket)-mean(down_baseline))*100:>+5.0f}, "
              f"Sortino {sortino(down_bracket)-sortino(down_baseline):>+5.3f}")
    if up_baseline:
        print(f"  UP/FLAT windows (skew bracket no effect):")
        print(f"    baseline:  n={len(up_baseline)} mean=${mean(up_baseline)*100:>+5.0f}")
        print(f"    bracket:   n={len(up_bracket)} mean=${mean(up_bracket)*100:>+5.0f}")

    # Write
    out_rows = []
    for b, br in zip(baseline, bracketed):
        out_rows.append({
            "entry": b["entry"],
            "is_down": b["is_down"],
            "baseline_pnl": b["pnl_per_share"],
            "bracket_pnl": br["pnl_per_share"],
            "delta_pnl": round(br["pnl_per_share"] - b["pnl_per_share"], 2),
        })
    with open(OUT, "w", newline="") as f:
        if out_rows:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
    print(f"\nwrote {OUT}")

    # Verdict
    print()
    print("=" * 78)
    print("Q1 SKEW VERDICT")
    print("=" * 78)
    p_base = [t["pnl_per_share"] for t in baseline]
    p_brkt = [t["pnl_per_share"] for t in bracketed]
    base_sort = sortino(p_base)
    brkt_sort = sortino(p_brkt)
    haircut_pct = (mean(p_brkt) - mean(p_base)) / abs(mean(p_base)) * 100 if mean(p_base) != 0 else 0
    print(f"  Baseline aggregate mean: ${mean(p_base)*100:>+5.0f}, Sortino {base_sort:+.3f}")
    print(f"  Bracket  aggregate mean: ${mean(p_brkt)*100:>+5.0f}, Sortino {brkt_sort:+.3f}")
    print(f"  Skew haircut on mean: {haircut_pct:+.1f}%")
    print()
    if brkt_sort < 0.5 and base_sort >= 0.5:
        print("  → Skew haircut PUSHES IVP63 Sortino BELOW 0.5 threshold")
        print("    Real-chain BPS edge is materially smaller than BS-flat synth")
    elif brkt_sort >= 0.5:
        print("  → Even with conservative skew bracket, IVP63 Sortino ≥ 0.5")
        print("    Synth edge is robust to skew direction")
    else:
        print("  → Both baseline AND bracket below 0.5 — IVP63 wasn't above threshold to begin with")


if __name__ == "__main__":
    main()
