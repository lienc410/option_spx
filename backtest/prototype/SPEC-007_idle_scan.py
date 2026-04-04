# PROTOTYPE — SPEC-007 前期研究
# 目标：全面统计当前 REDUCE_WAIT 时段分布，找出最大空转块，
#       并对每个候选块进行简单信用策略扫描，评估是否值得立项。
#
# 空转来源（SPEC-006 后）：
#   BEARISH + NORMAL
#   BEARISH + LOW_VOL
#   NEUTRAL + HIGH_VOL
#   BULLISH + HIGH_VOL + VIX RISING（已过滤）
#   BULLISH + HIGH_VOL + backwardation（已过滤）
#   BEARISH + HIGH_VOL + VIX RISING（已过滤）
#   所有 EXTREME_VOL（VIX ≥ 35）

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import numpy as np
from backtest.engine import run_backtest
from backtest.pricer import call_price, put_price, find_strike_for_delta
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history

print("加载数据（全量回测 2000-01-01）...")
trades, metrics, signals = run_backtest(start_date="2000-01-01", verbose=False)

sig_df = pd.DataFrame(signals)
sig_df["date"] = pd.to_datetime(sig_df["date"])
sig_df = sig_df.set_index("date").sort_index()
total_days = len(sig_df)

vix_hist = fetch_vix_history(period="max")
spx_hist = fetch_spx_history(period="max")
vix_hist.index = pd.to_datetime(vix_hist.index.date)
spx_hist.index = pd.to_datetime(spx_hist.index.date)
price_df = pd.DataFrame({"vix": vix_hist["vix"], "spx": spx_hist["close"]}).dropna()

# VIX 趋势
sig_df["vix_5d"]       = sig_df["vix"].rolling(5).mean()
sig_df["vix_5d_prior"] = sig_df["vix_5d"].shift(5)
sig_df["vix_trend"]    = "FLAT"
sig_df.loc[sig_df["vix_5d"] > sig_df["vix_5d_prior"] * 1.05, "vix_trend"] = "RISING"
sig_df.loc[sig_df["vix_5d"] < sig_df["vix_5d_prior"] * 0.95, "vix_trend"] = "FALLING"

# ─── 1. 全制度分布 ────────────────────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"信号历史总天数：{total_days}")
print(f"\n{'趋势 × 制度':^30} {'天数':>6} {'占比':>6}")
print("-" * 45)
for t in ["BULLISH", "NEUTRAL", "BEARISH"]:
    for r in ["LOW_VOL", "NORMAL", "HIGH_VOL"]:
        n = ((sig_df["trend"] == t) & (sig_df["regime"] == r)).sum()
        print(f"  {t:<10} × {r:<12}  {n:>6}d  {n/total_days*100:>5.1f}%")

# EXTREME_VOL（VIX ≥ 35）
n_extreme = (sig_df["vix"] >= 35).sum()
print(f"  {'ALL':<10} × {'EXTREME_VOL':<12}  {n_extreme:>6}d  {n_extreme/total_days*100:>5.1f}%")

# ─── 2. 当前 REDUCE_WAIT 天数精确统计 ────────────────────────────────────────
# 根据 selector.py 逻辑推导实际空转路径
print(f"\n{'='*65}")
print("当前 REDUCE_WAIT 路径分解：")

reduce_paths = {
    "BEARISH + LOW_VOL":
        sig_df[(sig_df["trend"] == "BEARISH") & (sig_df["regime"] == "LOW_VOL")],
    "BEARISH + NORMAL":
        sig_df[(sig_df["trend"] == "BEARISH") & (sig_df["regime"] == "NORMAL")],
    "BEARISH + HIGH_VOL + VIX RISING":
        sig_df[(sig_df["trend"] == "BEARISH") & (sig_df["regime"] == "HIGH_VOL")
               & (sig_df["vix_trend"] == "RISING")],
    "NEUTRAL + HIGH_VOL":
        sig_df[(sig_df["trend"] == "NEUTRAL") & (sig_df["regime"] == "HIGH_VOL")],
    "BULLISH + HIGH_VOL + VIX RISING":
        sig_df[(sig_df["trend"] == "BULLISH") & (sig_df["regime"] == "HIGH_VOL")
               & (sig_df["vix_trend"] == "RISING")],
    "EXTREME_VOL (VIX ≥ 35)":
        sig_df[sig_df["vix"] >= 35],
}
# backwardation 需要专门字段（signal_history 未记录），此处无法精确分离

