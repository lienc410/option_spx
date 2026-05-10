# SPEC-097: V2f Cluster Loss Mitigation — M1 Entry Frequency Throttle

Status: DONE

## Design Source

Research-driven. Q061 Tier 1 结论（R-20260510-08）：M1（N≥4 并发位置时入场频率从每 5 TD 降至每 10 TD）在 alpha 损失 -0.11pp 下将 1987 stress cluster loss 从 -47.1% 改善至 -44.1%，Sharpe 微升。PM 选 A（as-is 进 SPEC）。M2 正式 DROP。

## 范围边界

**仅改 backtest 研究层。生产代码路径零改动。**

| 组件 | 改变？ | 说明 |
|---|---|---|
| `research/strategies/ES_puts/backtest.py` | ✅ 修改 `run_phase2_v2f()` | 加 M1 cluster throttle 逻辑 |
| `web/server.py` | ✅ 更新 `/api/es-backtest/v2f` | 返回 M1 版 metrics；原 V2f（无 M1）数字存为 `v2f_baseline` 供对比 |
| `web/templates/es_backtest.html` | ✅ V2f tab 更新 | 展示 M1 调整后 metrics + 与 baseline 对比 |
| `strategy/es_params.py` | ❌ 不改 | 生产参数不变 |
| `production/` | ❌ 不改 | SPEC-061/086/088/095 状态不变 |

## M1 参数（backtest-only）

```python
V2F_CLUSTER_THRESHOLD = 4    # 并发位置数达到此值时触发降速
V2F_CLUSTER_ENTRY_FREQ = 10  # 高并发时入场间隔（trading days）
# 正常入场间隔仍为 V2F_ENTRY_FREQ = 5
```

## 功能要求

### F1 — `run_phase2_v2f()` M1 逻辑（`backtest.py`）

在现有 `should_enter` 判断中加入 cluster throttle：

```python
n_active = len(positions)
entry_freq = (
    V2F_CLUSTER_ENTRY_FREQ if n_active >= V2F_CLUSTER_THRESHOLD
    else V2F_ENTRY_FREQ
)
should_enter = (
    warmed
    and trend_ok
    and day_counter % entry_freq == 0
    and n_active < V2F_MAX_SLOTS
)
```

`V2F_CLUSTER_THRESHOLD` 和 `V2F_CLUSTER_ENTRY_FREQ` 定义为模块级常量（与 `V2F_STOP_MULT` 同位置）。

### F2 — `/api/es-backtest/v2f` 响应更新（`server.py`）

响应中新增 `v2f_m1` 字段（M1 版结果），原 `metrics` 字段重命名为 `v2f_baseline`（无 M1）以供 UI 对比：

```json
{
  "phase": "phase2_v2f_m1",
  "v2f_baseline": {
    "ann_roe_geometric": 0.0246,
    "sharpe": 0.22,
    "worst_trade_pct_nlv": -0.0924
  },
  "v2f_m1": {
    "ann_roe_geometric": 0.0235,
    "sharpe": 0.23,
    "worst_trade_pct_nlv": -0.0924,
    "stress_worst_single_pct_nlv": -0.1513,
    "stress_cluster_pct": -0.4407
  },
  "m1_delta": {
    "ann_roe_pp": -0.11,
    "sharpe_delta": +0.01,
    "stress_improvement_pp": +3.05
  },
  "caveats": [...]
}
```

Fail-soft 规则与 SPEC-095 一致。

### F3 — V2f tab UI 更新（`es_backtest.html`）

在现有 V2f tab 的对比卡片区新增 "M1 Cluster Throttle" 对比行：

| 指标 | V2f baseline | V2f + M1 | Δ |
|---|---|---|---|
| Ann ROE (acct.) | +2.46% | +2.35% | -0.11pp |
| Sharpe | 0.22 | 0.23 | +0.01 |
| 1987 stress single | -16.85% NLV | -15.13% NLV | +1.72pp |
| 1987 stress cluster | -47.1% | -44.1% | +3.05pp |

说明文字：`"M1: entry frequency reduced to every 10 trading days when ≥4 positions active"`

已有的 tail risk warning block（SPEC-096 F5）不变，但在 warning 末尾加一行：`"M1 cluster throttle active in current backtest variant."`

### F4 — 刷新 V2f 磁盘缓存

清空 V2f 相关缓存条目（不影响 V0 / Q041 / SPX 缓存）。

## 验收标准

- **AC1** — `run_phase2_v2f()` 默认启用 M1（N≥4 时 entry_freq=10）
- **AC2** — M1 Ann ROE ≈ +2.35%（±0.1pp），Sharpe ≈ 0.23（±0.02）
- **AC3** — `/api/es-backtest/v2f` 返回 `v2f_baseline` + `v2f_m1` + `m1_delta` 三段
- **AC4** — V2f tab 展示 M1 vs baseline 对比表；tail risk warning 末尾加 M1 说明
- **AC5** — `strategy/es_params.py` 未改动；生产路径回归 PASS
- **AC6** — V2f cache 已刷新，baseline 旧数字不再出现

## 研究 Caveats（继承自 SPEC-095，新增 M1 项）

1. BS-flat 合成数据；OTM put premium 低估 ~18-25%（Q057）
2. M1 stress worst -15.13% 距 V1 veto -15% 仍差 0.13pp（合成极端事件精度范围内；PM 知情，选 A 接受）
3. M2 已 DROP（路径依赖致 stress 恶化；不在本 SPEC 范围）

## 不在范围内

- M2（已 DROP）
- 将 M1 逻辑引入生产 bot（独立 SPEC 决策点）
- 改变 STOP_MULT 或其他 V2f 参数
- Phase 3/4 dynamic leverage（Q060 已关闭）

## 参考文件

```
research/strategies/ES_puts/backtest.py       ← run_phase2_v2f() 修改点
backtest/prototype/q061_m1_m2_alpha_impact.py ← M1 研究脚本（参考）
web/server.py                                 ← /api/es-backtest/v2f 更新
web/templates/es_backtest.html                ← V2f tab UI 更新
task/SPEC-095.md                              ← V2f 基础 SPEC（参考）
RESEARCH_LOG.md R-20260510-08                 ← Q061 完整研究记录
```

## Review

**DONE 2026-05-10，commit 4586a32，deployed old Air.**

AC1 ✅ `run_phase2_v2f()` 默认 M1（N≥4 → 10 TD）  
AC2 ✅ live M1 Ann ROE +2.38%（±0.1pp，目标 +2.35%）；Sharpe 0.235  
AC3 ✅ `/api/es-backtest/v2f` 返回 `v2f_baseline` + `v2f_m1` + `m1_delta`（phase=phase2_v2f_m1）  
AC4 ✅ V2f tab 含 M1 vs baseline 对比 + "M1 cluster throttle active" 标注  
AC5 ✅ `es_params.py` 未改；生产路径回归 PASS  
AC6 ✅ V2f cache 定向 purge + 旧 shape 自动失效 guard  

live 实测：baseline Ann ROE +2.650% / M1 +2.383% / Sharpe 0.235 / stress cluster M1 -44.45%（Δ +3.12pp vs baseline -47.57%）  
已知非阻塞噪音：E-Trade alert-state JSON decode 错误（pre-existing，与本 SPEC 无关）
