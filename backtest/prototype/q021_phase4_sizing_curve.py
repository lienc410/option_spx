"""
Q021 Phase 4 — Aftermath first-entry sizing curve study.

Per 2nd Quant 2nd-round review (`task/q021_2nd_quant_review_handoff_2.md`):

  V_D (2× first) is promising but not directly approvable. Reviewer points out
  V_D's incremental capital efficiency ($3.37/BP-day) is 30% below V_A baseline
  ($4.85/BP-day), suggesting leverage rather than smarter selection. He requests
  a targeted sizing-risk study to answer:

    "aftermath first-entry 的最佳风险集中方式是什么？"

PM (2026-04-25): selected option 2 — Phase 4 incl. V_E + V_H + V_G; standing
rule for all future strategy comparisons: include the full metrics pack
(marginal $/BP-day, worst trade, max BP%, concurrent 2× days, CVaR 5%).

Variants:
  V_A  SPEC-066 baseline                                  (cap=2 same-cluster)
  V_D  2× first, distinct cluster also 2×                 (Phase 3 hypothesis)
  V_E  1.5× first, distinct cluster also 1.5×             (sizing curve check)
  V_J  2× first, but distinct cluster only 1× if 2× open  (no overlap leverage)
  V_H  cap=2 same-cluster, 2nd entry only if VIX hasn't bounced  (split-entry gate)
  V_G  2× first with VIX disaster cap (VIX ≥ 35 → 1×)     (tail control)

Metrics pack (per standing rule, all variants):
  - PnL / Sharpe / MaxDD / n
  - PnL/BP-day                         (capital efficiency)
  - Marginal PnL/BP-day vs V_A         (leverage vs edge)
  - Worst single trade
  - Disaster window net (per event)
  - Max IC_HV BP% (running max across event days)
  - Max concurrent 2× IC_HV (count of days with ≥ 2 simultaneous 2× positions)
  - IC_HV CVaR 5%

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q021_phase4_sizing_curve
"""

from __future__ import annotations

import inspect
import pickle
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
DISASTER_VIX_THRESHOLD = 30.0  # 2026-04-26: lowered from 35 (no aftermath first entries had VIX ≥ 35; threshold was inert)
HV_NORMAL_BP = 0.07       # bp_target_high_vol (fraction)
HV_NORMAL_BP_PCT = 7.0    # same in percentage scale (engine stores bp_pct_account × 100)


# ──────────────────────────────────────────────────────────────────────
# Cluster map + VIX series (Phase 3 reuse)
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


# Globals patched into engine namespace at exec
_CLUSTER_MAP: dict[str, str | None] = {}
_VIX_BY_DATE: dict[str, float] = {}


# ──────────────────────────────────────────────────────────────────────
# Block / double helpers (one set per variant)
# ──────────────────────────────────────────────────────────────────────

def _same_cluster_open_ic_hv(positions, cur_cluster, cluster_map):
    if cur_cluster is None:
        return []
    return [p for p in positions
            if p.strategy == StrategyName.IRON_CONDOR_HV
            and cluster_map.get(p.entry_date) == cur_cluster]


def _q021_vd_block(positions, rec, date_str, cluster_map):
    """V_D / V_E / V_J / V_G block: aftermath same-cluster 2nd → BLOCK; non-aftermath → cap=2."""
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return any(p.strategy == rec.strategy for p in positions)
    same_strat = [p for p in positions if p.strategy == rec.strategy]
    cur = cluster_map.get(date_str)
    if cur is None:
        return len(same_strat) >= 2
    return bool(_same_cluster_open_ic_hv(positions, cur, cluster_map))


def _q021_d_or_e_double(positions, rec, date_str, cluster_map):
    """V_D and V_E doubler: aftermath AND no same-cluster IC_HV currently open.

    V_E uses the same predicate but with multiplier 1.5 in the patched line.
    """
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return False
    cur = cluster_map.get(date_str)
    if cur is None:
        return False
    return not _same_cluster_open_ic_hv(positions, cur, cluster_map)


def _q021_vj_double(positions, rec, date_str, cluster_map):
    """V_J doubler: aftermath AND NO IC_HV currently open at all (any cluster)."""
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return False
    cur = cluster_map.get(date_str)
    if cur is None:
        return False
    n_ic_hv_open = sum(1 for p in positions if p.strategy == StrategyName.IRON_CONDOR_HV)
    return n_ic_hv_open == 0


