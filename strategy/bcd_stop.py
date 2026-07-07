"""BCD debit stop tightening (SPEC-080).

当 bcd_stop_tightening_mode == "active" 时，BCD debit stop loss 从 -0.50 收紧到 -0.35。
"""
from __future__ import annotations
import json
from pathlib import Path

BCD_STOP_DEFAULT  = -0.50   # legacy hardcoded value; non-BCD debit strategies
BCD_STOP_TIGHTER  = -0.35   # Q038 Phase 2C plateau; BCD when mode=active

_ENGINE_LOG = Path("data/bcd_stop_shadow_engine.jsonl")
_LIVE_LOG   = Path("data/bcd_stop_shadow_live.jsonl")


def bcd_debit_stop(mode: str) -> float:
    """Return the effective BCD debit stop ratio for the current mode."""
    if mode == "active":
        return BCD_STOP_TIGHTER
    return BCD_STOP_DEFAULT


def debit_stop_ratio(entry_value: float, current_val: float,
                     roll_income: float = 0.0) -> float:
    """SPEC-127 §4b — debit-structure stop ratio anchored on the campaign
    Adjusted Basis（PM ratify 2026-07-06）。

    adjusted_basis = |initial debit| − cumulative short-leg roll income
    stop line: 结构现值 ≤ 0.5 × adjusted_basis ⇔ ratio ≤ −0.50

    含义：campaign 层最大追加损失恒为“剩余真实敞口”的一半；已入袋的 roll
    收入不参与止损分母（银行里的钱不该被拿来垫亏损空间）。

    Units: all three args share the engine's per-share entry_value units.

    零 roll（roll_income == 0）时走与旧口径完全相同的表达式
    (current_val − entry_value) / |entry_value| —— bit-identical，回归零行为
    变更（有单测锁定）。basis 已被 roll 收入全额收回（≤ 0）时敞口为零，
    ratio 止损失效（返回 0.0，永不触发）。
    """
    if not roll_income:
        entry_abs = abs(entry_value)
        if entry_abs <= 0:
            return 0.0
        # EXACT legacy expression — do not refactor (bit-identity AC).
        pnl = current_val - entry_value
        return pnl / entry_abs
    basis = abs(entry_value) - roll_income
    if basis <= 0:
        return 0.0
    return (current_val - basis) / basis


def log_bcd_stop_event(
    date: str,
    pnl_ratio: float,
    mode: str,
    source: str = "engine",   # "engine" | "live"
) -> None:
    """Log a would-be BCD stop trigger event (shadow and active modes)."""
    path = _LIVE_LOG if source == "live" else _ENGINE_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "date": date, "pnl_ratio": round(pnl_ratio, 4),
            "mode": mode, "source": source,
            "stop_active": BCD_STOP_TIGHTER,
            "stop_legacy": BCD_STOP_DEFAULT,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass
