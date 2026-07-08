# SPEC-135.2 — 账户级容量线合图（Q091 定稿 $238k 进代码与 Lane A，PM 确认 2026-07-07 晚）

**背景**: Q091 P0 RATIFIED——crash-day 可部署 defined-risk 容量 = excess $337,688 − buffer $100,000 ≈ **$238k**，PM 指定"后续所有容量讨论以此为准"。当前该数只活在 memo（research/q091/q091_p0_memo.md）——**真值必须进代码**。与 131v2 策略资金池是两个轴：资金池管家族集中度（篮子），容量管全账户崩盘承载（天花板）。

## 1. 常数之家（单一真值）

`strategy/capacity.py`：
- `CRASH_DEPLOYABLE_DR_USD = 238_000`——provenance 注释：Q091 P0 RATIFIED 2026-07-07（$337,688 − $100k buffer）；**更新路径 = SPEC-111 §4-B 重仿真（另一会话 lane），改值须 PM ratify**
- `used_defined_risk() -> dict`：全账户 open positions max loss 求和（**复用 SPEC-129 exposure 真值函数**跨家族聚合，禁旁路重推），返回 {used_usd, capacity_usd, pct, positions[]}

## 2. 显示合图（display-only，不做门）

- **Lane A ④ 资金层新增一行**（人话 + hover 三件套）：`账户级 defined-risk：已用 $76,600 / 可部署 $238,000（32%）——崩盘日安全垫 $100k 已预留`；code_ref=Q091
- **SPEC-129 开仓表单风险区新增同一条**：本单成交后 已用/容量（与家族并发行并列）
- 容量硬门是否设立 = SPEC-111 lane 未来治理决定，本 SPEC 不越界

## AC

常数单一来源断言（全仓 `238` 容量字面量仅 capacity.py 一处）；used_defined_risk 与 SPEC-129 家族机制同源一致性测试；7/7 生产向量（76,600/238,000=32.2%）；trace 纯附加（135.1 恒等合同沿用）；strict-JSON；人话铁律合规（135 §0）。
