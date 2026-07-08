# SPEC-137 — 遗留小项清扫批（2026-07-08 凌晨，PM 收尾指令下汇编）

积压的四个已确认小项，一批扫清：

1. **直连 sender 迁 gateway**（SPEC-130 遗留）：`scripts/etrade_status_notify`、`research/q041/collect_chains` collector alert、`research/q041/daily_chain_sanity` 三处改走 `notify.gateway.push`（分类 + about 首行 + dedupe），文案顺手人话化（136 表 #7）。迁移后 event_push 直连调用点全仓 grep 应只剩 gateway 与 telegram_bot 传输层。
2. **SPEC-123 duplicate-id 迁移**（Q088 T1 遗留）：6/3 的 `2026-06-03_bcd_001` 双 open 事件 id 冲突——按 SPEC-123 §4a 注释方案落 correction 事件消歧（append-only），campaign 归组复核不变。
3. **Short Leg Fill 字段**（SPEC-127 遗留）：开仓表单加可选 "Short Leg Fill" 输入 → open 事件记 per-leg fill → cycle-0 collapse 监控激活（填了才启用 ≤15% 检查，不填 21-DTE 兜底——127 回报里的既定方案）。
4. **put 墙 teal 入 token**（SPEC-132.1 遗留）：`#0F8A7C`/`#2FB8A6` 图表常量迁 theme.css token（如 `--teal-chart`），trace_render/结构地图改引 token；DESIGN.md Color 节补一行。

## AC

每项独立 commit；#1 全仓直连扫描清零断言（130 的静态扫描扩展）；#2 幂等 + campaign 数学回归；#3 ledger 字段 + collapse 激活单测（填/不填双路径）；#4 双主题渲染回归；全量 pytest 基线零新增。
