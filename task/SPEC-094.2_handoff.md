# SPEC-094.2 Developer Handoff（2026-07-10）

实施人：Developer（Fable 5 lane）。工作区 diff 未 commit，留待 Quant review。
中途因 API 中断一次；恢复后在**新 HEAD（4691f66，含 SPEC-137/138 合入）上全量重验**，详见 §3。
**2026-07-10 补充**：Quant 裁决 §④-1 为 spec 文件清单 clerical 漏列并修订 Handoff Contract §1、授权补 AC-9 消费端——`web/server.py` + `scripts/daily_snapshot.py` 两处小改与 2 个消费端测试已完成，AC-9 转全 PASS。

---

## ① 改动文件清单（每处对应 F 项 / B 项）

spec §Handoff Contract 第 1 条列出的 4 个文件 + Quant 2026-07-10 授权补列的 2 个消费端文件 + 新测试文件：

### `strategy/q042_gate.py` — F3 / B1 / N12
- 新增 `RUNTIME_STATE_PATH`（`data/sleeve_governance_runtime.json`）与 `_STALE_TRADING_DAYS=2`。
- **`read_main_bp_detail()`（新）**：fail-closed 读 `pools.spx_pm_bp_pct`（all view，PM ratify 定案），返回 provenance dict（value/source/timestamp/reason/all_view_pct/schwab_view_pct）。B1 全部判据落实：缺文件、parse 失败、缺/坏 timestamp、staleness >2 交易日、`status != "available"`、`errors` 非空、`basis_degraded`、degraded 全零形态（`pools_by_view.schwab` null **或** `pools.nlv_basis` 缺失/≤0）、plausibility gate（`spx_pm_bp_pct ≤ 0`，含 NaN/Inf 防御）。**无 last-known 回退**。
- **`read_main_bp_pct()` 重写**：签名 `-> Optional[float]`，None = fail-closed（替换旧 fail-open `return 0.0`；旧实现读的 `bp_pct_account` 生产从不存在，44/44 行 0.0 实锤）。
- `read_main_bp_source()`：N12 供 executor 取 provenance 记 gate log。
- **`log_gate()` 扩展**：可选 `bp_source` 字段（N12）；`result=None`（fail-closed）时写一行 `main_bp_pct: null / gate_available: false / allowance 全 0` 的 unavailable 行，保持日度台账连续可审计（schema 只增：`bp_source`/`gate_available`）。
- **`log_blocked_fire()`（新）**：F5.2 blocked record，`blocked_fire: {sleeve, reason, would_be_contracts, ddath}` 追加至 gate log。
- `_business_days_between()`：staleness 用 Mon–Fri 工作日近似"交易日"（见 §④ 取舍 2）。
- `compute_gate()` / allowance 公式 / cap 常数**一行未动**（invariant）。

### `production/q042_positions.py` — F2 / B4 / N9 / N11 + F6 helper
- **`_derive_expiry()`（新，F2 三级推导）**：① record 显式 `expiry` → 直接用；② `entry_target_date + dte` calendar days；③ legacy `signal_date + 90`。锚点 R-20260510-15，同时修 Sleeve A 错 61 天与 Sleeve B off-by-one。缺日期字段返回 None + log warning，**不抛异常**（B4）。
- `get_active_positions()`：expiry 改走 `_derive_expiry`（事件过滤原本就有，保留）。
- **`settle_expired_positions()` 重写**：
  - 签名 `(spx_close, today=None, paper=True, dry_run=False)`——N9 `today` 由 executor 传数据日；
  - B4：跳过 `event != "open"` 行（修 note 行 `strptime("")` ValueError 杀死整个 EOD 的静默死亡路径）；
  - B6：`dry_run=True` 只算 would-settle 列表，账本与 state 都不落盘；
  - N11：整文件重写改 `_atomic_write_jsonl()`（tempfile.mkstemp + os.replace）；
  - settle 后清 state 的 AC20 逻辑保留（加 key 存在性防御）。
- **`get_active_committed_debit_usd()`（新，F6 helper）**：扫 PAPER_LOG + LIVE_LOG 两账本，未 settle 且未过期 open 记录的 `(fill_debit or est_debit) × contracts` 求和。**B2 单位契约在 docstring 钉死：debit 已是每张合约美元，不再乘 multiplier**。
- `Q042Position.is_active` / `days_to_expiry` 对空 expiry 容错（B4 连带）。

