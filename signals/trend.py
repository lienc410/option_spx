"""
Trend Filter — SPX/SPY Direction Signal

Compares the 20-day and 50-day simple moving averages of SPX (^GSPC)
to determine directional bias for strategy selection.

Signal:
  BULLISH  : 20MA > 50MA by more than TREND_THRESHOLD (0.5%)
  BEARISH  : 20MA < 50MA by more than TREND_THRESHOLD (0.5%)
  NEUTRAL  : within ±TREND_THRESHOLD of each other

Used by the strategy selector to tilt between:
  BULLISH  → Bull Call Diagonal, Short Put, Bull Call Spread
  NEUTRAL  → Iron Condor, standard Diagonal
  BEARISH  → Bear Call Spread, Bear Put Spread, Put Diagonal
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import yfinance as yf


TREND_THRESHOLD = 0.005   # 0.5% gap between 20MA and 50MA to count as directional
MA_SHORT        = 20
MA_LONG         = 50
TICKER          = "^GSPC"  # S&P 500 index (SPX proxy)


class TrendSignal(str, Enum):
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"


@dataclass
class TrendSnapshot:
    date:       str
    spx:        float
    ma20:       float
    ma50:       float
    ma_gap_pct: float    # (ma20 - ma50) / ma50, signed
    signal:     TrendSignal
    above_200:  bool     # SPX above 200-day MA (macro regime check)

    def __str__(self) -> str:
        direction = "▲" if self.ma_gap_pct > 0 else "▼"
        macro = "above 200MA ✓" if self.above_200 else "BELOW 200MA ⚠"
        return (
            f"[{self.date}] SPX: {self.spx:,.0f} | "
            f"20MA: {self.ma20:,.0f}  50MA: {self.ma50:,.0f} | "
            f"Gap: {direction}{abs(self.ma_gap_pct)*100:.2f}% | "
            f"Signal: {self.signal.value}  ({macro})"
        )


def _classify_trend(ma_gap_pct: float) -> TrendSignal:
    if ma_gap_pct > TREND_THRESHOLD:
        return TrendSignal.BULLISH
    elif ma_gap_pct < -TREND_THRESHOLD:
        return TrendSignal.BEARISH
    return TrendSignal.NEUTRAL


def fetch_spx_history(period: str = "1y") -> pd.DataFrame:
    """Download SPX daily closes. Returns DataFrame with column 'close'."""
    ticker = yf.Ticker(TICKER)
    df = ticker.history(period=period)
    if df.empty:
        raise RuntimeError("Could not fetch SPX data from Yahoo Finance.")
    return df[["Close"]].rename(columns={"Close": "close"})


def get_current_trend(df: Optional[pd.DataFrame] = None) -> TrendSnapshot:
    """
    Return a TrendSnapshot for the most recent trading day.

    Args:
        df: Optional pre-fetched SPX DataFrame (column: 'close'). Fetches if None.
    """
    if df is None:
        df = fetch_spx_history(period="1y")

    if len(df) < MA_LONG + 1:
        raise ValueError(f"Need ≥{MA_LONG + 1} rows, got {len(df)}")

    spx    = float(df["close"].iloc[-1])
    ma20   = float(df["close"].rolling(MA_SHORT).mean().iloc[-1])
    ma50   = float(df["close"].rolling(MA_LONG).mean().iloc[-1])
    ma200  = float(df["close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else spx

    gap    = (ma20 - ma50) / ma50
    signal = _classify_trend(gap)
    date   = df.index[-1].strftime("%Y-%m-%d")

    return TrendSnapshot(
        date=date,
        spx=spx,
        ma20=ma20,
        ma50=ma50,
        ma_gap_pct=gap,
        signal=signal,
        above_200=(spx > ma200),
    )


def get_trend_history(df: Optional[pd.DataFrame] = None, period: str = "3mo") -> pd.DataFrame:
    """
    Return a DataFrame of daily trend signals.
    Columns: close, ma20, ma50, ma_gap_pct, signal, above_200
    """
    if df is None:
        df = fetch_spx_history(period="2y")

    out = df.copy()
    out["ma20"]      = out["close"].rolling(MA_SHORT).mean()
    out["ma50"]      = out["close"].rolling(MA_LONG).mean()
    out["ma200"]     = out["close"].rolling(200).mean()
    out["ma_gap_pct"] = (out["ma20"] - out["ma50"]) / out["ma50"]
    out["signal"]    = out["ma_gap_pct"].apply(_classify_trend)
    out["above_200"] = out["close"] > out["ma200"]

    out = out.dropna(subset=["ma50"])

    cutoff = pd.Timestamp.now(tz=out.index.tz) - _period_to_timedelta(period)
    return out[out.index >= cutoff][["close", "ma20", "ma50", "ma_gap_pct", "signal", "above_200"]]


def _period_to_timedelta(period: str) -> pd.Timedelta:
    mapping = {"1mo": "30D", "3mo": "90D", "6mo": "180D", "1y": "365D", "2y": "730D"}
    return pd.Timedelta(mapping.get(period, "90D"))


if __name__ == "__main__":
    print("Fetching SPX data...\n")

    df = fetch_spx_history(period="2y")
    snap = get_current_trend(df)

    print("=== Current Trend Signal ===")
    print(snap)
    print()

    signal_desc = {
        TrendSignal.BULLISH: "Tilt: BULLISH → Bull Call Diagonal, Short Put, Bull Call Spread",
        TrendSignal.NEUTRAL: "Tilt: NEUTRAL → Iron Condor, standard Diagonal (no directional bet)",
        TrendSignal.BEARISH: "Tilt: BEARISH → Bear Call Spread, Put Diagonal, Bear Put Spread",
    }
    print("→", signal_desc[snap.signal])

    if not snap.above_200:
        print("⚠  SPX is BELOW the 200-day MA — macro downtrend. Reduce size on bullish trades.")
    print()

    print("=== Last 30 Days: Trend History ===")
    history = get_trend_history(df, period="1mo")
    for date, row in history.iterrows():
        gap_str = f"{row['ma_gap_pct']*100:+.2f}%"
        macro   = "" if row["above_200"] else " ⚠200MA"
        print(f"  {date.strftime('%Y-%m-%d')}  SPX {row['close']:>8,.0f}  "
              f"20MA {row['ma20']:>8,.0f}  50MA {row['ma50']:>8,.0f}  "
              f"Gap {gap_str:>7}  {row['signal'].value:<8}{macro}")

    print()
    print("=== Signal Distribution (last 30d) ===")
    counts = history["signal"].value_counts()
    for sig, count in counts.items():
        print(f"  {sig.value:<10} {count:>3} days  ({count/len(history)*100:.0f}%)")
