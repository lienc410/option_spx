"""Q042 SPEC-094 F4 — Live-broker tie-out for ATM/+5% call spread DTE ~90.

Computes:
  - Schwab API live midpoint (broker_debit_per_contract)
  - Model BS+skew+term-multiplier prediction (model_debit_per_contract)
  - delta = abs(model − broker) / broker

F4 deployment gate (AC10): 5-day median delta < 15%.

Caveat: this script runs a single-day snapshot. PM had asserted multiple
trading days of data exist, but the Schwab cache is in-memory only (no
persistent file). Run this script daily Mon-Fri to accumulate the
5-day median.
"""

from __future__ import annotations

import pickle
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"


def get_current_spx_vix() -> tuple[float, float]:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    return float(spx["Close"].iloc[-1]), float(vix["Close"].iloc[-1])


def term_multiplier(dte: int) -> float:
    if dte <= 45:
        return 1.10
    if dte <= 120:
        return 1.00
    return 0.95


def skew_multiplier(moneyness: float) -> float:
    if moneyness >= 1.0:
        delta = min(moneyness - 1.0, 0.10)
        return 1.0 - 1.5 * delta
    delta = min(1.0 - moneyness, 0.10)
    return 1.0 + 1.5 * delta


def bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    if T <= 0:
        return max(0.0, S - K)
    if sigma <= 0:
        return max(0.0, S - K * np.exp(-r * T))
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def model_debit(S: float, K_long: float, K_short: float, T: float, vix: float, dte: int) -> float:
    sigma_atm = max(vix / 100.0, 0.10) * term_multiplier(dte)
    sigma_long = sigma_atm * skew_multiplier(K_long / S)
    sigma_short = sigma_atm * skew_multiplier(K_short / S)
    p_long = bs_call(S, K_long, T, sigma_long)
    p_short = bs_call(S, K_short, T, sigma_short)
    return p_long - p_short


def find_strike(chain: list[dict], target: float) -> dict | None:
    """Find the chain row with strike closest to target."""
    if not chain:
        return None
    best = min(chain, key=lambda r: abs(float(r["strike"]) - target))
    return best


def main() -> None:
    from schwab import client as schwab_client

    if not schwab_client.is_configured():
        print("ERROR: Schwab API not configured")
        return

    S, vix = get_current_spx_vix()
    print(f"Reference SPX (Yahoo last close): {S:.2f}")
    print(f"Reference VIX (Yahoo last close): {vix:.2f}")

    # Pull SPX chain DTE ~90
    target_dte = 90
    chain = schwab_client.get_option_chain(
        "SPX", "CALL",
        target_dte=target_dte,
        dte_range=10,
        center_strike=S,
        strike_window=200,  # widen to safely capture +5% (~$370 from ATM at SPX 7400 = ~75 strikes at $5 spacing)
    )
    print(f"\nSchwab SPX chain rows: {len(chain)}")
    if not chain:
        print("ERROR: no chain rows returned. Possibly outside market hours and no cached data.")
        return

    # Sort by strike, find ATM and +5% strikes
    chain.sort(key=lambda r: float(r["strike"]))
    actual_dte = chain[0].get("dte", target_dte)
    expiry = chain[0].get("expiry", "?")

    K_long_target = S
    K_short_target = S * 1.05

    long_row = find_strike(chain, K_long_target)
    short_row = find_strike(chain, K_short_target)

    if long_row is None or short_row is None:
        print(f"ERROR: could not find both strikes near ATM ({K_long_target:.0f}) and +5% ({K_short_target:.0f})")
        print(f"  Available strikes: {[r['strike'] for r in chain]}")
        return

    print(f"\n=== Spread legs ===")
    print(f"Long  ATM:  K={long_row['strike']:.0f}  bid={long_row['bid']:.2f}  ask={long_row['ask']:.2f}  mid={long_row['mid']:.2f}  iv={long_row.get('iv','?')}")
    print(f"Short +5%:  K={short_row['strike']:.0f}  bid={short_row['bid']:.2f}  ask={short_row['ask']:.2f}  mid={short_row['mid']:.2f}  iv={short_row.get('iv','?')}")

    # Broker midpoint debit
    broker_debit = float(long_row["mid"]) - float(short_row["mid"])
    print(f"\n=== Broker debit (midpoint) ===")
    print(f"  long_mid - short_mid = {long_row['mid']:.2f} - {short_row['mid']:.2f} = ${broker_debit:.2f}")
    print(f"  per 1 SPX contract (×100 multiplier): ${broker_debit * 100:.0f}")

    # Model debit using actual broker strikes
    K_long = float(long_row["strike"])
    K_short = float(short_row["strike"])
    T = actual_dte / 365
    model_debit_val = model_debit(S, K_long, K_short, T, vix, actual_dte)
    print(f"\n=== Model debit (BS + skew haircut + term-multiplier) ===")
    print(f"  σ_ATM_base = max(VIX/100, 10%) × term_mult({actual_dte}d) = {max(vix/100, 0.10) * term_multiplier(actual_dte):.4f}")
    print(f"  K_long={K_long:.0f} (moneyness {K_long/S:.4f}), K_short={K_short:.0f} (moneyness {K_short/S:.4f})")
    print(f"  model_debit per share: ${model_debit_val:.2f}")
    print(f"  per 1 SPX contract: ${model_debit_val * 100:.0f}")

    # Delta
    delta_pct = abs(model_debit_val - broker_debit) / broker_debit * 100
    print(f"\n=== F4 tie-out delta ===")
    print(f"  delta = |model − broker| / broker = |{model_debit_val:.2f} − {broker_debit:.2f}| / {broker_debit:.2f} = {delta_pct:.1f}%")
    print(f"  AC10 deployment gate (5-day median): < 15%")

    # Verdict (single-day)
    if delta_pct < 15:
        verdict = f"PASS (single-day) — delta {delta_pct:.1f}% < 15%"
    else:
        verdict = f"FAIL (single-day) — delta {delta_pct:.1f}% > 15%; recalibrate skew/term constants"
    print(f"\n=== Single-day verdict ===\n  {verdict}")
    print(f"\n  CAVEAT: AC10 requires 5-day median. Single snapshot is directional only.")
    print(f"  Run this script Mon-Fri to accumulate 5 trading days. Today: {date.today()}")

    # Also report IV comparison
    print(f"\n=== Implied volatility cross-check ===")
    long_iv = float(long_row.get("iv", 0))
    short_iv = float(short_row.get("iv", 0))
    sigma_atm = max(vix / 100, 0.10) * term_multiplier(actual_dte)
    sigma_long_model = sigma_atm * skew_multiplier(K_long / S) * 100  # to %
    sigma_short_model = sigma_atm * skew_multiplier(K_short / S) * 100
    print(f"  ATM   IV: broker={long_iv:.1f}%, model={sigma_long_model:.1f}%, delta={abs(sigma_long_model - long_iv):.1f}pp")
    print(f"  +5%   IV: broker={short_iv:.1f}%, model={sigma_short_model:.1f}%, delta={abs(sigma_short_model - short_iv):.1f}pp")
    print(f"  VIX (reference): {vix:.1f}%")


if __name__ == "__main__":
    main()