total_reduce = 0
for label, df in reduce_paths.items():
    n = len(df)
    total_reduce += n
    print(f"  {label:<38}  {n:>5}d  {n/total_days*100:>5.1f}%")

print(f"\n  {'估算 REDUCE_WAIT 总计':<38}  {total_reduce:>5}d  {total_reduce/total_days*100:>5.1f}%")

# ─── 3. 候选研究块：规模 ≥ 150d ──────────────────────────────────────────────
print(f"\n{'='*65}")
print("候选研究块（规模 ≥ 150 天，值得立项）：")
candidates = {k: v for k, v in reduce_paths.items() if len(v) >= 150}
for label, df in candidates.items():
    print(f"  {label}: {len(df)}d")

# ─── 4. 各候选块：快速信用策略扫描 ──────────────────────────────────────────
account_size = 150_000
risk_pct     = 0.02

def sim(entry_date, strategy, price_df, size_mult=0.5,
        profit_target=0.50, stop_mult=2.0, min_hold=10):
    if entry_date not in price_df.index:
        return None
    spx_e  = price_df.loc[entry_date, "spx"]
    sig_e  = price_df.loc[entry_date, "vix"] / 100

    if strategy == "bcs_45":
        cs = find_strike_for_delta(spx_e, 45, sig_e, 0.20, is_call=True)
        cl = find_strike_for_delta(spx_e, 45, sig_e, 0.10, is_call=True)
        legs = [(-1, True, cs, 45), (+1, True, cl, 45)]

    elif strategy == "bps_45":
        ps = find_strike_for_delta(spx_e, 45, sig_e, 0.20, is_call=False)
        pl = find_strike_for_delta(spx_e, 45, sig_e, 0.10, is_call=False)
        legs = [(-1, False, ps, 45), (+1, False, pl, 45)]

    elif strategy == "ic_45":
        wing = max(50, round(spx_e * 0.015 / 50) * 50)
        cs = find_strike_for_delta(spx_e, 45, sig_e, 0.16, is_call=True)
        ps = find_strike_for_delta(spx_e, 45, sig_e, 0.16, is_call=False)
        legs = [(-1, True, cs, 45), (+1, True, cs + wing, 45),
                (-1, False, ps, 45), (+1, False, ps - wing, 45)]

    elif strategy == "bps_normal_45":
        # NORMAL vol：delta 更靠近（0.30），权利金稍高
        ps = find_strike_for_delta(spx_e, 45, sig_e, 0.30, is_call=False)
        pl = find_strike_for_delta(spx_e, 45, sig_e, 0.15, is_call=False)
        legs = [(-1, False, ps, 45), (+1, False, pl, 45)]

    else:
        return None

    def price_legs(spx_now, sig_now, days_held):
        total = 0.0
        for action, is_call, strike, dte_entry in legs:
            dte_now = max(dte_entry - days_held, 1)
            p = (call_price(spx_now, strike, dte_now, sig_now)
                 if is_call else
                 put_price(spx_now, strike, dte_now, sig_now))
            total += action * p
        return total

    entry_val = price_legs(spx_e, sig_e, 0)
    if abs(entry_val) < 0.01:
        return None

    option_premium = abs(entry_val) * 100
    contracts = account_size * risk_pct * size_mult / option_premium

    max_dte = max(dte for _, _, _, dte in legs)
    future  = price_df[price_df.index > entry_date].iloc[:max_dte + 10]

    for day_idx, (date, row) in enumerate(future.iterrows(), start=1):
        spx_now = row["spx"]
        sig_now = row["vix"] / 100
        cur_val = price_legs(spx_now, sig_now, day_idx)
        pnl_ratio = (cur_val - entry_val) / abs(entry_val)

        hit_profit = pnl_ratio >= profit_target and day_idx >= min_hold
        hit_stop   = pnl_ratio <= -stop_mult
        hit_roll   = (max_dte - day_idx) <= 21

        if hit_profit:  reason = "50pct_profit"
        elif hit_stop:  reason = "stop_loss"
        elif hit_roll:  reason = "roll_21dte"
        else:           continue

        pnl_usd = pnl_ratio * option_premium * contracts
        return {"pnl": pnl_usd, "reason": reason, "days": day_idx}

    return {"pnl": 0.0, "reason": "end_of_sim", "days": max_dte}


