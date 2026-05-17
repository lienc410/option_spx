# STRATEGY_STATE

> **权威参数参考。每次改动策略参数或逻辑，必须同步更新本文件。**
> Last Updated: 2026-05-17

---

## 1. SPX Bull Put Spread — 主策略（Production）

**文件**: `strategy/selector.py`, `strategy/es_params.py`

### 1.1 Regime 定义

| Regime | VIX 范围 |
|--------|---------|
| LOW_VOL | VIX < 22 |
| NORMAL | 22 ≤ VIX < 35 (approximate; regime-decay rules apply) |
| HIGH_VOL | VIX ≥ 22（严格：低于 extreme_vix） |
| EXTREME_VOL | VIX ≥ 35 → Reduce/Wait |

`extreme_vix = 35.0`（`StrategyParams` 字段，可配置）

### 1.2 核心参数

```python
profit_target     = 0.60   # 平仓：已捕获 60% max credit（SPEC-077）
stop_mult         = 2.0    # 止损：mark ≥ 2× 入场 credit

bp_target_low_vol  = 0.15  # 15% NLV（SPEC-084）
bp_target_normal   = 0.15
bp_target_high_vol = 0.14

bp_ceiling_low_vol  = 0.25
bp_ceiling_normal   = 0.35
bp_ceiling_high_vol = 0.50
```

### 1.3 仓位规模

- **Full size** (4.5% NLV risk): 信号一致 + VIX 平/下行
- **Half size** (2.25% NLV risk): VIX 上行 OR 信号不一致 OR HIGH_VOL

### 1.4 IVP Gate（仅作用于 NORMAL + IV NEUTRAL + BULLISH 场景）

```python
BPS_NNB_IVP_UPPER = 55   # IVP ≥ 55 → block（stressed vol，tail risk）
BPS_NNB_IVP_LOWER = 43   # IVP < 43 → block（premium 不足）
```

来源：Q063/Q067/Q068/Q069 实证确认；jitter 存在但任何修复方案更差。

---

## 2. Aftermath Overlay — V3-A（Production，gate-bypass 模式）

**文件**: `strategy/selector.py` — `is_aftermath()`, V3-A broken-wing IC HV

### 2.1 触发条件

```python
AFTERMATH_PEAK_VIX_10D_MIN = 28.0   # trailing 10d peak VIX 需 ≥ 28
AFTERMATH_OFF_PEAK_PCT     = 0.10   # 当前 VIX ≤ peak × (1 - 0.10)
# 上界硬约束：current VIX < 40（EXTREME_VOL 不触发 aftermath）
```

`is_aftermath()` = `vix_peak_10d ≥ 28` AND `vix ≤ peak × 0.90` AND `vix < 40`

### 2.2 行为

- 触发时：替换 HIGH_VOL 常规 BPS，改推 V3-A（broken-wing Iron Condor HV）
- 角色：**gate-bypass**，不是结构性 alpha（Q064 结论）；峰值 28 维持（Q070 实证）

---

## 3. ES High-Vol Sell Put Ladder（Direct Recommendation）

**文件**: `research/strategies/ES_puts/backtest.py`, `notify/telegram_bot.py`
**SPEC**: SPEC-101（2026-05-14 DONE）

### 3.1 入场条件

```python
V2F_VIX_MIN_ENTRY = 22.0     # VIX gate（G6）
# 同时需要：trend = BULLISH（get_current_trend()）
# warmed + cadence_ok + n_active < V2F_MAX_SLOTS
```

### 3.2 参数

```python
V2F_ENTRY_DTE          = 49      # 入场 DTE
V2F_EXIT_DTE           = 21      # 出场 DTE
V2F_MAX_SLOTS          = 5       # 最大并发仓位
V2F_ENTRY_FREQ         = 5       # 常规：每 ≥5 天可入场一次
V2F_CLUSTER_THRESHOLD  = 4       # M1：N_active ≥ 4 时切换高频
V2F_CLUSTER_ENTRY_FREQ = 10      # M1 cluster 模式频率
V2F_STOP_MULT          = 15.0    # fail-safe 止损（历史 G6 样本从未触发）
V2F_PROFIT_TARGET      = 0.10    # 平仓：mark ≤ 10% 入场 premium
_ES_HV_TARGET_DELTA    = 0.20    # 目标 delta（bot 层）
```

### 3.3 信号推送模式