### `production/q042_executor.py` — F1 / F4 / F5 / F5b / F6
- `_send_telegram` → **`_send_gateway()`**（通用化：category/about/title/dedupe_key 参数化；SPEC-126 gateway 路径不变）。**以工作区/新 HEAD 的 "Drawdown Overlay（回撤加仓）" 文案为基线**（该文案已随 SPEC-137/138 合入 HEAD，未覆盖回旧文案）。
- **`_cash_context_line()`（F5b/AC14.1）**：`Liquid cash $X · 在场 debit 合计 $Y`（源 `strategy.cash_budget_governance.get_current_liquid_cash` / `get_open_debit_total_usd`），整体 try/except，失败降级 `n/a`，永不阻塞告警（AC16）。追加于**所有** trigger 告警（正常 fire、blocked、gate 不可用）正文末尾；`_format_alert()` 既有字段集一字未动（AC14 invariant）。
- **`_process_sleeve_fire()`（新）**：单 sleeve fire 的统一处理——gate 检查 → would-be sizing → fire 或 F5 blocked 路径：
  - blocked 原因三类：`gate_unavailable`（F3 fail-closed）/ `gate_binding_allowance_0` / `contracts_0`；Sleeve B allowance=0 专用 `sleeve_b_production_cap_0_by_design`；
  - N2：by-design 拦截降 FYI，其余 ACTION；
  - N6：gate_unavailable 的 blocked 告警与 F3 数据不可用 ACTION 共用 dedupe key `q042_gate_unavailable_{date}`（gateway 层同日合并为一条）；其他 blocked 用 `q042_blocked_{sleeve}_{date}`；正常 fire 保持 `q042_trigger_{sleeve}_{date}`；
  - N7：blocked 文案含"人工入场须经 /api/q042/position/open 记录并同步 trigger state"提示；
  - blocked 时**不写 active_position_id**（armed 已由 `update_sleeve_a/b` 内部消耗——trigger 语义 invariant，未动）；
  - B6：dry-run 下 blocked record 不落盘、告警不发（log-only would-block 明细）。
- **`run_eod_evaluation()` 重排**：
  - **F1**：settle（paper+live 两账本，N9 传 `today_str`，B6 传 `dry_run`）→ **然后** `load_state()`（N3 顺序：绝不跨 settle 持有同一内存副本）→ 状态级到期清理（`active_position_expiry <= today` 清双字段）+ settle 返回 sleeve 幂等双清 → 全部在 `update_sleeve_a/b` **之前**（到期日当日可 re-fire）；
  - **F3**：`read_main_bp_source()`；unavailable → gate=None、allowance=0、ACTION 告警（"Q042 gate 数据不可用，trigger 被保守拦截，请人工核查"+ 数据源/timestamp + 现金行）；`log_gate(gate, bp_source=...)` 每日照记（含 unavailable 行）；
  - **F4/B6**：dry-run 下 state 用 `copy.deepcopy` 推演（含 ATH 推进）、不 save_state、不写 pending record、不追加 gate log、不写 blocked record、不发任何 Telegram；stdout/log 打 would-fire / would-settle / would-block 明细。旧 `if sent or not dry_run` 反逻辑废除；
  - **F6/B2**：EOD 末尾 `combined_bp_pct = get_active_committed_debit_usd() / NLV × 100` 写回 state；**不乘 100**（debit 已 per-contract USD）；NLV=0 → 跳写保留旧值 + warning。N10 命名冲突已在代码注释注明（debit/NLV ≠ sleeve governance 的 maint/NLV）。
- `update_sleeve_a/b` 调用与状态机逻辑一行未动。

### `signals/q042_trigger.py` — F7（仅 snapshot 函数 + dataclass 一字段）
- `Q042Snapshot` 增 `ath_degraded: bool = False`（默认值，既有构造点不破坏）。
- `get_current_q042_snapshot()`：ATH 真值源 = state `ath_running_max`；state 缺失/为 0 → `ath_degraded=True` 且 fallback `ath = spx_close`（ddath 读 0，中性），**不再用短窗口最高价冒充 ATH**（旧行为会低估回撤）；默认 fetch 窗口 1mo → 6mo（展示需要）。walk-forward `get_q042_history` 未动。

