"""
Trend Filter — SPX/SPY Direction Signal

Compares SPX price to its 50-day simple moving average to determine
directional bias for strategy selection.

Signal:
  BULLISH  : SPX > 50MA by more than TREND_THRESHOLD (1%)
  BEARISH  : SPX < 50MA by more than TREND_THRESHOLD (1%)
  NEUTRAL  : within ±TREND_THRESHOLD of 50MA

Used by the strategy selector to tilt between:
  BULLISH  → Bull Put Spread, Bull Call Diagonal
  NEUTRAL  → Iron Condor, Wait
  BEARISH  → Usually wait for confirmation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import yfinance as yf

from data.market_cache import load_or_fetch_history


TREND_THRESHOLD = 0.01    # 1% gap between SPX price and 50MA to count as directional
ATR_PERIOD      = 14
ATR_THRESHOLD   = 1.0
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
    ma_gap_pct: float    # (spx - ma50) / ma50, signed
    signal:     TrendSignal
    above_200:  bool     # SPX above 200-day MA (macro regime check)
    atr14:      Optional[float] = None
    gap_sigma:  Optional[float] = None
    spx_30d_high: Optional[float] = None
    dist_30d_high_pct: Optional[float] = None

    def __str__(self) -> str:
        direction = "▲" if self.ma_gap_pct > 0 else "▼"
        macro = "above 200MA ✓" if self.above_200 else "BELOW 200MA ⚠"
        return (
            f"[{self.date}] SPX: {self.spx:,.0f} | "
            f"50MA: {self.ma50:,.0f} | "
            f"SPX vs 50MA: {direction}{abs(self.ma_gap_pct)*100:.2f}% | "
            f"Signal: {self.signal.value}  ({macro})"
        )


def _classify_trend(ma_gap_pct: float) -> TrendSignal:
    if ma_gap_pct > TREND_THRESHOLD:
        return TrendSignal.BULLISH
    elif ma_gap_pct < -TREND_THRESHOLD:
        return TrendSignal.BEARISH
    return TrendSignal.NEUTRAL


def _compute_atr14_close(close_series: pd.Series) -> pd.Series:
    tr = close_series.diff().abs()
    return tr.rolling(ATR_PERIOD).mean()


def _classify_trend_atr(gap_sigma: float) -> TrendSignal:
    if gap_sigma >= ATR_THRESHOLD:
        return TrendSignal.BULLISH
    if gap_sigma <= -ATR_THRESHOLD:
        return TrendSignal.BEARISH
    return TrendSignal.NEUTRAL


def fetch_spx_history(period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Download SPX prices from Yahoo Finance.

    Args:
        period:   lookback window (e.g. "1y", "60d").
        interval: bar size — "1d" for daily (default), "1h" or "5m" for intraday.
                  yfinance intraday limits:
                    "5m"  → max 60 days history
                    "1h"  → max 730 days history

    Returns DataFrame with column 'close', indexed by datetime.
    """
    def _fetch() -> pd.DataFrame:
        ticker = yf.Ticker(TICKER)
        return ticker.history(period=period, interval=interval)

    df = load_or_fetch_history(
        source="yahoo",
        symbol="GSPC",
        period=period,
        interval=interval,
        fetcher=_fetch,
    )
    if df.empty:
        raise RuntimeError("Could not fetch SPX data from Yahoo Finance.")
    return df[["Close"]].rename(columns={"Close": "close"})


def get_current_trend(
    df: Optional[pd.DataFrame] = None,
    current_spx: Optional[float] = None,
) -> TrendSnapshot:
    """
    Return a TrendSnapshot for the most recent trading day.

    Args:
        df:          Optional pre-fetched SPX EOD DataFrame (column: 'close'). Fetches if None.
                     Always used for MA20, MA50, MA200 computation.
        current_spx: Override for the current SPX price (e.g. from a 5m or 1h bar).
                     When provided, replaces df.iloc[-1] for gap/signal computation only.
                     All rolling averages remain EOD-based.
    """
    if df is None:
        df = fetch_spx_history(period="1y")

    if len(df) < MA_LONG + 1:
        raise ValueError(f"Need ≥{MA_LONG + 1} rows, got {len(df)}")

    # Current SPX price: intraday override if provided, else latest EOD close
    spx    = current_spx if current_spx is not None else float(df["close"].iloc[-1])
    ma20   = float(df["close"].rolling(MA_SHORT).mean().iloc[-1])
    ma50   = float(df["close"].rolling(MA_LONG).mean().iloc[-1])
    ma200  = float(df["close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else spx

    gap    = (spx - ma50) / ma50
    atr14 = None
    gap_sigma = None
    if len(df) >= ATR_PERIOD + MA_LONG:
        atr_series = _compute_atr14_close(df["close"])
        atr14 = float(atr_series.iloc[-1]) if pd.notna(atr_series.iloc[-1]) else None
        if atr14 is not None:
            gap_sigma = (spx - ma50) / max(atr14, 1.0)
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
        atr14=atr14,
        gap_sigma=gap_sigma,
    )


def get_trend_history(df: Optional[pd.DataFrame] = None, period: str = "3mo", use_atr: bool = False) -> pd.DataFrame:
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
    out["ma_gap_pct"] = (out["close"] - out["ma50"]) / out["ma50"]
    out["signal"]    = out["ma_gap_pct"].apply(_classify_trend)
    out["above_200"] = out["close"] > out["ma200"]
    if use_atr:
        out["atr14"] = _compute_atr14_close(out["close"])
        out["gap_sigma"] = (out["close"] - out["ma50"]) / out["atr14"].clip(lower=1.0)
        out["signal_atr"] = out["gap_sigma"].apply(_classify_trend_atr)

    out = out.dropna(subset=["ma50"])

    cutoff = pd.Timestamp.now(tz=out.index.tz) - _period_to_timedelta(period)
    columns = ["close", "ma20", "ma50", "ma_gap_pct", "signal", "above_200"]
    if use_atr:
        columns.extend(["atr14", "gap_sigma", "signal_atr"])
    return out[out.index >= cutoff][columns]


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
        TrendSignal.BULLISH: "Tilt: BULLISH → Bull Put Spread, Bull Call Diagonal",
        TrendSignal.NEUTRAL: "Tilt: NEUTRAL → Iron Condor, Wait (no directional bet)",
        TrendSignal.BEARISH: "Tilt: BEARISH → usually Reduce / Wait until edge improves",
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
