"""
Q021 Phase 2 — Distinct-peak vs back-to-back attribution under full engine.

Phase 1 attribution (doc/q021_phase1_attribution_2026-04-25.md) showed that
SPEC-066's incremental alpha over cap=1 (+18 trades / +$9,593) is dominated
by same-peak back-to-back captures (14 trades / $+8,458 = 88% of $) rather
than distinct-second-peak captures (4 trades / $+1,135).

This prototype runs the full engine (BP / shock / overlay) under four
variants to test PM's hypothesis: enforcing same-cluster dedup (PM intent)
instead of cap=2 + B should preserve the distinct-peak alpha while shedding
the back-to-back exposure that PM finds semantically unintended.

Variants:
  V0 baseline       — cap=1, OFF_PEAK=0.05  (pre-SPEC-064/066 production)
  V1 spec066        — cap=2, OFF_PEAK=0.10  (current production; reference)
  V2 pm_intent      — same-cluster max 1, no global cap, OFF_PEAK=0.10
                      (PM hypothesis: distinct aftermath cluster only)
  V3 pm_intent+cap2 — same-cluster max 1 AND global cap=2, OFF_PEAK=0.10
                      (defensive: belt-and-suspenders)

Cluster definition (matches Phase 1):
  - A trading day is "aftermath" iff peak_10d_VIX >= 28 AND off_peak_pct >= 0.10
  - Contiguous aftermath days form one cluster (cluster_id = first day)
  - Non-aftermath day → cluster_id = None (no group; cap behavior decides)

Method:
  1. Pre-compute cluster_map from VIX cache (dict[date_str → cluster_start_or_None])
  2. Inject cluster_map + helper into engine module namespace
  3. inspect.getsource → patch the `_already_open = ...` block → exec
  4. Run all 4 variants end-to-end with full engine

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q021_phase2_distinct_peak
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
OFF_PEAK_B = 0.10


# ──────────────────────────────────────────────────────────────────────
# Cluster map from VIX history
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
    is_aftermath: dict[str, bool] = {}
    for i, d in enumerate(dates):
        lo = max(0, i - 9)
        win = [vix[sd] for sd in dates[lo:i + 1]]
        peak = max(win)
        cur = vix[d]
        op = (peak - cur) / peak if peak > 0 else 0.0
        is_aftermath[d] = (peak >= 28.0) and (op >= 0.10)

    cluster: dict[str, str | None] = {}
    cur_id: str | None = None
    for d in dates:
        if is_aftermath[d]:
            if cur_id is None:
                cur_id = d
            cluster[d] = cur_id
        else:
            cur_id = None
            cluster[d] = None
    return cluster


# ──────────────────────────────────────────────────────────────────────
# Patched run_backtest builder
# ──────────────────────────────────────────────────────────────────────

_ORIG_BLOCK = (
    "_already_open = (\n"
    "            sum(1 for p in positions if p.strategy == rec.strategy) >= IC_HV_MAX_CONCURRENT\n"
    "            if rec.strategy == StrategyName.IRON_CONDOR_HV\n"
    "            else any(p.strategy == rec.strategy for p in positions)\n"
    "        )"
)


def _replacement(mode: str, cap: int) -> str:
    """
    mode:
      'cap_only'    — cap=cap (V0=1, V1=2)
      'cluster'     — same-cluster max 1, no cap (V2)
      'cluster_cap' — same-cluster max 1 AND cap (V3, cap=2)
    """
    if mode == "cap_only":
        return (
            f"_already_open = ("
            f"(sum(1 for p in positions if p.strategy == rec.strategy) >= {cap}) "
            f"if rec.strategy == StrategyName.IRON_CONDOR_HV "
            f"else any(p.strategy == rec.strategy for p in positions)"
            f")"
        )
    if mode == "cluster":
        return (
            "_already_open = ("
            "_q021_block_cluster(positions, rec, str(date.date()), _q021_cluster_map, cap=None) "
            "if rec.strategy == StrategyName.IRON_CONDOR_HV "
            "else any(p.strategy == rec.strategy for p in positions)"
            ")"
        )
    if mode == "cluster_cap":
        return (
            f"_already_open = ("
            f"_q021_block_cluster(positions, rec, str(date.date()), _q021_cluster_map, cap={cap}) "
            f"if rec.strategy == StrategyName.IRON_CONDOR_HV "
            f"else any(p.strategy == rec.strategy for p in positions)"
            f")"
        )
    raise ValueError(mode)


def _q021_block_cluster(positions, rec, date_str, cluster_map, cap):
    """Block IF: same-cluster IC_HV already open, OR explicit cap reached.

    Semantic: PM's intent is about aftermath same-cluster dedup only. Non-aftermath
    HIGH_VOL IC_HV entries fall back to SPEC-066 cap=2 behavior (which is not what
    PM is challenging). Therefore:
      - Today in aftermath (cur_cluster not None) AND any open IC_HV's
        entry was in the same cluster → BLOCK.
      - cap argument provides an explicit ceiling on top (None = no extra cap).

    cluster_map: date_str -> cluster_id (str) or None
    cap: int or None — global IC_HV ceiling regardless of cluster
    """
    same_strat = [p for p in positions if p.strategy == rec.strategy]
    if cap is not None and len(same_strat) >= cap:
        return True
    cur_cluster = cluster_map.get(date_str)
    if cur_cluster is None:
        # Non-aftermath day: PM's same-cluster rule does not apply here.
        # Behavior governed entirely by `cap` (None = unlimited like SPEC-066+
        # without numeric cap; for V2 we pair with cap=2 baseline elsewhere).
        return False
    for p in same_strat:
        p_cluster = cluster_map.get(p.entry_date)
        if p_cluster == cur_cluster:
            return True
    return False


def _build_patched(mode: str, cap: int):
    if mode == "cap_only" and cap == 1:
        return run_backtest  # baseline, unmodified
    src = inspect.getsource(engine_mod.run_backtest)
    if _ORIG_BLOCK not in src:
        # Fall back: try the cap=2-style line literally (for older revisions)
        raise RuntimeError("Expected _already_open block not found in run_backtest source")
    patched = src.replace(_ORIG_BLOCK, _replacement(mode, cap))
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


def _run(run_fn, off_peak):
    orig = sel.AFTERMATH_OFF_PEAK_PCT
    sel.AFTERMATH_OFF_PEAK_PCT = off_peak
    try:
        return _closed(run_fn(start_date=START, verbose=False).trades)
    finally:
        sel.AFTERMATH_OFF_PEAK_PCT = orig


def _trade_id(t):
    return (t.entry_date, t.strategy.value, round(t.entry_spx, 2),
            round(t.entry_vix, 2), t.exit_date)


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def run_study():
    global _CLUSTER_MAP
    print("Q021 Phase 2 — Distinct-peak vs back-to-back attribution (full engine)")
    print()

    print("  Building VIX aftermath cluster map ...")
    _CLUSTER_MAP = build_cluster_map()
    n_after = sum(1 for v in _CLUSTER_MAP.values() if v is not None)
    n_clusters = len(set(v for v in _CLUSTER_MAP.values() if v is not None))
    print(f"    {n_after} aftermath days across {n_clusters} clusters")
    print()

    variants = [
        ("V0_baseline",       "cap_only", 1, 0.05),
        ("V1_spec066",        "cap_only", 2, OFF_PEAK_B),
        ("V2_pm_intent",      "cluster",  0, OFF_PEAK_B),  # cap arg ignored
        ("V3_pm_intent_cap2", "cluster_cap", 2, OFF_PEAK_B),
    ]

    results: dict[str, list[Trade]] = {}
    for name, mode, cap, off_peak in variants:
        print(f"  Running {name} ({mode}, cap={cap}, OFF_PEAK={off_peak}) ...")
        run_fn = _build_patched(mode, cap)
        results[name] = _run(run_fn, off_peak)

    # ── System-level table ─────────────────────────────────────────
    print()
    print("=" * 110)
    print("  SYSTEM-LEVEL")
    print("=" * 110)
    print(f"  {'Variant':<22} {'n':>4} {'Total PnL':>13} {'Sharpe':>8} "
          f"{'MaxDD':>12} {'PnL Δ vs V0':>13} {'MaxConc IC_HV':>14}")

    base_total = _stats(results["V0_baseline"])["total"]
    for name, *_ in variants:
        s = _stats(results[name])
        dd = _max_dd(results[name])
        delta = s['total'] - base_total
        mx = _max_concurrent_ic_hv(results[name])
        print(f"  {name:<22} {s['n']:>4} {s['total']:>+13,} {s['sharpe']:>+8.2f} "
              f"{dd:>+12,.0f} {delta:>+13,} {mx:>14}")

    # ── IC_HV subset table ─────────────────────────────────────────
    print()
    print("=" * 110)
    print("  IC_HV SUBSET")
    print("=" * 110)
    print(f"  {'Variant':<22} {'n':>4} {'Total PnL':>13} {'avg':>8} {'win%':>6} {'Sharpe':>8}")
    for name, *_ in variants:
        ic = _ic_hv(results[name])
        s = _stats(ic)
        print(f"  {name:<22} {s['n']:>4} {s['total']:>+13,} {s['mean']:>+8,} "
              f"{s['win%']:>5.1f}% {s['sharpe']:>+8.2f}")

    # ── Pairwise: V1 spec066 vs V2 pm_intent — what changes? ───────
    print()
    print("=" * 110)
    print("  V1 (spec066) vs V2 (pm_intent) — IC_HV trade-set diff")
    print("=" * 110)
    ic_v1 = _ic_hv(results["V1_spec066"])
    ic_v2 = _ic_hv(results["V2_pm_intent"])
    ids_v1 = {_trade_id(t) for t in ic_v1}
    ids_v2 = {_trade_id(t) for t in ic_v2}
    only_v1 = [t for t in ic_v1 if _trade_id(t) not in ids_v2]
    only_v2 = [t for t in ic_v2 if _trade_id(t) not in ids_v1]
    print(f"  Only in V1 (spec066 keeps, pm_intent drops): {len(only_v1)} trades, "
          f"net ${sum(t.exit_pnl for t in only_v1):+,.0f}")
    print(f"  Only in V2 (pm_intent gains, spec066 missed): {len(only_v2)} trades, "
          f"net ${sum(t.exit_pnl for t in only_v2):+,.0f}")
    print()

    if only_v1:
        print("  Dropped by pm_intent (same-cluster back-to-back filtered):")
        for t in sorted(only_v1, key=lambda x: x.entry_date):
            cid = _CLUSTER_MAP.get(t.entry_date) or "—"
            print(f"    {t.entry_date} → {t.exit_date}  cluster={cid:<12}  "
                  f"VIX={t.entry_vix:>5.1f}  pnl=${t.exit_pnl:>+8,.0f}  ({t.exit_reason})")

    if only_v2:
        print()
        print("  Gained by pm_intent (BP freed → distinct-cluster captures):")
        for t in sorted(only_v2, key=lambda x: x.entry_date):
            cid = _CLUSTER_MAP.get(t.entry_date) or "—"
            print(f"    {t.entry_date} → {t.exit_date}  cluster={cid:<12}  "
                  f"VIX={t.entry_vix:>5.1f}  pnl=${t.exit_pnl:>+8,.0f}  ({t.exit_reason})")

    # ── 2026-03 case detail across all variants ────────────────────
    print()
    print("=" * 110)
    print("  2026-03 DOUBLE-PEAK CAPTURE (peak1 ≈ 03-06, peak2 ≈ 03-27)")
    print("=" * 110)
    for name, *_ in variants:
        ic = _ic_hv(results[name])
        q2 = [t for t in ic if "2026-03-01" <= t.entry_date <= "2026-04-15"]
        if not q2:
            print(f"  {name:<22} —")
            continue
        parts = []
        for t in q2:
            cid = _CLUSTER_MAP.get(t.entry_date) or "non_after"
            parts.append(f"{t.entry_date}[{cid}](${t.exit_pnl:+,.0f})")
        net = sum(t.exit_pnl for t in q2)
        print(f"  {name:<22} {len(q2)} trades, net ${net:+,.0f}")
        for p in parts:
            print(f"    {p}")

    # ── Cluster-coverage breakdown ──────────────────────────────────
    print()
    print("=" * 110)
    print("  CLUSTER COVERAGE (how many distinct aftermath clusters captured?)")
    print("=" * 110)
    print(f"  {'Variant':<22} {'#trades':>8} {'#clusters_hit':>14} "
          f"{'#multi_per_cluster':>20} {'avg trades/hit_cluster':>22}")
    for name, *_ in variants:
        ic_after = [t for t in _ic_hv(results[name])
                    if _CLUSTER_MAP.get(t.entry_date) is not None]
        by_cl: dict[str, int] = {}
        for t in ic_after:
            cid = _CLUSTER_MAP[t.entry_date]
            by_cl[cid] = by_cl.get(cid, 0) + 1
        n_clusters_hit = len(by_cl)
        n_multi = sum(1 for v in by_cl.values() if v > 1)
        avg = (sum(by_cl.values()) / n_clusters_hit) if n_clusters_hit else 0
        print(f"  {name:<22} {len(ic_after):>8} {n_clusters_hit:>14} "
              f"{n_multi:>20} {avg:>22.2f}")

    # ── Disaster windows ────────────────────────────────────────────
    print()
    print("=" * 110)
    print("  DISASTER WINDOWS (2008-09..12, 2020-02..04, 2025-04..05)")
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

    for name, *_ in variants:
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
        bd = ", ".join(f"{ev}={len(pls)}×(${sum(pls):+,.0f})" for ev, pls in by_event.items())
        print(f"  {name:<22} n={len(dis):>3}, {wins}W/{len(dis)-wins}L, "
              f"net ${net:+,.0f}  [{bd}]")


if __name__ == "__main__":
    run_study()