### `web/server.py` — F7/AC-9 消费端前半（Quant 2026-07-10 授权，spec Handoff Contract §1 已修订补列）
- `/api/q042/state` 序列化 `ath_degraded` 字段（**只增不改**，`getattr(..., False)` 防御旧 snapshot 对象）。其余路由与字段未触碰。

### `scripts/daily_snapshot.py` — F7/AC-9 消费端后半（同上授权）
- 消费 `/api/q042/state` 时读 `ath_degraded`：为 true → stderr 记 WARNING（沿用该脚本既有 `[daily_snapshot] WARNING` 惯例）且 `regime.ddath_pct` 记 **null**（不把 0 填充值当真实回撤记数）；健康路径照常记数。其余字段与流程未动。

### `tests/test_spec_094_2.py`（新）
22 个测试覆盖 AC-94.2-1..9（含 2 个 AC-9 消费端测试：server 序列化 + daily_snapshot 跳数/warning），全部磁盘面（4 账本/state/gate log/runtime.json）+ gateway.push 重定向 tmp/recorder，符合 SPEC-130 密闭房规。

---

## ② 9 个 AC 逐条验证结果

| AC | 结果 | 证据（测试名 / 输出） |
|---|---|---|
| AC-94.2-1 | **PASS** | `test_ac1_f3_integration_smoke_reads_pool_value`：真实结构非 degraded runtime fixture（`pools.nlv_basis=629000>0`），`read_main_bp_pct()` 走完读文件→取字段链路返回 18.61；**零 monkeypatch 返回值**；timestamp 注入新鲜值过 staleness（N1）。`test_ac1_fixture_asserts_non_degraded_nlv_basis_positive` 断言 fixture 前提 |
| AC-94.2-2 | **PASS** | (a) `test_ac2a_missing_file_and_stale`（缺文件 + 5 天 stale）；(b) `test_ac2b_degraded_fixture`（2026-07-07 实测形态：pools 全零+views 全 null+basis_degraded+timestamp 新鲜）；(c) `test_ac2c_zero_bp_available_fresh`（bp=0 且 available 且新鲜 → `nonpositive_bp`）；`test_ac2_executor_blocks_fire_on_unavailable[×3]`：三例均 executor 拦 fire（fired=[]、无仓、无 pending record）+ ACTION 告警 + `blocked_fire` record（reason=gate_unavailable） |
| AC-94.2-3 | **PASS** | `test_ac3_settle_yesterday_expiry_then_fire`：昨日 expiry 合成账本**含 1 条 note 行**（B4）→ EOD 后 settled=true、旧仓清空、当日 trigger 正常 fire 并落新仓；`test_ac3_boundary_expiry_today_not_rolled_back`：expiry=当日 → 当日结算 + 当日 re-fire + EOD 末 state 为新仓（N3 无副本回滚） |
| AC-94.2-4 | **PASS** | `test_ac4_expiry_three_tier`：dte=30 → entry+30；dte=90 → entry+90（off-by-one 修复）；显式 expiry 优先；note 行无日期 → None 不抛 |
| AC-94.2-5 | **PASS** | `test_ac5_dry_run_no_disk_no_push`：fixture 含一笔已到期仓（B6 覆盖），四文件（state/paper/live/gate log）**字节级前后一致**，pushes 记录器为空（无 Telegram、无 pending record） |
| AC-94.2-6 | **PASS** | `test_ac6_gate_zero_blocks_sleeve_a`：main_bp=65% → allowance=0 → `blocked_fire`（reason=gate_binding_allowance_0）+ ACTION ×1；`test_ac6_fire_b_is_fyi_by_design`：fire_B → blocked record（reason=sleeve_b_production_cap_0_by_design）+ **FYI 级**、零 ACTION（N2） |
| AC-94.2-7 | **PASS** | `test_ac7_committed_debit_encoding`：est_debit=25000 × 2 ct = $50k committed（**不再乘 100**），NLV 500k → `combined_bp_pct=10.0` 写回 state；`test_ac7_nlv_zero_skips_write`：NLV=0 → 保留旧值 7.77；`test_ac7_snapshot_reflects_combined_bp`：`/api/q042/state` 所序列化的 snapshot 字段反映之 |
| AC-94.2-8 | **代码侧 PASS / 生产核查 PENDING** | `test_ac8_gate_log_has_bp_source_when_available`：gate log 行 `main_bp_pct=18.61>0` 且 `bp_source.timestamp` 非空、source 含 `spx_pm_bp_pct`。**部署后 old Air 首个交易日的人工 `tail -1` 核查按 spec 属 PM/部署清单**，非本次可交付。注意：dev 机无 `data/sleeve_governance_runtime.json`（文件在 old Air），dev 上 dry-run 如实 fail-closed（见 §③ 冒烟） |
| AC-94.2-9 | **PASS**（消费端于 2026-07-10 经 Quant 授权补完，见 §④-1） | 生产者侧：`test_ac9_snapshot_ath_degraded`（state ath=0 → `ath_degraded=True` 且 ATH **不取**窗口最高价）+ `test_ac9_snapshot_ath_healthy`（ddath=-10% 精确）。消费端：`test_ac9_server_serializes_ath_degraded`（`/api/q042/state` 透出 ath_degraded true/false 两态）+ `test_ac9_daily_snapshot_skips_ddath_when_degraded`（degraded → stderr WARNING + `regime.ddath_pct=null` 不记数；健康 → 照常记 -5.25） |

