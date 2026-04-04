# PROTOTYPE — SPEC-006b
# 目标：在 BEARISH + HIGH_VOL 环境下，扫描所有候选策略的历史表现
#
# 候选策略：
#   A. Bull Put Spread HV（当前只在 BULLISH 时用，放宽到 BEARISH）
#   B. Bear Call Spread（方向性对齐：BEARISH + sell OTM call）
#   C. Iron Condor symmetric（δ0.16/δ0.16）
#   D. Iron Condor asymmetric（call δ0.20 tighter / put δ0.12 wider）
#   E. Far OTM Bull Put Spread（δ0.10 short put）
#
# 子环境分层：
#   ALL   : 所有 BEARISH + HIGH_VOL 入场点
#   FALL  : VIX 5日均线开始下行（regime 可能即将转变）
#   FLAT  : VIX 5日均线持平
#
# 参数网格：DTE = 21 / 35 / 45

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import numpy as np
from backtest.engine import run_backtest
from backtest.pricer import call_price, put_price, find_strike_for_delta
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history

print("加载数据...")
trades, metrics, signals = run_backtest(start_date="2000-01-01", verbose=False)

sig_df = pd.DataFrame(signals)
sig_df["date"] = pd.to_datetime(sig_df["date"])
sig_df = sig_df.set_index("date").sort_index()

vix_hist = fetch_vix_history(period="max")
spx_hist = fetch_spx_history(period="max")
vix_hist.index = pd.to_datetime(vix_hist.index.date)
spx_hist.index = pd.to_datetime(spx_hist.index.date)
price_df = pd.DataFrame({"vix": vix_hist["vix"], "spx": spx_hist["close"]}).dropna()

# VIX trend（5日均线 vs 5日前均线）
sig_df["vix_5d"]       = sig_df["vix"].rolling(5).mean()
sig_df["vix_5d_prior"] = sig_df["vix_5d"].shift(5)
sig_df["vix_trend"]    = "FLAT"
mask_rising  = sig_df["vix_5d"] > sig_df["vix_5d_prior"] * 1.05
mask_falling = sig_df["vix_5d"] < sig_df["vix_5d_prior"] * 0.95
sig_df.loc[mask_rising,  "vix_trend"] = "RISING"
sig_df.loc[mask_falling, "vix_trend"] = "FALLING"

# ─── 候选入场天（BEARISH + HIGH_VOL，VIX 非 EXTREME）──────────────────────
base = sig_df[
    (sig_df["trend"]  == "BEARISH") &
    (sig_df["regime"] == "HIGH_VOL") &
    (sig_df["vix"]    < 35)                # 排除 EXTREME_VOL
].dropna(subset=["vix_5d_prior"])

print(f"\nBEARISH + HIGH_VOL（VIX 22-35）总天数：{len(base)}")
for vt in ["RISING", "FLAT", "FALLING"]:
    n = (base["vix_trend"] == vt).sum()
    print(f"  VIX {vt:<8}: {n:>4}d ({n/len(base)*100:.0f}%)")

account_size = 150_000
risk_pct     = 0.02