def _q021_vg_double(positions, rec, date_str, cluster_map):
    """V_G doubler: V_D condition AND today's VIX < disaster threshold."""
    if not _q021_d_or_e_double(positions, rec, date_str, cluster_map):
        return False
    vix_today = _VIX_BY_DATE.get(date_str)
    if vix_today is None:
        return True  # missing VIX → still allow 2× (rare)
    return vix_today < DISASTER_VIX_THRESHOLD


def _q021_vh_block(positions, rec, date_str, cluster_map):
    """V_H block: V_A SPEC-066 cap=2 + VIX-no-bounce gate on same-cluster 2nd entry.

    Intended semantics: behave exactly like V_A (cap=2 across all IC_HV regardless
    of cluster) EXCEPT add an extra gate that blocks same-cluster 2nd entry if
    VIX has bounced above the first entry's VIX. This implements 2nd Quant's
    "split-entry" idea: scale-in only when market hasn't deteriorated.

    Logic:
      - non-IC_HV: any existing → block (engine baseline)
      - IC_HV: enforce baseline cap=2 first
      - IC_HV aftermath with same-cluster open: extra VIX-bounce check
    """
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return any(p.strategy == rec.strategy for p in positions)
    same_strat = [p for p in positions if p.strategy == rec.strategy]
    # Baseline cap=2 (matches engine and V_A)
    if len(same_strat) >= 2:
        return True
    cur = cluster_map.get(date_str)
    if cur is None:
        return False  # non-aftermath, under cap → allow
    same_cluster = _same_cluster_open_ic_hv(positions, cur, cluster_map)
    if not same_cluster:
        return False  # distinct cluster (or first in this cluster) → allow as V_A
    # Same-cluster 2nd entry candidate: apply VIX-no-bounce gate
    vix_today = _VIX_BY_DATE.get(date_str)
    if vix_today is None:
        return True
    for p in same_cluster:
        vix_first = _VIX_BY_DATE.get(p.entry_date)
        if vix_first is not None and vix_today > vix_first:
            return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Variant builders (engine.run_backtest patched per variant)
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


def _patched_run(block_predicate_fn_name: str | None,
                 double_predicate_fn_name: str | None,
                 multiplier: float,
                 helpers: dict):
    """Generic patcher.

    block_predicate_fn_name: name of bool fn(positions, rec, date_str, cluster_map)
                             returning True to BLOCK entry. None → use engine baseline cap.
    double_predicate_fn_name: name of bool fn(positions, rec, date_str, cluster_map)
                              returning True to apply size multiplier. None → no multiplier patch.
    multiplier: size multiplier applied when doubler returns True.
    helpers: extra names to inject into exec namespace.
    """
    src = inspect.getsource(engine_mod.run_backtest)

    if block_predicate_fn_name is not None:
        if _ORIG_ALREADY not in src:
            raise RuntimeError("Expected _already_open block not found")
        new_already = (
            f"_already_open = ({block_predicate_fn_name}(positions, rec, str(date.date()), _q021_cluster_map) "
            f"if rec.strategy == StrategyName.IRON_CONDOR_HV "
            f"else any(p.strategy == rec.strategy for p in positions))"
        )
        src = src.replace(_ORIG_ALREADY, new_already)

    if double_predicate_fn_name is not None:
        if _ORIG_BP_TARGET_LINE not in src:
            raise RuntimeError("Expected _new_bp_target line not found")
        if _ORIG_BP_TARGET_USAGE not in src:
            raise RuntimeError("Expected bp_target= usage not found")
        new_target = (
            f"_new_bp_target = (params.bp_target_for_regime(regime) * {multiplier} "
            f"if {double_predicate_fn_name}(positions, rec, str(date.date()), _q021_cluster_map) "
            f"else params.bp_target_for_regime(regime))"
        )
        src = src.replace(_ORIG_BP_TARGET_LINE, new_target)
        src = src.replace(_ORIG_BP_TARGET_USAGE, "bp_target=_new_bp_target,")

    ns = dict(engine_mod.__dict__)
    ns["_q021_cluster_map"] = _CLUSTER_MAP
    ns.update(helpers)
    exec(src, ns)
    return ns["run_backtest"]


def _build_variant_A():
    return run_backtest


