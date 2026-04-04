# SPX Options Strategy — System Implementation Status
**Date: 2026-03-30 | 完整系统实现文档，供全新 Claude agent 重建系统理解**

---

## 1. 项目概览

### 基本信息
- **项目名称**：spx-strat（`pyproject.toml` package name）
- **Python 版本**：≥ 3.11
- **安装方式**：`pip install -e .`（editable install）
- **工作目录**：`/Users/lienchen/Documents/workspace/SPX_strat`

### 核心功能
1. 每日自动计算期权策略推荐，通过 Telegram bot 推送
2. walk-forward 回测引擎（Precision B — Black-Scholes 定价）
3. 本地 Web Dashboard（Flask）
4. 策略管理（持仓追踪、开/平仓记录）

### 技术栈

| 组件 | 库 |
|------|---|
| 数据源 | yfinance（Yahoo Finance）|
| 回测定价 | Black-Scholes（自实现 `backtest/pricer.py`）|
| 推送 | python-telegram-bot ≥20（async）|
| 调度 | APScheduler 3.x（AsyncIOScheduler）|
| 数据处理 | pandas ≥2.0, numpy ≥1.26 |
| Web UI | Flask ≥3.0 |
| 配置 | python-dotenv（`.env` 文件）|

---

## 2. 文件结构

```
SPX_strat/
├── main.py                        # 主入口（CLI）
├── pyproject.toml                 # 项目依赖
├── .env                           # TELEGRAM_TOKEN + CHAT_ID（不提交）
├── logs/
│   └── current_position.json      # 持仓状态（strategy/state.py 管理）
├── data/
│   ├── market_cache/              # yfinance 缓存目录（.pkl 文件）
│   ├── market_cache.py            # 缓存策略管理
│   └── backtest_stats_cache.json  # Web dashboard 回测结果持久化缓存
├── signals/
│   ├── vix_regime.py              # VIX regime 分类 + 5日趋势 + backwardation
│   ├── iv_rank.py                 # IV Rank + IV Percentile 计算
│   ├── trend.py                   # SPX MA50 趋势信号
│   └── intraday.py                # 盘中 VIX spike / SPX stop 信号
├── strategy/
│   ├── catalog.py                 # StrategyDescriptor + CANONICAL_MATRIX + Greek metadata
│   ├── selector.py                # StrategyParams + StrategyName + select_strategy()
│   └── state.py                   # 持仓状态 CRUD（logs/current_position.json）
├── backtest/
│   ├── engine.py                  # 主回测引擎 run_backtest() + compute_metrics()
│   ├── pricer.py                  # Black-Scholes pricer（call/put price/delta + strike finder）
│   ├── experiment.py              # 参数实验框架（网格搜索）
│   └── prototype/                 # 各 SPEC 研究原型脚本（只读，不影响生产）
├── notify/
│   └── telegram_bot.py            # Telegram bot + APScheduler 定时推送
├── web/
│   ├── server.py                  # Flask dashboard
│   └── templates/                 # Jinja2 HTML 模板
├── tests/
│   ├── test_specs_017_015.py      # SPEC-017/015 单元测试（5 tests）
│   ├── test_spec_018_metrics.py   # SPEC-018 metrics 单元测试（3 tests）
│   ├── test_state_and_api.py      # 持仓状态 + API 测试
│   └── test_strategy_unification.py # 策略统一性测试
├── doc/
│   ├── SYSTEM_DESIGN.md           # 原始系统设计文档（参考）
│   ├── research_notes.md          # 研究笔记（§1–§31，持续追加）
│   ├── strategy_status_2026-03-30.md  # 策略设计状态（本期生成）
│   └── system_status_2026-03-30.md   # 系统实现状态（本文件）
└── task/
    ├── strategy_spec.md           # 历史归档（SPEC-001~003，旧格式）
    ├── SPEC-010.md ~ SPEC-023.md  # 当前 SPEC 文件
    └── *_handoff.md               # Codex 实施报告
```

---

## 3. 入口与运行方式

### `main.py` CLI 接口

```bash
python main.py                    # 默认：启动 Telegram bot
python main.py --dry-run          # 打印当日推荐至终端（不发送）
python main.py --backtest [--start=YYYY-MM-DD] [--verbose]  # 运行回测
python main.py --web [--port=5050]  # 启动本地 Web dashboard
python main.py --get-chat-id      # 获取 Telegram chat_id
```

### 环境变量（`.env`）

