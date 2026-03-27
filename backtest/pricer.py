"""
Black-Scholes Option Pricer

Uses VIX as the implied volatility proxy for SPX/SPY options.
Provides price, delta, theta for calls and puts.

Limitations (Precision B):
- Assumes constant IV throughout the holding period (no vol surface)
- No bid/ask spread modeled — prices are mid-market theoretical values
- American-style early assignment risk not modeled (relevant for SPY puts)
- Dividend yield assumed zero (small error for SPY; fine for SPX)
"""

import math
from scipy.stats import norm


RISK_FREE_RATE = 0.045    # ~4.5% (adjust to prevailing T-bill rate)
TRADING_DAYS   = 252


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float):
    """Compute d1 and d2 for Black-Scholes. T in years."""
    if T <= 0 or sigma <= 0:
        return float("inf"), float("inf")
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def call_price(S: float, K: float, dte: int, sigma: float, r: float = RISK_FREE_RATE) -> float:
    T = dte / TRADING_DAYS
    if T <= 0:
        return max(S - K, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def put_price(S: float, K: float, dte: int, sigma: float, r: float = RISK_FREE_RATE) -> float:
    T = dte / TRADING_DAYS
    if T <= 0:
        return max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def call_delta(S: float, K: float, dte: int, sigma: float, r: float = RISK_FREE_RATE) -> float:
    T = dte / TRADING_DAYS
    if T <= 0:
        return 1.0 if S > K else 0.0
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return norm.cdf(d1)


def put_delta(S: float, K: float, dte: int, sigma: float, r: float = RISK_FREE_RATE) -> float:
    return call_delta(S, K, dte, sigma, r) - 1.0


def option_theta(S: float, K: float, dte: int, sigma: float,
                 is_call: bool, r: float = RISK_FREE_RATE) -> float:
    """Daily theta (price decay per calendar day)."""
    T = dte / TRADING_DAYS
    if T <= 0:
        return 0.0
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    theta_annual = (
        - (S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
        - r * K * math.exp(-r * T) * (norm.cdf(d2) if is_call else -norm.cdf(-d2))
    )
    return theta_annual / TRADING_DAYS


def find_strike_for_delta(
    S: float, dte: int, sigma: float,
    target_delta: float, is_call: bool,
    r: float = RISK_FREE_RATE,
    tol: float = 0.001,
) -> float:
    """
    Binary-search for the strike that produces `target_delta` (absolute value).
    For calls: target_delta in (0, 1). For puts: target_delta in (0, 1) — sign applied internally.
    Returns the strike price.
    """
    lo, hi = S * 0.5, S * 1.5

    def delta_at(K):
        if is_call:
            return call_delta(S, K, dte, sigma, r)
        else:
            return abs(put_delta(S, K, dte, sigma, r))

    # For calls: higher K → lower delta. For puts: higher K → higher |delta|.
    for _ in range(60):
        mid  = (lo + hi) / 2
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
