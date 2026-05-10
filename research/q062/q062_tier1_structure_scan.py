"""Q062 Tier 1 — Structure / Strike / Tenor Feasibility Scan.

Question: Are Q042 baseline params (ATM/+5% vertical, 90 DTE) Pareto optimal,
or can we beat them on ≥2 of {ann_ROE, worst_trade, max_DD} via:
  S1 vertical with different width
  S2 naked long call (uncapped upside)
  S3 ITM call (high delta leverage)

We test 4 variants per sleeve vs baseline. Same trigger logic (dd4 lenient
for A, dd15+MA10 reclaim for B). Same 10% sizing per sleeve. Same BS+skew+term
pricing.

Pass bar (Tier 1 → Tier 2 promotion):
  Any variant beats sleeve baseline on ≥ 2 of:
    - ann ROE ≥ +1.0pp
    - worst trade ≥ +5pp (less negative)
    - max DD ≥ +3pp (less negative)

Metrics pack (per PM standing requirement):
  n / win_rate / ann_ROE / max_dd / worst_trade / median_winner / median_loser
  / Sharpe / marginal $/BP-day / CVaR_5% / disaster_window 2008/2020/2022

Caveat: naked call broker-vs-model pricing error is roughly 2x vertical's
(each leg error doesn't cancel). F4 validated 5.65% median delta for vertical;
naked call estimate ~10-12%. Relative ranking still reliable for Tier 1
feasibility, but absolute numbers should be discounted.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[2]
SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"

START = "2007-01-01"
END = "2026-05-10"
SIZING_PCT = 0.10
NLV_SEED = 100_000.0
RFR = 0.04


# ── Pricing (replicated from backtest/q042_engine.py) ────────────────────────

def _term_mult(dte: int) -> float:
    if dte <= 45: return 1.10
    if dte <= 120: return 1.00
    return 0.95


def _skew_mult(moneyness: float) -> float:
    if moneyness >= 1.0:
        delta = min(moneyness - 1.0, 0.10)
        return 1.0 - 1.5 * delta
    delta = min(1.0 - moneyness, 0.10)
    return 1.0 + 1.5 * delta


def _bs_call(S: float, K: float, T: float, sigma: float, r: float = RFR) -> float:
    if T <= 0: return max(0.0, S - K)
    if sigma <= 0: return max(0.0, S - K * np.exp(-r * T))
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def _bs_call_delta(S: float, K: float, T: float, sigma: float, r: float = RFR) -> float:
    if T <= 0: return 1.0 if S > K else 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return float(norm.cdf(d1))


def _price_call_skewed(S: float, K: float, vix: float, dte: int) -> float:
    sigma_atm = max(vix / 100.0, 0.10) * _term_mult(dte)
    sigma_k = sigma_atm * _skew_mult(K / S)
    T = dte / 365
    return _bs_call(S, K, T, sigma_k)


def _price_vertical(S: float, K_long: float, K_short: float, vix: float, dte: int) -> float:
    return max(0.0, _price_call_skewed(S, K_long, vix, dte) - _price_call_skewed(S, K_short, vix, dte))


# ── Trigger detection (replicated from research methodology) ─────────────────

def _find_triggers_ddath(ddath: pd.Series, thr: float, rearm_at: float) -> pd.DatetimeIndex:
    triggers = []
    armed = True
    for dt, dd in ddath.items():
        if armed and dd <= -thr:
            triggers.append(dt)
            armed = False
        elif not armed and dd >= rearm_at:
            armed = True
    return pd.DatetimeIndex(triggers)


def _apply_no_overlap(entries: pd.DatetimeIndex, dte: int) -> pd.DatetimeIndex:
    if len(entries) == 0: return entries
    kept = [entries[0]]
    last_close = entries[0] + pd.Timedelta(days=dte)
    for e in entries[1:]:
        if e >= last_close:
            kept.append(e)
            last_close = e + pd.Timedelta(days=dte)
    return pd.DatetimeIndex(kept)


def _find_sleeve_b_entries(
    dd15_crossings: pd.DatetimeIndex, close: pd.Series, ma10: pd.Series,
    trading_index: pd.DatetimeIndex, watch_days: int = 30,
) -> pd.DatetimeIndex:
    entries = []
    for crossing in dd15_crossings:
        try:
            cross_i = trading_index.get_loc(crossing)
        except KeyError:
            continue
        for j in range(cross_i + 1, min(cross_i + watch_days + 1, len(trading_index))):
            c = float(close.iloc[j])
            m = float(ma10.iloc[j]) if not pd.isna(ma10.iloc[j]) else c
            if c > m:
                entries.append(trading_index[j])
                break
    return pd.DatetimeIndex(entries)


# ── Variant config ────────────────────────────────────────────────────────────

@dataclass
class Variant:
    name: str
    structure: str           # "vertical" | "naked_call"
    long_offset_pct: float   # 0.00 = ATM, -0.05 = ITM 5%, +0.025 = OTM 2.5%
    short_offset_pct: float | None  # None for naked; e.g. 0.05 for ATM/+5% vertical
    dte: int


VARIANTS_A = [
    Variant("baseline_5pct_90D",   "vertical",   0.00,  0.05,  90),
    Variant("S1_2.5pct_60D",        "vertical",   0.00,  0.025, 60),
    Variant("S1_10pct_90D",         "vertical",   0.00,  0.10,  90),
    Variant("S2_naked_ATM_60D",     "naked_call", 0.00,  None,  60),
    Variant("S3_ITM5pct_60D",       "naked_call", -0.05, None,  60),
]
VARIANTS_B = [
    Variant("baseline_5pct_90D",   "vertical",   0.00,  0.05,  90),
    Variant("S1_15pct_120D",        "vertical",   0.00,  0.15,  120),
    Variant("S1_5pct_60D",          "vertical",   0.00,  0.05,  60),
    Variant("S2_naked_ATM_120D",    "naked_call", 0.00,  None,  120),
    Variant("S3_ITM5pct_120D",      "naked_call", -0.05, None,  120),
]


# ── Backtest one variant ──────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    pnl_pct_debit: float    # (payoff - debit) / debit
    debit_ps: float
    payoff_ps: float
    bp_days: int            # capital occupied days


def _run_variant(df: pd.DataFrame, signal_dates: pd.DatetimeIndex, variant: Variant) -> list[TradeRecord]:
    """Walk forward executing variant's structure on each signal date.

    Same no-overlap rule applied via signal_dates already filtered.
    Each trade: T+1 open entry, hold to expiry (cash settlement at close).
    """
    trades = []
    idx = df.index
    for sig in signal_dates:
        try:
            i = idx.get_loc(sig)
        except KeyError:
            continue
        if i + 1 >= len(df): continue
        S_signal = float(df["close"].iloc[i])
        S_entry  = float(df["open"].iloc[i + 1])
        vix      = float(df["vix"].iloc[i]) if not pd.isna(df["vix"].iloc[i]) else 20.0

        K_long = S_signal * (1.0 + variant.long_offset_pct)
        K_short = S_signal * (1.0 + variant.short_offset_pct) if variant.short_offset_pct is not None else None

        if variant.structure == "vertical":
            debit = _price_vertical(S_entry, K_long, K_short, vix, variant.dte)
        else:  # naked_call
            debit = _price_call_skewed(S_entry, K_long, vix, variant.dte)

        if debit <= 0: continue

        # Exit: walk forward to find first index >= entry_date + dte calendar days
        entry_dt = idx[i + 1]
        target_dt = entry_dt + pd.Timedelta(days=variant.dte)
        future = idx[idx >= target_dt]
        if len(future) == 0: continue
        exit_dt = future[0]
        S_expiry = float(df.loc[exit_dt, "close"])

        long_payoff = max(0.0, S_expiry - K_long)
        if K_short is not None:
            short_payoff = max(0.0, S_expiry - K_short)
            payoff = long_payoff - short_payoff
        else:
            payoff = long_payoff

        pnl_pct_debit = (payoff - debit) / debit
        bp_days = (exit_dt - entry_dt).days

        trades.append(TradeRecord(
            entry_date=entry_dt, exit_date=exit_dt,
            pnl_pct_debit=pnl_pct_debit, debit_ps=debit, payoff_ps=payoff,
            bp_days=bp_days,
        ))
    return trades


# ── Metrics pack ──────────────────────────────────────────────────────────────

@dataclass
class Metrics:
    n: int
    win_rate_pct: float
    ann_ROE_pct: float
    max_dd_pct: float
    worst_trade_pct: float
    median_winner_pct: float
    median_loser_pct: float
    sharpe: float
    marginal_dollar_per_bp_day: float
    cvar_5pct: float
    disaster_2008: float
    disaster_2020: float
    disaster_2022: float


def _compute_metrics(trades: list[TradeRecord], years: float) -> Metrics:
    if not trades:
        return Metrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    # Account-level PnL using same convention as q042_engine:
    # account_pct per trade = (pnl_pct_debit) * sizing_pct
    account_pcts = np.array([t.pnl_pct_debit * SIZING_PCT for t in trades])
    pnl_pct_debit = np.array([t.pnl_pct_debit for t in trades])

    wins = pnl_pct_debit > 0
    losses = pnl_pct_debit < 0
    total_pnl_pct = float(account_pcts.sum() * 100)
    ann = total_pnl_pct / years

    # equity curve & max DD
    equity = np.cumprod(1 + account_pcts)
    equity = np.insert(equity, 0, 1.0)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min() * 100)

    worst = float(pnl_pct_debit.min() * SIZING_PCT * 100)
    med_win = float(np.median(pnl_pct_debit[wins]) * SIZING_PCT * 100) if wins.any() else 0.0
    med_loss = float(np.median(pnl_pct_debit[losses]) * SIZING_PCT * 100) if losses.any() else 0.0

    # Sharpe: daily-equivalent. Each trade returns over avg ~bp_days. Approximate.
    # Convert per-trade returns to daily: r_daily = (1+r)^(1/bp_days) - 1
    bp_days = np.array([max(t.bp_days, 1) for t in trades])
    daily_rets = (1 + account_pcts) ** (1.0 / bp_days) - 1
    sharpe = float(daily_rets.mean() / daily_rets.std() * np.sqrt(252)) if daily_rets.std() > 0 else 0.0

    # marginal $/BP-day = total PnL $ / total BP-days occupied
    # (PnL in $: using NLV_SEED * account_pct)
    pnl_dollars = float((account_pcts * NLV_SEED).sum())
    bp_dollar_days = float(sum(t.debit_ps * 100 * t.bp_days for t in trades))  # rough $-day proxy
    marg_dpbd = pnl_dollars / bp_dollar_days if bp_dollar_days > 0 else 0.0

    # CVaR 5%
    sorted_pcts = np.sort(pnl_pct_debit * SIZING_PCT * 100)
    cvar_n = max(1, int(len(sorted_pcts) * 0.05))
    cvar = float(sorted_pcts[:cvar_n].mean())

    # Disaster windows
    def _window_pnl(start, end):
        in_w = [t for t in trades if pd.Timestamp(start) <= t.entry_date <= pd.Timestamp(end)]
        return float(sum(t.pnl_pct_debit * SIZING_PCT * 100 for t in in_w))

    return Metrics(
        n=len(trades),
        win_rate_pct=float(wins.mean() * 100),
        ann_ROE_pct=ann,
        max_dd_pct=max_dd,
        worst_trade_pct=worst,
        median_winner_pct=med_win,
        median_loser_pct=med_loss,
        sharpe=sharpe,
        marginal_dollar_per_bp_day=marg_dpbd,
        cvar_5pct=cvar,
        disaster_2008=_window_pnl("2008-09-01", "2009-03-31"),
        disaster_2020=_window_pnl("2020-02-15", "2020-04-30"),
        disaster_2022=_window_pnl("2022-01-01", "2022-12-31"),
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def _load_data() -> pd.DataFrame:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    spx.columns = [c.lower() for c in spx.columns]
    spx["vix"] = vix["Close"].reindex(spx.index).ffill()
    spx = spx.loc[START:END].copy()
    spx.dropna(subset=["close", "open"], inplace=True)
    return spx


def _build_signals(df: pd.DataFrame, dte_for_overlap: int) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """Build sleeve A and sleeve B signal date sets, applying no-overlap with given DTE."""
    ath = df["close"].cummax()
    ddath = df["close"] / ath - 1.0
    ma10 = df["close"].rolling(10).mean()

    raw_a = _find_triggers_ddath(ddath, 0.04, -0.02)
    sig_a = _apply_no_overlap(raw_a, dte_for_overlap)

    raw_b_cross = _find_triggers_ddath(ddath, 0.15, -0.02)
    raw_b_entry = _find_sleeve_b_entries(raw_b_cross, df["close"], ma10, df.index, 30)
    sig_b = _apply_no_overlap(raw_b_entry, dte_for_overlap)
    return sig_a, sig_b


def _print_table(name: str, results: list[tuple[Variant, Metrics]]) -> None:
    print(f"\n=== Sleeve {name} ===")
    print(f"{'variant':<26} | {'n':>3} | {'WR%':>5} | {'AnnROE%':>8} | "
          f"{'MaxDD%':>7} | {'Worst%':>7} | {'MedWin%':>8} | {'MedLoss%':>8} | "
          f"{'Sharpe':>6} | {'$/BPd':>7} | {'CVaR5%':>7} | {'2008':>6} | {'2020':>6} | {'2022':>6}")
    print("-" * 165)
    for v, m in results:
        print(f"{v.name:<26} | {m.n:>3d} | {m.win_rate_pct:>4.0f}% | {m.ann_ROE_pct:>+7.2f}% | "
              f"{m.max_dd_pct:>+6.1f}% | {m.worst_trade_pct:>+6.1f}% | "
              f"{m.median_winner_pct:>+7.2f}% | {m.median_loser_pct:>+7.2f}% | "
              f"{m.sharpe:>+5.2f} | {m.marginal_dollar_per_bp_day*1e6:>6.2f} | "
              f"{m.cvar_5pct:>+6.1f}% | {m.disaster_2008:>+5.1f}% | "
              f"{m.disaster_2020:>+5.1f}% | {m.disaster_2022:>+5.1f}%")


def _verdict(name: str, results: list[tuple[Variant, Metrics]]) -> tuple[str, list[str]]:
    baseline = next((m for v, m in results if v.name.startswith("baseline")), None)
    if baseline is None:
        return "FAIL", ["no baseline"]
    promotions = []
    for v, m in results:
        if v.name.startswith("baseline"): continue
        wins = 0
        notes = []
        if m.ann_ROE_pct - baseline.ann_ROE_pct >= 1.0:
            wins += 1
            notes.append(f"ann +{m.ann_ROE_pct - baseline.ann_ROE_pct:.2f}pp")
        if m.worst_trade_pct - baseline.worst_trade_pct >= 5.0:
            wins += 1
            notes.append(f"worst +{m.worst_trade_pct - baseline.worst_trade_pct:.1f}pp")
        if m.max_dd_pct - baseline.max_dd_pct >= 3.0:
            wins += 1
            notes.append(f"DD +{m.max_dd_pct - baseline.max_dd_pct:.1f}pp")
        if wins >= 2:
            promotions.append(f"  Sleeve {name}: {v.name} → PASS ({wins}/3) [{', '.join(notes)}]")
    return ("PASS" if promotions else "FAIL"), promotions


def main() -> None:
    print(f"Q062 Tier 1 — Structure / Strike / Tenor Feasibility Scan")
    print(f"Window: {START} → {END}")
    df = _load_data()
    years = (df.index.max() - df.index.min()).days / 365.25

    results_a = []
    for v in VARIANTS_A:
        sig_a, _ = _build_signals(df, v.dte)
        trades = _run_variant(df, sig_a, v)
        m = _compute_metrics(trades, years)
        results_a.append((v, m))

    results_b = []
    for v in VARIANTS_B:
        _, sig_b = _build_signals(df, v.dte)
        trades = _run_variant(df, sig_b, v)
        m = _compute_metrics(trades, years)
        results_b.append((v, m))

    _print_table("A (dd4 lenient)", results_a)
    _print_table("B (dd15 + MA10 reclaim)", results_b)

    print("\n=== Tier 1 Verdict ===")
    print("Pass bar: any variant beats sleeve baseline on ≥ 2/3 of "
          "{ann_ROE +1.0pp, worst_trade +5pp, max_dd +3pp}")
    verdict_a, prom_a = _verdict("A", results_a)
    verdict_b, prom_b = _verdict("B", results_b)
    print(f"\n  Sleeve A: {verdict_a}")
    for p in prom_a: print(p)
    print(f"\n  Sleeve B: {verdict_b}")
    for p in prom_b: print(p)
    if verdict_a == "PASS" or verdict_b == "PASS":
        print("\n→ Promote to Tier 2 grid scan (sleeve(s) marked PASS).")
    else:
        print("\n→ Baseline already Pareto. Q062 closure recommended.")


if __name__ == "__main__":
    main()
