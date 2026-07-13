"""SPEC-131 — 组合敞口真值（SPEC-129 entry-risk 单一真值函数下沉到中立模块）.

web/server.py 的 entry-risk 端点与 notify/telegram_bot 的晨报共用这里的
定义——bot 进程不 import Flask app。函数语义与 SPEC-129 落地版逐字一致
（server 侧保留薄别名）。

SPEC-131 规则（PM ratify 2026-07-07，阈值 T=40%）：
  每日推荐生成时计算目标策略家族并发 max loss / 流动现金；≥ T → 推荐卡与
  晨报降级为"条件满足，敞口已满（家族并发 $X = Y% ≥ T%）——非加仓号召"，
  ACTION 类降 STATE 语气。
  不拦手动开仓；不碰 selector 信号逻辑（显示/推送层，非新门）；分母不可用
  fail-soft（照常推荐 + 标注 n/a）。
  与 SPEC-079 的本质区别：079 是市场状态否决（Q087 A4 证零保护价值）；本
  规则是组合状态陈述——不预测市场，只陈述账户事实。
"""
from __future__ import annotations

import logging

log = logging.getLogger("exposure")

# PM ratify 2026-07-07（v2 同日口径修正）— 敞口降级阈值：
# 家族并发 max loss / 策略资金池（流动现金 + 全部已部署 debit 风险资本）。
# v1 曾以纯流动现金为分母、阈值 40%——分子分母不同池（debit 已付资本不在
# 现金里），v2 修正分母并重 ratify 阈值 30%（≈ 原意图等效换算 28.6% 取整；
# 7/7 实值 33.5% 仍触发，保持原 ratify 意图）。
EXPOSURE_DEGRADE_THRESHOLD_PCT = 30.0

# Q088 A5 housekeeping（自 web/server.py 下沉，2026-07-12 state-surface lanes
# 需要非 Flask 读取）：/ES per-contract SPAN margin 随 SPX 水位漂移，Schwab API
# 不暴露 per-position futures-option margin（memory: research_pm_bp_calculation）
# —— 保持"实测常量 + as-of 日期 + staleness 面"。过期时 /es BP gate payload 带
# warning（PM 在 open-draft 流程可见），不静默用旧值 gate。
# 刷新方式：TOS 读 1-lot /ES short put 实际 BP effect，更新这两个值。
ES_BP_PER_CONTRACT = 20_529.0
ES_BP_PER_CONTRACT_AS_OF = "2026-05-08"   # last TOS measurement (SPEC-089 era)
ES_BP_STALE_AFTER_DAYS = 90


