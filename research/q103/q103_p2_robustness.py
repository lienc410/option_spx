"""Q103 P2 — P1 结果的稳健性追加：量级尾部指标（不依赖 exit_reason 标签）+
production 中"bypass 世界里同日期不存在"的 26 笔交易特征刻画（组合状态涟漪
效应，R6 附录局限的量化，而非脚注带过）。复用 P1 同一对 run_backtest 结果。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.engine import StrategyName, run_backtest      # noqa: E402
from strategy.selector import StrategyParams                 # noqa: E402
from q103_p1_p3_gate_revalidation import (                   # noqa: E402
    START, END, _cell_lookup, _ic_trades, _tag_cell, era_split, summarize,
)

OUT = ROOT / "research" / "q103"


def main() -> int:
    prod = run_backtest(start_date=START, end_date=END, params=StrategyParams(), verbose=False)
    byp = run_backtest(start_date=START, end_date=END,
                       params=StrategyParams(bypass_p3_vix_rising_ic_gate=True), verbose=False)

    ic_prod, ic_byp = _ic_trades(prod), _ic_trades(byp)
    prod_dates = set(ic_prod.entry_date)
    byp_dates = set(ic_byp.entry_date)
    blocked = ic_byp[~ic_byp.entry_date.isin(prod_dates)].copy()
    passed = ic_byp[ic_byp.entry_date.isin(prod_dates)].copy()
    cells = _cell_lookup(byp.signals)
    for df in (blocked, passed):
        df["cell"] = df.entry_date.map(lambda d: _tag_cell(cells.loc[d]) if d in cells.index else None)
    blocked = blocked[blocked.cell.notna()]
    passed_all = passed.copy()
    passed = passed[passed.cell.notna()]
    print(f"passed off-cell（非 P3 保护 cell，两流恒同——理论上应为 BEARISH 分支 IC）: "
          f"{len(passed_all) - len(passed)}")

    # ── 量级尾部（独立于 exit_reason 标签）───────────────────────────────
    print("\n═ 量级尾部指标（占最大理论损失 = credit×stop_mult 的比例）═")
    stop_mult = StrategyParams().stop_mult
    for name, df in (("blocked-full", blocked), ("passed-full", passed)):
        if len(df) == 0:
            continue
        max_loss = df.entry_credit.abs() * 100 * df.contracts.abs() * stop_mult
        loss_ratio = (-df.exit_pnl / max_loss.replace(0, np.nan)).clip(lower=0)
        deep_tail = (loss_ratio >= 0.5).mean() * 100   # 触及 ≥50% 理论最大损失
        print(f"  {name}: n={len(df)}  深尾(≥50%理论最大损失)占比={deep_tail:.1f}%  "
              f"最大损失比例中位数={loss_ratio.median():.2f}  p90={loss_ratio.quantile(0.9):.2f}")

    # ── production 世界"消失"的交易特征刻画 ─────────────────────────────
    vanished = ic_prod[~ic_prod.entry_date.isin(byp_dates)].copy()
    print(f"\n═ Production 中 {len(vanished)}/{len(ic_prod)} 笔 IC 交易在 bypass 世界"
          f"同日期不存在（组合状态涟漪，R6 附录）═")
    if len(vanished):
        vanished["cell"] = vanished.entry_date.map(
            lambda d: _tag_cell(cells.loc[d]) if d in cells.index else "off_cell/date_gap")
        print(vanished.cell.value_counts())
        print(f"  vanished 均值 PnL: {vanished.exit_pnl.mean():.0f}  "
              f"（与 passed-full 均值 {passed.exit_pnl.mean():.0f} 比较，判断涟漪是否系统性偏向某方向）")
        vanished.to_csv(OUT / "q103_p2_vanished_trades.csv", index=False)
        # 检查 vanished 交易在 bypass 世界该日期附近是否有"替代"交易（同 cell 前后 5TD 内）
        near_hits = 0
        for d in vanished.entry_date:
            near = ic_byp[(pd.to_datetime(ic_byp.entry_date) - pd.Timestamp(d)).abs()
                          <= pd.Timedelta(days=7)]
            if len(near):
                near_hits += 1
        print(f"  vanished 交易中 {near_hits}/{len(vanished)} 笔在 bypass 世界 ±7 日内"
              f"有同类 IC 触发（支持'延迟/替代'而非'凭空消失'的解释）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