def scan_block(label, candidate_df, strategies):
    print(f"\n{'='*65}")
    print(f"扫描：{label}  ({len(candidate_df)} 候选天)")
    print(f"{'策略':<20} {'笔数':>5} {'WR':>6} {'均PnL':>8} {'总PnL':>10} {'Sharpe':>8}")
    print("-" * 60)

    results = {}
    for strat_key, label_s, size_mult in strategies:
        res_list = []
        last_exit = pd.Timestamp("1990-01-01")
        for date, row in candidate_df.iterrows():
            if (date - last_exit).days < 45:
                continue
            r = sim(date, strat_key, price_df, size_mult=size_mult)
            if r:
                r["date"] = date
                res_list.append(r)
                last_exit = date + pd.Timedelta(days=r["days"])

        if not res_list:
            print(f"  {label_s:<20}  {'—':>5}")
            continue

        pnls   = [r["pnl"] for r in res_list]
        wr     = sum(1 for p in pnls if p > 0) / len(pnls) * 100
        avg    = np.mean(pnls)
        tot    = sum(pnls)
        std    = np.std(pnls) if len(pnls) > 1 else 1e-9
        sharpe = avg / std
        results[strat_key] = {"n": len(pnls), "wr": wr, "avg": avg, "tot": tot, "sharpe": sharpe}
        print(f"  {label_s:<20} {len(pnls):>5} {wr:>5.0f}% {avg:>+8.0f} {tot:>+10.0f} {sharpe:>+8.3f}")

    return results


# ── BEARISH + LOW_VOL ────────────────────────────────────────────────────────
bl = sig_df[(sig_df["trend"] == "BEARISH") & (sig_df["regime"] == "LOW_VOL")]
bl = bl.dropna(subset=["vix_5d_prior"])
scan_block(
    "BEARISH + LOW_VOL",
    bl,
    [
        ("bcs_45",         "BCS δ0.20/0.10",    0.5),
        ("bps_45",         "BPS δ0.20/0.10",    0.5),
        ("ic_45",          "IC sym δ0.16",       0.5),
    ]
)

# ── BEARISH + NORMAL ─────────────────────────────────────────────────────────
bn = sig_df[(sig_df["trend"] == "BEARISH") & (sig_df["regime"] == "NORMAL")]
bn = bn.dropna(subset=["vix_5d_prior"])
scan_block(
    "BEARISH + NORMAL",
    bn,
    [
        ("bcs_45",         "BCS δ0.20/0.10",    1.0),
        ("bps_normal_45",  "BPS δ0.30/0.15",    1.0),
        ("ic_45",          "IC sym δ0.16",       1.0),
    ]
)

# ── NEUTRAL + HIGH_VOL ───────────────────────────────────────────────────────
nhv = sig_df[(sig_df["trend"] == "NEUTRAL") & (sig_df["regime"] == "HIGH_VOL")]
nhv = nhv[nhv["vix"] < 35].dropna(subset=["vix_5d_prior"])
# 进一步分层：VIX 非 RISING（与 BCS HV 相同逻辑）
nhv_safe = nhv[nhv["vix_trend"].isin(["FLAT", "FALLING"])]
scan_block(
    "NEUTRAL + HIGH_VOL (全量，VIX < 35)",
    nhv,
    [
        ("bcs_45",  "BCS δ0.20/0.10",  0.5),
        ("bps_45",  "BPS δ0.20/0.10",  0.5),
        ("ic_45",   "IC sym δ0.16",     0.5),
    ]
)
scan_block(
    "NEUTRAL + HIGH_VOL + VIX 非RISING",
    nhv_safe,
    [
        ("bcs_45",  "BCS δ0.20/0.10",  0.5),
        ("bps_45",  "BPS δ0.20/0.10",  0.5),
        ("ic_45",   "IC sym δ0.16",     0.5),
    ]
)

print("\n完成。")
