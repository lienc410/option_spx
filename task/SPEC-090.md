# SPEC-090: Q041 Daily Dual-Source Alignment Check

Status: DONE

## Design Source

This is an **engineering-driven Spec**.

Design substance 来源：
- **PM**：要求每日核对双源数据契合度，选 Option C（log + 日报 + 阈值告警）
- **Planner**：基于既有 Q041 overlap 协议（M1-M10）收口为工程 Spec

## 目标

在 Schwab（16:30 ET）和 Massive REST（16:35 ET）两个每日采集任务完成后，自动运行三项核心对齐检查，结果写入日志，发送 Telegram 日报，低于阈值时额外发告警。

## 背景

Q041 overlap 验证协议已定义 M1-M10 指标（`doc/q041_overlap_validation_protocol_2026-05-03.md`）。日常运营只需监控三项核心：

| 指标 | 含义 | 告警阈值 |
|---|---|---|
| **M1** | Traded key match %（两源可比合约覆盖率） | < 95% |
| **M4** | Same-day price deviation（Schwab last vs Massive day_close） | > 5% 合约偏差 > 2% |
| **M6** | Near-money IV completeness（Schwab iv 字段有效率） | < 95% |

## 功能项（Features）

### F1 — `research/q041/daily_alignment_check.py`

- 读取当日 Schwab chain 和 Massive REST snapshot（路径同现有采集脚本）
- 计算 M1 / M4 / M6 三项指标
- 仅交易日运行（内置 trading-day check，跳过周末 / 主要 US 假日）

### F2 — JSONL 日志

- 每日一条 JSON record → `data/q041_overlap_daily.jsonl`
- 字段：`date`、`m1_match_pct`、`m4_deviation_pct`（偏差 > 2% 的合约占比）、`m6_iv_completeness_pct`、`alert_fired`、`notes`

### F3 — Telegram 日报（每交易日 ~17:00 ET）

- 固定格式一条消息，例：
  ```
  📊 Q041 数据对齐日报 2026-05-09
  M1 key match:    98.3% ✅
  M4 price dev:     1.8% ✅  (<2% 占 98.2%)
  M6 IV complete:  100.0% ✅
  ```
- 数据不可用时（采集未完成 / 文件缺失）发「Q041 数据对齐：今日无数据」，不发空报

### F4 — 阈值告警（独立消息）

- 触发条件：M1 < 95% **OR** M4 > 5% 合约偏差超 2% **OR** M6 < 95%
- 告警消息单独发送，在日报之后
- 每项指标退化时注明具体数值和阈值
- 同一日内同一指标不重复告警

### F5 — launchd job（old Air，17:00 ET）

- 新建 `com.spxstrat.q041align` launchd plist
- 在 Schwab（16:30）和 Massive（16:35）采集之后运行，留 25 分钟缓冲
- 失败时 exit code 非 0，launchd 标准日志记录，不影响其他服务

## 验收标准（Acceptance Criteria）

- **AC1** — 脚本在有完整双源数据的交易日正确计算 M1 / M4 / M6，结果合理
- **AC2** — 结果写入 `data/q041_overlap_daily.jsonl`，字段格式正确，可逐行解析
- **AC3** — Telegram 日报在每个交易日发出，格式与示例一致
- **AC4** — M1 < 95% 或 M4 > 5% 合约偏差 > 2% 或 M6 < 95% 时发告警消息
- **AC5** — 双源数据任一缺失时 fail-soft（发「无数据」通知，不崩溃，不发空报）
- **AC6** — 周末 / US 假日不运行（脚本内 trading-day guard，launchd 层不依赖此）
- **AC7** — launchd job `com.spxstrat.q041align` 在 old Air 注册并在 17:00 ET 触发
- **AC8** — 回归：不影响现有三个 Q041 采集 job 和 Telegram bot 其他告警路径

## Out of Scope

- M2-M3 / M5 / M7-M10 指标（覆盖率和分布检查，属于人工周度 review）
- 历史补跑（只检查当日数据）
- 自动修复数据问题

## 依赖

- 现有 Schwab chain launchd job（`com.spxstrat.q041schwab`，16:30 ET）
- 现有 Massive REST launchd job（`com.spxstrat.q041massive`，16:35 ET）
- Telegram bot 已配置（`notify/telegram_bot.py`）
- `doc/q041_overlap_validation_protocol_2026-05-03.md`（M1-M10 定义）

## 参考文件（Developer 需读）

```
doc/q041_overlap_validation_protocol_2026-05-03.md  ← M1/M4/M6 定义
research/q041/collect_chains.py                     ← Schwab 采集输出格式
research/q041/collect_massive.py                    ← Massive REST 输出格式
notify/telegram_bot.py                              ← 现有 Telegram 发送接口
data/q041_overlap_daily.jsonl                       ← 新建（首次运行时创建）
```

## Review

- Implemented `research/q041/daily_alignment_check.py` as a read-only 17:00 ET monitor over the existing Schwab chain and Massive snapshot parquet outputs. The script computes:
  - `M1` on the Schwab `volume > 0` traded subset
  - `M4` on matched liquid contracts (`|delta| 0.10–0.50`, Massive `day_close > 1.0`, Schwab `last > 0`)
  - `M6` as Schwab near-money IV validity (`|delta| 0.25–0.75`, `iv > 0`)
- Added `tests/test_spec_090.py` covering:
  - metric computation
  - JSONL append format
  - Telegram daily report formatting
  - threshold alert firing + same-day dedupe
  - missing-data fail-soft
  - non-trading-day skip
- Validation:
  - `arch -arm64 venv/bin/python -m py_compile research/q041/daily_alignment_check.py tests/test_spec_090.py`
  - `arch -arm64 venv/bin/python -m unittest tests.test_spec_090 -v`
  - `arch -arm64 venv/bin/python -m unittest tests.test_q041_massive_snapshot -v`
  - `arch -arm64 venv/bin/python -m unittest tests.test_telegram_bot -v`
  - `arch -arm64 venv/bin/python -m research.q041.daily_alignment_check --date 2026-05-04 --skip-telegram --force`
- old Air runtime / launchd verification:
  - pulled `origin/main` containing commit `bc75a38`
  - registered `~/Library/LaunchAgents/com.spxstrat.q041align.plist`
  - loaded job `com.spxstrat.q041align`
  - manual `launchctl kickstart` succeeded, `runs = 1`, `last exit code = 0`
  - current Saturday trigger correctly logged `status=skipped` via trading-day guard
  - existing jobs `com.spxstrat.q041_collect`, `com.spxstrat.q041_massive_snapshot`, and `com.spxstrat.q041_massive_historical` remained loaded and unaffected
