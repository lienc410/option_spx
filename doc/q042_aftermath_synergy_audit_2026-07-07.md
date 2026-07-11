# Q042 × Aftermath × 主策略协同审计

**Date**: 2026-07-07
**Owner**: Quant Researcher
**Status**: 审计完成；old Air 生产核查完成；后续路由 = SPEC-094.2 (DRAFT) + Q093 (charter) + 低优先 backlog
**Scope**: 主策略（selector 短 vol 书）与两个分策略——Aftermath（SPEC-064/100，HIGH_VOL 余波 V3-A broken-wing IC 特批通道）、DD Overlay（Q042/SPEC-094/094.1/104，双 sleeve 长 call spread）——的生产层协同机制与各自实现完整性。

---

## 0. 一句话结论

研究设计层扎实（Q062/Q064-Q066/Q070/Q072 均有外审），但**生产实现层的协同机制有三处断裂**（联合 BP gate 死值、结算链路零调用、SPEC-094.1 迁移漏改结算模块），另有一个组合层现金缝隙（Q042 debit 不在任何治理范围内，单笔 ≈ 半个 liquid cash pool）。

## 1. old Air 生产核查结果（2026-07-07）

| 核查项 | 结果 | 含义 |
|---|---|---|
| `data/q042_gate_log.jsonl` | **44/44 条 `main_bp_pct: 0.0`**（部署至今全量），同期 live 有 2 笔 BCD $38.3k/笔在场 | dead gate **生产实锤**：F3 联合 BP gate 从未见过真实 BP |
| `data/q042_state.json` | sleeve A/B 均 armed=true、无挂仓；ath_running_max=7537.43 日更 | executor 每日 16:15 正常跑（launchd `com.spxstrat.q042_executor`）；**部署以来从未 fire**（ddATH -0.91%），故 AC20 断裂后果尚未发生——但一旦 fire 即永久卡死 |
| `data/q042_paper_trades.jsonl` | **文件不存在** | 部署以来 0 笔入账；grandfather 仓（2026-03-12，部署前人工开）从未进账本；**2026-11-10 6mo 评审样本积累 = 0** |
| executor log NLV | Schwab NLV ≈ **$629k**（2026-07-07） | Sleeve A Stage 1 debit = 12.5% × $629k ≈ **$78.6k**（修正初版审计按 $1.25M 合并口径的高估） |

## 2. 发现清单

### P0 — 协同机制断裂（code-confirmed + 生产实锤）

1. **Q042 F3 联合 BP gate 死值**。`strategy/q042_gate.py:98-115` `read_main_bp_pct()` 读 `positions[0].get("bp_pct_account", 0.0)`，但主策略开仓 `state_payload`（`web/server.py:5406`）从不写该字段（全仓无 writer；字段只存在于回测 CSV）。恒 0 → cap 恒 12.5% → 永不 binding。AC9-11 仅 unit-test 公式，未 integration-test 字段链路（`feedback_spec_integration_test` 模式复发，SPEC-089/094 `net_liquidation` 之后第三例）。exception fallback 0.0 = fail-open，与 SPEC-118.2 fail-closed 哲学相反。
2. **结算链路零调用**。`production/q042_positions.py:131` `settle_expired_positions` 无任何 caller（代码/launchd/scripts/文档穷尽 grep）；executor EOD 亦不做到期清理（walk-forward `get_q042_history` 有，live 无）。后果：到期不结算 → lifetime stats 永空 → 6mo 评审无数据机制；AC20 永不执行 → fire 一次后 `has_pos` 永真 → sleeve 永久静默失效。
3. **SPEC-094.1 迁移不完整**。`q042_positions.py:82-84` `_expiry_from_signal` 对两个 sleeve 硬编码 signal+90：Sleeve A 应为 entry+30（DTE 错 + 锚点错，R-20260510-15 修的正是锚点）；手动 open 端点记录的 `expiry` 字段被无视。

### P1 — 协同设计缺口

4. **Q042 现金占用零治理覆盖**（cash-bound 账户）。不在 SPEC-111/115 `CASH_OCCUPYING_STRATEGIES`；不走 sleeve governance；long spread PM 维持保证金 ≈ 0 → R1/R3/R4 池不可见。**今日绝对值**：单笔 ≈ $78.6k ≈ 52% × $152k liquid pool；与两笔 live BCD（$76.6k）并发即穿 SPEC-111 60% cap 语义。触发时点（ddATH ≤ -4%）与 BCD stop/roll、aftermath 入场现金需求同窗。Q092 reaudit ④「合成栈自洽」未覆盖此角。
5. **Q066 standing trigger 已触发未执行**。Q066（2026-05-12 CLOSED）承诺 cap 上调 / paper→live 即启动 co-fire 深研；5 天后 SPEC-104 同时满足两条件，未启动。且 escalation hook 指向的编号 Q067 已被 IVP jitter 研究占用并关闭。新证据（Q072 P3.3）：HV-heavy 日 aftermath × dd_overlay 日 PnL 相关 **+0.26（同向）**、post-2020 co-loss lift 2-6x、Greek 反向假设在 HV-heavy 不成立。
6. **stress episode live 定义窄于研究定义**。研究口径（`sleeve_governance.py:238-247`）含 `dd_overlay_active | aftermath_active`；live `_latest_market_stress`（:405-455）只有 vix≥22 / dd_20d / dd_60d。aftermath 情形基本被 vix≥22 覆盖（selector 仅 HIGH_VOL 分支激活）；dd_overlay 情形不然（慢磨 ddATH -5% 而 dd_60d > -4%、VIX<22 时研究进 stress cap 50%，live 不进）。
7. **Ladder `q042_active` 硬编码 False**（`sleeve_governance.py:675/915`）。shadow 数据里 q042 overlap 字段全假；Stage 2 前必须接线（并入 SPEC-108.2 backlog），否则「BCD + Q042 long-gamma 联合暴露监控」无数据。

