# SPEC-094.2 独立审计回复（2nd Quant Review — 最终稿）

**Date**: 2026-07-08
**Reviewer**: 2nd Quant（独立会话，与 1st Quant 无共享上下文）
**Review target**: `task/SPEC-094.2.md`（Status: DRAFT）
**Packet**: `task/SPEC-094.2_2nd_quant_review_packet_2026-07-07.md`

**Verdict: PASS WITH REVISIONS**（blocking 6 项 / non-blocking 13 项，见 §5）

方法声明：C1–C7 全部由本 reviewer 自行读源码 / 自跑 grep / 自复算 CSV 到 file:line，未采信 1st Quant 结论转述。生产侧读数（gate log 44/44 恒 0、NLV $629k、账本不存在）按 packet §2 末尾约定采信 `doc/q042_aftermath_synergy_audit_2026-07-07.md` §1。§2-3.1 的今日量化使用 `research/q091/q091_p0_snapshot.json`（2026-07-07 22:15 ET 双 broker live 快照，本审计已直接读取原始 JSON 核数）。本路径下曾存在一份同任务中断残稿；其独有论点（q091 实测数、C7 净额更正、Sleeve B off-by-one、maint-None 静默零通道）已由本 reviewer 逐条独立复核后并入，未经复核的内容一律未保留。

---

## 1. C1–C7 逐条复核

### C1 — `bp_pct_account` 生产无 writer，gate 恒 0 ✅ CONFIRMED

- `strategy/q042_gate.py:98-115`：`read_main_bp_pct()` 经 `strategy.state.read_state()` 取 `pos.get("bp_pct_account", 0.0)`；`:114-115` 任何异常 `return 0.0`（fail-open）。
- `strategy/state.py:218-227`：无仓时 `read_state()` 返回 `None` → `None.get` 抛 `AttributeError` → except → 0.0；有仓时 flat dict 字段来自开仓 `state_payload`。
- `web/server.py:5422-5442`：`state_payload` 字段全枚举，**无** `bp_pct_account`（packet 指针 5406 是其上方注释行，实际构造起于 5422，不影响结论）。
- 全仓 grep：writer 仅 `backtest/engine.py:130/359/396`（回测 Trade dataclass）、research 脚本、`web/server.py:7165`（回测渲染）、tests。生产 position-state 路径零 writer。
- 两条路（无仓异常 / 有仓缺字段）都恒 0，与生产 44/44 条 `main_bp_pct=0.0` 完全一致。

### C2 — `settle_expired_positions` 零调用方；fire 后 `has_pos` 永真 ✅ CONFIRMED

- grep 全仓唯一命中 = 定义行 `production/q042_positions.py:131`，零 caller。
- `production/q042_executor.py:185-270` 通读：无 settle 调用、无到期清理；fire 时 :244-245/:262-263 置 `active_position_id` 后无任何清除路径。
- `signals/q042_trigger.py:147/156`：fire 条件含 `not has_pos` → 一次 fire 该 sleeve 永久静默。
- walk-forward 对照：`signals/q042_trigger.py:329-337` 每日先清 expiry 再推状态机——研究有清理，live 没有。

### C3 — `_expiry_from_signal` 硬编码 signal+90 ✅ CONFIRMED（且比 packet 表述更糟一档）

- `production/q042_positions.py:82-84`：两 sleeve 一律 signal+90；被 `get_active_positions:111` 与 `settle_expired_positions:145` 共用。
- 锚点真值：`RESEARCH_LOG.md:912` R-20260510-15（`_exp_date` fast-path fix）= expiry 从 **entry（T+1）+ DTE** 起算；executor（`q042_executor.py:225-227`）与 walk-forward（`q042_trigger.py:345/357`：signal+31 / signal+91）均已按此实现。
- **加重项（packet 未提）**：`_expiry_from_signal` 对 Sleeve A 错 **61 天**（signal+90 vs entry+30=signal+31），对 Sleeve B 也错 **1 天**（signal+90 vs entry+90=signal+91）——settle 接线后 B 仓会提前一日用错误结算价结算。F2 三级推导恰好两者都修，结论不变，披露应补全。
- **引证 nuance**：SPEC-094.1 §2.3 表格字面写 "signal + 30 calendar days"（`task/SPEC-094.1.md:84`），entry 锚点是 R-20260510-15 的后续修正、094.1 文本未同步——F2 应引 R-20260510-15 为出处并给 094.1 记 errata（N8），防未来拿 094.1 字面反咬 F2。
- 手动 open 端点确认：`web/server.py:2701/2715` `expiry` 为**必填**——F2 tier-1 前提成立。

