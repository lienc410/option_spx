"""Q072 P4B — /ES Pool Ablation Framework (placeholder).

⚠ NUMBERS NOT FINAL. Awaiting Q071 HV Ladder config lock.

Per brief §P4B (口径修正 per round-2 2nd Quant review):

    E: HV Ladder only
    F: SPX pack (D from P4A) + HV Ladder economic overlay
        (合并 P&L stream，不合并 BP — /ES is SPAN pool, SPX is PM pool)

Currently uses V2f filtered (research/q072/q072_hv_ladder_v2f_baseline_trades.csv,
557 trades) as placeholder. When Q071 final config locks (likely with VIX≥22
gate and/or IVP gate per Q071 review), this framework re-runs HV Ladder
backtest and re-evaluates.

Key tail metric to recheck post-lock: 2022 single-year combined loss
($94k from V2f baseline). Q071 HV regime gate may materially reduce this if
filter cuts entries during sustained drawdown.

Splits: full / post-2020 / recent2y
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"
HV_TRADES = OUT / "q072_hv_ladder_v2f_baseline_trades.csv"  # PLACEHOLDER

ES_NLV = 100_000.0
ES_SPAN_FRAC = 0.05
ES_MULTIPLIER = 50.0

SPLITS = {
    "full":     ("2007-01-01", "2026-05-13"),
    "post2020": ("2020-01-01", "2026-05-13"),
    "recent2y": ("2024-01-01", "2026-05-13"),
}


def metrics_pack(daily_pnl: pd.Series, daily_bp_pct: pd.Series,
                 trade_pnls: list[float]) -> dict:
    pnl_arr = daily_pnl.values
    n_days = len(pnl_arr)
    total = float(pnl_arr.sum())
    years = n_days / 252
    avg_nlv = ES_NLV + pnl_arr.cumsum().mean()
    ann_roe = (total / years) / avg_nlv if years > 0 and avg_nlv > 0 else None
    sharpe = (pnl_arr.mean() / pnl_arr.std() * np.sqrt(252)) if pnl_arr.std() > 0 else None
    cum = pnl_arr.cumsum()
    dd = cum - np.maximum.accumulate(cum)
    max_dd = float(dd.min())
    worst_20d = float(pd.Series(pnl_arr).rolling(20).sum().min())
    return {
        "n_days": n_days,
        "n_trades": len(trade_pnls),
        "total_pnl": round(total, 0),
        "ann_roe_pct": round(ann_roe * 100, 2) if ann_roe is not None else None,
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "max_dd": round(max_dd, 0),
        "worst_trade": round(min(trade_pnls), 0),
        "worst_20d_window": round(worst_20d, 0),
        "avg_bp_pct": round(float(daily_bp_pct.mean()), 2),
        "peak_bp_pct": round(float(daily_bp_pct.max()), 2),
    }


def main():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    idx = daily.index
    hv = pd.read_csv(HV_TRADES, parse_dates=["entry_date", "exit_date"])

    # Daily P&L distribution (linear across holding period)
    pnl_hv = pd.Series(0.0, index=idx)
    bp_hv = pd.Series(0.0, index=idx)
    for _, t in hv.iterrows():
        m = (idx >= t["entry_date"]) & (idx <= t["exit_date"])
        n = m.sum()
        if n > 0:
            pnl_hv.loc[m] += t["pnl"] / n
            span_per = ES_SPAN_FRAC * t["entry_spx"] * ES_MULTIPLIER * t["contracts"]
            bp_hv.loc[m] += span_per
    bp_hv_pct = bp_hv / ES_NLV * 100

    # Group E: HV Ladder only
    rows = []
    for split, (s, e) in SPLITS.items():
        mask = (idx >= s) & (idx <= e)
        tr = hv[(hv.entry_date >= s) & (hv.entry_date <= e)]
        m = metrics_pack(pnl_hv[mask], bp_hv_pct[mask], tr["pnl"].tolist())
        rows.append({"split": split, "group": "E_hv_only", **m})
    results = pd.DataFrame(rows)
    results.to_csv(OUT / "q072_p4b_results_placeholder.csv", index=False)

    print("=" * 80)
    print("Q072 P4B — /ES Pool Framework (PLACEHOLDER — pre-Q071-lock)")
    print("=" * 80)
    print(f"\nHV Ladder placeholder: V2f filtered, {len(hv)} trades, 2007-2026")
    print(f"\nGroup E results across splits:")
    print(results[["split", "n_days", "n_trades", "total_pnl", "ann_roe_pct",
                   "sharpe", "max_dd", "worst_trade", "worst_20d_window",
                   "avg_bp_pct", "peak_bp_pct"]].to_string(index=False))

    print("\n⚠ THESE NUMBERS ARE PLACEHOLDERS. Q071 final config may:")
    print("  - Add VIX ≥ 22 gate → fewer HV trades, less always-on exposure")
    print("  - Add IVP gate → entry quality filter")
    print("  - Modify STOP behavior → 2022 path P&L will change materially")
    print("\nRerun this framework after Q071 final memo locks the strategy.")

    # Combined SPX (group D from P4A) + /ES (group E) economic overlay
    p4a_daily = pd.read_csv(OUT / "q072_p4a_daily_pnl.csv",
                            parse_dates=["date"]).set_index("date")
    spx_d = p4a_daily["D_main_plus_dd_plus_aftermath"]
    combined_pnl = spx_d.add(pnl_hv, fill_value=0.0)

    print(f"\nGroup F (SPX D + /ES E) — combined economic P&L:")
    rows_f = []
    for split, (s, e) in SPLITS.items():
        mask = (idx >= s) & (idx <= e)
        sub_pnl = combined_pnl[mask]
        years = mask.sum() / 252
        total = float(sub_pnl.sum())
        cum = sub_pnl.cumsum()
        dd = cum - cum.cummax()
        worst20 = sub_pnl.rolling(20).sum().min()
        rows_f.append({
            "split": split,
            "total_pnl": round(total, 0),
            "max_dd": round(float(dd.min()), 0),
            "worst_20d": round(float(worst20), 0),
            "implied_ann_pnl": round(total / years, 0),
        })
    print(pd.DataFrame(rows_f).to_string(index=False))
    pd.DataFrame(rows_f).to_csv(OUT / "q072_p4b_combined_placeholder.csv", index=False)

    print(f"\nFramework outputs saved to {OUT}/ (placeholder).")


if __name__ == "__main__":
    main()
