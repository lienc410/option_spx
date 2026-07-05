# SPEC-123 §4a — Ledger ID 碰撞迁移说明（2026-07-05，dev）

## 事实（oldair `logs/trade_log.jsonl` 真值）

| 事件 | id | timestamp | 备注 |
|---|---|---|---|
| open | `2026-06-03_bcd_001` | 11:24:03 | |
| open | `2026-06-03_bcd_001` | **11:24:05** | **与上一条同 id —— 碰撞** |
| open | `2026-06-03_bcd_002` | 11:24:35 | 正常 |
| correction (target=open) | `2026-06-03_bcd_001` | 13:31:29 | **目标歧义**：无法确定修正哪一笔 _001 |

外审原话"三笔 06-03 的 ledger ID 前缀相同"实际比前缀更严重：前两笔 open **完全同 id**。

## 根因与修复（已入代码，commit 见 SPEC-123 批）

`/api/position/open` 在**governance 评估之前**分配 id、评估之后 append——评估耗时数秒，
两个并发提交（11:24:03/05，疑似双击或重试）都在对方 append 前扫描了 log，各自算出 `_001`。

修复：id 分配下移至 append 临界区内，与 `write_state`/`append_event` 同持
`logs.trade_log_io.ID_ALLOC_LOCK`；`resolve_log()` 对同 id 多 open 输出
`duplicate_open_count` 标记（此前第二笔 open 被静默吞掉）。

## 既有记录的迁移（需 PM/Quant 确认，dev 不擅自改写 ledger）

待确认问题：**11:24:05 的第二笔 _001 是独立仓位还是双击误提交？**（两条 open 字段接近）

- 若为**独立仓位**：将 11:24:05 的 open 重编号为 `2026-06-03_bcd_003`（直接编辑该行 id），
  并确认 13:31 的 correction 目标是哪一笔（correction 行的 fields 与哪笔成交一致）；
  归因统计（BCD 家族 D1 状态机读 ledger）在迁移完成前按 `duplicate_open_count` 标记行保守处理。
- 若为**双击误提交**：对 11:24:05 那行补一条 `void` 事件（`target_event: open` + note 说明），
  保持 append-only 纪律，不删行。

**在迁移决定落地前**，D1 状态机（SPEC-123 §1）对带 `duplicate_open_count>0` 的 id
按"1 笔持仓"计（resolve_log 现行为），并在 Telegram 文案中注明该 id 待迁移。