```
TELEGRAM_TOKEN=...  # BotFather 颁发的 bot token
CHAT_ID=...         # 接收消息的 chat id
```

### 数据缓存控制（环境变量）

```
SPX_DISABLE_YF_CACHE=1   # 禁用缓存，每次都从 yfinance 实时拉取
SPX_REFRESH_YF_CACHE=1   # 忽略 TTL 强制刷新缓存
```

---

## 4. 核心模块详解

### 4.1 `data/market_cache.py` — 数据缓存层

**功能**：所有 yfinance 下载统一经此层缓存，避免重复请求。

缓存 TTL 策略：
- `5m` interval → 15 分钟
- `1h` interval → 6 小时
- `1d`（daily）→ 18 小时

缓存文件命名：`{source}__{symbol}__{period}__{interval}.pkl`，存入 `data/market_cache/` 目录。

**关键函数**：
```python
load_or_fetch_history(source, symbol, period, interval, fetcher) -> pd.DataFrame
```

---

### 4.2 `signals/vix_regime.py` — VIX Regime 分类

**数据源**：yfinance `^VIX`（EOD daily）+ `^VIX3M`（3-month VIX term structure）

**关键类**：
- `Regime`：LOW_VOL / NORMAL / HIGH_VOL（枚举）
- `Trend`：RISING / FALLING / FLAT（5日 VIX 均值变化 > 5%）
- `VixSnapshot`：单日快照，含 `regime`, `trend`, `vix3m`, `backwardation`

**关键函数**：
```python
get_current_snapshot(df=None, current_vix=None) -> VixSnapshot
get_regime_history(df=None, period="3mo") -> pd.DataFrame
fetch_vix_history(period="3mo", interval="1d") -> pd.DataFrame   # 列名: "vix"
fetch_vix3m_history(period="3mo", interval="1d") -> pd.DataFrame # 列名: "vix3m"
```

**分类阈值**：
- LOW_VOL：VIX < 15
- NORMAL：15 ≤ VIX < 22
- HIGH_VOL：VIX ≥ 22（含 EXTREME_VOL 子集，VIX ≥ 35 由 selector 处理）

---

### 4.3 `signals/iv_rank.py` — IV 信号

**数据源**：使用 VIX 作为 IV 代理（与 vix_regime.py 共享同一 VIX 历史）

**关键类**：
- `IVSignal`：HIGH / NEUTRAL / LOW
- `IVSnapshot`：含 `iv_rank`, `iv_percentile`, `iv_signal`

**计算逻辑**：
- IVR = (current VIX − 52w min) / (52w max − 52w min) × 100
- IVP = 过去 252 天中 VIX 低于今日的百分比

**关键函数**：
```python
compute_iv_rank(series: pd.Series) -> float      # IVR 0-100
compute_iv_percentile(series: pd.Series) -> float  # IVP 0-100
get_current_iv_snapshot(df=None) -> IVSnapshot
```

**有效 IV 信号规则**（selector 中执行）：
- IVR vs IVP 偏差 ≤ 15pt → 使用 IVR 分类
- 偏差 > 15pt → 改用 IVP 分类（避免 VIX spike 扭曲 IVR）
- 阈值：HIGH = IVP > 70，LOW = IVP < 40

---

### 4.4 `signals/trend.py` — SPX 趋势信号

**数据源**：yfinance `^GSPC`（SPX）EOD daily

**关键类**：
- `TrendSignal`：BULLISH / NEUTRAL / BEARISH
- `TrendSnapshot`：含 `spx`, `ma20`, `ma50`, `ma_gap_pct`, `signal`, `above_200`

**分类逻辑**：
- BULLISH：SPX > MA50 × 1.01（gap > +1%）
- BEARISH：SPX < MA50 × 0.99（gap < −1%）
- NEUTRAL：±1% 范围内
- 额外追踪：SPX > MA200（macro warning，但不影响 selector 决策，仅展示）

**关键函数**：
```python
get_current_trend(df=None, current_spx=None) -> TrendSnapshot
fetch_spx_history(period="1y", interval="1d") -> pd.DataFrame  # 列名: "close"
```

---

### 4.5 `signals/intraday.py` — 盘中监控信号

**用途**：盘中 VIX spike 告警 + SPX 止损触发；Telegram bot 可调用（非主推荐流程）

**阈值**：
- VIX 盘中涨幅 ≥ 8% from open → WARNING
- VIX 盘中涨幅 ≥ 15% from open → ALERT
- SPX 盘中跌幅 ≥ 1% from open → CAUTION
- SPX 盘中跌幅 ≥ 2% from open → TRIGGER

