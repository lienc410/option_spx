"""Q054 Pilot — Unusual Options Flow → Forward Directional Hit Rate.

Tier 0.5 study under Retail Basic UW subscription (no API access).

Question:
    Do UW "unusual" flow alerts (large near-DTE OTM premium, ask-side dominant
    bullish or bid-side dominant bearish) predict the underlying stock's
    SPY-excess return over T+1, T+5, T+10 horizons?

Pass bar:
    hit_rate ≥ 55% with binomial p < 0.05 AND median |excess return| ≥ 0.8%
    at T+5. Pass on (a) all-events slice OR (b) non-earnings-window slice.

Inputs:
    data/q054_flow_pilot/seg_NN_YYYYMMDD_YYYYMMDD.csv  — UW web exports
    (see task/q054_pilot_export_instructions_2026-05-10.md)

Outputs:
    Console summary table.
    data/q054_pilot_events.csv — deduped event list with forward returns.
    task/q054_pilot_results_2026-05-10.md — to be filled in by Quant after run.

Method:
    1. Concat all seg CSVs, schema-validate, drop ETF/index by ticker blacklist.
    2. Classify side: ask-side ≥ 70% of premium → bullish; bid-side ≥ 70% → bearish;
       otherwise mixed (drop).
    3. Dedup: same (ticker, side) within 5 trading days → keep first occurrence.
    4. Fetch per-ticker daily OHLC via yfinance (cached locally).
    5. Compute excess return = stock_ret - SPY_ret at T+1, T+5, T+10.
    6. Flag earnings-window events (T-5 to T+1 around any earnings date) via yfinance
       Ticker.earnings_dates; if unavailable, skip earnings filter and note caveat.
    7. Compute hit rate + binomial p + median excess by slice:
       (a) all events
       (b) non-earnings only
       (c) by sector (top 5 by count)
       (d) by mcap bucket if available
    8. Print pass/fail vs threshold.

Notes:
    - Forward returns use close-to-close. Event timestamp's date = T0; if event is
      after 16:00 ET (post-close), T0 should arguably be next day, but for daily-
      level pilot we treat event_date as T0 (close already known). Conservative:
      use NEXT trading day close as the "entry baseline" instead. Set
      ENTRY_BASELINE = "next_close" for the strict version.
    - SPY proxy chosen because GSPC has no tradeable price; SPY is the de-facto
      market benchmark used by short-vol literature.
"""

from __future__ import annotations

import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[2]
EXPORT_DIR = REPO / "data" / "q054_flow_pilot"
EVENTS_OUT = REPO / "data" / "q054_pilot_events.csv"
PRICE_CACHE = REPO / "data" / "q054_price_cache"
PRICE_CACHE.mkdir(parents=True, exist_ok=True)

ETF_INDEX_BLACKLIST = {
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "XLF", "XLE", "XLK", "XLY", "XLV",
    "XLI", "XLU", "XLP", "XLB", "XOP", "GDX", "EEM", "EFA", "TLT", "HYG", "LQD",
    "SQQQ", "TQQQ", "UVXY", "SVXY", "VXX", "SOXL", "SOXS", "TNA", "SPXL", "SPXS",
    "SPX", "SPXW", "NDX", "RUT", "VIX", "VIXY",
}

ASK_SIDE_BULLISH_THRESHOLD = 0.70
BID_SIDE_BEARISH_THRESHOLD = 0.70
DEDUP_WINDOW_TD = 5
HORIZONS = [1, 5, 10]
EARNINGS_BUFFER_DAYS = (5, 1)  # T-5 to T+1
ENTRY_BASELINE = "same_close"  # or "next_close" for strict version
PASS_HIT_RATE = 0.55
PASS_MEDIAN_EXCESS_PCT = 0.008  # 0.8%
PASS_P_VALUE = 0.05


# ---------------------------------------------------------------------------
# Phase 1: load + schema validation
# ---------------------------------------------------------------------------

REQUIRED_COLS_CANONICAL = [
    "ticker", "created_at", "total_ask_side_prem", "total_bid_side_prem",
    "underlying_price",
]

# Map common UW UI column aliases to canonical names.
COLUMN_ALIASES = {
    "tape_time": "created_at",
    "ts": "created_at",
    "ask_side_premium": "total_ask_side_prem",
    "bid_side_premium": "total_bid_side_prem",
    "askside_premium": "total_ask_side_prem",
    "bidside_premium": "total_bid_side_prem",
    "underlying": "underlying_price",
    "stock_price": "underlying_price",
    "symbol": "ticker",
}


