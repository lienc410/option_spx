# SPX Options Strategy — System Design Specification

**Version:** 1.0 (as of 2026-03-26)
**Author:** Created via iterative design session with Claude Code
**Purpose:** Complete technical specification for recreation and continued development of the SPX/SPY options recommendation system. Target reader: another Claude Code instance or engineer without access to source code.

---

## 1. System Overview

### 1.1 Philosophy

This is a **recommendation system, not an automated trading system.** It reads market signals (VIX level, implied volatility rank, SPX price trend), selects the most appropriate options strategy from a predefined decision matrix, and delivers that recommendation to the user via Telegram or a local web dashboard. The user reviews and **executes manually** through their broker.

The core intellectual content is the strategy logic — the code is merely the delivery vehicle.

**Guiding principles:**
- One position at a time (no overlapping strategies)
- Defined risk on every trade
- Theta income as primary objective, directional bets as secondary
- Portfolio Margin account ($125k+ minimum, SPAN-based margin)
- 30% cash buffer always maintained

### 1.2 Architecture

```
┌────────────────────────────────────────────────────┐
│                    DATA LAYER                       │
│  yfinance → VIX (^VIX)   yfinance → SPX (^GSPC)   │
└──────────────┬──────────────────┬───────────────────┘
               │                  │
┌──────────────▼──────────────────▼───────────────────┐
│                   SIGNAL LAYER                       │
│  signals/vix_regime.py   signals/iv_rank.py          │
│  signals/trend.py                                    │
└──────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────┐
│                  STRATEGY LAYER                      │
│  strategy/selector.py  (decision matrix)             │
│  → Recommendation dataclass                          │
└────────┬──────────────────────────┬─────────────────┘
         │                          │
┌────────▼────────┐     ┌───────────▼────────────────┐
│  DELIVERY LAYER │     │     VALIDATION LAYER        │
│  notify/        │     │  backtest/pricer.py         │
│  telegram_bot.py│     │  backtest/engine.py         │
│  web/server.py  │     │  (walk-forward simulation)  │
└─────────────────┘     └────────────────────────────┘
```

### 1.3 Underlying Assets

| Asset | Use Case | Tax Treatment |
|-------|----------|---------------|
| SPX (S&P 500 Index) | Theta strategies (diagonal, iron condor, short put) | Section 1256 (60/40 long/short capital gains), cash-settled |
| SPY (S&P 500 ETF) | Directional spreads, LEAP positions | Standard equity options treatment |

---

## 2. Project Structure

```
SPX_strat/
├── signals/
│   ├── __init__.py
│   ├── vix_regime.py       # VIX regime classifier
│   ├── iv_rank.py          # IV Rank + IV Percentile
│   └── trend.py            # SPX moving average trend
├── strategy/
│   ├── __init__.py
│   └── selector.py         # Decision matrix → Recommendation
├── backtest/
│   ├── __init__.py
│   ├── pricer.py           # Black-Scholes pricing engine
│   └── engine.py           # Walk-forward backtest
├── notify/
│   ├── __init__.py
│   └── telegram_bot.py     # Telegram bot + scheduler
├── web/
│   ├── __init__.py
│   ├── server.py           # Flask API + page routes
│   └── templates/
│       ├── index.html      # Dashboard (signals + recommendation)
│       ├── backtest.html   # Backtest results + equity curve
│       └── matrix.html     # Signal matrix reference
├── main.py                 # CLI entry point
├── pyproject.toml          # Package config + dependencies
├── .env                    # Secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
└── logs/
    ├── bot.log
    └── bot-error.log
```

---

## 3. Signal Layer

### 3.1 VIX Regime (`signals/vix_regime.py`)

**Data source:** yfinance ticker `^VIX`, fetched with `period="2y"` to ensure sufficient history for trend computation.

**Enums:**

```
Regime:  LOW_VOL | NORMAL | HIGH_VOL
Trend:   RISING  | FALLING | FLAT
```

**Classification thresholds (hard-coded, do not modify without re-backtesting):**

| Condition | Regime |
|-----------|--------|
| VIX < 15 | LOW_VOL |
| 15 ≤ VIX < 22 | NORMAL |
| VIX ≥ 22 | HIGH_VOL |

**5-day VIX trend:**
- Compute 5-day simple moving average of VIX closing prices
- Compare today's VIX to the 5-day SMA:
  - If today > SMA × 1.05: RISING
  - If today < SMA × 0.95: FALLING
  - Otherwise: FLAT
- Purpose: detect regime transitions before they cross the hard threshold

**Threshold warning:** If VIX is within 1 point of a regime boundary (i.e., 14–16 or 21–23), emit a `threshold_warning` string. This is for display only — it does not change strategy selection.

**Output dataclass `VixSnapshot`:**
```
date:               str           # "YYYY-MM-DD"
vix:                float         # current VIX closing value
regime:             Regime        # LOW_VOL | NORMAL | HIGH_VOL
trend:              Trend         # RISING | FALLING | FLAT
threshold_warning:  str | None    # e.g. "VIX near NORMAL/HIGH_VOL boundary"
```

