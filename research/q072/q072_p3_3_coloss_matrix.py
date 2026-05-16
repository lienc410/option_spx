"""Q072 P3.3 — Co-loss Matrix with Conditional Cuts.

Per PM gate decision 2026-05-15: conditional correlation matters, not just
full-sample. Specifically need correlation on:
    - all days
    - stress episode days (tight definition from P1)
    - worst 5% portfolio P&L days
    - HV BP > 40% days

Daily P&L per sleeve approximated by LINEAR DISTRIBUTION of exit_pnl across
each trade's holding period. This is a rough proxy — real MTM requires Greek
reconstruction (P3.2, deferred). Linear distribution preserves directional
correlation signal at coarse temporal resolution; precise day-level MTM moves
will refine in P3.2.

Sleeves:
    main         = baseline trades excluding BPS HV / Bear Call HV
    aftermath    = BPS_HV + Bear_Call_HV trades (Aftermath permission feed)
    dd_overlay   = q042 DD trades
    hv_ladder    = V2f filtered trades (placeholder, will refresh post-Q071)

Outputs:
    q072_p3_3_daily_pnl.csv      — daily P&L per sleeve
    q072_p3_3_corr_matrices.csv  — 4×4 corr for each condition × split
    q072_p3_3_coloss_rates.csv   — conditional co-loss rates
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"
BASELINE = REPO / "research" / "q042" / "baseline_19y_trades.csv"
DD_TRADES = REPO / "data" / "q042_backtest_trades.csv"
HV_TRADES = OUT / "q072_hv_ladder_v2f_baseline_trades.csv"

AFTERMATH_STRATS = {"Bull Put Spread (High Vol)", "Bear Call Spread (High Vol)",
                    "Iron Condor (High Vol)"}

SPLITS = {
    "full":     ("2007-01-01", "2026-05-13"),
    "post2020": ("2020-01-01", "2026-05-13"),
    "recent2y": ("2024-01-01", "2026-05-13"),
}


def distribute_trade_pnl(trades: pd.DataFrame, daily_idx: pd.DatetimeIndex,
                         entry_col: str, exit_col: str, pnl_col: str) -> pd.Series:
    """Linearly spread each trade's exit P&L across its holding days."""
    series = pd.Series(0.0, index=daily_idx)
    for _, t in trades.iterrows():
        entry = t[entry_col]
        exit_d = t[exit_col]
        pnl = t[pnl_col]
        mask = (daily_idx >= entry) & (daily_idx <= exit_d)
        n = mask.sum()
        if n > 0:
            series.loc[mask] += pnl / n
    return series


def build_daily_pnl(daily: pd.DataFrame) -> pd.DataFrame:
    print("Building daily P&L per sleeve (linear distribution)...")
    idx = daily.index

    baseline = pd.read_csv(BASELINE, parse_dates=["entry_date", "exit_date"])
    baseline["strategy"] = baseline["strategy"].str.strip()
    main_only = baseline[~baseline["strategy"].isin(AFTERMATH_STRATS)]
    aft_only = baseline[baseline["strategy"].isin(AFTERMATH_STRATS)]

    dd = pd.read_csv(DD_TRADES, parse_dates=["entry_date", "exit_date"])
    hv = pd.read_csv(HV_TRADES, parse_dates=["entry_date", "exit_date"])

    print(f"  main trades: {len(main_only)}  aftermath-feed trades: {len(aft_only)}  "
          f"DD: {len(dd)}  HV: {len(hv)}")

    pnl_df = pd.DataFrame(index=idx)
    pnl_df["main"] = distribute_trade_pnl(main_only, idx, "entry_date", "exit_date", "exit_pnl")
    pnl_df["aftermath"] = distribute_trade_pnl(aft_only, idx, "entry_date", "exit_date", "exit_pnl")
    pnl_df["dd_overlay"] = distribute_trade_pnl(dd, idx, "entry_date", "exit_date", "exit_pnl")
    pnl_df["hv_ladder"] = distribute_trade_pnl(hv, idx, "entry_date", "exit_date", "pnl")
    pnl_df["portfolio_total"] = pnl_df[["main", "aftermath", "dd_overlay", "hv_ladder"]].sum(axis=1)
    return pnl_df


