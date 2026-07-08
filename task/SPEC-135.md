# SPEC-135 — Decision Trace：决策管道可视化（PM 需求 2026-07-07）

**需求**: 主矩阵 + 各类门 + 治理层日益复杂，PM 要"where are we / why we are here"的单屏可视化。当日实例：7/7 一天内路由三变（早 carve BCD+敞口降级 → 午仓位 ACTION → 收盘 G2 触发 reduce_wait）。

**反漂移铁律（本 SPEC 的存在前提）**: 禁参数镜像——图的结构与数值**全部由生产代码每次评估时自吐**（trace），前端零硬编码 gate 清单。手画流程图 = 被禁止的镜像文档。

## 1. Trace 结构化输出

`select_strategy()` 加 trace 累加器：每个评估节点 `{layer, check, input, threshold, outcome, branch_taken, reason}`——数据层（VIX/IVP/趋势读数）→ 体制分层 → 矩阵格路由 → 格内门（VIX RISING / IVP 上下限 / carve 条件 / SPEC-060 死格等，**逐个记录含静默通过的**）→ 治理门（SPEC-123 halts、D2 前置门）→ 敞口层（131）→ 最终输出与语气。`bcd_governance.evaluate_gates` 同样入 trace。**行为零变更**：trace 只追加不分支（AC：全历史回放路由 bit-identical）。

## 2. 存储与 API

- 每日 trace 追加 `logs/recommendation_log.jsonl` 既有行（扩展字段，strict-JSON）
- `/api/decision-trace?date=`（缺省当日；v1 支持最近 30 日切换）

## 3. 渲染（新 /pipeline 页或 /spx 折叠区，dev 定）

**三泳道垂直 rail**（走过的节点高亮、未走分支 ghost、每节点显示 实际值 vs 阈值）：

- **Lane A 开仓决策管道**: 数据 → 体制 → 矩阵格 → 格内门链 → 治理门链 → 敞口 → 输出。7/7 实例应渲染为：VIX 16.13→NORMAL → carve(15-18)×BULLISH→BCD → **G2_18m_combined 红节点（−$6,006<0，含运行特性披露与 pm-clear 提示）** → reduce_wait
- **Lane B 持仓动作引擎**: 每个 open 仓位一行：21-DTE / collapse / profit-target / 止损锚 各触发器当前读数与距离
- **Lane C 描述层（明确标注"不进入决策"）**: Structure Map 摘要（墙/簇/线 + 证据 badge）——图本身教学决策边界：OI 墙不是门

## AC 要点

trace 注入后 selector 全量回放路由 bit-identical；当日 trace 与 rationale 文本一致性断言；G2 halt 日（7/7）作为固定测试用例（治理截断正确渲染）；静默通过的门必须出现在 trace（"为什么没拦"与"为什么拦"同权重）；三泳道分离与 Lane C 免责标注（内容审计项）；strict-JSON；DESIGN.md/theme 合规。
