# SPX Options Strategy — System Implementation Status
**Date: 2026-04-07（更新版，含 SPEC-039~047）| 完整系统实现文档，供全新 Claude agent 重建系统理解**

*承接 `system_status_2026-04-05.md`。主要变更（本版）：Schwab 期权链扫描器（SPEC-039/040/042/045/047）；EOD 4:03pm 推送（SPEC-041）；Schwab 实时告警取代 Yahoo 日内路径（SPEC-046）。策略核心逻辑、回测引擎、信号体系、selector 均无变更。*

---

## 1–3. 项目概览 / 技术栈 / 入口（无变更）

见 `system_status_2026-04-05.md` §1–3。

---

## 2. 文件结构（更新版）

```
SPX_strat/
├── main.py
├── pyproject.toml
├── .env
├── logs/
│   ├── current_position.json
│   └── trade_log.jsonl
├── data/
│   ├── market_cache/
│   ├── market_cache.py
│   └── backtest_stats_cache.json
├── signals/
│   ├── vix_regime.py
│   ├── iv_rank.py
│   ├── trend.py
│   ├── overlay.py
│   └── intraday.py              # ★ SPEC-046 更新：quote-driven helpers + realtime 字段
├── strategy/
│   ├── catalog.py
│   ├── selector.py
│   └── state.py
├── backtest/
│   ├── engine.py
│   ├── pricer.py
│   ├── experiment.py
│   ├── registry.py
│   ├── portfolio.py
│   ├── metrics_portfolio.py
│   ├── shock_engine.py
│   ├── attribution.py
│   ├── run_shock_analysis.py
│   ├── run_oos_validation.py
│   ├── run_trend_ablation.py
│   └── prototype/
├── performance/
│   ├── __init__.py
│   └── live.py
├── schwab/
│   ├── __init__.py
│   ├── auth.py
│   ├── client.py                # ★ SPEC-039/040/045/046 更新：chain + quote helpers
│   ├── scanner.py               # ★ SPEC-039/042/045/047 新文件：strike liquidity scanner
│   └── setup.py
├── notify/
│   └── telegram_bot.py          # ★ SPEC-041/046 更新：EOD push + Schwab primary alerts
├── web/
│   ├── server.py
│   └── templates/
│       ├── index.html
│       ├── matrix.html
│       ├── backtest.html
│       ├── margin.html
│       └── performance.html
├── tests/
│   ├── test_specs_017_015.py
│   ├── test_spec_018_metrics.py
│   ├── test_spec_batch_024_029_020.py
│   ├── test_state_and_api.py
│   ├── test_strategy_unification.py
│   ├── test_live_performance.py
│   ├── test_schwab_scanner.py   # ★ SPEC-039/047 新文件
│   ├── test_spec_046_quotes.py  # ★ SPEC-046 新文件：quote normalization
│   └── test_telegram_bot.py     # ★ SPEC-046 更新：bot Schwab/Yahoo/stale/realtime
├── doc/
│   └── research_notes.md        # ★ 新增 §42：delta monotonicity 设计决策
└── task/
    ├── strategy_spec.md
    ├── SPEC-010.md ~ SPEC-047.md
    └── *_handoff.md
```

---

## 4. 核心模块详解

### 4.1–4.24（无变更）

见 `system_status_2026-04-05.md` §4.1–4.24。

---

### 4.25 `schwab/scanner.py`（SPEC-039/042/045/047）★ 新文件

**常量**：
```python
_DELTA_SCAN_WINDOWS = (80, 140, 220)   # SPEC-047 自适应三轮窗口
_SCORE_WINDOW = 10                      # 评分邻域：最优中心 ±10 档
```

**关键函数**：

```python
def _is_index_symbol(symbol: str | None) -> bool
    # SPX / $SPX → True（驱动宽松 OI 过滤）

def _delta_gap(actual_delta: float, target_delta: float) -> float
    # abs(|actual| − |target|)

def _seek_target_delta_strike(chain: list[dict], target_delta: float) -> float | None
    # SPEC-045：排序后扫描穿越点，线性插值返回 strike
    # PUT: |delta| 随 strike 递增；CALL: delta 随 strike 递减（单调性）
    # 无穿越时返回最近边界 strike（boundary fallback）

def _is_boundary_hit(chain: list[dict], sought_strike: float | None) -> bool
    # SPEC-047：sought_strike == min(strikes) 或 max(strikes) → True
    # 空链或 sought_strike=None → True（视为边界）

def scan_strikes(chain: list[dict], target_delta: float, symbol: str | None = None) -> list[dict]
    # SPEC-039 评分核心
    # 过滤：bid > 0, spread_pct ≤ 50%, 非指数时 OI ≥ 100（指数宽松为 SPEC-042）
    # score = |delta − target| × 0.4 + spread_pct × 0.4 + oi_penalty + volume_penalty
    # oi_penalty（指数）= OI≤0 → 0.35，否则 0.2 × 1/log(OI+2)
    # 返回按 score 升序列表；首位 recommended=True

def build_strike_scan(
    symbol: str,
    option_type: str,
    target_delta: float,
    target_dte: int,
    center_strike: float | None = None,
) -> dict  # {"rows": list[dict], "scan_fallback": bool}
    # center_strike=None：宽泛单次链（原始路径，SPEC-039）
    # center_strike 指定：自适应三轮扩窗（SPEC-047）
    #   for window in (80, 140, 220):
    #     chain = get_option_chain(..., strike_window=window)
    #     sought = _seek_target_delta_strike(chain, target_delta)
    #     best_center = round(sought / 5.0) × 5.0
    #     if not _is_boundary_hit(chain, sought): break
    #   slice ±_SCORE_WINDOW around best_center → scan_strikes()
    #   首位 row 附加: delta_gap, interpolated_center（SPEC-045）
```

