"""
Q036 Phase 2 — Idle-BP-conditional overlay pilots.

Per Quant framing 2026-04-26 (`doc/q036_framing_and_feasibility_2026-04-26.md`)
and PM 2026-04-26 approval: test 3 conditional aftermath overlay pilots, all
gated on idle-BP threshold, evaluated at the **capital-allocation layer**
(NOT as rule replacements).

Pilot variants (see `task/IDLE_BP_OVERLAY_RESEARCH_NOTE.md` candidate list):

  V_baseline   : V_A SPEC-066 (no overlay)                                        — Q036 reference baseline
  Overlay-A    : 1.5× first-entry IFF idle BP ≥ 70%; else 1×                       — gentle overlay
  Overlay-B    : 2.0× first-entry IFF idle BP ≥ 70% AND VIX < 30; else 1×          — disaster cap variant
  Overlay-C    : 2.0× first-entry IFF idle BP ≥ 70% AND no IC_HV currently open    — short-gamma no-overlap variant

All 3 overlays ALSO apply a "boosted-first → block same-cluster 2nd" rule:
  if the same-cluster first entry deployed boosted size, no 2nd same-cluster
  entry is taken (deployed extra capital already). If the first entry was 1×
  (overlay condition failed), V_A behavior applies (cap=2 same-cluster).

Metrics output:
  §1 Account-level scoreboard (PnL, ROE, ann ROE, positive-year proportion)
  §2 Tail/risk pack (MaxDD, CVaR 5% account-level, disaster window net,
                     peak system BP%, forced-liquidation proxy)
  §3 Capital-allocation pack (idle-BP utilization rate, crowd-out check,
                              short-gamma stacking actualized at overlay trigger)
  §4 Standard Phase-4 metrics pack (PnL/BPd, marginal $/BPd vs V_A AND vs idle,
                                    worst trade, IC_HV CVaR 5%, max BP%, #2× ovl days)
  §5 IC_HV vs non-IC_HV decomposition (Q036 crowd-out test)
  §6 2026-03 double-peak sanity case
  §7 Cluster coverage
  §8 Recent slice 2018+ (account-level + standard pack)
  §9 Verdict scaffold

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q036_phase2_overlay_pilots
"""

from __future__ import annotations

import inspect
import pickle
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

import backtest.engine as engine_mod
import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from strategy.selector import StrategyName

START = "2000-01-01"
RECENT_SLICE_START = "2018-01-01"
OFF_PEAK_B = 0.10
DISASTER_VIX_THRESHOLD = 30.0
IDLE_BP_THRESHOLD = 0.70           # overlay fires only if (1 - used_bp) >= this
HV_NORMAL_BP = 0.07                # baseline IC_HV bp_target (fraction)
HV_NORMAL_BP_PCT = 7.0             # same in percentage scale
ACCOUNT_SIZE = 150_000.0
BOOSTED_BP_FRACTION_GUARD = HV_NORMAL_BP * 1.05  # heuristic to detect "boosted first"


# ──────────────────────────────────────────────────────────────────────
# Cluster map + VIX
# ──────────────────────────────────────────────────────────────────────

def _load_vix_close():
    pkl = Path("data/market_cache/yahoo__VIX__max__1d.pkl")
    df = pickle.loads(pkl.read_bytes())
    if hasattr(df, "Close"):
        s = df["Close"]
    else:
        s = df.iloc[:, 0]
    return {str(idx.date()): float(v) for idx, v in s.items() if v == v}


def build_cluster_map_and_vix() -> tuple[dict[str, str | None], dict[str, float]]:
    vix = _load_vix_close()
    dates = sorted(vix.keys())
    is_after: dict[str, bool] = {}
    for i, d in enumerate(dates):
        lo = max(0, i - 9)
        win = [vix[sd] for sd in dates[lo:i + 1]]
        peak = max(win)
        cur = vix[d]
        op = (peak - cur) / peak if peak > 0 else 0.0
        is_after[d] = (peak >= 28.0) and (op >= 0.10)

    cluster: dict[str, str | None] = {}
    cur_id: str | None = None
    for d in dates:
        if is_after[d]:
            if cur_id is None:
                cur_id = d
            cluster[d] = cur_id
        else:
            cur_id = None
            cluster[d] = None
    return cluster, vix


