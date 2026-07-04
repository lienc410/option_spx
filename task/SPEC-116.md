# SPEC-116 — Q085 S2-BPS 自适应 sleeve（Phase 1: Paper + 测量）

**来源**: Q085 研究线，G-review RATIFIED（外审条件全生效，见 `task/q085_g_review_packet_2026-07-04.md` 终态）
**性质**: **纯增量**——本 SPEC 不修改 selector/catalog/gates 的任何行为，只新增每日任务、数据文件与 Telegram 推送。生产矩阵行为零变化。
**Phase 边界**: 本 SPEC 只覆盖 paper 阶段。转实盘需满足 C3 测量门 + PM 显式决定，届时另起 SPEC-116.1（降级状态机接实盘 + 下单提示）。

## 1. 信号定义（point-in-time，只用 ≤ 信号日数据）

`signal_day(d)` 为真当且仅当同时满足：
1. **超卖复合**: SPX RSI(2) < 10（Wilder 平滑）**或** 连续三日收跌
2. **NORMAL regime**: 当日生产管线判定 regime == NORMAL（VIX 15-22 带）
3. **被挡**: 当日生产 selector 输出为 Reduce/Wait（无 strategy_key）——即现有 gate 栈拦下的日子
4. **Layer-1**: VIX < 35（EXTREME 永久锁定，不因本 sleeve 改变）

参考实现与冻结测试向量：`research/q085/q085_battery_lib.py`（F3_rsi2_os / F3_down3 定义）。

## 2. 每日任务（16:50 ET，晚于 16:30 链快照）

**A. Skew 监控（每天，无论是否信号日）**: 从当日 `data/q041_chains/<date>/SPX.parquet` 取 25-35 DTE puts，测 |Δ|≈0.50/0.30/0.15 三档 IV（各取最近 3 行均值），连同当日 VIX 落盘 `data/q085_skew_monitor.jsonl`。此文件是 CALIB 季度重测与 resume 前 fresh-CALIB 的数据基础（外审 C3/C6）。

**B. Paper 开仓（仅信号日）**: 从链快照构造 BPS——expiry 取最近 30 DTE；short = |Δ| 最近 0.30 的 put，long = |Δ| 最近 0.15 的 put；记录两腿 bid/ask/mid。entry credit 双口径：`mid`（mid−mid）与 `natural`（short@bid − long@ask）。写入 `data/q085_paper_log.jsonl`（open 事件）+ Telegram 推送。

**C. Paper 管理（每天，对全部 open 仓位）**: 用当日链快照重估平仓成本（双口径）；触发 `cost_mid ≥ 3 × credit_mid` → paper 止损平仓；否则 DTE ≤ 21 → paper 到期平仓。close 事件记录已实现 PnL（mid 与 natural 双口径）、hold 天数、期间 VIX 峰值（cascade 跟踪）、是否 breach（收盘 < short strike）。

**D. 降级统计（信息性，每次 close 后）**: 滚动 10 笔 PnL 和、sleeve 累计 PnL；若滚动和 < 0 或累计 ≤ -$5,000，推送 WARNING 注记（paper 阶段不停机，只记录——这两条规则在实盘阶段是硬性的）。

**E. 重叠跟踪（外审 C7）**: open 事件记录当日主 BPS sleeve 是否有在场仓位（净敞口叠加标记）。

## 3. Telegram 文案（沿用 house 双语规则）

- 信号日: `[S2-BPS PAPER] 信号日 · SPX <close> · VIX <v> · 30DTE <ks>/<kl> credit mid $<x> / natural $<y>`
- 平仓日: `[S2-BPS PAPER] 平仓 · <entry_date> 仓位 · PnL mid $<x> / natural $<y> · hold <n>d<如止损标注 STOP>`
- 非信号日：静默（skew 监控照常落盘）

## 4. AC 清单

- **AC-1 信号一致性**: 对 2024-01 以来的历史日期，`signal_day()` 输出与研究冻结向量完全一致（handoff 附 12 个正例 + 12 个反例日期）
- **AC-2 链提取集成冒烟**（非 mock，per `feedback_spec_integration_test`）: 对真实 `SPX.parquet` 跑通 skew 测量与 BPS 构造，字段名/类型断言
- **AC-3 skew monitor**: 每日 append，strict-JSON（禁 NaN/Inf，per `feedback_nan_json_browser_vs_python`），schema `{date, vix, atm_iv, d30_iv, d15_iv, d30_off, d15_off, atm_off}`
- **AC-4 静默性**: 非信号日零 Telegram
- **AC-5 生命周期**: open→(stop|expiry) close 全路径测试，双口径 PnL，stop 路径用构造的 3× 场景验证
- **AC-6 生产零扰动**: 本 SPEC 不触碰 `strategy/selector.py`、`strategy/catalog.py`、任何 gate 文件；CI 断言这些文件与 main 基线 bit-identical
- **AC-7 Layer-1**: VIX ≥ 35 日即使超卖+被挡也不产生信号（测试向量含 2020-03 型日期）

## 5. 转实盘门（记录在案，本 SPEC 不实现）

≥2 个信号日真实报价已捕获 + skew 偏移与 CALIB 假设复核 + PM 显式决定 → SPEC-116.1（1 张锁定、(10,5) 降级状态机硬性化、-$5k 累计全停、季度报表）。
