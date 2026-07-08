"""SPEC-135.2 — 账户级 crash-day defined-risk 容量（Q091 定稿真值之家）.

与 SPEC-131 v2 策略资金池是两个正交的轴：
  资金池（exposure.py）    — 家族集中度（篮子）：某一策略家族占策略资金池比例
  容量（本模块）           — 全账户崩盘承载（天花板）：所有 defined-risk 结构
                             的 max loss 合计 vs crash-day 可部署容量

display-only：本模块只供显示（Lane A ④ 资金层 + SPEC-129 开仓表单风险区），
不做门。容量硬门是否设立 = SPEC-111 lane 未来治理决定。
"""
from __future__ import annotations

import logging

log = logging.getLogger("capacity")

# ── Q091 P0 RATIFIED 2026-07-07（PM："后续所有容量讨论以此为准"）────────────
# crash-day 可部署 defined-risk 容量
#   = crash-day excess liquidity $337,688 − 崩盘日安全垫 buffer $100,000
#   ≈ $238,000
# provenance: research/q091/q091_p0_memo.md（P0 合成栈重放 + PM ratify）
# 更新路径：SPEC-111 §4-B 重仿真（另一会话 lane）——改此值必须 PM ratify，
# 任何 dev/研究改动不得自行调整。
Q091_CRASH_EXCESS_USD = 337_688.0
CRASH_BUFFER_USD = 100_000.0
CRASH_DEPLOYABLE_DR_USD = 238_000.0


def used_defined_risk() -> dict:
    """全账户已用 defined-risk（所有 open positions 的 max loss 合计，跨家族）。

    复用 SPEC-129 exposure 真值函数逐仓计算（credit = (width−credit)×100×n /
    debit = |debit|×100×n）——禁旁路重推，公式单一来源在 strategy/exposure。

    Returns:
      {used_usd, capacity_usd, buffer_usd, pct, positions: [
        {trade_id, account, strategy_key, max_loss_usd}]}
    fail-soft：state 不可读 → used=0 + positions=[]（显示层自行标注）。
    """
    from strategy.exposure import order_max_loss_usd
    from strategy.state import read_all_positions

    positions: list[dict] = []
    used = 0.0
    try:
        for p in ((read_all_positions() or {}).get("positions") or []):
            p_key = str(p.get("strategy_key") or "").strip().lower()
            ml = order_max_loss_usd(
                p_key, p.get("short_strike"), p.get("long_strike"),
                p.get("actual_premium") or p.get("model_premium"),
                p.get("contracts") or 1,
            )
            if ml is None:
                continue
            used += ml
            positions.append({
                "trade_id": p.get("trade_id"),
                "account": p.get("account"),
                "strategy_key": p_key,
                "max_loss_usd": ml,
            })
    except Exception as exc:
        log.warning("used_defined_risk unavailable: %s", exc)
    pct = round(used / CRASH_DEPLOYABLE_DR_USD * 100.0, 1) if CRASH_DEPLOYABLE_DR_USD else None
    return {
        "used_usd": round(used, 2),
        "capacity_usd": CRASH_DEPLOYABLE_DR_USD,
        "buffer_usd": CRASH_BUFFER_USD,
        "pct": pct,
        "positions": positions,
    }


def capacity_copy(used_usd: float, pct: float) -> str:
    """容量行文案单一来源（Lane A 与开仓表单共用语义；今日尺度绝对值原则）。"""
    return (f"账户级 defined-risk：已用 ${used_usd:,.0f} / "
            f"可部署 ${CRASH_DEPLOYABLE_DR_USD:,.0f}（{pct:.0f}%）"
            f"——崩盘日安全垫 ${CRASH_BUFFER_USD:,.0f} 已预留")
