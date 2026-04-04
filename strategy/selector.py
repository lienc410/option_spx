"""
Strategy Selector

Combines VIX regime, IV signal, and trend signal into a concrete strategy
recommendation with specific parameters: strategy name, underlying, DTE,
delta targets for each leg, and position sizing.

Decision matrix (updated):
─────────────────────────────────────────────────────────────────────
VIX Regime    IV Signal   Trend      → Strategy
─────────────────────────────────────────────────────────────────────
LOW_VOL       any         NEUTRAL    → Iron Condor           SPX 45
LOW_VOL       any         BULLISH    → Bull Call Diagonal     SPX 45/90
LOW_VOL       any         BEARISH    → Reduce / Wait          —
NORMAL        HIGH        BULLISH    → Bull Put Spread        SPX 30  *
NORMAL        HIGH        NEUTRAL    → Iron Condor            SPX 45
NORMAL        HIGH        BEARISH    → Bear Put Spread        SPY 21
NORMAL        NEUTRAL     BULLISH    → Bull Put Spread        SPX 30  *
NORMAL        NEUTRAL     NEUTRAL    → Iron Condor            SPX 45
NORMAL        NEUTRAL     BEARISH    → Bear Call Spread       SPY 21
NORMAL        LOW         BULLISH    → Bull Call Spread       SPY 21
NORMAL        LOW         NEUTRAL    → Reduce / Wait          —
NORMAL        LOW         BEARISH    → Bear Put Spread        SPY 21
HIGH_VOL      any         any        → Bull Put Spread HV     SPX **  *
EXTREME_VOL   any         any        → Reduce / Wait          —
─────────────────────────────────────────────────────────────────────
*  Bull Put Spread / HV skipped (→ REDUCE_WAIT) if VIX term structure is
   in backwardation (spot VIX > VIX3M), signalling elevated near-term panic.
** HIGH_VOL uses tighter params: lower delta (~0.20), DTE=35 (roll_21dte fires at ≤21),
   half position size — elevated premium offsets the extra risk.
   EXTREME_VOL threshold defaults to VIX ≥ 35 (configurable via StrategyParams).

Sizing tiers:
  Full size  — IV signal favors selling AND VIX trend falling/flat
  Half size  — VIX trend rising OR signals mixed OR HIGH_VOL regime

Exit rules:
  Credit positions: close at 50% profit (after min 10 days held) OR at 21 DTE
  Debit positions:  close at 50% profit or 50% loss; close before 7 DTE
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from strategy.catalog import strategy_descriptor, strategy_key as catalog_strategy_key

@dataclass
class StrategyParams:
    """
    Tunable strategy parameters passed through selector and backtest engine.
    All defaults reflect the baseline strategy design.
    """
    # VIX regime thresholds
    extreme_vix:        float = 35.0   # VIX ≥ this → REDUCE_WAIT (EXTREME_VOL)

    # HIGH_VOL Bull Put Spread params (22 ≤ VIX < extreme_vix)
    high_vol_delta:     float = 0.20   # short leg delta (further OTM than normal)
    high_vol_dte:       int   = 35     # enough window for theta; roll_21dte fires at DTE≤21 (~14-day hold)
    high_vol_size:      float = 0.50   # fraction of normal position size

    # NORMAL Bull Put Spread params
    normal_delta:       float = 0.30
    normal_dte:         int   = 30

    # Exit rules (apply to all credit strategies)
    profit_target:      float = 0.50   # close at this fraction of max credit
    stop_mult:          float = 2.0    # stop loss at N× credit received
    min_hold_days:      int   = 10     # minimum days before profit target can trigger

    # BP utilization target per regime (fraction of account_size per trade)
    # Used by backtest engine to size contracts; supersedes risk_pct + size_mult sizing.
    # Calibrated to tastytrade retail PM standard: single position ≤ 5–7% of account.
    bp_target_low_vol:  float = 0.10   # LOW_VOL:  10% — 2× scale (SPEC-024)
    bp_target_normal:   float = 0.10   # NORMAL:   10% — 2× scale (SPEC-024)
    bp_target_high_vol: float = 0.07   # HIGH_VOL: 7% — 2× scale (SPEC-024)

    # Total BP ceiling per regime (fraction of account_size, all concurrent positions combined)
    # Governs maximum aggregate portfolio margin utilization at any point in time.
    bp_ceiling_low_vol:  float = 0.25  # LOW_VOL:  conservative — thin premium environment
    bp_ceiling_normal:   float = 0.35  # NORMAL:   baseline
    bp_ceiling_high_vol: float = 0.50  # HIGH_VOL: elevated premium offsets higher per-trade risk

    # Portfolio accounting baseline
    initial_equity: float = 100_000.0

    # Portfolio-level Greek exposure limits (multi-position architecture)
    max_short_gamma_positions: int = 3

    # Vol persistence throttle — limits new HIGH_VOL entries in sticky spells
    spell_age_cap: int = 30
    max_trades_per_spell: int = 2

    # Shock engine budgets (SPEC-025)
    shock_mode: str = "shadow"
    shock_budget_core_normal: float = 0.0125
    shock_budget_core_hv: float = 0.0100
    shock_budget_incremental: float = 0.0040
    shock_budget_incremental_hv: float = 0.0030
    shock_budget_bp_headroom: float = 0.15

    # Overlay thresholds (SPEC-026)
    overlay_mode: str = "disabled"
    overlay_freeze_accel: float = 0.15
    overlay_freeze_vix: float = 30.0
    overlay_trim_accel: float = 0.25
    overlay_trim_shock: float = 0.01
    overlay_hedge_accel: float = 0.35
    overlay_hedge_shock: float = 0.015
    overlay_emergency_vix: float = 40.0
    overlay_emergency_shock: float = 0.025
    overlay_emergency_bp: float = 0.10

    # Trend signal controls (SPEC-020)
    use_atr_trend: bool = True    # ATR-normalized entry gate (RS-020-2 validated: OOS Sharpe +6bp, MaxDD -2.73pp)
    bearish_persistence_days: int = 1  # Persistence exit: 1 = legacy single-day (persistence filter rejected by RS-020-2)

    def bp_ceiling_for_regime(self, regime: "Regime") -> float:
        """Return the total-portfolio BP ceiling for the given regime."""
        from signals.vix_regime import Regime

        if regime == Regime.LOW_VOL:
            return self.bp_ceiling_low_vol
        if regime == Regime.HIGH_VOL:
            return self.bp_ceiling_high_vol
        return self.bp_ceiling_normal

    def bp_target_for_regime(self, regime: "Regime") -> float:
        """Return the per-trade BP utilization target for the given regime."""
        from signals.vix_regime import Regime

        if regime == Regime.LOW_VOL:
            return self.bp_target_low_vol
        if regime == Regime.HIGH_VOL:
            return self.bp_target_high_vol
        return self.bp_target_normal


DEFAULT_PARAMS = StrategyParams()

from signals.vix_regime  import Regime, Trend, VixSnapshot,   get_current_snapshot,   fetch_vix_history
from signals.iv_rank     import IVSignal, IVSnapshot,  get_current_iv_snapshot
from signals.trend       import TrendSignal, TrendSnapshot, get_current_trend, fetch_spx_history
from strategy.state      import get_position_action


# IV Percentile thresholds (used when IVR/IVP diverge)
IVP_HIGH_THRESHOLD = 70.0
IVP_LOW_THRESHOLD  = 40.0


class StrategyName(str, Enum):
    BULL_PUT_SPREAD     = "Bull Put Spread"
    BULL_PUT_SPREAD_HV  = "Bull Put Spread (High Vol)"  # HIGH_VOL regime variant
    BEAR_CALL_SPREAD_HV = "Bear Call Spread (High Vol)"
    BULL_CALL_DIAGONAL  = "Bull Call Diagonal"
    BEAR_CALL_DIAGONAL  = "Bear Call Diagonal"
    IRON_CONDOR         = "Iron Condor"
    IRON_CONDOR_HV      = "Iron Condor (High Vol)"
    BULL_CALL_SPREAD    = "Bull Call Spread"
    BEAR_CALL_SPREAD    = "Bear Call Spread"
    BEAR_PUT_SPREAD     = "Bear Put Spread"
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
    strategy_key:    str
    strategy:        StrategyName
    underlying:      str           # "SPX", "SPY", or "—"
    legs:            list[Leg]
    max_risk:        str           # human description
    target_return:   str
    size_rule:       str           # position sizing guideline
    roll_rule:       str           # when to roll or adjust
    rationale:       str           # one-line explanation of why this strategy
    position_action: str           # OPEN / HOLD / CLOSE_AND_OPEN / WAIT / CLOSE_AND_WAIT
    # signals that drove this recommendation
    vix_snapshot:    VixSnapshot   = field(repr=False)
    iv_snapshot:     IVSnapshot    = field(repr=False)
    trend_snapshot:  TrendSnapshot = field(repr=False)
    # flags
    macro_warning:   bool = False  # True if SPX below 200MA
    backwardation:   bool = False  # True if spot VIX > VIX3M (term structure filter triggered)
    guardrail_label: str = ""

    def summary(self) -> str:
        """Single-line summary for quick reading."""
        legs_str = "  |  ".join(
            f"{l.action} {l.option} {l.dte}DTE δ{l.delta:.2f}" for l in self.legs
        )
        warn = "  ⚠ macro downtrend" if self.macro_warning else ""
        bk   = "  ⚠ backwardation skip" if self.backwardation else ""
        return (
            f"{'─'*60}\n"
            f"Action   : {self.position_action}\n"
            f"Strategy : {self.strategy.value}\n"
            f"Underlying: {self.underlying}\n"
            f"Legs     : {legs_str if legs_str else '—'}\n"
            f"Max Risk : {self.max_risk}\n"
            f"Target   : {self.target_return}\n"
            f"Size Rule: {self.size_rule}\n"
            f"Roll At  : {self.roll_rule}\n"
            f"Why      : {self.rationale}{warn}{bk}\n"
            f"{'─'*60}"
        )

    def signals_summary(self) -> str:
        iv_note = ""
        diff = abs(self.iv_snapshot.iv_rank - self.iv_snapshot.iv_percentile)
        if diff > 15:
            iv_note = f" (IVP {self.iv_snapshot.iv_percentile:.1f} used — IVR distorted)"
        ts_note = ""
        if self.vix_snapshot.vix3m is not None:
            ts_dir = "backwardation ⚠" if self.vix_snapshot.backwardation else "contango ✓"
            ts_note = f" | Term structure: {ts_dir} (VIX3M {self.vix_snapshot.vix3m:.2f})"
        return (
            f"Signals  : VIX {self.vix_snapshot.vix:.2f} [{self.vix_snapshot.regime.value}] | "
            f"IV Rank {self.iv_snapshot.iv_rank:.1f} / IVP {self.iv_snapshot.iv_percentile:.1f} "
            f"[{self.iv_snapshot.iv_signal.value}]{iv_note} | "
            f"Trend [{self.trend_snapshot.signal.value}]{ts_note}"
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


def _size_rule(vix: VixSnapshot, iv_s: IVSignal, t: TrendSignal) -> str:
    """
    Two-tier sizing:
      Full  — IV favors selling (HIGH/NEUTRAL) AND VIX trend flat/falling
      Half  — VIX trend rising OR signals mixed
    """
    vix_rising = (vix.trend == Trend.RISING)
    signals_favor_sell = iv_s in (IVSignal.HIGH, IVSignal.NEUTRAL)

    if not vix_rising and signals_favor_sell:
        return "Full size — risk ≤ 3% of account (signals agree + VIX flat/falling)"
    return "Half size — risk ≤ 1.5% of account (VIX rising or signals mixed)"


def _build_recommendation(
    strategy: StrategyName,
    *,
    vix: VixSnapshot,
    iv: IVSnapshot,
    trend: TrendSnapshot,
    rationale: str,
    position_action: str,
    legs: list[Leg] | None = None,
    size_rule: str | None = None,
    macro_warning: bool = False,
    backwardation: bool = False,
    guardrail_label: str = "",
) -> Recommendation:
    desc = strategy_descriptor(strategy.value)
    return Recommendation(
        strategy_key    = desc.key,
        strategy        = strategy,
        underlying      = desc.underlying,
        legs            = legs or [],
        max_risk        = desc.max_risk_text,
        target_return   = desc.target_return_text,
        size_rule       = size_rule or "—",
        roll_rule       = desc.roll_rule_text,
        rationale       = rationale,
        position_action = position_action,
        vix_snapshot    = vix,
        iv_snapshot     = iv,
        trend_snapshot  = trend,
        macro_warning   = macro_warning,
        backwardation   = backwardation,
        guardrail_label = guardrail_label,
    )


def _guardrail_label(reason: str, backwardation: bool = False) -> str:
    text = reason.upper()
    if "EXTREME_VOL" in text or "TAIL RISK TOO ELEVATED" in text:
        return "EXTREME VOL"
    if backwardation or "BACKWARDATION" in text:
        return "BACKWARDATION"
    if "VIX RISING" in text:
        return "VIX RISING"
    if "IVP=" in text or "IVP " in text:
        return "IVP FILTER"
    if "LOW_VOL + BEARISH" in text:
        return "NO EDGE"
    if "PREMIUM" in text and "UNFAVOURABLE" in text:
        return "PREMIUM FILTER"
    return "GUARDRAIL"


def _reduce_wait(reason: str, vix: VixSnapshot, iv: IVSnapshot, trend: TrendSnapshot,
                 macro_warn: bool, backwardation: bool = False) -> Recommendation:
    """Helper: build a REDUCE_WAIT recommendation."""
    action = get_position_action(
        StrategyName.REDUCE_WAIT.value,
        is_wait=True,
        strategy_key=catalog_strategy_key(StrategyName.REDUCE_WAIT.value),
    )
    return _build_recommendation(
        StrategyName.REDUCE_WAIT,
        vix=vix,
        iv=iv,
        trend=trend,
        rationale=reason,
        position_action=action,
        size_rule="Hold cash; re-evaluate when conditions improve",
        macro_warning=macro_warn,
        backwardation=backwardation,
        guardrail_label=_guardrail_label(reason, backwardation),
    )


def select_strategy(
    vix:    VixSnapshot,
    iv:     IVSnapshot,
    trend:  TrendSnapshot,
    params: StrategyParams = DEFAULT_PARAMS,
) -> Recommendation:
    """
    Apply the decision matrix and return a Recommendation.

    Args:
        params: Tunable strategy parameters (thresholds, deltas, DTEs, exit rules).
                Defaults to DEFAULT_PARAMS; pass a custom StrategyParams to run
                parameter experiments via the backtest engine.
    """
    r    = vix.regime
    iv_s = _effective_iv_signal(iv)
    t    = trend.signal
    macro_warn = not trend.above_200

    # ── EXTREME_VOL: VIX above extreme threshold → always wait ───────
    if r == Regime.HIGH_VOL and vix.vix >= params.extreme_vix:
        return _reduce_wait(
            f"EXTREME_VOL (VIX ≥ {params.extreme_vix:.0f}) — tail risk too elevated; hold cash",
            vix, iv, trend, macro_warn,
        )

    # ── HIGH_VOL: trade with tighter params ──────────────────────────
    if r == Regime.HIGH_VOL:
        if t == TrendSignal.BEARISH:
            if vix.trend == Trend.RISING:
                return _reduce_wait(
                    "HIGH_VOL + BEARISH + VIX RISING — panic escalating; wait for VIX to stabilise before selling calls",
                    vix, iv, trend, macro_warn,
                )
            action = get_position_action(
                StrategyName.BEAR_CALL_SPREAD_HV.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.BEAR_CALL_SPREAD_HV.value),
            )
            return _build_recommendation(
                StrategyName.BEAR_CALL_SPREAD_HV,
                vix=vix,
                iv=iv,
                trend=trend,
                legs=[
                    Leg("SELL", "CALL", 45, 0.20,
                        "Short call — δ0.20 OTM, collects inflated HIGH_VOL premium"),
                    Leg("BUY",  "CALL", 45, 0.10,
                        "Long call — further OTM, caps upside risk"),
                ],
                size_rule=(
                    f"{int(params.high_vol_size*100)}% size — risk ≤ "
                    f"{1.5*params.high_vol_size:.1f}% of account "
                    f"(HIGH_VOL BEARISH, reduced exposure)"
                ),
                rationale=(
                    "HIGH_VOL + BEARISH + VIX stable — inflated call premium with "
                    "directional tailwind; δ0.20 short call has high PoP"
                ),
                position_action=action,
                macro_warning=macro_warn,
            )

        if t == TrendSignal.NEUTRAL:
            if vix.trend == Trend.RISING:
                return _reduce_wait(
                    "HIGH_VOL + NEUTRAL + VIX RISING — vol escalating; wait for VIX to stabilise",
                    vix, iv, trend, macro_warn,
                )
            if vix.backwardation:
                return _reduce_wait(
                    "HIGH_VOL + NEUTRAL + BACKWARDATION — near-term put panic elevated; skip IC HV",
                    vix, iv, trend, macro_warn, backwardation=True,
                )
            action = get_position_action(
                StrategyName.IRON_CONDOR_HV.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.IRON_CONDOR_HV.value),
            )
            return _build_recommendation(
                StrategyName.IRON_CONDOR_HV,
                vix=vix,
                iv=iv,
                trend=trend,
                legs=[
                    Leg("SELL", "CALL", 45, 0.16,
                        "Upper short wing — inflated HIGH_VOL call premium"),
                    Leg("BUY",  "CALL", 45, 0.08,
                        "Upper long wing"),
                    Leg("SELL", "PUT",  45, 0.16,
                        "Lower short wing — inflated HIGH_VOL put premium"),
                    Leg("BUY",  "PUT",  45, 0.08,
                        "Lower long wing"),
                ],
                size_rule=(
                    f"{int(params.high_vol_size*100)}% size — risk ≤ "
                    f"{1.5*params.high_vol_size:.1f}% of account "
                    f"(HIGH_VOL, reduced exposure)"
                ),
                rationale=(
                    "HIGH_VOL + NEUTRAL + VIX stable — inflated premium on both sides; "
                    "symmetric IC captures vol risk premium without directional bet"
                ),
                position_action=action,
                macro_warning=macro_warn,
            )

        if vix.backwardation:
            return _reduce_wait(
                "HIGH_VOL + BACKWARDATION — VIX term structure inverted; skip Bull Put Spread",
                vix, iv, trend, macro_warn, backwardation=True,
            )
        # P1: VIX momentum rising → premium spiking, near-term risk elevated
        if vix.trend == Trend.RISING:
            return _reduce_wait(
                "HIGH_VOL + VIX RISING — near-term panic building; wait for VIX to stabilise",
                vix, iv, trend, macro_warn,
            )
        action = get_position_action(
            StrategyName.BULL_PUT_SPREAD_HV.value,
            is_wait=False,
            strategy_key=catalog_strategy_key(StrategyName.BULL_PUT_SPREAD_HV.value),
        )
        long_delta = round(params.high_vol_delta * 0.5, 2)
        return _build_recommendation(
            StrategyName.BULL_PUT_SPREAD_HV,
            vix=vix,
            iv=iv,
            trend=trend,
            legs=[
                Leg("SELL", "PUT", params.high_vol_dte, params.high_vol_delta,
                    f"Short put — δ{params.high_vol_delta}, wider strike for elevated VIX"),
                Leg("BUY",  "PUT", params.high_vol_dte, long_delta,
                    "Long put — further OTM, caps downside"),
            ],
            size_rule=(
                f"{int(params.high_vol_size*100)}% size — risk ≤ "
                f"{1.5*params.high_vol_size:.1f}% of account (HIGH_VOL, reduced exposure)"
            ),
            rationale=(
                f"HIGH_VOL (22≤VIX<{params.extreme_vix:.0f}) — elevated premium offsets risk; "
                f"tighter params (δ{params.high_vol_delta}, {params.high_vol_dte}DTE, {int(params.high_vol_size*100)}% size)"
            ),
            position_action=action,
            macro_warning=macro_warn,
        )

    # ── LOW_VOL ──────────────────────────────────────────────────────
    if r == Regime.LOW_VOL:
        if t == TrendSignal.NEUTRAL:
            # P3: VIX rising in low-vol env = regime about to shift; skip condor
            if vix.trend == Trend.RISING:
                return _reduce_wait(
                    "LOW_VOL + NEUTRAL but VIX RISING — potential regime shift; Iron Condor risk too high",
                    vix, iv, trend, macro_warn,
                )
            # P3: IVP outside 20–50 sweet-spot — too low = insufficient premium; too high = tail risk
            if iv.iv_percentile < 20 or iv.iv_percentile > 50:
                return _reduce_wait(
                    f"LOW_VOL + NEUTRAL but IVP={iv.iv_percentile:.0f} outside 20–50 — Iron Condor risk/reward unfavourable",
                    vix, iv, trend, macro_warn,
                )
            action = get_position_action(
                StrategyName.IRON_CONDOR.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.IRON_CONDOR.value),
            )
            return _build_recommendation(
                StrategyName.IRON_CONDOR,
                vix=vix,
                iv=iv,
                trend=trend,
                legs=[
                    Leg("SELL", "CALL", 45, 0.16, "Upper short wing"),
                    Leg("BUY",  "CALL", 45, 0.08, "Upper long wing  (+50–100 pts above short)"),
                    Leg("SELL", "PUT",  45, 0.16, "Lower short wing"),
                    Leg("BUY",  "PUT",  45, 0.08, "Lower long wing  (-50–100 pts below short)"),
                ],
                size_rule=_size_rule(vix, iv_s, t),
                rationale="LOW_VOL + NEUTRAL — range-bound market; 16-delta wings give ~70% PoP",
                position_action=action,
                macro_warning=macro_warn,
            )

        if t == TrendSignal.BULLISH:
            action = get_position_action(
                StrategyName.BULL_CALL_DIAGONAL.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.BULL_CALL_DIAGONAL.value),
            )
            return _build_recommendation(
                StrategyName.BULL_CALL_DIAGONAL,
                vix=vix,
                iv=iv,
                trend=trend,
                legs=[
                    Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
                    Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
                ],
                size_rule=_size_rule(vix, iv_s, t),
                rationale="LOW_VOL + BULLISH — theta is cheap; use 45 DTE short leg to widen collection window",
                position_action=action,
                macro_warning=macro_warn,
            )

        # BEARISH in LOW_VOL → no edge; low-vol pullbacks are typically V-shaped
        return _reduce_wait(
            "LOW_VOL + BEARISH — 低波动环境中的方向性看跌无统计边际；V型反转概率高，等待趋势确认",
            vix, iv, trend, macro_warn,
        )

    # ── NORMAL ───────────────────────────────────────────────────────
    if iv_s == IVSignal.HIGH:
        if t == TrendSignal.BULLISH:
            # Backwardation filter: skip if near-term panic elevated
            if vix.backwardation:
                return _reduce_wait(
                    "NORMAL + IV HIGH + BULLISH but VIX term structure in BACKWARDATION — skip Bull Put Spread",
                    vix, iv, trend, macro_warn, backwardation=True,
                )
            # P1: VIX momentum rising → conditions deteriorating, skip selling puts
            if vix.trend == Trend.RISING:
                return _reduce_wait(
                    "NORMAL + IV HIGH + BULLISH but VIX RISING — wait for VIX to stabilise before selling premium",
                    vix, iv, trend, macro_warn,
                )
            # P1: IVP ≥ 50 means market already stressed — tail risk outweighs extra premium
            if iv.iv_percentile >= 50:
                return _reduce_wait(
                    f"NORMAL + IV HIGH + BULLISH but IVP={iv.iv_percentile:.0f} ≥ 50 — stressed vol environment, BPS tail risk too high",
                    vix, iv, trend, macro_warn,
                )
            action = get_position_action(
                StrategyName.BULL_PUT_SPREAD.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.BULL_PUT_SPREAD.value),
            )
            return _build_recommendation(
                StrategyName.BULL_PUT_SPREAD,
                vix=vix,
                iv=iv,
                trend=trend,
                legs=[
                    Leg("SELL", "PUT", 30, 0.30, "Short put — OTM, collects premium"),
                    Leg("BUY",  "PUT", 30, 0.15, "Long put  — further OTM, caps downside"),
                ],
                size_rule=_size_rule(vix, iv_s, t),
                rationale="NORMAL + IV HIGH + BULLISH — calm vol (IVP<50) + uptrend: Bull Put Spread",
                position_action=action,
                macro_warning=macro_warn,
            )

        if t == TrendSignal.BEARISH:
            if vix.trend == Trend.RISING:
                return _reduce_wait(
                    "NORMAL + IV HIGH + BEARISH + VIX RISING — skip Iron Condor while vol escalating",
                    vix, iv, trend, macro_warn,
                )
            if iv.iv_percentile >= 50:
                return _reduce_wait(
                    f"NORMAL + IV HIGH + BEARISH but IVP={iv.iv_percentile:.0f} ≥ 50 — stressed vol; IC put side at risk",
                    vix, iv, trend, macro_warn,
                )
            action = get_position_action(
                StrategyName.IRON_CONDOR.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.IRON_CONDOR.value),
            )
            return _build_recommendation(
                StrategyName.IRON_CONDOR,
                vix=vix,
                iv=iv,
                trend=trend,
                legs=[
                    Leg("SELL", "CALL", 45, 0.16, "Upper short wing — BEARISH trend adds call-side safety"),
                    Leg("BUY",  "CALL", 45, 0.08, "Upper long wing"),
                    Leg("SELL", "PUT",  45, 0.16, "Lower short wing — δ0.16 OTM after confirmed downtrend"),
                    Leg("BUY",  "PUT",  45, 0.08, "Lower long wing"),
                ],
                size_rule=_size_rule(vix, iv_s, t),
                rationale=(
                    "NORMAL + IV HIGH + BEARISH + VIX stable — MA50 lag means downtrend confirmed; "
                    "IC collects from both sides without directional bet"
                ),
                position_action=action,
                macro_warning=macro_warn,
            )

        # NEUTRAL trend + HIGH IV → Iron Condor (stable vol is good for condors)
        # P3: skip if VIX rising — condor will be hit by the move that's building
        if vix.trend == Trend.RISING:
            return _reduce_wait(
                "NORMAL + IV HIGH + NEUTRAL but VIX RISING — Iron Condor unsafe; wait for vol to stabilise",
                vix, iv, trend, macro_warn,
            )
        # P3: IVP > 50 means market already stressed — condor too likely to be breached
        if iv.iv_percentile > 50:
            return _reduce_wait(
                f"NORMAL + IV HIGH + NEUTRAL but IVP={iv.iv_percentile:.0f} > 50 — tail risk too elevated for Iron Condor",
                vix, iv, trend, macro_warn,
            )
        action = get_position_action(
            StrategyName.IRON_CONDOR.value,
            is_wait=False,
            strategy_key=catalog_strategy_key(StrategyName.IRON_CONDOR.value),
        )
        return _build_recommendation(
            StrategyName.IRON_CONDOR,
            vix=vix,
            iv=iv,
            trend=trend,
            legs=[
                Leg("SELL", "CALL", 45, 0.16, "Upper short wing"),
                Leg("BUY",  "CALL", 45, 0.08, "Upper long wing"),
                Leg("SELL", "PUT",  45, 0.16, "Lower short wing"),
                Leg("BUY",  "PUT",  45, 0.08, "Lower long wing"),
            ],
            size_rule=_size_rule(vix, iv_s, t),
            rationale="NORMAL + IV HIGH + NEUTRAL — rich premium + no directional edge: Iron Condor",
            position_action=action,
            macro_warning=macro_warn,
        )

    if iv_s == IVSignal.LOW:
        if t == TrendSignal.BULLISH:
            return _reduce_wait(
                "NORMAL + IV LOW + BULLISH — thin premium (IVP<40) makes Diagonal risk/reward unfavourable; wait for IV to expand",
                vix, iv, trend, macro_warn,
            )

        if t == TrendSignal.BEARISH:
            return _reduce_wait(
                "NORMAL + IV LOW + BEARISH — low premium insufficient for IC; skip",
                vix, iv, trend, macro_warn,
            )

        # NEUTRAL + LOW IV → no edge in any direction, not worth selling premium either
        return _reduce_wait(
            "NORMAL + IV LOW + NEUTRAL — no directional edge and premium cheap; skip",
            vix, iv, trend, macro_warn,
        )

    # iv_s == NEUTRAL, regime == NORMAL
    if t == TrendSignal.BULLISH:
        # Backwardation filter for Bull Put Spread
        if vix.backwardation:
            return _reduce_wait(
                "NORMAL + IV NEUTRAL + BULLISH but VIX term structure in BACKWARDATION — skip Bull Put Spread",
                vix, iv, trend, macro_warn, backwardation=True,
            )
        # P1: VIX momentum rising → conditions deteriorating, skip selling puts
        if vix.trend == Trend.RISING:
            return _reduce_wait(
                "NORMAL + IV NEUTRAL + BULLISH but VIX RISING — wait for VIX to stabilise before selling premium",
                vix, iv, trend, macro_warn,
            )
        # P1: IVP ≥ 50 — stressed vol; tail risk exceeds premium benefit
        if iv.iv_percentile >= 50:
            return _reduce_wait(
                f"NORMAL + IV NEUTRAL + BULLISH but IVP={iv.iv_percentile:.0f} ≥ 50 — stressed vol environment, BPS tail risk too high",
                vix, iv, trend, macro_warn,
            )
        # P2: IVP < 43 — insufficient premium for BPS risk/reward
        # Analysis (2026-03-28): borderline entry at IVP=43 caused 2025-10-03 loss.
        # Raise minimum from 40→43 to filter marginal premium environments.
        if iv.iv_percentile < 43:
            return _reduce_wait(
                f"NORMAL + IV NEUTRAL + BULLISH but IVP={iv.iv_percentile:.0f} < 43 — insufficient premium for BPS risk/reward",
                vix, iv, trend, macro_warn,
            )
        action = get_position_action(
            StrategyName.BULL_PUT_SPREAD.value,
            is_wait=False,
            strategy_key=catalog_strategy_key(StrategyName.BULL_PUT_SPREAD.value),
        )
        return _build_recommendation(
            StrategyName.BULL_PUT_SPREAD,
            vix=vix,
            iv=iv,
            trend=trend,
            legs=[
                Leg("SELL", "PUT", 30, 0.30, "Short put — OTM, collects premium"),
                Leg("BUY",  "PUT", 30, 0.15, "Long put  — further OTM, caps downside"),
            ],
            size_rule=_size_rule(vix, iv_s, t),
            rationale="NORMAL + IV NEUTRAL + BULLISH — uptrend with moderate premium: Bull Put Spread",
            position_action=action,
            macro_warning=macro_warn,
        )

    if t == TrendSignal.BEARISH:
        if vix.trend == Trend.RISING:
            return _reduce_wait(
                "NORMAL + IV NEUTRAL + BEARISH + VIX RISING — skip Iron Condor while vol escalating",
                vix, iv, trend, macro_warn,
            )
        if iv.iv_percentile < 20 or iv.iv_percentile > 50:
            return _reduce_wait(
                f"NORMAL + IV NEUTRAL + BEARISH but IVP={iv.iv_percentile:.0f} outside 20–50 — IC risk/reward unfavourable",
                vix, iv, trend, macro_warn,
            )
        action = get_position_action(
            StrategyName.IRON_CONDOR.value,
            is_wait=False,
            strategy_key=catalog_strategy_key(StrategyName.IRON_CONDOR.value),
        )
        return _build_recommendation(
            StrategyName.IRON_CONDOR,
            vix=vix,
            iv=iv,
            trend=trend,
            legs=[
                Leg("SELL", "CALL", 45, 0.16, "Upper short wing — BEARISH trend adds call-side safety"),
                Leg("BUY",  "CALL", 45, 0.08, "Upper long wing"),
                Leg("SELL", "PUT",  45, 0.16, "Lower short wing — δ0.16 OTM after confirmed downtrend"),
                Leg("BUY",  "PUT",  45, 0.08, "Lower long wing"),
            ],
            size_rule=_size_rule(vix, iv_s, t),
            rationale=(
                "NORMAL + IV NEUTRAL + BEARISH + VIX stable — MA50 lag means downtrend confirmed; "
                "IC collects from both sides without directional bet"
            ),
            position_action=action,
            macro_warning=macro_warn,
        )

    # NORMAL + NEUTRAL IV + NEUTRAL trend → Iron Condor (no directional bias, neutral vol)
    # P3: skip if VIX rising — range assumption breaking down
    if vix.trend == Trend.RISING:
        return _reduce_wait(
            "NORMAL + IV NEUTRAL + NEUTRAL but VIX RISING — Iron Condor unsafe; wait for vol to stabilise",
            vix, iv, trend, macro_warn,
        )
    # P3: IVP outside 20–50 — too low = free money illusion; too high = breached too often
    if iv.iv_percentile < 20 or iv.iv_percentile > 50:
        return _reduce_wait(
            f"NORMAL + IV NEUTRAL + NEUTRAL but IVP={iv.iv_percentile:.0f} outside 20–50 — Iron Condor risk/reward unfavourable",
            vix, iv, trend, macro_warn,
        )
    action = get_position_action(
        StrategyName.IRON_CONDOR.value,
        is_wait=False,
        strategy_key=catalog_strategy_key(StrategyName.IRON_CONDOR.value),
    )
    return _build_recommendation(
        StrategyName.IRON_CONDOR,
        vix=vix,
        iv=iv,
        trend=trend,
        legs=[
            Leg("SELL", "CALL", 45, 0.16, "Upper short wing"),
            Leg("BUY",  "CALL", 45, 0.08, "Upper long wing"),
            Leg("SELL", "PUT",  45, 0.16, "Lower short wing"),
            Leg("BUY",  "PUT",  45, 0.08, "Lower long wing"),
        ],
        size_rule=_size_rule(vix, iv_s, t),
        rationale="NORMAL + IV NEUTRAL + NEUTRAL — no directional edge: Iron Condor is the default",
        position_action=action,
        macro_warning=macro_warn,
    )


def get_recommendation(
    vix_df=None,
    spx_df=None,
    use_intraday: bool = False,
) -> Recommendation:
    """
    Fetch all signals and return today's recommendation.

    Args:
        vix_df:       Optional pre-fetched EOD VIX DataFrame (2y). Fetched if None.
        spx_df:       Optional pre-fetched EOD SPX DataFrame (2y). Fetched if None.
        use_intraday: When True, fetches a 5m bar for current VIX level and current
                      SPX price, passing them as overrides to the snapshot functions.
                      All historical baselines (IVR 252-day window, MA50, VIX3M) remain
                      EOD-based regardless of this flag.
    """
    vix_data = fetch_vix_history(period="2y") if vix_df is None else vix_df
    spx_data = fetch_spx_history(period="2y") if spx_df is None else spx_df

    current_vix: Optional[float] = None
    current_spx: Optional[float] = None

    if use_intraday:
        try:
            vix_5m = fetch_vix_history(period="1d", interval="5m")
            current_vix = float(vix_5m["vix"].iloc[-1])
        except Exception:
            pass  # Fall back to EOD close silently

        try:
            spx_5m = fetch_spx_history(period="1d", interval="5m")
            current_spx = float(spx_5m["close"].iloc[-1])
        except Exception:
            pass  # Fall back to EOD close silently

    vix_snap   = get_current_snapshot(vix_data, current_vix=current_vix)
    iv_snap    = get_current_iv_snapshot(vix_data, current_vix=current_vix)
    trend_snap = get_current_trend(spx_data, current_spx=current_spx)

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
        print(f"→  Action: {rec.position_action}")
        print("   Verify strikes on your broker platform,")
        print("   then execute manually per the size rule above.\n")
        print("   After executing, run /entered in Telegram to record the position.")
