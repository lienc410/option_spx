# SPX Options Strategy — System Implementation Status
**Date: 2026-04-05（更新版，含 SPEC-030~038）| 完整系统实现文档，供全新 Claude agent 重建系统理解**

*承接 `system_status_2026-03-30.md`。主要变更（初版）：SPEC-020/024-029 全部实施完成，新增 9 个模块文件，engine.py 深度集成 portfolio tracking / shock gate / overlay，StrategyParams 新增 19 个字段。*
*追加变更（SPEC-030~038）：真实交易录入链路全链路上线（trade log / correction / void / Schwab API / performance 页面 / paper trade filter）；Dashboard 前端大幅升级（Decision Strip / Risk Flag Bar / Backtest on-demand）。*

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
│   ├── current_position.json      # 持仓状态（strategy/state.py 管理）
│   └── trade_log.jsonl            # 永久交易日志（append-only，SPEC-034）★ 新
├── data/
│   ├── market_cache/              # yfinance 缓存目录（.pkl 文件）
│   ├── market_cache.py            # 缓存策略管理
│   └── backtest_stats_cache.json  # Web dashboard 回测结果持久化缓存
├── signals/
│   ├── vix_regime.py              # VIX regime 分类 + 5日趋势 + backwardation
│   ├── iv_rank.py                 # IV Rank + IV Percentile 计算
│   ├── trend.py                   # SPX MA50 趋势信号（ATR 标准化，SPEC-020）
│   ├── overlay.py                 # VIX Acceleration Overlay 状态机（SPEC-026）
│   └── intraday.py                # 盘中 VIX spike / SPX stop 信号
├── strategy/
│   ├── catalog.py                 # StrategyDescriptor + CANONICAL_MATRIX + Greek metadata
│   ├── selector.py                # StrategyParams（25 字段）+ StrategyName + select_strategy()
│   └── state.py                   # 持仓状态 CRUD（含 trade_id/strikes/premium/paper_trade 扩展字段）
├── backtest/
│   ├── engine.py                  # 主回测引擎（集成 portfolio/shock/overlay）
│   ├── pricer.py                  # Black-Scholes pricer
│   ├── experiment.py              # 参数实验框架
│   ├── registry.py                # Experiment ID + config hash（SPEC-024）
│   ├── portfolio.py               # DailyPortfolioRow + PortfolioTracker（SPEC-024）
│   ├── metrics_portfolio.py       # compute_portfolio_metrics()（SPEC-024）
│   ├── shock_engine.py            # 8-scenario shock risk engine（SPEC-025）
│   ├── attribution.py             # Strategy + regime attribution（SPEC-028）
│   ├── run_shock_analysis.py      # Phase A/B shock 分析（SPEC-027）
│   ├── run_oos_validation.py      # IS/OOS 验证 5 张报表（SPEC-029）
│   ├── run_trend_ablation.py      # 4-way ATR/Persistence ablation（SPEC-020）
│   └── prototype/                 # 各 SPEC 研究原型脚本（只读，不影响生产）
├── performance/
│   ├── __init__.py
│   └── live.py                    # compute_live_performance()（SPEC-037/038）★ 新
├── schwab/
│   ├── __init__.py
│   ├── auth.py                    # OAuth2 token 管理 + 自动续期（SPEC-035）★ 新
│   ├── client.py                  # Schwab API 封装（positions/balances/snapshot）★ 新
│   └── setup.py                   # 一次性授权引导（python -m schwab.setup）★ 新
├── notify/
│   └── telegram_bot.py            # Telegram bot + APScheduler 定时推送
├── web/
│   ├── server.py                  # Flask dashboard（含所有 API endpoints）
│   └── templates/
│       ├── index.html             # Dashboard（持仓面板/Decision Strip/Risk Flag Bar/交易modals）
│       ├── matrix.html            # 策略矩阵（avg_pnl/win_rate/当前格高亮）
│       ├── backtest.html          # 回测页面（on-demand，signals 独立加载，SPEC-033）
│       ├── margin.html            # 保证金估算 + Schwab live BP（SPEC-035）
│       └── performance.html       # 真实交易绩效页面（SPEC-037/038）★ 新
├── tests/
│   ├── test_specs_017_015.py      # SPEC-017/015 单元测试（5 tests）
│   ├── test_spec_018_metrics.py   # SPEC-018 metrics 单元测试（3 tests）
│   ├── test_spec_batch_024_029_020.py  # SPEC-024~029+020 批量单元测试（27 tests）
│   ├── test_state_and_api.py      # 持仓状态 + API + correction/void 测试
│   ├── test_strategy_unification.py   # 策略枚举 / catalog 一致性
│   └── test_live_performance.py   # live performance 聚合与 API 测试（SPEC-037/038）★ 新
├── doc/
│   ├── SYSTEM_DESIGN.md           # 原始系统设计文档（参考）
│   ├── research_notes.md          # 研究笔记（§1–§41）
│   ├── strategy_status_2026-04-05.md  # 当前版策略设计状态
│   └── system_status_2026-04-05.md    # 当前版系统实现状态（本文件）
└── task/
    ├── strategy_spec.md           # 历史归档（SPEC-001~003，旧格式）
    ├── SPEC-010.md ~ SPEC-038.md  # 当前 SPEC 文件（均为 DONE）
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

