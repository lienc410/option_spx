"""SPEC-119 — unified pricing library (Q087 Track B).

Single-truth Black-Scholes core + three explicit sigma modes:
  FLAT  — sigma = VIX/100 across strikes (reproduces historical backtests)
  CALIB — VIX + measured skew offsets from data/q085_skew_monitor.jsonl
  PESS  — CALIB + caller-supplied adverse bracket (no library defaults)

No default mode anywhere: research and backtest code must choose explicitly.
"""
from pricing.core import (  # noqa: F401
    DTE_CALENDAR_DAYS,
    DTE_TRADING_DAYS,
    call_delta,
    call_price,
    d1_d2,
    find_strike_for_delta,
    implied_vol,
    norm_cdf,
    norm_pdf,
    option_theta,
    put_delta,
    put_price,
)
from pricing.sigma import SigmaMode, sigma_for  # noqa: F401
from pricing.calibration import (  # noqa: F401
    CONV_ACT365,
    CONV_TD252,
    InsufficientCalibration,
    OffsetCurves,
    load_offsets,
    load_offsets_merged,
    to_trading_day_convention,
)