_CLUSTER_MAP: dict[str, str | None] = {}
_VIX_BY_DATE: dict[str, float] = {}


# ──────────────────────────────────────────────────────────────────────
# Block predicate (shared across all 3 overlays — adaptive)
# ──────────────────────────────────────────────────────────────────────

def _same_cluster_open_ic_hv(positions, cur_cluster, cluster_map):
    if cur_cluster is None:
        return []
    return [p for p in positions
            if p.strategy == StrategyName.IRON_CONDOR_HV
            and cluster_map.get(p.entry_date) == cur_cluster]


def _overlay_block(positions, rec, date_str, cluster_map):
    """Adaptive block: same-cluster 2nd is allowed (cap=2) IF first entry was 1× (overlay didn't fire);
    blocked if first entry was boosted (overlay deployed extra capital already)."""
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return any(p.strategy == rec.strategy for p in positions)
    same_strat = [p for p in positions if p.strategy == StrategyName.IRON_CONDOR_HV]
    cur = cluster_map.get(date_str)
    if cur is None:
        return len(same_strat) >= 2
    same_cluster = _same_cluster_open_ic_hv(positions, cur, cluster_map)
    if not same_cluster:
        return len(same_strat) >= 2  # respect global cap=2
    # Was any same-cluster open position boosted?
    boosted_open = any(
        getattr(p, "bp_target", 0.0) > BOOSTED_BP_FRACTION_GUARD
        for p in same_cluster
    )
    if boosted_open:
        return True
    return len(same_strat) >= 2


# ──────────────────────────────────────────────────────────────────────
# Doubler predicates (each takes _used_bp as 5th arg)
# ──────────────────────────────────────────────────────────────────────

def _idle_ok(used_bp: float) -> bool:
    return (1.0 - float(used_bp)) >= IDLE_BP_THRESHOLD


def _overlay_a_double(positions, rec, date_str, cluster_map, used_bp):
    """Overlay-A: 1.5× iff aftermath, no same-cluster open, idle BP ≥ 70%."""
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return False
    cur = cluster_map.get(date_str)
    if cur is None:
        return False
    if _same_cluster_open_ic_hv(positions, cur, cluster_map):
        return False
    return _idle_ok(used_bp)


def _overlay_b_double(positions, rec, date_str, cluster_map, used_bp):
    """Overlay-B: 2× iff aftermath, no same-cluster open, idle BP ≥ 70%, VIX < 30."""
    if not _overlay_a_double(positions, rec, date_str, cluster_map, used_bp):
        return False
    vix_today = _VIX_BY_DATE.get(date_str)
    if vix_today is None:
        return True
    return vix_today < DISASTER_VIX_THRESHOLD


def _overlay_c_double(positions, rec, date_str, cluster_map, used_bp):
    """Overlay-C: 2× iff aftermath, NO IC_HV open at all (any cluster), idle BP ≥ 70%."""
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return False
    cur = cluster_map.get(date_str)
    if cur is None:
        return False
    n_ic_hv_open = sum(1 for p in positions if p.strategy == StrategyName.IRON_CONDOR_HV)
    if n_ic_hv_open > 0:
        return False
    return _idle_ok(used_bp)


# ──────────────────────────────────────────────────────────────────────
# Patcher (extends Phase 4 patcher to thread _used_bp into doubler)
# ──────────────────────────────────────────────────────────────────────

_ORIG_ALREADY = (
    "_already_open = (\n"
    "            sum(1 for p in positions if p.strategy == rec.strategy) >= IC_HV_MAX_CONCURRENT\n"
    "            if rec.strategy == StrategyName.IRON_CONDOR_HV\n"
    "            else any(p.strategy == rec.strategy for p in positions)\n"
    "        )"
)
_ORIG_BP_TARGET_LINE = "_new_bp_target = params.bp_target_for_regime(regime)"
_ORIG_BP_TARGET_USAGE = "bp_target=params.bp_target_for_regime(regime),"


