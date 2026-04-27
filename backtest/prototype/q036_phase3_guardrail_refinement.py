"""
Q036 Phase 3 — Guardrail refinement after the approved Phase 2 pilots.

Purpose:
  Phase 2 showed that Overlay-B had the strongest account-level uplift while
  Overlay-C had the cleanest short-gamma stacking control. This pass asks a
  narrower follow-up question:

    can we combine B's disaster guardrail with C's no-overlap guardrail
    without collapsing the already-small ROE uplift?

Variants:
  V_baseline        : V_A / SPEC-066 baseline
  Overlay-B_ctrl    : 2.0x iff idle BP >= 70% and VIX < 30
  Overlay-C_ctrl    : 2.0x iff idle BP >= 70% and no IC_HV currently open
  Overlay-D_hybrid  : 2.0x iff idle BP >= 70% and VIX < 30 and no IC_HV open
  Overlay-E_hyb80   : Overlay-D plus stricter idle-BP gate (>= 80%)

All boosted-first entries still block the same-cluster 2nd entry, matching
the Phase 2 capital-allocation semantics.
"""

from __future__ import annotations

from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.prototype import q036_phase2_overlay_pilots as p2


def _idle_ok(used_bp: float, threshold: float) -> bool:
    return (1.0 - float(used_bp)) >= threshold


def _overlay_d_double(positions, rec, date_str, cluster_map, used_bp):
    """2x iff idle BP >= 70%, VIX < 30, and no IC_HV is already open."""
    if rec.strategy != p2.StrategyName.IRON_CONDOR_HV:
        return False
    if cluster_map.get(date_str) is None:
        return False
    if not _idle_ok(used_bp, 0.70):
        return False
    if p2._VIX_BY_DATE.get(date_str, 0.0) >= p2.DISASTER_VIX_THRESHOLD:
        return False
    n_ic_hv_open = sum(1 for pos in positions if pos.strategy == p2.StrategyName.IRON_CONDOR_HV)
    return n_ic_hv_open == 0


def _overlay_e_double(positions, rec, date_str, cluster_map, used_bp):
    """Overlay-D plus stricter idle-BP gate (>= 80%)."""
    if rec.strategy != p2.StrategyName.IRON_CONDOR_HV:
        return False
    if cluster_map.get(date_str) is None:
        return False
    if not _idle_ok(used_bp, 0.80):
        return False
    if p2._VIX_BY_DATE.get(date_str, 0.0) >= p2.DISASTER_VIX_THRESHOLD:
        return False
    n_ic_hv_open = sum(1 for pos in positions if pos.strategy == p2.StrategyName.IRON_CONDOR_HV)
    return n_ic_hv_open == 0


def _build_overlay_d():
    return p2._patched_run("_overlay_d_double", 2.0, {"_overlay_d_double": _overlay_d_double})


def _build_overlay_e():
    return p2._patched_run("_overlay_e_double", 2.0, {"_overlay_e_double": _overlay_e_double})


def _disaster_net(trades):
    ic = p2._ic_hv(trades)
    windows = [
        ("2008 GFC", "2008-09-01", "2008-12-31"),
        ("2020 COVID", "2020-02-20", "2020-04-30"),
        ("2025 Tariff", "2025-04-01", "2025-05-31"),
    ]
    by_window = []
    total = 0.0
    for label, lo, hi in windows:
        net = sum(t.exit_pnl for t in ic if lo <= t.entry_date <= hi)
        total += net
        by_window.append((label, int(net)))
    return int(total), by_window


def _overlay_fire_pack(trades, rows):
    rows_by_date = {r.date: r for r in rows}
    fires = [t for t in p2._ic_hv(trades) if p2._is_boosted_aftermath_first(t, p2._CLUSTER_MAP, 1.05)]
    sg_at = p2._short_gamma_at_dates(rows_by_date, [t.entry_date for t in fires])
    sg_pre = [max(0, c - 1) for c in sg_at]
    sg_ge2 = (sum(1 for c in sg_pre if c >= 2) / len(sg_pre) * 100) if sg_pre else 0.0
    return len(fires), (sum(sg_pre) / len(sg_pre) if sg_pre else 0.0), sg_ge2


