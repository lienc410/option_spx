# SPEC-091: Dual-Signal Daily Recommendation — Opening Signal + Settled-VIX Signal

Status: DONE

## Design Source

This is a **research-driven Spec**.

Design substance 来源：
- **Quant Researcher**：Q019 Tier 1–2.7 五层测试；stable rule recovery 60-70%；参数最终锁定见 `task/q019_path_e_pre_spec_2026-05-09.md`
- **PM**：双信号设计——保留 09:30 开盘推荐（Signal 1），新增 stable-VIX 第二推荐（Signal 2）；09:30 的 intraday VIX 用于 Signal 1，stable-VIX 用于 Signal 2
- **Planner**：将 Quant pre-SPEC memo 收口为 DRAFT Spec

## 锁定参数

| 参数 | 值 | 说明 |
|---|---|---|
| `SETTLING_INTERVAL` | `"1h"` | Yahoo Finance bar 粒度 |
| `SETTLING_THRESHOLD` | `0.5` | `\|VIX_h − VIX_{h-1}\| < 0.5` 判为 stable |
| `SETTLING_TIMEOUT_MIN` | `180` | 09:30 ET 起算，最晚 12:30 ET 触发 |
| `SETTLING_DATA_SOURCE` | `"yfinance:^VIX"` | Yahoo Finance VIX intraday |

## 一句话目标

保留现有 09:30 开盘推荐（Signal 1，行为完全不变），并在 VIX 早盘稳定后（最迟 12:30 ET）追加一次 stable-VIX 第二推荐（Signal 2）；两信号不同时发 Telegram 差异提醒，相同时发确认消息。

## 双信号设计

| 信号 | 时间 | VIX 口径 | 触发逻辑 |
|---|---|---|---|
| **Signal 1（零改动）** | 09:30 ET market open | 当前 intraday VIX | 现有行为完全不变 |
| **Signal 2（新增）** | stable 触发后立即；最晚 12:30 ET | 稳定后 VIX（或 timeout 时 VIX）| stable rule 每小时轮询，180 分钟 timeout |

## 功能项（Features）

### F1 — 保留 Signal 1（零改动）

现有 09:30 ET 开盘推荐逻辑、Telegram 推送、Web UI 展示**完全不变**。不触碰任何现有代码路径。

### F2 — `production/vix_settling.py`：Stable rule 核心实现

- **数据源**：`yfinance:^VIX`，`interval="1h"`，延迟约 15 分钟
- **轮询**：09:30 ET 开始，每整点检查（09:30、10:30、11:30、12:30 ET）
- **Stable 判断**：`|VIX_h − VIX_{h-1}| < 0.5`，满足即触发
- **Timeout**：180 分钟后（12:30 ET）未 stable → 用当前 VIX 直接决策，标注 timeout
- **Fallback 语义**：timeout 后行为恢复"使用当前 intraday VIX 决策"（即当前 live 行为），不跳过当日，不影响 Signal 1
- **配置**：`SETTLING_INTERVAL`、`SETTLING_THRESHOLD`、`SETTLING_TIMEOUT_MIN` 通过 config 可覆盖，便于 paper-trading 期调参
- **对外接口**：`get_stable_vix() -> (vix_value: float, status: Literal["stable", "timeout"], elapsed_min: int)`

### F3 — Signal 2 生成与比较

- 用 `get_stable_vix()` 返回值重跑 `select_strategy()`，生成 Signal 2
- 与 Signal 1 比较：
  - **不同** → 发 Telegram 差异提醒 + 更新 Web UI
  - **相同** → 发 Telegram 确认消息 + 更新 Web UI

### F4 — Telegram 推送

Signal 2 与 Signal 1 **不同**时：
```
🔄 VIX 稳定信号更新（耗时 47 分钟）
开盘时 VIX 24.3 → 推荐: BPS
稳定后 VIX 21.8 → 推荐: IC（已变化）
```

