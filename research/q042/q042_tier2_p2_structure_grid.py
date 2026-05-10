"""Q042 Tier 2 — P2 Structure grid with skew haircut.

Tier 1 winner: ATM/+5% call spread DTE 90.
Tier 2 P2 expands the structure space:
  - DTE: 30, 60, 90, 120
  - Strike combos:
    * Call spread: ATM/+3%, ATM/+5%, ATM/+8%, ATM/+10%
    * Long ATM call (no short)
    * LEAP ATM (DTE 365)
    * LEAP Δ0.30 (DTE 365)
    * Ratio call spread 1×2: long ATM, short 2× +5%
    * Risk reversal: long ATM call, short ATM put (skip if undefined risk; account-PM context = OK but BP huge)

Pricing: BS with σ = max(VIX/100, 0.10) — IV surface skew approximation:
  - ATM call IV ≈ VIX × 1.00 (baseline)
  - OTM call IV ≈ VIX × 0.85 (call skew haircut, calls trade ~15% below ATM)
  - OTM put IV ≈ VIX × 1.15 (put skew premium)
  - Term structure: short DTE → +10% multiplier (vol of vol higher near-dated); LEAP → -5% (long-dated calmer)

Triggers tested: dd10+ma50_reclaim, dd12+ma50_reclaim, dd15 naive (P1 finalists)

Output: $/$100 BP / day per structure × trigger combination.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[2]
SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"


def load() -> tuple[pd.DataFrame, pd.Series]:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    return (
        spx.loc["2007-01-01":"2026-05-08"].copy(),
        vix.loc["2007-01-01":"2026-05-08"]["Close"].copy(),
    )


def first_triggers(condition: pd.Series) -> pd.DatetimeIndex:
    fired = condition & ~condition.shift(1).fillna(False)
    return condition.index[fired]


def build_features(spx: pd.DataFrame, vix: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["ma50"] = df["close"].rolling(50).mean()
    df["vix"] = vix.reindex(df.index).ffill()
    return df


def find_entries(df: pd.DataFrame, dd_thr: float, confirmation: str) -> pd.DatetimeIndex:
    triggers = first_triggers(df["dd60"] <= -dd_thr)
    if confirmation == "none":
        return triggers
    entries = []
    for td in triggers:
        window = df.loc[td:].iloc[:30]
        if window.empty:
            continue
        if confirmation == "ma50_reclaim":
            ok = window[window["close"] > window["ma50"]]
        else:
            raise ValueError(confirmation)
        if not ok.empty:
            entries.append(ok.index[0])
    return pd.DatetimeIndex(entries).unique()


# ─── Pricing with skew haircut ──────────────────────────────────────────────


def term_multiplier(dte: int) -> float:
    """Term-structure multiplier on σ. Short DTE noisier, long DTE calmer."""
    if dte <= 45:
        return 1.10
    if dte <= 120:
        return 1.00
    return 0.95


def skew_multiplier(moneyness: float) -> float:
    """SPX skew approx: OTM puts ~+15%, OTM calls ~-15%, ATM = 1.0.

    moneyness = K/S (1.0 = ATM, >1 = OTM call, <1 = OTM put).
    Linear ramp: 1.0 → 1.0; 1.05 → 0.93; 1.10 → 0.85.
                 0.95 → 1.07; 0.90 → 1.15.
    """
    if moneyness >= 1.0:
        # OTM call — haircut
        delta = min(moneyness - 1.0, 0.10)
        return 1.0 - 1.5 * delta  # 1.0 at ATM, 0.85 at +10%
    else:
        delta = min(1.0 - moneyness, 0.10)
        return 1.0 + 1.5 * delta  # 1.0 at ATM, 1.15 at -10%


def bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    if T <= 0:
        return max(0.0, S - K)
    if sigma <= 0:
        return max(0.0, S - K * np.exp(-r * T))
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def strike_for_delta(S: float, T: float, sigma: float, target_delta: float, r: float = 0.04) -> float:
    d1 = norm.ppf(target_delta)
    log_ratio = d1 * sigma * np.sqrt(T) - (r + 0.5 * sigma**2) * T
    return S / np.exp(log_ratio)


def price_with_skew(S: float, K: float, T: float, vix: float, dte: int, r: float = 0.04) -> float:
    """BS price with skew-adjusted σ based on K/S moneyness."""
    sigma_atm = max(vix / 100.0, 0.10) * term_multiplier(dte)
    sigma_k = sigma_atm * skew_multiplier(K / S)
    return bs_call(S, K, T, sigma_k, r)


# ─── Structure definitions ──────────────────────────────────────────────────


def price_long_call(S: float, vix: float, dte: int) -> tuple[float, float, float]:
    """Returns (premium, K, BP) for long ATM call."""
    K = S
    T = dte / 365
    prem = price_with_skew(S, K, T, vix, dte)
    return prem, K, prem


def price_call_spread(S: float, vix: float, dte: int, otm_pct: float) -> tuple[float, float, float, float]:
    """Returns (net_debit, K_long, K_short, BP=net_debit) for ATM/+otm_pct% spread."""
    K_long = S
    K_short = S * (1 + otm_pct)
    T = dte / 365
    p_long = price_with_skew(S, K_long, T, vix, dte)
    p_short = price_with_skew(S, K_short, T, vix, dte)
    net = p_long - p_short
    return net, K_long, K_short, net


def price_ratio_spread(S: float, vix: float, dte: int) -> tuple[float, float, float, float]:
    """Returns (net_debit, K_long, K_short, BP) for 1× long ATM / 2× short +5% call.

    BP for naked-style ratio in PM = max possible loss between K_short and infinity.
    But for Tier 2, conservative estimate: BP = net_debit + (K_short - K_long) (max gain
    point is K_short; beyond K_short, naked short eats into.) For real PM margin would
    be much higher due to undefined upside; flag this caveat.
    """
    K_long = S
    K_short = S * 1.05
    T = dte / 365
    p_long = price_with_skew(S, K_long, T, vix, dte)
    p_short = price_with_skew(S, K_short, T, vix, dte)
    net_debit = p_long - 2 * p_short  # could be negative (credit)
    # Approximate PM BP: ~20% notional of the naked short leg as initial margin proxy
    bp_proxy = 0.20 * S * 2  # 2 short calls, 20% naked margin approx
    return net_debit, K_long, K_short, bp_proxy


# ─── Forward S calculation ──────────────────────────────────────────────────


def forward_close(df: pd.DataFrame, entry_date: pd.Timestamp, dte: int) -> float | None:
    """Return SPX close at expiry approx (entry + dte calendar days, find next trading day)."""
    target = entry_date + pd.Timedelta(days=dte)
    future = df.loc[entry_date:].loc[target:]
    if future.empty:
        # Fallback: last available
        future_all = df.loc[entry_date:]
        if len(future_all) >= dte * 252 // 365:
            return float(future_all["close"].iloc[min(len(future_all) - 1, dte * 252 // 365)])
        return None
    return float(future["close"].iloc[0])


# ─── Evaluation ─────────────────────────────────────────────────────────────


def evaluate_structure(df: pd.DataFrame, entries: pd.DatetimeIndex, structure_name: str, dte: int, **kwargs) -> dict:
    pnls_pct_bp = []  # PnL per $100 BP, full period
    pnls_bp_day = []  # PnL per $100 BP per day
    skipped = 0

    for entry in entries:
        if entry not in df.index:
            continue
        S = float(df.loc[entry, "close"])
        vix = float(df.loc[entry, "vix"])
        if np.isnan(vix):
            skipped += 1
            continue
        S_T = forward_close(df, entry, dte)
        if S_T is None:
            skipped += 1
            continue

        if structure_name == "long_atm":
            prem, K, BP = price_long_call(S, vix, dte)
            payoff = max(0.0, S_T - K)
            net = payoff - prem
        elif structure_name.startswith("spread_"):
            otm_pct = kwargs["otm_pct"]
            net_debit, K_long, K_short, BP = price_call_spread(S, vix, dte, otm_pct)
            long_payoff = max(0.0, S_T - K_long)
            short_payoff = max(0.0, S_T - K_short)
            net = (long_payoff - short_payoff) - net_debit
        elif structure_name == "ratio_1x2":
            net_debit, K_long, K_short, BP = price_ratio_spread(S, vix, dte)
            long_payoff = max(0.0, S_T - K_long)
            short_payoff = max(0.0, S_T - K_short)
            net = long_payoff - 2 * short_payoff - net_debit
        elif structure_name == "leap_atm":
            prem, K, BP = price_long_call(S, vix, dte)
            payoff = max(0.0, S_T - K)
            net = payoff - prem
        elif structure_name == "leap_d30":
            sigma_atm = max(vix / 100.0, 0.10) * term_multiplier(dte)
            T = dte / 365
            K = strike_for_delta(S, T, sigma_atm, 0.30)
            prem = price_with_skew(S, K, T, vix, dte)
            BP = prem
            payoff = max(0.0, S_T - K)
            net = payoff - prem
        else:
            raise ValueError(structure_name)

        if BP <= 0:
            skipped += 1
            continue
        pnl_pct_bp = net / BP * 100
        pnl_bp_day = pnl_pct_bp / dte
        pnls_pct_bp.append(pnl_pct_bp)
        pnls_bp_day.append(pnl_bp_day)

    if not pnls_pct_bp:
        return {"n": 0}

    arr = np.array(pnls_pct_bp)
    bd = np.array(pnls_bp_day)
    return {
        "n": len(arr),
        "median_$_per_$100BP": float(np.median(arr)),
        "avg_$_per_$100BP": float(np.mean(arr)),
        "win_rate": float((arr > 0).mean()),
        "worst": float(np.min(arr)),
        "best": float(np.max(arr)),
        "median_$bp_day_per_$100BP": float(np.median(bd)),
        "avg_$bp_day_per_$100BP": float(np.mean(bd)),
        "skipped": skipped,
    }


# ─── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    spx, vix = load()
    df = build_features(spx, vix)

    # P1 finalist triggers
    triggers = {
        "dd10_ma50_reclaim": find_entries(df, 0.10, "ma50_reclaim"),
        "dd12_ma50_reclaim": find_entries(df, 0.12, "ma50_reclaim"),
        "dd15_naive": find_entries(df, 0.15, "none"),
    }
    for name, entries in triggers.items():
        print(f"  {name}: n={len(entries)}")

    # Structure grid
    structures = []
    for dte in [30, 60, 90, 120]:
        for otm_pct in [0.03, 0.05, 0.08, 0.10]:
            structures.append((f"spread_{int(otm_pct*100):02d}pct_dte{dte}", "spread_atm_otm",
                              {"dte": dte, "otm_pct": otm_pct}))
        structures.append((f"long_atm_dte{dte}", "long_atm", {"dte": dte}))
        structures.append((f"ratio_1x2_dte{dte}", "ratio_1x2", {"dte": dte}))
    structures.append(("leap_atm_dte365", "leap_atm", {"dte": 365}))
    structures.append(("leap_d30_dte365", "leap_d30", {"dte": 365}))

    rows = []
    for trig_name, entries in triggers.items():
        for label, kind, params in structures:
            dte = params["dte"]
            if kind == "spread_atm_otm":
                res = evaluate_structure(df, entries, "spread_atm_otm_var", dte=dte, otm_pct=params["otm_pct"])
                # adjust: evaluate_structure expects "spread_*" prefix to read otm_pct kwarg
                res = evaluate_structure(df, entries, f"spread_{int(params['otm_pct']*100)}", dte=dte, otm_pct=params["otm_pct"])
            elif kind == "long_atm":
                res = evaluate_structure(df, entries, "long_atm", dte=dte)
            elif kind == "ratio_1x2":
                res = evaluate_structure(df, entries, "ratio_1x2", dte=dte)
            elif kind == "leap_atm":
                res = evaluate_structure(df, entries, "leap_atm", dte=dte)
            elif kind == "leap_d30":
                res = evaluate_structure(df, entries, "leap_d30", dte=dte)
            else:
                continue
            if res.get("n", 0) > 0:
                rows.append({"trigger": trig_name, "structure": label, **res})

    out = pd.DataFrame(rows)
    out_path = Path(__file__).resolve().parent / "p2_structure_grid.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")

    # Summary: top-5 per trigger by median $/BP-day
    print("\n=== Top-5 structures per trigger (by median $/$100BP/day) ===")
    for trig in triggers:
        sub = out[out["trigger"] == trig].copy()
        sub = sub.sort_values("median_$bp_day_per_$100BP", ascending=False)
        print(f"\n{trig}:")
        print(sub.head(8)[["structure", "n", "median_$_per_$100BP", "win_rate",
                           "median_$bp_day_per_$100BP", "worst"]].to_string(index=False, float_format=lambda x: f"{x:+.3f}" if isinstance(x, float) else str(x)))


if __name__ == "__main__":
    main()
