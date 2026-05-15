# SPEC-101: ES High-Vol Sell Put Ladder — VIX ≥ 22 Entry Gate

**Status**: DONE  
**Date**: 2026-05-14  
**Source**: Q071 P0–P5 research + 2nd Quant review PROMOTE  
**Promote level**: Paper/shadow/small-cell — NOT immediate full production

---

## 0. 一句话目标

在 /ES V2f 滚动 ladder 的 `should_enter` 中加入 `vix >= 22` gate，形成 **ES High-Vol Sell Put Ladder** 策略变体。仅在 HIGH_VOL regime 下入场，历史上将 MaxDD 从 -33.3% 压至 -9.7%，同时将 bootstrap sig_rate 从 0% 提升至 100%。

**重要**：本 SPEC 不改动生产 bot（SPEC-061）。所有改动在 backtest 研究层 + dashboard 展示层 + paper-trade 告警层。

---

## 1. 背景

### 1.1 研究来源

Q071 P0–P5（`research/q071/q071_memo_2026-05-14.md`）：
- P1 attribution 显示 VIX ≥ 22 bucket 在 V2f 语境下有显著 edge（vs VIX < 22 的负 PnL bucket）
- G6（VIX ≥ 22）是 8 个 gate candidates 中唯一同时满足 P0 Criterion B 的变体
- IVP 43-55 被实证驳斥（ann_roe 1.04% → 0.07%，-0.98pp），不纳入本 SPEC

### 1.2 V2f_base 的隐患

**V2f_base 本身 bootstrap sig_rate = 0%**（block=250，20 seeds）。生产 baseline 是脆弱边缘，不是统计确立的优势。本 SPEC 的 G6 gate 不是"增强"显著性，而是**创造**显著性。

### 1.3 G6 vs V2f_base 性能对比（26yr BS-flat）

| 指标 | V2f_base | ES HV Ladder (G6) |
|---|---|---|
| Ann ROE geometric | +1.04% | +1.14% (+0.09pp) |
| Sharpe | 0.15 | 0.34 |
| MaxDD | -33.3% | **-9.7%** |
| Worst trade % NLV | -10.6% | **-4.8%** |
| Worst 3mo cluster | -27.6% | **-8.4%** |
| Bootstrap sig_rate | **0%** | **100%** |
| 2020 COVID | -23.4% | **+3.1%** |
| 2022 | -33.1% | **-8.7%** |
| Active days % | 86% | 21% |

P0 判定：Criterion B PASS（ROE flat +0.09pp，MaxDD 改善 23.6pp ≫ 2pp 门槛）；V1 PASS；bootstrap PASS；SPAN ≤ 30% NLV → PROMOTE。

---

## 2. 范围边界

| 组件 | 改动？ | 说明 |
|---|---|---|
| `research/strategies/ES_puts/backtest.py` | ✅ | 新增 `V2F_VIX_MIN_ENTRY = 22.0` + `run_phase2_hvlad()` |
| `web/server.py` | ✅ | 新增 `/api/es-backtest/hvlad` 端点 |
| `web/templates/es_backtest.html` | ✅ | 新增 HV Ladder tab，展示 G6 vs V2f_base 对比 |
| `notify/telegram_bot.py` | ✅ | 新增 paper-trade 告警：VIX ≥ 22 + V2f 入场条件满足时推送 |
| `strategy/es_params.py` | ❌ | 不改 |
| `production/` | ❌ | 不改（SPEC-061 live bot 不变）|
| `data/q071_hv_paper_trades.jsonl` | ✅ | 新建 paper trade 记录文件 |

---

## 3. 策略参数

### 3.1 固定参数（继承 V2f，不改）

```python
V2F_ENTRY_DTE      = 49
V2F_EXIT_DTE       = 21
V2F_ENTRY_FREQ     = 5     # M1: N≥4 时改为 10
V2F_MAX_SLOTS      = 5
V2F_STOP_MULT      = 15.0  # 保留作 fail-safe（历史样本中未触发）
V2F_PROFIT_TARGET  = 0.10
```

### 3.2 新增参数

```python
V2F_VIX_MIN_ENTRY  = 22.0  # G6 gate：VIX < 22 时不入场
```

### 3.3 入场逻辑变更

```python
# 当前 V2f（_run_phase2_v2f_on_frame line 718）
should_enter = warmed and trend_ok and cadence_ok and n_active < V2F_MAX_SLOTS

# SPEC-101 HV Ladder
vix_ok = vix >= V2F_VIX_MIN_ENTRY          # ← 新增
should_enter = warmed and trend_ok and vix_ok and cadence_ok and n_active < V2F_MAX_SLOTS
```

