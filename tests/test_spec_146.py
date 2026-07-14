"""SPEC-146 — 盘中数据源双源+披露 AC 测试（07-13 晨报静默回退教训）。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import strategy.selector as sel                              # noqa: E402


def _dfs():
    """2y 合成行情：VIX 宽幅历史 + 温和现值；SPX 缓升趋势。"""
    idx = pd.bdate_range(end="2026-07-13", periods=520)
    rng = np.random.default_rng(7)
    vix = 14 + 8 * np.abs(np.sin(np.linspace(0, 9, 520))) + rng.normal(0, 0.4, 520)
    vix_df = pd.DataFrame({"vix": vix}, index=idx)
    px = 6000 * np.cumprod(1 + rng.normal(0.0004, 0.007, 520))
    spx_df = pd.DataFrame({"close": px, "open": px, "high": px * 1.004,
                           "low": px * 0.996}, index=idx)
    return vix_df, spx_df


def _boom(*a, **k):
    raise RuntimeError("yfinance down")


@pytest.fixture
def offline_5m(monkeypatch):
    """盘中 5m 主源全灭（VIX+SPX）。"""
    monkeypatch.setattr(sel, "fetch_vix_history", _boom)
    monkeypatch.setattr(sel, "fetch_spx_history", _boom)


def test_ac1_schwab_second_source_used(offline_5m, monkeypatch):
    import schwab.client as sc
    monkeypatch.setattr(sc, "get_vix_quote", lambda: {"last": 16.4})
    monkeypatch.setattr(sc, "get_spx_quote", lambda: {"last": 7500.0})
    vix_df, spx_df = _dfs()
    rec = sel.get_recommendation(vix_df=vix_df, spx_df=spx_df, use_intraday=True)
    assert rec.vix_snapshot.vix == pytest.approx(16.4)
    assert any("Schwab 报价替代" in n for n in rec.data_notes)
    assert not any("双源均失败" in n for n in rec.data_notes)


def test_ac2_double_failure_disclosed_stale(offline_5m, monkeypatch):
    import schwab.client as sc
    monkeypatch.setattr(sc, "get_vix_quote", _boom)
    monkeypatch.setattr(sc, "get_spx_quote", _boom)
    vix_df, spx_df = _dfs()
    rec = sel.get_recommendation(vix_df=vix_df, spx_df=spx_df, use_intraday=True)
    # 回退值 = 上一收盘（df 末行），且必须显式披露
    assert rec.vix_snapshot.vix == pytest.approx(float(vix_df["vix"].iloc[-1]))
    assert any("双源均失败" in n and "上一收盘" in n for n in rec.data_notes)
    # 披露进推送正文
    from notify.telegram_bot import _format_recommendation
    body = _format_recommendation(rec)
    assert "双源均失败" in body


def test_ac3_healthy_intraday_no_notes(monkeypatch):
    vix_df, spx_df = _dfs()
    idx5 = pd.date_range("2026-07-13 09:30", periods=10, freq="5min")
    monkeypatch.setattr(sel, "fetch_vix_history",
                        lambda **k: pd.DataFrame({"vix": [16.1] * 10}, index=idx5))
    monkeypatch.setattr(sel, "fetch_spx_history",
                        lambda **k: pd.DataFrame({"close": [7500.0] * 10}, index=idx5))
    rec = sel.get_recommendation(vix_df=vix_df, spx_df=spx_df, use_intraday=True)
    assert rec.data_notes == []
    assert rec.vix_snapshot.vix == pytest.approx(16.1)