**SPEC-042 指数宽松 OI 逻辑**：
- `_is_index_symbol()` 为 True 时，`open_interest < 100` 硬过滤 **不生效**
- 替换为 `oi_penalty` 纳入 score（OI=0 时 penalty=0.35，有 OI 时按 log 递减）
- 非指数保留原始硬过滤（`open_interest < 100` → 剔除）

---

### 4.26 `schwab/client.py`（SPEC-039/040/045/046 更新）

**新增：Option Chain 获取**（SPEC-039/040）

```python
def get_option_chain(
    symbol: str,
    option_type: str,         # "CALL" / "PUT"
    target_dte: int,
    dte_range: int = 7,
    center_strike: float | None = None,
    strike_window: int | None = None,
) -> list[dict]
    # Endpoint: GET /marketdata/v1/chains?symbol=...
    # center_strike=None → strikeCount=20（宽泛）
    # center_strike 指定 → strikeCount=max(300, strike_window*20)，本地裁剪
    # 每行归一化为: {strike, delta, bid, ask, spread_pct, open_interest, volume, expiry}
```

**`_chain_cache_key()` 含 `strike_window`**（SPEC-040/045）：
```python
def _chain_cache_key(symbol, option_type, target_dte, dte_range,
                     center_strike=None, strike_window=None) -> str
    # center_strike=None → "chain:{sym}:{type}:{dte}:{range}"
    # 有 center_strike → "chain:{sym}:{type}:{dte}:{range}:{center_key}:{w}"
    # 不同 strike_window → 不同缓存 key，防止宽窗数据覆盖窄窗
```

**新增：Index Quote 获取**（SPEC-046）

```python
def get_index_quote(symbol: str) -> dict
    # Endpoint: GET /marketdata/v1/quotes?symbols={symbol}
    # 返回归一化结构:
    # {
    #   "symbol": str,
    #   "last": float,
    #   "open": float,
    #   "high": float,
    #   "low": float,
    #   "close": float,
    #   "quote_time": str,          # ISO 8601（来自 tradeTime ms / 1000.0）
    #   "security_status": str,
    #   "realtime": bool,           # False = 账户为延迟报价
    # }

def get_vix_quote() -> dict     # get_index_quote("$VIX")
def get_spx_quote() -> dict     # get_index_quote("$SPX")
```

---

### 4.27 `signals/intraday.py`（SPEC-046 更新）

**Dataclass 更新**：`VixSpikeAlert` 和 `IntradayStopTrigger` 新增字段：
```python
realtime: Optional[bool] = None
    # True = Schwab 实时；False = 非实时账户；None = Yahoo fallback
```

**新增 Quote-Driven Helpers**：
```python
def get_vix_spike_from_quote(quote: dict) -> VixSpikeAlert
    # vix_open = quote["open"], vix_current = quote["last"]
    # timestamp 来自 quote["quote_time"]（市场数据时间，非 poll 时间）
    # realtime = quote.get("realtime")

def get_spx_stop_from_quote(quote: dict) -> IntradayStopTrigger
    # spx_open = quote["open"], spx_current = quote["last"]
    # 同上
```

---

### 4.28 `notify/telegram_bot.py`（SPEC-041/046 更新）

**新增模块变量**：
```python
_morning_snapshot: dict | None = None
    # {"strategy_key": str, "position_action": str, "date": str}
    # scheduled_push() 成功后写入；_reset_intraday_state() 每日 9:30 清除

_STALE_QUOTE_MINUTES = 10
    # 报价时效阈值；超过 10 分钟标注 delayed
```

