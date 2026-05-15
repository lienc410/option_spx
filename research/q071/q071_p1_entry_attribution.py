"""Q071 P1 — V2f entry attribution (no new gates).

Replicates research.strategies.ES_puts.backtest._run_phase2_v2f_on_frame logic
with attribution hooks: at each entry, records
  - IVP_252 (rolling VIX percentile, 252 TD lookback)
  - VIX absolute level (entry-day close)
  - VIX 5-TD trend (today vs prior 5-TD avg)
  - Active slot count at entry decision

Each resulting trade is labeled with the entry-day bucket. Then per-bucket
metrics are aggregated to test the prompt's key question:
  Does IVP_252 / VIX bucket exhibit an edge in V2f's actual entry distribution?

Outputs (research/q071/):
  q071_p1_trades_labeled.csv   — every V2f trade with bucket labels
  q071_p1_results_ivp.csv      — per IVP bucket
  q071_p1_results_vix.csv      — per VIX abs bucket
  q071_p1_results_combined.csv — IVP × VIX joint bucket
  q071_p1_results_vixtrend.csv — VIX 5TD trend bucket
  q071_p1_results_slots.csv    — active slots at entry bucket
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from research.strategies.ES_puts.backtest import (
    _load_data, _trend, _bp_per_contract,
    V2F_ENTRY_DTE, V2F_EXIT_DTE, V2F_ENTRY_FREQ, V2F_MAX_SLOTS,
    V2F_CLUSTER_THRESHOLD, V2F_CLUSTER_ENTRY_FREQ,
    V2F_STOP_MULT, V2F_PROFIT_TARGET, TARGET_DELTA,
    SPX_MULTIPLIER, WARMUP_DAYS, P2_INITIAL_EQUITY, P2_N_CONTRACTS,
)
from backtest.pricer import find_strike_for_delta, put_price
from signals.trend import TrendSignal

OUT = REPO / "research" / "q071"
OUT.mkdir(parents=True, exist_ok=True)

START = "2000-01-01"
END   = None  # latest available


def compute_ivp252(vix_series: pd.Series) -> pd.Series:
    """Rolling 252-TD IVP: % of prior 251 days where VIX was < today's value."""
    def w(arr):
        cur = arr[-1]
        return float((arr[:-1] < cur).mean() * 100.0)
    return vix_series.rolling(252).apply(w, raw=True)


def run_attributed_v2f(mode: str = "filtered", enable_m1: bool = True) -> pd.DataFrame:
    """V2f base engine replica with per-entry attribution.

    Returns a DataFrame of completed trades; each row carries the entry-day
    IVP_252, VIX abs, VIX 5TD avg, and n_active_at_entry.
    """
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(START)]
    if END:
        sim = sim[sim.index <= pd.Timestamp(END)]

    ivp252 = compute_ivp252(data["vix"])
    vix5_avg_series = data["vix"].rolling(5).mean().shift(1)  # prior 5TD avg

    trade_rows: list[dict] = []
    positions: dict[int, dict] = {}
    next_id = 0
    day_counter = 0
    days_since_entry = V2F_ENTRY_FREQ

    for date, row in sim.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        sig = vix / 100.0
        dstr = date.strftime("%Y-%m-%d")
        day_counter += 1
        days_since_entry += 1

        window = full_spx[full_spx.index <= date].iloc[-200:]
        warmed = len(window) >= WARMUP_DAYS
        trend_ok = True
        if mode == "filtered" and warmed:
            trend_ok = (_trend(window, spx) == TrendSignal.BULLISH)

        # --- close logic (matches engine: exits before entry on same day) ---
        to_close = []
        for pid, pos in positions.items():
            pos["expiry_dte"] -= 1
            cur_val = put_price(spx, pos["strike"], max(pos["expiry_dte"], 0), sig)
            reason = None
            if pos["expiry_dte"] <= V2F_EXIT_DTE:
                reason = "ladder_exit"
            elif cur_val >= pos["stop_premium"]:
                reason = "stop_loss"
            elif cur_val <= pos["profit_premium"]:
                reason = "profit_target"
            elif pos["expiry_dte"] <= 0:
                reason = "expiry"
            if reason:
                pos["exit_date"]    = dstr
                pos["exit_spx"]     = spx
                pos["exit_premium"] = cur_val
                pos["exit_reason"]  = reason
                pos["pnl"]          = (pos["entry_premium"] - cur_val) * pos["contracts"] * SPX_MULTIPLIER
                trade_rows.append(pos.copy())
                to_close.append(pid)
            else:
                pos["prev_val"] = cur_val
        for pid in to_close:
            del positions[pid]

        # --- entry logic ---
        n_active = len(positions)
        if enable_m1 and n_active >= V2F_CLUSTER_THRESHOLD:
            entry_freq = V2F_CLUSTER_ENTRY_FREQ
        else:
            entry_freq = V2F_ENTRY_FREQ
        cadence_mode = "relative" if enable_m1 else "legacy"
        cadence_ok = (
            days_since_entry >= entry_freq
            if cadence_mode == "relative"
            else day_counter % entry_freq == 0
        )
        should_enter = warmed and trend_ok and cadence_ok and n_active < V2F_MAX_SLOTS

        if should_enter:
            k = find_strike_for_delta(spx, V2F_ENTRY_DTE, sig, TARGET_DELTA, False)
            prem = put_price(spx, k, V2F_ENTRY_DTE, sig)
            if prem > 0.5:
                next_id += 1
                n = float(P2_N_CONTRACTS)
                bp_per = _bp_per_contract(spx, k, prem)
                cur_ivp = float(ivp252.loc[date]) if date in ivp252.index else float("nan")
                cur_v5  = float(vix5_avg_series.loc[date]) if date in vix5_avg_series.index else float("nan")
                positions[next_id] = {
                    "id":                next_id,
                    "entry_date":        dstr,
                    "expiry_dte":        V2F_ENTRY_DTE,
                    "strike":            k,
                    "entry_spx":         spx,
                    "entry_vix":         vix,
                    "entry_premium":     prem,
                    "contracts":         n,
                    "bp_per":            bp_per,
                    "bp_used":           n * bp_per,
                    "stop_premium":      prem * V2F_STOP_MULT,
                    "profit_premium":    prem * V2F_PROFIT_TARGET,
                    "prev_val":          prem,
                    "ivp252_entry":      cur_ivp,
                    "vix5_avg_prior":    cur_v5,
                    "n_active_at_entry": n_active,
                }
                if cadence_mode == "relative":
                    days_since_entry = 0

    return pd.DataFrame(trade_rows)


