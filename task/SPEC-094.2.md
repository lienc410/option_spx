# SPEC-094.2: Q042 执行层完整性修复包（gate 字段链路 / 结算 wiring / 30 DTE 迁移收尾 / dry-run 语义）

> **Rev 2026-07-08**：吸收独立 2nd Quant 审计（PASS WITH REVISIONS，`task/SPEC-094.2_2nd_quant_review_packet_2026-07-07_Review.md`）全部 6 项 blocking（B1-B6）与 13 项 non-blocking 修订。

## 目标

修复 2026-07-07 协同审计（`doc/q042_aftermath_synergy_audit_2026-07-07.md`）发现的 Q042 生产执行层缺陷。不改变任何研究层参数（trigger 阈值、sizing 比例、DTE、cap 数值均不动）；只让已批准的 SPEC-094/094.1/104 语义真正在生产上成立。

生产实锤（old Air 2026-07-07）：`q042_gate_log.jsonl` 44/44 条 `main_bp_pct=0.0`（同期 live 有 BCD 仓）；`settle_expired_positions` 零调用方；`q042_paper_trades.jsonl` 不存在。

## 策略/信号逻辑

无策略逻辑变更。本 spec 全部为执行层 wiring / 数据链路修复。

## 接口定义（F1–F7）

### F1 — 结算 wiring

`production/q042_executor.py::run_eod_evaluation` 在推进状态机**之前**：

1. 调 `settle_expired_positions(spx_close, today=today_str, paper=...)`（paper/live 两账本都扫；账本现实见 F6 注记）。**N9**：`today` 以数据日 `today_str` 作参数传入 settle，替换其内部 `date.today()`（节假日/数据滞后错位对齐）。
2. 状态级到期清理：若 `state[sleeve]["active_position_expiry"] <= today` → 清 `active_position_id`/`active_position_expiry`（与 walk-forward `get_q042_history` 行为对齐）；同时接受 settle 返回的 sleeve 列表做幂等双清。

顺序敏感（**N3**）：settle **先于** executor 的 `load_state()`（或 settle 后 re-load state）——禁止跨 settle 持有同一内存 state 副本，否则 executor 末尾整体 `save_state` 会用旧副本覆写 settle 落盘的清理（state expiry 与账本显式 expiry 分歧时覆写即真实回滚）。清理必须在 `update_sleeve_a/b` 之前，否则到期日当天的 trigger 仍被 `has_pos` 挡掉。expiry 当日结算 + 当日 re-fire 是研究语义（walk-forward 一致），非 bug。

**N11**：`settle_expired_positions` 的整文件重写从 `open("w")` 改为 `tempfile.mkstemp + os.replace`（同 `signals/q042_trigger.py:105-117` 模式）——账本是 6mo 评审唯一真值源。

### F2 — positions 模块 expiry 修正（SPEC-094.1 收尾）

`production/q042_positions.py` 中 expiry 推导（`get_active_positions` 与 `settle_expired_positions` 共用）改为三级：

1. record 显式 `expiry` 字段（手动 open 端点必填，`web/server.py:2701/2715`）→ 直接用；
2. 否则 `entry_target_date + dte` calendar days（executor record 自 SPEC-094.1 起携带 `dte`：A=30 / B=90）；
3. 否则 legacy fallback `signal_date + 90`（仅为兼容历史空账本，实际不应命中）。

锚点出处 = **R-20260510-15**（expiry 从 entry T+1 + DTE 起算；SPEC-094.1 §2.3 表格字面 "signal+30" 未同步该修正，已记 errata——见 N8）。现硬编码 signal+90 对 Sleeve A 错 61 天、**对 Sleeve B 也错 1 天**（signal+90 vs entry+90=signal+91，2nd Quant C3 加重项），三级推导两者都修。

**B4 — 事件过滤与缺字段容错**：`settle_expired_positions` 与 `get_active_positions` 统一跳过 `event != "open"` 行（note 事件与交易记录同文件；现 settle 无过滤——`q042_positions.py:143-146` 对照 `:99-101`——note 行缺日期字段 → `strptime("")` ValueError → 被 executor 最外层 except 吞掉，**当日整个 EOD 评估静默死亡**）；expiry 推导对缺失日期字段返回 None 跳过该行并 log warning，不抛异常。