---

## 4. 核心模块详解

### 4.1–4.3 数据层（`data/market_cache.py`，`signals/vix_regime.py`，`signals/iv_rank.py`）

与 system_status_2026-03-30.md §4.1–4.3 完全一致，无变更。

---

### 4.4 `signals/trend.py` — SPX 趋势信号（SPEC-020 ATR 版本）

**关键类**：
- `TrendSignal`：BULLISH / NEUTRAL / BEARISH
- `TrendSnapshot`：含 `spx`, `ma20`, `ma50`, `ma_gap_pct`, `signal`, `above_200`, `atr14: Optional[float]`, `gap_sigma: Optional[float]`（SPEC-020 新增）

**新增常量**：
```python
ATR_PERIOD = 14
ATR_THRESHOLD = 1.0
```

**新增函数**：
```python
_compute_atr14_close(close_series: pd.Series) -> pd.Series
    # close.diff().abs().rolling(14).mean()（True Range 近似）

_classify_trend_atr(gap_sigma: float) -> TrendSignal
    # gap_sigma >= ATR_THRESHOLD → BULLISH
    # gap_sigma <= -ATR_THRESHOLD → BEARISH
    # else → NEUTRAL
```

**分类逻辑（`use_atr=True` 时，引擎默认）**：
```python
gap_sigma = (SPX - MA50) / atr14
```

**`get_current_trend(use_atr=False)`** — `use_atr` 默认 False（向后兼容 live 路径）；engine 内通过 `params.use_atr_trend` 控制。

---

### 4.5 `signals/overlay.py` — VIX Acceleration Overlay（SPEC-026）★ 新文件

**关键类**：

```python
class OverlayLevel(IntEnum):
    L0_NORMAL    = 0
    L1_FREEZE    = 1
    L2_TRIM      = 2
    L3_HEDGE     = 3
    L4_EMERGENCY = 4

@dataclass
class OverlayResult:
    level: OverlayLevel
    vix_accel_3d: float
    book_core_shock: float   # ≤ 0，每日独立计算（Step 0）
    vix: float
    bp_headroom: float
    block_new_entries: bool  # level >= L1
    force_trim: bool         # level >= L2
    force_emergency: bool    # level == L4
    trigger_reason: str
```

**主函数**：
```python
def compute_overlay_signals(
    *, vix, vix_3d_ago, book_core_shock, bp_headroom, params
) -> OverlayResult
```

- `overlay_mode="disabled"` 恒返回 L0（向后兼容）
- L4 → L3 → L2 → L1 → L0 优先级降序判断
- L1/L4 OR 逻辑；L2/L3 AND 逻辑

---

### 4.6–4.7 策略层（`strategy/catalog.py`，`strategy/selector.py`）

`catalog.py` 无变更。

**`strategy/selector.py` — `StrategyParams` 当前完整状态（25 字段）**：

