"""Q093 P2 — Aftermath × Q042 co-fire co-loss 账本(Q066 standing-trigger 欠账)。

Question: aftermath 与 Q042 co-active 窗口的同向亏损在 PnL 层有多大?
Q066 的 "low-overlap (0.9% day-level) / non-redundant" 在 D30 结构 +
12.5% 生产 sizing 下是否仍成立?(Q066 触发条件 2026-05-17 已被 SPEC-104
cap 上调满足,至今未执行;Q072 P3.3 又给出 HV-heavy 日 +0.26 同向相关。)

Method(risk-audit,只出账本与 go/no-go,不做 gate/cutpoint 优化):
  1. 事件级 co-fire ledger:Q042 Sleeve A D30 窗口(n=35) × 主引擎 HV
     交易窗口(fresh run,$500k canonical)重叠;双口径——
     宽口径 = 全部 HV 策略(Q072 P3.3 同口径);
     严口径 = HV 交易且 entry 日在 SPEC-064 aftermath 窗口内
     (q072_p1_daily_flags.is_aftermath,day-level)。
  2. 日级 co-active:持仓日历重叠率(更新 Q066 的 0.9% 到 D30),
     pre/post-2020 分层。
  3. 线性摊分日 PnL(Q072 P3.3 先例,已知局限)在 co-active 日的联合分布:
     同日双负率、co-loss 日合计、worst 21td 滚动联合窗口。
  4. go/no-go(charter):post-2020 口径 worst co-window 联合亏损 >
     1.5 × 单 sleeve worst → 提联合 cap 设计稿;否则记录并 close。

Scale 口径(Q029 强制标注):HV/aftermath PnL = research scale(1×SPX equiv
fractional @ $500k canonical;live est ≈ ×0.1 走 XSP);Q042 = 生产 sizing
12.5% × $500k canonical(n_ct = floor($62.5k / debit_per_contract))。
相关性/比率与 scale 无关;美元数各带各的标签,不造假合计。

Output: q093_p2_cofire_ledger.csv + q093_p2_daily_coactive.csv + 终端摘要。
"""
from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "research" / "q093"
Q042_CSV = ROOT / "data" / "q042_backtest_trades.csv"
FLAGS_CSV = ROOT / "research" / "q072" / "q072_p1_daily_flags.csv"

ACCOUNT = 500_000.0
Q042_NEED = 62_500.0          # 12.5% × $500k canonical
ERAS = {"pre2020": ("2007-01-01", "2019-12-31"), "post2020": ("2020-01-01", "2026-12-31")}


