"""Q042 Tier 2 — P3 BP-stacking gate simulation.

Q3 in Tier 1 found 98.5% of dd10+ trigger dates land in HIGH_VOL where the main
strategy is already in BPS_HV / IC_HV reduced posture. This script quantifies
the actual BP collision and tests the proposed gate.

Inputs:
  - Q042 trigger dates from finalist configs (P1):
      * dd10_ma50_reclaim, dd12_ma50_reclaim, dd15_naive
  - Main strategy 19y daily BP envelope: research/q042/baseline_19y_bp_daily.csv
  - 3y trade log for cross-check: data/backtest_trades_3y_2026-04-29.csv

Gate proposal (default):
  q042_bp_cap = min(20% account, max(0%, 60% account − main_strategy_bp%))

Outputs:
  - For each finalist trigger:
    * n triggers, n entries
    * median main-strategy bp_pct at trigger
    * pct of triggers where main_bp > 40%
    * gate fire rate (gate cap = 0)
    * gate-allowed Q042 BP per trigger (median, p25, p75)
    * total combined peak BP (worst-case stacked)
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
BP_19Y = Path(__file__).resolve().parent / "baseline_19y_bp_daily.csv"
TRADE_3Y = REPO / "data" / "backtest_trades_3y_2026-04-29.csv"


def load_market() -> pd.DataFrame:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    df = pd.DataFrame(index=spx.loc["2007-01-01":"2026-05-08"].index)
    df["close"] = spx["Close"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["ma50"] = df["close"].rolling(50).mean()
    df["vix"] = vix["Close"].reindex(df.index).ffill()
    return df


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


def gate_capacity(main_bp_pct: float, q042_max_pct: float = 20.0, total_cap_pct: float = 60.0) -> float:
    """Default gate: q042 cap = min(q042_max, max(0, total_cap − main_bp_pct))."""
    return min(q042_max_pct, max(0.0, total_cap_pct - main_bp_pct))


def main() -> None:
    df = load_market()
    bp_daily = pd.read_csv(BP_19Y)
    bp_daily["date"] = pd.to_datetime(bp_daily["date"])
    bp_daily = bp_daily.set_index("date")
    print(f"19y bp daily: {bp_daily.index.min().date()} → {bp_daily.index.max().date()} (n={len(bp_daily)})")
    print(f"  baseline mean bp_pct: {bp_daily['bp_pct_account'].mean():.1f}% / median: {bp_daily['bp_pct_account'].median():.1f}% / p95: {bp_daily['bp_pct_account'].quantile(0.95):.1f}%")
    print(f"  bp_pct >0 days: {(bp_daily['bp_pct_account']>0).sum()} / {len(bp_daily)} = {(bp_daily['bp_pct_account']>0).mean()*100:.1f}%")

    # 3y subset cross-check
    bp_3y = bp_daily.loc["2023-01-01":"2026-05-08"]
    print(f"  3y subset (2023-01 → 2026-05): mean bp_pct: {bp_3y['bp_pct_account'].mean():.1f}% / p95: {bp_3y['bp_pct_account'].quantile(0.95):.1f}%")

    triggers_def = {
        "dd10_ma50_reclaim": (0.10, "ma50_reclaim"),
        "dd12_ma50_reclaim": (0.12, "ma50_reclaim"),
        "dd15_naive": (0.15, "none"),
    }

    # Two gate variants:
    gate_variants = [
        ("default",     {"q042_max_pct": 20.0, "total_cap_pct": 60.0}),
        ("conservative", {"q042_max_pct": 15.0, "total_cap_pct": 50.0}),
        ("aggressive",  {"q042_max_pct": 25.0, "total_cap_pct": 70.0}),
    ]

    print("\n" + "=" * 90)
    print("BP-stacking gate simulation")
    print("=" * 90)

    results_rows = []
    for trig_name, (dd, conf) in triggers_def.items():
        entries = find_entries(df, dd, conf)
        # Align with bp_daily index
        usable = [e for e in entries if e in bp_daily.index]
        if not usable:
            continue
        main_bp = bp_daily.loc[usable, "bp_pct_account"]
        regime = bp_daily.loc[usable, "regime"]
        vix_at_trig = df.loc[usable, "vix"]

        print(f"\n--- {trig_name} (n_entries={len(usable)}) ---")
        print(f"  main strategy bp_pct at trigger:  median={main_bp.median():.1f}% / p25={main_bp.quantile(0.25):.1f}% / p75={main_bp.quantile(0.75):.1f}% / max={main_bp.max():.1f}%")
        print(f"  vix at trigger:                   median={vix_at_trig.median():.1f} / p75={vix_at_trig.quantile(0.75):.1f}")
        print(f"  regime distribution: {regime.value_counts().to_dict()}")

        for gate_name, gate_kwargs in gate_variants:
            allowed = main_bp.apply(lambda x: gate_capacity(x, **gate_kwargs))
            blocked = (allowed <= 0).sum()
            partial = ((allowed > 0) & (allowed < gate_kwargs["q042_max_pct"])).sum()
            full = (allowed >= gate_kwargs["q042_max_pct"]).sum()
            avg_allowed = allowed.mean()
            combined_peak = (main_bp + allowed).max()

            print(f"  gate={gate_name:<13s}: blocked={blocked}/{len(allowed)} ({blocked/len(allowed)*100:.0f}%)  "
                  f"partial={partial}  full={full}  "
                  f"avg_q042_allowed={avg_allowed:.1f}%  combined_peak={combined_peak:.1f}%")
            results_rows.append({
                "trigger": trig_name,
                "gate": gate_name,
                "n_entries": len(usable),
                "blocked_pct": blocked / len(allowed) * 100,
                "partial_pct": partial / len(allowed) * 100,
                "full_pct": full / len(allowed) * 100,
                "avg_q042_allowed_pct": avg_allowed,
                "combined_peak_bp_pct": combined_peak,
                "main_bp_median_at_trig": main_bp.median(),
                "main_bp_p75_at_trig": main_bp.quantile(0.75),
                "vix_median_at_trig": vix_at_trig.median(),
            })

    out_df = pd.DataFrame(results_rows)
    out_path = Path(__file__).resolve().parent / "p3_bp_gate.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")

    # Holding-period collision: for default gate, simulate holding Q042 spread DTE=30
    # against main strategy's actual bp window. Track combined BP over the 30-day holds.
    print("\n" + "=" * 90)
    print("Hold-period BP collision (Q042 spread DTE=30, default gate)")
    print("=" * 90)

    # Use dd12_ma50_reclaim winner config
    entries = [e for e in find_entries(df, 0.12, "ma50_reclaim") if e in bp_daily.index]
    print(f"trigger: dd12_ma50_reclaim, n_entries={len(entries)}")

    overlap_combined_max_bp = []
    for entry in entries:
        end = entry + pd.Timedelta(days=45)  # 30-day DTE plus margin for next trade day
        window = bp_daily.loc[entry:end].iloc[:30]
        if window.empty:
            continue
        # Q042 BP held constant over the hold (worst-case assumption)
        q042_allow_at_entry = gate_capacity(window["bp_pct_account"].iloc[0])
        combined = window["bp_pct_account"] + q042_allow_at_entry
        overlap_combined_max_bp.append({
            "entry": str(entry.date()),
            "main_bp_at_entry": float(window["bp_pct_account"].iloc[0]),
            "q042_allowed": float(q042_allow_at_entry),
            "main_bp_max_during_hold": float(window["bp_pct_account"].max()),
            "combined_max_during_hold": float(combined.max()),
        })

    hold_df = pd.DataFrame(overlap_combined_max_bp)
    hold_path = Path(__file__).resolve().parent / "p3_hold_collision.csv"
    hold_df.to_csv(hold_path, index=False)
    print(f"\nhold-period stats (Q042 BP fixed at entry, main BP varying):")
    if not hold_df.empty:
        print(f"  q042_allowed at entry:        median={hold_df['q042_allowed'].median():.1f}% / blocked(=0)={(hold_df['q042_allowed']==0).sum()}")
        print(f"  combined peak during hold:    median={hold_df['combined_max_during_hold'].median():.1f}% / p75={hold_df['combined_max_during_hold'].quantile(0.75):.1f}% / max={hold_df['combined_max_during_hold'].max():.1f}%")
        print(f"  combined peak > 80% account:  {(hold_df['combined_max_during_hold']>80).sum()}/{len(hold_df)}")
        print(f"  combined peak > 100% account: {(hold_df['combined_max_during_hold']>100).sum()}/{len(hold_df)}")
    print(f"\nwrote {hold_path}")


if __name__ == "__main__":
    main()
