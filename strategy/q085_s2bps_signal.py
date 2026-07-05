"""SPEC-116 — Q085 S2-BPS signal (point-in-time, paper phase).

signal_day is true iff ALL of:
  1. oversold composite: SPX Wilder RSI(2) < 10 OR three consecutive down closes
  2. production regime == NORMAL (VIX 15-22 band)
  3. blocked: production selector output is Reduce/Wait (no tradable strategy_key)
  4. Layer-1: VIX close < 35 (EXTREME lock is never bypassed by this sleeve)

Reference truth: research/q085/q085_battery_lib.py (F3_rsi2_os / F3_down3).
regime / strategy_key MUST be passed in from the same recommendation pipeline
the Telegram bot uses — this module deliberately has no VIX/regime computation
of its own (口径漂移 guard).
"""
from __future__ import annotations

RSI_OS_THRESHOLD = 10.0
VIX_LAYER1_MAX = 35.0
RSI_WARMUP_MIN = 260  # bars needed before RSI(2) is considered settled


def wilder_rsi(closes: list[float], n: int = 2) -> float:
    """Wilder-smoothed RSI over a daily close series; returns the latest value.

    Matches research/q085/q085_battery_lib.py exactly:
      ewm(alpha=1/n, adjust=False) on up/down move series.
    """
    import pandas as pd

    c = pd.Series(closes, dtype=float)
    d = c.diff()
    ru = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    rd = (-d).clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    rsi = 100 - 100 / (1 + ru / rd)
    return float(rsi.iloc[-1])


def oversold_composite(closes: list[float]) -> dict:
    """closes: ascending daily SPX closes including today (>=260 bars for warmup).

    Returns {"rsi2": float, "down3": bool, "oversold": bool} where
    oversold = (rsi2 < 10) or down3; down3 = each of the last three closes
    lower than the prior close (successive declines, not cumulative).
    """
    if len(closes) < 4:
        raise ValueError(f"need >=4 closes for down3, got {len(closes)}")
    if len(closes) < RSI_WARMUP_MIN:
        import logging
        logging.getLogger(__name__).warning(
            "q085 signal: only %d closes (<%d warmup) — RSI(2) may be unsettled",
            len(closes), RSI_WARMUP_MIN,
        )
    rsi2 = wilder_rsi(closes, 2)
    c1, c2, c3, c4 = closes[-1], closes[-2], closes[-3], closes[-4]
    down3 = (c1 < c2) and (c2 < c3) and (c3 < c4)
    return {"rsi2": round(rsi2, 2), "down3": down3,
            "oversold": (rsi2 < RSI_OS_THRESHOLD) or down3}


def signal_day(
    spx_closes: list[float],
    vix_close: float,
    regime: str,
    strategy_key: str | None,
) -> dict:
    """Four-condition point-in-time signal with per-condition detail.

    regime / strategy_key come from the production recommendation pipeline
    (the bot's daily payload). Blocked = selector emitted Reduce/Wait: the
    live pipeline reports strategy_key="reduce_wait" while the research cache
    stores it as empty — treat both as blocked.
    """
    os_detail = oversold_composite(spx_closes)
    regime_ok = str(regime) == "NORMAL"
    sk = str(strategy_key or "").strip()
    blocked = (sk == "") or (sk == "reduce_wait")
    layer1_ok = float(vix_close) < VIX_LAYER1_MAX
    return {
        "rsi2": os_detail["rsi2"],
        "down3": os_detail["down3"],
        "oversold": os_detail["oversold"],
        "regime_ok": regime_ok,
        "blocked": blocked,
        "layer1_ok": layer1_ok,
        "signal": bool(os_detail["oversold"] and regime_ok and blocked and layer1_ok),
    }