def _num(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def strategy_family(strategy_key: str) -> str:
    """SPEC-129 §3 — 并发风险的家族口径：同策略含 _hv 变体（bull_put_spread 与
    bull_put_spread_hv 同家族；BCD 家族 = bull_call_diagonal，同 SPEC-123 用法）。"""
    k = str(strategy_key or "").strip().lower()
    return k[:-3] if k.endswith("_hv") else k


def estimate_bp_per_contract(strategy_key: str, short_strike, long_strike, premium) -> float | None:
    """Schwab PM BP ≈ max loss（研究结论：spread ≈ max_loss；BCD = debit×100）。
    SPEC-129 从 web/server._estimate_bp_per_contract 原样下沉。"""
    short_k = _num(short_strike)
    long_k = _num(long_strike)
    premium_val = abs(_num(premium) or 0.0)
    width = abs(short_k - long_k) if short_k is not None and long_k is not None else None

    if strategy_key == "bull_call_diagonal":
        return round(max(premium_val * 100.0, 0.0), 2)

    if strategy_key in {
        "bull_put_spread",
        "bull_put_spread_hv",
        "bear_call_spread_hv",
        "iron_condor",
        "iron_condor_hv",
    }:
        if width is None:
            return None
        return round(max((width - premium_val) * 100.0, 0.0), 2)

    if width is not None:
        return round(max((width - premium_val) * 100.0, 0.0), 2)
    return round(max(premium_val * 100.0, 0.0), 2)


def order_max_loss_usd(strategy_key: str, short_strike, long_strike, premium, contracts) -> float | None:
    """本单 max loss $（今日尺度绝对值）。credit 结构 = (width−credit)×100×n；
    debit 结构 = |debit|×100×n。"""
    per_contract = estimate_bp_per_contract(strategy_key, short_strike, long_strike, premium)
    n = _num(contracts)
    if per_contract is None or not n or n <= 0:
        return None
    return round(per_contract * n, 2)


def family_open_exposure(strategy_key: str) -> dict:
    """现有 open 同家族仓位 max loss 合计（state 真值，SPEC-129 语义）。"""
    from strategy.state import read_all_positions

    family = strategy_family(strategy_key)
    positions: list[dict] = []
    total = 0.0
    try:
        for p in ((read_all_positions() or {}).get("positions") or []):
            p_key = str(p.get("strategy_key") or "").strip().lower()
            if strategy_family(p_key) != family:
                continue
            ml = order_max_loss_usd(
                p_key, p.get("short_strike"), p.get("long_strike"),
                p.get("actual_premium") or p.get("model_premium"),
                p.get("contracts") or 1,
            )
            if ml is None:
                continue
            total += ml
            positions.append({
                "trade_id": p.get("trade_id"),
                "account": p.get("account"),
                "strategy_key": p_key,
                "max_loss_usd": ml,
            })
    except Exception as exc:
        log.warning("family exposure unavailable: %s", exc)
    return {"family": family, "family_open_max_loss_usd": round(total, 2),
            "family_open_positions": positions}


def liquid_cash() -> tuple[float | None, str]:
    """(usd | None, source)。不可用 → (None, 'unavailable')，永不 raise。"""
    try:
        from strategy.cash_budget_governance import get_current_liquid_cash
        cash = get_current_liquid_cash()
        source = str(cash.get("source") or "unavailable")
        if source != "unavailable":
            return round(float(cash.get("total") or 0.0), 2), source
        return None, source
    except Exception as exc:
        log.warning("liquid cash unavailable: %s", exc)
        return None, "unavailable"


def deployed_debit_capital() -> float:
    """SPEC-131 v2 — 全部已部署 debit 风险资本（所有 open debit 结构的
    |已付权利金|×100×n 合计）。debit 开仓时钱已离开现金池，必须补回分母；
    credit 结构 max loss 直接从现金扣、无预付，不进分母。"""
    from strategy.state import read_all_positions

    total = 0.0
    try:
        for p in ((read_all_positions() or {}).get("positions") or []):
            prem = _num(p.get("actual_premium") or p.get("model_premium"))
            n = _num(p.get("contracts")) or 1
            if prem is not None and prem < 0 and n > 0:
                total += abs(prem) * 100.0 * n
    except Exception as exc:
        log.warning("deployed debit capital unavailable: %s", exc)
    return round(total, 2)


def degrade_copy(family: str, family_usd: float, pct: float,
                 threshold_pct: float = EXPOSURE_DEGRADE_THRESHOLD_PCT) -> str:
    """降级文案单一来源——推荐卡与晨报必须逐字一致（AC）。分母定义（策略
    资金池）与阈值显式给出（今日尺度绝对值原则）；语义澄清：不禁止仅改语气
    （SPEC-131 v2 PM 要求入文案）。"""
    return (f"条件满足，敞口已满（{family} 家族并发 max loss "
            f"${family_usd:,.0f} = 占策略资金池 {pct:.1f}%（阈值 {threshold_pct:.0f}%））"
            "——非加仓号召。超阈值不禁止任何操作，仅改变推荐语气")


def evaluate_exposure_degrade(strategy_key: str, *,
                              threshold_pct: float = EXPOSURE_DEGRADE_THRESHOLD_PCT) -> dict:
    """SPEC-131 v2 主入口。显示/推送层专用——绝不改变 selector 输出。

    v2 口径修正（PM 抓出分母混池，2026-07-07 晚）：
      分母 = 策略资金池 = 流动现金 + 全部已部署 debit 风险资本
      （BCD 等 debit 的 $76,600 开仓时已离开现金池——v1 用纯流动现金做分母
      是分子分母不同池；credit max loss 无预付不进分母）
      今日正确值 = 76,600 / (152,346 + 76,600) = 33.5%；阈值重 ratify 30%。

    Returns:
      {degraded: bool, family, family_open_max_loss_usd,
       liquid_cash_usd|None, deployed_debit_usd, strategy_pool_usd|None,
       cash_source, pct_of_pool|None, threshold_pct, copy|None, note|None}
    fail-soft：现金分量不可用 → degraded=False + note 标注 n/a（照常推荐）。
    """
    fam = family_open_exposure(strategy_key)
    cash_usd, cash_source = liquid_cash()
    debit_usd = deployed_debit_capital()
    out = {
        "degraded": False,
        "family": fam["family"],
        "family_open_max_loss_usd": fam["family_open_max_loss_usd"],
        "family_open_positions": fam["family_open_positions"],
        "liquid_cash_usd": cash_usd,
        "deployed_debit_usd": debit_usd,
        "strategy_pool_usd": None,
        "cash_source": cash_source,
        # SPEC-138 F4: rail composition of the cash denominator. "partial" = a
        # broker rail dropped (E-Trade token expired); its shrunk pool inflates
        # pct_of_pool past the threshold purely from the missing rail (7/7:
        # 33.5%→42%). That is a data outage, not a real exposure event.
        "rail_complete": cash_source == "live",
        "pct_of_pool": None,
        "threshold_pct": float(threshold_pct),
        "copy": None,
        "note": None,
    }
    if cash_usd is None or cash_usd <= 0:
        out["note"] = "敞口检查: 流动现金 n/a — 降级检查跳过（fail-soft，照常推荐）"
        return out
    pool = cash_usd + debit_usd
    out["strategy_pool_usd"] = round(pool, 2)
    pct = fam["family_open_max_loss_usd"] / pool * 100.0
    out["pct_of_pool"] = round(pct, 2)
    if cash_source != "live":
        # 缺轨：同口径 pct 仅供参考，不因缺轨压低的分母翻"敞口已满"。degraded 保持
        # False（advisory/info），note 标 staleness——数据中断 ≠ 治理裁决。
        out["note"] = (
            f"敞口检查: 现金轨不齐（source={cash_source}），"
            f"同口径占比 {pct:.1f}% 仅供参考，缺轨压低分母不作降级判定")
        return out
    if pct >= threshold_pct:
        out["degraded"] = True
        out["copy"] = degrade_copy(fam["family"], fam["family_open_max_loss_usd"],
                                   pct, threshold_pct)
    return out
