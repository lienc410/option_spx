# SPEC-094.2 独立审计 Packet（2nd Quant Review）

**Date**: 2026-07-07
**Requestor**: Quant Researcher（1st）
**Trigger**: PM 指令——SPEC-094.2 审批以独立审计为前置
**Review target**: `task/SPEC-094.2.md`（Status: DRAFT）
**回复落点**: `task/SPEC-094.2_2nd_quant_review_packet_2026-07-07_Review.md`

---

## 1. Review 范围

SPEC-094.2 是 Q042 执行层完整性修复包（F1 结算 wiring / F2 expiry 修正 / F3 gate 数据源+fail-closed / F4 dry-run / F5+F5b blocked 告警+现金上下文 / F6 combined_bp_pct writer）。请独立验证：

1. **事实层**：spec 引用的每一条缺陷claim是否成立（要求 reviewer 自行读源码到 file:line，不采信 1st Quant 的结论转述）；
2. **设计层**：F1–F6 的方案是否正确、完备、无新风险（特别是 F3 数据源选择与 fail-closed 语义、F5 armed-consumption 语义决定）；
3. **AC 层**：验收标准是否可验证、是否足以防同类回归（特别是 AC-94.2-1 integration smoke 是否真的非 mock 可执行）；
4. **invariant 层**：spec 声称不动的东西（trigger/sizing/DTE/cap 参数、AC14/AC16）是否真的不会被 F1–F6 实施牵动；
5. **遗漏**：有没有 1st Quant 没看到的同类断裂或修复副作用。

## 2. 待验证的核心 claims（evidence pointers，reviewer 须独立复核）

| # | Claim | 指针 |
|---|---|---|
| C1 | `read_main_bp_pct` 读的 `bp_pct_account` 字段在生产 position state 从不存在（全仓无 writer），gate 恒 0 | `strategy/q042_gate.py:98-115`；`web/server.py:5406`（state_payload 构造）；grep `bp_pct_account` 全仓 |
| C2 | `settle_expired_positions` 零调用方；executor EOD 无到期清理；fire 后 `has_pos` 永真 | `production/q042_positions.py:131`；`production/q042_executor.py:185-270`；对照 `signals/q042_trigger.py:322-340`（walk-forward 有清理） |
| C3 | `_expiry_from_signal` 对两 sleeve 硬编码 signal+90，违反 SPEC-094.1（Sleeve A entry+30） | `production/q042_positions.py:82-84`；`task/SPEC-094.1.md` §表（Expiry 行） |
| C4 | dry-run 照发 Telegram、照 save_state、`if sent or not dry_run` 照写记录 | `production/q042_executor.py:229-265` |
| C5 | `combined_bp_pct` 无 writer，web monitor 恒 "ok" | grep writer；`web/server.py:2236-2245` |
| C6 | F3 拟用数据源 `data/sleeve_governance_runtime.json` 的 `pools.spx_pm_bp_pct` 存在且由 `record_state_snapshot` 日度持久化 | `strategy/sleeve_governance.py`（`_write_json(RUNTIME_STATE_PATH, state)` 路径与 state_payload["pools"] 构造） |
| C7 | F5b 依据：Q093 P1 重放否决现金闸门（挡 3 笔 +$244k 赢家 vs 保护 +$37k） | `research/q093/q093_p1_findings_2026-07-07.md` + `q093_p1_cash_stack.py`（方法学抽查：重放语义是否对齐 SPEC-111 生产语义 / Q092 基线复现） |

生产侧证据（reviewer 无法直接访问 old Air，采信如下已记录读数，但可质疑其解读）：gate log 44/44 条 `main_bp_pct=0.0`；`q042_state.json` 无挂仓；`q042_paper_trades.jsonl` 不存在；executor 日跑（16:15，Schwab NLV $629k）。来源：`doc/q042_aftermath_synergy_audit_2026-07-07.md` §1。

## 3. 1st Quant 已知的薄弱点（请重点打）

1. **F3 语义放宽**：R1 池口径（账户级 maint margin，含 equity）宽于 SPEC-094 原文「main strategy BP」。1st Quant 论证"方向保守可接受"——这是一个 unquantified caveat（`feedback_unquantified_caveat_sign_risk`），请核符号：是否存在 equity margin 抬高 BP 读数 → gate 过度压缩 Q042 → 在正确时刻挡掉 overlay 的场景？量级多大（今日 Schwab maint / NLV 读数下 allowance 还剩多少）？
2. **F5 armed-consumption 决定**（fire 即消耗，blocked 只告警不重试）：与研究 trigger 定义一致性 vs 漏单风险的 trade-off，1st Quant 选了前者。是否同意？
3. **F1 结算顺序**：settle → 状态清理 → update_sleeve 的顺序是否有边界日（expiry 当日再触发）双动作风险？
4. **staleness 阈值 2 交易日**（F3）是否合理（runtime snapshot 的实际写入频率）？

## 4. Verdict 格式要求

- 结论：**PASS / PASS WITH REVISIONS / FAIL**
- 若有修订项：逐条列 blocking / non-blocking，给出具体修改建议（可直接写替换文本）
- 方法学：引用 `METHODOLOGY.md` 与 `QUANT_RESEARCHER.md#short-premium-risk-management-principles` 中适用条款（如适用）
