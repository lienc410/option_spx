"""
Q064 P3 — V3-A (Broken-Wing IC_HV) vs 普通 BPS_HV Counterfactual
2026-05-11

在 15 个 aftermath=True 入场日上，对比两种结构：

V3-A（现行 aftermath routing，来自 selector.py SPEC-064）：
  Iron Condor HV broken-wing structure
  Put leg:  SELL PUT δ0.12, BUY PUT δ0.08  (DTE=45)
  Call leg: SELL CALL δ0.12, BUY CALL δ0.04  (DTE=45)

普通 BPS_HV（历史实际执行结构，counterfactual）：
  SELL PUT δ0.20, BUY PUT δ0.10  (DTE=35)

定价方法：
  - Entry: BS put/call，σ = max(VIX/100, 0.10) × term_multiplier(DTE)，r=0.04
  - Exit: BS mid-price at actual exit_date（用 remaining DTE 和 exit-date VIX 重新定价）
    这重现了实际的 60%/21DTE 平仓，包括亏损笔的早期止损

  注意：exit VIX 来自 yfinance ^VIX 历史数据

BP 计算（IC/BPS）：
  BPS_HV: BP = spread_width × 100 × contracts（单 spread，max loss 明确）
  V3-A IC: BP = max(put_wing_width, call_wing_width) × 100 × contracts
            (IC PM BP 取两翼宽度最大者，与 tastytrade/TIMS 标准一致)
"""

import os
import sys
import math
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import brentq
from scipy.stats import norm

warnings.filterwarnings("ignore")

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 常量 ─────────────────────────────────────────────────────────────────────
R = 0.04
CONTRACTS_MULTIPLIER = 100

# BPS_HV 参数（历史实际执行，selector.py StrategyParams）
BPS_HV_SHORT_DELTA = 0.20
BPS_HV_LONG_DELTA  = 0.10
BPS_HV_DTE         = 35

# V3-A 参数（selector.py SPEC-064 broken-wing IC_HV）
V3A_PUT_SHORT_DELTA  = 0.12
V3A_PUT_LONG_DELTA   = 0.08
V3A_CALL_SHORT_DELTA = 0.12
V3A_CALL_LONG_DELTA  = 0.04
V3A_DTE              = 45


# ── BS 定价工具 ───────────────────────────────────────────────────────────────
def term_multiplier(dte: int) -> float:
    """与 q042_pricing.py 一致的 term multiplier。"""
    if dte <= 45:
        return 1.10
    if dte <= 120:
        return 1.00
    return 0.95


def bs_put(S: float, K: float, T: float, sigma: float, r: float = R) -> float:
    if T <= 0:
        return max(0.0, K - S)
    if sigma <= 0:
        return max(0.0, K * math.exp(-r * T) - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return float(K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))


def bs_call(S: float, K: float, T: float, sigma: float, r: float = R) -> float:
    if T <= 0:
        return max(0.0, S - K)
    if sigma <= 0:
        return max(0.0, S - K * math.exp(-r * T))
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return float(S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2))


def delta_to_strike_put(S: float, target_delta: float, T: float, sigma: float,
                         r: float = R) -> float:
    """N(d1) = 1 - target_delta  →  解 K。"""
    def obj(K):
        if K <= 0:
            return -1.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return norm.cdf(d1) - (1.0 - target_delta)
    try:
        return brentq(obj, S * 0.40, S * 1.10, xtol=0.01)
    except ValueError:
        approx = sigma * math.sqrt(T) * norm.ppf(1.0 - target_delta)
        return max(S * 0.5, S * math.exp(-approx))


def delta_to_strike_call(S: float, target_delta: float, T: float, sigma: float,
                          r: float = R) -> float:
    """N(d1) = target_delta  →  解 K。"""
    def obj(K):
        if K <= 0:
            return -1.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return norm.cdf(d1) - target_delta
    try:
        return brentq(obj, S * 0.90, S * 2.0, xtol=0.01)
    except ValueError:
        approx = sigma * math.sqrt(T) * norm.ppf(target_delta)
        return S * math.exp(approx)


