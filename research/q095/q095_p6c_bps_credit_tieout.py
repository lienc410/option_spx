"""Q095 P6c — BPS credit 真实链对账（外审 standing comment #2：定价 CALIB 优先级最高）。

外审论点：CS 定价误差近线性，BPS credit 对 skew/滑点/smile 曲率极敏感——
真实成交 credit 若比模型肥 20-30%，P6 的 EV 差距幅度会显著变化（方向未必）。
本脚本用 old Air 每日 SPX 链归档做 Δ0.30/Δ0.15 D≈30 put spread 的
real mid credit vs 三模型对账。这是 CALIB 验证的【平静期段】；危机期链
不可得，仍留 standing（分层与 fallback 首用门槛不变）。

口径：short 腿 = 链上 |delta| 最近 0.30 的 put，long 腿 = 最近 0.15；
real = mid_short − mid_long；模型对同一 strikes 定价（r=4.5%, T=act/365）：
FLAT = σ=VIX；HAIRCUT = σ=VIX−2vp（P6 括号下端）；CALIB = SPEC-119 put 曲线。
VIX = 生产 executor 日志当日实值。
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

from pricing import core as pcore                      # noqa: E402
from pricing.calibration import load_offsets           # noqa: E402
from pricing.sigma import SigmaMode, sigma_for         # noqa: E402

CHAINS = REPO / "data" / "q041_chains"
EXEC_LOG = REPO / "logs" / "q042_executor.log"
R = 0.045


def vix_from_log(date: str):
    pat = re.compile(rf"EOD eval {date} SPX=\S+ VIX=([\d.]+)")
    for line in EXEC_LOG.read_text(errors="ignore").splitlines():
        m = pat.search(line)
        if m:
            return float(m.group(1))
    return None


def nearest_delta_row(puts: pd.DataFrame, target: float) -> pd.Series:
    return puts.loc[(puts.delta.abs() - target).abs().sort_values().index[0]]


def spot_from_puts(puts: pd.DataFrame) -> float:
    c = puts[(puts.delta.abs() > 0.35) & (puts.delta.abs() < 0.65)].sort_values("strike")
    if len(c) < 2:
        raise ValueError("no ATM puts")
    below = c[c.delta.abs() < 0.5].tail(1)
    above = c[c.delta.abs() >= 0.5].head(1)
    if below.empty or above.empty:
        return float(c.iloc[(c.delta.abs() - 0.5).abs().argmin()].strike)
    d0, k0 = abs(float(below.delta.iloc[0])), float(below.strike.iloc[0])
    d1, k1 = abs(float(above.delta.iloc[0])), float(above.strike.iloc[0])
    w = (0.5 - d0) / (d1 - d0) if d1 != d0 else 0.0
    return k0 + w * (k1 - k0)


def tieout(date: str, offsets) -> dict | None:
    pq = CHAINS / date / "SPX.parquet"
    if not pq.exists():
        return None
    df = pd.read_parquet(pq)
    puts = df[df.option_type == "PUT"]
    dtes = sorted(puts.dte.unique(), key=lambda d: abs(d - 30))
    dte = int(dtes[0])
    ch = puts[puts.dte == dte]
    vix = vix_from_log(date)
    if vix is None:
        return None
    S = spot_from_puts(ch)
    sr = nearest_delta_row(ch, 0.30)
    lr = nearest_delta_row(ch, 0.15)
    real = float(sr.mid) - float(lr.mid)
    T = dte / 365.0

    def model(tag):
        out = 0.0
        for row, sgn in ((sr, +1), (lr, -1)):
            ad = abs(float(row.delta))
            if tag == "FLAT":
                sig = vix / 100.0
            elif tag == "HAIRCUT":
                sig = max(vix - 2.0, 1.0) / 100.0
            else:
                sig = sigma_for(SigmaMode.CALIB, vix=vix, option_type="PUT",
                                abs_delta=ad, dte=dte, offsets=offsets)
            out += sgn * pcore.put_price(S, float(row.strike), T, sig, R)
        return out

    rec = {"date": date, "dte": dte, "vix": vix, "S": round(S, 1),
           "k_short": float(sr.strike), "k_long": float(lr.strike),
           "d_short": round(float(sr.delta), 3), "d_long": round(float(lr.delta), 3),
           "real_credit": round(real, 2)}
    for tag in ("FLAT", "HAIRCUT", "CALIB"):
        m = model(tag)
        rec[f"{tag.lower()}"] = round(m, 2)
        rec[f"{tag.lower()}_err_pct"] = round((m - real) / real * 100, 1)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    offsets = load_offsets()
    dates = sorted(d.name for d in CHAINS.iterdir()
                   if (d / "SPX.parquet").exists())[-args.days:]
    rows = [r for d in dates if (r := tieout(d, offsets))]
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    for tag in ("flat", "haircut", "calib"):
        print(f"{tag.upper():8s} 中位误差 {df[f'{tag}_err_pct'].median():+.1f}%")
    if args.out:
        df.to_csv(args.out, index=False)
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