### F3 — gate BP 数据源 + fail-closed

`strategy/q042_gate.py::read_main_bp_pct` 重写：

1. **数据源**：读 `data/sleeve_governance_runtime.json` 的 `pools.spx_pm_bp_pct`（SPEC-103/118.2 canonical 口径：账户级 maintenance margin / NLV，由 bot cron mon-fri 09:40 ET `record_state_snapshot` 日度持久化）。不再读 position state 的 `bp_pct_account`（该字段在生产从不存在）。
2. **fail-closed（B1）**：以下任一情形视为数据不可用 → 返回 `None`：
   - 缺文件；
   - timestamp 距今 > 2 交易日；
   - snapshot `status != "available"` 或 `errors` 非空；
   - `basis_degraded: true`（**不引入 last-known 回退**——上次健康读数不能证明今日 BP）；
   - `pools_by_view.schwab` 为 null 或 `pools` 缺 `nlv_basis` / `nlv_basis <= 0`（degraded 全零 fallback 形态，`sleeve_governance.py:804-811`——timestamp 新鲜但 pools 全零，2026-07-07 本机决策日志实测存在）；
   - **`pools.spx_pm_bp_pct <= 0`**（plausibility gate：本账户 equity 常驻 QQQ/SGOV + BCD 在场，账户级 maint 结构性 >0，2026-07-07 实测 18.6%；读数为 0 只可能是上游 broker 字段静默缺失：`portfolio_surface.py:366-379` maint 可为 None → `sleeve_governance.py:750` `_num→0.0` 不进 errors 不降 basis_degraded）。
   executor 遇 `None` 时 **allowance=0 并发 ACTION 告警**（"Q042 gate 数据不可用，trigger 被保守拦截，请人工核查"）。替换现有 fail-open（`return 0.0` = gate 永不 binding）。
3. **N12**：gate log 记录增加 `bp_source` 字段（数据源标识 + snapshot timestamp；可选同时记 schwab/all 双口径读数），供 staleness/口径审计与 AC-94.2-8 溯源。

**语义放宽披露（N5，PM 须知，数字为 2026-07-07 双 broker 实测）**：R1 池口径（账户级 maint margin，含 equity margin）宽于 SPEC-094 F3 原文「main strategy BP」。今日读数 all view **18.61%** / schwab view **16.77%**，gate 公式下 Sleeve A allowance **全额 12.5%（零压缩）**；binding 门槛 = 读数 > 47.5%，完全阻断 ≥ 60%；Q091 已批全部 stress 情景重算（最恶 2008 dd−45%+haircut 2.0）读数 ≤ **35.5%**，**无一 binding**——恒定 haircut 下 equity 下跌拉低（非推高）该比值。真实代价：非主策略 maint floor 今日 ≈ **12.5–18.6pp** 不可压缩底仓 → 60% 预算等效为 ~41.4–47.5pp 策略预算；压缩仅在 defined-risk short-vol 部署 ≥ ~$238k（Q091 全容量）+ 深度 stress 时出现，彼时与 gate 防 crowding 目的同向。**备选口径如实清单**：`pools_by_view.schwab` 仍是账户级 maint（非 SPX 期权 only，今日与 all view 差 1.8pp）；最接近 SPEC-094 字面口径的现成字段是 `spx_live_bp_pct`（`sleeve_governance.py:837`，SPX 期权书 BP / Schwab NLV；caveat：provenance 为 Margin Allocation rail、错误时 None、不含 ETrade 期权书）。**all vs schwab view 的选择交 PM 显式 ratify**（ETrade 书增长会使 all view 因与 Schwab 主书无关的原因漂移）。

**N13**：09:40 写 / 16:15 读 = ~6.5h 盘中 skew，崩盘日 EOD 保证金 >> 09:40 读数 → gate 偏松方向；backstop 角色 + 12.5pp 不可压缩底仓下可接受，据实披露。部署清单须确认 old Air governance snapshot 写入方（bot 09:40 cron / daemon launchd）存活——F3 使 Q042 新增对其的运维依赖。

### F4 — dry-run 语义

`--dry-run` 下：不发 Telegram（改 log-only）、不 `save_state`（对 deep-copy 的 state 推演，含 ATH 推进）、不写 pending record；stdout 打印 would-fire 明细。现行为（照发、照存、`if sent or not dry_run` 照写记录）全部废除。

