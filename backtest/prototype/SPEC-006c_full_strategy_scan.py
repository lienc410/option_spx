# PROTOTYPE — SPEC-006c
# 完整策略扫描：BEARISH + HIGH_VOL（VIX 22-35）
#
# 新增候选（在 006b 信用策略基础上补充）：
#   F. Bear Put Spread  (借方方向性，做空方向)
#   G. Bear Put Diagonal（借方 diagonal，mirrors BCD，90/45 DTE）
#   H. Put Calendar     (卖近买远同 strike，theta + vol crush）
#   I. LEAP Put         (单腿 90-180 DTE δ0.70 put，纯方向性）
#
# 维护成本评估维度：
#   腿数 / 需要主动管理 / vol 结构依赖性

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

sig_df["vix_5d"]       = sig_df["vix"].rolling(5).mean()
sig_df["vix_5d_prior"] = sig_df["vix_5d"].shift(5)
sig_df["vix_trend"]    = "FLAT"
sig_df.loc[sig_df["vix_5d"] > sig_df["vix_5d_prior"] * 1.05, "vix_trend"] = "RISING"
sig_df.loc[sig_df["vix_5d"] < sig_df["vix_5d_prior"] * 0.95, "vix_trend"] = "FALLING"

base = sig_df[
    (sig_df["trend"]  == "BEARISH") &
    (sig_df["regime"] == "HIGH_VOL") &
    (sig_df["vix"]    < 35)
].dropna(subset=["vix_5d_prior"])

account_size = 150_000
risk_pct     = 0.02


# ─── 模拟函数（全策略）─────────────────────────────────────────────────────
def sim(entry_date, strategy, price_df,
        profit_target=0.50, stop_pct=0.50, stop_mult=2.0,
        min_hold=10, size_mult=0.5):
    """
    Unified simulator. stop criteria vary by strategy type:
      credit: stop at -stop_mult × credit
      debit:  stop at -stop_pct × debit (50% loss of premium paid)
    """
    if entry_date not in price_df.index:
        return None
    spx_e   = price_df.loc[entry_date, "spx"]
    sig_e   = price_df.loc[entry_date, "vix"] / 100

    # ── Build legs ────────────────────────────────────────────────────
    is_credit = True

    if strategy == "bcs_45":
        cs = find_strike_for_delta(spx_e, 45, sig_e, 0.20, is_call=True)
        cl = find_strike_for_delta(spx_e, 45, sig_e, 0.10, is_call=True)
        legs = [(-1, True, cs, 45), (+1, True, cl, 45)]

    elif strategy == "ic_sym_45":
        wing = max(50, round(spx_e * 0.015 / 50) * 50)
        cs = find_strike_for_delta(spx_e, 45, sig_e, 0.16, is_call=True)
        ps = find_strike_for_delta(spx_e, 45, sig_e, 0.16, is_call=False)
        legs = [(-1, True, cs, 45), (+1, True, cs+wing, 45),
                (-1, False, ps, 45), (+1, False, ps-wing, 45)]

    elif strategy == "bps_hv_45":
        ps = find_strike_for_delta(spx_e, 45, sig_e, 0.20, is_call=False)
        pl = find_strike_for_delta(spx_e, 45, sig_e, 0.10, is_call=False)
        legs = [(-1, False, ps, 45), (+1, False, pl, 45)]

    elif strategy == "bear_put_spread_45":   # F: debit
        is_credit = False
        long_k  = find_strike_for_delta(spx_e, 45, sig_e, 0.50, is_call=False)  # ATM put
        short_k = find_strike_for_delta(spx_e, 45, sig_e, 0.25, is_call=False)  # OTM put
        legs = [(+1, False, long_k, 45), (-1, False, short_k, 45)]

    elif strategy == "bear_put_diag":        # G: debit diagonal (mirrors BCD)
        is_credit = False
        long_k  = find_strike_for_delta(spx_e, 90, sig_e, 0.70, is_call=False)  # deep ITM put 90d
        short_k = find_strike_for_delta(spx_e, 45, sig_e, 0.30, is_call=False)  # OTM put 45d
        legs = [(+1, False, long_k, 90), (-1, False, short_k, 45)]

    elif strategy == "put_calendar_45_21":   # H: sell 21d / buy 45d same strike
        is_credit = False  # net debit typically (buying more theta)
        atm = round(spx_e / 25) * 25  # round to nearest $25
        legs = [(-1, False, atm, 21), (+1, False, atm, 45)]

    elif strategy == "leap_put_90":          # I: single leg deep ITM put 90d
        is_credit = False
        long_k = find_strike_for_delta(spx_e, 90, sig_e, 0.70, is_call=False)
        legs = [(+1, False, long_k, 90)]

    elif strategy == "leap_put_180":         # I variant: 180d
        is_credit = False
        long_k = find_strike_for_delta(spx_e, 180, sig_e, 0.70, is_call=False)
        legs = [(+1, False, long_k, 180)]

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

        # Credit: profit_target on premium collected; stop at -stop_mult × credit
        # Debit:  profit_target on premium paid; stop at -stop_pct × debit
        if is_credit:
            hit_profit = pnl_ratio >= profit_target and day_idx >= min_hold
            hit_stop   = pnl_ratio <= -stop_mult
        else:
            hit_profit = pnl_ratio >= profit_target and day_idx >= min_hold
            hit_stop   = pnl_ratio <= -stop_pct

        # Short leg roll (for strategies with a 21d or 45d short leg)
        short_dtes = [dte for action, _, _, dte in legs if action == -1]
        min_short_dte = min((dte - day_idx for dte in short_dtes), default=999)
        hit_roll = min_short_dte <= 21

        if hit_profit:   reason = "50pct_profit"
        elif hit_stop:   reason = "stop_loss"
        elif hit_roll:   reason = "roll_21dte"
        else:            continue

        pnl_usd = pnl_ratio * option_premium * contracts
        return {"pnl": pnl_usd, "reason": reason, "days": day_idx,
                "spx_chg_pct": (spx_now - spx_e) / spx_e * 100}

    return {"pnl": 0.0, "reason": "end_of_sim", "days": max_dte,
            "spx_chg_pct": 0.0}