**关键函数**：
```python
get_vix_spike(interval="5m") -> VixSpikeAlert
get_spx_stop(interval="5m") -> IntradayStopTrigger
```

---

### 4.6 `strategy/catalog.py` — 策略描述符注册表

**核心数据结构**：

```python
@dataclass(frozen=True)
class StrategyDescriptor:
    key: str            # 稳定 key（snake_case）
    name: str           # StrategyName.value
    emoji: str
    direction: str      # "bull" / "bear" / "neut" / "wait"
    underlying: str     # "SPX" / "SPY" / "—"
    trade_type: str
    dte_text: str
    delta_text: str
    when_text: str
    risk_text: str
    detail_roll_text: str
    max_risk_text: str
    target_return_text: str
    roll_rule_text: str
    short_gamma: bool = False   # SPEC-017 新增
    short_vega:  bool = False   # SPEC-017 新增
    delta_sign:  str  = "neut"  # SPEC-017 新增 ("bull"/"bear"/"neut")
    manual_entry_allowed: bool = True
```

**注册的 7 个策略**：
- `bull_call_diagonal`：short_gamma=False
- `bull_put_spread`：short_gamma=True, delta="bull"
- `bull_put_spread_hv`：short_gamma=True, delta="bull"
- `bear_call_spread_hv`：short_gamma=True, delta="bear"
- `iron_condor`：short_gamma=True, delta="neut"
- `iron_condor_hv`：short_gamma=True, delta="neut"
- `reduce_wait`：short_gamma=False，manual_entry_allowed=False

**决策矩阵**（`CANONICAL_MATRIX`）：regime × IV × trend → strategy_key

**关键函数**：
```python
strategy_descriptor(strategy: Any) -> StrategyDescriptor
strategy_key(strategy: Any) -> str     # 返回稳定 snake_case key
strategy_catalog_payload() -> dict     # Web API 序列化（含 Greek 字段）
matrix_payload() -> dict               # 3D 矩阵序列化
```

---

### 4.7 `strategy/selector.py` — 推荐引擎

**核心数据结构**：

```python
@dataclass
class StrategyParams:
    extreme_vix:              float = 35.0
    high_vol_delta:           float = 0.20
    high_vol_dte:             int   = 35
    high_vol_size:            float = 0.50
    normal_delta:             float = 0.30
    normal_dte:               int   = 30
    profit_target:            float = 0.50
    stop_mult:                float = 2.0
    min_hold_days:            int   = 10
    bp_target_low_vol:        float = 0.05
    bp_target_normal:         float = 0.05
    bp_target_high_vol:       float = 0.035
    bp_ceiling_low_vol:       float = 0.25
    bp_ceiling_normal:        float = 0.35
    bp_ceiling_high_vol:      float = 0.50
    max_short_gamma_positions: int  = 3      # SPEC-017
    spell_age_cap:            int   = 30     # SPEC-015
    max_trades_per_spell:     int   = 2      # SPEC-015
```

**关键函数**：
```python
select_strategy(vix, iv, trend, params=DEFAULT_PARAMS) -> Recommendation
get_recommendation() -> Recommendation  # 拉取实时数据后调用 select_strategy
```

**`StrategyName` 枚举**（所有有效值）：
- `Bull Put Spread`
- `Bull Put Spread (High Vol)`
- `Bear Call Spread (High Vol)`
- `Bull Call Diagonal`
- `Bear Call Diagonal`（catalog 中无对应条目，仅枚举保留）
- `Iron Condor`
- `Iron Condor (High Vol)`
- `Bull Call Spread`
- `Bear Call Spread`
- `Bear Put Spread`
- `Reduce / Wait`

**`Recommendation` 对象**包含：strategy, underlying, legs, max_risk, target_return, size_rule, roll_rule, rationale, position_action, vix_snapshot, iv_snapshot, trend_snapshot, macro_warning, backwardation, guardrail_label

**`select_strategy()` 决策逻辑（简化）**：
1. EXTREME_VOL（VIX ≥ extreme_vix）→ 直接 REDUCE_WAIT
2. HIGH_VOL BEARISH + VIX RISING → REDUCE_WAIT
3. HIGH_VOL + backwardation (BPS/IC) → REDUCE_WAIT
4. NORMAL + IV_LOW（任何 trend）→ REDUCE_WAIT
5. 其余路径：查 CANONICAL_MATRIX，追加 guardrail 检查