**B6 — F1×F4 交互**：`--dry-run` 下跳过 F1 结算与状态清理的**落盘**（可对 deep-copy 推演并 stdout 报告 would-settle 明细）；dry-run 亦不追加 gate log（或写入带 `dry_run: true` 标记的行）、不写 blocked record。

### F5 — blocked-trigger 告警 + 落盘

fire 发生但被拦（gate allowance=0 / F3 fail-closed / `contracts=0`，即 NLV<$200k 或 debit 过贵）时：

1. 发 ACTION Telegram（含 sleeve、ddATH、拦截原因、would-be sizing）。**N2**：Sleeve B 的 by-design 拦截（production cap=0，`q042_config.py:14`）降级为 FYI 并注明 `sleeve_b_production_cap_0_by_design`（blocked record 照写，counterfactual 有值）——否则每次 fire_B（~0.26/yr）都拍一条要求人工核查的 ACTION。**N6**：F3 数据不可用 ACTION 与 F5 blocked_fire ACTION 同日同因时在 gateway dedupe key 层合并为一条；F3 告警用独立 dedupe key（现 trigger key = `q042_trigger_{sleeve}_{date}`）。**N7**：blocked 告警文案提示 PM——人工入场须经 `/api/q042/position/open` 记录**并同步 trigger state**（`active_position_id`/`active_position_expiry`），否则 no-overlap 保护对人工仓失效、可能双仓（端点顺手回写 state 为可选独立小改，不在本 spec 强制范围）。
2. 追加 blocked record 至 `data/q042_gate_log.jsonl`（增字段 `blocked_fire: {sleeve, reason, would_be_contracts, ddath}`），供 counterfactual 追踪（对齐 sleeve governance blocked-candidate 惯例）。

**armed 语义保持不变**：fire 即消耗 armed（与研究 trigger 定义一致——首次 crossing 即事件；2nd Quant §2.2 同意：armed 不消耗 + 重试会制造回测 n=35 从未验证过的入场分布，且按 METHODOLOGY execution-constraint 标准无 head-to-head 证据不得改）。漏单的正确解法 = 修 gate 数据源（F3）+ blocked record 可审计（F5），不是改 trigger 语义。

**F5b — 触发告警现金上下文（Q093 P1 R-a）**：所有 Q042 trigger 告警（含正常 fire）正文追加一行当前现金上下文：`Liquid cash $X · 在场 debit 合计 $Y`（数据源 `strategy.cash_budget_governance`；不可用时该行显示 `n/a`，实现以 try/except 包住，不阻塞告警——AC16 隔离自洽）。依据：Q093 P1 重放否决了对 Q042 设现金闸门（GOV 情景净成本 **−$281k/19y**（Q042 侧 −$244k + 主侧多挡 7 笔 −$37k），今日池 overdraft=0 无可保护对象），顺序风险改由「PM 执行时看得见池余量」覆盖——零挡单。

**B3 — AC14 关系**：F5b 构成 **AC14 修订版（AC14.1）**：既有字段集与格式保持，正文末尾追加现金上下文一行；SPEC-094 AC14 记 amendment 注记，AC14 验收 fixture 同步更新。

### F6 — `combined_bp_pct` writer

executor EOD 末尾：`combined_bp_pct = Σ_active( (fill_debit or est_debit) × contracts ) / NLV × 100` 写回 `q042_state.json`。

**B2 — 单位契约（钉死）**：账本 `est_debit`/`fill_debit` 均为**每张合约美元**（`q042_sizing.py:91` 已含 ×100；settle 端 `debit/_SPX_MULTIPLIER` 还原 per-share 为证），**不得再乘 multiplier**——初稿「× contracts × 100」会虚高 100 倍（1 张 $7,860 debit / NLV $629k 会写出 125% 而非 1.25%，把盲 monitor 修成尖叫 monitor）。NLV 取 `_fetch_nlv()`；NLV 不可得（=0）时**跳过本次写入保留旧值**（不写 0）。