def load_exports() -> pd.DataFrame:
    csvs = sorted(EXPORT_DIR.glob("seg_*.csv"))
    if not csvs:
        print(f"ERROR: no segments found in {EXPORT_DIR}")
        print("Have PM run UW exports per task/q054_pilot_export_instructions_2026-05-10.md")
        sys.exit(1)

    frames = []
    for f in csvs:
        df = pd.read_csv(f)
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.rename(columns=COLUMN_ALIASES)
        frames.append(df)
        print(f"loaded {f.name}: {len(df)} rows")

    df = pd.concat(frames, ignore_index=True)

    missing = [c for c in REQUIRED_COLS_CANONICAL if c not in df.columns]
    if missing:
        print(f"ERROR: missing required columns: {missing}")
        print(f"Available columns: {list(df.columns)}")
        print("Edit COLUMN_ALIASES at top of script to add missing mappings.")
        sys.exit(1)

    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["created_at", "ticker", "underlying_price"])
    df["ticker"] = df["ticker"].str.upper().str.strip()
    df["event_date"] = df["created_at"].dt.tz_convert("America/New_York").dt.date
    df["event_date"] = pd.to_datetime(df["event_date"])

    df["total_ask_side_prem"] = pd.to_numeric(df["total_ask_side_prem"], errors="coerce").fillna(0)
    df["total_bid_side_prem"] = pd.to_numeric(df["total_bid_side_prem"], errors="coerce").fillna(0)
    df["total_premium_calc"] = df["total_ask_side_prem"] + df["total_bid_side_prem"]

    return df


# ---------------------------------------------------------------------------
# Phase 2: side classification + dedup
# ---------------------------------------------------------------------------

def classify_side(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["total_premium_calc"] > 0]
    df["ask_share"] = df["total_ask_side_prem"] / df["total_premium_calc"]
    df["bid_share"] = df["total_bid_side_prem"] / df["total_premium_calc"]

    is_call = df.get("type", "").astype(str).str.lower() == "call"
    is_put = df.get("type", "").astype(str).str.lower() == "put"

    df["side"] = "mixed"
    bullish_call = is_call & (df["ask_share"] >= ASK_SIDE_BULLISH_THRESHOLD)
    bullish_put = is_put & (df["bid_share"] >= BID_SIDE_BEARISH_THRESHOLD)
    bearish_call = is_call & (df["bid_share"] >= BID_SIDE_BEARISH_THRESHOLD)
    bearish_put = is_put & (df["ask_share"] >= ASK_SIDE_BULLISH_THRESHOLD)
    df.loc[bullish_call | bullish_put, "side"] = "bullish"
    df.loc[bearish_call | bearish_put, "side"] = "bearish"

    df = df[df["side"].isin(["bullish", "bearish"])]
    df = df[~df["ticker"].isin(ETF_INDEX_BLACKLIST)]
    return df


def dedup_events(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["ticker", "side", "event_date"]).reset_index(drop=True)
    keep = []
    last_seen: dict[tuple[str, str], pd.Timestamp] = {}
    for row in df.itertuples():
        key = (row.ticker, row.side)
        if key in last_seen:
            gap = (row.event_date - last_seen[key]).days
            if gap < DEDUP_WINDOW_TD * 1.4:  # 5 td ≈ 7 cal days
                continue
        keep.append(row.Index)
        last_seen[key] = row.event_date
    return df.loc[keep].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase 3: price fetch + forward returns
# ---------------------------------------------------------------------------

