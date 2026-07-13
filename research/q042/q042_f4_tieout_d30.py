"""SPEC-094.5 F3 — D≈30 真实链 tie-out（生产结构 ATM/+5% + legacy 参照 +2.5%）。

背景：F4 对账历史只覆盖 SPEC-094 原结构（DTE 84-88，2026-05-04..08 五天），
094.1 换 D30 后生产结构从未对过账（Q100 P1 §2.3）。本脚本在 old Air 跑
（链归档在那边），对最近 N 个交易日的 SPX 链快照计算 broker mid debit vs
生产模型 debit（strategy.q042_pricing.estimate_debit——tie-out 验证的是
生产在用的模型，非 CALIB）。

预注册（SPEC-094.5，Q100 §2 真实链锚点外推）：D30/+5% 的 model 预期高于
broker（INC 高估宽腿 debit），delta_pct = (broker−model)/broker 预期落在
[−15%, −5%]；PASS 门槛沿 F4：5 日中位 |delta_pct| < 15%。区间外 = 新信息。

口径：
  - S（现货参照）：目标到期链上 CALL delta 最接近 0.50 的 strike 线性插值；
  - VIX：q042_executor.log 当日 EOD 行解析（生产自己记录的值，同源）；
  - strikes：round5(S)、round5(S×(1+w))，broker 腿取最近上市 strike mid；
  - 输出 schema 与 data/q042_f4_tieout_history.csv 完全一致（dte 列区分新旧行）。

用法（old Air）：python3 research/q042/q042_f4_tieout_d30.py --out /tmp/q042_tieout_d30.csv
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from strategy.q042_pricing import estimate_debit          # noqa: E402
from strategy.q042_sizing import _OTM_PCT_A, _STRIKE_ROUND  # noqa: E402

CHAINS = REPO / "data" / "q041_chains"
EXEC_LOG = REPO / "logs" / "q042_executor.log"
WIDTHS = (_OTM_PCT_A, 0.025)          # 生产宽度 + legacy 参照
TARGET_DTE = 30


def vix_from_log(date: str) -> float | None:
    pat = re.compile(rf"{date} 16:15.*EOD eval {date} SPX=\S+ VIX=([\d.]+)")
    for line in EXEC_LOG.read_text(errors="ignore").splitlines():
        m = pat.search(line)
        if m:
            return float(m.group(1))
    return None


def spot_from_chain(ch: pd.DataFrame) -> float:
    """delta 最接近 0.50 的两档 strike 线性插值出 S。"""
    c = ch.dropna(subset=["delta"]).sort_values("strike")
    c = c[(c.delta > 0.2) & (c.delta < 0.8)]
    if len(c) < 2:
        raise ValueError("insufficient deltas around ATM")
    below = c[c.delta >= 0.5].tail(1)
    above = c[c.delta < 0.5].head(1)
    if below.empty or above.empty:
        return float(c.iloc[(c.delta - 0.5).abs().argmin()].strike)
    d0, k0 = float(below.delta.iloc[0]), float(below.strike.iloc[0])
    d1, k1 = float(above.delta.iloc[0]), float(above.strike.iloc[0])
    w = (d0 - 0.5) / (d0 - d1) if d0 != d1 else 0.0
    return k0 + w * (k1 - k0)


def nearest_row(ch: pd.DataFrame, k: float) -> pd.Series:
    return ch.loc[(ch.strike - k).abs().sort_values().index[0]]


def tieout_for_date(date: str) -> list[dict]:
    pq = CHAINS / date / "SPX.parquet"
    if not pq.exists():
        return []
    df = pd.read_parquet(pq)
    calls = df[df.option_type == "CALL"].copy()
    dtes = sorted(calls.dte.unique(), key=lambda d: abs(d - TARGET_DTE))
    dte = int(dtes[0])
    ch = calls[calls.dte == dte]
    vix = vix_from_log(date)
    if vix is None:
        print(f"[{date}] no VIX in executor log — skip")
        return []
    S = spot_from_chain(ch)
    kl = round(S / _STRIKE_ROUND) * _STRIKE_ROUND
    rows = []
    long_row = nearest_row(ch, kl)
    for w in WIDTHS:
        ks = round(S * (1 + w) / _STRIKE_ROUND) * _STRIKE_ROUND
        short_row = nearest_row(ch, ks)
        broker_debit = float(long_row.mid) - float(short_row.mid)
        model = estimate_debit(S=S, K_long=float(long_row.strike),
                               K_short=float(short_row.strike), dte=dte, vix=vix)
        rows.append({
            "snapshot_date": date,
            "vix": vix,
            "dte": dte,
            "expiry": str(short_row.expiry),
            "K_long_ATM": float(long_row.strike),
            "K_short": float(short_row.strike),
            "actual_otm_pct": round((float(short_row.strike) / S - 1) * 100, 2),
            "broker_long_mid": float(long_row.mid),
            "broker_short_mid": float(short_row.mid),
            "broker_debit": round(broker_debit, 2),
            "model_debit": round(model, 2),
            "delta_pct": round((broker_debit - model) / broker_debit * 100, 2),
            "broker_long_iv": float(long_row.iv),
            "broker_short_iv": float(short_row.iv),
            "broker_long_volume": int(long_row.volume),
            "broker_short_volume": int(short_row.volume),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--out", type=Path, default=None,
                    help="输出 CSV（默认 append 到 data/q042_f4_tieout_history.csv）")
    args = ap.parse_args()
    dates = sorted(d.name for d in CHAINS.iterdir()
                   if (d / "SPX.parquet").exists())[-args.days:]
    rows = []
    for d in dates:
        rows.extend(tieout_for_date(d))
    if not rows:
        print("no rows produced")
        return 1
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    prod = out[out.actual_otm_pct > 3.5]          # +5% 生产结构行
    med = prod.delta_pct.abs().median()
    print(f"\n生产结构(+5%) 5日中位 |delta_pct| = {med:.2f}%  "
          f"{'PASS (<15%)' if med < 15 else 'FAIL'}  "
          f"预注册区间 [-15,-5] 命中: {prod.delta_pct.between(-15, -5).mean()*100:.0f}%")
    target = args.out or (REPO / "data" / "q042_f4_tieout_history.csv")
    header = not target.exists()
    out.to_csv(target, mode="a", header=header, index=False)
    print(f"appended {len(out)} rows -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