# ── Bucket labelers ──────────────────────────────────────────────────────

def ivp_bucket(v: float) -> str:
    if pd.isna(v): return "NA"
    if v < 30: return "1_<30"
    if v < 43: return "2_30-43"
    if v < 55: return "3_43-55"
    if v < 70: return "4_55-70"
    return "5_>70"


def vix_bucket(v: float) -> str:
    if v < 15: return "1_<15"
    if v < 20: return "2_15-20"
    if v < 25: return "3_20-25"
    if v < 30: return "4_25-30"
    return "5_>30"


def vix_trend_bucket(vix_today: float, vix5: float) -> str:
    if pd.isna(vix5) or vix5 <= 0: return "NA"
    if vix_today < vix5 * 0.97: return "1_falling"
    if vix_today > vix5 * 1.03: return "3_rising"
    return "2_flat"


def add_bucket_labels(trades: pd.DataFrame) -> pd.DataFrame:
    trades = trades.copy()
    trades["ivp_bucket"]        = trades["ivp252_entry"].apply(ivp_bucket)
    trades["vix_bucket"]        = trades["entry_vix"].apply(vix_bucket)
    trades["vix_trend_bucket"]  = trades.apply(
        lambda r: vix_trend_bucket(r["entry_vix"], r["vix5_avg_prior"]), axis=1
    )
    trades["slots_bucket"]      = trades["n_active_at_entry"].astype(int).astype(str)

    trades["hold_days"]         = (
        pd.to_datetime(trades["exit_date"]) - pd.to_datetime(trades["entry_date"])
    ).dt.days
    # PnL as fraction of entry premium notional (so cross-vol-regime comparable)
    notional = trades["entry_premium"] * trades["contracts"] * SPX_MULTIPLIER
    trades["pnl_pct_premium"]   = trades["pnl"] / notional.replace(0, np.nan)
    # PnL as fraction of NLV ($500k)
    trades["pnl_pct_nlv"]       = trades["pnl"] / P2_INITIAL_EQUITY
    trades["dollar_per_bp_day"] = trades.apply(
        lambda r: r["pnl"] / (r["bp_used"] * max(r["hold_days"], 1)) if r["bp_used"] > 0 else 0.0,
        axis=1,
    )
    trades["is_stop"]           = (trades["exit_reason"] == "stop_loss").astype(int)
    trades["is_win"]            = (trades["pnl"] > 0).astype(int)
    return trades


