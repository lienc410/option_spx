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
  Credit positions: close at 60% profit (after min 10 days held) OR at 21 DTE  [SPEC-077]
  Debit positions:  close at 50% profit or 50% loss; close before 7 DTE
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from strategy.catalog import strategy_descriptor, strategy_key as catalog_strategy_key
from strategy import decision_trace as T

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
    profit_target:      float = 0.60   # close at this fraction of max credit (SPEC-077)
    stop_mult:          float = 2.0    # stop loss at N× credit received
    min_hold_days:      int   = 10     # minimum days before profit target can trigger

    # BP utilization target per regime (fraction of account_size per trade)
    # Used by backtest engine to size contracts; supersedes risk_pct + size_mult sizing.
    # Calibrated to tastytrade retail PM standard: single position ≤ 5–7% of account.
    bp_target_low_vol:  float = 0.15   # LOW_VOL:  15% — Q045 J3 joint optimum (SPEC-084)
    bp_target_normal:   float = 0.15   # NORMAL:   15% — Q045 J3 joint optimum (SPEC-084)
    bp_target_high_vol: float = 0.14   # HIGH_VOL: 14% — Q045 J3 joint optimum (SPEC-084)
    # SPEC-111 (2026-06-01): BCD max debit per trade (USD). Reduces BCD sizing ~7%
    # so backtest median debit $23,864 → ≤$22,000, complying with 60%-of-cash cap.
    # Applied in backtest engine when sizing BCD positions. In production, the
    # cash_budget_governance.py hard cap enforces this dynamically against live cash.
    # Q096 (2026-07-12): engine-canonical sizing semantic, NOT a live directive.
    # One SPX BCD contract costs $38-41k at 2025-26 spot (> this cap) — engine
    # sizes ~0.6 fractional contracts while live's integer floor is 1 contract
    # (≈1.7× engine per-trade risk). Quote engine BCD per-trade figures with the
    # "(engine ~0.6ct)" lens. Do NOT raise to chase integer parity: the binding
    # constraint is bp_target (4.5%×$500k≈$22.5k, near-coincident), and
    # re-sizing would invalidate 26y of BCD backtest conclusions.
    bcd_max_debit_usd: float = 22_000.0

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
    # SPEC-100 (2026-05-13): Raised from 2 to 3 per Q064 P8 evidence:
    # +4 incremental trades over 19y, all winners, avg $1,356; total +$5,424;
    # worst trade unchanged at -$2,016. Spell-internal trade #1 vs #2 (baseline
    # data) showed no quality degradation, supporting that #3 should also hold.
    # P9 (2026-05-13) confirmed other spell reset params (hysteresis, high_reset,
    # age_cap) are deliberate design — do NOT change them without similar
    # Quant-grade evidence.
    max_trades_per_spell: int = 3

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
    # Research mode: bypass IVP entry gates for full-history matrix analysis.
    # NEVER set to True in production. See SPEC-056.
    disable_entry_gates: bool = False
    # Research mode: force a specific strategy regardless of signal routing.
    # When set, select_strategy() returns a recommendation for this strategy
    # using its standard legs, bypassing all regime/IV/trend routing logic.
    # NEVER set in production.
    force_strategy: str | None = None
    # BCD comfortable-top filter (SPEC-079)
    # SPEC-124 (Q088 T1, PM 2026-07-06): SPEC-079 comfort filter RETIRED.
    # shadow → disabled is zero-behavior-change (shadow never blocked; A4 found
    # zero detectable protective value, T1 concurred). Flipping the default
    # also stops backtests from spraying data/bcd_filter_shadow.jsonl (74MB of
    # 26y-replay pollution, archived 2026-07-06). Research can still opt in
    # explicitly via params.
    bcd_comfort_filter_mode: str = "disabled"   # "disabled" | "shadow" | "active"
    # BCD debit stop tightening (SPEC-080)
    bcd_stop_tightening_mode: str = "shadow"   # "disabled" | "shadow" | "active"
    # Overlay-F account-level IC_HV size-up (SPEC-075/076)
    overlay_f_mode: str = "shadow"  # "disabled" | "shadow" | "active"

    # Q068 Phase 7 regime stops (research mode — defaults disabled)
    # NEVER enable in production without separate SPEC approval.
    regime_stop_vix_rise:        float = 0.0    # e.g., 0.20 = exit if vix > entry_vix × 1.20
    regime_stop_below_ma10:      bool  = False  # exit if SPX_close < SPX_10dMA
    regime_stop_min_hold_days:   int   = 1      # min days before regime stops can trigger
    regime_stop_bps_only:        bool  = True   # only apply to BPS strategies (not BCD/IC)

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

# SPEC-113: NORMAL × IV_LOW × BULLISH carve-in
# VIX < 18 → BCD; VIX >= 18 → reduce_wait
# Threshold from Q083 P13 +8vp short-leg skew sensitivity: [18,20) sub-cells become weak under pessimistic skew
SPEC_113_VIX_THRESHOLD = 18.0

# IVP multi-horizon thresholds (SPEC-048~055)
REGIME_DECAY_IVP63_MAX   = 50
REGIME_DECAY_IVP252_MIN  = 50
LOCAL_SPIKE_IVP63_MIN    = 50
LOCAL_SPIKE_IVP252_MAX   = 50
IVP63_BCS_BLOCK          = 70
# DIAGONAL_IVP252_GATE_LO/HI removed — Gate 1 (SPEC-049) rescinded 2026-04-15
# BPS NORMAL+NEUTRAL+BULLISH gate: IVP upper cap (monkey-patchable for sensitivity research)
# Raised 50→55: Q015 OOS validation passed (Sharpe non-degrading in IS/OOS, Pareto improvement).
#
# BPS_NNB_IVP_UPPER = 55 is an empirical low-vol repricing filter, not a
# precise volatility cliff. Q063 confirmed that relaxing this gate re-admits
# negative-alpha BPS NNB entries, including recent 2024-2026 counterfactual
# losers (-$13.7k over 5 blocked entries). Q067 confirmed rank-jump / threshold
# jitter (7.37% historical / 11.5% recent daily flip rate; 61% reverse within
# 5 TD; 15% 126d-vs-252d window disagreement), but hysteresis / multi-horizon /
# cross-window variants all failed. Q068 MA-timing overrides and regime stops
# failed robustness / worst-trade tests (P6 variants worst -$15k vs baseline
# -$9k). Q069 smoothed (SMA/EWM) and slope-aware IVP variants also failed —
# smoothing introduces lag; slope-aware re-admits known 2026-02-25 bad trade.
# Mechanism: low VIX absolute level ≠ low IVP relative position. VIX 15-17 +
# IVP 60-65 can be "complacency before mean reversion," not safe premium-selling.
# Keep hard IVP_252 >= 55 block unless a future non-threshold framework
# (probabilistic / Bayesian / cross-asset) is explicitly approved.
# See task/q063_q067_q068_q069_closure_2nd_quant_review_2026-05-13.md
BPS_NNB_IVP_UPPER        = 55
BPS_NNB_IVP_LOWER        = 43

AFTERMATH_PEAK_VIX_10D_MIN = 28.0
AFTERMATH_LOOKBACK_DAYS = 10
AFTERMATH_OFF_PEAK_PCT = 0.10
IC_HV_MAX_CONCURRENT = 2


class StrategyName(str, Enum):
    ES_SHORT_PUT        = "ES Short Put"
    BULL_PUT_SPREAD     = "Bull Put Spread"
    BULL_PUT_SPREAD_HV  = "Bull Put Spread (High Vol)"  # HIGH_VOL regime variant
    BEAR_CALL_SPREAD_HV = "Bear Call Spread (High Vol)"
    BULL_CALL_DIAGONAL  = "Bull Call Diagonal"
    BEAR_CALL_DIAGONAL  = "Bear Call Diagonal"   # DEPRECATED (SPEC-073) — selector never returns this; retained for prototype script string-compat
    IRON_CONDOR         = "Iron Condor"
    IRON_CONDOR_HV      = "Iron Condor (High Vol)"
    BULL_CALL_SPREAD    = "Bull Call Spread"
    BEAR_CALL_SPREAD    = "Bear Call Spread"
    BEAR_PUT_SPREAD     = "Bear Put Spread"
    REDUCE_WAIT         = "Reduce / Wait"


