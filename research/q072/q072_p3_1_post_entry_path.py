"""Q072 P3.1 — Post-entry path for stress sleeves, bucketed by HV BP load.

Per `research/q072/q072_research_brief_2026-05-15.md` §P3.1, refined per PM
gate decision 2026-05-15 (P2 findings):

    Question is NOT "what's the average post-entry P&L for DD Overlay?"
    It IS "Does DD Overlay path risk worsen materially when HV Ladder is
    already heavy (BP > 40%) at entry?"

For each DD Overlay trade and each Aftermath window start:
    1d / 3d / 5d / 10d / 20d post-entry P&L path
    MAE (max adverse excursion) within window
    MFE (max favorable excursion) within window
    time-to-MAE
    exit P&L (DD trade) / 30d-forward P&L (Aftermath)

DD Overlay P&L: BS+skew daily mark-to-market of ATM/+5% call vertical
                (re-using q062 _price_call_skewed pricing).
Aftermath path: SPX cumulative return as proxy (no specific trade — permission
                window).

Then bucket by HV BP at entry: <20% / 20-40% / >40% of /ES NLV.
Split by sample: full / post-2020 / recent 2y.

Outputs:
    q072_p3_1_dd_paths.csv             — DD trades with full path metrics
    q072_p3_1_aftermath_paths.csv      — Aftermath windows with path metrics
    q072_p3_1_bucket_summary.csv       — aggregated by HV bucket × split
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

RFR = 0.04
HORIZONS = [1, 3, 5, 10, 20]
MAE_WINDOW = 30  # cap MAE search to first 30 trading days after entry
SPLITS = {
    "full":     ("2007-01-01", "2026-05-13"),
    "post2020": ("2020-01-01", "2026-05-13"),
    "recent2y": ("2024-01-01", "2026-05-13"),
}
HV_BUCKETS = [(-1, 20, "low<20"), (20, 40, "mid20-40"), (40, 100, "heavy>40")]


# ── BS + skew pricing (replicated from q062_tier1_structure_scan.py) ───────────
def _term_mult(dte: int) -> float:
    if dte <= 45: return 1.10
    if dte <= 120: return 1.00
    return 0.95


def _skew_mult(moneyness: float) -> float:
    if moneyness >= 1.0:
        d = min(moneyness - 1.0, 0.10)
        return 1.0 - 1.5 * d
    d = min(1.0 - moneyness, 0.10)
    return 1.0 + 1.5 * d


def _bs_call(S: float, K: float, T: float, sigma: float) -> float:
    if T <= 0: return max(0.0, S - K)
    if sigma <= 0: return max(0.0, S - K * np.exp(-RFR * T))
    d1 = (np.log(S / K) + (RFR + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-RFR * T) * norm.cdf(d2)


def _price_call_skewed(S: float, K: float, vix: float, dte: int) -> float:
    sigma_atm = max(vix / 100.0, 0.10) * _term_mult(dte)
    sigma_k = sigma_atm * _skew_mult(K / S)
    T = max(dte / 365.0, 1e-6)
    return _bs_call(S, K, T, sigma_k)


def price_spread(spx: float, vix: float, long_K: float, short_K: float, dte: int) -> float:
    return _price_call_skewed(spx, long_K, vix, dte) - _price_call_skewed(spx, short_K, vix, dte)


# ── Data loading ─────────────────────────────────────────────────────────────
def load_data() -> dict:
    daily = pd.read_csv(OUT / "q072_p1_daily_flags.csv", parse_dates=["date"]).set_index("date")
    dd = pd.read_csv(REPO / "data" / "q042_backtest_trades.csv",
                     parse_dates=["entry_date", "exit_date"])
    hv_bg = pd.read_csv(OUT / "q072_p2_hv_background.csv", parse_dates=["entry_date"])
    # entries (DD + Aftermath) with HV BP snapshot
    return {"daily": daily, "dd": dd, "hv_bg": hv_bg}


def hv_bucket(bp_pct: float) -> str:
    for lo, hi, name in HV_BUCKETS:
        if lo < bp_pct <= hi:
            return name
    return "heavy>40" if bp_pct > 40 else "low<20"


# ── DD Overlay trade path reconstruction ──────────────────────────────────────
def build_dd_paths(d: dict) -> pd.DataFrame:
    print("Building DD Overlay post-entry path (BS+skew MTM)...")
    daily = d["daily"]
    hv_lookup = d["hv_bg"].set_index(["sleeve", "entry_date"])

    rows = []
    for _, t in d["dd"].iterrows():
        entry = t["entry_date"]
        exit_d = t["exit_date"]
        long_K = t["long_strike"]
        short_K = t["short_strike"]
        debit = t["debit_per_share"]
        contracts = t["contracts"]
        dte_orig = 90  # DD Overlay SPEC-094 DTE 90

        # walk daily index from entry to exit
        if entry not in daily.index:
            continue
        path_idx = daily.index[(daily.index >= entry) & (daily.index <= exit_d)]
        if len(path_idx) < 2:
            continue

        days_held = (path_idx - entry).days
        daily_pnl = []
        for d_offset, dt in zip(days_held, path_idx):
            spx_t = daily.loc[dt, "spx_close"]
            vix_t = daily.loc[dt, "vix"]
            if pd.isna(spx_t) or pd.isna(vix_t):
                daily_pnl.append(np.nan)
                continue
            dte_remaining = max(dte_orig - d_offset, 1)
            cur_spread = price_spread(spx_t, vix_t, long_K, short_K, dte_remaining)
            pnl = (cur_spread - debit) * contracts * 100
            daily_pnl.append(pnl)
        pnl_arr = np.array(daily_pnl)
        valid = ~np.isnan(pnl_arr)
        if valid.sum() == 0:
            continue

        # horizon snapshots (relative to entry index 0)
        horizon_pnl = {}
        for h in HORIZONS:
            if h < len(pnl_arr) and not np.isnan(pnl_arr[h]):
                horizon_pnl[f"pnl_{h}d"] = round(float(pnl_arr[h]), 2)
            else:
                horizon_pnl[f"pnl_{h}d"] = None

        # MAE/MFE within MAE_WINDOW
        window = pnl_arr[:MAE_WINDOW][valid[:MAE_WINDOW]]
        if len(window) == 0:
            mae = mfe = t_mae = None
        else:
            mae = float(window.min())
            mfe = float(window.max())
            t_mae = int(np.argmin(window))

        # HV BP at entry
        try:
            hv_bp = hv_lookup.loc[("DD_Overlay", entry), "hv_bp_pct"]
        except KeyError:
            hv_bp = None

        rows.append({
            "sleeve": f"DD_{t['sleeve_id']}",
            "entry_date": entry,
            "exit_date": exit_d,
            "hv_bp_at_entry": round(float(hv_bp), 2) if hv_bp is not None else None,
            "hv_bucket": hv_bucket(float(hv_bp)) if hv_bp is not None else None,
            **horizon_pnl,
            "mae_dollar": round(mae, 2) if mae is not None else None,
            "mfe_dollar": round(mfe, 2) if mfe is not None else None,
            "time_to_mae_days": t_mae,
            "exit_pnl": float(t["exit_pnl"]),
            "trade_days": int(valid.sum()),
        })
    return pd.DataFrame(rows)


# ── Aftermath window path (SPX-based proxy) ──────────────────────────────────
def build_aftermath_paths(d: dict) -> pd.DataFrame:
    print("Building Aftermath window post-entry path (SPX proxy + VIX)...")
    daily = d["daily"]
    hv_lookup = d["hv_bg"].set_index(["sleeve", "entry_date"])

    # detect window start days = first day of contiguous is_aftermath
    flag = daily["aftermath_active"].astype(bool).values
    entries = []
    prev = False
    for i, f in enumerate(flag):
        if f and not prev:
            entries.append(daily.index[i])
        prev = f

    rows = []
    for entry in entries:
        spx0 = daily.loc[entry, "spx_close"]
        vix0 = daily.loc[entry, "vix"]
        if pd.isna(spx0):
            continue

        # walk MAE_WINDOW days forward
        idx_pos = daily.index.get_loc(entry)
        forward = daily.iloc[idx_pos:idx_pos + MAE_WINDOW + 1]
        spx_ret = (forward["spx_close"] - spx0) / spx0
        vix_delta = forward["vix"] - vix0
        valid = ~spx_ret.isna()
        if valid.sum() == 0:
            continue

        horizon_ret = {}
        for h in HORIZONS:
            if h < len(spx_ret) and not pd.isna(spx_ret.iloc[h]):
                horizon_ret[f"spx_ret_{h}d"] = round(float(spx_ret.iloc[h]) * 100, 3)
                horizon_ret[f"vix_delta_{h}d"] = round(float(vix_delta.iloc[h]), 2)
            else:
                horizon_ret[f"spx_ret_{h}d"] = None
                horizon_ret[f"vix_delta_{h}d"] = None

        mae_ret = float(spx_ret[valid].min())
        mfe_ret = float(spx_ret[valid].max())
        max_vix = float(forward["vix"].max())

        try:
            hv_bp = hv_lookup.loc[("Aftermath", entry), "hv_bp_pct"]
        except KeyError:
            hv_bp = None

        rows.append({
            "sleeve": "Aftermath",
            "entry_date": entry,
            "hv_bp_at_entry": round(float(hv_bp), 2) if hv_bp is not None else None,
            "hv_bucket": hv_bucket(float(hv_bp)) if hv_bp is not None else None,
            **horizon_ret,
            "mae_ret_pct": round(mae_ret * 100, 3),
            "mfe_ret_pct": round(mfe_ret * 100, 3),
            "max_vix_30d": round(max_vix, 2),
            "entry_vix": round(float(vix0), 2),
        })
    return pd.DataFrame(rows)


def bucket_summary(dd_df: pd.DataFrame, af_df: pd.DataFrame) -> pd.DataFrame:
    print("Aggregating by HV bucket × split...")
    rows = []
    for split_name, (s, e) in SPLITS.items():
        # DD by bucket
        dd_sub = dd_df[(dd_df.entry_date >= s) & (dd_df.entry_date <= e)]
        for bucket in ["low<20", "mid20-40", "heavy>40"]:
            sub = dd_sub[dd_sub.hv_bucket == bucket]
            if len(sub) == 0:
                continue
            rows.append({
                "split": split_name,
                "sleeve": "DD_Overlay",
                "hv_bucket": bucket,
                "n": len(sub),
                "exit_pnl_median": round(float(sub["exit_pnl"].median()), 0),
                "exit_pnl_worst": round(float(sub["exit_pnl"].min()), 0),
                "exit_pnl_mean": round(float(sub["exit_pnl"].mean()), 0),
                "mae_median": round(float(sub["mae_dollar"].median()), 0),
                "mae_p10": round(float(sub["mae_dollar"].quantile(0.10)), 0),
                "mae_worst": round(float(sub["mae_dollar"].min()), 0),
                "mfe_median": round(float(sub["mfe_dollar"].median()), 0),
                "time_to_mae_median": float(sub["time_to_mae_days"].median()),
                "pnl_10d_median": round(float(sub["pnl_10d"].dropna().median()), 0)
                    if sub["pnl_10d"].notna().any() else None,
                "pnl_20d_median": round(float(sub["pnl_20d"].dropna().median()), 0)
                    if sub["pnl_20d"].notna().any() else None,
            })

        # Aftermath by bucket
        af_sub = af_df[(af_df.entry_date >= s) & (af_df.entry_date <= e)]
        for bucket in ["low<20", "mid20-40", "heavy>40"]:
            sub = af_sub[af_sub.hv_bucket == bucket]
            if len(sub) == 0:
                continue
            rows.append({
                "split": split_name,
                "sleeve": "Aftermath",
                "hv_bucket": bucket,
                "n": len(sub),
                "spx_ret_5d_median": round(float(sub["spx_ret_5d"].dropna().median()), 3),
                "spx_ret_10d_median": round(float(sub["spx_ret_10d"].dropna().median()), 3),
                "spx_ret_20d_median": round(float(sub["spx_ret_20d"].dropna().median()), 3),
                "mae_ret_median": round(float(sub["mae_ret_pct"].median()), 3),
                "mae_ret_worst": round(float(sub["mae_ret_pct"].min()), 3),
                "max_vix_30d_median": round(float(sub["max_vix_30d"].median()), 2),
                "exit_pnl_median": None,
                "exit_pnl_worst": None,
                "exit_pnl_mean": None,
                "mae_median": None,
                "mae_p10": None,
                "mae_worst": None,
                "mfe_median": None,
                "time_to_mae_median": None,
                "pnl_10d_median": None,
                "pnl_20d_median": None,
            })
    return pd.DataFrame(rows)


def main():
    d = load_data()
    dd_paths = build_dd_paths(d)
    af_paths = build_aftermath_paths(d)
    summary = bucket_summary(dd_paths, af_paths)

    dd_paths.to_csv(OUT / "q072_p3_1_dd_paths.csv", index=False)
    af_paths.to_csv(OUT / "q072_p3_1_aftermath_paths.csv", index=False)
    summary.to_csv(OUT / "q072_p3_1_bucket_summary.csv", index=False)

    print("\n" + "=" * 70)
    print("Q072 P3.1 — Summary")
    print("=" * 70)

    print(f"\nDD Overlay paths reconstructed: {len(dd_paths)}")
    print(f"Aftermath windows reconstructed: {len(af_paths)}")

    print("\nDD Overlay — HV BP bucket × split (exit PnL & MAE):")
    dd_view = summary[summary.sleeve == "DD_Overlay"][
        ["split", "hv_bucket", "n", "exit_pnl_median", "exit_pnl_worst",
         "exit_pnl_mean", "mae_median", "mae_p10", "mae_worst",
         "time_to_mae_median", "pnl_20d_median"]
    ]
    print(dd_view.to_string(index=False))

    print("\nAftermath — HV BP bucket × split (SPX 20d ret & max drawdown):")
    af_view = summary[summary.sleeve == "Aftermath"][
        ["split", "hv_bucket", "n", "spx_ret_5d_median", "spx_ret_10d_median",
         "spx_ret_20d_median", "mae_ret_median", "mae_ret_worst",
         "max_vix_30d_median"]
    ]
    print(af_view.to_string(index=False))

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
