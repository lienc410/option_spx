# Q087 P0 — Track A 参数清单与时代敏感性分诊（2026-07-05 快照）

**性质**: 审计工作表（dated snapshot），真值永远以代码为准（file:line 已注）。非参数镜像文档。
**分类**: 🔴 = 时代拟合嫌疑高，优先审 | 🟡 = 需复核但嫌疑中 | 🟢 = 结构性/求生性，非时代问题 | ⚠️ = 立即发现的异常

## 信号层

| 参数 | 值 | 位置 | 分类 | 备注 |
|---|---|---|---|---|
| LOW_VOL/HIGH_VOL 边界 | 15 / 22 | signals/vix_regime.py:34-35 | 🟢 | regime 是可观测天气，自适应哲学边界内 |
| EXTREME≥35 Layer-1 边界 | 35.0（StrategyParams.extreme_vix） | selector.py:56 | 🟢 | 已定位，在生产路径。**⚠️ 但 selector.py:376 注释写 "hard boundary (40)"——35 vs 40 需核实是注释漂移还是存在第二个边界变量**（发 dev C-2 清册） |
| IVR HIGH/LOW | 50 / 30 | signals/iv_rank.py:32-33 | 🔴 | **IV_LOW=30 是 Q083 死格现象的直接驱动**（67.5% NORMAL×BULL 日落入 LOW 列）；252d lookback 的分位天然时代滞后 |
| IVR lookback | 252d | iv_rank.py:34 | 🟡 | spike 后 12 个月的"分位地板"机制根源；替代窗口从未测过 |
| 趋势 MA/gap/ATR | 20/50, 1%, ATR14×1.0 | signals/trend.py:27-31 | 🟡 | Q085 证明趋势信号无 forward 信息量，但此处用途是"状态分类"非预测——用途区分后再判 |

## Gate 层

| 参数 | 值 | 位置 | 分类 | 备注 |
|---|---|---|---|---|
| IVP 通用双门 | 40-70 | selector.py:182-183 | 🔴 | **Track A 头号对象**：Q085 P0 已证 anti-timing（被挡窗口低点→放行日 +3%）；上界挡住的日子左尾更肥是全样本聚合结论，需分时代重审 |
| BPS NNB 窄带 | 43-55 | selector.py:215-216 | 🔴 | Q015 时代校准；26 年只放行 96 天（<4 次/年）——过度保守首要嫌疑 |
| IVP63_BCS_BLOCK | 70 | selector.py:195 | 🟡 | |
| REGIME_DECAY/LOCAL_SPIKE 四阈值 | 全 50 | selector.py:191-194 | 🟡 | SPEC-048~055 时代产物 |
| SPEC-113 carve | VIX<18 | selector.py:188 | 🟡 | 2026-06 新验证，但锚在 BS-flat 定价上→ Track B 交叉复核 |
| SPEC-079 filter | VIX≤15 & dist≤-1% & gap>1.5pp | bcd_filter.py:9-11 | 🔴 | Q085 已证在 NORMAL 结构性失效；在 LOW_VOL 的真实拦截率与分时代净值从未复核 |
| Aftermath 触发 | peakVIX≥28 / 10d / -10% | selector.py:218-220 | 🟡 | |
| IC_HV 并发上限 | 2 | selector.py:221 | 🟢 | 风险结构性 |

## 治理层

| 参数 | 值 | 位置 | 分类 | 备注 |
|---|---|---|---|---|
| SPEC-111 cap/alert/floor | 60% / 75% / $30k | cash_budget_governance.py:42-44 | 🟡 | **2026-08-01 已有排期复审**（Q082 live-test tripwire routine）——Track A 不重复，只把时代镜头并入该复审 |
| Sleeve caps 七件套 | 80/80/60/50/50/40/90 | sleeve_governance.py:34-41 | 🟡 | Q078 时代校准，account scale 已变 |
| **SPX_NLV / ES_NLV** | **100,000 硬编码** | sleeve_governance.py:30-31 | ⚠️ | 账户真实 NLV 远非此值；所有 CAP_% 换算可能整体失真——**快赢候选：改为 live NLV 读数**（需 dev 确认下游用途后走 SPEC） |
| Ladder sizing/cadence/BP 顶 | 3 张 / 5d / 35% | sleeve_governance.py:41-43 | 🟡 | |

## /ES HV Ladder（实盘）

| 参数 | 值 | 位置 | 分类 | 备注 |
|---|---|---|---|---|
| V2F DTE/退出 | 49 / 21 | ES_puts/backtest.py:70-71 | 🟡 | |
| V2F 止损/止盈 | 15× / 10% | :76-77 | 🔴 | **15× 权利金止损极宽**——校准时代为高波动年份；telegram 监控用 2×/3×，两套口径关系需审 |
| V2F VIX 门 | ≥22 | :78 | 🟢 | 与 regime 边界一致 |
| 节奏/槽位/簇 | 5d/5 槽/4→10d | :72-75 | 🟡 | |

## Track A 排序建议（P0 结论，待 checkpoint #1）

1. **IVP 双门 + NNB 窄带**（🔴×2，Q085 证据现成，直接兑现自适应哲学）
2. **IV_LOW=30 与 252d lookback**（死格机制根源，与 #1 联动审）
3. **V2F 止损口径**（实盘资金，两套止损口径并存）
4. **SPEC-079 在 LOW_VOL 的真实作用**（可能是纯摩擦）
5. ⚠️ 两件立即核实项：EXTREME≥35 实现定位；SPX_NLV=100k 硬编码影响面（发 dev）
6. 历史 kill 档案分时代复查（Q084 首个）——与 verdict map 并行