# ─── 单笔模拟函数 ────────────────────────────────────────────────────────────
def sim_trade(entry_date, strategy, dte, price_df,
              min_hold=10, profit_target=0.50, stop_mult=2.0, size_mult=0.5):
    """
    Simulate one trade from entry_date.
    strategy: "bps_hv" | "bcs" | "ic_sym" | "ic_asym" | "bps_far"
    Returns dict or None.
    """
    if entry_date not in price_df.index:
        return None
    spx_e   = price_df.loc[entry_date, "spx"]
    sigma_e = price_df.loc[entry_date, "vix"] / 100

    # Build legs: (action, is_call, strike, dte_entry)
    # action: +1=long, -1=short; credit structure → net entry_val < 0
    if strategy == "bps_hv":
        ps = find_strike_for_delta(spx_e, dte, sigma_e, 0.20, is_call=False)
        pl = find_strike_for_delta(spx_e, dte, sigma_e, 0.10, is_call=False)
        legs = [(-1, False, ps, dte), (+1, False, pl, dte)]

    elif strategy == "bcs":
        cs = find_strike_for_delta(spx_e, dte, sigma_e, 0.20, is_call=True)
        cl = find_strike_for_delta(spx_e, dte, sigma_e, 0.10, is_call=True)
        legs = [(-1, True, cs, dte), (+1, True, cl, dte)]

    elif strategy == "ic_sym":
        wing = max(50, round(spx_e * 0.015 / 50) * 50)
        cs   = find_strike_for_delta(spx_e, dte, sigma_e, 0.16, is_call=True)
        ps   = find_strike_for_delta(spx_e, dte, sigma_e, 0.16, is_call=False)
        legs = [
            (-1, True,  cs,        dte), (+1, True,  cs + wing, dte),
            (-1, False, ps,        dte), (+1, False, ps - wing, dte),
        ]

    elif strategy == "ic_asym":
        wing = max(50, round(spx_e * 0.015 / 50) * 50)
        cs   = find_strike_for_delta(spx_e, dte, sigma_e, 0.20, is_call=True)
        ps   = find_strike_for_delta(spx_e, dte, sigma_e, 0.12, is_call=False)
        legs = [
            (-1, True,  cs,        dte), (+1, True,  cs + wing, dte),
            (-1, False, ps,        dte), (+1, False, ps - wing, dte),
        ]

    elif strategy == "bps_far":
        ps = find_strike_for_delta(spx_e, dte, sigma_e, 0.10, is_call=False)
        pl = find_strike_for_delta(spx_e, dte, sigma_e, 0.05, is_call=False)
        legs = [(-1, False, ps, dte), (+1, False, pl, dte)]

    else:
        return None

    def price_legs(spx_now, sigma_now, days_held):
        total = 0.0
        for action, is_call, strike, dte_entry in legs:
            dte_now = max(dte_entry - days_held, 1)
            p = (call_price(spx_now, strike, dte_now, sigma_now)
                 if is_call else
                 put_price(spx_now, strike, dte_now, sigma_now))
            total += action * p
        return total

    entry_val = price_legs(spx_e, sigma_e, 0)
    if abs(entry_val) < 0.01:
        return None

    option_premium = abs(entry_val) * 100
    contracts = account_size * risk_pct * size_mult / option_premium

    future = price_df[price_df.index > entry_date].iloc[:dte + 10]
    for day_idx, (date, row) in enumerate(future.iterrows(), start=1):
        spx_now   = row["spx"]
        sigma_now = row["vix"] / 100
        cur_val   = price_legs(spx_now, sigma_now, day_idx)
        pnl_ratio = (cur_val - entry_val) / abs(entry_val)

        if pnl_ratio >= profit_target and day_idx >= min_hold:
            reason = "50pct_profit"
        elif pnl_ratio <= -stop_mult:
            reason = "stop_loss"
        elif (dte - day_idx) <= 21:
            reason = "roll_21dte"
        else:
            continue

        pnl_usd = pnl_ratio * option_premium * contracts
        return {"pnl": pnl_usd, "reason": reason, "days": day_idx,
                "pnl_ratio": pnl_ratio, "entry_spx": spx_e, "entry_vix": price_df.loc[entry_date,"vix"]}

    return {"pnl": 0.0, "reason": "end_of_sim", "days": dte,
            "pnl_ratio": 0.0, "entry_spx": spx_e, "entry_vix": price_df.loc[entry_date,"vix"]}


# ─── 扫描函数 ────────────────────────────────────────────────────────────────
def scan(candidate_days, label, strategies, dtes):
    print(f"\n{'='*70}")
    print(f"环境：{label}  ({len(candidate_days)} 候选天)")
    print(f"{'策略':<14} {'DTE':>5} {'笔数':>5} {'WR':>7} {'均PnL':>9} {'总PnL':>10} {'Sharpe':>8}")
    print("-" * 70)
    best = None
    for strategy in strategies:
        for dte in dtes:
            results   = []
            last_exit = pd.Timestamp("1990-01-01")
            for date, row in candidate_days.iterrows():
                if (date - last_exit).days < dte:
                    continue
                res = sim_trade(date, strategy, dte, price_df)
                if res:
                    res["date"] = date
                    results.append(res)
                    last_exit = date + pd.Timedelta(days=res["days"])

            if not results:
                continue
            pnls   = [r["pnl"] for r in results]
            wr     = sum(1 for p in pnls if p > 0) / len(pnls) * 100
            avg    = np.mean(pnls)
            tot    = sum(pnls)
            std    = np.std(pnls) if len(pnls) > 1 else 1e-9
            sharpe = avg / std

            marker = ""
            if best is None or sharpe > best["sharpe"]:
                best = {"strategy": strategy, "dte": dte, "sharpe": sharpe,
                        "wr": wr, "avg": avg, "n": len(pnls)}
                marker = " ◄"

            print(f"  {strategy:<14} {dte:>5} {len(pnls):>5} {wr:>6.0f}% {avg:>+9.0f} {tot:>+10.0f} {sharpe:>+8.3f}{marker}")

    return best


strategies = ["bps_hv", "bcs", "ic_sym", "ic_asym", "bps_far"]
dtes       = [21, 35, 45]

# 全量扫描
best_all = scan(base, "BEARISH + HIGH_VOL ALL", strategies, dtes)

# VIX FALLING 子集
falling = base[base["vix_trend"] == "FALLING"]
best_fall = scan(falling, "BEARISH + HIGH_VOL + VIX FALLING", strategies, dtes)

# VIX FLAT 子集
flat = base[base["vix_trend"] == "FLAT"]
best_flat = scan(flat, "BEARISH + HIGH_VOL + VIX FLAT", strategies, dtes)

# ─── 汇总最优 ────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("最优策略汇总（按 Sharpe 代理）：")
for label, best in [("ALL", best_all), ("VIX FALLING", best_fall), ("VIX FLAT", best_flat)]:
    if best:
        print(f"  {label:<15}: {best['strategy']:<14} DTE={best['dte']}  "
              f"n={best['n']}  WR={best['wr']:.0f}%  Sharpe={best['sharpe']:+.3f}")

print("\n完成。")