active 口径 = **PAPER_LOG + LIVE_LOG** 的未 settle 且未过期 open 记录（与 F1 同口径）。**账本现实注记**：`/api/q042/position/open` 无论 `paper_trade` 真假一律写 PAPER_LOG，LIVE_LOG 全仓零 writer——live 手动单目前落在 paper 文件内以 `paper_trade` 字段区分（executor 记录用 `paper` 字段，双编码并存）；不写明扫描范围会原样复现 C5。

**N10**：文档注明命名冲突——`q042_state.json.combined_bp_pct`（debit/NLV）与 sleeve governance `pools.combined_bp_pct`（maint/NLV）同名不同义不同文件。

### F7 — snapshot ATH 稳健性（审计 #14，B5 补账）

`signals/q042_trigger.py::get_current_q042_snapshot`：ATH 以 state `ath_running_max` 为 seed（state 缺失/为 0 时**显式标记 degraded** 而非静默用 1 个月窗口最高价冒充 ATH）；默认 fetch 窗口拉长以覆盖展示需要，但 ATH 真值源 = state（executor 日度维护）。`daily_snapshot.py` 消费端遇 degraded 标记时记 warning 不记数。

## 边界条件与约束

- 不改 trigger 阈值 / re-arm / sizing 比例 / DTE 参数 / cap 数值（12.5/17.5/0）。
- Telegram alert **既有字段与格式**保持（AC14 字段集）；F5b 为 AC14.1 追加行 amendment（B3）。
- AC16 保持：Q042 executor 异常不得影响主策略流程。
- F1 结算首跑前备份 `q042_state.json` 与账本文件（rollback 用）；N11 原子写为持续保护。
- 账本当前为空（生产核实）：F1/F2 对存量数据是 no-op，无迁移风险；grandfather 仓 PM 补录后 F2/B4 路径即被真实数据覆盖。

## 不在范围内

- Q042 纳入 SPEC-111 现金治理 universe（Q093 P1 已否决 gate 形式，F5b 为替代）。
- stress flag live 对齐（`_latest_market_stress` 加 ddATH 条件）——独立小 spec 候选。
- ladder `q042_active` 接线——SPEC-108.2。
- Sleeve A TP/stop——2027-05 Tier 4 review。
- Sleeve B 任何变更；`/api/q042/position/open` 回写 trigger state（N7 可选独立小改）。

## Prototype
（无——纯执行层 wiring，逻辑以 AC 验收）

## Review

- **Spec 层**：独立 2nd Quant 审计 PASS WITH REVISIONS（2026-07-08）；6 blocking（B1-B6）+ 13 non-blocking（N1-N13）已全部吸收。审计报告：`task/SPEC-094.2_2nd_quant_review_packet_2026-07-07_Review.md`。**PM APPROVED 2026-07-08**。
- **实施层（Quant fidelity review 2026-07-10）：结论 PASS**
  - AC-94.2-1..9 全 PASS（22 tests，Quant 亲跑复核）；AC-8 生产人工核查半句留部署清单。
  - 相邻回归：Developer 全量 201+ passed（新 HEAD 4691f66 重验，SPEC-137/138 交互面逐一核清）；Quant 抽验 test_spec_104/111 = 47 passed、server 面 135_3+state_and_api = 29 passed。
  - Invariant 核查：trigger 常量/`update_sleeve_a/b` 状态机/`compute_gate` 公式/`_format_alert` 字段集/sizing/DTE/cap——diff grep 零命中 ✓。
  - **真实数据对数（Developer 无法执行项，Quant 补做）**：old Air 2026-07-10 09:40 runtime.json → `read_main_bp_detail()` 全链路正确（value=15.78%、provenance/timestamp 齐备、无 fail-closed），`compute_gate(15.78)` → allowance 12.5 不 binding——dead gate 修活实证。
  - AC-9 消费端缺口（handoff §④-1）：裁决为 spec 文件清单 clerical 漏列，2026-07-10 修订清单 + 授权补完；null ddath 下游兼容核查通过（journal/图表全 null-safe）。
  - Developer 判断取舍 §④ 共 11 条逐条复核，全部认可（含 F7 fallback=spx_close 中性归零、B6 选完全不追加、F3 unavailable 行保台账连续）。
  - handoff：`task/SPEC-094.2_handoff.md`。

## 验收标准

