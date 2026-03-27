"""
IV Rank & IV Percentile Calculator

Uses VIX as the implied volatility proxy for SPX/SPY options.

IV Rank (IVR):
  Where does today's IV sit within the past 52-week high/low range?
  IVR = (current_IV - 52w_low) / (52w_high - 52w_low) * 100
  Range: 0–100. Higher = IV is relatively expensive → selling strategies favored.

IV Percentile (IVP):
  What % of days in the past 52 weeks had IV *lower* than today?
  More robust than IVR when a single spike distorts the high.
  Range: 0–100.

Signal thresholds (from design doc):
  IVR > 50  → HIGH   → selling premium favored (short put, iron condor, diagonal)
  IVR 30–50 → NEUTRAL → no strong edge for either side
  IVR < 30  → LOW    → buying premium favored (LEAP, debit spread)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import yfinance as yf

from signals.vix_regime import fetch_vix_history  # noqa: E402 (run via python -m or pip install -e .)


# Thresholds
IV_HIGH_THRESHOLD    = 50.0
IV_LOW_THRESHOLD     = 30.0
LOOKBACK_DAYS        = 252   # ~1 trading year


class IVSignal(str, Enum):
    HIGH    = "HIGH"     # IVR > 50 → selling premium favored
    NEUTRAL = "NEUTRAL"  # IVR 30–50
    LOW     = "LOW"      # IVR < 30 → buying premium favored


@dataclass
class IVSnapshot:
    date:          str
    vix:           float
    iv_rank:       float    # 0–100
    iv_percentile: float    # 0–100
    iv_signal:     IVSignal
    iv_52w_high:   float
    iv_52w_low:    float

    def __str__(self) -> str:
        return (
            f"[{self.date}] VIX: {self.vix:.2f} | "
            f"IV Rank: {self.iv_rank:.1f} | "
            f"IV Pct: {self.iv_percentile:.1f} | "
            f"Signal: {self.iv_signal.value}  "
            f"(52w range: {self.iv_52w_low:.1f}–{self.iv_52w_high:.1f})"
        )


def _classify_iv_signal(iv_rank: float) -> IVSignal:
    if iv_rank > IV_HIGH_THRESHOLD:
        return IVSignal.HIGH
    elif iv_rank < IV_LOW_THRESHOLD:
        return IVSignal.LOW
    return IVSignal.NEUTRAL


def compute_iv_rank(series: pd.Series) -> float:
    """
    Compute IV Rank for the last value in `series` using the full series as lookback.

    IVR = (current - min) / (max - min) * 100
    Returns 50.0 if the range is zero (flat IV environment).
    """
    current  = float(series.iloc[-1])
    low_52w  = float(series.min())
    high_52w = float(series.max())
    spread   = high_52w - low_52w
    if spread == 0:
        return 50.0
    return (current - low_52w) / spread * 100.0


def compute_iv_percentile(series: pd.Series) -> float:
    """
    Compute IV Percentile: % of days where IV was *below* today's level.

    More robust than IVR when a single outlier spike distorts the 52w high.
    """
    current = float(series.iloc[-1])
    pct_below = (series.iloc[:-1] < current).mean() * 100.0
    return round(pct_below, 1)


def get_current_iv_snapshot(df: Optional[pd.DataFrame] = None) -> IVSnapshot:
    """
    Return an IVSnapshot for the most recent trading day.

    Args:
        df: Optional pre-fetched VIX DataFrame (column: 'vix'). Fetches if None.
    """
    if df is None:
        df = fetch_vix_history(period="1y")

    if len(df) < 30:
        raise ValueError(f"Need ≥30 rows for IV Rank, got {len(df)}")

    # Use up to 252 trading days for the lookback window
    window = df["vix"].iloc[-LOOKBACK_DAYS:]

    vix          = float(window.iloc[-1])
    iv_rank      = round(compute_iv_rank(window), 1)
    iv_pct       = compute_iv_percentile(window)
    iv_52w_high  = float(window.max())
    iv_52w_low   = float(window.min())
    iv_signal    = _classify_iv_signal(iv_rank)
    date_str     = df.index[-1].strftime("%Y-%m-%d")

    return IVSnapshot(
        date=date_str,
        vix=vix,
        iv_rank=iv_rank,
        iv_percentile=iv_pct,
        iv_signal=iv_signal,
        iv_52w_high=iv_52w_high,
        iv_52w_low=iv_52w_low,
    )


def get_iv_rank_history(df: Optional[pd.DataFrame] = None, period: str = "3mo") -> pd.DataFrame:
    """
    Return a DataFrame of rolling IV Rank and IV Percentile for each day.
    Uses a 252-day rolling window. Rows with insufficient history are dropped.

    Columns: vix, iv_rank, iv_percentile, iv_signal
    """
    if df is None:
        # Fetch extra history so the rolling window has data from day 1 of `period`
        df = fetch_vix_history(period="2y")

    result_rows = []
    vix_series  = df["vix"]

    for i in range(LOOKBACK_DAYS, len(vix_series)):
        window   = vix_series.iloc[i - LOOKBACK_DAYS: i + 1]
        ivr      = round(compute_iv_rank(window), 1)
        ivp      = compute_iv_percentile(window)
        result_rows.append({
            "date":          vix_series.index[i],
            "vix":           float(vix_series.iloc[i]),
            "iv_rank":       ivr,
            "iv_percentile": ivp,
            "iv_signal":     _classify_iv_signal(ivr),
        })

    if not result_rows:
        raise ValueError("Not enough history to compute rolling IV Rank (need 252+ trading days).")

    out = pd.DataFrame(result_rows).set_index("date")

    # Trim to requested period
    cutoff = pd.Timestamp.now(tz=out.index.tz) - _period_to_timedelta(period)
    return out[out.index >= cutoff]


def _period_to_timedelta(period: str) -> pd.Timedelta:
    mapping = {
        "1mo": "30D", "3mo": "90D", "6mo": "180D",
        "1y":  "365D", "2y": "730D",
    }
    return pd.Timedelta(mapping.get(period, "90D"))


if __name__ == "__main__":
    print("Fetching VIX data (1 year)...\n")

    df = fetch_vix_history(period="2y")

    # --- Current snapshot ---
    snap = get_current_iv_snapshot(df)
    print("=== Current IV Rank / Percentile ===")
    print(snap)
    print()

    # --- Signal interpretation ---
    signal_desc = {
        IVSignal.HIGH:    "IV is relatively EXPENSIVE → selling premium favored\n"
                          "  Strategies: Short Put, Iron Condor, Call Diagonal (short leg)",
        IVSignal.NEUTRAL: "IV is NEUTRAL → no strong edge for either buyer or seller\n"
                          "  Strategies: Bull Call Diagonal (standard), Calendar Spread",
        IVSignal.LOW:     "IV is relatively CHEAP → buying premium favored\n"
                          "  Strategies: Buy LEAP, Debit Spread (Bull Call/Bear Put)",
    }
    print("→", signal_desc[snap.iv_signal])
    print()

    # --- IVR note: percentile vs rank divergence ---
    diff = abs(snap.iv_rank - snap.iv_percentile)
    if diff > 15:
        print(f"⚠  IVR ({snap.iv_rank:.1f}) and IVP ({snap.iv_percentile:.1f}) diverge by {diff:.1f} pts")
        print("   → A single VIX spike is distorting the 52w high. IVP is more reliable here.\n")

    # --- Recent 30-day history ---
    print("=== Last 30 Days: IV Rank History ===")
    history = get_iv_rank_history(df, period="1mo")
    for date, row in history.iterrows():
        bar = "█" * int(row["iv_rank"] / 5)  # visual bar, max 20 chars
        print(f"  {date.strftime('%Y-%m-%d')}  VIX {row['vix']:5.2f}  "
              f"IVR {row['iv_rank']:5.1f}  IVP {row['iv_percentile']:5.1f}  "
              f"{row['iv_signal'].value:<8}  {bar}")

    # --- Signal distribution summary ---
    print()
    print("=== IV Signal Distribution (last 30d) ===")
    counts = history["iv_signal"].value_counts()
    total  = len(history)
    for signal, count in counts.items():
        pct = count / total * 100
        print(f"  {signal.value:<10} {count:>3} days  ({pct:.0f}%)")
