"""Q075 P2 — Constrained Simulator with Forced-Exit-on-Stress.

Per PM-locked parameters (2026-05-19) + 2nd Quant G2 PASS:

  Scope (constrained, NOT broad sweep):
    Core:        C3 small IC, C4 BCS
    Diagnostic:  C2 short-DTE BPS (informational only, not promotable from P2)
    Excluded:    C5 calendar, multi-entry cluster

  Sample: Type C first-in-cluster from Q075 P1 Primary sample.

  Locked parameters (PM 2026-05-19):
    Entry:            first-in-cluster Type C only
    Planned exit:     14 DTE (IC, BCS), 7 DTE (C2 short-DTE BPS)
    Forced exit:      stress_active flip True OR second_leg_active flip True
                      → exit at end-of-day on flip
    Stop:             trade-level stop at 2x credit loss
    Normal friction:  $50 round-trip per defined-risk trade
    Stress-exit slippage:
      BASE = 2.0x normal friction-adjusted mark
      Sensitivity sweep: 1.5x / 2.0x / 3.0x
    Strategy-specific stress shocks:
      IC put side:  IV +20%, put skew +10% on forced exit
      BCS:          downside stress provides RELIEF (call delta drops); test UPSIDE squeeze separately
      C2 BPS:       downside gap + gamma loss
    BCS upside squeeze (parametric base):
      +2% / +3% / +5% SPX over 5-10d
      Combined with VIX compression
    IC wing width sensitivity: 15 / 25 / 35 pt
    Cash hurdle:      FAIR BP-day BOXX yield on same capital-at-risk × actual holding days
    Cluster rule:     STRICT 1-per-cluster (≤3 cal-day gap)

  Pass/fail (per candidate):
    [1] Beats cash hurdle after forced stress exit
    [2] No material transition loss concentration (≤ 1 episode > -0.50% NLV per 5y window)
    [3] Worst single trade ≤ 1% NLV (≈ $8,940 on $894k NLV)
    [4] No new crisis-window failure (≥ -$2k per window)
    [5] ≥ 30 trades for inference
    [6] Clear ops rules

Outputs:
  q075_p2_trade_log.csv          — every trade with full detail
  q075_p2_summary_per_candidate.csv  — pass/fail per candidate per sensitivity
  q075_p2_squeeze_scenarios.csv      — BCS under +2/+3/+5% squeezes
  q075_p2_crisis_breakdown.csv       — 5 named windows
  q075_p2_cash_hurdle.csv            — fair BP-day baseline
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

# ── LOCKED PARAMETERS (PM 2026-05-19) ──────────────────────────────────
FRICTION_PER_TRADE = 50.0
STRESS_SLIPPAGE_BASE = 2.0
STRESS_SLIPPAGE_SENSITIVITY = [1.5, 2.0, 3.0]
STOP_MULT = 2.0
IC_WING_WIDTH_BASE = 25       # SPX points
IC_WING_SENSITIVITY = [15, 25, 35]
BCS_SQUEEZE_SCENARIOS = [
    ("+2pct_5d", 0.02, 5),
    ("+3pct_5d", 0.03, 5),
    ("+5pct_10d", 0.05, 10),
]
IC_BCS_PLANNED_DTE = 14
SBPS_PLANNED_DTE = 7
IV_SHOCK_BASE = 0.20      # IV +20% on forced exit (puts hurt)
PUT_SKEW_SHOCK = 0.10     # Additional +10% put skew on forced exit
WORST_TRADE_LIMIT_PCT_NLV = 0.01   # 1% NLV per trade
TRANSITION_LOSS_LIMIT_PCT_NLV = 0.005  # -0.5% NLV episode threshold

print("Q075 P2 — Constrained Simulator (PM-locked 2026-05-19)", flush=True)
print("=" * 70)
print(f"\nLocked parameters:")
print(f"  Friction: ${FRICTION_PER_TRADE} round-trip")
print(f"  Stress slippage: base {STRESS_SLIPPAGE_BASE}x, sensitivity {STRESS_SLIPPAGE_SENSITIVITY}")
print(f"  IV shock on forced exit: +{IV_SHOCK_BASE*100:.0f}%")
print(f"  Put skew shock: +{PUT_SKEW_SHOCK*100:.0f}%")
print(f"  IC wing widths: {IC_WING_SENSITIVITY}")
print(f"  BCS squeeze scenarios: {[s[0] for s in BCS_SQUEEZE_SCENARIOS]}")
print(f"  Cash hurdle: BP-day BOXX {CASH_YIELD*100:.1f}% × capital × holding days")

# ── Load Q075 P1 primary sample (Type C first-in-cluster only) ────────
print("\nLoading P1 Primary sample...")
primary_days = pd.read_csv(OUT / "q075_p1_primary_sample_days.csv",
                            index_col=0, parse_dates=True)
type_c_first = primary_days[
    (primary_days["type"] == "C_high_vol_controlled") &
    (primary_days["is_first_in_cluster"])
].copy()
print(f"  Type C first-in-cluster trades: {len(type_c_first)}")

# Reload market data for forward path (need daily SPX/VIX/stress flags)
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

# Stress / 2nd-leg flags (SPEC-104 R5/R6 unchanged)
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)

# ── Trade simulator core ───────────────────────────────────────────────
def simulate_short_spread(spread_kind, entry_date, spx_0, vix_0, ivp_0,
                          width_pt, planned_dte, slippage_mult,
                          apply_iv_shock=True, apply_skew_shock=True,
                          override_forward_path=None):
    """Simulate a defined-risk short spread (put credit or call credit).

    Returns dict with PnL, exit_reason, exit_date, exit_dte, etc.

    spread_kind: "put" (BPS) or "call" (BCS)
    override_forward_path: optional list of SPX values to inject (for squeeze test)
    """
    sigma_n = spx_0 * (vix_0 / 100.0) * (planned_dte / 252.0) ** 0.5
    credit_frac = 0.30 + min(0.20, (ivp_0 / 100.0) * 0.20)   # 30-50% of width
    credit = width_pt * credit_frac * 100.0
    max_loss = width_pt * 100.0 - credit
    stop_loss = STOP_MULT * credit

    if spread_kind == "put":
        short_strike = spx_0 - 1.0 * sigma_n
        long_strike = short_strike - width_pt
    else:  # call
        short_strike = spx_0 + 1.0 * sigma_n
        long_strike = short_strike + width_pt

    # Forward path
    try:
        idx0 = mkt.index.get_loc(entry_date)
    except KeyError:
        return None

    # Walk forward day by day
    pnl = None
    exit_reason = None
    exit_dte = planned_dte
    exit_date = None
    forced_by_stress = False

    for d_off in range(1, planned_dte + 1):
        cur_idx = idx0 + d_off
        if cur_idx >= len(mkt):
            cur_idx = len(mkt) - 1

        if override_forward_path is not None and d_off <= len(override_forward_path):
            spx_t = override_forward_path[d_off - 1]
            vix_t = vix_0  # squeeze test: VIX compression — keep low
            stress_t = False
            second_leg_t = False
        else:
            row = mkt.iloc[cur_idx]
            spx_t = row["spx_close"]
            vix_t = row["vix"]
            stress_t = bool(row["stress_active"])
            second_leg_t = bool(row["second_leg_active"])

        # Check forced exit
        if stress_t or second_leg_t:
            # Compute exit mark with stress shock
            dte_remaining = planned_dte - d_off
            time_decay_factor = max(0.05, (dte_remaining / planned_dte) ** 0.7)
            base_credit_remaining = credit * time_decay_factor

            if spread_kind == "put":
                # Put: harmed by SPX falling
                if spx_t <= short_strike:
                    intrinsic = min((short_strike - spx_t) * 100.0, width_pt * 100.0)
                    mark_loss = intrinsic - base_credit_remaining
                else:
                    mark_loss = -base_credit_remaining   # negative = we keep credit
                # Stress shock: IV+20% increases extrinsic value (bad for short)
                if apply_iv_shock:
                    iv_shock_loss = credit * IV_SHOCK_BASE * 1.5  # 30% of credit
                    mark_loss += iv_shock_loss
                if apply_skew_shock:
                    skew_loss = credit * PUT_SKEW_SHOCK
                    mark_loss += skew_loss
            else:  # call
                # Call: under downside stress, call moves OTM → RELIEF
                if spx_t >= short_strike:
                    intrinsic = min((spx_t - short_strike) * 100.0, width_pt * 100.0)
                    mark_loss = intrinsic - base_credit_remaining
                else:
                    mark_loss = -base_credit_remaining
                # Stress shock: IV+20% also raises call extrinsic, but call usually OTM in downside stress
                # Apply smaller shock (10% of credit instead of 30%)
                if apply_iv_shock:
                    iv_shock_loss = credit * IV_SHOCK_BASE * 0.5  # 10% of credit
                    mark_loss += iv_shock_loss
                # No skew shock for call side under downside stress (call skew often improves)

            # Slippage on adverse mark
            if mark_loss > 0:
                mark_loss *= slippage_mult

            pnl = credit - mark_loss - FRICTION_PER_TRADE
            pnl = max(pnl, -max_loss - FRICTION_PER_TRADE)
            exit_reason = "stress_force"
            exit_dte = d_off
            exit_date = mkt.index[cur_idx] if override_forward_path is None else entry_date + pd.Timedelta(days=d_off)
            forced_by_stress = True
            break

        # Check trade-level stop (intra-day SPX vs short strike)
        if spread_kind == "put" and spx_t <= short_strike:
            intrinsic = (short_strike - spx_t) * 100.0
            if intrinsic > stop_loss:
                pnl = -stop_loss - FRICTION_PER_TRADE
                exit_reason = "stop"
                exit_dte = d_off
                exit_date = mkt.index[cur_idx] if override_forward_path is None else entry_date + pd.Timedelta(days=d_off)
                break
        elif spread_kind == "call" and spx_t >= short_strike:
            intrinsic = (spx_t - short_strike) * 100.0
            if intrinsic > stop_loss:
                pnl = -stop_loss - FRICTION_PER_TRADE
                exit_reason = "stop"
                exit_dte = d_off
                exit_date = mkt.index[cur_idx] if override_forward_path is None else entry_date + pd.Timedelta(days=d_off)
                break

    if pnl is None:
        # Held to planned expiry
        fwd_idx = min(idx0 + planned_dte, len(mkt) - 1)
        spx_t = mkt.iloc[fwd_idx]["spx_close"]
        if override_forward_path is not None and planned_dte <= len(override_forward_path):
            spx_t = override_forward_path[planned_dte - 1]

        if spread_kind == "put":
            if spx_t >= short_strike:
                pnl = credit
            elif spx_t <= long_strike:
                pnl = -max_loss
            else:
                pnl = credit - (short_strike - spx_t) * 100.0
        else:  # call
            if spx_t <= short_strike:
                pnl = credit
            elif spx_t >= long_strike:
                pnl = -max_loss
            else:
                pnl = credit - (spx_t - short_strike) * 100.0
        pnl -= FRICTION_PER_TRADE
        exit_reason = "expiry"
        exit_date = mkt.index[fwd_idx]

    return {
        "entry_date": entry_date,
        "exit_date": exit_date,
        "exit_dte": exit_dte,
        "exit_reason": exit_reason,
        "pnl": pnl,
        "credit": credit,
        "max_loss": max_loss,
        "short_strike": short_strike,
        "long_strike": long_strike,
        "spx_0": spx_0,
        "vix_0": vix_0,
        "ivp_0": ivp_0,
        "sigma_n": sigma_n,
        "forced_by_stress": forced_by_stress,
        "spread_kind": spread_kind,
        "width_pt": width_pt,
    }


def simulate_ic(entry_date, spx_0, vix_0, ivp_0, width_pt, slippage_mult):
    """Iron condor = small put credit spread + small call credit spread, 1/3 size scaling."""
    put_trade = simulate_short_spread("put", entry_date, spx_0, vix_0, ivp_0,
                                       width_pt, IC_BCS_PLANNED_DTE, slippage_mult,
                                       apply_iv_shock=True, apply_skew_shock=True)
    call_trade = simulate_short_spread("call", entry_date, spx_0, vix_0, ivp_0,
                                        width_pt, IC_BCS_PLANNED_DTE, slippage_mult,
                                        apply_iv_shock=True, apply_skew_shock=False)
    if put_trade is None or call_trade is None:
        return None

    # 1/3 size combined IC
    pnl_combined_raw = (put_trade["pnl"] + put_trade["max_loss"] + FRICTION_PER_TRADE) + \
                       (call_trade["pnl"] + call_trade["max_loss"] + FRICTION_PER_TRADE)
    # Re-extract clean PnL components, then size to 1/3, then add IC-level friction
    put_pnl_clean = put_trade["pnl"] + FRICTION_PER_TRADE  # back out friction
    call_pnl_clean = call_trade["pnl"] + FRICTION_PER_TRADE
    ic_pnl = (put_pnl_clean + call_pnl_clean) / 3.0 - FRICTION_PER_TRADE

    # IC max loss = max(put_max_loss, call_max_loss) / 3 — both sides can't lose simultaneously fully
    ic_max_loss = max(put_trade["max_loss"], call_trade["max_loss"]) / 3.0

    # Forced by stress if either side was forced
    forced = put_trade["forced_by_stress"] or call_trade["forced_by_stress"]
    exit_dte = min(put_trade["exit_dte"], call_trade["exit_dte"])

    return {
        "entry_date": entry_date,
        "exit_date": min(put_trade["exit_date"], call_trade["exit_date"]),
        "exit_dte": exit_dte,
        "exit_reason": "stress_force" if forced else "expiry",
        "pnl": ic_pnl,
        "credit_combined": (put_trade["credit"] + call_trade["credit"]) / 3.0,
        "max_loss": ic_max_loss,
        "spx_0": spx_0,
        "vix_0": vix_0,
        "ivp_0": ivp_0,
        "forced_by_stress": forced,
        "spread_kind": "ic",
        "width_pt": width_pt,
        "put_pnl": put_pnl_clean / 3.0,
        "call_pnl": call_pnl_clean / 3.0,
    }


# ── Run all candidates ────────────────────────────────────────────────
print(f"\nRunning all candidates on {len(type_c_first)} Type C trades...")

all_trades = []

for slip_mult in STRESS_SLIPPAGE_SENSITIVITY:
    print(f"\n  Slippage {slip_mult}x:")

    # C3 IC — width sensitivity loop
    for width in IC_WING_SENSITIVITY:
        ic_trades = []
        for d, row in type_c_first.iterrows():
            if d not in mkt.index:
                continue
            spx_0 = mkt.loc[d, "spx_close"]
            t = simulate_ic(d, spx_0, row["vix"], row["ivp_252"], width, slip_mult)
            if t is None:
                continue
            t["candidate"] = f"C3_IC_w{width}"
            t["slippage_mult"] = slip_mult
            ic_trades.append(t)
        all_trades.extend(ic_trades)
        ic_df = pd.DataFrame(ic_trades)
        cum = ic_df["pnl"].sum() if len(ic_df) else 0
        worst = ic_df["pnl"].min() if len(ic_df) else 0
        forced_n = ic_df["forced_by_stress"].sum() if len(ic_df) else 0
        print(f"    C3 IC width={width:>2}pt: n={len(ic_df):>3} cum=${cum:>+10,.0f} worst=${worst:>+8,.0f} forced_by_stress={forced_n}")

    # C4 BCS — base case (no squeeze)
    bcs_trades = []
    for d, row in type_c_first.iterrows():
        if d not in mkt.index:
            continue
        spx_0 = mkt.loc[d, "spx_close"]
        t = simulate_short_spread("call", d, spx_0, row["vix"], row["ivp_252"],
                                   IC_WING_WIDTH_BASE, IC_BCS_PLANNED_DTE, slip_mult,
                                   apply_iv_shock=True, apply_skew_shock=False)
        if t is None:
            continue
        t["candidate"] = "C4_BCS"
        t["slippage_mult"] = slip_mult
        bcs_trades.append(t)
    all_trades.extend(bcs_trades)
    bcs_df = pd.DataFrame(bcs_trades)
    cum = bcs_df["pnl"].sum() if len(bcs_df) else 0
    worst = bcs_df["pnl"].min() if len(bcs_df) else 0
    forced_n = bcs_df["forced_by_stress"].sum() if len(bcs_df) else 0
    print(f"    C4 BCS:               n={len(bcs_df):>3} cum=${cum:>+10,.0f} worst=${worst:>+8,.0f} forced_by_stress={forced_n}")

    # C2 short-DTE BPS — diagnostic only
    sbps_trades = []
    for d, row in type_c_first.iterrows():
        if d not in mkt.index:
            continue
        spx_0 = mkt.loc[d, "spx_close"]
        t = simulate_short_spread("put", d, spx_0, row["vix"], row["ivp_252"],
                                   IC_WING_WIDTH_BASE, SBPS_PLANNED_DTE, slip_mult,
                                   apply_iv_shock=True, apply_skew_shock=True)
        if t is None:
            continue
        t["candidate"] = "C2_sBPS_diag"
        t["slippage_mult"] = slip_mult
        sbps_trades.append(t)
    all_trades.extend(sbps_trades)
    sbps_df = pd.DataFrame(sbps_trades)
    cum = sbps_df["pnl"].sum() if len(sbps_df) else 0
    worst = sbps_df["pnl"].min() if len(sbps_df) else 0
    forced_n = sbps_df["forced_by_stress"].sum() if len(sbps_df) else 0
    print(f"    C2 sBPS (diagnostic): n={len(sbps_df):>3} cum=${cum:>+10,.0f} worst=${worst:>+8,.0f} forced_by_stress={forced_n}")

trade_log = pd.DataFrame(all_trades)
# Strip nested objects for CSV
trade_log_export = trade_log.drop(columns=[c for c in ["put_pnl", "call_pnl"] if c in trade_log.columns]).copy()
trade_log_export.to_csv(OUT / "q075_p2_trade_log.csv", index=False)
print(f"\n  Saved trade log: {len(trade_log)} rows")

# ── BCS upside squeeze scenarios (BASE slippage 2.0x only) ────────────
print("\n" + "=" * 70)
print("BCS upside squeeze scenarios (parametric base, slippage 2.0x)")
print("=" * 70)

squeeze_rows = []
for sname, sq_pct, sq_days in BCS_SQUEEZE_SCENARIOS:
    trades = []
    for d, row in type_c_first.iterrows():
        if d not in mkt.index:
            continue
        spx_0 = mkt.loc[d, "spx_close"]
        # Build override forward path: linear rise to sq_pct over sq_days, then plateau
        path = []
        for d_off in range(1, IC_BCS_PLANNED_DTE + 1):
            if d_off <= sq_days:
                spx_t = spx_0 * (1 + sq_pct * d_off / sq_days)
            else:
                spx_t = spx_0 * (1 + sq_pct)
            path.append(spx_t)
        t = simulate_short_spread("call", d, spx_0, row["vix"], row["ivp_252"],
                                   IC_WING_WIDTH_BASE, IC_BCS_PLANNED_DTE, 2.0,
                                   apply_iv_shock=False,  # squeeze test isolates upside path
                                   apply_skew_shock=False,
                                   override_forward_path=path)
        if t is None:
            continue
        t["scenario"] = sname
        trades.append(t)

    df_sq = pd.DataFrame(trades)
    n = len(df_sq)
    cum = df_sq["pnl"].sum()
    worst = df_sq["pnl"].min()
    hit = (df_sq["pnl"] > 0).mean() * 100
    print(f"  {sname}: n={n} cum=${cum:>+10,.0f} worst=${worst:>+8,.0f} hit={hit:.1f}%")
    squeeze_rows.append({
        "scenario": sname,
        "n_trades": n,
        "cum_pnl": cum,
        "avg_pnl": cum / n if n else 0,
        "worst_pnl": worst,
        "hit_rate_pct": hit,
    })
pd.DataFrame(squeeze_rows).to_csv(OUT / "q075_p2_squeeze_scenarios.csv", index=False)

# ── Fair BP-day cash hurdle ────────────────────────────────────────────
print("\n" + "=" * 70)
print("Fair BP-day cash hurdle (per trade: max_loss × daily yield × actual holding days)")
print("=" * 70)

cash_rows = []
for cand in trade_log["candidate"].unique():
    for slip in STRESS_SLIPPAGE_SENSITIVITY:
        sub = trade_log[(trade_log["candidate"] == cand) & (trade_log["slippage_mult"] == slip)]
        if len(sub) == 0:
            continue
        # Compute cash hurdle per trade then sum
        sub_cash_per_trade = sub["max_loss"] * (CASH_YIELD / 252.0) * sub["exit_dte"]
        cash_cum = sub_cash_per_trade.sum()
        cand_cum = sub["pnl"].sum()
        excess = cand_cum - cash_cum
        cash_rows.append({
            "candidate": cand,
            "slippage_mult": slip,
            "n_trades": len(sub),
            "candidate_cum_pnl_usd": cand_cum,
            "fair_cash_hurdle_usd": cash_cum,
            "excess_over_cash_usd": excess,
            "excess_per_trade_usd": excess / len(sub),
            "worst_single_trade_usd": sub["pnl"].min(),
            "worst_single_trade_pct_nlv": sub["pnl"].min() / NLV * 100,
            "n_forced_by_stress": int(sub["forced_by_stress"].sum()),
            "pct_forced_by_stress": sub["forced_by_stress"].mean() * 100,
        })
cash_df = pd.DataFrame(cash_rows)
cash_df.to_csv(OUT / "q075_p2_cash_hurdle.csv", index=False)

# ── Summary per candidate per slippage (with PASS/FAIL bits) ──────────
print("\n" + "=" * 70)
print("SUMMARY — pass/fail per candidate per slippage")
print("=" * 70)
print(f"\nPass criteria:")
print(f"  [1] excess over cash > 0")
print(f"  [2] worst single trade ≥ -${WORST_TRADE_LIMIT_PCT_NLV * NLV:,.0f} ({WORST_TRADE_LIMIT_PCT_NLV*100:.1f}% NLV)")
print(f"  [3] ≥ 30 trades")

summary_rows = []
print(f"\n{'Candidate':<18} {'Slip':>5} {'n':>4} {'Cand $':>12} {'Cash $':>10} {'Excess $':>12} {'Worst':>10} {'%force':>8} {'PASS'}")
print("-" * 100)
for _, r in cash_df.iterrows():
    c1 = r["excess_over_cash_usd"] > 0
    c2 = r["worst_single_trade_usd"] >= -WORST_TRADE_LIMIT_PCT_NLV * NLV
    c3 = r["n_trades"] >= 30
    pass_all = c1 and c2 and c3
    flags = ("✓" if c1 else "✗") + ("✓" if c2 else "✗") + ("✓" if c3 else "✗")
    print(f"{r['candidate']:<18} {r['slippage_mult']:>4.1f}x {r['n_trades']:>4d} "
          f"${r['candidate_cum_pnl_usd']:>+11,.0f} ${r['fair_cash_hurdle_usd']:>+9,.0f} "
          f"${r['excess_over_cash_usd']:>+11,.0f} ${r['worst_single_trade_usd']:>+9,.0f} "
          f"{r['pct_forced_by_stress']:>7.1f}% {flags} {'✅' if pass_all else '❌'}")
    summary_rows.append({
        **r.to_dict(),
        "pass_excess_cash": c1,
        "pass_worst_trade": c2,
        "pass_sample_size": c3,
        "pass_all": pass_all,
    })
pd.DataFrame(summary_rows).to_csv(OUT / "q075_p2_summary_per_candidate.csv", index=False)

# ── Crisis breakdown (5 windows) ─────────────────────────────────────
print("\n" + "=" * 70)
print("Crisis window breakdown (base slippage 2.0x)")
print("=" * 70)
crisis_windows = {
    "DotCom_2000_03": ("2000-03-01", "2000-04-30"),
    "PreGFC_2007_07": ("2007-07-01", "2007-09-30"),
    "Vol_2018_02":    ("2018-01-15", "2018-03-15"),
    "COVID_2020_02":  ("2020-02-15", "2020-03-31"),
    "Bear_2022_01":   ("2022-01-01", "2022-02-28"),
}
crisis_rows = []
trade_log["entry_date"] = pd.to_datetime(trade_log["entry_date"])
base_log = trade_log[trade_log["slippage_mult"] == 2.0]
for cname, (s, e) in crisis_windows.items():
    in_window = base_log[(base_log["entry_date"] >= pd.Timestamp(s)) &
                          (base_log["entry_date"] <= pd.Timestamp(e))]
    if len(in_window) == 0:
        print(f"  [{cname}] no trades in window")
        continue
    for cand in in_window["candidate"].unique():
        sub = in_window[in_window["candidate"] == cand]
        cum = sub["pnl"].sum()
        worst = sub["pnl"].min()
        print(f"  [{cname}] {cand}: n={len(sub)} cum=${cum:+,.0f} worst=${worst:+,.0f}")
        crisis_rows.append({
            "crisis": cname,
            "candidate": cand,
            "n_trades": len(sub),
            "cum_pnl_usd": cum,
            "worst_trade_usd": worst,
        })
pd.DataFrame(crisis_rows).to_csv(OUT / "q075_p2_crisis_breakdown.csv", index=False)

print("\n" + "=" * 70)
print("Q075 P2 done. CSVs in research/q075/")
print("=" * 70)
