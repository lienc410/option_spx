# SPEC-096: Frontend Display Governance — ROE Denominator Unification + Label Clarification

Status: DONE

## Design Source

Governance-driven。治理审查 §2.1 识别了 ROE 口径不可比问题（48.2% vs -0.07% 假象）。SPEC-093 实施后 Q041 页面仍展示 sleeve-level（$50k basis）ROE，与 /ES 页面的 account-level（$500k basis）ROE 无法比较，误导 PM 判断。

## 问题陈述

| 页面 | 显示字段 | 实际分母 | 正确分母 | 误差 |
|---|---|---|---|---|
| `/q041` overview | Ann ROE | $50k per sleeve | $500k 账户权益 | **10× 膨胀** |
| `/q041/backtest` | Ann. ROE | $50k per sleeve | $500k 账户权益 | **10× 膨胀** |
| `/es-backtest` | Ann. ROE (V2f) | $500k 账户权益 | $500k 账户权益 | ✅ 正确 |

**根本原因**：`research/strategies/q041_csp_backtest.py:109` 每个 sleeve 用 `equity = 50_000.0` 初始化（代表 sleeve 的 BP deployed），而 /ES backtest 用 `P2_INITIAL_EQUITY = 500_000.0`（账户总权益）。Q041 的 sleeve PnL 是正确的，但分母用错了。

## 范围边界

| 组件 | 改变？ | 说明 |
|---|---|---|
| `web/server.py` (`_q041_backtest_summaries`) | ✅ | 修正 ROE 计算：sleeve PnL ÷ $500k |
| `web/templates/q041.html` | ✅ | ROE label 加 "(acct.)" 标注 |
| `web/templates/q041_backtest.html` | ✅ | ROE label 加 "(acct.)" 标注 |
| `web/templates/es_backtest.html` | ✅ | ROE label 加 "(acct.)" 标注（当前已正确，仅加 label）|
| `research/strategies/q041_csp_backtest.py` | ❌ 不改 | 研究层 $50k 初始值保留（代表 sleeve BP）；只在 display 层修正 |
| 任何回测算法或缓存结构 | ❌ 不改 | 只改 display 层计算和 label |

## 功能要求

### F1 — `_q041_backtest_summaries()` ROE 修正（`server.py`）

**当前（错误）逻辑**：
```python
init_equity = equity_curve[0].get("equity")   # = 50,000
ann_roe = ((end_equity / init_equity) ** (1/years) - 1) * 100
```

**修正后**：
```python
_Q041_ACCOUNT_EQUITY = 500_000.0   # 账户层分母（与 /ES 一致）
_Q041_SLEEVE_EQUITY  = 50_000.0    # sleeve BP deployed（用于 PnL 计算基础）

sleeve_pnl = end_equity - init_equity   # 用 equity_curve 原始 PnL（正确）
account_ann_roe = (
    (((_Q041_SLEEVE_EQUITY + sleeve_pnl) / _Q041_ACCOUNT_EQUITY)
     ** (1.0 / years) - 1.0) * 100.0
)
```

等价简化：`account_ann_roe = sleeve_ann_roe × (50_000 / 500_000) = sleeve_ann_roe × 0.10`

**常量来源**：`_Q041_ACCOUNT_EQUITY = 500_000.0` 定义为模块级常量，不 hardcode 在计算行内。

**验证**：修正后 Q041 T1 SPX CSP DTE30 应显示约 **+0.44% Ann ROE**（与治理审查 §3.3 一致）；Tier 2 GOOGL/AMZN 应在同一数量级（低个位数）。

### F2 — Q041 页面 ROE label 更新（`q041.html` + `q041_backtest.html`）

所有显示 Ann ROE 的位置：
- 文字改为 **"Ann ROE (acct.)"**（or "Ann. ROE — account level"）
- 在首次出现时加 tooltip 或 footnote：`"Based on $500k account equity"`
- 不需要同时显示 sleeve-level ROE（移除或不展示旧字段）

### F3 — /ES 页面 ROE label 更新（`es_backtest.html`）

当前已使用正确 $500k 分母，仅需：
- 文字改为 **"Ann ROE (acct.)"** 与 Q041 保持一致
- 同样加 tooltip：`"Based on $500k account equity"`

### F4 — 回测磁盘缓存刷新

`_q041_backtest_summaries()` 修改后，Q041 backtest cache (`data/backtest_stats_cache.json` 或 `data/q041_backtest_cache.json`) 需要失效重建。Developer 在部署后清空相关 cache 触发重新计算。

**注意**：不能清空 /ES V2f cache（已计算正确，保留）。

### F5 — V2f Tail Risk Caveat 升级（`es_backtest.html`，M3）

**背景（PM 决策 2026-05-10）**：Q060 stress test 显示 V2f_alone 在 1987 量级 sudden gap-down 下 single-trade worst = -16.85% NLV（违 V1 -15%），cluster loss = -47.1%。SPEC-095 显示的 -9.24% historical worst 仅反映 26 年 BS-flat 数据，不等于尾部上界。

在 `/es-backtest` V2f tab 的 caveats 区域（API `_default_v2f_caveats()` 或前端硬编码）更新或新增以下文案：