def aggregate(trades: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    g = trades.groupby(group_cols, observed=True)
    out = g.agg(
        entry_count        =("pnl",               "size"),
        win_rate           =("is_win",            "mean"),
        avg_pnl_pct        =("pnl_pct_premium",   "mean"),
        median_pnl_pct     =("pnl_pct_premium",   "median"),
        worst_pnl_pct      =("pnl_pct_premium",   "min"),
        worst_pnl_pct_nlv  =("pnl_pct_nlv",       "min"),
        stop_hit_rate      =("is_stop",           "mean"),
        dollar_per_bp_day  =("dollar_per_bp_day", "mean"),
        avg_hold_days      =("hold_days",         "mean"),
        total_pnl          =("pnl",               "sum"),
    ).reset_index()
    return out


def main() -> None:
    print("=" * 100)
    print("Q071 P1 — V2f Entry Attribution")
    print("=" * 100)
    print(f"V2f params: DTE={V2F_ENTRY_DTE} exit={V2F_EXIT_DTE} freq={V2F_ENTRY_FREQ} "
          f"max_slots={V2F_MAX_SLOTS} stop_mult={V2F_STOP_MULT}× profit={V2F_PROFIT_TARGET}")
    print(f"Window: {START} → present, mode=filtered (trend gate ON, SPEC-097 production)")
    print()

    print("Running V2f baseline with attribution …")
    trades = run_attributed_v2f(mode="filtered", enable_m1=True)
    print(f"  Total trades: {len(trades)}")

    if len(trades) == 0:
        print("ERROR: no trades produced")
        return

    trades = add_bucket_labels(trades)
    trades.to_csv(OUT / "q071_p1_trades_labeled.csv", index=False)
    print(f"  Wrote {OUT / 'q071_p1_trades_labeled.csv'}")

    # ── Aggregates ────────────────────────────────────────────────────
    agg_ivp     = aggregate(trades, ["ivp_bucket"])
    agg_vix     = aggregate(trades, ["vix_bucket"])
    agg_combo   = aggregate(trades, ["ivp_bucket", "vix_bucket"])
    agg_trend   = aggregate(trades, ["vix_trend_bucket"])
    agg_slots   = aggregate(trades, ["slots_bucket"])

    agg_ivp.to_csv(OUT / "q071_p1_results_ivp.csv", index=False)
    agg_vix.to_csv(OUT / "q071_p1_results_vix.csv", index=False)
    agg_combo.to_csv(OUT / "q071_p1_results_combined.csv", index=False)
    agg_trend.to_csv(OUT / "q071_p1_results_vixtrend.csv", index=False)
    agg_slots.to_csv(OUT / "q071_p1_results_slots.csv", index=False)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.float_format", lambda x: f"{x:8.3f}")

    print("\n── IVP_252 bucket ──────────────────────────────────────────────")
    print(agg_ivp.to_string(index=False))
    print("\n── VIX abs bucket ──────────────────────────────────────────────")
    print(agg_vix.to_string(index=False))
    print("\n── VIX 5TD-trend bucket ─────────────────────────────────────────")
    print(agg_trend.to_string(index=False))
    print("\n── Active-slots-at-entry bucket ─────────────────────────────────")
    print(agg_slots.to_string(index=False))
    print("\n── IVP × VIX joint bucket (n ≥ 1) ────────────────────────────────")
    print(agg_combo.to_string(index=False))

    # ── Stopping-condition check ──────────────────────────────────────
    print("\n" + "=" * 100)
    print("Stopping condition check (P1 → P2 gate)")
    print("=" * 100)
    if len(agg_ivp) >= 2:
        ivp_pnl_spread  = (agg_ivp["avg_pnl_pct"].max() - agg_ivp["avg_pnl_pct"].min())
        ivp_stop_spread = (agg_ivp["stop_hit_rate"].max() - agg_ivp["stop_hit_rate"].min())
        print(f"IVP bucket avg-pnl-pct spread:  {ivp_pnl_spread:+.4f}  (threshold ±0.05 = 5%)")
        print(f"IVP bucket stop-rate spread:    {ivp_stop_spread:+.4f}  (threshold ±0.05 = 5pp)")
        proceed_ivp = (abs(ivp_pnl_spread) >= 0.05) or (abs(ivp_stop_spread) >= 0.05)
        print(f"  → IVP edge detected:          {'YES' if proceed_ivp else 'NO'}")
    if len(agg_vix) >= 2:
        vix_pnl_spread  = (agg_vix["avg_pnl_pct"].max() - agg_vix["avg_pnl_pct"].min())
        vix_stop_spread = (agg_vix["stop_hit_rate"].max() - agg_vix["stop_hit_rate"].min())
        print(f"VIX bucket avg-pnl-pct spread:  {vix_pnl_spread:+.4f}")
        print(f"VIX bucket stop-rate spread:    {vix_stop_spread:+.4f}")


if __name__ == "__main__":
    main()