---

## 4. 功能要求

### F1 — `run_phase2_hvlad()` 函数（backtest.py）

复用 `_run_phase2_v2f_on_frame()`，新增 `vix_min_entry` 参数（默认 22.0）。在 `should_enter` 前插入 `vix_ok = vix >= vix_min_entry` 条件。

函数签名：
```python
def run_phase2_hvlad(
    sim_df: pd.DataFrame,
    mode: str = "baseline",
    vix_min_entry: float = 22.0,
) -> dict:
```

### F2 — `/api/es-backtest/hvlad` 端点（server.py）

格式参照 `/api/es-backtest/v2f`，返回：

```json
{
  "phase": "es_hv_ladder",
  "hvlad_metrics": {
    "ann_roe_geometric": 0.0114,
    "sharpe": 0.34,
    "max_dd": -0.097,
    "worst_trade_pct_nlv": -0.048,
    "bootstrap_sig_rate": 1.0
  },
  "v2f_baseline": { ... },
  "hv_delta": {
    "ann_roe_pp": 0.10,
    "sharpe_delta": 0.19,
    "max_dd_improvement_pp": 23.6,
    "bootstrap_improvement": "+100pp (0%→100%)"
  },
  "caveats": [
    "BS-flat pricing; OTM put premium underestimated ~17-25% (Q057)",
    "G6 deploys only 21% of trading days — accept low capital deployment",
    "Bootstrap sig supports paper promotion, not production certainty",
    "STOP=15 unused in historical sample; retained as fail-safe"
  ]
}
```

### F3 — HV Ladder tab（es_backtest.html）

在现有 V2f tab 之后新增 "HV Ladder" tab，展示：

| 指标 | V2f baseline | ES HV Ladder | Δ |
|---|---|---|---|
| Ann ROE (acct.) | +1.04% | +1.14% | +0.09pp |
| Sharpe | 0.15 | 0.34 | +0.19 |
| MaxDD | -33.3% | -9.7% | +23.6pp |
| Worst trade % NLV | -10.6% | -4.8% | +5.8pp |
| Bootstrap sig | 0% | 100% | +100pp |
| 2020 COVID | -23.4% | +3.1% | +26.5pp |

固定 caveat banner（黄色，始终可见）：

```
ES High-Vol Sell Put Ladder — paper/shadow mode only.
Bootstrap significance supports paper promotion; live sample accumulation required.
STOP=15 retained as fail-safe (0 historical triggers in G6 sample).
Strategy active only when VIX ≥ 22 — expect low capital deployment (~21% of trading days).
```

### F4 — Paper-trade 告警（telegram_bot.py）

在 `intraday_monitor` 或 daily push 中新增检查：当 V2f 入场条件满足（warmed + trend_ok + cadence_ok + slots < 5）**且 VIX ≥ 22** 时，推送 Telegram：

```
[ES HV Ladder] Paper-trade signal
Date: {today}
VIX: {vix:.1f} (≥22 ✓)
Active slots: {n}/{max}
Entry DTE: 49
Est. strike: {strike}
Est. premium: {prem:.2f}
→ Paper-trade only. No auto-execution.
```

记录到 `data/q071_hv_paper_trades.jsonl`（fail-soft：文件不存在时创建）。

### F5 — Paper trade 记录格式（q071_hv_paper_trades.jsonl）

```json
{
  "signal_date": "2026-05-14",
  "vix_at_signal": 24.3,
  "active_slots": 2,
  "est_strike": 5200,
  "est_premium": 45.2,
  "status": "paper"
}
```

---

## 5. 风险控制（继承 V2f，新增 VIX 数据 guard）

```
Max SPAN % NLV:     ≤ 30%（primary cap；/ES futures SPAN 估算）
Secondary monitor:  broker-reported BP / stress BP（display only，not gate）
Max active slots:   5
STOP_MULT:          15（fail-safe，历史 G6 样本中未触发）
VIX data guard:     VIX 数据缺失或 stale（> 1 trading day）时禁止入场，推 Telegram warning
```

---