**Key functions:**
- `fetch_vix_history(period: str) -> pd.DataFrame` — columns: `vix` (renamed from yfinance Close)
- `get_current_snapshot(df: pd.DataFrame) -> VixSnapshot`
- `get_regime_history(df: pd.DataFrame) -> pd.Series` — per-row regime classification (for backtest)
- `_classify_regime(vix: float) -> Regime` — pure function, deterministic

**Implementation note:** yfinance VIX data uses `America/Chicago` timezone. The backtest engine normalizes this to tz-naive dates using `df.index = pd.to_datetime(df.index.date)` before joining with SPX data.

---

### 3.2 IV Rank & IV Percentile (`signals/iv_rank.py`)

**Proxy:** Uses VIX as the implied volatility proxy for SPX/SPY options. This is standard practice since VIX ≈ 30-day implied vol of SPX options.

**Enums:**
```
IVSignal:  HIGH | NEUTRAL | LOW
```

**Output dataclass `IVSnapshot`:**
```
date:           str
vix:            float         # same as VixSnapshot.vix
iv_rank:        float         # 0–100
iv_percentile:  float         # 0–100
iv_signal:      IVSignal      # derived from iv_rank (primary)
iv_52w_high:    float
iv_52w_low:     float
```

**IV Rank (IVR) formula:**
```
IVR = (current_VIX - 52w_low) / (52w_high - 52w_low) × 100
```
- Lookback: 252 trading days (1 year)
- If 52w_high == 52w_low (flat environment): return 50.0
- Measures how expensive current IV is relative to the past year's range

**IV Percentile (IVP) formula:**
```
IVP = (count of days in lookback where VIX < current_VIX) / total_days × 100
```
- More robust than IVR when a single spike distorts the 52-week high
- Computed on `series.iloc[:-1]` (excludes today to avoid self-comparison)

**Signal classification (applied to IVR by default):**

| IVR | Signal |
|-----|--------|
| > 50 | HIGH — selling premium favored |
| 30–50 | NEUTRAL |
| < 30 | LOW — buying premium favored |

**IVR/IVP Divergence handling (critical business rule):**

If `|IVR - IVP| > 15`, a single historical VIX spike has distorted the 52-week high, making IVR artificially low. In this case, the strategy selector uses IVP with modified thresholds:

| IVP | Effective Signal |
|-----|-----------------|
| > 70 | HIGH |
| 40–70 | NEUTRAL |
| < 40 | LOW |

The selector applies this logic via `_effective_iv_signal(iv: IVSnapshot) -> IVSignal`. Constants:
- `IVP_HIGH_THRESHOLD = 70.0`
- `IVP_LOW_THRESHOLD = 40.0`
- `MIN_IVP_FOR_HIGH_VOL_SELL = 50.0` (minimum IVP to sell premium in HIGH_VOL regime)

**Key functions:**
- `compute_iv_rank(series: pd.Series) -> float`
- `compute_iv_percentile(series: pd.Series) -> float`
- `get_current_iv_snapshot(df: pd.DataFrame | None) -> IVSnapshot`

---

### 3.3 SPX Trend (`signals/trend.py`)

**Data source:** yfinance ticker `^GSPC` (S&P 500 index), fetched with `period="2y"`.

**Enums:**
```
TrendSignal:  BULLISH | NEUTRAL | BEARISH
```

**Output dataclass `TrendSnapshot`:**
```
date:       str
spx:        float         # current SPX closing price
ma20:       float         # 20-day simple moving average
ma50:       float         # 50-day simple moving average
ma200:      float         # 200-day simple moving average
ma_gap_pct: float         # (ma20 - ma50) / ma50, signed
signal:     TrendSignal
above_200:  bool          # SPX > 200MA (macro filter)
```

**Signal classification:**
```
TREND_THRESHOLD = 0.005   # 0.5%

gap = (MA20 - MA50) / MA50
if gap > +0.005:  BULLISH
if gap < -0.005:  BEARISH
else:             NEUTRAL
```

**Macro filter (`above_200`):** If `SPX < MA200`, the `macro_warning` flag is set to `True` in the Recommendation. This triggers a display warning: "reduce size 25–50% on bullish trades." It does NOT change the strategy selection itself.

**Implementation note:** yfinance SPX data uses `America/New_York` timezone. Must normalize to tz-naive dates before joining with VIX data in the backtest engine.

**Key functions:**
- `fetch_spx_history(period: str) -> pd.DataFrame` — columns: `spx`
- `get_current_trend(df: pd.DataFrame) -> TrendSnapshot`
- `_classify_trend(ma20: float, ma50: float) -> TrendSignal`

---

## 4. Strategy Layer (`strategy/selector.py`)

### 4.1 Data Models

