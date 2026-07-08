"""SPEC-135 — Decision Trace：决策管道自吐（反漂移铁律）.

图的结构与数值全部由生产代码每次评估时自吐——前端零硬编码 gate 清单，
禁参数镜像。label_human 与门定义同居代码（写在 gate 旁、随 gate 改动同
commit），不建独立词汇表文档。

人类语言铁律（SPEC-135 §0）：
  - 每节点 label_human 主显示 + code_ref 角标（溯源）
  - 数字带语义（"第 28 百分位（偏便宜）"而非 "IVP 27.9"）
  - 期权/策略术语保留英文（Bull Call Diagonal / delta / DTE / call…），
    解释性文字中文
  - hover 三件套 = {inputs 检查了什么数据, detail 实际值 vs 阈值, code_ref}
  - 静默通过的门也入 trace（"为什么没拦"与"为什么拦"同权重）

行为零变更：trace 只追加不分支（gate() 原样返回传入的布尔）；AC =
selector 全网格回放路由 bit-identical（tests/test_spec_135.py）。
线程隔离：collector 挂 threading.local（web 多线程互不污染）。
"""
from __future__ import annotations

import threading

_TLS = threading.local()


def _buf() -> list:
    buf = getattr(_TLS, "nodes", None)
    if buf is None:
        buf = []
        _TLS.nodes = buf
    return buf


def reset() -> None:
    """每次 select_strategy 评估开头调用——上一轮残留清空。"""
    _TLS.nodes = []


def add(layer: str, check: str, label_human: str, *, detail: str = "",
        inputs: dict | None = None, outcome: str = "info", code_ref: str = "",
        branch_taken: bool = True, kind: str = "evidence",
        stage: str = "") -> None:
    """追加一个 trace 节点（纯记录，永不影响控制流）。

    layer: data|cell|gate|governance|funding|exposure|output
    outcome: info|route|pass|advisory|veto|halt|accept|wait
      advisory（SPEC-135.3）：评估为真、改变语气/通知、不阻止任何东西——
      渲染为琥珀 ⚠"提示"；红色 ⛔ 只留给真拦截（halt / 会阻止推荐或需
      pm_override 的 veto）。PM 2026-07-07 实测把敞口提示误读成最终拦截
      理由——词汇表缺此档是根因。
    SPEC-135.1（纯附加两字段，层级由代码吐、前端零硬编码）：
      kind:  verdict（阶段结论，常显锚点）| evidence（支撑检查，缩进可折叠）
             | final（今日结论，最大锚点）
      stage: market_read | routing | gates | capital | governance | final
             （evidence 归属其锚点的 stage）
    """
    _buf().append({
        "layer": layer,
        "check": check,
        "label_human": label_human,
        "detail": detail,
        "inputs": inputs or {},
        "outcome": outcome,
        "code_ref": code_ref,
        "branch_taken": bool(branch_taken),
        "kind": kind,
        "stage": stage,
    })


def gate(passed: bool, check: str, label_human: str, *, detail: str = "",
         inputs: dict | None = None, code_ref: str = "",
         layer: str = "gate", kind: str = "evidence",
         stage: str = "gates") -> bool:
    """门节点：记录 pass/veto 并**原样返回** passed（行为零变更的机械保证）。
    调用方式（评估一次、记录、再分支）：
        _blocked = <原判定表达式>
        T.gate(not _blocked, "...", "...")
        if _blocked: return _reduce_wait(...)
    """
    add(layer, check, label_human, detail=detail, inputs=inputs,
        outcome="pass" if passed else "veto", code_ref=code_ref,
        kind=kind, stage=stage)
    return passed


def drain() -> list[dict]:
    """取走当前线程的全部节点并清空（attach 到 Recommendation 时用）。"""
    nodes = _buf()
    _TLS.nodes = []
    return nodes


def peek() -> list[dict]:
    return list(_buf())


def ev(x) -> str:
    """枚举安全取值：Enum→value，None→'—'，其余 str()。trace 对可选字段的
    容忍度必须 ≥ selector 本身（selector 容 None 的地方 trace 不得 crash）。"""
    if x is None:
        return "—"
    return getattr(x, "value", None) or str(x)