### P2 — 分策略自身

8. **Aftermath gate 不对称**：NEUTRAL 分支查 backwardation（`selector.py:925`），BEARISH 分支不查（:789）——V3-A 双边卖，BEARISH+倒挂时 put wing 照卖。需 fact-check 或注释固化为有意结论。
9. **Aftermath 二次上升窗口**：`is_aftermath` 只看距 10 日峰 ≥10% off，second-spike（peak 40→32→反弹 35.9）仍入场卖双边；Q072 实证 second-leg 正是 aftermath 失效场景，中间地带仅剩 R6 保护。
10. ~~`is_aftermath` docstring 漂移（5% vs 0.10）~~ — **已修**（Fast Path，`selector.py:384-388`，2026-07-07）。
11. **executor dry-run 不 dry**：`run_eod_evaluation(dry_run=True)` 照发 Telegram、照 `save_state`、telegram 成功时照写 pending record（`if sent or not dry_run`）。每次 AC 验证污染生产状态机。
12. **gate/sizing 拦截静默吞 trigger**：fire 时 armed 即消耗；allowance=0 或 contracts=0 时无告警无记录，需 ddATH 回 -2% 重新 arm。研究基线假设全部入场；live 漏单无 counterfactual。
13. **`combined_bp_pct` 无 writer**：恒 0，`/api/q042/state` cap utilization monitor（`server.py:2239`）永远 "ok"——SPEC-104 该日检 monitor 是盲的。
14. **snapshot ATH fallback 脆弱**：`get_current_q042_snapshot` 默认仅拉 1 个月，state 未初始化时 ddATH 失真；`daily_snapshot.py` 消费此值。
15. （确认维持）Sleeve A hold-to-expiry 无 TP/stop 为已知 MVP 决定，30 DTE 后机会成本已减，维持至 2027-05 Tier 4 review。

## 3. 协同叙事修正

「DD Overlay 对冲短 vol 书」叙事**降级**：Q066 结论仅为 low-overlap / non-redundant（0.9% 日重叠，外审已否 "fully orthogonal" 措辞）；Q072 P3.3 显示 HV-heavy 日两者同向亏（+0.26）。Sleeve A 是 bullish reversal bet 非 crash hedge；second-leg 中与 aftermath 同亏且同时抽现金。组合层正确读法：**两个独立 alpha，共享尾部**——资本与现金治理按此配置，不按对冲叙事放松。

## 4. 路由

| 项 | 载体 | 状态 |
|---|---|---|
| #1/2/3/11/12/13/14 修复包 | `task/SPEC-094.2.md` | DRAFT 已起草（本日） |
| #4 现金耦合量化 + #5 co-fire 欠账 | `research/q093/` charter | **P1 已 CLOSED（本日）**：SPEC-111 纳入方案被重放否决（GOV 净成本 −$281k/19y：Q042 侧 −$244k + 主侧多挡 7 笔 −$37k；今日池 overdraft=0 无可保护对象——净额经 2nd Quant N4 更正）；今日池 + 引擎 sizing 下现状零透支；改为 SPEC-094.2 F5b alert 现金上下文 + 池水位 ≥$150k 规则（live BCD 1.7x sizing 下例外——见 findings §2B）。P2 co-fire 待做 |
| #6 stress flag live 对齐 | 小 spec 候选（或并入 SPEC-094.2 视 PM） | backlog |
| #7 ladder 接线 | SPEC-108.2（Stage 2 前置） | backlog（已有 mutex 单向项同池） |
| #8/9 aftermath 分层 fact-check | Q093 P3（可选尾巴）或独立小研究 | backlog |
| grandfather 仓补录 | PM 经 `/api/q042/position/open` 手动 backfill（含 exit_pnl） | 操作项，否则 6mo 评审 n=0 |

## 5. Confidence / 边界

- P0 三条：code-confirmed + 生产日志实锤（gate log 44/44 全 0）。
- #4 量级：基于 executor 实测 Schwab NLV $629k 与 Q092 实测池 $152k；若 PM 后续把 sizing 基数改为其他口径需重算。
- #6/#9 为设计层缺口，未做反事实 PnL 量化——按宪法「事实先于反事实」，量化归 Q093/backlog，不在本审计给方向性结论。


---

## 勘误：grandfather 仓（2026-07-11，Quant 终审结案）

原文 L20"grandfather 仓（2026-03-12，**部署前人工开**）"措辞错误。凿实的出处（RESEARCH_LOG R-20260510-15 / L1006-1025）：

- 2026-03-12 = Sleeve A **模拟触发日**（ddATH −4.38%，走查引擎确认，long 6675/short 7005/debit $166.71 每股）——**paper 仓，非人工实仓**（主账本、Schwab 现仓、PM 本人三重证据均无实仓）
- "grandfather" 系 SPEC-094.1 参数迁移术语：5/10 换参数时该在飞旧参数 paper 仓被豁免至 6/11 自然到期，非"人工开"
- 到期时结算链未活（本审计 P0-2 所指缺陷），故到期失记——即 6mo 评审缺的那个样本

**处置（已完成）**：paper 仓已按引擎口径补录并用 094.2 修活的生产结算函数结算——`A-2026-03-12-002`，exit_pnl **+$16,329**（SPX 6/11 收盘 7394.30，双腿深 ITM 满宽结算；与独立手算一致）。首版补录（-001）因 fill_debit 单位错误（每股 vs 总美元）已 phantom 废弃留痕。**PM 无任何待办；本项全线关闭。**
