"""SPEC-128 — native Partnership Book engine (replaces the Excel formulas).

Pure function of the JSONL inputs under data/book/ — no hidden state, idempotent
recompute. Payload is shape-compatible with the legacy Drive/xlsx parser
(web/partnership_book.read_book) plus native extras (recon_checks, guarantees,
subaccounts).

Methodology replicated from research/book_management/Partnership_Shares_v3.5_SPEC.md:
  §3.1 two-layer cash ledger (Counts=Yes drives capital; No = transit legs)
  §3.2 snapshot-driven back-solved P&L, allocated by OPENING share
  §3.3 NAV/unit (base 100), end-of-period pricing (mathematically equivalent)
  §3.4 four return conventions (Simple / XIRR / yearly TWR / NAV-unit)
  §3.5 E*Trade merge dual basis (pool share basis vs personal cost basis;
       Lien ROI = personal-series TWR since 2025 — "三处一致" convention)

Migration acceptance: cent-level parity against the Excel's cached values
(scripts/book_migrate_from_xlsx.py gate; tests/test_spec_128.py).
"""
from __future__ import annotations

import json
import logging
import math
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("book_engine")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "book"

NAV_BASE = 100.0

# payload cache keyed on input mtimes (recompute only when inputs change)
_cache: dict[str, Any] = {"key": None, "payload": None}


# ── io ────────────────────────────────────────────────────────────────────────

