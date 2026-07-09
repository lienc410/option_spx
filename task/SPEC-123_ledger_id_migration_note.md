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

## 既有记录的迁移（SPEC-137 §2 落地，2026-07-08）

**判定：双击/重试误提交**（非独立仓位）。依据：两条 open 相隔 2s、字段接近；
成因正是 ID_ALLOC_LOCK 修复所封的 id 分配竞态（分配早于数秒的 governance 评估，
两个并发提交各自算出 `_001`）；D1 状态机一直按"1 笔持仓"处理该 id。

**为何不用 §4a 原列的 `void`**：id 级 `void` 会把整个 `_001`（含第一笔真实 open）
一并作废。改用 **append-only 消歧 correction**：

```json
{"id": "2026-06-03_bcd_001", "event": "correction", "target_event": "open",
 "fields": {}, "duplicate_open_resolution": "collapse", "note": "..."}
```

`resolve_log()` 见到 `duplicate_open_resolution == "collapse"` 即：保留第一笔 open、
`duplicate_open_count → 0`、**不 void 仓位**；13:31 的 correction 目标随之不再歧义
（只剩一笔 open）。id 不变 → campaign 归组复核不变。

**落地方式**：`scripts/spec137_dup_id_migration.py`（append-only + 幂等，重跑 no-op，
不改/删既有行）。**在 oldair 上运行一次**即完成迁移；未运行前 `duplicate_open_count`
仍为 2，D1 状态机继续按"1 笔持仓"保守处理（resolve_log 现行为不变）。
