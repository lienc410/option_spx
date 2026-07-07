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

# PM ratify 2026-07-07 — 敞口降级阈值（家族并发 max loss / 流动现金）
EXPOSURE_DEGRADE_THRESHOLD_PCT = 40.0


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


def degrade_copy(family: str, family_usd: float, pct: float,
                 threshold_pct: float = EXPOSURE_DEGRADE_THRESHOLD_PCT) -> str:
    """降级文案单一来源——推荐卡与晨报必须逐字一致（AC）。阈值与分母定义
    显式给出（今日尺度绝对值原则）。"""
    return (f"条件满足，敞口已满（{family} 家族并发 max loss "
            f"${family_usd:,.0f} = {pct:.1f}% 流动现金 ≥ {threshold_pct:.0f}%）"
            "——非加仓号召")


def evaluate_exposure_degrade(strategy_key: str, *,
                              threshold_pct: float = EXPOSURE_DEGRADE_THRESHOLD_PCT) -> dict:
    """SPEC-131 主入口。显示/推送层专用——绝不改变 selector 输出。

    Returns:
      {degraded: bool, family, family_open_max_loss_usd,
       liquid_cash_usd|None, cash_source, pct_of_cash|None,
       threshold_pct, copy|None, note|None}
    fail-soft：分母不可用 → degraded=False + note 标注 n/a（照常推荐）。
    """
    fam = family_open_exposure(strategy_key)
    cash_usd, cash_source = liquid_cash()
    out = {
        "degraded": False,
        "family": fam["family"],
        "family_open_max_loss_usd": fam["family_open_max_loss_usd"],
        "family_open_positions": fam["family_open_positions"],
        "liquid_cash_usd": cash_usd,
        "cash_source": cash_source,
        "pct_of_cash": None,
        "threshold_pct": float(threshold_pct),
        "copy": None,
        "note": None,
    }
    if cash_usd is None or cash_usd <= 0:
        out["note"] = "敞口检查: 流动现金 n/a — 降级检查跳过（fail-soft，照常推荐）"
        return out
    pct = fam["family_open_max_loss_usd"] / cash_usd * 100.0
    out["pct_of_cash"] = round(pct, 2)
    if pct >= threshold_pct:
        out["degraded"] = True
        out["copy"] = degrade_copy(fam["family"], fam["family_open_max_loss_usd"],
                                   pct, threshold_pct)
    return out
