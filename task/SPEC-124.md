# SPEC-124 — Q088 T1 制度化批（PM 2026-07-06 批准 DEFERRED #1）

小批，全部零行为变更或纯增量：

1. **SPEC-079 正式退役**：`bcd_comfort_filter_mode` 默认 shadow → **disabled**（生产从未拦截，零行为变更；A4+T1 双 verdict 支持）；`data/bcd_filter_shadow.jsonl` 回测重放污染修复——运行时与回测日志分流或回测侧禁写（74MB 现状归档后清理）；catalog/展示层撤下 comfort filter 描述
2. **断言批**（T1 收口清单）：profit-target catalog↔selector↔bot 一致性测试；sleeve_governance.py:662 的 100k fallback 用途断言（仅 shadow 展示，进 cap 数学即 raise）；矩阵展示↔行为一致性测试（SPEC-060 案例通用化，含 HIGH_VOL 两格 aftermath 归因）
3. **展示文案**：/aftermath 页注明"解锁日骑 iron_condor_hv 归因"；/es 页标注"live=SPEC-061 单张；ladder 为已验证未部署配置"（A5 项）；`_ES_BP_PER_CONTRACT=20529` 硬编码加新鲜度告警或改实时读（A5 项）
4. **DEFERRED.md 月度曝光**：heartbeat 或 bot 每月首个周一推送台账逾期项摘要（读 task/DEFERRED.md 的复核期限列）

AC: 079 退役后全回归绿（shadow 本就不拦，应零差异）；断言批各一条否定测试；文案人工核对；月度推送用假过期项集成测试。