def _yf_download(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    cache_path = PRICE_CACHE / f"{ticker}__{start.date()}__{end.date()}.pkl"
    if cache_path.exists():
        return pd.read_pickle(cache_path)
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("yfinance required: pip install yfinance")
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.to_pickle(cache_path)
    return df


def fetch_spy_benchmark(min_date: pd.Timestamp, max_date: pd.Timestamp) -> pd.Series:
    span_start = min_date - pd.Timedelta(days=5)
    span_end = max_date + pd.Timedelta(days=30)
    spy = _yf_download("SPY", span_start, span_end)
    if spy.empty:
        raise RuntimeError("SPY benchmark fetch failed")
    return spy["Close"]


def attach_forward_returns(events: pd.DataFrame, spy_close: pd.Series) -> pd.DataFrame:
    events = events.copy()
    for h in HORIZONS:
        events[f"stock_ret_t{h}"] = np.nan
        events[f"spy_ret_t{h}"] = np.nan
        events[f"excess_ret_t{h}"] = np.nan

    spy_close.index = pd.to_datetime(spy_close.index).tz_localize(None)

    min_date = pd.Timestamp(events["event_date"].min()) - pd.Timedelta(days=5)
    max_date = pd.Timestamp(events["event_date"].max()) + pd.Timedelta(days=30)

    tickers = events["ticker"].unique().tolist()
    print(f"fetching prices for {len(tickers)} tickers...")
    price_map = {}
    for i, t in enumerate(tickers):
        try:
            df = _yf_download(t, min_date, max_date)
            if not df.empty:
                price_map[t] = df["Close"]
        except Exception as e:
            print(f"  {t}: {e}")
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(tickers)}")

    print(f"  fetched {len(price_map)} / {len(tickers)} tickers successfully")

    for idx, row in events.iterrows():
        t = row["ticker"]
        if t not in price_map:
            continue
        s = price_map[t]
        ev_date = pd.Timestamp(row["event_date"])
        if ENTRY_BASELINE == "next_close":
            base_dates = s.index[s.index > ev_date]
        else:
            base_dates = s.index[s.index >= ev_date]
        if len(base_dates) == 0:
            continue
        base_date = base_dates[0]
        base_px = s.loc[base_date]
        spy_base_dates = spy_close.index[spy_close.index >= base_date]
        if len(spy_base_dates) == 0:
            continue
        spy_base_date = spy_base_dates[0]
        spy_base_px = spy_close.loc[spy_base_date]

        for h in HORIZONS:
            future_dates = s.index[s.index > base_date]
            if len(future_dates) < h:
                continue
            target_date = future_dates[h - 1]
            target_px = s.loc[target_date]
            stock_ret = float(target_px / base_px - 1)
            spy_future = spy_close.index[spy_close.index > spy_base_date]
            if len(spy_future) < h:
                continue
            spy_target = spy_close.loc[spy_future[h - 1]]
            spy_ret = float(spy_target / spy_base_px - 1)
            events.at[idx, f"stock_ret_t{h}"] = stock_ret
            events.at[idx, f"spy_ret_t{h}"] = spy_ret
            events.at[idx, f"excess_ret_t{h}"] = stock_ret - spy_ret

    return events


# ---------------------------------------------------------------------------
# Phase 4: earnings flagging
# ---------------------------------------------------------------------------