## 6. 验收标准

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `run_phase2_hvlad()` 默认 vix_min=22.0 | 26yr 回测 active_days ≈ 21%，n_trades ≈ 146（±10）|
| AC2 | AC2：HV Ladder ann_roe ≈ +1.14%（±0.1pp），sharpe ≈ 0.34（±0.05）| 回测数字 |
| AC3 | AC3：MaxDD ≈ -9.7%（±1pp），V1 PASS（worst trade < -15% NLV）| 回测数字 |
| AC4 | `/api/es-backtest/hvlad` 返回 hvlad_metrics + v2f_baseline + hv_delta + caveats | curl test |
| AC5 | HV Ladder tab 含对比表 + caveat banner（始终可见）| Visual on old Air |
| AC6 | Paper-trade 告警：VIX ≥ 22 + V2f 条件满足时推 Telegram + 写 JSONL | dry-run（mock VIX=24）|
| AC7 | VIX stale guard：VIX 数据缺失时不入场，推 warning | dry-run（mock stale VIX）|
| AC8 | `strategy/es_params.py` 未改；SPEC-061 生产 bot 未改 | grep + 回归 |
| AC9 | `data/q071_hv_paper_trades.jsonl` fail-soft（不存在时自动创建）| 删除文件后 dry-run |

---

## 7. Monitoring 仪表盘要求

Dashboard（/es-backtest HV Ladder tab 或独立 widget）需显示：

```
当前状态：
  VIX: {vix:.1f} → Gate {PASS ✓ / BLOCK ✗}
  Active slots: {n} / 5
  Est. SPAN %NLV: {span:.1f}%

Paper trade log：
  Total paper entries: {n}
  Last signal: {date}
```

---

## 8. 不在范围内

- IVP gate（Q072，optional post-SPEC）
- 将 G6 gate 写入生产 bot（独立 SPEC 决策点，需 paper 积累后评估）
- 修改 V2F_STOP_MULT（保持 15）
- 修改 DTE / 并发上限（保持 V2f 原值）
- VIX 数据源替换

---

## 9. Review Obligation

**PM 主导的 paper-trade 观察期，时机由 PM 判断**。没有时间锁定。

**建议参考触发条件（非强制）**：
- 任意一次 live VIX ≥ 22 触发 paper signal 后，PM 评估 entry 时机 / fill quality
- PM 认为 paper sample 足够时，通知 Quant 启动 re-run

**Quant re-run 内容**（PM 触发时执行）：
- Paper entry VIX 分布 vs historical G6（是否一致）
- Paper PnL vs backtest prediction（方向对齐？）
- 用 live + 扩展数据重跑 Q071 P5 bootstrap
- 若 live WR < 50% 或 worst paper trade < -10% NLV → 临时 Quant review

**Promote 决策**：是否将 G6 gate 写入生产 bot 由 PM 决定，需独立 SPEC。

---

## 10. 参考文件

```
research/q071/q071_memo_2026-05-14.md         ← 完整研究（P0-P5）
task/q071_2nd_quant_review_2026-05-14.md      ← 2nd Quant review（§7 建议起点）
research/strategies/ES_puts/backtest.py       ← _run_phase2_v2f_on_frame() 修改点
task/SPEC-095.md                              ← V2f 基础 SPEC
task/SPEC-097.md                              ← M1 cluster throttle 参考
RESEARCH_LOG.md R-20260514-01                 ← Q071 研究记录
```

---

## 11. Implementation Review — 2026-05-14

**Result**: PASS / DONE

- AC1–AC3 PASS: `run_phase2_hvlad(start=2000-01-01, end=2026-04-17)` returns 146 trades, active days 21.4%, ann ROE 1.14%, Sharpe 0.34, MaxDD -9.68%, worst trade -4.77% NLV, bootstrap sig_rate 100%.
- AC4 PASS: `/api/es-backtest/hvlad` returns `hvlad_metrics`, `v2f_baseline`, `hv_delta`, `caveats`, and paper state.
- AC5 PASS: `/es-backtest` has a separate `HV Ladder` tab with visible paper/shadow caveat banner.
- AC6 PASS: paper alert helper writes `data/q071_hv_paper_trades.jsonl` schema in dry-run/mock test.
- AC7 PASS: stale/missing VIX guard suppresses paper entry and returns warning.
- AC8 PASS: `strategy/es_params.py` and production `/ES` SPEC-061 bot logic were not modified.
- AC9 PASS: paper JSONL path is created fail-soft when absent.

Known validation note: `tests.test_telegram_bot` currently has broker-state/environment-dependent failures in legacy intraday tests caused by live Schwab mismatch/profit checks consuming mocked position payloads. SPEC-101-specific tests and SPEC-095 regression pass.