- **直接推荐**（不再是 paper-only）
- Telegram 推送：`📡 /ES HV Ladder — Entry Signal`
- PM 自行决定是否执行或作为纸盘
- 信号记录到 `data/q071_hv_paper_trades.jsonl`（status="signal"）
- VIX stale guard：数据缺失时不触发，推 warning

### 3.4 历史 backtest 表现（G6, 26yr）

| 指标 | V2f baseline | HV Ladder |
|---|---|---|
| Ann ROE (acct.) | +1.04% | +1.14% |
| Sharpe | 0.15 | 0.34 |
| MaxDD | -33.3% | -9.7% |
| Bootstrap sig | 0% | 100% |
| Active days | 86% | 21% |

---

## 4. Q042 Dual-Sleeve Drawdown Overlay（Paper Trading）

**文件**: `signals/q042_trigger.py`, `backtest/q042_engine.py`, `strategy/q042_pricing.py`
**SPEC**: SPEC-094（Sleeve B）+ SPEC-094.1（Sleeve A 参数修订）

### 4.1 Sleeve A — dd4 Lenient

```
触发：ddATH ≤ -4%（第一次穿越）
策略：ATM / +2.5% OTM call spread（SPEC-094.1）
DTE：30（SPEC-094.1；原 90）
No-overlap：30 trading days（原 90）
```

### 4.2 Sleeve B — dd15 + MA10 Reclaim

```
Outer：ddATH ≤ -15% → 进入 watching 模式
Inner：watching 期间 close > MA10（30 TD watch window）→ 触发
策略：ATM / +5% OTM call spread
DTE：90
No-overlap：90 trading days
Watch window：30 trading days
```

### 4.3 状态

- 双 sleeve 同时 paper trading on old Air（自 2026-05-10）
- Quant 监控时间线：2026-08-10 3mo / 2026-11-10 6mo（含 bootstrap）/ 2027-05-10 12mo

---

## 5. Sleeve Governance Caps（Production Daemon）

**文件**: `strategy/sleeve_governance.py`, `scripts/sleeve_governance_daemon.py`
**SPEC**: SPEC-103（2026-05-15 DONE + DEPLOYED）

### 5.1 硬上限（R1–R4）

```python
CAP_SPX_PM    = 70.0  # R1: SPX PM pool ≤ 70% NLV
                       # 依据：Schwab PM call 80% − 10pp safety
CAP_ES_SPAN   = 80.0  # R2: /ES SPAN pool ≤ 80% NLV
CAP_COMBINED  = 60.0  # R3: 全策略合并 ≤ 60% NLV
CAP_SHORT_VOL = 50.0  # R4: 所有 short-vol 仓位合并 ≤ 50% NLV
```

**Cap 注意事项**：
- R3/R4 caps：production 口径下 bind 可能比 backtest 更频繁，运行 1 个月后审实际数据
- PM equity baseline > 25% 时需重审 R1 物理依据

### 5.2 动态规则

**R5 — Stress Episode**（`stress_episode_from_flags()`）：
- 触发：VIX ≥ 22 OR ddATH ≥ 4% OR DD/Aftermath sleeve fires
- 效果：SPX PM cap 从 70% → 60%（`CAP_STRESS_EPISODE = 60.0`）

**R6 — Second-Leg Block**（`detect_second_leg_state()`）：
- 触发：ddATH ≤ -8% AND VIX ≥ 25
- 效果：硬禁止新增 short-vol 仓位

---

## 6. 明确不在生产中的

| 项目 | 状态 | 说明 |
|---|---|---|
| IVP gate（Q072 增量判别） | Optional post-SPEC | Q071 2nd Quant 标 OPTIONAL |
| Q072 P4B /ES rerun | 待 HV Ladder final config lock | 不阻塞 SPEC-103 |
| Q072 P4C.7 合成 stress test | 待 HV Ladder final config lock | 2008/2022 path inject |
| Q042 live execution | 纸盘积累期 | PM 决定 promote 时机 |
| HV Ladder 写入生产 bot | 独立 SPEC 决策 | 需 paper 积累后评估 |
| Q019 Signal 2 生产切换 | 6mo A/B 期（至 2026-11-09） | SPEC-091 |

---

## 7. 参数修改义务

> 任何对以上策略参数或逻辑的改动，**必须同步更新本文件对应章节**。
> 索引层（Planner/PM）负责维护；改动提交时本文件应与代码一同 commit。
