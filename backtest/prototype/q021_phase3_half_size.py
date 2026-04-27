"""
Q021 Phase 3 — Half-size same-cluster 2nd entry + 2018-2026 slice + BP gap decomp.

Per 2nd Quant review (`tests/q021_2nd_quant_handoff_2026-04-25.md`):
  Phase 1 + 2 evidence is insufficient to close Q021. Reviewer requested a small
  Phase 3 with three focused variants, recent-era slice, and decomposition of
  the V1↔V3 system-vs-IC_HV ~$1K gap (which Phase 2 left unexplained).

PM (2026-04-25): approved Phase 3; Q021 stays open; cluster threshold sweep
deferred to Phase 4.

Variants:
  V_A  SPEC-066 baseline       — cap=2, OFF_PEAK=0.10  (= Phase 2 V1)
  V_B  half-size back-to-back  — cap=2 + same-cluster 2nd entry allowed at
                                 size_mult × 0.5; OFF_PEAK=0.10
  V_C  distinct-cluster only   — cap=2 + same-cluster 2nd blocked
                                 (= Phase 2 V3)

Reporting:
  - Full sample (2000-..-2026)  + recent-era slice (2018-2026)
  - System / IC_HV / non-IC_HV decomposition  (closes Phase 2's $27K gap)
  - 2026-03 double-peak detail
  - Cluster coverage
  - Disaster windows (full sample only — recent slice has no GFC)

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q021_phase3_half_size
"""

from __future__ import annotations

import inspect
import pickle
from pathlib import Path

import numpy as np

import backtest.engine as engine_mod
import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from strategy.selector import StrategyName

START = "2000-01-01"
RECENT_SLICE_START = "2018-01-01"
OFF_PEAK_B = 0.10


# ──────────────────────────────────────────────────────────────────────
# Cluster map (same definition as Phase 2)
# ──────────────────────────────────────────────────────────────────────

def _load_vix_close():
    pkl = Path("data/market_cache/yahoo__VIX__max__1d.pkl")
    df = pickle.loads(pkl.read_bytes())
    if hasattr(df, "Close"):
        s = df["Close"]
    else:
        s = df.iloc[:, 0]
    return {str(idx.date()): float(v) for idx, v in s.items() if v == v}


def build_cluster_map() -> dict[str, str | None]:
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
    return cluster


# ──────────────────────────────────────────────────────────────────────
# Patched run_backtest builders
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


def _q021_is_same_cluster_2nd(positions, rec, date_str, cluster_map):
    """True if rec is IC_HV and any existing IC_HV position has cluster id matching today's."""
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return False
    cur = cluster_map.get(date_str)
    if cur is None:
        return False
    for p in positions:
        if p.strategy != StrategyName.IRON_CONDOR_HV:
            continue
        if cluster_map.get(p.entry_date) == cur:
            return True
    return False


def _q021_block_cluster(positions, rec, date_str, cluster_map, cap):
    """Block if same-cluster IC_HV open OR explicit cap reached. Same as Phase 2."""
    same_strat = [p for p in positions if p.strategy == rec.strategy]
    if cap is not None and len(same_strat) >= cap:
        return True
    cur = cluster_map.get(date_str)
    if cur is None:
        return False
    for p in same_strat:
        if cluster_map.get(p.entry_date) == cur:
            return True
    return False


def _q021_vd_block(positions, rec, date_str, cluster_map):
    """V_D block: aftermath same-cluster 2nd → BLOCK; non-aftermath → cap=2."""
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return any(p.strategy == rec.strategy for p in positions)
    same_strat = [p for p in positions if p.strategy == rec.strategy]
    cur = cluster_map.get(date_str)
    if cur is None:
        return len(same_strat) >= 2
    for p in same_strat:
        if cluster_map.get(p.entry_date) == cur:
            return True
    return False


def _q021_vd_double(positions, rec, date_str, cluster_map):
    """V_D 2× size: today is aftermath AND no same-cluster IC_HV currently open."""
    if rec.strategy != StrategyName.IRON_CONDOR_HV:
        return False
    cur = cluster_map.get(date_str)
    if cur is None:
        return False
    for p in positions:
        if p.strategy != StrategyName.IRON_CONDOR_HV:
            continue
        if cluster_map.get(p.entry_date) == cur:
            return False
    return True


