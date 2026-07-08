"""Q092 P0 — 合成治理栈重放(BP-utilization reaudit ④)。

Question: SPEC-084 J3 sizing + BP ceilings(35/50%)+ SPEC-111 现金闸门
(60% cap / $30k floor / bcd_max_debit $22k)叠加后,历史交易流里**哪道约束
在什么时候咬住、咬掉多少 PnL**?——每层各自验证过,合成系统从未整体跑过
(reaudit §3.4)。

Method(不改引擎):标准回测(account $500k canonical,引擎已含 SPEC-084
bp_targets + ceilings + bcd_max_debit)吐出的交易流按时间重放,叠 SPEC-111
现金闸门,语义对齐生产:

    liquid(t) = P0 − Σ active_debit_commitments(t)      # 付掉的 debit 即离池
    入场时:liquid < $30k floor            → BLOCK
           committed + need > 60% × liquid → BLOCK
    离场时:debit 返还 + realized PnL 不回池(PM 现金调度不可知,取平稳保守假设)

现金池 P0 网格 {37k, 90k, 152k, 250k}(37k=Q081 证据基,152k=今天,其余插值)。
Credit 策略不吃现金、不过此闸(BPS/IC/BCS 全通过)——它们的约束是 BP ceiling,
由引擎内生,报告其余量。

Output: research/q092/q092_p0_replay.csv + 终端摘要。
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "research" / "q092"
ACCOUNT = 500_000.0
POOL_GRID = [37_000.0, 90_000.0, 152_000.0, 250_000.0]
CAP_PCT = 0.60
FLOOR = 30_000.0
WINDOWS = [("3y", "2023-01-01"), ("19y", "2007-01-01")]


def _is_debit(t) -> bool:
    return float(getattr(t, "entry_credit", 0.0) or 0.0) > 0


def _cash_need(t) -> float:
    return abs(float(t.entry_credit)) * 100.0 * float(t.contracts)


def replay(trades, pool0: float) -> dict:
    """Chronological SPEC-111 gate replay over the debit subset."""
    seq = sorted(trades, key=lambda t: (str(t.entry_date), str(t.exit_date)))
    active: list[tuple[str, float]] = []   # (exit_date, cash_need)
    blocked_floor = blocked_cap = passed = 0
    pnl_foregone = 0.0
    committed_path = []
    for t in seq:
        if not _is_debit(t):
            continue
        d = str(t.entry_date)
        active = [(x, c) for x, c in active if x >= d]
        committed = sum(c for _, c in active)
        liquid = pool0 - committed
        need = _cash_need(t)
        committed_path.append(committed)
        if liquid < FLOOR:
            blocked_floor += 1
            pnl_foregone += float(t.exit_pnl)
            continue
        if committed + need > CAP_PCT * liquid:
            blocked_cap += 1
            pnl_foregone += float(t.exit_pnl)
            continue
        passed += 1
        active.append((str(t.exit_date), need))
    n_debit = passed + blocked_floor + blocked_cap
    return {
        "pool0": pool0,
        "debit_trades": n_debit,
        "passed": passed,
        "blocked_floor": blocked_floor,
        "blocked_cap": blocked_cap,
        "blocked_pct": round((blocked_floor + blocked_cap) / n_debit * 100.0, 1) if n_debit else 0.0,
        "pnl_foregone_usd": round(pnl_foregone, 0),
        "max_committed": round(max(committed_path), 0) if committed_path else 0.0,
    }


def bp_side_report(trades) -> dict:
    """BP ceiling slack — daily concurrent total_bp from the engine's trades."""
    daily = defaultdict(float)
    for t in trades:
        d0, d1 = date.fromisoformat(str(t.entry_date)), date.fromisoformat(str(t.exit_date))
        cur = d0
        while cur <= d1:
            daily[cur] += float(t.total_bp)
            cur = date.fromordinal(cur.toordinal() + 1)
    if not daily:
        return {}
    vals = sorted(daily.values())
    return {
        "peak_bp_pct": round(max(vals) / ACCOUNT * 100.0, 1),
        "p95_bp_pct": round(vals[int(0.95 * (len(vals) - 1))] / ACCOUNT * 100.0, 1),
        "avg_bp_pct": round(sum(vals) / len(vals) / ACCOUNT * 100.0, 1),
    }


def main() -> int:
    from backtest.engine import run_backtest
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, start in WINDOWS:
        trades, metrics, _ = run_backtest(start_date=start, verbose=False,
                                          account_size=ACCOUNT)
        total_pnl = sum(float(t.exit_pnl) for t in trades)
        n_debit = sum(1 for t in trades if _is_debit(t))
        debit_pnl = sum(float(t.exit_pnl) for t in trades if _is_debit(t))
        bp = bp_side_report(trades)
        print(f"\n=== {label} ({start}→) — {len(trades)} trades, "
              f"debit {n_debit} (PnL ${debit_pnl:,.0f} of ${total_pnl:,.0f}) ===")
        print(f"BP side: peak {bp.get('peak_bp_pct')}% / p95 {bp.get('p95_bp_pct')}% "
              f"/ avg {bp.get('avg_bp_pct')}% of ${ACCOUNT:,.0f} "
              f"(ceilings 35/50%)")
        for pool0 in POOL_GRID:
            r = replay(trades, pool0)
            r["window"] = label
            r["total_pnl"] = round(total_pnl, 0)
            r["debit_pnl"] = round(debit_pnl, 0)
            r.update({f"bp_{k}": v for k, v in bp.items()})
            rows.append(r)
            print(f"pool ${pool0:>8,.0f}: debit {r['passed']}/{r['debit_trades']} pass, "
                  f"blocked floor={r['blocked_floor']} cap={r['blocked_cap']} "
                  f"({r['blocked_pct']}%), PnL foregone ${r['pnl_foregone_usd']:>10,.0f}, "
                  f"max committed ${r['max_committed']:,.0f}")
    with (OUT / "q092_p0_replay.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
