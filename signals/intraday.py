"""
Intraday Signals — VIX Spike Alert, Stop-Loss Trigger, Entry Signal

Three intraday signals for live monitoring and backtesting:
  VixSpikeAlert       : VIX rises N% from session open → hedge / close-short signal
  IntradayStopTrigger : SPX drops N% from session open → exit / reduce-size signal
  IntradayEntrySignal : Combined — READY only when VIX not spiking and SPX not stressed

Data resolution:
  interval="1h"  → backtesting (yfinance supports up to 730 days)
  interval="5m"  → live strategy (yfinance supports up to 60 days)

Thresholds:
  VIX +8%  from session open → WARNING
  VIX +15% from session open → ALERT
  SPX -1%  from session open → CAUTION
  SPX -2%  from session open → TRIGGER
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd

from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history


# ─── Thresholds ──────────────────────────────────────────────────────────────
VIX_SPIKE_WARN    = 0.08   # VIX +8%  from session open → WARNING
VIX_SPIKE_ALERT   = 0.15   # VIX +15% from session open → ALERT
SPX_STOP_CAUTION  = 0.01   # SPX -1%  from session open → CAUTION
SPX_STOP_TRIGGER  = 0.02   # SPX -2%  from session open → TRIGGER


# ─── Enums ───────────────────────────────────────────────────────────────────
class SpikeLevel(str, Enum):
    NONE    = "NONE"
    WARNING = "WARNING"   # VIX +8%
    ALERT   = "ALERT"     # VIX +15%


class StopLevel(str, Enum):
    NONE    = "NONE"
    CAUTION = "CAUTION"   # SPX -1%
    TRIGGER = "TRIGGER"   # SPX -2%


class EntryCondition(str, Enum):
    WAIT  = "WAIT"    # VIX spiking or SPX stressed — do not enter
    READY = "READY"   # conditions clear for entry


# ─── Dataclasses ─────────────────────────────────────────────────────────────
@dataclass
class VixSpikeAlert:
    timestamp:   str
    vix_open:    float
    vix_current: float
    spike_pct:   float    # positive = spike, negative = drop
    level:       SpikeLevel

    def __str__(self) -> str:
        sign = "+" if self.spike_pct >= 0 else ""
        return (
            f"[{self.timestamp}] VIX Spike: {sign}{self.spike_pct*100:.1f}% "
            f"(open {self.vix_open:.2f} → {self.vix_current:.2f}) | "
            f"Level: {self.level.value}"
        )


@dataclass
class IntradayStopTrigger:
    timestamp:   str
    spx_open:    float
    spx_current: float
    drop_pct:    float    # negative = drop from open
    level:       StopLevel

    def __str__(self) -> str:
        sign = "+" if self.drop_pct >= 0 else ""
        return (
            f"[{self.timestamp}] SPX Move: {sign}{self.drop_pct*100:.1f}% "
            f"(open {self.spx_open:,.0f} → {self.spx_current:,.0f}) | "
            f"Level: {self.level.value}"
        )


@dataclass
class IntradayEntrySignal:
    timestamp:  str
    vix:        float
    spx:        float
    vix_stable: bool           # True = no spike
    spx_stable: bool           # True = not in stop zone
    condition:  EntryCondition

    def __str__(self) -> str:
        return (
            f"[{self.timestamp}] Entry: {self.condition.value} | "
            f"VIX {self.vix:.2f} ({'stable' if self.vix_stable else 'spiking'}) | "
            f"SPX {self.spx:,.0f} ({'stable' if self.spx_stable else 'stressed'})"
        )


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _session_open(df: pd.DataFrame, col: str) -> float:
    """First bar of the most recent trading session."""
    last_date = df.index[-1].date()
    session = df[df.index.date == last_date]
    return float((session if not session.empty else df)[col].iloc[0])


def _classify_spike(pct: float) -> SpikeLevel:
    if pct >= VIX_SPIKE_ALERT:  return SpikeLevel.ALERT
    if pct >= VIX_SPIKE_WARN:   return SpikeLevel.WARNING
    return SpikeLevel.NONE


def _classify_stop(pct: float) -> StopLevel:
    if pct <= -SPX_STOP_TRIGGER: return StopLevel.TRIGGER
    if pct <= -SPX_STOP_CAUTION: return StopLevel.CAUTION
    return StopLevel.NONE


def _intraday_period(interval: str) -> str:
    """Safe lookback period for a given yfinance interval."""
    return "7d" if interval == "5m" else "60d"


# ─── Public API ──────────────────────────────────────────────────────────────
def get_vix_spike(
    df: Optional[pd.DataFrame] = None,
    interval: str = "5m",
) -> VixSpikeAlert:
    """
    Check current intraday VIX spike vs session open.

    Args:
        df:       Pre-fetched VIX intraday DataFrame (col: 'vix'). Fetches if None.
        interval: "5m" for live (default), "1h" for backtest.
    """
    if df is None:
        df = fetch_vix_history(period=_intraday_period(interval), interval=interval)

    vix_open    = _session_open(df, "vix")
    vix_current = float(df["vix"].iloc[-1])
    spike_pct   = (vix_current - vix_open) / vix_open if vix_open else 0.0
    ts          = df.index[-1].strftime("%Y-%m-%d %H:%M")

    return VixSpikeAlert(
        timestamp=ts,
        vix_open=vix_open,
        vix_current=vix_current,
        spike_pct=spike_pct,
        level=_classify_spike(spike_pct),
    )


def get_spx_stop(
    df: Optional[pd.DataFrame] = None,
    interval: str = "5m",
) -> IntradayStopTrigger:
    """
    Check current intraday SPX drop vs session open.

    Args:
        df:       Pre-fetched SPX intraday DataFrame (col: 'close'). Fetches if None.
        interval: "5m" for live (default), "1h" for backtest.
    """
    if df is None:
        df = fetch_spx_history(period=_intraday_period(interval), interval=interval)

    spx_open    = _session_open(df, "close")
    spx_current = float(df["close"].iloc[-1])
    drop_pct    = (spx_current - spx_open) / spx_open if spx_open else 0.0
    ts          = df.index[-1].strftime("%Y-%m-%d %H:%M")

    return IntradayStopTrigger(
        timestamp=ts,
        spx_open=spx_open,
        spx_current=spx_current,
        drop_pct=drop_pct,
        level=_classify_stop(drop_pct),
    )


def get_entry_signal(
    vix_df: Optional[pd.DataFrame] = None,
    spx_df: Optional[pd.DataFrame] = None,
    interval: str = "5m",
) -> IntradayEntrySignal:
    """
    Combined intraday entry signal.
    READY only when VIX is not spiking AND SPX is not in stop zone.

    Args:
        vix_df:   Pre-fetched intraday VIX DataFrame. Fetches if None.
        spx_df:   Pre-fetched intraday SPX DataFrame. Fetches if None.
        interval: "5m" for live (default), "1h" for backtest.
    """
    spike = get_vix_spike(vix_df, interval=interval)
    stop  = get_spx_stop(spx_df, interval=interval)

    vix_stable = spike.level == SpikeLevel.NONE
    spx_stable = stop.level == StopLevel.NONE
    condition  = EntryCondition.READY if (vix_stable and spx_stable) else EntryCondition.WAIT

    return IntradayEntrySignal(
        timestamp=spike.timestamp,
        vix=spike.vix_current,
        spx=stop.spx_current,
        vix_stable=vix_stable,
        spx_stable=spx_stable,
        condition=condition,
    )


def get_intraday_history(
    interval: str = "1h",
    period: str = "60d",
) -> pd.DataFrame:
    """
    Fetch aligned VIX + SPX intraday bars for backtesting.

    Args:
        interval: "1h" for backtest (up to 730d), "5m" for recent live data (up to 60d).
        period:   lookback window (e.g. "60d", "30d", "730d").

    Returns DataFrame with columns:
        vix, close,
        spike_pct (VIX % from session open),
        drop_pct  (SPX % from session open),
        vix_level (SpikeLevel),
        stop_level (StopLevel)
    """
    vix_df = fetch_vix_history(period=period, interval=interval)
    spx_df = fetch_spx_history(period=period, interval=interval)

    df = pd.DataFrame({
        "vix":   vix_df["vix"],
        "close": spx_df["close"],
    }).dropna()

    if df.empty:
        raise ValueError("No overlapping intraday bars for VIX and SPX.")

    df["_date"]      = df.index.date
    df["vix_open"]   = df.groupby("_date")["vix"].transform("first")
    df["close_open"] = df.groupby("_date")["close"].transform("first")

    df["spike_pct"] = (df["vix"]   - df["vix_open"])   / df["vix_open"]
    df["drop_pct"]  = (df["close"] - df["close_open"]) / df["close_open"]

    df["vix_level"]  = df["spike_pct"].apply(_classify_spike)
    df["stop_level"] = df["drop_pct"].apply(_classify_stop)

    return df.drop(columns=["_date", "vix_open", "close_open"])


if __name__ == "__main__":
    print("Fetching intraday signals (5m, last 7 days)...\n")

    spike = get_vix_spike(interval="5m")
    stop  = get_spx_stop(interval="5m")
    entry = get_entry_signal(interval="5m")

    print("=== VIX Spike Alert ===")
    print(spike)
    print()

    print("=== SPX Stop Trigger ===")
    print(stop)
    print()

    print("=== Entry Signal ===")
    print(entry)
    print()

    print("=== Intraday History (1h, last 60 days) — last 10 bars ===")
    hist = get_intraday_history(interval="1h", period="60d")
    for ts, row in hist.tail(10).iterrows():
        print(
            f"  {ts.strftime('%Y-%m-%d %H:%M')}  "
            f"VIX {row['vix']:5.2f} ({row['spike_pct']*100:+.1f}%) [{row['vix_level'].value:<8}]  "
            f"SPX {row['close']:>8,.0f} ({row['drop_pct']*100:+.1f}%) [{row['stop_level'].value}]"
        )
