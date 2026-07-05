"""SPEC-119 — Black-Scholes single truth (d1/d2, prices, greeks, strike-for-delta).

Numeric conventions are EXPLICIT parameters — no hidden defaults beyond the
documented ones below. The two day-count conventions in production are both
supported; the caller picks:

  T = dte / DTE_TRADING_DAYS   (252)  — backtest engine convention (pricer.py)
  T = dte / DTE_CALENDAR_DAYS  (365)  — Q042 / attribution convention

r and q (continuous dividend yield) are explicit. q=0.0 reproduces the
production convention; research code historically used q=0.013 — both are
first-class so either side can reproduce its own history exactly.

CDF: scipy.stats.norm primary (what every production copy used); an
Abramowitz-Stegun fallback keeps degraded environments alive (inherited from
sleeve_governance._bs_put, SPEC-108.1) — accuracy ~1e-7, only used if scipy
is genuinely unavailable.
"""
from __future__ import annotations

import math

DTE_TRADING_DAYS = 252    # backtest engine day-count
DTE_CALENDAR_DAYS = 365   # Q042 / attribution day-count

try:
    from scipy.stats import norm as _norm
    _HAVE_SCIPY = True
except Exception:  # pragma: no cover — degraded env only
    _HAVE_SCIPY = False


def norm_cdf(x: float) -> float:
    if _HAVE_SCIPY:
        return float(_norm.cdf(x))
    # Abramowitz & Stegun 26.2.17 (|err| < 7.5e-8)
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    p = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
             + t * (-1.821255978 + t * 1.330274429))))
    pdf = math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
    return (1.0 - pdf * p) if x >= 0 else pdf * p


def norm_pdf(x: float) -> float:
    if _HAVE_SCIPY:
        return float(_norm.pdf(x))
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def d1_d2(S: float, K: float, T: float, r: float, sigma: float,
          q: float = 0.0) -> tuple[float, float]:
    """T in YEARS. Returns (inf, inf) on degenerate inputs (T<=0 or sigma<=0),
    matching the historical pricer.py convention."""
    if T <= 0 or sigma <= 0:
        return float("inf"), float("inf")
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)


def call_price(S: float, K: float, T: float, sigma: float, r: float,
               q: float = 0.0) -> float:
    if T <= 0:
        return max(S - K, 0.0)
    if sigma <= 0:
        return max(0.0, S * math.exp(-q * T) - K * math.exp(-r * T))
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    return S * math.exp(-q * T) * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)


def put_price(S: float, K: float, T: float, sigma: float, r: float,
              q: float = 0.0) -> float:
    if T <= 0:
        return max(K - S, 0.0)
    if sigma <= 0:
        return max(0.0, K * math.exp(-r * T) - S * math.exp(-q * T))
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * math.exp(-q * T) * norm_cdf(-d1)


def call_delta(S: float, K: float, T: float, sigma: float, r: float,
               q: float = 0.0) -> float:
    if T <= 0:
        return 1.0 if S > K else 0.0
    d1, _ = d1_d2(S, K, T, r, sigma, q)
    return math.exp(-q * T) * norm_cdf(d1)


def put_delta(S: float, K: float, T: float, sigma: float, r: float,
              q: float = 0.0) -> float:
    if T <= 0:
        return -1.0 if S < K else 0.0
    return call_delta(S, K, T, sigma, r, q) - math.exp(-q * T)


def option_theta(S: float, K: float, T: float, sigma: float, is_call: bool,
                 r: float, q: float = 0.0, *, per_days: int = DTE_TRADING_DAYS) -> float:
    """Theta per day (annual theta / per_days). per_days=252 reproduces the
    backtest pricer; pass 365 for calendar-day decay."""
    if T <= 0:
        return 0.0
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    theta_annual = (
        - (S * math.exp(-q * T) * norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
        - r * K * math.exp(-r * T) * (norm_cdf(d2) if is_call else -norm_cdf(-d2))
        + q * S * math.exp(-q * T) * (norm_cdf(d1) if is_call else -norm_cdf(-d1))
    )
    return theta_annual / per_days


def implied_vol(price: float, S: float, K: float, T: float, r: float,
                *, is_call: bool, q: float = 0.0) -> float | None:
    """BS implied vol from a price, bisection on [1e-4, 3.0]. Returns None when
    the price is outside the attainable range (below intrinsic / above bounds).

    CONVENTION WARNING: the result is only meaningful to a consumer pricing
    with the SAME (T day-count, r, q). Solving under ACT/365 and consuming
    under trading-day T=dte/252 shifts sigma by ~sqrt(252/365) ≈ 0.83× —
    never mix (SPEC-119 AC-3 root cause: vendor IV columns do exactly this
    kind of convention drift vs our pricer).
    """
    if price <= 0 or T <= 0:
        return None
    px = call_price if is_call else put_price
    lo, hi = 1e-4, 3.0
    if price <= px(S, K, T, lo, r, q=q) or price >= px(S, K, T, hi, r, q=q):
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if px(S, K, T, mid, r, q=q) > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def find_strike_for_delta(S: float, T: float, sigma: float,
                          target_delta: float, is_call: bool, r: float,
                          q: float = 0.0, tol: float = 0.001) -> float:
    """Binary search for the strike with |delta| == target_delta.
    Ported verbatim from backtest/pricer.py (60 iterations, round to int)."""
    lo, hi = S * 0.5, S * 1.5

    def delta_at(K: float) -> float:
        if is_call:
            return call_delta(S, K, T, sigma, r, q)
        return abs(put_delta(S, K, T, sigma, r, q))

    for _ in range(60):
        mid = (lo + hi) / 2
        dmid = delta_at(mid)
        if abs(dmid - target_delta) < tol:
            return round(mid)
        if is_call:
            if dmid > target_delta:
                lo = mid
            else:
                hi = mid
        else:
            if dmid < target_delta:
                lo = mid
            else:
                hi = mid
    return round((lo + hi) / 2)
