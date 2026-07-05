"""
Black-Scholes Option Pricer — thin adapter over pricing.core (SPEC-119).

The engine's public API and numeric conventions are unchanged (T = dte/252,
r = 4.5%, q = 0, scipy CDF): every function below delegates to the unified
pricing.core with exactly those parameters, so backtests are bit-identical
to the pre-migration implementation (AC-1 frozen-snapshot verified).

Limitations (Precision B) — unchanged:
- Assumes constant IV throughout the holding period (no vol surface): this is
  pricing.sigma FLAT mode; CALIB/PESS live in pricing.sigma for research use.
- No bid/ask spread modeled — mid-market theoretical values.
- American-style early assignment risk not modeled.
- Dividend yield assumed zero (q=0).
"""

from pricing import core as _core

RISK_FREE_RATE = 0.045    # ~4.5% (adjust to prevailing T-bill rate)
TRADING_DAYS   = 252


def _T(dte: int) -> float:
    return dte / TRADING_DAYS


def call_price(S: float, K: float, dte: int, sigma: float, r: float = RISK_FREE_RATE) -> float:
    if _T(dte) <= 0:
        return max(S - K, 0.0)
    return _core.call_price(S, K, _T(dte), sigma, r, q=0.0)


def put_price(S: float, K: float, dte: int, sigma: float, r: float = RISK_FREE_RATE) -> float:
    if _T(dte) <= 0:
        return max(K - S, 0.0)
    return _core.put_price(S, K, _T(dte), sigma, r, q=0.0)


def call_delta(S: float, K: float, dte: int, sigma: float, r: float = RISK_FREE_RATE) -> float:
    return _core.call_delta(S, K, _T(dte), sigma, r, q=0.0)


def put_delta(S: float, K: float, dte: int, sigma: float, r: float = RISK_FREE_RATE) -> float:
    return call_delta(S, K, dte, sigma, r) - 1.0


def option_theta(S: float, K: float, dte: int, sigma: float,
                 is_call: bool, r: float = RISK_FREE_RATE) -> float:
    """Daily theta (price decay per trading day, annual/252)."""
    return _core.option_theta(S, K, _T(dte), sigma, is_call, r, q=0.0,
                              per_days=TRADING_DAYS)


def find_strike_for_delta(
    S: float, dte: int, sigma: float,
    target_delta: float, is_call: bool,
    r: float = RISK_FREE_RATE,
    tol: float = 0.001,
) -> float:
    return _core.find_strike_for_delta(S, _T(dte), sigma, target_delta,
                                       is_call, r, q=0.0, tol=tol)
