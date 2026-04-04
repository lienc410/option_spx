"""
Portfolio shock engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from backtest.pricer import call_price, put_price


@dataclass(frozen=True)
class ShockScenario:
    name: str
    spot_shock: float
    vix_shock: float
    is_core: bool


STANDARD_SCENARIOS: list[ShockScenario] = [
    ShockScenario("S1_mild_down", -0.02, 5.0, True),
    ShockScenario("S2_mod_down", -0.03, 8.0, True),
    ShockScenario("S3_severe_down", -0.05, 15.0, True),
    ShockScenario("S4_vol_spike", 0.00, 10.0, True),
    ShockScenario("S5_mild_up", 0.02, -3.0, False),
    ShockScenario("S6_rally", 0.05, -8.0, False),
    ShockScenario("S7_vol_normalize", 0.03, -5.0, False),
    ShockScenario("S8_term_inversion", -0.02, 5.0, False),
]


@dataclass
class LegSnapshot:
    option_type: str
    strike: float
    dte: int
    contracts: float
    current_spx: float


@dataclass
class PositionSnapshot:
    strategy_key: str
    is_short_gamma: bool
    legs: list[LegSnapshot] = field(default_factory=list)


@dataclass
class ShockReport:
    date: str
    nav: float
    mode: str
    pre_scenarios: dict[str, float]
    pre_max_core_loss_pct: float
    post_scenarios: dict[str, float]
    post_max_core_loss_pct: float
    incremental_shock_pct: float
    budget_core: float
    budget_incremental: float
    approved: bool
    reject_reason: Optional[str]
    sigma_used: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _reprice_leg(leg: LegSnapshot, shocked_spx: float, shocked_sigma: float, current_sigma: float) -> float:
    t_years = max(leg.dte, 1) / 365.0
    if leg.option_type == "put":
        base = put_price(leg.current_spx, leg.strike, t_years, 0.02, current_sigma)
        shocked = put_price(shocked_spx, leg.strike, t_years, 0.02, shocked_sigma)
    else:
        base = call_price(leg.current_spx, leg.strike, t_years, 0.02, current_sigma)
        shocked = call_price(shocked_spx, leg.strike, t_years, 0.02, shocked_sigma)
    return -leg.contracts * (shocked - base) * 100


def _run_scenarios(positions: list[PositionSnapshot], current_spx: float, sigma: float) -> dict[str, float]:
    scenario_pnl: dict[str, float] = {}
    for scenario in STANDARD_SCENARIOS:
        shocked_spx = current_spx * (1.0 + scenario.spot_shock)
        shocked_sigma = max(0.05, min(2.0, (sigma * 100.0 + scenario.vix_shock) / 100.0))
        pnl = 0.0
        for position in positions:
            for leg in position.legs:
                pnl += _reprice_leg(leg, shocked_spx, shocked_sigma, sigma)
        scenario_pnl[scenario.name] = pnl
    return scenario_pnl


def _max_core_loss_pct(scenarios: dict[str, float], nav: float) -> float:
    core_names = {scenario.name for scenario in STANDARD_SCENARIOS if scenario.is_core}
    core_pnls = [value for name, value in scenarios.items() if name in core_names]
    if not core_pnls or nav <= 0:
        return 0.0
    return min(core_pnls) / nav


def run_shock_check(
    *,
    positions: list[PositionSnapshot],
    current_spx: float,
    current_vix: float,
    date: str,
    params,
    candidate_position: Optional[PositionSnapshot] = None,
    account_size: float = 100_000.0,
    is_high_vol: bool = False,
) -> ShockReport:
    sigma = max(0.05, min(2.0, current_vix / 100.0))
    mode = getattr(params, "shock_mode", "shadow")

    pre_scenarios = _run_scenarios(positions, current_spx, sigma)
    pre_max_core = _max_core_loss_pct(pre_scenarios, account_size)

    post_positions = positions + [candidate_position] if candidate_position is not None else positions
    post_scenarios = _run_scenarios(post_positions, current_spx, sigma)
    post_max_core = _max_core_loss_pct(post_scenarios, account_size)
    incremental = post_max_core - pre_max_core

    budget_core = params.shock_budget_core_hv if is_high_vol else params.shock_budget_core_normal
    budget_incremental = (
        params.shock_budget_incremental_hv if is_high_vol else params.shock_budget_incremental
    )

    core_breach = abs(post_max_core) > budget_core
    incremental_breach = abs(incremental) > budget_incremental

    approved = True
    reject_reason = None
    if mode == "active" and (core_breach or incremental_breach):
        approved = False
        reasons = []
        if core_breach:
            reasons.append(f"core {abs(post_max_core)*100:.2f}% > {budget_core*100:.2f}%")
        if incremental_breach:
            reasons.append(f"incremental {abs(incremental)*100:.2f}% > {budget_incremental*100:.2f}%")
        reject_reason = "; ".join(reasons)

    return ShockReport(
        date=date,
        nav=account_size,
        mode=mode,
        pre_scenarios=pre_scenarios,
        pre_max_core_loss_pct=pre_max_core,
        post_scenarios=post_scenarios,
        post_max_core_loss_pct=post_max_core,
        incremental_shock_pct=incremental,
        budget_core=budget_core,
        budget_incremental=budget_incremental,
        approved=approved,
        reject_reason=reject_reason,
        sigma_used=sigma,
    )
