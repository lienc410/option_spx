"""
Strategy Selector

Combines VIX regime, IV signal, and trend signal into a concrete strategy
recommendation with specific parameters: strategy name, underlying, DTE,
delta targets for each leg, and position sizing.

Decision matrix (from design doc):
─────────────────────────────────────────────────────────────────────
VIX Regime   IV Signal   Trend      → Strategy
─────────────────────────────────────────────────────────────────────
LOW_VOL      any         NEUTRAL    → Iron Condor        SPX 45/90
LOW_VOL      any         BULLISH    → Bull Call Diagonal SPX 45/90
LOW_VOL      any         BEARISH    → Bear Call Diagonal SPX 45/90
NORMAL       HIGH        BULLISH    → Short Put          SPX 30
NORMAL       HIGH        NEUTRAL    → Bull Call Diagonal SPX 30/90
NORMAL       HIGH        BEARISH    → Bear Put Spread    SPY 21
NORMAL       NEUTRAL     BULLISH    → Bull Call Diagonal SPX 30/90
NORMAL       NEUTRAL     NEUTRAL    → Bull Call Diagonal SPX 30/90
NORMAL       NEUTRAL     BEARISH    → Bear Call Spread   SPY 21
NORMAL       LOW         BULLISH    → Bull Call Spread   SPY 21
NORMAL       LOW         NEUTRAL    → Calendar Spread    SPX 30/60
NORMAL       LOW         BEARISH    → Bear Put Spread    SPY 21
HIGH_VOL     HIGH/NEUTRAL BULLISH   → Buy LEAP Call      SPY 365+
HIGH_VOL     HIGH/NEUTRAL NEUTRAL   → Buy LEAP Call      SPY 365+
HIGH_VOL     HIGH/NEUTRAL BEARISH   → Buy LEAP Put       SPY 365+
HIGH_VOL     LOW          any       → Reduce / Wait      —
─────────────────────────────────────────────────────────────────────

IV signal uses IV Percentile (IVP) when IVR/IVP diverge by > 15 pts,
as a VIX spike may have distorted the 52-week high.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from signals.vix_regime  import Regime, VixSnapshot,   get_current_snapshot,   fetch_vix_history
from signals.iv_rank     import IVSignal, IVSnapshot,  get_current_iv_snapshot
from signals.trend       import TrendSignal, TrendSnapshot, get_current_trend, fetch_spx_history


# IV Percentile thresholds (used when IVR/IVP diverge)
IVP_HIGH_THRESHOLD = 70.0
IVP_LOW_THRESHOLD  = 40.0

# Minimum IVP to sell premium in HIGH_VOL (if IVP low → vol not rich, wait)
MIN_IVP_FOR_HIGH_VOL_SELL = 50.0


class StrategyName(str, Enum):
    BULL_CALL_DIAGONAL  = "Bull Call Diagonal"
    BEAR_CALL_DIAGONAL  = "Bear Call Diagonal"
    IRON_CONDOR         = "Iron Condor"
    SHORT_PUT           = "Short Put"
    BULL_CALL_SPREAD    = "Bull Call Spread"
    BEAR_CALL_SPREAD    = "Bear Call Spread"
    BEAR_PUT_SPREAD     = "Bear Put Spread"
    CALENDAR_SPREAD     = "Calendar Spread"
    BUY_LEAP_CALL       = "Buy LEAP Call"
    BUY_LEAP_PUT        = "Buy LEAP Put"
    REDUCE_WAIT         = "Reduce / Wait"


@dataclass
class Leg:
    action:   str          # "BUY" or "SELL"
    option:   str          # "CALL" or "PUT"
    dte:      int          # days to expiration
    delta:    float        # target delta (absolute value)
    note:     str = ""


@dataclass
class Recommendation:
    strategy:        StrategyName
    underlying:      str           # "SPX" or "SPY"
    legs:            list[Leg]
    max_risk:        str           # human description
    target_return:   str
    size_rule:       str           # position sizing guideline
    roll_rule:       str           # when to roll or adjust
    rationale:       str           # one-line explanation of why this strategy
    # signals that drove this recommendation
    vix_snapshot:    VixSnapshot   = field(repr=False)
    iv_snapshot:     IVSnapshot    = field(repr=False)
    trend_snapshot:  TrendSnapshot = field(repr=False)
    # flags
    macro_warning:   bool = False  # True if SPX below 200MA


    def summary(self) -> str:
        """Single-line summary for quick reading."""
        legs_str = "  |  ".join(
            f"{l.action} {l.option} {l.dte}DTE δ{l.delta:.2f}" for l in self.legs
        )
        warn = "  ⚠ macro downtrend" if self.macro_warning else ""
        return (
            f"{'─'*60}\n"
            f"Strategy : {self.strategy.value}\n"
            f"Underlying: {self.underlying}\n"
            f"Legs     : {legs_str}\n"
            f"Max Risk : {self.max_risk}\n"
            f"Target   : {self.target_return}\n"
            f"Size Rule: {self.size_rule}\n"
            f"Roll At  : {self.roll_rule}\n"
            f"Why      : {self.rationale}{warn}\n"
            f"{'─'*60}"
        )

    def signals_summary(self) -> str:
        iv_note = ""
        diff = abs(self.iv_snapshot.iv_rank - self.iv_snapshot.iv_percentile)
        if diff > 15:
            iv_note = f" (IVP {self.iv_snapshot.iv_percentile:.1f} used — IVR distorted)"
        return (
            f"Signals  : VIX {self.vix_snapshot.vix:.2f} [{self.vix_snapshot.regime.value}] | "
            f"IV Rank {self.iv_snapshot.iv_rank:.1f} / IVP {self.iv_snapshot.iv_percentile:.1f} "
            f"[{self.iv_snapshot.iv_signal.value}]{iv_note} | "
            f"Trend [{self.trend_snapshot.signal.value}]"
        )


def _effective_iv_signal(iv: IVSnapshot) -> IVSignal:
    """
    Use IV Percentile instead of IV Rank when they diverge by > 15 pts,
    as a single VIX spike can make IVR appear misleadingly low.
    """
    diff = abs(iv.iv_rank - iv.iv_percentile)
    if diff <= 15:
        return iv.iv_signal

    # Reclassify using IVP
    if iv.iv_percentile > IVP_HIGH_THRESHOLD:
        return IVSignal.HIGH
    elif iv.iv_percentile < IVP_LOW_THRESHOLD:
        return IVSignal.LOW
    return IVSignal.NEUTRAL


def select_strategy(
    vix: VixSnapshot,
    iv:  IVSnapshot,
    trend: TrendSnapshot,
) -> Recommendation:
    """
    Apply the decision matrix and return a Recommendation.
    """
    r    = vix.regime
    iv_s = _effective_iv_signal(iv)
    t    = trend.signal
    macro_warn = not trend.above_200

    # ── HIGH_VOL ─────────────────────────────────────────────────────
    if r == Regime.HIGH_VOL:
        if iv_s == IVSignal.LOW:
            return Recommendation(
                strategy      = StrategyName.REDUCE_WAIT,
                underlying    = "—",
                legs          = [],
                max_risk      = "No new positions",
                target_return = "—",
                size_rule     = "Hold cash; VIX elevated but premium not rich",
                roll_rule     = "Re-evaluate when VIX drops below 22 or IVP rises above 50",
                rationale     = "HIGH_VOL + LOW IV — unusual combo (vol elevated but not priced in?). Wait.",
                vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
                macro_warning = macro_warn,
            )

        if t == TrendSignal.BEARISH:
            return Recommendation(
                strategy      = StrategyName.BUY_LEAP_PUT,
                underlying    = "SPY",
                legs          = [Leg("BUY", "PUT", 365, 0.70, "Deep ITM LEAP put — buy when IV high")],
                max_risk      = "Full premium paid",
                target_return = "50–100%+ on LEAP if SPX continues lower",
                size_rule     = "Max 20–25% of risk budget; LEAP is a long-hold position",
                roll_rule     = "Roll 90 days before expiry if still in the money",
                rationale     = "HIGH_VOL + BEARISH — IV spike + downtrend: buy LEAP put while vol is elevated",
                vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
                macro_warning = macro_warn,
            )

        # BULLISH or NEUTRAL in HIGH_VOL → buy LEAP call
        return Recommendation(
            strategy      = StrategyName.BUY_LEAP_CALL,
            underlying    = "SPY",
            legs          = [Leg("BUY", "CALL", 365, 0.70, "Deep ITM LEAP call — buy when IV high")],
            max_risk      = "Full premium paid",
            target_return = "50–100%+ on LEAP if SPX recovers",
            size_rule     = "Max 20–25% of risk budget; LEAP is a long-hold position",
            roll_rule     = "Roll 90 days before expiry; sell covered call on top (PMCC) once VIX normalises",
            rationale     = "HIGH_VOL + BULLISH/NEUTRAL — IV spike: buy LEAP call cheaply relative to realised vol",
            vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
            macro_warning = macro_warn,
        )

    # ── LOW_VOL ──────────────────────────────────────────────────────
    if r == Regime.LOW_VOL:
        if t == TrendSignal.NEUTRAL:
            return Recommendation(
                strategy      = StrategyName.IRON_CONDOR,
                underlying    = "SPX",
                legs          = [
                    Leg("SELL", "CALL", 45, 0.16, "Upper short wing"),
                    Leg("BUY",  "CALL", 45, 0.08, "Upper long wing  (+50–100 pts above short)"),
                    Leg("SELL", "PUT",  45, 0.16, "Lower short wing"),
                    Leg("BUY",  "PUT",  45, 0.08, "Lower long wing  (-50–100 pts below short)"),
                ],
                max_risk      = "Wing width × 100 − net credit",
                target_return = "Collect 25–33% of wing width as credit; close at 50% profit",
                size_rule     = "Risk ≤ 3% of account per condor; PM margin ~3–5× lower than Reg-T",
                roll_rule     = "Roll at 21 DTE if untested; defend at 30% loss of credit received",
                rationale     = "LOW_VOL + NEUTRAL — range-bound market; 16-delta wings give ~70% PoP",
                vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
                macro_warning = macro_warn,
            )

        if t == TrendSignal.BULLISH:
            return Recommendation(
                strategy      = StrategyName.BULL_CALL_DIAGONAL,
                underlying    = "SPX",
                legs          = [
                    Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
                    Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
                ],
                max_risk      = "Net debit paid",
                target_return = "15–20% of debit; close short leg at 50% profit and re-sell",
                size_rule     = "Risk ≤ 3% of account per diagonal",
                roll_rule     = "Roll short leg at 21 DTE to exactly 30 DTE (set calendar alert)",
                rationale     = "LOW_VOL + BULLISH — theta is cheap; use 45 DTE short leg to widen collection window",
                vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
                macro_warning = macro_warn,
            )

        # BEARISH in LOW_VOL
        return Recommendation(
            strategy      = StrategyName.BEAR_CALL_DIAGONAL,
            underlying    = "SPX",
            legs          = [
                Leg("BUY",  "PUT", 90, 0.70, "Long leg — deep ITM put"),
                Leg("SELL", "PUT", 45, 0.30, "Short leg — OTM put"),
            ],
            max_risk      = "Net debit paid",
            target_return = "15–20% of debit",
            size_rule     = "Risk ≤ 3% of account",
            roll_rule     = "Roll short leg at 21 DTE",
            rationale     = "LOW_VOL + BEARISH — bearish diagonal captures downside with defined risk",
            vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
            macro_warning = macro_warn,
        )

    # ── NORMAL ───────────────────────────────────────────────────────
    if iv_s == IVSignal.HIGH:
        if t == TrendSignal.BULLISH:
            return Recommendation(
                strategy      = StrategyName.SHORT_PUT,
                underlying    = "SPX",
                legs          = [Leg("SELL", "PUT", 30, 0.30, "OTM short put — cash-secured or PM margined")],
                max_risk      = "Strike price × 100 (theoretical max if SPX → 0); manage at 2× credit",
                target_return = "Close at 50% of credit received (~15 DTE)",
                size_rule     = "Risk ≤ 3% of account; PM margin ≈ 15–20% of notional",
                roll_rule     = "Roll at 21 DTE if > 50% profit; defend at 2× credit loss",
                rationale     = "NORMAL + IV HIGH + BULLISH — rich premium + uptrend: ideal short put setup",
                vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
                macro_warning = macro_warn,
            )

        if t == TrendSignal.BEARISH:
            return Recommendation(
                strategy      = StrategyName.BEAR_PUT_SPREAD,
                underlying    = "SPY",
                legs          = [
                    Leg("BUY",  "PUT", 21, 0.50, "ATM put — full delta exposure"),
                    Leg("SELL", "PUT", 21, 0.25, "OTM put — cap cost, define risk"),
                ],
                max_risk      = "Net debit paid (spread width − credit)",
                target_return = "50–80% of max profit; close before 7 DTE",
                size_rule     = "Risk ≤ 2% of account; tactical position",
                roll_rule     = "Close at 50% profit or 7 DTE, whichever comes first",
                rationale     = "NORMAL + IV HIGH + BEARISH — premium rich; debit spread limits overpaying for vol",
                vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
                macro_warning = macro_warn,
            )

        # NEUTRAL
        return Recommendation(
            strategy      = StrategyName.BULL_CALL_DIAGONAL,
            underlying    = "SPX",
            legs          = [
                Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM"),
                Leg("SELL", "CALL", 30, 0.30, "Short leg — OTM, theta collection"),
            ],
            max_risk      = "Net debit paid",
            target_return = "15–20% of debit per cycle",
            size_rule     = "Risk ≤ 3% of account",
            roll_rule     = "Roll short leg at 21 DTE to exactly 30 DTE",
            rationale     = "NORMAL + IV HIGH + NEUTRAL — premium elevated; standard diagonal is the core position",
            vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
            macro_warning = macro_warn,
        )

    if iv_s == IVSignal.LOW:
        if t == TrendSignal.BULLISH:
            return Recommendation(
                strategy      = StrategyName.BULL_CALL_SPREAD,
                underlying    = "SPY",
                legs          = [
                    Leg("BUY",  "CALL", 21, 0.50, "ATM call — directional"),
                    Leg("SELL", "CALL", 21, 0.25, "OTM call — reduce cost"),
                ],
                max_risk      = "Net debit paid",
                target_return = "50–80% of max profit; close before 7 DTE",
                size_rule     = "Risk ≤ 2% of account; directional tactical trade",
                roll_rule     = "Close at 50% profit or 7 DTE",
                rationale     = "NORMAL + IV LOW + BULLISH — cheap vol + uptrend: buy debit spread",
                vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
                macro_warning = macro_warn,
            )

        if t == TrendSignal.BEARISH:
            return Recommendation(
                strategy      = StrategyName.BEAR_PUT_SPREAD,
                underlying    = "SPY",
                legs          = [
                    Leg("BUY",  "PUT", 21, 0.50, "ATM put"),
                    Leg("SELL", "PUT", 21, 0.25, "OTM put — reduce cost"),
                ],
                max_risk      = "Net debit paid",
                target_return = "50–80% of max profit",
                size_rule     = "Risk ≤ 2% of account",
                roll_rule     = "Close at 50% profit or 7 DTE",
                rationale     = "NORMAL + IV LOW + BEARISH — cheap vol; buy direction directly",
                vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
                macro_warning = macro_warn,
            )

        # NEUTRAL + LOW IV
        return Recommendation(
            strategy      = StrategyName.CALENDAR_SPREAD,
            underlying    = "SPX",
            legs          = [
                Leg("SELL", "CALL", 30, 0.50, "Near-term ATM — sell short vol"),
                Leg("BUY",  "CALL", 60, 0.50, "Far-term ATM  — long vol"),
            ],
            max_risk      = "Net debit paid",
            target_return = "20–30% of debit; close when front leg decays 50%",
            size_rule     = "Risk ≤ 2% of account",
            roll_rule     = "Roll front leg at 7 DTE",
            rationale     = "NORMAL + IV LOW + NEUTRAL — sell near-term vol, hold long-term vol cheaply",
            vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
            macro_warning = macro_warn,
        )

    # iv_s == NEUTRAL, regime == NORMAL
    if t == TrendSignal.BEARISH:
        return Recommendation(
            strategy      = StrategyName.BEAR_CALL_SPREAD,
            underlying    = "SPY",
            legs          = [
                Leg("SELL", "CALL", 21, 0.40, "Near ATM call — sell into resistance"),
                Leg("BUY",  "CALL", 21, 0.20, "OTM call — cap risk"),
            ],
            max_risk      = "Wing width − credit received",
            target_return = "50% of credit",
            size_rule     = "Risk ≤ 2% of account",
            roll_rule     = "Close at 50% profit or 7 DTE",
            rationale     = "NORMAL + IV NEUTRAL + BEARISH — directional credit spread in downtrend",
            vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
            macro_warning = macro_warn,
        )

    # NORMAL + NEUTRAL IV + BULLISH or NEUTRAL trend → standard diagonal
    return Recommendation(
        strategy      = StrategyName.BULL_CALL_DIAGONAL,
        underlying    = "SPX",
        legs          = [
            Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM"),
            Leg("SELL", "CALL", 30, 0.30, "Short leg — OTM"),
        ],
        max_risk      = "Net debit paid",
        target_return = "15–20% of debit per cycle",
        size_rule     = "Risk ≤ 3% of account",
        roll_rule     = "Roll short leg at 21 DTE to exactly 30 DTE",
        rationale     = "NORMAL + IV NEUTRAL + BULLISH/NEUTRAL — standard diagonal is the default core position",
        vix_snapshot  = vix, iv_snapshot = iv, trend_snapshot = trend,
        macro_warning = macro_warn,
    )


def get_recommendation(
    vix_df=None,
    spx_df=None,
) -> Recommendation:
    """
    Fetch all signals and return today's recommendation.
    Accepts optional pre-fetched DataFrames to avoid redundant downloads.
    """
    vix_data  = fetch_vix_history(period="2y")
    spx_data  = fetch_spx_history(period="2y")

    vix_snap   = get_current_snapshot(vix_data)
    iv_snap    = get_current_iv_snapshot(vix_data)
    trend_snap = get_current_trend(spx_data)

    return select_strategy(vix_snap, iv_snap, trend_snap)


if __name__ == "__main__":
    print("Fetching market data...\n")
    rec = get_recommendation()

    print("=" * 60)
    print("   SPX/SPY OPTIONS RECOMMENDATION")
    print("=" * 60)
    print(rec.signals_summary())
    print()
    print(rec.summary())
    print()

    if rec.macro_warning:
        print("⚠  MACRO WARNING: SPX is below its 200-day MA.")
        print("   Consider reducing size by 25–50% on any bullish trade.\n")

    if rec.strategy == StrategyName.REDUCE_WAIT:
        print("→  No new positions recommended today. Hold cash.\n")
    else:
        print("→  Next action: verify strikes on your broker platform,")
        print("   then execute manually per the size rule above.\n")
