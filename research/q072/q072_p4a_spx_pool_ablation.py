"""Q072 P4A — SPX PM Pool Ablation.

Per brief §P4A (口径修正 per round-2 2nd Quant review):

    A: Main only                      (baseline excluding Aftermath-gated BPS_HV)
    B: Main + DD Overlay
    C: Main + BPS_HV (aftermath permission ON, i.e., production behavior)
    D: Main + DD Overlay + BPS_HV (aftermath permission ON)

Aftermath is a PERMISSION GATE, not a standalone sleeve. Ablation tests whether
the gate's BPS_HV feed is net-positive given DD Overlay presence.

Splits: full / post-2020 / recent2y

Standard metrics pack (per PM standing rule):
    total P&L / Ann ROE / Sharpe / max DD / CVaR 5% / worst trade /
    worst 20d window / marginal $/BP-day / avg BP / peak BP

Outputs:
    q072_p4a_results.csv     — 4 groups × 3 splits with full metrics
    q072_p4a_daily_pnl.csv   — daily P&L per group across 19y
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

NLV_SEED = 100_000.0
AFTERMATH_GATED = {"Bull Put Spread (High Vol)"}  # BPS_HV: gated by aftermath permission

SPLITS = {
    "full":     ("2007-01-01", "2026-05-13"),
    "post2020": ("2020-01-01", "2026-05-13"),
    "recent2y": ("2024-01-01", "2026-05-13"),
}


def distribute_pnl(trades: pd.DataFrame, daily_idx: pd.DatetimeIndex,
                   entry_col: str, exit_col: str, pnl_col: str) -> pd.Series:
    s = pd.Series(0.0, index=daily_idx)
    for _, t in trades.iterrows():
        m = (daily_idx >= t[entry_col]) & (daily_idx <= t[exit_col])
        n = m.sum()
        if n > 0:
            s.loc[m] += t[pnl_col] / n
    return s


def distribute_bp(trades: pd.DataFrame, daily_idx: pd.DatetimeIndex,
                  entry_col: str, exit_col: str, bp_col: str) -> pd.Series:
    s = pd.Series(0.0, index=daily_idx)
    for _, t in trades.iterrows():
        m = (daily_idx >= t[entry_col]) & (daily_idx <= t[exit_col])
        s.loc[m] += t[bp_col]
    return s


def metrics_pack(daily_pnl: pd.Series, daily_bp_pct: pd.Series,
                 trade_pnls: list[float] | None = None) -> dict:
    pnl_arr = daily_pnl.values
    n_days = len(pnl_arr)
    total = float(pnl_arr.sum())
    years = n_days / 252
    # Ann ROE: total return on NLV_SEED + reinvested cum P&L, simple
    avg_nlv = NLV_SEED + pnl_arr.cumsum().mean()
    ann_roe = (total / years) / avg_nlv if years > 0 and avg_nlv > 0 else None
    # Sharpe on daily P&L (no risk-free subtraction for simplicity, daily-level)
    daily_std = pnl_arr.std()
    sharpe = (pnl_arr.mean() / daily_std * np.sqrt(252)) if daily_std > 0 else None
    # Max drawdown of cumulative P&L
    cum = pnl_arr.cumsum()
    peak = np.maximum.accumulate(cum)
    dd = cum - peak
    max_dd = float(dd.min())
    # CVaR 5% on daily P&L
    p5 = np.percentile(pnl_arr, 5)
    cvar = float(pnl_arr[pnl_arr <= p5].mean()) if (pnl_arr <= p5).any() else None
    # Worst trade
    worst_trade = min(trade_pnls) if trade_pnls else None
    # Worst 20d rolling sum
    worst_20d = float(pd.Series(pnl_arr).rolling(20).sum().min())
    # Avg BP / peak BP
    avg_bp = float(daily_bp_pct.mean())
    peak_bp = float(daily_bp_pct.max())
    # $/BP-day: total P&L / sum(BP_dollar daily) where BP_dollar = bp_pct/100 * NLV_SEED
    bp_dollar_days = (daily_bp_pct / 100 * NLV_SEED).sum()
    dollar_bp_day = total / bp_dollar_days if bp_dollar_days > 0 else None

    return {
        "n_days": n_days,
        "total_pnl": round(total, 0),
        "ann_roe_pct": round(ann_roe * 100, 2) if ann_roe is not None else None,
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "max_dd": round(max_dd, 0),
        "cvar_5pct_daily": round(cvar, 0) if cvar is not None else None,
        "worst_trade": round(worst_trade, 0) if worst_trade is not None else None,
        "worst_20d_window": round(worst_20d, 0),
        "avg_bp_pct": round(avg_bp, 2),
        "peak_bp_pct": round(peak_bp, 2),
        "dollar_per_bp_day": round(dollar_bp_day, 4) if dollar_bp_day is not None else None,
    }


def main():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    idx = daily.index

    baseline = pd.read_csv(BASELINE, parse_dates=["entry_date", "exit_date"])
    baseline["strategy"] = baseline["strategy"].str.strip()
    dd = pd.read_csv(DD_TRADES, parse_dates=["entry_date", "exit_date"])

    main_only = baseline[~baseline["strategy"].isin(AFTERMATH_GATED)]
    main_plus_aftermath = baseline  # production: aftermath ON, all BPS_HV present
    bps_hv = baseline[baseline["strategy"].isin(AFTERMATH_GATED)]

    print(f"main_only trades: {len(main_only)}  BPS_HV (aftermath-gated): {len(bps_hv)}  "
          f"DD Overlay: {len(dd)}")

    # Build daily P&L and BP for each group
    pnl_main = distribute_pnl(main_only, idx, "entry_date", "exit_date", "exit_pnl")
    pnl_bps_hv = distribute_pnl(bps_hv, idx, "entry_date", "exit_date", "exit_pnl")
    pnl_dd = distribute_pnl(dd, idx, "entry_date", "exit_date", "exit_pnl")
    bp_main = distribute_bp(main_only, idx, "entry_date", "exit_date", "bp_pct_account")
    bp_bps_hv = distribute_bp(bps_hv, idx, "entry_date", "exit_date", "bp_pct_account")
    bp_dd = pd.Series(0.0, index=idx)
    for _, t in dd.iterrows():
        m = (idx >= t["entry_date"]) & (idx <= t["exit_date"])
        bp_dd.loc[m] += t["account_pct"] * 100

    groups = {
        "A_main_only": {
            "pnl": pnl_main,
            "bp": bp_main,
            "trades_pnl": main_only["exit_pnl"].tolist(),
        },
        "B_main_plus_dd": {
            "pnl": pnl_main + pnl_dd,
            "bp": bp_main + bp_dd,
            "trades_pnl": main_only["exit_pnl"].tolist() + dd["exit_pnl"].tolist(),
        },
        "C_main_plus_aftermath": {
            "pnl": pnl_main + pnl_bps_hv,
            "bp": bp_main + bp_bps_hv,
            "trades_pnl": main_plus_aftermath["exit_pnl"].tolist(),
        },
        "D_main_plus_dd_plus_aftermath": {
            "pnl": pnl_main + pnl_dd + pnl_bps_hv,
            "bp": bp_main + bp_dd + bp_bps_hv,
            "trades_pnl": main_plus_aftermath["exit_pnl"].tolist() + dd["exit_pnl"].tolist(),
        },
    }

    # Save daily P&L per group
    daily_pnl_df = pd.DataFrame({g: groups[g]["pnl"] for g in groups})
    daily_pnl_df.index.name = "date"
    daily_pnl_df.to_csv(OUT / "q072_p4a_daily_pnl.csv", float_format="%.2f")

    # Compute metrics × split
    rows = []
    for split_name, (s, e) in SPLITS.items():
        mask = (idx >= s) & (idx <= e)
        for gname, gdata in groups.items():
            sub_pnl = gdata["pnl"][mask]
            sub_bp = gdata["bp"][mask]
            # filter trades in split window
            # rough: use baseline's entry_date filter
            if gname == "A_main_only":
                tr = main_only[(main_only.entry_date >= s) & (main_only.entry_date <= e)]
                trade_pnls = tr["exit_pnl"].tolist()
            elif gname == "B_main_plus_dd":
                tr1 = main_only[(main_only.entry_date >= s) & (main_only.entry_date <= e)]
                tr2 = dd[(dd.entry_date >= s) & (dd.entry_date <= e)]
                trade_pnls = tr1["exit_pnl"].tolist() + tr2["exit_pnl"].tolist()
            elif gname == "C_main_plus_aftermath":
                tr = baseline[(baseline.entry_date >= s) & (baseline.entry_date <= e)]
                trade_pnls = tr["exit_pnl"].tolist()
            else:  # D
                tr1 = baseline[(baseline.entry_date >= s) & (baseline.entry_date <= e)]
                tr2 = dd[(dd.entry_date >= s) & (dd.entry_date <= e)]
                trade_pnls = tr1["exit_pnl"].tolist() + tr2["exit_pnl"].tolist()
            m = metrics_pack(sub_pnl, sub_bp, trade_pnls)
            rows.append({"split": split_name, "group": gname, "n_trades": len(trade_pnls), **m})
    results = pd.DataFrame(rows)
    results.to_csv(OUT / "q072_p4a_results.csv", index=False)

    print("\n" + "=" * 80)
    print("Q072 P4A — SPX PM Pool Ablation Results")
    print("=" * 80)

    for split in ["full", "post2020", "recent2y"]:
        print(f"\n--- {split} ---")
        sub = results[results.split == split]
        cols = ["group", "n_trades", "total_pnl", "ann_roe_pct", "sharpe", "max_dd",
                "cvar_5pct_daily", "worst_trade", "worst_20d_window", "avg_bp_pct",
                "peak_bp_pct", "dollar_per_bp_day"]
        print(sub[cols].to_string(index=False))

        # marginal contributions (vs A_main_only)
        a_pnl = sub[sub.group == "A_main_only"]["total_pnl"].values[0]
        print(f"\n  Marginal vs A_main_only ({split}):")
        for g in ["B_main_plus_dd", "C_main_plus_aftermath", "D_main_plus_dd_plus_aftermath"]:
            g_pnl = sub[sub.group == g]["total_pnl"].values[0]
            g_worst = sub[sub.group == g]["worst_20d_window"].values[0]
            a_worst = sub[sub.group == "A_main_only"]["worst_20d_window"].values[0]
            print(f"    {g}: ΔP&L = ${g_pnl - a_pnl:+,.0f}, "
                  f"Δworst_20d = ${g_worst - a_worst:+,.0f}")

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
