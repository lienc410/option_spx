"""
Q012 Phase C — Joint Portfolio Simulation: Governance Architecture Comparison
=============================================================================

研究设计哲学：
  不是在现有 SPEC-061 上打补丁，而是从头设计多策略共享 BP 池的治理架构。
  治理层应独立于策略执行层，通过统一的 BP 预算框架协调两个策略。

核心问题：
  给定 SPX Credit 和 /ES short put 共享同一 PM BP 池，
  什么样的治理架构能在最大化账户 ROE 的同时控制 SPAN 扩张风险？

四种治理架构对比：

  Arch-0  Baseline（仅 SPX Credit，无 /ES）
  Arch-1  Additive（/ES 简单叠加，仅共享 cap 20% NLV，无 stress correction）
  Arch-2  Dynamic Budget（动态 BP 预算分配，regime-dependent，Phase A SPAN 校正）
  Arch-3  Regime-Gated（HIGH_VOL 下 /ES 完全封锁，LOW_VOL 下 /ES 优先）

对比维度（PM 2026-04-26 standing rule 全指标包）：
  - Account AnnROE（SPX + /ES 合并）
  - /ES 独立贡献（marginal AnnROE）
  - /ES trades enabled / blocked
  - Sharpe, MaxDD, CVaR 5%
  - SPAN breach events（post-entry VIX spike 导致 BP 超限的次数）
  - Worst trade, disaster window

方法：
  1. 运行 SPX Credit 19年回测，提取所有 trades（含开仓/平仓日期和 BP 占用）
  2. 建立每日 SPX Credit BP 状态时间序列
  3. 对每个 /ES BULLISH 信号日，按 4 种架构判断是否允许 /ES 开仓
  4. 仿真 /ES 交易的 PnL，合并到账户层指标
  5. 输出全指标包 + 架构对比矩阵
"""

from __future__ import annotations
import sys, math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest.pricer import put_price, find_strike_for_delta
from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.portfolio import DailyPortfolioRow
from signals.trend import (
    fetch_spx_history, _classify_trend_atr, _compute_atr14_close,
    TREND_THRESHOLD, TrendSignal,
)
from signals.vix_regime import fetch_vix_history

# ── Constants ─────────────────────────────────────────────────────────────────
ES_MULT       = 50
CALIB_VIX     = 19.0
CALIB_SPAN    = 20_529.0
CALIB_ES      = 5_400.0
SCAN_EXP      = 1.10
VOL_SHOCK     = 0.50
NLV0          = 500_000.0

# /ES trade parameters
ES_DTE        = 45
ES_DELTA      = 0.20
ES_STOP_MULT  = 3.0
ES_PROFIT_PCT = 0.10
ES_GAMMA_DTE  = 5

# SPX Credit account parameters (consistent with SPEC-084)
SPX_ACCOUNT   = 500_000.0
SPX_START     = "2007-01-01"

WARMUP        = 64

# ── Phase A SPAN model (inline) ───────────────────────────────────────────────

def _calibrate_base_scan() -> float:
    sigma0 = CALIB_VIX / 100.0
    k0 = find_strike_for_delta(CALIB_ES, ES_DTE, sigma0, ES_DELTA, is_call=False)
    p0 = put_price(CALIB_ES, k0, ES_DTE, sigma0)
    target = CALIB_SPAN / ES_MULT
    lo, hi = 0.01, 0.35
    for _ in range(80):
        mid = (lo + hi) / 2.0
        su  = sigma0 * (1.0 + VOL_SHOCK)
        ed  = CALIB_ES * (1.0 - mid)
        pdn = put_price(ed, k0, ES_DTE, su)
        val = max(pdn - p0, 0.0) + p0
        if val < target: lo = mid
        else:            hi = mid
    return (lo + hi) / 2.0

_BASE_SCAN = _calibrate_base_scan()

def es_span(es_price: float, vix: float, existing_strike: float | None = None,
            existing_dte: int | None = None) -> float:
    """
    SPAN estimate for /ES short put.
    If existing_strike/dte provided: re-mark existing position at current (es_price, vix).
    Otherwise: estimate for new 20-delta 45-DTE position.
    """
    scan_pct = _BASE_SCAN * (vix / CALIB_VIX) ** SCAN_EXP
    sigma    = vix / 100.0
    if existing_strike is not None and existing_dte is not None:
        k   = existing_strike
        dte = max(existing_dte, 1)
    else:
        k   = find_strike_for_delta(es_price, ES_DTE, sigma, ES_DELTA, is_call=False)
        dte = ES_DTE
    prem   = put_price(es_price, k, dte, sigma)
    sigma_u = sigma * (1.0 + VOL_SHOCK)
    ed     = es_price * (1.0 - scan_pct)
    pdn    = put_price(ed, k, dte, sigma_u)
    return max(pdn - prem, 0.0) * ES_MULT + prem * ES_MULT