def _build_variant_D():
    return _patched_run(
        "_q021_vd_block", "_q021_d_or_e_double", 2.0,
        {"_q021_vd_block": _q021_vd_block,
         "_q021_d_or_e_double": _q021_d_or_e_double},
    )


def _build_variant_E():
    return _patched_run(
        "_q021_vd_block", "_q021_d_or_e_double", 1.5,
        {"_q021_vd_block": _q021_vd_block,
         "_q021_d_or_e_double": _q021_d_or_e_double},
    )


def _build_variant_J():
    return _patched_run(
        "_q021_vd_block", "_q021_vj_double", 2.0,
        {"_q021_vd_block": _q021_vd_block,
         "_q021_vj_double": _q021_vj_double},
    )


def _build_variant_H():
    return _patched_run(
        "_q021_vh_block", None, 1.0,
        {"_q021_vh_block": _q021_vh_block},
    )


def _build_variant_G():
    return _patched_run(
        "_q021_vd_block", "_q021_vg_double", 2.0,
        {"_q021_vd_block": _q021_vd_block,
         "_q021_vg_double": _q021_vg_double},
    )


# ──────────────────────────────────────────────────────────────────────
# Helpers: stats and metrics pack
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


def _is_2x_aftermath_first(t, cluster_map, multiplier=1.5) -> bool:
    """Reconstruct whether this trade was opened at boosted size by a V_D/V_E/V_J/V_G doubler.

    bp_pct_account is stored in percentage scale (engine: total_bp/account_size*100).
    1× trade ~7.0; 1.5× ~10.5; 2× ~14.0. Threshold uses HV_NORMAL_BP_PCT (7.0).
    """
    if t.strategy.value != StrategyName.IRON_CONDOR_HV.value:
        return False
    if cluster_map.get(t.entry_date) is None:
        return False
    return float(t.bp_pct_account) > multiplier * HV_NORMAL_BP_PCT


def _max_ic_hv_bp_pct(trades) -> tuple[float, str]:
    """Running max of summed bp_pct_account across simultaneously-open IC_HV positions.

    Returns (max_pct, date_when_reached).
    """
    events = []
    for t in _ic_hv(trades):
        events.append((t.entry_date, +1, float(t.bp_pct_account)))
        events.append((t.exit_date, -1, float(t.bp_pct_account)))
    # Sort: same date — apply exits before entries to avoid double-counting transitions
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
    """Count event-days where ≥ 2 IC_HV positions opened at boosted size are simultaneously open.

    Walks entry/exit events of trades flagged as boosted; counts unique dates
    where the running concurrent-boosted-count is ≥ 2.
    """
    flagged = [t for t in _ic_hv(trades)
               if _is_2x_aftermath_first(t, cluster_map, multiplier_threshold)]
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


