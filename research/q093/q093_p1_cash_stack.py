"""Q093 P1 — Q042 crash-day 现金叠加重放(SPEC-111 pool × Sleeve A 触发流)。

Question: Q042 Sleeve A(生产 cap 12.5% × NLV,debit,不在 SPEC-111 universe)
的触发日现金需求叠加到 SPEC-111 现金池上,历史上会产生多少次冲突?
——Q092 reaudit ④「合成栈自洽」未覆盖此角(audit 2026-07-07 P1 #4)。

Method: 复用 Q092 P0 重放语义(liquid = P0 − committed;floor $30k;
cap 60%)。主引擎 debit 流(canonical $500k)+ Q042 Sleeve A 触发流
(data/q042_backtest_trades.csv,SPEC-094.1 D30 结构,n=35)按时间合成。

两个情景:
  S-EXO(今日现实):Q042 不受任何闸门,触发即吃池;测它对主 debit 流的
    挤出(新增 block / PnL foregone vs Q092 基线)+ 池透支事件
    (need > liquid,即必须 crash-day 卖 QQQ/SGOV 才能成交)。
  S-GOV(纳入治理反事实):Q042 与主 debit 同过 floor/cap 闸;测 Q042
    被挡笔数与 overlay PnL foregone。

Q042 单笔需求双口径:canonical 12.5%×$500k=$62.5k;
today-scale 12.5%×$629k(2026-07-07 executor 实测 Schwab NLV)=$78.6k。
Sleeve B 生产 cap 0%,不入流。

Output: research/q093/q093_p1_cash_stack.csv + 终端摘要。
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "research" / "q093"
Q042_CSV = ROOT / "data" / "q042_backtest_trades.csv"

ACCOUNT = 500_000.0
POOL_GRID = [37_000.0, 90_000.0, 152_000.0, 250_000.0]
CAP_PCT = 0.60
FLOOR = 30_000.0
WINDOWS = [("3y", "2023-01-01"), ("19y", "2007-01-01")]
Q042_NEED_VARIANTS = [("canonical_62.5k", 62_500.0), ("today_78.6k", 78_600.0)]


@dataclass
class Item:
    entry_date: str
    exit_date: str
    need: float          # cash committed while active (0 for credit trades)
    pnl: float           # realized PnL if entered (production-scaled for Q042)
    kind: str            # "main_debit" | "q042"


def _is_debit(t) -> bool:
    return float(getattr(t, "entry_credit", 0.0) or 0.0) > 0


def _main_items(trades) -> list[Item]:
    out = []
    for t in trades:
        if not _is_debit(t):
            continue
        out.append(Item(
            entry_date=str(t.entry_date), exit_date=str(t.exit_date),
            need=abs(float(t.entry_credit)) * 100.0 * float(t.contracts),
            pnl=float(t.exit_pnl), kind="main_debit",
        ))
    return out


def _q042_items(start: str, need: float) -> list[Item]:
    out = []
    with Q042_CSV.open() as f:
        for row in csv.DictReader(f):
            if row["sleeve_id"] != "A":
                continue                     # Sleeve B production cap = 0%
            if row["entry_date"] < start:
                continue
            debit_ct = float(row["debit_per_share"]) * 100.0
            n_ct = int(need // debit_ct) if debit_ct > 0 else 0
            exit_d = row["exit_date"] or (
                date.fromisoformat(row["entry_date"]) + timedelta(days=30)
            ).isoformat()
            out.append(Item(
                entry_date=row["entry_date"], exit_date=exit_d,
                need=n_ct * debit_ct,        # actual committed after contract rounding
                pnl=float(row["exit_pnl"]) * n_ct,   # CSV pnl is per 1 contract
                kind="q042",
            ))
    return out


def replay(items: list[Item], pool0: float, mode: str) -> dict:
    """Chronological SPEC-111 replay.

    mode:
      "ISO" — 现状:Q042 免闸且对主闸门不可见(main gate 只算 main committed);
              另行跟踪 combined committed,统计池被抽穿(combined > pool)事件。
      "VIS" — 单向可见提案:Q042 免闸但其 committed 计入主闸门口径。
      "GOV" — 纳入治理反事实:Q042 与主 debit 同过 floor/cap 闸。
    """
    seq = sorted(items, key=lambda x: (x.entry_date, x.exit_date))
    active_main: list[tuple[str, float]] = []
    active_q042: list[tuple[str, float]] = []
    st = {
        "main_pass": 0, "main_block_floor": 0, "main_block_cap": 0,
        "main_pnl_foregone": 0.0,
        "q042_pass": 0, "q042_block": 0, "q042_pnl_foregone": 0.0,
        "q042_overdraft": 0,          # 免闸情景:need > liquid → 被迫卖资产
        "combined_breach": 0,         # ISO: combined committed > pool 的入场事件
        "max_committed": 0.0,         # 口径:combined(真实池占用)
    }
    for it in seq:
        d = it.entry_date
        active_main = [(x, c) for x, c in active_main if x >= d]
        active_q042 = [(x, c) for x, c in active_q042 if x >= d]
        committed_main = sum(c for _, c in active_main)
        committed_q042 = sum(c for _, c in active_q042)
        combined = committed_main + committed_q042
        st["max_committed"] = max(st["max_committed"], combined)

        # 主闸门看到的 committed 口径按 mode 区分
        committed_vis = committed_main if mode == "ISO" else combined
        liquid_vis = pool0 - committed_vis
        liquid_true = pool0 - combined

        if it.kind == "q042" and mode in ("ISO", "VIS"):
            if it.need > liquid_true:
                st["q042_overdraft"] += 1
            if mode == "ISO" and combined + it.need > pool0:
                st["combined_breach"] += 1
            st["q042_pass"] += 1
            active_q042.append((it.exit_date, it.need))
            continue

        blocked_floor = liquid_vis < FLOOR
        blocked_cap = (committed_vis + it.need) > CAP_PCT * liquid_vis
        if blocked_floor or blocked_cap:
            if it.kind == "q042":
                st["q042_block"] += 1
                st["q042_pnl_foregone"] += it.pnl
            else:
                st["main_block_floor" if blocked_floor else "main_block_cap"] += 1
                st["main_pnl_foregone"] += it.pnl
            continue
        if it.kind == "main_debit":
            st["main_pass"] += 1
            if mode == "ISO" and combined + it.need > pool0:
                st["combined_breach"] += 1
            active_main.append((it.exit_date, it.need))
        else:
            st["q042_pass"] += 1
            active_q042.append((it.exit_date, it.need))
    return st


def main() -> int:
    from backtest.engine import run_backtest
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, start in WINDOWS:
        trades, _, _ = run_backtest(start_date=start, verbose=False,
                                    account_size=ACCOUNT)
        main_items = _main_items(trades)
        print(f"\n=== {label} ({start}→) — main debit n={len(main_items)} ===")
        # 基线(无 Q042)用于 delta 校验,应复现 Q092
        for pool0 in POOL_GRID:
            base = replay(main_items, pool0, mode="GOV")
            for var_label, need in Q042_NEED_VARIANTS:
                q042 = _q042_items(start, need)
                for scen in ("ISO", "VIS", "GOV"):
                    r = replay(main_items + q042, pool0, mode=scen)
                    row = {
                        "window": label, "pool0": pool0, "q042_need": var_label,
                        "scenario": scen, "q042_n": len(q042), **r,
                        "main_block_delta": (r["main_block_floor"] + r["main_block_cap"])
                                            - (base["main_block_floor"] + base["main_block_cap"]),
                        "main_pnl_foregone_delta": round(
                            r["main_pnl_foregone"] - base["main_pnl_foregone"], 0),
                    }
                    rows.append(row)
                    extra = (f" breach={r['combined_breach']}" if scen == "ISO"
                             else "")
                    print(f"pool ${pool0:>8,.0f} {var_label:>15s} {scen}: "
                          f"q042 {r['q042_pass']}/{len(q042)} pass"
                          f" od={r['q042_overdraft']}{extra}"
                          f", q042 PnL foregone ${r['q042_pnl_foregone']:>9,.0f}"
                          f" | main block Δ+{row['main_block_delta']}"
                          f", main PnL foregone Δ${row['main_pnl_foregone_delta']:>9,.0f}"
                          f", max committed ${r['max_committed']:,.0f}")
    with (OUT / "q093_p1_cash_stack.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT / 'q093_p1_cash_stack.csv'} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
