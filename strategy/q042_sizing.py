"""Q042 Position Sizing — SPX-only (F2)

Single entry point: compute_sizing().

Inputs:  NLV, current SPX close, current VIX, sleeve_id.
Outputs: (long_strike, short_strike, contracts, est_debit_per_contract)

Rules (from SPEC-094 F2, updated by SPEC-104):
  - NLV < $200k → skip (return 0 contracts)
  - Sleeve A staged target debit = NLV × 12.5%
  - Sleeve B remains unchanged at NLV × 10% and is not production-routed
  - Long K  = ATM rounded to nearest $5
  - Short K = ATM × 1.05 rounded to nearest $5
  - Contracts = floor(target_debit / est_debit_per_contract)
  - Symbol fixed = SPX (no XSP branch in MVP)
"""

from __future__ import annotations

from typing import Optional, Tuple

from strategy.q042_config import (
    Q042_SLEEVE_A_PRODUCTION_CAP_PCT,
    Q042_SLEEVE_B_PAPER_SIZING_PCT,
)
from strategy.q042_pricing import estimate_debit

_NLV_MINIMUM    = 200_000.0   # activation threshold
_STRIKE_ROUND   = 5.0         # $5 increments
_OTM_PCT_A      = 0.025       # Sleeve A: ATM/+2.5% (SPEC-094.1)
_OTM_PCT_B      = 0.05        # Sleeve B: ATM/+5%  (unchanged)
_DTE_A          = 30          # Sleeve A: 30 DTE   (SPEC-094.1)
_DTE_B          = 90          # Sleeve B: 90 DTE   (unchanged)
_SPX_MULTIPLIER = 100         # SPX contract multiplier


def q042_sleeve_cap_pct(sleeve_id: str = "A") -> float:
    """Return the sizing cap used for draft entries.

    Sleeve B remains research-only, but the paper draft keeps its legacy 10%
    sizing so historical/paper records remain comparable.
    """
    return Q042_SLEEVE_A_PRODUCTION_CAP_PCT if str(sleeve_id).upper() == "A" else Q042_SLEEVE_B_PAPER_SIZING_PCT


def _round_strike(price: float, increment: float = _STRIKE_ROUND) -> int:
    return int(round(price / increment) * increment)


def compute_sizing(
    nlv: float,
    spx_close: float,
    vix: float,
    sleeve_id: str = "A",
) -> Tuple[Optional[int], Optional[int], int, Optional[float]]:
    """
    Compute Q042 spread sizing for one sleeve entry.

    Args:
        nlv:       Net liquidation value in USD.
        spx_close: Current SPX level (entry reference price for strikes).
        vix:       Current VIX level (used for BS pricing).
        sleeve_id: "A" or "B".

    Returns:
        (long_strike, short_strike, contracts, est_debit_per_contract)
        long_strike/short_strike are int (rounded to nearest $5).
        est_debit_per_contract is in USD (per-share debit × 100).
        Returns (None, None, 0, None) if NLV below activation threshold.

    AC6 example: NLV $500k, SPX 7400, VIX 25, sleeve_id="A"
        → (7400, 7585, n, ~est) [Sleeve A: ATM/+2.5%, DTE 30]
    AC7: NLV $150k → (None, None, 0, None)
    """
    if nlv < _NLV_MINIMUM:
        return None, None, 0, None

    oTM = _OTM_PCT_A if sleeve_id == "A" else _OTM_PCT_B
    dte = _DTE_A     if sleeve_id == "A" else _DTE_B

    long_k  = _round_strike(spx_close)
    short_k = _round_strike(spx_close * (1.0 + oTM))

    debit_per_share = estimate_debit(
        S=spx_close,
        K_long=float(long_k),
        K_short=float(short_k),
        dte=dte,
        vix=vix,
    )
    debit_per_contract = debit_per_share * _SPX_MULTIPLIER

    if debit_per_contract <= 0:
        return long_k, short_k, 0, None

    target = nlv * (q042_sleeve_cap_pct(sleeve_id) / 100.0)
    contracts = int(target // debit_per_contract)

    return long_k, short_k, contracts, round(debit_per_contract, 2)
