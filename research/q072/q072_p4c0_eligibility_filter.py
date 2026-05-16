"""Q072 P4C.0 — Eligibility Filter.

Per brief §P4C.0 + PM gate-decision additions (2026-05-15):

Eligibility filter is the FIRST gate. Candidates that fail eligibility are not
ranked, not priced, not entered. Six hard rules:

    R1: SPX PM pool cap          (default X% NLV)
    R2: /ES SPAN cap             (default Y% NLV)
    R3: Combined economic cap    (default Z% NLV)
    R4: Max short-vol exposure cap (sum of short-vega-paying sleeves)
    R5: Stress episode cap       (lower cap during tight stress episode)
    R6: No-new-short-vol if second-leg selloff state ← PM-added rule

Initial cap values (from production reverse-engineering + brief):
    X = 70   (SPX PM pool)
    Y = 80   (/ES SPAN — V2f historically peaks ~86%)
    Z = 60   (combined economic across pools, % of combined NLV)
    short_vol_cap = 50  (% combined NLV — caps sum of BPS_HV+IC_HV+HV_Ladder)
    stress_episode_cap = 60   (SPX PM pool cap reduced during stress)
    second_leg_block = absolute (no new short-vol sleeve in second-leg state)

This script:
    1. Reconstructs daily portfolio state from P1/P3 outputs
    2. Builds historical candidate trade list (baseline + DD + HV)
    3. For each candidate entry day, runs the filter
    4. Outputs blocker log + by-rule breakdown

Second-leg state detection:
    Active when ALL true:
        - SPX in drawdown ≥ 8% from 60d high
        - SPX has had ≥ 2% intermediate bounce in last 30 days
        - VIX ≥ 25
        - Days since current episode start > 14
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"
BASELINE = REPO / "research" / "q042" / "baseline_19y_trades.csv"
DD_TRADES = REPO / "data" / "q042_backtest_trades.csv"
HV_TRADES = OUT / "q072_hv_ladder_v2f_baseline_trades.csv"

SPX_NLV = 100_000.0
ES_NLV = 100_000.0
COMBINED_NLV = SPX_NLV + ES_NLV
ES_MULTIPLIER = 50.0
ES_SPAN_FRAC = 0.05

# Cap defaults (initial values, P4C.5 will sensitivity-test)
CAP_SPX_PM = 70.0
CAP_ES_SPAN = 80.0
CAP_COMBINED = 60.0  # % of combined NLV
CAP_SHORT_VOL = 50.0
CAP_STRESS_EPISODE = 60.0  # SPX PM pool reduced during tight stress
SECOND_LEG_BLOCK_SHORT_VOL = True

SHORT_VOL_STRATS = {"Bull Put Spread (High Vol)", "Iron Condor (High Vol)",
                    "Bear Call Spread (High Vol)"}
SHORT_VOL_SLEEVES = {"HV_Ladder", "BPS_HV", "IC_HV", "BearCall_HV"}


@dataclass
class CandidateTrade:
    sleeve: str            # 'main_bps' / 'main_ic' / 'bps_hv' / 'dd_overlay_A' / 'dd_overlay_B' / 'hv_ladder'
    strategy: str          # original strategy name
    entry_date: pd.Timestamp
    bp_dollar: float       # estimated BP requirement at entry
    pool: str              # 'SPX_PM' or 'ES_SPAN'
    is_short_vol: bool
    exit_date: pd.Timestamp


@dataclass
class FilterResult:
    passed: bool
    blocker: str | None    # None if passed; else the rule name


def detect_second_leg_state(daily: pd.DataFrame) -> pd.Series:
    """Detect second-leg selloff state per PM's rule R6."""
    close = daily["spx_close"]
    high_60d = close.rolling(60, min_periods=10).max()
    dd_60d = close / high_60d - 1.0

    # Check intermediate bounce in last 30d
    bounce_flag = pd.Series(False, index=daily.index)
    for i in range(30, len(daily)):
        window = close.iloc[i - 30:i + 1]
        low_in_window = window.min()
        idx_low = window.idxmin()
        # after the low, did we bounce ≥2%?
        post_low = window[window.index > idx_low]
        if len(post_low) > 0 and (post_low.max() / low_in_window - 1) > 0.02:
            # And are we currently at or near new low?
            if close.iloc[i] <= low_in_window * 1.01:
                bounce_flag.iloc[i] = True

    # Days since current episode start
    eid = daily["episode_id_tight"].values
    days_in_ep = np.zeros(len(daily), dtype=int)
    cur_ep = -1
    counter = 0
    for i, e in enumerate(eid):
        if e != cur_ep:
            cur_ep = e
            counter = 0 if e >= 0 else -1
        else:
            if counter >= 0:
                counter += 1
        days_in_ep[i] = counter

    flag = (
        (dd_60d <= -0.08)
        & bounce_flag
        & (daily["vix"] >= 25)
        & (pd.Series(days_in_ep, index=daily.index) > 14)
    )
    return flag.astype(bool)