def load_q042() -> pd.DataFrame:
    df = pd.read_csv(Q042_CSV)
    df = df[df["sleeve_id"] == "A"].copy()
    debit_ct = df["debit_per_share"] * 100.0
    df["n_ct"] = (Q042_NEED // debit_ct).astype(int)
    df["pnl_prod"] = df["exit_pnl"] * df["n_ct"]          # CSV pnl per 1 contract
    df["entry"] = pd.to_datetime(df["entry_date"])
    df["exit"] = pd.to_datetime(df["exit_date"])
    return df


def load_hv_trades() -> pd.DataFrame:
    from backtest.engine import run_backtest
    trades, _, _ = run_backtest(start_date="2007-01-01", verbose=False,
                                account_size=ACCOUNT)
    rows = []
    for t in trades:
        sname = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
        if "High Vol" not in sname:
            continue
        rows.append({
            "strategy": sname,
            "entry": pd.Timestamp(str(t.entry_date)),
            "exit": pd.Timestamp(str(t.exit_date)),
            "pnl_research": float(t.exit_pnl),
        })
    return pd.DataFrame(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    flags = pd.read_csv(FLAGS_CSV, parse_dates=["date"]).set_index("date")
    aftermath_days = set(flags.index[flags["is_aftermath"].astype(bool)])

    q042 = load_q042()
    hv = load_hv_trades()
    hv["strict_aftermath"] = hv["entry"].isin(aftermath_days)
    print(f"HV trades n={len(hv)} (strict aftermath-entry n={int(hv['strict_aftermath'].sum())}) | "
          f"Q042 A n={len(q042)}")

    # ── 1. 事件级 co-fire ledger ────────────────────────────────────────────
    ledger = []
    for _, q in q042.iterrows():
        for _, h in hv.iterrows():
            o0, o1 = max(q["entry"], h["entry"]), min(q["exit"], h["exit"])
            if o0 > o1:
                continue
            ledger.append({
                "q042_entry": q["entry"].date(), "q042_exit": q["exit"].date(),
                "q042_pnl_prod": round(q["pnl_prod"], 0), "q042_n_ct": q["n_ct"],
                "hv_strategy": h["strategy"],
                "hv_entry": h["entry"].date(), "hv_exit": h["exit"].date(),
                "hv_pnl_research": round(h["pnl_research"], 0),
                "overlap_days": (o1 - o0).days + 1,
                "strict_aftermath": bool(h["strict_aftermath"]),
                "era": "post2020" if q["entry"] >= pd.Timestamp("2020-01-01") else "pre2020",
                "both_neg": bool(q["pnl_prod"] < 0 and h["pnl_research"] < 0),
            })
    led = pd.DataFrame(ledger)
    led.to_csv(OUT / "q093_p2_cofire_ledger.csv", index=False)

    print("\n=== 事件级 co-fire（trade-window 重叠对）===")
    for scope, sub in [("宽口径(全 HV)", led),
                       ("严口径(aftermath-entry)", led[led["strict_aftermath"]] if len(led) else led)]:
        if len(sub) == 0:
            print(f"{scope}: 0 对")
            continue
        for era in ("pre2020", "post2020", None):
            s = sub if era is None else sub[sub["era"] == era]
            if len(s) == 0:
                continue
            uniq_q = s.drop_duplicates("q042_entry")
            print(f"{scope} [{era or 'all'}]: {len(s)} 对 / {len(uniq_q)} 个 Q042 事件卷入 | "
                  f"双负 {int(s['both_neg'].sum())} 对 | "
                  f"双负对合计: q042 ${s.loc[s['both_neg'],'q042_pnl_prod'].sum():,.0f}(prod) + "
                  f"hv ${s.loc[s['both_neg'],'hv_pnl_research'].sum():,.0f}(research)")

    # ── 2. 日级 co-active + 线性摊分联合 PnL ────────────────────────────────
    idx = pd.bdate_range("2007-01-01", max(q042["exit"].max(), hv["exit"].max()))
    def active_flag(df):
        f = pd.Series(False, index=idx)
        for _, t in df.iterrows():
            f.loc[t["entry"]:t["exit"]] = True
        return f
    def linear_pnl(df, pnl_col):
        s = pd.Series(0.0, index=idx)
        for _, t in df.iterrows():
            span = s.loc[t["entry"]:t["exit"]]
            if len(span):
                s.loc[t["entry"]:t["exit"]] += t[pnl_col] / len(span)
        return s

    hv_active, q_active = active_flag(hv), active_flag(q042)
    hv_strict_active = active_flag(hv[hv["strict_aftermath"]])
    co = hv_active & q_active
    co_strict = hv_strict_active & q_active
    daily = pd.DataFrame({
        "hv_pnl": linear_pnl(hv, "pnl_research"),
        "q042_pnl": linear_pnl(q042, "pnl_prod"),
        "co_active": co, "co_active_strict": co_strict,
    })
    daily.to_csv(OUT / "q093_p2_daily_coactive.csv")

    print("\n=== 日级 co-active（持仓日历）===")
    for era, (a, b) in {**ERAS, "all": ("2007-01-01", "2026-12-31")}.items():
        d = daily.loc[a:b]
        n = len(d)
        print(f"[{era}] 交易日 {n} | 宽口径 co-active {int(d['co_active'].sum())} "
              f"({d['co_active'].mean()*100:.2f}%) | 严口径 {int(d['co_active_strict'].sum())} "
              f"({d['co_active_strict'].mean()*100:.2f}%)")

    print("\n=== co-active 日联合 PnL（线性摊分近似，Q072 P3.3 同法）===")
    for era, (a, b) in {**ERAS, "all": ("2007-01-01", "2026-12-31")}.items():
        d = daily.loc[a:b]
        c = d[d["co_active"]]
        if len(c) < 5:
            print(f"[{era}] co-active 日 n={len(c)} < 5，只记事实不算相关")
            continue
        both_neg = ((c["hv_pnl"] < 0) & (c["q042_pnl"] < 0))
        corr = c["hv_pnl"].corr(c["q042_pnl"])
        print(f"[{era}] n={len(c)} | corr={corr:+.3f} | 双负日 {int(both_neg.sum())} "
              f"({both_neg.mean()*100:.1f}%) | 双负日合计: hv ${c.loc[both_neg,'hv_pnl'].sum():,.0f}(research) "
              f"+ q042 ${c.loc[both_neg,'q042_pnl'].sum():,.0f}(prod)")

    # ── 3. worst 21td 滚动联合窗口 vs 单 sleeve worst（go/no-go）────────────
    print("\n=== worst 21td 滚动窗口（go/no-go: 联合 > 1.5×单边 worst?）===")
    roll_hv = daily["hv_pnl"].rolling(21).sum()
    roll_q = daily["q042_pnl"].rolling(21).sum()
    roll_joint = (daily["hv_pnl"] + daily["q042_pnl"]).rolling(21).sum()
    co_any = daily["co_active"].rolling(21).max().astype(bool)   # 窗口含 co-active 日
    for era, (a, b) in {**ERAS, "all": ("2007-01-01", "2026-12-31")}.items():
        m = (daily.index >= a) & (daily.index <= b)
        j = roll_joint[m & co_any]
        if len(j.dropna()) == 0:
            print(f"[{era}] 无含 co-active 的 21td 窗口")
            continue
        w_joint, w_joint_d = j.min(), j.idxmin()
        w_hv, w_q = roll_hv[m].min(), roll_q[m].min()
        ratio = w_joint / min(w_hv, w_q) if min(w_hv, w_q) < 0 else float("nan")
        print(f"[{era}] joint worst(co-window)=${w_joint:,.0f} @ {w_joint_d.date()} | "
              f"hv-only worst=${w_hv:,.0f} | q042-only worst=${w_q:,.0f} | "
              f"joint/单边worst 比={ratio:.2f} → {'GO(>1.5 提联合cap)' if ratio > 1.5 else 'NO-GO(记录即可)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