```python
@dataclass
class StrategyParams:
    # 基础参数（9个，同 2026-03-30）
    extreme_vix:              float = 35.0
    high_vol_delta:           float = 0.20
    high_vol_dte:             int   = 35
    high_vol_size:            float = 0.50
    normal_delta:             float = 0.30
    normal_dte:               int   = 30
    profit_target:            float = 0.50
    stop_mult:                float = 2.0
    min_hold_days:            int   = 10

    # BP 利用率（SPEC-024 2× 放大）
    bp_target_low_vol:        float = 0.10   # 从 0.05 放大
    bp_target_normal:         float = 0.10   # 从 0.05 放大
    bp_target_high_vol:       float = 0.07   # 从 0.035 放大
    bp_ceiling_low_vol:       float = 0.25
    bp_ceiling_normal:        float = 0.35
    bp_ceiling_high_vol:      float = 0.50

    # Portfolio Greek（SPEC-017）
    max_short_gamma_positions: int  = 3

    # Spell throttle（SPEC-015）
    spell_age_cap:            int   = 30
    max_trades_per_spell:     int   = 2

    # Daily portfolio（SPEC-024）
    initial_equity:           float = 100_000.0

    # Shock engine（SPEC-025）
    shock_mode:               str   = "shadow"
    shock_budget_core_normal: float = 0.0125
    shock_budget_core_hv:     float = 0.0100
    shock_budget_incremental: float = 0.0040
    shock_budget_incremental_hv: float = 0.0030
    shock_budget_bp_headroom: float = 0.15

    # Overlay（SPEC-026）
    overlay_mode:             str   = "disabled"
    overlay_freeze_accel:     float = 0.15
    overlay_freeze_vix:       float = 30.0
    overlay_trim_accel:       float = 0.25
    overlay_trim_shock:       float = 0.01
    overlay_hedge_accel:      float = 0.35
    overlay_hedge_shock:      float = 0.015
    overlay_emergency_vix:    float = 40.0
    overlay_emergency_shock:  float = 0.025
    overlay_emergency_bp:     float = 0.10

    # ATR trend（SPEC-020）
    use_atr_trend:            bool  = True   # RS-020-2 Fast Path
    bearish_persistence_days: int   = 1      # Persistence 已拒绝，保持单日翻转
```

---

### 4.8 `strategy/state.py` — 持仓状态追踪

无变更。见 system_status_2026-03-30.md §4.8。

---

### 4.9 `backtest/pricer.py` — Black-Scholes 定价器

无变更。见 system_status_2026-03-30.md §4.9。

---

### 4.10 `backtest/engine.py` — 主回测引擎（重度集成）

**精度等级**：Precision B（Black-Scholes 定价，无 bid-ask，无滑点）

**`BacktestResult` dataclass**（替代原始元组返回）：
```python
@dataclass
class BacktestResult:
    trades: list[Trade]
    metrics: dict
    signals: list[dict]
    portfolio_rows: list[DailyPortfolioRow] = field(default_factory=list)
    shock_reports: list[ShockReport] = field(default_factory=list)
    experiment_id: str = ""
    config_hash: str = ""
    portfolio_metrics: PortfolioMetrics | None = None

    def __iter__(self):
        # 向后兼容：解包为 (trades, metrics, signals)
        return iter((self.trades, self.metrics, self.signals))
```

**`run_backtest()` 主循环流程（更新后）**：

```
每日迭代：
Step 0  【每日独立，不依赖入场路径】
  - 读取 vix_3d_ago（前3日 VIX，头3天用当日代替 → accel=0）
  - 若有开仓位：run_shock_check(candidate_position=None) → _daily_book_shock
  - compute_overlay_signals(...) → overlay
  - 若 params.use_atr_trend：计算 atr14 + gap_sigma

Step pre-entry  【overlay 处置】
  - if overlay.force_trim: 强制平所有仓位，exit_reason = "overlay_emergency"（L4）或 "overlay_trim"（L2/L3）

Steps 1–6  【原有守护链 + 新增 overlay check】
  1. rec.strategy != REDUCE_WAIT
  2. not overlay.block_new_entries（L1+ → skip entry）
  3–6. 原有 dedup / synthetic_ic / sg_limit / spell_block 检查

Step 7  【Shock Gate，SPEC-025】
  - run_shock_check(existing + candidate, ...)
  - shock_mode="active": post_max_core > budget → 拒绝

Step 8  【BP ceiling】
  - _used_bp + _new_bp_target ≤ _ceiling

每日结束：
  - tracker.update_day(realized_pnl, open_marks, bp_used, ...) → DailyPortfolioRow
  - 维护 bearish_streak（Persistence filter 预留，当前 persistence_days=1 即单日触发）
```

