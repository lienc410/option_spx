"""Q071 — shared V2f engine with gate / cadence-mode / stop hooks.

Replicates research.strategies.ES_puts.backtest._run_phase2_v2f_on_frame
with three configurable extensions used across P2, P3, P4, P5:

  - gate_fn(ctx): bool — entry gate based on (date, vix, ivp252, vix5_avg, n_active)
  - cadence_mode: "hard_skip" (A), "delay_retry" (B), "size_scale" (C)
  - stop_mult_override: float | None — overrides V2F_STOP_MULT for P4

Returns: dict of {trades, daily_rows, gate_eval_log, n_decline_gate, ...}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

import math
import numpy as np
import pandas as pd

from research.strategies.ES_puts.backtest import (
    _load_data, _trend, _bp_per_contract, _make_row,
    V2F_ENTRY_DTE, V2F_EXIT_DTE, V2F_ENTRY_FREQ, V2F_MAX_SLOTS,
    V2F_CLUSTER_THRESHOLD, V2F_CLUSTER_ENTRY_FREQ,
    V2F_STOP_MULT, V2F_PROFIT_TARGET, TARGET_DELTA,
    SPX_MULTIPLIER, WARMUP_DAYS, P2_INITIAL_EQUITY, P2_N_CONTRACTS,
)
from backtest.pricer import find_strike_for_delta, put_price
from backtest.metrics_portfolio import compute_portfolio_metrics
from signals.trend import TrendSignal


# ── IVP_252 series ────────────────────────────────────────────────────

def compute_ivp252(vix_series: pd.Series) -> pd.Series:
    def w(arr):
        cur = arr[-1]
        return float((arr[:-1] < cur).mean() * 100.0)
    return vix_series.rolling(252).apply(w, raw=True)


# ── Entry context passed to gate_fn ──────────────────────────────────

@dataclass
class EntryCtx:
    date:       pd.Timestamp
    vix:        float
    ivp252:     float
    vix5_avg:   float       # prior 5-TD VIX average
    n_active:   int


GateFn = Callable[[EntryCtx], bool]


def gate_pass_all(_ctx: EntryCtx) -> bool:
    return True


# ── Bootstrap helpers (seed-stable per SPEC) ─────────────────────────

def _bootstrap_seed_stability_v2(
    pnl_series: list[float],
    *,
    initial_equity: float,
    years: float,
    seeds: int = 20,
    block_size: int = 250,
    n_boot: int = 2000,
) -> dict:
    if not pnl_series or years <= 0:
        return {"sig_rate": 0.0, "ci_lo": float("nan"), "seed_count": seeds, "block_size": block_size}

    arr = np.asarray(pnl_series, dtype=float)
    n = len(arr)
    if n < 10:
        return {"sig_rate": 0.0, "ci_lo": float("nan"), "seed_count": seeds, "block_size": block_size}

    sig_count = 0
    ci_los: list[float] = []
    for seed in range(1, seeds + 1):
        rng = np.random.default_rng(seed=seed)
        boot_means = np.empty(n_boot)
        max_start = max(1, n - block_size + 1)
        for idx in range(n_boot):
            n_blocks = math.ceil(n / block_size)
            starts = rng.integers(0, max_start, size=n_blocks)
            sample = np.concatenate([arr[s : s + block_size] for s in starts])[:n]
            boot_means[idx] = sample.mean()
        ci_lo = float(np.percentile(boot_means, 2.5))
        ci_hi = float(np.percentile(boot_means, 97.5))
        if ci_lo > 0:
            sig_count += 1
        ann_frac = (ci_lo * (n / years)) / initial_equity
        ci_los.append(ann_frac)
    return {
        "sig_rate":   sig_count / seeds,
        "ci_lo":      float(np.median(ci_los)),
        "seed_count": seeds,
        "block_size": block_size,
    }


# ── Main parameterised engine ────────────────────────────────────────

def run_v2f_with_gate(
    *,
    gate_fn:           GateFn = gate_pass_all,
    cadence_mode:      Literal["hard_skip", "delay_retry", "size_scale"] = "hard_skip",
    delay_max_td:      int = 5,         # mode B: re-check daily up to this many TD
    size_fail_scale:   float = 0.5,     # mode C: size when gate fails
    stop_mult:         float = V2F_STOP_MULT,
    profit_target:     float = V2F_PROFIT_TARGET,
    start_date:        str = "2000-01-01",
    end_date:          Optional[str] = None,
    enable_m1:         bool = True,
    apply_trend_gate:  bool = True,
    label:             str = "v2f_gated",
) -> dict:
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(start_date)]
    if end_date:
        sim = sim[sim.index <= pd.Timestamp(end_date)]

    ivp252 = compute_ivp252(data["vix"])
    vix5_avg_series = data["vix"].rolling(5).mean().shift(1)

    equity = P2_INITIAL_EQUITY
    peak_eq = P2_INITIAL_EQUITY
    daily_rows = []
    trades = []
    positions: dict[int, dict] = {}
    next_id = 0
    day_counter = 0
    days_since_entry = V2F_ENTRY_FREQ

    # Delay-retry state (mode B)
    delay_pending = False
    delay_days_remaining = 0

    n_eval_decisions = 0
    n_pass_gate = 0
    n_fail_gate = 0
    active_slot_history: list[int] = []
    bp_peak_pct_nlv = 0.0

    exp_id = f"q071_{label}"

    for date, row in sim.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        sig = vix / 100.0
        dstr = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0
        day_counter += 1
        days_since_entry += 1

        # Trend gate (V2f baseline behavior)
        window = full_spx[full_spx.index <= date].iloc[-200:]
        warmed = len(window) >= WARMUP_DAYS
        trend_ok = True
        if apply_trend_gate and warmed:
            trend_ok = (_trend(window, spx) == TrendSignal.BULLISH)

        # ─── Exit logic ───────────────────────────────────────────
        to_close = []
        for pid, pos in positions.items():
            pos["expiry_dte"] -= 1
            cur_val = put_price(spx, pos["strike"], max(pos["expiry_dte"], 0), sig)
            daily_pnl += (pos["prev_val"] - cur_val) * pos["contracts"] * SPX_MULTIPLIER
            reason = None
            if pos["expiry_dte"] <= V2F_EXIT_DTE:
                reason = "ladder_exit"
            elif cur_val >= pos["stop_premium"]:
                reason = "stop_loss"
            elif cur_val <= pos["profit_premium"]:
                reason = "profit_target"
            elif pos["expiry_dte"] <= 0:
                reason = "expiry"
            if reason:
                pnl_total = (pos["entry_premium"] - cur_val) * pos["contracts"] * SPX_MULTIPLIER
                trades.append({
                    "id":             pos["id"],
                    "entry_date":     pos["entry_date"],
                    "exit_date":      dstr,
                    "entry_spx":      pos["entry_spx"],
                    "exit_spx":       spx,
                    "entry_vix":      pos["entry_vix"],
                    "entry_premium":  pos["entry_premium"],
                    "exit_premium":   cur_val,
                    "exit_reason":    reason,
                    "contracts":      pos["contracts"],
                    "pnl":            pnl_total,
                    "bp_used":        pos["bp_used"],
                    "ivp252_entry":   pos["ivp252_entry"],
                    "vix5_avg_prior": pos["vix5_avg_prior"],
                    "size_scale":     pos["size_scale"],
                })
                to_close.append(pid)
            else:
                pos["prev_val"] = cur_val
        for pid in to_close:
            del positions[pid]

        # ─── Entry decision ───────────────────────────────────────
        n_active = len(positions)
        active_slot_history.append(n_active)
        if enable_m1 and n_active >= V2F_CLUSTER_THRESHOLD:
            entry_freq = V2F_CLUSTER_ENTRY_FREQ
        else:
            entry_freq = V2F_ENTRY_FREQ
        cadence_mode_rel = enable_m1  # use relative cadence under M1 mode
        cadence_ok = (
            days_since_entry >= entry_freq
            if cadence_mode_rel
            else day_counter % entry_freq == 0
        )

        would_enter = warmed and trend_ok and cadence_ok and n_active < V2F_MAX_SLOTS

        # Mode B (delay_retry): if we are mid-delay, force daily check
        if cadence_mode == "delay_retry" and delay_pending and trend_ok and n_active < V2F_MAX_SLOTS and warmed:
            would_enter = True

        size_scale_applied = 1.0
        if would_enter:
            n_eval_decisions += 1
            cur_ivp = float(ivp252.loc[date]) if date in ivp252.index else float("nan")
            cur_v5  = float(vix5_avg_series.loc[date]) if date in vix5_avg_series.index else float("nan")
            ctx = EntryCtx(date=date, vix=vix, ivp252=cur_ivp, vix5_avg=cur_v5, n_active=n_active)
            gate_ok = gate_fn(ctx)
            if gate_ok:
                n_pass_gate += 1
                size_scale_applied = 1.0
                # reset delay state
                delay_pending = False
                delay_days_remaining = 0
            else:
                n_fail_gate += 1
                if cadence_mode == "hard_skip":
                    would_enter = False
                elif cadence_mode == "delay_retry":
                    # Start (or continue) delay window
                    if not delay_pending:
                        delay_pending = True
                        delay_days_remaining = delay_max_td
                    else:
                        delay_days_remaining -= 1
                    would_enter = False
                    if delay_days_remaining <= 0:
                        # Give up — wait for next normal cadence
                        delay_pending = False
                        delay_days_remaining = 0
                elif cadence_mode == "size_scale":
                    # Enter at reduced size
                    size_scale_applied = size_fail_scale
                    would_enter = True
                else:
                    raise ValueError(f"unknown cadence_mode {cadence_mode}")

        if would_enter:
            k = find_strike_for_delta(spx, V2F_ENTRY_DTE, sig, TARGET_DELTA, False)
            prem = put_price(spx, k, V2F_ENTRY_DTE, sig)
            if prem > 0.5:
                next_id += 1
                n = float(P2_N_CONTRACTS) * size_scale_applied
                bp_per = _bp_per_contract(spx, k, prem)
                cur_ivp_open = float(ivp252.loc[date]) if date in ivp252.index else float("nan")
                cur_v5_open  = float(vix5_avg_series.loc[date]) if date in vix5_avg_series.index else float("nan")
                positions[next_id] = {
                    "id":                next_id,
                    "entry_date":        dstr,
                    "expiry_dte":        V2F_ENTRY_DTE,
                    "strike":            k,
                    "entry_spx":         spx,
                    "entry_vix":         vix,
                    "entry_premium":     prem,
                    "contracts":         n,
                    "bp_used":           n * bp_per,
                    "stop_premium":      prem * stop_mult,
                    "profit_premium":    prem * profit_target,
                    "prev_val":          prem,
                    "ivp252_entry":      cur_ivp_open,
                    "vix5_avg_prior":    cur_v5_open,
                    "size_scale":        size_scale_applied,
                }
                if cadence_mode_rel:
                    days_since_entry = 0

        # ─── Daily portfolio row ──────────────────────────────────
        bp_active = sum(p["bp_used"] for p in positions.values())
        bp_peak_pct_nlv = max(bp_peak_pct_nlv, bp_active / P2_INITIAL_EQUITY)

        from backtest.portfolio import DailyPortfolioRow
        end_eq = equity + daily_pnl
        peak_eq = max(peak_eq, end_eq)
        dd = (end_eq - peak_eq) / peak_eq if peak_eq else 0.0
        ret = daily_pnl / equity if equity else 0.0
        dr = DailyPortfolioRow(
            date=dstr, start_equity=equity, end_equity=end_eq,
            daily_return_gross=ret, daily_return_net=ret,
            realized_pnl=0.0, unrealized_pnl_delta=daily_pnl, total_pnl=daily_pnl,
            bp_used=bp_active, bp_headroom=max(equity - bp_active, 0.0),
            short_gamma_count=len(positions), open_positions=len(positions),
            regime="NORMAL", vix=vix, cumulative_equity=end_eq, drawdown=dd,
            experiment_id=exp_id,
        )
        daily_rows.append(dr)
        equity = end_eq

    # ─── Aggregate metrics ──────────────────────────────────────
    pm = compute_portfolio_metrics(daily_rows).to_dict() if daily_rows else {}
    pnl_list = [t["pnl"] for t in trades]
    years = (pm.get("total_days", 0) or 0) / 252

    # geometric ann return
    final_eq = daily_rows[-1].cumulative_equity if daily_rows else P2_INITIAL_EQUITY
    ann_roe_geo = (final_eq / P2_INITIAL_EQUITY) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    # worst trade as % NLV
    worst_pnl_nlv = (min(pnl_list) / P2_INITIAL_EQUITY) if pnl_list else 0.0

    # avg/peak active slots
    avg_slots = float(np.mean(active_slot_history)) if active_slot_history else 0.0
    peak_slots = int(max(active_slot_history)) if active_slot_history else 0

    return {
        "label":            label,
        "n_trades":         len(trades),
        "n_eval":           n_eval_decisions,
        "n_pass_gate":      n_pass_gate,
        "n_fail_gate":      n_fail_gate,
        "ann_roe_geo":      ann_roe_geo,
        "sharpe":           pm.get("daily_sharpe", 0.0),
        "sortino":          pm.get("daily_sortino", 0.0),
        "max_drawdown":     pm.get("max_drawdown", 0.0),
        "worst_pnl_nlv":    worst_pnl_nlv,
        "v1_pass":          worst_pnl_nlv >= -0.15,
        "avg_slots":        avg_slots,
        "peak_slots":       peak_slots,
        "peak_bp_pct_nlv":  bp_peak_pct_nlv,
        "trades":           trades,
        "daily_rows":       daily_rows,
        "pnl_per_bp_day":   pm.get("pnl_per_bp_day", 0.0),
        "years":            years,
        "final_equity":     final_eq,
        "total_days":       pm.get("total_days", 0),
    }


def run_bootstrap(result: dict, seeds: int = 20, block_size: int = 250) -> dict:
    pnls = [t["pnl"] for t in result["trades"]]
    return _bootstrap_seed_stability_v2(
        pnls,
        initial_equity=P2_INITIAL_EQUITY,
        years=result["years"],
        seeds=seeds,
        block_size=block_size,
    )
