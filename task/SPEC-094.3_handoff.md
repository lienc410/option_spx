# SPEC-094.3 Handoff — Q042 Fill 确认闭环（幽灵仓位防护）

Developer 实施记录，2026-07-11。改动留工作区未 commit（按任务纪律）。

---

## ① 文件 ↔ F 项对照

| 文件 | F 项 | 内容 | Diff 规模 |
|---|---|---|---|
| `production/q042_executor.py` | F1 | 新增 `_check_pending_fills()`（每日确认提醒 + T+5 兜底释放 + phantom 标记）+ `run_eod_evaluation` 调用点（settle/状态级到期清理之后、`update_sleeve_*` 之前，独立 try/except 隔离，AC16） | +128 行 |
| `production/q042_positions.py` | phantom 过滤 | `get_active_positions` / `settle_expired_positions` / `get_active_committed_debit_usd` / `get_lifetime_stats` 四处 `if t.get("phantom"): continue`（视同 void） | +8 行 |
| `web/server.py` | F2 | `api_q042_position_open` 尾部回写 `state[sleeve].active_position_id/expiry`（幂等：相同 id 不动；不同 id → ACTION 告警不覆盖；整段 try/except 隔离，state 同步失败不影响记账成功响应）；响应新增只增字段 `state_synced`/`state_conflict` | +45 行 |
| `tests/test_spec_094_3.py` | AC-94.3-1..6 | 新建，13 tests，密闭房规同 094.2（磁盘面 tmp 重定向 + gateway recorder） | 新文件 |

账本 schema：新增可选 `phantom: true` 字段（spec 要求）+ 可选 `phantom_date`（审计链附带，见 ④-4）。
未触碰：trigger/armed/re-arm 状态机、sizing、cap、`compute_gate`、`_format_alert`（AC14.1 字段集）、AC16 结构——diff 除新函数与调用点外零改动既有行（仅 `_q042_append` 后返回语句改为携带新字段）。

## ② AC 逐条验收

| AC# | 结论 | 证据（tests/test_spec_094_3.py） |
|---|---|---|
| AC-94.3-1 | **PASS** | `test_ac1_daily_reminder_fyi_state_untouched`：entry T-3（2026-07-02→07-08，n=3 交易日）→ 恰 1 条 **FYI**，dedupe `q042_fill_reminder_A-2026-07-01_2026-07-08`，正文含"第 4 天未确认""T+5 自动释放"；state 双字段不动；账本无 phantom |
| AC-94.3-2 | **PASS** | `test_ac2_t5_release_phantom_action_and_same_day_fire`（端到端）：entry T-6（n=6≥5）→ 账本打 `phantom:true`（settled 仍 false，不删）+ ACTION"幽灵仓位已释放…立即补录并手工恢复 state" + state 双字段清空；**同日 ddATH −5% 场景 sleeve A 正常 fire**（`fired` 含 A，state 槽位变为 `A-2026-07-08` 新仓），armed 由 fire 消耗、释放不回补。附加 `test_ac2_release_slot_mismatch_keeps_state`：槽位 id 与记录不符时只打 phantom + 告警（正文注明"未清动"），不动槽位 |
| AC-94.3-3 | **PASS** | `test_ac3_backfilled_record_unaffected_after_t5`：`fill_debit` 已回填 + entry T-6 → 账本 bytes 逐字节不变、槽位保留、零提醒零释放 |
| AC-94.3-4 | **PASS** | 5 tests：committed（$50k phantom → `get_active_committed_debit_usd`=0）/ settle（expiry 已过的 phantom 行返回 `[]` 且账本 bytes 不变）/ lifetime stats（防御性：即使 phantom 被人为标 settled+exit_pnl 也不计入）/ `get_active_positions`（跳 phantom 取真实记录；仅剩 phantom → None）/ F6 端到端（phantom $50k、NLV $500k → `combined_bp_pct`=0.0） |
| AC-94.3-5 | **PASS** | 3 tests：正常回写（trade_id/expiry 落 state，`state_synced:true`，零告警）/ 冲突（state 已有不同 id → 不覆盖 + ACTION `q042_open_state_conflict_{trade_id}` + `state_conflict` 载明双 id，账本记录仍成功写入）/ 幂等（槽位已 == 即将生成的 id → state bytes 一字不动，零告警） |
| AC-94.3-6 | **PASS** | `test_ac6_dry_run_zero_disk_zero_push`（hash 比对，沿 AC-94.2-5 模式）：fixture 同含释放档（T+6）与提醒档（T+3）+ would-fire 场景 → paper/live/state/gate log 四面 bytes 前后一致 + `pushes == []` |

## ③ 回归数字

- **主回归**（任务指定命令）：`venv/bin/python -m pytest tests/test_spec_094_2.py tests/test_spec_094_3.py tests/test_spec_135_3.py tests/test_state_and_api.py -q` → **64 passed, 0 failed**（其中 SPEC-094.2 硬 invariant 22 tests 全绿；094.3 新增 13 tests）。
- **相邻 q042 面**（自主加测）：`test_spec_104 / 108 / 108_1 / 125 / 119 / 135_5` → **140 passed + 4 subtests passed**。
- **import 冒烟**：`production.q042_executor` / `production.q042_positions` / `web.server` 三模块 import OK。
- **真实 repo dry-run**：`venv/bin/python -m production.q042_executor --dry-run` → `data/q042_state.json` sha256 前后一致；`q042_paper_trades.jsonl` / `q042_live_trades.jsonl` / `q042_gate_log.jsonl` 本机不存在且未被创建 → **零落盘 PASS**。（本机无 `sleeve_governance_runtime.json` → F3 fail-closed 警告属 dev 机预期，dry-run 下无告警无 gate log 追加，语义正确。）