---

### 4.8 `strategy/state.py` — 持仓状态追踪

**状态文件**：`logs/current_position.json`（原子写入，flock 锁）

**Schema**：
```json
{
  "strategy_key": "bull_put_spread",
  "strategy": "Bull Put Spread",
  "underlying": "SPX",
  "opened_at": "2025-01-15",
  "status": "open",
  "roll_count": 0,
  "rolled_at": null,
  "notes": [],
  "closed_at": null,
  "close_note": null
}
```

**position_action 枚举**：
- `OPEN`：无持仓，新开仓
- `HOLD`：持仓策略与推荐一致，保持
- `CLOSE_AND_OPEN`：持仓策略不同，先平再开
- `WAIT`：REDUCE_WAIT 信号，无新仓
- `CLOSE_AND_WAIT`：有持仓但信号为等待，平仓

---

### 4.9 `backtest/pricer.py` — Black-Scholes 定价器

**功能**：SPX 期权定价（European，无股息）。

**关键函数**：
```python
call_price(S, K, T_days, sigma) -> float   # 看涨期权价格（index points）
put_price(S, K, T_days, sigma) -> float    # 看跌期权价格
call_delta(S, K, T_days, sigma) -> float   # Delta [0, 1]
put_delta(S, K, T_days, sigma) -> float    # Delta [-1, 0]
find_strike_for_delta(S, T_days, sigma, target_delta, is_call) -> float  # 二分法找 strike
```

**注意**：以 index points 为单位。P&L 需 × 100（SPX 合约乘数）。

---

### 4.10 `backtest/engine.py` — 主回测引擎

**精度等级**：Precision B（Black-Scholes 定价，无 bid-ask，无滑点）

**关键常量（模块级）**：
```python
SYNTHETIC_IC_PAIRS = {
    ("bull_put_spread_hv", "bear_call_spread_hv"),
    ("bear_call_spread_hv", "bull_put_spread_hv"),
}
SHORT_GAMMA_KEYS = {
    "bull_put_spread", "bull_put_spread_hv", "bear_call_spread_hv",
    "iron_condor", "iron_condor_hv",
}
HIGH_VOL_STRATEGY_KEYS = {
    "bull_put_spread_hv", "bear_call_spread_hv", "iron_condor_hv",
}
```

**`Trade` dataclass**（已完成交易记录）：
```
strategy, underlying, entry_date, exit_date, entry_spx, exit_spx, entry_vix,
entry_credit, exit_pnl, exit_reason, dte_at_entry, dte_at_exit,
spread_width, option_premium, bp_per_contract, contracts, total_bp, bp_pct_account
```
衍生属性：`pnl_pct`, `hold_days`, `rom_annualized`

**`Position` dataclass**（进行中的持仓）：
```
strategy, underlying, entry_date, entry_spx, entry_vix, entry_sigma,
legs (list of tuples), entry_value, days_held, size_mult, short_strike,
spread_width, bp_per_contract, bp_target
```
腿格式：`(action: int, is_call: bool, strike: float, dte_at_entry: int, qty: int)`
- action +1 = long，-1 = short

**`run_backtest()` 主循环流程**：

```
每日迭代：
1. 加载 EOD VIX / SPX / VIX3M 数据（lookback 400 天，确保 rolling 窗口）
2. 可选 1h bar 覆盖当日 VIX/SPX 点位（rolling 窗口仍用 EOD）
3. 计算信号：
   - regime = _classify_regime(vix)
   - _update_hv_spell_state() → 更新 hv_spell_start, hv_spell_trade_count
   - IVR/IVP（252日窗口）
   - iv_eff = HIGH if IVP>70, LOW if IVP<40, else NEUTRAL
   - MA50 gap → trend
   - VIX 5日趋势
4. 组装 VixSnapshot / IVSnapshot / TrendSnapshot
5. select_strategy() → rec
6. 记录 signal_history（含 strategy_key, hv_spell_age）
7. 管理开仓位（days_held++，检查出场条件）：
   - 50pct_profit（hold ≥ min_hold_days）
   - stop_loss（信用：2×credit；借方：50% debit）
   - roll_21dte（short DTE ≤ 21）
   - roll_up（BPS 系列，SPX 涨 ≥3%，DTE > 14，IVP ≥ 30）
   - trend_flip（Diagonal，hold ≥ 3天，trend → BEARISH）
8. 开新仓（守护链全部通过）：
   - rec.strategy != REDUCE_WAIT
   - not _already_open（同 StrategyName 去重）
   - not _block_synthetic_ic()
   - not _block_short_gamma_limit()
   - not _block_hv_spell_entry()
   - _used_bp + _new_bp_target ≤ _ceiling
   → 成功开仓后：若 HIGH_VOL 策略，hv_spell_trade_count += 1
9. 回测结束：所有未平仓位以 end_of_backtest 强平
```

