"""
Portfolio Shock-Risk Engine — SPEC-025

Reprices the current portfolio under 8 standard stress scenarios using
Black-Scholes to estimate potential P&L impact of market shocks.

Scenarios (S1–S8):
  Core (S1–S4) — used for budget control:
    S1: SPX -2%,  VIX +5pt   (mild selloff)
    S2: SPX -3%,  VIX +8pt   (moderate selloff)
    S3: SPX -5%,  VIX +15pt  (severe selloff)
    S4: SPX  0%,  VIX +10pt  (pure vol spike)

  Tail (S5–S7) — recorded only, NOT in budget control in v1:
    S5: SPX +2%,  VIX -3pt   (mild rally)
    S6: SPX +5%,  VIX -8pt   (strong rally + vol crush)
    S7: SPX +3%,  VIX -5pt   (rally + vol normalization)

  S8 (separate tracking):
    S8: SPX -2%,  VIX +5pt   (same values as S1, tracked independently for
                               term structure inversion analysis; parameters
                               may diverge in v2)

Key design decisions:
  - sigma = max(0.05, min(2.00, current_vix / 100))  ← NOT entry_sigma
    Rationale: shock repricing uses today's realized IV baseline
  - Core scenarios only (S1-S4) used for max_core_loss_pct budget
  - shadow mode: always approved=True, audit log only
  - active mode: blocks entry if budget breached

ShockReport structure:
  - pre_*:  existing book BEFORE candidate entry
  - post_*: book AFTER adding candidate entry (only when candidate provided)
  - budget fields stored directly for downstream analysis
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from backtest.pricer import put_price, call_price

if TYPE_CHECKING:
    from strategy.selector import StrategyParams


# ─── Scenario definitions ────────────────────────────────────────────────────

@dataclass(frozen=True)
class ShockScenario:
    name:       str
    spot_shock: float   # fractional SPX move (−0.05 = −5%)
    vix_shock:  float   # additive VIX points change (+8 = VIX rises by 8pt)
    is_core:    bool    # True → included in max_core_loss budget calculation


STANDARD_SCENARIOS: list[ShockScenario] = [
    # Core scenarios — down + vol (budget control)
    ShockScenario("S1_mild_down",     spot_shock=-0.02, vix_shock=+5.0,  is_core=True),
    ShockScenario("S2_mod_down",      spot_shock=-0.03, vix_shock=+8.0,  is_core=True),
    ShockScenario("S3_severe_down",   spot_shock=-0.05, vix_shock=+15.0, is_core=True),
    ShockScenario("S4_vol_spike",     spot_shock=+0.00, vix_shock=+10.0, is_core=True),
    # Tail scenarios — up (recorded only, not in budget v1)
    ShockScenario("S5_mild_up",       spot_shock=+0.02, vix_shock=-3.0,  is_core=False),
    ShockScenario("S6_rally",         spot_shock=+0.05, vix_shock=-8.0,  is_core=False),
    ShockScenario("S7_vol_normalize", spot_shock=+0.03, vix_shock=-5.0,  is_core=False),
    # S8: same spot/vol as S1 but tracked independently for term structure analysis
    ShockScenario("S8_term_inversion",spot_shock=-0.02, vix_shock=+5.0,  is_core=False),
]

CORE_SCENARIOS = [s for s in STANDARD_SCENARIOS if s.is_core]


# ─── Position snapshot for shock repricing ───────────────────────────────────

@dataclass
class LegSnapshot:
    """One option leg."""
    option_type:  str     # "put" or "call"
    strike:       float
    dte:          int     # days to expiry as of today
    contracts:    float   # number of contracts (negative = short)
    current_spx:  float   # today's SPX close (baseline for repricing)


@dataclass
class PositionSnapshot:
    """Minimal description of one open position for shock repricing."""
    strategy_key:   str
    is_short_gamma: bool
    legs:           list[LegSnapshot] = field(default_factory=list)


# ─── Shock report ────────────────────────────────────────────────────────────

@dataclass
class ShockReport:
    """
    Result of running all 8 scenarios on the current portfolio.

    pre_*  fields = existing book before candidate entry.
    post_* fields = book including candidate entry (only set when candidate provided).
    """
    date:                     str
    nav:                      float
    mode:                     str     # "shadow" | "active"

    # Existing book (pre-entry)
    pre_scenarios:            dict[str, float]   # scenario_name → P&L ($)
    pre_max_core_loss_pct:    float              # min(S1-S4 pnl) / nav  (≤ 0)

    # Post-entry (after adding candidate; 0.0 if no candidate)
    post_scenarios:           dict[str, float]
    post_max_core_loss_pct:   float

    # Incremental = post - pre
    incremental_shock_pct:    float

    # Budget thresholds stored for downstream analysis
    budget_core:              float
    budget_incremental:       float

    # Decision
    approved:                 bool
    reject_reason:            Optional[str]

    # Convenience fields (derived)
    sigma_used:               float = 0.0


def _reprice_leg(
    leg: LegSnapshot,
    shocked_spx: float,
    shocked_sigma: float,
    current_sigma: float,
    risk_free: float = 0.02,
) -> float:
    """
    P&L (in USD, ×100 multiplier) for one leg under shocked conditions.

    Uses current_sigma for baseline price and shocked_sigma for stressed price.
    contracts < 0 → short position → profit when option value falls.
    """
    T = max(leg.dte, 1) / 365.0
    if leg.option_type == "put":
        baseline_price = put_price(leg.current_spx, leg.strike, T, risk_free, current_sigma)
        shocked_price  = put_price(shocked_spx,      leg.strike, T, risk_free, shocked_sigma)
    elif leg.option_type == "call":
        baseline_price = call_price(leg.current_spx, leg.strike, T, risk_free, current_sigma)
        shocked_price  = call_price(shocked_spx,      leg.strike, T, risk_free, shocked_sigma)
    else:
        raise ValueError(f"Unknown option_type: {leg.option_type!r}")

    price_change = shocked_price - baseline_price
    # Short position (contracts < 0): P&L = -(contracts) * change * 100
    return -leg.contracts * price_change * 100


def _run_scenarios(
    positions: list[PositionSnapshot],
    current_spx: float,
    sigma: float,
) -> dict[str, float]:
    """Run all 8 scenarios and return scenario_name → total portfolio P&L."""
    results: dict[str, float] = {}
    for sc in STANDARD_SCENARIOS:
        shocked_spx = current_spx * (1.0 + sc.spot_shock)
        shocked_vix = sigma * 100 + sc.vix_shock
        shocked_sigma = max(0.05, min(2.00, shocked_vix / 100))
        pnl = sum(
            _reprice_leg(leg, shocked_spx, shocked_sigma, sigma)
            for pos in positions
            for leg in pos.legs
        )
        results[sc.name] = pnl
    return results


def _max_core_loss_pct(scenario_pnl: dict[str, float], nav: float) -> float:
    """Worst P&L across Core scenarios (S1-S4) as fraction of NAV. ≤ 0."""
    core_pnl = [scenario_pnl[s.name] for s in CORE_SCENARIOS if s.name in scenario_pnl]
    if not core_pnl or nav <= 0:
        return 0.0
    return min(core_pnl) / nav


def run_shock_check(
    *,
    positions: list[PositionSnapshot],
    current_spx: float,
    current_vix: float,
    date: str,
    params: "StrategyParams",
    candidate_position: Optional[PositionSnapshot] = None,
    account_size: float = 100_000,
    is_high_vol: bool = False,
) -> ShockReport:
    """
    Run all 8 shock scenarios on the current portfolio.

    Args:
        positions:           Currently open positions (pre-entry book).
        current_spx:         Today's SPX close.
        current_vix:         Today's VIX close.
        date:                Today's date string (YYYY-MM-DD).
        params:              StrategyParams (budget thresholds and shock_mode).
        candidate_position:  Proposed new position (incremental analysis; None = book-only).
        account_size:        Account NAV in USD.
        is_high_vol:         True when regime is HIGH_VOL (tighter budgets).

    Returns:
        ShockReport with pre/post scenario results, breach flags, and approval decision.
    """
    nav = account_size
    # sigma = today's VIX / 100, clamped for BS stability
    sigma = max(0.05, min(2.00, current_vix / 100))

    mode = getattr(params, "shock_mode", "shadow")

    # ── Pre-entry: existing book ───────────────────────────────────────────────
    pre_scenarios = _run_scenarios(positions, current_spx, sigma)
    pre_max_core = _max_core_loss_pct(pre_scenarios, nav)

    # ── Post-entry: book + candidate ──────────────────────────────────────────
    if candidate_position is not None:
        post_positions = positions + [candidate_position]
        post_scenarios = _run_scenarios(post_positions, current_spx, sigma)
        post_max_core = _max_core_loss_pct(post_scenarios, nav)
    else:
        post_scenarios = dict(pre_scenarios)
        post_max_core = pre_max_core

    incremental_shock_pct = post_max_core - pre_max_core  # ≤ 0 if candidate adds risk

    # ── Budget thresholds ─────────────────────────────────────────────────────
    budget_core = (
        params.shock_budget_core_hv if is_high_vol else params.shock_budget_core_normal
    )
    budget_incremental = (
        params.shock_budget_incremental_hv if is_high_vol else params.shock_budget_incremental
    )

    # Breaches (compare absolute loss against budget)
    core_breach        = abs(post_max_core) > budget_core
    incremental_breach = abs(incremental_shock_pct) > budget_incremental

    # ── Decision ──────────────────────────────────────────────────────────────
    reject_reason: Optional[str] = None
    if mode == "active" and (core_breach or incremental_breach):
        approved = False
        reasons = []
        if core_breach:
            reasons.append(
                f"core_loss {abs(post_max_core)*100:.2f}% > budget {budget_core*100:.2f}%"
            )
        if incremental_breach:
            reasons.append(
                f"incremental {abs(incremental_shock_pct)*100:.2f}% > budget {budget_incremental*100:.2f}%"
            )
        reject_reason = "; ".join(reasons)
    else:
        approved = True

    return ShockReport(
        date=date,
        nav=nav,
        mode=mode,
        pre_scenarios=pre_scenarios,
        pre_max_core_loss_pct=pre_max_core,
        post_scenarios=post_scenarios,
        post_max_core_loss_pct=post_max_core,
        incremental_shock_pct=incremental_shock_pct,
        budget_core=budget_core,
        budget_incremental=budget_incremental,
        approved=approved,
        reject_reason=reject_reason,
        sigma_used=sigma,
    )


if __name__ == "__main__":
    from strategy.selector import StrategyParams
    params = StrategyParams()

    # Empty book → zero shock
    report = run_shock_check(
        positions=[],
        current_spx=5000.0,
        current_vix=20.0,
        date="2026-01-01",
        params=params,
        account_size=100_000,
    )
    assert report.pre_max_core_loss_pct == 0.0, f"Expected 0, got {report.pre_max_core_loss_pct}"
    assert report.approved is True
    assert abs(report.sigma_used - 0.20) < 1e-6
    assert len(report.pre_scenarios) == 8
    print(f"Empty book sigma={report.sigma_used:.2f}  pre_core={report.pre_max_core_loss_pct:.4f}")

    # Single short put → should show negative P&L under down scenarios
    leg = LegSnapshot(
        option_type="put", strike=4800.0, dte=30,
        contracts=-1.0,  # short 1 put
        current_spx=5000.0,
    )
    pos = PositionSnapshot(strategy_key="bull_put_spread", is_short_gamma=True, legs=[leg])
    report2 = run_shock_check(
        positions=[pos],
        current_spx=5000.0,
        current_vix=20.0,
        date="2026-01-01",
        params=params,
        account_size=100_000,
    )
    assert report2.pre_max_core_loss_pct <= 0, "Short put should show loss in down scenarios"
    print(f"Short put  sigma={report2.sigma_used:.2f}  pre_core={report2.pre_max_core_loss_pct*100:.3f}% NAV")
    print("shock_engine.py OK")