### C4 — dry-run 不 dry ✅ CONFIRMED

- `q042_executor.py:240/258`：`_send_telegram` 无条件调用；`:241-242/259-260`：`if sent or not dry_run` → dry-run 下发送成功反而**会**写 pending record；`:265`：`save_state` 无条件（含 :210-212 ATH 推进持久化）。
- 补充：`:221` `log_gate(gate)` 同样无条件 append——dry-run 会写 gate log 重复日期行，F4 现文本没覆盖（并入 B6）。

### C5 — `combined_bp_pct` 无 writer，monitor 恒 "ok" ✅ CONFIRMED

- 唯一"writer" = `signals/q042_trigger.py:92` 默认 0.0；`:272` 读、`web/server.py:2236-2245` 读（`:2239` 恒 "ok"）、`scripts/daily_snapshot.py:397` 消费死值。SPEC-104 cap utilization monitor 确认是盲的。
- 附注：`strategy/sleeve_governance.py:526` 的 pools 里有同名字段（(spx_maint+es)/nlv，maint 口径），不同文件不同义——F6 需注明（N10）。

### C6 — `pools.spx_pm_bp_pct` 存在且日度持久化 ✅ CONFIRMED（附两条关键保留 → B1）

- 字段构造 `sleeve_governance.py:519-528`（`_pools_for_view`）；back-compat `pools` = "all" view（:803-826）；写盘 `record_state_snapshot`→`_write_json(RUNTIME_STATE_PATH, state)`（:1240-1271）；路径 = `data/sleeve_governance_runtime.json`（:23）。
- **日度节奏 repo 内可证**：bot cron **mon-fri 09:40 ET**（`notify/telegram_bot.py:1814-1821` `scheduled_ladder_shadow_push` → `record_state_snapshot`）+ `scripts/sleeve_governance_daemon.py:16`（launchd 候选）。
- **保留 1（degraded 全零 fallback）**：NLV 不可得时 `_pools_for_view` 返回 None，`pools` 落到 :804-811 **全零 dict**、snapshot 照写、timestamp 新鲜。本机 `data/sleeve_governance_decisions.jsonl` 最后一条（2026-07-07T23:31:55，Schwab 未认证环境）实测正是该形态：pools 全零 + pools_by_view 全 null + `basis_degraded: true` + last-known basis $1.24M 存在。F3 的三条件（缺文件/stale/**basis_degraded 且无 last-known**）在此形态下**全不触发** → 读 0.0 → dead-gate 换文件复活。
- **保留 2（maint-None 静默零）**：`web/portfolio_surface.py:366-379` broker 余额部分不可用时 `maintenance_margin` 可为 None → `sleeve_governance.py:750` `_num(None) or 0.0`，**不进 errors、status 仍 "available"、basis_degraded 仍 False**（NLV 读到即可）→ `spx_pm_bp_pct` 静默变小/变零，F3 三条防线同样全部旁通。这与 C1 同属 silent-zero fail-open 类，是 SPEC-089/094 `net_liquidation` key-mismatch 之后该类问题**第 3 次**出现（`feedback_spec_integration_test` 谱系）。两条通道合并为 **B1**。
- **保留 3（all view 混基）**：`pools` = (schwab_maint+etrade_maint)/(schwab_nlv+etrade_nlv)（:508-514），而 Q042 sizing 用 Schwab NLV 单基（`q042_executor.py:143-151`）。今日实测差 1.8pp（见 §2-3.1），经济上可接受，但须 PM 显式 ratify（N5）。

### C7 — Q093 P1 重放否决现金闸门 ✅ 方法学 CONFIRMED；findings §3 净额聚合有误（方向反而更强）

- **数字复算**（`research/q093/q093_p1_cash_stack.csv`，19y/$152k/today_78.6k）：ISO 35/35 pass、0 overdraft、0 breach、max_committed $97,469.85；GOV 32/35、`q042_pnl_foregone=$243,758.76`、`main_block_delta=+7`、`main_pnl_foregone_delta=+$37,338`；VIS Δ+8/$36,016；$90k 池 breach=8/od=1、$37k 池 breach=42/od=35——findings §1/§2 全部对上。
- **生产语义对齐 ✓**：floor = 入场前 `liquid < $30k`（脚本 :138 = `cash_budget_governance.py:279`）；cap = `(committed+need) > 60% × liquid`（:139 = `:301-304`）；静态池假设 findings §4 已披露且方向保守。
- **符号约定 ✓**：`_is_debit` 用 `entry_credit > 0`，经 `backtest/engine.py:97-103` 注释确认 positive = debit paid，正确。
- **Q092 基线 ✓**：脚本内同 replayer 跑 main-only 基线做 delta 校验（:169-170）；107/107 声明与结构自洽（本审计未重跑 19y 全量，此点为采信项，已标注）。
- **发现的错误（N4）**：findings §3 写「-$244k vs 保护 +$37k，净 **-$207k**」——CSV 里 GOV 的 `main_pnl_foregone_delta=+$37,338` 是 GOV 情景下主 debit 侧**多被挡 7 笔的代价**（ISO 下 Δ=0），不是"保护"。GOV 真实净成本 = **-$281k**。$152k 池 overdraft=0，闸门根本没有可保护对象。方向不变、否决更强，但这正是 `feedback_unquantified_caveat_sign_risk` 型符号错误，findings 与 packet C7 措辞都应更正。**F5b 依据经更正后依然成立且更强**。
- F5b 数据源确认 ✓：`strategy.cash_budget_governance` 的 `get_current_liquid_cash()`（:72）与 open debit 合计函数均存在；F5b「不可用时 n/a 不阻塞」与 AC16 隔离自洽（实现须真正 try/except 包住）。

---

## 2. §3 四个自报薄弱点的裁定

### 2.1 F3 语义放宽——**符号已量化：当前账本下"方向保守可接受"成立、历史/情景成本 $0；但披露必须带数字，且有一处错误暗示要改**

数据源：`research/q091/q091_p0_snapshot.json`（2026-07-07 22:15 ET，本审计直接核过原始 JSON）：Schwab maint **$105,402.62** / NLV **$628,391.28**；E-Trade maint **$127,867.66** / NLV **$624,855.23**；现金合计 $152.3k；equity MV 合计 $1,036k；BCD（主策略）max loss **$76.6k**。

**今日读数与 allowance**（用 `q042_gate.py:68-79` 实际公式复算）：

| 口径 | main_bp 读数 | cap = min(12.5, max(0, 60−mb)) | Sleeve A allowance |
|---|---:|---:|---:|
| `pools.spx_pm_bp_pct`（all view，F3 拟用） | **18.61%** | 12.50% | **12.5% = $78.6k（零压缩）** |
| `pools_by_view.schwab` | 16.77% | 12.50% | 12.5%（零压缩） |

binding 门槛 = 读数 > 47.5%；完全阻断 ≥ 60%。距今日读数 **29–31pp**。

**packet 点名的"错误时刻压缩"场景核查**：恒定 haircut 下 equity 下跌方向**推不高**该比值——maint/NLV = m·E/(C+E) 对 E 单调递增（现金 $152k 垫分母），equity 缩水时读数**下降**；上升只经由 house haircut escalation。按 Q091 已批情景网格重算（期权按 long-spread 残值归零最坏处理）：ddATH −4%（触发区）≈19%、2022 阴跌 dd−25% ≈18.8%、2022+h1.5 ≈28.2%、2020 dd−34%+h1.5 ≈27.6%、**2008 dd−45%+h2.0 ≈35.5%（最恶格）**——全部 < 47.5%，**无一 binding**。当前账本结构下，F3 换口径对 overlay 的历史与情景成本 = **$0**，packet 担心的场景不存在。

**放宽真正的代价与校准漂移（必须写进披露，N5）**：
- 非主策略 maint floor（equity maint + ETrade 账户 maint）今日 = 233.3k − 76.6k(BCD) ≈ **$156.7k ≈ 12.5pp**（若 ETrade maint 含策略仓则下修，bracket 12.5–18.6pp）→ 60% 预算等效压缩为 **~41.4–47.5pp 的策略预算**。研究校准（`q042_tier2_p3_bp_gate.py`：trigger 日 main_bp 中位 2.8%/p75 3.5%/max 36.5%，19y gate firing rate=0%）里这个常数项不存在。
- 压缩实际出现的条件：defined-risk short-vol 部署 ≥ ~$238k（Q091 全可部署容量）+ dd−10%+h1.5 → 读数 ~51% → allowance 压至 ~9%；部署 ~$340k + 同 stress → ~60% → 全阻断。彼时 gate 收缩与其防 crowding 的设计目的同向，不算误伤——但 PM 若把 short-vol 站立推向 Q092 实测 peak ~48% 一带，研究口径 cap 剩 12% 而生产口径读数 ~60%+ → 全阻断。这是时代条件性差异，须知情。
- **披露文本错误暗示**：spec F3 写「若 PM 要求严格『SPX 期权 sleeve only』口径，改读 `pools_by_view.schwab.spx_pm_bp_dollars`」——**schwab view 同样是账户级 maint（今日 $105.4k 主要成分是 equity maint + BCD），不是 options-only**。runtime 里最接近 SPEC-094 字面口径的现成字段是 **`spx_live_bp_pct`**（`sleeve_governance.py:837`，SPX 期权书 BP / Schwab NLV），但其 provenance 是 Margin Allocation rail、错误时为 None、不含 ETrade 期权书。备选清单应如实改写（N5）。

**裁定**：披露方向（保守 = 读数只高不低、allowance 只小不大）符号正确；今日与全部 Q091 已批情景下量级为零；接受放宽的前提 = B1（封 silent-zero）、N5（带数字披露 + view 选择 PM ratify）、F5 blocked record（使未来过度压缩可测——spec 已含，认可）三件套。

### 2.2 F5 armed-consumption——**同意 1st Quant 的选择**

- 研究定义（`q042_ddath_full_scan.py` find_triggers_ddath；`signals/q042_trigger.py:149-152` 注释已固化）：首次 crossing 即事件。armed 不消耗 + 重试会制造回测 n=35 从未验证过的入场分布；METHODOLOGY §2 双判定标准下这是 execution-constraint 变更，须 head-to-head 显著优于现状才可改——没有这个证据。`feedback_short_dte_entry_signal_cannot_gate_forward` 同向。
- 漏单的正确解法 = 修 gate 数据源（F3）+ blocked record 可审计（F5），不是改 trigger 语义。组合正确。
- 衍生缺口（N7）：PM 收到 blocked 告警后若人工入场，`/api/q042/position/open`（`web/server.py:2692-2730`）**不回写** `q042_state.json` → `has_pos` 仍 False → 下次 fire 无 no-overlap 保护，可能双仓。F5 的设计主动邀请这种人工入场，spec 应给一句处理。

### 2.3 F1 结算顺序——**顺序设计与研究对齐，边界日无双动作 bug；真正风险是 state 副本覆写（N3）+ dry-run 交互（B6）**

- settle → 状态清理 → update_sleeve 与 walk-forward（:329-340）一致；expiry 当日结算（用当日 close，AC19 语义）+ 同日 re-fire 在研究里本就允许，非 bug。AC-94.2-3 只测 expiry=昨日，**应补 expiry=当日边界 case**。
- settle 内部 AC20 清理（`q042_positions.py:171-178`）与 F1 step-2 是幂等双清，常规路径无害。
- **边界风险（N3）**：settle 自带 load/save state，而 executor `:208` 已持内存副本、`:265` 末尾整体 save。若实现把 settle 放在 executor `load_state` 之后，settle 落盘的清理会被末尾旧副本覆写；step-2 会救回"state expiry ≤ today"的常规形态，但 **state expiry 与账本推导 expiry 分歧时**（手动 record 显式 expiry ≠ state 值）覆写变成真实回滚。spec 必须写明顺序约束（settle 先于 load_state，或 settle 后 re-load），step-2 同时按 settle 返回的 sleeve 列表清理。
- **1st Quant 完全未见的交互（B6）**：F1 把 settle 接进 `run_eod_evaluation` 后，`--dry-run` 也会执行 settle 的**真实落盘**（账本重写 + save_state），F4 只豁免了 executor 自身的三类副作用。dry-run 日恰有到期仓 → AC-94.2-5「q042_state.json 字节不变」必然违反、账本被真改。spec 未定义，必须补。

### 2.4 staleness 阈值 2 交易日——**给定 09:40 ET 日度 cadence，阈值合理；但它防错了轴**

- 写入节奏 repo 内可证（bot cron mon-fri 09:40 ET）：2 TD 容忍一次调度 miss，不至于因单日抖动 fail-closed；bot/daemon 停摆 2 TD → fail-closed + 3 日升级条款兜底。阈值本身无异议。
- 但 timestamp staleness 只防"daemon 死了"，防不了 §1-C6 的两条 silent-zero 通道（daemon 活着、读数悄悄归零）——那才是本系统三次前科的失效模式，见 B1。
- 附带披露（N13）：09:40 写、16:15 读 = ~6.5h 盘中偏差，崩盘日 EOD 保证金 >> 09:40 读数 → gate 偏松方向（fail-open 侧）。backstop 角色 + 12.5pp 不可压缩底仓下可接受，但 spec 应写明；部署清单应确认 old Air governance daemon/bot 存活（F3 使 Q042 新增对其的运维依赖）。

---

## 3. AC 层与 invariant 层其余核查

- **AC-94.2-1**：非 mock 设计正确（`feedback_spec_integration_test` 的正面回应）。两处必须补：(a) fixture timestamp 是静态的，staleness gate 会让该 AC 自落盘 2 TD 后永久红——须允许注入时钟/重写 fixture timestamp（维持禁 monkeypatch 返回值）（N1）；(b) 正向 fixture 必须为非 degraded 快照（`pools.nlv_basis > 0`），并配 B1 的两个反例 fixture。
- **AC-94.2-5**：断言集缺账本与 gate log → 并入 B6。
- **AC-94.2-7**：须钉死字段编码（并入 B2），否则 fixture 与实现可一起错 100 倍。
- **AC-94.2-8**：可执行。PCC 显示 schwab view（今日 16.77%）vs F3 all view（18.61%）差 1.8pp，rollback 的 10pp 阈值留有余量 ✓。
- **Invariants**：trigger/re-arm/sizing/DTE/cap 参数——F1–F6 不触碰 `q042_trigger.py` 常量、`q042_sizing.py`、`q042_config.py` ✓；AC16 隔离结构不变（:267-269）✓；gate 三函数全仓仅 executor 调用，F3 重写无涟漪 ✓；`q042_state.json` 字段语义——F6 是修复非破坏 ✓；**AC14 invariant 与 F5b 直接自相矛盾（B3）**。

---

## 4. 方法学条款对照

- METHODOLOGY §4「未量化 caveat 不作支撑」：F3 的"方向保守可接受"经本 review 量化补齐后成立；spec 披露段必须携带数字（N5），否则原措辞仍属未量化 caveat。
- METHODOLOGY §4「裸注记死信禁令」：B5（审计 #14 路由缺账 = 不合规第三态）。
- METHODOLOGY §3「今日尺度绝对值」：§2-3.1 全部以 2026-07-07 双 broker 实测绝对值报出 ✓。
- METHODOLOGY §6 Dev 行「非 mock 集成冒烟」：AC-94.2-1 合规；B1 把同一原则从"读的时候"延伸到"写的时候"（上游 writer 静默降级）——该类第 3 次出现，按 `governance_naked_note_death_sentence` 二次浮现标准，不修不放行。
- METHODOLOGY §2「事实先于 PnL」/§4「生产函数单一化」：C7 复用生产闸门常量语义 + Q092 基线复现 ✓；净额聚合错误（N4）不改方向但必须更正留痕。
- METHODOLOGY §7「约定契约进代码」：B2 的单位断言要求。
- `QUANT_RESEARCHER.md#short-premium-risk-management-principles`：本 spec 为 long-premium overlay 执行层、无 exit 层变更，不触发；F5 armed 决定与"entry-time gating 可用、forward gating 不可用"边界一致。
- Memory `feedback_semantic_selfcontradiction_flag`：B3 正是该 P0 形态。

---

## 5. 修订项清单

### Blocking（6 项，修完可批）

**B1 — F3 增加数据有效性/合理性谓词，封死两条 silent-zero fail-open 通道。** F3 第 3 点替换为：

> **fail-closed**：以下任一情形视为数据不可用 → 返回 `None`：缺文件；timestamp 距今 > 2 交易日；snapshot `status != "available"` 或 `errors` 非空；`basis_degraded: true`（**不引入 last-known 回退**——上次健康读数不能证明今日 BP）；`pools_by_view.schwab` 为 null 或 `pools` 缺 `nlv_basis`/`nlv_basis <= 0`（degraded 全零 fallback，`sleeve_governance.py:804-811`）；**`pools.spx_pm_bp_pct <= 0`**（plausibility gate：本账户 equity 常驻 QQQ/SGOV + BCD 在场，账户级 maint 结构性 >0——2026-07-07 实测 18.6%；读数为 0 只可能是上游 broker 字段静默缺失：`portfolio_surface.py:366-379` maint 可为 None → `sleeve_governance.py:750` `_num→0.0` 不进 errors 不降 basis）。executor 遇 `None` 时 allowance=0 并发 ACTION 告警。

配套 AC-94.2-2 增加两例：(a) degraded fixture（pools 全零 + pools_by_view 全 null + basis_degraded true + timestamp 新鲜——本机 2026-07-07 实测形态）→ 必须 fail-closed；(b) `spx_pm_bp_pct=0.0` 且 status "available"、timestamp 新鲜 → 必须 fail-closed。AC-94.2-1 正向 fixture 断言 `nlv_basis > 0`。

**B2 — F6 公式去掉 ×100、钉死单位契约、写明账本范围与 NLV fallback。** 替换文本：

> F6：`combined_bp_pct = Σ_active( (fill_debit or est_debit) × contracts ) / NLV × 100` 写回 `q042_state.json`。单位注记：账本 `est_debit`/`fill_debit` 均为**每张合约美元**（`q042_sizing.py:91` 已含 ×100；settle 端 `debit/_SPX_MULTIPLIER` 还原 per-share 为证），**不得再乘 multiplier**——现草案「× contracts × 100」会虚高 100 倍（1 张 $7,860 debit / NLV $629k 会写出 125% 而非 1.25%，把盲 monitor 修成尖叫 monitor）。NLV 取 `_fetch_nlv()`；NLV 不可得（=0）时跳过本次写入保留旧值（不写 0）。active 口径 = PAPER_LOG + LIVE_LOG 的未 settle 且未过期 open 记录（与 F1 同口径）；现状注记：`/api/q042/position/open` 无论 `paper_trade` 真假一律写 PAPER_LOG（`web/server.py:2476-2477`），LIVE_LOG 全仓零 writer——live 手动单目前落在 paper 文件内以 `paper_trade` 字段区分。
> AC-94.2-7 钉死编码：合成记录 `est_debit=25000, contracts=2`（$50k committed）、NLV $500k → `combined_bp_pct=10.0`。

**B3 — 解除 F5b 与 AC14 invariant 的自相矛盾。** 边界条件与 Handoff invariants 第 2 条同步替换：

> 不改 Telegram alert **既有字段与格式**（AC14 字段集保持）；F5b 在正文末尾**追加**一行现金上下文，构成 AC14 修订版（AC14.1，SPEC-094 AC14 记 amendment 注记），AC14 验收 fixture 同步更新。

**B4 — F2 增加 settle 事件过滤与缺字段容错。** F2 末尾追加：

> `settle_expired_positions` 与 `get_active_positions` 统一跳过 `event != "open"` 行（note 事件与交易记录同文件 `data/q042_paper_trades.jsonl`；现 settle 无过滤——`q042_positions.py:143-146` 对照 `:99-101`——note 行缺 `signal_date`/`entry_target_date` → `strptime("")` ValueError → 异常被 executor 最外层 except 吞掉，**当日整个 EOD 评估静默死亡**）；expiry 推导对缺失日期字段返回 None 跳过该行并 log warning，不抛异常。
> AC-94.2-3 的合成账本必须含 1 条 `event:"note"` 记录。

**B5 — 补齐审计路由 #14。** `doc/q042_aftermath_synergy_audit_2026-07-07.md` §4 明确路由「#1/2/3/11/12/13/**14** 修复包 → SPEC-094.2」；spec 覆盖了前六项，**#14（`get_current_q042_snapshot` 默认只拉 1mo、state 未初始化时 ddATH 失真，`signals/q042_trigger.py:234-245`，`daily_snapshot.py` 消费）既无 F 项也不在"不在范围内"清单**。按裸注记死信禁令二选一并写入 spec：(a) 增加 F7（snapshot 以 state `ath_running_max` 为 seed / 拉长 fetch 窗口 / state 缺失时显式标记 degraded）；或 (b) "不在范围内"列出 #14 + 理由 + 登记 `task/DEFERRED.md`。

**B6 — 定义 F1×F4 交互：dry-run 禁止 settle 落盘。** F4 追加：

> `--dry-run` 下跳过 F1 结算与状态清理的**落盘**（可对 deep-copy 推演并 stdout 报告 would-settle 明细）；dry-run 亦不追加 gate log（或写入带 `dry_run: true` 标记）、不写 blocked record。AC-94.2-5 的 hash 比对范围扩展至 `q042_paper_trades.jsonl`、`q042_live_trades.jsonl`、`q042_gate_log.jsonl`，且 fixture 必须含一笔已到期仓（否则该 AC 测不到本条）。

### Non-blocking（13 项，建议随修）

- **N1**：AC-94.2-1 注明允许注入时钟/重写 fixture timestamp 以过 staleness gate（维持禁 monkeypatch 返回值）——否则该 AC 落盘 2 TD 后永久红。
- **N2**：F5 对 Sleeve B 的 by-design 拦截（production cap=0，`q042_config.py:14`）单独处理：blocked record 照写（counterfactual 有值），告警降 FYI 并注明 `sleeve_b_production_cap_0_by_design`——否则每次 fire_B（~0.26/yr）都会拍一条要求人工核查的 ACTION。
- **N3**：F1 写明 settle 与 executor `load_state` 的顺序约束（settle 先行，或 settle 后 re-load state；禁止跨 settle 持有同一内存 state），step-2 清理同时接受 settle 返回的 sleeve 列表；AC-94.2-3 补 expiry=当日边界 case（当日结算 + 当日 re-fire 资格 + 断言 EOD 全流程后清理不被回滚）。
- **N4**：更正 `research/q093/q093_p1_findings_2026-07-07.md` §3 与 packet C7 净额：「GOV 净成本 = −$243,759（Q042 侧）− $37,338（主侧多挡 7 笔，ISO 下 Δ=0）= **−$281k**；$152k 池 overdraft=0，无被保护对象」。F5b 依据不受影响、反而加强。
- **N5**：F3 披露段写入本 review §2-3.1 量化数字（今日 18.61%/16.77%、binding 门槛 47.5%、Q091 全情景 ≤35.5% 不触及、非策略 maint floor ≈12.5–18.6pp → 等效策略预算 ~41.4–47.5pp、压缩仅在 defined-risk 部署 ≥~$238k+stress 出现）；**删除/更正**「`pools_by_view.schwab.spx_pm_bp_dollars` = SPX 期权 only」暗示（schwab view 仍是账户级 maint）；备选清单列入 `spx_live_bp_pct`（`sleeve_governance.py:837`，最接近 SPEC-094 字面口径，caveat：rail provenance、可为 None、不含 ETrade）；all-vs-schwab view 选择（今日差 1.8pp、ETrade 书增长会使 all view 因与 Schwab 主书无关的原因漂移）交 PM 显式 ratify。
- **N6**：F3 数据不可用 ACTION 与 F5 blocked_fire ACTION 同日同因时在 gateway dedupe key 层合并为一条；F3 告警用独立 dedupe key（现 trigger key = `q042_trigger_{sleeve}_{date}`，`q042_executor.py:109`）。
- **N7**：blocked 告警文案提示 PM：人工入场须经 `/api/q042/position/open` 记录**并同步 trigger state**（或该端点顺手回写 `active_position_id`/`active_position_expiry`，独立小改）——否则 no-overlap 保护对人工仓失效、可能双仓。
- **N8**：SPEC-094.1 §2.3「signal + 30」记 errata（真值 = entry+30，出处 R-20260510-15）；F2 文本引 R-20260510-15 为锚点出处。
- **N9**：settle 内部用 `date.today()`（`q042_positions.py:137`）而 executor 判定用数据日 `today_str`（yfinance 最后 bar）；F1 把 `today` 作为参数传入 settle 对齐（节假日/数据滞后错位）。
- **N10**：F6 文档注明 `combined_bp_pct` 命名冲突（q042_state.json = debit/NLV vs sleeve governance pools = maint/NLV，同名不同义不同文件）。
- **N11**：`settle_expired_positions` 的整文件重写（`q042_positions.py:165-169` `open("w")`）改用 `tempfile.mkstemp + os.replace`（同 `signals/q042_trigger.py:105-117` 模式，3 行改动）——账本是 6mo 评审唯一真值源，"首跑前备份"只保护第一次。
- **N12**：gate log 记录增加 `bp_source` 字段（数据源标识 + snapshot timestamp，可选同时记 schwab/all 双口径读数）——staleness/口径审计与 AC-94.2-8 溯源用。
- **N13**：部署核查补充：确认 old Air governance snapshot 写入方（bot 09:40 cron / daemon launchd）存活——F3 使 Q042 新增对其的运维依赖；spec 披露 09:40 写 / 16:15 读的 ~6.5h 盘中 skew（崩盘日读数偏低 → gate 偏松方向，backstop 角色下可接受）。

---

## 6. 遗漏项汇总（1st Quant 未见、本审计新增）

1. **F3 fail-closed 被两条 silent-zero 通道旁通**（B1）：degraded 全零 fallback（timestamp 新鲜）+ maint-None 静默零（status 仍 available）——最可能真实故障模式下 dead-gate 复活，本审计最重要的发现。
2. **F6 公式 100 倍单位错误**（B2）。
3. **F5b×AC14 自相矛盾**（B3）。
4. **settle 对 note 事件 crash → 整个 EOD 静默死亡**（B4）。
5. **审计 #14 路由缺账**（B5）。
6. **F1×F4 交互未定义：dry-run 仍会真实结算落盘**（B6）。
7. **账本单文件现实**：LIVE_LOG 全仓零 writer、`paper_trade`（手动端点）vs `paper`（executor）双编码并存——F1「两账本都扫」今日实际只有一本有数据，F6 不写明扫描范围会原样复现 C5（并入 B2）。
8. **Sleeve B expiry off-by-one**（C3 加重项）。
9. **Q093 findings §3 净额聚合错误**（−$207k 应为 −$281k，N4）。
10. **手动入场的 state/ledger split-brain 双仓风险**（N7）。
11. **Sleeve B by-design 拦截的 ACTION 误分级**（N2）。
12. **executor↔settle 的 state 副本覆写边界**（N3）与 **账本非原子重写**（N11）。

---
*Reviewer 独立验证记录：全部 file:line 于 2026-07-08 本地工作区（HEAD 4cef6b1）复核；今日读数来自 `research/q091/q091_p0_snapshot.json` 原始 JSON（本审计直接读取）；gate 算术用 `strategy/q042_gate.py`/`strategy/q042_config.py` 代码真值复算；C7 数字由 `research/q093/q093_p1_cash_stack.csv` 逐行复算。采信而未复核的仅两项：old Air 生产读数（audit §1，packet 约定）与 Q092 基线 107/107 复现声明，均已标注。*
