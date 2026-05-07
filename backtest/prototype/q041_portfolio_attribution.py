"""
Q041 Portfolio Attribution — Multi-Sleeve Joint Backtest

Tier 3 prototype output for SPEC-085 F3 attribution carrier.

Purpose
-------
Quantify how much account-level deployment efficiency Q041 sleeves add over
the post-SPEC-084 J3 SPX baseline. Emits the four headline metrics consumed by
SPEC-085 /api/portfolio/attribution: idle_day_capture, delta_avg_bp,
bp_fill_contribution, worst_day_overlap.

Window
------
2023-01-02 -> 2026-04-29 (matches Q045 phase2d J3 BP timeline).
~3.3 years, 873 trading days.

Honest data caveats (also written into the JSON `notes` field)
- option-level multi-sleeve simulation is NOT 19y; only ~3.3y is covered
- COVID 2020 NOT covered
- 2022 bear market only partially covered (J3 baseline starts 2023-01)
- forward-tracking validation against live deployment still required

Sleeves simulated
- J3 baseline (SPX matrix): read from data/q045_phase2d_idle_bp_timeline.csv
- Q041 Tier 1 SPX CSP   Δ0.20 DTE30, BP cap 20%
- Q041 Tier 2 GOOGL CSP Δ0.20 DTE21, BP allocation 7.5% (single-name <=10%, combined <=15%)
- Q041 Tier 2 AMZN  CSP Δ0.25 DTE21, BP allocation 7.5% (single-name <=10%, combined <=15%)
- Q041 Tier 3 (COST/JPM): SKIPPED — review_only per Q041 packet

Sizing rationale: Tier 2 single-name cap 10% but combined cap 15% binds when both
open. Conservative per-cycle allocation = 7.5% each so combined sits at 15% when
both open and respects single-name cap when only one open. Matches SPEC-085
sizing_reference text.

Mechanics
---------
- Monthly third-Friday rolls, non-overlapping cycles per sleeve
- BS delta selection (R=4.5%, slippage 3% on premium)
- For SPX: spot from data/market_cache/yahoo__GSPC__max__1d.pkl
- For GOOGL/AMZN: spot extracted from option chain via put-call parity
  S ≈ (C - P) + K * exp(-rT) on nearest-expiry strikes, median across strikes
- BP usage timeline per sleeve = bp_cap_pct on every trading day the position is open
  (entry_date inclusive, expiry exclusive — exit at expiry close)

Metrics
-------
1. idle_day_capture (days)
   trading days where J3 BP_pct = 0 AND any Q041 sleeve has BP > 0
2. delta_avg_bp (pct_points)
   mean(joint daily BP) - mean(J3 daily BP), where joint = J3 + Q041
3. bp_fill_contribution (pct_points)
   mean(Q041 daily BP) — additive contribution to average BP utilization
4. worst_day_overlap (pct_points)
   share of bottom-5% SPX daily-return days in window where any Q041 sleeve is open
   (tail-risk co-occurrence proxy; positive means we add short exposure during SPX tails)

Run
---
arch -arm64 venv/bin/python -m backtest.prototype.q041_portfolio_attribution

Outputs
-------
- data/q041_portfolio_attribution_latest.json (consumed by SPEC-085)
- stdout summary table (cycles per sleeve, joint BP stats, attribution metrics)
"""

from __future__ import annotations

import calendar
import json
import pickle
import sys
import warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data" / "q041_historical"
GSPC_PATH = ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
J3_TIMELINE = ROOT / "data" / "q045_phase2d_idle_bp_timeline.csv"
ARTIFACT_PATH = ROOT / "data" / "q041_portfolio_attribution_latest.json"

R = 0.045
SLIP = 0.03
PREMIUM_FLOOR = 0.10
ACCOUNT = 150_000.0

WIN_START = pd.Timestamp("2023-01-02")
WIN_END = pd.Timestamp("2026-04-29")

SLEEVES = [
    {"id": "tier1_spx_csp",   "symbol": "SPX",   "dte": 30, "target_delta": 0.20, "bp_cap_pct": 20.0},
    {"id": "tier2_googl_csp", "symbol": "GOOGL", "dte": 21, "target_delta": 0.20, "bp_cap_pct": 7.5},
    {"id": "tier2_amzn_csp",  "symbol": "AMZN",  "dte": 21, "target_delta": 0.25, "bp_cap_pct": 7.5},
]


