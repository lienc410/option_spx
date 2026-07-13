"""SPEC-094.5 — Sleeve A 宽度 2.5%→5% AC 测试（AC-94.5-1..4；5=old Air tie-out，6=全套回归）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy import q042_sizing as sz                       # noqa: E402
from strategy.q042_sizing import compute_sizing              # noqa: E402

CSV = ROOT / "data" / "q042_backtest_trades.csv"
SPX_PKL = ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"


# ── AC-94.5-1 A 结构 = ATM/+5%, DTE30 ────────────────────────────────────────

def test_ac1_sleeve_a_width_5pct():
    assert sz._OTM_PCT_A == 0.05
    assert sz._DTE_A == 30                                   # DTE 不动（Q100 确认）
    long_k, short_k, contracts, est = compute_sizing(500_000, 7400.0, 25.0, "A")
    assert (long_k, short_k) == (7400, 7770)                 # 7400×1.05
    assert contracts > 0 and est is not None


# ── AC-94.5-2 Sleeve B 逐位不变 ──────────────────────────────────────────────

def test_ac2_sleeve_b_bit_identical():
    # 改动前冻结值（B 代码路径零 diff；回归 pin 防未来误伤）
    assert compute_sizing(500_000, 7400.0, 25.0, "B") == (7400, 7770, 2, 18360.63)
    assert compute_sizing(629_000, 7500.0, 18.0, "B") == (7500, 7875, 3, 17366.5)
    assert sz._OTM_PCT_B == 0.05 and sz._DTE_B == 90


# ── AC-94.5-3 再生 CSV：strike 规则 + 信号流对齐（integration，非 mock）──────

@pytest.mark.skipif(not (CSV.exists() and SPX_PKL.exists()), reason="repo data")
def test_ac3_regen_csv_strikes_and_signal_alignment():
    df = pd.read_csv(CSV)
    a = df[df.sleeve_id == "A"]
    # +5% 规则（strike 取整造成 ±0.4% 内摆动）
    ratio = a.short_strike / a.long_strike
    assert ratio.between(1.044, 1.056).all(), ratio[~ratio.between(1.044, 1.056)]
    # 信号流对齐：CSV == 生产 walk-forward（feedback_signal_translation_alignment_ac）
    spx = pd.read_pickle(SPX_PKL)
    idx = pd.to_datetime(spx.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    spx.index = idx.normalize()
    spx = spx.loc["2007-01-01":]
    from signals.q042_trigger import get_q042_history
    ea, eb = get_q042_history(
        spx.rename(columns={c: c.lower() for c in spx.columns}),
        start="2007-01-01", end=str(spx.index[-1].date()))
    assert set(a.signal_date) == {e["signal_date"] for e in ea}
    assert set(df[df.sleeve_id == "B"].signal_date) == {e["signal_date"] for e in eb}


# ── AC-94.5-4 金行复核：2007-02-27 手算一致 ──────────────────────────────────

@pytest.mark.skipif(not CSV.exists(), reason="repo data")
def test_ac4_golden_row():
    df = pd.read_csv(CSV)
    r = df[(df.sleeve_id == "A") & (df.signal_date == "2007-02-27")].iloc[0]
    assert (r.long_strike, r.short_strike) == (1400, 1470)   # S=1399.04 ×1.05→1469.0→1470
    # exit_pnl = (内在 − debit) × 100；2007-03-30 收盘 1420.86 → 内在 20.86
    assert r.exit_pnl == pytest.approx((1420.86 - 1400 - r.debit_per_share) * 100, abs=1.0)
    assert r.status == "CLOSED" and r.contracts == 1.0