def _read_events(path: Path) -> list[dict]:
    """Apply append-only event semantics: void events remove their target id."""
    if not path.exists():
        return []
    rows, voided = [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("event") == "void" and r.get("target_id"):
            voided.add(r["target_id"])
        else:
            rows.append(r)
    return [r for r in rows if r.get("id") not in voided]


def _data_key(data_dir: Path) -> tuple:
    files = sorted(data_dir.glob("*.json*"))
    return (str(data_dir),) + tuple((f.name, f.stat().st_mtime) for f in files)


# ── pool engine (§3.2 / §3.3) ─────────────────────────────────────────────────

def _pool_engine(snapshots: list[dict], flows: list[dict], partners: list[str]) -> dict:
    """Snapshot-driven unitized pool accounting.

    Returns {periods, members, nav_unit, total_value, last_date} where members
    maps partner -> {contributions, distributions, net_capital, pnl, balance,
    share_pct, simple_return, irr, yearly_pnl: {year: $}} and periods carry
    {date, year, opening_total, net_flow, pnl, pool_return, nav}.
    """
    # last-write-wins per DATE: re-recording an (unclosed) snapshot date is
    # the natural correction flow, and a double-submit cannot create a
    # phantom period. Events are already in append order.
    by_date: dict[str, dict] = {}
    for s in snapshots:
        if s.get("event", "snapshot") == "snapshot":
            by_date[str(s["date"])[:10]] = s
    snaps = sorted(by_date.values(), key=lambda s: str(s["date"]))
    if not snaps:
        return {"periods": [], "members": {}, "nav_unit": NAV_BASE,
                "total_value": 0.0, "last_date": None, "yearly_pnl": {},
                "quarantined": [], "orphan_flows": [], "pending_flows": []}

    quarantined: list[dict] = []
    yearly_contrib: dict[str, dict[str, float]] = {}
    yearly_distrib: dict[str, dict[str, float]] = {}
    year_end_bal: dict[str, dict[str, float]] = {}
    bal = {p: 0.0 for p in partners}
    contrib = {p: 0.0 for p in partners}
    distrib = {p: 0.0 for p in partners}
    pnl_cum = {p: 0.0 for p in partners}
    yearly_pnl: dict[str, dict[str, float]] = {}
    units = {p: 0.0 for p in partners}
    cashflow_series: dict[str, list[tuple[date, float]]] = {p: [] for p in partners}
    nav = NAV_BASE
    periods = []

    flows_by_snap: dict[str, list[dict]] = {}
    for f in flows:
        if f.get("event", "flow") != "flow":
            continue
        flows_by_snap.setdefault(str(f["snapshot_date"])[:10], []).append(f)

    prev_total = 0.0
    for snap in snaps:
        d = str(snap["date"])[:10]
        total = float(snap["total"])
        year = d[:4]
        opening = dict(bal)
        opening_total = prev_total

        net = {p: 0.0 for p in partners}
        for f in flows_by_snap.get(d, []):
            if str(f.get("counts", "")).lower() != "yes":
                continue
            p = f.get("partner")
            if p not in bal:
                # A typo'd partner must NOT crash the whole book — quarantine
                # the row and surface it as a recon red (writes are validated,
                # this guards historical/hand-edited data)
                quarantined.append({"id": f.get("id"), "partner": p,
                                    "snapshot_date": d, "amount": f.get("amount")})
                continue
            amt = float(f["amount"])
            if str(f.get("type", "")).lower() == "contribution":
                net[p] += amt
                contrib[p] += amt
                yearly_contrib.setdefault(year, {}).setdefault(p, 0.0)
                yearly_contrib[year][p] += amt
                cashflow_series[p].append((date.fromisoformat(d), -amt))
            else:
                net[p] -= amt
                distrib[p] += amt
                yearly_distrib.setdefault(year, {}).setdefault(p, 0.0)
                yearly_distrib[year][p] += amt
                cashflow_series[p].append((date.fromisoformat(d), amt))

        net_total = sum(net.values())
        period_pnl = total - prev_total - net_total

        # allocate by OPENING share; first period (opening 0) by flow share
        if opening_total > 1e-9:
            alloc_base = {p: opening[p] / opening_total for p in partners}
        else:
            base_total = net_total if abs(net_total) > 1e-9 else 1.0
            alloc_base = {p: net[p] / base_total for p in partners}

        pool_return = (period_pnl / opening_total) if opening_total > 1e-9 else 0.0
        nav = nav * (1.0 + pool_return)

        for p in partners:
            share_pnl = period_pnl * alloc_base[p]
            pnl_cum[p] += share_pnl
            yearly_pnl.setdefault(year, {}).setdefault(p, 0.0)
            yearly_pnl[year][p] += share_pnl
            bal[p] = opening[p] + net[p] + share_pnl
            if nav > 1e-9:
                units[p] += net[p] / nav       # end-of-period pricing (§3.3)

        year_end_bal[year] = dict(bal)   # last period of the year wins
        periods.append({"date": d, "year": year, "opening_total": opening_total,
                        "net_flow": net_total, "pnl": period_pnl,
                        "pool_return": pool_return, "nav": nav,
                        "closed": bool(snap.get("closed"))})
        prev_total = total

    snap_dates = {str(s["date"])[:10] for s in snaps}
    last_snap = periods[-1]["date"]
    orphans, pending = [], []
    for f in flows:
        if f.get("event", "flow") != "flow":
            continue
        if str(f.get("counts", "")).lower() != "yes":
            continue
        sd = str(f.get("snapshot_date"))[:10]
        if sd in snap_dates:
            continue
        # future-dated = pending the next reconciliation snapshot (fine);
        # past-dated orphan = silently excluded capital -> P&L poison (RED)
        (pending if sd > last_snap else orphans).append(
            {"id": f.get("id"), "snapshot_date": sd, "partner": f.get("partner"),
             "amount": f.get("amount")})

    last_date = date.fromisoformat(periods[-1]["date"])
    members = {}
    for p in partners:
        flows_p = cashflow_series[p] + ([(last_date, bal[p])] if bal[p] > 1e-9 else [])
        members[p] = {
            "contributions": round(contrib[p], 2),
            "distributions": round(distrib[p], 2),
            "net_capital": round(contrib[p] - distrib[p], 2),
            "pnl": pnl_cum[p],
            "balance": bal[p],
            "share_pct": (bal[p] / prev_total) if prev_total > 1e-9 else 0.0,
            # §3.4 Simple = P&L ÷ 净投入 (NET capital, not gross contributions)
            "simple_return": (pnl_cum[p] / (contrib[p] - distrib[p]))
                             if (contrib[p] - distrib[p]) > 1e-9 else None,
            "irr": _xirr(flows_p),
            "units": units[p],
        }
    return {"periods": periods, "members": members, "nav_unit": nav,
            "total_value": prev_total, "last_date": periods[-1]["date"],
            "yearly_pnl": yearly_pnl, "quarantined": quarantined,
            "orphan_flows": orphans, "pending_flows": pending,
            "yearly_contrib": yearly_contrib, "yearly_distrib": yearly_distrib,
            "year_end_bal": year_end_bal}


def _xirr(flows: list[tuple[date, float]]) -> float | None:
    """Excel-compatible XIRR (ACT/365) via bisection; None when undefined."""
    if len(flows) < 2:
        return None
    if not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        return None
    t0 = flows[0][0]

    def npv(rate: float) -> float:
        return sum(a / (1.0 + rate) ** ((d - t0).days / 365.0) for d, a in flows)

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-9:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


# ── yearly TWR (§3.4) ─────────────────────────────────────────────────────────

def _yearly_twr(periods: list[dict], current_year: str) -> list[dict]:
    years: dict[str, float] = {}
    for per in periods:
        y = per["year"]
        years[y] = years.get(y, 1.0) * (1.0 + per["pool_return"])
    out = []
    for y in sorted(years):
        label = f"{y} YTD" if y == current_year else y
        out.append({"period": label, "year": y, "twr": years[y] - 1.0})
    return out


# ── personal series (CXZ_ETrade / Lien_ETrade sheets) ─────────────────────────

def _personal_years(events: list[dict]) -> list[dict]:
    """Explicit year rows (migrated verbatim from the sheets' year blocks):
    {period, start, end, net_flow, incomplete} → pnl = end − start − net_flow,
    return = pnl / start. Incomplete years render None (数据不全)."""
    out = []
    for r in sorted((e for e in events if e.get("event") == "year_row"),
                    key=lambda e: e["period"]):
        if r.get("incomplete"):
            out.append({"period": r["period"], "pnl": None, "return_pct": None,
                        "incomplete": True})
            continue
        start, end = float(r["start"]), float(r["end"])
        pnl = end - start - float(r.get("net_flow") or 0.0)
        out.append({"period": r["period"], "pnl": pnl,
                    "return_pct": (pnl / start) if start > 1e-9 else None})
    return out


def _twr_since(years: list[dict], since: str) -> float | None:
    acc, seen = 1.0, False
    for y in years:
        if y.get("return_pct") is None or y["period"] < since:
            continue
        acc *= (1.0 + y["return_pct"])
        seen = True
    return (acc - 1.0) if seen else None


# ── recon checks (§SW_Reconciliation, six automated) ─────────────────────────

def _recon_checks(pool: dict, sub_pending: dict[str, float]) -> list[dict]:
    """Automated integrity checks (v3.5 SW_Reconciliation §, extended):
    the six workbook checks + quarantine/orphan guards from this engine."""
    checks = []
    members = pool["members"]
    total = pool["total_value"]

    bal_sum = sum(m["balance"] for m in members.values())
    checks.append({"name": "balances_equal_snapshot_total",
                   "ok": abs(bal_sum - total) < 0.01,
                   "detail": f"Σbalance {bal_sum:,.2f} vs snapshot {total:,.2f}"})
    share_sum = sum(m["share_pct"] for m in members.values())
    checks.append({"name": "shares_sum_100",
                   "ok": abs(share_sum - 1.0) < 1e-6 or total < 1e-9,
                   "detail": f"Σshare {share_sum:.6f}"})
    pnl_sum = sum(m["pnl"] for m in members.values())
    period_pnl_sum = sum(p["pnl"] for p in pool["periods"])
    checks.append({"name": "pnl_allocation_complete",
                   "ok": abs(pnl_sum - period_pnl_sum) < 0.01,
                   "detail": f"Σmember pnl {pnl_sum:,.2f} vs Σperiod pnl {period_pnl_sum:,.2f}"})
    neg = [p for p, m in members.items() if m["balance"] < -0.01]
    checks.append({"name": "no_negative_balances", "ok": not neg,
                   "detail": f"negative: {neg or '—'}"})
    net_cap = sum(m["net_capital"] for m in members.values())
    checks.append({"name": "summary_ties_out",
                   "ok": abs(net_cap + pnl_sum - total) < 0.01,
                   "detail": f"net capital {net_cap:,.2f} + pnl {pnl_sum:,.2f} vs value {total:,.2f}"})
    neg_sub = {k: v for k, v in sub_pending.items() if v < -0.01}
    checks.append({"name": "subaccounts_nonnegative", "ok": not neg_sub,
                   "detail": f"pending {sub_pending} (negative: {neg_sub or '—'})"})
    q = pool.get("quarantined", [])
    checks.append({"name": "no_unknown_partners", "ok": not q,
                   "detail": ("—" if not q else
                              f"{len(q)} 笔 Counts=Yes 流水的合伙人不在名单: "
                              + ", ".join(f"{r['partner']!r}({r['id']})" for r in q))})
    o = pool.get("orphan_flows", [])
    checks.append({"name": "no_orphaned_flows", "ok": not o,
                   "detail": ("—" if not o else
                              f"{len(o)} 笔 Counts=Yes 流水的快照期不存在（已被计算排除，盈亏失真）: "
                              + ", ".join(f"{r['snapshot_date']}({r['id']})" for r in o))})
    return checks


def _subaccount_pending(flows: list[dict], sub_names: list[str]) -> dict[str, float]:
    pend = {s: 0.0 for s in sub_names}
    for f in flows:
        if f.get("event", "flow") != "flow":
            continue
        amt = float(f["amount"])
        if f.get("to") in pend:
            pend[f["to"]] += amt
        if f.get("from") in pend:
            pend[f["from"]] -= amt
    return {k: round(v, 2) for k, v in pend.items()}


# ── top-level compute ─────────────────────────────────────────────────────────

def compute_book(data_dir: Path | None = None, force: bool = False) -> dict[str, Any]:
    data_dir = data_dir or DATA_DIR
    cfg_path = data_dir / "config.json"
    if not cfg_path.exists():
        return {"available": False,
                "message": "账本原生数据未初始化（data/book/ 缺 config.json）"}

    key = _data_key(data_dir)
    if not force and _cache["key"] == key and _cache["payload"] is not None:
        return _cache["payload"]

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    sw = _pool_engine(_read_events(data_dir / "sw_snapshots.jsonl"),
                      _read_events(data_dir / "sw_cashledger.jsonl"),
                      cfg["sw_partners"])
    et = _pool_engine(_read_events(data_dir / "et_snapshots.jsonl"),
                      _read_events(data_dir / "et_cashledger.jsonl"),
                      cfg["et_partners"])

    cxz_years = _personal_years(_read_events(data_dir / "cxz_etrade.jsonl"))
    lien_years = _personal_years(_read_events(data_dir / "lien_etrade.jsonl"))

    current_year = str(max((p["year"] for p in sw["periods"] + et["periods"]),
                           default=str(datetime.now().year)))

    # --- by_year (SW pool TWR + per-partner $, display alias per config) ---
    disp = cfg.get("partner_display", {})
    by_year = []
    for row in _yearly_twr(sw["periods"], current_year):
        y = row["year"]
        by_year.append({
            "period": row["period"],
            "twr": row["twr"],
            "partners": {disp.get(p, p): sw["yearly_pnl"].get(y, {}).get(p, 0.0)
                         for p in cfg["sw_partners"]},
            "total_pnl": sum(sw["yearly_pnl"].get(y, {}).values()),
        })

    # --- ET pool summary (dual basis, §3.5) ---
    merge = cfg.get("et_merge", {})
    etrade_pool = []
    for p in cfg["et_partners"]:
        m = et["members"][p]
        cost_basis = float(merge.get("cost_basis", {}).get(p, m["contributions"]))
        current_value = m["balance"]
        roi_conv = merge.get("roi_convention", {}).get(p, "pool")
        if roi_conv == "value_vs_cost_basis":
            roi = ((current_value - cost_basis) / cost_basis) if cost_basis > 1e-9 else None
        elif roi_conv == "personal_series_twr_since_2025":
            roi = _twr_since(lien_years if p == "Lien" else cxz_years, "2025")
        else:
            roi = m["simple_return"]
        etrade_pool.append({
            "name": p,
            "contributed": round(m["contributions"], 2),
            "cost_basis": round(cost_basis, 2),
            "current_value": current_value,
            "share_pct": m["share_pct"],
            "pool_pnl": m["pnl"],
            "return_on_invested": roi,
        })
    et_by_name = {p["name"]: p for p in etrade_pool}

    # --- Consolidation ---
    members = []
    for join in cfg["members"]:
        sw_m = sw["members"].get(join["sw"]) if join.get("sw") else None
        et_m = et_by_name.get(join["et"]) if join.get("et") else None
        sw_val = sw_m["balance"] if sw_m else 0.0
        et_val = et_m["current_value"] if et_m else 0.0
        tot = sw_val + et_val
        # §3.5 dual basis: Consolidation counts the ET side at PERSONAL COST
        # BASIS — CXZ's merge markup (298,551 pool basis − 207,907 personal
        # cost) is his P&L in the cross-broker view, not contributed capital.
        m_contrib = (sw_m["net_capital"] if sw_m else 0.0) + \
                    (et_m["cost_basis"] if et_m else 0.0)
        m_pnl = (sw_m["pnl"] if sw_m else 0.0) + \
                ((et_m["current_value"] - et_m["cost_basis"]) if et_m else 0.0)
        members.append({
            "name": join["display"],
            "schwab_value": sw_val,
            "etrade_value": et_val,
            "total_value": tot,
            "schwab_pct": (sw_val / tot) if tot > 1e-9 else 0.0,
            "etrade_pct": (et_val / tot) if tot > 1e-9 else 0.0,
            "contrib": round(m_contrib, 2),        # 净投入口径（SW 净 + ET 个人成本基）
            # 基金对账单标准分列：出资总额 / 分配 —— 恒等式
            # contributions_gross − distributions = contrib（净投入）
            "contributions_gross": round(
                (sw_m["contributions"] if sw_m else 0.0)
                + (et_m["cost_basis"] if et_m else 0.0), 2),
            "distributions": round(
                (sw_m["distributions"] if sw_m else 0.0), 2),
            # any merge-basis member gets the convention marker — option B
            # (basis reset to merge-date value) distorts the BLENDED simple
            # return even when contributed == cost_basis (Lien's 3.6% case)
            "dual_basis": bool(et_m),
            "return_parts": ({
                "sw_simple": (sw_m["simple_return"] if sw_m else None),
                "et_since_merge": (((et_m["current_value"] - et_m["cost_basis"])
                                    / et_m["cost_basis"])
                                   if et_m and et_m["cost_basis"] > 1e-9 else None),
            } if et_m else None),
            "pnl": m_pnl,
            "return_pct": (m_pnl / m_contrib) if m_contrib > 1e-9 else None,
        })

    sw_total, et_total = sw["total_value"], et["total_value"]
    grand = sw_total + et_total
    total_contrib = sum(m["contrib"] for m in members)
    total_pnl = sum(m["pnl"] for m in members)
    total = {
        "schwab_value": sw_total, "etrade_value": et_total, "total_value": grand,
        "schwab_pct": (sw_total / grand) if grand > 1e-9 else 0.0,
        "etrade_pct": (et_total / grand) if grand > 1e-9 else 0.0,
        "contrib": round(total_contrib, 2), "pnl": total_pnl,
        "contributions_gross": round(sum(m["contributions_gross"] for m in members), 2),
        "distributions": round(sum(m["distributions"] for m in members), 2),
        "return_pct": (total_pnl / total_contrib) if total_contrib > 1e-9 else None,
    }
    aum = {"total": grand,
           "schwab": {"value": sw_total, "pct": total["schwab_pct"]},
           "etrade": {"value": et_total, "pct": total["etrade_pct"]}}

    etrade_by_year = {"lien": lien_years, "cxz": cxz_years}

    # --- member statements ---
    member_statements = []
    for join, m in zip(cfg["members"], members):
        sw_m = sw["members"].get(join["sw"]) if join.get("sw") else None
        ccc = None
        if sw_m:
            ccc = {k: sw_m[k] for k in ("contributions", "distributions",
                                        "net_capital", "pnl", "balance",
                                        "share_pct", "simple_return", "irr")}
            ccc["by_year"] = [
                {"period": y["period"], "twr": y["twr"],
                 "pnl": y["partners"].get(disp.get(join["sw"], join["sw"]))}
                for y in by_year]
        et_block = None
        if join.get("et") and join["et"] in et_by_name:
            et_block = dict(et_by_name[join["et"]])
            et_block["by_year"] = etrade_by_year.get(join["et"].lower(), [])
        member_statements.append({
            "name": m["name"],
            "total": {"current": m["total_value"], "contrib": m["contrib"],
                      "pnl": m["pnl"], "return_pct": m["return_pct"],
                      "schwab_value": m["schwab_value"], "etrade_value": m["etrade_value"],
                      "schwab_pct": m["schwab_pct"], "etrade_pct": m["etrade_pct"]},
            "ccc": ccc,
            "etrade": et_block,
        })

    # --- native extras ---
    sub_pending = _subaccount_pending(
        _read_events(data_dir / "sw_cashledger.jsonl"), cfg.get("subaccounts", []))
    recon_checks = _recon_checks(sw, sub_pending) + [
        {**c, "name": f"et_{c['name']}"}
        for c in _recon_checks(et, {})
        if c["name"] != "subaccounts_nonnegative"]   # ET has no subaccounts

    guarantees = []
    for g in cfg.get("guarantees", []):
        floor = float(g["basis"]) * (1.0 + float(g["hurdle"]))
        # actual = beneficiary's SW balance at the LAST snapshot of the period
        # year (period-lock convention; matches the workbook's 2025 row)
        actual = None
        year_periods = [p for p in sw["periods"] if p["year"] == str(g["period"])]
        if year_periods:
            actual = _balance_at(data_dir, cfg, g["beneficiary"],
                                 year_periods[-1]["date"])
        guarantees.append({**g, "floor": round(floor, 2), "actual": actual,
                           "met": (actual is not None and actual >= floor)})

    # UI form options (SPEC-128 follow-up): dropdowns from config + observed
    # ledger values — the Counts/Type/Partner judgments stay human, the UI
    # just constrains typos.
    _all_flows = (_read_events(data_dir / "sw_cashledger.jsonl")
                  + _read_events(data_dir / "et_cashledger.jsonl"))
    _accounts = sorted({v for f in _all_flows for v in (f.get("from"), f.get("to"))
                        if v})
    _instruments = sorted({f.get("instrument") for f in _all_flows if f.get("instrument")}
                          | {"Wire", "Check", "Transfer", "Book", "Deposit"})
    form_options = {
        "partners": {"sw": cfg["sw_partners"], "et": cfg["et_partners"]},
        "accounts": _accounts,
        "instruments": _instruments,
    }

    # recent entries (void UI): last 12 rows across ledgers, newest first
    recent = []
    for fkey, fname in (("sw_snapshots", "sw_snapshots.jsonl"),
                        ("et_snapshots", "et_snapshots.jsonl"),
                        ("sw_flows", "sw_cashledger.jsonl"),
                        ("et_flows", "et_cashledger.jsonl"),
                        ("cxz", "cxz_etrade.jsonl"), ("lien", "lien_etrade.jsonl")):
        for r in _read_events(data_dir / fname):
            if r.get("recorded_at"):      # only UI-recorded rows are voidable here
                recent.append({"file": fkey, "id": r["id"],
                               "recorded_at": r["recorded_at"],
                               "summary": _row_summary(fkey, r)})
    recent.sort(key=lambda r: r["recorded_at"], reverse=True)

    # capital-flows sub-page (fund-accounting view): full enriched ledger +
    # per-pool rollforward + transit/pending zones
    def _flow_rows(pool_key: str, fname: str) -> list[dict]:
        rows = []
        for r in _read_events(data_dir / fname):
            if r.get("event", "flow") != "flow":
                continue
            rows.append({
                "pool": pool_key, "id": r.get("id"),
                "snapshot_date": r.get("snapshot_date"),
                "bank_date": r.get("bank_date"),
                "partner": disp.get(r.get("partner"), r.get("partner")) or "—",
                "from": r.get("from", ""), "to": r.get("to", ""),
                "amount": r.get("amount"), "fee": r.get("fee", 0),
                "instrument": r.get("instrument", ""),
                "counts": r.get("counts"), "type": r.get("type") or "",
                "note": r.get("note", ""), "native": bool(r.get("recorded_at")),
            })
        return rows

    all_flow_rows = (_flow_rows("SW", "sw_cashledger.jsonl")
                     + _flow_rows("ET", "et_cashledger.jsonl"))
    all_flow_rows.sort(key=lambda r: (r["snapshot_date"] or r["bank_date"] or "9999",
                                      r["id"] or ""), reverse=True)
    capital_activity = {
        "flows": all_flow_rows,
        "rollforward": {
            "sw": _rollforward(sw, cfg["sw_partners"], disp),
            "et": _rollforward(et, cfg["et_partners"], disp),
        },
        "totals": {
            "sw": {"contributions": sum(m["contributions"] for m in sw["members"].values()),
                   "distributions": sum(m["distributions"] for m in sw["members"].values())},
            "et": {"contributions": sum(m["contributions"] for m in et["members"].values()),
                   "distributions": sum(m["distributions"] for m in et["members"].values())},
        },
        "pending_flows": sw.get("pending_flows", []) + et.get("pending_flows", []),
        "subaccounts": sub_pending,
        # (17) 在途构成：组成子账户 pending 的中转腿
        "transit_legs": [f for f in all_flow_rows if f["counts"] != "Yes"],
        "fees": {
            "sw": round(sum(float(f.get("fee") or 0) for f in all_flow_rows if f["pool"] == "SW"), 2),
            "et": round(sum(float(f.get("fee") or 0) for f in all_flow_rows if f["pool"] == "ET"), 2),
        },
    }

    payload = {
        "available": True,
        "source": "native",
        "form_options": form_options,
        "recent_entries": recent[:12],
        "capital_activity": capital_activity,
        "source_detail": f"native engine · data/book ({len(sw['periods'])} SW + {len(et['periods'])} ET periods)",
        "members": members,
        "total": total,
        "aum": aum,
        "by_year": by_year,
        "etrade_pool": etrade_pool,
        "etrade_by_year": etrade_by_year,
        "member_statements": member_statements,
        "reconciled": {
            "schwab_ccc354": ({"date": sw["last_date"], "value": sw_total}
                              if sw["last_date"] else None),
            "etrade_pm": ({"date": et["last_date"], "value": et_total}
                          if et["last_date"] else None),
        },
        # (11) 期间明细：每快照期的 总值/净流/倒挤盈亏/期间收益/NAV/关账
        "pool_periods": {"sw": sw["periods"], "et": et["periods"]},
        "recon_checks": recon_checks,
        "recon_all_green": all(c["ok"] for c in recon_checks),
        "guarantees": guarantees,
        "subaccounts": sub_pending,
        "nav_unit": {"sw": sw["nav_unit"], "et": et["nav_unit"]},
    }
    _cache["key"] = key
    _cache["payload"] = payload
    return payload


def _rollforward(pool: dict, partners: list[str], display: dict) -> list[dict]:
    last_date = pool.get("last_date") or ""
    open_year = last_date[:4]
    """Capital account rollforward (基金会计标准表): per year × partner —
    opening capital + contributions − distributions + allocated P&L = closing.
    The identity is asserted per cell (engine-level integrity, ±$0.01)."""
    years = sorted(pool.get("year_end_bal", {}))
    out = []
    prev_close = {p: 0.0 for p in partners}
    for y in years:
        rows = []
        for p in partners:
            opening = prev_close[p]
            c = pool.get("yearly_contrib", {}).get(y, {}).get(p, 0.0)
            dd = pool.get("yearly_distrib", {}).get(y, {}).get(p, 0.0)
            pnl = pool.get("yearly_pnl", {}).get(y, {}).get(p, 0.0)
            closing = pool["year_end_bal"][y].get(p, 0.0)
            identity_ok = abs(opening + c - dd + pnl - closing) < 0.01
            rows.append({"partner": display.get(p, p), "opening": opening,
                         "contributions": c, "distributions": dd, "pnl": pnl,
                         "closing": closing, "identity_ok": identity_ok})
            prev_close[p] = closing
        out.append({
            "year": y,
            "label": (f"{y} YTD（至 {last_date[5:]}）" if y == open_year else y),
            "rows": rows,
            "totals": {k: sum(r[k] for r in rows)
                       for k in ("opening", "contributions", "distributions",
                                 "pnl", "closing")},
            "identity_ok": all(r["identity_ok"] for r in rows),
        })
    return out


def _row_summary(fkey: str, r: dict) -> str:
    if "snapshots" in fkey:
        return f"快照 {r.get('date')} = ${r.get('total'):,.2f}"
    if "flows" in fkey:
        return (f"{r.get('snapshot_date')} {r.get('partner') or '—'} "
                f"{r.get('from')}→{r.get('to')} ${r.get('amount'):,.2f} "
                f"[{r.get('counts')}/{r.get('type') or '—'}]")
    return f"{r.get('event')} {r.get('month') or r.get('period')} {r.get('value', '')}"


def _balance_at(data_dir: Path, cfg: dict, partner: str, upto_date: str) -> float | None:
    """Partner's SW balance as of a snapshot date — focused replay of the pool
    truncated at that date (inputs are tiny; replay is cheap and exact)."""
    flows = _read_events(data_dir / "sw_cashledger.jsonl")
    snapshots = _read_events(data_dir / "sw_snapshots.jsonl")
    partial_snaps = [s for s in snapshots
                     if s.get("event", "snapshot") == "snapshot"
                     and str(s["date"])[:10] <= upto_date]
    if not partial_snaps:
        return None
    sub = _pool_engine(partial_snaps, flows, cfg["sw_partners"])
    m = sub["members"].get(partner)
    return m["balance"] if m else None


# ── write API (append-only; SPEC-128 §4) ─────────────────────────────────────

_WRITE_LOCK = threading.Lock()   # single-user tool, but waitress is threaded


def _next_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def _append(path: Path, row: dict) -> None:
    for k, v in row.items():
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"book: non-finite {k}={v} refused (strict-JSON)")
    with _WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