**返回值**：`(trades: list[Trade], metrics: dict, signal_history: list[dict])`

**Helper 函数**（模块级，可单独导入测试）：
```python
_block_synthetic_ic(existing_keys: set[str], new_key: str | None) -> bool
_block_short_gamma_limit(existing_keys, new_key, max_positions) -> bool
_update_hv_spell_state(regime, vix, date, hv_spell_start, hv_spell_trade_count, extreme_vix) -> tuple
_block_hv_spell_entry(regime, vix, new_key, hv_spell_start, hv_spell_trade_count, params, date) -> bool
compute_metrics(trades: list[Trade]) -> dict
```

**`compute_metrics()` 返回字段**：
```
total_trades, win_rate, avg_win, avg_loss, expectancy, total_pnl, max_drawdown,
sharpe, calmar, cvar5, cvar10, skew, kurt,
by_strategy: {key: {n, win_rate, avg_pnl, avg_rom, median_rom}}
```

Sharpe 计算：`(mean_pnl / std_pnl) × sqrt(252 / avg_hold_days)`（trade-level Sharpe，非日收益）

---

### 4.11 `notify/telegram_bot.py` — Telegram Bot

**命令列表**：
- `/today`：立即获取并发送今日推荐
- `/entered`：记录已开仓（写入 state file）
- `/closed`：平仓
- `/backtest`：运行 1 年快速回测并发送摘要
- `/status`：当前信号 + 持仓状态
- `/help`：命令列表

**自动推送**：每个美国交易日 09:35 ET（APScheduler CronTrigger），跳过周末和美国联邦假日。

**Backtest 摘要包含**（SPEC-018 扩展后）：
- Sharpe, WR, Total PnL, MaxDD
- **Calmar** ratio
- **CVaR 5%**
- **Skew**

**依赖**：
- `python-telegram-bot ≥20`（异步架构，全 async/await）
- `APScheduler ≥3.10`（`AsyncIOScheduler`）
- APScheduler 在 `post_init` hook 内启动（避免事件循环冲突）

**消息格式**：HTML（非 MarkdownV2），使用 `<code>` / `<b>` 标签。

---

### 4.12 `web/server.py` — Flask Dashboard

**启动**：`python main.py --web [--port=5050]`，默认 `http://localhost:5050`

**主要 API 端点**（推测 / 从代码结构）：
- 推荐矩阵展示（catalog payload）
- 实时信号显示
- 回测结果（带 5 分钟内存缓存 + 磁盘持久化缓存）

**回测缓存**：
- 内存：`_backtest_cache`，TTL=300 秒
- 磁盘：`data/backtest_stats_cache.json`，按 `StrategyParams` hash 失效

---

## 5. 数据流向

```
yfinance (^VIX, ^VIX3M, ^GSPC)
    ↓ load_or_fetch_history() [TTL 缓存]
    ↓
signals/vix_regime.py  →  VixSnapshot (regime, trend, backwardation)
signals/iv_rank.py     →  IVSnapshot  (IVR, IVP, iv_signal)
signals/trend.py       →  TrendSnapshot (MA50 gap, signal)
    ↓
strategy/selector.py  select_strategy()
    ↓
Recommendation (strategy, legs, rationale, position_action, ...)
    ↓
┌──────────────────┬──────────────────┬──────────────────┐
│ Telegram bot     │ Web dashboard    │ Backtest engine  │
│ /today 推送      │ 实时展示         │ walk-forward     │
│ /entered 记录    │ 回测结果         │ 历史验证         │
└──────────────────┴──────────────────┴──────────────────┘
```

---

## 6. 测试覆盖

```
tests/
├── test_specs_017_015.py    # 5 tests — SPEC-015/017（全通过）
│   ├── test_strategy_catalog_payload_includes_greek_fields
│   ├── test_synthetic_ic_pair_is_blocked
│   ├── test_short_gamma_limit_blocks_only_short_gamma_entries
│   ├── test_hv_spell_state_tracks_and_resets
│   └── test_hv_spell_entry_block_and_noop_config
├── test_spec_018_metrics.py  # 3 tests — SPEC-018
│   ├── extended fields exist in compute_metrics
│   ├── empty list safe (no exception)
│   └── bot summary mentions new fields
├── test_state_and_api.py     # 持仓状态 CRUD + API
└── test_strategy_unification.py  # 策略枚举 / catalog 一致性
```