**新增函数**：
```python
def _alert_timing_label(timestamp: str | None, realtime: bool | None) -> str
    # realtime is False → "[delayed — non-realtime quote]"（无条件，不计时差）
    # realtime is True 或 None，时差 > 10min → "[sent {t} | delayed {X}m]"
    # 否则 → "[bar {quote_time} | sent {send_time}]"

def scheduled_eod_push()       # SPEC-041：4:03pm ET
    # select_strategy(use_intraday=False)（强制 EOD 收盘数据）
    # 与 _morning_snapshot 对比，推送 EOD 信号快照
```

**`intraday_monitor()` 更新**（SPEC-046）：
```python
# Primary: try get_vix_quote() + get_spx_quote()
#   → get_vix_spike_from_quote() / get_spx_stop_from_quote()
#   → 告警消息附 _alert_timing_label()
# Fallback: except → get_vix_spike(interval="5m") / get_spx_stop(interval="5m")
#   （原 Yahoo 路径，realtime=None 走时差逻辑）
# Outer except: log only，不崩溃
```

**`scheduled_push()` 更新**（SPEC-041）：
- 成功推送后写入 `_morning_snapshot`

---

## 5. 数据流向（更新版）

```
yfinance (^VIX, ^VIX3M, ^GSPC)
    ↓ load_or_fetch_history() [TTL 缓存]
    ↓
signals/vix_regime.py  →  VixSnapshot
signals/iv_rank.py     →  IVSnapshot
signals/trend.py       →  TrendSnapshot
    ↓
strategy/selector.py  select_strategy()
    ↓
Recommendation
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ backtest/engine.py  run_backtest()（无变更）                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Live Alert Path（notify/telegram_bot.py）                        │
│                                                                 │
│  9:35am ET  scheduled_push()                                    │
│    → select_strategy(use_intraday=True)                         │
│    → 推送 + 写 _morning_snapshot                                │
│                                                                 │
│  4:03pm ET  scheduled_eod_push()  ★ SPEC-041 新增              │
│    → select_strategy(use_intraday=False)                        │
│    → 对比 _morning_snapshot → 推送 EOD 快照                    │
│                                                                 │
│  每 5min    intraday_monitor()  ★ SPEC-046 更新                │
│    Primary: schwab/client.py get_vix_quote / get_spx_quote      │
│      → signals/intraday.py get_*_from_quote()                   │
│      → 告警 + timing label（realtime / stale 标注）             │
│    Fallback: Yahoo intraday history（原有路径）                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Live Strike Scan（web/server.py /api/position/open-draft）       │
│                                                                 │
│  schwab/client.py get_option_chain(... strike_window=w)         │
│    ↓ [缓存 key 含 strike_window，防 contamination]              │
│  schwab/scanner.py build_strike_scan(center_strike=...)         │
│    ↓ 自适应三轮扩窗 (80→140→220)  ★ SPEC-047                   │
│    ↓ _seek_target_delta_strike() 插值  ★ SPEC-045              │
│    ↓ _is_boundary_hit() 检测  ★ SPEC-047                       │
│    ↓ scan_strikes() 评分（指数宽松 OI）  ★ SPEC-042            │
│    ↓ rows 附 delta_gap + interpolated_center  ★ SPEC-045       │
│  → {"rows": [...], "scan_fallback": bool}                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 测试覆盖

```
tests/
├── test_specs_017_015.py
├── test_spec_018_metrics.py
├── test_spec_batch_024_029_020.py
├── test_state_and_api.py
├── test_strategy_unification.py
├── test_live_performance.py
├── test_schwab_scanner.py        # ★ SPEC-039/047 新文件
│   ├── scan_strikes() 基础评分与排序
│   ├── scan_strikes() 指数宽松 OI（SPEC-042）
│   ├── _is_boundary_hit() — min/max/interior/空链
│   ├── T1: pass1 边界 → pass2 触发，call_count=2
│   ├── T2: pass1+2 边界 → pass3 触发，call_count=3
│   ├── T3: pass1 内部穿越停止（call_count=1）
│   ├── T4: pass2 内部穿越停止（call_count=2）
│   └── T5: pass3 边界 fallback 不崩溃
├── test_spec_046_quotes.py       # ★ SPEC-046 新文件
│   ├── get_index_quote() 归一化（tradeTime ms→秒）
│   ├── get_vix_spike_from_quote() 用 open/last
│   ├── get_spx_stop_from_quote() 用 open/last
│   └── realtime 字段透传
└── test_telegram_bot.py          # ★ SPEC-046 扩展
    ├── intraday_monitor() Schwab primary
    ├── intraday_monitor() fallback to Yahoo on exception
    ├── _alert_timing_label() stale > 10min
    └── _alert_timing_label() realtime=False 无条件标注
