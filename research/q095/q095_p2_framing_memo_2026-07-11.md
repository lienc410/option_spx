# Q095 P2 Framing Memo — 模式切换赛跑（预注册，待 PM ratify 杀标）

**Date**: 2026-07-11 · **Status**: PRE-REGISTERED, NOT STARTED — 杀标经 PM ratify 后开跑

## 假设（PM 2026-07-11 修正版）

不做"事前预测震荡"；做**状态确认 + posture 响应**："确认单边已结束"后停发方向性家族新仓/降杠杆，即使确认晚几天。价值来自赛跑：`价值窗口 ≈ dwell time − detection lag − whipsaw 成本`。

**P1 支撑**：账本亏损侧近乎纯 delta（BCD 184%/BPS 87%）——砍方向逆风窗口砍的是纯 delta 亏损；IC（premium 引擎，delta 份额 2-11%）不受影响可照常运行。**响应按家族分层**：切换确认只作用于 BPS/BCD 新仓，不动 IC。

## 与已有 kill 的边界（预注册声明）

- Q082 P9/memory 反驳射程 = entry-time gate 预测 forward；本研究是状态确认后改变**后续**行为，不在射程。但若 P2 结果显示分类器实质上只是 MA-cross 换皮（与 MA 信号 flip 高度重合），则引用 Q082 P9 直接归档。
- Q089 E2（等回调入场 kill）：本研究不含任何"等待入场"组件；降仓后资金的再部署走已有 Q042 通道，不新设等待规则。
- Q067（jitter fixes 全败）：本研究的杀标结构直接继承其教训（见下）。

## 事实层设计（先事实后反事实，宪法序）

**分类器候选（预注册 4 个，不再加）**：①efficiency ratio（|净位移|/Σ|日位移|，20d）②区间宽度/ATR 比（20d high-low vs 14d ATR 倍数）③MA20 斜率带（斜率绝对值分位）④ADX(14)。切点各预注册 1 个（中位数基准），**不做切点网格**（`feedback_stratum_cutpoint_overfit`）。

**三分布（26y 日度）**：
1. 转换频率 + detection lag：真值转换点用后视平滑段定义（预注册：20d 前向累计位移 <1×ATR 段起点），各分类器确认延迟分布；
2. dwell time：转换后非单边状态驻留交易日分布；
3. flip-rate：分类器日级状态翻转率 + 5TD 内回翻率（Q067 口径）。

## 杀标（PM ratify 对象）

| # | 杀标 | 阈值 | 依据 |
|---|---|---|---|
| K1 | flip-rate 首杀 | 日级翻转率 > 8% 或 5TD 回翻率 > 50% → 该分类器死 | Q067 实测 7.4-11.5%/61% 即为"fix 全败"区间 |
| K2 | 赛跑窗口 | median(dwell) − median(lag) < 5 TD → 死在事实层 | 窗口小于一周无操作价值 |
| K3 | 反事实（仅过 K1/K2 后）| "确认→停发 BPS/BCD 新仓"vs 现状 head-to-head，execution 标准（vs 现状显著优，whipsaw 计满摩擦 + 踏空机会成本），且 worst-era 分层不得恶化 | `feedback_decision_type_governs_significance_standard` |

全部 4 个分类器死于 K1/K2 → P2 CLOSED-NULL 归档，PM 感受①记为"已测未获证"，不进任何 gate。

## 不在范围

持仓期强平/止损规则（Principle 1 边界另议）；IC 路由变更；"回调买入"新规则（Q042 已覆盖）。