def _build_variant_A():
    """V_A = SPEC-066 production (cap=2). Use unmodified run_backtest."""
    return run_backtest


def _build_variant_B():
    """V_B = cap=2 + same-cluster 2nd entry allowed at half BP size.

    Engine's `size_mult` field is dead code — actual sizing flows via `bp_target`.
    So we patch:
      (1) `_new_bp_target = params.bp_target_for_regime(regime)` — used by the
           BP ceiling check at entry time. Halve when same-cluster 2nd IC_HV.
      (2) `bp_target=params.bp_target_for_regime(regime),` — used in Position
           construction. Halve identically so contracts/PnL/total_bp track.

    Both must halve so the ceiling check is consistent with the position the
    engine actually opens.
    """
    src = inspect.getsource(engine_mod.run_backtest)
    if _ORIG_BP_TARGET_LINE not in src:
        raise RuntimeError("Expected _new_bp_target line not found")
    if _ORIG_BP_TARGET_USAGE not in src:
        raise RuntimeError("Expected bp_target= usage in Position not found")

    new_target_line = (
        "_new_bp_target = (params.bp_target_for_regime(regime) * 0.5 "
        "if _q021_is_same_cluster_2nd(positions, rec, str(date.date()), _q021_cluster_map) "
        "else params.bp_target_for_regime(regime))"
    )
    new_usage = "bp_target=_new_bp_target,"

    patched = src.replace(_ORIG_BP_TARGET_LINE, new_target_line)
    patched = patched.replace(_ORIG_BP_TARGET_USAGE, new_usage)
    if patched == src:
        raise RuntimeError("V_B bp_target patches produced no change")

    ns = dict(engine_mod.__dict__)
    ns["_q021_cluster_map"] = _CLUSTER_MAP
    ns["_q021_is_same_cluster_2nd"] = _q021_is_same_cluster_2nd
    exec(patched, ns)
    return ns["run_backtest"]


def _build_variant_D():
    """V_D = aftermath first entry at 2× size + distinct-cluster 2nd allowed (also 2×) + same-cluster back-to-back blocked.

    PM 2026-04-25 reframe: SPEC-066 cap=2 same-cluster back-to-back is operationally
    equivalent (~) to a single 2×-size entry on the first aftermath day, but with
    extra position management overhead. V_D tests that hypothesis.

    Patches:
      (1) `_already_open` → V_D block: same-cluster aftermath blocked; non-aftermath cap=2
      (2) `_new_bp_target` + `bp_target=` Position arg → 2× when V_D doubling condition holds
    """
    src = inspect.getsource(engine_mod.run_backtest)
    if _ORIG_ALREADY not in src:
        raise RuntimeError("Expected _already_open block not found")
    if _ORIG_BP_TARGET_LINE not in src:
        raise RuntimeError("Expected _new_bp_target line not found")
    if _ORIG_BP_TARGET_USAGE not in src:
        raise RuntimeError("Expected bp_target= usage not found")

    new_already = (
        "_already_open = ("
        "_q021_vd_block(positions, rec, str(date.date()), _q021_cluster_map) "
        "if rec.strategy == StrategyName.IRON_CONDOR_HV "
        "else any(p.strategy == rec.strategy for p in positions)"
        ")"
    )
    new_target = (
        "_new_bp_target = (params.bp_target_for_regime(regime) * 2.0 "
        "if _q021_vd_double(positions, rec, str(date.date()), _q021_cluster_map) "
        "else params.bp_target_for_regime(regime))"
    )
    new_usage = "bp_target=_new_bp_target,"

    patched = src.replace(_ORIG_ALREADY, new_already)
    patched = patched.replace(_ORIG_BP_TARGET_LINE, new_target)
    patched = patched.replace(_ORIG_BP_TARGET_USAGE, new_usage)
    if patched == src:
        raise RuntimeError("V_D patches produced no change")

    ns = dict(engine_mod.__dict__)
    ns["_q021_cluster_map"] = _CLUSTER_MAP
    ns["_q021_vd_block"] = _q021_vd_block
    ns["_q021_vd_double"] = _q021_vd_double
    exec(patched, ns)
    return ns["run_backtest"]