def _run(run_fn, off_peak):
    orig = sel.AFTERMATH_OFF_PEAK_PCT
    sel.AFTERMATH_OFF_PEAK_PCT = off_peak
    try:
        return _closed(run_fn(start_date=START, verbose=False).trades)
    finally:
        sel.AFTERMATH_OFF_PEAK_PCT = orig


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def run_study():
    global _CLUSTER_MAP, _VIX_BY_DATE
    print("Q021 Phase 4 — Aftermath first-entry sizing curve study")
    print()

    print("  Building VIX cluster map + series ...")
    _CLUSTER_MAP, _VIX_BY_DATE = build_cluster_map_and_vix()
    n_after = sum(1 for v in _CLUSTER_MAP.values() if v is not None)
    n_clusters = len(set(v for v in _CLUSTER_MAP.values() if v is not None))
    print(f"    {n_after} aftermath days across {n_clusters} clusters")
    print()

    variants = [
        ("V_A_spec066",     _build_variant_A, 1.0),
        ("V_D_2x_first",    _build_variant_D, 2.0),
        ("V_E_1.5x_first",  _build_variant_E, 1.5),
        ("V_J_2x_no_overlap", _build_variant_J, 2.0),
        ("V_H_split_entry", _build_variant_H, 1.0),
        ("V_G_2x_disaster_cap", _build_variant_G, 2.0),
    ]

    results: dict[str, list[Trade]] = {}
    for name, builder, _ in variants:
        print(f"  Running {name} ...")
        run_fn = builder()
        results[name] = _run(run_fn, OFF_PEAK_B)

    base = "V_A_spec066"
    base_pnl = _stats(results[base])["total"]
    base_bp_days = _bp_days(results[base])

    # ── 1. SYSTEM-LEVEL FULL SAMPLE ───────────────────────────────────
    print()
    print("=" * 120)
    print("  1. SYSTEM-LEVEL — FULL SAMPLE")
    print("=" * 120)
    print(f"  {'Variant':<22} {'n':>4} {'Total PnL':>13} {'Sharpe':>8} {'MaxDD':>10} {'Δ vs V_A':>12}")
    for name, _, _ in variants:
        s = _stats(results[name])
        dd = _max_dd(results[name])
        delta = s['total'] - base_pnl
        ds = f"{delta:+,}" if name != base else "—"
        print(f"  {name:<22} {s['n']:>4} {s['total']:>+13,} {s['sharpe']:>+8.2f} "
              f"{dd:>+10,.0f} {ds:>12}")

    # ── 2. RECENT SLICE 2018+ ─────────────────────────────────────────
    print()
    print("=" * 120)
    print(f"  2. SYSTEM-LEVEL — RECENT SLICE (entry_date ≥ {RECENT_SLICE_START})")
    print("=" * 120)
    print(f"  {'Variant':<22} {'n':>4} {'Total PnL':>13} {'Sharpe':>8} {'MaxDD':>10} {'Δ vs V_A':>12}")
    recent: dict[str, list[Trade]] = {}
    for name, _, _ in variants:
        recent[name] = _slice(results[name], RECENT_SLICE_START)
    rb_pnl = _stats(recent[base])["total"]
    for name, _, _ in variants:
        s = _stats(recent[name])
        dd = _max_dd(recent[name])
        delta = s['total'] - rb_pnl
        ds = f"{delta:+,}" if name != base else "—"
        print(f"  {name:<22} {s['n']:>4} {s['total']:>+13,} {s['sharpe']:>+8.2f} "
              f"{dd:>+10,.0f} {ds:>12}")

    # ── 3. METRICS PACK — FULL SAMPLE ─────────────────────────────────
    print()
    print("=" * 120)
    print("  3. METRICS PACK — FULL SAMPLE  (per Phase 4 standing rule)")
    print("=" * 120)
    print(f"  {'Variant':<22} {'PnL/BPd':>9} {'MarginalΔ$/BPd':>15} {'Worst':>10} "
          f"{'IC_HV CVaR5%':>13} {'MaxBP%':>10} {'#2× ovl days':>13}")
    for name, _, mult in variants:
        ts = results[name]
        bp_d = _bp_days(ts)
        per = _stats(ts)['total'] / bp_d if bp_d > 0 else 0.0

        if name == base:
            marg = "—"
        else:
            d_pnl = _stats(ts)['total'] - base_pnl
            d_bp = bp_d - base_bp_days
            if abs(d_bp) > 1e-6:
                marg_v = d_pnl / d_bp
                marg = f"{marg_v:+.4f}"
            else:
                marg = "n/a"

        worst = _worst_trade(ts)
        cvar = _cvar_5pct(_ic_hv(ts))
        max_bp_pct, _ = _max_ic_hv_bp_pct(ts)
        if mult > 1.0:
            n_2x_ovl = _concurrent_2x_event_days(ts, _CLUSTER_MAP, multiplier_threshold=mult * 0.9)
        else:
            n_2x_ovl = 0  # variants without size boost
        print(f"  {name:<22} {per:>+9.4f} {marg:>15} {worst:>+10,.0f} "
              f"{cvar:>+13,.0f} {max_bp_pct:>9.1f}% {n_2x_ovl:>13}")
    print()
    print("  Marginal $/BP-day = (PnL_v − PnL_A) / (BPdays_v − BPdays_A)")
    print(f"  V_A baseline PnL/BPd = {base_pnl/base_bp_days:+.4f}  →  any marginal below this = leverage drag")

    # ── 4. IC_HV vs NON-IC_HV DECOMPOSITION ───────────────────────────
    print()
    print("=" * 120)
    print("  4. IC_HV vs NON-IC_HV DECOMPOSITION — full sample")
    print("=" * 120)
    print(f"  {'Variant':<22} {'IC_HV n':>8} {'IC_HV PnL':>13} {'nonIC_HV n':>11} "
          f"{'nonIC_HV PnL':>14} {'Σ check':>13}")
    base_ic = _stats(_ic_hv(results[base]))['total']
    base_non = _stats(_non_ic_hv(results[base]))['total']
    for name, _, _ in variants:
        ic = _stats(_ic_hv(results[name]))
        non = _stats(_non_ic_hv(results[name]))
        sigma = ic['total'] + non['total']
        d_ic = ic['total'] - base_ic
        d_non = non['total'] - base_non
        deltas = f"(IC{d_ic:+,}, non{d_non:+,})" if name != base else ""
        print(f"  {name:<22} {ic['n']:>8} {ic['total']:>+13,} {non['n']:>11} "
              f"{non['total']:>+14,} {sigma:>+13,}  {deltas}")

    # ── 5. 2026-03 DOUBLE-PEAK ────────────────────────────────────────
    print()
    print("=" * 120)
    print("  5. 2026-03 DOUBLE-PEAK CAPTURE")
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

    # ── 6. DISASTER WINDOWS ───────────────────────────────────────────
    print()
    print("=" * 120)
    print("  6. DISASTER WINDOWS — FULL SAMPLE")
    print("=" * 120)
    windows = [
        ("2008 GFC",    "2008-09-01", "2008-12-31"),
        ("2020 COVID",  "2020-02-20", "2020-04-30"),
        ("2025 Tariff", "2025-04-01", "2025-05-31"),
    ]

    def _in(d):
        for nm, lo, hi in windows:
            if lo <= d <= hi:
                return nm
        return None

    for name, _, _ in variants:
        ic = _ic_hv(results[name])
        dis = [t for t in ic if _in(t.entry_date)]
        if not dis:
            print(f"  {name:<22} —")
            continue
        net = sum(t.exit_pnl for t in dis)
        wins = sum(1 for t in dis if t.exit_pnl > 0)
        by_event: dict[str, list[float]] = {}
        for t in dis:
            ev = _in(t.entry_date)
            by_event.setdefault(ev, []).append(t.exit_pnl)
        bd = ", ".join(f"{ev}={len(pls)}×(${sum(pls):+,.0f})"
                       for ev, pls in by_event.items())
        print(f"  {name:<22} n={len(dis):>2}, {wins}W/{len(dis)-wins}L, "
              f"net ${net:+,.0f}  [{bd}]")

    # ── 7. CLUSTER COVERAGE ───────────────────────────────────────────
    print()
    print("=" * 120)
    print("  7. CLUSTER COVERAGE")
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

    # ── 8. METRICS PACK — RECENT SLICE ────────────────────────────────
    print()
    print("=" * 120)
    print(f"  8. METRICS PACK — RECENT SLICE ({RECENT_SLICE_START}+)")
    print("=" * 120)
    rb_bp_days = _bp_days(recent[base])
    rb_pnl = _stats(recent[base])['total']
    print(f"  {'Variant':<22} {'PnL/BPd':>9} {'MarginalΔ$/BPd':>15} {'Worst':>10} {'IC_HV CVaR5%':>13}")
    for name, _, _ in variants:
        ts = recent[name]
        bp_d = _bp_days(ts)
        per = _stats(ts)['total'] / bp_d if bp_d > 0 else 0.0
        if name == base:
            marg = "—"
        else:
            d_pnl = _stats(ts)['total'] - rb_pnl
            d_bp = bp_d - rb_bp_days
            marg = f"{d_pnl/d_bp:+.4f}" if abs(d_bp) > 1e-6 else "n/a"
        worst = _worst_trade(ts)
        cvar = _cvar_5pct(_ic_hv(ts))
        print(f"  {name:<22} {per:>+9.4f} {marg:>15} {worst:>+10,.0f} {cvar:>+13,.0f}")

    # ── 9. VERDICT SCAFFOLD ──────────────────────────────────────────
    print()
    print("=" * 120)
    print("  9. VERDICT SCAFFOLD")
    print("=" * 120)
    print("  Read order:")
    print("    §3 marginal $/BP-day → if any variant > V_A baseline (~4.85), it adds smart edge")
    print("                           if all < V_A baseline, the extra PnL is leverage")
    print("    §3 IC_HV CVaR 5%      → tail concentration; lower (more negative) = worse tail")
    print("    §3 #2× overlap days   → 0 days for V_J means overlap is fully suppressed")
    print("    §6 disaster net       → confirms whether tail damage materialises")
    print("    §5 2026-03 case       → semantic check on PM motivation")


if __name__ == "__main__":
    run_study()