_POOL_FILES = {"sw": ("sw_snapshots.jsonl", "sw_cashledger.jsonl"),
               "et": ("et_snapshots.jsonl", "et_cashledger.jsonl")}
_SERIES_FILES = {"cxz": "cxz_etrade.jsonl", "lien": "lien_etrade.jsonl"}


def _last_closed_date(data_dir: Path, pool: str) -> str | None:
    snaps = _read_events(data_dir / _POOL_FILES[pool][0])
    closed = [str(s["date"])[:10] for s in snaps
              if s.get("event", "snapshot") == "snapshot" and s.get("closed")]
    return max(closed) if closed else None


def _assert_period_open(data_dir: Path, pool: str, date_str: str) -> None:
    """Period-lock (v3.5 §8): reconciled history is immutable. Any write dated
    at or BEFORE the last closed snapshot would silently re-segment locked
    periods and change historical P&L — refuse."""
    last = _last_closed_date(data_dir, pool)
    if last is not None and date_str <= last:
        raise ClosedPeriodError(
            f"{date_str} 在已关账期内（最后关账 {last}）——历史更正请用新分录，不改锁定期")


class ClosedPeriodError(ValueError):
    """Write targets a snapshot period marked Closed? (period-lock, v3.5 §8)."""


def record_snapshot(pool: str, date_str: str, total: float, note: str = "",
                    data_dir: Path | None = None) -> dict:
    data_dir = data_dir or DATA_DIR
    if pool not in _POOL_FILES:
        raise ValueError(f"unknown pool {pool!r}")
    total = float(total)
    if not math.isfinite(total) or total < 0:
        raise ValueError(f"snapshot total must be a finite non-negative number, got {total}")
    try:
        date.fromisoformat(date_str)
    except ValueError:
        raise ValueError(f"invalid date {date_str!r}")
    _assert_period_open(data_dir, pool, date_str)
    row = {"id": _next_id(f"{pool}snap"), "event": "snapshot", "date": date_str,
           "total": float(total), "note": note, "closed": False,
           "recorded_at": datetime.now().isoformat(timespec="seconds")}
    _append(data_dir / _POOL_FILES[pool][0], row)
    return row


def record_flow(pool: str, payload: dict, data_dir: Path | None = None) -> dict:
    data_dir = data_dir or DATA_DIR
    if pool not in _POOL_FILES:
        raise ValueError(f"unknown pool {pool!r}")
    snap_date = str(payload["snapshot_date"])[:10]
    try:
        date.fromisoformat(snap_date)
    except ValueError:
        raise ValueError(f"invalid snapshot_date {snap_date!r}")
    _assert_period_open(data_dir, pool, snap_date)
    counts = str(payload.get("counts", "")).strip().capitalize()
    ftype = str(payload.get("type", "")).strip().capitalize()
    if counts not in ("Yes", "No"):
        raise ValueError("counts must be Yes/No")
    if counts == "Yes" and ftype not in ("Contribution", "Distribution"):
        raise ValueError("type must be Contribution/Distribution when counts=Yes")
    amount = float(payload["amount"])
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError(f"amount must be positive (ledger convention: 金额恒正，方向由 Type 决定), got {amount}")
    if counts == "Yes":
        cfg_path = data_dir / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
        allowed = cfg.get(f"{pool}_partners", [])
        if allowed and payload.get("partner") not in allowed:
            raise ValueError(
                f"partner {payload.get('partner')!r} 不在 {pool.upper()} 合伙人名单 {allowed}"
                "（Counts=Yes 必须归属到已知合伙人）")
        # 快照期不存在时提示（未来期 = 待对账，合法；不匹配任何已有快照且早于
        # 最后快照 = 会被引擎排除 -> 直接拒绝，防孤儿）
        snaps = _read_events(data_dir / _POOL_FILES[pool][0])
        snap_dates = {str(s["date"])[:10] for s in snaps
                      if s.get("event", "snapshot") == "snapshot"}
        if snap_dates and snap_date not in snap_dates and snap_date <= max(snap_dates):
            raise ValueError(
                f"快照期 {snap_date} 不存在（已有快照最晚 {max(snap_dates)}）——"
                "Counts=Yes 流水必须归属已有快照期或未来对账期，否则会被计算排除")
    row = {"id": _next_id(f"{pool}flow"), "event": "flow",
           "snapshot_date": snap_date,
           "bank_date": str(payload.get("bank_date") or snap_date)[:10],
           "partner": payload["partner"], "from": payload.get("from", ""),
           "to": payload.get("to", ""), "amount": float(payload["amount"]),
           "fee": float(payload.get("fee") or 0.0),
           "instrument": payload.get("instrument", ""),
           "counts": counts, "type": ftype, "note": payload.get("note", ""),
           "recorded_at": datetime.now().isoformat(timespec="seconds")}
    _append(data_dir / _POOL_FILES[pool][1], row)
    return row


def record_series_event(series: str, payload: dict, data_dir: Path | None = None) -> dict:
    data_dir = data_dir or DATA_DIR
    if series not in _SERIES_FILES:
        raise ValueError(f"unknown series {series!r}")
    ev = payload.get("event")
    if ev not in ("mark", "year_row"):
        raise ValueError("event must be mark/year_row")
    row = {"id": _next_id(series), **payload,
           "recorded_at": datetime.now().isoformat(timespec="seconds")}
    _append(data_dir / _SERIES_FILES[series], row)
    return row


def record_void(file_key: str, target_id: str, note: str,
                data_dir: Path | None = None) -> dict:
    data_dir = data_dir or DATA_DIR
    all_files = {**{f"{k}_snapshots": v[0] for k, v in _POOL_FILES.items()},
                 **{f"{k}_flows": v[1] for k, v in _POOL_FILES.items()},
                 **_SERIES_FILES}
    if file_key not in all_files:
        raise ValueError(f"unknown file {file_key!r} (one of {sorted(all_files)})")
    row = {"id": _next_id("void"), "event": "void", "target_id": target_id,
           "note": note, "recorded_at": datetime.now().isoformat(timespec="seconds")}
    _append(data_dir / all_files[file_key], row)
    return row