# SPEC-106 §2.2 + §3.2 — payoff-type taxonomy. Pure mapping; does NOT influence
# select_strategy decisions. Used by the /api/strategy-matrix surface and the
# UI helper text so PM sees that "low IV under LOW_VOL = debit buy" vs "low IV
# under NORMAL = credit premium too thin" are semantically opposite regimes.
def get_payoff_type(strategy_name: str | None) -> str:
    """Map a strategy display-name → payoff taxonomy bucket.

    Buckets:
      CREDIT          — net-credit short-premium (BPS / IC / BCS_HV) — needs IV
      DEBIT           — net-debit long-vol structure (BCD / Calendar) — wants cheap options
      NEUTRAL_PREMIUM — mixed / unmapped (default fallback)
      WAIT            — REDUCE_WAIT (no statistical edge in this cell)
      RESEARCH_ONLY   — Stress Put Ladder / paper-only (0% production cap)
    """
    if strategy_name is None:
        return "WAIT"
    name = str(strategy_name).strip()
    if name in {"Reduce / Wait", "REDUCE_WAIT"}:
        return "WAIT"
    if name in {
        "Bull Put Spread", "Bull Put Spread (High Vol)",
        "Iron Condor", "Iron Condor (High Vol)",
        "Bear Call Spread (High Vol)", "Bear Call Spread",
        "ES Short Put",
    }:
        return "CREDIT"
    if name in {"Bull Call Diagonal", "Bear Call Diagonal", "Calendar", "Diagonal"}:
        return "DEBIT"
    if name in {"Stress Put Ladder", "HV Ladder"}:
        return "RESEARCH_ONLY"
    return "NEUTRAL_PREMIUM"


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
    canonical_strategy: str = ""
    re_enable_hint: str = ""
    overlay_mode: str = "disabled"
    overlay_f_would_fire: bool = False
    overlay_f_factor: float = 1.0
    overlay_f_rationale: str = ""
    overlay_f_idle_bp_pct: float | None = None
    overlay_f_sg_count: int | None = None
    overlay_f_fail_closed: bool = False
    shock_mode: str = "disabled"
    local_spike: bool = False
    # SPEC-106 — payoff taxonomy (CREDIT / DEBIT / WAIT / NEUTRAL_PREMIUM /
    # RESEARCH_ONLY). Auto-populated by _build_recommendation / _reduce_wait.
    payoff_type: str = ""
    # SPEC-135 — Decision Trace：本次评估走过的全部节点（数据层/格路由/
    # 门链含静默通过/治理/最终输出），由 decision_trace 收集器自吐。
    # 纯附加字段：不参与任何路由决策（AC：注入前后路由 bit-identical）。
    trace: list = field(default_factory=list, repr=False)
    # SPEC-143 — Q101 aftermath 首笔 0.5× staging（live 推荐层 only）。
    # 只由 _apply_aftermath_staging_live（get_recommendation 内）写入；
    # select_strategy 本体永不触碰 → 回测路径恒为 None（回测隔离 AC-4）。
    aftermath_staging: dict | None = None

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


def is_aftermath(vix: VixSnapshot, params: "StrategyParams | None" = None) -> bool:
    """
    HIGH_VOL aftermath window:
    - trailing 10-day peak VIX >= 28
    - current VIX at least 10% off that peak (AFTERMATH_OFF_PEAK_PCT;
      0.05 → 0.10 per Q018 Variant B, R-20260419 line — MaxDD -36%)
    - current VIX remains below the EXTREME_VOL boundary (params.extreme_vix)

    SPEC-118.1: the EXTREME guard previously hardcoded 40.0 while the selector's
    actual EXTREME boundary is params.extreme_vix (35.0) — two divergent
    boundaries. Unified to the single source. Decision-path behavior is
    bit-identical (selector only calls this inside the HIGH_VOL branch, which
    already requires vix < extreme_vix, so the guard never bound there). The
    only visible change is the /api/aftermath display endpoint: for
    VIX ∈ [35, 40) it now reports inactive, matching what the selector
    actually does.
    """
    peak = vix.vix_peak_10d
    if peak is None:
        return False
    if peak < AFTERMATH_PEAK_VIX_10D_MIN:
        return False
    extreme = (params or DEFAULT_PARAMS).extreme_vix
    if vix.vix >= extreme:
        return False
    return vix.vix <= peak * (1.0 - AFTERMATH_OFF_PEAK_PCT)


def _size_rule(vix: VixSnapshot, iv_s: IVSignal, t: TrendSignal) -> str:
    """
    Two-tier sizing:
      Full  — IV favors selling (HIGH/NEUTRAL) AND VIX trend flat/falling
      Half  — VIX trend rising OR signals mixed
    """
    vix_rising = (vix.trend == Trend.RISING)
    signals_favor_sell = iv_s in (IVSignal.HIGH, IVSignal.NEUTRAL)

    if not vix_rising and signals_favor_sell:
        return "Full size — risk ≤ 4.5% of account (signals agree + VIX flat/falling)"
    return "Half size — risk ≤ 2.25% of account (VIX rising or signals mixed)"


def _compute_size_tier(
    strategy_key: str,
    iv: IVSnapshot,
    vix: VixSnapshot,
    iv_s: IVSignal,
    t: TrendSignal,
) -> str:
    """
    Two-tier sizing with regime decay and local spike overrides for DIAGONAL only (SPEC-053/055b).
    """
    if iv.regime_decay and strategy_key == StrategyName.BULL_CALL_DIAGONAL.value:
        return "Full size — regime decay: vol cooling from elevated base (SPEC-053)"
    local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)
    if local_spike and strategy_key == StrategyName.BULL_CALL_DIAGONAL.value:
        return "Full size — local spike: near-term vol elevated above calm long-term base (SPEC-055b)"
    return _size_rule(vix, iv_s, t)


def _build_recommendation(
    strategy: StrategyName,
    *,
    params: StrategyParams = DEFAULT_PARAMS,
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
    canonical_strategy: str = "",
    re_enable_hint: str = "",
    local_spike: bool = False,
) -> Recommendation:
    desc = strategy_descriptor(strategy.value)
    # SPEC-135 — 最终输出节点 + 把本轮 trace 附到 rec（drain 清空收集器，
    # 纯附加：不影响任何字段/路由）
    if strategy == StrategyName.REDUCE_WAIT:
        # SPEC-135.4：词表合规——状态词用 NO ENTRY（DESIGN.md 词表；WAIT/观望
        # 不在词表），叙事行"今日结论：不开新仓"
        T.add("output", "final_verdict", "今日结论：不开新仓",
              detail=rationale, outcome="wait", code_ref="selector._reduce_wait",
              kind="final", stage="final")
    else:
        T.add("output", "final_verdict",
              f"今日结论：开仓候选 — {strategy.value}（动作 {position_action}）",
              detail=rationale, outcome="accept",
              code_ref="selector._build_recommendation", kind="final", stage="final")
    _trace_nodes = T.drain()
    return Recommendation(
        trace           = _trace_nodes,
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
        canonical_strategy = canonical_strategy or strategy.value,
        re_enable_hint = re_enable_hint,
        overlay_mode = params.overlay_mode,
        overlay_f_would_fire = False,
        overlay_f_factor = 1.0,
        overlay_f_rationale = "",
        overlay_f_idle_bp_pct = None,
        overlay_f_sg_count = None,
        overlay_f_fail_closed = False,
        shock_mode = params.shock_mode,
        local_spike = local_spike,
        payoff_type = get_payoff_type(strategy.value),
    )


def _apply_overlay_f_decision(rec: Recommendation, decision) -> Recommendation:
    rec.overlay_f_would_fire = bool(decision.would_fire)
    rec.overlay_f_factor = float(decision.effective_factor)
    rec.overlay_f_rationale = str(decision.rationale or "")
    rec.overlay_f_idle_bp_pct = decision.idle_bp_pct
    rec.overlay_f_sg_count = decision.sg_count
    rec.overlay_f_fail_closed = bool(decision.fail_closed)
    return rec


def _eval_overlay_f_live(rec: Recommendation, params: StrategyParams) -> Recommendation:
    if params.overlay_f_mode == "disabled":
        return rec
    from strategy.overlay import (
        append_overlay_f_log,
        build_live_portfolio_state,
        evaluate_overlay_f,
    )

    state = build_live_portfolio_state()
    decision = evaluate_overlay_f(
        mode=params.overlay_f_mode,
        strategy_key=rec.strategy_key,
        vix=rec.vix_snapshot.vix,
        portfolio_state=state,
    )
    append_overlay_f_log(
        date=rec.vix_snapshot.date,
        strategy=rec.strategy_key,
        vix=rec.vix_snapshot.vix,
        decision=decision,
    )
    return _apply_overlay_f_decision(rec, decision)


