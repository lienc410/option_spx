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
        # SPEC-138 F4: a partial read (a broker rail dropped) shrinks the cash
        # denominator; a floor/cap "breach" off that shrunk pool is a data
        # outage, NOT a governance verdict — degrade the trace node to advisory
        # (135.3 琥珀 ⚠ 提示档), never a red veto.
        degraded = cash.get("source") == "partial"
        stale_txt = ("　⚠ 数据降级：现金轨不齐（"
                     f"{cash.get('error') or '某轨缺席'}），同口径仅供参考，不作硬拦"
                     ) if degraded else ""
        if not available:
            floor_outcome = "info"
        elif total >= CASH_FLOOR_USD:
            floor_outcome = "pass"
        elif degraded:
            floor_outcome = "advisory"
        else:
            floor_outcome = "veto"
        nodes.append({
            "layer": "funding", "check": "cash_floor",
            "label_human": f"现金池余额 vs 底线（任何时候留足 ${CASH_FLOOR_USD:,.0f} 应急现金）",
            "detail": ((f"当前流动现金 ${total:,.0f} vs 底线 ${CASH_FLOOR_USD:,.0f}"
                        "——此门在开仓 API 有真实拦截路径（手动单可 pm_override）"
                        + stale_txt)
                       if available else "现金数据不可用（fail-soft，不拦）"),
            "inputs": {"liquid_cash": total if available else None,
                       "floor": CASH_FLOOR_USD, "source": cash.get("source"),
                       "rail_complete": cash.get("source") == "live"},
            "outcome": floor_outcome,
            "code_ref": "SPEC-115 cash floor", "branch_taken": True,
            "kind": "evidence", "stage": "capital",
        })
        if available:
            open_cash = float(get_open_cash_collateral_total_usd().get("total") or 0.0)
            cap = CAP_PCT * total
            headroom = cap - open_cash
            if headroom > 0:
                budget_outcome = "pass"
            elif degraded:
                budget_outcome = "advisory"
            else:
                budget_outcome = "veto"
            nodes.append({
                "layer": "funding", "check": "cash_budget",
                "label_human": (f"占用现金的策略预算 cap：最多用流动现金的 "
                                f"{CAP_PCT:.0%} 押在 debit/现金担保结构上"),
                "detail": (f"已占用 ${open_cash:,.0f} / cap ${cap:,.0f} → "
                           f"还可再部署约 ${max(headroom, 0):,.0f}"
                           "（允许张数 = 余量 ÷ 单张成本，随所选行权价而变）"
                           "——此门在开仓 API 有真实拦截路径（手动单可 pm_override）"
                           + stale_txt),
                "inputs": {"open_cash": round(open_cash, 2), "cap_pct": CAP_PCT,
                           "headroom": round(headroom, 2),
                           "rail_complete": cash.get("source") == "live"},
                "outcome": budget_outcome,
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
        # SPEC-138 F4: a partial cash read shrinks the pool denominator and
        # inflates pct_of_pool past threshold purely from the missing rail
        # (7/7: 33.5%→42%). exposure.py already holds degraded=False on a
        # partial read; the trace surfaces the staleness note as advisory, not
        # a clean pass, so the PM sees "数据降级" not "敞口已满".
        rail_incomplete = deg.get("rail_complete") is False
        if rail_incomplete and deg.get("note"):
            detail = deg["note"]
        elif deg.get("pct_of_pool") is not None:
            detail = (f"家族并发 max loss ${deg['family_open_max_loss_usd']:,.0f} = "
                      f"占策略资金池 {deg['pct_of_pool']:.1f}%（阈值 "
                      f"{deg['threshold_pct']:.0f}%）——超阈值不禁止任何操作，仅改变推荐语气")
        else:
            detail = deg.get("note") or "敞口数据不可用"
        if deg.get("degraded"):
            exp_outcome = "advisory"
        elif rail_incomplete:
            exp_outcome = "advisory"   # 缺轨 staleness：不判 pass，也绝不 veto
        else:
            exp_outcome = "pass"
        nodes.append({
            "layer": "exposure", "check": "family_exposure_degrade",
            "label_human": "同家族敞口占策略资金池比例（满仓时推荐降语气，不拦操作）",
            "detail": detail,
            "inputs": {k: deg.get(k) for k in
                       ("family", "family_open_max_loss_usd", "strategy_pool_usd",
                        "pct_of_pool", "threshold_pct", "degraded", "rail_complete")},
            # SPEC-135.3：degraded = 提示不拦（改变推荐语气、不阻止任何操作）
            # → advisory（琥珀 ⚠），不再用 veto——PM 曾把它误读成最终拦截理由
            "outcome": exp_outcome,
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


# ═══ SPEC-140 §1 — Lane B/D 人话主文唯一 copy 源 ═════════════════════════════
# 同一触发器的人话主文只此一处：推送（bcd_governance H-5 ACTION 正文首行、
# q042 executor alert 状态行、15:55 digest 持仓行/联动线附行）与
# /api/decision-trace 对应节点全部 import 下面的纯函数渲染——推送与网页
# 逐字相等是 AC（tests/test_spec_140.py 断言 ×4），任何一方不得手写第二套。
# 纯函数、零 I/O；触发器判定与阈值逻辑留在各自生产模块
# （bcd_governance / q042_gate），这里只负责"人话怎么说"。
# ES Ladder 状态已由 SPEC-135.5 同源（web.server.hvladder_live_payload
# .status_human），验收沿用，不在此重复。

_LANE_B_ACTION_TAIL = " → 规则要求今天平掉或滚动（roll），已推送提醒"


def lane_b_action_label(action: dict) -> str:
    """Lane B 触发行主文（21-DTE / collapse buyback 双触发，SPEC-127 §4）。

    输入 = strategy.bcd_governance.evaluate_short_leg_actions 的 action dict
    （dte_trigger / collapse_trigger / residual_frac 由触发器引擎判定并随
    action 携带——阈值不在本层重推）。21-DTE 档行文与 SPEC-135 时期 Lane B
    逐字一致；collapse 档为 SPEC-140 补齐的触发器专属行文（此前 Lane B 对
    collapse 触发误用 DTE 行文渲染）。缺结构化标记的旧 action dict 按
    DTE 档渲染（向后兼容）。"""
    dte_hit = bool(action.get("dte_trigger", True))
    collapse_hit = bool(action.get("collapse_trigger"))
    frac = action.get("residual_frac")
    frac_txt = f"{frac:.0%}" if isinstance(frac, (int, float)) else "—"
    if dte_hit and collapse_hit:
        return (f"卖出的近月 call 腿只剩 {action.get('short_dte')} 天到期，"
                f"且残值只剩入场权利金的 {frac_txt}（collapse buyback）"
                f"{_LANE_B_ACTION_TAIL}")
    if collapse_hit:
        return (f"卖出的近月 call 腿残值只剩入场权利金的 {frac_txt}"
                f"（collapse buyback 触发）{_LANE_B_ACTION_TAIL}")
    return (f"卖出的近月 call 腿只剩 {action.get('short_dte')} 天到期"
            f"{_LANE_B_ACTION_TAIL}")


def lane_b_hold_label(dte: int, action_dte_threshold: int) -> str:
    """Lane B 未触发行主文（阈值 = bcd_governance.SHORT_ACTION_DTE，由调用方
    传入——不在本层镜像常数）。"""
    return (f"短腿还有 {dte} 天到期（>{action_dte_threshold} 天），"
            "未触发任何管理规则 — 继续持有")


def lane_d_linkage_label(*, gate_available: bool, main_bp, budget: float,
                         cap, allowance, binding: bool) -> tuple[str, str]:
    """Lane D「与主策略的联动」主文 + outcome（唯一 copy 源，SPEC-140 §1）。

    消费方：_lane_d_dd_overlay 联动线节点、q042 executor 拦截/gate 不可用
    alert 的状态行、digest D 泳道联动线附行。数值由调用方从生产真值传入
    （gate log 最新行 / compute_gate 结果）；公式与判定只活在 q042_gate。
    outcome：pass=未压缩 ／ advisory=压缩或 fail-closed ／ veto=容量归零
    （真拦截：overlay 开仓被联合门实际挡下）。行文与 SPEC-135.5 逐字一致。"""
    if not gate_available or main_bp is None:
        return ("与主策略的联动：主策略 BP 读数不可用 → 联合门 "
                "fail-closed，DD Overlay 容量归零", "advisory")
    if not binding:
        return (f"与主策略的联动：主策略 BP 占用 {main_bp:.1f}% vs "
                f"预算线 {budget:.0f}% → DD Overlay 容量档位 "
                f"{allowance:.1f}%（联合门未压缩）", "pass")
    if cap and cap > 0:
        return (f"与主策略的联动：主策略 BP 占用 {main_bp:.1f}% 挤占 "
                f"{budget:.0f}% 预算线 → DD Overlay 容量档位被压缩到 "
                f"{allowance:.1f}%", "advisory")
    return (f"与主策略的联动：主策略 BP 占用 {main_bp:.1f}% ≥ "
            f"{budget:.0f}% 预算线 → DD Overlay 容量归零"
            "（双 sleeve 禁开）", "veto")


def q101_staging_label(staging: dict) -> tuple[str, str]:
    """SPEC-143 — Q101 aftermath 首笔 0.5× staging 三态人话主文 + outcome
    （唯一 copy 源）。

    消费方：selector._apply_aftermath_staging_live 的 Lane A trace 节点、
    /api/recommendation 卡片 rationale 附注、/api/position/open-draft 的
    legs_hint 附注——三处逐字相等是 AC（tests/test_spec_143.py，断言样式同
    SPEC-140）；任何一方不得手写第二套。判定逻辑与常量只活在
    strategy/aftermath_staging.py（本层只负责"人话怎么说"）。
    outcome：advisory（态 1/3，⚠ 提示档改张数不拦推荐，非 veto）／
    pass（态 2，实测通过按标准张数）。
    """
    state = staging.get("state")
    s = staging.get("s")
    if state == 2:
        return (f"Q101 staging：skew 实测通过（s = {s:.2f} < 1.5× calm 基线）"
                "——按标准张数", "pass")
    if state == 3:
        return (f"Q101 staging：实测 put 斜率 s = {s:.2f} ≥ 1.5× calm 基线，"
                "维持 0.5× —— Q101 预承诺复判触发，通道处置待 Quant 重跑判定网格",
                "advisory")
    return ("Q101 staging：本窗口 skew 未实测，首笔 0.5×，实测落地后恢复",
            "advisory")


def lane_b_positions(today: str, calls=None) -> list[dict]:
    """Lane B「手上的仓位要动吗？」— 每个 open 仓位一行，人话触发器状态。

    行文 = lane_b_action_label / lane_b_hold_label（SPEC-140 §1 唯一 copy
    源，与 H-5 推送正文首行逐字相等）。calls: 可选当日 call 链（collapse
    残值触发器需要链数据；缺省 None 与既有 /api 现算行为一致——只评估
    DTE 触发）。"""
    items: list[dict] = []
    try:
        from strategy.bcd_governance import (SHORT_ACTION_DTE,
                                             evaluate_short_leg_actions,
                                             open_bcd_positions)
        from strategy.campaign import current_short_leg
        actions = {a["trade_id"]: a for a in evaluate_short_leg_actions(today, calls)}
        for pos in open_bcd_positions():
            cur = current_short_leg(pos)
            a = actions.get(pos["id"])
            if a:
                text = lane_b_action_label(a)
                state = "action"
            else:
                from datetime import date as _date
                try:
                    dte = (_date.fromisoformat(str(cur.get("expiry"))[:10])
                           - _date.fromisoformat(today)).days
                    text = lane_b_hold_label(dte, SHORT_ACTION_DTE)
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


# ═══ SPEC-135.5 — Lane D「Sleeve 决策引擎泳道」═══════════════════════════════
# 语义：这些引擎真实决策（armed/触发/容量分配/信号），区别于 Lane C 的
# "只描述不决策"。每台引擎一行（人话主行 + badge + hover 三件套），
# stage="sleeve"，kind/stage 契约沿 SPEC-135.1。
#
# 数据同源铁律（AC：静态断言零旁路重推，tests/test_spec_135_5.py）：
#   DD Overlay   ← web.server.q042_state_payload（= /api/q042/state 同一组装点）
#   联动线       ← strategy.q042_gate.read_latest_gate_row（F3 联合门日度落盘，
#                  main_bp/cap/src 逐字段照抄；公式只活在 q042_gate.compute_gate）
#   Aftermath    ← web.server.aftermath_state_payload（selector.is_aftermath 同函数）
#   压力状态机   ← strategy.sleeve_governance 生产函数（_latest_market_stress /
#                  booster_signal_conditions / active_spx_cap / booster_mode /
#                  ladder_mode——与 /api/sleeve-governance/state 同一批真值函数）
#   ES Ladder    ← web.server.hvladder_live_payload.status_human（与首页
#                  Stress Put Ladder 卡同一 copy 源，词不在本层重组）
# badge 词表 = DESIGN.md Action State + Signal-outcome states（ARMED/WATCHING/
# SIGNAL/HOLD/NO ENTRY/WARNING/CALM/BLOCKED），不得自造。
# web.server 的 import 全部惰性（调用时 web.server 必已在 sys.modules——
# 唯一生产调用方就是 /api/decision-trace 路由本身）。

LANE_D_SEMANTICS = ("决策引擎状态——它们真实决策（armed/触发/容量/信号），"
                    "区别于 Lane C 的只描述")


def _sleeve_node(check: str, label_human: str, *, summary: str | None = None,
                 badge_word: str | None = None, badge_label: str | None = None,
                 detail: str = "", inputs: dict | None = None,
                 outcome: str = "info", code_ref: str = "",
                 kind: str = "verdict") -> dict:
    """Lane D 节点（135.1 契约字段 + badge/summary 纯附加两字段）。"""
    node = {
        "layer": "sleeve", "check": check, "label_human": label_human,
        "detail": detail, "inputs": inputs or {}, "outcome": outcome,
        "code_ref": code_ref, "branch_taken": True,
        "kind": kind, "stage": "sleeve",
        "summary": summary,
    }
    if badge_word:
        node["badge"] = {"word": badge_word, "label": badge_label or badge_word}
    return node


def _lane_d_dd_overlay() -> list[dict]:
    """DD Overlay 引擎行 + 联动线（本泳道的灵魂）。"""
    nodes: list[dict] = []
    try:
        from web.server import q042_state_payload
        from signals.q042_trigger import (_DD4_THRESHOLD, _DD15_THRESHOLD,
                                          _REARM_THRESHOLD)
        st = q042_state_payload()
        ddath = st.get("ddath_pct")                    # 已是 % 值（负 = 回撤）
        degraded = bool(st.get("ath_degraded"))
        a = st.get("sleeve_a") or {}
        b = st.get("sleeve_b") or {}
        # payload 的 active_position 可能携带已结算历史仓（is_active=False，如
        # grandfather 补录）——HOLD 语义 = 有活仓，必须按 is_active 过滤，否则
        # 零持仓被渲染成 HOLD（词表违规，2026-07-11 生产实测抓获）
        def _live(p):
            return p if (p and p.get("is_active", True)) else None
        a_pos = _live(a.get("active_position"))
        # SPEC-094.7: B 为阶梯多仓（active_positions 列表）；legacy 单仓字段兜底
        b_pos_list = [pp for pp in (b.get("active_positions") or []) if _live(pp)]
        if not b_pos_list and _live(b.get("active_position")):
            b_pos_list = [b.get("active_position")]
        b_pos = b_pos_list[0] if b_pos_list else None
        b_rungs = b.get("rungs") or {}
        b_armed_n = sum(1 for r in b_rungs.values() if r.get("armed"))
        trig_a = _DD4_THRESHOLD * 100                  # -4.0
        trig_b = _DD15_THRESHOLD * 100                 # -15.0
        rearm = _REARM_THRESHOLD * 100                 # -2.0

        def _strike(v) -> str:
            return f"{v:g}" if isinstance(v, (int, float)) else "—"

        def _pos_phrase(tag: str, p: dict) -> str:
            # SPEC-094.7 instrument-aware（原文案误写 put spread——结构是 call）
            rung_s = ""
            if p.get("rung") is not None:
                try:
                    rung_s = f"（rung {float(p['rung'])*100:+.0f}%）"
                except (TypeError, ValueError):
                    pass
            if p.get("instrument") == "XSP_LEAP":
                struct = f"{_strike(p.get('long_strike'))} XSP ITM LEAP 单腿"
            else:
                struct = (f"{_strike(p.get('long_strike'))}/"
                          f"{_strike(p.get('short_strike'))} call spread")
            return (f"Sleeve {tag}{rung_s} 已挂仓（{p.get('contracts', '—')} 张 "
                    f"{struct}，{p.get('expiry_date', '—')} 到期还剩 "
                    f"{p.get('days_to_expiry', '—')} 天）")

        if a_pos or b_pos_list:
            phrases = ([_pos_phrase("A", a_pos)] if a_pos else []) +                       [_pos_phrase("B", p) for p in b_pos_list]
            label = "DD Overlay：" + "；".join(phrases)
            badge_word, badge_label = "HOLD", "HOLD"
            summary = "DD Overlay HOLD"
            outcome = "info"
        elif a.get("armed") and b.get("armed"):
            # SPEC-094.7: B 是阶梯（4 档），×2 语义退役 → A + B n/4 档
            b_tag = (f"B {b_armed_n}/{len(b_rungs)} 档" if b_rungs else "B")
            if degraded:
                label = f"DD Overlay：待命中（A + {b_tag}）"
            else:
                gap = ddath - trig_a                   # 距 A 触发线还差几个百分点
                label = (f"DD Overlay：待命中（A + {b_tag}；回撤 {ddath:+.1f}%，"
                         f"距 Sleeve A 触发线 {trig_a:.0f}% 还差 {gap:.1f}pp）")
            badge_word, badge_label = "ARMED", f"ARMED A+{b_armed_n or ''}"
            summary = f"DD Overlay ARMED（A + {b_tag}）"
            outcome = "info"
        elif a.get("armed") or b.get("armed"):
            armed_tag = "A" if a.get("armed") else "B"
            label = (f"DD Overlay：仅 Sleeve {armed_tag} 待命"
                     + ("" if degraded else f"（回撤 {ddath:+.1f}%）"))
            badge_word, badge_label = "ARMED", f"ARMED {armed_tag}"
            summary = f"DD Overlay ARMED（{armed_tag}）"
            outcome = "info"
        else:
            label = (f"DD Overlay：已触发过、等待重新武装"
                     f"（回撤回到 {rearm:.0f}% 以内才重新 armed）")
            badge_word, badge_label = "NO ENTRY", "NO ENTRY"
            summary = "DD Overlay 待重新武装"
            outcome = "info"
        if degraded:
            # SPEC-094.2 F7 语义：state ATH 缺失/为 0 → ddath 是中性填充值，
            # 不是真回撤读数——显式标注 + 琥珀提示档
            label += "｜⚠ ATH 基准缺失（degraded，F7）——回撤读数不可用"
            outcome = "advisory"
        nodes.append(_sleeve_node(
            "dd_overlay", label,
            summary=summary, badge_word=badge_word, badge_label=badge_label,
            detail=(f"ddATH = SPX 收盘 ÷ 2007 起 running ATH − 1 = "
                    f"{'不可用（ATH degraded）' if degraded else f'{ddath:+.2f}%'} · "
                    f"Sleeve A 触发线 {trig_a:.0f}%（T+1 直接开）· "
                    f"Sleeve B 阶梯 {trig_b:.0f}/−25/−35/−45%（touch 即 fire，"
                    f"SPEC-094.7；浅档 spread D90，深档 XSP LEAP D730）· "
                    f"re-arm 线 {rearm:.0f}%（全档复位）· Sleeve A 生产档 cap "
                    f"{a.get('production_cap_pct', '—')}%（{a.get('stage', '—')}，"
                    f"paper）· Sleeve B research_only"),
            inputs={"date": st.get("date"), "ddath_pct": ddath,
                    "ath_degraded": degraded,
                    "sleeve_a_armed": a.get("armed"),
                    "sleeve_b_armed": b.get("armed"),
                    "sleeve_b_rungs_armed": b_armed_n,
                    "positions": ([a_pos.get("trade_id")] if a_pos else [])
                                 + [p.get("trade_id") for p in b_pos_list]},
            outcome=outcome,
            code_ref="SPEC-094 F1 · signals/q042_trigger · /api/q042/state"))
    except Exception as exc:
        nodes.append(_sleeve_node(
            "dd_overlay", f"DD Overlay：状态不可用（fail-soft）: {exc}",
            summary="DD Overlay 不可用", detail=str(exc),
            code_ref="SPEC-094 F1"))

    # 联动线：主策略 BP → DD Overlay 容量档位（F3 联合门第一次有显示面；
    # 数据 = gate log 最新行 main_bp/cap/src 逐字段照抄，公式不在此重推）
    try:
        from strategy.q042_gate import (_MAIN_BP_BUDGET, read_latest_gate_row)
        row = read_latest_gate_row()
        budget = _MAIN_BP_BUDGET
        if row is None:
            nodes.append(_sleeve_node(
                "dd_overlay_main_linkage",
                "与主策略的联动：联合门 gate log 尚无记录（F3 日更 09:40 ET 落盘）",
                kind="evidence",
                code_ref="SPEC-094.2 F3 · strategy/q042_gate"))
        else:
            main_bp = row.get("main_bp_pct")
            cap = row.get("q042_combined_cap")
            a_allow = row.get("sleeve_a_allowance")
            b_allow = row.get("sleeve_b_allowance")
            binding = bool(row.get("gate_binding"))
            src = row.get("bp_source") or {}
            inputs = {"date": row.get("date"), "main_bp_pct": main_bp,
                      "q042_combined_cap": cap,
                      "sleeve_a_allowance": a_allow,
                      "sleeve_b_allowance": b_allow,
                      "gate_binding": binding,
                      "src": src.get("source"),
                      "src_timestamp": src.get("timestamp")}
            # SPEC-140 §1 — 联动线主文与 outcome 由唯一 copy 源渲染
            # （lane_d_linkage_label；q042 executor alert 状态行同函数）
            label, outcome = lane_d_linkage_label(
                gate_available=row.get("gate_available") is not False,
                main_bp=main_bp, budget=budget, cap=cap,
                allowance=a_allow, binding=binding)
            nodes.append(_sleeve_node(
                "dd_overlay_main_linkage", label, kind="evidence",
                detail=(f"gate log {row.get('date')} 行：main_bp "
                        f"{main_bp if main_bp is not None else '—'}% · combined cap {cap}% · "
                        f"Sleeve A 档 {a_allow}% / B 档 {b_allow}% · "
                        f"binding={binding} · BP 读数源 {src.get('source') or '—'} "
                        f"@ {src.get('timestamp') or '—'}"
                        "（公式与判定只活在 q042_gate.compute_gate；本行只读日度落盘）"),
                inputs=inputs, outcome=outcome,
                code_ref="SPEC-094 F3 / SPEC-094.2 · strategy/q042_gate"))
    except Exception as exc:
        nodes.append(_sleeve_node(
            "dd_overlay_main_linkage",
            f"与主策略的联动：联合门读数不可用（fail-soft）: {exc}",
            kind="evidence", detail=str(exc),
            code_ref="SPEC-094.2 F3"))
    return nodes


def _lane_d_aftermath() -> dict:
    """Aftermath 余波窗口引擎行（is_aftermath 与 selector 同一函数）。"""
    try:
        from web.server import aftermath_state_payload
        am = aftermath_state_payload()
        vix = am.get("vix")
        peak = am.get("vix_peak_10d")
        off = am.get("off_peak_pct")
        thr_peak = am.get("threshold_peak_min")
        thr_off = am.get("threshold_off_peak_pct")
        thr_max = am.get("threshold_vix_max")   # = params.extreme_vix（SPEC-144 单源）
        regime = am.get("regime") or "—"
        detail = (f"触发三条件（is_aftermath，与 selector 同一函数）："
                  f"10 日 VIX 峰值 ≥ {thr_peak:.0f}（现 {peak if peak is not None else '—'}）· "
                  f"自峰值回落 ≥ {thr_off:.0f}%（现 {off if off is not None else '—'}%）· "
                  f"VIX < {thr_max:.0f}（现 {vix}）")
        inputs = {k: am.get(k) for k in
                  ("active", "vix", "vix_peak_10d", "off_peak_pct",
                   "threshold_peak_min", "threshold_off_peak_pct",
                   "threshold_vix_max", "regime", "reason", "date")}
        if am.get("active"):
            return _sleeve_node(
                "aftermath_window",
                (f"Aftermath 余波窗口：已激活（VIX 从 10 日峰值 {peak} 回落 "
                 f"{off:.0f}%，HIGH_VOL 特批结构解锁）"),
                summary="Aftermath SIGNAL", badge_word="SIGNAL",
                detail=detail, inputs=inputs, outcome="pass",
                code_ref="strategy/selector.is_aftermath · /api/aftermath/state")
        reason = str(am.get("reason") or "")
        if reason.startswith("no_peak_data"):
            why = "10 日 VIX 峰值数据缺失"
        elif reason.startswith("peak_below_threshold"):
            why = (f"10 日峰值 {peak} 未达 {thr_peak:.0f}，无恐慌尖峰可回落"
                   f"——当前 regime {regime}")
        elif reason.startswith("vix_above_extreme"):
            why = f"VIX {vix} 仍在 {thr_max:.0f} 极端区上方"
        elif reason.startswith("insufficient_off_peak"):
            why = f"VIX {vix} 距峰值 {peak} 只回落 {off}%（需 ≥{thr_off:.0f}%）"
        else:
            why = "触发条件未满足"
        return _sleeve_node(
            "aftermath_window", f"Aftermath 余波窗口：未激活（{why}）",
            summary="Aftermath 未激活", badge_word="NO ENTRY",
            detail=detail, inputs=inputs, outcome="info",
            code_ref="strategy/selector.is_aftermath · /api/aftermath/state")
    except Exception as exc:
        return _sleeve_node(
            "aftermath_window",
            f"Aftermath 余波窗口：状态不可用（fail-soft）: {exc}",
            summary="Aftermath 不可用", detail=str(exc),
            code_ref="strategy/selector.is_aftermath")


def _lane_d_stress_machine() -> dict:
    """Sleeve 压力状态机引擎行（SPEC-103/105/108 生产函数同源）。"""
    try:
        from strategy.sleeve_governance import (_latest_market_stress,
                                                active_spx_cap,
                                                booster_mode,
                                                booster_signal_conditions,
                                                ladder_mode)
        market = _latest_market_stress()
        bmode, lmode = booster_mode(), ladder_mode()
        if market.get("status") != "available":
            return _sleeve_node(
                "sleeve_stress_machine",
                (f"Sleeve 压力状态机：市场读数不可用"
                 f"（{market.get('reason') or '—'}）——fail-closed，"
                 "booster 不给、cap 按常规档"),
                summary="压力机读数不可用",
                detail=f"booster {bmode} / entry ladder {lmode}",
                inputs={"status": market.get("status"),
                        "reason": market.get("reason"),
                        "booster_mode": bmode, "ladder_mode": lmode},
                code_ref="SPEC-103/105 · strategy/sleeve_governance")
        cond = booster_signal_conditions(market)
        cap_pct, cap_regime = active_spx_cap(market)
        regime_human = {
            "second_leg": f"二次下探 episode（SPX PM cap 压到 {cap_pct:.0f}%）",
            "stress": f"stress episode 进行中（SPX PM cap 压到 {cap_pct:.0f}%）",
            "booster": f"benign booster 生效（SPX PM cap 提到 {cap_pct:.0f}%）",
            "booster_shadow": (f"benign 条件全数满足（booster 处 shadow 档，"
                               f"生产 cap 仍 {cap_pct:.0f}%）"),
            "normal": f"正常态（SPX PM cap {cap_pct:.0f}%）",
        }.get(cap_regime, f"{cap_regime}（SPX PM cap {cap_pct:.0f}%）")
        stressed = bool(market.get("stress_episode_active")) or \
            bool(market.get("second_leg_active"))
        ddath = market.get("ddath")
        vix5 = market.get("vix_5d_change")
        ivp = market.get("ivp252")

        def _fx(key: str) -> str:
            return "✓" if cond.get(key) else "✗"

        detail = (
            "warm-up/benign 条件逐条（B4）："
            f"数据齐备 {_fx('warmed')} · 无 stress {_fx('no_stress')} · "
            f"无二次下探 {_fx('no_second_leg')} · "
            f"SPX>MA50 {_fx('trend_ok')}（{market.get('spx_close')} vs "
            f"{market.get('ma50')}）· "
            f"ddATH>-4% {_fx('ddath_ok')}（现 "
            f"{f'{ddath * 100:+.1f}%' if ddath is not None else '—'}）· "
            f"VIX<22 {_fx('vix_ok')}（现 {market.get('vix')}）· "
            f"VIX 5d 变化≤+1.5 {_fx('vix5d_ok')}（现 "
            f"{vix5 if vix5 is not None else '—'}）· "
            f"IVP252<55（或 VIX<15 逃逸）{_fx('ivp_gate_pass')}（现 "
            f"{ivp if ivp is not None else '—'}）；"
            "stress 合成 = VIX≥22 ∨ 20d 回撤≤−4% ∨ 60d 回撤≤−4%"
        )
        return _sleeve_node(
            "sleeve_stress_machine",
            (f"Sleeve 压力状态机：{regime_human} · booster {bmode} / "
             f"entry ladder {lmode}"),
            summary=f"压力机 {'WARNING' if stressed else 'CALM'}",
            badge_word="WARNING" if stressed else "CALM",
            detail=detail,
            inputs={"cap_pct": cap_pct, "cap_regime": cap_regime,
                    "booster_mode": bmode, "ladder_mode": lmode,
                    "stress_episode_active": market.get("stress_episode_active"),
                    "second_leg_active": market.get("second_leg_active"),
                    "vix": market.get("vix"), "ddath": ddath,
                    "dd_20d": market.get("dd_20d"),
                    "dd_60d": market.get("dd_60d"),
                    "conditions": {k: bool(v) for k, v in cond.items()}},
            outcome="advisory" if stressed else "info",
            code_ref="SPEC-103/105/108 · strategy/sleeve_governance")
    except Exception as exc:
        return _sleeve_node(
            "sleeve_stress_machine",
            f"Sleeve 压力状态机：状态不可用（fail-soft）: {exc}",
            summary="压力机不可用", detail=str(exc),
            code_ref="SPEC-103 · strategy/sleeve_governance")


def _lane_d_es_ladder() -> dict:
    """ES Ladder 引擎行——与首页 Stress Put Ladder 卡同一 copy 源
    （status_human 只在 hvladder_live_payload 组装）。"""
    try:
        from web.server import hvladder_live_payload
        hv = hvladder_live_payload()
        sh = hv.get("status_human") or {}
        label = (f"ES Ladder（Stress Put Ladder /ES）：{sh.get('slots_text')} · "
                 f"{sh.get('state_text')}")
        vix_c = hv.get("vix_current")
        avg5 = hv.get("vix_5td_avg")
        cad = hv.get("cadence_elapsed_trading_days")
        return _sleeve_node(
            "es_ladder", label,
            summary=f"ES Ladder {sh.get('badge_label')}",
            badge_word=sh.get("badge_word"), badge_label=sh.get("badge_label"),
            detail=(f"VIX {f'{vix_c:.1f}' if isinstance(vix_c, (int, float)) else '—'} / 门槛 "
                    f"{hv.get('threshold')}（5 日均 "
                    f"{f'{avg5:.1f}' if isinstance(avg5, (int, float)) else '—'}）· "
                    f"cadence 距上次 entry {cad if cad is not None else '—'} "
                    f"个交易日 · {hv.get('research_only_note')}"),
            inputs={"active_slots": hv.get("active_slots"),
                    "max_slots": hv.get("max_slots"),
                    "vix_current": vix_c, "threshold": hv.get("threshold"),
                    "blockers": hv.get("blockers"),
                    "signal_live": hv.get("signal_live"),
                    "status": hv.get("status")},
            outcome="info",
            code_ref="SPEC-104 / Q071 HV Ladder · /api/hvladder/live")
    except Exception as exc:
        return _sleeve_node(
            "es_ladder", f"ES Ladder：状态不可用（fail-soft）: {exc}",
            summary="ES Ladder 不可用", detail=str(exc),
            code_ref="SPEC-104 / Q071 HV Ladder")


def lane_d_sleeves() -> dict:
    """Lane D 全泳道（当日现算；历史不存档，v1 与 Lane B 同口径）。"""
    engines = _lane_d_dd_overlay() + [
        _lane_d_aftermath(),
        _lane_d_stress_machine(),
        _lane_d_es_ladder(),
    ]
    summary_line = " · ".join(n["summary"] for n in engines if n.get("summary"))
    return {
        "semantics": LANE_D_SEMANTICS,
        "engines": engines,
        "summary_line": summary_line or None,
    }
