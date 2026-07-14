from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyDescriptor:
    key: str
    name: str
    emoji: str
    direction: str
    underlying: str
    trade_type: str
    dte_text: str
    delta_text: str
    when_text: str
    risk_text: str
    detail_roll_text: str
    max_risk_text: str
    target_return_text: str
    roll_rule_text: str
    short_gamma: bool = False
    short_vega: bool = False
    delta_sign: str = "neut"
    manual_entry_allowed: bool = True


STRATEGIES_BY_KEY: dict[str, StrategyDescriptor] = {
    "es_short_put": StrategyDescriptor(
        key="es_short_put",
        name="ES Short Put",
        emoji="📉",
        direction="bull",
        underlying="/ES",
        trade_type="Credit — Naked Put",
        dte_text="45 DTE",
        delta_text="Short put δ0.20",
        when_text="Standalone /ES production cell. Only available when the trend filter is bullish and shared buying power stays inside the conservative NLV cap.",
        risk_text="Undefined downside below the strike. This minimal production path is limited to one slot, one contract, and a hard pre-trade buying-power check.",
        detail_roll_text="Close at 21 DTE if still open. Stop out at 10× credit (disaster fail-safe; 2× mark raises an early warning); do not add size or ladder expiries inside this path.",
        max_risk_text="Undefined downside; entry blocked by shared BP <= 20% NLV cap",
        target_return_text="Single 1-lot income candidate; manage manually inside the existing position workflow",
        roll_rule_text="Close at 21 DTE; stop at 10× credit (2× warning)",
        short_gamma=True,
        short_vega=True,
        delta_sign="bull",
    ),
    "bull_call_diagonal": StrategyDescriptor(
        key="bull_call_diagonal",
        name="Bull Call Diagonal",
        emoji="📈",
        direction="bull",
        underlying="SPX",
        trade_type="Debit — Diagonal Spread",
        dte_text="Long 90 DTE / Short 45 DTE",
        delta_text="Long call δ0.70 (90d)  Short call δ0.30 (45d)",
        when_text="LOW_VOL + BULLISH. Cheap theta and bullish trend favor a 90/45 diagonal when volatility is subdued.",
        risk_text="Max risk = net debit paid. Directional upside plus front-leg theta decay; the trade is closed if the bullish thesis breaks.",
        detail_roll_text="Close the entire position when the short leg reaches 21 DTE. Take profit at +60% of debit (params.profit_target); stop at -50% of debit. Short-leg residual ≤15% of entry credit → buy back / roll immediately (SPEC-127 collapse buyback, position-state trigger — the bot pushes CLOSE/ROLL when it fires).",
        max_risk_text="Net debit paid",
        target_return_text="15–20% of debit paid; close entire position at 60% profit",
        roll_rule_text="Close entire position at 21 DTE of short leg; stop out at 50% loss of debit; short-leg residual ≤15% → collapse buyback (SPEC-127)",
        short_gamma=False,
        short_vega=False,
        delta_sign="bull",
    ),
    "iron_condor": StrategyDescriptor(
        key="iron_condor",
        name="Iron Condor",
        emoji="🦅",
        direction="neut",
        underlying="SPX",
        trade_type="Credit — Iron Condor",
        dte_text="45 DTE (all legs)",
        delta_text="Short put δ0.16 / Short call δ0.16 | Long wings δ0.08",
        when_text="LOW_VOL + NEUTRAL and selected NORMAL neutral/bearish cells, but only when VIX is stable and IVP sits inside the allowed band.",
        risk_text="Max risk = wing width × 100 − net credit. Defined risk on both sides with short strikes at δ0.16 and protective wings at δ0.08.",
        detail_roll_text="Target 60% profit after at least 10 days held. Close at 21 DTE rather than rolling forward in the selector layer.",
        max_risk_text="Wing width × 100 − net credit",
        target_return_text="Collect 25–33% of wing width; close at 60% profit",
        roll_rule_text="Close at 21 DTE; take 60% profit after min 10 days held",
        short_gamma=True,
        short_vega=True,
        delta_sign="neut",
    ),
    "bull_put_spread": StrategyDescriptor(
        key="bull_put_spread",
        name="Bull Put Spread",
        emoji="💰",
        direction="bull",
        underlying="SPX",
        trade_type="Credit — Bull Put Spread",
        dte_text="30 DTE",
        delta_text="Short put δ0.30  Long put δ0.15",
        when_text="NORMAL regime with bullish trend when guardrails pass. Both HIGH-IV and NEUTRAL-IV bullish paths can use it.",
        risk_text="Max risk = spread width − net credit. Fully defined downside with short put at δ0.30 and hedge put at δ0.15, same expiry.",
        detail_roll_text="Target 60% profit after at least 10 days held. Close at 21 DTE. The backtest engine also enforces stop/roll-up management.",
        max_risk_text="Spread width − net credit (defined, capped downside)",
        target_return_text="Close at 60% of credit; min 10 days held before profit target fires",
        roll_rule_text="Close at 21 DTE; take 60% profit after min 10 days held",
        short_gamma=True,
        short_vega=True,
        delta_sign="bull",
    ),
    "bull_put_spread_hv": StrategyDescriptor(
        key="bull_put_spread_hv",
        name="Bull Put Spread (High Vol)",
        emoji="🔥",
        direction="bull",
        underlying="SPX",
        trade_type="Credit — Vertical Spread (Reduced Size)",
        dte_text="35 DTE",
        delta_text="Short put δ0.20  Long put δ0.10",
        when_text="HIGH_VOL + BULLISH under calmer conditions inside the high-vol regime. The selector requires no backwardation and no rising VIX before selling puts.",
        risk_text="Max risk = spread width − net credit. Uses reduced size, shorter delta (δ0.20 / δ0.10), and 35 DTE to keep risk tighter in stressed vol.",
        detail_roll_text="Close at 21 DTE; stop at 2× credit. Reduced-size premium sale, not a hold-to-expiry trade.",
        max_risk_text="Spread width − net credit (defined risk)",
        target_return_text="Close at 60% of credit; wider strikes = more premium collected",
        roll_rule_text="Close at 21 DTE; take 60% profit after min 10 days held; stop at 2× credit",
        short_gamma=True,
        short_vega=True,
        delta_sign="bull",
    ),
    "bear_call_spread_hv": StrategyDescriptor(
        key="bear_call_spread_hv",
        name="Bear Call Spread (High Vol)",
        emoji="🛡️",
        direction="bear",
        underlying="SPX",
        trade_type="Credit — Vertical Spread (Reduced Size)",
        dte_text="45 DTE",
        delta_text="Short call δ0.20  Long call δ0.10",
        when_text="HIGH_VOL + BEARISH when VIX is not rising. Inflated call premium and bearish trend allow a defined-risk call spread with tighter delta and reduced size.",
        risk_text="Max risk = spread width − net credit. Sell at δ0.20 with a further OTM long call to cap upside risk. Reduced size reflects elevated vol regime and gap risk.",
        detail_roll_text="Close at 21 DTE; stop at 2× credit. Wait instead if VIX is still rising.",
        max_risk_text="Spread width − net credit (defined risk)",
        target_return_text="Close at 60% of credit received",
        roll_rule_text="Close at 21 DTE; stop at 2× credit",
        short_gamma=True,
        short_vega=True,
        delta_sign="bear",
    ),
    "iron_condor_hv": StrategyDescriptor(
        key="iron_condor_hv",
        name="Iron Condor (High Vol)",
        emoji="🦅",
        direction="neut",
        underlying="SPX",
        trade_type="Credit — Iron Condor (Reduced Size)",
        dte_text="45 DTE (all legs)",
        delta_text="Short put δ0.16 / Short call δ0.16 | Long wings δ0.08",
        when_text="HIGH_VOL + NEUTRAL when VIX is stable and term structure is not in backwardation. Rich premium on both sides supports a reduced-size condor.",
        risk_text="Defined risk on both sides. Elevated premium improves credit, but position size stays reduced because the vol regime remains stressed.",
        detail_roll_text="Close at 21 DTE; stop at 2× credit. Skip when VIX is rising or term structure is inverted.",
        max_risk_text="Wing width × 100 − net credit (defined risk)",
        target_return_text="Close at 60% of credit received",
        roll_rule_text="Close at 21 DTE; stop at 2× credit",
        short_gamma=True,
        short_vega=True,
        delta_sign="neut",
    ),
    # ── SPEC-115 Phase A: Q041 T2 CSP paper-trade strategies ──────────────────
    "q041_t2_googl_csp": StrategyDescriptor(
        key="q041_t2_googl_csp",
        name="Q041 T2 GOOGL CSP",
        emoji="📋",
        direction="bull",
        underlying="GOOGL",
        trade_type="Credit — Cash-Secured Put (Paper)",
        dte_text="21 DTE (±3d)",
        delta_text="Short put δ0.20 (±5pp)",
        when_text=(
            "Daily EOD scan; Q041 paper-trade lane only. SPEC-111 cash cap binds "
            "single GOOGL CSP ($36.6k) typically > $22.2k cap."
        ),
        risk_text=(
            "Assignment risk = K × 100 cash. Single-name tail (missing COVID/2019-2021 "
            "in 4y backtest). Paper trade verifies cash-bound boundary."
        ),
        detail_roll_text="No roll in paper. Default exit: hold to expiry or assignment.",
        max_risk_text="K × 100 cash collateral per contract (~$36.6k at K=$366).",
        target_return_text="Full credit at expiry (S_exit > K).",
        roll_rule_text="None — Phase A is observation lane.",
        short_gamma=True,
        short_vega=False,
        delta_sign="pos",
        manual_entry_allowed=False,
    ),
    "q041_t2_amzn_csp": StrategyDescriptor(
        key="q041_t2_amzn_csp",
        name="Q041 T2 AMZN CSP",
        emoji="📋",
        direction="bull",
        underlying="AMZN",
        trade_type="Credit — Cash-Secured Put (Paper)",
        dte_text="21 DTE (±3d)",
        delta_text="Short put δ0.25 (±5pp)",
        when_text=(
            "Daily EOD scan; Q041 paper-trade lane only. SPEC-111 cash cap binds "
            "single AMZN CSP ($25.2k) typically > $22.2k cap."
        ),
        risk_text=(
            "Assignment risk = K × 100 cash. Single-name tail (missing COVID/2019-2021 "
            "in 4y backtest). Paper trade verifies cash-bound boundary."
        ),
        detail_roll_text="No roll in paper. Default exit: hold to expiry or assignment.",
        max_risk_text="K × 100 cash collateral per contract (~$25.2k at K=$252).",
        target_return_text="Full credit at expiry (S_exit > K).",
        roll_rule_text="None — Phase A is observation lane.",
        short_gamma=True,
        short_vega=False,
        delta_sign="pos",
        manual_entry_allowed=False,
    ),
    # ── SPEC-115 Phase B: Q041 T3 earnings IC paper-trade strategies ──────────
    "q041_t3_cost_earnings_ic": StrategyDescriptor(
        key="q041_t3_cost_earnings_ic",
        name="Q041 T3 COST Earnings IC",
        emoji="📅",
        direction="neutral",
        underlying="COST",
        trade_type="Credit — Iron Condor (Earnings Paper)",
        dte_text="1-14 DTE (post-earnings nearest)",
        delta_text="ATM straddle wings, 1.0× implied move width",
        when_text=(
            "T-3 trading days before COST earnings; VIX ≥ 15 gate. "
            "Q041 paper-trade lane (observe-only → cautious paper per PM 2026-06-06)."
        ),
        risk_text=(
            "Max loss = width × 100 ≈ $4,200; 单事件击穿风险 (S_exit < K_put OR > K_call). "
            "N=15 backtest, 4y window missing COVID/2019-2021. SPEC-111 cap binds."
        ),
        detail_roll_text="No roll. T+1 (earnings 次日) auto close.",
        max_risk_text="(spread_width - net_credit) × 100 per contract.",
        target_return_text="Full credit at T+1 if both strikes hold.",
        roll_rule_text="None — paper observation lane.",
        short_gamma=True,
        short_vega=True,
        delta_sign="neut",
        manual_entry_allowed=False,
    ),
    "q041_t3_jpm_earnings_ic": StrategyDescriptor(
        key="q041_t3_jpm_earnings_ic",
        name="Q041 T3 JPM Earnings IC",
        emoji="📅",
        direction="neutral",
        underlying="JPM",
        trade_type="Credit — Iron Condor (Earnings Paper)",
        dte_text="1-14 DTE (post-earnings nearest)",
        delta_text="ATM straddle wings, 1.0× implied move width",
        when_text=(
            "T-3 trading days before JPM earnings; VIX ≥ 15 gate. "
            "Optional IMR ≥ 33% filter (skip if historical data missing)."
        ),
        risk_text=(
            "Max loss = width × 100 ≈ $2,000; N=9 backtest (very small sample). "
            "4y window missing COVID/2019-2021. SPEC-111 cap binds."
        ),
        detail_roll_text="No roll. T+1 auto close.",
        max_risk_text="(spread_width - net_credit) × 100 per contract.",
        target_return_text="Full credit at T+1 if both strikes hold.",
        roll_rule_text="None — paper observation lane.",
        short_gamma=True,
        short_vega=True,
        delta_sign="neut",
        manual_entry_allowed=False,
    ),
    "reduce_wait": StrategyDescriptor(
        key="reduce_wait",
        name="Reduce / Wait",
        emoji="⏸",
        direction="wait",
        underlying="—",
        trade_type="No position",
        dte_text="—",
        delta_text="—",
        when_text="No new position. Used for EXTREME_VOL and for any path where guardrails reject the setup: rising VIX, backwardation, stressed IVP, insufficient premium, or structurally low-edge combinations.",
        risk_text="Cash is a position. Hold flat and preserve capital when the selector does not see a positive-expectancy entry.",
        detail_roll_text="No position to roll. Re-evaluate on the next session after signals update.",
        max_risk_text="No new positions",
        target_return_text="—",
        roll_rule_text="Re-evaluate next trading session",
        short_gamma=False,
        short_vega=False,
        delta_sign="neut",
        manual_entry_allowed=False,
    ),
}

