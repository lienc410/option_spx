"""SPEC-094.5 F2 — 再生 data/q042_backtest_trades.csv（walk-forward 账本）。

该 CSV 此前无入库生成器（SPEC-094 F8 一次性产物）；本脚本修复可复现性缺口：
从 signals.q042_trigger.get_q042_history（生产状态机 walk-forward）+ 生产 INC
定价（strategy.q042_pricing.estimate_debit）按【当前 strategy.q042_sizing 常量】
再生全表——参数改动（如 094.5 宽度 2.5%→5%）跑一次本脚本即让 dashboard
回测视图跟上代码真值，无 mirror 漂移。

记账惯例（与原表逐列一致，AC-94.5-4 金行复核）：
  - contracts = 1.0 research scale；无摩擦；
  - 结算 = 首个 date ≥ signal+1+DTE 的交易日收盘内在价值；
  - exit_pnl = (intrinsic − debit_per_share) × 100；
  - account_pct = per-share ROI × 0.10（legacy 10%-sizing 显示口径，
    非生产 sizing——生产 A 为 12.5% staged，见 SPEC-104）；
  - 数据末尾未结算仓 → status=OPEN，exit 字段按最新收盘 MTM 快照。
Q100 P1 注（保守方向已量化）：INC 对 D30/+5% 高估 debit ~+12%（真实链
2026-05-04 锚点）→ 本表对新结构的历史 PnL 系统性【低估】，方向保守。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signals.q042_trigger import get_q042_history            # noqa: E402
from strategy.q042_pricing import estimate_debit             # noqa: E402
from strategy.q042_sizing import (                           # noqa: E402
    _DTE_A, _DTE_B, _OTM_PCT_A, _OTM_PCT_B, _STRIKE_ROUND,
)

CSV = ROOT / "data" / "q042_backtest_trades.csv"
LEGACY_DISPLAY_SIZING = 0.10   # account_pct 显示口径（原表惯例）


def _round_strike(px: float) -> int:
    return int(round(px / _STRIKE_ROUND) * _STRIKE_ROUND)


def _load_spx() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    vix = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl")
    vi = pd.to_datetime(vix.index)
    if vi.tz is not None:
        vi = vi.tz_localize(None)
    vix.index = vi.normalize()
    spx = df.loc["2007-01-01":]
    return spx, vix["Close"].reindex(spx.index).ffill()


def build_rows() -> pd.DataFrame:
    spx, vix = _load_spx()
    close = spx["Close"]
    wf = spx.rename(columns={c: c.lower() for c in spx.columns})
    end = str(close.index[-1].date())
    entries_a, entries_b = get_q042_history(wf, start="2007-01-01", end=end)

    rows = []
    for sleeve, entries, otm, dte in (
        ("A", entries_a, _OTM_PCT_A, _DTE_A),
        ("B", entries_b, _OTM_PCT_B, _DTE_B),
    ):
        for e in entries:
            sig = pd.Timestamp(e["signal_date"])
            S = float(close.loc[sig])
            vx = float(vix.loc[sig])
            kl = _round_strike(S)
            ks = _round_strike(S * (1.0 + otm))
            debit = estimate_debit(S=S, K_long=float(kl), K_short=float(ks),
                                   dte=dte, vix=vx)
            expiry = sig + pd.Timedelta(days=1 + dte)
            pos = close.index.searchsorted(expiry)
            if pos < len(close):
                exit_d, status = close.index[pos], "CLOSED"
            else:
                exit_d, status = close.index[-1], "OPEN"     # MTM 快照行
            st = float(close.loc[exit_d])
            intrinsic = max(st - kl, 0.0) - max(st - ks, 0.0)
            pnl = (intrinsic - debit) * 100.0
            rows.append({
                "sleeve_id": sleeve,
                "signal_date": e["signal_date"],
                "entry_date": e["entry_date"],
                "exit_date": str(exit_d.date()),
                "ath_at_signal": round(e["ath_at_signal"], 2),
                "ddath_at_signal": round(e["ddath_at_signal"], 4),
                "long_strike": kl,
                "short_strike": ks,
                "contracts": 1.0,
                "debit_per_share": round(debit, 4),
                "exit_pnl": round(pnl, 1),
                "account_pct": round(pnl / (debit * 100.0) * LEGACY_DISPLAY_SIZING, 4),
                "status": status,
            })
    df = pd.DataFrame(rows).sort_values(["signal_date", "sleeve_id"])
    return df


def main() -> int:
    df = build_rows()
    df.to_csv(CSV, index=False)
    for s in ("A", "B"):
        g = df[(df.sleeve_id == s) & (df.status == "CLOSED")]
        print(f"sleeve {s}: n={len(g)} (+{(df.sleeve_id == s).sum() - len(g)} OPEN) "
              f"WR={(g.exit_pnl > 0).mean()*100:.0f}% total(1ct)=${g.exit_pnl.sum():,.0f}")
    print(f"wrote {CSV.relative_to(ROOT)} rows={len(df)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