---

## ③ 相邻回归结果（新 HEAD 4691f66 重验）

中断恢复后确认：HEAD 前移 3 commit（SPEC-137/138），其中 `production/q042_executor.py`（告警文案 2 处）、`strategy/cash_budget_governance.py`（`evaluate_cash_collateral_budget` 缺轨 advisory）、`strategy/sleeve_governance.py`（告警文案 1 处）被其他 lane 合入。逐一核对交互面：

- executor 合入仅为文案改动，我的工作区版本**本就以该文案为基线**（任务要求），无冲突；
- SPEC-138 F6 只改 `evaluate_cash_collateral_budget` 内部；我的 F5b 只调 `get_current_liquid_cash` / `get_open_debit_total_usd`，两者签名与返回结构未变，**无交互**；
- sleeve_governance 合入不触及 runtime.json 结构，F3 判据不受影响。

回归执行（全部在新 HEAD、venv python 3.12）：

| 套件 | 结果 |
|---|---|
| `tests/test_spec_094_2.py`（本 spec，AC-9 消费端补完后 22 tests） | **22 passed** |
| `test_spec_104 / 103 / 111 / 115_cash_collateral / 118 / 138 / q041_paper_log / q041_t3_governance` | **100 passed** |
| `test_spec_108 / 108_1 / 135 / 135_3 / test_state_and_api` | **101 passed（+4 subtests）** |
| AC-9 补完后 server 面重验：`test_spec_135_3 + test_state_and_api`（web/server.py 被碰） | **29 passed** |
| import 冒烟：4 个改动模块 | OK |
| `python -m production.q042_executor --dry-run --verbose`（2026-07-10） | fired 0；F3 如实 `missing_file` fail-closed（dev 机无 runtime.json，预期）；F6 NLV=0 跳写；**state mtime 不变、gate log / paper log 未创建、零推送** |

注：中断前旧 HEAD 上曾见 2 个失败（`test_state_and_api` 的 backtest-cache 项、`test_q041_paper_log` ac6），当时已用 stash 法证明与本改动无关（无我的 diff 也同样失败）；两者均已被 SPEC-137/138 合入的测试修复**在新 HEAD 上转绿**。当前相邻回归零失败。

（无 `tests/test_spec_094*.py` 旧测试存在——本 spec 测试是第一份。）

---

## ④ Spec 歧义 / 无法实施项 / 判断取舍（诚实记录）

