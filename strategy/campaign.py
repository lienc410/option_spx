"""SPEC-127 §1 — Campaign 双层记账（diagonal roll accounting）.

Campaign（战役）= 长腿的生命周期。开仓创建 campaign_id（默认 = 自身 trade id）；
每次 roll = 一个 cycle；长腿平掉/到期则 campaign 结束。一个 campaign 可以跨多个
trade_id（Schwab + E-Trade 双仓、加仓 tranche 共享同一长腿生命周期）。

双层：
  Cycle 层  — 第 0 行 = 初始建仓（debit）；其后每行一个 roll（旧短腿平仓 cost、
              新短腿开仓 credit、该 cycle 实现额、持有天数）；平仓行收尾。
  Campaign 层 — 英雄指标 Adjusted Basis = 初始 debit − 累计短腿净收入；
              Campaign Net = 全部现金流 Σ + 未平 legs 现值；ROI = Net / 初始 debit。

现金流符号约定（与 ledger / closed_trades 一致）：
  open.actual_premium — signed credit received（debit 为负，e.g. −411）
  roll.closed_short.price — 买回旧短腿的 per-share cost（正 = 付出）
  roll.new_short.price   — 卖出新短腿的 per-share credit（正 = 收到）
  roll_net_credit = new_short.price − closed_short.price
  close.exit_premium — signed cost to close（debit 平仓收钱 → 负）

恒等式（AC-3，构建时断言）：
  adjusted_basis_usd == initial_debit_usd − Σ(roll cycle realized_usd)
"""
from __future__ import annotations

import math
from datetime import date