# ─── 扫描器 ──────────────────────────────────────────────────────────────────
STRATEGIES = [
    # 信用（已验证）
    ("bcs_45",              "BCS credit",       "信用", 2, "低"),
    ("ic_sym_45",           "IC sym credit",    "信用", 4, "低"),
    ("bps_hv_45",           "BPS HV credit",    "信用", 2, "低"),
    # 借方方向性
    ("bear_put_spread_45",  "Bear Put Spread",  "借方方向", 2, "低"),
    ("bear_put_diag",       "Bear Put Diagonal","借方方向", 2, "中"),
    # Calendar / Theta 中性
    ("put_calendar_45_21",  "Put Calendar",     "借方中性", 2, "中"),
    # LEAP
    ("leap_put_90",         "LEAP Put 90d",     "借方方向", 1, "低"),
    ("leap_put_180",        "LEAP Put 180d",    "借方方向", 1, "低"),
]

def run_scan(candidate_df, env_label):
    print(f"\n{'='*80}")
    print(f"环境：{env_label}  ({len(candidate_df)} 候选天)")
    print(f"{'策略':<22} {'类型':<10} {'腿':>3} {'维护':>5} {'笔数':>5} "
          f"{'WR':>6} {'均PnL':>8} {'总PnL':>10} {'Sharpe':>8}")
    print("-" * 80)

    results_all = []
    for strat_key, label, stype, legs, maint in STRATEGIES:
        res_list = []
        last_exit = pd.Timestamp("1990-01-01")
        max_dte = {"bcs_45":45,"ic_sym_45":45,"bps_hv_45":45,
                   "bear_put_spread_45":45,"bear_put_diag":90,
                   "put_calendar_45_21":45,"leap_put_90":90,"leap_put_180":180}[strat_key]
        hold_gap = max_dte

        for date, row in candidate_df.iterrows():
            if (date - last_exit).days < hold_gap:
                continue
            r = sim(date, strat_key, price_df)
            if r:
                r["date"] = date
                res_list.append(r)
                last_exit = date + pd.Timedelta(days=r["days"])

        if not res_list:
            print(f"  {label:<22} {stype:<10} {legs:>3} {maint:>5}  {'—':>5}")
            continue

        pnls   = [r["pnl"] for r in res_list]
        wr     = sum(1 for p in pnls if p > 0) / len(pnls) * 100
        avg    = np.mean(pnls)
        tot    = sum(pnls)
        std    = np.std(pnls) if len(pnls) > 1 else 1e-9
        sharpe = avg / std
        results_all.append((strat_key, label, stype, legs, maint,
                             len(pnls), wr, avg, tot, sharpe))
        print(f"  {label:<22} {stype:<10} {legs:>3} {maint:>5} {len(pnls):>5} "
              f"{wr:>5.0f}% {avg:>+8.0f} {tot:>+10.0f} {sharpe:>+8.3f}")

    return results_all


# 全量（不区分 VIX 趋势）
all_res   = run_scan(base, "BEARISH + HIGH_VOL ALL (VIX non-EXTREME)")

# VIX FLAT + FALLING 子集（排除最危险的 RISING）
safe = base[base["vix_trend"].isin(["FLAT", "FALLING"])]
safe_res  = run_scan(safe, "BEARISH + HIGH_VOL + VIX FLAT or FALLING")

# ─── 汇总：多维度评分 ────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("综合评分（VIX FLAT+FALLING 子集）：WR × Sharpe / 腿数  → 简洁性调整后性价比")
print("-" * 80)
if safe_res:
    scored = []
    for row in safe_res:
        strat_key, label, stype, legs, maint, n, wr, avg, tot, sharpe = row
        score = (wr / 100) * max(sharpe, 0) / legs  # 简洁性惩罚
        scored.append((score, label, stype, legs, maint, n, wr, avg, sharpe))
    for score, label, stype, legs, maint, n, wr, avg, sharpe in sorted(scored, reverse=True):
        print(f"  {label:<22} score={score:.3f}  WR={wr:.0f}%  Sharpe={sharpe:+.3f}  "
              f"腿={legs}  n={n}  均PnL=${avg:+.0f}")

print("\n完成。")
