"""Q072 P4C.4 + Full 5-Allocator Simulation.

Simulates 19y portfolio under each of 5 allocator rules × 2 cap configs:
    allocators: main-first / sleeve-first / FCFS / static-cap / priority
    caps:       default / B_tight

For each day:
    1. Expire trades whose exit_date < today
    2. Collect new candidates (entry_date == today)
    3. Order by allocator rule
    4. For each in order: check eligibility (R1-R6 from P4C.0); if pass, enter
    5. Record entered + blocked

After simulation:
    Daily P&L = linear distribution of entered trades' exit_pnl
    Daily BP per pool

Output: per (allocator × cap × split) metrics pack.

Note on "shadow lifecycle" (P4C.4 brief):
    For blocked trades we use realized exit_pnl as counterfactual (since baseline
    backtest already ran them). True forward-fill MTM repricing is overkill — the
    baseline IS the natural counterfactual. We track:
        - blocked_pnl_total: sum of exit_pnl of trades the allocator blocked
            (positive = allocator gave up these gains)
        - blocked_worst_trade: most negative exit_pnl of blocked trades
            (negative = allocator avoided this loss)
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research" / "q072"

DAILY_FLAGS = OUT / "q072_p1_daily_flags.csv"
BASELINE = REPO / "research" / "q042" / "baseline_19y_trades.csv"
DD_TRADES = REPO / "data" / "q042_backtest_trades.csv"
HV_TRADES = OUT / "q072_hv_ladder_v2f_baseline_trades.csv"
PRIORITY = OUT / "q072_p4c1_candidates_with_priority.csv"

SPX_NLV = 100_000.0
ES_NLV = 100_000.0
COMBINED_NLV = SPX_NLV + ES_NLV
ES_MULTIPLIER = 50.0
ES_SPAN_FRAC = 0.05

SHORT_VOL_STRATS = {"Bull Put Spread (High Vol)", "Iron Condor (High Vol)",
                    "Bear Call Spread (High Vol)"}
MAIN_SLEEVES = {"Bull Put Spread", "Iron Condor", "Bull Call Diagonal"}
DD_SLEEVES = {"DD_Overlay_A", "DD_Overlay_B"}

CAPS = {
    "default": dict(SPX_PM=70.0, ES_SPAN=80.0, COMBINED=60.0,
                    SHORT_VOL=50.0, STRESS_EPISODE=60.0,
                    STATIC_PER_SLEEVE=None),
    "B_tight": dict(SPX_PM=60.0, ES_SPAN=60.0, COMBINED=50.0,
                    SHORT_VOL=35.0, STRESS_EPISODE=50.0,
                    STATIC_PER_SLEEVE=None),
}

# Static per-sleeve caps (used by static-cap allocator only, applied on top of cap config)
STATIC_PER_SLEEVE_CAPS = {
    "main":       70.0,   # % of pool
    "dd_overlay": 20.0,
    "aftermath":  15.0,
    "hv_ladder":  60.0,   # /ES SPAN max
}

SPLITS = {
    "full":        ("2007-01-01", "2026-05-13"),
    "post2020":    ("2020-01-01", "2026-05-13"),
    "recent2y":    ("2024-01-01", "2026-05-13"),
    "stress_2008": ("2008-01-01", "2009-12-31"),
    "stress_2022": ("2022-01-01", "2022-12-31"),
}


@dataclass
class Candidate:
    sleeve: str
    sleeve_class: str        # main / dd_overlay / aftermath / hv_ladder
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    bp_dollar: float
    pool: str                # SPX_PM / ES_SPAN
    is_short_vol: bool
    priority: float
    realized_pnl: float
    arrival_order: int       # FCFS tiebreaker


def classify_sleeve(strategy: str) -> tuple[str, str]:
    """Return (sleeve_label, sleeve_class)."""
    s = strategy.strip()
    sleeve = s.replace(" ", "_").replace("(", "").replace(")", "")
    if s in MAIN_SLEEVES:
        return sleeve, "main"
    if s in SHORT_VOL_STRATS:
        return sleeve, "aftermath"  # Aftermath-gated HV main strategies
    return sleeve, "main"


def load_candidates() -> list[Candidate]:
    baseline = pd.read_csv(BASELINE, parse_dates=["entry_date", "exit_date"])
    baseline["strategy"] = baseline["strategy"].str.strip()
    dd = pd.read_csv(DD_TRADES, parse_dates=["entry_date", "exit_date"])
    hv = pd.read_csv(HV_TRADES, parse_dates=["entry_date", "exit_date"])
    priority = pd.read_csv(PRIORITY, parse_dates=["entry_date"])
    pri_lookup = priority.set_index(["sleeve", "entry_date"])["priority"].to_dict()

    cands = []
    order = 0
    for _, t in baseline.iterrows():
        sleeve, cls = classify_sleeve(t["strategy"])
        cands.append(Candidate(
            sleeve=sleeve, sleeve_class=cls,
            entry_date=t["entry_date"], exit_date=t["exit_date"],
            bp_dollar=t["bp_pct_account"] / 100 * SPX_NLV,
            pool="SPX_PM",
            is_short_vol=t["strategy"] in SHORT_VOL_STRATS,
            priority=pri_lookup.get((sleeve, t["entry_date"]), 0.0),
            realized_pnl=t["exit_pnl"],
            arrival_order=order,
        ))
        order += 1
    for _, t in dd.iterrows():
        sleeve = f"DD_Overlay_{t['sleeve_id']}"
        cands.append(Candidate(
            sleeve=sleeve, sleeve_class="dd_overlay",
            entry_date=t["entry_date"], exit_date=t["exit_date"],
            bp_dollar=t["account_pct"] * SPX_NLV,
            pool="SPX_PM",
            is_short_vol=False,
            priority=pri_lookup.get((sleeve, t["entry_date"]), 0.0),
            realized_pnl=t["exit_pnl"],
            arrival_order=order,
        ))
        order += 1
    for _, t in hv.iterrows():
        span = ES_SPAN_FRAC * t["entry_spx"] * ES_MULTIPLIER * t["contracts"]
        cands.append(Candidate(
            sleeve="HV_Ladder", sleeve_class="hv_ladder",
            entry_date=t["entry_date"], exit_date=t["exit_date"],
            bp_dollar=span, pool="ES_SPAN",
            is_short_vol=True,
            priority=pri_lookup.get(("HV_Ladder", t["entry_date"]), 0.0),
            realized_pnl=t["pnl"],
            arrival_order=order,
        ))
        order += 1
    return cands


def order_by_allocator(cands_today: list[Candidate], allocator: str) -> list[Candidate]:
    if allocator == "main-first":
        return sorted(cands_today,
                      key=lambda c: (0 if c.sleeve_class == "main" else 1, c.arrival_order))
    if allocator == "sleeve-first":
        return sorted(cands_today,
                      key=lambda c: (0 if c.sleeve_class != "main" else 1, c.arrival_order))
    if allocator == "FCFS":
        return sorted(cands_today, key=lambda c: c.arrival_order)
    if allocator == "static-cap":
        # static-cap order is FCFS but with per-sleeve constraint at acceptance time
        return sorted(cands_today, key=lambda c: c.arrival_order)
    if allocator == "priority":
        return sorted(cands_today, key=lambda c: -c.priority)
    raise ValueError(allocator)


def simulate(cands: list[Candidate], daily_index: pd.DatetimeIndex,
             second_leg_flag: pd.Series, stress_flag: pd.Series,
             allocator: str, cap_name: str) -> dict:
    cap = CAPS[cap_name]
    # group candidates by entry_date for fast lookup
    cands_by_day = {}
    for c in cands:
        cands_by_day.setdefault(c.entry_date, []).append(c)

    # active trades state
    active = []  # list of Candidate currently active
    # per-pool BP tracker (running)
    entered_log = []
    blocked_log = []

    daily_pnl = pd.Series(0.0, index=daily_index)
    daily_spx_bp = pd.Series(0.0, index=daily_index)
    daily_es_bp = pd.Series(0.0, index=daily_index)
    daily_combined_bp = pd.Series(0.0, index=daily_index)
    daily_short_vol_bp = pd.Series(0.0, index=daily_index)

    for dt in daily_index:
        # expire trades
        active = [t for t in active if t.exit_date >= dt]

        # compute current state (before today's new entries)
        spx_bp_pct = sum(t.bp_dollar for t in active if t.pool == "SPX_PM") / SPX_NLV * 100
        es_bp_pct = sum(t.bp_dollar for t in active if t.pool == "ES_SPAN") / ES_NLV * 100
        combined_bp_dollar = (
            sum(t.bp_dollar for t in active if t.pool == "SPX_PM")
            + sum(t.bp_dollar for t in active if t.pool == "ES_SPAN")
        )
        combined_pct = combined_bp_dollar / COMBINED_NLV * 100
        short_vol_dollar = sum(t.bp_dollar for t in active if t.is_short_vol)
        short_vol_pct = short_vol_dollar / COMBINED_NLV * 100

        # per-sleeve current BP (for static-cap allocator)
        sleeve_class_bp = {
            "main": sum(t.bp_dollar for t in active if t.sleeve_class == "main"),
            "dd_overlay": sum(t.bp_dollar for t in active if t.sleeve_class == "dd_overlay"),
            "aftermath": sum(t.bp_dollar for t in active if t.sleeve_class == "aftermath"),
            "hv_ladder": sum(t.bp_dollar for t in active if t.sleeve_class == "hv_ladder"),
        }

        # process new candidates today
        today_cands = cands_by_day.get(dt, [])
        if today_cands:
            ordered = order_by_allocator(today_cands, allocator)
            for c in ordered:
                # check eligibility (R1-R6) including current accumulated additions
                new_bp_pool_pct = (c.bp_dollar /
                                   (SPX_NLV if c.pool == "SPX_PM" else ES_NLV)) * 100
                new_combined_pct = c.bp_dollar / COMBINED_NLV * 100

                blocker = None
                if c.pool == "SPX_PM" and spx_bp_pct + new_bp_pool_pct > cap["SPX_PM"]:
                    blocker = "R1_spx_pm_pool_cap"
                elif c.pool == "ES_SPAN" and es_bp_pct + new_bp_pool_pct > cap["ES_SPAN"]:
                    blocker = "R2_es_span_cap"
                elif combined_pct + new_combined_pct > cap["COMBINED"]:
                    blocker = "R3_combined_economic_cap"
                elif c.is_short_vol and (short_vol_pct + new_combined_pct > cap["SHORT_VOL"]):
                    blocker = "R4_short_vol_cap"
                elif (stress_flag.loc[dt] if dt in stress_flag.index else False) and \
                     c.pool == "SPX_PM" and \
                     spx_bp_pct + new_bp_pool_pct > cap["STRESS_EPISODE"]:
                    blocker = "R5_stress_episode_cap"
                elif (second_leg_flag.loc[dt] if dt in second_leg_flag.index else False) \
                     and c.is_short_vol:
                    blocker = "R6_second_leg_short_vol_block"

                # additional static per-sleeve cap (only static-cap allocator)
                if blocker is None and allocator == "static-cap":
                    sc = STATIC_PER_SLEEVE_CAPS
                    if c.sleeve_class == "main":
                        if (sleeve_class_bp["main"] + c.bp_dollar) / SPX_NLV * 100 > sc["main"]:
                            blocker = "STATIC_main_cap"
                    elif c.sleeve_class == "dd_overlay":
                        if (sleeve_class_bp["dd_overlay"] + c.bp_dollar) / SPX_NLV * 100 > sc["dd_overlay"]:
                            blocker = "STATIC_dd_cap"
                    elif c.sleeve_class == "aftermath":
                        if (sleeve_class_bp["aftermath"] + c.bp_dollar) / SPX_NLV * 100 > sc["aftermath"]:
                            blocker = "STATIC_aftermath_cap"
                    elif c.sleeve_class == "hv_ladder":
                        if (sleeve_class_bp["hv_ladder"] + c.bp_dollar) / ES_NLV * 100 > sc["hv_ladder"]:
                            blocker = "STATIC_hv_cap"

                if blocker is None:
                    # accept
                    active.append(c)
                    entered_log.append({
                        "sleeve": c.sleeve, "entry_date": c.entry_date,
                        "exit_date": c.exit_date, "pnl": c.realized_pnl,
                        "bp_dollar": c.bp_dollar, "pool": c.pool,
                    })
                    # update running state
                    if c.pool == "SPX_PM":
                        spx_bp_pct += new_bp_pool_pct
                    else:
                        es_bp_pct += new_bp_pool_pct
                    combined_pct += new_combined_pct
                    if c.is_short_vol:
                        short_vol_pct += new_combined_pct
                    sleeve_class_bp[c.sleeve_class] += c.bp_dollar
                else:
                    blocked_log.append({
                        "sleeve": c.sleeve, "entry_date": c.entry_date,
                        "blocker": blocker, "realized_pnl": c.realized_pnl,
                        "bp_dollar": c.bp_dollar,
                    })

        # record daily state
        daily_spx_bp.loc[dt] = spx_bp_pct
        daily_es_bp.loc[dt] = es_bp_pct
        daily_combined_bp.loc[dt] = combined_pct
        daily_short_vol_bp.loc[dt] = short_vol_pct

    # daily P&L: linear distribution of entered trades
    for t in entered_log:
        m = (daily_pnl.index >= t["entry_date"]) & (daily_pnl.index <= t["exit_date"])
        n = m.sum()
        if n > 0:
            daily_pnl.loc[m] += t["pnl"] / n

    return {
        "allocator": allocator, "cap": cap_name,
        "entered": entered_log, "blocked": blocked_log,
        "daily_pnl": daily_pnl, "daily_spx_bp": daily_spx_bp,
        "daily_es_bp": daily_es_bp, "daily_combined_bp": daily_combined_bp,
    }


def compute_metrics(result: dict, split_window: tuple) -> dict:
    s, e = split_window
    idx = result["daily_pnl"].index
    mask = (idx >= s) & (idx <= e)
    pnl = result["daily_pnl"][mask].values
    spx_bp = result["daily_spx_bp"][mask]
    es_bp = result["daily_es_bp"][mask]
    combined_bp = result["daily_combined_bp"][mask]

    entered = [t for t in result["entered"]
               if s <= t["entry_date"].strftime("%Y-%m-%d") <= e]
    blocked = [t for t in result["blocked"]
               if s <= t["entry_date"].strftime("%Y-%m-%d") <= e]

    n_days = len(pnl)
    total = float(pnl.sum())
    years = n_days / 252
    avg_nlv = COMBINED_NLV + pnl.cumsum().mean()
    ann_roe = (total / years) / avg_nlv if years > 0 and avg_nlv > 0 else None
    sharpe = (pnl.mean() / pnl.std() * np.sqrt(252)) if pnl.std() > 0 else None
    cum = pnl.cumsum()
    dd = cum - np.maximum.accumulate(cum)
    max_dd = float(dd.min())
    worst_20d = float(pd.Series(pnl).rolling(20).sum().min())
    worst_trade = min((t["pnl"] for t in entered), default=0)
    blocked_pnl_total = sum(t["realized_pnl"] for t in blocked)
    blocked_worst = min((t["realized_pnl"] for t in blocked), default=0)

    return {
        "n_entered": len(entered),
        "n_blocked": len(blocked),
        "total_pnl": round(total, 0),
        "ann_roe_pct": round(ann_roe * 100, 2) if ann_roe is not None else None,
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "max_dd": round(max_dd, 0),
        "worst_trade": round(worst_trade, 0),
        "worst_20d": round(worst_20d, 0),
        "avg_spx_bp": round(float(spx_bp.mean()), 2),
        "peak_spx_bp": round(float(spx_bp.max()), 2),
        "avg_es_bp": round(float(es_bp.mean()), 2),
        "peak_es_bp": round(float(es_bp.max()), 2),
        "avg_combined_bp": round(float(combined_bp.mean()), 2),
        "blocked_pnl_total": round(blocked_pnl_total, 0),
        "blocked_worst_trade": round(blocked_worst, 0),
    }


def main():
    daily = pd.read_csv(DAILY_FLAGS, parse_dates=["date"]).set_index("date")
    cands = load_candidates()

    # Build state flags from daily
    second_leg = pd.Series(False, index=daily.index)
    # Re-detect second-leg from P4C.0 logic (reuse)
    from q072_p4c0_eligibility_filter import detect_second_leg_state
    second_leg = detect_second_leg_state(daily)
    stress_flag = daily["episode_id_tight"] >= 0

    allocators = ["main-first", "sleeve-first", "FCFS", "static-cap", "priority"]
    all_results = []

    for cap_name in CAPS:
        for allocator in allocators:
            print(f"Running {allocator} / {cap_name}...")
            r = simulate(cands, daily.index, second_leg, stress_flag, allocator, cap_name)
            for split, win in SPLITS.items():
                m = compute_metrics(r, win)
                all_results.append({
                    "allocator": allocator, "cap": cap_name, "split": split, **m
                })

    df = pd.DataFrame(all_results)
    df.to_csv(OUT / "q072_p4c4_allocator_results.csv", index=False)

    print("\n" + "=" * 90)
    print("Q072 P4C.4 — 5-Allocator Simulation Results")
    print("=" * 90)

    for split in ["full", "post2020", "recent2y", "stress_2022"]:
        print(f"\n--- {split} ---")
        sub = df[df.split == split]
        cols = ["allocator", "cap", "n_entered", "n_blocked", "total_pnl",
                "ann_roe_pct", "sharpe", "max_dd", "worst_20d",
                "peak_spx_bp", "peak_es_bp", "blocked_pnl_total", "blocked_worst_trade"]
        print(sub[cols].to_string(index=False))

    print(f"\nOutputs saved to {OUT}/")


if __name__ == "__main__":
    main()
