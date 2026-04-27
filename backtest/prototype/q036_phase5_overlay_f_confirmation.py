"""
Q036 Phase 5 — Overlay-F confirmation.

Narrow confirmation pass focused only on the current lead candidate:
  Overlay-F_sglt2 = 2x iff idle BP >= 70%, VIX < 30, and pre-existing
  short-gamma count < 2.

Questions:
  1. Is the uplift spread across years, or concentrated in a few episodes?
  2. Where do overlay fires actually occur by regime / VIX bucket / SG count?
  3. Does the recent-era slice still support the candidate?
"""

from __future__ import annotations

from collections import defaultdict

from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.prototype import q036_phase2_overlay_pilots as p2
from backtest.prototype import q036_phase4_short_gamma_guard as p4


def _yearly_pnl(trades):
    by_year = defaultdict(float)
    for t in trades:
        by_year[int(t.exit_date[:4])] += t.exit_pnl
    return dict(sorted((y, int(v)) for y, v in by_year.items()))


def _regime_counts(rows, dates):
    by_date = {r.date: r for r in rows}
    out = defaultdict(int)
    for d in dates:
        row = by_date.get(d)
        if row is not None:
            out[row.regime] += 1
    return dict(sorted(out.items()))


def _vix_bucket(v):
    if v < 20:
        return "<20"
    if v < 25:
        return "20-25"
    if v < 30:
        return "25-30"
    if v < 35:
        return "30-35"
    return ">=35"


def _vix_bucket_counts(dates):
    out = defaultdict(int)
    for d in dates:
        v = p2._VIX_BY_DATE.get(d)
        if v is not None:
            out[_vix_bucket(v)] += 1
    return dict(sorted(out.items()))


def _fire_pack(trades, rows):
    rows_by_date = {r.date: r for r in rows}
    fires = [t for t in p2._ic_hv(trades) if p2._is_boosted_aftermath_first(t, p2._CLUSTER_MAP, 1.05)]
    fire_dates = [t.entry_date for t in fires]
    sg_at = p2._short_gamma_at_dates(rows_by_date, fire_dates)
    sg_pre = [max(0, c - 1) for c in sg_at]
    idle_at = p2._idle_bp_at_dates(rows_by_date, fire_dates)
    return fires, fire_dates, sg_pre, idle_at


def _recent_pack(trades, rows, recent_start):
    rt = p2._slice(trades, recent_start)
    rr = [r for r in rows if r.date >= recent_start]
    return rt, rr


