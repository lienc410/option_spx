"""Q075 P3 — Forensic Probes (Goal: BREAK IC, not confirm it).

Per 2nd Quant G3 PASS (2026-05-19) + PM-locked P3 implementation choices:

  IC Primary (C3 w15/25/35):
    Probe A — Stress-fire + SPX-down subset (leg decomposition)
    Probe B — Intraperiod MAE (CORE check — worst MTM during hold)
    Probe C — Downside shock injection (3 canonical scenarios)
    Probe D — Gap-down at entry+1 (base); entry+3 if entry+1 clean (diagnostic)

  BCS Secondary (C4):
    4 melt-up analogs:
      2019-Q1 broad rebound
      2023-Q4 rally
      2024-H1 rally
      Mechanical: argmax(SPX_10d_%return - VIX_10d_%return) across 26y
    Pass bar:
      cum loss >= -$10k
      single worst >= -0.5% NLV
      hit rate >= 60% (diagnostic, not hard veto)

  C2 sBPS Diagnostic only:
    one-pass: cum, worst, forced-exit, top-5 losses, gap-down sensitivity
    NO promotion inside Q075; reopening requires separate PM approval

Locked downside shock scenarios:
  Mild:    SPX -2% / 5d,  IV +20%, skew +10%
  Base:    SPX -3% / 5d,  IV +20%, skew +10%
  Severe:  SPX -5% / 10d, IV +40%, skew +20%

Outputs (research/q075/):
  q075_p3_ic_intraperiod_mae.csv      — Probe B (core)
  q075_p3_ic_downside_shocks.csv      — Probe C
  q075_p3_ic_gap_down.csv             — Probe D
  q075_p3_ic_stress_subset.csv        — Probe A with leg decomposition
  q075_p3_bcs_analogs.csv             — 4 melt-up analogs
  q075_p3_bcs_mechanical_metadata.csv — selected window + score
  q075_p3_c2_diagnostic.csv           — C2 one-pass summary
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

# Locked params
FRICTION_PER_TRADE = 50.0
STOP_MULT = 2.0
IC_BCS_PLANNED_DTE = 14
SBPS_PLANNED_DTE = 7
IC_WIDTHS = [15, 25, 35]
BCS_WIDTH = 25
STRESS_SLIPPAGE_BASE = 2.0
WORST_TRADE_LIMIT_NLV = 0.01

# Downside shock scenarios per PM lock
DOWNSIDE_SHOCKS = [
    {"name": "Mild",   "spx_pct": -0.02, "days": 5,  "iv_pct": 0.20, "skew_pct": 0.10},
    {"name": "Base",   "spx_pct": -0.03, "days": 5,  "iv_pct": 0.20, "skew_pct": 0.10},
    {"name": "Severe", "spx_pct": -0.05, "days": 10, "iv_pct": 0.40, "skew_pct": 0.20},
]

print("Q075 P3 — Forensic Probes (Goal: BREAK IC)", flush=True)
print("=" * 70)

# ── Load data ──────────────────────────────────────────────────────────
primary_days = pd.read_csv(OUT / "q075_p1_primary_sample_days.csv",
                            index_col=0, parse_dates=True)
type_c_first = primary_days[
    (primary_days["type"] == "C_high_vol_controlled") &
    (primary_days["is_first_in_cluster"])
].copy()
print(f"\nType C first-in-cluster trades: {len(type_c_first)}")

from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
combined = pd.read_csv(REPO / "research" / "q073" / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")
mkt = mkt[(mkt.index >= combined.index.min()) & (mkt.index <= combined.index.max())]
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)

# ── Spread math (refactored from P2) ───────────────────────────────────
def spread_components(spx_0, vix_0, ivp_0, width_pt, planned_dte, spread_kind):
    sigma_n = spx_0 * (vix_0 / 100.0) * (planned_dte / 252.0) ** 0.5
    credit_frac = 0.30 + min(0.20, (ivp_0 / 100.0) * 0.20)
    credit = width_pt * credit_frac * 100.0
    max_loss = width_pt * 100.0 - credit
    if spread_kind == "put":
        short_strike = spx_0 - 1.0 * sigma_n
        long_strike  = short_strike - width_pt
    else:  # call
        short_strike = spx_0 + 1.0 * sigma_n
        long_strike  = short_strike + width_pt
    return {"sigma_n": sigma_n, "credit": credit, "max_loss": max_loss,
            "short_strike": short_strike, "long_strike": long_strike}

def mtm_at(spx_t, components, day_offset, planned_dte, spread_kind,
            iv_shock=0.0, skew_shock=0.0):
    """Mark-to-market PnL relative to entry credit.
    Positive = unrealized profit; negative = unrealized loss.
    """
    short_strike = components["short_strike"]
    long_strike = components["long_strike"]
    credit = components["credit"]
    max_loss = components["max_loss"]
    dte_remaining = max(0.5, planned_dte - day_offset)
    time_decay = (dte_remaining / planned_dte) ** 0.7
    base_credit_remaining = credit * time_decay

    if spread_kind == "put":
        if spx_t <= short_strike:
            intrinsic = min((short_strike - spx_t) * 100.0, max_loss + credit)
            mark_loss = intrinsic - base_credit_remaining
        else:
            mark_loss = -base_credit_remaining
        # Stress / shock additions
        iv_extra_loss = credit * iv_shock * 1.5     # +20% IV → +30% credit mark
        skew_extra_loss = credit * skew_shock
        mark_loss += iv_extra_loss + skew_extra_loss
    else:  # call
        if spx_t >= short_strike:
            intrinsic = min((spx_t - short_strike) * 100.0, max_loss + credit)
            mark_loss = intrinsic - base_credit_remaining
        else:
            mark_loss = -base_credit_remaining
        iv_extra_loss = credit * iv_shock * 0.5     # +20% IV → +10% credit mark (call usually OTM in downside)
        mark_loss += iv_extra_loss

    pnl_mtm = -(mark_loss)
    pnl_mtm = max(pnl_mtm, -max_loss)
    return pnl_mtm

def simulate_trade_full(entry_date, spx_0, vix_0, ivp_0, width_pt, planned_dte,
                         spread_kind, slippage_mult=STRESS_SLIPPAGE_BASE,
                         iv_shock=0.20, skew_shock=0.10,
                         override_path=None, gap_day=None, gap_pct=None):
    """Full trade sim with intraperiod tracking.
    Returns: dict with PnL, MAE, leg PnL components, exit reason.
    """
    comp = spread_components(spx_0, vix_0, ivp_0, width_pt, planned_dte, spread_kind)
    short_strike = comp["short_strike"]
    long_strike = comp["long_strike"]
    credit = comp["credit"]
    max_loss = comp["max_loss"]

    try:
        idx0 = mkt.index.get_loc(entry_date)
    except KeyError:
        return None

    worst_mtm_pnl = credit  # start at full credit (best case)
    min_distance_to_short = float("inf")
    days_within_half_sigma = 0
    sigma_n = comp["sigma_n"]

    pnl = None
    exit_dte = planned_dte
    exit_reason = None
    exit_date = None
    forced_by_stress = False
    intra_path = []

    for d_off in range(1, planned_dte + 1):
        if override_path is not None and d_off <= len(override_path):
            spx_t = override_path[d_off - 1]
            stress_t = False
            second_leg_t = False
        else:
            cur_idx = min(idx0 + d_off, len(mkt) - 1)
            row = mkt.iloc[cur_idx]
            spx_t = row["spx_close"]
            # Gap-down injection at specified day
            if gap_day is not None and d_off == gap_day and gap_pct is not None:
                spx_t = spx_0 * (1 + gap_pct)
            stress_t = bool(row["stress_active"])
            second_leg_t = bool(row["second_leg_active"])

        # Track intraperiod MAE (without stress shock — pure underlying mark)
        mtm = mtm_at(spx_t, comp, d_off, planned_dte, spread_kind,
                     iv_shock=0.0, skew_shock=0.0)
        worst_mtm_pnl = min(worst_mtm_pnl, mtm)
        # Distance to short strike (signed: positive = SPX above for put, below for call → safer)
        if spread_kind == "put":
            distance = (spx_t - short_strike) / sigma_n
        else:
            distance = (short_strike - spx_t) / sigma_n
        min_distance_to_short = min(min_distance_to_short, distance)
        if distance < 0.5:
            days_within_half_sigma += 1
        intra_path.append({"d_off": d_off, "spx_t": spx_t, "mtm_pnl": mtm,
                           "distance_to_short_sigma": distance,
                           "stress_active": stress_t})

        # Forced exit on stress
        if stress_t or second_leg_t:
            # Apply stress shock to exit mark
            exit_mtm_with_shock = mtm_at(spx_t, comp, d_off, planned_dte, spread_kind,
                                          iv_shock=iv_shock, skew_shock=skew_shock)
            mark_loss = -exit_mtm_with_shock if exit_mtm_with_shock < 0 else 0
            if mark_loss > 0:
                mark_loss *= slippage_mult
                exit_pnl = -mark_loss
            else:
                exit_pnl = exit_mtm_with_shock
            pnl = exit_pnl - FRICTION_PER_TRADE
            pnl = max(pnl, -max_loss - FRICTION_PER_TRADE)
            exit_reason = "stress_force"
            exit_dte = d_off
            exit_date = mkt.index[min(idx0 + d_off, len(mkt) - 1)]
            forced_by_stress = True
            break

        # Trade-level stop
        if spread_kind == "put" and spx_t <= short_strike:
            intrinsic = (short_strike - spx_t) * 100.0
            if intrinsic > STOP_MULT * credit:
                pnl = -STOP_MULT * credit - FRICTION_PER_TRADE
                exit_reason = "stop"
                exit_dte = d_off
                exit_date = mkt.index[min(idx0 + d_off, len(mkt) - 1)]
                break
        elif spread_kind == "call" and spx_t >= short_strike:
            intrinsic = (spx_t - short_strike) * 100.0
            if intrinsic > STOP_MULT * credit:
                pnl = -STOP_MULT * credit - FRICTION_PER_TRADE
                exit_reason = "stop"
                exit_dte = d_off
                exit_date = mkt.index[min(idx0 + d_off, len(mkt) - 1)]
                break

    if pnl is None:
        # Held to expiry
        if override_path is not None and planned_dte <= len(override_path):
            spx_t = override_path[planned_dte - 1]
        else:
            fwd_idx = min(idx0 + planned_dte, len(mkt) - 1)
            spx_t = mkt.iloc[fwd_idx]["spx_close"]
        exit_pnl = mtm_at(spx_t, comp, planned_dte, planned_dte, spread_kind,
                          iv_shock=0.0, skew_shock=0.0)
        pnl = exit_pnl - FRICTION_PER_TRADE
        exit_reason = "expiry"
        exit_date = mkt.index[min(idx0 + planned_dte, len(mkt) - 1)] if override_path is None else entry_date + pd.Timedelta(days=planned_dte)

    return {
        "entry_date": entry_date, "exit_date": exit_date, "exit_dte": exit_dte,
        "exit_reason": exit_reason, "pnl": pnl,
        "worst_intra_mtm": worst_mtm_pnl, "min_dist_to_short_sigma": min_distance_to_short,
        "days_within_0.5sigma": days_within_half_sigma,
        "credit": credit, "max_loss": max_loss,
        "short_strike": short_strike, "long_strike": long_strike,
        "spx_0": spx_0, "vix_0": vix_0, "ivp_0": ivp_0, "sigma_n": sigma_n,
        "forced_by_stress": forced_by_stress, "spread_kind": spread_kind, "width_pt": width_pt,
    }

def simulate_ic_full(entry_date, spx_0, vix_0, ivp_0, width_pt,
                      slippage_mult=STRESS_SLIPPAGE_BASE,
                      iv_shock=0.20, skew_shock=0.10,
                      override_path=None, gap_day=None, gap_pct=None):
    put_t = simulate_trade_full(entry_date, spx_0, vix_0, ivp_0, width_pt, IC_BCS_PLANNED_DTE,
                                  "put", slippage_mult, iv_shock, skew_shock,
                                  override_path, gap_day, gap_pct)
    call_t = simulate_trade_full(entry_date, spx_0, vix_0, ivp_0, width_pt, IC_BCS_PLANNED_DTE,
                                   "call", slippage_mult, iv_shock=iv_shock, skew_shock=0.0,
                                   override_path=override_path, gap_day=gap_day, gap_pct=gap_pct)
    if put_t is None or call_t is None:
        return None
    put_pnl_clean = put_t["pnl"] + FRICTION_PER_TRADE
    call_pnl_clean = call_t["pnl"] + FRICTION_PER_TRADE
    ic_pnl = (put_pnl_clean + call_pnl_clean) / 3.0 - FRICTION_PER_TRADE
    ic_worst_mtm = (put_t["worst_intra_mtm"] + call_t["worst_intra_mtm"]) / 3.0
    ic_max_loss = max(put_t["max_loss"], call_t["max_loss"]) / 3.0
    return {
        "entry_date": entry_date,
        "exit_date": min(put_t["exit_date"], call_t["exit_date"]),
        "exit_dte": min(put_t["exit_dte"], call_t["exit_dte"]),
        "pnl": ic_pnl,
        "put_pnl": put_pnl_clean / 3.0,
        "call_pnl": call_pnl_clean / 3.0,
        "worst_intra_mtm": ic_worst_mtm,
        "min_dist_put": put_t["min_dist_to_short_sigma"],
        "min_dist_call": call_t["min_dist_to_short_sigma"],
        "days_within_0.5sigma_put": put_t["days_within_0.5sigma"],
        "days_within_0.5sigma_call": call_t["days_within_0.5sigma"],
        "max_loss_ic": ic_max_loss, "max_loss_per_leg": put_t["max_loss"],
        "credit_total": (put_t["credit"] + call_t["credit"]) / 3.0,
        "spx_0": spx_0, "vix_0": vix_0, "ivp_0": ivp_0,
        "sigma_n": put_t["sigma_n"], "width_pt": width_pt,
        "forced_by_stress": put_t["forced_by_stress"] or call_t["forced_by_stress"],
        "put_exit_reason": put_t["exit_reason"], "call_exit_reason": call_t["exit_reason"],
    }

# ── Probe B: Intraperiod MAE (CORE) ────────────────────────────────────
print("\n" + "=" * 70)
print("Probe B — Intraperiod MAE (IC across 3 widths)")
print("=" * 70)

mae_rows = []
for width in IC_WIDTHS:
    rows = []
    for d, row in type_c_first.iterrows():
        if d not in mkt.index:
            continue
        spx_0 = mkt.loc[d, "spx_close"]
        t = simulate_ic_full(d, spx_0, row["vix"], row["ivp_252"], width)
        if t is None:
            continue
        t["width"] = width
        rows.append(t)
    df = pd.DataFrame(rows)
    n = len(df)
    worst_pnl = df["pnl"].min()
    worst_mae = df["worst_intra_mtm"].min()
    avg_mae = df["worst_intra_mtm"].mean()
    mae_pct_max_loss = (worst_mae / df["max_loss_ic"].iloc[0]) * 100
    mae_pct_nlv = worst_mae / NLV * 100
    min_dist_put = df["min_dist_put"].min()
    min_dist_call = df["min_dist_call"].min()
    days_close_put = df["days_within_0.5sigma_put"].mean()
    print(f"  IC w{width}: n={n}, exit_PnL worst=${worst_pnl:+,.0f}, "
          f"MAE worst=${worst_mae:+,.0f} ({mae_pct_max_loss:.1f}% max_loss, {mae_pct_nlv:+.3f}% NLV), "
          f"min dist put/call={min_dist_put:.2f}σ/{min_dist_call:.2f}σ, "
          f"avg days within 0.5σ put={days_close_put:.1f}")
    for r in rows:
        r["width"] = width
        mae_rows.append(r)
pd.DataFrame(mae_rows).to_csv(OUT / "q075_p3_ic_intraperiod_mae.csv", index=False)

# ── Probe A: Stress-fire + SPX-down subset with leg decomposition ──────
print("\n" + "=" * 70)
print("Probe A — Stress-fire + SPX-down subset (leg decomposition)")
print("=" * 70)

mae_df = pd.DataFrame(mae_rows)
forced_subset = mae_df[mae_df["forced_by_stress"]].copy()
forced_subset["spx_exit"] = forced_subset.apply(
    lambda r: mkt.loc[r["exit_date"], "spx_close"] if r["exit_date"] in mkt.index else np.nan,
    axis=1)
forced_subset["spx_move_pct"] = (forced_subset["spx_exit"] / forced_subset["spx_0"] - 1.0) * 100
spx_down_subset = forced_subset[forced_subset["spx_move_pct"] < 0].copy()
spx_down_subset["distance_to_short_put_at_exit_pct"] = (
    (spx_down_subset["spx_exit"] - spx_down_subset.apply(
        lambda r: r["spx_0"] - r["sigma_n"], axis=1)
    ) / spx_down_subset["spx_0"] * 100
)
spx_down_subset["call_offset_ratio"] = spx_down_subset.apply(
    lambda r: r["call_pnl"] / max(0.01, -r["put_pnl"]) if r["put_pnl"] < 0 else np.nan,
    axis=1)

print(f"\nForced-by-stress IC trades (all widths): {len(forced_subset)}")
print(f"  Subset with SPX down at exit: {len(spx_down_subset)}")

for w in IC_WIDTHS:
    sub = spx_down_subset[spx_down_subset["width"] == w]
    if len(sub) == 0:
        continue
    avg_spx_down = sub["spx_move_pct"].mean()
    avg_put_pnl = sub["put_pnl"].mean()
    avg_call_pnl = sub["call_pnl"].mean()
    avg_ic_pnl = sub["pnl"].mean()
    n_put_losses = (sub["put_pnl"] < 0).sum()
    avg_call_offset = sub["call_offset_ratio"].mean()
    print(f"  IC w{w}: n={len(sub)} stress+SPXdown, avg SPX move {avg_spx_down:.2f}%, "
          f"avg put PnL ${avg_put_pnl:+,.0f}, avg call PnL ${avg_call_pnl:+,.0f}, "
          f"avg IC PnL ${avg_ic_pnl:+,.0f}, put-losing trades {n_put_losses}/{len(sub)}, "
          f"avg call_offset_ratio {avg_call_offset:.2f}")

spx_down_subset.to_csv(OUT / "q075_p3_ic_stress_subset.csv", index=False)

# ── Probe C: Downside shock injection ──────────────────────────────────
print("\n" + "=" * 70)
print("Probe C — Downside shock injection (3 canonical scenarios)")
print("=" * 70)

shock_rows = []
for shock in DOWNSIDE_SHOCKS:
    for width in IC_WIDTHS:
        trades = []
        for d, row in type_c_first.iterrows():
            if d not in mkt.index:
                continue
            spx_0 = mkt.loc[d, "spx_close"]
            # Build override forward path: linear decline to shock spx_pct over shock days, then plateau
            path = []
            for d_off in range(1, IC_BCS_PLANNED_DTE + 1):
                if d_off <= shock["days"]:
                    spx_t = spx_0 * (1 + shock["spx_pct"] * d_off / shock["days"])
                else:
                    spx_t = spx_0 * (1 + shock["spx_pct"])
                path.append(spx_t)
            t = simulate_ic_full(d, spx_0, row["vix"], row["ivp_252"], width,
                                  iv_shock=shock["iv_pct"], skew_shock=shock["skew_pct"],
                                  override_path=path)
            if t is None:
                continue
            t["width"] = width
            t["shock"] = shock["name"]
            trades.append(t)
        df = pd.DataFrame(trades)
        if len(df) == 0:
            continue
        cum = df["pnl"].sum()
        worst = df["pnl"].min()
        hit = (df["pnl"] > 0).mean() * 100
        avg = df["pnl"].mean()
        worst_pct_nlv = worst / NLV * 100
        print(f"  {shock['name']:6} IC w{width}: n={len(df)} cum=${cum:>+10,.0f} "
              f"avg=${avg:+,.0f} worst=${worst:+,.0f} ({worst_pct_nlv:+.3f}% NLV) hit={hit:.1f}%")
        for t in trades:
            shock_rows.append(t)
pd.DataFrame(shock_rows).to_csv(OUT / "q075_p3_ic_downside_shocks.csv", index=False)

# ── Probe D: Gap-down at entry+1 ───────────────────────────────────────
print("\n" + "=" * 70)
print("Probe D — Gap-down at entry+1 (-2% and -3%)")
print("=" * 70)

gap_rows = []
gap_scenarios = [("gap_2pct_entry+1", 1, -0.02), ("gap_3pct_entry+1", 1, -0.03)]
for sname, gd, gp in gap_scenarios:
    for width in IC_WIDTHS:
        trades = []
        for d, row in type_c_first.iterrows():
            if d not in mkt.index:
                continue
            spx_0 = mkt.loc[d, "spx_close"]
            t = simulate_ic_full(d, spx_0, row["vix"], row["ivp_252"], width,
                                  gap_day=gd, gap_pct=gp)
            if t is None:
                continue
            t["width"] = width
            t["scenario"] = sname
            trades.append(t)
        df = pd.DataFrame(trades)
        if len(df) == 0:
            continue
        cum = df["pnl"].sum()
        worst = df["pnl"].min()
        hit = (df["pnl"] > 0).mean() * 100
        worst_pct_nlv = worst / NLV * 100
        print(f"  {sname} IC w{width}: n={len(df)} cum=${cum:>+10,.0f} "
              f"worst=${worst:+,.0f} ({worst_pct_nlv:+.3f}% NLV) hit={hit:.1f}%")
        for t in trades:
            gap_rows.append(t)
pd.DataFrame(gap_rows).to_csv(OUT / "q075_p3_ic_gap_down.csv", index=False)

# Conditional entry+3 if entry+1 clean
gap_df = pd.DataFrame(gap_rows)
entry1_3pct_w25 = gap_df[(gap_df["scenario"] == "gap_3pct_entry+1") & (gap_df["width"] == 25)]
worst_entry1 = entry1_3pct_w25["pnl"].min() if len(entry1_3pct_w25) else 0
if worst_entry1 / NLV * 100 > -0.5:  # if entry+1 -3% gap stayed within -0.5% NLV
    print("\n  entry+1 -3% gap clean (worst within -0.5% NLV) — running entry+3 -3% diagnostic")
    e3_rows = []
    for width in IC_WIDTHS:
        for d, row in type_c_first.iterrows():
            if d not in mkt.index:
                continue
            spx_0 = mkt.loc[d, "spx_close"]
            t = simulate_ic_full(d, spx_0, row["vix"], row["ivp_252"], width,
                                  gap_day=3, gap_pct=-0.03)
            if t is None:
                continue
            t["width"] = width
            t["scenario"] = "gap_3pct_entry+3"
            e3_rows.append(t)
    e3_df = pd.DataFrame(e3_rows)
    for w in IC_WIDTHS:
        sub = e3_df[e3_df["width"] == w]
        if len(sub) == 0:
            continue
        cum = sub["pnl"].sum()
        worst = sub["pnl"].min()
        hit = (sub["pnl"] > 0).mean() * 100
        print(f"    entry+3 -3% IC w{w}: n={len(sub)} cum=${cum:+,.0f} worst=${worst:+,.0f} hit={hit:.1f}%")
    # Append to gap_rows for export
    pd.concat([gap_df, e3_df]).to_csv(OUT / "q075_p3_ic_gap_down.csv", index=False)

# ── BCS 4 melt-up analogs ─────────────────────────────────────────────
print("\n" + "=" * 70)
print("BCS 4 melt-up analogs (pass: cum >= -$10k AND worst >= -0.5% NLV)")
print("=" * 70)

# Extract best 14-TD sub-window per historical period (rule: max SPX_14d - VIX_14d %)
def best_14td_window(mkt_full, start_date, end_date):
    period = mkt_full[(mkt_full.index >= start_date) & (mkt_full.index <= end_date)]
    best_score = -1e9
    best_start = None
    for i in range(len(period) - 14):
        spx_s = period["spx_close"].iloc[i]
        spx_e = period["spx_close"].iloc[i + 14]
        vix_s = period["vix"].iloc[i]
        vix_e = period["vix"].iloc[i + 14]
        spx_ret = (spx_e / spx_s - 1.0) * 100
        vix_ret = (vix_e / vix_s - 1.0) * 100
        score = spx_ret - vix_ret
        if score > best_score:
            best_score = score
            best_start = period.index[i]
    if best_start is None:
        return None, None
    bs_loc = mkt_full.index.get_loc(best_start)
    win_path = [mkt_full["spx_close"].iloc[bs_loc + j] / mkt_full["spx_close"].iloc[bs_loc]
                for j in range(1, 15)]
    return win_path, {"start": best_start, "score": best_score,
                       "spx_start": mkt_full["spx_close"].iloc[bs_loc],
                       "spx_end": mkt_full["spx_close"].iloc[bs_loc + 14],
                       "vix_start": mkt_full["vix"].iloc[bs_loc],
                       "vix_end": mkt_full["vix"].iloc[bs_loc + 14]}

# Mechanical: scan all 10d windows, find max(SPX_10d% - VIX_10d%)
def mechanical_best_window(mkt_full, window_days=10):
    best_score = -1e9
    best_start = None
    for i in range(len(mkt_full) - window_days):
        spx_s = mkt_full["spx_close"].iloc[i]
        spx_e = mkt_full["spx_close"].iloc[i + window_days]
        vix_s = mkt_full["vix"].iloc[i]
        vix_e = mkt_full["vix"].iloc[i + window_days]
        spx_ret = (spx_e / spx_s - 1.0) * 100
        vix_ret = (vix_e / vix_s - 1.0) * 100
        score = spx_ret - vix_ret
        if score > best_score:
            best_score = score
            best_start = mkt_full.index[i]
    if best_start is None:
        return None, None
    bs_loc = mkt_full.index.get_loc(best_start)
    # Extend to 14d path for IC simulation (mechanical is 10d but we use 14 DTE hold)
    win_path = [mkt_full["spx_close"].iloc[min(bs_loc + j, len(mkt_full) - 1)] /
                mkt_full["spx_close"].iloc[bs_loc] for j in range(1, 15)]
    return win_path, {"start": best_start, "score": best_score,
                       "spx_start": mkt_full["spx_close"].iloc[bs_loc],
                       "vix_start": mkt_full["vix"].iloc[bs_loc]}

analogs = []
for name, start, end in [
    ("2019_Q1_rebound", "2019-01-02", "2019-03-31"),
    ("2023_Q4_rally",   "2023-10-02", "2023-12-31"),
    ("2024_H1_rally",   "2024-01-02", "2024-06-30"),
]:
    path, meta = best_14td_window(mkt, start, end)
    if path is None:
        continue
    analogs.append((name, path, meta))

mech_path, mech_meta = mechanical_best_window(mkt, 10)
analogs.append(("mechanical_10d", mech_path, mech_meta))

mech_records = []
for name, _, meta in analogs:
    mech_records.append({"analog": name, **meta})
pd.DataFrame(mech_records).to_csv(OUT / "q075_p3_bcs_mechanical_metadata.csv", index=False)
print("\nAnalog metadata:")
for name, _, meta in analogs:
    print(f"  {name}: start={meta['start'].strftime('%Y-%m-%d')}, score={meta['score']:.2f}, "
          f"SPX {meta.get('spx_start', 0):.0f}→{meta.get('spx_end', meta.get('spx_start', 0)*(1+meta['score']/100)):.0f}")

bcs_rows = []
print(f"\n{'Analog':<22} {'n':>4} {'Cum $':>10} {'Worst $':>10} {'Hit%':>6} {'Pass[cum≥-10k & worst≥-0.5%NLV & hit≥60%]':<48}")
print("-" * 110)
for name, path, _ in analogs:
    trades = []
    for d, row in type_c_first.iterrows():
        if d not in mkt.index:
            continue
        spx_0 = mkt.loc[d, "spx_close"]
        analog_path = [spx_0 * r for r in path]
        t = simulate_trade_full(d, spx_0, row["vix"], row["ivp_252"], BCS_WIDTH,
                                 IC_BCS_PLANNED_DTE, "call",
                                 iv_shock=0.0, skew_shock=0.0,
                                 override_path=analog_path)
        if t is None:
            continue
        t["analog"] = name
        trades.append(t)
    df = pd.DataFrame(trades)
    if len(df) == 0:
        continue
    cum = df["pnl"].sum()
    worst = df["pnl"].min()
    hit = (df["pnl"] > 0).mean() * 100
    worst_pct_nlv = worst / NLV * 100
    c1 = cum >= -10_000
    c2 = worst_pct_nlv >= -0.5
    c3 = hit >= 60
    pass_flag = ("✓" if c1 else "✗") + ("✓" if c2 else "✗") + ("✓" if c3 else "✗")
    overall_pass = "✅ PASS" if (c1 and c2) else "❌ FAIL"  # c3 diagnostic only
    print(f"{name:<22} {len(df):>4} ${cum:>+9,.0f} ${worst:>+9,.0f} {hit:>5.1f}% {pass_flag} {overall_pass}")
    for t in trades:
        bcs_rows.append(t)
pd.DataFrame(bcs_rows).to_csv(OUT / "q075_p3_bcs_analogs.csv", index=False)

# ── C2 sBPS diagnostic ────────────────────────────────────────────────
print("\n" + "=" * 70)
print("C2 sBPS diagnostic (one-pass; do NOT promote)")
print("=" * 70)

c2_trades = []
for d, row in type_c_first.iterrows():
    if d not in mkt.index:
        continue
    spx_0 = mkt.loc[d, "spx_close"]
    t = simulate_trade_full(d, spx_0, row["vix"], row["ivp_252"], 25,
                             SBPS_PLANNED_DTE, "put",
                             iv_shock=0.20, skew_shock=0.10)
    if t is None:
        continue
    c2_trades.append(t)

# Also gap-down diagnostic
c2_gap_trades = []
for gp in [-0.02, -0.03]:
    for d, row in type_c_first.iterrows():
        if d not in mkt.index:
            continue
        spx_0 = mkt.loc[d, "spx_close"]
        t = simulate_trade_full(d, spx_0, row["vix"], row["ivp_252"], 25,
                                 SBPS_PLANNED_DTE, "put",
                                 iv_shock=0.20, skew_shock=0.10,
                                 gap_day=1, gap_pct=gp)
        if t is None:
            continue
        t["gap_pct"] = gp
        c2_gap_trades.append(t)

c2_df = pd.DataFrame(c2_trades)
gap_df_c2 = pd.DataFrame(c2_gap_trades)
print(f"\nC2 sBPS base case: n={len(c2_df)}, cum=${c2_df['pnl'].sum():+,.0f}, "
      f"worst=${c2_df['pnl'].min():+,.0f}, forced_exit={c2_df['forced_by_stress'].sum()}")
top5 = c2_df.nsmallest(5, "pnl")[["entry_date", "exit_date", "pnl", "forced_by_stress"]]
print(f"Top-5 losses:")
print(top5.to_string(index=False))
for gp in [-0.02, -0.03]:
    sub = gap_df_c2[gap_df_c2["gap_pct"] == gp]
    print(f"\nC2 sBPS gap-down {gp*100:.0f}% entry+1: n={len(sub)}, cum=${sub['pnl'].sum():+,.0f}, "
          f"worst=${sub['pnl'].min():+,.0f}")

c2_df.to_csv(OUT / "q075_p3_c2_diagnostic.csv", index=False)

print("\n" + "=" * 70)
print("Q075 P3 done. CSVs in research/q075/")
print("=" * 70)