# ---------- BS helpers ----------
def bs_price(S, K, T, r, sigma, ot):
    if T < 1e-6 or sigma < 1e-4:
        return max(0.0, (S - K) if ot == "C" else (K - S))
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if ot == "C":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_iv(S, K, T, r, price, ot):
    if price < 1e-6 or T < 1e-6:
        return np.nan
    intrinsic = max(0.0, (S - K) if ot == "C" else (K - S))
    if price <= intrinsic:
        return np.nan
    try:
        return brentq(lambda s: bs_price(S, K, T, r, s, ot) - price, 0.001, 5.0, maxiter=50)
    except Exception:
        return np.nan


def bs_delta(S, K, T, r, sigma, ot):
    if T < 1e-6 or sigma < 1e-4:
        return np.nan
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1) if ot == "C" else (norm.cdf(d1) - 1.0)


# ---------- Roll-date scheduler ----------
def third_friday(year, month):
    cal = calendar.monthcalendar(year, month)
    fridays = [w[4] for w in cal if w[4] != 0]
    return pd.Timestamp(year, month, fridays[2])


def build_roll_dates(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    rds = []
    for yr in range(start.year, end.year + 1):
        for mo in range(1, 13):
            tf = third_friday(yr, mo)
            if start <= tf <= end:
                rds.append(tf)
    return rds


# ---------- Spot extractors ----------
def load_spx_spot() -> dict:
    with open(GSPC_PATH, "rb") as f:
        gspc = pickle.load(f)
    gspc.index = pd.to_datetime(gspc.index).tz_localize(None)
    return gspc["Close"].to_dict()


def parity_spot_per_date(df: pd.DataFrame) -> dict:
    """
    Estimate underlying spot per date via put-call parity on the nearest-expiry chain.
    S ≈ (C - P) + K * exp(-rT), median across strikes with both C and P quoted.
    """
    out = {}
    for d, sub in df.groupby("date"):
        exps = np.sort(sub["expiry"].unique())
        # nearest expiry with at least 5 strikes having both C and P
        chosen_exp = None
        for e in exps:
            if (e - d).days < 1:
                continue
            chunk = sub[sub["expiry"] == e]
            calls = chunk[chunk["option_type"] == "C"].set_index("strike")["close"]
            puts = chunk[chunk["option_type"] == "P"].set_index("strike")["close"]
            common = calls.index.intersection(puts.index)
            if len(common) >= 5:
                chosen_exp = e
                T = max((e - d).days / 365.0, 1e-3)
                disc = np.exp(-R * T)
                implied = pd.Series({k: (calls[k] - puts[k]) + k * disc for k in common})
                # ATM band: take strikes whose implied is near the median to denoise
                med = float(implied.median())
                band = implied[(implied > med * 0.85) & (implied < med * 1.15)]
                if len(band) >= 3:
                    out[d] = float(band.median())
                else:
                    out[d] = med
                break
        if chosen_exp is None:
            continue
    return out


def get_px(d: pd.Timestamp, px_dict: dict, lookback: int = 5):
    for i in range(lookback):
        t = d - pd.Timedelta(days=i)
        if t in px_dict:
            return px_dict[t]
    return None


# ---------- Cycle simulator ----------
def find_expiry_dte(roll_date, df_slice, dte_tgt, win=10):
    avail = [e for e in df_slice["expiry"].unique() if e > roll_date]
    cands = [e for e in avail if abs((e - roll_date).days - dte_tgt) <= win]
    if not cands:
        cands = avail
    if not cands:
        return None
    return min(cands, key=lambda e: abs((e - roll_date).days - dte_tgt))


def simulate_sleeve(sleeve: dict, roll_dates: list[pd.Timestamp]) -> pd.DataFrame:
    sym = sleeve["symbol"]
    dte_tgt = sleeve["dte"]
    target_delta = sleeve["target_delta"]

    df = pd.read_parquet(DATA_DIR / f"{sym}.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df["expiry"] = pd.to_datetime(df["expiry"])

    df_by_date = {d: g for d, g in df.groupby("date")}

    if sym == "SPX":
        px_dict = load_spx_spot()
    else:
        px_dict = parity_spot_per_date(df)

    cycles = []
    prev_expiry = None
    for rd in roll_dates:
        if prev_expiry is not None and rd < prev_expiry:
            continue
        rd_actual = rd
        if rd not in df_by_date:
            for i in range(1, 5):
                t = rd - pd.Timedelta(days=i)
                if t in df_by_date:
                    rd_actual = t
                    break
            else:
                continue
        slice_ = df_by_date[rd_actual]
        exp = find_expiry_dte(rd, slice_, dte_tgt)
        if exp is None:
            continue
        S_entry = get_px(rd, px_dict)
        S_exit = get_px(exp, px_dict)
        if S_entry is None or S_exit is None:
            continue
        T = max((exp - rd).days / 365.0, 1e-3)

        sub = slice_[
            (slice_["expiry"] == exp)
            & (slice_["option_type"] == "P")
            & (slice_["close"] > PREMIUM_FLOOR)
        ]
        records = []
        for _, row in sub.iterrows():
            iv = bs_iv(S_entry, row["strike"], T, R, row["close"], "P")
            if np.isnan(iv):
                continue
            d = bs_delta(S_entry, row["strike"], T, R, iv, "P")
            if np.isnan(d):
                continue
            records.append({"K": row["strike"], "price": row["close"], "iv": iv, "delta": d})
        if not records:
            continue

        best = min(records, key=lambda r: abs(abs(r["delta"]) - target_delta))
        K = best["K"]
        price = best["price"]
        net_prem = price * (1.0 - SLIP)
        settle = max(0.0, K - S_exit)
        cycle_pnl = net_prem - settle  # per share, multiply by 100 for $/contract
        bp_per_contract = K  # naked CSP: BP ≈ strike (margin requirement proxy)

        cycles.append({
            "sleeve_id": sleeve["id"],
            "entry_date": pd.Timestamp(rd),
            "exit_date": pd.Timestamp(exp),
            "S_entry": float(S_entry),
            "S_exit": float(S_exit),
            "K": float(K),
            "delta": float(best["delta"]),
            "price": float(price),
            "net_prem": float(net_prem),
            "settle": float(settle),
            "pnl_per_share": float(cycle_pnl),
            "ret_per_bp": float(cycle_pnl / bp_per_contract) if bp_per_contract > 0 else 0.0,
            "hit": bool(S_exit < K),
        })
        prev_expiry = exp

    return pd.DataFrame(cycles)


# ---------- Daily BP overlay ----------
def sleeve_bp_timeline(cycles: pd.DataFrame, bp_cap_pct: float, idx: pd.DatetimeIndex) -> pd.Series:
    series = pd.Series(0.0, index=idx)
    if cycles.empty:
        return series
    for _, row in cycles.iterrows():
        e = pd.Timestamp(row["entry_date"])
        x = pd.Timestamp(row["exit_date"])
        mask = (idx >= e) & (idx < x)  # entry inclusive, expiry exclusive
        series.loc[mask] = bp_cap_pct
    return series


def main():
    print("Q041 Portfolio Attribution — multi-sleeve joint backtest")
    print("=" * 72)

    # ---- 1. J3 baseline timeline ----
    if not J3_TIMELINE.exists():
        raise SystemExit(f"Missing J3 baseline timeline: {J3_TIMELINE}")
    j3 = pd.read_csv(J3_TIMELINE)
    j3.rename(columns={j3.columns[0]: "date"}, inplace=True)
    j3["date"] = pd.to_datetime(j3["date"])
    j3 = j3[(j3["date"] >= WIN_START) & (j3["date"] <= WIN_END)]
    j3 = j3.set_index("date").sort_index()
    j3 = j3[j3.index.weekday < 5]  # trading days only
    idx = j3.index
    print(f"J3 baseline: {len(idx)} trading days, {idx.min().date()} → {idx.max().date()}")
    print(f"J3 mean BP%: {j3['j3_bp_pct'].mean():.2f}")
    j3_idle_days = (j3["j3_bp_pct"] == 0).sum()
    print(f"J3 fully-idle days: {j3_idle_days} ({j3_idle_days/len(j3)*100:.1f}%)")

    # ---- 2. Simulate sleeves ----
    roll_dates = build_roll_dates(WIN_START - pd.Timedelta(days=15), WIN_END)
    sleeve_results = {}
    sleeve_timelines = {}
    for s in SLEEVES:
        print(f"\n[sleeve] {s['id']} (sym={s['symbol']}, dte={s['dte']}, Δ={s['target_delta']}, cap={s['bp_cap_pct']}%)")
        cycles = simulate_sleeve(s, roll_dates)
        if cycles.empty:
            print("  no cycles produced")
            continue
        cycles = cycles[(cycles["entry_date"] <= WIN_END) & (cycles["exit_date"] >= WIN_START)]
        wr = (cycles["pnl_per_share"] > 0).mean() if len(cycles) else 0.0
        cum_ret = float(np.prod(1.0 + cycles["ret_per_bp"].values) - 1.0) if len(cycles) else 0.0
        worst = float(cycles["ret_per_bp"].min()) if len(cycles) else 0.0
        mean_dte = float((cycles["exit_date"] - cycles["entry_date"]).dt.days.mean()) if len(cycles) else 0.0
        print(f"  N={len(cycles)} cycles | WR={wr*100:.0f}% | CumRetOnBP={cum_ret*100:.1f}% | WorstCycleRetOnBP={worst*100:.2f}% | meanDTE={mean_dte:.1f}")
        sleeve_results[s["id"]] = cycles
        sleeve_timelines[s["id"]] = sleeve_bp_timeline(cycles, s["bp_cap_pct"], idx)

    # ---- 3. Build joint daily BP timeline ----
    q041_total = pd.Series(0.0, index=idx)
    for tl in sleeve_timelines.values():
        q041_total += tl

    joint = j3["j3_bp_pct"].astype(float) + q041_total
    delta_avg_bp = float(joint.mean() - j3["j3_bp_pct"].mean())
    bp_fill_contribution = float(q041_total.mean())

    j3_zero_mask = j3["j3_bp_pct"] == 0
    q041_open_mask = q041_total > 0
    idle_capture_days = int((j3_zero_mask & q041_open_mask).sum())
    idle_capture_share_pct = float(idle_capture_days / max(j3_idle_days, 1) * 100.0)

    # ---- 4. Worst-day overlap ----
    spx_px = load_spx_spot()
    spx_close = pd.Series({pd.Timestamp(k): v for k, v in spx_px.items()})
    spx_close = spx_close.sort_index()
    spx_close = spx_close[(spx_close.index >= WIN_START) & (spx_close.index <= WIN_END)]
    spx_ret = spx_close.pct_change().dropna()
    # align to joint index where overlap exists
    spx_ret = spx_ret[spx_ret.index.isin(idx)]
    n_tail = max(1, int(np.floor(len(spx_ret) * 0.05)))
    worst_days = spx_ret.nsmallest(n_tail).index
    overlap_count = int((q041_total.reindex(worst_days).fillna(0) > 0).sum())
    worst_day_overlap_pct = float(overlap_count / n_tail * 100.0) if n_tail else 0.0

    # Occupancy baseline + excess overlap (tail-clustering signal vs. plain occupancy)
    q041_open_share_pct = float((q041_total > 0).mean() * 100.0)
    excess_overlap_pp = float(worst_day_overlap_pct - q041_open_share_pct)

    # ---- 5. Diagnostics ----
    print("\n" + "=" * 72)
    print("Joint BP statistics")
    print("-" * 72)
    print(f"  J3 mean BP%             : {j3['j3_bp_pct'].mean():.2f}")
    print(f"  Q041 mean BP%           : {q041_total.mean():.2f}")
    print(f"  Joint mean BP%          : {joint.mean():.2f}")
    print(f"  Joint max BP%           : {joint.max():.2f}")
    print(f"  Days w/ joint BP > 50%  : {(joint > 50).sum()}")
    print(f"  Days w/ joint BP > 35%  : {(joint > 35).sum()}")

    print("\nAttribution metrics")
    print("-" * 72)
    print(f"  idle_day_capture        : {idle_capture_days} days  ({idle_capture_share_pct:.1f}% of J3 idle days)")
    print(f"  delta_avg_bp            : +{delta_avg_bp:.2f} pp")
    print(f"  bp_fill_contribution    : +{bp_fill_contribution:.2f} pp")
    print(f"  worst_day_overlap       : {worst_day_overlap_pct:.1f}%  (n_tail={n_tail} days)")
    print(f"  Q041 open occupancy     : {q041_open_share_pct:.1f}%  (baseline for overlap)")
    print(f"  excess overlap vs base  : {excess_overlap_pp:+.1f} pp  (tail-clustering signal)")

    # ---- 6. Worst cycle overlap diagnostic ----
    print("\nPer-sleeve worst cycles")
    print("-" * 72)
    for sid, cyc in sleeve_results.items():
        if cyc.empty:
            continue
        worst_row = cyc.loc[cyc["ret_per_bp"].idxmin()]
        print(f"  {sid}: worst entry {worst_row['entry_date'].date()} ret={worst_row['ret_per_bp']*100:.2f}% K={worst_row['K']:.1f} S_exit={worst_row['S_exit']:.1f}")

    # ---- 7. Emit artifact ----
    artifact = {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": "backtest/prototype/q041_portfolio_attribution.py",
        "window": {
            "start": str(idx.min().date()),
            "end": str(idx.max().date()),
            "trading_days": int(len(idx)),
        },
        "account_size_usd": ACCOUNT,
        "sleeves_simulated": [
            {"id": s["id"], "symbol": s["symbol"], "dte": s["dte"], "target_delta": s["target_delta"], "bp_cap_pct": s["bp_cap_pct"], "n_cycles": int(len(sleeve_results.get(s["id"], pd.DataFrame())))}
            for s in SLEEVES
        ],
        "j3_baseline": {
            "mean_bp_pct": round(float(j3["j3_bp_pct"].mean()), 2),
            "fully_idle_days": int(j3_idle_days),
            "fully_idle_share_pct": round(float(j3_idle_days / len(j3) * 100), 2),
        },
        "idle_day_capture": {
            "value": idle_capture_days,
            "unit": "days",
            "share_of_j3_idle_pct": round(idle_capture_share_pct, 2),
        },
        "delta_avg_bp": {
            "value": round(delta_avg_bp, 2),
            "unit": "pct_points",
        },
        "bp_fill_contribution": {
            "value": round(bp_fill_contribution, 2),
            "unit": "pct_points",
        },
        "worst_day_overlap": {
            "value": round(worst_day_overlap_pct, 2),
            "unit": "pct_points",
            "n_tail_days": int(n_tail),
            "definition": "share of bottom-5% SPX daily-return days where any Q041 sleeve had open exposure",
            "q041_open_occupancy_pct": round(q041_open_share_pct, 2),
            "excess_overlap_vs_occupancy_pp": round(excess_overlap_pp, 2),
            "interpretation": "compare worst_day_overlap against q041_open_occupancy_pct; near-zero excess = no tail clustering, large positive excess = Q041 disproportionately exposed during SPX tails",
        },
        "joint_bp_diagnostics": {
            "mean_pct": round(float(joint.mean()), 2),
            "max_pct": round(float(joint.max()), 2),
            "days_above_35_pct": int((joint > 35).sum()),
            "days_above_50_pct": int((joint > 50).sum()),
        },
        "notes": (
            "Window 2023-01-02 to 2026-04-29 (~3.3y). Joint multi-sleeve backtest restricted "
            "by Q041 historical option data availability (2022-05 to 2026-05). Does NOT cover "
            "COVID 2020 or full 2022 bear market. SPX spot from yfinance ^GSPC; GOOGL/AMZN spot "
            "via put-call parity from option chain. Tier 2 single-name allocation is 7.5% per "
            "sleeve so combined Tier 2 sits at packet cap 15% when both open and respects the "
            "10% single-name cap when only one open. Tier 3 (COST/JPM) is review-only per Q041 "
            "packet and not simulated. CSP BP is approximated as strike (margin requirement "
            "proxy) which slightly overstates BP vs PM defined-risk; metrics are consistent "
            "across sleeves under this proxy. SPEC-085 forward-tracking surface should still "
            "be the primary evidence source; this artifact is a research-side prior, not a "
            "live-validated quantification."
        ),
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2))
    print(f"\nArtifact written: {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