# ── 人话语义辅助（数字带语义，§0）────────────────────────────────────────────

def ivp_phrase(ivp: float) -> str:
    """IV 百分位 → 人话（期权贵贱刻度）。"""
    if ivp >= 70:
        band = "偏贵（卖方premium丰厚但尾部风险高）"
    elif ivp >= 43:
        band = "中性偏上（premium 够付风险）"
    elif ivp >= 20:
        band = "偏便宜（premium 单薄）"
    else:
        band = "极便宜（几乎没premium可收）"
    return f"第 {ivp:.0f} 百分位（{band}）"


def vix_phrase(vix_level: float, regime: str) -> str:
    names = {"LOW_VOL": "低波动区（<15）", "NORMAL": "正常区（15-22）",
             "HIGH_VOL": "高波动区（≥22）"}
    return f"恐慌指数 VIX {vix_level:.1f} — {names.get(regime, regime)}"


def trend_phrase(signal: str, ma_gap_pct: float) -> str:
    names = {"BULLISH": "上升趋势", "BEARISH": "下降趋势", "NEUTRAL": "无明确趋势"}
    return (f"{names.get(signal, signal)}（价格相对 50 日均线 "
            f"{ma_gap_pct * 100:+.1f}%）")


# ── SPEC-135 装配层（select_strategy 之外的泳道数据，评估时组装）──────────────
# 这些层做 I/O（券商现金/治理状态/链快照），不进 select_strategy 纯函数；
# 由 /api/decision-trace 与日度落盘共用。全部 fail-soft。

