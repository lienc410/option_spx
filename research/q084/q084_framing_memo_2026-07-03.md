# Q084 Framing Memo — NORMAL × IV_LOW × NEUTRAL 非方向策略研究

**日期**: 2026-07-03
**来源**: Fable 外部 review（`task/q083_fable_external_review_2026-07-03.md`）识别为 SPEC-113 之后下一个最大的可修死格；PM 2026-07-03 指示按序执行立项。
**状态**: REGISTERED — P0 表征已完成（本文 §2），P1 起待 PM 过目本 memo 后按常规节奏推进。

---

## 1. 研究问题

`NORMAL × IV_LOW × NEUTRAL` 当前无条件路由 reduce_wait（26 年 182 个 blocked 天，零策略覆盖）。该格与 SPEC-113 carve 同属"post-spike IVR 地板"现象，但 trend 为 NEUTRAL——bull 方向结构不适用。问题：是否存在非方向性 +vega 结构（ATM calendar / double diagonal）使该格的边际经济收益为正？

## 2. P0 表征（已完成，数据源同 Q083：`_signal_history_cache.csv`）

| 维度 | 值 | 对照（SPEC-113 carve） |
|---|---|---|
| blocked 天数 | 182 / 26y | 562 |
| VIX 中位 | **18.64**（min 15.04 / max 21.97） | 16.72 |
| VIX<18 子集 | 仅 66/182 | 100%（定义内） |
| fwd-21td vol expansion（≥1.2x）频率 | **45.1%** | BULLISH 格 29.6%（P11） |
| 年份聚簇 | 2003-04、2010-12、2023 为主；**2008 有 18 天** | 同类 decay 年 |

三个直接推论：
1. **+vega 先验比 BULLISH 格更强**（45.1% vs 29.6% 扩张频率）——calendar/double diagonal 的方向正确；short-vega IC 符号错误，直接排除。
2. **该格比 carve 更"险"**：VIX 中位高 ~2 点，且含 2008 年 18 天（crisis 邻接污染）。P1 必须先做 Layer-1 求生筛查（per `feedback_survival_vs_income_layering`：2008 型天数剔除或单列，不参与收益论证）。
3. **规模先验小**：182 天 ≈ carve 的 1/3。按 SPEC-113 兑现比例线性锚定（562 天 → 今日尺度净 +$8,857/yr），本格天花板量级 ~$2.9k/yr——研究工作量按此定尺寸（短 phase 计划，不做 15-phase 长线）。

## 3. Phase 计划（短线）

- **P0** 表征 ✅（本 memo）
- **P1** 反事实模拟：ATM calendar（近月 short ~30-45 DTE / 远月 long ~90 DTE）在 182 天上的 PnL 分布；2008 天单列；today-scale 绝对值从第一天起报（per `feedback_absolute_at_today_scale_not_historical_ratio`）
- **P2** 稳健性前置（per `feedback_post_withdrawal_proposals_front_load_robustness`）：悲观 skew bracket + term-structure 敏感性；exit-day unsmoothed 记账（per `feedback_sharpe_smoothing_artifact`）
- **G-review** 2nd quant packet（task/）；kill 类 verdict 需外审（per `feedback_kill_gate_external_read`）
- **Verdict**：DOCUMENT-and-stop 是合法终点（per `feedback_layer_n_replacement_outcome`，cash 是合法终点）

## 4. 预注册 kill gates（P1 前锁定，PM 可在过目时调整）

1. **双门槛**（per `feedback_boundary_research_dual_threshold`）：freq AND ROE 同时达标才继续——若 Layer-1 筛后可交易天 <120/26y，或悲观 bracket 下今日尺度净收益（扣 QQQ 10% 机会成本）< **$1,500/yr**，则 DOCUMENT 收尾。
2. **切点纪律**（per `feedback_stratum_cutpoint_overfit`）：不做 VIX 子切点搜索；若 aggregate 零信号，不用 stratum-edge 复活提案。
3. **指标包完整**（per `feedback_strategy_metrics_pack`）：marginal $/BP-day、worst trade、disaster window、CVaR 全套，与 SPEC-113 carve 同表对照。

## 5. 与现有治理的交互（预先声明）

- Calendar/double diagonal 是 debit/cash-occupying 结构 → 入 `CASH_OCCUPYING_STRATEGIES`（SPEC-115 泛化后的框架），受 SPEC-111 cap/floor 管辖。SPEC-113 §6.2 前置依赖在此触发：**第二个 cash-occupying 策略加入时须重审 SPEC-111 并发假设**（sequential-ladder 冗余失效）。
- SPEC-079 comfortable-top filter 对该格结构性失效（VIX≥15 定义内），与 carve 相同——若 P1 显示需要入场风控，须新设计，不能复用 SPEC-079。