# ── Governance Architectures ──────────────────────────────────────────────────

GovernArch = Literal["arch0", "arch1", "arch2", "arch3"]

@dataclass
class GovernanceState:
    """Runtime state for the governance layer (updated daily)."""
    spx_bp_used:   float = 0.0   # current SPX Credit BP in use (USD)
    es_bp_used:    float = 0.0   # current /ES BP in use (USD, 0 or active SPAN)
    current_nlv:   float = NLV0
    es_open:       bool  = False

    @property
    def total_bp_used(self) -> float:
        return self.spx_bp_used + self.es_bp_used

    @property
    def total_bp_pct(self) -> float:
        return self.total_bp_used / self.current_nlv


def _vix_regime(vix: float) -> str:
    if vix < 15:   return "LOW_VOL"
    if vix < 25:   return "NORMAL"
    if vix < 35:   return "HIGH_VOL"
    return "EXTREME_VOL"


def governance_allows_es_entry(
    arch: GovernArch,
    state: GovernanceState,
    vix: float,
    es_price: float,
) -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    Checks whether governance rules permit a new /ES entry.
    """
    if state.es_open:
        return False, "already_open"

    span_est = es_span(es_price, vix)
    regime   = _vix_regime(vix)
    nlv      = state.current_nlv

    if arch == "arch0":
        return False, "arch0_no_es"

    if arch == "arch1":
        # Simple shared cap: combined BP ≤ 20% NLV
        combined = state.spx_bp_used + span_est
        if combined > nlv * 0.20:
            return False, f"cap_breach_{combined/nlv*100:.1f}pct"
        return True, "ok"

    if arch == "arch2":
        # Dynamic budget with Phase A stress correction
        stress_mult = (1.0 if vix < 22 else
                       1.3 if vix < 30 else
                       1.6 if vix < 40 else 2.0)
        span_stressed = span_est * stress_mult
        # /ES sub-budget: max 8% NLV in LOW_VOL/NORMAL, 4% in HIGH_VOL, 0 in EXTREME
        es_budget = (nlv * 0.08 if regime in ("LOW_VOL", "NORMAL") else
                     nlv * 0.04 if regime == "HIGH_VOL" else 0.0)
        if es_budget == 0.0:
            return False, f"arch2_extreme_vol_blocked"
        if span_stressed > es_budget:
            return False, f"arch2_span_exceeds_budget_{span_stressed:.0f}>{es_budget:.0f}"
        # Also enforce total account cap (35% NLV ceiling per SPEC-084)
        combined = state.spx_bp_used + span_stressed
        if combined > nlv * 0.32:
            return False, f"arch2_total_cap_{combined/nlv*100:.1f}pct"
        return True, "ok"

    if arch == "arch3":
        # Regime-gated: HIGH_VOL+ blocks /ES; LOW_VOL gives /ES priority
        if regime in ("HIGH_VOL", "EXTREME_VOL"):
            return False, f"arch3_regime_blocked_{regime}"
        # In LOW_VOL: relax SPX Credit constraint for /ES entry
        combined = state.spx_bp_used + span_est
        cap = nlv * 0.25 if regime == "LOW_VOL" else nlv * 0.20
        if combined > cap:
            return False, f"arch3_cap_{combined/nlv*100:.1f}pct"
        return True, "ok"

    return False, "unknown_arch"


# ── SPX Credit state loader ───────────────────────────────────────────────────

def build_spx_daily_state(start: str = SPX_START) -> pd.DataFrame:
    """
    Run SPX Credit backtest and build a per-day BP-used series.
    Returns DataFrame with index=date, columns=[spx_bp_used, spx_pnl_cumulative].
    """
    print("  Building SPX Credit daily state (running backtest) …", flush=True)
    from backtest.engine import run_backtest
    from strategy.selector import StrategyParams

    params = StrategyParams()
    try:
        result = run_backtest(
            params=params,
            start_date=start,
            account_size=SPX_ACCOUNT,
        )
    except TypeError:
        result = run_backtest(start_date=start, account_size=SPX_ACCOUNT)

    trades = result.trades
    portfolio_rows = result.portfolio_rows

    # Build per-day BP series from portfolio rows
    rows = []
    for pr in portfolio_rows:
        rows.append({
            "date": pd.Timestamp(pr.date),
            "spx_equity": pr.end_equity,
            "spx_bp_used": pr.bp_used_usd if hasattr(pr, "bp_used_usd") else 0.0,
        })
    df = pd.DataFrame(rows).set_index("date").sort_index()

    # If bp_used_usd not available, reconstruct from trades
    if df["spx_bp_used"].sum() == 0:
        daily_bp: dict[pd.Timestamp, float] = {}
        for t in trades:
            if not (t.entry_date and t.exit_date):
                continue
            try:
                ed = pd.Timestamp(t.entry_date)
                xd = pd.Timestamp(t.exit_date)
                bp = float(t.total_bp or 0)
                d  = ed
                while d <= xd:
                    daily_bp[d] = daily_bp.get(d, 0.0) + bp
                    d += pd.Timedelta(days=1)
            except Exception:
                pass
        df["spx_bp_used"] = pd.Series(daily_bp)
        df["spx_bp_used"] = df["spx_bp_used"].fillna(0.0)

    return df


# ── /ES daily signal ──────────────────────────────────────────────────────────

def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    df = df.copy()
    df.index = idx.normalize()
    return df


def _trend_sig(window: pd.Series, spx_today: float) -> TrendSignal:
    if len(window) < 50:
        return TrendSignal.NEUTRAL
    ma50 = float(window.iloc[-50:].mean())
    atr_raw = _compute_atr14_close(window)
    try:
        atr = float(atr_raw.iloc[-1]) if hasattr(atr_raw, "iloc") else float(atr_raw)
    except Exception:
        return TrendSignal.NEUTRAL
    if atr <= 0.0:
        return TrendSignal.NEUTRAL
    gap = (spx_today - ma50) / atr
    return _classify_trend_atr(gap)


def build_market_series(start: str = SPX_START) -> pd.DataFrame:
    """Build daily market series with SPX, VIX, and trend signal."""
    print("  Building market series (trend signal) …", flush=True)
    vdf = _strip_tz(fetch_vix_history(period="max", interval="1d"))
    sdf = _strip_tz(fetch_spx_history(period="max", interval="1d"))
    merged = pd.DataFrame({"spx": sdf["close"], "vix": vdf["vix"]}).dropna()
    full   = merged.copy()
    merged = merged[merged.index >= pd.Timestamp(start)].copy()

    signals = []
    for date, row in merged.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        window = full[full.index <= date]["spx"].iloc[-200:]
        bullish = (len(window) >= WARMUP and _trend_sig(window, spx) == TrendSignal.BULLISH)
        signals.append({"date": date, "spx": spx, "vix": vix, "bullish": bullish})

    return pd.DataFrame(signals).set_index("date")


# ── /ES Trade simulator ───────────────────────────────────────────────────────

@dataclass
class EsPos:
    entry_date: str
    entry_spx:  float
    entry_vix:  float
    strike:     float
    entry_prem: float
    dte:        int
    contracts:  float
    span:       float


@dataclass
class EsTrade:
    entry_date:   str
    exit_date:    str
    entry_spx:    float
    exit_spx:     float
    entry_vix:    float
    exit_vix:     float
    entry_prem:   float
    exit_prem:    float
    contracts:    float
    pnl:          float
    exit_reason:  str
    span_at_entry: float
    max_span:     float   # max SPAN during hold (SPAN expansion tracking)
    arch:         str
    allowed_by:   str


def simulate_es_trades(
    market:    pd.DataFrame,
    spx_state: pd.DataFrame,
    arch:      GovernArch,
    nlv:       float = NLV0,
) -> list[EsTrade]:
    """
    Simulate /ES short put trades under a given governance architecture.
    """
    trades: list[EsTrade] = []
    pos: EsPos | None     = None
    gov = GovernanceState(current_nlv=nlv)

    for date, row in market.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        dstr = date.strftime("%Y-%m-%d")

        # Update governance state with today's SPX Credit BP
        spx_bp = float(spx_state["spx_bp_used"].get(date, 0.0))
        gov.spx_bp_used   = spx_bp
        gov.es_bp_used    = es_span(spx, vix, pos.strike, pos.dte) if pos else 0.0
        gov.es_open       = pos is not None

        sigma = vix / 100.0

        # ── Manage open /ES position ──────────────────────────────────────────
        if pos:
            pos.dte -= 1
            cur_prem = put_price(spx, pos.strike, max(pos.dte, 0), sigma)
            span_now = es_span(spx, vix, pos.strike, pos.dte)
            pos.span = max(pos.span, span_now)  # track max SPAN during hold

            reason = None
            if   pos.dte <= ES_GAMMA_DTE:                     reason = "gamma_risk"
            elif cur_prem >= pos.entry_prem * ES_STOP_MULT:   reason = "stop_loss"
            elif cur_prem <= pos.entry_prem * ES_PROFIT_PCT:  reason = "profit_target"
            elif pos.dte  <= 0:                               reason = "expiry"

            if reason:
                pnl = (pos.entry_prem - cur_prem) * pos.contracts * ES_MULT
                trades.append(EsTrade(
                    entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx,   exit_spx=spx,
                    entry_vix=pos.entry_vix,   exit_vix=vix,
                    entry_prem=pos.entry_prem, exit_prem=cur_prem,
                    contracts=pos.contracts,   pnl=pnl,
                    exit_reason=reason,
                    span_at_entry=es_span(pos.entry_spx, pos.entry_vix),
                    max_span=pos.span,
                    arch=arch, allowed_by="",
                ))
                pos = None
                gov.es_open   = False
                gov.es_bp_used = 0.0

        # ── Entry attempt ─────────────────────────────────────────────────────
        if pos is None and row["bullish"]:
            allowed, reason = governance_allows_es_entry(arch, gov, vix, spx)
            if allowed:
                k    = find_strike_for_delta(spx, ES_DTE, sigma, ES_DELTA, is_call=False)
                prem = put_price(spx, k, ES_DTE, sigma)
                if prem > 0.5:
                    span0 = es_span(spx, vix)
                    n     = max(nlv * 0.04 / (spx * ES_MULT), 0.1)  # 4% NLV per contract notional
                    pos   = EsPos(
                        entry_date=dstr, entry_spx=spx, entry_vix=vix,
                        strike=k, entry_prem=prem, dte=ES_DTE,
                        contracts=n, span=span0,
                    )
                    gov.es_open    = True
                    gov.es_bp_used = span0

    return trades


# ── Metrics computation ───────────────────────────────────────────────────────

def compute_es_metrics(
    trades: list[EsTrade],
    market: pd.DataFrame,
    nlv:    float = NLV0,
) -> dict:
    if not trades:
        return {
            "n_trades": 0, "win_rate": 0, "ann_roe": 0,
            "sharpe": 0, "max_dd_pct": 0, "cvar_5": 0,
            "worst_trade_pct": 0, "avg_bp_pct": 0,
            "span_breach_days": 0, "max_span_mult": 0,
        }

    total_pnl    = sum(t.pnl for t in trades)
    wins         = [t for t in trades if t.pnl > 0]
    stops        = [t for t in trades if t.exit_reason == "stop_loss"]
    start        = pd.Timestamp(trades[0].entry_date)
    end          = pd.Timestamp(trades[-1].exit_date)
    years        = max((end - start).days / 365.25, 1.0)
    ann_roe      = total_pnl / nlv / years * 100

    pnl_series   = [t.pnl / nlv * 100 for t in trades]
    worst        = min(pnl_series)
    sharpe       = (np.mean(pnl_series) / (np.std(pnl_series) + 1e-9)) * math.sqrt(252 / 45)

    sorted_pnl   = sorted(pnl_series)
    cvar_cut     = max(1, int(len(sorted_pnl) * 0.05))
    cvar         = np.mean(sorted_pnl[:cvar_cut])

    # SPAN breach events: max_span > 1.5x entry span
    span_breaches = sum(1 for t in trades if t.max_span > t.span_at_entry * 1.5)
    max_span_mult = max((t.max_span / max(t.span_at_entry, 1) for t in trades), default=1.0)

    avg_bp_pct = np.mean([t.span_at_entry / nlv * 100 for t in trades])

    # Max drawdown on /ES equity curve
    eq = nlv
    peak = nlv
    max_dd = 0.0
    for t in trades:
        eq += t.pnl
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    return {
        "n_trades":        len(trades),
        "win_rate":        round(len(wins) / len(trades) * 100, 1),
        "stop_rate":       round(len(stops) / len(trades) * 100, 1),
        "total_pnl":       round(total_pnl, 0),
        "ann_roe":         round(ann_roe, 3),
        "sharpe":          round(sharpe, 3),
        "max_dd_pct":      round(max_dd, 2),
        "cvar_5":          round(cvar, 3),
        "worst_trade_pct": round(worst, 3),
        "avg_bp_pct":      round(avg_bp_pct, 2),
        "span_breach_days": span_breaches,
        "max_span_mult":   round(max_span_mult, 2),
    }


def compute_combined_metrics(
    spx_state: pd.DataFrame,
    es_trades: list[EsTrade],
    nlv:       float = NLV0,
) -> dict:
    """Combined account metrics: SPX equity curve + /ES PnL overlay."""
    # Build daily combined equity
    spx_eq = spx_state["spx_equity"].copy()
    es_by_date: dict[pd.Timestamp, float] = {}
    for t in es_trades:
        d = pd.Timestamp(t.exit_date)
        es_by_date[d] = es_by_date.get(d, 0.0) + t.pnl

    combined_eq = spx_eq.copy()
    for d, pnl in es_by_date.items():
        if d in combined_eq.index:
            # Add to equity from that date forward
            combined_eq.loc[d:] += pnl

    # Compute metrics on combined equity curve
    daily_rets = combined_eq.pct_change().dropna()
    if len(daily_rets) < 10:
        return {}

    years = len(daily_rets) / 252
    start_eq = float(combined_eq.iloc[0])
    end_eq   = float(combined_eq.iloc[-1])
    ann_roe  = ((end_eq / start_eq) ** (1 / years) - 1) * 100

    sharpe = float(daily_rets.mean() / (daily_rets.std() + 1e-9) * math.sqrt(252))
    rolling_max = combined_eq.cummax()
    dd_pct = ((combined_eq - rolling_max) / rolling_max * 100)
    max_dd = float(dd_pct.min())

    sorted_dr = daily_rets.sort_values().values
    cvar_cut  = max(1, int(len(sorted_dr) * 0.05))
    cvar      = float(np.mean(sorted_dr[:cvar_cut]) * 100)

    return {
        "combined_ann_roe": round(ann_roe, 3),
        "combined_sharpe":  round(sharpe, 3),
        "combined_max_dd":  round(max_dd, 2),
        "combined_cvar_5":  round(cvar, 3),
        "combined_end_eq":  round(end_eq, 0),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 72)
    print("Q012 PHASE C — Joint Portfolio Simulation: Governance Architecture")
    print("=" * 72)
    print(f"  Window: {SPX_START} → today   NLV: ${NLV0:,.0f}")
    print()

    # ── Load data ────────────────────────────────────────────────────────────
    spx_state = build_spx_daily_state()
    market    = build_market_series()

    n_bullish = int(market["bullish"].sum())
    print(f"  /ES BULLISH trend days: {n_bullish:,} / {len(market):,} "
          f"({n_bullish/len(market)*100:.1f}%)")
    print(f"  SPX Credit data: {len(spx_state):,} days, "
          f"avg BP ${spx_state['spx_bp_used'].mean():,.0f}")
    print()

    # ── Run all architectures ─────────────────────────────────────────────────
    archs: list[GovernArch] = ["arch0", "arch1", "arch2", "arch3"]
    arch_labels = {
        "arch0": "Baseline (SPX only)",
        "arch1": "Additive (simple 20% cap)",
        "arch2": "Dynamic Budget (stress-adj, regime budget)",
        "arch3": "Regime-Gated (HIGH_VOL blocked)",
    }

    results = {}
    for arch in archs:
        print(f"  Simulating {arch_labels[arch]} …", flush=True)
        trades  = simulate_es_trades(market, spx_state, arch)
        metrics = compute_es_metrics(trades, market)
        comb    = compute_combined_metrics(spx_state, trades, NLV0)
        n_blocked = n_bullish - metrics["n_trades"]
        results[arch] = {
            "label":     arch_labels[arch],
            "es_trades": trades,
            "es_m":      metrics,
            "comb":      comb,
            "n_bullish": n_bullish,
            "n_blocked": n_blocked,
        }

    # ── Summary table ─────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print("RESULTS SUMMARY")
    print("=" * 72)

    # Architecture comparison
    rows = []
    for arch, r in results.items():
        em = r["es_m"]
        cm = r["comb"]
        rows.append({
            "Architecture":       r["label"],
            "/ES Trades":         em["n_trades"],
            "Blocked":            r["n_blocked"],
            "/ES Ann ROE%":       em["ann_roe"],
            "/ES WR%":            em.get("win_rate", 0),
            "/ES Stop%":          em.get("stop_rate", 0),
            "SPAN Breaches":      em["span_breach_days"],
            "Max SPAN mult":      em["max_span_mult"],
            "Combined ROE%":      cm.get("combined_ann_roe", "—"),
            "Combined Sharpe":    cm.get("combined_sharpe", "—"),
            "Combined MaxDD%":    cm.get("combined_max_dd", "—"),
            "Combined CVaR5%":    cm.get("combined_cvar_5", "—"),
        })

    df_sum = pd.DataFrame(rows)
    print(df_sum.to_string(index=False))

    # ── Detailed /ES metrics per architecture ─────────────────────────────────
    print()
    print("─" * 72)
    print("DETAILED /ES METRICS")
    print("─" * 72)
    for arch, r in results.items():
        if arch == "arch0":
            continue
        em = r["es_m"]
        if em["n_trades"] == 0:
            print(f"\n{r['label']}: no trades")
            continue
        print(f"\n{r['label']}:")
        print(f"  Trades: {em['n_trades']}  WR: {em['win_rate']}%  Stop: {em['stop_rate']}%")
        print(f"  Total PnL: ${em['total_pnl']:,.0f}  Ann ROE: {em['ann_roe']}%")
        print(f"  Sharpe: {em['sharpe']}  MaxDD: {em['max_dd_pct']}%  CVaR5: {em['cvar_5']}%")
        print(f"  Worst trade: {em['worst_trade_pct']}% acct  Avg BP: {em['avg_bp_pct']}%")
        print(f"  SPAN breaches (>1.5x): {em['span_breach_days']}  Max SPAN mult: {em['max_span_mult']}x")

    # ── Marginal /ES contribution ─────────────────────────────────────────────
    print()
    print("─" * 72)
    print("MARGINAL /ES ROE CONTRIBUTION (vs Arch-0 Baseline)")
    print("─" * 72)
    base_roe = results["arch0"]["comb"].get("combined_ann_roe", 0)
    for arch in ["arch1", "arch2", "arch3"]:
        r    = results[arch]
        roe  = r["comb"].get("combined_ann_roe", base_roe)
        delta = round(roe - base_roe, 3) if isinstance(roe, float) else "—"
        bp_pct = r["es_m"]["avg_bp_pct"]
        n    = r["es_m"]["n_trades"]
        print(f"  {r['label'][:38]:38s}: +{delta}pp  ({n} trades, avg {bp_pct}% BP)")

    # ── Governance recommendation ─────────────────────────────────────────────
    print()
    print("─" * 72)
    print("GOVERNANCE RECOMMENDATION")
    print("─" * 72)

    # Find best architecture by combined ROE vs CVaR tradeoff
    best_arch = max(
        ["arch1", "arch2", "arch3"],
        key=lambda a: (
            results[a]["comb"].get("combined_ann_roe", 0)
            - abs(results[a]["es_m"]["cvar_5"])
            - results[a]["es_m"]["span_breach_days"] * 0.01
        )
    )
    print(f"  Recommended: {arch_labels[best_arch]}")
    print()
    er = results[best_arch]
    em = er["es_m"]
    print(f"  /ES trades enabled:   {em['n_trades']}  ({em['n_trades']/n_bullish*100:.1f}% of BULLISH days)")
    print(f"  /ES blocked:          {er['n_blocked']}  ({er['n_blocked']/n_bullish*100:.1f}%)")
    print(f"  SPAN breach events:   {em['span_breach_days']}")
    print(f"  Marginal ROE add:     +{results[best_arch]['comb'].get('combined_ann_roe',0)-base_roe:.3f}pp")
    print()
    print("  Design principle:")
    if best_arch == "arch2":
        print("  → Dynamic BP budget with stress correction is the optimal architecture.")
        print("    It balances /ES alpha capture with SPAN risk management.")
        print("    Governance layer should sit ABOVE strategy execution (not patched in).")
    elif best_arch == "arch3":
        print("  → Regime-gated architecture maximises risk-adjusted returns.")
        print("    HIGH_VOL blocking prevents the 100% cap-breach regime identified in Phase B.")
    else:
        print("  → Simple additive architecture is sufficient given the data.")


if __name__ == "__main__":
    run()