def _build_variant_C():
    """V_C = cap=2 + same-cluster 2nd blocked (= Phase 2 V3)."""
    src = inspect.getsource(engine_mod.run_backtest)
    if _ORIG_ALREADY not in src:
        raise RuntimeError("Expected _already_open block not found")
    repl = (
        "_already_open = ("
        "_q021_block_cluster(positions, rec, str(date.date()), _q021_cluster_map, cap=2) "
        "if rec.strategy == StrategyName.IRON_CONDOR_HV "
        "else any(p.strategy == rec.strategy for p in positions)"
        ")"
    )
    patched = src.replace(_ORIG_ALREADY, repl)
    ns = dict(engine_mod.__dict__)
    ns["_q021_cluster_map"] = _CLUSTER_MAP
    ns["_q021_block_cluster"] = _q021_block_cluster
    exec(patched, ns)
    return ns["run_backtest"]


_CLUSTER_MAP: dict[str, str | None] = {}


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


def _max_concurrent_ic_hv(trades):
    events = []
    for t in _ic_hv(trades):
        events.append((t.entry_date, +1))
        events.append((t.exit_date, -1))
    events.sort()
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return peak


def _slice(trades, lo, hi=None):
    if hi is None:
        return [t for t in trades if t.entry_date >= lo]
    return [t for t in trades if lo <= t.entry_date <= hi]