def run_study():
    print("Q036 Phase 5 — Overlay-F confirmation")
    print()

    p2._CLUSTER_MAP, p2._VIX_BY_DATE = p2.build_cluster_map_and_vix()
    variants = [
        ("V_baseline", p2._build_baseline),
        ("Overlay-F_sglt2", p4._build_overlay_f),
    ]

    results = {}
    rows_by_var = {}
    for name, builder in variants:
        print(f"  Running {name} ...")
        trades, rows = p2._run_full(builder(), p2.OFF_PEAK_B)
        results[name] = trades
        rows_by_var[name] = rows

    base = "V_baseline"
    lead = "Overlay-F_sglt2"
    base_total = p2._stats(results[base])["total"]
    lead_total = p2._stats(results[lead])["total"]
    base_ann = compute_portfolio_metrics(rows_by_var[base]).ann_return * 100
    lead_ann = compute_portfolio_metrics(rows_by_var[lead]).ann_return * 100

    print()
    print("=" * 120)
    print("  §1 TOP-LINE CONFIRMATION")
    print("=" * 120)
    print(f"  Baseline total PnL:   {base_total:+,}")
    print(f"  Overlay-F total PnL:  {lead_total:+,}")
    print(f"  Δ total PnL:          {lead_total - base_total:+,}")
    print(f"  Baseline ann ROE:     {base_ann:+.3f}%")
    print(f"  Overlay-F ann ROE:    {lead_ann:+.3f}%")
    print(f"  Δ ann ROE:            {lead_ann - base_ann:+.3f}pp")
    print(f"  Baseline MaxDD:       {p2._max_dd(results[base]):+,.0f}")
    print(f"  Overlay-F MaxDD:      {p2._max_dd(results[lead]):+,.0f}")
    print(f"  Baseline CVaR5:       {p2._cvar_5pct(results[base]):+,.0f}")
    print(f"  Overlay-F CVaR5:      {p2._cvar_5pct(results[lead]):+,.0f}")

    print()
    print("=" * 120)
    print("  §2 YEARLY ATTRIBUTION")
    print("=" * 120)
    base_y = _yearly_pnl(results[base])
    lead_y = _yearly_pnl(results[lead])
    years = sorted(set(base_y) | set(lead_y))
    print(f"  {'Year':<6} {'Baseline':>10} {'Overlay-F':>10} {'Delta':>10}")
    deltas = []
    pos = 0
    neg = 0
    for y in years:
        b = base_y.get(y, 0)
        f = lead_y.get(y, 0)
        d = f - b
        deltas.append((y, d))
        if d > 0:
            pos += 1
        elif d < 0:
            neg += 1
        print(f"  {y:<6} {b:>+10,} {f:>+10,} {d:>+10,}")
    abs_total = sum(abs(d) for _, d in deltas) or 1
    top = sorted(deltas, key=lambda x: abs(x[1]), reverse=True)[:5]
    print()
    print(f"  Positive delta years: {pos}/{len(years)}")
    print(f"  Negative delta years: {neg}/{len(years)}")
    print("  Top 5 absolute delta years:")
    for y, d in top:
        print(f"    {y}: {d:+,} ({abs(d) / abs_total * 100:.1f}% of total absolute yearly delta)")

    print()
    print("=" * 120)
    print("  §3 OVERLAY FIRE DISTRIBUTION")
    print("=" * 120)
    fires, fire_dates, sg_pre, idle_at = _fire_pack(results[lead], rows_by_var[lead])
    print(f"  Overlay-F fire count: {len(fires)}")
    print(f"  Mean pre-existing short-gamma count: {sum(sg_pre) / len(sg_pre):.2f}" if sg_pre else "  Mean pre-existing short-gamma count: n/a")
    print(f"  Fires with pre-existing SG >= 2: {sum(1 for c in sg_pre if c >= 2)}/{len(sg_pre)}")
    print(f"  Mean idle BP at fire: {sum(idle_at) / len(idle_at) * 100:.1f}%" if idle_at else "  Mean idle BP at fire: n/a")
    print()
    print("  Fires by regime:")
    for k, v in _regime_counts(rows_by_var[lead], fire_dates).items():
        print(f"    {k}: {v}")
    print("  Fires by VIX bucket:")
    for k, v in _vix_bucket_counts(fire_dates).items():
        print(f"    {k}: {v}")
    print("  Fires by pre-existing short-gamma count:")
    sg_dist = defaultdict(int)
    for c in sg_pre:
        sg_dist[c] += 1
    for k in sorted(sg_dist):
        print(f"    {k}: {sg_dist[k]}")

    print()
    print("=" * 120)
    print(f"  §4 RECENT SLICE ({p2.RECENT_SLICE_START}+)")
    print("=" * 120)
    base_rt, base_rr = _recent_pack(results[base], rows_by_var[base], p2.RECENT_SLICE_START)
    lead_rt, lead_rr = _recent_pack(results[lead], rows_by_var[lead], p2.RECENT_SLICE_START)
    base_recent_total = p2._stats(base_rt)["total"]
    lead_recent_total = p2._stats(lead_rt)["total"]
    base_recent_ann = compute_portfolio_metrics(base_rr).ann_return * 100
    lead_recent_ann = compute_portfolio_metrics(lead_rr).ann_return * 100
    base_recent_bp = p2._bp_days(base_rt)
    lead_recent_bp = p2._bp_days(lead_rt)
    recent_marg = ((lead_recent_total - base_recent_total) / (lead_recent_bp - base_recent_bp)
                   if abs(lead_recent_bp - base_recent_bp) > 1e-6 else 0.0)
    print(f"  Baseline recent total PnL:  {base_recent_total:+,}")
    print(f"  Overlay-F recent total PnL: {lead_recent_total:+,}")
    print(f"  Δ recent total PnL:         {lead_recent_total - base_recent_total:+,}")
    print(f"  Baseline recent ann ROE:    {base_recent_ann:+.3f}%")
    print(f"  Overlay-F recent ann ROE:   {lead_recent_ann:+.3f}%")
    print(f"  Δ recent ann ROE:           {lead_recent_ann - base_recent_ann:+.3f}pp")
    print(f"  Recent marginal $/BP-day:   {recent_marg:+.4f}")
    print(f"  Baseline recent MaxDD:      {p2._max_dd(base_rt):+,.0f}")
    print(f"  Overlay-F recent MaxDD:     {p2._max_dd(lead_rt):+,.0f}")


if __name__ == "__main__":
    run_study()