def build_portfolio_state(daily: pd.DataFrame, baseline: pd.DataFrame,
                          dd: pd.DataFrame, hv: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct daily portfolio BP, short-vol exposure, second-leg state."""
    state = pd.DataFrame(index=daily.index)
    state["spx_pm_bp_pct"] = 0.0
    state["es_span_bp_pct"] = 0.0
    state["short_vol_bp_dollar"] = 0.0

    # baseline trades (main + HV-feeds)
    for _, t in baseline.iterrows():
        m = (state.index >= t["entry_date"]) & (state.index <= t["exit_date"])
        state.loc[m, "spx_pm_bp_pct"] += t["bp_pct_account"]
        if t["strategy"].strip() in SHORT_VOL_STRATS:
            state.loc[m, "short_vol_bp_dollar"] += t["bp_pct_account"] / 100 * SPX_NLV

    # DD overlay (SPX pool; NOT short-vol — it's long gamma)
    for _, t in dd.iterrows():
        m = (state.index >= t["entry_date"]) & (state.index <= t["exit_date"])
        state.loc[m, "spx_pm_bp_pct"] += t["account_pct"] * 100

    # HV Ladder (/ES pool; short-vol)
    for _, t in hv.iterrows():
        m = (state.index >= t["entry_date"]) & (state.index <= t["exit_date"])
        span = ES_SPAN_FRAC * t["entry_spx"] * ES_MULTIPLIER * t["contracts"]
        state.loc[m, "es_span_bp_pct"] += span / ES_NLV * 100
        state.loc[m, "short_vol_bp_dollar"] += span

    state["combined_bp_dollar"] = (
        state["spx_pm_bp_pct"] / 100 * SPX_NLV
        + state["es_span_bp_pct"] / 100 * ES_NLV
    )
    state["combined_bp_pct"] = state["combined_bp_dollar"] / COMBINED_NLV * 100
    state["short_vol_bp_pct"] = state["short_vol_bp_dollar"] / COMBINED_NLV * 100

    state["stress_episode"] = daily["episode_id_tight"] >= 0
    state["second_leg"] = detect_second_leg_state(daily)
    return state


def run_filter(candidate: CandidateTrade, state_row: pd.Series) -> FilterResult:
    """Apply 6 hard rules. Return first blocker, or pass."""
    new_bp_pct_pool = (candidate.bp_dollar /
                       (SPX_NLV if candidate.pool == "SPX_PM" else ES_NLV)) * 100
    new_bp_dollar = candidate.bp_dollar
    new_combined_pct = new_bp_dollar / COMBINED_NLV * 100

    # R1: SPX PM pool cap
    if candidate.pool == "SPX_PM":
        if state_row["spx_pm_bp_pct"] + new_bp_pct_pool > CAP_SPX_PM:
            return FilterResult(False, "R1_spx_pm_pool_cap")
    # R2: /ES SPAN cap
    if candidate.pool == "ES_SPAN":
        if state_row["es_span_bp_pct"] + new_bp_pct_pool > CAP_ES_SPAN:
            return FilterResult(False, "R2_es_span_cap")
    # R3: Combined economic cap
    if state_row["combined_bp_pct"] + new_combined_pct > CAP_COMBINED:
        return FilterResult(False, "R3_combined_economic_cap")
    # R4: Max short-vol exposure
    if candidate.is_short_vol:
        new_sv = state_row["short_vol_bp_pct"] + new_combined_pct
        if new_sv > CAP_SHORT_VOL:
            return FilterResult(False, "R4_short_vol_cap")
    # R5: Stress episode reduced cap
    if state_row["stress_episode"] and candidate.pool == "SPX_PM":
        if state_row["spx_pm_bp_pct"] + new_bp_pct_pool > CAP_STRESS_EPISODE:
            return FilterResult(False, "R5_stress_episode_cap")
    # R6: Second-leg blocks new short-vol
    if SECOND_LEG_BLOCK_SHORT_VOL and state_row["second_leg"] and candidate.is_short_vol:
        return FilterResult(False, "R6_second_leg_short_vol_block")
    return FilterResult(True, None)


def build_candidate_list(baseline: pd.DataFrame, dd: pd.DataFrame,
                         hv: pd.DataFrame) -> list[CandidateTrade]:
    candidates = []
    for _, t in baseline.iterrows():
        strat = t["strategy"].strip()
        sleeve = strat.replace(" ", "_").replace("(", "").replace(")", "")
        candidates.append(CandidateTrade(
            sleeve=sleeve,
            strategy=strat,
            entry_date=t["entry_date"],
            bp_dollar=t["bp_pct_account"] / 100 * SPX_NLV,
            pool="SPX_PM",
            is_short_vol=strat in SHORT_VOL_STRATS,
            exit_date=t["exit_date"],
        ))
    for _, t in dd.iterrows():
        candidates.append(CandidateTrade(
            sleeve=f"DD_Overlay_{t['sleeve_id']}",
            strategy="DD Overlay",
            entry_date=t["entry_date"],
            bp_dollar=t["account_pct"] * SPX_NLV,
            pool="SPX_PM",
            is_short_vol=False,
            exit_date=t["exit_date"],
        ))
    for _, t in hv.iterrows():
        span = ES_SPAN_FRAC * t["entry_spx"] * ES_MULTIPLIER * t["contracts"]
        candidates.append(CandidateTrade(
            sleeve="HV_Ladder",
            strategy="HV Ladder (V2f)",
            entry_date=t["entry_date"],
            bp_dollar=span,
            pool="ES_SPAN",
            is_short_vol=True,
            exit_date=t["exit_date"],
        ))
    return candidates


def main():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    baseline = pd.read_csv(BASELINE, parse_dates=["entry_date", "exit_date"])
    dd = pd.read_csv(DD_TRADES, parse_dates=["entry_date", "exit_date"])
    hv = pd.read_csv(HV_TRADES, parse_dates=["entry_date", "exit_date"])

    print("Building portfolio state...")
    state = build_portfolio_state(daily, baseline, dd, hv)
    state.to_csv(OUT / "q072_p4c0_portfolio_state.csv", float_format="%.3f")

    print(f"Daily state stats:")
    print(f"  spx_pm_bp_pct  avg {state.spx_pm_bp_pct.mean():.1f}  P95 {state.spx_pm_bp_pct.quantile(0.95):.1f}  max {state.spx_pm_bp_pct.max():.1f}")
    print(f"  es_span_bp_pct avg {state.es_span_bp_pct.mean():.1f}  P95 {state.es_span_bp_pct.quantile(0.95):.1f}  max {state.es_span_bp_pct.max():.1f}")
    print(f"  combined_bp_pct avg {state.combined_bp_pct.mean():.1f}  P95 {state.combined_bp_pct.quantile(0.95):.1f}  max {state.combined_bp_pct.max():.1f}")
    print(f"  short_vol_bp_pct avg {state.short_vol_bp_pct.mean():.1f}  P95 {state.short_vol_bp_pct.quantile(0.95):.1f}  max {state.short_vol_bp_pct.max():.1f}")
    print(f"  stress_episode days: {state.stress_episode.sum()} ({state.stress_episode.mean()*100:.1f}%)")
    print(f"  second_leg days: {state.second_leg.sum()} ({state.second_leg.mean()*100:.1f}%)")

    print(f"\nRunning eligibility on {len(baseline) + len(dd) + len(hv)} historical candidates...")
    candidates = build_candidate_list(baseline, dd, hv)

    # For counterfactual evaluation: when checking candidate C entering on date D,
    # use portfolio state EXCLUDING candidate C itself (would be circular). Approximate
    # by subtracting C's BP from state if C is currently active (since real entry on
    # day D means it just started — state on D would already include C). Simpler: use
    # state on prior trading day (D-1).
    state_lag1 = state.shift(1)

    log = []
    for c in candidates:
        if c.entry_date not in state.index:
            continue
        idx = state.index.get_loc(c.entry_date)
        if idx == 0:
            continue
        sr = state_lag1.iloc[idx]
        r = run_filter(c, sr)
        log.append({
            "sleeve": c.sleeve,
            "strategy": c.strategy,
            "entry_date": c.entry_date,
            "bp_dollar": round(c.bp_dollar, 0),
            "pool": c.pool,
            "is_short_vol": c.is_short_vol,
            "spx_pm_bp_before": round(float(sr["spx_pm_bp_pct"]), 1),
            "es_span_bp_before": round(float(sr["es_span_bp_pct"]), 1),
            "combined_bp_before": round(float(sr["combined_bp_pct"]), 1),
            "short_vol_bp_before": round(float(sr["short_vol_bp_pct"]), 1),
            "stress_episode": bool(sr["stress_episode"]),
            "second_leg": bool(sr["second_leg"]),
            "passed": r.passed,
            "blocker": r.blocker,
        })
    log_df = pd.DataFrame(log)
    log_df.to_csv(OUT / "q072_p4c0_eligibility_log.csv", index=False)

    print("\n" + "=" * 70)
    print("Q072 P4C.0 — Eligibility Filter Results")
    print("=" * 70)

    total = len(log_df)
    passed = log_df.passed.sum()
    blocked = total - passed
    print(f"\nTotal candidates: {total}")
    print(f"Passed: {passed} ({passed / total * 100:.1f}%)")
    print(f"Blocked: {blocked} ({blocked / total * 100:.1f}%)")

    print(f"\nBlocker breakdown:")
    blocker_counts = log_df[~log_df.passed].blocker.value_counts()
    print(blocker_counts.to_string())

    print(f"\nBlocked candidates by sleeve:")
    sleeve_blocked = log_df[~log_df.passed].sleeve.value_counts()
    print(sleeve_blocked.to_string())

    print(f"\nBlocked candidates by year:")
    log_df["year"] = pd.to_datetime(log_df.entry_date).dt.year
    year_blocked = log_df[~log_df.passed].groupby("year").size()
    print(year_blocked.to_string())

    # Cap binding analysis: what % of time was each cap close to bind?
    print(f"\nCap-binding stats (state distribution vs caps):")
    print(f"  Days SPX_PM >= 60%: {(state.spx_pm_bp_pct >= 60).sum()}")
    print(f"  Days SPX_PM >= 65%: {(state.spx_pm_bp_pct >= 65).sum()}")
    print(f"  Days combined >= 50%: {(state.combined_bp_pct >= 50).sum()}")
    print(f"  Days combined >= 60%: {(state.combined_bp_pct >= 60).sum()}")
    print(f"  Days short_vol >= 40%: {(state.short_vol_bp_pct >= 40).sum()}")
    print(f"  Days short_vol >= 50%: {(state.short_vol_bp_pct >= 50).sum()}")

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