def _trade_id(t):
    return (t.entry_date, t.strategy.value, round(t.entry_spx, 2),
            round(t.entry_vix, 2), t.exit_date)


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
    global _CLUSTER_MAP
    print("Q021 Phase 3 — Half-size + recent slice + BP gap decomposition")
    print()

    print("  Building VIX aftermath cluster map ...")
    _CLUSTER_MAP = build_cluster_map()
    n_after = sum(1 for v in _CLUSTER_MAP.values() if v is not None)
    n_clusters = len(set(v for v in _CLUSTER_MAP.values() if v is not None))
    print(f"    {n_after} aftermath days across {n_clusters} clusters")
    print()

    variants = [
        ("V_A_spec066",     _build_variant_A),
        ("V_B_half_size",   _build_variant_B),
        ("V_C_distinct",    _build_variant_C),
        ("V_D_2x_first",    _build_variant_D),
    ]

    results: dict[str, list[Trade]] = {}
    for name, builder in variants:
        print(f"  Running {name} ...")
        run_fn = builder()
        results[name] = _run(run_fn, OFF_PEAK_B)

    # ── 1. System-level full-sample table ──────────────────────────
    print()
    print("=" * 110)
    print("  1. SYSTEM-LEVEL — FULL SAMPLE (2000-..-2026)")
    print("=" * 110)
    print(f"  {'Variant':<18} {'n':>4} {'Total PnL':>13} {'Sharpe':>8} "
          f"{'MaxDD':>12} {'MaxConc IC_HV':>14}")
    base_pnl = _stats(results["V_A_spec066"])["total"]
    for name, _ in variants:
        s = _stats(results[name])
        dd = _max_dd(results[name])
        mx = _max_concurrent_ic_hv(results[name])
        delta = s['total'] - base_pnl
        delta_str = f"({delta:+,})" if name != "V_A_spec066" else ""
        print(f"  {name:<18} {s['n']:>4} {s['total']:>+13,} {s['sharpe']:>+8.2f} "
              f"{dd:>+12,.0f} {mx:>14}  {delta_str}")

    # ── 2. Recent-era slice ────────────────────────────────────────
    print()
    print("=" * 110)
    print(f"  2. SYSTEM-LEVEL — RECENT SLICE (entry_date ≥ {RECENT_SLICE_START})")
    print("=" * 110)
    print(f"  {'Variant':<18} {'n':>4} {'Total PnL':>13} {'Sharpe':>8} {'MaxDD':>12}")
    recent: dict[str, list[Trade]] = {}
    for name, _ in variants:
        recent[name] = _slice(results[name], RECENT_SLICE_START)
    rb_pnl = _stats(recent["V_A_spec066"])["total"]
    for name, _ in variants:
        s = _stats(recent[name])
        dd = _max_dd(recent[name])
        delta = s['total'] - rb_pnl
        delta_str = f"({delta:+,})" if name != "V_A_spec066" else ""
        print(f"  {name:<18} {s['n']:>4} {s['total']:>+13,} {s['sharpe']:>+8.2f} "
              f"{dd:>+12,.0f}  {delta_str}")

    # ── 3. IC_HV vs non-IC_HV decomposition (the $27K gap explainer) ──
    print()
    print("=" * 110)
    print("  3. IC_HV vs NON-IC_HV DECOMPOSITION — full sample")
    print("=" * 110)
    print(f"  {'Variant':<18} {'IC_HV n':>8} {'IC_HV PnL':>12} "
          f"{'nonIC_HV n':>11} {'nonIC_HV PnL':>13} {'Σ check':>12}")
    base_ic = _stats(_ic_hv(results["V_A_spec066"]))["total"]
    base_non = _stats(_non_ic_hv(results["V_A_spec066"]))["total"]
    for name, _ in variants:
        ic = _stats(_ic_hv(results[name]))
        non = _stats(_non_ic_hv(results[name]))
        sigma = ic['total'] + non['total']
        d_ic = ic['total'] - base_ic
        d_non = non['total'] - base_non
        deltas = f"(IC {d_ic:+,}, non {d_non:+,})" if name != "V_A_spec066" else ""
        print(f"  {name:<18} {ic['n']:>8} {ic['total']:>+12,} "
              f"{non['n']:>11} {non['total']:>+13,} {sigma:>+12,}  {deltas}")

    print()
    print("  → 'non-IC_HV ΔPnL' isolates the BP/shock interaction effect that")
    print("    the 2nd Quant review flagged as missing in Phase 2.")

    # ── 4. Same-cluster 2nd entry detail (V_B) ─────────────────────
    print()
    print("=" * 110)
    print("  4. V_B SAME-CLUSTER 2ND ENTRIES (the trades that get half size)")
    print("=" * 110)
    ic_b = _ic_hv(results["V_B_half_size"])
    second_entries = []
    by_cluster_count: dict[str, int] = {}
    for t in sorted(ic_b, key=lambda x: x.entry_date):
        cid = _CLUSTER_MAP.get(t.entry_date)
        if cid is None:
            continue
        n_so_far = by_cluster_count.get(cid, 0)
        by_cluster_count[cid] = n_so_far + 1
        if n_so_far >= 1:
            second_entries.append(t)
    print(f"  Total V_B IC_HV trades:                {len(ic_b)}")
    print(f"  Same-cluster 2nd-entries (half size):  {len(second_entries)}")
    print(f"  Sum PnL of half-size 2nd-entries:      $"
          f"{sum(t.exit_pnl for t in second_entries):+,.0f}")
    if second_entries:
        print()
        for t in second_entries[:30]:
            cid = _CLUSTER_MAP.get(t.entry_date)
            print(f"    {t.entry_date} → {t.exit_date}  cluster={cid}  "
                  f"VIX={t.entry_vix:>5.1f}  pnl=${t.exit_pnl:>+8,.0f}  "
                  f"contracts={t.contracts:.2f}  bp%={t.bp_pct_account*100:.2f}  ({t.exit_reason})")
        if len(second_entries) > 30:
            print(f"    ... +{len(second_entries) - 30} more")

    # ── 5. 2026-03 double-peak case ────────────────────────────────
    print()
    print("=" * 110)
    print("  5. 2026-03 DOUBLE-PEAK CAPTURE")
    print("=" * 110)
    for name, _ in variants:
        ic = _ic_hv(results[name])
        q2 = [t for t in ic if "2026-03-01" <= t.entry_date <= "2026-04-15"]
        if not q2:
            print(f"  {name:<18} —")
            continue
        net = sum(t.exit_pnl for t in q2)
        print(f"  {name:<18} {len(q2)} trades, net ${net:+,.0f}")
        for t in q2:
            cid = _CLUSTER_MAP.get(t.entry_date) or "non_after"
            print(f"    {t.entry_date}[{cid}] contracts={t.contracts:.2f} "
                  f"pnl=${t.exit_pnl:+,.0f}")

    # ── 6. Cluster coverage ────────────────────────────────────────
    print()
    print("=" * 110)
    print("  6. CLUSTER COVERAGE")
    print("=" * 110)
    print(f"  {'Variant':<18} {'#after_trades':>14} {'#clusters_hit':>14} "
          f"{'#multi':>8} {'avg/hit':>10}")
    for name, _ in variants:
        ic_after = [t for t in _ic_hv(results[name])
                    if _CLUSTER_MAP.get(t.entry_date) is not None]
        by_cl: dict[str, int] = {}
        for t in ic_after:
            cid = _CLUSTER_MAP[t.entry_date]
            by_cl[cid] = by_cl.get(cid, 0) + 1
        n_hit = len(by_cl)
        n_multi = sum(1 for v in by_cl.values() if v > 1)
        avg = (sum(by_cl.values()) / n_hit) if n_hit else 0
        print(f"  {name:<18} {len(ic_after):>14} {n_hit:>14} {n_multi:>8} {avg:>10.2f}")

    # ── 7. Disaster windows (full sample) ───────────────────────────
    print()
    print("=" * 110)
    print("  7. DISASTER WINDOWS — FULL SAMPLE")
    print("=" * 110)
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

    for name, _ in variants:
        ic = _ic_hv(results[name])
        dis = [t for t in ic if _in(t.entry_date)]
        if not dis:
            print(f"  {name:<18} —")
            continue
        net = sum(t.exit_pnl for t in dis)
        wins = sum(1 for t in dis if t.exit_pnl > 0)
        by_event: dict[str, list[float]] = {}
        for t in dis:
            ev = _in(t.entry_date)
            by_event.setdefault(ev, []).append(t.exit_pnl)
        bd = ", ".join(f"{ev}={len(pls)}×(${sum(pls):+,.0f})"
                       for ev, pls in by_event.items())
        print(f"  {name:<18} n={len(dis):>2}, {wins}W/{len(dis)-wins}L, "
              f"net ${net:+,.0f}  [{bd}]")

    # ── 8. BP-adjusted return (PnL / sum of BP-days used) ───────────
    print()
    print("=" * 110)
    print("  8. BP-ADJUSTED RETURN — full sample")
    print("=" * 110)
    print("  BP-days = sum_over_trades(bp_pct_account × hold_days).")
    print(f"  {'Variant':<18} {'PnL':>13} {'BP-days':>10} {'PnL/BP-day':>12}")
    for name, _ in variants:
        ts = results[name]
        bp_days = 0.0
        for t in ts:
            held = max(0, _date_diff(t.exit_date, t.entry_date))
            bp_days += float(t.bp_pct_account) * held
        s = _stats(ts)
        per = s['total'] / bp_days if bp_days > 0 else 0.0
        print(f"  {name:<18} {s['total']:>+13,} {bp_days:>10.0f} {per:>+12.4f}")

    # ── 9. Verdict scaffold ────────────────────────────────────────
    print()
    print("=" * 110)
    print("  9. VERDICT SCAFFOLD (raw inputs for Phase 3 deliverable)")
    print("=" * 110)
    print("  Compare V_A vs V_B (does half-size beat current full-size back-to-back?)")
    print("  Compare V_A vs V_C (Phase 2 V3 — already known -$9K full sample)")
    print("  Per 2nd Quant: focus on recent slice + non-IC_HV delta.")


def _date_diff(a: str, b: str) -> int:
    """ISO-date string subtraction (a - b) in days."""
    from datetime import date
    da = date.fromisoformat(a)
    db = date.fromisoformat(b)
    return (da - db).days


if __name__ == "__main__":
    run_study()
