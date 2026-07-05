# SPEC-122 — BCD 真实报价影子记录（Q087 SPEC-120 §2 裁决配套）

**目的**: SPEC-120 显示 BCD 家族（LOW_VOL 看涨两格 + SPEC-113 carve）是矩阵中唯一被校准定价实质压缩的特许经营权，而其校准恰好最弱、真实 ledger 恰好为正。本 SPEC 用真实报价终审模型之争——**不改任何路由/gate/执行行为，纯记录**。

## 变更（复用 SPEC-116 机器）

1. 每日 16:50 任务扩展：当日若为 BCD 信号日（LOW_VOL×BULLISH 放行 或 SPEC-113 carve 放行——按生产 selector 判定，含 SPEC-079 filter 后状态），从当日 SPX 链快照构造真实 BCD 报价：
   - 长腿：90 DTE 最近到期、|Δ| 最近 0.70 call；短腿：45 DTE 最近到期、|Δ| 最近 0.30 call
   - 记录两腿 bid/ask/mid、vendor iv、mid-implied iv、debit（mid 与 natural 双口径）
   - 同时落三个模型 debit（FLAT/CALIB/PESS，调 pricing 库同参）→ 每条记录自带 model-vs-real 误差
2. 落盘 `data/q087_bcd_quote_shadow.jsonl`（strict-JSON）；Telegram 静默（纯记录，heartbeat 注册表加 trading_day 新鲜度即可）
3. Checkpoint 定义：**≥8 个信号日**后出对比报告（预计 4-8 周，LOW_VOL 信号频率高于 carve）——real debit 落在 FLAT/CALIB 之间哪里，直接决定 BCD 家族裁决与 A4/Q088 的后续

## AC

- AC-1 信号日判定与生产 selector 一致（复用其输出，禁止旁路重算）
- AC-2 真实链集成冒烟（非 mock）：对 2026-07-02 快照构造 BCD 双腿并断言字段
- AC-3 三模型 debit 与 pricing 库一致（同参断言）
- AC-4 非信号日零写入零推送；AC-5 heartbeat 注册表新条目
