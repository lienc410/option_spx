"""Q042 Tier 3 — A4 / A5 / A6: re-trigger spacing, SPX vs XSP, account-scale.

Three smaller analyses bundled into one script:

A4 — Re-trigger spacing rule
  Look at gap-days between consecutive Q042 triggers in the dd12+reclaim
  sample. Recommend a min-spacing rule that prevents BP doubling during
  multi-leg drawdowns without missing distinct events.

A5 — SPX vs XSP economics
  Static math:
    SPX:  multiplier 100, $5 strike granularity, contract notional ≈ $500k
    XSP:  multiplier 100 (notional 1/10 of SPX), $1 strike granularity,
          contract notional ≈ $50k
  Compute min-position economics at various account sizes.

A6 — Account-scale activation threshold
  At 1% account / entry, what's the minimum NLV where 1 contract is buyable
  for SPX vs XSP, given the typical net-debit of an ATM/+5% spread DTE 90?
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

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


def a4_retrigger_spacing(df: pd.DataFrame) -> None:
    print("=" * 100)
    print("A4 — Re-trigger spacing rule analysis")
    print("=" * 100)

    for trig_name, dd, conf in [
        ("dd12_ma50_reclaim", 0.12, "ma50_reclaim"),
        ("dd15_naive", 0.15, "none"),
        ("dd10_ma50_reclaim", 0.10, "ma50_reclaim"),
    ]:
        entries = find_entries(df, dd, conf)
        if len(entries) < 2:
            continue
        gaps_days = (entries[1:] - entries[:-1]).days

        print(f"\n--- {trig_name} (n={len(entries)}) ---")
        print(f"  gap distribution: median={np.median(gaps_days):.0f}d, "
              f"p25={np.percentile(gaps_days, 25):.0f}d, "
              f"p75={np.percentile(gaps_days, 75):.0f}d, "
              f"min={np.min(gaps_days):.0f}d, max={np.max(gaps_days):.0f}d")
        print(f"  gaps < 30 days:  {(gaps_days < 30).sum()} of {len(gaps_days)}")
        print(f"  gaps < 60 days:  {(gaps_days < 60).sum()} of {len(gaps_days)}")
        print(f"  gaps < 90 days:  {(gaps_days < 90).sum()} of {len(gaps_days)}")
        print(f"  gaps < 180 days: {(gaps_days < 180).sum()} of {len(gaps_days)}")

        # Show closely-spaced trigger pairs (< 60 days)
        close_pairs = [(entries[i], entries[i+1], gaps_days[i])
                       for i in range(len(gaps_days)) if gaps_days[i] < 60]
        if close_pairs:
            print(f"  closely-spaced (<60d) pairs:")
            for a, b, g in close_pairs[:6]:
                print(f"    {a.date()} → {b.date()}: {g}d apart")

    # Recommendation: min-spacing tied to DTE so trades don't overlap
    print("\n=== Recommendation ===")
    print("For DTE 90 spread, recommend min-spacing ≥ 30 days (don't double up while held).")
    print("For DTE 30 spread, recommend min-spacing ≥ 21 days (~1 trading month).")
    print("Equivalent rule: max 1 active Q042 spread at any time (= no overlap).")


def a5_spx_vs_xsp(df: pd.DataFrame) -> None:
    print("\n" + "=" * 100)
    print("A5 — SPX vs XSP economics")
    print("=" * 100)

    # Recent SPX values for sizing math
    recent_spx = float(df["close"].iloc[-1])
    print(f"Reference SPX = {recent_spx:.0f} (latest available)")

    # ATM/+5% spread DTE 90, with VIX 25 reference (typical Q042 entry vol)
    # rough debit: per Tier 2, ATM call at VIX 25, DTE 90 ≈ S × σ × √T × 0.4 ≈ S × 0.25 × 0.5 × 0.4 = S × 0.05
    # +5% short call ≈ S × 0.04
    # net debit per share ≈ S × 0.01-0.02

    # Per Tier 2 P2 actual data: dd12+reclaim DTE90 net_debit median ≈ 1-2% of S
    # Conservative estimate: 1.5% × S
    debit_pct = 0.015
    debit_per_share = recent_spx * debit_pct

    spx_multiplier = 100
    xsp_multiplier = 100  # XSP also uses 100, but XSP is 1/10 of SPX index value
    xsp_index = recent_spx / 10  # XSP is 1/10 SPX

    spx_debit_per_contract = debit_per_share * spx_multiplier
    xsp_debit_per_contract = (xsp_index * debit_pct) * xsp_multiplier

    print(f"\nTypical net-debit estimate (ATM/+5% spread DTE 90, VIX ~25): {debit_pct*100:.1f}% of underlying")
    print(f"  SPX: ${spx_debit_per_contract:,.0f} per 1 contract (1× SPX multiplier 100)")
    print(f"  XSP: ${xsp_debit_per_contract:,.0f} per 1 contract (1× XSP multiplier 100, index 1/10 of SPX)")

    # Strike granularity
    print(f"\nStrike granularity:")
    print(f"  SPX: $5 spacing → ATM strike rounded to nearest $5 = max strike error ~ ±$2.50 (0.04% of SPX)")
    print(f"  XSP: $1 spacing → ATM strike rounded to nearest $1 = max strike error ~ ±$0.50 (0.07% of XSP)")
    print(f"  Both negligible at the position level.")

    # Bid-ask spreads (rough estimates)
    print(f"\nTypical bid-ask spread (per leg):")
    print(f"  SPX: $0.20-0.50 → 2 legs × 100 = $40-$100 per spread")
    print(f"  XSP: $0.05-0.15 → 2 legs × 100 = $10-$30 per spread")

    # Tax treatment
    print(f"\nTax treatment (US):")
    print(f"  Both SPX and XSP are Section 1256 contracts → 60/40 long/short capital gains, marked-to-market")


def a6_account_scale(df: pd.DataFrame) -> None:
    print("\n" + "=" * 100)
    print("A6 — Account-scale activation threshold")
    print("=" * 100)

    recent_spx = float(df["close"].iloc[-1])
    debit_pct = 0.015

    # 1% of account / entry
    print(f"\nAt 1% account / entry sizing, ATM/+5% DTE 90 spread debit ~ {debit_pct*100:.1f}% × S = ${recent_spx * debit_pct * 100:.0f} per SPX contract:")
    print(f"\n{'NLV':>10} | {'1% account':>12} | {'SPX contracts':>13} | {'XSP contracts':>13} | viable?")
    print("-" * 80)

    for nlv in [25_000, 50_000, 100_000, 150_000, 250_000, 500_000, 1_000_000]:
        budget = nlv * 0.01
        spx_contracts = budget / (recent_spx * debit_pct * 100)
        xsp_contracts = budget / ((recent_spx / 10) * debit_pct * 100)
        spx_viable = "✓" if spx_contracts >= 1 else "✗ (use XSP)"
        xsp_viable = "✓" if xsp_contracts >= 1 else "✗"
        print(f"${nlv:>9,} | ${budget:>11,.0f} | {spx_contracts:>12.2f} | {xsp_contracts:>12.2f} | "
              f"SPX {spx_viable}, XSP {xsp_viable}")

    print("\n=== Activation thresholds ===")
    spx_min = (recent_spx * debit_pct * 100) / 0.01
    xsp_min = ((recent_spx / 10) * debit_pct * 100) / 0.01
    print(f"  SPX 1-contract min NLV (1% account/entry): ${spx_min:,.0f}")
    print(f"  XSP 1-contract min NLV (1% account/entry): ${xsp_min:,.0f}")
    print(f"\n  Recommendation:")
    print(f"    NLV ≥ ${xsp_min:,.0f}: activate Q042 with XSP")
    print(f"    NLV ≥ ${spx_min:,.0f}: switch to SPX (cheaper bid-ask per BP, equivalent tax)")
    print(f"    NLV < ${xsp_min:,.0f}: skip Q042 (sub-1-contract sizing not viable)")

    # Account scaling: at NLV X, 5% sleeve cap = how many contracts simultaneously
    print("\n=== Sleeve cap interpretation at 5% MVP cap ===")
    print(f"  5% sleeve = max 5 concurrent 1%-sized positions (same DTE)")
    print(f"  Or: 1 single 5%-sized position (concentrated on 1 trade)")
    print(f"  Default sizing per entry = 1% account → up to 5 trades held simultaneously without breaching cap")
    print(f"  But: re-trigger spacing rule (≥30d for DTE 90) means in practice n=1-2 concurrent positions")


def main() -> None:
    spx, vix = load()
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["ma50"] = df["close"].rolling(50).mean()
    df["vix"] = vix.reindex(df.index).ffill()

    a4_retrigger_spacing(df)
    a5_spx_vs_xsp(df)
    a6_account_scale(df)


if __name__ == "__main__":
    main()