## ④ 取舍 / 歧义诚实记录

1. **F1 位置 vs spec"末段"字样（最重要，请 Quant 裁决）**：spec F1 写"`run_eod_evaluation` 末段，settle 之后"，但 AC-94.3-2 要求"释放**同日** ddATH ≤ -4% 场景下 sleeve 可正常 fire"。`update_sleeve_a` 的 fire 条件含 `not has_pos`——若扫描真放末段（update_sleeve 之后），释放当日 fire 已被幽灵槽位挡掉，AC-2 端到端不可能成立（也复刻不了 2026-06-10 counterfactual）。**实施取位 = settle + 状态级到期清理之后、`update_sleeve_*` 之前**："settle 之后"强约束保持（已到期行先 settle，F1 显式跳过 expiry≤today 行），且释放先于 F6 使 committed 当日即排除 phantom。按 AC（可验证行为）> 位置副词的优先级实施，未改 spec 一字。
2. **"不在范围内：Sleeve B" 的解读**：F1 spec 文本本身是 sleeve 参数化的（"Q042 [sleeve]"、`state[sleeve].active_position_id`），故扫描按字面覆盖两 sleeve 记录；out-of-scope 的 "Sleeve B" 解读为 "Sleeve B 策略语义零变更"（对齐 094.2 同位置措辞 "Sleeve B 任何变更"），而非"扫描跳过 B 记录"。F2 端点两 sleeve 均回写（端点本就接受 A/B）。若 Quant 认定应字面跳过 B，改动为 `_check_pending_fills` 内加一行 sleeve 过滤，测试不受影响（全部用 A）。
3. **释放时槽位 id 不匹配**：spec 未规定。实施为保守取向——只打 phantom + ACTION（正文注明槽位"未清动"并给出现值），不动槽位（它可能指向另一真实仓，清掉会破坏 no-overlap）。
4. **`phantom_date` 附加字段**：spec 只要求 `phantom: true`；额外写入 `phantom_date`（释放日）以保审计链可追溯。可选字段、只增，任何读方不感知。
5. **trade_id 合成口径**：executor 写的 pending 记录本无 `trade_id` 字段（AC17 schema 未动）。dedupe key / 告警用 `rec.trade_id or f"{sleeve}-{signal_date}"` 合成——与 `get_active_positions` 现行合成完全同口径；手动记录（有 `trade_id`，带 -NNN 后缀）直接用真值，与 F2 回写的 state id 精确匹配。
6. **每日提醒计数约定**：n = entry_target_date 之后经过的交易日数（`strategy.q078_ladder.trading_days_between`，复用其 2025-2026 假日表，不建 mirror）。entry 当日 n=0 即发"第 1 天"提醒；n∈[0,4] 共 5 个提醒日，n≥5 释放——对齐 spec"连续 5 日提醒未获响应即释放"。**假日表只覆盖 2025-2026**：表外年份退化为纯周末口径（T+5 可能提早 1-2 个交易日到达），2027 前需扩表或切 `pandas_market_calendars`（repo 已有依赖，见 `strategy/intraday_governance.py`）。
7. **gateway about/category 取值**（spec 未指定，按 gateway ratified forms）：每日提醒 = FYI/"新开仓"（AC-1 钉了 FYI 档）；幽灵释放 = ACTION/"系统状态"；F2 冲突 = ACTION/"系统状态"。三者均独立消息独立 dedupe key，AC14.1 触发告警格式零触碰。
8. **dry-run 释放对 deep-copy state 推演**（清槽位 → 当日 would-fire 在 log 可见），零落盘零推送——与 094.2 settle 的 dry-run 推演语义对称，使 dry-run 输出忠实预演真跑行为。
9. **`q042_concentration_monitor` 未加 phantom 过滤**：其样本仅含 settled + exit_pnl 记录，phantom 永不进 settle → 天然免疫；spec/任务列的四个过滤点已全覆盖，不扩面。
10. **F2 冲突告警失败不阻塞**：告警 push 包在内层 try/except，账本已写入的 200 响应永远返回（`state_conflict` 字段仍载明冲突，前端可见）。
11. **backtest 缓存**：本次全部改动在执行层（executor/positions/server），未触碰任何回测用策略算法文件，Q041/ES/SPX 三套磁盘缓存**无需刷新**。

## ⑤ 给 Quant 的复核提示

1. **裁决 ④-1**：F1 取位（update_sleeve 之前）是本实施唯一与 spec 字面（"末段"）有出入的点，AC-2 语义强制。若裁决为"保持末段 + 放弃同日 fire"，需 PM 修订 AC-2 后返工。
2. **裁决 ④-2**：Sleeve B 记录是否纳入 F1 扫描（现纳入）。
3. **真实数据对数（Developer 无法执行项）**：old Air 部署后构造/等待首个 pending 场景，核对 ①每日 FYI 到达且 dedupe 正确 ②T+5 释放 ACTION 文案与 state 清理 ③释放当日 gate log 无异常。rollback 条款：首次 T+5 若误清真实仓位 → 按 ACTION 指引补录 + 手工恢复 state；连续 2 次误释放 → 回 Quant 复核 T+5 参数（spec §Failure/rollback）。
4. **运维提示**：假日表 2027 到期（④-6）；F1 对 `strategy/q078_ladder` 新增一个 import 依赖（纯函数，无 IO）。
5. **AC-8（094.2）周一形式核查**不受本次影响：gate 读数路径零触碰。
6. 复核入口：13 tests 在 `tests/test_spec_094_3.py`，单跑 `venv/bin/python -m pytest tests/test_spec_094_3.py -q`；交易日事实锚（2026-07-03 假日）注释在文件头。

---
实施：Developer（Claude），2026-07-11。工作区未 commit。