def _patched_run(double_predicate_fn_name: str, multiplier: float, helpers: dict):
    """Patch run_backtest with overlay block + idle-BP-aware doubler."""
    src = inspect.getsource(engine_mod.run_backtest)

    if _ORIG_ALREADY not in src:
        raise RuntimeError("Expected _already_open block not found")
    new_already = (
        f"_already_open = (_overlay_block(positions, rec, str(date.date()), _q036_cluster_map) "
        f"if rec.strategy == StrategyName.IRON_CONDOR_HV "
        f"else any(p.strategy == rec.strategy for p in positions))"
    )
    src = src.replace(_ORIG_ALREADY, new_already)

    if _ORIG_BP_TARGET_LINE not in src:
        raise RuntimeError("Expected _new_bp_target line not found")
    if _ORIG_BP_TARGET_USAGE not in src:
        raise RuntimeError("Expected bp_target= usage not found")
    new_target = (
        f"_new_bp_target = (params.bp_target_for_regime(regime) * {multiplier} "
        f"if {double_predicate_fn_name}(positions, rec, str(date.date()), _q036_cluster_map, _used_bp) "
        f"else params.bp_target_for_regime(regime))"
    )
    src = src.replace(_ORIG_BP_TARGET_LINE, new_target)
    src = src.replace(_ORIG_BP_TARGET_USAGE, "bp_target=_new_bp_target,")

    ns = dict(engine_mod.__dict__)
    ns["_q036_cluster_map"] = _CLUSTER_MAP
    ns["_overlay_block"] = _overlay_block
    ns.update(helpers)
    exec(src, ns)
    return ns["run_backtest"]


def _build_baseline():
    return run_backtest


def _build_overlay_a():
    return _patched_run("_overlay_a_double", 1.5,
                        {"_overlay_a_double": _overlay_a_double})


def _build_overlay_b():
    return _patched_run("_overlay_b_double", 2.0,
                        {"_overlay_b_double": _overlay_b_double})


def _build_overlay_c():
    return _patched_run("_overlay_c_double", 2.0,
                        {"_overlay_c_double": _overlay_c_double})


# ──────────────────────────────────────────────────────────────────────
# Stats helpers
# ──────────────────────────────────────────────────────────────────────

def _closed(trades):
    return [t for t in trades if t.exit_reason != "end_of_backtest"]


def _stats(trades):
    if not trades:
        return {"n": 0, "mean": 0, "total": 0, "win%": 0.0, "sharpe": 0.0}
    p = np.array([t.exit_pnl for t in trades])
    n = len(p)
    mu = float(p.mean())
    sd = float(p.std(ddof=1)) if n > 1 else 0.0
    return {"n": n, "mean": round(mu), "total": int(p.sum()),
            "win%": round((p > 0).mean() * 100, 1),
            "sharpe": round(mu / sd, 2) if sd > 0 else 0.0}


def _max_dd(trades):
    if not trades:
        return 0.0
    ts = sorted(trades, key=lambda t: t.exit_date)
    cum = np.cumsum([t.exit_pnl for t in ts])
    peak = np.maximum.accumulate(cum)
    return float((cum - peak).min())


def _ic_hv(trades):
    return [t for t in trades if t.strategy.value == StrategyName.IRON_CONDOR_HV.value]


def _non_ic_hv(trades):
    return [t for t in trades if t.strategy.value != StrategyName.IRON_CONDOR_HV.value]


def _slice(trades, lo, hi=None):
    if hi is None:
        return [t for t in trades if t.entry_date >= lo]
    return [t for t in trades if lo <= t.entry_date <= hi]


def _date_diff(a: str, b: str) -> int:
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def _bp_days(trades) -> float:
    s = 0.0
    for t in trades:
        held = max(0, _date_diff(t.exit_date, t.entry_date))
        s += float(t.bp_pct_account) * held
    return s


def _worst_trade(trades) -> float:
    return min((t.exit_pnl for t in trades), default=0.0)


def _cvar_5pct(trades) -> float:
    if not trades:
        return 0.0
    pnls = sorted(t.exit_pnl for t in trades)
    cutoff = max(1, int(len(pnls) * 0.05))
    return float(np.mean(pnls[:cutoff]))


def _is_boosted_aftermath_first(t, cluster_map, multiplier=1.5) -> bool:
    if t.strategy.value != StrategyName.IRON_CONDOR_HV.value:
        return False
    if cluster_map.get(t.entry_date) is None:
        return False
    return float(t.bp_pct_account) > multiplier * HV_NORMAL_BP_PCT