NAME_TO_KEY = {desc.name: key for key, desc in STRATEGIES_BY_KEY.items()}
KEY_TO_NAME = {key: desc.name for key, desc in STRATEGIES_BY_KEY.items()}

CANONICAL_MATRIX: dict[str, dict[str, dict[str, str | dict[str, str]]]] = {
    "LOW_VOL": {
        "HIGH":    {"BULLISH": "bull_call_diagonal", "NEUTRAL": "iron_condor",    "BEARISH": "reduce_wait"},
        "NEUTRAL": {"BULLISH": "bull_call_diagonal", "NEUTRAL": "iron_condor",    "BEARISH": "reduce_wait"},
        "LOW":     {"BULLISH": "bull_call_diagonal", "NEUTRAL": "iron_condor",    "BEARISH": "reduce_wait"},
    },
    "NORMAL": {
        "HIGH":    {"BULLISH": "bull_put_spread",    "NEUTRAL": "iron_condor",    "BEARISH": "iron_condor"},
        "NEUTRAL": {"BULLISH": "bull_put_spread",    "NEUTRAL": "iron_condor",    "BEARISH": "iron_condor"},
        "LOW":     {
            # SPEC-113: VIX<18 carve to BCD; VIX≥18 stays reduce_wait
            "BULLISH": {"VIX_LT_18": "bull_call_diagonal", "VIX_GE_18": "reduce_wait"},
            "NEUTRAL": "reduce_wait",
            "BEARISH": "reduce_wait",
        },
    },
    "HIGH_VOL": {
        "HIGH":    {"BULLISH": "bull_put_spread_hv", "NEUTRAL": "iron_condor_hv", "BEARISH": "bear_call_spread_hv"},
        "NEUTRAL": {"BULLISH": "bull_put_spread_hv", "NEUTRAL": "iron_condor_hv", "BEARISH": "bear_call_spread_hv"},
        "LOW":     {"BULLISH": "bull_put_spread_hv", "NEUTRAL": "iron_condor_hv", "BEARISH": "bear_call_spread_hv"},
    },
    "EXTREME_VOL": {
        "HIGH":    {"BULLISH": "reduce_wait",        "NEUTRAL": "reduce_wait",    "BEARISH": "reduce_wait"},
        "NEUTRAL": {"BULLISH": "reduce_wait",        "NEUTRAL": "reduce_wait",    "BEARISH": "reduce_wait"},
        "LOW":     {"BULLISH": "reduce_wait",        "NEUTRAL": "reduce_wait",    "BEARISH": "reduce_wait"},
    },
}