def run_study():
    print("Q036 Phase 3 — Guardrail refinement")
    print()

    p2._CLUSTER_MAP, p2._VIX_BY_DATE = p2.build_cluster_map_and_vix()

    variants = [
        ("V_baseline", p2._build_baseline),
        ("Overlay-B_ctrl", p2._build_overlay_b),
        ("Overlay-C_ctrl", p2._build_overlay_c),
        ("Overlay-D_hybrid", _build_overlay_d),
        ("Overlay-E_hyb80", _build_overlay_e),
    ]

    results = {}
    rows_by_var = {}
    for name, builder in variants:
        print(f"  Running {name} ...")
        trades, rows = p2._run_full(builder(), p2.OFF_PEAK_B)
        results[name] = trades
        rows_by_var[name] = rows

    base = "V_baseline"
    base_total = p2._stats(results[base])["total"]
    base_bp_days = p2._bp_days(results[base])
    base_dd = p2._max_dd(results[base])
    base_cvar = p2._cvar_5pct(results[base])
    base_peak_bp = p2._peak_system_bp_pct(rows_by_var[base])[0]
    base_ann = compute_portfolio_metrics(rows_by_var[base]).ann_return
    base_dis_total, _ = _disaster_net(results[base])
    total_idle_budget = sum((p2.ACCOUNT_SIZE - r.bp_used) / p2.ACCOUNT_SIZE * 100 for r in rows_by_var[base])

    print()
    print("=" * 120)
    print("  §1 ACCOUNT-LEVEL + INCREMENTAL TAIL COST")
    print("=" * 120)
    print(
        f"  {'Variant':<18} {'TotalPnL':>10} {'AnnROE%':>9} {'ΔAnnROEpp':>10} "
        f"{'MaxDD':>10} {'ΔCVaR':>9} {'DisNet':>9} {'PeakBP%':>8}"
    )
    for name, _ in variants:
        total = p2._stats(results[name])["total"]
        ann = compute_portfolio_metrics(rows_by_var[name]).ann_return * 100
        d_ann = ann - (base_ann * 100)
        dd = p2._max_dd(results[name])
        cvar = p2._cvar_5pct(results[name])
        dis_total, _ = _disaster_net(results[name])
        peak_bp = p2._peak_system_bp_pct(rows_by_var[name])[0]
        d_ann_s = "—" if name == base else f"{d_ann:+.3f}"
        d_cvar_s = "—" if name == base else f"{cvar - base_cvar:+.0f}"
        print(
            f"  {name:<18} {total:>+10,} {ann:>+8.2f}% {d_ann_s:>10} "
            f"{dd:>+10,.0f} {d_cvar_s:>9} {dis_total:>+9,} {peak_bp:>7.1f}%"
        )

    print()
    print("=" * 120)
    print("  §2 CAPITAL-ALLOCATION GOVERNANCE")
    print("=" * 120)
    print(
        f"  {'Variant':<18} {'+BPdays':>10} {'IdleUtil%':>10} {'OvlFires':>9} "
        f"{'SGmean':>8} {'SG>=2':>8} {'Marg$/BPd':>10}"
    )
    for name, _ in variants:
        if name == base:
            print(f"  {name:<18} {'—':>10} {'—':>10} {'—':>9} {'—':>8} {'—':>8} {'—':>10}")
            continue
        bp_days = p2._bp_days(results[name])
        d_bp = bp_days - base_bp_days
        util = d_bp / total_idle_budget * 100 if total_idle_budget else 0.0
        fires, sg_mean, sg_ge2 = _overlay_fire_pack(results[name], rows_by_var[name])
        marg = (p2._stats(results[name])["total"] - base_total) / d_bp if abs(d_bp) > 1e-6 else 0.0
        print(
            f"  {name:<18} {d_bp:>+10,.0f} {util:>9.2f}% {fires:>9} "
            f"{sg_mean:>8.2f} {sg_ge2:>7.0f}% {marg:>+10.4f}"
        )

    print()
    print("=" * 120)
    print("  §3 DISASTER WINDOW DETAIL")
    print("=" * 120)
    for name, _ in variants:
        total, by_window = _disaster_net(results[name])
        detail = ", ".join(f"{label} {net:+,}" for label, net in by_window)
        print(f"  {name:<18} total {total:+,}  |  {detail}")

    print()
    print("=" * 120)
    print("  §4 RECENT SLICE (2018+)")
    print("=" * 120)
    recent_base = p2._slice(results[base], p2.RECENT_SLICE_START)
    base_recent_total = p2._stats(recent_base)["total"]
    base_recent_bp = p2._bp_days(recent_base)
    print(f"  {'Variant':<18} {'TotalPnL':>10} {'PnL/BPd':>9} {'Marg$/BPd':>10} {'MaxDD':>10}")
    for name, _ in variants:
        ts = p2._slice(results[name], p2.RECENT_SLICE_START)
        total = p2._stats(ts)["total"]
        bpd = p2._bp_days(ts)
        per = total / bpd if bpd > 0 else 0.0
        if name == base:
            marg = "—"
        else:
            d_pnl = total - base_recent_total
            d_bp = bpd - base_recent_bp
            marg = f"{d_pnl / d_bp:+.4f}" if abs(d_bp) > 1e-6 else "n/a"
        dd = p2._max_dd(ts)
        print(f"  {name:<18} {total:>+10,} {per:>+9.4f} {marg:>10} {dd:>+10,.0f}")


if __name__ == "__main__":
    run_study()
