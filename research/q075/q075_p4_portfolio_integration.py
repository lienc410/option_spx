"""Q075 P4 — Portfolio Integration (IC w25 primary, w35 alternative).

Per 2nd Quant G3.5-waived light review (2026-05-20):

  Goal: determine whether IC overlay adds +0.05-0.20pp (Soft) / +0.20pp (Strong)
        ROE without degrading worst-20d / worst-63d by more than 0.25pp
        and without creating capital competition with SPX / Q042.

  Baseline: SPEC-104 Arch-3 + SPEC-105 v2 Gate F (rebuilt per Q074.2 logic)
  Overlay:  IC at Type C first-in-cluster days, forced-exit-on-stress

  Required:
    ΔROE vs baseline
    MaxDD / Worst 20d / Worst 63d / Sharpe (V1/V2/V3 pass)
    Bootstrap (block=250, 20 seeds)
    Walk-forward H1 (2000-2012) / H2 (2013-2026)
    Capital competition / BP-day consumption
    Correlation with existing sleeves (SPX, Q42, cash)
    Crisis window behavior (5 named)
    Operational burden

  Special table (mandatory):
    IC overlay during stress-adjacent periods (10d before any stress trigger):
      entry count
      forced-exit count
      cumulative PnL
      worst 20d contribution

  Promotion bar:
    Strong: ΔROE ≥ +0.20pp + risk thresholds pass
    Soft:   +0.05 to +0.20pp + risk thresholds pass
    Reject: < +0.05pp OR any risk threshold fail

  Risk thresholds (mandatory):
    Worst 20d degradation ≤ +0.25pp vs baseline
    Worst 63d degradation ≤ +0.25pp vs baseline
    No new crisis-window failure
    No capital competition with SPX/Q042 safety reserve

Outputs:
  q075_p4_metrics.csv
  q075_p4_walkforward.csv
  q075_p4_bootstrap.csv
  q075_p4_crisis.csv
  q075_p4_capital_competition.csv
  q075_p4_stress_adjacent.csv
  q075_p4_correlation.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "research" / "q075"
NLV = 894_000.0
CASH_YIELD = 0.043

# ── Locked params (from P3) ───────────────────────────────────────────
FRICTION_PER_TRADE = 50.0
STRESS_SLIPPAGE_BASE = 2.0
STOP_MULT = 2.0
IC_PLANNED_DTE = 14
IV_SHOCK_FORCED = 0.20
PUT_SKEW_SHOCK = 0.10
IC_WIDTHS = [25, 35]   # P4 only: primary + alternative

# Baseline allocations (SPEC-104 + SPEC-105 v2)
P13R_SPX = 0.60
P13R_Q42 = 0.10
HV_ALLOC = 0.0
Q42_ALLOC = 0.175
STRESS_SPX_CAP = 0.50
SECOND_LEG_CAP = 0.40
NORMAL_CAP = 0.80
BOOSTER_CAP = 0.90
FRICTION_ANN_SPX = 0.0035
FRICTION_ANN_Q42 = 0.0005

print("Q075 P4 — Portfolio Integration", flush=True)
print("=" * 70)

# ── Load data ──────────────────────────────────────────────────────────
print("\nLoading data + rebuilding SPEC-104 + SPEC-105 v2 baseline...")
combined = pd.read_csv(REPO / "research" / "q073" / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")

from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
mkt = mkt[(mkt.index >= combined.index.min()) & (mkt.index <= combined.index.max())]

# Build features
mkt["ma50"] = mkt["spx_close"].rolling(50).mean()
mkt["above_ma50"] = (mkt["spx_close"] > mkt["ma50"]).astype(int)
mkt["ath_running"] = mkt["spx_close"].expanding().max()
mkt["ddath"] = mkt["spx_close"] / mkt["ath_running"] - 1.0
mkt["vix_5d_change"] = mkt["vix"] - mkt["vix"].shift(5)

def rolling_pct(series, window=252):
    def w(arr):
        if len(arr) < window:
            return np.nan
        cur = arr[-1]
        return (arr[:-1] < cur).mean() * 100.0
    return series.rolling(window).apply(w, raw=True)

mkt["ivp_252"] = rolling_pct(mkt["vix"], 252)
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)
mkt["normal_state"] = (~mkt["stress_active"] & ~mkt["second_leg_active"])

# ── Build SPEC-104 + SPEC-105 v2 baseline daily PnL ────────────────────
print("Building baseline (SPEC-104 + Gate F)...")
df = combined.copy().join(mkt[["above_ma50", "ddath", "vix", "vix_5d_change", "ivp_252",
                                 "stress_active", "second_leg_active", "normal_state"]], how="left").ffill()

# B4 with Gate F per SPEC-105 v2
def b4_f(row):
    if pd.isna(row["ivp_252"]):
        return False
    common = (
        not row["stress_active"]
        and not row["second_leg_active"]
        and row["above_ma50"] == 1
        and row["ddath"] > -0.04
        and row["vix"] < 22
        and row["vix_5d_change"] <= 1.5
    )
    if not common:
        return False
    return (row["ivp_252"] < 55.0) or (row["vix"] < 15.0)

df["booster_active"] = df.apply(b4_f, axis=1)

# State-dependent SPX cap
spx_alloc = pd.Series(NORMAL_CAP, index=df.index)
spx_alloc[df["stress_active"]] = STRESS_SPX_CAP
spx_alloc[df["second_leg_active"]] = SECOND_LEG_CAP
booster_eligible = df["booster_active"] & ~df["stress_active"] & ~df["second_leg_active"]
spx_alloc[booster_eligible] = BOOSTER_CAP
df["spx_alloc"] = spx_alloc
df["cash_alloc"] = 1.0 - spx_alloc - HV_ALLOC - Q42_ALLOC

# Compute baseline daily PnL
spx_pnl = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX)
q42_pnl = df["q42a_pnl"] * (Q42_ALLOC / P13R_Q42)
cash_pnl = df["cash_alloc"] * NLV * CASH_YIELD / 252.0
spx_drag = FRICTION_ANN_SPX * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
q42_drag = FRICTION_ANN_Q42 * NLV * (Q42_ALLOC / P13R_Q42) / 252.0
df["baseline_pnl"] = (spx_pnl - spx_drag) + (q42_pnl - q42_drag) + cash_pnl

print(f"  Baseline days: {len(df)}")
print(f"  Booster active days: {int(booster_eligible.sum())} ({booster_eligible.sum()/len(df)*100:.1f}%)")

# ── Identify Type C first-in-cluster (Q075 P1 sample) ─────────────────
primary_days = pd.read_csv(OUT / "q075_p1_primary_sample_days.csv",
                            index_col=0, parse_dates=True)
type_c_first = primary_days[
    (primary_days["type"] == "C_high_vol_controlled") &
    (primary_days["is_first_in_cluster"])
].copy()
print(f"\n  Type C first-in-cluster: {len(type_c_first)} entry candidates")

# ── IC trade simulator (P3-style, exit booked on exit date) ───────────
def spread_components(spx_0, vix_0, ivp_0, width_pt, planned_dte, spread_kind):
    sigma_n = spx_0 * (vix_0 / 100.0) * (planned_dte / 252.0) ** 0.5
    credit_frac = 0.30 + min(0.20, (ivp_0 / 100.0) * 0.20)
    credit = width_pt * credit_frac * 100.0
    max_loss = width_pt * 100.0 - credit
    if spread_kind == "put":
        short_strike = spx_0 - 1.0 * sigma_n
        long_strike  = short_strike - width_pt
    else:
        short_strike = spx_0 + 1.0 * sigma_n
        long_strike  = short_strike + width_pt
    return {"sigma_n": sigma_n, "credit": credit, "max_loss": max_loss,
            "short_strike": short_strike, "long_strike": long_strike}

def mtm_at(spx_t, comp, day_offset, planned_dte, kind, iv_shock=0.0, skew_shock=0.0):
    short_k = comp["short_strike"]
    credit = comp["credit"]
    max_loss = comp["max_loss"]
    dte_remaining = max(0.5, planned_dte - day_offset)
    time_decay = (dte_remaining / planned_dte) ** 0.7
    base_credit_rem = credit * time_decay
    if kind == "put":
        if spx_t <= short_k:
            intrinsic = min((short_k - spx_t) * 100.0, max_loss + credit)
            mark_loss = intrinsic - base_credit_rem
        else:
            mark_loss = -base_credit_rem
        mark_loss += credit * iv_shock * 1.5 + credit * skew_shock
    else:
        if spx_t >= short_k:
            intrinsic = min((spx_t - short_k) * 100.0, max_loss + credit)
            mark_loss = intrinsic - base_credit_rem
        else:
            mark_loss = -base_credit_rem
        mark_loss += credit * iv_shock * 0.5
    return -mark_loss

def simulate_leg(entry_date, spx_0, vix_0, ivp_0, width_pt, kind, slip=2.0,
                  iv_shock=0.20, skew_shock=0.10):
    comp = spread_components(spx_0, vix_0, ivp_0, width_pt, IC_PLANNED_DTE, kind)
    short_k = comp["short_strike"]
    credit = comp["credit"]
    max_loss = comp["max_loss"]
    try:
        idx0 = mkt.index.get_loc(entry_date)
    except KeyError:
        return None
    pnl = None
    exit_d = None
    exit_dte = IC_PLANNED_DTE
    forced = False
    for d_off in range(1, IC_PLANNED_DTE + 1):
        cur_idx = min(idx0 + d_off, len(mkt) - 1)
        row = mkt.iloc[cur_idx]
        spx_t = row["spx_close"]
        stress_t = bool(row["stress_active"])
        second_leg_t = bool(row["second_leg_active"])
        if stress_t or second_leg_t:
            mtm_shock = mtm_at(spx_t, comp, d_off, IC_PLANNED_DTE, kind,
                                iv_shock=iv_shock, skew_shock=skew_shock if kind == "put" else 0.0)
            if mtm_shock < 0:
                mark_loss = -mtm_shock * slip
                exit_pnl = -mark_loss
            else:
                exit_pnl = mtm_shock
            pnl = exit_pnl - FRICTION_PER_TRADE
            pnl = max(pnl, -max_loss - FRICTION_PER_TRADE)
            exit_d = mkt.index[cur_idx]
            exit_dte = d_off
            forced = True
            break
        # Trade-level stop
        if kind == "put" and spx_t <= short_k:
            intrinsic = (short_k - spx_t) * 100.0
            if intrinsic > STOP_MULT * credit:
                pnl = -STOP_MULT * credit - FRICTION_PER_TRADE
                exit_d = mkt.index[cur_idx]
                exit_dte = d_off
                break
        elif kind == "call" and spx_t >= short_k:
            intrinsic = (spx_t - short_k) * 100.0
            if intrinsic > STOP_MULT * credit:
                pnl = -STOP_MULT * credit - FRICTION_PER_TRADE
                exit_d = mkt.index[cur_idx]
                exit_dte = d_off
                break
    if pnl is None:
        fwd_idx = min(idx0 + IC_PLANNED_DTE, len(mkt) - 1)
        spx_t = mkt.iloc[fwd_idx]["spx_close"]
        exit_pnl = mtm_at(spx_t, comp, IC_PLANNED_DTE, IC_PLANNED_DTE, kind, 0.0, 0.0)
        pnl = exit_pnl - FRICTION_PER_TRADE
        exit_d = mkt.index[fwd_idx]
    return {"pnl": pnl, "exit_date": exit_d, "exit_dte": exit_dte, "forced": forced,
            "max_loss": max_loss, "credit": credit, "short_strike": short_k}

def simulate_ic(entry_date, spx_0, vix_0, ivp_0, width_pt):
    put = simulate_leg(entry_date, spx_0, vix_0, ivp_0, width_pt, "put")
    call = simulate_leg(entry_date, spx_0, vix_0, ivp_0, width_pt, "call")
    if put is None or call is None:
        return None
    # 1/3 size combined IC
    ic_pnl = ((put["pnl"] + FRICTION_PER_TRADE) + (call["pnl"] + FRICTION_PER_TRADE)) / 3.0 - FRICTION_PER_TRADE
    ic_max_loss = max(put["max_loss"], call["max_loss"]) / 3.0
    exit_d = min(put["exit_date"], call["exit_date"])
    exit_dte = min(put["exit_dte"], call["exit_dte"])
    forced = put["forced"] or call["forced"]
    return {"entry_date": entry_date, "exit_date": exit_d, "exit_dte": exit_dte,
            "pnl": ic_pnl, "max_loss": ic_max_loss,
            "credit_combined": (put["credit"] + call["credit"]) / 3.0,
            "forced_by_stress": forced}

# ── Simulate IC overlay daily PnL series for each width ───────────────
print("\nSimulating IC overlay daily PnL series...")

def ic_overlay_daily(width_pt):
    """Returns daily PnL series for IC overlay. PnL booked on exit date."""
    overlay = pd.Series(0.0, index=df.index)
    bp_reserved = pd.Series(0.0, index=df.index)
    trades = []
    for d, row in type_c_first.iterrows():
        if d not in mkt.index:
            continue
        spx_0 = mkt.loc[d, "spx_close"]
        t = simulate_ic(d, spx_0, row["vix"], row["ivp_252"], width_pt)
        if t is None:
            continue
        # Book PnL on exit date
        if t["exit_date"] in overlay.index:
            overlay.loc[t["exit_date"]] += t["pnl"]
        # Reserve BP during hold
        entry_idx = df.index.get_loc(d)
        exit_idx = df.index.get_loc(t["exit_date"]) if t["exit_date"] in df.index else entry_idx + t["exit_dte"]
        hold_idx_range = df.index[entry_idx:min(exit_idx + 1, len(df))]
        bp_reserved.loc[hold_idx_range] += t["max_loss"]
        trades.append(t)
    return overlay, bp_reserved, pd.DataFrame(trades)

overlays = {}
trade_logs = {}
bp_series = {}
for w in IC_WIDTHS:
    ov, bp, tl = ic_overlay_daily(w)
    overlays[w] = ov
    trade_logs[w] = tl
    bp_series[w] = bp
    n = len(tl)
    cum = tl["pnl"].sum() if n else 0
    print(f"  IC w{w}: {n} trades, cum PnL ${cum:+,.0f}, avg hold {tl['exit_dte'].mean():.1f}d, forced {tl['forced_by_stress'].sum()}/{n}")

# ── Build combined daily PnL: baseline + overlay ───────────────────────
print("\nComputing combined portfolio metrics...")

def compute_metrics(daily_pnl_series, name):
    eq = NLV + daily_pnl_series.cumsum()
    years = len(daily_pnl_series) / 252
    ann_roe = (eq.iloc[-1] / NLV) ** (1.0/years) - 1.0
    running_max = eq.cummax()
    drawdown = (eq - running_max) / running_max
    max_dd = drawdown.min()
    daily_ret = daily_pnl_series / eq.shift(1).fillna(NLV)
    w20 = daily_ret.rolling(20).sum().min()
    w63 = daily_ret.rolling(63).sum().min()
    sharpe = daily_ret.mean() / daily_ret.std() * (252**0.5) if daily_ret.std() > 0 else 0
    return {
        "name": name,
        "n_days": len(daily_pnl_series),
        "ann_roe_pct": ann_roe * 100,
        "max_dd_pct": max_dd * 100,
        "worst_20d_pct": w20 * 100,
        "worst_63d_pct": w63 * 100,
        "sharpe": sharpe,
        "v1_pass": max_dd >= -0.28,
        "v2_pass": w20 >= -0.11,
        "v3_pass": w63 >= -0.17,
        "floor_8_pass": ann_roe >= 0.08,
        "final_equity_M": eq.iloc[-1] / 1e6,
    }

baseline_metrics = compute_metrics(df["baseline_pnl"], "baseline_104+105v2")
results = {"baseline": baseline_metrics}
print(f"\n{'Variant':<22} {'ROE %':>7} {'ΔROE':>7} {'MaxDD %':>8} {'W20d %':>8} {'W63d %':>8} {'Sharpe':>7} {'V1V2V3'}")
print("-" * 80)
v = baseline_metrics
print(f"{'baseline_104+105v2':<22} {v['ann_roe_pct']:>7.3f}  {'-':>6}  {v['max_dd_pct']:>8.2f} {v['worst_20d_pct']:>8.2f} {v['worst_63d_pct']:>8.2f} {v['sharpe']:>7.2f}  "
      f"{'✓' if v['v1_pass'] else '✗'}{'✓' if v['v2_pass'] else '✗'}{'✓' if v['v3_pass'] else '✗'}")

for w in IC_WIDTHS:
    combined_pnl = df["baseline_pnl"] + overlays[w]
    m = compute_metrics(combined_pnl, f"+IC_w{w}")
    m["delta_roe_pp"] = m["ann_roe_pct"] - baseline_metrics["ann_roe_pct"]
    m["delta_max_dd_pp"] = m["max_dd_pct"] - baseline_metrics["max_dd_pct"]
    m["delta_w20d_pp"] = m["worst_20d_pct"] - baseline_metrics["worst_20d_pct"]
    m["delta_w63d_pp"] = m["worst_63d_pct"] - baseline_metrics["worst_63d_pct"]
    m["delta_sharpe"] = m["sharpe"] - baseline_metrics["sharpe"]
    results[f"ic_w{w}"] = m
    print(f"{'+IC_w'+str(w):<22} {m['ann_roe_pct']:>7.3f} {m['delta_roe_pp']:>+6.3f} {m['max_dd_pct']:>8.2f} "
          f"{m['worst_20d_pct']:>8.2f} {m['worst_63d_pct']:>8.2f} {m['sharpe']:>7.2f}  "
          f"{'✓' if m['v1_pass'] else '✗'}{'✓' if m['v2_pass'] else '✗'}{'✓' if m['v3_pass'] else '✗'} "
          f"(Δw20d {m['delta_w20d_pp']:+.3f}pp Δw63d {m['delta_w63d_pp']:+.3f}pp)")

# Save metrics
metrics_df = pd.DataFrame([{**v, "candidate": k} for k, v in results.items()])
metrics_df.to_csv(OUT / "q075_p4_metrics.csv", index=False)

# ── Capital competition ───────────────────────────────────────────────
print("\n" + "=" * 70)
print("Capital competition (BP-day consumption)")
print("=" * 70)

baseline_bp_pct = (df["spx_alloc"] + Q42_ALLOC + HV_ALLOC).rename("baseline_bp_alloc_pct")
cap_rows = []
for w in IC_WIDTHS:
    ic_bp_pct = bp_series[w] / NLV * 100   # IC max_loss as % NLV
    combined_bp_pct = baseline_bp_pct * 100 + ic_bp_pct  # baseline already fraction; convert
    # When baseline_bp + ic > 100%, cash residual is negative (margin loan)
    # Critical: does IC ever push BP > 100% beyond what baseline already does?
    baseline_overdraft = (baseline_bp_pct * 100 > 100).sum()
    combined_overdraft = (combined_bp_pct > 100).sum()
    new_overdraft_days = combined_overdraft - baseline_overdraft
    max_combined = combined_bp_pct.max()
    avg_ic_bp_days_active = (ic_bp_pct > 0).sum()
    avg_ic_bp_size = ic_bp_pct[ic_bp_pct > 0].mean() if (ic_bp_pct > 0).any() else 0
    print(f"  IC w{w}: avg IC BP size when active {avg_ic_bp_size:.3f}% NLV, active {avg_ic_bp_days_active} days, "
          f"max combined BP {max_combined:.1f}% NLV, new overdraft days {new_overdraft_days}")
    cap_rows.append({
        "candidate": f"IC_w{w}",
        "avg_ic_bp_pct_when_active": avg_ic_bp_size,
        "ic_active_days": int(avg_ic_bp_days_active),
        "max_combined_bp_pct": max_combined,
        "baseline_overdraft_days": int(baseline_overdraft),
        "combined_overdraft_days": int(combined_overdraft),
        "new_overdraft_days_from_ic": int(new_overdraft_days),
    })
pd.DataFrame(cap_rows).to_csv(OUT / "q075_p4_capital_competition.csv", index=False)

# ── Correlation with existing sleeves ─────────────────────────────────
print("\n" + "=" * 70)
print("Correlation with existing sleeves")
print("=" * 70)
corr_rows = []
for w in IC_WIDTHS:
    ov_active = overlays[w][overlays[w] != 0]
    if len(ov_active) > 10:
        # Align dates
        dates = ov_active.index.intersection(df.index)
        spx_active = df.loc[dates, "spx_pnl"]
        q42_active = df.loc[dates, "q42a_pnl"]
        ic_active = ov_active.loc[dates]
        if len(dates) > 5:
            corr_spx = ic_active.corr(spx_active)
            corr_q42 = ic_active.corr(q42_active)
            corr_baseline = ic_active.corr(df.loc[dates, "baseline_pnl"])
            print(f"  IC w{w} on exit days (n={len(dates)}): corr(IC, SPX)={corr_spx:+.3f}, corr(IC, Q42)={corr_q42:+.3f}, corr(IC, baseline)={corr_baseline:+.3f}")
            corr_rows.append({
                "candidate": f"IC_w{w}",
                "n_exit_days": len(dates),
                "corr_with_spx_pnl": corr_spx,
                "corr_with_q42_pnl": corr_q42,
                "corr_with_baseline_pnl": corr_baseline,
            })
pd.DataFrame(corr_rows).to_csv(OUT / "q075_p4_correlation.csv", index=False)

# ── Crisis windows ────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Crisis window behavior")
print("=" * 70)
crisis_windows = {
    "DotCom_2000_03": ("2000-03-01", "2000-04-30"),
    "PreGFC_2007_07": ("2007-07-01", "2007-09-30"),
    "Vol_2018_02":    ("2018-01-15", "2018-03-15"),
    "COVID_2020_02":  ("2020-02-15", "2020-03-31"),
    "Bear_2022_01":   ("2022-01-01", "2022-02-28"),
}
crisis_rows = []
for cname, (s, e) in crisis_windows.items():
    s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
    in_window = df[(df.index >= s_ts) & (df.index <= e_ts)]
    baseline_cum = in_window["baseline_pnl"].sum()
    print(f"\n[{cname}] baseline window PnL ${baseline_cum:+,.0f}")
    for w in IC_WIDTHS:
        ic_cum = overlays[w].loc[in_window.index].sum() if len(in_window) else 0
        n_ic_trades = (trade_logs[w]["entry_date"] >= s_ts).sum() if "entry_date" in trade_logs[w].columns else 0
        n_ic_trades_in_window = trade_logs[w][(trade_logs[w]["entry_date"] >= s_ts) & (trade_logs[w]["entry_date"] <= e_ts)].shape[0] if len(trade_logs[w]) else 0
        combined_cum = baseline_cum + ic_cum
        delta = ic_cum
        print(f"   IC w{w}: window IC cum ${ic_cum:+,.0f} (n_trades_in_window={n_ic_trades_in_window}), combined ${combined_cum:+,.0f}, Δ vs baseline ${delta:+,.0f}")
        crisis_rows.append({
            "crisis": cname,
            "candidate": f"IC_w{w}",
            "n_ic_trades_in_window": n_ic_trades_in_window,
            "baseline_cum_pnl": baseline_cum,
            "ic_cum_pnl": ic_cum,
            "combined_cum_pnl": combined_cum,
            "delta_pnl": delta,
        })
pd.DataFrame(crisis_rows).to_csv(OUT / "q075_p4_crisis.csv", index=False)

# ── Stress-adjacent table (mandatory per 2nd Quant) ───────────────────
print("\n" + "=" * 70)
print("IC overlay during stress-adjacent periods (10d before any stress trigger)")
print("=" * 70)

# Identify "stress-adjacent" days = 10d-window prior to first day of stress activation
mkt["stress_prev"] = mkt["stress_active"].shift(1).fillna(False)
mkt["stress_trigger"] = mkt["stress_active"] & ~mkt["stress_prev"]
trigger_dates = mkt.index[mkt["stress_trigger"]]
stress_adjacent_dates = set()
for trig in trigger_dates:
    idx0 = mkt.index.get_loc(trig)
    for d_off in range(1, 11):
        i = idx0 - d_off
        if i >= 0:
            stress_adjacent_dates.add(mkt.index[i])

sa_rows = []
for w in IC_WIDTHS:
    tl = trade_logs[w]
    if len(tl) == 0:
        continue
    tl["entry_date"] = pd.to_datetime(tl["entry_date"])
    in_sa = tl["entry_date"].isin(stress_adjacent_dates)
    sub = tl[in_sa]
    n_entries_sa = len(sub)
    n_forced_sa = sub["forced_by_stress"].sum()
    cum_sa = sub["pnl"].sum()
    worst_trade_sa = sub["pnl"].min() if len(sub) else 0
    # 20d window contribution
    if len(sub):
        worst_20d_contrib = sub["pnl"].rolling(window=20).sum().min()
    else:
        worst_20d_contrib = 0
    print(f"  IC w{w} in stress-adjacent (10d pre-trigger): n_entries={n_entries_sa}, "
          f"forced_exits={n_forced_sa}, cum=${cum_sa:+,.0f}, worst_trade=${worst_trade_sa:+,.0f}, "
          f"worst_20d_contribution=${worst_20d_contrib:+,.0f}")
    sa_rows.append({
        "candidate": f"IC_w{w}",
        "total_entries": len(tl),
        "stress_adjacent_entries": n_entries_sa,
        "stress_adjacent_entries_pct": n_entries_sa / len(tl) * 100,
        "forced_exits_in_sa": int(n_forced_sa),
        "sa_cum_pnl": cum_sa,
        "sa_worst_trade": worst_trade_sa,
        "sa_worst_20d_contribution": worst_20d_contrib,
    })
pd.DataFrame(sa_rows).to_csv(OUT / "q075_p4_stress_adjacent.csv", index=False)

# ── Bootstrap ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Bootstrap (block=250, 20 seeds) — ΔROE vs baseline")
print("=" * 70)

def block_bootstrap_delta(combined_pnl, baseline_pnl, n_seeds=20, block=250):
    n = len(combined_pnl)
    n_blocks = n // block
    deltas = []
    base_arr = baseline_pnl.values
    comb_arr = combined_pnl.values
    for s in range(n_seeds):
        rng = np.random.default_rng(42 + s)
        starts = rng.integers(0, n - block, size=n_blocks)
        bp_seq = np.concatenate([base_arr[i:i+block] for i in starts])
        cp_seq = np.concatenate([comb_arr[i:i+block] for i in starts])
        years = len(bp_seq) / 252
        eq_b = NLV + bp_seq.cumsum()
        eq_c = NLV + cp_seq.cumsum()
        roe_b = (eq_b[-1] / NLV) ** (1.0/years) - 1
        roe_c = (eq_c[-1] / NLV) ** (1.0/years) - 1
        deltas.append((roe_c - roe_b) * 100)
    return np.array(deltas)

boot_rows = []
for w in IC_WIDTHS:
    combined = df["baseline_pnl"] + overlays[w]
    deltas = block_bootstrap_delta(combined, df["baseline_pnl"])
    print(f"  IC w{w}: ΔROE mean {deltas.mean():+.3f}pp σ {deltas.std():.3f}pp, "
          f"5-95% [{np.percentile(deltas, 5):+.3f}, {np.percentile(deltas, 95):+.3f}], "
          f"P(ΔROE > 0) = {(deltas > 0).mean()*100:.1f}%")
    boot_rows.append({
        "candidate": f"IC_w{w}",
        "delta_roe_mean_pp": float(deltas.mean()),
        "delta_roe_std_pp": float(deltas.std()),
        "p5_pp": float(np.percentile(deltas, 5)),
        "p95_pp": float(np.percentile(deltas, 95)),
        "p_droe_positive_pct": float((deltas > 0).mean() * 100),
        "n_seeds": 20, "block": 250,
    })
pd.DataFrame(boot_rows).to_csv(OUT / "q075_p4_bootstrap.csv", index=False)

# ── Walk-forward H1 / H2 ──────────────────────────────────────────────
print("\n" + "=" * 70)
print("Walk-forward H1 (2000-2012) / H2 (2013-2026)")
print("=" * 70)
splits = {
    "H1_2000_2012": ("2000-01-01", "2012-12-31"),
    "H2_2013_2026": ("2013-01-01", "2026-12-31"),
}
wf_rows = []
for period_name, (s, e) in splits.items():
    s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
    sub_idx = (df.index >= s_ts) & (df.index <= e_ts)
    base_period = df.loc[sub_idx, "baseline_pnl"]
    base_metrics = compute_metrics(base_period, f"{period_name}_baseline")
    print(f"\n[{period_name}] baseline ROE {base_metrics['ann_roe_pct']:.3f}%, W20d {base_metrics['worst_20d_pct']:.2f}%")
    wf_rows.append({"period": period_name, "candidate": "baseline",
                    "ann_roe_pct": base_metrics["ann_roe_pct"],
                    "delta_roe_pp": 0.0,
                    "max_dd_pct": base_metrics["max_dd_pct"],
                    "worst_20d_pct": base_metrics["worst_20d_pct"],
                    "worst_63d_pct": base_metrics["worst_63d_pct"],
                    "v2_pass": base_metrics["v2_pass"]})
    for w in IC_WIDTHS:
        comb_period = base_period + overlays[w].loc[sub_idx]
        m = compute_metrics(comb_period, f"{period_name}_+IC_w{w}")
        droe = m["ann_roe_pct"] - base_metrics["ann_roe_pct"]
        print(f"  + IC w{w}: ROE {m['ann_roe_pct']:.3f}% (Δ{droe:+.3f}pp), W20d {m['worst_20d_pct']:.2f}%, W63d {m['worst_63d_pct']:.2f}%")
        wf_rows.append({"period": period_name, "candidate": f"IC_w{w}",
                        "ann_roe_pct": m["ann_roe_pct"],
                        "delta_roe_pp": droe,
                        "max_dd_pct": m["max_dd_pct"],
                        "worst_20d_pct": m["worst_20d_pct"],
                        "worst_63d_pct": m["worst_63d_pct"],
                        "v2_pass": m["v2_pass"]})
pd.DataFrame(wf_rows).to_csv(OUT / "q075_p4_walkforward.csv", index=False)

# ── Final verdict ─────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FINAL VERDICT per Q075 P0 §8 promotion bar")
print("=" * 70)

for w in IC_WIDTHS:
    m = results[f"ic_w{w}"]
    droe = m["delta_roe_pp"]
    dw20 = m["delta_w20d_pp"]
    dw63 = m["delta_w63d_pp"]
    v1v2v3 = m["v1_pass"] and m["v2_pass"] and m["v3_pass"]
    risk_pass = dw20 <= 0.25 and dw63 <= 0.25 and v1v2v3
    if droe >= 0.20 and risk_pass:
        verdict = "STRONG PROMOTE"
    elif droe >= 0.05 and risk_pass:
        verdict = "SOFT PROMOTE"
    elif droe >= 0.05 and not risk_pass:
        verdict = "REJECT (risk threshold)"
    elif droe < 0.05:
        verdict = "DOCUMENT (sub-threshold)"
    else:
        verdict = "REJECT"
    print(f"\n  IC w{w}: ΔROE {droe:+.3f}pp, ΔW20d {dw20:+.3f}pp, ΔW63d {dw63:+.3f}pp, V1V2V3 {'✓' if v1v2v3 else '✗'} → {verdict}")

print("\n" + "=" * 70)
print("Q075 P4 done. CSVs in research/q075/")
print("=" * 70)