**`run_backtest()` 签名变更**：
```python
def run_backtest(
    params=None,
    start_date=None,
    end_date=None,
    account_size=150_000,
    collect_shock_reports=False,   # 新增：控制是否收集 ShockReport
) -> BacktestResult
```

---

### 4.11 `backtest/registry.py`（SPEC-024）★ 新文件

```python
def generate_experiment_id(timestamp: datetime | None = None) -> str
    # 格式：EXP-YYYYMMDD-HHMMSS-XXXX（XXXX 为 4 位随机大写字母+数字）
    # 长度：24 字符

def config_hash(params: StrategyParams) -> str
    # sha256(sorted JSON of dataclass fields)[:12]
    # 12 字符 hex；相同参数哈希相同
```

---

### 4.12 `backtest/portfolio.py`（SPEC-024）★ 新文件

**`DailyPortfolioRow` 17 字段 dataclass**：

| 字段 | 说明 |
|---|---|
| date | 日期 |
| start_equity | 日初净值 |
| end_equity | 日末净值 |
| daily_return_gross | 毛收益率 |
| daily_return_net | 净收益率 |
| realized_pnl | 当日已实现 PnL |
| unrealized_pnl_delta | unrealized PnL 日变化 |
| total_pnl | realized + unrealized_delta |
| bp_used | 当日使用 BP（USD）|
| bp_headroom | BP 剩余（USD；SPEC 描述为 NAV 比例，存储为 USD，不影响下游）|
| short_gamma_count | short-gamma 仓位数 |
| open_positions | 开仓数量 |
| regime | 当日 VIX Regime |
| vix | 当日 VIX |
| cumulative_equity | 累计净值 |
| drawdown | (cumulative_equity - peak) / peak，≤ 0 |
| experiment_id | 所属实验 ID |

**`PortfolioTracker`**：
```python
class PortfolioTracker:
    _prev_marks: dict[str, float]   # position_id → 前一日 mark
    def __init__(self, initial_equity, experiment_id, account_size=None)
    def update_day(self, *, date, realized_pnl, open_position_marks,
                   bp_used, bp_ceiling_usd, short_gamma_count,
                   open_positions, regime, vix) -> DailyPortfolioRow
    def get_rows(self) -> list[DailyPortfolioRow]
    def reset(self) -> None
```

---

### 4.13 `backtest/metrics_portfolio.py`（SPEC-024）★ 新文件

```python
@dataclass
class PortfolioMetrics:
    ann_return: float
    daily_sharpe: float    # mean(ret_net) / std(ret_net) * sqrt(252)
    daily_sortino: float
    daily_calmar: float
    max_drawdown: float
    cvar_95: float         # mean(bottom 5% daily returns)
    worst_5d_drawdown: float
    positive_months_pct: float
    pnl_per_bp_day: float  # total_net_pnl / sum(daily_bp_used)；sum=0 → 0.0
    total_days: int
    experiment_id: str
    def to_dict(self) -> dict

def compute_portfolio_metrics(rows: Sequence[DailyPortfolioRow]) -> PortfolioMetrics
    # 空输入抛出 ValueError
```

---

### 4.14 `backtest/shock_engine.py`（SPEC-025）★ 新文件

**8 个标准场景**（`STANDARD_SCENARIOS`）：
```python
S1: spot_pct=-0.02, vix_shock_pt=+5,  is_core=True
S2: spot_pct=-0.03, vix_shock_pt=+8,  is_core=True
S3: spot_pct=-0.05, vix_shock_pt=+15, is_core=True
S4: spot_pct=0.00,  vix_shock_pt=+10, is_core=True
S5: spot_pct=+0.02, vix_shock_pt=-3,  is_core=False
S6: spot_pct=+0.05, vix_shock_pt=-8,  is_core=False
S7: spot_pct=+0.03, vix_shock_pt=-5,  is_core=False
S8: spot_pct=-0.02, vix_shock_pt=+5,  is_core=False  # 独立记录
```

**`ShockReport` dataclass**：
```python
date, nav, mode, pre_scenarios, pre_max_core_loss_pct,
post_scenarios, post_max_core_loss_pct,
incremental_shock_pct, budget_core, budget_incremental,
approved, reject_reason, sigma_used
```

**主函数**：
```python
def run_shock_check(
    positions, current_spx, current_vix, date, params,
    candidate_position=None,   # None → 仅计算现有 book（Step 0 用途）
    account_size=100_000,
    is_high_vol=False,
) -> ShockReport
```

---

### 4.15 `backtest/attribution.py`（SPEC-028）★ 新文件

```python
def compute_strategy_attribution(trades: list[Trade]) -> list[dict]
    # 11 列，按 net_pnl 降序；含 pnl_per_bp_day

def compute_regime_attribution(rows: list[DailyPortfolioRow], account_size) -> list[dict]
    # 8 列，按 pnl 降序；按 VIX regime 分组

def print_strategy_attribution(attr_list) -> None
def print_regime_attribution(attr_list) -> None
```

**`pnl_per_bp_day`**：`total_net_pnl / sum(daily_used_bp)`，衡量每占用 $1 保证金 1 天的净收益。

---

### 4.16 `backtest/run_shock_analysis.py`（SPEC-027）★ 新文件

```python
def compute_hit_rates(shock_records: list[dict]) -> dict
    # 使用预算列直接比较（不依赖 approved 字段，shadow mode 下 approved 恒 True）
    # any_core_breach = abs(post_max_core_loss_pct) > budget_max_core

def run_phase_a_analysis(start_date, end_date) -> None
    # 运行 EXP-baseline（shadow），输出 hit rate 年度分布 + breach type 分布 + percentiles
```

---

### 4.17 `backtest/run_oos_validation.py`（SPEC-029）★ 新文件

```python
def _split(result, cutoff="2020-01-01") -> tuple[list, list]
    # date < cutoff → IS；date >= cutoff → OOS
    # IS + OOS 行数之和 = Full 行数（无重叠、无遗漏）

def _run_config(config_name, params, start_date, end_date) -> BacktestResult

def run_oos_validation(
    start_date="2000-01-01", end_date="2026-03-31", cutoff="2020-01-01"
) -> None
    # 运行 EXP-baseline（overlay disabled）+ EXP-full（overlay active）
    # 打印 R1–R5 五张报表
```

**关键设计**：单次全历史回测 + 日期过滤（避免两次独立回测的 cold-start artifact）。

---

### 4.18 `backtest/run_trend_ablation.py`（SPEC-020）★ 新文件

4-way ablation：
- `EXP-baseline`：use_atr=False, persist=1
- `EXP-atr`：use_atr=True, persist=1
- `EXP-persist`：use_atr=False, persist=3
- `EXP-full`：use_atr=True, persist=3

输出：Full Sharpe / MaxDD / OOS Sharpe / OOS MaxDD / Full Trades 对比表。

---

### 4.19 `notify/telegram_bot.py`

无变更。见 system_status_2026-03-30.md §4.11。

---

### 4.20 `strategy/state.py` — 扩展字段（SPEC-034/038）★ 更新

`write_state()` 通过 `**extra_fields` 接受并持久化以下字段（开仓时写入）：

```python
trade_id, short_strike, long_strike, expiry, dte_at_entry,
contracts, actual_premium, model_premium,
entry_spx, entry_vix, regime, iv_signal, trend_signal,
paper_trade  # SPEC-038 新增
```

新增函数：
```python
def update_open_position(**fields) -> None
    # Patch 当前 open position，不重置 opened_at / status 等身份字段
```

---

### 4.21 `logs/trade_log_io.py`（SPEC-034/036/038）★ 新文件