Signal 2 与 Signal 1 **相同**时：
```
✅ VIX 稳定确认（耗时 47 分钟）
VIX 稳定于 22.1，开盘推荐 BPS 维持不变
```

**Timeout** 情形额外标注：`「早盘 VIX 未稳定，按 12:30 当前值 24.3 决策」`

**不受影响**：intraday alerts（SPEC-086 credit stop monitor 等）仍 real-time，完全独立。

### F5 — Web UI：双信号展示（§3.5 落地）

- **等待期**（09:30 → stable 前）：Signal 1 正常显示；Signal 2 区域显示 `「VIX stabilising... current 24.3 / prev 25.1 / Δ=−0.8（threshold 0.5）」`
- **stable 触发后**：双栏展示，Signal 2 标注 `稳定于 VIX 22.1，耗时 47 分钟`
- **timeout 触发后**：双栏展示，Signal 2 标注 `timeout（12:30 ET，VIX 24.3）`

### F6 — 日志

每日写入 `data/q019_settling_log.jsonl`：
`date`、`vix_signal1`、`rec_signal1`、`vix_signal2`、`rec_signal2`、`settling_status`（`stable` / `timeout`）、`elapsed_min`、`changed`

### F7 — launchd job（old Air，09:30 ET 启动）

- 新建 `com.spxstrat.signal_settling` launchd plist
- 09:30 ET 启动，内部每小时轮询至 stable 或 12:30 ET
- 仅交易日运行（内置 trading-day guard）
- 失败时 exit code 非 0，launchd 标准日志，不影响其他服务

## 决策路径范围（§3.4）

| 路径 | 走 stable rule？ |
|---|---|
| 每日 strategy recommendation（Signal 2）| ✅ 是 |
| Intraday alerts（SPEC-086 credit stop 等）| ❌ 否，保持 real-time |
| pnl_ratio / mark-multiple stop trigger | ❌ 否 |
| EXTREME_VOL alert | ❌ 否 |

## 设计边界

**不变的**：Signal 1 路径、backtest engine VIX 口径（仍 close-based）、intraday alerts、VIX 阈值参数（HIGH_VOL=22 / LOW_VOL=15）、`vix_window` / 5d MA 计算

**不在范围内**：改 backtest VIX 口径、改 intraday alert VIX 口径、调整任何 VIX 阈值参数、Signal 2 触发任何自动仓位 action、切换数据源到 Schwab / Polygon

## 风险注记（§5，Review 须显式回应）

- **R1**：Tier 2.6 真实 hourly 数据仅 2024-2026（2 年），worst years 用 OHLC 代理估计，存在 model risk
- **R2**：Yahoo VIX 延迟约 15 分钟；stable 判断可能稍滞后于真实稳定时刻。可接受（研究用同源数据验证）
- **R3**：Signal 2 不同于 Signal 1 约 9.48% 交易日（≈ 24 次/年）；所有交易日都会发确认或差异消息（约 240 次/年），PM 需接受 Telegram 频率
- **R4**：极端日 timeout 后 Signal 2 恢复当前 live 行为，Path E 收益不体现，但无额外损失
- **R5**：预期收益 ~$2k/年，工程量需保持比例

## Paper-Trading 验证期 + 上线 Gate（§3.6）

**验证期**：1-2 个月并行运行，记录 `data/q019_settling_log.jsonl`，与假装是当前 live 的 baseline 对比。

**上线 Gate（4 条全部满足）**：
1. Paper trading ≥ 30 个交易日
2. ≥ 80% 的日子在 120 分钟内触发 stable（timeout 率 ≤ 20%）
3. 无"stable 后立刻又 unstable"震荡案例
4. 2nd Quant review APPROVE

**上线后 Quant 追踪**：第 1/3/6 个月由 Quant 跑 live-vs-backtest 实测，回填 `QUANT_RESEARCHER.md` Q019 governance 章节 recovery rate。如 timeout 率超 20% 或 recovery 偏离 67% ±15pp，Quant 评估是否调整 θ 或 timeout。