def funding_trace(strategy_key: str) -> list[dict]:
    """Lane A ④ 资金检查层（SPEC-135 v2 新增；131 v2 口径渲染）。"""
    nodes: list[dict] = []
    try:
        from strategy.cash_budget_governance import (CAP_PCT, CASH_FLOOR_USD,
                                                     get_current_liquid_cash,
                                                     get_open_cash_collateral_total_usd)
        cash = get_current_liquid_cash()
        total = float(cash.get("total") or 0.0)
        available = cash.get("source") != "unavailable"
        nodes.append({
            "layer": "funding", "check": "cash_floor",
            "label_human": f"现金池余额 vs 底线（任何时候留足 ${CASH_FLOOR_USD:,.0f} 应急现金）",
            "detail": ((f"当前流动现金 ${total:,.0f} vs 底线 ${CASH_FLOOR_USD:,.0f}"
                        "——此门在开仓 API 有真实拦截路径（手动单可 pm_override）")
                       if available else "现金数据不可用（fail-soft，不拦）"),
            "inputs": {"liquid_cash": total if available else None,
                       "floor": CASH_FLOOR_USD, "source": cash.get("source")},
            "outcome": ("pass" if (available and total >= CASH_FLOOR_USD)
                        else ("veto" if available else "info")),
            "code_ref": "SPEC-115 cash floor", "branch_taken": True,
            "kind": "evidence", "stage": "capital",
        })
        if available:
            open_cash = float(get_open_cash_collateral_total_usd().get("total") or 0.0)
            cap = CAP_PCT * total
            headroom = cap - open_cash
            nodes.append({
                "layer": "funding", "check": "cash_budget",
                "label_human": (f"占用现金的策略预算 cap：最多用流动现金的 "
                                f"{CAP_PCT:.0%} 押在 debit/现金担保结构上"),
                "detail": (f"已占用 ${open_cash:,.0f} / cap ${cap:,.0f} → "
                           f"还可再部署约 ${max(headroom, 0):,.0f}"
                           "（允许张数 = 余量 ÷ 单张成本，随所选行权价而变）"
                           "——此门在开仓 API 有真实拦截路径（手动单可 pm_override）"),
                "inputs": {"open_cash": round(open_cash, 2), "cap_pct": CAP_PCT,
                           "headroom": round(headroom, 2)},
                "outcome": "pass" if headroom > 0 else "veto",
                "code_ref": "SPEC-111/115 cash budget", "branch_taken": True,
                "kind": "evidence", "stage": "capital",
            })
    except Exception as exc:
        nodes.append({"layer": "funding", "check": "cash_budget",
                      "label_human": "资金预算检查不可用（fail-soft，不拦）",
                      "detail": str(exc), "inputs": {}, "outcome": "info",
                      "code_ref": "SPEC-111/115", "branch_taken": True,
                      "kind": "evidence", "stage": "capital"})
    try:
        from strategy.exposure import evaluate_exposure_degrade
        deg = evaluate_exposure_degrade(strategy_key)
        if deg.get("pct_of_pool") is not None:
            detail = (f"家族并发 max loss ${deg['family_open_max_loss_usd']:,.0f} = "
                      f"占策略资金池 {deg['pct_of_pool']:.1f}%（阈值 "
                      f"{deg['threshold_pct']:.0f}%）——超阈值不禁止任何操作，仅改变推荐语气")
        else:
            detail = deg.get("note") or "敞口数据不可用"
        nodes.append({
            "layer": "exposure", "check": "family_exposure_degrade",
            "label_human": "同家族敞口占策略资金池比例（满仓时推荐降语气，不拦操作）",
            "detail": detail,
            "inputs": {k: deg.get(k) for k in
                       ("family", "family_open_max_loss_usd", "strategy_pool_usd",
                        "pct_of_pool", "threshold_pct", "degraded")},
            # SPEC-135.3：degraded = 提示不拦（改变推荐语气、不阻止任何操作）
            # → advisory（琥珀 ⚠），不再用 veto——PM 曾把它误读成最终拦截理由
            "outcome": "advisory" if deg.get("degraded") else "pass",
            "code_ref": "SPEC-131 v2", "branch_taken": True,
            "kind": "evidence", "stage": "capital",
        })
    except Exception as exc:
        nodes.append({"layer": "exposure", "check": "family_exposure_degrade",
                      "label_human": "敞口检查不可用（fail-soft，照常推荐）",
                      "detail": str(exc), "inputs": {}, "outcome": "info",
                      "code_ref": "SPEC-131 v2", "branch_taken": True,
                      "kind": "evidence", "stage": "capital"})
    # SPEC-135.2 — 账户级 crash-day defined-risk 容量线（Q091 定稿，display-only）
    try:
        from strategy.capacity import (Q091_CRASH_EXCESS_USD, capacity_copy,
                                       used_defined_risk)
        cap = used_defined_risk()
        nodes.append({
            "layer": "funding", "check": "account_dr_capacity",
            "label_human": capacity_copy(cap["used_usd"], cap["pct"] or 0.0),
            "detail": (f"全账户 defined-risk max loss 合计 ${cap['used_usd']:,.0f} vs "
                       f"crash-day 可部署容量 ${cap['capacity_usd']:,.0f}"
                       f"（= excess ${Q091_CRASH_EXCESS_USD:,.0f} − buffer "
                       f"${cap['buffer_usd']:,.0f}，Q091 P0 RATIFIED；"
                       "display-only，不做门）"),
            "inputs": {"used_usd": cap["used_usd"], "capacity_usd": cap["capacity_usd"],
                       "pct": cap["pct"],
                       "positions": [p["trade_id"] for p in cap["positions"]]},
            "outcome": "pass",
            "code_ref": "Q091", "branch_taken": True,
            "kind": "evidence", "stage": "capital",
        })
    except Exception as exc:
        nodes.append({"layer": "funding", "check": "account_dr_capacity",
                      "label_human": "账户级容量检查不可用（fail-soft，不拦）",
                      "detail": str(exc), "inputs": {}, "outcome": "info",
                      "code_ref": "Q091", "branch_taken": True,
                      "kind": "evidence", "stage": "capital"})
    return nodes