MATRIX_IV_ORDER = ["HIGH", "NEUTRAL", "LOW"]
MATRIX_TREND_ORDER = ["BULLISH", "NEUTRAL", "BEARISH"]


def strategy_key(strategy: Any) -> str:
    raw = getattr(strategy, "value", strategy)
    if raw in STRATEGIES_BY_KEY:
        return raw
    if raw in NAME_TO_KEY:
        return NAME_TO_KEY[raw]
    raise KeyError(f"Unknown strategy: {raw!r}")


def strategy_descriptor(strategy: Any) -> StrategyDescriptor:
    return STRATEGIES_BY_KEY[strategy_key(strategy)]


def strategy_name(strategy: Any) -> str:
    return strategy_descriptor(strategy).name


def manual_entry_options() -> list[dict[str, str]]:
    out = []
    for key, desc in STRATEGIES_BY_KEY.items():
        if desc.manual_entry_allowed:
            out.append({"key": key, "name": desc.name, "underlying": desc.underlying})
    return out


def _condition_label(key: str) -> str:
    return {"VIX_LT_18": "VIX < 18", "VIX_GE_18": "VIX ≥ 18"}.get(key, key)


def _render_cell(value: str | dict[str, str]) -> Any:
    if isinstance(value, str):
        return {
            "type": "single",
            "strategy": strategy_descriptor(value).key,
            "name": strategy_descriptor(value).name,
        }
    # dict-valued conditional cell (SPEC-113: NORMAL.LOW.BULLISH)
    return {
        "type": "conditional",
        "conditions": {
            cond_key: {
                "strategy": strategy_descriptor(strat).key,
                "name": strategy_descriptor(strat).name,
                "label": _condition_label(cond_key),
            }
            for cond_key, strat in value.items()
        },
    }


def matrix_payload() -> dict[str, Any]:
    return {
        regime: {
            iv: {trend: _render_cell(cell) for trend, cell in trend_map.items()}
            for iv, trend_map in iv_map.items()
        }
        for regime, iv_map in CANONICAL_MATRIX.items()
    }


def strategy_catalog_payload() -> dict[str, Any]:
    return {
        "strategies": {key: asdict(desc) for key, desc in STRATEGIES_BY_KEY.items()},
        "matrix": matrix_payload(),
        "manual_entry_options": manual_entry_options(),
        "iv_order": MATRIX_IV_ORDER,
        "trend_order": MATRIX_TREND_ORDER,
    }
