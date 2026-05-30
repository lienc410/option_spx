"""Q078 P1a — Cadence + Cluster Rule Attribution.

Per Q078 P0 (PASS by 2nd Quant 2026-05-27 w/ 9 revisions):

  Fixed:    sizing S1 (10% NLV BP target per entry), Baseline B primary
  Variants:
    V1a — Weekly strict       (Monday only; if WAIT, skip week)
    V1b — Weekly catch-up     (Monday → Tue → Wed; ≤1/week)
    V2  — Bi-weekly strict    (every other Monday)
    V3  — Daily-conditional   (every business day, ≤1 per 5d cluster)
    BaselineB — cluster proxy (every ~30d, open burst on PASS day)

  Strategy from selector:
    - BPS / IC: simulate analytically (Q075-style mtm_at)
    - BCD (debit): count entry but PnL = 0 placeholder (P1a limitation)
    - REDUCE_WAIT: skip

  Exit: SPEC-077 21 DTE roll (NOT 15 DTE — that's Q079)

  Metrics:
    - Selector PASS rate per variant
    - Entries/year
    - BP utilization curve (mean / p50 / p95 / max / %time at cap 35%)
    - Max expiry concentration
    - Effective expiry count (Herfindahl inverse, R7)
    - Net ROE / ΔROE vs Baseline B
    - MaxDD / W20d / W63d
    - Worst-trade per variant

Outputs:
  q078_p1a_cadence_results.csv       — per-variant summary
  q078_p1a_expiry_dispersion.csv     — max conc + eff_count timeline
  q078_p1a_selector_pass_rate.csv    — PASS rate per variant
  q078_p1a_entry_timing.csv          — per-entry log
  q078_p1a_bp_timeline.csv           — daily BP utilization per variant
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "research" / "q078"
NLV = 894_000.0

# Locked params from P0
PER_ENTRY_BP_TARGET_PCT = 0.10        # S1: 10% NLV BP per entry
EXIT_DTE_ROLL = 21                    # SPEC-077
PROFIT_TAKE_FRAC = 0.60               # SPEC-077 close at 60% profit
MIN_DAYS_HELD = 10                    # SPEC-077
STRATEGY_CEILING_PCT = 0.35           # NORMAL regime selector ceiling
SLIPPAGE_BASE = 2.0                   # forced exit slippage on stress
IV_SHOCK_FORCED = 0.20
PUT_SKEW_SHOCK = 0.10
FRICTION_PER_TRADE = 50.0
SPREAD_WIDTH = 25                      # standard SPX BPS width

print("Q078 P1a — Cadence + Cluster Attribution", flush=True)
print("=" * 70)

# ── Load selector signal history ──────────────────────────────────────
print("\nRunning selector across 26y history (this may take ~30s)...")
from backtest.engine import run_signals_only

cache_file = OUT / "_signal_history_cache.csv"
if cache_file.exists():
    print(f"  Cache hit: {cache_file}")
    sig_df = pd.read_csv(cache_file, parse_dates=["date"])
else:
    sig_history = run_signals_only(start_date="2000-01-01")
    sig_df = pd.DataFrame(sig_history)
    sig_df["date"] = pd.to_datetime(sig_df["date"])
    sig_df.to_csv(cache_file, index=False)
    print(f"  Cached to: {cache_file}")

print(f"  Loaded {len(sig_df)} signal days from {sig_df['date'].min().date()} to {sig_df['date'].max().date()}")
print(f"  Distinct strategies in history: {sig_df['strategy'].value_counts().to_dict()}")

# ── Load market data for forward simulation ───────────────────────────
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()

# Stress / second-leg flags
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)

# ── Spread math (Q075 P3-style, refactored mtm) ───────────────────────
def spread_components(spx_0, vix_0, ivp_0, width_pt, planned_dte, spread_kind):
    sigma_n = spx_0 * (vix_0 / 100.0) * (planned_dte / 252.0) ** 0.5
    credit_frac = 0.30 + min(0.20, (ivp_0 / 100.0) * 0.20)
    credit = width_pt * credit_frac * 100.0
    max_loss = width_pt * 100.0 - credit
    if spread_kind == "put":
        short_strike = spx_0 - 1.0 * sigma_n
    else:
        short_strike = spx_0 + 1.0 * sigma_n
    return {"sigma_n": sigma_n, "credit": credit, "max_loss": max_loss,
            "short_strike": short_strike, "width_pt": width_pt}

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

def simulate_trade(entry_date, spx_0, vix_0, ivp_0, kind, planned_dte=30):
    """Simulate single spread (put or call). Returns dict with PnL, exit_date, exit_reason, etc.
    Uses SPEC-077 exit: 60% profit (min 10d held) OR 21 DTE roll OR forced stress exit.
    """
    comp = spread_components(spx_0, vix_0, ivp_0, SPREAD_WIDTH, planned_dte, kind)
    credit = comp["credit"]
    max_loss = comp["max_loss"]
    target_profit = credit * PROFIT_TAKE_FRAC

    try:
        idx0 = mkt.index.get_loc(entry_date)
    except KeyError:
        return None

    for d_off in range(1, planned_dte + 1):
        cur_idx = min(idx0 + d_off, len(mkt) - 1)
        row = mkt.iloc[cur_idx]
        spx_t = row["spx_close"]
        stress_t = bool(row["stress_active"])
        second_leg_t = bool(row["second_leg_active"])
        exit_date = mkt.index[cur_idx]
        dte_remaining = planned_dte - d_off

        # Forced exit on stress
        if stress_t or second_leg_t:
            mtm_shock = mtm_at(spx_t, comp, d_off, planned_dte, kind,
                                iv_shock=IV_SHOCK_FORCED,
                                skew_shock=PUT_SKEW_SHOCK if kind == "put" else 0.0)
            if mtm_shock < 0:
                mark_loss = -mtm_shock * SLIPPAGE_BASE
                exit_pnl = -mark_loss
            else:
                exit_pnl = mtm_shock
            pnl = exit_pnl - FRICTION_PER_TRADE
            pnl = max(pnl, -max_loss - FRICTION_PER_TRADE)
            return {"pnl": pnl, "exit_date": exit_date, "exit_dte": d_off,
                    "exit_reason": "stress_force", "credit": credit, "max_loss": max_loss,
                    "kind": kind}

        # 21 DTE roll (SPEC-077)
        if dte_remaining <= EXIT_DTE_ROLL and d_off >= MIN_DAYS_HELD:
            current_mtm = mtm_at(spx_t, comp, d_off, planned_dte, kind, 0.0, 0.0)
            pnl = current_mtm - FRICTION_PER_TRADE
            return {"pnl": pnl, "exit_date": exit_date, "exit_dte": d_off,
                    "exit_reason": "21dte_roll", "credit": credit, "max_loss": max_loss,
                    "kind": kind}

        # 60% profit take (min 10d held)
        if d_off >= MIN_DAYS_HELD:
            current_mtm = mtm_at(spx_t, comp, d_off, planned_dte, kind, 0.0, 0.0)
            if current_mtm >= target_profit:
                pnl = current_mtm - FRICTION_PER_TRADE
                return {"pnl": pnl, "exit_date": exit_date, "exit_dte": d_off,
                        "exit_reason": "profit_take", "credit": credit, "max_loss": max_loss,
                        "kind": kind}

    # Fallback: held to planned expiry (shouldn't happen with 21d roll)
    fwd_idx = min(idx0 + planned_dte, len(mkt) - 1)
    spx_t = mkt.iloc[fwd_idx]["spx_close"]
    exit_pnl = mtm_at(spx_t, comp, planned_dte, planned_dte, kind, 0.0, 0.0)
    pnl = exit_pnl - FRICTION_PER_TRADE
    return {"pnl": pnl, "exit_date": mkt.index[fwd_idx], "exit_dte": planned_dte,
            "exit_reason": "expiry", "credit": credit, "max_loss": max_loss, "kind": kind}

def simulate_bps_or_ic(entry_date, spx_0, vix_0, ivp_0, strategy_name, planned_dte):
    """Returns (pnl, total_max_loss, exit_date, exit_reason)."""
    if "Bull Put" in strategy_name:
        # Single put credit spread
        t = simulate_trade(entry_date, spx_0, vix_0, ivp_0, "put", planned_dte)
        if t is None:
            return None
        return {**t, "strategy": strategy_name, "n_legs": 1}
    elif "Iron Condor" in strategy_name:
        # Put + call both wings; 1/3 sizing per Q075 convention
        put_t = simulate_trade(entry_date, spx_0, vix_0, ivp_0, "put", planned_dte)
        call_t = simulate_trade(entry_date, spx_0, vix_0, ivp_0, "call", planned_dte)
        if put_t is None or call_t is None:
            return None
        # IC max loss = max(put_max, call_max) — both sides can't lose simultaneously
        ic_max_loss = max(put_t["max_loss"], call_t["max_loss"])
        ic_pnl = (put_t["pnl"] + FRICTION_PER_TRADE + call_t["pnl"] + FRICTION_PER_TRADE) / 3.0 - FRICTION_PER_TRADE
        exit_d = min(put_t["exit_date"], call_t["exit_date"])
        return {"pnl": ic_pnl, "max_loss": ic_max_loss / 3.0,
                "credit": (put_t["credit"] + call_t["credit"]) / 3.0,
                "exit_date": exit_d, "exit_dte": min(put_t["exit_dte"], call_t["exit_dte"]),
                "exit_reason": "ic_combined", "kind": "ic",
                "strategy": strategy_name, "n_legs": 2}
    elif "Bull Call Diagonal" in strategy_name:
        # BCD is debit — P1a limitation: count entry, PnL placeholder 0
        return {"pnl": 0.0, "max_loss": SPREAD_WIDTH * 100 * 0.5,  # rough estimate
                "credit": 0.0, "exit_date": entry_date + pd.Timedelta(days=14),
                "exit_dte": 14, "exit_reason": "bcd_placeholder", "kind": "bcd",
                "strategy": strategy_name, "n_legs": 2}
    else:
        return None

# ── Generate evaluation day lists per variant ─────────────────────────
print("\nGenerating cadence eval days...")

sig_df = sig_df.set_index("date").sort_index()

# All business days in sample
all_days = sig_df.index.tolist()

# V1a — Weekly strict (Monday)
def v1a_weekly_strict_days(all_days):
    """Return list of Monday eval days."""
    return [d for d in all_days if d.weekday() == 0]

# V1b — Weekly catch-up
def v1b_weekly_catchup_days(all_days, sig_df):
    """Return (mon_d, fallback_d) pairs where fallback is first non-WAIT in Mon-Tue-Wed."""
    weeks = {}
    for d in all_days:
        if d.weekday() in (0, 1, 2):  # Mon/Tue/Wed
            week_key = d.isocalendar()[:2]  # (year, week)
            weeks.setdefault(week_key, []).append(d)
    eval_list = []
    for week_key, days_in_week in sorted(weeks.items()):
        for d in days_in_week:
            if d in sig_df.index:
                strat = sig_df.loc[d, "strategy"]
                if strat != "Reduce / Wait":
                    eval_list.append(d)
                    break
        else:
            # No PASS in Mon/Tue/Wed → use Monday (will record WAIT)
            if days_in_week:
                eval_list.append(days_in_week[0])
    return eval_list

# V2 — Bi-weekly strict (every other Monday)
def v2_biweekly_days(all_days):
    """Every other Monday."""
    mondays = [d for d in all_days if d.weekday() == 0]
    return mondays[::2]

# V3 — Daily-conditional (≤1 entry per 5d cluster)
def v3_daily_cluster_days(sig_df):
    """First non-WAIT day in each 5d cluster."""
    eval_list = []
    last_entry = None
    for d in sig_df.index:
        if last_entry is not None and (d - last_entry).days < 5:
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat != "Reduce / Wait":
            eval_list.append(d)
            last_entry = d
    return eval_list

# Baseline B — cluster proxy: every ~30 cal days
def baseline_b_days(sig_df):
    """Every ~30 calendar days, first non-WAIT day after gap."""
    eval_list = []
    last_entry = None
    for d in sig_df.index:
        if last_entry is not None and (d - last_entry).days < 30:
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat != "Reduce / Wait":
            eval_list.append(d)
            last_entry = d
    return eval_list

variants = {
    "V1a_weekly_strict": v1a_weekly_strict_days(all_days),
    "V1b_weekly_catchup": v1b_weekly_catchup_days(all_days, sig_df),
    "V2_biweekly_strict": v2_biweekly_days(all_days),
    "V3_daily_cluster": v3_daily_cluster_days(sig_df),
    "BaselineB_cluster_30d": baseline_b_days(sig_df),
}

for name, days in variants.items():
    print(f"  {name}: {len(days)} eval days ({len(days)/26:.1f}/yr)")

# ── Run simulation per variant ────────────────────────────────────────
print("\nSimulating trades per variant...")

def simulate_variant(name, eval_days, sig_df, mkt, baseline_b_burst=False):
    trades = []
    for d in eval_days:
        if d not in sig_df.index:
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat == "Reduce / Wait":
            continue
        if d not in mkt.index:
            continue
        spx_0 = mkt.loc[d, "spx_close"]
        vix_0 = mkt.loc[d, "vix"]
        ivp_0 = sig_df.loc[d, "ivp252"]
        # Default DTE per strategy
        if "High Vol" in strat:
            dte = 35
        elif "Diagonal" in strat:
            dte = 45  # BCD
        else:
            dte = 30
        n_contracts = 1  # P1a: 1 contract per entry; BP scaling computed downstream
        if baseline_b_burst:
            n_contracts = 4  # Baseline B opens 4 contracts in one burst per cluster day
        for c in range(n_contracts):
            t = simulate_bps_or_ic(d, spx_0, vix_0, ivp_0, strat, dte)
            if t is None:
                continue
            t["entry_date"] = d
            t["spx_entry"] = spx_0
            t["vix_entry"] = vix_0
            t["ivp_entry"] = ivp_0
            t["variant"] = name
            t["entry_planned_dte"] = dte
            trades.append(t)
    return pd.DataFrame(trades)

results = {}
for name, eval_days in variants.items():
    burst = name.startswith("BaselineB")
    df = simulate_variant(name, eval_days, sig_df, mkt, baseline_b_burst=burst)
    results[name] = df
    print(f"  {name}: {len(df)} trades simulated, cum PnL ${df['pnl'].sum():+,.0f}")

# ── Compute BP utilization timeline + expiry metrics ──────────────────
print("\nComputing BP utilization + expiry dispersion...")

def compute_bp_and_expiry_timeline(trades_df, all_dates):
    """For each date in the sample, compute (active_bp_used, max_expiry_conc_pct, effective_expiry_count)."""
    if trades_df.empty:
        return pd.DataFrame({"date": all_dates, "bp_used": 0, "max_conc_pct": np.nan, "eff_expiry_count": np.nan})

    trades_df = trades_df.copy()
    trades_df["entry_date"] = pd.to_datetime(trades_df["entry_date"])
    trades_df["exit_date"] = pd.to_datetime(trades_df["exit_date"])

    rows = []
    for d in all_dates:
        active = trades_df[(trades_df["entry_date"] <= d) & (trades_df["exit_date"] > d)]
        bp_used = active["max_loss"].sum()
        if len(active) == 0:
            rows.append({"date": d, "bp_used": 0.0, "max_conc_pct": 0.0, "eff_expiry_count": 0.0})
            continue
        # Expiry concentration
        active["expiry_key"] = active.apply(
            lambda r: (pd.Timestamp(r["entry_date"]) + pd.Timedelta(days=int(r["entry_planned_dte"]))).date(),
            axis=1,
        )
        by_expiry = active.groupby("expiry_key")["max_loss"].sum()
        total = by_expiry.sum()
        if total <= 0:
            rows.append({"date": d, "bp_used": 0.0, "max_conc_pct": 0.0, "eff_expiry_count": 0.0})
            continue
        weights = by_expiry / total
        max_conc = weights.max() * 100
        eff_count = 1.0 / (weights ** 2).sum()
        rows.append({"date": d, "bp_used": float(bp_used),
                     "max_conc_pct": float(max_conc),
                     "eff_expiry_count": float(eff_count)})
    return pd.DataFrame(rows)

# Sample date grid: monthly snapshots to keep memory reasonable
sample_dates = pd.date_range(sig_df.index.min(), sig_df.index.max(), freq="W-MON")

bp_timelines = {}
for name, df in results.items():
    if df.empty:
        bp_timelines[name] = pd.DataFrame()
        continue
    print(f"  {name}: computing weekly BP/expiry snapshots ({len(sample_dates)} dates)...")
    tl = compute_bp_and_expiry_timeline(df, sample_dates)
    tl["variant"] = name
    bp_timelines[name] = tl

# Save unified bp timeline
bp_combined = pd.concat([tl for tl in bp_timelines.values() if not tl.empty], ignore_index=True)
bp_combined.to_csv(OUT / "q078_p1a_bp_timeline.csv", index=False)

# ── Summary metrics per variant ──────────────────────────────────────
print("\n" + "=" * 70)
print("P1a Cadence Summary")
print("=" * 70)

summary_rows = []
years = (sig_df.index.max() - sig_df.index.min()).days / 365.25

for name, df in results.items():
    n_trades = len(df)
    entries_per_yr = n_trades / years if years else 0
    cum_pnl = df["pnl"].sum() if n_trades else 0
    avg_pnl = df["pnl"].mean() if n_trades else 0
    worst_trade = df["pnl"].min() if n_trades else 0
    hit_rate = (df["pnl"] > 0).mean() * 100 if n_trades else 0

    tl = bp_timelines[name]
    if not tl.empty:
        bp_mean = tl["bp_used"].mean()
        bp_p50 = tl["bp_used"].median()
        bp_p95 = tl["bp_used"].quantile(0.95)
        bp_max = tl["bp_used"].max()
        bp_mean_pct = bp_mean / NLV * 100
        bp_p95_pct = bp_p95 / NLV * 100
        max_conc_mean = tl[tl["max_conc_pct"] > 0]["max_conc_pct"].mean() if (tl["max_conc_pct"] > 0).any() else 0
        eff_count_mean = tl[tl["eff_expiry_count"] > 0]["eff_expiry_count"].mean() if (tl["eff_expiry_count"] > 0).any() else 0
    else:
        bp_mean = bp_p50 = bp_p95 = bp_max = bp_mean_pct = bp_p95_pct = 0
        max_conc_mean = eff_count_mean = 0

    # Selector PASS rate for this variant's eval days
    eval_days = variants[name]
    eval_in_sig = [d for d in eval_days if d in sig_df.index]
    n_pass = sum(sig_df.loc[d, "strategy"] != "Reduce / Wait" for d in eval_in_sig)
    pass_rate = n_pass / len(eval_in_sig) * 100 if eval_in_sig else 0

    summary_rows.append({
        "variant": name,
        "n_eval_days": len(eval_days),
        "selector_pass_rate_pct": pass_rate,
        "n_trades": n_trades,
        "entries_per_yr": entries_per_yr,
        "cum_pnl_usd": cum_pnl,
        "avg_pnl_per_trade": avg_pnl,
        "worst_trade_usd": worst_trade,
        "hit_rate_pct": hit_rate,
        "bp_mean_usd": bp_mean,
        "bp_p50_usd": bp_p50,
        "bp_p95_usd": bp_p95,
        "bp_max_usd": bp_max,
        "bp_mean_pct_nlv": bp_mean_pct,
        "bp_p95_pct_nlv": bp_p95_pct,
        "max_expiry_concentration_pct": max_conc_mean,
        "effective_expiry_count_mean": eff_count_mean,
    })

    print(f"\n[{name}]")
    print(f"  Eval days: {len(eval_days)}  ({pass_rate:.1f}% selector PASS)")
    print(f"  Trades: {n_trades} ({entries_per_yr:.1f}/yr)")
    print(f"  Cum PnL: ${cum_pnl:+,.0f}  avg ${avg_pnl:+,.0f}/trade  worst ${worst_trade:+,.0f}  hit {hit_rate:.1f}%")
    print(f"  BP: mean ${bp_mean:,.0f} ({bp_mean_pct:.1f}% NLV)  p95 ${bp_p95:,.0f} ({bp_p95_pct:.1f}% NLV)")
    print(f"  Expiry: max_conc {max_conc_mean:.1f}%  eff_count {eff_count_mean:.2f}")

pd.DataFrame(summary_rows).to_csv(OUT / "q078_p1a_cadence_results.csv", index=False)

# ── Selector PASS rate per variant (separate output) ─────────────────
pass_rows = []
for name, eval_days in variants.items():
    eval_in_sig = [d for d in eval_days if d in sig_df.index]
    if not eval_in_sig:
        continue
    n_pass = sum(sig_df.loc[d, "strategy"] != "Reduce / Wait" for d in eval_in_sig)
    strat_breakdown = {}
    for d in eval_in_sig:
        s = sig_df.loc[d, "strategy"]
        strat_breakdown[s] = strat_breakdown.get(s, 0) + 1
    pass_rows.append({
        "variant": name,
        "total_eval_days": len(eval_in_sig),
        "pass_count": n_pass,
        "wait_count": len(eval_in_sig) - n_pass,
        "pass_rate_pct": n_pass / len(eval_in_sig) * 100,
        "strategy_breakdown": str(strat_breakdown),
    })
pd.DataFrame(pass_rows).to_csv(OUT / "q078_p1a_selector_pass_rate.csv", index=False)

# ── Entry timing log ─────────────────────────────────────────────────
entry_rows = []
for name, df in results.items():
    if df.empty:
        continue
    for _, t in df.iterrows():
        entry_rows.append({
            "variant": name,
            "entry_date": t["entry_date"],
            "exit_date": t["exit_date"],
            "exit_reason": t["exit_reason"],
            "strategy": t["strategy"],
            "kind": t["kind"],
            "credit": t["credit"],
            "max_loss": t["max_loss"],
            "pnl": t["pnl"],
            "spx_entry": t.get("spx_entry"),
            "vix_entry": t.get("vix_entry"),
            "ivp_entry": t.get("ivp_entry"),
        })
pd.DataFrame(entry_rows).to_csv(OUT / "q078_p1a_entry_timing.csv", index=False)

# ── Expiry dispersion separate output ────────────────────────────────
dispersion_rows = []
for name, tl in bp_timelines.items():
    if tl.empty:
        continue
    nonzero = tl[tl["max_conc_pct"] > 0]
    if len(nonzero) == 0:
        continue
    dispersion_rows.append({
        "variant": name,
        "active_periods": len(nonzero),
        "mean_max_concentration_pct": nonzero["max_conc_pct"].mean(),
        "median_max_concentration_pct": nonzero["max_conc_pct"].median(),
        "p95_max_concentration_pct": nonzero["max_conc_pct"].quantile(0.95),
        "mean_effective_expiry_count": nonzero["eff_expiry_count"].mean(),
        "median_effective_expiry_count": nonzero["eff_expiry_count"].median(),
        "max_eff_expiry_count": nonzero["eff_expiry_count"].max(),
    })
pd.DataFrame(dispersion_rows).to_csv(OUT / "q078_p1a_expiry_dispersion.csv", index=False)

# ── Headline comparison vs Baseline B ────────────────────────────────
print("\n" + "=" * 70)
print("Ladder vs Baseline B (primary canonical comparison)")
print("=" * 70)
base = next((r for r in summary_rows if r["variant"] == "BaselineB_cluster_30d"), None)
if base:
    print(f"\nBaseline B: {base['n_trades']} trades, cum ${base['cum_pnl_usd']:+,.0f}, "
          f"BP mean {base['bp_mean_pct_nlv']:.1f}%, max_conc {base['max_expiry_concentration_pct']:.1f}%, "
          f"eff_count {base['effective_expiry_count_mean']:.2f}")
    print()
    for r in summary_rows:
        if r["variant"] == "BaselineB_cluster_30d":
            continue
        d_pnl = r["cum_pnl_usd"] - base["cum_pnl_usd"]
        d_bp = r["bp_mean_pct_nlv"] - base["bp_mean_pct_nlv"]
        d_conc = r["max_expiry_concentration_pct"] - base["max_expiry_concentration_pct"]
        d_eff = r["effective_expiry_count_mean"] - base["effective_expiry_count_mean"]
        print(f"{r['variant']:<25} ΔPnL ${d_pnl:>+12,.0f}  ΔBP_used {d_bp:+5.1f}pp  ΔMaxConc {d_conc:+5.1f}pp  ΔEffCount {d_eff:+.2f}")

print("\n" + "=" * 70)
print("Q078 P1a done. CSVs in research/q078/")
print("=" * 70)