```python
TRADE_LOG_FILE = Path("logs/trade_log.jsonl")

def append_event(event: dict) -> None          # append-only 写入
def load_log() -> list[dict]                   # 原始行（供审计）
def load_log_by_id(trade_id: str) -> list[dict]
def resolve_log() -> list[dict]                # 合并 correction，标记 voided/paper_trade
def next_trade_id(strategy_key: str) -> str    # 格式：{YYYY-MM-DD}_{abbrev}_{seq:03d}
def strategy_abbrev(strategy_key: str) -> str
```

**`resolve_log()` 返回结构（每条 trade）：**
```python
{
  "id":          str,
  "voided":      bool,
  "paper_trade": bool,   # 取自 open.paper_trade，默认 False
  "open":        dict | None,
  "close":       dict | None,
  "rolls":       list[dict],
  "notes":       list[dict],
  "corrections": list[dict],   # 原始 correction 行，供审计
}
```

**事件类型：**
- `open`：开仓，含 strikes / premium / regime / signals
- `close`：平仓，含 exit_premium / actual_pnl
- `roll`：换仓，含 new_expiry / new_strikes / roll_credit
- `note`：备注
- `correction`：patch 式修正（fields 字段为 patch dict），不修改原始行
- `void`：作废整笔交易

---

### 4.22 `schwab/auth.py`（SPEC-035）★ 新文件

OAuth2 Authorization Code Flow 封装：
- Token 文件：`~/.spxstrat/schwab_token.json`（项目外，不 commit）
- Access token 有效期 30 分钟，refresh token 7 天
- `ensure_access_token()`：剩余 < 5 分钟自动 refresh，不中断服务
- `token_status()` → `{"configured", "authenticated", "token_expires_in", "refresh_expires_in", "stale"}`
- `interactive_setup()`：引导 OAuth2 授权流程（python -m schwab.setup）

---

### 4.23 `schwab/client.py`（SPEC-035）★ 新文件

```python
def get_account_positions() -> dict      # 持仓列表 + Greeks
def get_account_balances() -> dict       # BP / net_liquidation / margin
def live_position_snapshot(state: dict | None) -> dict
    # 匹配 expiry+short_strike → 返回 mark/bid/ask/Greeks/unrealized_pnl/trade_log_pnl
    # trade_log_pnl = (actual_premium - mark) × contracts × 100
    # 未配置时返回 {"visible": False}
```

缓存：市场开盘（09:30–16:00 ET）60 秒；收盘后 300 秒。

---

### 4.24 `performance/live.py`（SPEC-037/038）★ 新文件

```python
def compute_live_performance(
    resolved_trades: list[dict],
    schwab_snapshot: dict | None = None,
    include_paper: bool = False,
) -> dict
```

**输出结构：**
```python
{
  "summary": {closed_trades, open_trades, win_rate, total_realized_pnl,
               avg_win, avg_loss, expectancy, best_trade, worst_trade},
  "by_strategy": {strategy_key: {n, win_rate, total_pnl, avg_pnl}},
  "monthly": [{month, realized_pnl, trades}],        # 按 close.timestamp ET 月归档
  "recent_closed": [...],                            # 最近 10 笔，按 closed_at 倒序
  "open_positions": [{id, strategy_key, paper_trade, entry_premium, mark, ...}],
  "trade_count_raw": int,
  "trade_count_effective": int,                      # 排除 voided 后
  "include_paper": bool,
  "paper_trade_count": int,
}
```

**过滤优先级（compute 内部）：**
1. 排除 `voided = true`
2. 若 `include_paper = false`，排除 `paper_trade = true`
3. 只统计有 open + close 的 resolved trades（unrealized 单独展示）

**expectancy 公式：** `(win_rate × avg_win) + ((1 − win_rate) × avg_loss)`

---

## 5. 数据流向（更新版）

