"""Q042 Position Sizing — SPX-only (F2)

Single entry point: compute_sizing().

Inputs:  NLV, current SPX close, current VIX, sleeve_id.
Outputs: (long_strike, short_strike, contracts, est_debit_per_contract)

Rules (from SPEC-094 F2, updated by SPEC-104 / SPEC-094.1 / SPEC-094.5):
  - NLV < $200k → skip (return 0 contracts)
  - Sleeve A staged target debit = NLV × 12.5%
  - Sleeve B remains unchanged at NLV × 10% and is not production-routed
  - Long K  = ATM rounded to nearest $5
  - Short K = ATM × 1.05 rounded to nearest $5 (Sleeve A: SPEC-094.5, DTE 30
    保持; Sleeve B: 原始不变, DTE 90)
  - Contracts = floor(target_debit / est_debit_per_contract)
  - Symbol fixed = SPX (no XSP branch in MVP)
"""

from __future__ import annotations

from typing import Optional, Tuple

from strategy.q042_config import (
    Q042_SLEEVE_A_PRODUCTION_CAP_PCT,
    Q042_SLEEVE_B_PAPER_SIZING_PCT,
)
from strategy.q042_pricing import estimate_debit

_NLV_MINIMUM    = 200_000.0   # activation threshold
_STRIKE_ROUND   = 5.0         # $5 increments
_OTM_PCT_A      = 0.05        # Sleeve A: ATM/+5% (SPEC-094.5; 094.1 的 2.5% 被 Q100 P1 推翻)
_OTM_PCT_B      = 0.05        # Sleeve B 浅档: ATM/+5%  (unchanged)
_DTE_A          = 30          # Sleeve A: 30 DTE   (SPEC-094.1)
_DTE_B          = 90          # Sleeve B 浅档: 90 DTE (unchanged)
_SPX_MULTIPLIER = 100         # SPX contract multiplier

# SPEC-094.7 — Sleeve B 深档结构（Q102 P2 门槛：spread 全宽度深档 FAIL，
# ITM85 LEAP 730d 两括号端 PASS）。paper-only；production cap 仍 0。
_B_DEEP_THRESHOLD = -0.25     # rung ≤ 此值 → LEAP 结构
_B_LEAP_K_RATIO   = 0.85      # ITM 股票替代惯例（≈0.8Δ），Q102 预注册值
_B_LEAP_DTE       = 730       # 365d 括号一端 FAIL，730d 两端 PASS（周期复原跑道）
_B_LEAP_VOL_MULT  = 0.875     # est 估价用括号 [0.75,1.0] 中点；真实 fill 走 pending-fill
_XSP_SCALE        = 10.0      # XSP = SPX/10（SPX LEAP 单张超预算 → XSP 落地）


def b_rung_structure(rung: float) -> dict:
    """Sleeve B 结构路由（单真值；trigger 走查 / executor / engine 共用）。"""
    if rung <= _B_DEEP_THRESHOLD:
        return {"instrument": "XSP_LEAP", "dte": _B_LEAP_DTE, "symbol": "XSP"}
    return {"instrument": "SPREAD", "dte": _DTE_B, "symbol": "SPX"}


def compute_leap_sizing(
    nlv: float,
    spx_close: float,
    vix: float,
) -> Tuple[Optional[float], None, int, Optional[float]]:
    """深档 XSP ITM LEAP sizing（SPEC-094.7 F2）。

    Returns (long_strike_xsp, None, contracts, est_debit_per_contract_usd)。
    K = round(S×0.85/10)（XSP $1 粒度）；est = BS(σ=VIX×0.875, q=1.6%,
    r=4.5%)/10 ×100（per-contract USD）。est 仅供告警/草稿；paper 实际
    fill 由 SPEC-094.3 pending-fill 流程记录。
    """
    if nlv < _NLV_MINIMUM:
        return None, None, 0, None
    from pricing import core as _core
    k_xsp = float(round(spx_close * _B_LEAP_K_RATIO / _XSP_SCALE))
    k_spx = k_xsp * _XSP_SCALE
    sigma = max(vix * _B_LEAP_VOL_MULT / 100.0, 0.01)
    px_spx = _core.call_price(spx_close, k_spx, _B_LEAP_DTE / 365.0, sigma,
                              0.045, q=0.016)
    debit_per_contract = px_spx / _XSP_SCALE * 100.0     # XSP per-contract USD
    if debit_per_contract <= 0:
        return k_xsp, None, 0, None
    target = nlv * (Q042_SLEEVE_B_PAPER_SIZING_PCT / 100.0)
    return k_xsp, None, int(target // debit_per_contract), round(debit_per_contract, 2)


def q042_sleeve_cap_pct(sleeve_id: str = "A") -> float:
    """Return the sizing cap used for draft entries.

    Sleeve B remains research-only, but the paper draft keeps its legacy 10%
    sizing so historical/paper records remain comparable.
    """
    return Q042_SLEEVE_A_PRODUCTION_CAP_PCT if str(sleeve_id).upper() == "A" else Q042_SLEEVE_B_PAPER_SIZING_PCT


def _round_strike(price: float, increment: float = _STRIKE_ROUND) -> int:
    return int(round(price / increment) * increment)


def compute_sizing(
    nlv: float,
    spx_close: float,
    vix: float,
    sleeve_id: str = "A",
) -> Tuple[Optional[int], Optional[int], int, Optional[float]]:
    """
    Compute Q042 spread sizing for one sleeve entry.

    Args:
        nlv:       Net liquidation value in USD.
        spx_close: Current SPX level (entry reference price for strikes).
        vix:       Current VIX level (used for BS pricing).
        sleeve_id: "A" or "B".

    Returns:
        (long_strike, short_strike, contracts, est_debit_per_contract)
        long_strike/short_strike are int (rounded to nearest $5).
        est_debit_per_contract is in USD (per-share debit × 100).
        Returns (None, None, 0, None) if NLV below activation threshold.

    AC6 example: NLV $500k, SPX 7400, VIX 25, sleeve_id="A"
        → (7400, 7770, n, ~est) [Sleeve A: ATM/+5%, DTE 30 — SPEC-094.5]
    AC7: NLV $150k → (None, None, 0, None)
    """
    if nlv < _NLV_MINIMUM:
        return None, None, 0, None

    oTM = _OTM_PCT_A if sleeve_id == "A" else _OTM_PCT_B
    dte = _DTE_A     if sleeve_id == "A" else _DTE_B

    long_k  = _round_strike(spx_close)
    short_k = _round_strike(spx_close * (1.0 + oTM))

    debit_per_share = estimate_debit(
        S=spx_close,
        K_long=float(long_k),
        K_short=float(short_k),
        dte=dte,
        vix=vix,
    )
    debit_per_contract = debit_per_share * _SPX_MULTIPLIER

    if debit_per_contract <= 0:
        return long_k, short_k, 0, None

    target = nlv * (q042_sleeve_cap_pct(sleeve_id) / 100.0)
    contracts = int(target // debit_per_contract)

    return long_k, short_k, contracts, round(debit_per_contract, 2)