def _max_ic_hv_bp_pct(trades) -> tuple[float, str]:
    events = []
    for t in _ic_hv(trades):
        events.append((t.entry_date, +1, float(t.bp_pct_account)))
        events.append((t.exit_date, -1, float(t.bp_pct_account)))
    events.sort(key=lambda e: (e[0], 0 if e[1] == -1 else 1))
    cur = 0.0
    peak = 0.0
    peak_date = ""
    for d, sign, bp in events:
        cur += sign * bp
        if cur > peak:
            peak = cur
            peak_date = d
    return peak, peak_date


def _concurrent_2x_event_days(trades, cluster_map, multiplier_threshold=1.5) -> int:
    flagged = [t for t in _ic_hv(trades)
               if _is_boosted_aftermath_first(t, cluster_map, multiplier_threshold)]
    events = []
    for t in flagged:
        events.append((t.entry_date, +1))
        events.append((t.exit_date, -1))
    events.sort(key=lambda e: (e[0], 0 if e[1] == -1 else 1))
    days = set()
    cur = 0
    for d, sign in events:
        cur += sign
        if cur >= 2:
            days.add(d)
    return len(days)


def _annual_pnl_proportion(trades, account_size) -> tuple[dict[int, float], int, int]:
    """Return (per-year PnL dict, n_pos_years, total_years)."""
    by_year: dict[int, float] = defaultdict(float)
    for t in trades:
        y = int(t.exit_date[:4])
        by_year[y] += t.exit_pnl
    if not by_year:
        return {}, 0, 0
    pos = sum(1 for v in by_year.values() if v > 0)
    return dict(sorted(by_year.items())), pos, len(by_year)


def _account_level_pack(trades, account_size, years_span) -> dict:
    s = _stats(trades)
    total_pnl = s["total"]
    roe = total_pnl / account_size
    ann_roe_simple = roe / years_span if years_span > 0 else 0.0
    by_year, n_pos, n_total = _annual_pnl_proportion(trades, account_size)
    return {
        "total_pnl": total_pnl,
        "roe": roe,
        "ann_roe_simple": ann_roe_simple,
        "pos_years": n_pos,
        "total_years": n_total,
        "by_year": by_year,
    }


def _peak_system_bp_pct(rows) -> tuple[float, str]:
    """Peak BP% of account observed in daily portfolio rows."""
    peak = 0.0
    peak_date = ""
    for r in rows:
        bp_pct = (r.bp_used / ACCOUNT_SIZE) * 100
        if bp_pct > peak:
            peak = bp_pct
            peak_date = r.date
    return peak, peak_date


def _disaster_window_max_bp(rows, lo, hi) -> tuple[float, str]:
    peak = 0.0
    peak_date = ""
    for r in rows:
        if lo <= r.date <= hi:
            bp_pct = (r.bp_used / ACCOUNT_SIZE) * 100
            if bp_pct > peak:
                peak = bp_pct
                peak_date = r.date
    return peak, peak_date


def _forced_liq_proxy(rows, lo, hi, drawdown_threshold=-0.05) -> tuple[float, str]:
    """Simple forced-liquidation proxy: peak (BP_pct × |drawdown|) within window."""
    peak = 0.0
    peak_date = ""
    for r in rows:
        if lo <= r.date <= hi:
            bp_pct = r.bp_used / ACCOUNT_SIZE
            stress = bp_pct * abs(r.drawdown)
            if stress > peak:
                peak = stress
                peak_date = r.date
    return peak, peak_date


def _short_gamma_at_dates(rows_by_date, dates) -> list[int]:
    """Return short_gamma_count for each date (ignores misses)."""
    out = []
    for d in dates:
        r = rows_by_date.get(d)
        if r is not None:
            out.append(int(r.short_gamma_count))
    return out


def _idle_bp_at_dates(rows_by_date, dates) -> list[float]:
    out = []
    for d in dates:
        r = rows_by_date.get(d)
        if r is not None:
            idle = (ACCOUNT_SIZE - r.bp_used) / ACCOUNT_SIZE
            out.append(float(idle))
    return out


# ──────────────────────────────────────────────────────────────────────
# Run wrapper that returns trades + portfolio rows
# ──────────────────────────────────────────────────────────────────────

def _run_full(run_fn, off_peak):
    orig = sel.AFTERMATH_OFF_PEAK_PCT
    sel.AFTERMATH_OFF_PEAK_PCT = off_peak
    try:
        result = run_fn(start_date=START, verbose=False)
    finally:
        sel.AFTERMATH_OFF_PEAK_PCT = orig
    closed = _closed(result.trades)
    return closed, result.portfolio_rows


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def run_study():
    global _CLUSTER_MAP, _VIX_BY_DATE
    print("Q036 Phase 2 — Idle-BP-conditional overlay pilots")
    print()

    print("  Building VIX cluster map + series ...")
    _CLUSTER_MAP, _VIX_BY_DATE = build_cluster_map_and_vix()
    n_after = sum(1 for v in _CLUSTER_MAP.values() if v is not None)
    n_clusters = len(set(v for v in _CLUSTER_MAP.values() if v is not None))
    print(f"    {n_after} aftermath days across {n_clusters} clusters")
    print()

    variants = [
        ("V_baseline",       _build_baseline,   1.0),
        ("Overlay-A_1.5x",   _build_overlay_a,  1.5),
        ("Overlay-B_2x_disc",_build_overlay_b,  2.0),
        ("Overlay-C_2x_noov",_build_overlay_c,  2.0),
    ]

    results: dict[str, list[Trade]] = {}
    rows_by_var: dict[str, list] = {}
    for name, builder, _ in variants:
        print(f"  Running {name} ...")
        run_fn = builder()
        results[name], rows_by_var[name] = _run_full(run_fn, OFF_PEAK_B)

    base = "V_baseline"
    base_pnl = _stats(results[base])["total"]
    base_bp_days = _bp_days(results[base])

    # Years span
    all_years = sorted({int(t.exit_date[:4]) for t in results[base]})
    years_span = (all_years[-1] - all_years[0] + 1) if all_years else 1

    # ── §1 Account-level scoreboard ───────────────────────────────────
    print()
    print("=" * 120)
    print("  §1 ACCOUNT-LEVEL SCOREBOARD (Q036 top-line metric)")
    print("=" * 120)
    print(f"  Account size: ${ACCOUNT_SIZE:,.0f}   Years observed: {years_span}")
    print()
    print(f"  {'Variant':<22} {'Total PnL':>12} {'ROE':>8} {'AnnROE(simple)':>16} "
          f"{'+yrs/total':>12} {'Δ PnL vs base':>15}")
    pack_by_var = {}
    for name, _, _ in variants:
        pack = _account_level_pack(results[name], ACCOUNT_SIZE, years_span)
        pack_by_var[name] = pack
        roe_pct = pack["roe"] * 100
        ann_pct = pack["ann_roe_simple"] * 100
        d_pnl = pack["total_pnl"] - base_pnl
        ds = f"{d_pnl:+,}" if name != base else "—"
        print(f"  {name:<22} {pack['total_pnl']:>+12,} {roe_pct:>+7.1f}% "
              f"{ann_pct:>+15.2f}% {pack['pos_years']:>4}/{pack['total_years']:<5}  {ds:>15}")

    # ── §2 Tail / risk pack ───────────────────────────────────────────
    print()
    print("=" * 120)
    print("  §2 TAIL / RISK PACK (account-level)")
    print("=" * 120)
    print(f"  {'Variant':<22} {'MaxDD':>10} {'CVaR5%(all)':>13} "
          f"{'PeakSysBP%':>12} {'Δ MaxDD':>11}")
    base_dd = _max_dd(results[base])
    for name, _, _ in variants:
        ts = results[name]
        dd = _max_dd(ts)
        cvar_all = _cvar_5pct(ts)  # account-level CVaR (all trades)
        peak_bp, peak_dt = _peak_system_bp_pct(rows_by_var[name])
        d_dd = dd - base_dd
        ds = f"{d_dd:+,.0f}" if name != base else "—"
        print(f"  {name:<22} {dd:>+10,.0f} {cvar_all:>+13,.0f} "
              f"{peak_bp:>11.1f}% {ds:>11}")
    print()
    print("  Disaster windows (IC_HV trades + max system BP% during window):")
    print(f"  {'Variant':<22} {'Window':<14} {'IC_HV n':>8} {'IC_HV net':>11} "
          f"{'MaxSysBP%':>11} {'ForcedLiq*':>11}")
    windows = [
        ("2008 GFC",    "2008-09-01", "2008-12-31"),
        ("2020 COVID",  "2020-02-20", "2020-04-30"),
        ("2025 Tariff", "2025-04-01", "2025-05-31"),
    ]
    for name, _, _ in variants:
        ic = _ic_hv(results[name])
        rows = rows_by_var[name]
        for label, lo, hi in windows:
            dis = [t for t in ic if lo <= t.entry_date <= hi]
            n = len(dis)
            net = sum(t.exit_pnl for t in dis)
            max_bp, _ = _disaster_window_max_bp(rows, lo, hi)
            fl, _ = _forced_liq_proxy(rows, lo, hi)
            print(f"  {name:<22} {label:<14} {n:>8} {net:>+11,.0f} "
                  f"{max_bp:>10.1f}% {fl:>11.4f}")
    print("  *ForcedLiq proxy = max(BP_fraction × |drawdown|) within window. Higher = more stress.")

    # ── §3 Capital-allocation pack ────────────────────────────────────
    print()
    print("=" * 120)
    print("  §3 CAPITAL-ALLOCATION PACK (Q036 specific)")
    print("=" * 120)
    print("  Idle-BP utilization rate (overlay-deployed BP-days / total available idle BP-days)")
    print("  and short-gamma stacking actualized at overlay trigger moments.")
    print()
    base_rows = rows_by_var[base]
    # Total idle BP-days available under baseline (account-day count × idle fraction)
    total_baseline_idle_bp_days = sum(
        (ACCOUNT_SIZE - r.bp_used) / ACCOUNT_SIZE * 100  # idle pct-points × 1 day
        for r in base_rows
    )
    print(f"  Baseline total idle BP-day budget: ~{total_baseline_idle_bp_days:,.0f} pct-day units")
    print()
    print(f"  {'Variant':<22} {'+BPdays':>10} {'IdleUtil%':>11} {'#OverlayFires':>14} "
          f"{'OvlSGmean':>11} {'Ovl#≥2':>9} {'CrowdOut':>10}")
    base_non_pnl = _stats(_non_ic_hv(results[base]))['total']
    for name, mult_label, mult in variants:
        if name == base:
            print(f"  {name:<22} {'—':>10} {'—':>11} {'—':>14} {'—':>11} {'—':>9} {'—':>10}")
            continue
        ts = results[name]
        rows = rows_by_var[name]
        rows_by_date = {r.date: r for r in rows}
        bpd_extra = _bp_days(ts) - base_bp_days
        util_pct = (bpd_extra / total_baseline_idle_bp_days * 100) if total_baseline_idle_bp_days else 0.0

        # Overlay fires = boosted aftermath first entries (bp_pct > 1.05 × normal)
        ovl_fires = [t for t in _ic_hv(ts)
                     if _is_boosted_aftermath_first(t, _CLUSTER_MAP, 1.05)]
        ovl_dates = [t.entry_date for t in ovl_fires]
        sg_at_fires = _short_gamma_at_dates(rows_by_date, ovl_dates)
        # short_gamma at fire moment INCLUDES the new overlay position itself in the snapshot
        # (portfolio_rows is computed end-of-day). Subtract 1 to express "stacking before this fire".
        sg_pre = [max(0, c - 1) for c in sg_at_fires]
        sg_mean = float(np.mean(sg_pre)) if sg_pre else 0.0
        sg_stack_pct = (sum(1 for c in sg_pre if c >= 2) / len(sg_pre) * 100) if sg_pre else 0.0

        # Crowd-out: did non-IC_HV PnL change vs baseline?
        non_pnl = _stats(_non_ic_hv(ts))['total']
        crowd = "OK" if abs(non_pnl - base_non_pnl) < 1 else f"Δ${non_pnl - base_non_pnl:+,.0f}"
        print(f"  {name:<22} {bpd_extra:>+10,.0f} {util_pct:>10.2f}% {len(ovl_fires):>14} "
              f"{sg_mean:>11.2f} {sg_stack_pct:>8.0f}% {crowd:>10}")
    print()
    print("  Interpretation:")
    print("    +BPdays    = extra BP-days deployed by overlay (positive only)")
    print("    IdleUtil%  = of TOTAL baseline idle BP-day budget, what fraction overlay consumed")
    print("    Ovl#≥2    = % of overlay fires where account already carried ≥ 2 short-gamma BEFORE overlay added")
    print("    CrowdOut   = non-IC_HV PnL delta vs baseline; OK = exact match (no portfolio interaction)")

    # ── §4 Standard Phase-4 metrics pack ──────────────────────────────
    print()
    print("=" * 120)
    print("  §4 STANDARD METRICS PACK (Phase-4 standing rule)")
    print("=" * 120)
    base_pnl_per_bpd = base_pnl / base_bp_days if base_bp_days > 0 else 0.0
    print(f"  V_baseline PnL/BP-day = {base_pnl_per_bpd:+.4f}  (the rule-layer threshold)")
    print(f"  Idle baseline marginal $/BP-day = $0.0000  (the capital-allocation threshold)")
    print()
    print(f"  {'Variant':<22} {'PnL/BPd':>9} {'Marg vs A':>11} {'Marg vs idle':>13} "
          f"{'Worst':>10} {'IC_HV CVaR5%':>13} {'MaxBP%':>9} {'#2× ovl':>9}")
    for name, _, mult in variants:
        ts = results[name]
        bp_d = _bp_days(ts)
        per = _stats(ts)['total'] / bp_d if bp_d > 0 else 0.0
        if name == base:
            marg_a = "—"
            marg_idle = "—"
        else:
            d_pnl = _stats(ts)['total'] - base_pnl
            d_bp = bp_d - base_bp_days
            if abs(d_bp) > 1e-6:
                m_a = d_pnl / d_bp
                marg_a = f"{m_a:+.4f}"
                # vs idle: same incremental dollar / same incremental BP — but threshold is $0
                marg_idle = f"{m_a:+.4f}"
            else:
                marg_a = "n/a"
                marg_idle = "n/a"
        worst = _worst_trade(ts)
        cvar_ic = _cvar_5pct(_ic_hv(ts))
        max_bp_pct, _ = _max_ic_hv_bp_pct(ts)
        if mult > 1.0:
            n_2x_ovl = _concurrent_2x_event_days(ts, _CLUSTER_MAP, multiplier_threshold=mult * 0.9)
        else:
            n_2x_ovl = 0
        print(f"  {name:<22} {per:>+9.4f} {marg_a:>11} {marg_idle:>13} "
              f"{worst:>+10,.0f} {cvar_ic:>+13,.0f} {max_bp_pct:>8.1f}% {n_2x_ovl:>9}")
    print()
    print("  Marg vs A    = (PnL_v − PnL_base) / (BPdays_v − BPdays_base) — rule-layer threshold V_A")
    print("  Marg vs idle = same numerator/denominator but compared to $0/BP-day idle baseline")
    print("                 (Q036 binding threshold: positive marginal vs idle = overlay is value-additive)")

    # ── §5 IC_HV vs non-IC_HV ─────────────────────────────────────────
    print()
    print("=" * 120)
    print("  §5 IC_HV vs NON-IC_HV DECOMPOSITION (Q036 crowd-out test)")
    print("=" * 120)
    print(f"  {'Variant':<22} {'IC_HV n':>8} {'IC_HV PnL':>13} "
          f"{'nonIC n':>8} {'nonIC PnL':>13} {'Σ check':>13}")
    for name, _, _ in variants:
        ic = _stats(_ic_hv(results[name]))
        non = _stats(_non_ic_hv(results[name]))
        sigma = ic['total'] + non['total']
        print(f"  {name:<22} {ic['n']:>8} {ic['total']:>+13,} "
              f"{non['n']:>8} {non['total']:>+13,} {sigma:>+13,}")

    # ── §6 2026-03 sanity ─────────────────────────────────────────────
    print()
    print("=" * 120)
    print("  §6 2026-03 DOUBLE-PEAK SANITY")
    print("=" * 120)
    for name, _, _ in variants:
        ic = _ic_hv(results[name])
        q2 = [t for t in ic if "2026-03-01" <= t.entry_date <= "2026-04-15"]
        if not q2:
            print(f"  {name:<22} —")
            continue
        net = sum(t.exit_pnl for t in q2)
        print(f"  {name:<22} {len(q2)} trades, net ${net:+,.0f}")
        for t in q2:
            cid = _CLUSTER_MAP.get(t.entry_date) or "non_after"
            print(f"    {t.entry_date}[{cid}] contracts={t.contracts:.2f} "
                  f"bp%={t.bp_pct_account:.2f} pnl=${t.exit_pnl:+,.0f}")

    # ── §7 Cluster coverage ───────────────────────────────────────────
    print()
    print("=" * 120)
    print("  §7 CLUSTER COVERAGE (IC_HV aftermath only)")
    print("=" * 120)
    print(f"  {'Variant':<22} {'#after_trades':>14} {'#clusters_hit':>14} "
          f"{'#multi':>8} {'avg/hit':>10}")
    for name, _, _ in variants:
        ic_after = [t for t in _ic_hv(results[name])
                    if _CLUSTER_MAP.get(t.entry_date) is not None]
        by_cl: dict[str, int] = {}
        for t in ic_after:
            cid = _CLUSTER_MAP[t.entry_date]
            by_cl[cid] = by_cl.get(cid, 0) + 1
        n_hit = len(by_cl)
        n_multi = sum(1 for v in by_cl.values() if v > 1)
        avg = (sum(by_cl.values()) / n_hit) if n_hit else 0
        print(f"  {name:<22} {len(ic_after):>14} {n_hit:>14} {n_multi:>8} {avg:>10.2f}")

    # ── §8 Recent slice 2018+ ─────────────────────────────────────────
    print()
    print("=" * 120)
    print(f"  §8 RECENT SLICE ({RECENT_SLICE_START}+) — account level + standard pack")
    print("=" * 120)
    recent_pnl_base = _stats(_slice(results[base], RECENT_SLICE_START))['total']
    recent_bp_base = _bp_days(_slice(results[base], RECENT_SLICE_START))
    recent_years = years_span - (int(RECENT_SLICE_START[:4]) - all_years[0]) if all_years else 1
    print(f"  Recent years observed: {recent_years}")
    print()
    print(f"  {'Variant':<22} {'Total PnL':>12} {'AnnROE%':>9} {'PnL/BPd':>9} "
          f"{'Marg vs A':>11} {'IC_HV CVaR5%':>13} {'MaxDD':>10}")
    for name, _, _ in variants:
        ts = _slice(results[name], RECENT_SLICE_START)
        s = _stats(ts)
        bp_d = _bp_days(ts)
        per = s['total'] / bp_d if bp_d > 0 else 0.0
        if name == base:
            marg = "—"
        else:
            d_pnl = s['total'] - recent_pnl_base
            d_bp = bp_d - recent_bp_base
            marg = f"{d_pnl/d_bp:+.4f}" if abs(d_bp) > 1e-6 else "n/a"
        ann_pct = (s['total'] / ACCOUNT_SIZE / recent_years * 100) if recent_years > 0 else 0.0
        cvar_ic = _cvar_5pct(_ic_hv(ts))
        dd = _max_dd(ts)
        print(f"  {name:<22} {s['total']:>+12,} {ann_pct:>+8.2f}% {per:>+9.4f} "
              f"{marg:>11} {cvar_ic:>+13,.0f} {dd:>+10,.0f}")

    # ── §9 Verdict scaffold ──────────────────────────────────────────
    print()
    print("=" * 120)
    print("  §9 VERDICT SCAFFOLD")
    print("=" * 120)
    print("  Read order:")
    print("    §1 Account-level Δ ROE          → Q036 top-line: does overlay improve account ROE?")
    print("    §2 ΔMaxDD, peak BP%, fl proxy   → Q036 tail cost: is the tail cost acceptable?")
    print("    §3 IdleUtil%, Ovl#≥2, CrowdOut  → Q036 capital-allocation governance:")
    print("                                       overlay should USE idle BP without stacking risk")
    print("    §4 Marg vs idle ($0)            → Q036 binding threshold: must be > $0/BP-day")
    print("    §4 Marg vs A ($4.85)            → rule-layer reference (NOT the Q036 threshold)")
    print()
    print("  Decision rules:")
    print("    DROP if:    no variant has positive ann ROE delta vs baseline")
    print("                OR every variant has Ovl#≥2 ≥ 50% (stacking unmanaged)")
    print("                OR Marg vs idle ≤ 0 across all variants")
    print("    CONTINUE:   ≥ 1 variant has +ann ROE AND tail cost manageable AND stacking < 50%")
    print("    DRAFT SPEC: 1 variant clearly dominates on (ROE delta, tail delta, stacking control)")
    print("                AND incremental ROE / incremental MaxDD is favorable")


if __name__ == "__main__":
    run_study()