| AC# | 描述 | 验证 |
|---|---|---|
| AC-94.2-1 | F3 integration smoke（非 mock）：以 old Air 实际 `sleeve_governance_runtime.json` 为 fixture（**断言 `pools.nlv_basis > 0` 的非 degraded 快照**），`read_main_bp_pct()` 返回其 `pools.spx_pm_bp_pct` 值（>0） | pytest + fixture 文件；**禁止** monkeypatch 返回值。**N1**：允许注入时钟/重写 fixture timestamp 以过 staleness gate（否则落盘 2 TD 后永久红） |
| AC-94.2-2 | F3 fail-closed 三例：(a) 缺文件/stale >2TD；(b) **degraded fixture**（pools 全零 + pools_by_view 全 null + basis_degraded true + timestamp 新鲜——2026-07-07 本机实测形态）；(c) **`spx_pm_bp_pct=0.0` 且 status "available"、timestamp 新鲜** → 三例均须 executor 拦截 fire + ACTION 告警 + blocked record | pytest 时钟/文件注入 |
| AC-94.2-3 | F1：构造 expiry=昨日的合成账本（**必须含 1 条 `event:"note"` 记录**，B4）+ state → EOD 跑后 settled=true、`active_position_id=null`、当日 trigger 可正常 fire；**补 expiry=当日边界 case**（当日结算 + 当日 re-fire 资格 + 断言 EOD 全流程后清理不被 state 副本回滚，N3） | pytest 端到端 |
| AC-94.2-4 | F2：Sleeve A record（dte=30）expiry = entry+30；**Sleeve B record（dte=90）expiry = entry+90（修 off-by-one）**；带显式 `expiry` 的手动 record 以其为准 | pytest |
| AC-94.2-5 | F4：`--dry-run` 跑后 `q042_state.json`、**`q042_paper_trades.jsonl`、`q042_live_trades.jsonl`、`q042_gate_log.jsonl`** 字节不变（或 gate log 仅含 `dry_run:true` 标记行）、无 Telegram 调用、无 pending record；**fixture 必须含一笔已到期仓**（否则测不到 B6） | pytest + 文件 hash 前后比对 |
| AC-94.2-6 | F5：gate=0 场景 fire → gate log 出现 `blocked_fire` 记录 + ACTION 告警 1 次；fire_B 场景 → blocked record + **FYI 级**告警（N2） | pytest |
| AC-94.2-7 | F6 **编码钉死（B2）**：合成记录 `est_debit=25000, contracts=2`（$50k committed）、NLV $500k → `combined_bp_pct=10.0`；NLV=0 → 跳写保留旧值；`/api/q042/state` monitor 反映之 | pytest + API 冒烟 |
| AC-94.2-8 | 部署后 old Air 首个交易日：gate log `main_bp_pct` > 0 且 `bp_source` 携带 snapshot timestamp（当前有 BCD 仓，maint margin 非零；PCC schwab view 16.77% vs F3 all view 18.61%，差 1.8pp 在 rollback 10pp 阈值内） | 人工核 `tail -1 q042_gate_log.jsonl` |
| AC-94.2-9 | F7：state 缺失/ath=0 时 snapshot 返回 degraded 标记（不再用 1mo 窗口最高价冒充 ATH）；daily_snapshot 消费端 warning 不记数 | pytest |

## Handoff Contract

1. **What changes**：`production/q042_executor.py`（F1/F4/F5/F5b/F6）、`production/q042_positions.py`（F2/B4/N9/N11）、`strategy/q042_gate.py`（F3/N12）、`signals/q042_trigger.py`（F7，仅 snapshot 函数）、`web/server.py`（仅 `/api/q042/state` 序列化 `ath_degraded`，字段只增）、`scripts/daily_snapshot.py`（F7 消费端：degraded 时 warning 不记数）；`q042_gate_log.jsonl` schema 追加可选 `blocked_fire`/`bp_source`/`gate_available` 字段。
   *（Rev 2026-07-10 clerical 补正：初版清单漏列 F7/AC-9 消费端所需的后两个文件，与 F7 规范文本内部矛盾——Developer handoff §④-1 抓出。规范内容不变，仅文件清单补齐。）*
