# -*- coding: utf-8 -*-
"""清仓总账 P&L 台账 (每次扫描重建, display-only)

口径:
  接手基线 = 2026-05-31 中信App快照(市值 + 持有收益, App摊薄口径——含更早的已实现亏损)
  份额链   = 5-31市值 ÷ 当日单位净值 起链; 逐笔交易扣减(有显式份额用显式——App真值,
             无则按 pct_sold×剩余); 全额赎回以显式份额自校正链误差
  已落袋   = 卖出份额 × 结算日单位净值(recorded_at ET+12h→北京, 15:00截单规则推结算日;
             净值未出时用最新值并标"暂估")
  在手盯市 = 剩余份额 × 最新单位净值(修正 positions.csv 账面不随净值漂移的盲区)
  累计盈亏 = 已落袋 + 在手盯市 − 接手成本; 拆分 接手→5-31(旧账) / 5-31→今(清仓期)

已知精度界: 未扣赎回费(次新基 0.25-0.75%档, 全程约¥0.5-1.5k); 结算日±1天; 份额链±2%
(有显式份额处自校正)。分红检查: 各基金 累计=单位净值(无现金分红), 份额法安全。
"""
from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

OUTDIR = Path(__file__).resolve().parent
PNL_JSON = OUTDIR / "fund_pnl.json"
TRADE_LOG = OUTDIR / "trade_log.csv"

# 接手基线: 2026-05-31 中信App快照 {code: (name, 市值, 持有收益¥)}
TAKEOVER = {
    "024930": ("华夏卓越成长混合",     152086.10,  52086.10),
    "007119": ("睿远成长价值混合A",    141325.43,  57511.75),
    "024915": ("华夏红利价值混合",     136386.96, -31229.63),
    "009076": ("工银圆兴混合",         133813.91,  13813.91),
    "013610": ("中信保诚前瞻优势混合", 103306.75,     845.89),
    "011692": ("华安研究智选混合A",     93525.56,  -8204.56),
    "003095": ("中欧医疗健康混合",      50730.79, -65286.59),
    "007880": ("朱雀产业智选混合",      42118.97,  -8308.07),
    "009010": ("华夏兴阳一年持有混合",  32060.03, -37939.97),
    "010864": ("泓德卓远混合A",         22936.78,  -2932.61),
}
BASELINE_DATE = "2026-05-31"


def _unit_nav_series(code: str) -> pd.Series:
    import akshare as ak
    df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    df["净值日期"] = pd.to_datetime(df["净值日期"])
    df = df.sort_values("净值日期")
    return pd.Series(pd.to_numeric(df["单位净值"], errors="coerce").values,
                     index=df["净值日期"]).dropna()


def _settle_date(recorded_at: str, trade_date: str) -> pd.Timestamp:
    """recorded_at(ET) + 12h → 北京墙钟; <15:00 当日截单, 否则次日。返回候选结算日(自然日)。"""
    try:
        bj = datetime.fromisoformat(recorded_at) + timedelta(hours=12)
    except (ValueError, TypeError):
        return pd.Timestamp(trade_date) + pd.Timedelta(days=1)
    d = pd.Timestamp(bj.date())
    return d if bj.hour < 15 else d + pd.Timedelta(days=1)


def build_ledger() -> dict:
    navs = {}
    for c in TAKEOVER:
        navs[c] = _unit_nav_series(c)
        time.sleep(0.3)

    trades = []
    if TRADE_LOG.exists():
        with open(TRADE_LOG, encoding="utf-8") as f:
            trades = list(csv.DictReader(f))

    base = pd.Timestamp(BASELINE_DATE)
    funds, tot = {}, {"cost": 0.0, "proceeds": 0.0, "current": 0.0,
                      "recorded_amt": 0.0, "estimated": False}
    for c, (name, mv0, pnl0) in TAKEOVER.items():
        s = navs[c]
        nav0 = float(s[s.index <= base].iloc[-1])
        shares = mv0 / nav0
        shares_start, proceeds, est = shares, 0.0, False
        for t in [x for x in trades if x["code"] == c]:
            cand = _settle_date(t.get("recorded_at", ""), t.get("trade_date", ""))
            after = s[s.index >= cand]
            if len(after):
                pnav = float(after.iloc[0])
            else:                       # 结算净值未公布 → 暂估(用最新)
                pnav, est = float(s.iloc[-1]), True
            if t.get("shares"):
                ssold = float(t["shares"])          # App 显式份额 = 真值(可自校正链误差)
            else:
                ssold = float(t.get("pct_sold") or 0) * shares
            if float(t.get("pct_sold") or 0) >= 0.999 and not t.get("shares"):
                ssold = shares
            proceeds += ssold * pnav
            shares = max(0.0, shares - ssold)
            tot["recorded_amt"] += float(t.get("amount_cny") or 0)
        latest_nav = float(s.iloc[-1])
        current = shares * latest_nav
        cost = mv0 - pnl0
        funds[c] = {
            "name": name, "cost": round(cost, 2), "mv_0531": round(mv0, 2),
            "pnl_pre": round(pnl0, 2),
            "proceeds": round(proceeds, 2), "current": round(current, 2),
            "shares_left": round(shares, 2), "shares_start": round(shares_start, 2),
            "held_pct": round(shares / shares_start, 4) if shares_start else 0,
            "pnl_total": round(proceeds + current - cost, 2),
            "pnl_since": round(proceeds + current - mv0, 2),
            "estimated": est,
            "nav_date": s.index[-1].strftime("%Y-%m-%d"),
        }
        tot["cost"] += cost
        tot["proceeds"] += proceeds
        tot["current"] += current
        tot["estimated"] = tot["estimated"] or est

    mv0_total = sum(v[1] for v in TAKEOVER.values())
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline": {"date": BASELINE_DATE, "mv": round(mv0_total, 2),
                     "cost": round(tot["cost"], 2),
                     "note": "接手基线=2026-05-31 中信App快照(摊薄口径, 含更早已实现亏损)"},
        "totals": {
            "proceeds": round(tot["proceeds"], 2),
            "current": round(tot["current"], 2),
            "recovered": round(tot["proceeds"] + tot["current"], 2),
            "pnl_total": round(tot["proceeds"] + tot["current"] - tot["cost"], 2),
            "pnl_pre_baseline": round(mv0_total - tot["cost"], 2),
            "pnl_since_baseline": round(tot["proceeds"] + tot["current"] - mv0_total, 2),
            "pnl_total_pct": round((tot["proceeds"] + tot["current"] - tot["cost"]) / tot["cost"], 6),
            "recorded_amt": round(tot["recorded_amt"], 2),
            "estimated": tot["estimated"],
        },
        "caveats": "未扣赎回费(约¥0.5-1.5k); 结算日±1天; 份额链±2%(显式份额处自校正); 净到手以App交割单为准",
        "funds": funds,
    }
    import os
    tmp = str(PNL_JSON) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PNL_JSON)
    print(f"写出 {PNL_JSON}  总盈亏 {payload['totals']['pnl_total']:+,.0f}"
          f" (旧账 {payload['totals']['pnl_pre_baseline']:+,.0f} / 清仓期 {payload['totals']['pnl_since_baseline']:+,.0f})")
    return payload


def refresh_safe():
    """主扫描内嵌入口: 全程隔离, 失败不影响主扫描。每次扫描都跑(P&L 随净值日变)。"""
    try:
        build_ledger()
    except Exception as e:  # noqa: BLE001
        print(f"  P&L 台账刷新失败(跳过): {type(e).__name__}: {e}")


if __name__ == "__main__":
    build_ledger()
