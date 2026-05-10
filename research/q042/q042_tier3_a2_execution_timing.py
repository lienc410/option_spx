"""Q042 Tier 3 — A2 Execution timing / trigger-to-fill drift sensitivity.

Reviewer's challenge (Q5/Q7): for DTE30 spread, T+0 vs T+1 vs T+2 entry
materially changes economics. Daily OHLC lets us simulate:
  - T_signal_close: entry at signal-day close (Tier 2 baseline; impossible
    in live unless EOD signal is acted on at the auction print)
  - T+1 open: realistic alert-then-execute-next-morning flow
  - T+1 close: alert-but-wait pattern
  - T+2 close: 2-day delay (e.g., weekend or PM travel)

Pricing baseline: same BS + skew + term-multiplier as P2.
Trigger sample: dd12+ma50_reclaim (n=41) and dd15 naive (n=192).

For each entry day variant, compute:
  - net debit at the alternative entry price/IV
  - forward expiry close at original DTE target
  - PnL%
  - aggregate metrics: median, win rate, $/BP-day

Goal: identify whether T+0 → T+1 drift is small (DTE30 acceptable) or
material (forces DTE60+ for production).
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
    df["open"] = spx["Open"]
    df["high"] = spx["High"]
    df["low"] = spx["Low"]
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
        ok = window[window["close"] > window["ma50"]] if confirmation == "ma50_reclaim" else pd.DataFrame()
        if not ok.empty:
            entries.append(ok.index[0])
    return pd.DatetimeIndex(entries).unique()


# Pricing


def term_multiplier(dte: int) -> float:
    if dte <= 45:
        return 1.10
    if dte <= 120:
        return 1.00
    return 0.95


def skew_multiplier(moneyness: float) -> float:
    if moneyness >= 1.0:
        delta = min(moneyness - 1.0, 0.10)
        return 1.0 - 1.5 * delta
    delta = min(1.0 - moneyness, 0.10)
    return 1.0 + 1.5 * delta


def bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    if T <= 0:
        return max(0.0, S - K)
    if sigma <= 0:
        return max(0.0, S - K * np.exp(-r * T))
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def price_with_skew(S: float, K: float, T: float, vix: float, dte: int) -> float:
    sigma_atm = max(vix / 100.0, 0.10) * term_multiplier(dte)
    sigma_k = sigma_atm * skew_multiplier(K / S)
    return bs_call(S, K, T, sigma_k)


def evaluate_with_entry_variant(
    df: pd.DataFrame,
    signal_dates: pd.DatetimeIndex,
    dte: int,
    otm_pct: float,
    entry_variant: str,
) -> pd.DataFrame:
    """Evaluate trades where entry happens at a variant of signal-day timing."""
    rows = []
    for sig in signal_dates:
        if sig not in df.index:
            continue
        # Entry day + price selection
        if entry_variant == "T_close":
            entry_day = sig
            S_entry = float(df.loc[sig, "close"])
        elif entry_variant == "T1_open":
            future = df.loc[sig:].iloc[1:2]
            if future.empty:
                continue
            entry_day = future.index[0]
            S_entry = float(future["open"].iloc[0])
        elif entry_variant == "T1_close":
            future = df.loc[sig:].iloc[1:2]
            if future.empty:
                continue
            entry_day = future.index[0]
            S_entry = float(future["close"].iloc[0])
        elif entry_variant == "T2_close":
            future = df.loc[sig:].iloc[2:3]
            if future.empty:
                continue
            entry_day = future.index[0]
            S_entry = float(future["close"].iloc[0])
        else:
            raise ValueError(entry_variant)

        # Use signal-day VIX (close) as IV reference — could be different from
        # entry-day VIX, but that introduces secondary effect we mostly want
        # to isolate the price drift, not IV drift.
        # For T+1/T+2, however, IV at entry has already moved → use entry-day VIX
        if entry_variant == "T_close":
            vix = float(df.loc[sig, "vix"])
        else:
            vix = float(df.loc[entry_day, "vix"])
        if np.isnan(vix):
            continue

        # Strikes set at signal-day close (broker would lock strikes at order time
        # but for sim we keep strikes consistent across variants for fair compare)
        S_signal = float(df.loc[sig, "close"])
        K_long = S_signal
        K_short = S_signal * (1 + otm_pct)

        T = dte / 365
        # Price the option at the entry-day spot S_entry, with IV at entry-day VIX
        p_long = price_with_skew(S_entry, K_long, T, vix, dte)
        p_short = price_with_skew(S_entry, K_short, T, vix, dte)
        net_debit = p_long - p_short
        if net_debit <= 0:
            continue

        # Expiry: target = entry_day + dte calendar days
        target = entry_day + pd.Timedelta(days=dte)
        future = df.loc[entry_day:].loc[target:]
        if future.empty:
            continue
        S_expiry = float(future["close"].iloc[0])

        long_payoff = max(0.0, S_expiry - K_long)
        short_payoff = max(0.0, S_expiry - K_short)
        spread_payoff = (long_payoff - short_payoff) - net_debit
        rows.append({
            "signal_date": sig,
            "entry_date": entry_day,
            "S_signal": S_signal,
            "S_entry": S_entry,
            "drift_pct": (S_entry / S_signal - 1) * 100,
            "vix": vix,
            "net_debit": net_debit,
            "S_expiry": S_expiry,
            "pnl_pct_bp": spread_payoff / net_debit * 100,
        })
    return pd.DataFrame(rows)


def summary(trades: pd.DataFrame, dte: int) -> dict:
    if trades.empty:
        return {"n": 0}
    pnl = trades["pnl_pct_bp"]
    drift = trades["drift_pct"]
    return {
        "n": len(trades),
        "median_pnl_pct_bp": float(pnl.median()),
        "mean_pnl_pct_bp": float(pnl.mean()),
        "win_rate": float((pnl > 0).mean()),
        "median_$bp_day": float(pnl.median() / dte),
        "drift_median_pct": float(drift.median()),
        "drift_p25_pct": float(drift.quantile(0.25)),
        "drift_p75_pct": float(drift.quantile(0.75)),
    }


def main() -> None:
    spx, vix = load()
    df = build_features(spx, vix)

    triggers = {
        "dd12_ma50_reclaim": find_entries(df, 0.12, "ma50_reclaim"),
        "dd15_naive": find_entries(df, 0.15, "none"),
    }

    print("=" * 100)
    print("A2 — Execution timing / trigger-to-fill drift sensitivity")
    print("=" * 100)

    rows = []
    # Test DTE30 (most timing-sensitive) and DTE90 (likely production winner)
    for dte in [30, 60, 90]:
        for trig_name, signal_dates in triggers.items():
            for variant in ["T_close", "T1_open", "T1_close", "T2_close"]:
                trades = evaluate_with_entry_variant(df, signal_dates, dte, 0.05, variant)
                m = summary(trades, dte)
                m.update({"dte": dte, "trigger": trig_name, "variant": variant})
                rows.append(m)

    out = pd.DataFrame(rows)
    cols = ["dte", "trigger", "variant", "n", "win_rate", "median_pnl_pct_bp",
            "mean_pnl_pct_bp", "median_$bp_day",
            "drift_median_pct", "drift_p25_pct", "drift_p75_pct"]
    print(out[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)))

    out_path = Path(__file__).resolve().parent / "a2_execution_timing.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")

    # Drift summary
    print("\n=== Entry drift summary (S_entry / S_signal − 1) ===")
    for trig in triggers:
        for variant in ["T1_open", "T1_close", "T2_close"]:
            sub = out[(out["trigger"] == trig) & (out["variant"] == variant) & (out["dte"] == 30)]
            if not sub.empty:
                r = sub.iloc[0]
                print(f"  {trig} {variant}: median drift {r['drift_median_pct']:+.2f}% "
                      f"(p25 {r['drift_p25_pct']:+.2f}, p75 {r['drift_p75_pct']:+.2f})")

    # Headline: DTE30 PnL degradation T_close → T+1 close
    print("\n=== T+0 → T+1_close PnL degradation (DTE30) ===")
    for trig in triggers:
        t0 = out[(out["trigger"] == trig) & (out["variant"] == "T_close") & (out["dte"] == 30)].iloc[0]
        t1c = out[(out["trigger"] == trig) & (out["variant"] == "T1_close") & (out["dte"] == 30)].iloc[0]
        delta_med = t1c["median_pnl_pct_bp"] - t0["median_pnl_pct_bp"]
        delta_wr = t1c["win_rate"] - t0["win_rate"]
        print(f"  {trig} DTE30: median PnL {t0['median_pnl_pct_bp']:+.1f} → {t1c['median_pnl_pct_bp']:+.1f} "
              f"(Δ {delta_med:+.1f}/$100BP), win rate {t0['win_rate']*100:.0f}% → {t1c['win_rate']*100:.0f}% "
              f"(Δ {delta_wr*100:+.1f}pp)")

    print("\n=== T+0 → T+1_close PnL degradation (DTE90) ===")
    for trig in triggers:
        t0 = out[(out["trigger"] == trig) & (out["variant"] == "T_close") & (out["dte"] == 90)].iloc[0]
        t1c = out[(out["trigger"] == trig) & (out["variant"] == "T1_close") & (out["dte"] == 90)].iloc[0]
        delta_med = t1c["median_pnl_pct_bp"] - t0["median_pnl_pct_bp"]
        delta_wr = t1c["win_rate"] - t0["win_rate"]
        print(f"  {trig} DTE90: median PnL {t0['median_pnl_pct_bp']:+.1f} → {t1c['median_pnl_pct_bp']:+.1f} "
              f"(Δ {delta_med:+.1f}/$100BP), win rate {t0['win_rate']*100:.0f}% → {t1c['win_rate']*100:.0f}% "
              f"(Δ {delta_wr*100:+.1f}pp)")


if __name__ == "__main__":
    main()