## 验收标准（Acceptance Criteria）

- **AC1** — Signal 1 路径行为与当前完全一致（回归必须通过）
- **AC2** — `vix_settling.py`：hourly 轮询正确；`|ΔVIX| < 0.5` 时立即触发；180 分钟后 timeout
- **AC3** — Signal 2 与 Signal 1 不同时，Telegram 差异提醒格式正确
- **AC4** — Signal 2 与 Signal 1 相同时，Telegram 确认消息发出
- **AC5** — Timeout 时 Telegram 标注 `timeout（12:30 ET）`
- **AC6** — Web UI 正确展示双信号 + settling 实时状态（等待 / 稳定 / timeout）
- **AC7** — 每日 `data/q019_settling_log.jsonl` 正确写入，字段完整
- **AC8** — 非交易日不触发（trading-day guard）
- **AC9** — launchd job `com.spxstrat.signal_settling` 在 old Air 注册，09:30 ET 启动验证
- **AC10** — 回归：现有 Telegram bot、intraday alerts、`/api/recommendation`（Signal 1）不受影响

## 参考文件（Developer 需读）

```
task/q019_path_e_pre_spec_2026-05-09.md         ← Quant pre-SPEC 完整 memo（含研究依据 + 6 设计点）
research/q019/tier2_6_hourly_live_simulation.py  ← stable rule 参考实现
web/server.py                                    ← Signal 1 现有 endpoint + Signal 2 展示
notify/telegram_bot.py                           ← 差异 / 确认推送
task/SPEC-090.md                                 ← launchd job 注册结构参考
```

## Review

- Implemented a fully sidecar-style Signal 2 path in `production/vix_settling.py`.
  - Signal 1 path remains untouched:
    - no changes to `notify/telegram_bot.py` scheduling or push logic
    - no changes to `/api/recommendation` shape or behavior
  - Signal 2 is independent:
    - reads hourly Yahoo `^VIX`
    - applies fixed `1h / 0.5 / 180m` settled-VIX rule
    - writes read-only state artifact for web
    - appends one daily paper-trading JSONL row
    - sends one Telegram confirmation/diff message when finalized
- Added read-only web surface:
  - `/api/recommendation/settling`
  - homepage panel in `web/templates/portfolio_home.html`
- Validation:
  - `arch -arm64 venv/bin/python -m py_compile production/vix_settling.py web/server.py tests/test_spec_091.py`
  - `arch -arm64 venv/bin/python -m unittest tests.test_spec_091 -v`
  - `arch -arm64 venv/bin/python -m unittest tests.test_telegram_bot -v`
  - `arch -arm64 venv/bin/python -m production.vix_settling --skip-telegram --verbose`
- old Air runtime / launchd verification:
  - pulled `origin/main` containing commit `fec65c1`
  - ran `pip install -e .`
  - restarted `com.spxstrat.web`
  - verified `/api/recommendation/settling` route and homepage panel are live
  - registered `~/Library/LaunchAgents/com.spxstrat.signal_settling.plist`
  - loaded job `com.spxstrat.signal_settling`
  - manual `launchctl kickstart` succeeded with `runs = 1`, `last exit code = 0`
  - current non-trading-day run correctly produced `status=skipped`
- Acceptance summary:
  - `AC1` PASS — Signal 1 untouched; `/api/recommendation` shape unchanged
  - `AC2` PASS — stable/timeout logic unit-tested
  - `AC3` PASS — diff message formatter verified
  - `AC4` PASS — same-signal confirmation formatter verified
  - `AC5` PASS — timeout message explicitly labels `12:30 ET`
  - `AC6` PASS — read-only web UI surface implemented and served
  - `AC7` PASS — `data/q019_settling_log.jsonl` append path implemented and tested
  - `AC8` PASS — non-trading-day guard implemented and tested
  - `AC9` PASS — old Air launchd job registered and kickstarted
  - `AC10` PASS — telegram bot / intraday alert regression test passed unchanged
