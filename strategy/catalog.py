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
        detail_roll_text="Close the entire position when the short leg reaches 21 DTE. Take profit at +50% of debit; stop at -50% of debit.",
        max_risk_text="Net debit paid",
        target_return_text="15–20% of debit paid; close entire position at 50% profit",
        roll_rule_text="Close entire position at 21 DTE of short leg; stop out at 50% loss of debit",
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
        detail_roll_text="Target 50% profit after at least 10 days held. Close at 21 DTE rather than rolling forward in the selector layer.",
        max_risk_text="Wing width × 100 − net credit",
        target_return_text="Collect 25–33% of wing width; close at 50% profit",
        roll_rule_text="Close at 21 DTE; take 50% profit after min 10 days held",
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
        detail_roll_text="Target 50% profit after at least 10 days held. Close at 21 DTE. The backtest engine also enforces stop/roll-up management.",
        max_risk_text="Spread width − net credit (defined, capped downside)",
        target_return_text="Close at 50% of credit; close at 50% after min 10 days held",
        roll_rule_text="Close at 21 DTE; take 50% profit after min 10 days held",
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
        target_return_text="Close at 50% of credit; wider strikes = more premium collected",
        roll_rule_text="Close at 21 DTE; stop at 2× credit",
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
        target_return_text="Close at 50% of credit received",
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
        target_return_text="Close at 50% of credit received",
        roll_rule_text="Close at 21 DTE; stop at 2× credit",
        short_gamma=True,
        short_vega=True,
        delta_sign="neut",
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

CANONICAL_MATRIX: dict[str, dict[str, dict[str, str]]] = {
    "LOW_VOL": {
        "HIGH":    {"BULLISH": "bull_call_diagonal", "NEUTRAL": "iron_condor",    "BEARISH": "reduce_wait"},
        "NEUTRAL": {"BULLISH": "bull_call_diagonal", "NEUTRAL": "iron_condor",    "BEARISH": "reduce_wait"},
        "LOW":     {"BULLISH": "bull_call_diagonal", "NEUTRAL": "iron_condor",    "BEARISH": "reduce_wait"},
    },
    "NORMAL": {
        "HIGH":    {"BULLISH": "bull_put_spread",    "NEUTRAL": "iron_condor",    "BEARISH": "iron_condor"},
        "NEUTRAL": {"BULLISH": "bull_put_spread",    "NEUTRAL": "iron_condor",    "BEARISH": "iron_condor"},
        "LOW":     {"BULLISH": "reduce_wait",        "NEUTRAL": "reduce_wait",    "BEARISH": "reduce_wait"},
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


def matrix_payload() -> dict[str, Any]:
    return {
        regime: {
            iv: {
                trend: strategy_descriptor(key).key
                for trend, key in trend_map.items()
            }
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