**运行方式**：`python3 -m unittest discover tests`（python-telegram-bot 需已安装）

---

## 7. SPEC 执行状态

### 已完成（DONE）

| SPEC | 主题 | 修改文件 |
|------|------|---------|
| SPEC-010 | VIX 期限结构（backwardation）过滤 | selector.py, vix_regime.py |
| SPEC-011 | Bear Call Spread HV（HIGH_VOL BEARISH）| selector.py, catalog.py |
| SPEC-012 | ROM 指标 | engine.py（Trade.rom_annualized）|
| SPEC-013 | BP 利用率仓位定量 | selector.py（StrategyParams），engine.py |
| SPEC-014 | 多仓并行引擎（positions list）| engine.py（run_backtest 重构）|
| SPEC-015 | Vol spell throttle（sticky spell 限流）| selector.py, engine.py |
| SPEC-017 | Greek-aware dedup（Synthetic IC block）| catalog.py, selector.py, engine.py |
| SPEC-018 | Extended metrics（Calmar/CVaR/Skew）| engine.py, telegram_bot.py |

### 研究 SPEC（DRAFT — 无 Codex 实现）

| SPEC | 主题 | 结论摘要 |
|------|------|---------|
| SPEC-016 | Realism haircut | BPS haircut 30%，Diagonal 6%，HV 信用策略 70–74% |
| SPEC-019 | 趋势信号效果分析 | EXIT trigger > ENTRY gate；MA50 滞后 1.2 天可忽略 |
| SPEC-020 | P&L 归因 | 86% 来自 Theta；趋势是 risk reducer 非 return driver |
| SPEC-021 | Filter 复杂度协议 | Filter 叠加无改善；Protocol 1-4 已建立 |
| SPEC-022 | Sharpe 鲁棒性 | 3yr CI 宽度 1.56；Diagonal 最稳；BPS 退化最严重 |
| SPEC-023 | 压力测试 | VIX 25→50 是最大实际风险；50% haircut 后 Sharpe ~0.99 |

---

## 8. 已知限制与技术债

### Precision B 系统性偏差（SPEC-016 量化）

| 偏差 | 影响 |
|------|------|
| IV Bias（VIX/SPX 负相关）| short-vol 策略高估 10–12%；Diagonal 低估 10% |
| Bid-Ask Slippage | 每腿 $40–75（未建模）|
| 资金占用成本（5% p.a.）| 短持影响小，Diagonal 影响较大 |

**综合 realism haircut：51.1%**（加权平均）→ 调整后 Sharpe ~0.99

### 已知近似

- Trade-level Sharpe（非日收益 Sharpe），多仓并行下 equity curve 非连续
- Spell 假重置：VIX 在 HIGH/NORMAL 边界单日跳入跳出可能误重置 spell state（概率低，已接受）
- VIX = daily EOD，非期权隐含 IV（无 VIX 期货曲线）
- 无美式期权早行权建模
- 无 pin risk / gap risk 建模

### Live 模式限制

- Telegram bot 不跨日保持 spell state（每次启动重新计算）
- 盘中信号仅用于告警，不修改 EOD 推荐逻辑
- VVIX 数据源未接入（yfinance 无稳定历史）

---

## 9. 开发协作协议

### 三角角色分工（`CLAUDE.md`）

| 角色 | 职责 |
|------|------|
| PM（用户）| 最终决策者，唯一能将 Spec Status 改为 APPROVED/REJECTED |
| Claude（Quant Researcher）| 策略设计、信号分析、编写 Spec、review 实施 |
| Codex（Developer）| 仅执行 APPROVED 状态的 Spec，不修改 Spec |

### Spec 流程

- 位置：`task/SPEC-{三位数编号}.md`
- 状态：DRAFT → APPROVED → 实施 → DONE（Claude review 后）
- Handoff 报告：`task/SPEC-{id}_handoff.md`（Codex 实施完成后提交）
- Claude review：读 handoff + 源码 + 跑测试 → 写入 Spec `## Review` 字段 → 改 Status

### Fast Path 规则

单文件，改动 ≤ 15 行，不新增函数或类，仅改 selector 路由/参数常量，不碰 engine.py/signals/ → Claude 直接修改，无需 Codex。
