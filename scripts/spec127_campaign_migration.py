#!/usr/bin/env python3
"""SPEC-127 AC-6 — ledger 迁移：既有 BCD 交易回填 campaign_id 与 legs。

Ledger 是 append-only：迁移只追加 correction 事件（target_event=open），不改
任何历史行。resolve_log() 会把 correction fields 合并进 resolved open。

分组规则（campaign = 长腿的生命周期）：
  同 strategy_key=bull_call_diagonal、同 long_strike、同 long_expiry、同开仓日
  的非 void 交易共享一个 campaign（PM 的双仓 = Schwab + E-Trade 各一 trade_id，
  同日同结构 → 首个 campaign）。campaign_id = 组内最小 trade_id。

long_expiry 解析顺序：resolved open（含既有 correction）→ data/closed_trades.jsonl
同 trade_id 行（H-3 修正过的平仓行带 long_expiry）→ 短腿 expiry（vertical 兜底，
但此时会在输出里标注 WARN）。

幂等：resolved open 已带 campaign_id 的交易直接跳过；重复运行零追加。

用法：
  python3 scripts/spec127_campaign_migration.py            # dry-run（只打印计划）
  python3 scripts/spec127_campaign_migration.py --apply    # 追加 correction 事件
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BCD_KEY = "bull_call_diagonal"
ET = ZoneInfo("America/New_York")


def _closed_trades_long_expiry() -> dict[str, str]:
    """trade_id -> long_expiry from data/closed_trades.jsonl (H-3 corrected rows)."""
    out: dict[str, str] = {}
    path = ROOT / "data" / "closed_trades.jsonl"
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        tid, le = r.get("trade_id"), r.get("long_expiry")
        if tid and le:
            out[str(tid)] = str(le)
    return out


def build_plan() -> list[dict]:
    from logs.trade_log_io import resolve_log

    le_lookup = _closed_trades_long_expiry()
    bcd = []
    for t in resolve_log():
        o = t.get("open") or {}
        if t.get("voided") or o.get("strategy_key") != BCD_KEY:
            continue
        bcd.append(t)

    # 分组：同开仓日 + 同长腿
    groups: dict[tuple, list[dict]] = {}
    for t in bcd:
        o = t["open"]
        opened = (str(o.get("timestamp") or "")[:10]) or str(o.get("opened_at") or "")
        long_expiry = (o.get("long_expiry")
                       or le_lookup.get(str(t["id"]))
                       or None)
        key = (opened, str(o.get("long_strike")), str(long_expiry))
        groups.setdefault(key, []).append(t)

    plan: list[dict] = []
    for key, members in sorted(groups.items()):
        campaign_id = min(str(m["id"]) for m in members)
        for m in members:
            o = m["open"]
            existing = o.get("campaign_id")
            long_expiry = (o.get("long_expiry") or le_lookup.get(str(m["id"])))
            warn = None
            if not long_expiry:
                long_expiry = o.get("expiry")
                warn = "long_expiry unresolved — fell back to short expiry (vertical?)"
            fields: dict = {}
            if not existing:
                fields["campaign_id"] = campaign_id
            if not o.get("legs"):
                fields["legs"] = [
                    {"side": "short", "strike": o.get("short_strike"), "expiry": o.get("expiry")},
                    {"side": "long", "strike": o.get("long_strike"), "expiry": long_expiry},
                ]
            if not o.get("long_expiry") and long_expiry and long_expiry != o.get("expiry"):
                fields["long_expiry"] = long_expiry
            plan.append({
                "trade_id": m["id"],
                "campaign_id": existing or campaign_id,
                "group_key": key,
                "closed": m.get("close") is not None,
                "close_reason": (m.get("close") or {}).get("exit_reason"),
                "fields": fields,
                "skip": not fields,
                "warn": warn,
            })
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SPEC-127 campaign_id/legs backfill")
    ap.add_argument("--apply", action="store_true", help="追加 correction 事件（缺省 dry-run）")
    args = ap.parse_args(argv)

    plan = build_plan()
    if not plan:
        print("no BCD trades in ledger — nothing to migrate")
        return 0

    n_apply = 0
    for p in plan:
        tag = "SKIP (already migrated)" if p["skip"] else ("APPLY" if args.apply else "PLAN")
        closed = f" closed({p['close_reason']})" if p["closed"] else " open"
        warn = f"  WARN: {p['warn']}" if p.get("warn") else ""
        print(f"[{tag}] {p['trade_id']} -> campaign {p['campaign_id']}{closed}"
              f" fields={sorted(p['fields'])}{warn}")
        if p["skip"] or not args.apply:
            continue
        from logs.trade_log_io import append_event
        append_event({
            "id": p["trade_id"],
            "event": "correction",
            "timestamp": datetime.now(ET).isoformat(timespec="seconds"),
            "target_event": "open",
            "fields": p["fields"],
            "reason": "SPEC-127 migration: campaign_id/legs backfill (append-only)",
        })
        n_apply += 1

    if args.apply:
        print(f"\napplied {n_apply} correction event(s)")
        # 迁移后校验：campaign 构建不抛错 + 恒等式通过
        from logs.trade_log_io import resolve_log
        from strategy.campaign import build_campaigns
        camps = [c for c in build_campaigns(resolve_log())
                 if c.get("strategy_key") == BCD_KEY]
        for c in camps:
            print(f"  campaign {c['campaign_id']}: members={c['members']} "
                  f"status={c['status']} debit=${c['initial_debit_usd']:,.0f} "
                  f"roll_income=${c['roll_income_usd']:,.0f} "
                  f"adjusted_basis=${c['adjusted_basis_usd']:,.0f} "
                  f"realized=${c['realized_usd']:,.0f}")
    else:
        pending = sum(1 for p in plan if not p["skip"])
        print(f"\ndry-run: {pending} correction event(s) would be appended "
              f"(re-run with --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