**`Leg` dataclass:**
```
action:  str    # "BUY" or "SELL"
option:  str    # "CALL" or "PUT"
dte:     int    # days to expiration target
delta:   float  # absolute delta target (e.g., 0.35 for 35-delta)
note:    str    # human-readable description (default "")
```

**`Recommendation` dataclass:**
```
strategy:       StrategyName
underlying:     str           # "SPX" or "SPY" or "—"
legs:           list[Leg]     # may be empty (REDUCE_WAIT)
max_risk:       str           # human description
target_return:  str
size_rule:      str
roll_rule:      str
rationale:      str           # one-line explanation
vix_snapshot:   VixSnapshot
iv_snapshot:    IVSnapshot
trend_snapshot: TrendSnapshot
macro_warning:  bool          # True if SPX below 200MA
```

**`StrategyName` enum (str enum):**
```
BULL_CALL_DIAGONAL  = "Bull Call Diagonal"
BEAR_CALL_DIAGONAL  = "Bear Call Diagonal"
IRON_CONDOR         = "Iron Condor"
SHORT_PUT           = "Short Put"
BULL_CALL_SPREAD    = "Bull Call Spread"
BEAR_CALL_SPREAD    = "Bear Call Spread"
BEAR_PUT_SPREAD     = "Bear Put Spread"
CALENDAR_SPREAD     = "Calendar Spread"
BUY_LEAP_CALL       = "Buy LEAP Call"
BUY_LEAP_PUT        = "Buy LEAP Put"
REDUCE_WAIT         = "Reduce / Wait"
```

### 4.2 Decision Matrix (complete)

The selector first determines the **effective IV signal** (with IVR/IVP divergence correction), then applies this matrix. The regime is the primary branch, IV and trend are secondary.

#### HIGH_VOL regime (VIX ≥ 22)

| IV Signal | Trend | → Strategy | Underlying | Leg Structure |
|-----------|-------|-----------|------------|---------------|
| LOW | any | Reduce / Wait | — | No position |
| HIGH or NEUTRAL | BEARISH | Buy LEAP Put | SPY | BUY PUT 365 DTE δ0.70 |
| HIGH or NEUTRAL | BULLISH | Buy LEAP Call | SPY | BUY CALL 365 DTE δ0.70 |
| HIGH or NEUTRAL | NEUTRAL | Buy LEAP Call | SPY | BUY CALL 365 DTE δ0.70 |