1. **AC-94.2-9 消费端半句与文件边界矛盾——已解决（Quant 2026-07-10 裁决 + 授权）**：原始矛盾：F7/AC-9 要求 "daily_snapshot 消费端遇 degraded 标记时记 warning 不记数"，但 Handoff Contract §1 只列 4 个文件（F7 注明"仅 snapshot 函数"），且消费端实施必须同时改 `web/server.py`（`/api/q042/state` 原不透出 `ath_degraded`）与 `scripts/daily_snapshot.py`。按角色纪律先停下记录。**裁决**：Quant 判定为 spec 起草时文件清单 clerical 漏列，已修订 Handoff Contract §1 补列两文件并授权实施。已按授权补完（见 §① 末两条 + AC-9 两个消费端测试），server 面相邻回归重验通过。
2. **staleness "交易日" 用 Mon–Fri 工作日近似**（无 holiday calendar 依赖）。节假日会使近似计数 ≥ 真实交易日数 → staleness 更早触发 → 方向**保守**（fail-closed 提前而非滞后），与 B1 精神一致。
3. **B6 gate log 二选一**：spec 给了 "不追加 或 写 dry_run:true 标记行"，我选**完全不追加**（AC-5 按字节不变验收，最干净）。
4. **F3 unavailable 时 gate log 仍写一行 unavailable 记录**（`main_bp_pct: null, gate_available: false, allowance 全 0, bp_source 含 reason`）。spec 未明说 unavailable 当日 gate row 怎么办；我判断日度台账连续性 + fail-closed 事件可审计性优于留空。schema 只增字段，旧行不受影响。
5. **`read_main_bp_pct` 返回类型 float → Optional[float]**：spec 明确要求"返回 None"，这是有意的签名变化；全 repo 唯一调用方是 executor（已同步）。
6. **dry-run 下 F3 数据不可用 ACTION 也不发**（log-only）：F4 "不发 Telegram" 按字面覆盖全部推送类别。
7. **blocked 时 would-be sizing 照算**（含 gate unavailable 场景），保证 counterfactual record 有值（F5 惯例对齐）。
8. **F6 排除"已过期但未 settle"记录**：F6 spec 口径 = "未 settle 且未过期"（与 F1 同口径）；executor 中 F6 在 settle 之后运行，正常日两者一致；账本残留过期未结算记录时不计为 committed。
9. **`_send_telegram` 更名 `_send_gateway`**：模块内部 helper（无外部引用），为 F5 多类别推送参数化；gateway 调用路径与 escape 边界（H-4）不变。
10. **F7 fallback 值选 `ath = spx_close`**（degraded 时 ddath=0 中性）而非窗口 max：窗口 max 恰是 spec 要消灭的"冒充 ATH"行为；ddath=0 不会误触发（-4%/-15% 都不可能达到），消费端凭 `ath_degraded` 跳过记数。
11. **部署提示（非代码）**：边界条件要求 F1 首跑前备份 `q042_state.json` 与两账本——这属部署清单动作；同批建议按 N13 核查 old Air governance snapshot 写入方（bot 09:40 cron）存活，F3 自此对其有运维依赖。

## ⑤ 给 Quant reviewer 的重点复核提示

1. **F3 判据 ↔ sleeve_governance 真实字段的映射**（`strategy/q042_gate.py::read_main_bp_detail`）：尤其 degraded 全零形态判据我实现为 `pools_by_view.schwab is None **or** nlv_basis 缺/≤0`（spec 原文 "为 null 或 pools 缺 nlv_basis"），以及 plausibility gate 对 NaN/Inf 的处理。fixture 结构对照 `current_governance_state()` 输出，但**建议拿 old Air 真实 runtime.json 跑一遍 `read_main_bp_detail()` 对数**（dev 机没有该文件，我只能按代码真值构造）。
2. **N3 顺序**：executor 里 settle → load_state → 状态清理 → update_sleeve_* → save_state 的链条（`run_eod_evaluation` 前 40 行），`test_ac3_boundary_expiry_today_not_rolled_back` 是护栏，但值得人眼再过一遍。
3. **B2 单位**：`get_active_committed_debit_usd` 与 executor F6 除法（`production/q042_positions.py` / `q042_executor.py` 末段），AC-7 钉死 10.0%。
4. **dedupe key 拓扑（N6）**：`q042_gate_unavailable_{date}`（F3 告警 + gate_unavailable blocked 共用）/ `q042_blocked_{sleeve}_{date}` / `q042_trigger_{sleeve}_{date}` 三类——测试里 gateway 被 recorder 替换，**真实 dedupe 合并行为未过集成**（依赖 SPEC-126 gateway 既有测试）。
5. **§④-1 的 AC-9 消费端缺口已按 Quant 2026-07-10 授权补完**（server 序列化 + daily_snapshot 跳数），两处均为最小增量改动，建议顺带过目 `scripts/daily_snapshot.py` 的 null 语义与下游 journal 图对 null ddath 的兼容（`_r(None)` 返回 None，与既有 partial 行为一致）。
6. armed 消耗语义、`update_sleeve_a/b`、compute_gate 公式、`_format_alert` 字段集、sizing/DTE/cap 常数——全部 invariant，diff 里应看不到任何触碰；若看到即是我错。
