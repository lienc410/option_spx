# SPEC-094.5 — Q042 Sleeve A 宽度替换（D30 +2.5% → +5%）+ F4 真实链对账补账

## 目标

Q100 P1（R-20260712-03）独立重验裁定：Sleeve A 的 +2.5% short 腿宽度是 Q062 用
width-directional 有偏定价尺子（INC 低估窄腿 debit 5.7% / 高估宽腿 11.8%，真实链
2026-05-04 锚点）选出的；ATM/+5% 在 INC/CALIB/STRESS 三路定价、两时代、
year-bootstrap P=0.965 下通过全部预注册 R1 条件（+$292k/19y，$/cash-day +29%，
等预算尾部完全相同）。PM 2026-07-12 ratify：宽度改 5%，DTE30/触发/时机/12.5% 全部不动；
同时补上 094.1 换结构后一直缺失的生产结构真实链对账。

## 策略/信号逻辑

无触发/治理/sizing-% 变更。仅 short strike 偏移：`ATM×1.025 → ATM×1.05`。

## 接口定义

**F1 参数替换**：`strategy/q042_sizing.py` `_OTM_PCT_A 0.025 → 0.05`（单一真值源；
41bfe45 之后前端经 `/api/q042/state` params 块读代码真值，零文案跟改）。
**F2 回测账本再生**：新增 `scripts/q042_regen_backtest.py`（修复该 CSV 无生成器的
可复现性缺口），从 `get_q042_history` walk-forward + 生产 INC 定价按**当前**
sizing 常量再生 `data/q042_backtest_trades.csv`；schema/记账惯例逐列保持
（1.0 contracts research scale，account_pct = ROI×10% legacy 显示惯例，
到期=首个 ≥signal+1+DTE 交易日收盘内在价值结算，无摩擦）。
**F3 F4-对账补账**：新增 `research/q042/q042_f4_tieout_d30.py`（old Air 跑，
链归档在那边）：对最近 5 个交易日的 SPX 链快照，计算 D≈30 的 ATM/+5%（生产）
与 ATM/+2.5%（legacy 参照）broker mid debit vs 生产模型 debit，追加至
`data/q042_f4_tieout_history.csv`（schema 不变，dte 列区分新旧行）。

## 边界条件与约束

- 无在飞 A 仓（2026-07-12 生产 state 双 sleeve armed/无仓，audit 已核）→ 无
  grandfather 语义；新结构自下一次 fire 生效。
- 预注册（Q100 §2）：INC 模型在 D30/+5% 预期高估 debit → tie-out delta_pct
  预期落在 **[−15%, −5%]**（模型贵于 broker = 回测保守方向）。落在区间外 = 新信息，
  记录并评估是否触发定价迁移研究（CALIB 化归 backlog，不在本 spec）。
- 主策略三套回测磁盘缓存不受影响（q042_sizing 不在 selector/主引擎路径）。

## 不在范围内

DTE/触发深度/时机/re-arm/12.5% cap（Q100 全部确认现任）；Sleeve B 一切；
Q042 定价模型 INC→CALIB 迁移（登记 backlog）；17.5% staging（挂起绑定 Q092 (a)/(b)）。

## Review
- 结论：Q100 P1 findings = 本 spec 的研究依据（预注册 R1 四条全过 + 真实链仲裁）。

## 验收标准

| AC# | 描述 | 结果 |
|---|---|---|
| AC-94.5-1 | `compute_sizing(500k, 7400, 25, "A")` → strikes (7400, 7770)，DTE 30 语义不变 | |
| AC-94.5-2 | Sleeve B 零 diff：`compute_sizing(..., "B")` strikes/DTE/debit 与改动前逐位一致 | |
| AC-94.5-3 | 再生 CSV：A 行 short_strike 全部 = round5(S×1.05)；**信号流对齐**：A 行 signal_date 集合 == Q100 独立重放流（38 事件，feedback_signal_translation_alignment_ac） | |
| AC-94.5-4 | 再生 CSV 金行复核：2007-02-27 行 (KL 1400, KS 1470, exit_pnl = 内在−debit 手算一致)；B 行与再生前逐位一致 | |
| AC-94.5-5 | F4 补账：old Air 最近 5 交易日 D≈30 两宽度对账行落盘；PASS = 5 日中位 \|delta_pct\| < 15%（沿 F4 门槛）；record 预注册区间命中与否 | |
| AC-94.5-6 | 回归：094.2(22)+094.3(13)+094.4(13)+142(14) 全绿；`/api/q042/state` params 块 otm_pct 显示 5.0 | |

## Handoff Contract

1. **What changes**: `strategy/q042_sizing.py`（1 常量 + docstring）；新增 `scripts/q042_regen_backtest.py`、`research/q042/q042_f4_tieout_d30.py`、`tests/test_spec_094_5.py`；再生 `data/q042_backtest_trades.csv`；追加 `data/q042_f4_tieout_history.csv`。
2. **Invariants**: 触发状态机/gate/settle/告警链路零 diff；Sleeve B 逐位不变；web 层零改动（41bfe45 动态化已覆盖）。
3. **Acceptance**: AC-94.5-1..6。
4. **Rollback**: `_OTM_PCT_A` 回 0.025 + 重跑 regen 脚本即回退。

---
Status: DRAFT → implementing 2026-07-12