**Rationale for HIGH_VOL:** Elevated fear. Sell-side premium is expensive but dangerous. Buy LEAP calls/puts to capture large directional moves. When VIX normalizes, convert LEAP call to PMCC (Poor Man's Covered Call) by selling 30-45 DTE calls against it.

#### LOW_VOL regime (VIX < 15)

| IV Signal | Trend | → Strategy | Underlying | Leg Structure |
|-----------|-------|-----------|------------|---------------|
| any | NEUTRAL | Iron Condor | SPX | SELL CALL 45 DTE δ0.16, BUY CALL 45 DTE δ0.08, SELL PUT 45 DTE δ0.16, BUY PUT 45 DTE δ0.08 |
| any | BULLISH | Bull Call Diagonal | SPX | BUY CALL 90 DTE δ0.70, SELL CALL 45 DTE δ0.30 |
| any | BEARISH | Bear Call Diagonal | SPX | BUY PUT 90 DTE δ0.70, SELL PUT 45 DTE δ0.30 |

**Note:** IV signal is not differentiated in LOW_VOL — trend alone determines strategy.

**Iron Condor wing width:** `max(50, round(spx × 0.015 / 50) × 50)` — approximately 1.5% of SPX, rounded to nearest $50. Long wings are added on top of the short strikes.

#### NORMAL regime (VIX 15–22) — primary operating regime

| IV Signal | Trend | → Strategy | Underlying | Leg Structure |
|-----------|-------|-----------|------------|---------------|
| HIGH | BULLISH | Short Put | SPX | SELL PUT 30 DTE δ0.30 |
| HIGH | NEUTRAL | Bull Call Diagonal | SPX | BUY CALL 90 DTE δ0.70, SELL CALL 30 DTE δ0.35 |
| HIGH | BEARISH | Bear Put Spread | SPY | BUY PUT 21 DTE δ0.55, SELL PUT 21 DTE δ0.30 |
| NEUTRAL | BULLISH | Bull Call Diagonal | SPX | BUY CALL 90 DTE δ0.70, SELL CALL 30 DTE δ0.35 |
| NEUTRAL | NEUTRAL | Bull Call Diagonal | SPX | BUY CALL 90 DTE δ0.70, SELL CALL 30 DTE δ0.35 |
| NEUTRAL | BEARISH | Bear Call Spread | SPY | SELL CALL 21 DTE δ0.30, BUY CALL 21 DTE δ0.15 |
| LOW | BULLISH | Bull Call Spread | SPY | BUY CALL 21 DTE δ0.50, SELL CALL 21 DTE δ0.25 |
| LOW | NEUTRAL | Calendar Spread | SPX | BUY CALL 60 DTE δ0.50 (ATM), SELL CALL 30 DTE δ0.50 (ATM) |
| LOW | BEARISH | Bear Put Spread | SPY | BUY PUT 21 DTE δ0.55, SELL PUT 21 DTE δ0.30 |

### 4.3 Position Management Rules

**Roll rule:** Roll short leg at DTE=21 to exactly 30 DTE. Set calendar alert. Do not let short legs expire.

**Profit target:** Close at 50% of maximum credit received (credit strategies) or 50% of maximum theoretical gain (debit strategies).

**Stop loss:** Close when loss reaches 2× the initial credit received (credit strategies). For debit strategies: close at full debit loss.

**Key function:** `get_recommendation() -> Recommendation`
- Fetches all three signals (VIX, IV, trend) using their respective fetch functions
- Calls `select_strategy(vix_snap, iv_snap, trend_snap)`
- Returns a fully populated `Recommendation`

---

## 5. Backtest Layer

### 5.1 Pricing Engine (`backtest/pricer.py`)

**Method:** Black-Scholes (European options). SPX options are European-style, so this is appropriate. SPY options are American-style — Black-Scholes slightly understates put prices for American options (ignores early assignment), making backtest results conservatively biased.

**Constants:**
```
RISK_FREE_RATE = 0.045    # 4.5% annualized
TRADING_DAYS   = 252
```

**Core formulas:**
```
d1 = (ln(S/K) + (r + σ²/2) × T) / (σ × √T)
d2 = d1 - σ × √T
T  = dte / TRADING_DAYS

call_price = S × N(d1) - K × e^(-r×T) × N(d2)
put_price  = K × e^(-r×T) × N(-d2) - S × N(-d1)
call_delta = N(d1)
put_delta  = -N(-d1)
```

Where `N()` is the standard normal CDF (`scipy.stats.norm.cdf`).

**Strike search (`find_strike_for_delta`):**
Binary search (60 iterations) over a range of ±50% of current SPX price. Finds the strike that produces the target absolute delta. For calls: search where `call_delta(strike) == target`. For puts: search where `abs(put_delta(strike)) == target`.

**Key functions:**
```python
call_price(S, K, dte, sigma) -> float
put_price(S, K, dte, sigma) -> float
call_delta(S, K, dte, sigma) -> float
put_delta(S, K, dte, sigma) -> float
find_strike_for_delta(S, dte, sigma, target_delta, is_call) -> float
```

### 5.2 Backtest Engine (`backtest/engine.py`)

**Method:** Walk-forward simulation. Processes each historical trading day in sequence. No lookahead bias — signal computation at time `t` only uses data available at time `t`.

**Input data:** Merged DataFrame of VIX and SPX closing prices from `start_date` to today.

**Critical timezone fix:** VIX data from yfinance uses `America/Chicago` timezone; SPX uses `America/New_York`. Both must be normalized to tz-naive dates before merging:
```python
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
```
Without this, the join produces 0 matching rows.

**`Trade` dataclass:**
```
strategy:       StrategyName
underlying:     str
entry_date:     str           # "YYYY-MM-DD"
exit_date:      str           # "" until closed
entry_spx:      float
exit_spx:       float
entry_vix:      float
entry_credit:   float         # positive = credit received, negative = debit paid
exit_pnl:       float         # final P&L in dollars (positive = profit)
exit_reason:    str           # "50pct_profit" | "stop_loss" | "roll_21dte" | "expiry"
dte_at_entry:   int
dte_at_exit:    int
```

**`Position` dataclass (open trade):**
```
strategy:       StrategyName
underlying:     str
entry_date:     str
entry_spx:      float
entry_vix:      float
entry_sigma:    float         # VIX / 100
legs:           list[tuple]   # (action: int, is_call: bool, strike: float, dte: int, qty: int)
                              # action: +1 = long, -1 = short
entry_value:    float         # net debit (positive) or net credit (negative) at entry
days_held:      int           # incremented each simulated day
```

**Leg construction (`_build_legs`):** Uses `find_strike_for_delta` to find strikes at entry. Delta targets match the selector's Leg definitions. Returns `(legs_list, short_dte)` where `short_dte` is used for the roll-at-21 check.

**P&L computation (critical — sign convention):**
```python
entry_value  = sum(action × price × qty)  # at entry date
current_value = sum(action × price × qty)  # repriced daily with same legs, reduced DTE

pnl = current_value - entry_value
```

- **Credit trade example:** sell 1 put for $500 → `entry_value = -500`. Later, buy back for $250 → `current_value = -250`. `pnl = -250 - (-500) = +250`. ✓
- **Debit trade example:** buy spread for $500 → `entry_value = +500`. Later, worth $700 → `current_value = +700`. `pnl = +700 - +500 = +200`. ✓

**Common mistake:** `pnl = entry_value - current_value` is WRONG and produces inverted P&L.

**Exit rules (checked in this order each simulated day):**
1. Short DTE ≤ 21 → exit with reason `"roll_21dte"`. Compute pnl.
2. `pnl_ratio = pnl / abs(entry_value)` ≥ 0.50 → exit with reason `"50pct_profit"`.
3. `pnl_ratio` ≤ -2.0 (credit trades only, where `entry_value < 0`) → exit with reason `"stop_loss"`.
4. DTE ≤ 0 → exit with reason `"expiry"`.

**New position entry:** If no open position on a given day, compute signals from historical data and call `select_strategy`. If strategy is not `REDUCE_WAIT`, build legs and open position. Only enter on days with valid data for all three signal sources.

**`compute_metrics(trades) -> dict`:**
```python
{
  "total_trades": int,
  "win_rate":     float,        # fraction 0–1
  "avg_win":      float,        # average P&L of winning trades
  "avg_loss":     float,        # average P&L of losing trades (negative)
  "expectancy":   float,        # weighted average P&L per trade
  "total_pnl":    float,
  "max_drawdown": float,        # most negative cumulative drawdown (negative number)
  "sharpe":       float,        # annualized Sharpe = mean(pnl) / std(pnl) × √(trades_per_year)
  "by_strategy":  dict,         # { strategy_name: { n, win_rate, avg_pnl } }
}
```

**Backtest results (2023-01-10 → 2026-03-26, Precision B):**
- 41 trades, win rate 70.7%, expectancy +$400/trade
- Total P&L +$16,389, max drawdown -$18,864, Sharpe 0.42
- Bull Call Diagonal: 13 trades, 100% win rate, avg +$1,859

**Precision B limitations:**
- No bid/ask spread (optimistic by ~0.1–0.3%)
- Constant IV per day (no intraday vol moves)
- No slippage or commissions
- American-style early assignment not modeled

---

## 6. Notification Layer (`notify/telegram_bot.py`)

### 6.1 Bot Setup

- Library: `python-telegram-bot >= 20` (async API)
- Parse mode: **HTML** (not MarkdownV2 — MarkdownV2 requires escaping too many characters in dynamic content)
- HTML escaping function: `_h(text)` → replaces `&`, `<`, `>` only. Never escape other characters.
- Bot username: @Spx_opt_bot (user-specific; recreate with @BotFather)

### 6.2 Commands

| Command | Handler | Behavior |
|---------|---------|----------|
| /today | `cmd_today` | Fetch signals + send recommendation |
| /status | `cmd_status` | Show raw VIX / IVR / IVP / trend values |
| /backtest | `cmd_backtest` | Run 1-year walk-forward backtest, send summary |
| /help | `cmd_help` | List commands |
| /start | → cmd_help | Alias for /help |

### 6.3 Scheduled Push

- Scheduler: `APScheduler.AsyncIOScheduler`
- Schedule: Mon–Fri, 09:35 ET
- Timezone: `ZoneInfo("America/New_York")`

**Critical implementation detail:** The `AsyncIOScheduler.start()` call must happen inside the `Application.post_init` async callback, NOT in the `main()` function. Calling it before the event loop is running raises `RuntimeError: no running event loop`.

```python
async def post_init(application: Application) -> None:
    scheduler = AsyncIOScheduler(timezone=ET)
    scheduler.add_job(
        scheduled_push,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=35, timezone=ET),
        args=[application.bot, chat_id],
    )
    scheduler.start()

app = Application.builder().token(token).post_init(post_init).build()
```

**Trading day check:** Before each scheduled push, `is_trading_day()` checks:
1. Weekday (Mon–Fri only)
2. US federal holidays for 2025 and 2026 (hardcoded set)

### 6.4 Message Format

Recommendation message structure (HTML):
```
{emoji} <b>Options Recommendation — {date}</b>
────────────────────────────────
<b>Strategy:</b>   {strategy}
<b>Underlying:</b> {underlying}

<b>Legs:</b>
  {action} {option} {dte}DTE  δ{delta}  <i>{note}</i>
  ...

<b>Max Risk:</b>  {max_risk}
<b>Target:</b>    {target_return}
<b>Size Rule:</b> {size_rule}
<b>Roll At:</b>   {roll_rule}

<b>Why:</b> <i>{rationale}</i>

<b>Signals:</b> VIX {vix} [{regime}]  IVR {iv_rank}  Trend {trend_signal}
[⚠️ <b>SPX below 200MA</b> — reduce size]
────────────────────────────────
<i>Verify strikes on your broker before executing.</i>
```

---

## 7. Web Layer

### 7.1 Flask Server (`web/server.py`)

**Framework:** Flask ≥ 3.0
**Port:** 5050 (default), configurable via `--port=N`
**Templates:** Jinja2 in `web/templates/`

**JSON serialization:** Dataclasses with enum fields are serialized using `dataclasses.asdict()` + a custom `_EnumEncoder(json.JSONEncoder)` that converts enum instances to their `.value` string. The `default=str` fallback handles any remaining non-serializable types.

**In-memory backtest cache:** `_backtest_cache: dict[str, tuple[float, dict]]`
Key = `start_date` string. TTL = 300 seconds (5 minutes). Avoids re-running expensive (~30s) simulations on page refresh.

**Routes:**

| Route | Returns |
|-------|---------|
| `GET /` | `index.html` |
| `GET /matrix` | `matrix.html` |
| `GET /backtest` | `backtest.html` |
| `GET /api/recommendation` | JSON: Recommendation dataclass |
| `GET /api/backtest?start=YYYY-MM-DD` | JSON: `{metrics, trades}` |

**API response for `/api/recommendation`:** Full Recommendation dataclass serialized to JSON. All enum values become their string `.value`. All nested dataclasses (VixSnapshot, IVSnapshot, TrendSnapshot, Leg) become nested JSON objects.

**API response for `/api/backtest`:**
```json
{
  "metrics": {
    "total_trades": 41,
    "win_rate": 0.707,
    "avg_win": 1200.5,
    "avg_loss": -650.2,
    "expectancy": 400.1,
    "total_pnl": 16389.0,
    "max_drawdown": -18864.0,
    "sharpe": 0.42,
    "by_strategy": {
      "Bull Call Diagonal": { "n": 13, "win_rate": 1.0, "avg_pnl": 1859.0 }
    }
  },
  "trades": [
    {
      "strategy": "Bull Call Diagonal",
      "underlying": "SPX",
      "entry_date": "2023-01-23",
      "exit_date": "2023-03-15",
      "entry_spx": 3972.0,
      "exit_spx": 4109.0,
      "entry_vix": 19.8,
      "entry_credit": -2800.0,
      "exit_pnl": 1350.0,
      "exit_reason": "50pct_profit",
      "dte_at_entry": 90,
      "dte_at_exit": 21
    }
  ]
}
```

### 7.2 Dashboard (`web/templates/index.html`)

**Design theme:** Dark terminal editorial. Dark navy/black background, warm off-white text, gold accents for bullish, green for profit, red for loss/bearish. Typography: `Newsreader` (italic serif for strategy name) + `JetBrains Mono` (numbers) + `DM Sans` (UI text).

**Page structure:**
1. Sticky nav bar (Dashboard | Matrix | Backtest links, live dot, date)
2. 3-column signal strip (VIX card | IVR/IVP card | SPX Trend card)
   - Each card has a colored top border matching its current signal state (gold=NORMAL/HIGH-IV, green=BULLISH, red=BEARISH/HIGH-VOL, blue=LOW-VOL/LOW-IV)
3. Recommendation card (loading spinner → populated by JS)
   - Header: emoji + italic strategy name + underlying + date
   - Left gold accent bar (3px, CSS `::before`)
   - Legs table: columns = action (green=BUY, orange=SELL) | option type (blue=CALL, red=PUT) | DTE | delta | note
   - 4-column metrics row: Max Risk | Target Return | Size Rule | Roll At
   - Rationale in italic with quotation marks
   - Macro warning banner (red background) if `macro_warning = true`
4. Footer: disclaimer text

**Data flow:** Page load → JS `fetch('/api/recommendation')` → render signal cards + recommendation card. Loading spinner shown during fetch. Error state with "Try again" button if fetch fails.

### 7.3 Backtest (`web/templates/backtest.html`)

**Libraries:** Chart.js 4.4.0 (from CDN jsDelivr)

**Page structure:**
1. Controls bar: Start Date input | End Date input | "Run Backtest" button | elapsed timer
2. 6 metric cards (2 rows × 3): Total Trades | Win Rate | Expectancy | Total P&L | Max Drawdown | Sharpe
3. Equity curve chart (Chart.js line chart)
4. By-strategy table
5. Collapsible trade log table

**Equity curve chart details:**
- X axis: exit dates of completed trades (sorted chronologically)
- Y axis: cumulative P&L in dollars
- Line: gold (#C9A840), 1.5px, tension 0.35, gradient fill
- **Trade markers:** per-point colored dots. Green circle (`pointStyle: 'circle'`) = profitable trade, red triangle (`pointStyle: 'triangle'`) = losing trade
- Tooltip on hover (nearest-point mode): shows strategy name, underlying, entry→exit dates, trade P&L, cumulative P&L, SPX in/out, VIX at entry, exit reason

**Backtest is auto-run** on page load with default start date = 1 year ago. Results cached 5 minutes server-side.

**Trade log table columns:** # | Strategy | UL | Entry Date | Exit Date | SPX In | VIX | P&L | Exit Reason
Exit reason shown as color-coded pill: green (50pct_profit) | red (stop_loss) | gold (roll_21dte) | gray (default)

### 7.4 Signal Matrix (`web/templates/matrix.html`)

**Purpose:** Reference tool showing the complete 16-combination decision matrix. Allows exploration of all strategy choices and highlights the current market position.

**Page structure:**
1. Signal banner: live signal path `VIX 18.4 [NORMAL] → IV HIGH (IVP 67) → BULLISH → Short Put`
2. Three regime tabs (LOW VOL / NORMAL / HIGH VOL)
3. 3×3 strategy grid (IV: HIGH/NEUTRAL/LOW rows × Trend: BULLISH/NEUTRAL/BEARISH columns)
4. Legend (direction colors)
5. Detail panel (populated on cell click)

**Matrix behavior:**
- On load: fetches `/api/recommendation` to get current signals
- Auto-switches to the tab matching current regime
- Highlights current cell with gold border + "NOW" label
- Auto-populates detail panel with current strategy
- Clicking any other cell shows its strategy details without page reload

**Detail panel fields:** Underlying | DTE Structure | Delta Targets | Trade Type | When to Use | Risk Profile | Roll/Exit Rule

**Strategy color coding:**
- Bullish: green
- Bearish: red
- Neutral/both sides: gold
- Defensive (LEAP): blue
- Wait: gray

---

## 8. Entry Point (`main.py`)

```
Usage:
  python main.py                          # Run Telegram bot (default)
  python main.py --dry-run                # Print today's recommendation to terminal
  python main.py --backtest [--start=YYYY-MM-DD] [--verbose]  # Run backtest
  python main.py --web [--port=N]        # Start Flask dashboard (default port 5050)
  python main.py --get-chat-id           # Find Telegram chat_id
```

---

## 9. Package Configuration (`pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "spx-strat"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "yfinance>=0.2",
    "pandas>=2.0",
    "numpy>=1.26",
    "scipy>=1.12",
    "python-telegram-bot>=20",
    "python-dotenv>=1.0",
    "apscheduler>=3.10",
    "flask>=3.0",
]

[tool.setuptools.packages.find]
where = ["."]
```

**Installation:** `pip install -e .` — enables `from signals.vix_regime import ...` style imports across all modules. Run from project root. Python 3.11+ required.

---

## 10. Deployment (macOS)

### 10.1 Environment

**Virtual environment:** `venv/` in project root, created with `python3.12 -m venv venv`.

**Secrets file:** `.env` in project root (excluded from git via `.gitignore`):
```
TELEGRAM_BOT_TOKEN=<token from @BotFather>
TELEGRAM_CHAT_ID=<your personal chat ID>
```

To find chat ID: `python main.py --get-chat-id`, then send any message to the bot.

### 10.2 launchd Auto-start (LaunchAgent)

File: `~/Library/LaunchAgents/com.spxstrat.bot.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spxstrat.bot</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/{username}/Documents/workspace/SPX_strat/venv/bin/python</string>
        <string>main.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/{username}/Documents/workspace/SPX_strat</string>

    <key>KeepAlive</key>
    <true/>

    <key>RunAtLoad</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>StandardOutPath</key>
    <string>/Users/{username}/Documents/workspace/SPX_strat/logs/bot.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/{username}/Documents/workspace/SPX_strat/logs/bot-error.log</string>
</dict>
</plist>
```

**Management commands:**
```bash
launchctl load   ~/Library/LaunchAgents/com.spxstrat.bot.plist   # start
launchctl unload ~/Library/LaunchAgents/com.spxstrat.bot.plist   # stop
launchctl list | grep spxstrat                                     # status (shows PID + exit code)
tail -f logs/bot-error.log                                        # live log
```

**Limitation:** LaunchAgent only runs when user is logged in. For always-on operation (no login required), would need LaunchDaemon with root/admin setup.

### 10.3 .gitignore

Excluded from git:
```
venv/
__pycache__/
*.pyc, *.pyo
.env
config.local.yaml
*.db
.DS_Store
logs/
*.log
```

---

## 11. Critical Implementation Notes

These are non-obvious decisions and bugs that were discovered and fixed during development. A new implementation must incorporate all of them.

### 11.1 Timezone Normalization in Backtest

**Problem:** yfinance returns VIX with `America/Chicago` index, SPX with `America/New_York`. Merging on DatetimeIndex produces 0 matching rows.

**Fix:** Before any join or comparison, normalize both DataFrames to tz-naive date indices:
```python
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
```
Apply this immediately after fetching, before any derived computations.

### 11.2 P&L Sign Convention

The P&L formula must be `current_value - entry_value`, NOT `entry_value - current_value`.

`entry_value` and `current_value` are computed as `sum(action × price × qty)` where `action = +1` for long, `-1` for short. This means a credit (short) position has a negative `entry_value`.

Flipping the formula inverts all P&L signs, producing negative total P&L with inversely correlated win/loss trades.

### 11.3 APScheduler Event Loop

`AsyncIOScheduler.start()` raises `RuntimeError: no running event loop` if called before the asyncio event loop is running. The event loop is only running inside an async context.

**Fix:** Start the scheduler inside `Application.post_init(application)`, which is an async callback called by `application.run_polling()` after the event loop starts.

### 11.4 Telegram Parse Mode

**Do not use MarkdownV2.** It requires escaping many special characters (`-`, `.`, `(`, `)`, `!`, `+`, etc.) in dynamic content. Any unescaped character crashes the message send.

**Use HTML parse mode.** Only three characters need escaping: `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`. Implement a single `_h(text)` function for this.

### 11.5 IVR/IVP Divergence

When a single historical VIX spike (e.g., 52.3 during a market crash) distorts the 52-week high, IVR is artificially compressed (e.g., 35.9) while IVP correctly reflects that current IV is high (e.g., 94.0). The two metrics can diverge by 50+ points.

The selector must always check for divergence: if `|IVR - IVP| > 15`, use IVP with thresholds 70/40 instead of IVR with thresholds 50/30.

---

## 12. Future Development Roadmap

### Priority D: Polygon.io Real Options Chain (Precision A)

**Purpose:** Replace Black-Scholes strike/price estimation with real historical options chain data.
**Cost:** $29/month (Polygon.io Options Starter plan)
**Target module:** `strategy/params.py` (new) — given a strategy name and today's date, return actual strikes from live options chain.
**Impact:** More accurate position sizing, more realistic backtesting, real DTE/strike recommendations instead of delta-targeted estimates.

**API pattern:**
```
GET https://api.polygon.io/v3/snapshot/options/{underlyingTicker}
    ?expiration_date={YYYY-MM-DD}
    &contract_type={call|put}
    &order=asc&limit=250&sort=strike_price
    &apiKey={POLYGON_API_KEY}
```

**Backtest upgrade path:** `backtest/engine_precision_a.py` — replace `_build_legs()` Black-Scholes calls with actual historical chain lookups. This requires historical options data ($29/month Starter plan includes it).

### Priority E: LaunchDaemon (Always-on, No Login Required)

**Purpose:** Run bot even when macOS user is not logged in.
**Method:** Move plist from `~/Library/LaunchAgents/` to `/Library/LaunchDaemons/`, add `<key>UserName</key><string>lienchen</string>`.
**Requirement:** `sudo launchctl load` — requires administrator password.

### Priority F: Multi-Strategy Position Tracking

**Purpose:** Track when the user actually executed a recommended trade. Store entry/exit dates, actual strikes, actual P&L.
**Method:** SQLite database (`trades.db`, already in .gitignore). New `/api/journal` endpoint. Telegram commands: `/entered`, `/closed`.

### Priority G: VIX Term Structure

**Purpose:** Check VIX vs VIX3M (3-month) vs VVIX (vol of vol) for richer signal.
**Signal:** If VIX > VIX3M (backwardation) → elevated near-term fear, be cautious with short vol. If VIX < VIX3M (normal contango) → favorable for selling premium.
**yfinance tickers:** `^VIX3M`, `^VVIX`

### Priority H: Greeks-Based Position Sizing

**Purpose:** Size positions by portfolio-level delta/theta targets rather than % of account.
**Target:** Portfolio delta < ±50, portfolio theta = 0.1–0.3% of NAV per day.

---

## 13. Design Decisions Log

| Decision | Alternative Considered | Reason |
|----------|----------------------|--------|
| VIX as IV proxy | Actual options chain IV | Free, always available, sufficient accuracy for signal classification |
| Black-Scholes pricing | Polygon historical chain | Free, deterministic, sufficient for walk-forward validation |
| HTML Telegram parse mode | MarkdownV2 | MarkdownV2 too fragile with dynamic content; HTML needs only 3 escapes |
| LaunchAgent (not cron) | cron | LaunchAgent restarts on crash, logs stdout/stderr, integrates with macOS lifecycle |
| Post_init for APScheduler | main() function | Asyncio event loop must be running before scheduler.start() |
| IVP over IVR on divergence | Always use IVR | Single VIX spike distorts IVR; IVP is more robust measure |
| One position at a time | Portfolio of positions | Simplicity; user executes manually; avoids complex margin interactions |
| SPX for theta strategies | SPY | Section 1256 tax treatment (60/40 cap gains), cash-settled, no assignment risk |
| SPY for directional spreads | SPX | Smaller notional, easier to manage size for directional bets |

---

## 14. Backtest Interpretation Notes

The current backtest (Precision B) is useful for **strategy validation**, not for forecasting actual returns. Expected adjustments for live trading:

- **Bid/ask spread:** Subtract ~$50–$150/trade for realistic fill prices
- **Commission:** Interactive Brokers: ~$0.65/contract × legs. On a 2-leg diagonal: -$1.30/trade minimum
- **Slippage:** Market orders: -$25–$75/trade. Limit orders at mid: -$0 to -$50/trade
- **Early assignment (American options):** Small risk on SPY options; SPX is European (no early assignment)
- **IV skew:** Black-Scholes assumes flat vol surface. Real OTM puts are priced with higher IV (put skew), making short puts cheaper in practice than the model assumes

Total expected drag: approximately **-$100 to -$300 per trade** vs Precision B results. Adjust expectancy accordingly: +$400 model → ~+$100 to +$300 realistic.

---

*Document generated 2026-03-26. For questions about design decisions, refer to the git history and inline code comments.*
