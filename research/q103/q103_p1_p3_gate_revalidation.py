"""
FROZEN (2026-07-22, PM ratify): P3 门已整体退役（strategy/selector.py 三处 gate 删除），本脚本引用的 StrategyParams.bypass_p3_vix_rising_ic_gate 已随之移除——脚本不再可运行，作为本次研究的可追溯记录保留（结果已固化在 q103_p1_findings_2026-07-22.md 与 CSV 产物里）。
Q103 P1 — 独立重验 P3 门（"VIX rising 时跳过 Iron Condor"）。

PM 2026-07-22："按你的说法，我们是应该像 A1-A5 那五个门一样被独立重验"
（回应 07-21 晨报复盘：selector NORMAL·NEUTRAL·NEUTRAL P3 拦了一次 IC，
本文档确认该门自 SPEC-020 起从未被独立重验过 —— Q087 Track A 只测了
A1-A5，此门不在名单内）。

## 门的位置（三处，逐位相同的 45DTE / δ0.16-0.08 IC 结构）
  1. LOW_VOL · NEUTRAL          (lv_neutral_vix_rising)
  2. NORMAL · IV_HIGH · NEUTRAL (nhn_vix_rising)
  3. NORMAL · IV_NEUTRAL · NEUTRAL (nnn_vix_rising)
三处触发条件一致：vix.trend == RISING（5 日均 vs 前 5 日均）→ 该 cell 从
Iron Condor 降级为 reduce_wait。同 regime×iv×trend 组合下 BEARISH 分支
的 IC（无 P3）作为天然对照，证明该 gate 不是"这个 regime 不能开 IC"，
而是专门针对"NEUTRAL trend + VIX 抬头"的定向拦截。

## 方法（Q087 A1-A5 同一套：复用生产引擎，不建平行精简计价器）
strategy.selector.StrategyParams 新增 `bypass_p3_vix_rising_ic_gate`
（默认 False，生产零改动，见 selector.py 注记）。跑两次完整 26 年
walk-forward（FLAT sigma，canonical 起点 2000-01-01，与 Q073/Q078 等
既有全历史研究同惯例）：
  A) 生产流（gate 生效）
  B) bypass 流（gate 失效，三个 cell 一律按 IC 路由）
两流的 signal_history 里 regime/iv_signal/trend 逐日计算与 gate 无关、
完全一致；两流 Iron Condor 交易 entry_date 的**集合差** B−A 就是被 P3
拦截的反事实交易——这个差集不含其它 cell 的 IC（BEARISH 分支两流恒同，
在差集中自然抵消），也天然承接 engine 的并发仓位 / BP 上限等次级约束
（bypass 后新开的 IC 若撞上并发上限会被其它 gate 挡，如实呈现不特事屏蔽）。

## 预注册判定规则（先写规则，后跑数——防止看到结果再挑标准）
  R1 (evidence gate)：blocked cohort（B−A 差集）n < 8 → facts-only，不出
     promote/kill verdict（feedback_layer_n_replacement_outcome 纪律）。
  R2 (kill-class 额外举证，feedback_status_quo_bias_in_verdicts)：本门是
     防御门，"MAINTAIN"（现状）本身就带 status-quo 立场，所以判定门槛
     反过来设——MAINTAIN 需要 blocked cohort 显著更差；证据不够 →
     RETIRE 候选（不是自动默认维持现状）。
  R3 (显著性)：blocked cohort 均值 PnL 与 passed cohort 均值 PnL 的差，
     用 year-block bootstrap（≥2000 次重抽样）出双侧 CI；MAINTAIN 需要
     CI 上界 < 0（blocked 显著更差，含 IC 惯常防御逻辑校验方向）。
  R4 (尾部专项，IC 的真实风险是尾部不是均值)：无论 R3 结果，单独报告
     blocked cohort 的 worst-trade / 触及最大损失比例(触及 stop_mult
     即视为 tail-hit) vs passed cohort 同口径——即使均值差不显著，
     tail 分布显著更差也构成 MAINTAIN 依据（IC 防御门的经济学是"避免
     尾部"不是"提高均值"，R3 单独可能测不到这一点）。
  R5 (时代分层)：full(2000+) 与 post-2020 分别报告，符号不一致需在
     结论里明写（feedback_adaptive_posture_no_allweather_gate 同精神）。
  R6 (反事实局限)：blocked cohort 全部来自 FLAT sigma 26y 引擎——与
     production 一致的已知局限（Q087 Track B：CALIB 修正约 15-20%，
     方向未知，不单独为本研究重新定价）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.engine import StrategyName, run_backtest          # noqa: E402
from strategy.selector import StrategyParams                    # noqa: E402

OUT = ROOT / "research" / "q103"
START = "2000-01-01"
END = "2026-07-21"
STOP_MULT = 2.0            # StrategyParams.stop_mult default — tail-hit threshold


def _ic_trades(result) -> pd.DataFrame:
    rows = [t for t in result.trades if t.strategy == StrategyName.IRON_CONDOR]
    return pd.DataFrame([{
        "entry_date": t.entry_date, "exit_date": t.exit_date,
        "exit_pnl": t.exit_pnl, "exit_reason": t.exit_reason,
        "entry_credit": t.entry_credit, "contracts": t.contracts,
        "pnl_pct": t.pnl_pct, "hold_days": t.hold_days,
    } for t in rows])


def _cell_lookup(signal_history: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(signal_history).set_index("date")
    return df[["regime", "iv_signal", "trend", "vix", "vix_5d_avg"]]


def _tag_cell(row) -> str | None:
    if row["trend"] != "NEUTRAL":
        return None
    if row["regime"] == "LOW_VOL":
        return "LOW_VOL·NEUTRAL"
    if row["regime"] == "NORMAL" and row["iv_signal"] == "HIGH":
        return "NORMAL·HIGH·NEUTRAL"
    if row["regime"] == "NORMAL" and row["iv_signal"] == "NEUTRAL":
        return "NORMAL·NEUTRAL·NEUTRAL"
    return None


def year_block_bootstrap(a: pd.Series, a_years, b: pd.Series, b_years, n=4000, seed=13):
    """P(mean(a) - mean(b) 的 CI)；a=blocked(反事实), b=passed(实际)。
    年块重抽样：每次抽样对每年独立重抽该年内的交易（保留年内相关性）。"""
    ya = pd.Series(a.values, index=a_years).groupby(level=0)
    yb = pd.Series(b.values, index=b_years).groupby(level=0)
    years_a, years_b = sorted(ya.groups), sorted(yb.groups)
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n):
        sa = np.concatenate([rng.choice(ya.get_group(y).values,
                             size=len(ya.get_group(y)), replace=True)
                             for y in rng.choice(years_a, size=len(years_a), replace=True)]) \
             if years_a else np.array([0.0])
        sb = np.concatenate([rng.choice(yb.get_group(y).values,
                             size=len(yb.get_group(y)), replace=True)
                             for y in rng.choice(years_b, size=len(years_b), replace=True)]) \
             if years_b else np.array([0.0])
        diffs.append(sa.mean() - sb.mean())
    d = np.array(diffs)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def era_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    yr = pd.to_datetime(df.entry_date).dt.year
    return df, df[yr >= 2020]


def summarize(df: pd.DataFrame, label: str) -> dict:
    if len(df) == 0:
        return {"label": label, "n": 0}
    tail_hit = (df.exit_reason == "stop_loss").mean() * 100
    return {
        "label": label, "n": len(df),
        "mean_pnl": round(df.exit_pnl.mean(), 0),
        "median_pnl": round(df.exit_pnl.median(), 0),
        "wr_pct": round((df.exit_pnl > 0).mean() * 100),
        "worst_pnl": round(df.exit_pnl.min(), 0),
        "tail_hit_pct": round(tail_hit, 1),
        "cvar10_pnl": round(df.exit_pnl.nsmallest(max(1, len(df) // 10)).mean(), 0),
    }


def main() -> int:
    print(f"═ Q103 P1: production run (gate ON) {START}→{END} ═")
    prod = run_backtest(start_date=START, end_date=END,
                        params=StrategyParams(), verbose=False)
    print(f"═ Q103 P1: bypass run (gate OFF) ═")
    byp = run_backtest(start_date=START, end_date=END,
                       params=StrategyParams(bypass_p3_vix_rising_ic_gate=True),
                       verbose=False)

    ic_prod = _ic_trades(prod)
    ic_byp = _ic_trades(byp)
    print(f"\nIC trades: production n={len(ic_prod)}  bypass n={len(ic_byp)}  "
          f"(bypass 应 ≥ production)")

    prod_dates = set(ic_prod.entry_date)
    blocked = ic_byp[~ic_byp.entry_date.isin(prod_dates)].copy()
    passed = ic_byp[ic_byp.entry_date.isin(prod_dates)].copy()
    print(f"blocked（反事实，B−A 差集）n={len(blocked)}  "
          f"passed（两流共有，真实发生）n={len(passed)}")

    # 用 bypass 流的 signal_history 给每笔 IC 打 cell 标签（regime/iv/trend
    # 与 gate 无关，两流逐日相同；用 bypass 流因为它含全部 IC 触发日）
    cells = _cell_lookup(byp.signals)
    for df in (blocked, passed):
        df["cell"] = df.entry_date.map(lambda d: _tag_cell(cells.loc[d]) if d in cells.index else None)
        df["vix_5d_avg"] = df.entry_date.map(lambda d: cells.loc[d, "vix_5d_avg"] if d in cells.index else None)

    off_cell = blocked[blocked.cell.isna()]
    if len(off_cell):
        print(f"⚠ {len(off_cell)} 笔 blocked 交易 cell 打标失败（登记，不计入判定）：\n{off_cell[['entry_date']]}")
    blocked = blocked[blocked.cell.notna()]
    passed = passed[passed.cell.notna()]

    blocked.to_csv(OUT / "q103_p1_blocked_trades.csv", index=False)
    passed.to_csv(OUT / "q103_p1_passed_trades.csv", index=False)

    print(f"\n═ Cell 分布（blocked / passed）═")
    print(pd.concat([blocked.cell.value_counts().rename("blocked"),
                     passed.cell.value_counts().rename("passed")], axis=1).fillna(0).astype(int))

    # ── R1 evidence gate ──────────────────────────────────────────────
    if len(blocked) < 8:
        print(f"\n❌ R1 EVIDENCE GATE: blocked n={len(blocked)} < 8 → "
              f"FACTS-ONLY，不出 promote/kill verdict。以下仅供事实记录。")

    print(f"\n═ R5 时代分层汇总 ═")
    rows = []
    for era_label, era_fn in (("full", lambda d: d), ("post2020", lambda d: era_split(d)[1])):
        b_e, p_e = era_fn(blocked), era_fn(passed)
        rows.append(summarize(b_e, f"blocked-{era_label}"))
        rows.append(summarize(p_e, f"passed-{era_label}"))
    summ = pd.DataFrame(rows)
    print(summ.to_string(index=False))
    summ.to_csv(OUT / "q103_p1_summary.csv", index=False)

    # ── R3 bootstrap on mean-PnL diff, era-stratified ──────────────────
    print(f"\n═ R3 Year-block bootstrap: mean(blocked) − mean(passed) 95% CI ═")
    for era_label, era_fn in (("full", lambda d: d), ("post2020", lambda d: era_split(d)[1])):
        b_e, p_e = era_fn(blocked), era_fn(passed)
        if len(b_e) < 2 or len(p_e) < 2:
            print(f"  {era_label}: n 太小，跳过 bootstrap")
            continue
        b_yr = pd.to_datetime(b_e.entry_date).dt.year
        p_yr = pd.to_datetime(p_e.entry_date).dt.year
        lo, hi = year_block_bootstrap(b_e.exit_pnl, b_yr, p_e.exit_pnl, p_yr)
        sign = "blocked 显著更差 (MAINTAIN 支持)" if hi < 0 else \
               ("blocked 显著更好 (RETIRE 支持)" if lo > 0 else "CI 跨零，不显著")
        print(f"  {era_label}: diff CI [{lo:+.0f}, {hi:+.0f}]  → {sign}")

    # ── R4 tail-focused comparison (independent of R3 significance) ────
    print(f"\n═ R4 尾部专项（stop_loss 触及率 + worst-trade + CVaR10）═")
    for cell in sorted(set(blocked.cell) | set(passed.cell)):
        b_c, p_c = blocked[blocked.cell == cell], passed[passed.cell == cell]
        print(f"  [{cell}] blocked: n={len(b_c)} tail_hit={summarize(b_c,'')['tail_hit_pct'] if len(b_c) else '—'}% "
              f"worst={summarize(b_c,'')['worst_pnl'] if len(b_c) else '—'} | "
              f"passed: n={len(p_c)} tail_hit={summarize(p_c,'')['tail_hit_pct'] if len(p_c) else '—'}% "
              f"worst={summarize(p_c,'')['worst_pnl'] if len(p_c) else '—'}")

    # ── Sanity: does VIX_RISING actually predict near-term forward vol? ──
    print(f"\n═ 附加 sanity check：blocked 日 5 日均 VIX 前后变化（是否真的在'抬头'）═")
    print(f"  blocked 触发日 vix_5d_avg 均值: {blocked.vix_5d_avg.mean():.2f}")
    print(f"  passed  触发日 vix_5d_avg 均值: {passed.vix_5d_avg.mean():.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