```
yfinance (^VIX, ^VIX3M, ^GSPC)
    ↓ load_or_fetch_history() [TTL 缓存]
    ↓
signals/vix_regime.py  →  VixSnapshot (regime, trend, backwardation)
signals/iv_rank.py     →  IVSnapshot  (IVR, IVP, iv_signal)
signals/trend.py       →  TrendSnapshot (MA50 gap, ATR gap_sigma, signal)
    ↓
strategy/selector.py  select_strategy()
    ↓
Recommendation (strategy, legs, rationale, position_action, ...)
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ backtest/engine.py  run_backtest()                               │
│   Step 0: shock_engine.py run_shock_check(book) → book_shock    │
│   Step 0: overlay.py compute_overlay_signals() → overlay        │
│   pre-entry: overlay.force_trim → 清仓                          │
│   Steps 1–8: dedup / overlay.block / shock gate / BP ceiling    │
│   daily: portfolio.py tracker.update_day() → DailyPortfolioRow  │
│   ↓                                                              │
│ BacktestResult: trades, metrics, signals,                        │
│                 portfolio_rows, shock_reports,                   │
│                 experiment_id, config_hash, portfolio_metrics    │
└─────────────────────────────────────────────────────────────────┘
    ↓
attribution.py  → strategy/regime attribution
run_oos_validation.py → R1–R5 报表
run_shock_analysis.py → Phase A/B 分析
```

---

## 6. 测试覆盖

```
tests/
├── test_specs_017_015.py           # 5 tests — SPEC-015/017（全通过）
├── test_spec_018_metrics.py        # 3 tests — SPEC-018
├── test_spec_batch_024_029_020.py  # 27 tests — SPEC-024/025/026/027/028/029/020 ★ 新
│   ├── BacktestResult 3-tuple 向后兼容
│   ├── pnl_per_bp_day = 0.0（bp_used 全零）
│   ├── shock shadow 模式 approved=True
│   ├── shock active 模式超预算 approved=False
│   ├── overlay disabled → L0
│   ├── overlay vix=30+accel=50%+shock=1.2% → L2（force_trim）
│   ├── compute_hit_rates 使用预算列而非 approved 字段
│   ├── _split IS + OOS 无重叠无遗漏
│   ├── ATR 计算辅助函数
│   └── ... 共 27 项
├── test_state_and_api.py           # 持仓状态 CRUD + API + correction/void/paper_trade 测试
├── test_strategy_unification.py   # 策略枚举 / catalog 一致性
└── test_live_performance.py       # live performance 聚合 + paper_trade filter + API（SPEC-037/038）★ 新
```

**运行方式**：`python3 -m unittest discover tests`

---

## 7. SPEC 执行状态

### 已完成（DONE）

| SPEC | 主题 | 修改/新增文件 |
|------|------|-------------|
| SPEC-010 | VIX 期限结构（backwardation）过滤 | selector.py, vix_regime.py |
| SPEC-011 | Bear Call Spread HV（HIGH_VOL BEARISH）| selector.py, catalog.py |
| SPEC-012 | ROM 指标 | engine.py |
| SPEC-013 | BP 利用率仓位定量 | selector.py, engine.py |
| SPEC-014 | 多仓并行引擎 | engine.py |
| SPEC-015 | Vol spell throttle | selector.py, engine.py |
| SPEC-017 | Greek-aware dedup（Synthetic IC block）| catalog.py, selector.py, engine.py |
| SPEC-018 | Extended metrics（Calmar/CVaR/Skew）| engine.py, telegram_bot.py |
| SPEC-020 | ATR-Normalized Entry Gate（RS-020-2 生产）| signals/trend.py, strategy/selector.py, backtest/engine.py |
| SPEC-024 | Daily portfolio infrastructure + bp_target 2× | backtest/registry.py, portfolio.py, metrics_portfolio.py, selector.py, engine.py |
| SPEC-025 | Portfolio Shock-Risk Engine（shadow mode）| backtest/shock_engine.py, engine.py |
| SPEC-026 | VIX Acceleration Overlay（4级状态机）| signals/overlay.py, selector.py, engine.py |
| SPEC-027 | Shock Engine Phase A Bug Fix + A/B framework | backtest/run_shock_analysis.py |
| SPEC-028 | Capital Efficiency Attribution | backtest/attribution.py |
| SPEC-029 | IS/OOS Validation（2000-2019 / 2020-2026）| backtest/run_oos_validation.py |

