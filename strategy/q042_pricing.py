"""Q042 — BS + skew haircut + term-multiplier call pricing.

Canonical pricing model shared by F2 (sizing), F8 (backtest), and F4
(live tie-out validation). Matches the research-phase scripts exactly so
backtest and live numbers are computed by the same formula.
"""

from __future__ import annotations

from pricing import core as _core


def term_multiplier(dte: int) -> float:
    """Scale ATM IV for DTE: term structure haircut on raw VIX."""
    if dte <= 45:
        return 1.10
    if dte <= 120:
        return 1.00
    return 0.95


def skew_multiplier(moneyness: float) -> float:
    """Approximate SPX call skew: OTM calls are cheaper (negative skew)."""
    if moneyness >= 1.0:
        delta = min(moneyness - 1.0, 0.10)
        return 1.0 - 1.5 * delta
    delta = min(1.0 - moneyness, 0.10)
    return 1.0 + 1.5 * delta


def bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    """Black-Scholes European call price — delegates to pricing.core (SPEC-119).

    Public signature and conventions unchanged (T in years, r=4%, q=0);
    the Q042 skew/term multipliers above stay local — they are this sleeve's
    historical sigma model, superseded for NEW research by pricing.sigma CALIB.
    """
    return float(_core.call_price(S, K, T, sigma, r, q=0.0))


def estimate_debit(
    S: float,
    K_long: float,
    K_short: float,
    dte: int,
    vix: float,
) -> float:
    """
    Estimate net debit per-share for an ATM/+5% SPX call spread.

    Args:
        S:       Current SPX level (used as reference for IV scaling).
        K_long:  Long call strike (ATM, rounded to nearest $5).
        K_short: Short call strike (+5% OTM, rounded to nearest $5).
        dte:     Target DTE.
        vix:     Current VIX level.

    Returns:
        Net debit per share (multiply × 100 for per-contract cost).
    """
    T = dte / 365.0
    sigma_atm = max(vix / 100.0, 0.10) * term_multiplier(dte)
    sigma_long = sigma_atm * skew_multiplier(K_long / S)
    sigma_short = sigma_atm * skew_multiplier(K_short / S)
    p_long = bs_call(S, K_long, T, sigma_long)
    p_short = bs_call(S, K_short, T, sigma_short)
    return max(0.0, p_long - p_short)
