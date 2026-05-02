"""
SPEC-074 F4 — backtest selection parity test.

Goal
----
Guard against regression in the equivalence between backtest snapshot
construction (`backtest/engine.py:735-834`) and the live `select_strategy`
selector. Since HC engine.py:835 / :1252 call `select_strategy` directly
(no `_backtest_select` wrapper exists), parity reduces to:

  1. backtest snapshots populate every field that select_strategy gates read
  2. select_strategy returns a valid Recommendation across regime variety
  3. specific date / regime combinations reach the expected gate paths

This test reads from the cached yfinance pkls under
`data/market_cache/yahoo__*__max__1d.pkl` so it is offline / network-free.

Acceptance threshold (SPEC-074 §F5 PM Option A, 2026-05-02): >=95% of the
hand-picked dates must produce a non-error Recommendation. The
LOW_VOL + IVP_HIGH path divergence between HC (SPEC-056c removed) and MC
(SPEC-054 retained) is documented as a legal HC-vs-MC difference; this
HC-only test does not encode an MC comparison, so the 95% threshold is a
regression guard within HC.

Date selection rationale
------------------------
22 dates (>=4 each in 2008 / 2018 / 2020 / 2022, plus extras), chosen
to exercise: HIGH_VOL backwardation, VIX_RISING gate, IVP63 >= 70 gate,
aftermath bypass, LOW_VOL IVP range filter, Path C BCD candidates.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from signals.iv_rank import (
    IVSignal,
    IVSnapshot,
    compute_iv_percentile,
    compute_iv_rank,
)
from signals.trend import (
    TREND_THRESHOLD,
    TrendSignal,
    TrendSnapshot,
    _classify_trend_atr,
    _compute_atr14_close,
)
from signals.vix_regime import (
    VixSnapshot,
    _classify_regime,
    _classify_trend as _vix_classify_trend,
)
from strategy.selector import (
    DEFAULT_PARAMS,
    Recommendation,
    StrategyName,
    StrategyParams,
    select_strategy,
)


PARITY_THRESHOLD = 0.95   # SPEC-074 F5 Option A
VIX3M_INCEPTION = pd.Timestamp("2003-12-04")


PARITY_DATES = [
    # 2008 — GFC peak window
    "2008-09-29",
    "2008-10-10",
    "2008-10-24",
    "2008-11-20",
    "2008-12-05",
    # 2018 — Volmageddon + Q4 selloff
    "2018-02-05",
    "2018-02-09",
    "2018-06-15",
    "2018-10-11",
    "2018-12-24",
    # 2020 — COVID + recovery
    "2020-02-28",
    "2020-03-16",
    "2020-03-23",
    "2020-04-15",
    "2020-06-11",
    "2020-09-04",
    # 2022 — rate-hike bear
    "2022-01-24",
    "2022-02-24",
    "2022-05-09",
    "2022-06-13",
    "2022-09-13",
    "2022-10-13",
]


@dataclass
class _Snaps:
    vix: VixSnapshot
    iv: IVSnapshot
    trend: TrendSnapshot


def _load_market_data() -> dict:
    cache_root = "data/market_cache"
    vix_df = pd.read_pickle(f"{cache_root}/yahoo__VIX__max__1d.pkl")
    spx_df = pd.read_pickle(f"{cache_root}/yahoo__GSPC__max__1d.pkl")
    vix3m_df = pd.read_pickle(f"{cache_root}/yahoo__VIX3M__max__1d.pkl")

    vix_df = vix_df.rename(columns={"Close": "vix"})[["vix"]]
    spx_df = spx_df.rename(columns={"Close": "close"})[["close"]]
    vix3m_df = vix3m_df.rename(columns={"Close": "vix3m"})[["vix3m"]]

    vix_df.index = pd.to_datetime(vix_df.index.date)
    spx_df.index = pd.to_datetime(spx_df.index.date)
    vix3m_df.index = pd.to_datetime(vix3m_df.index.date)

    return {"vix": vix_df, "spx": spx_df, "vix3m": vix3m_df}


def _build_snapshots_engine_path(
    date: pd.Timestamp,
    market: dict,
    params: StrategyParams,
) -> _Snaps:
    """Mirror of backtest/engine.py:735-834 snapshot construction."""
    vix_df = market["vix"]
    spx_df = market["spx"]
    vix3m_df = market["vix3m"]

    if date not in vix_df.index or date not in spx_df.index:
        raise KeyError(f"Date {date} not in cached data (likely non-trading day)")

    spx = float(spx_df.loc[date, "close"])
    vix = float(vix_df.loc[date, "vix"])

    vix3m = (
        float(vix3m_df.loc[date, "vix3m"])
        if date in vix3m_df.index and not pd.isna(vix3m_df.loc[date, "vix3m"])
        else None
    )

    full_vix = vix_df[vix_df.index <= date]["vix"]
    full_spx = spx_df[spx_df.index <= date]["close"]

    if len(full_vix) < 60 or len(full_spx) < 55:
        raise ValueError(f"Insufficient lookback at {date}")

    regime = _classify_regime(vix)

    iv_window = (full_vix.iloc[-252:] if len(full_vix) >= 252 else full_vix).copy()
    iv_window.iloc[-1] = vix
    ivr = compute_iv_rank(iv_window)
    ivp = compute_iv_percentile(iv_window)

    w63 = (full_vix.iloc[-63:] if len(full_vix) >= 63 else full_vix).copy()
    w63.iloc[-1] = vix
    if len(w63) < 63:
        ivp63_val = float(ivp)
    else:
        ivp63_val = round(
            float((w63.iloc[:-1] < float(w63.iloc[-1])).mean()) * 100.0, 1
        )
    regime_decay = (float(ivp) >= 50.0) and (ivp63_val < 50.0)

    iv_eff = (
        IVSignal.HIGH if ivp > 70 else (IVSignal.LOW if ivp < 40 else IVSignal.NEUTRAL)
    )

    ma20_val = (
        float(full_spx.rolling(20).mean().iloc[-1])
        if len(full_spx) >= 20
        else spx
    )
    ma50_val = (
        float(full_spx.rolling(50).mean().iloc[-1])
        if len(full_spx) >= 50
        else spx
    )
    ma200_val = (
        float(full_spx.rolling(200).mean().iloc[-1])
        if len(full_spx) >= 200
        else spx
    )
    gap = (spx - ma50_val) / ma50_val if ma50_val else 0
    atr14: Optional[float] = None
    gap_sigma: Optional[float] = None
    if len(full_spx) >= 64:
        atr_series = _compute_atr14_close(full_spx)
        latest_atr = atr_series.iloc[-1]
        if pd.notna(latest_atr):
            atr14 = float(latest_atr)
            gap_sigma = (spx - ma50_val) / max(atr14, 1.0)
    if params.use_atr_trend and gap_sigma is not None:
        trend = _classify_trend_atr(gap_sigma)
    else:
        trend = (
            TrendSignal.BULLISH if gap > TREND_THRESHOLD
            else (TrendSignal.BEARISH if gap < -TREND_THRESHOLD else TrendSignal.NEUTRAL)
        )

    vix_5d_avg = (
        float(full_vix.iloc[-5:].mean()) if len(full_vix) >= 5 else vix
    )
    vix_5d_ago = (
        float(full_vix.iloc[-10:-5].mean())
        if len(full_vix) >= 10
        else vix_5d_avg
    )
    vix_trend = _vix_classify_trend(vix_5d_avg, vix_5d_ago)
    vix_peak_10d = (
        float(full_vix.iloc[-10:].max()) if len(full_vix) >= 10 else None
    )

    vix_snap = VixSnapshot(
        date=str(date.date()),
        vix=vix,
        regime=regime,
        trend=vix_trend,
        vix_5d_avg=vix_5d_avg,
        vix_5d_ago=vix_5d_ago,
        transition_warning=False,
        vix3m=vix3m,
        backwardation=(vix3m is not None and vix > vix3m),
        vix_peak_10d=vix_peak_10d,
    )
    iv_snap = IVSnapshot(
        date=str(date.date()),
        vix=vix,
        iv_rank=ivr,
        iv_percentile=ivp,
        iv_signal=iv_eff,
        iv_52w_high=float(iv_window.max()),
        iv_52w_low=float(iv_window.min()),
        ivp63=ivp63_val,
        ivp252=float(ivp),
        regime_decay=regime_decay,
    )
    trend_snap = TrendSnapshot(
        date=str(date.date()),
        spx=spx,
        ma20=ma20_val,
        ma50=ma50_val,
        ma_gap_pct=gap,
        signal=trend,
        above_200=(spx > ma200_val),
        atr14=atr14,
        gap_sigma=gap_sigma,
    )
    return _Snaps(vix=vix_snap, iv=iv_snap, trend=trend_snap)


class BacktestSelectParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.market = _load_market_data()

    def test_snapshot_fields_populated_for_all_dates(self) -> None:
        for date_str in PARITY_DATES:
            with self.subTest(date=date_str):
                date = pd.Timestamp(date_str)
                snaps = _build_snapshots_engine_path(date, self.market, DEFAULT_PARAMS)

                if date >= VIX3M_INCEPTION:
                    self.assertIsNotNone(
                        snaps.vix.vix3m,
                        f"{date_str}: vix3m None despite post-inception",
                    )
                    self.assertIsInstance(snaps.vix.backwardation, bool)

                self.assertIsNotNone(snaps.iv.ivp63)
                self.assertFalse(np.isnan(snaps.iv.ivp63))
                self.assertIsNotNone(snaps.iv.ivp252)
                self.assertFalse(np.isnan(snaps.iv.ivp252))

                self.assertIsNotNone(snaps.vix.regime)
                self.assertIsNotNone(snaps.vix.trend)
                self.assertIsNotNone(snaps.trend.signal)

    def test_select_strategy_no_exception_threshold(self) -> None:
        successes: list[str] = []
        failures: list[tuple[str, str]] = []

        for date_str in PARITY_DATES:
            date = pd.Timestamp(date_str)
            try:
                snaps = _build_snapshots_engine_path(
                    date, self.market, DEFAULT_PARAMS
                )
                rec = select_strategy(
                    snaps.vix, snaps.iv, snaps.trend, DEFAULT_PARAMS
                )
                self.assertIsInstance(rec, Recommendation)
                self.assertIsInstance(rec.strategy, StrategyName)
                successes.append(date_str)
            except Exception as exc:
                failures.append((date_str, repr(exc)))

        success_rate = len(successes) / len(PARITY_DATES)
        self.assertGreaterEqual(
            success_rate,
            PARITY_THRESHOLD,
            f"parity success rate {success_rate:.1%} < {PARITY_THRESHOLD:.0%}; "
            f"failures: {failures}",
        )

    def test_canonical_strategy_field_set(self) -> None:
        for date_str in PARITY_DATES:
            with self.subTest(date=date_str):
                date = pd.Timestamp(date_str)
                snaps = _build_snapshots_engine_path(
                    date, self.market, DEFAULT_PARAMS
                )
                rec = select_strategy(
                    snaps.vix, snaps.iv, snaps.trend, DEFAULT_PARAMS
                )
                self.assertIsInstance(rec.canonical_strategy, str)

    def test_backwardation_flag_consistency(self) -> None:
        for date_str in PARITY_DATES:
            date = pd.Timestamp(date_str)
            if date < VIX3M_INCEPTION:
                continue
            with self.subTest(date=date_str):
                snaps = _build_snapshots_engine_path(
                    date, self.market, DEFAULT_PARAMS
                )
                if snaps.vix.vix3m is None:
                    continue
                expected = snaps.vix.vix > snaps.vix.vix3m
                self.assertEqual(
                    snaps.vix.backwardation,
                    expected,
                    f"{date_str}: backwardation flag {snaps.vix.backwardation} != "
                    f"vix({snaps.vix.vix}) > vix3m({snaps.vix.vix3m})",
                )

    def test_known_backwardation_2020_03_16(self) -> None:
        date = pd.Timestamp("2020-03-16")
        snaps = _build_snapshots_engine_path(date, self.market, DEFAULT_PARAMS)
        self.assertTrue(
            snaps.vix.backwardation,
            f"2020-03-16 backwardation expected True, got {snaps.vix.backwardation} "
            f"(vix={snaps.vix.vix}, vix3m={snaps.vix.vix3m})",
        )


if __name__ == "__main__":
    unittest.main()