def flag_earnings_window(events: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    events["in_earnings_window"] = False
    try:
        import yfinance as yf
    except ImportError:
        print("WARN: yfinance unavailable, skipping earnings flag")
        return events

    tickers = events["ticker"].unique().tolist()
    print(f"flagging earnings windows for {len(tickers)} tickers...")
    cache: dict[str, pd.DatetimeIndex] = {}
    for t in tickers:
        try:
            ed = yf.Ticker(t).earnings_dates
            if ed is None or ed.empty:
                cache[t] = pd.DatetimeIndex([])
            else:
                cache[t] = pd.DatetimeIndex(ed.index).tz_localize(None).normalize()
        except Exception:
            cache[t] = pd.DatetimeIndex([])

    pre, post = EARNINGS_BUFFER_DAYS
    for idx, row in events.iterrows():
        t = row["ticker"]
        ev = pd.Timestamp(row["event_date"])
        edates = cache.get(t, pd.DatetimeIndex([]))
        for ed in edates:
            if (ed - pd.Timedelta(days=pre)) <= ev <= (ed + pd.Timedelta(days=post)):
                events.at[idx, "in_earnings_window"] = True
                break
    return events


# ---------------------------------------------------------------------------
# Phase 5: hit-rate stats
# ---------------------------------------------------------------------------

@dataclass
class SliceResult:
    name: str
    n: int
    hit_rate_t1: float
    hit_rate_t5: float
    hit_rate_t10: float
    median_excess_t1: float
    median_excess_t5: float
    median_excess_t10: float
    p_value_t5: float


def directional_hit(side: str, excess: float) -> int | None:
    if pd.isna(excess):
        return None
    if side == "bullish":
        return int(excess > 0)
    if side == "bearish":
        return int(excess < 0)
    return None


def compute_slice(events: pd.DataFrame, name: str) -> SliceResult:
    n_total = len(events)
    if n_total == 0:
        return SliceResult(name, 0, *([np.nan] * 7))

    hits = {h: [] for h in HORIZONS}
    excess = {h: [] for h in HORIZONS}
    for _, row in events.iterrows():
        for h in HORIZONS:
            v = row[f"excess_ret_t{h}"]
            if pd.isna(v):
                continue
            excess[h].append(float(v))
            hit = directional_hit(row["side"], v)
            if hit is not None:
                hits[h].append(hit)

    def hr(h: int) -> float:
        return float(np.mean(hits[h])) if hits[h] else float("nan")

    def med(h: int) -> float:
        return float(np.median(np.abs(excess[h]))) if excess[h] else float("nan")

    n_t5 = len(hits[5])
    if n_t5 > 0:
        bt = binomtest(int(sum(hits[5])), n_t5, p=0.5, alternative="greater")
        p_t5 = float(bt.pvalue)
    else:
        p_t5 = float("nan")

    return SliceResult(
        name=name, n=n_total,
        hit_rate_t1=hr(1), hit_rate_t5=hr(5), hit_rate_t10=hr(10),
        median_excess_t1=med(1), median_excess_t5=med(5), median_excess_t10=med(10),
        p_value_t5=p_t5,
    )


def print_results(results: list[SliceResult]) -> None:
    print()
    print("=" * 110)
    print(f"{'slice':<32} | {'n':>5} | {'HR t1':>6} | {'HR t5':>6} | {'HR t10':>6} | "
          f"{'|exc| t5':>9} | {'p t5':>7} | {'PASS?':>6}")
    print("-" * 110)
    for r in results:
        passed = (
            (not np.isnan(r.hit_rate_t5)) and r.hit_rate_t5 >= PASS_HIT_RATE
            and r.median_excess_t5 >= PASS_MEDIAN_EXCESS_PCT
            and r.p_value_t5 < PASS_P_VALUE
        )
        verdict = "PASS" if passed else "FAIL"
        print(f"{r.name:<32} | {r.n:>5d} | "
              f"{r.hit_rate_t1*100:>5.1f}% | {r.hit_rate_t5*100:>5.1f}% | {r.hit_rate_t10*100:>5.1f}% | "
              f"{r.median_excess_t5*100:>+8.2f}% | {r.p_value_t5:>7.3f} | {verdict:>6}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("Q054 Pilot — Unusual Flow Hit Rate")
    print("=" * 70)

    raw = load_exports()
    print(f"\nRaw rows: {len(raw)}")

    sided = classify_side(raw)
    print(f"After side classification (bullish/bearish, exclude mixed/ETF): {len(sided)}")

    deduped = dedup_events(sided)
    print(f"After dedup ({DEDUP_WINDOW_TD}-td same ticker+side): {len(deduped)}")

    print(f"\nEvent date range: {deduped['event_date'].min().date()} → {deduped['event_date'].max().date()}")
    print(f"Side breakdown: {deduped['side'].value_counts().to_dict()}")
    print(f"Top 10 tickers: {deduped['ticker'].value_counts().head(10).to_dict()}")

    min_d = pd.Timestamp(deduped["event_date"].min())
    max_d = pd.Timestamp(deduped["event_date"].max())
    spy = fetch_spy_benchmark(min_d, max_d)
    print(f"SPY benchmark: {len(spy)} bars")

    events = attach_forward_returns(deduped, spy)
    n_with_ret = events["excess_ret_t5"].notna().sum()
    print(f"Events with valid T+5 excess return: {n_with_ret} / {len(events)}")

    events = flag_earnings_window(events)
    n_earn = int(events["in_earnings_window"].sum())
    print(f"Events in earnings window (T-5 to T+1): {n_earn} ({n_earn/len(events)*100:.1f}%)")

    events.to_csv(EVENTS_OUT, index=False)
    print(f"\nwrote {EVENTS_OUT}")

    results = []
    results.append(compute_slice(events, "all"))
    results.append(compute_slice(events[~events["in_earnings_window"]], "non_earnings"))
    results.append(compute_slice(events[events["side"] == "bullish"], "bullish_all"))
    results.append(compute_slice(events[events["side"] == "bearish"], "bearish_all"))
    results.append(compute_slice(
        events[(~events["in_earnings_window"]) & (events["side"] == "bullish")],
        "bullish_non_earnings",
    ))
    results.append(compute_slice(
        events[(~events["in_earnings_window"]) & (events["side"] == "bearish")],
        "bearish_non_earnings",
    ))

    if "sector" in events.columns:
        for sec, g in events.groupby("sector"):
            if len(g) >= 30:
                results.append(compute_slice(g, f"sector={sec}"))

    print_results(results)

    print("\n=== Pass criteria ===")
    print(f"  hit_rate_t5 ≥ {PASS_HIT_RATE*100:.0f}%")
    print(f"  median |excess_t5| ≥ {PASS_MEDIAN_EXCESS_PCT*100:.1f}%")
    print(f"  binomial p_t5 < {PASS_P_VALUE}")
    print("\nIf primary slices (all / non_earnings) FAIL, expected outcome — kill thread.")
    print("If non_earnings PASSes but all FAILs, signal is real but earnings-confounded.")


if __name__ == "__main__":
    main()