def _build_forced_recommendation(
    strategy_key: str,
    vix: VixSnapshot,
    iv: IVSnapshot,
    trend: TrendSnapshot,
    params: StrategyParams,
) -> Recommendation:
    """
    Build a valid Recommendation for the specified strategy using its standard legs,
    regardless of current regime/IV/trend. Used only for matrix audit research (SPEC-057).
    """
    _FORCED_LEGS: dict[str, list[Leg]] = {
        "es_short_put": [
            Leg("SELL", "PUT", 45, 0.20, "Short put — minimal /ES production cell"),
        ],
        "bull_call_diagonal": [
            Leg("BUY", "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
            Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
        ],
        "iron_condor": [
            Leg("SELL", "CALL", 45, 0.16, "Short call wing"),
            Leg("BUY", "CALL", 45, 0.08, "Long call wing"),
            Leg("SELL", "PUT", 45, 0.16, "Short put wing"),
            Leg("BUY", "PUT", 45, 0.08, "Long put wing"),
        ],
        "bull_put_spread": [
            Leg("SELL", "PUT", 30, 0.30, "Short put"),
            Leg("BUY", "PUT", 30, 0.15, "Long put"),
        ],
        "bull_put_spread_hv": [
            Leg("SELL", "PUT", 35, 0.20, "Short put — HV params"),
            Leg("BUY", "PUT", 35, 0.10, "Long put — HV params"),
        ],
        "bear_call_spread_hv": [
            Leg("SELL", "CALL", 45, 0.20, "Short call — HV params"),
            Leg("BUY", "CALL", 45, 0.10, "Long call — HV params"),
        ],
        "iron_condor_hv": [
            Leg("SELL", "CALL", 45, 0.16, "Short call wing — HV"),
            Leg("BUY", "CALL", 45, 0.08, "Long call wing — HV"),
            Leg("SELL", "PUT", 45, 0.16, "Short put wing — HV"),
            Leg("BUY", "PUT", 45, 0.08, "Long put wing — HV"),
        ],
    }
    legs = _FORCED_LEGS.get(strategy_key)
    if legs is None:
        raise ValueError(f"_build_forced_recommendation: unknown strategy_key {strategy_key!r}")

    forced_map: dict[str, StrategyName] = {
        "es_short_put": StrategyName.ES_SHORT_PUT,
        "bull_call_diagonal": StrategyName.BULL_CALL_DIAGONAL,
        "iron_condor": StrategyName.IRON_CONDOR,
        "bull_put_spread": StrategyName.BULL_PUT_SPREAD,
        "bull_put_spread_hv": StrategyName.BULL_PUT_SPREAD_HV,
        "bear_call_spread_hv": StrategyName.BEAR_CALL_SPREAD_HV,
        "iron_condor_hv": StrategyName.IRON_CONDOR_HV,
    }
    strategy_enum = forced_map.get(strategy_key)
    if strategy_enum is None:
        raise ValueError(f"_build_forced_recommendation: cannot map {strategy_key!r} to StrategyName")

    t = trend.signal
    iv_s = _effective_iv_signal(iv)
    size = _compute_size_tier(strategy_key, iv, vix, iv_s, t)
    local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)
    action = get_position_action(
        strategy_enum.value,
        is_wait=False,
        strategy_key=strategy_key,
    )

    return _build_recommendation(
        strategy_enum,
        params=params,
        vix=vix,
        iv=iv,
        trend=trend,
        legs=legs,
        size_rule=size,
        rationale=f"[FORCED] matrix audit — standard {strategy_key} legs",
        position_action=action,
        local_spike=local_spike,
    )


def _guardrail_label(reason: str, backwardation: bool = False) -> str:
    text = reason.upper()
    if "EXTREME_VOL" in text or "TAIL RISK TOO ELEVATED" in text:
        return "EXTREME VOL"
    if backwardation or "BACKWARDATION" in text:
        return "BACKWARDATION"
    if "VIX RISING" in text:
        return "VIX RISING"
    if re.search(r'\bIVP', text):
        # Extract the specific condition from the reason string (between "but " and "—")
        m = re.search(r'but\s+([^—;(]+)', reason, re.IGNORECASE)
        if m:
            cond = m.group(1).strip().replace(">=", "≥").replace("<=", "≤")
            return f"IVP FILTER — {cond}"
        return "IVP FILTER"
    if "LOW_VOL + BEARISH" in text:
        return "NO EDGE"
    if "PREMIUM" in text and "UNFAVOURABLE" in text:
        return "PREMIUM FILTER"
    return "GUARDRAIL"


def _re_enable_hint(label: str, params: StrategyParams = DEFAULT_PARAMS) -> str:
    if label == "EXTREME VOL":
        return f"VIX below {params.extreme_vix:.0f}"
    if label == "BACKWARDATION":
        return "VIX spot falls below VIX3M (contango restored)"
    if label == "VIX RISING":
        return "VIX trend turns FLAT or FALLING"
    if label == "MACRO DOWNTREND":
        return "SPX recovers above 200MA"
    if label.startswith("IVP FILTER"):
        detail = label[len("IVP FILTER"):].lstrip(" —").strip()
        if not detail:
            return "IV percentile returns to the allowed band"
        metric_m = re.match(r'(\w+)\s*=', detail, re.IGNORECASE)
        metric = metric_m.group(1) if metric_m else "IVP"
        if re.search(r'[≥>]=?\s*\d+', detail):
            threshold = re.search(r'[≥>]=?\s*(\d+)', detail)
            return f"{metric} drops below {threshold.group(1)}" if threshold else "IV percentile drops"
        if re.search(r'<\s*\d+', detail):
            threshold = re.search(r'<\s*(\d+)', detail)
            return f"{metric} rises above {threshold.group(1)}" if threshold else "IV percentile rises"
        if re.search(r'outside\s*\d+', detail, re.IGNORECASE):
            band = re.search(r'outside\s*(\d+)[–\-](\d+)', detail, re.IGNORECASE)
            return f"IVP returns to the {band.group(1)}–{band.group(2)} range" if band else "IV percentile returns to the allowed band"
        if re.search(r'\bin\b.*\d+[–\-]\d+', detail, re.IGNORECASE):
            band = re.search(r'(\d+)[–\-](\d+)', detail)
            return f"{metric} moves outside the {band.group(1)}–{band.group(2)} range" if band else "IV percentile returns to the allowed band"
        return "IV percentile returns to the allowed band"
    if label == "PREMIUM FILTER":
        return "Premium widens back to an acceptable level"
    return "Conditions improve"


