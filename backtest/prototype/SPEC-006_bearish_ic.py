# PROTOTYPE — SPEC-006 前期研究
# 目标：验证 BEARISH 趋势 + NORMAL vol 环境下部署 Iron Condor 的可行性
#
# 研究问题：
#   1. BEARISH + NORMAL 期间有多少可用交易日？占比多少？
#   2. 当前 IC（NEUTRAL 趋势）的历史表现作为基准
#   3. 模拟：若在 BEARISH + NORMAL + IVP 25-50 + VIX 非 RISING 时入场 IC，
#      历史结果如何？（symmetric wings vs asymmetric wings）
#   4. 确定推荐入场约束和翼宽参数

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import numpy as np
from backtest.engine import run_backtest
from backtest.pricer import call_price, put_price, find_strike_for_delta
from strategy.selector import StrategyName, DEFAULT_PARAMS

print("运行全量回测 2000-01-01（获取信号历史）...")
trades, metrics, signals = run_backtest(start_date="2000-01-01", verbose=False)

sig_df = pd.DataFrame(signals)
sig_df["date"] = pd.to_datetime(sig_df["date"])
sig_df = sig_df.set_index("date").sort_index()

total_days = len(sig_df)

# ─── 1. 制度分布 ─────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"信号历史总天数：{total_days}")
print(f"\n趋势分布：")
for t in ["BULLISH", "NEUTRAL", "BEARISH"]:
    n = (sig_df["trend"] == t).sum()
    print(f"  {t:<10} {n:>5}d  ({n/total_days*100:.1f}%)")

print(f"\n体制分布：")
for r in ["LOW_VOL", "NORMAL", "HIGH_VOL"]:
    n = (sig_df["regime"] == r).sum()
    print(f"  {r:<12} {n:>5}d  ({n/total_days*100:.1f}%)")

# ─── 2. 当前空转的 BEARISH 天数 ──────────────────────────────────────────────
bearish_normal = sig_df[
    (sig_df["trend"] == "BEARISH") &
    (sig_df["regime"] == "NORMAL")
]
bearish_low = sig_df[
    (sig_df["trend"] == "BEARISH") &
    (sig_df["regime"] == "LOW_VOL")
]
bearish_hv = sig_df[
    (sig_df["trend"] == "BEARISH") &
    (sig_df["regime"] == "HIGH_VOL")
]

print(f"\n{'='*60}")
print(f"当前完全空转的 BEARISH 天数：")
print(f"  BEARISH + NORMAL   {len(bearish_normal):>5}d  ({len(bearish_normal)/total_days*100:.1f}%)")
print(f"  BEARISH + LOW_VOL  {len(bearish_low):>5}d  ({len(bearish_low)/total_days*100:.1f}%)")
print(f"  BEARISH + HIGH_VOL {len(bearish_hv):>5}d  ({len(bearish_hv)/total_days*100:.1f}%)")

# ─── 3. BEARISH + NORMAL 中满足 IC 约束的天数 ──────────────────────────────
# 约束：IVP 25–50，VIX 非 RISING（用 vix vs vix_5d_avg 代理）
# vix_5d_avg 未存入 signal_history，用 vix 滚动均值代理 VIX trend
sig_df["vix_5d"] = sig_df["vix"].rolling(5).mean()
sig_df["vix_5d_prior"] = sig_df["vix_5d"].shift(5)
sig_df["vix_rising"] = sig_df["vix_5d"] > sig_df["vix_5d_prior"] * 1.05  # >5% = RISING

candidate_days = sig_df[
    (sig_df["trend"] == "BEARISH") &
    (sig_df["regime"] == "NORMAL") &
    (sig_df["ivp"] >= 25) &
    (sig_df["ivp"] <= 50) &
    (~sig_df["vix_rising"])
].dropna(subset=["vix_5d_prior"])

print(f"\n满足 IC 约束的 BEARISH+NORMAL 天数：")
print(f"  IVP 25-50 + VIX non-rising: {len(candidate_days):>5}d  ({len(candidate_days)/total_days*100:.1f}%)")

# IVP 分布
print(f"\n  IVP 分布（BEARISH + NORMAL）：")
for lo, hi in [(25,30),(30,35),(35,40),(40,45),(45,50)]:
    n = ((bearish_normal["ivp"] >= lo) & (bearish_normal["ivp"] < hi)).sum()
    print(f"    IVP {lo}-{hi}: {n:>4}d")

# ─── 4. 当前 NEUTRAL 趋势 IC 表现（基准）──────────────────────────────────
ic_trades = [t for t in trades if t.strategy == StrategyName.IRON_CONDOR]
print(f"\n{'='*60}")
print(f"基准：当前 IC 表现（NEUTRAL 趋势下）")
print(f"  笔数：{len(ic_trades)}")
if ic_trades:
    wr  = sum(1 for t in ic_trades if t.exit_pnl > 0) / len(ic_trades)
    avg = np.mean([t.exit_pnl for t in ic_trades])
    tot = sum(t.exit_pnl for t in ic_trades)
    print(f"  WR：{wr*100:.0f}%  均PnL：${avg:+.0f}  总PnL：${tot:+.0f}")
    by_exit = {}
    for t in ic_trades:
        by_exit.setdefault(t.exit_reason, []).append(t.exit_pnl)
    for r, pnls in sorted(by_exit.items()):
        wr_r = sum(1 for p in pnls if p > 0) / len(pnls) * 100
        print(f"    {r:<18} n={len(pnls):>2}  WR {wr_r:.0f}%  avg ${np.mean(pnls):+.0f}")

