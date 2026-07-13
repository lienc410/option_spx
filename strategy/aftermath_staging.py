"""SPEC-143 — Aftermath 首笔 0.5× staging（Q101 裁决 3，live 推荐层 only）.

唯一生产调用方是 selector._apply_aftermath_staging_live（get_recommendation
的 LIVE-ONLY wrapper，同 SPEC-123 D1 先例）。回测路径（Q041/ES/SPX）直接调
select_strategy，永远不 import 本模块——回测隔离由调用拓扑保证
（AC-4：matrix_audit.csv 前后 diff 为空 + 全量测试零新增失败，
tests/test_spec_143.py 另含静态断言 backtest/ 零本模块 import）。

三态（task/SPEC-143.md §行为）：
  态 1  窗口内无 skew 实测（含 monitor 文件缺失/字段缺——危害向保守）
        → 张数 = max(1, floor(标准张数 × 0.5))，advisory ⚠（非 veto）
  态 2  窗口内已有 skew 读数且 s < 1.5 → 标准张数，trace 注明 s 值
  态 3  s ≥ 1.5 → 维持 0.5× + Q101 预承诺复判 advisory

常量出处 research/q101/（q101_e1_memo.md §6 裁决 3 与 SKEW1 校准中位）；
不建参数 mirror 文档（agent 用 grep 取代码真值）。
人话文案唯一 copy 源 = strategy/decision_trace.q101_staging_label
（本模块只产出结构化 staging dict，不产出文案）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

# ── Q101 常量（出处 research/q101/q101_e1_memo.md，勿建 mirror 文档）─────────
# 首笔证据缺口降档系数（裁决 3：对盲打的那笔按证据缺口定 size）
Q101_STAGING_FACTOR = 0.5
# 预承诺复判触发线：实测 put 斜率 ≥ 1.5× calm 基线才阻止加仓（噪音防护档）
Q101_SLOPE_RECHECK_MULT = 1.5
# calm 中位 put 斜率基线（vp）= d15_moff 1.78 − atm_moff (−2.74) = 4.52
# （Q101 SKEW1 臂校准中位，research/q101/）
Q101_CALM_PUT_SLOPE_VP = 4.52

# skew monitor 真值文件（SPEC-085 日更 job 落盘）
SKEW_MONITOR_PATH = Path(__file__).resolve().parent.parent / "data" / "q085_skew_monitor.jsonl"

# aftermath V3-A 推荐走 iron_condor_hv key（strategy/state_surface.py 同口径）
V3A_STRATEGY_KEY = "iron_condor_hv"


def staged_contracts(standard: int) -> int:
    """0.5× staging 张数：max(1, floor(标准张数 × 0.5))（SPEC-143 AC-2）。"""
    return max(1, math.floor(int(standard) * Q101_STAGING_FACTOR))


def put_slope_multiple(d15_moff, atm_moff) -> float | None:
    """s = (d15_moff − atm_moff) / 4.52vp；字段缺/非数值 → None（视同无读数）。"""
    try:
        d15 = float(d15_moff)
        atm = float(atm_moff)
    except (TypeError, ValueError):
        return None
    if math.isnan(d15) or math.isnan(atm):
        return None
    return (d15 - atm) / Q101_CALM_PUT_SLOPE_VP


def aftermath_window_start(vix_df, params=None) -> str | None:
    """当前 is_aftermath 连续区间的起始日（ISO），最后一个 EOD 日不活跃则 None。

    与 selector 同一真值函数：逐日构造 SimpleNamespace snapshot 直调
    strategy.selector.is_aftermath（Q101 v1.2 探针同款直调法，vs
    q064_p1_daily_flags 一致率 99.24%）。vix_df = fetch_vix_history 输出
    （'vix' 列，datetime index）。
    """
    from strategy.selector import is_aftermath

    if vix_df is None or "vix" not in getattr(vix_df, "columns", []) or len(vix_df) == 0:
        return None
    vix = vix_df["vix"]
    peak10 = vix.rolling(10, min_periods=10).max()
    start = None
    # 从最新 EOD 日往回走连续 True 区间
    for i in range(len(vix) - 1, -1, -1):
        peak = peak10.iloc[i]
        snap = SimpleNamespace(
            vix=float(vix.iloc[i]),
            vix_peak_10d=(None if peak != peak else float(peak)),  # NaN → None
        )
        if not is_aftermath(snap, params):
            break
        start = vix.index[i]
    if start is None:
        return None
    try:
        return start.date().isoformat()
    except AttributeError:
        return str(start)[:10]


def window_has_v3a_open(window_start: str) -> bool:
    """窗口内是否已有本策略（iron_condor_hv）真实开仓（非 void、非 paper）。

    真值 = logs/trade_log.jsonl resolve 后的 open 事件；开仓日期取 open
    timestamp 的日期段。读账本失败 → False（按首笔处理，与态 1 的保守方向
    一致：不确定时降档，绝不虚增张数）。
    """
    try:
        from logs.trade_log_io import resolve_log
        for row in resolve_log():
            o = row.get("open") or {}
            if row.get("voided") or o.get("paper_trade"):
                continue
            if o.get("strategy_key") != V3A_STRATEGY_KEY:
                continue
            ts = str(o.get("timestamp") or "")
            if ts[:10] >= str(window_start):
                return True
    except Exception:
        return False
    return False


def latest_window_skew(window_start: str, monitor_path: Path | None = None) -> dict | None:
    """窗口内（date ≥ 窗口起始日）最新一条可用 skew 读数。

    行内 d15_moff / atm_moff 任一缺失或非数值 → 该行不可用；文件缺失、
    JSON 坏行、全部不可用 → None（态 1，危害向保守）。
    """
    path = Path(monitor_path) if monitor_path is not None else SKEW_MONITOR_PATH
    best: dict | None = None
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                date = str(row.get("date") or "")
                if not date or date < str(window_start):
                    continue
                s = put_slope_multiple(row.get("d15_moff"), row.get("atm_moff"))
                if s is None:
                    continue
                if best is None or date >= best["date"]:
                    best = {
                        "date": date,
                        "s": round(s, 4),
                        "d15_moff": float(row["d15_moff"]),
                        "atm_moff": float(row["atm_moff"]),
                    }
    except OSError:
        return None
    return best


def evaluate_staging(
    vix_df,
    params=None,
    monitor_path: Path | None = None,
    today: str | None = None,
) -> dict:
    """三态判定（结构化输出；文案由 decision_trace.q101_staging_label 渲染）。

    返回 dict：state ∈ {1,2,3}、factor（0.5 或 1.0）、s、window_start、
    first_trade、reading_date。窗口起始日不可得（如盘中新窗口尚无 EOD 行）
    → 以 today 为窗口起始日（最保守口径：只认当天及以后的读数）。
    """
    window_start = None
    try:
        window_start = aftermath_window_start(vix_df, params)
    except Exception:
        window_start = None
    if window_start is None:
        from datetime import date as _date
        window_start = str(today or _date.today().isoformat())

    first_trade = not window_has_v3a_open(window_start)
    reading = latest_window_skew(window_start, monitor_path)

    if reading is None:
        state, factor, s = 1, Q101_STAGING_FACTOR, None
    elif reading["s"] >= Q101_SLOPE_RECHECK_MULT:
        state, factor, s = 3, Q101_STAGING_FACTOR, reading["s"]
    else:
        state, factor, s = 2, 1.0, reading["s"]

    return {
        "state": state,
        "factor": factor,
        "s": s,
        "window_start": window_start,
        "first_trade": first_trade,
        "reading_date": reading["date"] if reading else None,
    }
