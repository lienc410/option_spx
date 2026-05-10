"""
research/tools/iv_expansion_stress_test.py — generalised IV/VIX shock stress test
=================================================================================

Source: Q012/Q051/Q052 closure (R-20260509-02 Action A1).

v0.1 supports three short-premium structures used in main strategy + Q041:

  - naked_put / CSP    (e.g. /ES short put, SPX CSP, GOOGL CSP)
  - bull_put_spread    (BPS — main strategy bread-and-butter)
  - iron_condor        (BPS + BCS combined)

Output per VIX shock (default +10 / +20 / +40), four metrics:

  1. mark_loss_dollars   — change in MTM value under stress (positive when losing)
  2. stress_bp_dollars   — BP/margin under stress (expanded vs entry)
  3. pnl_ratio           — current loss as fraction of stop reference
                            (max_loss for spreads; entry_credit for naked puts)
  4. survival            — pass / warn / fail per simple thresholds

Stress shock model:

  - VIX shock: linear add (e.g. current 19 + shock 20 → new VIX 39)
  - Correlated underlying drop: -1% per +3 VIX shock points
    (calibrated from /ES Phase A; consistent for v0.1 across all underlyings)
  - IV under stress: entry_iv × (new_vix / current_vix); for indices where
    VIX ≈ option IV this collapses to new_vix/100. For single names, use
    `iv_proxy_factor` to express entry_iv / current_vix (e.g. 1.5 if
    GOOGL IV = 30% when VIX = 20)

Out of scope (v0.2+): BCD diagonal, calendar spreads, ratio spreads.

Reference for principles enforced by this tool:
  QUANT_RESEARCHER.md → "Short-Premium Risk Management Principles"
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest.pricer import call_price, find_strike_for_delta, put_price


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_SHOCKS = [10, 20, 40]

# Correlation: -1% underlying per +3 VIX points of shock (Phase A calibration)
SPX_DROP_PER_VIX = 1.0 / 3.0 / 100.0

# /ES SPAN model (Phase A calibration constants)
ES_SPAN_CALIB = 20_529.0
ES_CALIB_VIX  = 19.0
ES_CALIB_SPOT = 5400.0
ES_MULT       = 50.0
ES_VOL_SHOCK  = 0.50
ES_SCAN_EXP   = 1.10

# Survival thresholds (loose; spec-review can override per-spec)
WARN_BP_PCT_NLV = 0.25
FAIL_BP_PCT_NLV = 0.35
WARN_PNL_FACTOR = 0.6   # warn at 60% of stop


# ── /ES SPAN model (Phase A inline) ───────────────────────────────────────────

def _es_base_scan_pct() -> float:
    sigma0 = ES_CALIB_VIX / 100
    k0     = find_strike_for_delta(ES_CALIB_SPOT, 45, sigma0, 0.20, is_call=False)
    p0     = put_price(ES_CALIB_SPOT, k0, 45, sigma0)
    target = ES_SPAN_CALIB / ES_MULT
    lo, hi = 0.01, 0.35
    for _ in range(80):
        mid = (lo + hi) / 2
        ed  = ES_CALIB_SPOT * (1 - mid)
        pdn = put_price(ed, k0, 45, sigma0 * (1 + ES_VOL_SHOCK))
        val = max(pdn - p0, 0) + p0
        if val < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


_ES_BASE_SCAN = _es_base_scan_pct()


def es_span_per_contract(spot: float, vix: float, strike: float, dte: int) -> float:
    """Per-contract /ES SPAN using Phase A model."""
    sigma    = max(vix / 100, 0.01)
    rem_dte  = max(dte, 1)
    cur_prem = put_price(spot, strike, rem_dte, sigma)
    scan_pct = _ES_BASE_SCAN * (vix / ES_CALIB_VIX) ** ES_SCAN_EXP
    sigma_u  = sigma * (1 + ES_VOL_SHOCK)
    spot_dn  = spot * (1 - scan_pct)
    prem_dn  = put_price(spot_dn, strike, rem_dte, sigma_u)
    return max(prem_dn - cur_prem, 0) * ES_MULT + cur_prem * ES_MULT


# ── OCC PM model (SPX naked put, single names) ────────────────────────────────

def occ_pm_naked_put(
    spot: float, strike: float, premium: float, multiplier: float = 100.0
) -> float:
    """OCC Portfolio Margin for a single naked short put.
    Method A: 15% × notional - OTM amount + premium
    Method B: 10% × strike × multiplier + premium
    BP = max(A, B)
    """
    method_a = (0.15 * spot * multiplier
                - max(spot - strike, 0) * multiplier
                + premium * multiplier)
    method_b = 0.10 * strike * multiplier + premium * multiplier
    return max(method_a, method_b)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class StressPoint:
    vix_shock: int
    new_vix: float
    new_spot: float

    entry_value_dollars:  float    # entry credit (spreads) or premium-value (naked)
    stress_value_dollars: float
    mark_loss_dollars:    float    # positive when losing

    entry_bp_dollars:  float
    stress_bp_dollars: float
    bp_expansion_pct:  float

    pnl_ratio:      float          # negative when losing
    stop_proximity: float          # pnl_ratio - stop_pnl_ratio (negative = past stop)
    survival:       str            # pass / warn / fail


@dataclass
class StressReport:
    label:          str
    structure:      str
    spot:           float
    vix:            float
    contracts:      int
    nlv:            float
    stop_pnl_ratio: float

    entry_state:   dict
    stress_points: list[StressPoint] = field(default_factory=list)

    def worst_point(self) -> StressPoint:
        return max(self.stress_points, key=lambda s: -s.pnl_ratio)

    def print_table(self) -> None:
        print(f"\n{'━'*82}")
        print(f"  {self.label}")
        print(f"{'━'*82}")
        es_str = "  ".join(f"{k}={v}" for k, v in self.entry_state.items())
        print(f"  Structure: {self.structure}   Spot: {self.spot:.0f}  "
              f"VIX: {self.vix:.1f}  Contracts: {self.contracts}  NLV: ${self.nlv:,.0f}")
        print(f"  Entry state: {es_str}")
        print(f"  Stop rule: pnl_ratio ≤ {self.stop_pnl_ratio}")
        print()
        print(f"    {'VIX_shk':>7}  {'NewVIX':>6}  {'NewSpot':>8}  "
              f"{'MarkLoss$':>11}  {'StressBP$':>11}  {'BPexp%':>7}  "
              f"{'pnlRat':>7}  {'Surv':>5}")
        print(f"    {'─'*72}")
        for p in self.stress_points:
            shk = f"+{p.vix_shock}" if p.vix_shock else "0"
            print(f"    {shk:>7}  {p.new_vix:>6.1f}  {p.new_spot:>8.1f}  "
                  f"${p.mark_loss_dollars:>10,.0f}  ${p.stress_bp_dollars:>10,.0f}  "
                  f"{p.bp_expansion_pct:>+6.1f}%  {p.pnl_ratio:>+7.2f}  "
                  f"{p.survival:>5}")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _shock_market(spot: float, vix: float, shock: int,
                  iv_proxy_factor: float = 1.0) -> tuple[float, float, float]:
    new_vix   = vix + shock
    new_sigma = max(new_vix / 100 * iv_proxy_factor, 0.01)
    new_spot  = spot * (1 - SPX_DROP_PER_VIX * shock) if shock > 0 else spot
    return new_vix, new_sigma, new_spot


def _classify_survival(pnl_ratio: float, stress_bp: float, nlv: float,
                       stop_pnl_ratio: float) -> str:
    if pnl_ratio <= stop_pnl_ratio or stress_bp > nlv * FAIL_BP_PCT_NLV:
        return "fail"
    if (pnl_ratio <= stop_pnl_ratio * WARN_PNL_FACTOR
            or stress_bp > nlv * WARN_BP_PCT_NLV):
        return "warn"
    return "pass"


# ── Stress test functions ─────────────────────────────────────────────────────

def stress_naked_put(
    label:            str,
    spot:             float,
    vix:              float,
    target_delta:     float,
    dte:              int,
    contracts:        int   = 1,
    nlv:              float = 500_000.0,
    multiplier:       float = 100.0,
    iv_proxy_factor:  float = 1.0,
    stop_pnl_ratio:   float = -2.0,           # /ES style: -200% credit
    use_es_span_model: bool  = False,
    shocks:           list[int] | None = None,
) -> StressReport:
    """Stress test a single naked short put.

    `pnl_ratio` here is in CREDIT-MULTIPLES:
      -1.0 = loss equals 1× credit received
      -2.0 = loss equals 2× credit (stop fires when mark = 3× entry premium)
    """
    shocks = shocks or DEFAULT_SHOCKS
    sigma  = vix / 100 * iv_proxy_factor

    strike      = find_strike_for_delta(spot, dte, sigma, target_delta, is_call=False)
    entry_prem  = put_price(spot, strike, dte, sigma)
    entry_value = entry_prem * multiplier * contracts

    if use_es_span_model:
        entry_bp = es_span_per_contract(spot, vix, strike, dte) * contracts
    else:
        entry_bp = occ_pm_naked_put(spot, strike, entry_prem, multiplier) * contracts

    points: list[StressPoint] = []
    for shock in [0] + list(shocks):
        new_vix, new_sigma, new_spot = _shock_market(spot, vix, shock, iv_proxy_factor)
        stress_prem  = put_price(new_spot, strike, dte, new_sigma)
        stress_value = stress_prem * multiplier * contracts
        mark_loss    = stress_value - entry_value

        if use_es_span_model:
            stress_bp = es_span_per_contract(new_spot, new_vix, strike, dte) * contracts
        else:
            stress_bp = occ_pm_naked_put(new_spot, strike, stress_prem, multiplier) * contracts

        bp_exp = (stress_bp / entry_bp - 1) * 100 if entry_bp > 0 else 0.0

        # Naked-put pnl_ratio: loss / entry credit (negative when losing)
        pnl_ratio = -mark_loss / entry_value if entry_value > 0 else 0.0

        stop_prox = pnl_ratio - stop_pnl_ratio
        surv      = _classify_survival(pnl_ratio, stress_bp, nlv, stop_pnl_ratio)

        points.append(StressPoint(
            vix_shock=shock, new_vix=new_vix, new_spot=new_spot,
            entry_value_dollars=entry_value,
            stress_value_dollars=stress_value,
            mark_loss_dollars=mark_loss,
            entry_bp_dollars=entry_bp, stress_bp_dollars=stress_bp,
            bp_expansion_pct=bp_exp,
            pnl_ratio=pnl_ratio, stop_proximity=stop_prox, survival=surv,
        ))

    return StressReport(
        label=label, structure="naked_put",
        spot=spot, vix=vix, contracts=contracts, nlv=nlv,
        stop_pnl_ratio=stop_pnl_ratio,
        entry_state={
            "strike":            round(strike, 1),
            "premium_per_share": round(entry_prem, 2),
            "credit_dollars":    round(entry_value, 0),
            "bp_dollars":        round(entry_bp, 0),
        },
        stress_points=points,
    )


def stress_bps(
    label:           str,
    spot:            float,
    vix:             float,
    short_delta:     float,
    long_delta:      float,
    dte:             int,
    contracts:       int   = 1,
    nlv:             float = 500_000.0,
    multiplier:      float = 100.0,
    iv_proxy_factor: float = 1.0,
    stop_pnl_ratio:  float = -0.50,    # main strategy convention
    shocks:          list[int] | None = None,
) -> StressReport:
    """Stress test a Bull Put Spread (short higher-strike + long lower-strike put).

    `pnl_ratio` is in MAX-LOSS fraction:
      -0.5 = lost 50% of max loss
      -1.0 = lost full max loss (capped)
    """
    shocks = shocks or DEFAULT_SHOCKS
    sigma  = vix / 100 * iv_proxy_factor

    short_k = find_strike_for_delta(spot, dte, sigma, short_delta, is_call=False)
    long_k  = find_strike_for_delta(spot, dte, sigma, long_delta,  is_call=False)
    short_p = put_price(spot, short_k, dte, sigma)
    long_p  = put_price(spot, long_k,  dte, sigma)

    entry_credit_per_share = short_p - long_p
    width                  = short_k - long_k
    entry_value            = entry_credit_per_share * multiplier * contracts
    max_loss               = (width - entry_credit_per_share) * multiplier * contracts
    entry_bp               = max_loss   # capped exposure

    points: list[StressPoint] = []
    for shock in [0] + list(shocks):
        new_vix, new_sigma, new_spot = _shock_market(spot, vix, shock, iv_proxy_factor)
        new_short    = put_price(new_spot, short_k, dte, new_sigma)
        new_long     = put_price(new_spot, long_k,  dte, new_sigma)
        new_net      = new_short - new_long
        stress_value = new_net * multiplier * contracts
        mark_loss    = min(stress_value - entry_value, max_loss)

        # BP for credit spread is fixed (max-loss-capped)
        stress_bp = entry_bp
        bp_exp    = 0.0

        pnl_ratio = -mark_loss / max_loss if max_loss > 0 else 0.0
        pnl_ratio = max(pnl_ratio, -1.0)

        stop_prox = pnl_ratio - stop_pnl_ratio
        surv      = _classify_survival(pnl_ratio, stress_bp, nlv, stop_pnl_ratio)

        points.append(StressPoint(
            vix_shock=shock, new_vix=new_vix, new_spot=new_spot,
            entry_value_dollars=entry_value,
            stress_value_dollars=stress_value,
            mark_loss_dollars=mark_loss,
            entry_bp_dollars=entry_bp, stress_bp_dollars=stress_bp,
            bp_expansion_pct=bp_exp,
            pnl_ratio=pnl_ratio, stop_proximity=stop_prox, survival=surv,
        ))

    return StressReport(
        label=label, structure="bull_put_spread",
        spot=spot, vix=vix, contracts=contracts, nlv=nlv,
        stop_pnl_ratio=stop_pnl_ratio,
        entry_state={
            "short_strike":     round(short_k, 1),
            "long_strike":      round(long_k, 1),
            "width":            round(width, 1),
            "credit_per_share": round(entry_credit_per_share, 2),
            "credit_dollars":   round(entry_value, 0),
            "max_loss_dollars": round(max_loss, 0),
            "bp_dollars":       round(entry_bp, 0),
        },
        stress_points=points,
    )


def stress_iron_condor(
    label:             str,
    spot:              float,
    vix:               float,
    put_short_delta:   float,
    put_long_delta:    float,
    call_short_delta:  float,
    call_long_delta:   float,
    dte:               int,
    contracts:         int   = 1,
    nlv:               float = 500_000.0,
    multiplier:        float = 100.0,
    iv_proxy_factor:   float = 1.0,
    stop_pnl_ratio:    float = -0.50,
    shocks:            list[int] | None = None,
) -> StressReport:
    """Stress test an Iron Condor (BPS + BCS).

    Max loss = max(put_width, call_width) - total_credit (only one side fires).
    """
    shocks = shocks or DEFAULT_SHOCKS
    sigma  = vix / 100 * iv_proxy_factor

    # Put side
    p_short_k = find_strike_for_delta(spot, dte, sigma, put_short_delta, is_call=False)
    p_long_k  = find_strike_for_delta(spot, dte, sigma, put_long_delta,  is_call=False)
    p_short_p = put_price(spot, p_short_k, dte, sigma)
    p_long_p  = put_price(spot, p_long_k,  dte, sigma)
    p_credit  = p_short_p - p_long_p
    p_width   = p_short_k - p_long_k

    # Call side
    c_short_k = find_strike_for_delta(spot, dte, sigma, call_short_delta, is_call=True)
    c_long_k  = find_strike_for_delta(spot, dte, sigma, call_long_delta,  is_call=True)
    c_short_p = call_price(spot, c_short_k, dte, sigma)
    c_long_p  = call_price(spot, c_long_k,  dte, sigma)
    c_credit  = c_short_p - c_long_p
    c_width   = c_long_k - c_short_k

    total_credit_per_share = p_credit + c_credit
    max_loss_per_share     = max(p_width, c_width) - total_credit_per_share
    entry_value            = total_credit_per_share * multiplier * contracts
    max_loss               = max_loss_per_share * multiplier * contracts
    entry_bp               = max_loss

    points: list[StressPoint] = []
    for shock in [0] + list(shocks):
        new_vix, new_sigma, new_spot = _shock_market(spot, vix, shock, iv_proxy_factor)

        new_p_short = put_price(new_spot, p_short_k, dte, new_sigma)
        new_p_long  = put_price(new_spot, p_long_k,  dte, new_sigma)
        new_p_net   = new_p_short - new_p_long

        new_c_short = call_price(new_spot, c_short_k, dte, new_sigma)
        new_c_long  = call_price(new_spot, c_long_k,  dte, new_sigma)
        new_c_net   = new_c_short - new_c_long

        new_total_net = new_p_net + new_c_net
        stress_value  = new_total_net * multiplier * contracts
        mark_loss     = min(stress_value - entry_value, max_loss)

        stress_bp = entry_bp
        bp_exp    = 0.0

        pnl_ratio = -mark_loss / max_loss if max_loss > 0 else 0.0
        pnl_ratio = max(pnl_ratio, -1.0)

        stop_prox = pnl_ratio - stop_pnl_ratio
        surv      = _classify_survival(pnl_ratio, stress_bp, nlv, stop_pnl_ratio)

        points.append(StressPoint(
            vix_shock=shock, new_vix=new_vix, new_spot=new_spot,
            entry_value_dollars=entry_value,
            stress_value_dollars=stress_value,
            mark_loss_dollars=mark_loss,
            entry_bp_dollars=entry_bp, stress_bp_dollars=stress_bp,
            bp_expansion_pct=bp_exp,
            pnl_ratio=pnl_ratio, stop_proximity=stop_prox, survival=surv,
        ))

    return StressReport(
        label=label, structure="iron_condor",
        spot=spot, vix=vix, contracts=contracts, nlv=nlv,
        stop_pnl_ratio=stop_pnl_ratio,
        entry_state={
            "p_short_strike":         round(p_short_k, 1),
            "p_long_strike":          round(p_long_k, 1),
            "c_short_strike":         round(c_short_k, 1),
            "c_long_strike":          round(c_long_k, 1),
            "total_credit_per_share": round(total_credit_per_share, 2),
            "credit_dollars":         round(entry_value, 0),
            "max_loss_dollars":       round(max_loss, 0),
        },
        stress_points=points,
    )


# ── Self-validation: reproduce Phase A /ES result ─────────────────────────────

def _validate_against_phase_a() -> bool:
    """Reproduce Phase A /ES Δ0.20 DTE45 SPAN expansion as sanity check.
    Phase A reported (R-20260508-12 reference numbers):
        VIX 19, calibrated SPAN ≈ $20,529
        VIX 30 (post-entry): SPAN multiplier ~2.25x
        VIX 60: SPAN multiplier ~5.72x
    """
    print("Self-validation: /ES Δ0.20 DTE45 SPAN expansion vs Phase A")
    r = stress_naked_put(
        label="VALIDATION /ES Δ0.20 DTE45",
        spot=ES_CALIB_SPOT, vix=ES_CALIB_VIX, target_delta=0.20, dte=45,
        contracts=1, multiplier=ES_MULT, use_es_span_model=True,
        stop_pnl_ratio=-2.0,
    )
    base   = next(p for p in r.stress_points if p.vix_shock == 0)
    shock20 = next(p for p in r.stress_points if p.vix_shock == 20)
    shock40 = next(p for p in r.stress_points if p.vix_shock == 40)

    base_span    = base.entry_bp_dollars
    mult_at_30   = shock20.stress_bp_dollars / base_span    # VIX 19+20 = 39
    mult_at_60   = shock40.stress_bp_dollars / base_span    # VIX 19+40 = 59

    print(f"  Entry SPAN @ VIX 19: ${base_span:,.0f}  (Phase A target ~$20,529)")
    print(f"  Stress SPAN @ VIX 39: ${shock20.stress_bp_dollars:,.0f}  "
          f"(mult {mult_at_30:.2f}×)")
    print(f"  Stress SPAN @ VIX 59: ${shock40.stress_bp_dollars:,.0f}  "
          f"(mult {mult_at_60:.2f}×)")
    print(f"  Entry premium per share: ${r.entry_state['premium_per_share']}")
    print(f"  Stress premium @ +40 shock: ${shock40.stress_value_dollars/ES_MULT/r.contracts:.2f}/sh")

    # Sanity tolerances aligned to Phase A A2 (existing-position re-mark) model:
    # at VIX 39 we expect ~3.0-4.0× (between Phase A A2's 35:2.84 and 40:3.44)
    # at VIX 59 we expect ~4.5-6.5× (Phase A A2 trajectory)
    ok_calib = abs(base_span - ES_SPAN_CALIB) < 100
    ok_30    = 3.0 < mult_at_30 < 4.0
    ok_60    = 4.5 < mult_at_60 < 6.5
    overall  = ok_calib and ok_30 and ok_60
    print(f"  Validation: calib={'✓' if ok_calib else '✗'}  "
          f"VIX 39 mult={'✓' if ok_30 else '✗'}  "
          f"VIX 59 mult={'✓' if ok_60 else '✗'}")
    return overall


if __name__ == "__main__":
    print("=" * 82)
    print("iv_expansion_stress_test.py — v0.1 self-test")
    print("=" * 82)

    ok = _validate_against_phase_a()
    print(f"\n  Self-validation: {'PASS' if ok else 'FAIL'}")

    # Demo: SPX BPS at current market levels
    print("\n\nDemo 1 — SPX BPS Δ0.30/Δ0.15 width≈variable")
    r = stress_bps(
        label="DEMO SPX BPS Δ0.30/0.15 DTE45",
        spot=5400, vix=19, short_delta=0.30, long_delta=0.15, dte=45,
        contracts=1, stop_pnl_ratio=-0.50,
    )
    r.print_table()

    # Demo: SPX IC standard
    print("\n\nDemo 2 — SPX IC Δ0.20 puts / Δ0.15 calls")
    r = stress_iron_condor(
        label="DEMO SPX IC Δ0.20p/Δ0.15c DTE45",
        spot=5400, vix=19,
        put_short_delta=0.20, put_long_delta=0.10,
        call_short_delta=0.15, call_long_delta=0.05,
        dte=45, contracts=1, stop_pnl_ratio=-0.50,
    )
    r.print_table()