def _num(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _day(ts: str | None) -> str | None:
    if not ts:
        return None
    return str(ts)[:10]


def _days_between(a: str | None, b: str | None) -> int | None:
    try:
        return (date.fromisoformat(str(b)[:10]) - date.fromisoformat(str(a)[:10])).days
    except (TypeError, ValueError):
        return None


def current_short_leg(resolved: dict) -> dict:
    """Current short leg of a resolved trade: last roll's new_short wins over
    the open event's original short. entry_price = the credit collected when
    THIS short leg was sold (known for rolled cycles; for cycle 0 only when
    the open recorded a per-leg fill — legs[].entry_price / short_entry_price)."""
    o = resolved.get("open") or {}
    rolls = resolved.get("rolls") or []
    if rolls:
        ns = rolls[-1].get("new_short") or {}
        return {
            "strike": _num(ns.get("strike")),
            "expiry": ns.get("expiry"),
            "entry_price": _num(ns.get("price")),
            "since": _day(rolls[-1].get("timestamp")),
        }
    entry_price = _num(o.get("short_entry_price"))
    if entry_price is None:
        for leg in o.get("legs") or []:
            if isinstance(leg, dict) and leg.get("side") == "short":
                entry_price = _num(leg.get("entry_price"))
                break
    return {
        "strike": _num(o.get("short_strike")),
        "expiry": o.get("expiry"),
        "entry_price": entry_price,
        "since": _day(o.get("timestamp")) or o.get("opened_at"),
    }


def trade_roll_income_usd(resolved: dict) -> float:
    """Σ roll net credits of one member trade, in dollars."""
    o = resolved.get("open") or {}
    contracts = _num(o.get("contracts")) or 1.0
    total = 0.0
    for r in resolved.get("rolls") or []:
        net = _num(r.get("roll_net_credit"))
        if net is None:
            ns, cs = r.get("new_short") or {}, r.get("closed_short") or {}
            np_, cp = _num(ns.get("price")), _num(cs.get("price"))
            net = (np_ - cp) if (np_ is not None and cp is not None) else None
        if net is not None:
            n = _num(r.get("contracts")) or contracts
            total += net * 100.0 * n
    return total


def _member_cycles(resolved: dict) -> list[dict]:
    """Cycle rows for one member trade (rows carry the member trade_id)."""
    o = resolved.get("open") or {}
    c = resolved.get("close")
    tid = resolved.get("id")
    contracts = _num(o.get("contracts")) or 1.0
    entry_prem = _num(o.get("actual_premium"))
    opened = _day(o.get("timestamp")) or o.get("opened_at")

    rows: list[dict] = []
    rolls = resolved.get("rolls") or []
    # Row 0 — 初始建仓（debit）
    rows.append({
        "cycle": 0,
        "kind": "open",
        "trade_id": tid,
        "date": opened,
        "short_strike": _num(o.get("short_strike")),
        "short_expiry": o.get("expiry"),
        "long_strike": _num(o.get("long_strike")),
        "long_expiry": o.get("long_expiry") or o.get("expiry"),
        "contracts": contracts,
        "cashflow_usd": (entry_prem * 100.0 * contracts) if entry_prem is not None else None,
        "realized_usd": None,
        "days_held": None,  # filled below once the next boundary is known
    })
    prev_date = opened
    for k, r in enumerate(rolls, start=1):
        ns, cs = r.get("new_short") or {}, r.get("closed_short") or {}
        rdate = _day(r.get("timestamp"))
        net = _num(r.get("roll_net_credit"))
        if net is None:
            np_, cp = _num(ns.get("price")), _num(cs.get("price"))
            net = (np_ - cp) if (np_ is not None and cp is not None) else None
        n = _num(r.get("contracts")) or contracts
        rows[-1]["days_held"] = _days_between(prev_date, rdate)
        rows.append({
            "cycle": k,
            "kind": "roll",
            "trade_id": tid,
            "date": rdate,
            "closed_short_strike": _num(cs.get("strike")),
            "closed_short_expiry": cs.get("expiry"),
            "closed_short_price": _num(cs.get("price")),
            "short_strike": _num(ns.get("strike")),
            "short_expiry": ns.get("expiry"),
            "new_short_price": _num(ns.get("price")),
            "contracts": n,
            "cashflow_usd": (net * 100.0 * n) if net is not None else None,
            "realized_usd": (net * 100.0 * n) if net is not None else None,
            "days_held": None,
        })
        prev_date = rdate
    if c is not None:
        cdate = _day(c.get("timestamp"))
        exit_prem = _num(c.get("exit_premium"))
        pnl = _num(c.get("actual_pnl"))
        if pnl is None and entry_prem is not None and exit_prem is not None:
            pnl = (entry_prem - exit_prem) * 100.0 * contracts
        rows[-1]["days_held"] = _days_between(prev_date, cdate)
        rows.append({
            "cycle": len(rolls) + 1,
            "kind": "close",
            "trade_id": tid,
            "date": cdate,
            "exit_reason": c.get("exit_reason"),
            "contracts": contracts,
            "cashflow_usd": (-exit_prem * 100.0 * contracts) if exit_prem is not None else None,
            "realized_usd": pnl,
            "days_held": None,
        })
    return rows


def build_campaigns(resolved_trades: list[dict], *, include_voided: bool = False,
                    today: str | None = None) -> list[dict]:
    """Group resolved trades into campaigns and compute the two-layer view.

    AC-3: adjusted basis is accumulated directly from roll events AND
    re-derived from the cycle rows; the two must agree (loud assert)."""
    groups: dict[str, list[dict]] = {}
    for t in resolved_trades:
        if t.get("voided") and not include_voided:
            continue
        if not t.get("open"):
            continue
        cid = t.get("campaign_id") or (t.get("open") or {}).get("campaign_id") or t.get("id")
        groups.setdefault(str(cid), []).append(t)

    out: list[dict] = []
    for cid, members in sorted(groups.items()):
        members = sorted(members, key=lambda t: str(t.get("id")))
        opens = [m["open"] for m in members]
        initial_debit = 0.0     # dollars, positive for debit structures
        roll_income = 0.0       # dollars
        realized_closed = 0.0   # dollars, Σ closed members' close pnl (excl. roll income)
        contracts_total = 0.0
        cycles: list[dict] = []
        any_open = False
        paper = all(bool(m.get("paper_trade")) for m in members)
        for m in members:
            o = m["open"]
            n = _num(o.get("contracts")) or 1.0
            contracts_total += n
            ep = _num(o.get("actual_premium"))
            if ep is not None:
                initial_debit += -ep * 100.0 * n  # debit(-) → positive cost
            roll_income += trade_roll_income_usd(m)
            if m.get("close") is None:
                any_open = True
            else:
                pnl = _num((m.get("close") or {}).get("actual_pnl"))
                if pnl is None:
                    xp = _num((m.get("close") or {}).get("exit_premium"))
                    if ep is not None and xp is not None:
                        pnl = (ep - xp) * 100.0 * n
                if pnl is not None:
                    realized_closed += pnl
            cycles.extend(_member_cycles(m))
        cycles.sort(key=lambda r: (str(r.get("date") or ""), r.get("cycle") or 0))

        adjusted_basis = initial_debit - roll_income
        # AC-3 identity — independent re-derivation from the cycle rows.
        cycle_roll_sum = sum(r["realized_usd"] for r in cycles
                             if r.get("kind") == "roll" and r.get("realized_usd") is not None)
        if not math.isclose(adjusted_basis, initial_debit - cycle_roll_sum,
                            rel_tol=1e-9, abs_tol=0.01):
            raise AssertionError(
                f"SPEC-127 AC-3 identity violated for campaign {cid}: "
                f"adjusted_basis={adjusted_basis:.2f} vs "
                f"initial−Σcycles={initial_debit - cycle_roll_sum:.2f}")

        realized_total = realized_closed + roll_income
        status = "open" if any_open else "closed"
        n_rolls = sum(len(m.get("rolls") or []) for m in members)
        # n_cycles = 当前是第几个短腿周期（badge 语义）：双仓同步 roll 一次是
        # cycle 2，不是 3 —— 取 member 维度的最大值；n_rolls 仍是事件总数。
        n_cycles = 1 + max((len(m.get("rolls") or []) for m in members), default=0)
        # 长腿 / 当前短腿（open member 优先；closed campaign 用最后状态）
        ref = next((m for m in members if m.get("close") is None), members[-1])
        ref_open = ref["open"]
        cur_short = current_short_leg(ref)
        today = today or date.today().isoformat()
        long_expiry = ref_open.get("long_expiry") or ref_open.get("expiry")

        camp = {
            "campaign_id": cid,
            "strategy_key": ref_open.get("strategy_key"),
            "strategy": ref_open.get("strategy"),
            "underlying": ref_open.get("underlying"),
            "paper_trade": paper,
            "status": status,
            "members": [m["id"] for m in members],
            "accounts": sorted({str((m["open"] or {}).get("account") or "schwab") for m in members}),
            "opened_at": min((_day(o.get("timestamp")) or o.get("opened_at") or "") for o in opens) or None,
            "closed_at": (max((_day((m.get("close") or {}).get("timestamp")) or "")
                              for m in members) or None) if status == "closed" else None,
            "contracts_total": contracts_total,
            "n_cycles": n_cycles,
            "n_rolls": n_rolls,
            "initial_debit_usd": round(initial_debit, 2),
            "roll_income_usd": round(roll_income, 2),
            "adjusted_basis_usd": round(adjusted_basis, 2),
            "realized_usd": round(realized_total, 2),
            "long_strike": _num(ref_open.get("long_strike")),
            "long_expiry": long_expiry,
            "long_dte": _days_between(today, long_expiry),
            "short_strike": cur_short.get("strike"),
            "short_expiry": cur_short.get("expiry"),
            "short_dte": _days_between(today, cur_short.get("expiry")) if status == "open" else None,
            "short_entry_price": cur_short.get("entry_price"),
            "cycles": cycles,
        }
        if status == "closed" and initial_debit > 0:
            camp["campaign_net_usd"] = round(realized_total, 2)
            camp["campaign_roi"] = round(realized_total / initial_debit, 4)
        _assert_finite(camp)
        out.append(camp)
    return out


def _assert_finite(obj, path: str = "campaign") -> None:
    """No NaN/Inf may reach the browser (json.dumps would emit literals that
    break fetch().json())."""
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError(f"non-finite value at {path}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_finite(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_finite(v, f"{path}[{i}]")