```

**运行方式**：`python3 -m unittest discover tests`

---

## 7. SPEC 执行状态

### 已完成（DONE）

| SPEC | 主题 | 修改/新增文件 |
|------|------|-------------|
| SPEC-010 | VIX 期限结构过滤 | selector.py, vix_regime.py |
| SPEC-011 | Bear Call Spread HV | selector.py, catalog.py |
| SPEC-012 | ROM 指标 | engine.py |
| SPEC-013 | BP 利用率仓位定量 | selector.py, engine.py |
| SPEC-014 | 多仓并行引擎 | engine.py |
| SPEC-015 | Vol spell throttle | selector.py, engine.py |
| SPEC-017 | Greek-aware dedup | catalog.py, selector.py, engine.py |
| SPEC-018 | Extended metrics | engine.py, telegram_bot.py |
| SPEC-020 | ATR-Normalized Entry Gate | signals/trend.py, selector.py, engine.py |
| SPEC-024 | Daily portfolio + bp_target 2× | backtest/registry.py, portfolio.py, metrics_portfolio.py, selector.py, engine.py |
| SPEC-025 | Portfolio Shock-Risk Engine | backtest/shock_engine.py, engine.py |
| SPEC-026 | VIX Acceleration Overlay | signals/overlay.py, selector.py, engine.py |
| SPEC-027 | Shock Engine Phase A/B | backtest/run_shock_analysis.py |
| SPEC-028 | Capital Efficiency Attribution | backtest/attribution.py |
| SPEC-029 | IS/OOS Validation | backtest/run_oos_validation.py |
| SPEC-030 | Intraday Stop Signal Research | 研究结论：提前触发率 0%，收盘判断足够 |
| SPEC-031 | Dashboard 前端改进 | index.html, matrix.html, backtest.html, server.py |
| SPEC-032 | Decision Strip + Risk Flag Bar | index.html, selector.py |
| SPEC-033 | Backtest On-Demand + 磁盘缓存 | backtest.html, server.py |
| SPEC-034 | Trade Entry UI + Trade Log | logs/trade_log_io.py, state.py, server.py, index.html |
| SPEC-035 | Schwab API Read-Only | schwab/auth.py, schwab/client.py, schwab/setup.py, server.py, index.html, margin.html |
| SPEC-036 | Trade Log Corrections & Void | logs/trade_log_io.py, server.py, index.html |
| SPEC-037 | Live Trade Performance Tracking | performance/live.py, server.py, performance.html |
| SPEC-038 | Paper Trade Tag & Performance Filter | trade_log_io.py, state.py, server.py, performance.live, index.html, performance.html |
| SPEC-039 | Option Chain Liquidity Scanner | schwab/scanner.py（新）, schwab/client.py, web/server.py, web/templates/index.html |
| SPEC-040 | Strike-Centered Option Chain Scan | schwab/client.py（strikeCount + cache key）|
| SPEC-041 | EOD Signal Snapshot Push (4:03pm) | notify/telegram_bot.py |
| SPEC-042 | Index Option Liquidity Filter Relaxation | schwab/scanner.py |
| SPEC-045 | Delta-Seeking Strike Scan via Interpolation | schwab/scanner.py, schwab/client.py |
| SPEC-046 | Schwab Intraday Alert Source | schwab/client.py, signals/intraday.py, notify/telegram_bot.py |
| SPEC-047 | Adaptive Multi-Pass Delta-Seeking Scan | schwab/scanner.py |

### 待实现（APPROVED）

| SPEC | 主题 | 说明 |
|------|------|------|
| SPEC-044 | Delta Deviation Display in Open Modal | web/server.py + index.html；`target_delta`/`live_delta`/`delta_gap` 新列 |

### 已取消

| SPEC | 主题 | 原因 |
|------|------|------|
| SPEC-043 | Wider Delta-Seeking Strike Scan（迭代扩窗）| 被 SPEC-045（插值方案）完全取代 |

### 研究 SPEC（无 Codex 实现）

| SPEC | 主题 | 结论摘要 |
|------|------|---------|
| SPEC-016 | Realism haircut | BPS 30%，Diagonal 6%，HV 70–74% |
| SPEC-019 | 趋势信号效果分析 | EXIT trigger > ENTRY gate；MA50 滞后可忽略 |
| SPEC-021 | Filter 复杂度协议 | Filter 叠加无自动改善；协议 1-4 已建立 |
| SPEC-022 | Sharpe 鲁棒性 | 3yr CI 宽度 1.56；差异 < 0.5 视为噪声 |
| SPEC-023 | 压力测试 | VIX 25→50 是最大实际风险；50% haircut 后 Sharpe ~0.99 |

---

## 8. 已知限制与技术债（无变化）

见 `system_status_2026-04-05.md` §8。

---

## 9. 开发协作协议（无变化）

见 `system_status_2026-04-05.md` §9。