def lane_b_positions(today: str) -> list[dict]:
    """Lane B「手上的仓位要动吗？」— 每个 open 仓位一行，人话触发器状态。"""
    items: list[dict] = []
    try:
        from strategy.bcd_governance import evaluate_short_leg_actions, open_bcd_positions
        from strategy.campaign import current_short_leg
        actions = {a["trade_id"]: a for a in evaluate_short_leg_actions(today, None)}
        for pos in open_bcd_positions():
            cur = current_short_leg(pos)
            a = actions.get(pos["id"])
            if a:
                text = (f"卖出的近月 call 腿只剩 {a['short_dte']} 天到期 → "
                        "规则要求今天平掉或滚动（roll），已推送提醒")
                state = "action"
            else:
                from datetime import date as _date
                try:
                    dte = (_date.fromisoformat(str(cur.get("expiry"))[:10])
                           - _date.fromisoformat(today)).days
                    text = f"短腿还有 {dte} 天到期（>21 天），未触发任何管理规则 — 继续持有"
                except Exception:
                    text = "短腿到期日数据不可用"
                state = "hold"
            items.append({"trade_id": pos["id"], "state": state,
                          "label_human": text,
                          "code_ref": "SPEC-127 §4 (21-DTE/collapse)"})
    except Exception as exc:
        items.append({"trade_id": None, "state": "info",
                      "label_human": f"持仓触发器评估不可用（fail-soft）: {exc}",
                      "code_ref": "SPEC-127"})
    return items


def lane_c_terrain(date_str: str) -> dict:
    """Lane C「地形参考——只描述，不决策」：叙事句式 + 免责标注。"""
    out = {"disclaimer": "地形参考——只描述，不进任何决策与推送（Q090 封账口径）",
           "narrative": None, "available": False}
    try:
        from strategy.structure_map import progress, read_shadow
        rows = [r for r in read_shadow() if r.get("date") == date_str] or read_shadow()[-1:]
        if not rows:
            out["narrative"] = "结构 shadow 尚无记录（job 17:00 ET 日更）"
            return out
        r = rows[-1]
        prog = progress()
        parts = []
        walls = (r.get("walls") or {}).get("calls") or []
        if walls:
            tops = "与".join(f"{int(w['strike'])}" for w in walls[:2])
            dists = "/".join(f"{w['dist_pct']:+.1f}%" for w in walls[:2])
            parts.append(f"头顶期权持仓墙：{tops} 价位堆着最多机构 call 合约（距收盘 {dists}）")
        elif r.get("chain_missing"):
            parts.append(f"当日期权链快照缺失（最近 {r.get('chain_asof', '—')}），墙位不可用")
        if r.get("s3_flag"):
            parts.append(f"价格贴墙（<0.5%）——该状态正在积累记录，"
                         f"已记 {prog['s3_n']} 天/攒满 {prog['s3_target']} 天做正式统计检验")
        s1r = r.get("s1r_nearest")
        s4 = r.get("s4_line")
        near_bits = []
        if s1r and abs(s1r.get("dist_pct", 99)) < 1.0:
            near_bits.append(f"历史压力簇 {s1r['level']:.0f} 在价格附近（{s1r['dist_pct']:+.1f}%）")
        if r.get("s4_flag") and s4:
            near_bits.append(f"下降趋势线 {s4:.0f} 正压在价格上方")
        if near_bits:
            parts.append("；".join(near_bits) + "（Q090 无验证边际，仅描述）")
        else:
            parts.append("历史价位簇与下降趋势线今天都不在价格附近")
        if r.get("vol_ratio") is not None:
            vr = r["vol_ratio"]
            parts.append(f"今日量比 V/20d = {vr}（{'明显缩量' if vr < 0.85 else '正常量'}）")
        out["narrative"] = "；".join(parts) + "。"
        out["available"] = True
        out["row_date"] = r.get("date")
        # SPEC-135.4 §3：首页 SPX 卡底一行地形摘要（同一 shadow row 派生，
        # 代码自吐——前端只拼"地形（只描述，不进决策）：{summary_line}"外壳，
        # 零地形文案/阈值硬编码）。无墙位数据时不发（首页行 fail-soft 隐藏）。
        sl_bits = []
        if r.get("s3_flag"):
            sl_bits.append(f"贴 call 墙（<0.5%）已记 {prog['s3_n']} 天")
        if walls:
            wall_str = " · ".join(
                f"{int(w['strike'])}/{w['dist_pct']:+.1f}%" for w in walls[:2])
            sl_bits.append(wall_str if sl_bits else f"call 墙 {wall_str}")
        if sl_bits:
            out["summary_line"] = "——".join(sl_bits)
    except Exception as exc:
        out["narrative"] = f"地形数据不可用（fail-soft）: {exc}"
    return out
