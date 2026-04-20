"""
VIX Regime Classifier

Classifies current market environment into three VIX regimes used by the selector:
  LOW_VOL  : VIX < 15      → Iron Condor / Bull Call Diagonal / Reduce-Wait
  NORMAL   : 15 ≤ VIX < 22 → Bull Put Spread / Iron Condor / Bull Call Diagonal / Reduce-Wait
  HIGH_VOL : VIX ≥ 22      → Bull Put Spread (High Vol) / Reduce-Wait

Also computes a 5-day VIX trend (rising / falling / flat) to detect regime transitions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import yfinance as yf

from data.market_cache import load_or_fetch_history


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
    vix3m: Optional[float]   # 3-month VIX (^VIX3M); None if unavailable
    backwardation: bool       # True if spot VIX > VIX3M (elevated near-term panic)
    vix_peak_10d: Optional[float] = None  # trailing 10-trading-day peak VIX, inclusive of current day

    def __str__(self) -> str:
        warn = " ⚠ near threshold" if self.transition_warning else ""
        ts_str = ""
        if self.vix3m is not None:
            ts_label = " ⚠ BACKWARDATION" if self.backwardation else ""
            ts_str = f" | VIX3M: {self.vix3m:.2f}{ts_label}"
        return (
            f"[{self.date}] VIX: {self.vix:.2f} | "
            f"Regime: {self.regime.value} | "
            f"Trend: {self.trend.value} | "
            f"5d avg: {self.vix_5d_avg:.2f}{warn}{ts_str}"
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


def fetch_vix3m_history(period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """Download 3-month VIX prices from Yahoo Finance."""
    def _fetch() -> pd.DataFrame:
        ticker = yf.Ticker("^VIX3M")
        return ticker.history(period=period, interval=interval)

    df = load_or_fetch_history(
        source="yahoo",
        symbol="VIX3M",
        period=period,
        interval=interval,
        fetcher=_fetch,
    )
    if df.empty:
        raise RuntimeError("Could not fetch VIX3M data from Yahoo Finance.")
    return df[["Close"]].rename(columns={"Close": "vix3m"})


def fetch_vix3m() -> Optional[float]:
    """
    Fetch the current 3-month VIX (^VIX3M) from Yahoo Finance.
    Returns None if the data is unavailable.
    """
    try:
        df = fetch_vix3m_history(period="5d")
        if df.empty:
            return None
        return float(df["vix3m"].iloc[-1])
    except Exception:
        return None


def fetch_vix_history(period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """
    Download VIX prices from Yahoo Finance.

    Args:
        period:   lookback window (e.g. "3mo", "1y", "60d").
        interval: bar size — "1d" for daily (default), "1h" or "5m" for intraday.
                  yfinance intraday limits:
                    "5m"  → max 60 days history
                    "1h"  → max 730 days history

    Returns a DataFrame with column 'vix', indexed by datetime.
    Raises RuntimeError if data cannot be fetched.
    """
    def _fetch() -> pd.DataFrame:
        ticker = yf.Ticker("^VIX")
        return ticker.history(period=period, interval=interval)

    df = load_or_fetch_history(
        source="yahoo",
        symbol="VIX",
        period=period,
        interval=interval,
        fetcher=_fetch,
    )
    if df.empty:
        raise RuntimeError("Could not fetch VIX data from Yahoo Finance.")
    return df[["Close"]].rename(columns={"Close": "vix"})


def get_current_snapshot(
    df: Optional[pd.DataFrame] = None,
    current_vix: Optional[float] = None,
) -> VixSnapshot:
    """
    Return a VixSnapshot for the most recent trading day.

    Args:
        df:          Optional pre-fetched VIX EOD DataFrame (column: 'vix').
                     Fetches if None. Always used for 5-day trend and VIX3M baseline.
        current_vix: Override for the current VIX level (e.g. from a 5m or 1h bar).
                     When provided, replaces df.iloc[-1] for regime classification only.
                     The 5-day rolling trend and VIX3M comparison remain EOD-based.
    """
    if df is None:
        df = fetch_vix_history(period="1mo")

    if len(df) < 6:
        raise ValueError(f"Not enough VIX data: need ≥6 rows, got {len(df)}")

    # Current VIX level: intraday override if provided, else latest EOD close
    vix      = current_vix if current_vix is not None else float(df.iloc[-1]["vix"])
    date_str = df.index[-1].strftime("%Y-%m-%d")

    # 5-day rolling average: last 5 days vs prior 5 days
    vix_5d_avg  = float(df["vix"].iloc[-5:].mean())
    vix_5d_ago  = float(df["vix"].iloc[-10:-5].mean()) if len(df) >= 10 else vix_5d_avg
    vix_peak_10d = float(df["vix"].iloc[-10:].max()) if len(df) >= 10 else None

    regime  = _classify_regime(vix)
    trend   = _classify_trend(vix_5d_avg, vix_5d_ago)
    warning = _is_near_threshold(vix)
    vix3m   = fetch_vix3m()
    backwardation = (vix3m is not None) and (vix > vix3m)

    return VixSnapshot(
        date=date_str,
        vix=vix,
        regime=regime,
        trend=trend,
        vix_5d_avg=vix_5d_avg,
        vix_5d_ago=vix_5d_ago,
        transition_warning=warning,
        vix3m=vix3m,
        backwardation=backwardation,
        vix_peak_10d=vix_peak_10d,
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
        Regime.LOW_VOL:  "Strategy set: Iron Condor / Bull Call Diagonal / Reduce-Wait",
        Regime.NORMAL:   "Strategy set: Bull Put Spread / Iron Condor / Bull Call Diagonal / Reduce-Wait",
        Regime.HIGH_VOL: "Strategy set: Bull Put Spread (High Vol) / Reduce-Wait",
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