| SPEC-030 | Intraday Stop Signal Research | 研究结论：提前触发率 0%，收盘判断足够 |
| SPEC-031 | Dashboard 前端改进（6项）| index.html, matrix.html, backtest.html, server.py |
| SPEC-032 | Decision Strip + Risk Flag Bar | index.html, selector.py（canonical_strategy / re_enable_hint）|
| SPEC-033 | Backtest On-Demand + 磁盘缓存 | backtest.html, server.py（/api/signals/history / /api/backtest/latest-cached）|
| SPEC-034 | Trade Entry UI + Trade Log | logs/trade_log_io.py, state.py, server.py, index.html |
| SPEC-035 | Schwab API Read-Only | schwab/auth.py, schwab/client.py, schwab/setup.py, server.py, index.html, margin.html |
| SPEC-036 | Trade Log Corrections & Void | logs/trade_log_io.py（resolve_log）, server.py（correction/void endpoints）, index.html |
| SPEC-037 | Live Trade Performance Tracking | performance/live.py, server.py, performance.html |
| SPEC-038 | Paper Trade Tag & Performance Filter | trade_log_io.py, state.py, server.py, performance.live, index.html, performance.html |

### 研究 SPEC（研究完成，无 Codex 实现）

| SPEC | 主题 | 结论摘要 |
|------|------|---------|
| SPEC-016 | Realism haircut | BPS 30%，Diagonal 6%，HV 70–74% |
| SPEC-019 | 趋势信号效果分析 | EXIT trigger > ENTRY gate；MA50 滞后可忽略 |
| SPEC-021 | Filter 复杂度协议 | Filter 叠加无自动改善；协议 1-4 已建立 |
| SPEC-022 | Sharpe 鲁棒性 | 3yr CI 宽度 1.56；差异 < 0.5 视为噪声 |
| SPEC-023 | 压力测试 | VIX 25→50 是最大实际风险；50% haircut 后 Sharpe ~0.99 |

---

## 8. 已知限制与技术债

### Precision B 系统性偏差

| 偏差 | 影响 |
|------|------|
| IV Bias（VIX/SPX 负相关）| short-vol 策略高估 10–12%；Diagonal 低估 10% |
| Bid-Ask Slippage | 每腿 $40–75（未建模）|
| 资金占用成本（5% p.a.）| 短持影响小，Diagonal 影响较大 |

综合 realism haircut：51.1%（加权平均）→ 调整后 Sharpe ~0.99

### 已知近似

- `DailyPortfolioRow.bp_headroom` 存储为 USD（非 NAV 比例），SPEC 描述为比例，不影响下游计算（已记录）
- True Range 近似（`close.diff().abs()`）而非真实 TR（含 prev_close）；v1 可接受
- Trade-level Sharpe 与 daily portfolio Sharpe 数值差异（~1.4 vs ~0.9）来自计量基础不同，不是 bug
- Spell 假重置：VIX 在 HIGH/NORMAL 边界单日跳入跳出可能误重置（概率低，已接受）
- VIX = daily EOD，非期权隐含 IV
- 无美式期权早行权建模
- 无 pin risk / gap risk 建模

### Overlay / Shock 未完成项

- L3 hedge（long put spread）v2 实现待独立 SPEC
- `vix_accel_1d` L4 fast-path（COVID 类极速崩溃优化）待验证
- Shock active mode 上线条件：需 Phase B A/B 验证（AC B1–B4）通过后决定
- 多仓 trim 精细化（按 shock 贡献排序）待多仓引擎扩展后处理

---

## 9. 开发协作协议

### 三角角色分工（`CLAUDE.md`）

| 角色 | 职责 |
|------|------|
| PM（用户）| 最终决策者，唯一能将 Spec Status 改为 APPROVED/REJECTED |
| Claude（Quant Researcher）| 策略设计、信号分析、编写 Spec、review 实施 |
| Codex（Developer）| 仅执行 APPROVED 状态的 Spec，不修改 Spec |

### Fast Path 规则

单文件，改动 ≤ 15 行，不新增函数或类，仅改 selector 路由/参数常量，不碰 engine.py/signals/ → Claude 直接修改，无需 Codex。

本轮 Fast Path 案例：
- SPEC-024 Fast Path：`bp_target` 默认值 2× 放大（selector.py 3 行）
- SPEC-020 Fast Path：`use_atr_trend: bool = True`（selector.py 1 行）