def _reduce_wait(reason: str, vix: VixSnapshot, iv: IVSnapshot, trend: TrendSnapshot,
                 macro_warn: bool, backwardation: bool = False,
                 canonical_strategy: str = "", params: StrategyParams = DEFAULT_PARAMS) -> Recommendation:
    """Helper: build a REDUCE_WAIT recommendation."""
    label = _guardrail_label(reason, backwardation)
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
        guardrail_label=label,
        canonical_strategy=canonical_strategy,
        re_enable_hint=_re_enable_hint(label, params),
        params=params,
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
    T.reset()   # SPEC-135: 每次评估自吐一份 trace（纯记录，不分支）
    if params.force_strategy:
        return _build_forced_recommendation(params.force_strategy, vix, iv, trend, params)

    r    = vix.regime
    iv_s = _effective_iv_signal(iv)
    t    = trend.signal
    macro_warn = not trend.above_200

    # ── SPEC-135 数据层（① 市场读数，全部带语义描述）────────────────────────
    T.add("data", "vix_regime", T.vix_phrase(vix.vix, T.ev(r)),
          detail=f"5日均 {vix.vix_5d_avg} vs 前5日 {vix.vix_5d_ago} → 动量 {T.ev(vix.trend)}",
          inputs={"vix": round(vix.vix, 2), "regime": T.ev(r), "vix_trend": T.ev(vix.trend)},
          code_ref="signals/vix_regime.py", stage="market_read")
    T.add("data", "iv_percentile", f"期权贵贱：{T.ivp_phrase(iv.iv_percentile)}",
          detail=f"IVR {iv.iv_rank:.0f} / IVP {iv.iv_percentile:.0f}"
                 + ("（两者分歧 >15，以 IVP 为准重分类）" if abs(iv.iv_rank - iv.iv_percentile) > 15 else ""),
          inputs={"iv_rank": round(iv.iv_rank, 1), "iv_percentile": round(iv.iv_percentile, 1),
                  "effective_signal": T.ev(iv_s)},
          code_ref="selector._effective_iv_signal", stage="market_read")
    T.add("data", "trend", T.trend_phrase(T.ev(t), trend.ma_gap_pct),
          detail=("价格在 200 日均线上方（宏观环境正常）" if trend.above_200
                  else "价格跌破 200 日均线（宏观逆风警示）"),
          inputs={"signal": T.ev(t), "ma_gap_pct": round(trend.ma_gap_pct, 4),
                  "above_200": trend.above_200},
          code_ref="signals/trend.py", stage="market_read")
    T.add("data", "term_structure",
          "VIX 期限结构：" + ("倒挂（近月恐慌高于远月 — 短期极度紧张）" if vix.backwardation
                             else "正常 contango（近月低于远月）"),
          detail=f"VIX {vix.vix:.1f} vs VIX3M {vix.vix3m if vix.vix3m is not None else '—'}",
          inputs={"backwardation": vix.backwardation, "vix3m": vix.vix3m},
          code_ref="signals/vix_regime.py", stage="market_read")

    # ── EXTREME_VOL: VIX above extreme threshold → always wait ───────
    _extreme = (r == Regime.HIGH_VOL and vix.vix >= params.extreme_vix)
    if not T.gate(not _extreme, "extreme_vol",
                  f"极端波动刹车：恐慌指数是否失控（≥{params.extreme_vix:.0f} 一律持币）",
                  detail=f"VIX {vix.vix:.1f} vs 极端线 {params.extreme_vix:.0f}",
                  inputs={"vix": round(vix.vix, 2), "extreme_vix": params.extreme_vix},
                  code_ref="selector EXTREME_VOL"):
        return _reduce_wait(
            f"EXTREME_VOL (VIX ≥ {params.extreme_vix:.0f}) — tail risk too elevated; hold cash",
            vix, iv, trend, macro_warn,
            canonical_strategy=(
                StrategyName.BEAR_CALL_SPREAD_HV.value if t == TrendSignal.BEARISH
                else StrategyName.IRON_CONDOR_HV.value if t == TrendSignal.NEUTRAL
                else StrategyName.BULL_PUT_SPREAD_HV.value
            ),
            params=params,
        )

    # ── HIGH_VOL: trade with tighter params ──────────────────────────
    if r == Regime.HIGH_VOL:
        T.add("cell", "route_high_vol",
              f"查策略手册：高波动区 × {T.trend_phrase(T.ev(t), trend.ma_gap_pct)}"
              "（高波动格用收紧参数：更小 delta、更小仓位）",
              inputs={"regime": T.ev(r), "trend": T.ev(t), "iv_signal": T.ev(iv_s)},
              outcome="route", code_ref="selector HIGH_VOL matrix", stage="routing")
        if t == TrendSignal.BEARISH:
            _aftermath_ok = (iv_s == IVSignal.HIGH and is_aftermath(vix))
            T.add("gate", "hv_bearish_aftermath",
                  "余波特批通道：恐慌刚从峰值明显回落时，可绕过常规门做双侧收权利金"
                  "（broken-wing Iron Condor）",
                  detail=(f"10日VIX峰值 {vix.vix_peak_10d or vix.vix:.1f} → 现在 {vix.vix:.1f}"
                          + ("，满足余波条件" if _aftermath_ok else "，不满足（走常规门链）")),
                  inputs={"iv_signal": T.ev(iv_s), "vix_peak_10d": vix.vix_peak_10d},
                  outcome="pass" if _aftermath_ok else "info",
                  code_ref="SPEC-064 aftermath", stage="gates")
            if _aftermath_ok:
                peak = vix.vix_peak_10d or vix.vix
                drop_pct = max(0.0, (1.0 - (vix.vix / peak)) * 100.0) if peak else 0.0
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
                        Leg("SELL", "CALL", 45, 0.12,
                            "Upper short wing — aftermath (broken-wing V3-A)"),
                        Leg("BUY",  "CALL", 45, 0.04,
                            "Upper long wing — broken-wing tighter (V3-A)"),
                        Leg("SELL", "PUT",  45, 0.12,
                            "Lower short wing — aftermath (broken-wing V3-A)"),
                        Leg("BUY",  "PUT",  45, 0.08,
                            "Lower long wing — symmetric (V3-A)"),
                    ],
                    size_rule=(
                        f"{int(params.high_vol_size*100)}% size — risk ≤ "
                        f"{1.5*params.high_vol_size:.1f}% of account "
                        f"(HIGH_VOL, reduced exposure)"
                    ),
                    rationale=(
                        f"HIGH_VOL + BEARISH + IV HIGH + aftermath (VIX peak={peak:.1f} → now={vix.vix:.1f}, "
                        f"-{drop_pct:.1f}% off peak) — bypass VIX_RISING / ivp63 gates per SPEC-064"
                    ),
                    position_action=action,
                    macro_warning=macro_warn,
                )
            _rising = (vix.trend == Trend.RISING)
            if not T.gate(not _rising, "hv_bearish_vix_rising",
                          "恐慌还在升级吗？升级中不卖 call，等它稳住",
                          detail=f"VIX 动量 {T.ev(vix.trend)}（5日均 {vix.vix_5d_avg} vs 前5日 {vix.vix_5d_ago}）",
                          inputs={"vix_trend": T.ev(vix.trend)},
                          code_ref="selector HIGH_VOL·BEARISH P1"):
                return _reduce_wait(
                    "HIGH_VOL + BEARISH + VIX RISING — panic escalating; wait for VIX to stabilise before selling calls",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BEAR_CALL_SPREAD_HV.value,
                    params=params,
                )
            _ivp63_hot = (not params.disable_entry_gates and iv.ivp63 >= IVP63_BCS_BLOCK)
            if not T.gate(not _ivp63_hot, "hv_bearish_ivp63",
                          "恐慌是否处于近 3 个月最高位？是则均值回归风险太大，不卖 call spread",
                          detail=f"63日 IV 分位 {iv.ivp63:.0f} vs 拦截线 {IVP63_BCS_BLOCK}",
                          inputs={"ivp63": round(iv.ivp63, 1), "block": IVP63_BCS_BLOCK},
                          code_ref="selector IVP63_BCS_BLOCK"):
                return _reduce_wait(
                    f"HIGH_VOL + BEARISH but ivp63={iv.ivp63:.0f} >= {IVP63_BCS_BLOCK} — "
                    "VIX at 63-day high; mean reversion risk too elevated for BCS_HV short call",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BEAR_CALL_SPREAD_HV.value,
                    params=params,
                )
            # SPEC-060: HIGH_VOL + BEARISH + IV=HIGH → IC_HV
            # Bootstrap matrix: IC_HV $937 ✓ vs BCS_HV $465 ✓ (n=33 vs n=50);
            # double-sided premium dominates single-direction call spread in HIGH_IV stress.
            if iv_s == IVSignal.HIGH:
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
                            "Upper short wing — rich HIGH_VOL call premium"),
                        Leg("BUY",  "CALL", 45, 0.08,
                            "Upper long wing"),
                        Leg("SELL", "PUT",  45, 0.16,
                            "Lower short wing — rich HIGH_VOL put premium"),
                        Leg("BUY",  "PUT",  45, 0.08,
                            "Lower long wing"),
                    ],
                    size_rule=(
                        f"{int(params.high_vol_size*100)}% size — risk ≤ "
                        f"{1.5*params.high_vol_size:.1f}% of account "
                        f"(HIGH_VOL, reduced exposure)"
                    ),
                    rationale=(
                        "HIGH_VOL + BEARISH + IV HIGH + VIX stable — double-sided premium "
                        "captures vol risk premium; IC_HV outperforms BCS_HV in this cell (SPEC-060)"
                    ),
                    position_action=action,
                    macro_warning=macro_warn,
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
            _aftermath_ok = (iv_s == IVSignal.HIGH and is_aftermath(vix))
            T.add("gate", "hv_neutral_aftermath",
                  "余波特批通道：恐慌刚从峰值明显回落时的双侧收权利金特批",
                  detail=(f"10日VIX峰值 {vix.vix_peak_10d or vix.vix:.1f} → 现在 {vix.vix:.1f}"
                          + ("，满足" if _aftermath_ok else "，不满足（走常规门链）")),
                  inputs={"iv_signal": T.ev(iv_s), "vix_peak_10d": vix.vix_peak_10d},
                  outcome="pass" if _aftermath_ok else "info", code_ref="SPEC-064 aftermath",
                  stage="gates")
            if _aftermath_ok:
                _bw = vix.backwardation
                if not T.gate(not _bw, "hv_neutral_aftermath_backwardation",
                              "近月恐慌是否高于远月（倒挂）？倒挂时短期 put 恐慌太热，不做 Iron Condor",
                              detail=f"VIX {vix.vix:.1f} vs VIX3M {vix.vix3m}",
                              inputs={"backwardation": _bw},
                              code_ref="selector HIGH_VOL·NEUTRAL aftermath"):
                    return _reduce_wait(
                        "HIGH_VOL + NEUTRAL + BACKWARDATION — near-term put panic elevated; skip IC HV",
                        vix, iv, trend, macro_warn, backwardation=True,
                        canonical_strategy=StrategyName.IRON_CONDOR_HV.value,
                        params=params,
                    )
                peak = vix.vix_peak_10d or vix.vix
                drop_pct = max(0.0, (1.0 - (vix.vix / peak)) * 100.0) if peak else 0.0
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
                        Leg("SELL", "CALL", 45, 0.12,
                            "Upper short wing — aftermath (broken-wing V3-A)"),
                        Leg("BUY",  "CALL", 45, 0.04,
                            "Upper long wing — broken-wing tighter (V3-A)"),
                        Leg("SELL", "PUT",  45, 0.12,
                            "Lower short wing — aftermath (broken-wing V3-A)"),
                        Leg("BUY",  "PUT",  45, 0.08,
                            "Lower long wing — symmetric (V3-A)"),
                    ],
                    size_rule=(
                        f"{int(params.high_vol_size*100)}% size — risk ≤ "
                        f"{1.5*params.high_vol_size:.1f}% of account "
                        f"(HIGH_VOL, reduced exposure)"
                    ),
                    rationale=(
                        f"HIGH_VOL + NEUTRAL + IV HIGH + aftermath (VIX peak={peak:.1f} → now={vix.vix:.1f}, "
                        f"-{drop_pct:.1f}% off peak) — bypass VIX_RISING / ivp63 gates per SPEC-064"
                    ),
                    position_action=action,
                    macro_warning=macro_warn,
                )
            _rising = (vix.trend == Trend.RISING)
            if not T.gate(not _rising, "hv_neutral_vix_rising",
                          "恐慌还在升级吗？升级中不做 Iron Condor",
                          detail=f"VIX 动量 {T.ev(vix.trend)}",
                          inputs={"vix_trend": T.ev(vix.trend)},
                          code_ref="selector HIGH_VOL·NEUTRAL"):
                return _reduce_wait(
                    "HIGH_VOL + NEUTRAL + VIX RISING — vol escalating; wait for VIX to stabilise",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.IRON_CONDOR_HV.value,
                    params=params,
                )
            _bw = vix.backwardation
            if not T.gate(not _bw, "hv_neutral_backwardation",
                          "近月恐慌是否高于远月（倒挂）？倒挂时不做 Iron Condor",
                          detail=f"VIX {vix.vix:.1f} vs VIX3M {vix.vix3m}",
                          inputs={"backwardation": _bw},
                          code_ref="selector HIGH_VOL·NEUTRAL"):
                return _reduce_wait(
                    "HIGH_VOL + NEUTRAL + BACKWARDATION — near-term put panic elevated; skip IC HV",
                    vix, iv, trend, macro_warn, backwardation=True,
                    canonical_strategy=StrategyName.IRON_CONDOR_HV.value,
                    params=params,
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

        _bw = vix.backwardation
        if not T.gate(not _bw, "hv_bullish_backwardation",
                      "近月恐慌是否高于远月（倒挂）？倒挂时不卖 put spread",
                      detail=f"VIX {vix.vix:.1f} vs VIX3M {vix.vix3m}",
                      inputs={"backwardation": _bw},
                      code_ref="selector HIGH_VOL·BULLISH"):
            return _reduce_wait(
                "HIGH_VOL + BACKWARDATION — VIX term structure inverted; skip Bull Put Spread",
                vix, iv, trend, macro_warn, backwardation=True,
                canonical_strategy=StrategyName.BULL_PUT_SPREAD_HV.value,
                params=params,
            )
        # P1: VIX momentum rising → premium spiking, near-term risk elevated
        _rising = (vix.trend == Trend.RISING)
        if not T.gate(not _rising, "hv_bullish_vix_rising",
                      "恐慌还在升级吗？升级中不卖 put",
                      detail=f"VIX 动量 {T.ev(vix.trend)}",
                      inputs={"vix_trend": T.ev(vix.trend)},
                      code_ref="selector HIGH_VOL·BULLISH P1"):
            return _reduce_wait(
                "HIGH_VOL + VIX RISING — near-term panic building; wait for VIX to stabilise",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.BULL_PUT_SPREAD_HV.value,
                params=params,
            )
        # SPEC-060: HIGH_VOL + BULLISH + IV=NEUTRAL → IC_HV
        # Bootstrap matrix: IC $1,837 ✓ (n=11) vs BPS_HV $100 not significant (n=13).
        if iv_s == IVSignal.NEUTRAL:
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
                        "Upper short wing — HIGH_VOL premium"),
                    Leg("BUY",  "CALL", 45, 0.08,
                        "Upper long wing"),
                    Leg("SELL", "PUT",  45, 0.16,
                        "Lower short wing — HIGH_VOL premium"),
                    Leg("BUY",  "PUT",  45, 0.08,
                        "Lower long wing"),
                ],
                size_rule=(
                    f"{int(params.high_vol_size*100)}% size — risk ≤ "
                    f"{1.5*params.high_vol_size:.1f}% of account "
                    f"(HIGH_VOL, reduced exposure)"
                ),
                rationale=(
                    "HIGH_VOL + BULLISH + IV NEUTRAL + VIX stable — IC_HV dominates BPS_HV "
                    "in this cell; double-sided premium with no directional bet (SPEC-060)"
                ),
                position_action=action,
                macro_warning=macro_warn,
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
        T.add("cell", "route_low_vol",
              f"查策略手册：低波动区 × {T.trend_phrase(T.ev(t), trend.ma_gap_pct)}",
              inputs={"regime": T.ev(r), "trend": T.ev(t), "iv_signal": T.ev(iv_s)},
              outcome="route", code_ref="selector LOW_VOL matrix", stage="routing")
        if t == TrendSignal.NEUTRAL:
            # P3: VIX rising in low-vol env = regime about to shift; skip condor
            _rising = (vix.trend == Trend.RISING)
            if not T.gate(not _rising, "lv_neutral_vix_rising",
                          "恐慌在低位抬头吗？低波动区里 VIX 上冲常是体制切换前兆，不做 Iron Condor",
                          detail=f"VIX 动量 {T.ev(vix.trend)}",
                          inputs={"vix_trend": T.ev(vix.trend)},
                          code_ref="selector LOW_VOL·NEUTRAL P3"):
                return _reduce_wait(
                    "LOW_VOL + NEUTRAL but VIX RISING — potential regime shift; Iron Condor risk too high",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.IRON_CONDOR.value,
                    params=params,
                )
            # P3: IVP outside 20–50 sweet-spot — too low = insufficient premium; too high = tail risk
            _ivp_out = (iv.iv_percentile < 20 or iv.iv_percentile > 50)
            if not T.gate(not _ivp_out, "lv_neutral_ivp_band",
                          "premium 在甜区吗？（第 20-50 百分位）太便宜没肉、太贵尾部风险高",
                          detail=f"当前 {T.ivp_phrase(iv.iv_percentile)}，甜区 20-50",
                          inputs={"iv_percentile": round(iv.iv_percentile, 1), "band": [20, 50]},
                          code_ref="selector LOW_VOL·NEUTRAL P3"):
                return _reduce_wait(
                    f"LOW_VOL + NEUTRAL but IVP={iv.iv_percentile:.0f} outside 20–50 — Iron Condor risk/reward unfavourable",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.IRON_CONDOR.value,
                    params=params,
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
            if not params.disable_entry_gates:
                # Gate 1 (SPEC-049) removed by sensitivity analysis (2026-04-15):
                # ivp252 ∈ [30,50] gate blocked significantly profitable trades
                # (47 trades, avg +$987, bootstrap CI [+574, +1751]).
                # Net system cost: -$11,146. Same negative-selection-bias pattern
                # as Gate 3 (SPEC-054 → SPEC-056c).

                # ── Gate 2 (SPEC-051): IV=HIGH in LOW_VOL ────────────────────
                _iv_high = (iv_s == IVSignal.HIGH)
                if not T.gate(not _iv_high, "lv_bullish_iv_high",
                              "低波动区里期权反常偏贵吗？是则可能是波动扩张前兆，"
                              "Bull Call Diagonal 的卖出腿会暴露",
                              detail=f"当前 {T.ivp_phrase(iv.iv_percentile)}",
                              inputs={"iv_signal": T.ev(iv_s),
                                      "iv_percentile": round(iv.iv_percentile, 1)},
                              code_ref="SPEC-051 Gate 2"):
                    return _reduce_wait(
                        f"LOW_VOL + BULLISH but IV=HIGH (IVP={iv.iv_percentile:.0f}) — "
                        "vol expansion signal in low-vol regime; DIAGONAL short leg exposed",
                        vix, iv, trend, macro_warn,
                        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                        params=params,
                    )

                # Gate 3 (SPEC-054) removed by SPEC-056c:
                # both-high (ivp63≥50 AND ivp252≥50) no longer blocked —
                # F006 research had negative selection bias (n=8 was post-Gate-1/2 residual).
                # Full-history event study (n=14) shows Sharpe +1.56, similar to double_low.

            from strategy.bcd_filter import should_block_bcd
            _comfort_block = should_block_bcd(
                params.bcd_comfort_filter_mode,
                vix=vix.vix,
                dist_30d_high_pct=trend.dist_30d_high_pct,
                ma_gap_pct=trend.ma_gap_pct,
                date=vix.date,
            )
            if not T.gate(not _comfort_block, "lv_bullish_comfort_top",
                          "『舒适顶部』过滤：VIX 低 + 贴近 30 日高点 + 远离均线三项同时"
                          "成立时拦（注：Q087 A4 已证此过滤零保护价值，当前多为 shadow 模式）",
                          detail=(f"vix={vix.vix:.1f}, 距30日高点 {trend.dist_30d_high_pct}"
                                  f", 均线偏离 {trend.ma_gap_pct:.3f}"),
                          inputs={"mode": params.bcd_comfort_filter_mode},
                          code_ref="SPEC-079 comfortable-top"):
                return _reduce_wait(
                    f"BCD comfortable-top filter (SPEC-079): risk_score=3 "
                    f"(vix={vix.vix:.1f}, dist_30d={trend.dist_30d_high_pct:.3f}, "
                    f"ma_gap={trend.ma_gap_pct:.3f})",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                    params=params,
                )

            action = get_position_action(
                StrategyName.BULL_CALL_DIAGONAL.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.BULL_CALL_DIAGONAL.value),
            )
            local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)
            return _build_recommendation(
                StrategyName.BULL_CALL_DIAGONAL,
                vix=vix,
                iv=iv,
                trend=trend,
                legs=[
                    Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
                    Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
                ],
                size_rule=_compute_size_tier(
                    StrategyName.BULL_CALL_DIAGONAL.value, iv, vix, iv_s, t
                ),
                rationale="LOW_VOL + BULLISH — theta is cheap; use 45 DTE short leg to widen collection window",
                position_action=action,
                macro_warning=macro_warn,
                local_spike=local_spike,
            )

        # BEARISH in LOW_VOL → no edge; low-vol pullbacks are typically V-shaped
        T.gate(False, "lv_bearish_dead_cell",
               "手册死格：低波动区的下跌通常是 V 型反转，方向性看跌没有统计边际 → 一律观望",
               detail="低波动 pullback 历史上多为 V 型，做空胜率无优势",
               inputs={"cell": "LOW_VOL|BEARISH"}, code_ref="selector LOW_VOL·BEARISH")
        return _reduce_wait(
            "LOW_VOL + BEARISH — 低波动环境中的方向性看跌无统计边际；V型反转概率高，等待趋势确认",
            vix, iv, trend, macro_warn,
            params=params,
        )

    # ── NORMAL ───────────────────────────────────────────────────────
    T.add("cell", "route_normal",
          f"查策略手册：正常波动区 × 期权{T.ev(iv_s)}贵贱档 × "
          f"{T.trend_phrase(T.ev(t), trend.ma_gap_pct)}",
          inputs={"regime": T.ev(r), "iv_signal": T.ev(iv_s), "trend": T.ev(t)},
          outcome="route", code_ref="selector NORMAL matrix", stage="routing")
    if iv_s == IVSignal.HIGH:
        if t == TrendSignal.BULLISH:
            # Backwardation filter: skip if near-term panic elevated
            _bw = vix.backwardation
            if not T.gate(not _bw, "nhb_backwardation",
                          "近月恐慌是否高于远月（倒挂）？倒挂时不卖 put spread",
                          detail=f"VIX {vix.vix:.1f} vs VIX3M {vix.vix3m}",
                          inputs={"backwardation": _bw},
                          code_ref="selector NORMAL·HIGH·BULLISH"):
                return _reduce_wait(
                    "NORMAL + IV HIGH + BULLISH but VIX term structure in BACKWARDATION — skip Bull Put Spread",
                    vix, iv, trend, macro_warn, backwardation=True,
                    canonical_strategy=StrategyName.BULL_PUT_SPREAD.value,
                    params=params,
                )
            # P1: VIX momentum rising → conditions deteriorating, skip selling puts
            _rising = (vix.trend == Trend.RISING)
            if not T.gate(not _rising, "nhb_vix_rising",
                          "恐慌还在升级吗？升级中不卖 put",
                          detail=f"VIX 动量 {T.ev(vix.trend)}",
                          inputs={"vix_trend": T.ev(vix.trend)},
                          code_ref="selector NORMAL·HIGH·BULLISH P1"):
                return _reduce_wait(
                    "NORMAL + IV HIGH + BULLISH but VIX RISING — wait for VIX to stabilise before selling premium",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BULL_PUT_SPREAD.value,
                    params=params,
                )
            # SPEC-060 Change 3: NORMAL + IV_HIGH + BULLISH → REDUCE_WAIT
            # Bootstrap matrix: BPS avg −$299 not significant (n=23);
            # BCS_HV CI [$755,$1,044] is bootstrap-degenerate (n=10, block_size=5 ≈ 2 blocks).
            # No strategy has statistically significant alpha in this cell.
            T.gate(False, "nhb_dead_cell",
                   "手册死格：此组合（正常区 + 期权偏贵 + 上升趋势）26 年回测中"
                   "没有任何策略有统计显著优势 → 一律观望",
                   detail="bootstrap 矩阵：BPS 均值 −$299 不显著（n=23）",
                   inputs={"cell": "NORMAL|HIGH|BULLISH"},
                   code_ref="SPEC-060 Change 3")
            return _reduce_wait(
                "NORMAL + IV HIGH + BULLISH — no strategy has statistically significant alpha in this cell; REDUCE_WAIT (SPEC-060)",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.BULL_PUT_SPREAD.value,
                params=params,
            )

        if t == TrendSignal.BEARISH:
            _rising = (vix.trend == Trend.RISING)
            if not T.gate(not _rising, "nhbe_vix_rising",
                          "恐慌还在升级吗？升级中不做 Iron Condor",
                          detail=f"VIX 动量 {T.ev(vix.trend)}",
                          inputs={"vix_trend": T.ev(vix.trend)},
                          code_ref="selector NORMAL·HIGH·BEARISH"):
                return _reduce_wait(
                    "NORMAL + IV HIGH + BEARISH + VIX RISING — skip Iron Condor while vol escalating",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.IRON_CONDOR.value,
                    params=params,
                )
            # IVP ≥ 50 gate removed by SPEC-058:
            # SPEC-057 matrix shows IC avg $2,043 (n=13) in NORMAL|HIGH|BEARISH —
            # rich premium outweighs put-side tail risk in this cell.
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
        _rising = (vix.trend == Trend.RISING)
        if not T.gate(not _rising, "nhn_vix_rising",
                      "恐慌还在升级吗？升级中不做 Iron Condor",
                      detail=f"VIX 动量 {T.ev(vix.trend)}",
                      inputs={"vix_trend": T.ev(vix.trend)},
                      code_ref="selector NORMAL·HIGH·NEUTRAL P3"):
            return _reduce_wait(
                "NORMAL + IV HIGH + NEUTRAL but VIX RISING — Iron Condor unsafe; wait for vol to stabilise",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.IRON_CONDOR.value,
                params=params,
            )
        # IVP > 50 gate removed by SPEC-058:
        # SPEC-057 matrix shows IC avg $1,017 (n=9) in NORMAL|HIGH|NEUTRAL —
        # rich premium still favors IC even when IVP elevated in NORMAL regime.
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
            # SPEC-113 carve: VIX<18 routes to BCD (spike-decay state with +vega cushion)
            _carve_ok = (vix.vix < SPEC_113_VIX_THRESHOLD)
            T.gate(_carve_ok, "nlb_spec113_carve",
                   f"温和带特批通道：VIX 低于 {SPEC_113_VIX_THRESHOLD:.0f} 时此格特批做 "
                   "Bull Call Diagonal（买远月 call + 卖近月 call）——"
                   "spike 衰减态中 +vega 缓冲有结构性回报",
                   detail=f"VIX {vix.vix:.1f} vs 特批线 {SPEC_113_VIX_THRESHOLD:.0f}"
                          + ("，进入特批" if _carve_ok else "，不满足（该格无常规策略 → 观望）"),
                   inputs={"vix": round(vix.vix, 2), "threshold": SPEC_113_VIX_THRESHOLD},
                   code_ref="SPEC-113 carve")
            if _carve_ok:
                from strategy.bcd_filter import should_block_bcd
                _comfort_block = (not params.disable_entry_gates and should_block_bcd(
                    params.bcd_comfort_filter_mode,
                    vix=vix.vix,
                    dist_30d_high_pct=trend.dist_30d_high_pct,
                    ma_gap_pct=trend.ma_gap_pct,
                    date=vix.date,
                ))
                if not T.gate(not _comfort_block, "nlb_comfort_top",
                              "『舒适顶部』过滤：VIX 低 + 贴近 30 日高点 + 远离均线三项"
                              "同时成立时拦（Q087 A4 已证零保护价值，多为 shadow 模式）",
                              detail=(f"vix={vix.vix:.1f}, 距30日高点 {trend.dist_30d_high_pct}"
                                      f", 均线偏离 {trend.ma_gap_pct:.3f}"),
                              inputs={"mode": params.bcd_comfort_filter_mode},
                              code_ref="SPEC-079 comfortable-top"):
                    return _reduce_wait(
                        f"SPEC-113 BCD carve (NORMAL+IV_LOW+BULL+VIX<{SPEC_113_VIX_THRESHOLD}) but "
                        f"comfortable-top filter (SPEC-079): risk_score=3 "
                        f"(vix={vix.vix:.1f}, dist_30d={trend.dist_30d_high_pct:.3f}, "
                        f"ma_gap={trend.ma_gap_pct:.3f})",
                        vix, iv, trend, macro_warn,
                        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                        params=params,
                    )

                action = get_position_action(
                    StrategyName.BULL_CALL_DIAGONAL.value,
                    is_wait=False,
                    strategy_key=catalog_strategy_key(StrategyName.BULL_CALL_DIAGONAL.value),
                )
                local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)
                return _build_recommendation(
                    StrategyName.BULL_CALL_DIAGONAL,
                    vix=vix, iv=iv, trend=trend,
                    legs=[
                        Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
                        Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
                    ],
                    size_rule=_compute_size_tier(
                        StrategyName.BULL_CALL_DIAGONAL.value, iv, vix, iv_s, t
                    ),
                    rationale=(
                        f"NORMAL + IV LOW + BULLISH + VIX={vix.vix:.1f} < {SPEC_113_VIX_THRESHOLD} "
                        f"(SPEC-113 carve) — spike-decay state where BCD +vega cushion is structurally rewarded "
                        f"(P11 +18.5% period-ROE on 46 carved trades, +8vp Sortino 0.860)"
                    ),
                    position_action=action,
                    macro_warning=macro_warn,
                    local_spike=local_spike,
                )

            # VIX >= 18: stays reduce_wait
            return _reduce_wait(
                f"NORMAL + IV LOW + BULLISH + VIX={vix.vix:.1f} >= {SPEC_113_VIX_THRESHOLD} — "
                f"SPEC-113 carve gate (VIX too high for +vega cushion to dominate under pessimistic skew)",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                params=params,
            )

        if t == TrendSignal.BEARISH:
            T.gate(False, "nlbe_dead_cell",
                   "手册死格：期权太便宜 + 下降趋势，没有值得卖的 premium → 观望",
                   inputs={"cell": "NORMAL|LOW|BEARISH"},
                   code_ref="selector NORMAL·LOW·BEARISH")
            return _reduce_wait(
                "NORMAL + IV LOW + BEARISH — low premium insufficient for IC; skip",
                vix, iv, trend, macro_warn,
                params=params,
            )

        # NEUTRAL + LOW IV → no edge in any direction, not worth selling premium either
        T.gate(False, "nln_dead_cell",
               "手册死格：无方向 + premium 便宜，两头都没边际 → 观望",
               inputs={"cell": "NORMAL|LOW|NEUTRAL"},
               code_ref="selector NORMAL·LOW·NEUTRAL")
        return _reduce_wait(
            "NORMAL + IV LOW + NEUTRAL — no directional edge and premium cheap; skip",
            vix, iv, trend, macro_warn,
            params=params,
        )

    # iv_s == NEUTRAL, regime == NORMAL
    if t == TrendSignal.BULLISH:
        # Backwardation filter for Bull Put Spread
        _bw = vix.backwardation
        if not T.gate(not _bw, "nnb_backwardation",
                      "近月恐慌是否高于远月（倒挂）？倒挂 = 短期极度紧张，不卖 put spread",
                      detail=f"VIX {vix.vix:.1f} vs VIX3M {vix.vix3m}",
                      inputs={"backwardation": _bw},
                      code_ref="selector NNB backwardation"):
            return _reduce_wait(
                "NORMAL + IV NEUTRAL + BULLISH but VIX term structure in BACKWARDATION — skip Bull Put Spread",
                vix, iv, trend, macro_warn, backwardation=True,
                canonical_strategy=StrategyName.BULL_PUT_SPREAD.value,
                params=params,
            )
        # P1: VIX momentum rising → conditions deteriorating, skip selling puts
        _rising = (vix.trend == Trend.RISING)
        if not T.gate(not _rising, "nnb_vix_rising",
                      "恐慌还在升级吗？升级中不卖 put，等它稳住",
                      detail=f"VIX 动量 {T.ev(vix.trend)}",
                      inputs={"vix_trend": T.ev(vix.trend)},
                      code_ref="selector NNB P1"):
            return _reduce_wait(
                "NORMAL + IV NEUTRAL + BULLISH but VIX RISING — wait for VIX to stabilise before selling premium",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.BULL_PUT_SPREAD.value,
                params=params,
            )
        # P1: IVP ≥ BPS_NNB_IVP_UPPER — stressed vol; tail risk exceeds premium benefit
        # （5 月实盘复审 F1：PM 曾把这道『入场』门当『退出』信号用——它拦的是
        #   开新仓，不是要求平已有仓）
        _ivp_hot = (iv.iv_percentile >= BPS_NNB_IVP_UPPER)
        if not T.gate(not _ivp_hot, "nnb_ivp_upper",
                      f"期权是否太贵（≥第 {BPS_NNB_IVP_UPPER} 百分位）？太贵 = 市场在"
                      "定价压力，尾部风险超过 premium 收益，不开新 Bull Put Spread",
                      detail=f"当前 {T.ivp_phrase(iv.iv_percentile)}，上限 {BPS_NNB_IVP_UPPER}",
                      inputs={"iv_percentile": round(iv.iv_percentile, 1),
                              "upper": BPS_NNB_IVP_UPPER},
                      code_ref="selector NNB BPS_NNB_IVP_UPPER"):
            return _reduce_wait(
                f"NORMAL + IV NEUTRAL + BULLISH but IVP={iv.iv_percentile:.0f} ≥ {BPS_NNB_IVP_UPPER} — stressed vol environment, BPS tail risk too high",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.BULL_PUT_SPREAD.value,
                params=params,
            )
        # P2: IVP < BPS_NNB_IVP_LOWER — insufficient premium for BPS risk/reward
        # Analysis (2026-03-28): borderline entry at IVP=43 caused 2025-10-03 loss.
        # Raise minimum from 40→43 to filter marginal premium environments.
        _ivp_thin = (iv.iv_percentile < BPS_NNB_IVP_LOWER)
        if not T.gate(not _ivp_thin, "nnb_ivp_lower",
                      f"premium 够肉吗（≥第 {BPS_NNB_IVP_LOWER} 百分位）？太薄不值得"
                      "承担 put spread 的下行风险",
                      detail=f"当前 {T.ivp_phrase(iv.iv_percentile)}，下限 {BPS_NNB_IVP_LOWER}",
                      inputs={"iv_percentile": round(iv.iv_percentile, 1),
                              "lower": BPS_NNB_IVP_LOWER},
                      code_ref="selector NNB BPS_NNB_IVP_LOWER"):
            return _reduce_wait(
                f"NORMAL + IV NEUTRAL + BULLISH but IVP={iv.iv_percentile:.0f} < {BPS_NNB_IVP_LOWER} — insufficient premium for BPS risk/reward",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.BULL_PUT_SPREAD.value,
                params=params,
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
        _rising = (vix.trend == Trend.RISING)
        if not T.gate(not _rising, "nnbe_vix_rising",
                      "恐慌还在升级吗？升级中不做 Iron Condor",
                      detail=f"VIX 动量 {T.ev(vix.trend)}",
                      inputs={"vix_trend": T.ev(vix.trend)},
                      code_ref="selector NORMAL·NEUTRAL·BEARISH"):
            return _reduce_wait(
                "NORMAL + IV NEUTRAL + BEARISH + VIX RISING — skip Iron Condor while vol escalating",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.IRON_CONDOR.value,
                params=params,
            )
        _ivp_out = (iv.iv_percentile < 20 or iv.iv_percentile > 50)
        if not T.gate(not _ivp_out, "nnbe_ivp_band",
                      "premium 在甜区吗？（第 20-50 百分位）",
                      detail=f"当前 {T.ivp_phrase(iv.iv_percentile)}，甜区 20-50",
                      inputs={"iv_percentile": round(iv.iv_percentile, 1), "band": [20, 50]},
                      code_ref="selector NORMAL·NEUTRAL·BEARISH"):
            return _reduce_wait(
                f"NORMAL + IV NEUTRAL + BEARISH but IVP={iv.iv_percentile:.0f} outside 20–50 — IC risk/reward unfavourable",
                vix, iv, trend, macro_warn,
                canonical_strategy=StrategyName.IRON_CONDOR.value,
                params=params,
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
    _rising = (vix.trend == Trend.RISING)
    if not T.gate(not _rising, "nnn_vix_rising",
                  "恐慌还在升级吗？升级中区间假设失效，不做 Iron Condor",
                  detail=f"VIX 动量 {T.ev(vix.trend)}",
                  inputs={"vix_trend": T.ev(vix.trend)},
                  code_ref="selector NORMAL·NEUTRAL·NEUTRAL P3"):
        return _reduce_wait(
            "NORMAL + IV NEUTRAL + NEUTRAL but VIX RISING — Iron Condor unsafe; wait for vol to stabilise",
            vix, iv, trend, macro_warn,
            canonical_strategy=StrategyName.IRON_CONDOR.value,
            params=params,
        )
    # P3: IVP outside 20–50 — too low = free money illusion; too high = breached too often
    _ivp_out = (iv.iv_percentile < 20 or iv.iv_percentile > 50)
    if not T.gate(not _ivp_out, "nnn_ivp_band",
                  "premium 在甜区吗？（第 20-50 百分位）太低是免费午餐幻觉、太高被击穿太频繁",
                  detail=f"当前 {T.ivp_phrase(iv.iv_percentile)}，甜区 20-50",
                  inputs={"iv_percentile": round(iv.iv_percentile, 1), "band": [20, 50]},
                  code_ref="selector NORMAL·NEUTRAL·NEUTRAL P3"):
        return _reduce_wait(
            f"NORMAL + IV NEUTRAL + NEUTRAL but IVP={iv.iv_percentile:.0f} outside 20–50 — Iron Condor risk/reward unfavourable",
            vix, iv, trend, macro_warn,
            canonical_strategy=StrategyName.IRON_CONDOR.value,
            params=params,
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


def select_es_short_put(
    vix: VixSnapshot,
    iv: IVSnapshot,
    trend: TrendSnapshot,
    params: StrategyParams = DEFAULT_PARAMS,
) -> Recommendation:
    macro_warn = not trend.above_200

    if trend.signal != TrendSignal.BULLISH:
        return _reduce_wait(
            "ES short put blocked — trend filter not bullish; no new /ES short put",
            vix,
            iv,
            trend,
            macro_warn,
            canonical_strategy=StrategyName.ES_SHORT_PUT.value,
            params=params,
        )

    return _build_recommendation(
        StrategyName.ES_SHORT_PUT,
        params=params,
        vix=vix,
        iv=iv,
        trend=trend,
        legs=[
            Leg("SELL", "PUT", 45, 0.20, "Single-slot /ES short put candidate"),
        ],
        size_rule="1 contract max; single slot only; require projected /ES BP <= 20% of NLV",
        rationale="Trend filter passed — minimal /ES short put production cell candidate",
        position_action="OPEN",
        macro_warning=macro_warn,
    )


def get_recommendation(
    vix_df=None,
    spx_df=None,
    use_intraday: bool = False,
    params: StrategyParams = DEFAULT_PARAMS,
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

    rec = select_strategy(vix_snap, iv_snap, trend_snap, params)
    rec = _apply_aftermath_staging_live(rec, vix_data, params)
    rec = _eval_overlay_f_live(rec, params)
    return _apply_bcd_governance_live(rec, vix_snap, iv_snap, trend_snap, params)


def _apply_aftermath_staging_live(rec: Recommendation, vix_df,
                                  params: StrategyParams = DEFAULT_PARAMS) -> Recommendation:
    """SPEC-143 — Q101 aftermath 首笔 0.5× staging，LIVE-ONLY wrapper
    （get_recommendation 路径；回测直接调 select_strategy，永不经过这里——
    与 SPEC-123 D1 同一隔离拓扑，AC-4 回测输出逐字节不变）。

    仅命中 aftermath V3-A 推荐（iron_condor_hv 且 rationale 带 aftermath
    标记——与 web.server.api_aftermath_window_gates 同一判别口径；两条
    aftermath 分支的 rationale 恒含该词，tests/test_spec_143.py 有双分支
    行为断言防漂移）。三态判定在 strategy/aftermath_staging.py；人话文案
    单源 decision_trace.q101_staging_label。advisory ⚠ 档：改张数与语气，
    不拦推荐、不新增推送（SPEC-140 §4/§5 推送宪法）。
    """
    if rec.strategy_key != "iron_condor_hv" or "aftermath" not in (rec.rationale or ""):
        return rec
    try:
        from strategy.aftermath_staging import evaluate_staging

        staging = evaluate_staging(vix_df, params, today=rec.vix_snapshot.date)
        label, outcome = T.q101_staging_label(staging)
        staging = {**staging, "label_human": label, "outcome": outcome,
                   "code_ref": "SPEC-143 · research/q101"}
        rec.aftermath_staging = staging
        rec.rationale += f"　[{label}]"
        T.add("governance", "q101_aftermath_staging", label,
              detail=(f"窗口起始 {staging['window_start']} · 窗口内读数 "
                      f"{staging['reading_date'] or '无'} · "
                      f"s = {staging['s'] if staging['s'] is not None else '—'}"
                      f"（= (d15_moff − atm_moff) ÷ 4.52vp calm 中位基线）· "
                      f"窗口首笔 = {'是' if staging['first_trade'] else '否'} · "
                      f"张数系数 {staging['factor']:g}×——提示不拦：只降张数，"
                      "不阻止开仓，不新增推送"),
              inputs={k: staging[k] for k in
                      ("state", "factor", "s", "window_start",
                       "first_trade", "reading_date")},
              outcome=outcome, code_ref="SPEC-143 · research/q101",
              kind=("evidence" if outcome == "pass" else "verdict"),
              stage="governance")
        rec.trace = (rec.trace or []) + T.drain()
    except Exception:
        # staging must never break the recommendation path (fail-soft，
        # 同 bcd governance wrapper 先例)
        import logging
        logging.getLogger("selector").exception("aftermath staging wrapper failed")
    return rec


def _apply_bcd_governance_live(rec: Recommendation, vix: VixSnapshot, iv: IVSnapshot,
                               trend: TrendSnapshot,
                               params: StrategyParams = DEFAULT_PARAMS) -> Recommendation:
    """SPEC-123 — LIVE-ONLY wrapper (get_recommendation path; backtests call
    select_strategy directly and never read governance state).

    D1: while the BCD family is halted, BCD cells downgrade to REDUCE_WAIT
    with the triggering gate in the rationale. NB the halt is a ROUTINE REVIEW
    EVENT (P(6-trade sum<0 | edge real) ≈ 39-48%/window) — copy stays calm.
    D2: while the LOW_VOL quote-gate is accumulating, BCD recs carry an
    advisory tag; after unlock, the first-5-trades 1-lot advisory."""
    if rec.strategy_key != "bull_call_diagonal":
        return rec
    try:
        from strategy import bcd_governance as gov
        halt = gov.is_halted()
        # 显式 force_strategy = PM 手动 override（唯一调用方：/api/position/
        # open-draft 预填，供 add-tranche / roll 的链筛选与执行价预填）。halt 只
        # 暂停 *自动* 新开仓；它绝不能拦住 PM 管理现有仓位所需的 advisory 预填
        # ——halt 文案自己写明"持仓管理不受影响"。故 force 时保留真实腿，把 halt
        # 作为 rationale 上的知情提示（提示不拦），不 downgrade 成 wait。
        # （2026-07-07 D1 halt 触发后 add-tranche/roll 预填全断的回归根因。）
        if halt and params.force_strategy:
            reasons = "；".join(
                f"{g.get('detail') or '?'}（{g.get('gate', '?')}）"
                for g in (halt.get("gates") or [])
            ) or "触发门未知"
            rec.rationale += (
                f"　[BCD 家族复核门触发（{halt.get('at')} 起）：{reasons}"
                f"——自动新开仓已暂停；本预填仅供持仓管理/显式 override 参考（提示不拦）]"
            )
            T.add("governance", "bcd_family_halt",
                  "安全刹车（override 放行）：家族复核门触发，但本次为 PM 显式 force 预填 → 提示不拦",
                  detail=("；".join(f"{g.get('detail') or '?'}"
                                    for g in (halt.get("gates") or []))
                          + "。halt 只暂停自动新开仓，不阻断持仓管理预填。"
                            "PM 复核后解除：python -m strategy.bcd_governance --pm-clear"),
                  inputs={"halted_at": halt.get("at"),
                          "gates": [g.get("gate") for g in (halt.get("gates") or [])]},
                  outcome="advisory", code_ref="SPEC-123 D1", stage="governance")
            rec.trace = (rec.trace or []) + T.drain()
            return rec
        # SPEC-135 治理层节点（安全刹车——含运行特性披露人话版）。halted 分支
        # 会走 _reduce_wait → 新 trace 从这些节点开始重建，故先 reset 再记。
        if halt:
            T.reset()
            # SPEC-135.4：主行只留一句人话；预注册概率说明与 pm-clear 解除命令
            # 全部收进 detail（展开/hover 承载），不在锚点主行刷屏
            T.add("governance", "bcd_family_halt",
                  "安全刹车：该策略家族近期合计收益转负 → 暂停开新仓，等待复核",
                  detail=("；".join(f"{g.get('detail') or '?'}"
                                    for g in (halt.get("gates") or []))
                          + "。预注册说明：策略良好时每周期也有约四成概率误踩此门"
                            "——是『要求复核』不是『宣布失效』。"
                            "PM 复核后解除：python -m strategy.bcd_governance --pm-clear"),
                  inputs={"halted_at": halt.get("at"),
                          "gates": [g.get("gate") for g in (halt.get("gates") or [])]},
                  outcome="halt", code_ref="SPEC-123 D1",
                  kind="verdict", stage="governance")
            # Lead with what happened in plain language (the gate dict already
            # carries a human-readable detail); the gate code is provenance
            # and trails in parentheses. "SPEC-123 D1，门：G2_18m_combined"
            # told PM nothing (2026-07-07 review).
            reasons = "；".join(
                f"{g.get('detail') or '?'}（{g.get('gate', '?')}）"
                for g in (halt.get("gates") or [])
            ) or "触发门未知"
            halted_rec = _reduce_wait(
                f"BCD 新开仓暂停（{halt.get('at')} 起）— 收益复核门触发：{reasons}。"
                f"这是预期内的例行复核（edge 真实时每窗口也有约 39-48% 概率触发），"
                f"不是策略失效判定；持仓管理不受影响。"
                f"PM 复核后解除：python -m strategy.bcd_governance --pm-clear（SPEC-123 D1）",
                vix, iv, trend, macro_warn=False,
                canonical_strategy=rec.strategy.value, params=params,
            )
            # 治理截断：保留 selector 原 trace（走到开仓候选的完整路径）+
            # 追加治理节点与最终观望结论——PM 看到"本来会开、被刹车拦下"全程。
            # SPEC-135.1：原 final(accept) 锚点降级为 verdict（阶段结论"候选"），
            # 只改新增的 kind/stage 字段，既有字段逐字节不变
            prior = list(rec.trace or [])
            for _n in prior:
                if _n.get("check") == "final_verdict":
                    _n["kind"] = "verdict"
                    _n["stage"] = "routing"
            halted_rec.trace = prior + halted_rec.trace
            return halted_rec
        T.add("governance", "bcd_family_halt",
              "安全刹车：策略家族收益复核门（本日未触发）",
              detail="家族累计/月度/18个月合并各门均在允许区",
              outcome="pass", code_ref="SPEC-123 D1", stage="governance")
        regime_val = getattr(vix.regime, "value", str(vix.regime))
        if regime_val == "LOW_VOL":
            qg = gov.quote_gate_status()
            if not qg["unlocked"]:
                # SPEC-136 单源：quote_gate_status().label_human（digest /
                # 手动开仓 advisory 同源），禁止手写第二套
                _qg_label = qg.get("label_human") or (
                    f"真实报价已积累 {qg['days']}/{qg['needed']} 天")
                rec.rationale += (f"　[BCD 重开前置：{_qg_label}——"
                                  f"未满前开 BCD 将触发即时复审（提示不拦）]")
                T.add("governance", "bcd_quote_gate",
                      f"报价前置门：已记录 {qg['days']} 天 / 需 {qg['needed']} 天真实报价"
                      "（未解锁前开 BCD 触发即时复审，不拦）",
                      inputs=qg, outcome="info", code_ref="SPEC-123 D2",
                      stage="governance")
            else:
                adv = gov.first5_advisory()
                if adv:
                    rec.rationale += f"　[BCD 纪律：{adv}]"
        rec.trace = (rec.trace or []) + T.drain()
    except Exception:
        # governance must never break the recommendation path
        import logging
        logging.getLogger("selector").exception("bcd governance wrapper failed")
    return rec


def get_es_recommendation(
    vix_df=None,
    spx_df=None,
    use_intraday: bool = False,
) -> Recommendation:
    vix_data = fetch_vix_history(period="2y") if vix_df is None else vix_df
    spx_data = fetch_spx_history(period="2y") if spx_df is None else spx_df

    current_vix: Optional[float] = None
    current_spx: Optional[float] = None

    if use_intraday:
        try:
            vix_5m = fetch_vix_history(period="1d", interval="5m")
            current_vix = float(vix_5m["vix"].iloc[-1])
        except Exception:
            pass

        try:
            spx_5m = fetch_spx_history(period="1d", interval="5m")
            current_spx = float(spx_5m["close"].iloc[-1])
        except Exception:
            pass

    vix_snap = get_current_snapshot(vix_data, current_vix=current_vix)
    iv_snap = get_current_iv_snapshot(vix_data, current_vix=current_vix)
    trend_snap = get_current_trend(spx_data, current_spx=current_spx)

    return select_es_short_put(vix_snap, iv_snap, trend_snap)


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