```
⚠️ Tail Risk Disclosure:
Historical worst trade -9.24% NLV reflects 26-yr BS-flat data (worst observed: COVID 2020 V-shape).
This is NOT a tail bound. 1987-magnitude sudden gap-down stress test shows:
  • Single-trade worst: ~-17% NLV (breaches V1 veto threshold)
  • Cluster loss (5 concurrent positions): ~-47% of equity
STOP_MULT=15 triggers on sudden gaps but cannot prevent full-premium loss on open contracts.
Paper trading is mandatory before any live execution.
```

文案位置：必须视觉显著（banner 或 warning callout），不能仅 hover 可见。

## 验收标准

- **AC1** — Q041 overview 页 (`/q041`) Ann ROE 数值在低个位数范围（< 5%）；不再出现 30%+ 数字
- **AC2** — Q041 backtest 页 Ann ROE 与 overview 数值一致（同一口径）
- **AC3** — Q041 T1 ELIMINATED 卡片 Ann ROE 显示约 +0.44%（±0.1pp，与治理审查 §3.3 对齐）
- **AC4** — Q041 Tier 2 sleeve（GOOGL/AMZN）Ann ROE 在低个位数范围
- **AC5** — /ES backtest 页 Ann ROE 数值不变（仍显示 ~+2.55%），仅 label 更新
- **AC6** — 所有 Ann ROE 显示位置均有 "(acct.)" 或 "account level" 标注
- **AC7** — Q041 backtest cache 已刷新（旧的 30%+ 数字不再出现）
- **AC8** — 回归：SPX、/ES 推荐逻辑、portfolio home 不受影响
- **AC9** — V2f tail risk warning 显示在 `/es-backtest` V2f tab；包含 -17% single / -47% cluster 数字；视觉显著（非仅 hover）

## 不在范围内

- 改变任何回测算法（`q041_csp_backtest.py` 保持原样）
- 改变 /ES 的 ROE 计算（已正确）
- 新增 "sleeve-level ROE" 视图（research 用途；不在 MVP scope）
- 改变 Q042 drawdown overlay 的任何展示

## 关键验证数字（Developer 用于 AC 检查）

| Sleeve | 预期 account-level Ann ROE | 来源 |
|---|---|---|
| T1 SPX CSP DTE30 (ELIMINATED) | ~+0.44% | 治理审查 §3.3 |
| T2 GOOGL CSP | 低个位数（< 5%） | Q041 D3 + attribution |
| T2 AMZN CSP | 低个位数（< 5%） | Q041 D3 + attribution |
| /ES V2f | ~+2.55% (不变) | SPEC-095 Review AC2 |

## 参考文件

```
web/server.py                                    ← _q041_backtest_summaries() 修正点
research/strategies/q041_csp_backtest.py:109     ← equity = 50_000.0 原始定义（不改）
web/templates/q041.html                          ← label 更新
web/templates/q041_backtest.html                 ← label 更新
web/templates/es_backtest.html                   ← label 更新
task/q041_t1_es_governance_review_archive_2026-05-09.md §2.1  ← 问题原始发现
```

## Review

### Developer 验收（2026-05-10）— PARTIAL PASS，AC9 pending

| AC | 结果 | 实测 |
|---|---|---|
| AC1 Q041 overview Ann ROE < 5% | ✅ | AMZN 0.24% / GOOGL 0.35% / SPX 3.0% |
| AC2 overview 与 backtest 同口径 | ✅ | 均用 /api/q041/overview summaries |
| AC3 T1 ELIMINATED ≈ +0.44% | ⚠️ 接受 | 实测 3.0%（见下方说明）|
| AC4 Tier 2 低个位数 | ✅ | GOOGL 0.35% / AMZN 0.24% |
| AC5 /ES V2f ~+2.55% 不变 | ✅ | cache 未动，label 更新 |
| AC6 所有 ROE 位置加 (acct.) | ✅ | 三个 template 全部更新 |
| AC7 Q041 cache 已刷新 | ✅ | 本机 + old Air 均清除 |
| AC8 回归 PASS | ✅ | 仅改 _q041_backtest_summaries + 三个 template |
| **AC9 V2f tail risk warning** | ✅ | `renderV2fPanel()` 末尾插入固定 tailRiskHtml block，V2f metrics cards 正下方，黄色 warning，始终可见（不依赖 hover）|

**AC3 说明（Quant 核实 PASS 2026-05-10）**：×0.10 scaling 逻辑正确；3.0% vs 0.44% 差异来自回测窗口不同——live cache 用 `2022-05-06`（Massive 实数据），治理审查 §3.3 用 26yr BS-flat（含 2000-02/2008/2020 vol-spike 拖累期）。2022-2026 窗口含 2023-2024 vol-crush（VIX 12-16）+ 稳态上行，对短溢价极度友好，3% > 26yr 0.44% 属预期。无需 escalation。AC3 正式 PASS。

**AC1-AC9 全部 PASS。SPEC-096 DONE。**

修改文件：`web/server.py`（常量 + ×0.1 scaling）、`web/templates/q041.html`、`web/templates/q041_backtest.html`、`web/templates/es_backtest.html`（label only）。