# ── 市场数据 ──────────────────────────────────────────────────────────────────
def load_price_series(ticker: str, start: str = "2009-01-01") -> pd.Series:
    raw = yf.download(ticker, start=start, end="2025-06-30", progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    prices = raw["Close"].squeeze()
    prices.index = pd.to_datetime(prices.index).normalize()
    return prices


def get_price_on(prices: pd.Series, date: pd.Timestamp) -> float:
    date = pd.Timestamp(date).normalize()
    if date in prices.index:
        return float(prices.loc[date])
    for delta in range(1, 6):
        for sign in [1, -1]:
            d = date + timedelta(days=sign * delta)
            if d in prices.index:
                return float(prices.loc[d])
    raise ValueError(f"No price data near {date}")


# ── 入场定价 ──────────────────────────────────────────────────────────────────
def price_bps_hv_entry(S: float, vix: float, dte: int = BPS_HV_DTE) -> dict:
    """BPS_HV entry: SELL PUT δ0.20, BUY PUT δ0.10, DTE=35。"""
    T = dte / 365.0
    sigma = max(vix / 100.0, 0.10) * term_multiplier(dte)
    K_short = delta_to_strike_put(S, BPS_HV_SHORT_DELTA, T, sigma)
    K_long  = delta_to_strike_put(S, BPS_HV_LONG_DELTA,  T, sigma)
    p_short = bs_put(S, K_short, T, sigma)
    p_long  = bs_put(S, K_long,  T, sigma)
    credit  = p_short - p_long
    return {
        "short_strike": K_short,
        "long_strike":  K_long,
        "spread_width": K_short - K_long,
        "entry_credit_per_share": credit,
        "sigma": sigma,
        "dte": dte,
    }


def price_v3a_entry(S: float, vix: float, dte: int = V3A_DTE) -> dict:
    """V3-A broken-wing IC_HV entry。"""
    T = dte / 365.0
    sigma = max(vix / 100.0, 0.10) * term_multiplier(dte)
    K_ps = delta_to_strike_put( S, V3A_PUT_SHORT_DELTA,  T, sigma)
    K_pl = delta_to_strike_put( S, V3A_PUT_LONG_DELTA,   T, sigma)
    K_cs = delta_to_strike_call(S, V3A_CALL_SHORT_DELTA, T, sigma)
    K_cl = delta_to_strike_call(S, V3A_CALL_LONG_DELTA,  T, sigma)
    put_c  = bs_put( S, K_ps, T, sigma) - bs_put( S, K_pl, T, sigma)
    call_c = bs_call(S, K_cs, T, sigma) - bs_call(S, K_cl, T, sigma)
    return {
        "put_short_K":  K_ps,
        "put_long_K":   K_pl,
        "put_width":    K_ps - K_pl,
        "put_credit":   put_c,
        "call_short_K": K_cs,
        "call_long_K":  K_cl,
        "call_width":   K_cl - K_cs,
        "call_credit":  call_c,
        "entry_credit_per_share": put_c + call_c,
        "sigma": sigma,
        "dte": dte,
    }


# ── 出场定价（BS mid-price at exit_date，用 remaining DTE 和 exit VIX） ────────
def exit_value_bps(S_exit: float, vix_exit: float,
                   entry: dict, dte_at_exit: int) -> float:
    """
    BPS exit value per share（正数 = 买回成本；信用价值减少）。
    用 BS 重新定价 spread at exit_date。
    T_exit = remaining DTE at exit / 365。
    """
    K_short = entry["short_strike"]
    K_long  = entry["long_strike"]
    # 用 exit DTE 和 exit VIX 重新算 sigma（保持 term_multiplier 一致）
    # exit DTE: 注意 DTE=0 时用 intrinsic
    T = max(dte_at_exit / 365.0, 0.0)
    sigma = max(vix_exit / 100.0, 0.10) * term_multiplier(max(dte_at_exit, 1))

    if T <= 0:
        # Hold to expiry: intrinsic
        cost = max(0.0, K_short - S_exit) - max(0.0, K_long - S_exit)
    else:
        cost = bs_put(S_exit, K_short, T, sigma) - bs_put(S_exit, K_long, T, sigma)

    return max(0.0, cost)  # cost to close (debit paid to close)


def exit_value_v3a(S_exit: float, vix_exit: float,
                   entry: dict, dte_at_exit: int) -> float:
    """
    V3-A IC exit value per share（买回成本）。
    """
    K_ps = entry["put_short_K"]
    K_pl = entry["put_long_K"]
    K_cs = entry["call_short_K"]
    K_cl = entry["call_long_K"]
    T = max(dte_at_exit / 365.0, 0.0)
    sigma = max(vix_exit / 100.0, 0.10) * term_multiplier(max(dte_at_exit, 1))

    if T <= 0:
        put_cost  = max(0.0, K_ps - S_exit) - max(0.0, K_pl - S_exit)
        call_cost = max(0.0, S_exit - K_cs) - max(0.0, S_exit - K_cl)
    else:
        put_cost  = bs_put( S_exit, K_ps, T, sigma) - bs_put( S_exit, K_pl, T, sigma)
        call_cost = bs_call(S_exit, K_cs, T, sigma) - bs_call(S_exit, K_cl, T, sigma)
        put_cost  = max(0.0, put_cost)
        call_cost = max(0.0, call_cost)

    return put_cost + call_cost


# ── BP 计算 ───────────────────────────────────────────────────────────────────
def bp_bps(entry: dict, contracts: float) -> float:
    """BPS_HV BP = spread_width × 100 × contracts（最大亏损）。"""
    return entry["spread_width"] * CONTRACTS_MULTIPLIER * contracts


def bp_v3a(entry: dict, contracts: float) -> float:
    """
    IC BP = max(put_wing_width, call_wing_width) × 100 × contracts。
    tastytrade/TIMS PM标准：IC 的 BP 取两翼中的较宽者。
    """
    max_wing = max(entry["put_width"], entry["call_width"])
    return max_wing * CONTRACTS_MULTIPLIER * contracts


# ── 主计算 ────────────────────────────────────────────────────────────────────
def max_consec_losses(pnl_series):
    mx = cur = 0
    for v in pnl_series:
        if v < 0:
            cur += 1
            mx = max(mx, cur)
        else:
            cur = 0
    return mx


def main():
    print("=" * 70)
    print("Q064 P3 — V3-A vs BPS_HV Counterfactual (15 aftermath trades)")
    print("=" * 70)

    # 读取 P2 标记数据
    tagged = pd.read_csv(
        os.path.join(OUT_DIR, "q064_p2_tagged_trades.csv"),
        parse_dates=["entry_date", "exit_date"],
    )
    aftermath = tagged[tagged["is_aftermath"] == True].copy().reset_index(drop=True)
    print(f"aftermath=True trades: {len(aftermath)}")

    # 下载市场数据
    print("Downloading SPX and VIX data ...")
    spx_prices = load_price_series("^GSPC")
    vix_prices = load_price_series("^VIX")
    print("Data ready.\n")

    records = []
    for _, row in aftermath.iterrows():
        entry_date = pd.Timestamp(row["entry_date"])
        exit_date  = pd.Timestamp(row["exit_date"])
        vix_entry  = float(row["vix_at_entry"])
        contracts  = float(row["contracts"])
        actual_pnl = float(row["exit_pnl"])
        actual_bp  = float(row["total_bp"])
        dte_entry  = int(row["dte_at_entry"])
        dte_exit   = int(row["dte_at_exit"])
        hold_days  = (exit_date - entry_date).days

        S_entry   = get_price_on(spx_prices, entry_date)
        S_exit    = get_price_on(spx_prices, exit_date)
        vix_exit  = get_price_on(vix_prices, exit_date)

        # ── BPS_HV ──────────────────────────────────────────────────────────
        bps_entry = price_bps_hv_entry(S_entry, vix_entry, dte=BPS_HV_DTE)
        # remaining DTE at exit = DTE_entry - hold_days（近似）
        bps_dte_exit = max(BPS_HV_DTE - hold_days, 0)
        bps_close_cost = exit_value_bps(S_exit, vix_exit, bps_entry, bps_dte_exit)
        bps_credit     = bps_entry["entry_credit_per_share"]
        bps_pnl_share  = bps_credit - bps_close_cost
        bps_pnl_total  = bps_pnl_share * CONTRACTS_MULTIPLIER * contracts
        bps_bp         = bp_bps(bps_entry, contracts)
        bps_bp_day     = (
            bps_pnl_total / bps_bp / hold_days * 10_000
            if bps_bp > 0 and hold_days > 0 else float("nan")
        )

        # ── V3-A IC_HV ──────────────────────────────────────────────────────
        v3a_entry = price_v3a_entry(S_entry, vix_entry, dte=V3A_DTE)
        v3a_dte_exit = max(V3A_DTE - hold_days, 0)
        v3a_close_cost = exit_value_v3a(S_exit, vix_exit, v3a_entry, v3a_dte_exit)
        v3a_credit     = v3a_entry["entry_credit_per_share"]
        v3a_pnl_share  = v3a_credit - v3a_close_cost
        v3a_pnl_total  = v3a_pnl_share * CONTRACTS_MULTIPLIER * contracts
        v3a_bp         = bp_v3a(v3a_entry, contracts)
        v3a_bp_day     = (
            v3a_pnl_total / v3a_bp / hold_days * 10_000
            if v3a_bp > 0 and hold_days > 0 else float("nan")
        )

        rec = {
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "exit_date":  exit_date.strftime("%Y-%m-%d"),
            "vix_at_entry": round(vix_entry, 2),
            "vix_at_exit":  round(vix_exit, 2),
            "vix_peak_10d": round(float(row["vix_peak_10d"]), 2),
            "S_entry": round(S_entry, 2),
            "S_exit":  round(S_exit, 2),
            "contracts": round(contracts, 4),
            "hold_days": hold_days,
            # Actual
            "actual_pnl": round(actual_pnl, 2),
            "actual_bp":  round(actual_bp, 2),
            # BPS_HV counterfactual
            "bps_short_K":      round(bps_entry["short_strike"], 0),
            "bps_long_K":       round(bps_entry["long_strike"], 0),
            "bps_spread_width": round(bps_entry["spread_width"], 0),
            "bps_entry_credit": round(bps_credit * CONTRACTS_MULTIPLIER * contracts, 2),
            "bps_close_cost":   round(bps_close_cost * CONTRACTS_MULTIPLIER * contracts, 2),
            "bps_pnl":          round(bps_pnl_total, 2),
            "bps_bp":           round(bps_bp, 2),
            "bps_bp_day":       round(bps_bp_day, 4) if not math.isnan(bps_bp_day) else None,
            # V3-A
            "v3a_put_short_K":  round(v3a_entry["put_short_K"], 0),
            "v3a_put_long_K":   round(v3a_entry["put_long_K"], 0),
            "v3a_put_width":    round(v3a_entry["put_width"], 0),
            "v3a_call_short_K": round(v3a_entry["call_short_K"], 0),
            "v3a_call_long_K":  round(v3a_entry["call_long_K"], 0),
            "v3a_call_width":   round(v3a_entry["call_width"], 0),
            "v3a_put_credit":   round(v3a_entry["put_credit"] * CONTRACTS_MULTIPLIER * contracts, 2),
            "v3a_call_credit":  round(v3a_entry["call_credit"] * CONTRACTS_MULTIPLIER * contracts, 2),
            "v3a_entry_credit": round(v3a_credit * CONTRACTS_MULTIPLIER * contracts, 2),
            "v3a_close_cost":   round(v3a_close_cost * CONTRACTS_MULTIPLIER * contracts, 2),
            "v3a_pnl":          round(v3a_pnl_total, 2),
            "v3a_bp":           round(v3a_bp, 2),
            "v3a_bp_day":       round(v3a_bp_day, 4) if not math.isnan(v3a_bp_day) else None,
            # Diff
            "pnl_diff_v3a_minus_bps": round(v3a_pnl_total - bps_pnl_total, 2),
        }
        records.append(rec)

    df = pd.DataFrame(records)

    # ── 汇总统计 ──────────────────────────────────────────────────────────────
    def summary_stats(col_pnl, col_bp, col_bp_day, label):
        pnl = df[col_pnl]
        bp  = df[col_bp]
        bpd = df[col_bp_day].dropna()
        n   = len(pnl)
        wins = (pnl > 0).sum()
        return {
            "structure":          label,
            "n":                  n,
            "win_rate_%":         round(wins / n * 100, 1),
            "avg_pnl_$":          round(pnl.mean(), 0),
            "median_pnl_$":       round(pnl.median(), 0),
            "total_pnl_$":        round(pnl.sum(), 0),
            "worst_trade_$":      round(pnl.min(), 0),
            "avg_bp_$":           round(bp.mean(), 0),
            "median_$/bp_day":    round(bpd.median(), 4) if len(bpd) > 0 else None,
            "max_consec_losses":  max_consec_losses(pnl),
        }

    stats_act = {
        "structure":          "Actual (historical BPS_HV)",
        "n":                  len(df),
        "win_rate_%":         round((df["actual_pnl"] > 0).mean() * 100, 1),
        "avg_pnl_$":          round(df["actual_pnl"].mean(), 0),
        "median_pnl_$":       round(df["actual_pnl"].median(), 0),
        "total_pnl_$":        round(df["actual_pnl"].sum(), 0),
        "worst_trade_$":      round(df["actual_pnl"].min(), 0),
        "avg_bp_$":           round(df["actual_bp"].mean(), 0),
        "median_$/bp_day":    44.32,  # from P2
        "max_consec_losses":  max_consec_losses(df["actual_pnl"]),
    }
    stats_bps = summary_stats("bps_pnl", "bps_bp", "bps_bp_day", "BPS_HV (BS counterfactual)")
    stats_v3a = summary_stats("v3a_pnl", "v3a_bp", "v3a_bp_day", "V3-A IC_HV broken-wing")

    summary_df = pd.DataFrame([stats_act, stats_bps, stats_v3a])

    # ── 打印 ──────────────────────────────────────────────────────────────────
    print("── 逐笔结果 ──")
    print(df[[
        "entry_date", "vix_at_entry", "vix_at_exit", "S_entry", "S_exit",
        "bps_pnl", "v3a_pnl", "actual_pnl", "pnl_diff_v3a_minus_bps",
    ]].to_string(index=False))

    print("\n── 汇总对比 ──")
    print(summary_df.to_string(index=False))

    print("\n── 结构参数对比（平均值）──")
    print(f"BPS_HV  DTE={BPS_HV_DTE}: avg spread_width={df['bps_spread_width'].mean():.0f} pts, "
          f"avg entry_credit=${df['bps_entry_credit'].mean():.0f}, "
          f"avg BP=${df['bps_bp'].mean():.0f}")
    print(f"V3-A    DTE={V3A_DTE}: avg put_width={df['v3a_put_width'].mean():.0f} pts, "
          f"avg call_width={df['v3a_call_width'].mean():.0f} pts")
    print(f"         avg put_credit=${df['v3a_put_credit'].mean():.0f}, "
          f"avg call_credit=${df['v3a_call_credit'].mean():.0f}, "
          f"avg total_credit=${df['v3a_entry_credit'].mean():.0f}, "
          f"avg BP=${df['v3a_bp'].mean():.0f}")

    print("\n── V3-A minus BPS_HV P&L 分布 ──")
    diff = df["pnl_diff_v3a_minus_bps"]
    print(f"  mean:   ${diff.mean():+.0f}")
    print(f"  median: ${diff.median():+.0f}")
    print(f"  V3-A > BPS_HV: {(diff > 0).sum()}/{len(diff)} trades")
    print(f"  worst spread (V3-A − BPS): ${diff.min():+.0f}")

    print("\n── BP-Day 对比 ──")
    print(f"  BPS_HV  median $/BP-day: {df['bps_bp_day'].dropna().median():.2f}")
    print(f"  V3-A    median $/BP-day: {df['v3a_bp_day'].dropna().median():.2f}")

    # 保存
    out_path = os.path.join(OUT_DIR, "q064_p3_results.csv")
    df.to_csv(out_path, index=False)
    print(f"\nSaved {len(df)}-row detail to: {out_path}")

    sum_path = os.path.join(OUT_DIR, "q064_p3_summary.csv")
    summary_df.to_csv(sum_path, index=False)
    print(f"Saved summary to: {sum_path}")

    return df, summary_df


if __name__ == "__main__":
    df, summary = main()