# ─── 5. 模拟 BEARISH IC：每次入场后持仓 45 天，BS 定价计算 PnL ──────────────
# 方法：对 candidate_days 中每个潜在入场点，计算 BS 定价 IC PnL
# 翼宽设置：
#   Symmetric: PUT short δ0.16 / CALL short δ0.16（与当前 IC 相同）
#   Asymmetric: PUT short δ0.12 / CALL short δ0.20（put 更 OTM，call 更 OTM）

print(f"\n{'='*60}")
print(f"模拟 BEARISH + NORMAL IC 入场（独立仓位，不互相干扰）")
print(f"DTE=45，止盈 50% credit，止损 2× credit，最低持 10 天")

# 加载历史数据用于逐日 PnL 计算
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_hist = fetch_vix_history(period="max")
spx_hist = fetch_spx_history(period="max")
vix_hist.index = pd.to_datetime(vix_hist.index.date)
spx_hist.index = pd.to_datetime(spx_hist.index.date)
price_df = pd.DataFrame({"vix": vix_hist["vix"], "spx": spx_hist["close"]}).dropna()

account_size = 150_000
risk_pct = 0.02

def simulate_ic(entry_date, spx_e, sigma_e, put_short_delta, call_short_delta,
                price_df, dte=45, min_hold=10, profit_target=0.50, stop_mult=2.0):
    """Simulate one IC trade from entry_date. Returns (pnl_usd, exit_reason, days_held)."""
    wing = max(50, round(spx_e * 0.015 / 50) * 50)
    cs = find_strike_for_delta(spx_e, dte, sigma_e, call_short_delta, is_call=True)
    cl = cs + wing
    ps = find_strike_for_delta(spx_e, dte, sigma_e, put_short_delta, is_call=False)
    pl = ps - wing

    # Entry credit (negative = credit received)
    entry_val = (
        - call_price(spx_e, cs, dte, sigma_e)
        + call_price(spx_e, cl, dte, sigma_e)
        - put_price(spx_e, ps, dte, sigma_e)
        + put_price(spx_e, pl, dte, sigma_e)
    )  # net credit = negative number
    if abs(entry_val) < 0.01:
        return None

    option_premium = abs(entry_val) * 100
    contracts = account_size * risk_pct / option_premium

    future = price_df[price_df.index > entry_date].iloc[:dte+5]
    for day_idx, (date, row) in enumerate(future.iterrows(), start=1):
        spx_now = row["spx"]
        sigma_now = row["vix"] / 100
        dte_now = max(dte - day_idx, 1)

        cur_val = (
            - call_price(spx_now, cs, dte_now, sigma_now)
            + call_price(spx_now, cl, dte_now, sigma_now)
            - put_price(spx_now, ps, dte_now, sigma_now)
            + put_price(spx_now, pl, dte_now, sigma_now)
        )
        pnl_ratio = (cur_val - entry_val) / abs(entry_val)  # positive = profit

        if pnl_ratio >= profit_target and day_idx >= min_hold:
            return pnl_ratio * option_premium * contracts, "50pct_profit", day_idx
        if pnl_ratio <= -stop_mult:
            return pnl_ratio * option_premium * contracts, "stop_loss", day_idx
        if dte_now <= 21:
            return pnl_ratio * option_premium * contracts, "roll_21dte", day_idx

    return 0.0, "end_of_sim", dte

# 对 candidate_days 中每 30 天最多取一个入场点（避免重叠模拟）
results = {"symmetric": [], "asymmetric": []}
last_entry = pd.Timestamp("1990-01-01")

for date, row in candidate_days.iterrows():
    if (date - last_entry).days < 45:  # 避免重叠持仓
        continue
    if date not in price_df.index:
        continue
    spx_e = price_df.loc[date, "spx"]
    sigma_e = price_df.loc[date, "vix"] / 100

    for mode in ["symmetric", "asymmetric"]:
        if mode == "symmetric":
            res = simulate_ic(date, spx_e, sigma_e, 0.16, 0.16, price_df)
        else:
            res = simulate_ic(date, spx_e, sigma_e, 0.12, 0.20, price_df)
        if res:
            pnl, reason, days = res
            results[mode].append({"date": date, "pnl": pnl, "reason": reason, "days": days})

    last_entry = date

print(f"\n模拟入场笔数：{len(results['symmetric'])}")
for mode, res_list in results.items():
    if not res_list:
        continue
    pnls = [r["pnl"] for r in res_list]
    wr   = sum(1 for p in pnls if p > 0) / len(pnls) * 100
    avg  = np.mean(pnls)
    tot  = sum(pnls)
    std  = np.std(pnls)
    sharpe_proxy = avg / std if std > 0 else 0
    print(f"\n  [{mode}]  WR {wr:.0f}%  均PnL ${avg:+.0f}  总PnL ${tot:+.0f}  Sharpe代理 {sharpe_proxy:.3f}")
    by_r = {}
    for r in res_list:
        by_r.setdefault(r["reason"], []).append(r["pnl"])
    for reason, pnls_r in sorted(by_r.items()):
        wr_r = sum(1 for p in pnls_r if p > 0) / len(pnls_r) * 100
        print(f"    {reason:<18} n={len(pnls_r):>2}  WR {wr_r:.0f}%  avg ${np.mean(pnls_r):+.0f}")

print("\n完成。")
