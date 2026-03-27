"""
VIX Regime Classifier

Classifies current market environment into one of three regimes based on VIX level:
  LOW_VOL  : VIX < 15  → Iron Condor / Bear Call Diagonal (45/90 DTE)
  NORMAL   : 15 ≤ VIX < 22 → Bull Call Diagonal (30/90-120 DTE)
  HIGH_VOL : VIX ≥ 22  → Buy LEAP / reduce short exposure

Also computes a 5-day VIX trend (rising / falling / flat) to detect regime transitions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import yfinance as yf


class Regime(str, Enum):
    LOW_VOL  = "LOW_VOL"   # VIX < 15
    NORMAL   = "NORMAL"    # 15 <= VIX < 22
    HIGH_VOL = "HIGH_VOL"  # VIX >= 22


class Trend(str, Enum):
    RISING  = "RISING"   # 5-day avg VIX rising
    FALLING = "FALLING"  # 5-day avg VIX falling
    FLAT    = "FLAT"     # within ±5% of 5-day average


# Thresholds — matches the design doc
LOW_VOL_THRESHOLD  = 15.0
HIGH_VOL_THRESHOLD = 22.0
TREND_BAND         = 0.05   # 5% change to count as rising/falling


@dataclass
class VixSnapshot:
    date: str
    vix: float
    regime: Regime
    trend: Trend
    vix_5d_avg: float
    vix_5d_ago: float
    transition_warning: bool  # True if near a threshold (within 1 point)

    def __str__(self) -> str:
        warn = " ⚠ near threshold" if self.transition_warning else ""
        return (
            f"[{self.date}] VIX: {self.vix:.2f} | "
            f"Regime: {self.regime.value} | "
            f"Trend: {self.trend.value} | "
            f"5d avg: {self.vix_5d_avg:.2f}{warn}"
        )


def _classify_regime(vix: float) -> Regime:
    if vix < LOW_VOL_THRESHOLD:
        return Regime.LOW_VOL
    elif vix < HIGH_VOL_THRESHOLD:
        return Regime.NORMAL
    else:
        return Regime.HIGH_VOL


def _classify_trend(current_avg: float, prior_avg: float) -> Trend:
    if prior_avg == 0:
        return Trend.FLAT
    change = (current_avg - prior_avg) / prior_avg
    if change > TREND_BAND:
        return Trend.RISING
    elif change < -TREND_BAND:
        return Trend.FALLING
    return Trend.FLAT


def _is_near_threshold(vix: float, band: float = 1.0) -> bool:
    """True if VIX is within `band` points of LOW_VOL or HIGH_VOL threshold."""
    return (
        abs(vix - LOW_VOL_THRESHOLD)  < band or
        abs(vix - HIGH_VOL_THRESHOLD) < band
    )


def fetch_vix_history(period: str = "3mo") -> pd.DataFrame:
    """
    Download VIX closing prices from Yahoo Finance.

    Returns a DataFrame with columns: ['Close'] indexed by date.
    Raises RuntimeError if data cannot be fetched.
    """
    ticker = yf.Ticker("^VIX")
    df = ticker.history(period=period)
    if df.empty:
        raise RuntimeError("Could not fetch VIX data from Yahoo Finance.")
    return df[["Close"]].rename(columns={"Close": "vix"})


def get_current_snapshot(df: Optional[pd.DataFrame] = None) -> VixSnapshot:
    """
    Return a VixSnapshot for the most recent trading day.

    Args:
        df: Optional pre-fetched VIX DataFrame (for testing / caching).
            If None, fetches fresh data from Yahoo Finance.
    """
    if df is None:
        df = fetch_vix_history(period="1mo")

    if len(df) < 6:
        raise ValueError(f"Not enough VIX data: need ≥6 rows, got {len(df)}")

    latest      = df.iloc[-1]
    vix         = float(latest["vix"])
    date_str    = df.index[-1].strftime("%Y-%m-%d")

    # 5-day rolling average: last 5 days vs prior 5 days
    vix_5d_avg  = float(df["vix"].iloc[-5:].mean())
    vix_5d_ago  = float(df["vix"].iloc[-10:-5].mean()) if len(df) >= 10 else vix_5d_avg

    regime  = _classify_regime(vix)
    trend   = _classify_trend(vix_5d_avg, vix_5d_ago)
    warning = _is_near_threshold(vix)

    return VixSnapshot(
        date=date_str,
        vix=vix,
        regime=regime,
        trend=trend,
        vix_5d_avg=vix_5d_avg,
        vix_5d_ago=vix_5d_ago,
        transition_warning=warning,
    )


def get_regime_history(df: Optional[pd.DataFrame] = None, period: str = "3mo") -> pd.DataFrame:
    """
    Return a DataFrame of daily VIX regime classifications for backtesting / review.

    Columns: date, vix, regime, trend, transition_warning
    """
    if df is None:
        df = fetch_vix_history(period=period)

    df = df.copy()
    df["regime"]  = df["vix"].apply(_classify_regime)
    df["vix_5d"]  = df["vix"].rolling(5).mean()
    df["trend"]   = Trend.FLAT  # placeholder; computed row-by-row below
    df["transition_warning"] = df["vix"].apply(_is_near_threshold)

    # Compute trend: compare rolling 5d avg to prior rolling 5d avg
    df["vix_5d_prior"] = df["vix_5d"].shift(5)
    mask = df["vix_5d_prior"].notna()
    df.loc[mask, "trend"] = df.loc[mask].apply(
        lambda r: _classify_trend(r["vix_5d"], r["vix_5d_prior"]), axis=1
    )

    return df[["vix", "regime", "trend", "transition_warning"]].dropna()


if __name__ == "__main__":
    print("Fetching VIX data...\n")

    # --- Current snapshot ---
    snapshot = get_current_snapshot()
    print("=== Current Market Regime ===")
    print(snapshot)
    print()

    # --- Regime description ---
    descriptions = {
        Regime.LOW_VOL:  "Strategy: Iron Condor or Bear Call Diagonal | DTE: 45/90",
        Regime.NORMAL:   "Strategy: Bull Call Diagonal (primary)      | DTE: 30/90-120",
        Regime.HIGH_VOL: "Strategy: Buy LEAP (reduce short exposure)  | DTE: 1-2 years",
    }
    print("→", descriptions[snapshot.regime])

    if snapshot.trend == Trend.RISING and snapshot.regime != Regime.HIGH_VOL:
        print("⚠  Trend: VIX rising — monitor for regime upgrade")
    elif snapshot.trend == Trend.FALLING and snapshot.regime != Regime.LOW_VOL:
        print("✓  Trend: VIX falling — regime may soften")

    print()

    # --- Recent 30-day history ---
    print("=== Last 30 Days: Regime History ===")
    history = get_regime_history(period="1mo")
    for date, row in history.iterrows():
        warn = " ⚠" if row["transition_warning"] else ""
        print(f"  {date.strftime('%Y-%m-%d')}  VIX {row['vix']:5.2f}  {str(row['regime'].value):<10}  {str(row['trend'].value):<8}{warn}")

    # --- Regime distribution summary ---
    print()
    print("=== Regime Distribution (last 30d) ===")
    counts = history["regime"].value_counts()
    total  = len(history)
    for regime, count in counts.items():
        pct = count / total * 100
        print(f"  {regime.value:<12} {count:>3} days  ({pct:.0f}%)")
