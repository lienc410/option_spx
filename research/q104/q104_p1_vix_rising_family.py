"""
FROZEN (2026-07-22, 裁决执行完毕): 本脚本引用的 StrategyParams.bypass_vix_rising_momentum_gates 已随裁决执行移除——脚本不再可运行，作为本次批量重验的可追溯记录保留（结果固化在 q104_p1_findings_2026-07-22.md 与 CSV 产物里）。
Q104 P1 — 批量重验剩余 7 个"VIX rising 跳过"动量门（PM 2026-07-22 指令：
清查全盘同类疑点后，同机制家族批量重验）。

与今天已退役的 3 个 P3 门（Q103）逐字同一段代码
（`_rising = vix.trend == Trend.RISING`），只是挂在不同 regime×iv×trend
组合上、守着不同策略。清点结果（selector.py 全 gate 盘点）：

  gate                  regime    iv       trend     guards
  hv_bearish_vix_rising HIGH_VOL  (HV分支)  BEARISH   BEAR_CALL_SPREAD_HV
  hv_neutral_vix_rising HIGH_VOL  NEUTRAL   NEUTRAL   IRON_CONDOR_HV
  hv_bullish_vix_rising HIGH_VOL  (HV分支)  BULLISH   BULL_PUT_SPREAD_HV
  nhb_vix_rising        NORMAL    HIGH      BULLISH   BULL_PUT_SPREAD
  nhbe_vix_rising       NORMAL    HIGH      BEARISH   IRON_CONDOR
  nnb_vix_rising        NORMAL    NEUTRAL   BULLISH   BULL_PUT_SPREAD
  nnbe_vix_rising       NORMAL    NEUTRAL   BEARISH   IRON_CONDOR

Q087 Track A（A1-A5）审计名单核对：IVP 双门(40-70)/BPS NNB 窄带/V2F 止损/
SPEC-079/IV_LOW 阈值——与本家族零重叠，从未被任何审计覆盖。

## 方法（与 Q103 同一套，同一评判尺，不因为已经杀过一次就放松举证标准）
`StrategyParams.bypass_vix_rising_momentum_gates`（默认 False）一次性关闭
全部 7 处；跑两次完整 26y walk-forward（FLAT sigma，2000-01-01 起，与
Q073/Q078/Q103 同惯例）。因涉及 5 个不同策略（IC/IC_HV/BPS/BPS_HV/
BCS_HV），trade 归属改用「entry_date 在两流的策略级差集」，每个 gate
分开报告（不同策略风险形状不同，不能像 Q103 那样单一 IC 结构直接汇总），
同时给一个跨 gate 的 pooled 视图作为总览。

## 预注册判定规则（Q103 同款，逐条搬运，先写后跑）
  R1 evidence gate：某 gate 的 blocked n < 8 → 该 gate 单独 facts-only，
     不给它自己的 promote/kill verdict（仍计入 pooled 视图供参考）。
  R2 kill-class 反向举证（feedback_status_quo_bias_in_verdicts）：
     MAINTAIN 需要 blocked 显著更差的正面证据；证据不够 → RETIRE 候选。
  R3 显著性：year-block bootstrap 95% CI（blocked − passed 均值差），
     MAINTAIN 需要 CI 上界 < 0。
  R4 尾部专项：exit_reason 标签 + 独立于标签的量级指标（占理论最大损失
     credit×stop_mult 的比例），credit 策略与 debit 策略（无——本族全为
     credit：IC/BPS/BCS）用同一公式，signed entry_credit 已处理符号。
  R5 时代分层：full(2000+) 与 post2020 分列，符号不一致必须明写。
  R6 反事实局限：FLAT sigma、组合状态涟漪（同 Q103 P2 附录，本次按 pooled
     层面报告涟漪量级，不逐 gate 重复）。
  R7（本次新增，因多 gate 同时开）：一次性关闭 7 个 gate 会互相影响并发
     仓位/BP 占用节奏，比 Q103 单开 3 个更强——涟漪量级必须报告且不能
     假设可忽略；若涟漪本身量级接近或超过任一 gate 的效应量，该 gate
     的 verdict 需要额外谨慎（在结论里明确标注，不能只看均值差）。
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

OUT = ROOT / "research" / "q104"
START = "2000-01-01"
END = "2026-07-21"

# gate → (guarded strategy enum, regime, iv_signal, trend) — regime/iv/trend
# used to cross-check via signal_history that a candidate day truly belongs
# to this gate's cell (guards against a same-strategy trade from an
# unrelated, non-gated cell leaking into the diff).
GATE_MAP = {
    "hv_bearish_vix_rising": (StrategyName.BEAR_CALL_SPREAD_HV, "HIGH_VOL", None, "BEARISH"),
    "hv_neutral_vix_rising": (StrategyName.IRON_CONDOR_HV, "HIGH_VOL", "NEUTRAL", "NEUTRAL"),
    "hv_bullish_vix_rising": (StrategyName.BULL_PUT_SPREAD_HV, "HIGH_VOL", None, "BULLISH"),
    "nhb_vix_rising": (StrategyName.BULL_PUT_SPREAD, "NORMAL", "HIGH", "BULLISH"),
    "nhbe_vix_rising": (StrategyName.IRON_CONDOR, "NORMAL", "HIGH", "BEARISH"),
    "nnb_vix_rising": (StrategyName.BULL_PUT_SPREAD, "NORMAL", "NEUTRAL", "BULLISH"),
    "nnbe_vix_rising": (StrategyName.IRON_CONDOR, "NORMAL", "NEUTRAL", "BEARISH"),
}


def _trades_df(result, strategy: StrategyName) -> pd.DataFrame:
    rows = [t for t in result.trades if t.strategy == strategy]
    return pd.DataFrame([{
        "entry_date": t.entry_date, "exit_date": t.exit_date,
        "exit_pnl": t.exit_pnl, "exit_reason": t.exit_reason,
        "entry_credit": t.entry_credit, "contracts": t.contracts,
        "pnl_pct": t.pnl_pct, "hold_days": t.hold_days,
    } for t in rows])


def _cell_lookup(signals: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(signals).set_index("date")
    return df[["regime", "iv_signal", "trend", "vix_5d_avg"]]


def _matches_cell(row, regime, iv_signal, trend) -> bool:
    if row["regime"] != regime or row["trend"] != trend:
        return False
    if iv_signal is not None and row["iv_signal"] != iv_signal:
        return False
    return True


def year_block_bootstrap(a: pd.Series, a_years, b: pd.Series, b_years, n=4000, seed=17):
    ya = pd.Series(a.values, index=a_years).groupby(level=0)
    yb = pd.Series(b.values, index=b_years).groupby(level=0)
    years_a, years_b = sorted(ya.groups), sorted(yb.groups)
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n):
        sa = np.concatenate([rng.choice(ya.get_group(y).values, size=len(ya.get_group(y)), replace=True)
                             for y in rng.choice(years_a, size=len(years_a), replace=True)]) if years_a else np.array([0.0])
        sb = np.concatenate([rng.choice(yb.get_group(y).values, size=len(yb.get_group(y)), replace=True)
                             for y in rng.choice(years_b, size=len(years_b), replace=True)]) if years_b else np.array([0.0])
        diffs.append(sa.mean() - sb.mean())
    d = np.array(diffs)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def summarize(df: pd.DataFrame) -> dict:
    if len(df) == 0:
        return {"n": 0}
    stop_mult = StrategyParams().stop_mult
    max_loss = df.entry_credit.abs() * 100 * df.contracts.abs() * stop_mult
    loss_ratio = (-df.exit_pnl / max_loss.replace(0, np.nan)).clip(lower=0)
    return {
        "n": len(df), "mean_pnl": round(df.exit_pnl.mean(), 0),
        "median_pnl": round(df.exit_pnl.median(), 0),
        "wr_pct": round((df.exit_pnl > 0).mean() * 100),
        "worst_pnl": round(df.exit_pnl.min(), 0),
        "tail_hit_pct": round((df.exit_reason == "stop_loss").mean() * 100, 1),
        "deep_tail_pct": round((loss_ratio >= 0.5).mean() * 100, 1),
        "cvar10_pnl": round(df.exit_pnl.nsmallest(max(1, len(df) // 10)).mean(), 0),
    }


def main() -> int:
    print(f"═ Q104 P1: production run (7 gates ON) {START}→{END} ═")
    prod = run_backtest(start_date=START, end_date=END, params=StrategyParams(), verbose=False)
    print(f"═ Q104 P1: bypass run (7 gates OFF) ═")
    byp = run_backtest(start_date=START, end_date=END,
                       params=StrategyParams(bypass_vix_rising_momentum_gates=True), verbose=False)
    cells = _cell_lookup(byp.signals)

    all_blocked, all_passed = [], []
    verdict_rows = []
    for gate, (strat, regime, iv_signal, trend) in GATE_MAP.items():
        ic_prod = _trades_df(prod, strat)
        ic_byp = _trades_df(byp, strat)
        prod_dates = set(ic_prod.entry_date)
        cand_blocked = ic_byp[~ic_byp.entry_date.isin(prod_dates)].copy()
        cand_passed = ic_byp[ic_byp.entry_date.isin(prod_dates)].copy()
        cand_blocked = cand_blocked[cand_blocked.entry_date.map(
            lambda d: d in cells.index and _matches_cell(cells.loc[d], regime, iv_signal, trend))]
        cand_passed = cand_passed[cand_passed.entry_date.map(
            lambda d: d in cells.index and _matches_cell(cells.loc[d], regime, iv_signal, trend))]
        cand_blocked = cand_blocked.assign(gate=gate)
        cand_passed = cand_passed.assign(gate=gate)
        all_blocked.append(cand_blocked)
        all_passed.append(cand_passed)

        b_sum, p_sum = summarize(cand_blocked), summarize(cand_passed)
        print(f"\n[{gate}] guards {strat.value} @ {regime}·{iv_signal or '(HV)'}·{trend}")
        print(f"  blocked n={b_sum['n']}  passed n={p_sum['n']}")
        if b_sum["n"] < 8:
            print(f"  ❌ R1: blocked n={b_sum['n']} < 8 → FACTS-ONLY (仅登记，不出 verdict)")
        else:
            print(f"  blocked: mean={b_sum['mean_pnl']} wr={b_sum['wr_pct']}% worst={b_sum['worst_pnl']} "
                  f"tail_hit={b_sum['tail_hit_pct']}% deep_tail={b_sum['deep_tail_pct']}%")
            print(f"  passed : mean={p_sum['mean_pnl']} wr={p_sum['wr_pct']}% worst={p_sum['worst_pnl']} "
                  f"tail_hit={p_sum['tail_hit_pct']}% deep_tail={p_sum['deep_tail_pct']}%")
            if p_sum["n"] >= 2:
                b_yr = pd.to_datetime(cand_blocked.entry_date).dt.year
                p_yr = pd.to_datetime(cand_passed.entry_date).dt.year
                lo, hi = year_block_bootstrap(cand_blocked.exit_pnl, b_yr, cand_passed.exit_pnl, p_yr)
                sign = "MAINTAIN 支持 (blocked显著更差)" if hi < 0 else \
                       ("RETIRE 支持 (blocked显著更好)" if lo > 0 else "CI跨零不显著")
                print(f"  bootstrap CI [{lo:+.0f}, {hi:+.0f}] → {sign}")
        verdict_rows.append({"gate": gate, "strategy": strat.value,
                             "blocked_n": b_sum["n"], "passed_n": p_sum["n"],
                             "blocked_mean": b_sum.get("mean_pnl"), "passed_mean": p_sum.get("mean_pnl"),
                             "blocked_wr": b_sum.get("wr_pct"), "passed_wr": p_sum.get("wr_pct"),
                             "blocked_worst": b_sum.get("worst_pnl"), "passed_worst": p_sum.get("worst_pnl"),
                             "blocked_deep_tail": b_sum.get("deep_tail_pct"),
                             "passed_deep_tail": p_sum.get("deep_tail_pct")})

    blocked_all = pd.concat(all_blocked) if all_blocked else pd.DataFrame()
    passed_all = pd.concat(all_passed) if all_passed else pd.DataFrame()
    blocked_all.to_csv(OUT / "q104_p1_blocked_trades.csv", index=False)
    passed_all.to_csv(OUT / "q104_p1_passed_trades.csv", index=False)
    pd.DataFrame(verdict_rows).to_csv(OUT / "q104_p1_verdict_table.csv", index=False)

    print(f"\n═ Pooled 总览（跨全部 7 个 gate）═")
    bp, pp = summarize(blocked_all), summarize(passed_all)
    print(f"  blocked: n={bp['n']} mean={bp.get('mean_pnl')} wr={bp.get('wr_pct')}% "
          f"deep_tail={bp.get('deep_tail_pct')}%")
    print(f"  passed : n={pp['n']} mean={pp.get('mean_pnl')} wr={pp.get('wr_pct')}% "
          f"deep_tail={pp.get('deep_tail_pct')}%")

    # ── R5 时代分层（pooled） ─────────────────────────────────────────────
    for label, era in (("full", blocked_all), ("post2020", None)):
        pass
    for era_label in ("full", "post2020"):
        b_e = blocked_all if era_label == "full" else blocked_all[pd.to_datetime(blocked_all.entry_date).dt.year >= 2020]
        p_e = passed_all if era_label == "full" else passed_all[pd.to_datetime(passed_all.entry_date).dt.year >= 2020]
        bs, ps = summarize(b_e), summarize(p_e)
        print(f"\n  [{era_label}] blocked n={bs['n']} mean={bs.get('mean_pnl')} | "
              f"passed n={ps['n']} mean={ps.get('mean_pnl')}")

    # ── R7 组合状态涟漪（pooled，7 gate 同时开的量级）──────────────────────
    print(f"\n═ R7 组合状态涟漪（7 gate 同时 bypass 的次级效应）═")
    for strat in {v[0] for v in GATE_MAP.values()}:
        ic_prod = _trades_df(prod, strat)
        ic_byp = _trades_df(byp, strat)
        byp_dates = set(ic_byp.entry_date)
        vanished = ic_prod[~ic_prod.entry_date.isin(byp_dates)]
        if len(ic_prod):
            print(f"  {strat.value}: production n={len(ic_prod)}, "
                  f"{len(vanished)} 笔（{len(vanished)/len(ic_prod)*100:.0f}%）在 bypass 世界同日期不存在，"
                  f"均值 PnL={vanished.exit_pnl.mean() if len(vanished) else float('nan'):.0f}"
                  if len(vanished) else f"  {strat.value}: production n={len(ic_prod)}, 0 笔位移")

    return 0


if __name__ == "__main__":
    sys.exit(main())