2. **Invariants**：trigger/re-arm/sizing/DTE/cap 参数；alert 既有字段集（AC14→AC14.1 追加行 amendment）；AC16 隔离；`q042_state.json` 既有字段语义；web API 既有字段（只增不改）；`update_sleeve_a/b` 状态机逻辑一行不动。
3. **Acceptance checks**：上表 AC-94.2-1..9（正向：AC-3 到期次日/当日可 re-fire；边界：AC-2 三例 fail-closed）。
4. **Out of scope**：见上节。
5. **Failure / rollback**：部署后首个 EOD 若 executor 异常、或 AC-94.2-8 读数与 Portfolio Command Center BP 明显矛盾（>10pp）→ 回滚 commit + 恢复备份 state；F3 告警连续 3 日触发（数据源持续不可用）→ 回 Quant 复核数据源选择（含 old Air snapshot 写入方存活核查，N13）。

## PM ratify 项（APPROVED 确认，2026-07-08）

1. F3 口径选择：**已定 = `pools.spx_pm_bp_pct`（all view）**。理由：canonical 单源；审计确认备选 schwab view 同样是账户级 maint（含 equity），并无它宣称的 "SPX 期权 only" 语义优势，故 all view 是唯一有意义的默认。Developer 按 all view 实施；若未来 ETrade 期权书显著增长导致 all view 漂移，另开小改切 `spx_live_bp_pct`（不在本 spec 范围）。
2. F3 语义放宽披露：**PM 已读接受**（binding 门槛 47.5%、今日 18.61%、Q091 全情景 ≤35.5% 零压缩、非策略 maint floor ≈12.5-18.6pp）。

---
Status: DONE


---

## Grandfather 仓补录 — 已裁决注销（2026-07-11）

PM 确认（原话）："我还没有手动做过 DD overlay。" → grandfather 仓 = **空集**，补录项注销。

**三重证据补强（2026-07-11，Quant 核查）**：① 主账本最早记录 2026-05-04，全账本零 2026-03 行；② Schwab 现仓 SPX 期权计数 = 0（无 3 月残留仓）；③ PM 亲口确认。**⚠ 向审计 lane 标记**：synergy audit（doc/q042_aftermath_synergy_audit_2026-07-07.md L20）中"grandfather 仓（2026-03-12，部署前人工开）"系**无出处断言**——任何可触达真值源均无此仓，违反叙事纪律（标"实际"的事实须引账本行）。请该 lane 更正审计文档或提供出处。

含义修正：Q042 账本历史从 2026-07（094.2 修活 gate）起算，11 月 6mo 评审的 n 来源 = 自动 paper 流水（7-11 月约 4 个月），非 grandfather 补录。评审时账本起点即机器诞生点，无历史缺口需解释。
（记录人：Quant 主会话，PM 委托执行链内；另一会话 standing 清单中的对应项可据此关闭。）


## AC-8 提前实质核查 + 周一形式核查预警（2026-07-11，Quant）

**实质已核**（PM"数据处理不等未来验收"指令）：oldair dry-run（venv 解释器）→ `gate: main_bp=15.8% cap=12.5% src=sleeve_governance_runtime.pools.spx_pm_bp_pct(all)`——新代码全链路真实 BP + 来源归因确认（对照死门裸 0.0）。

**⚠ 周一（7/13）形式核查预警**：原 AC-8 期望 "main_bp_pct > 0"，但**全部 SPX 仓位已于 7/10 平掉**——若 PM 周一未开新仓，周一 09:40 快照刷新后 16:15 gate log 将写 **main_bp≈0.0 是真值**（书面平仓），不是死门复发。正确判据改为：**`bp_source` 字段存在**（新代码必写）且数值追踪现实（有仓>0/无仓=0）。勿把 true-zero 误读为 dead-zero。（本次 dry-run 的 15.8% 系周六读周五 09:40 快照的滞后值，周一刷新后消失，亦属正常。）


## Grandfather 终章（2026-07-11 深夜，全线关闭）

出处凿实：2026-03-12 = paper 模拟触发（RESEARCH_LOG R-20260510-15），"grandfather"=参数迁移豁免术语，审计"人工开"系措辞错误（勘误已入 synergy audit 附录）。paper 仓已补录+生产结算：`A-2026-03-12-002` exit_pnl +$16,329（6mo 评审首个样本就位，n=1 而非 0）。首版补录单位错误已 phantom 留痕。**PM 空集声明与全部事实一致；无人再欠任何动作。**