def conditional_corr_matrix(pnl_df: pd.DataFrame, daily: pd.DataFrame,
                            split_window: tuple) -> dict:
    s, e = split_window
    sub_pnl = pnl_df.loc[(pnl_df.index >= s) & (pnl_df.index <= e)]
    sub_daily = daily.loc[(daily.index >= s) & (daily.index <= e)]

    # Align HV BP and stress flag from daily
    hv_bp = sub_daily["hv_ladder_bp"]
    # Use tight episode flag (rebuild from daily.episode_id_tight)
    in_stress = sub_daily["episode_id_tight"] >= 0

    sleeves = ["main", "aftermath", "dd_overlay", "hv_ladder"]
    sub_pnl_4 = sub_pnl[sleeves]

    # worst 5% by portfolio total
    p5 = np.percentile(sub_pnl["portfolio_total"], 5)
    worst5 = sub_pnl["portfolio_total"] <= p5

    conditions = {
        "all":         np.ones(len(sub_pnl), dtype=bool),
        "stress_only": in_stress.values,
        "worst5pct":   worst5.values,
        "hv_heavy_40": (hv_bp.values > 40),
    }
    out = {}
    for cond_name, mask in conditions.items():
        if mask.sum() < 5:
            out[cond_name] = None
            continue
        corr = sub_pnl_4[mask].corr().round(3)
        out[cond_name] = corr
    return out


def coloss_rates(pnl_df: pd.DataFrame, daily: pd.DataFrame,
                 split_window: tuple) -> pd.DataFrame:
    s, e = split_window
    sub = pnl_df.loc[(pnl_df.index >= s) & (pnl_df.index <= e)]
    sleeves = ["main", "aftermath", "dd_overlay", "hv_ladder"]
    rows = []
    for a in sleeves:
        # baseline: unconditional P(a < 0)
        p_a_loss = (sub[a] < 0).mean()
        for b in sleeves:
            if a == b:
                continue
            p_b_loss = (sub[b] < 0).mean()
            # joint: P(b<0 | a in worst-5% of a's distribution)
            a_p5 = np.percentile(sub[a], 5)
            a_worst5 = sub[a] <= a_p5
            if a_worst5.sum() < 5:
                continue
            p_b_loss_given_a_worst5 = (sub[a_worst5][b] < 0).mean()
            # independence baseline: P(b < 0)
            ratio = p_b_loss_given_a_worst5 / p_b_loss if p_b_loss > 0 else None
            rows.append({
                "a (worst-5% trigger)": a,
                "b": b,
                "p_b_loss_uncond": round(p_b_loss, 3),
                "p_b_loss_given_a_worst5": round(p_b_loss_given_a_worst5, 3),
                "lift_ratio": round(ratio, 2) if ratio is not None else None,
            })
    return pd.DataFrame(rows)


def main():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    pnl_df = build_daily_pnl(daily)
    pnl_df.to_csv(OUT / "q072_p3_3_daily_pnl.csv", float_format="%.2f")

    # Compute per split
    all_rows = []
    all_coloss = []
    for split_name, window in SPLITS.items():
        mats = conditional_corr_matrix(pnl_df, daily, window)
        for cond, corr in mats.items():
            if corr is None:
                continue
            stacked = corr.stack().reset_index()
            stacked.columns = ["sleeve_a", "sleeve_b", "corr"]
            stacked["split"] = split_name
            stacked["condition"] = cond
            all_rows.append(stacked)
        coloss = coloss_rates(pnl_df, daily, window)
        coloss["split"] = split_name
        all_coloss.append(coloss)

    corr_df = pd.concat(all_rows, ignore_index=True)
    coloss_df = pd.concat(all_coloss, ignore_index=True)
    corr_df.to_csv(OUT / "q072_p3_3_corr_matrices.csv", index=False)
    coloss_df.to_csv(OUT / "q072_p3_3_coloss_rates.csv", index=False)

    print("\n" + "=" * 70)
    print("Q072 P3.3 — Summary")
    print("=" * 70)

    for split_name, window in SPLITS.items():
        print(f"\n--- {split_name} ---")
        mats = conditional_corr_matrix(pnl_df, daily, window)
        for cond, corr in mats.items():
            if corr is None:
                continue
            print(f"\n  {cond} corr matrix:")
            print(corr.to_string())

    print(f"\n\nKey co-loss rates (full sample, sorted by lift_ratio):")
    full_coloss = coloss_df[coloss_df.split == "full"].sort_values("lift_ratio", ascending=False)
    print(full_coloss.to_string(index=False))

    print(f"\n\nKey co-loss rates (post2020):")
    post_coloss = coloss_df[coloss_df.split == "post2020"].sort_values("lift_ratio", ascending=False)
    print(post_coloss.to_string(index=False))

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
